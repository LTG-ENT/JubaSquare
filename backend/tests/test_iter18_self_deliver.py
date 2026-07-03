"""Iteration 18 backend tests — Seller self-delivery flow.

Covers:
  * POST /api/seller/splits/{id}/self-deliver-start (success / 400 / 403)
  * POST /api/seller/splits/{id}/self-deliver-complete (success / 400 for
    invalid otp, not_started, short signature)
  * POST /api/seller/restaurant-orders/{id}/self-deliver-start & complete
  * POST /api/driver/location for role=seller / role=driver / forbidden roles
  * GET /api/customer/orders/{id}/live-tracking includes seller-as-driver
  * GET /api/health regression

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

DELIVERY_OTP = "424242"
SIG = "SGVsbG9EZWxpdmVyeVBpY3R1cmVFbmNvZGVk"  # 36 chars base64-ish
SHORT_SIG = "short"  # 5 chars


def _hash(pw): return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


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
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def ctx(mongo, admin_token):
    db, loop = mongo

    # Two sellers (owner + other), one customer, one driver.
    seller_id = str(uuid.uuid4())
    other_seller_id = str(uuid.uuid4())
    driver_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())

    seller_email = f"test_selfdel_{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"test_other_{uuid.uuid4().hex[:8]}@example.com"
    driver_email = f"test_driver_{uuid.uuid4().hex[:8]}@example.com"
    customer_email = f"test_cust_{uuid.uuid4().hex[:8]}@example.com"
    pw = "TestPass!123"

    # Two shops (seller-managed & admin-managed), two restaurants (same).
    shop_seller = f"TEST_shopSell_{uuid.uuid4().hex[:6]}"
    shop_admin = f"TEST_shopAdm_{uuid.uuid4().hex[:6]}"
    rest_seller = f"TEST_restSell_{uuid.uuid4().hex[:6]}"

    # Splits + restaurant_orders (multiple, one per subtest).
    def _mk_split(shop_id, ready=True, cod=True):
        return {
            "id": f"TEST_split_{uuid.uuid4().hex[:8]}",
            "seller_id": seller_id,
            "shop_id": shop_id,
            "order_id": f"TEST_ord_{uuid.uuid4().hex[:6]}",
            "customer_id": customer_id,
            "delivery_status": "pending",
            "seller_preparation_status": "ready_for_pickup" if ready else "accepted",
            "pickup_status": "pending",
            "customer_delivery_otp": DELIVERY_OTP,
            "payment_method": "cash_on_delivery" if cod else "wallet",
            "created_at": "2026-01-01T00:00:00+00:00",
        }

    def _mk_rest_order(rest_id, ready=True, cod=True):
        return {
            "id": f"TEST_ro_{uuid.uuid4().hex[:8]}",
            "seller_id": seller_id,
            "restaurant_id": rest_id,
            "customer_id": customer_id,
            "status": "accepted",
            "delivery_status": "pending",
            "seller_preparation_status": "ready_for_pickup" if ready else "accepted",
            "pickup_status": "pending",
            "customer_delivery_otp": DELIVERY_OTP,
            "payment_method": "cash_on_delivery" if cod else "wallet",
            "delivery_area": "Munuki",
            "created_at": "2026-01-01T00:00:00+00:00",
            "items": [], "total_usd": 10.0,
        }

    # Pre-create documents needed across many tests.
    split_ok = _mk_split(shop_seller)                 # for successful start+complete
    split_admin_shop = _mk_split(shop_admin)          # 400 (admin-managed)
    split_not_ready = _mk_split(shop_seller, ready=False)  # 400 (not ready)
    split_wrong_owner = _mk_split(shop_seller)        # 403
    split_wrong_owner["seller_id"] = other_seller_id
    split_for_otp = _mk_split(shop_seller)            # 400 invalid otp
    split_before_start = _mk_split(shop_seller)       # 400 complete before start
    split_short_sig = _mk_split(shop_seller)          # 400 short signature

    ro_ok = _mk_rest_order(rest_seller)
    ro_tracking = _mk_rest_order(rest_seller)  # used for live-tracking test

    async def _setup():
        await db.settings.update_one(
            {"id": "system"},
            {"$setOnInsert": {"id": "system"},
             "$set": {"admin_manages_delivery": False}},
            upsert=True,
        )
        await db.users.insert_many([
            {"id": seller_id, "email": seller_email, "name": "TEST Seller",
             "role": "seller", "password_hash": _hash(pw),
             "email_verified": True, "is_active": True,
             "must_change_password": False, "settings": {}, "phone": ""},
            {"id": other_seller_id, "email": other_email, "name": "TEST Other",
             "role": "seller", "password_hash": _hash(pw),
             "email_verified": True, "is_active": True,
             "must_change_password": False, "settings": {}, "phone": ""},
            {"id": driver_id, "email": driver_email, "name": "TEST Driver",
             "role": "driver", "password_hash": _hash(pw),
             "email_verified": True, "is_active": True,
             "must_change_password": False, "settings": {}, "phone": ""},
            {"id": customer_id, "email": customer_email, "name": "TEST Customer",
             "role": "customer", "password_hash": _hash(pw),
             "email_verified": True, "is_active": True,
             "must_change_password": False, "settings": {}, "phone": ""},
        ])
        common = {"seller_id": seller_id, "area": "Munuki",
                  "verification": "Verified", "is_deleted": False}
        await db.shops.insert_many([
            {"id": shop_seller, "name": "TEST_SellerShop", "delivery_managed_by": "seller", **common},
            {"id": shop_admin, "name": "TEST_AdminShop", "delivery_managed_by": "admin", **common},
        ])
        await db.restaurants.insert_one(
            {"id": rest_seller, "name": "TEST_SellerRest",
             "delivery_managed_by": "seller", **common}
        )
        await db.seller_order_splits.insert_many([
            split_ok, split_admin_shop, split_not_ready, split_wrong_owner,
            split_for_otp, split_before_start, split_short_sig,
        ])
        await db.restaurant_orders.insert_many([ro_ok, ro_tracking])

    loop.run_until_complete(_setup())

    def _login(email):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": email, "password": pw}, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()["token"]

    seller_hdr = {"Authorization": f"Bearer {_login(seller_email)}"}
    other_hdr = {"Authorization": f"Bearer {_login(other_email)}"}
    driver_hdr = {"Authorization": f"Bearer {_login(driver_email)}"}
    customer_hdr = {"Authorization": f"Bearer {_login(customer_email)}"}
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}

    data = {
        "db": db, "loop": loop,
        "seller_id": seller_id, "driver_id": driver_id,
        "customer_id": customer_id, "other_seller_id": other_seller_id,
        "seller_hdr": seller_hdr, "other_hdr": other_hdr,
        "driver_hdr": driver_hdr, "customer_hdr": customer_hdr,
        "admin_hdr": admin_hdr,
        "shop_seller": shop_seller, "shop_admin": shop_admin,
        "rest_seller": rest_seller,
        "split_ok": split_ok["id"],
        "split_admin_shop": split_admin_shop["id"],
        "split_not_ready": split_not_ready["id"],
        "split_wrong_owner": split_wrong_owner["id"],
        "split_for_otp": split_for_otp["id"],
        "split_before_start": split_before_start["id"],
        "split_short_sig": split_short_sig["id"],
        "ro_ok": ro_ok["id"],
        "ro_tracking": ro_tracking["id"],
    }
    yield data

    async def _cleanup():
        await db.users.delete_many(
            {"id": {"$in": [seller_id, other_seller_id, driver_id, customer_id]}})
        await db.shops.delete_many({"seller_id": seller_id})
        await db.restaurants.delete_many({"seller_id": seller_id})
        await db.seller_order_splits.delete_many({"seller_id": {"$in": [seller_id, other_seller_id]}})
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
    body = r.json()
    assert body.get("status") == "ok"


# ============================================================
# 1. /seller/splits/{id}/self-deliver-start
# ============================================================

def test_split_self_deliver_start_success(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/splits/{ctx['split_ok']}/self-deliver-start",
        headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["driver_id"] == ctx["seller_id"]
    assert body["pickup_status"] == "picked_up"
    assert body["seller_handover_status"] == "handed_to_driver"
    assert body["delivery_status"] == "out_for_delivery"
    assert body["self_delivered_by_seller"] is True


def test_split_self_deliver_start_admin_managed_400(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/splits/{ctx['split_admin_shop']}/self-deliver-start",
        headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 400, r.text


def test_split_self_deliver_start_not_ready_400(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/splits/{ctx['split_not_ready']}/self-deliver-start",
        headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 400, r.text


def test_split_self_deliver_start_wrong_owner_403(ctx):
    # other seller tries to start
    r = requests.post(
        f"{BASE_URL}/api/seller/splits/{ctx['split_wrong_owner']}/self-deliver-start",
        headers=ctx["seller_hdr"], timeout=30)
    # seller (in seller_hdr) is not the owner of split_wrong_owner (owned by other)
    assert r.status_code == 403, r.text


# ============================================================
# 2. /seller/splits/{id}/self-deliver-complete
# ============================================================

def test_split_self_deliver_complete_success(ctx):
    # split_ok has already been started in test above; complete it now.
    r = requests.post(
        f"{BASE_URL}/api/seller/splits/{ctx['split_ok']}/self-deliver-complete",
        headers=ctx["seller_hdr"],
        json={"otp": DELIVERY_OTP, "signature_b64": SIG, "receiver_name": "Alice"},
        timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["delivery_status"] == "delivered"
    assert body["proof_of_delivery_status"] == "submitted"
    assert body.get("delivered_at")
    # COD-specific
    assert body["payment_status"] == "collected_by_seller"
    assert body["cash_handover_status"] == "not_applicable"


def test_split_complete_before_start_400(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/splits/{ctx['split_before_start']}/self-deliver-complete",
        headers=ctx["seller_hdr"],
        json={"otp": DELIVERY_OTP, "signature_b64": SIG, "receiver_name": "Bob"},
        timeout=30)
    assert r.status_code == 400, r.text


def test_split_complete_invalid_otp_400(ctx):
    # First start delivery on the split_for_otp
    r = requests.post(
        f"{BASE_URL}/api/seller/splits/{ctx['split_for_otp']}/self-deliver-start",
        headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    # Now try to complete with bad otp
    r = requests.post(
        f"{BASE_URL}/api/seller/splits/{ctx['split_for_otp']}/self-deliver-complete",
        headers=ctx["seller_hdr"],
        json={"otp": "000000", "signature_b64": SIG, "receiver_name": "Bob"},
        timeout=30)
    assert r.status_code == 400, r.text


def test_split_complete_short_signature_400(ctx):
    # First start delivery on the split_short_sig
    r = requests.post(
        f"{BASE_URL}/api/seller/splits/{ctx['split_short_sig']}/self-deliver-start",
        headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    r = requests.post(
        f"{BASE_URL}/api/seller/splits/{ctx['split_short_sig']}/self-deliver-complete",
        headers=ctx["seller_hdr"],
        json={"otp": DELIVERY_OTP, "signature_b64": SHORT_SIG, "receiver_name": "Bob"},
        timeout=30)
    # Pydantic min_length=10 -> 422, endpoint check -> 400. Accept either.
    assert r.status_code in (400, 422), r.text


# ============================================================
# 3. /seller/restaurant-orders/{id}/self-deliver-start & complete
# ============================================================

def test_rest_self_deliver_start_success(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/restaurant-orders/{ctx['ro_ok']}/self-deliver-start",
        headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["driver_id"] == ctx["seller_id"]
    assert body["delivery_status"] == "out_for_delivery"
    assert body["status"] == "out_for_delivery"
    assert body["self_delivered_by_seller"] is True


def test_rest_self_deliver_complete_success(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/restaurant-orders/{ctx['ro_ok']}/self-deliver-complete",
        headers=ctx["seller_hdr"],
        json={"otp": DELIVERY_OTP, "signature_b64": SIG, "receiver_name": "Alice"},
        timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["delivery_status"] == "delivered"
    assert body["status"] == "delivered"
    assert body["cash_handover_status"] == "not_applicable"
    assert body["payment_status"] == "collected_by_seller"


# ============================================================
# 4. POST /api/driver/location — role gating
# ============================================================

def test_driver_location_seller_ok(ctx):
    r = requests.post(f"{BASE_URL}/api/driver/location",
                      headers=ctx["seller_hdr"],
                      json={"lat": 4.85, "lng": 31.6}, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    # Verify doc created
    async def _check():
        doc = await ctx["db"].driver_locations.find_one(
            {"driver_id": ctx["seller_id"]}, {"_id": 0})
        assert doc is not None
        assert doc["lat"] == 4.85 and doc["lng"] == 31.6
    ctx["loop"].run_until_complete(_check())


def test_driver_location_driver_ok(ctx):
    r = requests.post(f"{BASE_URL}/api/driver/location",
                      headers=ctx["driver_hdr"],
                      json={"lat": 4.86, "lng": 31.61}, timeout=30)
    assert r.status_code == 200, r.text


def test_driver_location_customer_forbidden(ctx):
    r = requests.post(f"{BASE_URL}/api/driver/location",
                      headers=ctx["customer_hdr"],
                      json={"lat": 4.85, "lng": 31.6}, timeout=30)
    assert r.status_code == 403, r.text


def test_driver_location_admin_forbidden(ctx):
    r = requests.post(f"{BASE_URL}/api/driver/location",
                      headers=ctx["admin_hdr"],
                      json={"lat": 4.85, "lng": 31.6}, timeout=30)
    assert r.status_code == 403, r.text


# ============================================================
# 5. Live tracking includes seller-as-driver
# ============================================================

def test_live_tracking_reflects_seller_driver(ctx):
    # Start self-delivery for ro_tracking (this sets driver_id=seller,
    # status='out_for_delivery').
    r = requests.post(
        f"{BASE_URL}/api/seller/restaurant-orders/{ctx['ro_tracking']}/self-deliver-start",
        headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    # Seller pushes GPS
    r = requests.post(f"{BASE_URL}/api/driver/location",
                      headers=ctx["seller_hdr"],
                      json={"lat": 4.851, "lng": 31.605}, timeout=30)
    assert r.status_code == 200, r.text
    # Customer queries live tracking
    r = requests.get(
        f"{BASE_URL}/api/customer/orders/{ctx['ro_tracking']}/live-tracking",
        headers=ctx["customer_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assignments = body.get("assignments", [])
    assert len(assignments) >= 1, f"No assignments returned: {body}"
    seller_assn = next((a for a in assignments if a["driver_id"] == ctx["seller_id"]), None)
    assert seller_assn is not None, f"Seller assignment missing: {assignments}"
    loc = seller_assn.get("driver_location")
    assert loc is not None, "driver_location should be populated"
    assert abs(loc["lat"] - 4.851) < 1e-6
    assert abs(loc["lng"] - 31.605) < 1e-6
