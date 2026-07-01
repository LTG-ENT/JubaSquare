"""
Iteration 12: Odoo Service Token Management tests.

Covers:
  - GET    /api/admin/odoo/service-token          (admin JWT only)
  - POST   /api/admin/odoo/service-token/generate (admin JWT only, 409 if exists)
  - POST   /api/admin/odoo/service-token/rotate   (admin JWT only)
  - Webhook auth source-of-truth switching (DB takes precedence over env)
  - Previous (rotated-out) token must stop working immediately
  - Service token must NOT be allowed to manage itself

Cleans the `odoo_service_tokens` collection at module start so the state is
deterministic, then leaves a fresh DB-managed token active at the end.

Raw token VALUES are never printed.
"""
import os
import asyncio
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://jubasquare-odoo-v2.preview.emergentagent.com",
).rstrip("/")


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


ENV_ODOO_TOKEN = _load_env_value("ODOO_WEBHOOK_TOKEN")
MONGO_URL = _load_env_value("MONGO_URL")
DB_NAME = _load_env_value("DB_NAME")

ADMIN_EMAIL = "admin@LTG.com"
ADMIN_PASSWORD = "Kokobleake1"
SELLER_CREDS = [
    ("seller@demo.com", "Demo1234!"),
    ("seller@demo.com", "1234"),
    # Fallback test user seeded directly into DB by the testing agent for
    # this iteration because seller@demo.com is not present in this env.
    ("test_seller_iter12@demo.com", "TestPass1234!"),
]

# Shared state across tests
STATE = {
    "admin_jwt": None,
    "seller_jwt": None,
    "first_raw_token": None,
    "rotated_raw_token": None,
}


# ---------- module-level setup: clear DB tokens ----------
@pytest.fixture(scope="module", autouse=True)
def _clean_token_collection():
    async def _wipe():
        client = AsyncIOMotorClient(MONGO_URL)
        try:
            await client[DB_NAME].odoo_service_tokens.delete_many({})
        finally:
            client.close()
    asyncio.get_event_loop().run_until_complete(_wipe())
    yield
    # Teardown: nothing — we intentionally leave the last rotated token in place.


# ---------- 0. Auth helpers ----------
def _login(email: str, password: str):
    return requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )


def test_00_login_admin():
    r = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    STATE["admin_jwt"] = r.json()["token"]
    assert STATE["admin_jwt"]


def test_01_login_seller():
    last = None
    for email, pwd in SELLER_CREDS:
        r = _login(email, pwd)
        last = r
        if r.status_code == 200:
            STATE["seller_jwt"] = r.json()["token"]
            return
    pytest.skip(f"Seller login failed for all candidates (last status={last.status_code if last else 'n/a'})")


# ---------- 1. GET service-token auth gating ----------
def test_10_get_status_requires_auth():
    r = requests.get(f"{BASE_URL}/api/admin/odoo/service-token", timeout=10)
    assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"


def test_11_get_status_rejects_service_token_header():
    # Service token must NOT be allowed to read/manage itself.
    # At this point DB is clean; env fallback would otherwise authorize webhook
    # endpoints, but management endpoints are admin-JWT-only.
    r = requests.get(
        f"{BASE_URL}/api/admin/odoo/service-token",
        headers={"X-JubaSquare-Odoo-Token": ENV_ODOO_TOKEN},
        timeout=10,
    )
    assert r.status_code in (401, 403), f"service token should NOT manage itself, got {r.status_code}"


def test_12_get_status_with_admin_initially_env():
    # DB cleared → expect env fallback
    r = requests.get(
        f"{BASE_URL}/api/admin/odoo/service-token",
        headers={"Authorization": f"Bearer {STATE['admin_jwt']}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("status", "source", "masked_preview", "created_at", "last_rotated_at", "created_by"):
        assert k in data, f"missing key {k} in {list(data.keys())}"
    assert data["source"] in ("env", None)
    if ENV_ODOO_TOKEN:
        assert data["source"] == "env"
        assert data["status"] == "active"
    # raw token must never appear
    assert "raw_token" not in data
    assert "token_hash" not in data


# ---------- 2. Generate endpoint ----------
def test_20_generate_requires_auth():
    r = requests.post(f"{BASE_URL}/api/admin/odoo/service-token/generate", timeout=10)
    assert r.status_code in (401, 403)


def test_21_generate_rejects_non_admin():
    if not STATE.get("seller_jwt"):
        pytest.skip("no seller jwt")
    r = requests.post(
        f"{BASE_URL}/api/admin/odoo/service-token/generate",
        headers={"Authorization": f"Bearer {STATE['seller_jwt']}"},
        timeout=10,
    )
    assert r.status_code == 403, f"expected 403 for non-admin got {r.status_code}"


def test_22_generate_success_admin():
    r = requests.post(
        f"{BASE_URL}/api/admin/odoo/service-token/generate",
        headers={"Authorization": f"Bearer {STATE['admin_jwt']}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "raw_token" in data and isinstance(data["raw_token"], str)
    assert len(data["raw_token"]) == 64, "raw token should be 64 hex chars"
    assert all(c in "0123456789abcdef" for c in data["raw_token"])
    assert "masked_preview" in data and data["masked_preview"].endswith(data["raw_token"][-4:])
    assert "warning" in data
    STATE["first_raw_token"] = data["raw_token"]


def test_23_generate_twice_returns_409():
    r = requests.post(
        f"{BASE_URL}/api/admin/odoo/service-token/generate",
        headers={"Authorization": f"Bearer {STATE['admin_jwt']}"},
        timeout=10,
    )
    assert r.status_code == 409, f"expected 409 got {r.status_code} {r.text}"


def test_24_status_after_generate_reports_database():
    r = requests.get(
        f"{BASE_URL}/api/admin/odoo/service-token",
        headers={"Authorization": f"Bearer {STATE['admin_jwt']}"},
        timeout=10,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "database"
    assert data["status"] == "active"
    assert data["created_by"] == ADMIN_EMAIL or (data["created_by"] or "").lower() == ADMIN_EMAIL.lower()
    assert "raw_token" not in data
    # masked preview should end with the last 4 chars of the issued raw token
    assert data["masked_preview"].endswith(STATE["first_raw_token"][-4:])


# ---------- 3. Env token must stop working after DB token issued ----------
def test_30_env_token_revoked_after_db_token_exists():
    r = requests.get(
        f"{BASE_URL}/api/admin/odoo/shops",
        headers={"X-JubaSquare-Odoo-Token": ENV_ODOO_TOKEN},
        timeout=10,
    )
    assert r.status_code == 403, f"env token must be rejected when DB token exists, got {r.status_code}"


def test_31_new_db_token_works_on_shops():
    r = requests.get(
        f"{BASE_URL}/api/admin/odoo/shops",
        headers={"X-JubaSquare-Odoo-Token": STATE["first_raw_token"]},
        timeout=10,
    )
    assert r.status_code == 200, f"new DB token should work, got {r.status_code} {r.text}"


def test_32_new_db_token_passes_webhook_auth_on_upsert():
    # Webhook auth must accept it; payload may be invalid (400/422) but NOT 401/403
    r = requests.post(
        f"{BASE_URL}/api/odoo/products/upsert",
        headers={"X-JubaSquare-Odoo-Token": STATE["first_raw_token"]},
        json={},  # intentionally empty
        timeout=10,
    )
    assert r.status_code not in (401, 403), f"webhook auth failed with new token: {r.status_code} {r.text}"


def test_33_odoo_health_reports_configured():
    r = requests.get(f"{BASE_URL}/api/odoo/health", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data.get("webhook_configured") is True


# ---------- 4. Rotate endpoint ----------
def test_40_rotate_requires_auth():
    r = requests.post(f"{BASE_URL}/api/admin/odoo/service-token/rotate", timeout=10)
    assert r.status_code in (401, 403)


def test_41_rotate_rejects_non_admin():
    if not STATE.get("seller_jwt"):
        pytest.skip("no seller jwt")
    r = requests.post(
        f"{BASE_URL}/api/admin/odoo/service-token/rotate",
        headers={"Authorization": f"Bearer {STATE['seller_jwt']}"},
        timeout=10,
    )
    assert r.status_code == 403


def test_42_rotate_rejects_service_token_header():
    # Service token must NOT be allowed to rotate itself
    r = requests.post(
        f"{BASE_URL}/api/admin/odoo/service-token/rotate",
        headers={"X-JubaSquare-Odoo-Token": STATE["first_raw_token"]},
        timeout=10,
    )
    assert r.status_code in (401, 403), f"service token cannot rotate itself, got {r.status_code}"


def test_43_rotate_success():
    r = requests.post(
        f"{BASE_URL}/api/admin/odoo/service-token/rotate",
        headers={"Authorization": f"Bearer {STATE['admin_jwt']}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "raw_token" in data and len(data["raw_token"]) == 64
    assert data["raw_token"] != STATE["first_raw_token"], "rotate must produce a different token"
    assert data.get("last_rotated_at") is not None
    assert "warning" in data and "revoked" in data["warning"].lower()
    STATE["rotated_raw_token"] = data["raw_token"]


def test_44_previous_token_revoked_after_rotate():
    r = requests.get(
        f"{BASE_URL}/api/admin/odoo/shops",
        headers={"X-JubaSquare-Odoo-Token": STATE["first_raw_token"]},
        timeout=10,
    )
    assert r.status_code == 403, f"old token must be revoked after rotate, got {r.status_code}"


def test_45_new_rotated_token_works():
    r = requests.get(
        f"{BASE_URL}/api/admin/odoo/shops",
        headers={"X-JubaSquare-Odoo-Token": STATE["rotated_raw_token"]},
        timeout=10,
    )
    assert r.status_code == 200, f"new rotated token must work, got {r.status_code} {r.text}"


def test_46_status_reflects_last_rotated_at():
    r = requests.get(
        f"{BASE_URL}/api/admin/odoo/service-token",
        headers={"Authorization": f"Bearer {STATE['admin_jwt']}"},
        timeout=10,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "database"
    assert data["last_rotated_at"] is not None
    assert data["masked_preview"].endswith(STATE["rotated_raw_token"][-4:])
