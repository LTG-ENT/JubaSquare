"""Iter24 backend tests.

Covers:
- /api/seller/analytics returns by_channel {combined, marketplace, restaurant}
  each with totals(today/week/month/all_time) and revenue_series.
- Delivered SHOP split (6.84) + delivered RESTAURANT order (4.20) roll up
  correctly per channel and combined.
- /api/seller/splits back-fills delivery_managed_by from parent shop
  when field missing (seller / admin / legacy-missing → platform default).
- POST /api/restaurant-orders persists delivery_managed_by on new orders.
- Regression: /api/orders/mine order.exchange_rate_ssp,
  /api/admin/odoo/orders/pending 200, admin login 200.
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

RUN_TAG = f"TEST_iter24_{uuid.uuid4().hex[:8]}"


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
        "exchange_rates",
    ]:
        d[coll].delete_many({"id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"email": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"seller_id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"shop_id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"restaurant_id": {"$regex": f"^{RUN_TAG}"}})
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
def seller_ctx(api, admin_headers, db):
    seller_email = f"{RUN_TAG}_seller@example.com".lower()
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/admin/users", headers=admin_headers, json={
        "email": seller_email, "name": f"{RUN_TAG} Seller", "role": "seller",
        "password": password, "phone": "+211900000000", "email_verified": True,
    })
    assert r.status_code == 200, f"admin create seller failed: {r.status_code} {r.text}"
    seller_id = r.json()["user"]["id"]

    lr = api.post(f"{BASE_URL}/api/auth/login",
                  json={"email": seller_email, "password": password})
    assert lr.status_code == 200, lr.text
    tok = lr.json()["token"]
    return {"id": seller_id, "email": seller_email, "token": tok,
            "headers": {"Authorization": f"Bearer {tok}",
                        "Content-Type": "application/json"}}


# ------------------------------------------------------------
# 1) Admin regression
# ------------------------------------------------------------
class TestAdminRegression:
    def test_admin_login_200(self, admin_headers):
        assert admin_headers["Authorization"].startswith("Bearer ")

    def test_odoo_pending_200(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/admin/odoo/orders/pending",
                    headers=admin_headers)
        assert r.status_code == 200, r.text


# ------------------------------------------------------------
# 2) /api/seller/analytics — by_channel shape + math
# ------------------------------------------------------------
class TestSellerAnalyticsByChannel:
    def test_by_channel_shape_and_math(self, api, seller_ctx, db):
        seller = seller_ctx

        # Seed a delivered SHOP split with seller_earning 6.84
        shop_id = f"{RUN_TAG}_shop_an"
        db.shops.insert_one({
            "id": shop_id, "seller_id": seller["id"],
            "name": "TEST_Shop_An", "area": "Juba",
            "delivery_managed_by": "seller",
            "created_at": _now(),
        })
        prod_id = f"{RUN_TAG}_prod_an"
        db.products.insert_one({
            "id": prod_id, "seller_id": seller["id"], "shop_id": shop_id,
            "name": "TEST_Prod_An", "price_usd": 5.0, "stock": 100,
            "created_at": _now(),
        })
        db.seller_order_splits.insert_one({
            "id": f"{RUN_TAG}_split_an",
            "seller_id": seller["id"], "shop_id": shop_id,
            "order_id": f"{RUN_TAG}_oan",
            "delivery_managed_by": "seller",
            "seller_preparation_status": "handed_to_driver",
            "delivery_status": "delivered",
            "payment_status": "collected_by_seller",
            "seller_earning_usd": 6.84,
            "order_total_usd": 12.0,
            "created_at": _now(),
        })

        # Seed a delivered RESTAURANT order with seller_earning 4.20
        rest_id = f"{RUN_TAG}_rest_an"
        db.restaurants.insert_one({
            "id": rest_id, "seller_id": seller["id"], "name": "TEST_Rest_An",
            "area": "Juba", "delivery_managed_by": "seller",
            "is_open": True, "created_at": _now(),
        })
        mi_id = f"{RUN_TAG}_mi_an"
        db.menu_items.insert_one({
            "id": mi_id, "seller_id": seller["id"], "restaurant_id": rest_id,
            "name": "TEST_MI", "price_usd": 4.0, "created_at": _now(),
        })
        db.restaurant_orders.insert_one({
            "id": f"{RUN_TAG}_ro_an",
            "restaurant_id": rest_id, "seller_id": seller["id"],
            "delivery_status": "delivered",
            "seller_earning_usd": 4.20,
            "order_total_usd": 6.0,
            "delivery_managed_by": "seller",
            "created_at": _now(),
        })

        r = api.get(f"{BASE_URL}/api/seller/analytics",
                    headers=seller["headers"])
        assert r.status_code == 200, r.text
        data = r.json()

        # Shape
        assert "totals" in data and "revenue_series" in data
        assert "by_channel" in data
        for ch in ("combined", "marketplace", "restaurant"):
            assert ch in data["by_channel"], f"missing channel {ch}"
            block = data["by_channel"][ch]
            assert "totals" in block and "revenue_series" in block
            for period in ("today", "week", "month", "all_time"):
                assert period in block["totals"]
                assert "revenue" in block["totals"][period]
                assert "orders" in block["totals"][period]
            # 30-day series
            assert isinstance(block["revenue_series"], list)
            assert len(block["revenue_series"]) == 30
            first = block["revenue_series"][0]
            assert "date" in first and "revenue" in first and "orders" in first

        # Backwards compat: top-level totals == combined totals
        assert data["totals"] == data["by_channel"]["combined"]["totals"]
        assert data["revenue_series"] == data["by_channel"]["combined"]["revenue_series"]

        # Math
        mkt = data["by_channel"]["marketplace"]["totals"]["all_time"]
        rest = data["by_channel"]["restaurant"]["totals"]["all_time"]
        combined = data["by_channel"]["combined"]["totals"]["all_time"]

        assert round(mkt["revenue"], 2) == 6.84, f"marketplace={mkt}"
        assert mkt["orders"] == 1
        assert round(rest["revenue"], 2) == 4.20, f"restaurant={rest}"
        assert rest["orders"] == 1
        assert round(combined["revenue"], 2) == 11.04, f"combined={combined}"
        assert combined["orders"] == 2


# ------------------------------------------------------------
# 3) _enrich_rate back-fills delivery_managed_by on splits
# ------------------------------------------------------------
class TestEnrichBackfillsDeliveryManagedBy:
    def _seed_split_no_mb(self, db, seller_id, shop_id):
        sid = f"{RUN_TAG}_split_{uuid.uuid4().hex[:6]}"
        doc = {
            "id": sid, "seller_id": seller_id, "shop_id": shop_id,
            "order_id": f"{RUN_TAG}_o_{uuid.uuid4().hex[:6]}",
            "seller_preparation_status": "pending",
            "delivery_status": "pending",
            "created_at": _now(),
        }
        # explicitly NOT setting delivery_managed_by
        db.seller_order_splits.insert_one(doc)
        return sid

    def test_backfill_seller_from_shop(self, api, seller_ctx, db):
        seller = seller_ctx
        shop_id = f"{RUN_TAG}_shop_bfs"
        db.shops.insert_one({
            "id": shop_id, "seller_id": seller["id"],
            "name": "TEST_Shop_BFS", "delivery_managed_by": "seller",
            "created_at": _now(),
        })
        sid = self._seed_split_no_mb(db, seller["id"], shop_id)
        r = api.get(f"{BASE_URL}/api/seller/splits", headers=seller["headers"])
        assert r.status_code == 200, r.text
        rows = [x for x in r.json() if x["id"] == sid]
        assert rows, "seeded split not returned"
        assert rows[0]["delivery_managed_by"] == "seller"

    def test_backfill_admin_from_shop(self, api, seller_ctx, db):
        seller = seller_ctx
        shop_id = f"{RUN_TAG}_shop_bfa"
        db.shops.insert_one({
            "id": shop_id, "seller_id": seller["id"],
            "name": "TEST_Shop_BFA", "delivery_managed_by": "admin",
            "created_at": _now(),
        })
        sid = self._seed_split_no_mb(db, seller["id"], shop_id)
        r = api.get(f"{BASE_URL}/api/seller/splits", headers=seller["headers"])
        assert r.status_code == 200, r.text
        rows = [x for x in r.json() if x["id"] == sid]
        assert rows, "seeded split not returned"
        assert rows[0]["delivery_managed_by"] == "admin"

    def test_backfill_platform_default_when_missing(self, api, seller_ctx, db):
        """Shop has NO delivery_managed_by field. Platform default should
        kick in. admin_manages_delivery is False by default → 'seller'."""
        seller = seller_ctx
        shop_id = f"{RUN_TAG}_shop_bfp"
        db.shops.insert_one({
            "id": shop_id, "seller_id": seller["id"],
            "name": "TEST_Shop_BFP",
            # no delivery_managed_by field
            "created_at": _now(),
        })
        sid = self._seed_split_no_mb(db, seller["id"], shop_id)
        r = api.get(f"{BASE_URL}/api/seller/splits", headers=seller["headers"])
        assert r.status_code == 200, r.text
        rows = [x for x in r.json() if x["id"] == sid]
        assert rows, "seeded split not returned"
        # Read the settings to figure out the expected fallback
        sysettings = db.settings.find_one({"id": "system"}) or {}
        expected = "admin" if sysettings.get("admin_manages_delivery") else "seller"
        assert rows[0]["delivery_managed_by"] == expected, (
            f"expected fallback={expected}, got {rows[0]['delivery_managed_by']}, "
            f"settings.admin_manages_delivery={sysettings.get('admin_manages_delivery')}")


# ------------------------------------------------------------
# 4) POST /api/restaurant-orders persists delivery_managed_by
# ------------------------------------------------------------
class TestRestaurantOrderPersistsDeliveryManagedBy:
    def test_created_restaurant_order_has_dmb(self, api, admin_headers, seller_ctx, db):
        seller = seller_ctx

        # Seed a restaurant owned by seller + a menu item
        rest_id = f"{RUN_TAG}_rest_cr"
        db.restaurants.insert_one({
            "id": rest_id, "seller_id": seller["id"], "name": "TEST_Rest_CR",
            "area": "Juba", "delivery_managed_by": "seller",
            "is_open": True, "is_deleted": False, "created_at": _now(),
        })
        mi_id = f"{RUN_TAG}_mi_cr"
        db.menu_items.insert_one({
            "id": mi_id, "seller_id": seller["id"], "restaurant_id": rest_id,
            "name": "TEST_MI_CR", "price_usd": 3.5, "created_at": _now(),
        })

        # Create a customer and login
        cust_email = f"{RUN_TAG}_cust_cr@example.com".lower()
        sr = api.post(f"{BASE_URL}/api/auth/signup", json={
            "email": cust_email, "name": f"{RUN_TAG} Cust CR",
            "password": "TestPass123!", "phone": "+211900000002",
        })
        assert sr.status_code == 200, f"signup failed: {sr.text}"
        db.users.update_one({"email": cust_email}, {"$set": {"email_verified": True}})
        lg = api.post(f"{BASE_URL}/api/auth/login",
                      json={"email": cust_email, "password": "TestPass123!"})
        assert lg.status_code == 200
        cust_headers = {"Authorization": f"Bearer {lg.json()['token']}",
                        "Content-Type": "application/json"}

        # POST /api/restaurant-orders
        payload = {
            "restaurant_id": rest_id,
            "items": [{
                "item_type": "menu_item", "item_id": mi_id,
                "name": "TEST_MI_CR", "price_usd": 3.5, "quantity": 1,
                "sides": [],
            }],
            "delivery_type": "delivery",
            "customer_name": "TEST Cust CR",
            "customer_phone": "+211900000002",
            "customer_address": "Test Addr CR",
            "customer_area": "Juba",
            "payment_method": "cash",
        }
        r = api.post(f"{BASE_URL}/api/restaurant-orders",
                     headers=cust_headers, json=payload)
        assert r.status_code == 200, f"create failed: {r.status_code} {r.text}"
        order_id = r.json()["id"]

        # Verify via direct Mongo read
        doc = db.restaurant_orders.find_one({"id": order_id})
        assert doc is not None
        assert "delivery_managed_by" in doc, "delivery_managed_by not persisted"
        # Restaurant is seller-managed → resolved as 'seller'
        assert doc["delivery_managed_by"] == "seller", (
            f"expected 'seller', got {doc['delivery_managed_by']}")


# ------------------------------------------------------------
# 5) Regression: /api/orders/mine exchange_rate_ssp still returned
# ------------------------------------------------------------
class TestOrdersMineExchangeRateSSPRegression:
    def test_order_level_exchange_rate_ssp(self, api, admin_headers, seller_ctx, db):
        seller = seller_ctx
        shop_id = f"{RUN_TAG}_shop_reg"
        prod_id = f"{RUN_TAG}_prod_reg"
        db.shops.insert_one({
            "id": shop_id, "seller_id": seller["id"], "name": "TEST_Reg",
            "area": "Juba", "delivery_managed_by": "seller",
            "created_at": _now(),
        })
        db.products.insert_one({
            "id": prod_id, "seller_id": seller["id"], "shop_id": shop_id,
            "name": "TEST_Prod_Reg", "price_usd": 5.0, "stock": 100,
            "created_at": _now(),
        })
        db.exchange_rates.update_one(
            {"seller_id": seller["id"]},
            {"$set": {"seller_id": seller["id"], "rate": 6500.0, "updated_at": _now()}},
            upsert=True,
        )

        cust_email = f"{RUN_TAG}_cust_reg@example.com".lower()
        sr = api.post(f"{BASE_URL}/api/auth/signup", json={
            "email": cust_email, "name": "TEST Cust Reg",
            "password": "TestPass123!", "phone": "+211900000010",
        })
        assert sr.status_code == 200, sr.text
        db.users.update_one({"email": cust_email}, {"$set": {"email_verified": True}})
        lg = api.post(f"{BASE_URL}/api/auth/login",
                      json={"email": cust_email, "password": "TestPass123!"})
        assert lg.status_code == 200
        cust_id = lg.json()["user"]["id"]
        cust_headers = {"Authorization": f"Bearer {lg.json()['token']}",
                        "Content-Type": "application/json"}

        order_id = f"{RUN_TAG}_order_reg"
        db.orders.insert_one({
            "id": order_id, "customer_id": cust_id,
            "customer_name": "TEST", "customer_email": cust_email,
            "phone": "+211900000010", "area": "Juba", "address": "Test",
            "items": [{"item_id": prod_id, "name": "TEST_Prod_Reg",
                       "quantity": 1, "price_usd": 5.0,
                       "shop_id": shop_id, "seller_id": seller["id"]}],
            "subtotal_usd": 5.0, "delivery_fee_usd": 2.0, "total_usd": 7.0,
            "delivery_status": "pending",
            "payment_method": "cash_on_delivery",
            "created_at": _now(),
        })
        r = api.get(f"{BASE_URL}/api/orders/mine", headers=cust_headers)
        assert r.status_code == 200, r.text
        mine = next((o for o in r.json() if o["id"] == order_id), None)
        assert mine, "seeded order not returned"
        assert float(mine.get("exchange_rate_ssp") or 0) == 6500.0
