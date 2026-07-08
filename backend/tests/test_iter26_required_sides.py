"""Iter26 backend tests — REQUIRED sides on menu items.

Covers:
- MenuItemIn new fields: sides_required, sides_min_choices, sides_max_choices.
- POST/PUT /api/menu-items persistence + roundtrip.
- POST /api/restaurant-orders server-side sides constraint enforcement:
    * missing required sides → 400
    * too many sides → 400
    * invalid side name → 400
    * valid selection → 200 with subtotal including side price
    * sides_required=False: any count accepted
- GET /api/restaurants/{id}/menu returns new fields.
- Regressions: /api/odoo/health, admin login, seller analytics.by_channel,
  /api/orders/mine exchange_rate_ssp, /api/odoo/kitchen/accept.
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

RUN_TAG = f"TEST_iter26_{uuid.uuid4().hex[:8]}"


def _now():
    return datetime.now(timezone.utc).isoformat()


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
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return {"Authorization": f"Bearer {r.json()['token']}",
            "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def seller_ctx(api, admin_headers):
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
def category_id(db):
    cid = f"{RUN_TAG}_cat_food"
    db.categories.insert_one({
        "id": cid, "name": "TestFood", "slug": f"{RUN_TAG}_food",
        "group": "restaurant", "created_at": _now(),
    })
    return cid


@pytest.fixture(scope="module")
def restaurant_id(db, seller_ctx):
    rid = f"{RUN_TAG}_rest_main"
    db.restaurants.insert_one({
        "id": rid, "seller_id": seller_ctx["id"],
        "name": "TEST_Rest26", "area": "Juba",
        "is_open": True, "is_deleted": False,
        "verification": "Verified",  # allow customer menu access
        "delivery_managed_by": "seller",
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "created_at": _now(),
    })
    return rid


def _make_menu_item(api, seller_ctx, restaurant_id, category_id, **extra):
    payload = {
        "restaurant_id": restaurant_id,
        "name": extra.pop("name", f"Pizza_{uuid.uuid4().hex[:6]}"),
        "price_usd": extra.pop("price_usd", 10.0),
        "category_id": category_id,
        "side_items": extra.pop("side_items",
                                [{"name": "Small", "price_usd": 0.0},
                                 {"name": "Large", "price_usd": 3.0},
                                 {"name": "Extra Cheese", "price_usd": 1.5}]),
        **extra,
    }
    r = api.post(f"{BASE_URL}/api/menu-items",
                 headers=seller_ctx["headers"], json=payload)
    assert r.status_code in (200, 201), r.text
    return r.json()


# =========================================================================
# 1) MenuItem: create + roundtrip with required-sides fields
# =========================================================================
class TestMenuItemRequiredSidesPersistence:
    def test_create_with_required_sides(self, api, seller_ctx, restaurant_id, category_id):
        item = _make_menu_item(api, seller_ctx, restaurant_id, category_id,
                               sides_required=True,
                               sides_min_choices=1,
                               sides_max_choices=1)
        assert item["sides_required"] is True
        assert item["sides_min_choices"] == 1
        assert item["sides_max_choices"] == 1
        # Roundtrip GET
        r = api.get(f"{BASE_URL}/api/restaurants/{restaurant_id}/menu")
        assert r.status_code == 200, r.text
        found = next((m for m in r.json() if m["id"] == item["id"]), None)
        assert found, "created item missing from menu GET"
        assert found["sides_required"] is True
        assert found["sides_min_choices"] == 1
        assert found["sides_max_choices"] == 1

    def test_update_persists_new_values(self, api, seller_ctx, restaurant_id, category_id):
        item = _make_menu_item(api, seller_ctx, restaurant_id, category_id,
                               sides_required=False)
        assert item.get("sides_required") in (False, None)
        upd = {
            "restaurant_id": restaurant_id,
            "name": item["name"],
            "price_usd": item["price_usd"],
            "category_id": category_id,
            "side_items": item.get("side_items", []),
            "sides_required": True,
            "sides_min_choices": 2,
            "sides_max_choices": 3,
        }
        r = api.put(f"{BASE_URL}/api/menu-items/{item['id']}",
                    headers=seller_ctx["headers"], json=upd)
        assert r.status_code == 200, r.text
        got = r.json()
        assert got["sides_required"] is True
        assert got["sides_min_choices"] == 2
        assert got["sides_max_choices"] == 3

    def test_menu_get_returns_new_fields_present(self, api, seller_ctx, restaurant_id, category_id):
        # Unset sides_required — field may be False/None, must not error
        item = _make_menu_item(api, seller_ctx, restaurant_id, category_id)
        r = api.get(f"{BASE_URL}/api/restaurants/{restaurant_id}/menu")
        assert r.status_code == 200
        found = next((m for m in r.json() if m["id"] == item["id"]), None)
        assert found is not None
        assert "sides_required" in found
        assert "sides_min_choices" in found
        assert "sides_max_choices" in found


# =========================================================================
# 2) Restaurant-order sides constraint enforcement
# =========================================================================
class TestRestaurantOrderSidesEnforcement:
    def _order_payload(self, restaurant_id, item, sides):
        return {
            "restaurant_id": restaurant_id,
            "items": [{
                "item_type": "menu_item",
                "item_id": item["id"],
                "name": item["name"],
                "price_usd": item["price_usd"],
                "quantity": 1,
                "sides": sides,
            }],
            "delivery_type": "pickup",  # avoid delivery fee calc
            "customer_name": "TEST Cust",
            "customer_phone": "+211900000002",
            "payment_method": "cash",
        }

    def test_missing_required_side_400(self, api, seller_ctx, customer_ctx, restaurant_id, category_id):
        item = _make_menu_item(api, seller_ctx, restaurant_id, category_id,
                               sides_required=True,
                               sides_min_choices=1, sides_max_choices=1)
        r = api.post(f"{BASE_URL}/api/restaurant-orders",
                     headers=customer_ctx["headers"],
                     json=self._order_payload(restaurant_id, item, []))
        assert r.status_code == 400, r.text
        assert "requires at least 1 side" in r.text.lower()

    def test_too_many_sides_400(self, api, seller_ctx, customer_ctx, restaurant_id, category_id):
        item = _make_menu_item(api, seller_ctx, restaurant_id, category_id,
                               sides_required=True,
                               sides_min_choices=1, sides_max_choices=1)
        sides = [
            {"name": "Small", "price_usd": 0.0},
            {"name": "Large", "price_usd": 3.0},
        ]
        r = api.post(f"{BASE_URL}/api/restaurant-orders",
                     headers=customer_ctx["headers"],
                     json=self._order_payload(restaurant_id, item, sides))
        assert r.status_code == 400, r.text
        assert "allows at most 1 side" in r.text.lower()

    def test_invalid_side_name_400(self, api, seller_ctx, customer_ctx, restaurant_id, category_id):
        item = _make_menu_item(api, seller_ctx, restaurant_id, category_id,
                               sides_required=True,
                               sides_min_choices=1, sides_max_choices=1)
        sides = [{"name": "NotOnMenu", "price_usd": 5.0}]
        r = api.post(f"{BASE_URL}/api/restaurant-orders",
                     headers=customer_ctx["headers"],
                     json=self._order_payload(restaurant_id, item, sides))
        assert r.status_code == 400, r.text
        assert "invalid sides" in r.text.lower()

    def test_valid_selection_creates_order_with_side_price(self, api, seller_ctx, customer_ctx, restaurant_id, category_id):
        item = _make_menu_item(api, seller_ctx, restaurant_id, category_id,
                               price_usd=10.0,
                               sides_required=True,
                               sides_min_choices=1, sides_max_choices=1)
        sides = [{"name": "Large", "price_usd": 3.0}]
        r = api.post(f"{BASE_URL}/api/restaurant-orders",
                     headers=customer_ctx["headers"],
                     json=self._order_payload(restaurant_id, item, sides))
        assert r.status_code in (200, 201), r.text
        order = r.json()
        # subtotal should be price(10) + side(3) * qty(1) = 13
        assert abs(float(order["subtotal"]) - 13.0) < 0.01, order
        assert order["items"][0]["sides"][0]["name"] == "Large"

    def test_not_required_accepts_any_count(self, api, seller_ctx, customer_ctx, restaurant_id, category_id):
        item = _make_menu_item(api, seller_ctx, restaurant_id, category_id,
                               sides_required=False)
        # 0 sides
        r0 = api.post(f"{BASE_URL}/api/restaurant-orders",
                      headers=customer_ctx["headers"],
                      json=self._order_payload(restaurant_id, item, []))
        assert r0.status_code in (200, 201), r0.text
        # many sides (also arbitrary names allowed when not required)
        many = [{"name": "Small", "price_usd": 0.0},
                {"name": "Large", "price_usd": 3.0},
                {"name": "Extra Cheese", "price_usd": 1.5}]
        r1 = api.post(f"{BASE_URL}/api/restaurant-orders",
                      headers=customer_ctx["headers"],
                      json=self._order_payload(restaurant_id, item, many))
        assert r1.status_code in (200, 201), r1.text


# =========================================================================
# 3) Regressions
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

    def test_orders_mine_exchange_rate_ssp(self, api, db, seller_ctx, customer_ctx):
        db.exchange_rates.update_one(
            {"seller_id": seller_ctx["id"]},
            {"$set": {"seller_id": seller_ctx["id"], "rate": 6500.0,
                      "updated_at": _now()}},
            upsert=True,
        )
        oid = f"{RUN_TAG}_order_reg"
        shop_id = f"{RUN_TAG}_shop_reg"
        prod_id = f"{RUN_TAG}_pp_reg"
        db.shops.insert_one({"id": shop_id, "seller_id": seller_ctx["id"],
                             "name": "TEST_Reg", "area": "Juba",
                             "created_at": _now()})
        db.products.insert_one({"id": prod_id, "seller_id": seller_ctx["id"],
                                "shop_id": shop_id, "name": "P",
                                "price_usd": 5.0, "stock": 10,
                                "created_at": _now()})
        db.orders.insert_one({
            "id": oid, "customer_id": customer_ctx["id"],
            "customer_name": "TEST", "customer_email": customer_ctx["email"],
            "phone": "+211900000002", "area": "Juba", "address": "Test",
            "items": [{"item_id": prod_id, "name": "P",
                       "quantity": 1, "price_usd": 5.0,
                       "shop_id": shop_id, "seller_id": seller_ctx["id"]}],
            "subtotal_usd": 5.0, "delivery_fee_usd": 2.0, "total_usd": 7.0,
            "delivery_status": "pending",
            "payment_method": "cash_on_delivery",
            "created_at": _now(),
        })
        r = api.get(f"{BASE_URL}/api/orders/mine",
                    headers=customer_ctx["headers"])
        assert r.status_code == 200, r.text
        mine = next((o for o in r.json() if o["id"] == oid), None)
        assert mine, "seeded order not returned"
        assert float(mine.get("exchange_rate_ssp") or 0) == 6500.0

    def test_odoo_kitchen_accept(self, api, db, admin_headers, seller_ctx):
        # Generate a service token
        db.odoo_service_tokens.delete_many({})
        tr = api.post(f"{BASE_URL}/api/admin/odoo/service-token/generate",
                      headers=admin_headers)
        assert tr.status_code == 200, tr.text
        tok = tr.json()["raw_token"]
        oid = f"{RUN_TAG}_ro_kitchen"
        db.restaurant_orders.insert_one({
            "id": oid,
            "restaurant_id": f"{RUN_TAG}_rest_x",
            "seller_id": seller_ctx["id"],
            "status": "pending",
            "seller_preparation_status": "pending",
            "delivery_status": "pending",
            "payment_status": "pending_collection",
            "created_at": _now(),
        })
        r = api.post(f"{BASE_URL}/api/odoo/kitchen/accept",
                     headers={"X-Jubasquare-Odoo-Token": tok,
                              "Content-Type": "application/json"},
                     json={"order_id": oid})
        assert r.status_code == 200, r.text
        doc = db.restaurant_orders.find_one({"id": oid})
        assert doc["seller_preparation_status"] == "accepted"
        assert doc["status"] == "accepted"
