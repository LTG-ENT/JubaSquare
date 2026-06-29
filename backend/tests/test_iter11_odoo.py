"""
Iteration 11: Odoo 18 integration verification tests.
Verifies fixes for:
 - product upsert writes to `stock` (primary) and `stock_quantity` (metadata)
 - `category_id` required on upsert (Pydantic 422)
 - `seller_id` auto-derived from shop/restaurant owner
 - admin Odoo endpoints accept JWT OR X-JubaSquare-Odoo-Token, but service
   token does NOT work on other admin endpoints
 - pending endpoints return real (non-placeholder) shapes
"""
import os
import uuid
import asyncio
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://locale-switcher-5.preview.emergentagent.com").rstrip("/")

# Load backend .env directly for the service token
def _load_env_value(key: str) -> str:
    try:
        with open("/app/backend/.env", "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""

ODOO_TOKEN = _load_env_value("ODOO_WEBHOOK_TOKEN")
MONGO_URL = _load_env_value("MONGO_URL").strip('"')
DB_NAME = _load_env_value("DB_NAME").strip('"')

ADMIN_EMAIL = "admin@LTG.com"
ADMIN_PASSWORD = "Kokobleake1"

# Track created product for cleanup
_CREATED = {"product_id": None, "shop_id": None, "odoo_product_id": None}


# ---------- fixtures ----------

@pytest.fixture(scope="session")
def admin_jwt():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def test_shop():
    r = requests.get(f"{BASE_URL}/api/shops", timeout=15)
    assert r.status_code == 200
    data = r.json()
    shops = data if isinstance(data, list) else data.get("shops", [])
    assert shops, "No shops available to run test"
    return shops[0]


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def mongo_db(event_loop):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    yield db
    client.close()


# ---------- Public health check ----------

class TestOdooHealth:
    def test_health_public_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/odoo/health", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["webhook_configured"] is True


# ---------- Webhook auth on /api/odoo/products/upsert ----------

class TestOdooUpsertAuth:
    UPSERT = f"{BASE_URL}/api/odoo/products/upsert"
    valid_payload = {
        "shop_id": "any",
        "odoo_product_id": "p1",
        "name": "x",
        "price": 1.0,
        "category_id": "cat-1",
    }

    def test_missing_token_returns_401(self):
        r = requests.post(self.UPSERT, json=self.valid_payload, timeout=10)
        assert r.status_code == 401, r.text

    def test_wrong_token_returns_403(self):
        r = requests.post(
            self.UPSERT,
            json=self.valid_payload,
            headers={"X-JubaSquare-Odoo-Token": "definitely-not-the-token"},
            timeout=10,
        )
        assert r.status_code == 403, r.text

    def test_missing_category_id_returns_422(self):
        payload = {
            "shop_id": "any",
            "odoo_product_id": "p1",
            "name": "x",
            "price": 1.0,
            # category_id intentionally missing
        }
        r = requests.post(
            self.UPSERT,
            json=payload,
            headers={"X-JubaSquare-Odoo-Token": ODOO_TOKEN},
            timeout=10,
        )
        assert r.status_code == 422, r.text

    def test_missing_shop_and_restaurant_returns_400(self):
        payload = {
            "odoo_product_id": "p1",
            "name": "x",
            "price": 1.0,
            "category_id": "cat-1",
        }
        r = requests.post(
            self.UPSERT,
            json=payload,
            headers={"X-JubaSquare-Odoo-Token": ODOO_TOKEN},
            timeout=10,
        )
        assert r.status_code == 400, r.text


# ---------- Odoo-disabled shop returns 200 ignored ----------

class TestOdooDisabledShop:
    def test_upsert_against_disabled_shop_returns_ignored(self, mongo_db, event_loop):
        # Find or create a shop where odoo_connection.enabled is false/missing
        async def find_disabled():
            doc = await mongo_db.shops.find_one(
                {"$or": [
                    {"odoo_connection.enabled": {"$ne": True}},
                    {"odoo_connection": {"$exists": False}},
                ]},
                {"id": 1},
            )
            return doc
        shop = event_loop.run_until_complete(find_disabled())
        assert shop, "No Odoo-disabled shop available"
        payload = {
            "shop_id": shop["id"],
            "odoo_product_id": f"disabled-{uuid.uuid4().hex[:8]}",
            "name": "disabled-shop-product",
            "price": 1.0,
            "category_id": "cat-x",
        }
        r = requests.post(
            f"{BASE_URL}/api/odoo/products/upsert",
            json=payload,
            headers={"X-JubaSquare-Odoo-Token": ODOO_TOKEN},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "ignored"


# ---------- End-to-end: enable Odoo, upsert, verify product, stock-update ----------

class TestOdooE2EProductFlow:
    def test_e2e_upsert_and_stock_update(self, mongo_db, event_loop, test_shop):
        shop_id = test_shop["id"]
        seller_id = test_shop["seller_id"]
        _CREATED["shop_id"] = shop_id
        odoo_pid = f"odoo-{uuid.uuid4().hex[:10]}"
        _CREATED["odoo_product_id"] = odoo_pid
        category_id = f"cat-{uuid.uuid4().hex[:8]}"

        # 1) enable odoo on shop
        async def enable():
            await mongo_db.shops.update_one(
                {"id": shop_id},
                {"$set": {"odoo_connection.enabled": True}},
            )
        event_loop.run_until_complete(enable())

        # 2) upsert product
        payload = {
            "shop_id": shop_id,
            "odoo_product_id": odoo_pid,
            "odoo_product_sku": "SKU-TEST",
            "name": "TEST_OdooProduct",
            "description": "from odoo test",
            "price": 12.5,
            "image_url": "https://example.com/img.jpg",
            "stock_quantity": 42,
            "publish": True,
            "category_id": category_id,
        }
        r = requests.post(
            f"{BASE_URL}/api/odoo/products/upsert",
            json=payload,
            headers={"X-JubaSquare-Odoo-Token": ODOO_TOKEN},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "success"
        product_id = body["product_id"]
        _CREATED["product_id"] = product_id

        # 3) verify product fields in db
        async def fetch():
            return await mongo_db.products.find_one({"id": product_id}, {"_id": 0})
        prod = event_loop.run_until_complete(fetch())
        assert prod is not None, "product not persisted"
        assert prod.get("stock") == 42, f"stock != 42, got {prod.get('stock')}"
        assert prod.get("stock_quantity") == 42
        assert prod.get("category_id") == category_id
        assert prod.get("seller_id") == seller_id, f"seller_id mismatch: {prod.get('seller_id')} vs {seller_id}"
        assert prod.get("shop_id") == shop_id
        assert prod.get("is_active") is True
        assert prod.get("odoo_source") is True

        # 4) stock update -> both stock & stock_quantity become 7
        r2 = requests.post(
            f"{BASE_URL}/api/odoo/products/stock-update",
            json={"shop_id": shop_id, "odoo_product_id": odoo_pid, "stock_quantity": 7},
            headers={"X-JubaSquare-Odoo-Token": ODOO_TOKEN},
            timeout=15,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json().get("status") == "success"

        prod2 = event_loop.run_until_complete(fetch())
        assert prod2.get("stock") == 7
        assert prod2.get("stock_quantity") == 7

    def test_cleanup(self, mongo_db, event_loop):
        async def cleanup():
            if _CREATED["product_id"]:
                await mongo_db.products.delete_one({"id": _CREATED["product_id"]})
            await mongo_db.odoo_sync_logs.delete_many(
                {"shop_id": _CREATED["shop_id"], "request_payload.odoo_product_id": _CREATED["odoo_product_id"]}
            )
        event_loop.run_until_complete(cleanup())


# ---------- Admin Odoo endpoints: JWT OR service token ----------

class TestAdminOdooDualAuth:
    SHOPS_URL = f"{BASE_URL}/api/admin/odoo/shops"

    def test_no_auth_returns_401(self):
        r = requests.get(self.SHOPS_URL, timeout=10)
        assert r.status_code == 401, r.text

    def test_wrong_service_token_returns_403(self):
        r = requests.get(
            self.SHOPS_URL,
            headers={"X-JubaSquare-Odoo-Token": "wrong-token"},
            timeout=10,
        )
        assert r.status_code == 403, r.text

    def test_valid_service_token_returns_200(self):
        r = requests.get(
            self.SHOPS_URL,
            headers={"X-JubaSquare-Odoo-Token": ODOO_TOKEN},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_valid_admin_jwt_returns_200(self, admin_jwt):
        r = requests.get(
            self.SHOPS_URL,
            headers={"Authorization": f"Bearer {admin_jwt}"},
            timeout=10,
        )
        assert r.status_code == 200, r.text


# ---------- Service token must NOT bypass auth on non-Odoo admin endpoints ----------

class TestServiceTokenScope:
    def test_service_token_does_not_work_on_admin_users(self):
        # /api/admin/users should NOT accept service token
        r = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers={"X-JubaSquare-Odoo-Token": ODOO_TOKEN},
            timeout=10,
        )
        # We expect NOT 200 — typically 401 (no auth) or 403
        assert r.status_code != 200, f"Service token leaked to /api/admin/users: {r.status_code}"
        assert r.status_code in (401, 403), f"Unexpected status {r.status_code}: {r.text}"


# ---------- Pending endpoints return real shapes (not placeholders) ----------

class TestOdooPendingEndpoints:
    @pytest.fixture(autouse=True)
    def _auth(self):
        self.h = {"X-JubaSquare-Odoo-Token": ODOO_TOKEN}

    def test_products_pending(self):
        r = requests.get(f"{BASE_URL}/api/admin/odoo/products/pending", headers=self.h, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body, dict)
        assert "products" in body and "menu_items" in body
        assert isinstance(body["products"], list)
        assert isinstance(body["menu_items"], list)
        # must not be a placeholder shape
        assert "placeholder" not in str(body).lower() or body["products"] != [] or body["menu_items"] != [] or "status" not in body

    def test_orders_pending(self):
        r = requests.get(f"{BASE_URL}/api/admin/odoo/orders/pending", headers=self.h, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body, list)

    def test_delivery_updates_pending(self):
        r = requests.get(f"{BASE_URL}/api/admin/odoo/delivery-updates/pending", headers=self.h, timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_payout_summaries_pending(self):
        r = requests.get(f"{BASE_URL}/api/admin/odoo/payout-summaries/pending", headers=self.h, timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_driver_cash_pending(self):
        r = requests.get(f"{BASE_URL}/api/admin/odoo/driver-cash/pending", headers=self.h, timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)


# ---------- Confirmation doc no longer contains old token literal ----------

class TestConfirmationDoc:
    def test_no_juba_odoo_secure_in_doc(self):
        with open("/app/ODOO_INTEGRATION_CONFIRMATION.md", "r") as f:
            content = f.read()
        assert "juba-odoo-secure-" not in content, "Old token literal still present!"
