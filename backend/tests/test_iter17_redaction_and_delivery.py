"""Iteration 17 backend tests

Verifies that customer contact info (phone, area, address) is exposed to a
seller ONLY when the seller manages delivery for the corresponding shop /
restaurant (i.e. the seller IS the driver). When admin manages delivery,
seller-facing responses NULL out those fields. customer_name is NEVER
redacted. Admin responses always see the full contact info.

Endpoints exercised:
  * GET /api/seller/restaurant-orders-cod
  * GET /api/restaurant-orders/restaurant/{restaurant_id}   (Kitchen)
  * GET /api/restaurant-orders/{order_id}
  * GET /api/orders/seller
  * GET /api/seller/splits
  * platform-toggle path (settings.admin_manages_delivery=True) with
    delivery_managed_by='default'

All ephemeral users/shops/restaurants/orders/splits/restaurant_orders are
cleaned up at the end of the session. Test data prefixed with TEST_.
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

CUST_PHONE = "+211900000001"
CUST_AREA = "Munuki"
CUST_ADDRESS = "TEST Street 42"
CUST_NAME = "TEST Customer"


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
    """Seed one seller with:
       - Restaurant A: delivery_managed_by='seller'  → expose contacts
       - Restaurant B: delivery_managed_by='admin'   → redact contacts
       - Shop S: delivery_managed_by='seller'         → expose contacts
       - Shop T: delivery_managed_by='admin'          → redact contacts
       - Restaurant D: delivery_managed_by='default'  → follow platform toggle
       - Shop U: delivery_managed_by='default'        → follow platform toggle
       Also creates a product per shop (needed for /orders/seller lookup).
       Then inserts restaurant_orders / orders / seller_order_splits docs
       with customer contact info populated.
    """
    db, loop = mongo

    seller_id = str(uuid.uuid4())
    seller_email = f"test_seller_{uuid.uuid4().hex[:8]}@example.com"
    seller_password = "TestPass!123"

    # IDs we'll use
    rest_a = f"TEST_restA_{uuid.uuid4().hex[:6]}"
    rest_b = f"TEST_restB_{uuid.uuid4().hex[:6]}"
    rest_d = f"TEST_restD_{uuid.uuid4().hex[:6]}"
    shop_s = f"TEST_shopS_{uuid.uuid4().hex[:6]}"
    shop_t = f"TEST_shopT_{uuid.uuid4().hex[:6]}"
    shop_u = f"TEST_shopU_{uuid.uuid4().hex[:6]}"
    prod_s = f"TEST_prodS_{uuid.uuid4().hex[:6]}"
    prod_t = f"TEST_prodT_{uuid.uuid4().hex[:6]}"
    prod_u = f"TEST_prodU_{uuid.uuid4().hex[:6]}"

    ro_a = f"TEST_roA_{uuid.uuid4().hex[:6]}"
    ro_b = f"TEST_roB_{uuid.uuid4().hex[:6]}"
    ro_d = f"TEST_roD_{uuid.uuid4().hex[:6]}"
    ord_s = f"TEST_ordS_{uuid.uuid4().hex[:6]}"
    ord_t = f"TEST_ordT_{uuid.uuid4().hex[:6]}"
    split_s = f"TEST_splitS_{uuid.uuid4().hex[:6]}"
    split_t = f"TEST_splitT_{uuid.uuid4().hex[:6]}"

    async def _setup():
        # Ensure platform default is admin_manages_delivery=False initially
        await db.settings.update_one(
            {"id": "system"},
            {"$setOnInsert": {"id": "system"}, "$set": {
                "require_verification": True,
                "admin_manages_delivery": False,
                "auto_approve_shops": False,
            }},
            upsert=True,
        )
        await db.users.insert_one({
            "id": seller_id, "email": seller_email, "name": "TEST Seller",
            "role": "seller", "phone": "", "password_hash": _hash(seller_password),
            "email_verified": True, "is_active": True,
            "must_change_password": False, "settings": {},
        })
        common = {"seller_id": seller_id, "area": "Munuki",
                  "verification": "Verified", "is_deleted": False}
        await db.restaurants.insert_many([
            {"id": rest_a, "name": "TEST_RestA", "delivery_managed_by": "seller", **common},
            {"id": rest_b, "name": "TEST_RestB", "delivery_managed_by": "admin", **common},
            {"id": rest_d, "name": "TEST_RestD", "delivery_managed_by": "default", **common},
        ])
        await db.shops.insert_many([
            {"id": shop_s, "name": "TEST_ShopS", "delivery_managed_by": "seller", **common},
            {"id": shop_t, "name": "TEST_ShopT", "delivery_managed_by": "admin", **common},
            {"id": shop_u, "name": "TEST_ShopU", "delivery_managed_by": "default", **common},
        ])
        await db.products.insert_many([
            {"id": prod_s, "shop_id": shop_s, "seller_id": seller_id,
             "name": "TEST_ProdS", "price_usd": 5.0, "verification": "Verified"},
            {"id": prod_t, "shop_id": shop_t, "seller_id": seller_id,
             "name": "TEST_ProdT", "price_usd": 5.0, "verification": "Verified"},
            {"id": prod_u, "shop_id": shop_u, "seller_id": seller_id,
             "name": "TEST_ProdU", "price_usd": 5.0, "verification": "Verified"},
        ])

        # restaurant_orders with customer contact filled
        base_ro = {
            "customer_id": "TEST_cust_x",
            "customer_name": CUST_NAME,
            "customer_phone": CUST_PHONE,
            "customer_area": CUST_AREA,
            "customer_address": CUST_ADDRESS,
            "seller_id": seller_id,
            "status": "pending",
            "delivery_status": "pending",
            "created_at": "2026-01-01T00:00:00+00:00",
            "items": [], "total_usd": 10.0,
        }
        await db.restaurant_orders.insert_many([
            {**base_ro, "id": ro_a, "restaurant_id": rest_a},
            {**base_ro, "id": ro_b, "restaurant_id": rest_b},
            {**base_ro, "id": ro_d, "restaurant_id": rest_d},
        ])

        # marketplace `orders` docs containing product refs
        base_ord = {
            "customer_id": "TEST_cust_x",
            "customer_name": CUST_NAME,
            "customer_phone": CUST_PHONE,
            "customer_area": CUST_AREA,
            "customer_address": CUST_ADDRESS,
            "phone": CUST_PHONE, "area": CUST_AREA, "address": CUST_ADDRESS,
            "status": "pending",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        await db.orders.insert_many([
            {**base_ord, "id": ord_s, "items": [{"item_id": prod_s, "quantity": 1, "price_usd": 5.0}]},
            {**base_ord, "id": ord_t, "items": [{"item_id": prod_t, "quantity": 1, "price_usd": 5.0}]},
        ])

        # seller_order_splits pointing to shops S / T
        base_split = {
            "seller_id": seller_id,
            "customer_id": "TEST_cust_x",
            "customer_name": CUST_NAME,
            "customer_phone": CUST_PHONE,
            "customer_area": CUST_AREA,
            "customer_address": CUST_ADDRESS,
            "phone": CUST_PHONE, "area": CUST_AREA, "address": CUST_ADDRESS,
            "delivery_status": "pending",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        await db.seller_order_splits.insert_many([
            {**base_split, "id": split_s, "shop_id": shop_s, "order_id": ord_s},
            {**base_split, "id": split_t, "shop_id": shop_t, "order_id": ord_t},
        ])
    loop.run_until_complete(_setup())

    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": seller_email, "password": seller_password}, timeout=30)
    assert r.status_code == 200, r.text
    seller_token = r.json()["token"]

    data = {
        "db": db, "loop": loop,
        "seller_id": seller_id,
        "seller_hdr": {"Authorization": f"Bearer {seller_token}"},
        "admin_hdr": {"Authorization": f"Bearer {admin_token}"},
        "rest_a": rest_a, "rest_b": rest_b, "rest_d": rest_d,
        "shop_s": shop_s, "shop_t": shop_t, "shop_u": shop_u,
        "prod_s": prod_s, "prod_t": prod_t, "prod_u": prod_u,
        "ro_a": ro_a, "ro_b": ro_b, "ro_d": ro_d,
        "ord_s": ord_s, "ord_t": ord_t,
        "split_s": split_s, "split_t": split_t,
    }
    yield data

    async def _cleanup():
        await db.users.delete_one({"id": seller_id})
        await db.restaurants.delete_many({"seller_id": seller_id})
        await db.shops.delete_many({"seller_id": seller_id})
        await db.products.delete_many({"seller_id": seller_id})
        await db.restaurant_orders.delete_many({"seller_id": seller_id})
        await db.orders.delete_many({"customer_id": "TEST_cust_x"})
        await db.seller_order_splits.delete_many({"seller_id": seller_id})
        # Restore default platform toggle
        await db.settings.update_one({"id": "system"},
                                     {"$set": {"admin_manages_delivery": False}})
    loop.run_until_complete(_cleanup())


# ---------- helpers ----------

def _by_id(rows, oid):
    for r in rows:
        if r.get("id") == oid:
            return r
    return None


def _assert_exposed(o, tag):
    assert o is not None, f"{tag}: order not found in response"
    assert o.get("customer_name") == CUST_NAME, f"{tag}: name must always be visible"
    assert o.get("customer_phone") == CUST_PHONE, f"{tag}: customer_phone should be exposed"
    assert o.get("customer_area") == CUST_AREA, f"{tag}: customer_area should be exposed"
    assert o.get("customer_address") == CUST_ADDRESS, f"{tag}: customer_address should be exposed"


def _assert_redacted(o, tag):
    assert o is not None, f"{tag}: order not found in response"
    # customer_name NEVER redacted
    assert o.get("customer_name") == CUST_NAME, f"{tag}: name must always be visible"
    assert o.get("customer_phone") is None, f"{tag}: customer_phone MUST be null, got {o.get('customer_phone')!r}"
    assert o.get("customer_area") is None, f"{tag}: customer_area MUST be null"
    assert o.get("customer_address") is None, f"{tag}: customer_address MUST be null"


def _assert_redacted_marketplace(o, tag):
    _assert_redacted(o, tag)
    # legacy fields (phone/area/address) also nulled on marketplace orders/splits
    assert o.get("phone") is None, f"{tag}: legacy phone MUST be null"
    assert o.get("area") is None, f"{tag}: legacy area MUST be null"
    assert o.get("address") is None, f"{tag}: legacy address MUST be null"


# ================================================================
# 1. /api/seller/restaurant-orders-cod
# ================================================================

def test_seller_rest_cod_exposes_A_redacts_B(ctx):
    r = requests.get(f"{BASE_URL}/api/seller/restaurant-orders-cod",
                     headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    rows = r.json()
    _assert_exposed(_by_id(rows, ctx["ro_a"]), "seller-cod RestA(seller)")
    _assert_redacted(_by_id(rows, ctx["ro_b"]), "seller-cod RestB(admin)")


# ================================================================
# 2. GET /api/restaurant-orders/restaurant/{id}  (Kitchen)
# ================================================================

def test_kitchen_A_exposes_contacts(ctx):
    r = requests.get(f"{BASE_URL}/api/restaurant-orders/restaurant/{ctx['rest_a']}",
                     headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    _assert_exposed(_by_id(r.json(), ctx["ro_a"]), "kitchen RestA(seller)")


def test_kitchen_B_redacts_contacts(ctx):
    r = requests.get(f"{BASE_URL}/api/restaurant-orders/restaurant/{ctx['rest_b']}",
                     headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    _assert_redacted(_by_id(r.json(), ctx["ro_b"]), "kitchen RestB(admin)")


# ================================================================
# 3. GET /api/restaurant-orders/{order_id}
# ================================================================

def test_single_restaurant_order_A_exposes(ctx):
    r = requests.get(f"{BASE_URL}/api/restaurant-orders/{ctx['ro_a']}",
                     headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    _assert_exposed(r.json(), "single RestA(seller)")


def test_single_restaurant_order_B_redacts(ctx):
    r = requests.get(f"{BASE_URL}/api/restaurant-orders/{ctx['ro_b']}",
                     headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    _assert_redacted(r.json(), "single RestB(admin)")


# ================================================================
# 4. /api/orders/seller  (marketplace orders)
# ================================================================

def test_orders_seller_S_exposes_T_redacts(ctx):
    r = requests.get(f"{BASE_URL}/api/orders/seller",
                     headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    rows = r.json()
    ord_s = _by_id(rows, ctx["ord_s"])
    ord_t = _by_id(rows, ctx["ord_t"])
    _assert_exposed(ord_s, "orders/seller ShopS(seller)")
    # marketplace order should also keep legacy phone/area/address
    assert ord_s.get("phone") == CUST_PHONE
    assert ord_s.get("address") == CUST_ADDRESS
    _assert_redacted_marketplace(ord_t, "orders/seller ShopT(admin)")


# ================================================================
# 5. /api/seller/splits
# ================================================================

def test_seller_splits_S_exposes_T_redacts(ctx):
    r = requests.get(f"{BASE_URL}/api/seller/splits",
                     headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    rows = r.json()
    sp_s = _by_id(rows, ctx["split_s"])
    sp_t = _by_id(rows, ctx["split_t"])
    _assert_exposed(sp_s, "splits ShopS(seller)")
    assert sp_s.get("phone") == CUST_PHONE
    _assert_redacted_marketplace(sp_t, "splits ShopT(admin)")


# ================================================================
# 6. Regression: admin always sees full contacts
# ================================================================

def test_admin_sees_full_contacts_everywhere(ctx):
    # kitchen (both A and B) as admin
    for rid, tag in [(ctx["rest_a"], "admin kitchen A"),
                     (ctx["rest_b"], "admin kitchen B")]:
        r = requests.get(f"{BASE_URL}/api/restaurant-orders/restaurant/{rid}",
                         headers=ctx["admin_hdr"], timeout=30)
        assert r.status_code == 200, r.text
        # Admin path skips redaction; check the seeded order specifically
        seeded_id = ctx["ro_a"] if rid == ctx["rest_a"] else ctx["ro_b"]
        _assert_exposed(_by_id(r.json(), seeded_id), tag)

    # single restaurant-order as admin
    r = requests.get(f"{BASE_URL}/api/restaurant-orders/{ctx['ro_b']}",
                     headers=ctx["admin_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    _assert_exposed(r.json(), "admin single RestB")

    # /api/orders/seller for admin — admin has no products, will get []
    # so we skip that admin-branch check (endpoint requires seller/admin
    # and filters by items; admin has no seller products).


# ================================================================
# 7. Regression: customer_name NEVER redacted (implicitly checked above,
#    but explicit assertion for clarity on the redacted paths)
# ================================================================

def test_customer_name_never_redacted(ctx):
    r = requests.get(f"{BASE_URL}/api/restaurant-orders/{ctx['ro_b']}",
                     headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert body["customer_name"] == CUST_NAME
    assert body["customer_phone"] is None


# ================================================================
# 8. Platform-toggle path — delivery_managed_by='default'
# ================================================================

def _set_admin_manages(ctx, value: bool):
    async def _op():
        await ctx["db"].settings.update_one(
            {"id": "system"}, {"$set": {"admin_manages_delivery": value}}
        )
    ctx["loop"].run_until_complete(_op())


def test_platform_toggle_off_default_exposes(ctx):
    """admin_manages_delivery=False + delivery_managed_by='default'
    → seller manages → exposed."""
    _set_admin_manages(ctx, False)
    # Restaurant D via /seller/restaurant-orders-cod
    r = requests.get(f"{BASE_URL}/api/seller/restaurant-orders-cod",
                     headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200
    _assert_exposed(_by_id(r.json(), ctx["ro_d"]),
                    "toggle-OFF default RestD (should expose)")


def test_platform_toggle_on_default_redacts(ctx):
    """admin_manages_delivery=True + delivery_managed_by='default'
    → admin manages → redacted."""
    _set_admin_manages(ctx, True)
    try:
        r = requests.get(f"{BASE_URL}/api/seller/restaurant-orders-cod",
                         headers=ctx["seller_hdr"], timeout=30)
        assert r.status_code == 200
        _assert_redacted(_by_id(r.json(), ctx["ro_d"]),
                         "toggle-ON default RestD (should redact)")
        # Also confirm B (explicit admin) stays redacted
        _assert_redacted(_by_id(r.json(), ctx["ro_b"]),
                         "toggle-ON explicit-admin RestB")
        # And A (explicit seller) still exposed regardless of toggle
        _assert_exposed(_by_id(r.json(), ctx["ro_a"]),
                        "toggle-ON explicit-seller RestA")
    finally:
        _set_admin_manages(ctx, False)


def test_platform_toggle_single_order_default(ctx):
    """Verify /restaurant-orders/{id} also honors the toggle for default entities."""
    _set_admin_manages(ctx, True)
    try:
        r = requests.get(f"{BASE_URL}/api/restaurant-orders/{ctx['ro_d']}",
                         headers=ctx["seller_hdr"], timeout=30)
        assert r.status_code == 200
        _assert_redacted(r.json(), "single RestD toggle-ON")
    finally:
        _set_admin_manages(ctx, False)
        r = requests.get(f"{BASE_URL}/api/restaurant-orders/{ctx['ro_d']}",
                         headers=ctx["seller_hdr"], timeout=30)
        assert r.status_code == 200
        _assert_exposed(r.json(), "single RestD toggle-OFF")
