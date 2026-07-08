"""Iter 31 backend tests.

Covers:
- GET /api/health.
- GET /api/seller/low-stock-report: happy path, buckets, sort order,
  soft-deleted exclusion, role gating (401 anon, 403 customer, 403 admin).
- Odoo /api/odoo/products/upsert: new optional fields
  (promo bogo, is_ltg_partner, product_section_id for shop,
   menu_section_id + sides_required + side_items + prep_time_minutes for
   restaurant); backwards-compat: minimal payload doesn't overwrite existing
   promo/section/is_ltg_partner values.
- Admin LTG toggles for shop, restaurant, product still work.
- New Mongo indexes exist on favorites/orders/products/menu_items/shops/restaurants.
- Regression: GET /api/shops still returns has_active_promo & has_wholesale.
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

# Ensure env vars are loaded (backend/.env is authoritative)
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

RUN_TAG = f"TEST_iter31_{uuid.uuid4().hex[:8]}"


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------------- fixtures ----------------
@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    d = client[DB_NAME]
    yield d
    # Teardown: purge all TEST_iter31_* rows we created
    for coll in [
        "users", "shops", "restaurants", "products", "menu_items",
        "orders", "categories", "odoo_sync_logs",
    ]:
        d[coll].delete_many({"id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"email": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"seller_id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"shop_id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"restaurant_id": {"$regex": f"^{RUN_TAG}"}})
    # Odoo service token cleanup only if we created it here (see marker)
    d.odoo_service_tokens.delete_many({"created_by_email": f"{RUN_TAG}@marker"})
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
def seller_ctx(api, admin_headers):
    email = f"{RUN_TAG}_seller@example.com".lower()
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/admin/users", headers=admin_headers, json={
        "email": email, "name": f"{RUN_TAG} Seller", "role": "seller",
        "password": password, "phone": "+211900000091", "email_verified": True,
    })
    assert r.status_code == 200, r.text
    sid = r.json()["user"]["id"]
    lr = api.post(f"{BASE_URL}/api/auth/login",
                  json={"email": email, "password": password})
    assert lr.status_code == 200, lr.text
    tok = lr.json()["token"]
    return {"id": sid, "email": email, "token": tok,
            "headers": {"Authorization": f"Bearer {tok}",
                        "Content-Type": "application/json"}}


@pytest.fixture(scope="module")
def customer_ctx(api, db):
    email = f"{RUN_TAG}_cust@example.com".lower()
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "name": f"{RUN_TAG} Cust",
        "password": password, "phone": "+211900000092",
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
def shop_cat(db):
    cid = f"{RUN_TAG}_cat_shop"
    db.categories.insert_one({
        "id": cid, "name": "TestShopCat31", "slug": f"{RUN_TAG}_shopcat",
        "group": "shop", "created_at": _now(),
    })
    return cid


@pytest.fixture(scope="module")
def food_cat(db):
    cid = f"{RUN_TAG}_cat_food"
    db.categories.insert_one({
        "id": cid, "name": "TestFoodCat31", "slug": f"{RUN_TAG}_foodcat",
        "group": "restaurant", "created_at": _now(),
    })
    return cid


@pytest.fixture(scope="module")
def shop_id(db, seller_ctx, shop_cat):
    sid = f"{RUN_TAG}_shop_a"
    db.shops.insert_one({
        "id": sid, "name": "TEST_iter31_Shop_A",
        "seller_id": seller_ctx["id"],
        "area": "Juba", "category": "gen",
        "verification": "Verified", "is_public": True, "is_deleted": False,
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "product_sections": [
            {"id": "sec1", "name": "Featured", "sort": 1}
        ],
        "is_ltg_partner": False,
        "odoo_connection": {"enabled": True, "sync_products": True},
        "created_at": _now(),
    })
    return sid


@pytest.fixture(scope="module")
def restaurant_id(db, seller_ctx, food_cat):
    rid = f"{RUN_TAG}_rest_a"
    db.restaurants.insert_one({
        "id": rid, "name": "TEST_iter31_Rest_A",
        "seller_id": seller_ctx["id"],
        "area": "Juba", "is_open": True,
        "is_deleted": False, "verification": "Verified",
        "delivery_managed_by": "seller",
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "menu_sections": [{"id": "msec1", "name": "Mains", "sort": 1}],
        "is_ltg_partner": False,
        "odoo_connection": {"enabled": True, "sync_products": True},
        "created_at": _now(),
    })
    return rid


# ---------------- 1) Health ----------------
class TestHealth:
    def test_health(self, api):
        r = api.get(f"{BASE_URL}/api/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


# ---------------- 2) Low-stock report ----------------
class TestLowStockReport:
    """Seed 3 products in one shop for the seller:
    - out-of-stock (stock=0)
    - low-stock (stock=3, threshold=5)
    - healthy (stock=20)
    Plus a soft-deleted low-stock product that must be excluded.
    """

    @pytest.fixture(scope="class")
    def seeded(self, db, seller_ctx, shop_id, shop_cat):
        ids = {
            "oos": f"{RUN_TAG}_p_oos",
            "low": f"{RUN_TAG}_p_low",
            "ok":  f"{RUN_TAG}_p_ok",
            "del": f"{RUN_TAG}_p_del",
        }
        base = {
            "seller_id": seller_ctx["id"], "shop_id": shop_id,
            "category_id": shop_cat, "price_usd": 10.0,
            "is_active": True, "is_deleted": False,
            "created_at": _now(),
        }
        db.products.insert_many([
            {**base, "id": ids["oos"], "name": "OOS Widget", "stock": 0},
            {**base, "id": ids["low"], "name": "Low Widget", "stock": 3},
            {**base, "id": ids["ok"],  "name": "OK Widget",  "stock": 20},
            {**base, "id": ids["del"], "name": "Deleted Widget",
             "stock": 1, "is_deleted": True},
        ])
        return ids

    def test_anonymous_401(self, api):
        r = api.get(f"{BASE_URL}/api/seller/low-stock-report")
        assert r.status_code == 401, r.text

    def test_customer_forbidden(self, api, customer_ctx):
        r = api.get(f"{BASE_URL}/api/seller/low-stock-report",
                    headers=customer_ctx["headers"])
        assert r.status_code == 403, r.text

    def test_admin_forbidden(self, api, admin_headers):
        # admin doesn't have seller role -> 403
        r = api.get(f"{BASE_URL}/api/seller/low-stock-report",
                    headers=admin_headers)
        assert r.status_code == 403, r.text

    def test_seller_report_happy_path(self, api, seller_ctx, seeded, shop_id):
        r = api.get(f"{BASE_URL}/api/seller/low-stock-report",
                    headers=seller_ctx["headers"])
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["default_threshold"] == 5
        assert j["out_of_stock_count"] == 1
        assert j["low_stock_count"] == 1
        # total_products excludes soft-deleted
        assert j["total_products"] == 3
        # shops list is populated
        shop_ids_in = [s["id"] for s in j.get("shops", [])]
        assert shop_id in shop_ids_in
        # out_of_stock entry
        assert len(j["out_of_stock"]) == 1
        oos = j["out_of_stock"][0]
        assert oos["id"] == seeded["oos"]
        assert oos["_shop_name"] == "TEST_iter31_Shop_A"
        assert oos["_threshold"] == 5
        # low_stock entry
        assert len(j["low_stock"]) == 1
        low = j["low_stock"][0]
        assert low["id"] == seeded["low"]
        assert low["_shop_name"] == "TEST_iter31_Shop_A"
        # deleted product must not appear
        all_ids = [p["id"] for p in j["out_of_stock"] + j["low_stock"]]
        assert seeded["del"] not in all_ids


# ---------------- 3) Odoo upsert extended fields ----------------
@pytest.fixture(scope="module")
def odoo_token(api, admin_headers, db):
    """Get or provision an Odoo service token so we can hit the webhooks.

    Strategy:
    1. If ODOO_WEBHOOK_TOKEN env is set -> use it.
    2. Else, if no active DB token -> ask admin to generate one and use it.
    3. If an active DB token already exists (its raw isn't retrievable) ->
       return None so tests skip.
    """
    env_tok = os.environ.get("ODOO_WEBHOOK_TOKEN") or ""
    if env_tok:
        return env_tok
    active = db.odoo_service_tokens.find_one({"active": True})
    if active:
        return None  # can't get raw, skip
    r = api.post(f"{BASE_URL}/api/admin/odoo/service-token/generate",
                 headers=admin_headers)
    if r.status_code != 200:
        return None
    tok = r.json().get("raw_token")
    # mark for cleanup
    db.odoo_service_tokens.update_many(
        {"active": True},
        {"$set": {"created_by_email": f"{RUN_TAG}@marker"}},
    )
    return tok


class TestOdooUpsertExtended:
    def _headers(self, tok):
        return {"X-Jubasquare-Odoo-Token": tok,
                "Content-Type": "application/json"}

    def test_shop_upsert_with_promo_bogo_section_ltg(
        self, api, odoo_token, db, shop_id, shop_cat
    ):
        if not odoo_token:
            pytest.skip("skipped: no odoo token")
        odoo_pid = f"{RUN_TAG}_ody_shop_1"
        payload = {
            "shop_id": shop_id,
            "odoo_product_id": odoo_pid,
            "odoo_product_sku": "SKU-1",
            "name": "Odoo Shop Product 1",
            "price": 12.5,
            "category_id": shop_cat,
            "publish": True,
            "stock_quantity": 50,
            "promo": {
                "active": True, "type": "bogo", "value": 0,
                "bogo_min_qty": 3,
            },
            "product_section_id": "sec1",
            "is_ltg_partner": True,
        }
        r = api.post(f"{BASE_URL}/api/odoo/products/upsert",
                     headers=self._headers(odoo_token), json=payload)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["status"] == "success"
        assert j["action"] == "created"
        pid = j["product_id"]
        # DB verify
        doc = db.products.find_one({"id": pid})
        assert doc is not None
        assert doc["promo"]["type"] == "bogo"
        assert doc["promo"]["bogo_min_qty"] == 3
        assert doc["promo"]["active"] is True
        assert doc["product_section_id"] == "sec1"
        assert doc["is_ltg_partner"] is True
        # Reflected via GET /api/products
        gr = api.get(f"{BASE_URL}/api/products",
                     params={"shop_id": shop_id, "limit": 200})
        assert gr.status_code == 200
        listing = {p["id"]: p for p in gr.json()}
        assert pid in listing
        got = listing[pid]
        assert got.get("is_ltg_partner") is True
        # tag for later backcompat test
        return pid

    def test_restaurant_upsert_with_sides(
        self, api, odoo_token, db, restaurant_id, food_cat
    ):
        if not odoo_token:
            pytest.skip("skipped: no odoo token")
        odoo_pid = f"{RUN_TAG}_ody_rest_1"
        payload = {
            "restaurant_id": restaurant_id,
            "odoo_product_id": odoo_pid,
            "name": "Odoo Menu Item 1",
            "price": 8.0,
            "category_id": food_cat,
            "publish": True,
            "stock_quantity": 100,
            "menu_section_id": "msec1",
            "sides_required": True,
            "side_items": [
                {"id": "s1", "name": "Fries", "price_usd": 1.5,
                 "is_default": True},
                {"id": "s2", "name": "Salad", "price_usd": 2.0},
            ],
            "prep_time_minutes": 15,
        }
        r = api.post(f"{BASE_URL}/api/odoo/products/upsert",
                     headers=self._headers(odoo_token), json=payload)
        assert r.status_code == 200, r.text
        mid = r.json()["product_id"]
        doc = db.menu_items.find_one({"id": mid})
        assert doc is not None
        assert doc["menu_section_id"] == "msec1"
        assert doc["sides_required"] is True
        assert len(doc["side_items"]) == 2
        assert doc["side_items"][0]["name"] == "Fries"
        assert doc["prep_time_minutes"] == 15

    def test_backwards_compat_minimal_payload(
        self, api, odoo_token, db, shop_id, shop_cat
    ):
        """Sending an upsert WITHOUT the new fields must not overwrite
        previously-persisted promo / product_section_id / is_ltg_partner."""
        if not odoo_token:
            pytest.skip("skipped: no odoo token")
        odoo_pid = f"{RUN_TAG}_ody_shop_bc"
        # Step 1 — full payload
        p1 = {
            "shop_id": shop_id,
            "odoo_product_id": odoo_pid,
            "name": "Odoo BC Product",
            "price": 5.0,
            "category_id": shop_cat,
            "publish": True,
            "promo": {"active": True, "type": "percent", "value": 15,
                      "bogo_min_qty": 2},
            "product_section_id": "sec1",
            "is_ltg_partner": True,
        }
        r1 = api.post(f"{BASE_URL}/api/odoo/products/upsert",
                      headers=self._headers(odoo_token), json=p1)
        assert r1.status_code == 200
        pid = r1.json()["product_id"]
        # Step 2 — minimal payload (no new fields at all)
        p2 = {
            "shop_id": shop_id,
            "odoo_product_id": odoo_pid,
            "name": "Odoo BC Product v2",
            "price": 6.0,
            "category_id": shop_cat,
            "publish": True,
        }
        r2 = api.post(f"{BASE_URL}/api/odoo/products/upsert",
                      headers=self._headers(odoo_token), json=p2)
        assert r2.status_code == 200, r2.text
        # Same product id (matched by odoo_product_id)
        assert r2.json()["product_id"] == pid
        assert r2.json()["action"] == "updated"
        # Verify persisted state — name/price changed but new fields kept
        doc = db.products.find_one({"id": pid})
        assert doc["name"] == "Odoo BC Product v2"
        assert doc["price_usd"] == 6.0
        assert doc.get("promo", {}).get("type") == "percent"
        assert doc.get("promo", {}).get("value") == 15
        assert doc.get("product_section_id") == "sec1"
        assert doc.get("is_ltg_partner") is True


# ---------------- 4) Admin LTG toggles regression ----------------
class TestAdminLTGToggles:
    def test_shop_toggle(self, api, admin_headers, shop_id, db):
        r = api.put(f"{BASE_URL}/api/admin/shops/{shop_id}/ltg-partner",
                    headers=admin_headers, json={"is_ltg_partner": True})
        assert r.status_code == 200, r.text
        assert r.json()["is_ltg_partner"] is True
        assert db.shops.find_one({"id": shop_id})["is_ltg_partner"] is True
        # untoggle
        r2 = api.put(f"{BASE_URL}/api/admin/shops/{shop_id}/ltg-partner",
                     headers=admin_headers, json={"is_ltg_partner": False})
        assert r2.status_code == 200

    def test_restaurant_toggle(self, api, admin_headers, restaurant_id, db):
        r = api.put(
            f"{BASE_URL}/api/admin/restaurants/{restaurant_id}/ltg-partner",
            headers=admin_headers, json={"is_ltg_partner": True})
        assert r.status_code == 200, r.text
        assert r.json()["is_ltg_partner"] is True

    def test_product_toggle(self, api, admin_headers, db, seller_ctx,
                            shop_id, shop_cat):
        pid = f"{RUN_TAG}_p_ltg_tgl"
        db.products.insert_one({
            "id": pid, "name": "LTG toggle target",
            "shop_id": shop_id, "seller_id": seller_ctx["id"],
            "category_id": shop_cat, "price_usd": 3.0,
            "stock": 5, "is_active": True, "is_deleted": False,
            "created_at": _now(),
        })
        r = api.put(f"{BASE_URL}/api/admin/products/{pid}/ltg-partner",
                    headers=admin_headers, json={"is_ltg_partner": True})
        assert r.status_code == 200, r.text
        assert r.json()["is_ltg_partner"] is True


# ---------------- 5) Mongo indexes ----------------
class TestIndexes:
    """Verify perf indexes added in iter31 seed_production_indexes."""

    def _has_key(self, index_list, key_spec):
        """key_spec is a list of (field, direction) tuples in Mongo order."""
        want = list(key_spec)
        for ix in index_list:
            got = list(ix["key"].items())
            if got == want:
                return True
        return False

    def test_favorites_target_id(self, db):
        idx = list(db.favorites.list_indexes())
        assert self._has_key(idx, [("target_id", 1)])

    def test_orders_shop_id(self, db):
        idx = list(db.orders.list_indexes())
        # composite (shop_id, status)
        assert self._has_key(idx, [("shop_id", 1), ("status", 1)])

    def test_products_promo_active(self, db):
        idx = list(db.products.list_indexes())
        assert self._has_key(idx, [("promo.active", 1)])

    def test_menu_items_promo_active(self, db):
        idx = list(db.menu_items.list_indexes())
        assert self._has_key(idx, [("promo.active", 1)])

    def test_shops_is_ltg_partner(self, db):
        idx = list(db.shops.list_indexes())
        assert self._has_key(idx, [("is_ltg_partner", 1)])

    def test_restaurants_is_ltg_partner(self, db):
        idx = list(db.restaurants.list_indexes())
        assert self._has_key(idx, [("is_ltg_partner", 1)])


# ---------------- 6) /api/shops regression ----------------
class TestShopsRegression:
    def test_shops_has_flags(self, api):
        r = api.get(f"{BASE_URL}/api/shops", params={"limit": 200})
        assert r.status_code == 200, r.text
        shops = r.json()
        assert isinstance(shops, list)
        # Every returned shop must carry has_active_promo & has_wholesale
        # (booleans) — computed enrichment fields.
        for sh in shops[:20]:
            assert "has_active_promo" in sh
            assert "has_wholesale" in sh
            assert isinstance(sh["has_active_promo"], bool)
            assert isinstance(sh["has_wholesale"], bool)
