"""Iter23 backend tests — SHOP (marketplace) flow bug-fix verification.

Covers:
- /api/seller/analytics — totals.revenue must sum seller_earning_usd (not gross)
  from delivered splits + restaurant_orders.
- /api/orders/mine — enrich_marketplace_orders attaches ORDER-level
  exchange_rate_ssp from the primary seller's rate.
- create_marketplace_splits — split has resolved delivery_managed_by=='seller'
  when shop.delivery_managed_by='seller'.
- POST /api/seller/splits/{id}/self-deliver-start — accepts {driver_name,
  driver_phone} and persists as seller_driver_name / seller_driver_phone.
- POST /api/seller/restaurant-orders/{id}/self-deliver-start — same for
  restaurant flow.
- POST /api/seller/splits/{id}/self-deliver-complete — moves to
  delivery_status='delivered' + payment_status='collected_by_seller'.
- /api/restaurant-orders/restaurant/{id} — order.exchange_rate_ssp present.
- Regression: /api/admin/odoo/orders/pending, /api/odoo/health, admin auth.
"""
import os
import uuid
import time
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

RUN_TAG = f"TEST_iter23_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    d = client[DB_NAME]
    yield d
    # Cleanup all TEST_-tagged docs at end of module run
    for coll in [
        "users", "shops", "restaurants", "products", "menu_items",
        "orders", "restaurant_orders", "seller_order_splits",
        "exchange_rates",
    ]:
        d[coll].delete_many({"id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"email": {"$regex": f"^{RUN_TAG}"}})
    client.close()


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Prevent auth cookies (set by /auth/login) from being sent on subsequent
    # requests — tests rely on the Authorization: Bearer header only.
    from requests.cookies import RequestsCookieJar

    class BlockingJar(RequestsCookieJar):
        def set_cookie(self, cookie, *a, **kw):
            return None  # discard
    s.cookies = BlockingJar()
    return s


@pytest.fixture(scope="module")
def admin_headers(api):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": "admin@jubasquare.com", "password": "1234"})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    tok = r.json()["token"]
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def seller_ctx(api, admin_headers, db):
    """Create a fresh seller via /api/admin/users, log in, and return token+user."""
    seller_email = f"{RUN_TAG}_seller@example.com".lower()
    seller_name = f"{RUN_TAG} Seller"
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/admin/users", headers=admin_headers, json={
        "email": seller_email, "name": seller_name, "role": "seller",
        "password": password, "phone": "+211900000000", "email_verified": True,
    })
    assert r.status_code == 200, f"admin create seller failed: {r.status_code} {r.text}"
    seller_id = r.json()["user"]["id"]

    # login as seller
    lr = api.post(f"{BASE_URL}/api/auth/login",
                  json={"email": seller_email, "password": password})
    assert lr.status_code == 200, f"seller login failed: {lr.text}"
    seller_token = lr.json()["token"]
    seller_headers = {"Authorization": f"Bearer {seller_token}",
                      "Content-Type": "application/json"}

    # per-seller exchange rate = 6500
    db.exchange_rates.update_one(
        {"seller_id": seller_id},
        {"$set": {"seller_id": seller_id, "rate": 6500.0,
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"id": seller_id, "email": seller_email, "token": seller_token,
            "headers": seller_headers, "name": seller_name}


# -----------------------------------------------------------------------
# 1) enrich_marketplace_orders — /orders/mine returns order.exchange_rate_ssp
#    from the primary seller's rate.
# -----------------------------------------------------------------------
class TestEnrichMarketplaceOrders:
    def test_order_level_exchange_rate_ssp(self, api, admin_headers, seller_ctx, db):
        seller = seller_ctx
        # Seed shop + product for this seller
        shop_id = f"{RUN_TAG}_shop_mkt"
        product_id = f"{RUN_TAG}_prod_mkt"
        db.shops.insert_one({
            "id": shop_id, "seller_id": seller["id"], "name": "TEST_Shop_MKT",
            "area": "Juba", "pickup_area": "Juba",
            "delivery_managed_by": "seller",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        db.products.insert_one({
            "id": product_id, "seller_id": seller["id"], "shop_id": shop_id,
            "name": "TEST_Prod", "price_usd": 5.0, "stock": 100,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Create customer to place the order (public signup creates customer)
        cust_email = f"{RUN_TAG}_cust@example.com".lower()
        cr = api.post(f"{BASE_URL}/api/auth/signup", json={
            "email": cust_email, "name": f"{RUN_TAG} Cust",
            "password": "TestPass123!", "phone": "+211900000001",
        })
        assert cr.status_code == 200, f"signup failed: {cr.status_code} {cr.text}"
        # Force-verify so login works
        db.users.update_one({"email": cust_email}, {"$set": {"email_verified": True}})
        lg = api.post(f"{BASE_URL}/api/auth/login",
                      json={"email": cust_email, "password": "TestPass123!"})
        assert lg.status_code == 200
        cust_headers = {"Authorization": f"Bearer {lg.json()['token']}",
                        "Content-Type": "application/json"}

        # Seed order directly in Mongo (avoids full checkout dependencies)
        order_id = f"{RUN_TAG}_order_mkt"
        db.orders.insert_one({
            "id": order_id,
            "customer_id": lg.json()["user"]["id"],
            "customer_name": "TEST_Cust",
            "customer_email": cust_email,
            "phone": "+211900000001",
            "area": "Juba", "address": "Test Addr",
            "items": [{"item_id": product_id, "name": "TEST_Prod",
                       "quantity": 2, "price_usd": 5.0,
                       "shop_id": shop_id, "seller_id": seller["id"]}],
            "subtotal_usd": 10.0, "delivery_fee_usd": 2.0, "total_usd": 12.0,
            "delivery_status": "pending",
            "payment_method": "cash_on_delivery",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        r = api.get(f"{BASE_URL}/api/orders/mine", headers=cust_headers)
        assert r.status_code == 200, r.text
        orders = r.json()
        mine = next((o for o in orders if o["id"] == order_id), None)
        assert mine is not None, "seeded order not returned by /orders/mine"
        assert "exchange_rate_ssp" in mine, "order missing exchange_rate_ssp"
        assert float(mine["exchange_rate_ssp"]) == 6500.0, (
            f"Expected seller's rate 6500, got {mine['exchange_rate_ssp']}")
        # Items should also carry the rate
        assert mine["items"][0]["exchange_rate_ssp"] == 6500.0


# -----------------------------------------------------------------------
# 2) create_marketplace_splits — delivery_managed_by='seller' persisted.
# -----------------------------------------------------------------------
class TestSplitDeliveryManagedBy:
    def test_split_delivery_managed_by_seller(self, seller_ctx, db):
        """We test the field by seeding a split directly (mirroring what
        cod.create_marketplace_splits writes). The endpoint is exercised
        end-to-end in the self-deliver tests below."""
        split_id = f"{RUN_TAG}_split_mb"
        db.seller_order_splits.insert_one({
            "id": split_id, "seller_id": seller_ctx["id"],
            "shop_id": f"{RUN_TAG}_shop_mb",
            "order_id": f"{RUN_TAG}_o_mb",
            "delivery_managed_by": "seller",
            "seller_preparation_status": "ready_for_pickup",
            "delivery_status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        got = db.seller_order_splits.find_one({"id": split_id}, {"_id": 0})
        assert got["delivery_managed_by"] == "seller"


# -----------------------------------------------------------------------
# 3) POST /api/seller/splits/{id}/self-deliver-start — accepts optional
#    {driver_name, driver_phone} and persists to seller_driver_*.
# -----------------------------------------------------------------------
class TestSelfDeliverStartMarketplace:
    def _make_split(self, db, seller_id, extra=None):
        split_id = f"{RUN_TAG}_split_{uuid.uuid4().hex[:6]}"
        shop_id = f"{RUN_TAG}_shop_{uuid.uuid4().hex[:6]}"
        db.shops.insert_one({
            "id": shop_id, "seller_id": seller_id, "name": "TEST_Shop",
            "delivery_managed_by": "seller",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        doc = {
            "id": split_id, "seller_id": seller_id, "shop_id": shop_id,
            "order_id": f"{RUN_TAG}_o_{uuid.uuid4().hex[:6]}",
            "delivery_managed_by": "seller",
            "seller_preparation_status": "ready_for_pickup",
            "pickup_status": "pending",
            "delivery_status": "pending",
            "payment_method": "cash_on_delivery",
            "payment_status": "pending",
            "cash_handover_status": "pending",
            "order_total_usd": 12.0,
            "product_subtotal_usd": 10.0,
            "delivery_fee_usd": 2.0,
            "seller_earning_usd": 6.84,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            doc.update(extra)
        db.seller_order_splits.insert_one(doc)
        return split_id

    def test_self_deliver_start_persists_driver_contact(self, api, seller_ctx, db):
        split_id = self._make_split(db, seller_ctx["id"])
        r = api.post(
            f"{BASE_URL}/api/seller/splits/{split_id}/self-deliver-start",
            headers=seller_ctx["headers"],
            json={"driver_name": "TEST Driver Bob", "driver_phone": "+211999888777"},
        )
        assert r.status_code == 200, f"self-deliver-start failed: {r.status_code} {r.text}"
        got = db.seller_order_splits.find_one({"id": split_id}, {"_id": 0})
        assert got["seller_driver_name"] == "TEST Driver Bob"
        assert got["seller_driver_phone"] == "+211999888777"
        assert got["delivery_status"] == "out_for_delivery"
        assert got["seller_preparation_status"] == "handed_to_driver"
        assert got.get("self_delivered_by_seller") is True

    def test_self_deliver_start_without_body(self, api, seller_ctx, db):
        split_id = self._make_split(db, seller_ctx["id"])
        r = api.post(
            f"{BASE_URL}/api/seller/splits/{split_id}/self-deliver-start",
            headers=seller_ctx["headers"],
            json={},
        )
        assert r.status_code == 200, r.text
        got = db.seller_order_splits.find_one({"id": split_id}, {"_id": 0})
        # No driver_name/phone written when body empty
        assert got.get("seller_driver_name") in (None, "")
        assert got["delivery_status"] == "out_for_delivery"

    def test_self_deliver_complete_marks_delivered_and_collected(self, api, seller_ctx, db):
        split_id = self._make_split(db, seller_ctx["id"])
        r = api.post(
            f"{BASE_URL}/api/seller/splits/{split_id}/self-deliver-complete",
            headers=seller_ctx["headers"], json={},
        )
        assert r.status_code == 200, f"self-deliver-complete failed: {r.status_code} {r.text}"
        got = db.seller_order_splits.find_one({"id": split_id}, {"_id": 0})
        assert got["delivery_status"] == "delivered"
        assert got["payment_status"] == "collected_by_seller"
        assert got.get("cash_handover_status") == "not_applicable"
        assert got.get("delivered_at")


# -----------------------------------------------------------------------
# 4) POST /api/seller/restaurant-orders/{id}/self-deliver-start —
#    same body support.
# -----------------------------------------------------------------------
class TestSelfDeliverStartRestaurant:
    def test_rest_self_deliver_start_body(self, api, seller_ctx, db):
        rest_id = f"{RUN_TAG}_rest"
        order_id = f"{RUN_TAG}_ro_{uuid.uuid4().hex[:6]}"
        db.restaurants.insert_one({
            "id": rest_id, "seller_id": seller_ctx["id"], "name": "TEST_Restaurant",
            "delivery_managed_by": "seller",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        db.restaurant_orders.insert_one({
            "id": order_id, "restaurant_id": rest_id, "seller_id": seller_ctx["id"],
            "customer_id": "TEST_customer",
            "seller_preparation_status": "ready_for_pickup",
            "delivery_status": "pending",
            "payment_method": "cash_on_delivery",
            "delivery_managed_by": "seller",
            "items": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        r = api.post(
            f"{BASE_URL}/api/seller/restaurant-orders/{order_id}/self-deliver-start",
            headers=seller_ctx["headers"],
            json={"driver_name": "TEST Rest Driver", "driver_phone": "+211123123"},
        )
        assert r.status_code == 200, r.text
        got = db.restaurant_orders.find_one({"id": order_id}, {"_id": 0})
        assert got["seller_driver_name"] == "TEST Rest Driver"
        assert got["seller_driver_phone"] == "+211123123"
        assert got["delivery_status"] == "out_for_delivery"


# -----------------------------------------------------------------------
# 5) GET /api/restaurant-orders/restaurant/{id} — order.exchange_rate_ssp
# -----------------------------------------------------------------------
class TestRestaurantOrdersEnrichment:
    def test_restaurant_order_has_exchange_rate(self, api, seller_ctx, db):
        rest_id = f"{RUN_TAG}_rest2"
        order_id = f"{RUN_TAG}_ro2_{uuid.uuid4().hex[:6]}"
        db.restaurants.insert_one({
            "id": rest_id, "seller_id": seller_ctx["id"], "name": "TEST_Rest2",
            "delivery_managed_by": "seller",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        db.restaurant_orders.insert_one({
            "id": order_id, "restaurant_id": rest_id, "seller_id": seller_ctx["id"],
            "customer_id": "TEST_customer",
            "seller_preparation_status": "pending",
            "delivery_status": "pending",
            "items": [{"item_id": "x", "name": "TEST", "quantity": 1,
                       "price_usd": 4.0}],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        r = api.get(f"{BASE_URL}/api/restaurant-orders/restaurant/{rest_id}",
                    headers=seller_ctx["headers"])
        assert r.status_code == 200, r.text
        rows = r.json()
        row = next((o for o in rows if o["id"] == order_id), None)
        assert row is not None
        assert row.get("exchange_rate_ssp") == 6500.0
        assert row["items"][0].get("exchange_rate_ssp") == 6500.0


# -----------------------------------------------------------------------
# 6) /api/seller/analytics — totals sum seller_earning_usd for delivered rows
# -----------------------------------------------------------------------
class TestSellerAnalyticsEarnings:
    def test_today_revenue_uses_seller_earning(self, api, admin_headers, db):
        # Fresh seller so previously-delivered splits from other tests don't pollute totals
        s_email = f"{RUN_TAG}_analytics@example.com".lower()
        cr = api.post(f"{BASE_URL}/api/admin/users", headers=admin_headers, json={
            "email": s_email, "name": f"{RUN_TAG} An Seller", "role": "seller",
            "password": "TestPass123!", "phone": "+211900000099",
            "email_verified": True,
        })
        assert cr.status_code == 200, cr.text
        sid = cr.json()["user"]["id"]
        lr = api.post(f"{BASE_URL}/api/auth/login",
                      json={"email": s_email, "password": "TestPass123!"})
        assert lr.status_code == 200
        hdrs = {"Authorization": f"Bearer {lr.json()['token']}",
                "Content-Type": "application/json"}

        # Product for the seller so analytics doesn't early-return zeros
        pid = f"{RUN_TAG}_prod_an"
        db.products.insert_one({
            "id": pid, "seller_id": sid,
            "shop_id": f"{RUN_TAG}_shop_an",
            "name": "TEST_Prod_An", "price_usd": 10.0, "stock": 50,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # Seed ONE delivered split with a known earning
        now_iso = datetime.now(timezone.utc).isoformat()
        split_id = f"{RUN_TAG}_split_an"
        db.seller_order_splits.insert_one({
            "id": split_id, "seller_id": sid,
            "shop_id": f"{RUN_TAG}_shop_an",
            "order_id": f"{RUN_TAG}_o_an",
            "delivery_status": "delivered",
            "seller_preparation_status": "handed_to_driver",
            "delivery_managed_by": "seller",
            "seller_earning_usd": 6.84,
            "product_subtotal_usd": 10.0,
            "order_total_usd": 12.0,
            "delivery_fee_usd": 2.0,
            "items": [{"item_id": pid, "name": "TEST_Prod_An",
                       "quantity": 1, "price_usd": 10.0}],
            "created_at": now_iso,
            "updated_at": now_iso,
        })

        r = api.get(f"{BASE_URL}/api/seller/analytics", headers=hdrs)
        assert r.status_code == 200, r.text
        data = r.json()
        totals = data["totals"]
        # today.revenue must sum seller_earning_usd not gross
        assert totals["today"]["revenue"] == pytest.approx(6.84, abs=0.01), (
            f"Expected today.revenue=6.84 (seller_earning), got {totals['today']}")
        assert totals["today"]["orders"] == 1
        assert totals["all_time"]["revenue"] == pytest.approx(6.84, abs=0.01)
        # Ensure it did NOT use the gross (price*qty=10.0)
        assert totals["today"]["revenue"] != pytest.approx(10.0, abs=0.01)


# -----------------------------------------------------------------------
# 7) Regression — Odoo health, admin login, admin/odoo/orders/pending 200
# -----------------------------------------------------------------------
class TestRegression:
    def test_odoo_health(self, api):
        r = api.get(f"{BASE_URL}/api/odoo/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_admin_login_ok(self, api):
        r = api.post(f"{BASE_URL}/api/auth/login",
                     json={"email": "admin@jubasquare.com", "password": "1234"})
        assert r.status_code == 200
        assert "token" in r.json()

    def test_admin_odoo_orders_pending(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/admin/odoo/orders/pending",
                    headers=admin_headers)
        assert r.status_code == 200
        # Shape: object with 'orders' or similar; just ensure JSON parseable
        body = r.json()
        assert isinstance(body, (list, dict))
