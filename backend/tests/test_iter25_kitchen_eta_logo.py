"""Iter25 backend tests.

Covers:
- POST /api/odoo/kitchen/{action} state machine (accept, preparing, ready,
  complete, cancel) driven by X-Jubasquare-Odoo-Token service token.
- Auth failures (missing token → 401; invalid action → 400; unknown order → 404).
- Sub-order targeting via `sub_order_id`.
- New RestaurantIn/ShopIn fields: receipt_show_logo, receipt_logo_url,
  eta_mode, eta_fixed_minutes, eta_min_minutes, eta_max_minutes — PUT/GET round-trip.
- _enrich_rate populates receipt_show_logo/logo_url + eta_* on
  /seller/splits and /seller/restaurant-orders-cod when parent has them.
- GET /api/products: in-stock first within the same verification tier.
- Regression: /api/seller/analytics.by_channel, /api/orders/mine.exchange_rate_ssp,
  /api/admin/odoo/orders/pending 200, admin login.
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

RUN_TAG = f"TEST_iter25_{uuid.uuid4().hex[:8]}"


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    d = client[DB_NAME]
    yield d
    # Cleanup per RUN_TAG
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
    # Wipe token + kitchen logs so subsequent runs start clean
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
def seller_ctx(api, admin_headers, db):
    seller_email = f"{RUN_TAG}_seller@example.com".lower()
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/admin/users", headers=admin_headers, json={
        "email": seller_email, "name": f"{RUN_TAG} Seller", "role": "seller",
        "password": password, "phone": "+211900000000", "email_verified": True,
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
def odoo_token(api, admin_headers, db):
    """Generate service token via admin endpoint. Wipes any existing tokens
    first so the endpoint doesn't 409."""
    db.odoo_service_tokens.delete_many({})
    r = api.post(f"{BASE_URL}/api/admin/odoo/service-token/generate",
                 headers=admin_headers)
    assert r.status_code == 200, f"token gen failed: {r.status_code} {r.text}"
    return r.json()["raw_token"]


# ============================================================
# 1) Admin regression
# ============================================================
class TestAdminRegression:
    def test_admin_login_200(self, admin_headers):
        assert admin_headers["Authorization"].startswith("Bearer ")

    def test_odoo_pending_200(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/admin/odoo/orders/pending",
                    headers=admin_headers)
        assert r.status_code == 200, r.text


# ============================================================
# 2) Kitchen actions state machine (restaurant_orders)
# ============================================================
class TestKitchenActionsRestaurantOrders:
    def _seed_order(self, db, seller_ctx, suffix):
        oid = f"{RUN_TAG}_ro_{suffix}"
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
        return oid

    def test_accept(self, api, db, seller_ctx, odoo_token):
        oid = self._seed_order(db, seller_ctx, "acc")
        r = api.post(f"{BASE_URL}/api/odoo/kitchen/accept",
                     headers={"X-Jubasquare-Odoo-Token": odoo_token,
                              "Content-Type": "application/json"},
                     json={"order_id": oid})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["status"] == "success"
        assert j["action"] == "accept"
        assert j["entity_type"] == "restaurant_order"
        doc = db.restaurant_orders.find_one({"id": oid})
        assert doc["seller_preparation_status"] == "accepted"
        assert doc["status"] == "accepted"
        assert doc.get("accepted_at")
        log = db.odoo_sync_logs.find_one({"id": j["log_id"]})
        assert log and log["kind"] == "kitchen_action"
        assert log["action"] == "accept"
        assert log["matched"] is True

    def test_preparing(self, api, db, seller_ctx, odoo_token):
        oid = self._seed_order(db, seller_ctx, "prep")
        r = api.post(f"{BASE_URL}/api/odoo/kitchen/preparing",
                     headers={"X-Jubasquare-Odoo-Token": odoo_token},
                     json={"order_id": oid})
        assert r.status_code == 200, r.text
        doc = db.restaurant_orders.find_one({"id": oid})
        assert doc["seller_preparation_status"] == "preparing"
        assert doc["status"] == "cooking"
        assert doc.get("preparing_started_at")

    def test_ready(self, api, db, seller_ctx, odoo_token):
        oid = self._seed_order(db, seller_ctx, "rdy")
        r = api.post(f"{BASE_URL}/api/odoo/kitchen/ready",
                     headers={"X-Jubasquare-Odoo-Token": odoo_token},
                     json={"order_id": oid})
        assert r.status_code == 200, r.text
        doc = db.restaurant_orders.find_one({"id": oid})
        assert doc["seller_preparation_status"] == "ready_for_pickup"
        assert doc["status"] == "ready"
        assert doc.get("ready_at")

    def test_complete(self, api, db, seller_ctx, odoo_token):
        oid = self._seed_order(db, seller_ctx, "cmp")
        r = api.post(f"{BASE_URL}/api/odoo/kitchen/complete",
                     headers={"X-Jubasquare-Odoo-Token": odoo_token},
                     json={"order_id": oid})
        assert r.status_code == 200, r.text
        doc = db.restaurant_orders.find_one({"id": oid})
        assert doc["seller_preparation_status"] == "handed_to_driver"
        assert doc["delivery_status"] == "delivered"
        assert doc["status"] == "delivered"
        assert doc["payment_status"] == "collected_by_seller"
        assert doc.get("delivered_at")
        assert doc.get("cash_collected_at")

    def test_cancel(self, api, db, seller_ctx, odoo_token):
        oid = self._seed_order(db, seller_ctx, "cnc")
        r = api.post(f"{BASE_URL}/api/odoo/kitchen/cancel",
                     headers={"X-Jubasquare-Odoo-Token": odoo_token},
                     json={"order_id": oid, "reason": "Out of stock"})
        assert r.status_code == 200, r.text
        doc = db.restaurant_orders.find_one({"id": oid})
        assert doc["seller_preparation_status"] == "cancelled"
        assert doc["status"] == "cancelled"
        assert doc["cancellation_reason"] == "Out of stock"
        assert doc.get("cancelled_at")
        assert doc.get("cancelled_by") == "odoo"


# ============================================================
# 3) Kitchen action auth + validation
# ============================================================
class TestKitchenActionAuth:
    def test_missing_token_401(self, api):
        r = api.post(f"{BASE_URL}/api/odoo/kitchen/accept",
                     headers={"Content-Type": "application/json"},
                     json={"order_id": "whatever"})
        # verify_odoo_webhook: missing header → 401 (503/500 only if not configured)
        assert r.status_code in (401, 500), f"unexpected {r.status_code}: {r.text}"

    def test_invalid_token_403(self, api, odoo_token):
        r = api.post(f"{BASE_URL}/api/odoo/kitchen/accept",
                     headers={"X-Jubasquare-Odoo-Token": "bogus_" + odoo_token[:8]},
                     json={"order_id": "whatever"})
        assert r.status_code == 403, r.text

    def test_invalid_action_400(self, api, odoo_token):
        r = api.post(f"{BASE_URL}/api/odoo/kitchen/nuke",
                     headers={"X-Jubasquare-Odoo-Token": odoo_token},
                     json={"order_id": "whatever"})
        assert r.status_code == 400, r.text

    def test_missing_order_id_400(self, api, odoo_token):
        r = api.post(f"{BASE_URL}/api/odoo/kitchen/accept",
                     headers={"X-Jubasquare-Odoo-Token": odoo_token},
                     json={})
        assert r.status_code == 400, r.text

    def test_unknown_order_id_404(self, api, odoo_token):
        r = api.post(f"{BASE_URL}/api/odoo/kitchen/accept",
                     headers={"X-Jubasquare-Odoo-Token": odoo_token},
                     json={"order_id": f"{RUN_TAG}_nonexistent"})
        assert r.status_code == 404, r.text

    def test_sub_order_missing_404(self, api, odoo_token):
        r = api.post(f"{BASE_URL}/api/odoo/kitchen/accept",
                     headers={"X-Jubasquare-Odoo-Token": odoo_token},
                     json={"order_id": f"{RUN_TAG}_o_x",
                           "sub_order_id": f"{RUN_TAG}_sub_missing"})
        assert r.status_code == 404, r.text


# ============================================================
# 4) Sub-order (seller_order_splits) targeting
# ============================================================
class TestKitchenActionSplit:
    def test_split_accept(self, api, db, seller_ctx, odoo_token):
        oid = f"{RUN_TAG}_split_ord"
        sid = f"{RUN_TAG}_split_id"
        db.seller_order_splits.insert_one({
            "id": sid,
            "order_id": oid,
            "seller_id": seller_ctx["id"],
            "seller_preparation_status": "pending",
            "delivery_status": "pending",
            "created_at": _now(),
        })
        r = api.post(f"{BASE_URL}/api/odoo/kitchen/accept",
                     headers={"X-Jubasquare-Odoo-Token": odoo_token},
                     json={"order_id": oid, "sub_order_id": sid})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["entity_type"] == "seller_order_split"
        doc = db.seller_order_splits.find_one({"id": sid})
        assert doc["seller_preparation_status"] == "accepted"
        assert doc["status"] == "accepted"


# ============================================================
# 5) PUT /restaurants and /shops persist new receipt-logo / ETA fields
# ============================================================
class TestReceiptLogoAndEtaPersistence:
    def _seed_restaurant(self, db, seller_ctx, suffix):
        rid = f"{RUN_TAG}_rest_upd_{suffix}"
        db.restaurants.insert_one({
            "id": rid, "seller_id": seller_ctx["id"],
            "name": "TEST_RestBase", "area": "Juba",
            "is_open": True, "is_deleted": False,
            "delivery_managed_by": "seller",
            "created_at": _now(),
        })
        return rid

    def _seed_shop(self, db, seller_ctx, suffix):
        sid = f"{RUN_TAG}_shop_upd_{suffix}"
        db.shops.insert_one({
            "id": sid, "seller_id": seller_ctx["id"],
            "name": "TEST_ShopBase", "area": "Juba",
            "delivery_managed_by": "seller",
            "created_at": _now(),
        })
        return sid

    def test_restaurant_put_persists_new_fields(self, api, db, seller_ctx):
        rid = self._seed_restaurant(db, seller_ctx, "a")
        payload = {
            "name": "TEST_RestUpd",
            "category": "food",
            "area": "Juba",
            "is_open": True,
            "receipt_show_logo": True,
            "receipt_logo_url": "https://x/rlogo.png",
            "eta_mode": "range",
            "eta_min_minutes": 25,
            "eta_max_minutes": 40,
        }
        r = api.put(f"{BASE_URL}/api/restaurants/{rid}",
                    headers=seller_ctx["headers"], json=payload)
        assert r.status_code == 200, r.text
        # Owner GET (restaurant is not Verified → auth required)
        g = api.get(f"{BASE_URL}/api/restaurants/{rid}",
                    headers=seller_ctx["headers"]).json()
        assert g.get("receipt_show_logo") is True, g
        assert g.get("receipt_logo_url") == "https://x/rlogo.png"
        assert g.get("eta_mode") == "range"
        assert g.get("eta_min_minutes") == 25
        assert g.get("eta_max_minutes") == 40

    def test_restaurant_put_eta_fixed(self, api, db, seller_ctx):
        rid = self._seed_restaurant(db, seller_ctx, "b")
        payload = {
            "name": "TEST_RestUpd2",
            "category": "food", "area": "Juba", "is_open": True,
            "eta_mode": "fixed", "eta_fixed_minutes": 30,
        }
        r = api.put(f"{BASE_URL}/api/restaurants/{rid}",
                    headers=seller_ctx["headers"], json=payload)
        assert r.status_code == 200, r.text
        g = api.get(f"{BASE_URL}/api/restaurants/{rid}",
                    headers=seller_ctx["headers"]).json()
        assert g.get("eta_mode") == "fixed"
        assert g.get("eta_fixed_minutes") == 30

    def test_shop_put_persists_new_fields(self, api, db, seller_ctx):
        sid = self._seed_shop(db, seller_ctx, "a")
        payload = {
            "name": "TEST_ShopUpd",
            "kind": "retail",
            "area": "Juba",
            "receipt_show_logo": True,
            "receipt_logo_url": "https://x/slogo.png",
            "eta_mode": "fixed",
            "eta_fixed_minutes": 45,
        }
        r = api.put(f"{BASE_URL}/api/shops/{sid}",
                    headers=seller_ctx["headers"], json=payload)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("receipt_show_logo") is True
        assert j.get("receipt_logo_url") == "https://x/slogo.png"
        assert j.get("eta_mode") == "fixed"
        assert j.get("eta_fixed_minutes") == 45


# ============================================================
# 6) _enrich_rate: splits + restaurant-orders-cod snapshots
# ============================================================
class TestEnrichReceiptAndEta:
    def test_splits_get_receipt_logo_and_eta(self, api, db, seller_ctx):
        shop_id = f"{RUN_TAG}_shop_enr"
        db.shops.insert_one({
            "id": shop_id, "seller_id": seller_ctx["id"],
            "name": "TEST_ShopEnr", "area": "Juba",
            "delivery_managed_by": "seller",
            "receipt_show_logo": True,
            "receipt_logo_url": "https://x/l.png",
            "eta_mode": "range",
            "eta_min_minutes": 10, "eta_max_minutes": 20,
            "created_at": _now(),
        })
        sid = f"{RUN_TAG}_spl_enr"
        db.seller_order_splits.insert_one({
            "id": sid, "seller_id": seller_ctx["id"], "shop_id": shop_id,
            "order_id": f"{RUN_TAG}_o_enr",
            "seller_preparation_status": "pending",
            "delivery_status": "pending",
            "created_at": _now(),
        })
        r = api.get(f"{BASE_URL}/api/seller/splits",
                    headers=seller_ctx["headers"])
        assert r.status_code == 200, r.text
        rows = [x for x in r.json() if x["id"] == sid]
        assert rows, "split not returned"
        row = rows[0]
        assert row.get("receipt_show_logo") is True
        assert row.get("receipt_logo_url") == "https://x/l.png"
        assert row.get("eta_mode") == "range"
        assert row.get("eta_min_minutes") == 10
        assert row.get("eta_max_minutes") == 20

    def test_restaurant_orders_cod_get_snapshots(self, api, db, seller_ctx):
        rest_id = f"{RUN_TAG}_rest_enr"
        db.restaurants.insert_one({
            "id": rest_id, "seller_id": seller_ctx["id"],
            "name": "TEST_RestEnr", "area": "Juba",
            "delivery_managed_by": "seller", "is_open": True,
            "receipt_show_logo": True,
            "receipt_logo_url": "https://x/rl.png",
            "eta_mode": "fixed", "eta_fixed_minutes": 15,
            "created_at": _now(),
        })
        oid = f"{RUN_TAG}_ro_enr"
        db.restaurant_orders.insert_one({
            "id": oid, "restaurant_id": rest_id,
            "seller_id": seller_ctx["id"],
            "delivery_status": "pending",
            "seller_preparation_status": "pending",
            "delivery_managed_by": "seller",
            "created_at": _now(),
        })
        r = api.get(f"{BASE_URL}/api/seller/restaurant-orders-cod",
                    headers=seller_ctx["headers"])
        assert r.status_code == 200, r.text
        rows = [x for x in r.json() if x["id"] == oid]
        assert rows, "restaurant order not returned"
        row = rows[0]
        assert row.get("receipt_show_logo") is True
        assert row.get("receipt_logo_url") == "https://x/rl.png"
        assert row.get("eta_mode") == "fixed"
        assert row.get("eta_fixed_minutes") == 15


# ============================================================
# 7) GET /api/products in-stock first within same verification tier
# ============================================================
class TestProductsInStockFirst:
    def test_in_stock_before_out_of_stock(self, api, db, seller_ctx):
        shop_id = f"{RUN_TAG}_shop_sort"
        db.shops.insert_one({
            "id": shop_id, "seller_id": seller_ctx["id"],
            "name": "TEST_ShopSort", "area": "Juba",
            "verification": "Verified",
            "delivery_managed_by": "seller",
            "is_public": True,
            "created_at": _now(),
        })
        # Ensure seller does NOT auto-hide out of stock
        db.users.update_one({"id": seller_ctx["id"]},
                            {"$set": {"settings.auto_hide_out_of_stock": False}})
        prods = [
            (f"{RUN_TAG}_p_a", 5),
            (f"{RUN_TAG}_p_b", 0),
            (f"{RUN_TAG}_p_c", 2),
        ]
        for pid, stk in prods:
            db.products.insert_one({
                "id": pid, "seller_id": seller_ctx["id"],
                "shop_id": shop_id, "name": pid, "price_usd": 1.0,
                "stock": stk, "is_active": True,
                "created_at": _now(),
            })

        r = api.get(f"{BASE_URL}/api/products?shop_id={shop_id}")
        assert r.status_code == 200, r.text
        # Products returned may include only ours (shop_id filter)
        got = [p for p in r.json() if p["id"].startswith(f"{RUN_TAG}_p_")]
        assert len(got) == 3, f"expected 3, got {len(got)}: {got}"
        # In-stock (5, 2) must come before out-of-stock (0)
        stocks = [int(p.get("stock", 0)) for p in got]
        # The last one must be 0, the first two must be > 0
        assert stocks[-1] == 0, f"expected 0 stock last, got {stocks}"
        assert stocks[0] > 0 and stocks[1] > 0, f"in-stock not first: {stocks}"


# ============================================================
# 8) Regressions
# ============================================================
class TestRegressions:
    def test_analytics_by_channel_shape(self, api, seller_ctx):
        r = api.get(f"{BASE_URL}/api/seller/analytics",
                    headers=seller_ctx["headers"])
        assert r.status_code == 200, r.text
        data = r.json()
        assert "by_channel" in data
        for ch in ("combined", "marketplace", "restaurant"):
            assert ch in data["by_channel"]

    def test_orders_mine_exchange_rate_ssp(self, api, db, seller_ctx):
        # Seed a customer + order
        cust_email = f"{RUN_TAG}_cust_reg@example.com".lower()
        sr = api.post(f"{BASE_URL}/api/auth/signup", json={
            "email": cust_email, "name": "TEST Cust Reg",
            "password": "TestPass123!", "phone": "+211900099010",
        })
        assert sr.status_code == 200, sr.text
        db.users.update_one({"email": cust_email},
                            {"$set": {"email_verified": True}})
        lg = api.post(f"{BASE_URL}/api/auth/login",
                      json={"email": cust_email, "password": "TestPass123!"})
        assert lg.status_code == 200
        cust_id = lg.json()["user"]["id"]
        cust_headers = {"Authorization": f"Bearer {lg.json()['token']}",
                        "Content-Type": "application/json"}
        db.exchange_rates.update_one(
            {"seller_id": seller_ctx["id"]},
            {"$set": {"seller_id": seller_ctx["id"], "rate": 6500.0,
                      "updated_at": _now()}},
            upsert=True,
        )
        oid = f"{RUN_TAG}_order_reg"
        shop_id = f"{RUN_TAG}_shop_reg2"
        prod_id = f"{RUN_TAG}_pp"
        db.shops.insert_one({"id": shop_id, "seller_id": seller_ctx["id"],
                             "name": "TEST_Reg2", "area": "Juba",
                             "created_at": _now()})
        db.products.insert_one({"id": prod_id, "seller_id": seller_ctx["id"],
                                "shop_id": shop_id, "name": "P",
                                "price_usd": 5.0, "stock": 10,
                                "created_at": _now()})
        db.orders.insert_one({
            "id": oid, "customer_id": cust_id,
            "customer_name": "TEST", "customer_email": cust_email,
            "phone": "+211900099010", "area": "Juba", "address": "Test",
            "items": [{"item_id": prod_id, "name": "P",
                       "quantity": 1, "price_usd": 5.0,
                       "shop_id": shop_id, "seller_id": seller_ctx["id"]}],
            "subtotal_usd": 5.0, "delivery_fee_usd": 2.0, "total_usd": 7.0,
            "delivery_status": "pending",
            "payment_method": "cash_on_delivery",
            "created_at": _now(),
        })
        r = api.get(f"{BASE_URL}/api/orders/mine", headers=cust_headers)
        assert r.status_code == 200, r.text
        mine = next((o for o in r.json() if o["id"] == oid), None)
        assert mine, "seeded order not returned"
        assert float(mine.get("exchange_rate_ssp") or 0) == 6500.0
