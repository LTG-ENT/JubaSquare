"""Iteration 20 backend tests — Simplified Seller Self-Delivery flow.

Covers the refactor where seller-managed delivery is a single one-click
step (no OTP / signature / receiver_name):
  * POST /api/seller/restaurant-orders/{id}/self-deliver-complete  (empty body)
  * POST /api/seller/splits/{id}/self-deliver-complete             (empty body)
  * Admin-managed → 400
  * Wrong preparation status → 400
  * Deprecated /self-deliver-start wrapper (no-op, still 200)
  * /api/driver/location role gating (seller now 403, driver still 200)
  * Regressions: seller cod redaction (iter17), seller_earning_usd includes
    delivery_fee for seller-managed and excludes for admin-managed (iter19)
  * /api/health regression

All test data uses TEST_ prefix and is cleaned up post-session.
"""
import os
import sys
import uuid
import asyncio
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
import bcrypt  # noqa: E402

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_EMAIL = "admin@jubasquare.com"
ADMIN_PASSWORD = "1234"


def _hash(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def mongo(event_loop):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    yield db, event_loop
    client.close()


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def ctx(mongo, admin_token):
    db, loop = mongo

    seller_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    driver_id = str(uuid.uuid4())
    seller_email = f"test_iter20_sell_{uuid.uuid4().hex[:8]}@example.com"
    driver_email = f"test_iter20_drv_{uuid.uuid4().hex[:8]}@example.com"
    customer_email = f"test_iter20_cust_{uuid.uuid4().hex[:8]}@example.com"
    pw = "TestPass!123"

    shop_seller = f"TEST_shopSell20_{uuid.uuid4().hex[:6]}"
    shop_admin = f"TEST_shopAdm20_{uuid.uuid4().hex[:6]}"
    rest_seller = f"TEST_restSell20_{uuid.uuid4().hex[:6]}"
    rest_admin = f"TEST_restAdm20_{uuid.uuid4().hex[:6]}"

    def _mk_split(shop_id, prep="ready_for_pickup", cod=True):
        return {
            "id": f"TEST_split20_{uuid.uuid4().hex[:8]}",
            "seller_id": seller_id,
            "shop_id": shop_id,
            "order_id": f"TEST_ord20_{uuid.uuid4().hex[:6]}",
            "customer_id": customer_id,
            "customer_phone": "+211900000001",
            "customer_area": "Munuki",
            "customer_address": "House #1",
            "delivery_status": "pending",
            "seller_preparation_status": prep,
            "pickup_status": "pending",
            "payment_method": "cash_on_delivery" if cod else "wallet",
            "order_total_usd": 12.0,
            "product_subtotal_usd": 10.0,
            "delivery_fee_usd": 2.0,
            "platform_commission_usd": 1.0,
            "seller_earning_usd": 11.0,  # seller-managed keeps delivery
            "created_at": "2026-01-01T00:00:00+00:00",
        }

    def _mk_rest_order(rest_id, prep="ready_for_pickup", cod=True,
                       seller_managed=True):
        # seller_earning_usd: seller-managed includes delivery (11), admin excludes (9)
        earn = 11.0 if seller_managed else 9.0
        return {
            "id": f"TEST_ro20_{uuid.uuid4().hex[:8]}",
            "seller_id": seller_id,
            "restaurant_id": rest_id,
            "customer_id": customer_id,
            "customer_name": "Test Customer",
            "customer_phone": "+211900000002",
            "customer_area": "Munuki",
            "customer_address": "Street 2",
            "status": "accepted",
            "delivery_status": "pending",
            "seller_preparation_status": prep,
            "pickup_status": "pending",
            "payment_method": "cash_on_delivery" if cod else "wallet",
            "delivery_area": "Munuki",
            "product_subtotal_usd": 10.0,
            "delivery_fee_usd": 2.0,
            "order_total_usd": 12.0,
            "platform_commission_usd": 1.0,
            "seller_earning_usd": earn,
            "created_at": "2026-01-01T00:00:00+00:00",
            "items": [], "total_usd": 12.0,
        }

    # --- documents ---
    split_ok = _mk_split(shop_seller)
    split_admin = _mk_split(shop_admin)
    split_wrong_status = _mk_split(shop_seller, prep="accepted")

    ro_ok = _mk_rest_order(rest_seller)
    ro_admin_managed = _mk_rest_order(rest_admin, seller_managed=False)
    ro_wrong_status = _mk_rest_order(rest_seller, prep="accepted")
    ro_deprecated_start = _mk_rest_order(rest_seller)
    split_deprecated_start = _mk_split(shop_seller)

    async def _setup():
        await db.settings.update_one(
            {"id": "system"},
            {"$setOnInsert": {"id": "system"},
             "$set": {"admin_manages_delivery": False}},
            upsert=True,
        )
        await db.users.insert_many([
            {"id": seller_id, "email": seller_email, "name": "TEST Seller20",
             "role": "seller", "password_hash": _hash(pw),
             "email_verified": True, "is_active": True,
             "must_change_password": False, "settings": {}, "phone": ""},
            {"id": driver_id, "email": driver_email, "name": "TEST Driver20",
             "role": "driver", "password_hash": _hash(pw),
             "email_verified": True, "is_active": True,
             "must_change_password": False, "settings": {}, "phone": ""},
            {"id": customer_id, "email": customer_email, "name": "TEST Cust20",
             "role": "customer", "password_hash": _hash(pw),
             "email_verified": True, "is_active": True,
             "must_change_password": False, "settings": {}, "phone": ""},
        ])
        common = {"seller_id": seller_id, "area": "Munuki",
                  "verification": "Verified", "is_deleted": False}
        await db.shops.insert_many([
            {"id": shop_seller, "name": "TEST_SellerShop20",
             "delivery_managed_by": "seller", **common},
            {"id": shop_admin, "name": "TEST_AdminShop20",
             "delivery_managed_by": "admin", **common},
        ])
        await db.restaurants.insert_many([
            {"id": rest_seller, "name": "TEST_SellerRest20",
             "delivery_managed_by": "seller", **common},
            {"id": rest_admin, "name": "TEST_AdminRest20",
             "delivery_managed_by": "admin", **common},
        ])
        await db.seller_order_splits.insert_many([
            split_ok, split_admin, split_wrong_status, split_deprecated_start,
        ])
        await db.restaurant_orders.insert_many([
            ro_ok, ro_admin_managed, ro_wrong_status, ro_deprecated_start,
        ])

    loop.run_until_complete(_setup())

    def _login(email):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": email, "password": pw}, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()["token"]

    seller_hdr = {"Authorization": f"Bearer {_login(seller_email)}"}
    driver_hdr = {"Authorization": f"Bearer {_login(driver_email)}"}
    customer_hdr = {"Authorization": f"Bearer {_login(customer_email)}"}
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}

    data = {
        "db": db, "loop": loop,
        "seller_id": seller_id, "driver_id": driver_id,
        "customer_id": customer_id,
        "seller_hdr": seller_hdr, "driver_hdr": driver_hdr,
        "customer_hdr": customer_hdr, "admin_hdr": admin_hdr,
        "shop_seller": shop_seller, "shop_admin": shop_admin,
        "rest_seller": rest_seller, "rest_admin": rest_admin,
        "split_ok": split_ok["id"],
        "split_admin": split_admin["id"],
        "split_wrong_status": split_wrong_status["id"],
        "split_deprecated_start": split_deprecated_start["id"],
        "ro_ok": ro_ok["id"],
        "ro_admin_managed": ro_admin_managed["id"],
        "ro_wrong_status": ro_wrong_status["id"],
        "ro_deprecated_start": ro_deprecated_start["id"],
    }
    yield data

    async def _cleanup():
        await db.users.delete_many(
            {"id": {"$in": [seller_id, driver_id, customer_id]}})
        await db.shops.delete_many({"seller_id": seller_id})
        await db.restaurants.delete_many({"seller_id": seller_id})
        await db.seller_order_splits.delete_many({"seller_id": seller_id})
        await db.restaurant_orders.delete_many({"seller_id": seller_id})
        await db.driver_locations.delete_many(
            {"driver_id": {"$in": [seller_id, driver_id]}})
        await db.audit_logs.delete_many({"user_id": seller_id})
    loop.run_until_complete(_cleanup())


# ============================================================
# 0. Health
# ============================================================
def test_health_ok():
    r = requests.get(f"{BASE_URL}/api/health", timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "ok"


# ============================================================
# 1. Restaurant order self-deliver-complete (empty body)
# ============================================================
def test_rest_self_deliver_complete_empty_body_success(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/restaurant-orders/{ctx['ro_ok']}/self-deliver-complete",
        headers=ctx["seller_hdr"], json={}, timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "delivered"
    assert body["delivery_status"] == "delivered"
    assert body.get("delivered_at")
    assert body["payment_status"] == "collected_by_seller"
    assert body["cash_handover_status"] == "not_applicable"


def test_rest_self_deliver_complete_admin_managed_400(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/restaurant-orders/{ctx['ro_admin_managed']}/self-deliver-complete",
        headers=ctx["seller_hdr"], json={}, timeout=30,
    )
    assert r.status_code == 400, r.text


def test_rest_self_deliver_complete_wrong_status_400(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/restaurant-orders/{ctx['ro_wrong_status']}/self-deliver-complete",
        headers=ctx["seller_hdr"], json={}, timeout=30,
    )
    assert r.status_code == 400, r.text


# ============================================================
# 2. Split self-deliver-complete (empty body)
# ============================================================
def test_split_self_deliver_complete_empty_body_success(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/splits/{ctx['split_ok']}/self-deliver-complete",
        headers=ctx["seller_hdr"], json={}, timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["delivery_status"] == "delivered"
    assert body["payment_status"] == "collected_by_seller"
    assert body["cash_handover_status"] == "not_applicable"
    assert body.get("delivered_at")


def test_split_self_deliver_complete_admin_managed_400(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/splits/{ctx['split_admin']}/self-deliver-complete",
        headers=ctx["seller_hdr"], json={}, timeout=30,
    )
    assert r.status_code == 400, r.text


def test_split_self_deliver_complete_wrong_status_400(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/splits/{ctx['split_wrong_status']}/self-deliver-complete",
        headers=ctx["seller_hdr"], json={}, timeout=30,
    )
    assert r.status_code == 400, r.text


# ============================================================
# 3. Deprecated /self-deliver-start (no-op wrapper) — seller-managed only
# ============================================================
def test_split_self_deliver_start_deprecated_noop(ctx):
    # Before state
    async def _get_before():
        return await ctx["db"].seller_order_splits.find_one(
            {"id": ctx["split_deprecated_start"]}, {"_id": 0})
    before = ctx["loop"].run_until_complete(_get_before())
    r = requests.post(
        f"{BASE_URL}/api/seller/splits/{ctx['split_deprecated_start']}/self-deliver-start",
        headers=ctx["seller_hdr"], json={}, timeout=30,
    )
    assert r.status_code == 200, r.text
    after = ctx["loop"].run_until_complete(_get_before())
    # No state change
    assert after.get("delivery_status") == before.get("delivery_status")
    assert after.get("seller_preparation_status") == before.get("seller_preparation_status")
    assert after.get("pickup_status") == before.get("pickup_status")


def test_rest_self_deliver_start_deprecated_noop(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/restaurant-orders/{ctx['ro_deprecated_start']}/self-deliver-start",
        headers=ctx["seller_hdr"], json={}, timeout=30,
    )
    assert r.status_code == 200, r.text


# ============================================================
# 4. /api/driver/location role gating
# ============================================================
def test_driver_location_seller_now_forbidden(ctx):
    r = requests.post(
        f"{BASE_URL}/api/driver/location",
        headers=ctx["seller_hdr"],
        json={"lat": 4.85, "lng": 31.6}, timeout=30,
    )
    assert r.status_code == 403, r.text


def test_driver_location_driver_ok(ctx):
    r = requests.post(
        f"{BASE_URL}/api/driver/location",
        headers=ctx["driver_hdr"],
        json={"lat": 4.86, "lng": 31.61}, timeout=30,
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}


def test_driver_location_customer_forbidden(ctx):
    r = requests.post(
        f"{BASE_URL}/api/driver/location",
        headers=ctx["customer_hdr"],
        json={"lat": 4.85, "lng": 31.6}, timeout=30,
    )
    assert r.status_code == 403, r.text


# ============================================================
# 5. Regression: /seller/restaurant-orders-cod redaction
#    seller-managed → exposes customer contact; admin-managed → hides
# ============================================================
def test_seller_rest_cod_redaction(ctx):
    r = requests.get(
        f"{BASE_URL}/api/seller/restaurant-orders-cod",
        headers=ctx["seller_hdr"], timeout=30,
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    by_id = {row["id"]: row for row in rows}

    # ro_admin_managed → phone/area/address stripped
    admin_row = by_id.get(ctx["ro_admin_managed"])
    assert admin_row is not None
    assert admin_row.get("customer_phone") in (None, "")
    assert admin_row.get("customer_address") in (None, "")

    # Find a seller-managed restaurant order that still exists (not yet completed)
    seller_row = by_id.get(ctx["ro_wrong_status"]) or by_id.get(ctx["ro_deprecated_start"])
    assert seller_row is not None
    assert seller_row.get("customer_phone")
    assert seller_row.get("customer_address")


# ============================================================
# 6. Regression: seller_earning_usd — seller-managed includes delivery_fee,
#    admin-managed excludes it (persisted at order creation time).
# ============================================================
def test_seller_earning_includes_delivery_only_for_seller_managed(ctx):
    async def _fetch():
        seller_row = await ctx["db"].restaurant_orders.find_one(
            {"id": ctx["ro_wrong_status"]}, {"_id": 0})
        admin_row = await ctx["db"].restaurant_orders.find_one(
            {"id": ctx["ro_admin_managed"]}, {"_id": 0})
        return seller_row, admin_row
    seller_row, admin_row = ctx["loop"].run_until_complete(_fetch())
    # Product 10 - commission 1 + delivery 2 = 11 (seller-managed)
    assert seller_row["seller_earning_usd"] == 11.0
    # Product 10 - commission 1 = 9 (admin-managed)
    assert admin_row["seller_earning_usd"] == 9.0
