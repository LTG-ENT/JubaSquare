"""Iter27 backend tests — seller-defined SECTIONS + time-limited PROMO.

Covers:
- PUT /api/restaurants/{id} menu_sections persistence, sanitisation, max-6 enforcement.
- PUT /api/shops/{id} product_sections persistence, sanitisation, max-6 enforcement.
- POST/PUT /api/menu-items with menu_section_id + promo persist and roundtrip.
- POST/PUT /api/products with product_section_id + promo persist.
- Server-side effective_price_usd enforcement on POST /api/restaurant-orders:
    * percent promo → discounted subtotal (bypasses client-sent price)
    * amount promo → discounted subtotal
    * date-window not-yet-active promo → raw price
    * date-window expired promo → raw price
    * active=False promo → raw price
    * negative-safety (amount > price) → 0.0 subtotal
- Server-side effective_price_usd enforcement on POST /api/orders (marketplace).
- Regressions: /api/odoo/health, admin login, seller analytics.by_channel,
  /api/odoo/kitchen/accept, /api/restaurants/{id}/menu with iter25/26 fields.
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

RUN_TAG = f"TEST_iter27_{uuid.uuid4().hex[:8]}"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    d = client[DB_NAME]
    yield d
    for coll in [
        "users", "shops", "restaurants", "products", "menu_items",
        "orders", "restaurant_orders", "seller_order_splits",
        "exchange_rates", "categories",
    ]:
        d[coll].delete_many({"id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"email": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"seller_id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"shop_id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"restaurant_id": {"$regex": f"^{RUN_TAG}"}})
    d.odoo_service_tokens.delete_many({})
    d.odoo_sync_logs.delete_many({"kind": "kitchen_action"})
    client.close()


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    from requests.cookies import RequestsCookieJar

    class BlockingJar(RequestsCookieJar):
        def set_cookie(self, cookie, *a, **kw):
            return None
    s.cookies = BlockingJar()
    return s


@pytest.fixture(scope="module")
def admin_headers(api):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": "admin@jubasquare.com", "password": "1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}",
            "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def seller_ctx(api, admin_headers, db):
    seller_email = f"{RUN_TAG}_seller@example.com".lower()
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/admin/users", headers=admin_headers, json={
        "email": seller_email, "name": f"{RUN_TAG} Seller", "role": "seller",
        "password": password, "phone": "+211900000001", "email_verified": True,
    })
    assert r.status_code == 200, r.text
    seller_id = r.json()["user"]["id"]
    lr = api.post(f"{BASE_URL}/api/auth/login",
                  json={"email": seller_email, "password": password})
    assert lr.status_code == 200, lr.text
    tok = lr.json()["token"]
    return {"id": seller_id, "email": seller_email, "token": tok,
            "headers": {"Authorization": f"Bearer {tok}",
                        "Content-Type": "application/json"}}


@pytest.fixture(scope="module")
def customer_ctx(api, db):
    email = f"{RUN_TAG}_cust@example.com".lower()
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "name": f"{RUN_TAG} Cust",
        "password": password, "phone": "+211900000002",
    })
    assert r.status_code == 200, r.text
    db.users.update_one({"email": email}, {"$set": {"email_verified": True}})
    lg = api.post(f"{BASE_URL}/api/auth/login",
                  json={"email": email, "password": password})
    assert lg.status_code == 200, lg.text
    tok = lg.json()["token"]
    return {"id": lg.json()["user"]["id"], "email": email, "token": tok,
            "headers": {"Authorization": f"Bearer {tok}",
                        "Content-Type": "application/json"}}


@pytest.fixture(scope="module")
def food_category_id(db):
    cid = f"{RUN_TAG}_cat_food"
    db.categories.insert_one({
        "id": cid, "name": "TestFood", "slug": f"{RUN_TAG}_food",
        "group": "restaurant", "created_at": _now(),
    })
    return cid


@pytest.fixture(scope="module")
def shop_category_id(db):
    cid = f"{RUN_TAG}_cat_shop"
    db.categories.insert_one({
        "id": cid, "name": "TestShopCat", "slug": f"{RUN_TAG}_shopcat",
        "group": "shop", "created_at": _now(),
    })
    return cid


@pytest.fixture(scope="module")
def restaurant_id(db, seller_ctx):
    rid = f"{RUN_TAG}_rest_main"
    db.restaurants.insert_one({
        "id": rid, "seller_id": seller_ctx["id"],
        "name": "TEST_Rest27", "area": "Juba",
        "is_open": True, "is_deleted": False,
        "verification": "Verified",
        "delivery_managed_by": "seller",
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "menu_sections": [],
        "created_at": _now(),
    })
    return rid


@pytest.fixture(scope="module")
def shop_id(api, seller_ctx, shop_category_id, db):
    payload = {
        "name": "TEST_Shop27", "area": "Juba", "category": "gen",
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
    }
    r = api.post(f"{BASE_URL}/api/shops", headers=seller_ctx["headers"], json=payload)
    assert r.status_code in (200, 201), r.text
    sid = r.json()["id"]
    # Rename id to be RUN_TAG-prefixed for cleanup
    new_id = f"{RUN_TAG}_{sid}"
    db.shops.update_one({"id": sid}, {"$set": {"id": new_id}})
    return new_id


def _restaurant_put_payload(**overrides):
    base = {
        "name": "TEST_Rest27",
        "area": "Juba",
        "is_open": True,
        "delivery_mode": "free",
        "delivery_fee_usd": 0.0,
        "menu_sections": [],
    }
    base.update(overrides)
    return base


def _shop_put_payload(**overrides):
    base = {
        "name": "TEST_Shop27",
        "area": "Juba",
        "delivery_mode": "free",
        "delivery_fee_usd": 0.0,
        "product_sections": [],
    }
    base.update(overrides)
    return base


# =========================================================================
# 1) Restaurant menu_sections
# =========================================================================
class TestRestaurantMenuSections:
    def test_put_persists_and_roundtrips(self, api, seller_ctx, restaurant_id):
        body = _restaurant_put_payload(menu_sections=[
            {"id": "s1", "name": "Starter", "sort_order": 0},
        ])
        r = api.put(f"{BASE_URL}/api/restaurants/{restaurant_id}",
                    headers=seller_ctx["headers"], json=body)
        assert r.status_code == 200, r.text
        assert r.json()["menu_sections"] == [
            {"id": "s1", "name": "Starter", "sort_order": 0}
        ]
        g = api.get(f"{BASE_URL}/api/restaurants/{restaurant_id}")
        assert g.status_code == 200
        assert g.json()["menu_sections"] == [
            {"id": "s1", "name": "Starter", "sort_order": 0}
        ]

    def test_put_rejects_more_than_6(self, api, seller_ctx, restaurant_id):
        sections = [{"id": f"s{i}", "name": f"Sec{i}", "sort_order": i} for i in range(7)]
        r = api.put(f"{BASE_URL}/api/restaurants/{restaurant_id}",
                    headers=seller_ctx["headers"],
                    json=_restaurant_put_payload(menu_sections=sections))
        assert r.status_code == 400, r.text
        assert "maximum 6 menu sections" in r.text.lower()

    def test_put_sanitises_sections(self, api, seller_ctx, restaurant_id):
        raw = [
            {"id": "a", "name": "  Trimmed  ", "sort_order": "5"},
            {"id": "b", "name": "", "sort_order": 0},          # empty name → drop
            {"id": "a", "name": "Dup id", "sort_order": 1},    # dup → drop
            {"id": "c", "name": "X" * 60, "sort_order": 2},    # trim >40
            {"id": "d", "name": "Ok", "sort_order": 0},
        ]
        r = api.put(f"{BASE_URL}/api/restaurants/{restaurant_id}",
                    headers=seller_ctx["headers"],
                    json=_restaurant_put_payload(menu_sections=raw))
        assert r.status_code == 200, r.text
        ms = r.json()["menu_sections"]
        ids = [s["id"] for s in ms]
        assert ids == ["a", "c", "d"]
        d = {s["id"]: s for s in ms}
        assert d["a"]["name"] == "Trimmed"
        assert d["a"]["sort_order"] == 5
        assert len(d["c"]["name"]) == 40
        assert d["d"]["sort_order"] == 0


# =========================================================================
# 2) Shop product_sections
# =========================================================================
class TestShopProductSections:
    def test_put_6_sections_persist(self, api, seller_ctx, shop_id):
        sections = [{"id": f"p{i}", "name": f"Sec{i}", "sort_order": i} for i in range(6)]
        r = api.put(f"{BASE_URL}/api/shops/{shop_id}",
                    headers=seller_ctx["headers"],
                    json=_shop_put_payload(product_sections=sections))
        assert r.status_code == 200, r.text
        assert len(r.json()["product_sections"]) == 6

    def test_put_rejects_more_than_6(self, api, seller_ctx, shop_id):
        sections = [{"id": f"p{i}", "name": f"Sec{i}", "sort_order": i} for i in range(7)]
        r = api.put(f"{BASE_URL}/api/shops/{shop_id}",
                    headers=seller_ctx["headers"],
                    json=_shop_put_payload(product_sections=sections))
        assert r.status_code == 400, r.text
        assert "maximum 6 product sections" in r.text.lower()


# =========================================================================
# 3) MenuItem menu_section_id + promo persist + roundtrip
# =========================================================================
class TestMenuItemSectionAndPromo:
    def test_create_with_section_and_promo(self, api, seller_ctx, restaurant_id, food_category_id):
        promo = {"active": True, "type": "percent", "value": 20}
        payload = {
            "restaurant_id": restaurant_id,
            "name": f"Pizza_{uuid.uuid4().hex[:6]}",
            "price_usd": 10.0,
            "category_id": food_category_id,
            "menu_section_id": "s1",
            "promo": promo,
        }
        r = api.post(f"{BASE_URL}/api/menu-items",
                     headers=seller_ctx["headers"], json=payload)
        assert r.status_code in (200, 201), r.text
        item = r.json()
        assert item["menu_section_id"] == "s1"
        assert item["promo"]["active"] is True
        assert item["promo"]["type"] == "percent"
        assert float(item["promo"]["value"]) == 20.0
        # Roundtrip via GET /menu
        g = api.get(f"{BASE_URL}/api/restaurants/{restaurant_id}/menu")
        assert g.status_code == 200
        found = next((m for m in g.json() if m["id"] == item["id"]), None)
        assert found is not None
        assert found["menu_section_id"] == "s1"
        assert found["promo"]["value"] == 20

    def test_put_updates_section_and_promo(self, api, seller_ctx, restaurant_id, food_category_id):
        # Create with defaults
        create = api.post(f"{BASE_URL}/api/menu-items",
                          headers=seller_ctx["headers"], json={
                              "restaurant_id": restaurant_id,
                              "name": f"Burger_{uuid.uuid4().hex[:6]}",
                              "price_usd": 8.0,
                              "category_id": food_category_id,
                          })
        assert create.status_code in (200, 201), create.text
        iid = create.json()["id"]
        new_promo = {"active": True, "type": "amount", "value": 1.5}
        upd = api.put(f"{BASE_URL}/api/menu-items/{iid}",
                      headers=seller_ctx["headers"], json={
                          "restaurant_id": restaurant_id,
                          "name": create.json()["name"],
                          "price_usd": 8.0,
                          "category_id": food_category_id,
                          "menu_section_id": "s2",
                          "promo": new_promo,
                      })
        assert upd.status_code == 200, upd.text
        got = upd.json()
        assert got["menu_section_id"] == "s2"
        assert got["promo"]["type"] == "amount"
        assert float(got["promo"]["value"]) == 1.5


# =========================================================================
# 4) Product product_section_id + promo persist
# =========================================================================
class TestProductSectionAndPromo:
    def test_create_with_section_and_promo(self, api, seller_ctx, shop_id, shop_category_id):
        r = api.post(f"{BASE_URL}/api/products",
                     headers=seller_ctx["headers"], json={
                         "shop_id": shop_id,
                         "name": f"Widget_{uuid.uuid4().hex[:6]}",
                         "category_id": shop_category_id,
                         "price_usd": 4.0,
                         "product_section_id": "p1",
                         "promo": {"active": True, "type": "amount", "value": 1.5},
                     })
        assert r.status_code in (200, 201), r.text
        p = r.json()
        assert p["product_section_id"] == "p1"
        assert p["promo"]["type"] == "amount"
        assert float(p["promo"]["value"]) == 1.5

    def test_put_updates_section_and_promo(self, api, seller_ctx, shop_id, shop_category_id):
        c = api.post(f"{BASE_URL}/api/products",
                     headers=seller_ctx["headers"], json={
                         "shop_id": shop_id,
                         "name": f"Gizmo_{uuid.uuid4().hex[:6]}",
                         "category_id": shop_category_id,
                         "price_usd": 4.0,
                     })
        assert c.status_code in (200, 201), c.text
        pid = c.json()["id"]
        upd = api.put(f"{BASE_URL}/api/products/{pid}",
                      headers=seller_ctx["headers"], json={
                          "shop_id": shop_id,
                          "name": c.json()["name"],
                          "category_id": shop_category_id,
                          "price_usd": 4.0,
                          "product_section_id": "p2",
                          "promo": {"active": True, "type": "percent", "value": 10},
                      })
        assert upd.status_code == 200, upd.text
        assert upd.json()["product_section_id"] == "p2"
        assert upd.json()["promo"]["type"] == "percent"


# =========================================================================
# 5) PROMO server-side enforcement on restaurant orders
# =========================================================================
def _seed_menu_item(db, restaurant_id, seller_id, category_id, price_usd, promo):
    iid = f"{RUN_TAG}_mi_{uuid.uuid4().hex[:8]}"
    db.menu_items.insert_one({
        "id": iid, "restaurant_id": restaurant_id, "seller_id": seller_id,
        "name": f"Item_{iid[-6:]}", "price_usd": price_usd,
        "category_id": category_id, "side_items": [],
        "sides_required": False,
        "promo": promo,
        "created_at": _now(),
    })
    return iid


def _restaurant_order_payload(restaurant_id, item_id, name, sent_price, qty=1):
    return {
        "restaurant_id": restaurant_id,
        "items": [{
            "item_type": "menu_item",
            "item_id": item_id,
            "name": name,
            "price_usd": sent_price,
            "quantity": qty,
            "sides": [],
        }],
        "delivery_type": "pickup",
        "customer_name": "TEST Cust",
        "customer_phone": "+211900000002",
        "payment_method": "cash",
    }


class TestPromoEnforcementRestaurant:
    def test_percent_promo_applied_server_side(
            self, api, db, customer_ctx, restaurant_id, seller_ctx, food_category_id):
        iid = _seed_menu_item(db, restaurant_id, seller_ctx["id"], food_category_id,
                              10.0, {"active": True, "type": "percent", "value": 20})
        # Client sends inflated $10 price; server must still charge $8.
        r = api.post(f"{BASE_URL}/api/restaurant-orders",
                     headers=customer_ctx["headers"],
                     json=_restaurant_order_payload(restaurant_id, iid, "X", 10.0))
        assert r.status_code in (200, 201), r.text
        order = r.json()
        assert abs(float(order["subtotal"]) - 8.0) < 0.01, order
        assert abs(float(order["items"][0]["price_usd"]) - 8.0) < 0.01

    def test_percent_promo_ignores_client_lower_price(
            self, api, db, customer_ctx, restaurant_id, seller_ctx, food_category_id):
        iid = _seed_menu_item(db, restaurant_id, seller_ctx["id"], food_category_id,
                              10.0, {"active": True, "type": "percent", "value": 20})
        # Client sends $1; server must still charge $8 (effective).
        r = api.post(f"{BASE_URL}/api/restaurant-orders",
                     headers=customer_ctx["headers"],
                     json=_restaurant_order_payload(restaurant_id, iid, "X", 1.0))
        assert r.status_code in (200, 201), r.text
        assert abs(float(r.json()["subtotal"]) - 8.0) < 0.01

    def test_amount_promo_applied(
            self, api, db, customer_ctx, restaurant_id, seller_ctx, food_category_id):
        iid = _seed_menu_item(db, restaurant_id, seller_ctx["id"], food_category_id,
                              10.0, {"active": True, "type": "amount", "value": 2.5})
        r = api.post(f"{BASE_URL}/api/restaurant-orders",
                     headers=customer_ctx["headers"],
                     json=_restaurant_order_payload(restaurant_id, iid, "X", 10.0))
        assert r.status_code in (200, 201), r.text
        assert abs(float(r.json()["subtotal"]) - 7.5) < 0.01

    def test_starts_in_future_no_discount(
            self, api, db, customer_ctx, restaurant_id, seller_ctx, food_category_id):
        future = _iso(datetime.now(timezone.utc) + timedelta(days=365))
        iid = _seed_menu_item(db, restaurant_id, seller_ctx["id"], food_category_id,
                              10.0, {"active": True, "type": "percent",
                                     "value": 50, "starts_at": future})
        r = api.post(f"{BASE_URL}/api/restaurant-orders",
                     headers=customer_ctx["headers"],
                     json=_restaurant_order_payload(restaurant_id, iid, "X", 10.0))
        assert r.status_code in (200, 201), r.text
        assert abs(float(r.json()["subtotal"]) - 10.0) < 0.01

    def test_ends_in_past_no_discount(
            self, api, db, customer_ctx, restaurant_id, seller_ctx, food_category_id):
        past = _iso(datetime.now(timezone.utc) - timedelta(days=365))
        iid = _seed_menu_item(db, restaurant_id, seller_ctx["id"], food_category_id,
                              10.0, {"active": True, "type": "percent",
                                     "value": 50, "ends_at": past})
        r = api.post(f"{BASE_URL}/api/restaurant-orders",
                     headers=customer_ctx["headers"],
                     json=_restaurant_order_payload(restaurant_id, iid, "X", 10.0))
        assert r.status_code in (200, 201), r.text
        assert abs(float(r.json()["subtotal"]) - 10.0) < 0.01

    def test_active_false_no_discount(
            self, api, db, customer_ctx, restaurant_id, seller_ctx, food_category_id):
        iid = _seed_menu_item(db, restaurant_id, seller_ctx["id"], food_category_id,
                              10.0, {"active": False, "type": "percent", "value": 50})
        r = api.post(f"{BASE_URL}/api/restaurant-orders",
                     headers=customer_ctx["headers"],
                     json=_restaurant_order_payload(restaurant_id, iid, "X", 10.0))
        assert r.status_code in (200, 201), r.text
        assert abs(float(r.json()["subtotal"]) - 10.0) < 0.01

    def test_amount_promo_never_negative(
            self, api, db, customer_ctx, restaurant_id, seller_ctx, food_category_id):
        iid = _seed_menu_item(db, restaurant_id, seller_ctx["id"], food_category_id,
                              1.0, {"active": True, "type": "amount", "value": 5.0})
        r = api.post(f"{BASE_URL}/api/restaurant-orders",
                     headers=customer_ctx["headers"],
                     json=_restaurant_order_payload(restaurant_id, iid, "X", 1.0))
        assert r.status_code in (200, 201), r.text
        assert abs(float(r.json()["subtotal"]) - 0.0) < 0.01


# =========================================================================
# 6) PROMO server-side enforcement on marketplace orders
# =========================================================================
class TestPromoEnforcementMarketplace:
    def test_percent_promo_applied(
            self, api, db, customer_ctx, seller_ctx, shop_id, shop_category_id):
        pid = f"{RUN_TAG}_pp_promo_{uuid.uuid4().hex[:6]}"
        db.products.insert_one({
            "id": pid, "seller_id": seller_ctx["id"], "shop_id": shop_id,
            "name": "MP_Widget", "price_usd": 8.0, "stock": 100,
            "category_id": shop_category_id,
            "promo": {"active": True, "type": "percent", "value": 25},
            "created_at": _now(),
        })
        r = api.post(f"{BASE_URL}/api/orders", headers=customer_ctx["headers"], json={
            "items": [{"item_type": "product", "item_id": pid, "name": "MP_Widget",
                       "price_usd": 8.0, "quantity": 1}],
            "area": "Juba", "address": "Somewhere", "phone": "+211900000002",
            "order_kind": "marketplace",
        })
        assert r.status_code in (200, 201), r.text
        order = r.json()
        # 25% off $8 = $6
        assert abs(float(order["subtotal_usd"]) - 6.0) < 0.01, order
        assert abs(float(order["items"][0]["price_usd"]) - 6.0) < 0.01


# =========================================================================
# 7) Regressions
# =========================================================================
class TestRegressions:
    def test_odoo_health(self, api):
        r = api.get(f"{BASE_URL}/api/odoo/health")
        assert r.status_code == 200, r.text

    def test_admin_login(self, admin_headers):
        assert admin_headers["Authorization"].startswith("Bearer ")

    def test_seller_analytics_by_channel(self, api, seller_ctx):
        r = api.get(f"{BASE_URL}/api/seller/analytics",
                    headers=seller_ctx["headers"])
        assert r.status_code == 200, r.text
        data = r.json()
        assert "by_channel" in data
        for ch in ("combined", "marketplace", "restaurant"):
            assert ch in data["by_channel"]

    def test_menu_returns_iter25_26_fields(self, api, seller_ctx, restaurant_id,
                                            food_category_id):
        # Iter25/26 fields: prep_time_minutes, sides_required, sides_min_choices,
        # sides_max_choices. Verify they roundtrip alongside the new fields.
        r = api.post(f"{BASE_URL}/api/menu-items",
                     headers=seller_ctx["headers"], json={
                         "restaurant_id": restaurant_id,
                         "name": f"Regr_{uuid.uuid4().hex[:6]}",
                         "price_usd": 5.0,
                         "category_id": food_category_id,
                         "prep_time_minutes": 12,
                         "sides_required": False,
                         "menu_section_id": "s1",
                         "promo": {"active": False, "type": "percent", "value": 0},
                     })
        assert r.status_code in (200, 201), r.text
        item = r.json()
        g = api.get(f"{BASE_URL}/api/restaurants/{restaurant_id}/menu")
        assert g.status_code == 200
        found = next((m for m in g.json() if m["id"] == item["id"]), None)
        assert found is not None
        assert found.get("prep_time_minutes") == 12
        assert "sides_required" in found
        assert "sides_min_choices" in found
        assert "sides_max_choices" in found
        assert found.get("menu_section_id") == "s1"
        assert "promo" in found

    def test_odoo_kitchen_accept(self, api, db, admin_headers, seller_ctx):
        db.odoo_service_tokens.delete_many({})
        tr = api.post(f"{BASE_URL}/api/admin/odoo/service-token/generate",
                      headers=admin_headers)
        assert tr.status_code == 200, tr.text
        tok = tr.json()["raw_token"]
        oid = f"{RUN_TAG}_ro_kitchen"
        db.restaurant_orders.insert_one({
            "id": oid, "restaurant_id": f"{RUN_TAG}_rest_x",
            "seller_id": seller_ctx["id"],
            "status": "pending", "seller_preparation_status": "pending",
            "delivery_status": "pending", "payment_status": "pending_collection",
            "created_at": _now(),
        })
        r = api.post(f"{BASE_URL}/api/odoo/kitchen/accept",
                     headers={"X-Jubasquare-Odoo-Token": tok,
                              "Content-Type": "application/json"},
                     json={"order_id": oid})
        assert r.status_code == 200, r.text
        doc = db.restaurant_orders.find_one({"id": oid})
        assert doc["seller_preparation_status"] == "accepted"
