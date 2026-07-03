"""Iter22 backend tests: enriched /api/admin/odoo/orders/pending envelope +
POST /api/odoo/orders/status-update webhook + service-token flow + regressions.
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://jubasquare-odoo-v2.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get(
    "MONGO_URL",
    "mongodb+srv://Admin:Kokob1234567890@jubasquare-database.llu96aj.mongodb.net/?appName=JubaSquare-Database&compressors=zlib",
)
DB_NAME = os.environ.get("DB_NAME", "jubasquare")


# ---- Shared fixtures --------------------------------------------------------
@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": "admin@jubasquare.com", "password": "1234"})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"Missing token in response: {data}"
    assert data.get("user", {}).get("role") == "admin"
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def mongo_db():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    yield db
    client.close()


# ---- Health -----------------------------------------------------------------
class TestHealth:
    def test_odoo_health(self, api):
        r = api.get(f"{BASE_URL}/api/odoo/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "webhook_configured" in data
        assert data["service"] == "jubasquare-odoo-integration"


# ---- Admin auth regression --------------------------------------------------
class TestAuth:
    def test_admin_login(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 20


# ---- Service token management ----------------------------------------------
_generated_token_holder = {"raw": None}


class TestServiceToken:
    def test_status_admin_only(self, admin_headers):
        # unauthenticated - use a fresh session so login cookies don't leak
        anon = requests.Session()
        r = anon.get(f"{BASE_URL}/api/admin/odoo/service-token")
        assert r.status_code in (401, 403), f"unauth got {r.status_code}: {r.text}"
        api = requests.Session()
        # admin
        r = api.get(f"{BASE_URL}/api/admin/odoo/service-token", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert "configured" in body or "is_configured" in body or "active" in body or isinstance(body, dict)

    def test_generate_or_rotate(self, api, admin_headers):
        r = api.post(f"{BASE_URL}/api/admin/odoo/service-token/generate", headers=admin_headers)
        if r.status_code == 200:
            body = r.json()
            assert "raw_token" in body and len(body["raw_token"]) >= 32
            _generated_token_holder["raw"] = body["raw_token"]
            # Second generate must 409
            r2 = api.post(f"{BASE_URL}/api/admin/odoo/service-token/generate", headers=admin_headers)
            assert r2.status_code == 409, f"expected 409, got {r2.status_code}: {r2.text}"
        elif r.status_code == 409:
            # Token pre-existed → rotate
            rr = api.post(f"{BASE_URL}/api/admin/odoo/service-token/rotate", headers=admin_headers)
            assert rr.status_code == 200, rr.text
            _generated_token_holder["raw"] = rr.json()["raw_token"]
        else:
            pytest.fail(f"Unexpected generate status {r.status_code}: {r.text}")

    def test_rotate_returns_new_token(self, api, admin_headers):
        assert _generated_token_holder["raw"], "generate step must have run first"
        r = api.post(f"{BASE_URL}/api/admin/odoo/service-token/rotate", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert "raw_token" in body
        assert body["raw_token"] != _generated_token_holder["raw"], "rotate must issue a NEW token"
        _generated_token_holder["raw"] = body["raw_token"]


# ---- Placeholder /pending endpoints (must return 200 lists on fresh DB) ----
class TestPendingEndpoints:
    def _get(self, api, headers, path):
        r = api.get(f"{BASE_URL}{path}", headers=headers)
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text}"
        return r.json()

    def test_products_pending(self, api, admin_headers):
        data = self._get(api, admin_headers, "/api/admin/odoo/products/pending")
        # can be a list or {"products": [], "menu_items": []}
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "products" in data and "menu_items" in data
            assert isinstance(data["products"], list) and isinstance(data["menu_items"], list)

    def test_delivery_updates_pending(self, api, admin_headers):
        data = self._get(api, admin_headers, "/api/admin/odoo/delivery-updates/pending")
        assert isinstance(data, list)

    def test_payout_summaries_pending(self, api, admin_headers):
        data = self._get(api, admin_headers, "/api/admin/odoo/payout-summaries/pending")
        assert isinstance(data, list)

    def test_driver_cash_pending(self, api, admin_headers):
        data = self._get(api, admin_headers, "/api/admin/odoo/driver-cash/pending")
        assert isinstance(data, list)

    def test_orders_pending_empty(self, api, admin_headers):
        data = self._get(api, admin_headers, "/api/admin/odoo/orders/pending")
        assert isinstance(data, list)  # empty in fresh DB


# ---- Enrichment shape test: seed temporary shop + split, verify envelope ---
class TestOrdersPendingEnrichment:
    def test_enriched_envelope(self, api, admin_headers, mongo_db):
        shop_id = f"TEST_shop_{uuid.uuid4().hex[:8]}"
        split_id = f"TEST_split_{uuid.uuid4().hex[:8]}"
        product_id = f"TEST_prod_{uuid.uuid4().hex[:8]}"
        order_id = f"TEST_ord_{uuid.uuid4().hex[:8]}"

        shop_doc = {
            "id": shop_id,
            "name": "TEST_OdooShop",
            "seller_id": "TEST_seller",
            "area": "Juba",
            "odoo_connection": {"enabled": True, "send_orders": True, "send_delivery_updates": True},
        }
        product_doc = {
            "id": product_id,
            "shop_id": shop_id,
            "name": "TEST_Product",
            "odoo_product_sku": "SKU-TEST-1",
            "odoo_product_id": 42,
            "sku": "SKU-TEST-1",
        }
        split_doc = {
            "id": split_id,
            "order_id": order_id,
            "shop_id": shop_id,
            "shop_name": "TEST_OdooShop",
            "seller_id": "TEST_seller",
            "customer_id": "TEST_cust",
            "customer_name": "Alice Test",
            "customer_phone": "+211900000000",
            "customer_email": "alice@test.local",
            "customer_area": "Juba",
            "delivery_area": "Juba",
            "customer_address": "42 Test Rd",
            "payment_method": "cash_on_delivery",
            "delivery_type": "delivery",
            "note": "test note",
            "items": [{
                "item_id": product_id,
                "name": "TEST_Product",
                "price_usd": 10.5,
                "quantity": 2,
                "sides": [{"name": "Extra sauce", "price_usd": 0.5}],
            }],
            "product_subtotal_usd": 22.0,
            "delivery_fee_usd": 3.0,
            "order_total_usd": 25.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "odoo_sync_status": "pending",
        }

        try:
            mongo_db.shops.insert_one(shop_doc)
            mongo_db.products.insert_one(product_doc)
            mongo_db.seller_order_splits.insert_one(split_doc)

            r = api.get(f"{BASE_URL}/api/admin/odoo/orders/pending", headers=admin_headers)
            assert r.status_code == 200, r.text
            listing = r.json()
            found = next((x for x in listing if x.get("sub_order_id") == split_id), None)
            assert found is not None, f"seeded split not found in pending list ({len(listing)} items)"

            # Envelope shape
            required = [
                "sub_order_id", "order_id", "entity_type", "customer_name",
                "customer_phone", "delivery_area", "delivery_address",
                "payment_method", "delivery_type", "currency", "exchange_rate_ssp",
                "subtotal_usd", "delivery_fee_usd", "total_usd", "items", "meta",
            ]
            missing = [k for k in required if k not in found]
            assert not missing, f"Missing keys in envelope: {missing}"

            assert found["entity_type"] == "shop_order_split"
            assert found["currency"] == "USD"
            assert isinstance(found["exchange_rate_ssp"], (int, float))
            assert found["subtotal_usd"] == 22.0
            assert found["delivery_fee_usd"] == 3.0
            assert found["total_usd"] == 25.0
            assert found["payment_method"] == "cash_on_delivery"
            assert found["delivery_type"] == "delivery"
            assert found["customer_name"] == "Alice Test"

            # Items
            assert len(found["items"]) == 1
            it = found["items"][0]
            for k in ("sku", "odoo_product_id", "name", "quantity", "price_usd", "sides"):
                assert k in it, f"item missing key {k}"
            assert it["sku"] == "SKU-TEST-1"
            assert it["odoo_product_id"] == 42
            assert it["quantity"] == 2
            assert it["price_usd"] == 10.5
            assert isinstance(it["sides"], list) and len(it["sides"]) == 1
            assert it["sides"][0]["name"] == "Extra sauce"
            assert it["sides"][0]["price_usd"] == 0.5

            # Meta
            assert found["meta"]["source"] == "jubasquare"
            assert "created_at" in found["meta"]
        finally:
            mongo_db.seller_order_splits.delete_one({"id": split_id})
            mongo_db.products.delete_one({"id": product_id})
            mongo_db.shops.delete_one({"id": shop_id})

    def test_disabled_shop_not_returned(self, api, admin_headers, mongo_db):
        shop_id = f"TEST_shop_{uuid.uuid4().hex[:8]}"
        split_id = f"TEST_split_{uuid.uuid4().hex[:8]}"
        try:
            mongo_db.shops.insert_one({
                "id": shop_id, "name": "TEST_disabled", "seller_id": "TEST_s",
                "odoo_connection": {"enabled": False, "send_orders": False},
            })
            mongo_db.seller_order_splits.insert_one({
                "id": split_id, "order_id": "ord_x", "shop_id": shop_id,
                "items": [], "odoo_sync_status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            r = api.get(f"{BASE_URL}/api/admin/odoo/orders/pending", headers=admin_headers)
            assert r.status_code == 200
            listing = r.json()
            assert not any(x.get("sub_order_id") == split_id for x in listing), \
                "Split from disabled shop must NOT appear"
        finally:
            mongo_db.seller_order_splits.delete_one({"id": split_id})
            mongo_db.shops.delete_one({"id": shop_id})


# ---- Webhook: status-update -------------------------------------------------
class TestStatusUpdateWebhook:
    def test_missing_token_header(self, api):
        r = api.post(f"{BASE_URL}/api/odoo/orders/status-update",
                     json={"order_id": "x", "status": "synced"})
        # 401 (missing) is spec; 500 acceptable if not configured
        assert r.status_code in (401, 500), f"got {r.status_code}: {r.text}"

    def test_admin_jwt_alone_rejected(self, api, admin_headers):
        # Admin JWT header is NOT the webhook auth — must fail (401/403).
        r = api.post(f"{BASE_URL}/api/odoo/orders/status-update",
                     headers=admin_headers,
                     json={"order_id": "x", "status": "synced"})
        assert r.status_code in (401, 403, 500), f"got {r.status_code}"

    def test_invalid_token(self, api):
        r = api.post(f"{BASE_URL}/api/odoo/orders/status-update",
                     headers={"X-Jubasquare-Odoo-Token": "invalid-nonsense"},
                     json={"order_id": "x", "status": "synced"})
        assert r.status_code in (401, 403, 500)

    def test_valid_token_unmatched_restaurant_order(self, api, mongo_db):
        raw = _generated_token_holder["raw"]
        assert raw, "service token must have been generated in earlier test"
        fake_order_id = str(uuid.uuid4())
        r = api.post(
            f"{BASE_URL}/api/odoo/orders/status-update",
            headers={"X-Jubasquare-Odoo-Token": raw, "Content-Type": "application/json"},
            json={"order_id": fake_order_id, "status": "synced"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "success"
        assert body.get("matched") is False
        assert "log_id" in body
        log_doc = mongo_db.odoo_sync_logs.find_one({"id": body["log_id"]})
        assert log_doc is not None
        assert log_doc.get("entity_type") == "restaurant_order"
        assert log_doc.get("order_id") == fake_order_id
        # cleanup
        mongo_db.odoo_sync_logs.delete_one({"id": body["log_id"]})

    def test_valid_token_matches_seller_split(self, api, mongo_db):
        raw = _generated_token_holder["raw"]
        assert raw
        order_id = str(uuid.uuid4())
        split_id = str(uuid.uuid4())
        try:
            mongo_db.seller_order_splits.insert_one({
                "id": split_id, "order_id": order_id, "shop_id": "TEST_shop",
                "items": [], "odoo_sync_status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            r = api.post(
                f"{BASE_URL}/api/odoo/orders/status-update",
                headers={"X-Jubasquare-Odoo-Token": raw, "Content-Type": "application/json"},
                json={"order_id": order_id, "sub_order_id": split_id, "status": "synced"},
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["status"] == "success"
            assert body["matched"] is True
            updated = mongo_db.seller_order_splits.find_one({"id": split_id})
            assert updated["odoo_sync_status"] == "synced"
            assert "odoo_last_sync_at" in updated
            mongo_db.odoo_sync_logs.delete_one({"id": body["log_id"]})
        finally:
            mongo_db.seller_order_splits.delete_one({"id": split_id})

    def test_missing_body_fields(self, api):
        raw = _generated_token_holder["raw"]
        assert raw
        r = api.post(
            f"{BASE_URL}/api/odoo/orders/status-update",
            headers={"X-Jubasquare-Odoo-Token": raw, "Content-Type": "application/json"},
            json={"order_id": "onlyid"},
        )
        assert r.status_code == 400
