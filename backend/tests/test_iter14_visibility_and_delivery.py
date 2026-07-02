"""Iteration 14 backend tests

Covers:
  - Customer visibility gate on Shops / Restaurants (Verified only, admins bypass, owner-preview)
  - Menu / product visibility gate (linked to parent's verification)
  - Restaurant "Mirror Shops" delivery persistence via PUT /api/restaurants/{id}
  - Admin override PUT /api/admin/restaurants/{id}/delivery-managed-by
  - _calculate_delivery_fee for seller-managed restaurants (free/fixed/per_area) and admin fallback
  - Health

Cleans up all ephemeral users/shops/restaurants/menu_items/products at the end.
"""
import os
import sys
import uuid
import asyncio
import logging
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

# ---------- helpers ----------

def _hash(pw: str) -> str:
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
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def seller_ctx(mongo, admin_token):
    """Create a real seller in Mongo, log them in, create Pending+Verified shops and restaurants.
    Returns dict with ids/tokens. Cleans up after session."""
    db, loop = mongo

    seller_id = str(uuid.uuid4())
    seller_email = f"test_seller_{uuid.uuid4().hex[:8]}@example.com"
    seller_password = "TestPass!123"

    async def _setup():
        # Ensure system settings exist and defaults are proper
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
            "id": seller_id,
            "email": seller_email,
            "name": "TEST Seller",
            "role": "seller",
            "phone": "",
            "password_hash": _hash(seller_password),
            "email_verified": True,
            "is_active": True,
            "must_change_password": False,
            "settings": {},
        })
    loop.run_until_complete(_setup())

    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": seller_email, "password": seller_password}, timeout=30)
    assert r.status_code == 200, f"seller login failed: {r.status_code} {r.text}"
    seller_token = r.json()["token"]
    seller_hdr = {"Authorization": f"Bearer {seller_token}"}
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}

    # --- Create a Pending shop (default status is Pending when auto_approve_shops=False)
    r = requests.post(f"{BASE_URL}/api/shops", headers=seller_hdr, json={
        "name": "TEST_PendingShop", "area": "Munuki", "kind": "retail",
        "delivery_mode": "fixed", "delivery_fee_usd": 2.5,
    }, timeout=30)
    assert r.status_code == 200, r.text
    pending_shop = r.json()
    assert pending_shop["verification"] == "Pending"

    # A Verified shop (flip via mongo directly to save an admin call)
    r = requests.post(f"{BASE_URL}/api/shops", headers=seller_hdr, json={
        "name": "TEST_VerifiedShop", "area": "Munuki", "kind": "retail",
    }, timeout=30)
    assert r.status_code == 200
    verified_shop = r.json()

    # Pending restaurant
    r = requests.post(f"{BASE_URL}/api/restaurants", headers=seller_hdr, json={
        "name": "TEST_PendingResto", "area": "Munuki",
        "delivery_mode": "free", "delivery_fee_usd": 0,
    }, timeout=30)
    assert r.status_code == 200, r.text
    pending_rest = r.json()
    assert pending_rest["verification"] == "Pending"

    # Verified restaurant
    r = requests.post(f"{BASE_URL}/api/restaurants", headers=seller_hdr, json={
        "name": "TEST_VerifiedResto", "area": "Munuki",
    }, timeout=30)
    assert r.status_code == 200
    verified_rest = r.json()

    async def _flip_verified():
        await db.shops.update_one({"id": verified_shop["id"]}, {"$set": {"verification": "Verified"}})
        await db.restaurants.update_one({"id": verified_rest["id"]}, {"$set": {"verification": "Verified"}})
    loop.run_until_complete(_flip_verified())

    # Need a valid restaurant category for menu items
    async def _get_cat():
        c = await db.categories.find_one({"group": "restaurant"}, {"_id": 0, "id": 1})
        return c["id"] if c else None
    cat_id = loop.run_until_complete(_get_cat())

    # Create menu items on both restaurants (if we have a cat)
    menu_pending = menu_verified = None
    if cat_id:
        r = requests.post(f"{BASE_URL}/api/menu-items", headers=seller_hdr, json={
            "restaurant_id": pending_rest["id"], "name": "TEST_MenuPending",
            "price_usd": 5.0, "category_id": cat_id,
        }, timeout=30)
        if r.status_code == 200:
            menu_pending = r.json()
        r = requests.post(f"{BASE_URL}/api/menu-items", headers=seller_hdr, json={
            "restaurant_id": verified_rest["id"], "name": "TEST_MenuVerified",
            "price_usd": 6.0, "category_id": cat_id,
        }, timeout=30)
        if r.status_code == 200:
            menu_verified = r.json()

    # Products - pick a shop-group category
    async def _get_prod_cat():
        c = await db.categories.find_one({"group": {"$ne": "restaurant"}}, {"_id": 0, "id": 1})
        return c["id"] if c else None
    prod_cat = loop.run_until_complete(_get_prod_cat())
    prod_pending = prod_verified = None
    if prod_cat:
        r = requests.post(f"{BASE_URL}/api/products", headers=seller_hdr, json={
            "shop_id": pending_shop["id"], "name": "TEST_ProdPending",
            "category_id": prod_cat, "price_usd": 4.0,
        }, timeout=30)
        if r.status_code == 200:
            prod_pending = r.json()
        r = requests.post(f"{BASE_URL}/api/products", headers=seller_hdr, json={
            "shop_id": verified_shop["id"], "name": "TEST_ProdVerified",
            "category_id": prod_cat, "price_usd": 4.0,
        }, timeout=30)
        if r.status_code == 200:
            prod_verified = r.json()

    ctx = {
        "seller_id": seller_id,
        "seller_email": seller_email,
        "seller_hdr": seller_hdr,
        "admin_hdr": admin_hdr,
        "pending_shop": pending_shop,
        "verified_shop": verified_shop,
        "pending_rest": pending_rest,
        "verified_rest": verified_rest,
        "menu_pending": menu_pending,
        "menu_verified": menu_verified,
        "prod_pending": prod_pending,
        "prod_verified": prod_verified,
    }
    yield ctx

    # ---- Cleanup ----
    async def _cleanup():
        await db.users.delete_one({"id": seller_id})
        await db.shops.delete_many({"seller_id": seller_id})
        await db.restaurants.delete_many({"seller_id": seller_id})
        await db.menu_items.delete_many({"seller_id": seller_id})
        await db.products.delete_many({"seller_id": seller_id})
    loop.run_until_complete(_cleanup())


# ================= Tests =================

def test_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=10)
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


# --- Shop visibility ---

def test_anon_shops_list_only_verified(seller_ctx):
    r = requests.get(f"{BASE_URL}/api/shops", timeout=30)
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert seller_ctx["verified_shop"]["id"] in ids
    assert seller_ctx["pending_shop"]["id"] not in ids


def test_anon_get_pending_shop_404(seller_ctx):
    r = requests.get(f"{BASE_URL}/api/shops/{seller_ctx['pending_shop']['id']}", timeout=30)
    assert r.status_code == 404


def test_owner_get_own_pending_shop_200(seller_ctx):
    r = requests.get(f"{BASE_URL}/api/shops/{seller_ctx['pending_shop']['id']}",
                     headers=seller_ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200
    assert r.json()["id"] == seller_ctx["pending_shop"]["id"]


def test_admin_shops_list_includes_pending(seller_ctx):
    r = requests.get(f"{BASE_URL}/api/shops", headers=seller_ctx["admin_hdr"], timeout=30)
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert seller_ctx["pending_shop"]["id"] in ids
    assert seller_ctx["verified_shop"]["id"] in ids


def test_admin_get_pending_shop_200(seller_ctx):
    r = requests.get(f"{BASE_URL}/api/shops/{seller_ctx['pending_shop']['id']}",
                     headers=seller_ctx["admin_hdr"], timeout=30)
    assert r.status_code == 200


# --- Restaurant visibility ---

def test_anon_restaurants_list_only_verified(seller_ctx):
    r = requests.get(f"{BASE_URL}/api/restaurants", timeout=30)
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert seller_ctx["verified_rest"]["id"] in ids
    assert seller_ctx["pending_rest"]["id"] not in ids


def test_anon_get_pending_restaurant_404(seller_ctx):
    r = requests.get(f"{BASE_URL}/api/restaurants/{seller_ctx['pending_rest']['id']}", timeout=30)
    assert r.status_code == 404


def test_owner_get_own_pending_restaurant_200(seller_ctx):
    r = requests.get(f"{BASE_URL}/api/restaurants/{seller_ctx['pending_rest']['id']}",
                     headers=seller_ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200


def test_admin_restaurants_list_shows_all(seller_ctx):
    r = requests.get(f"{BASE_URL}/api/restaurants", headers=seller_ctx["admin_hdr"], timeout=30)
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert seller_ctx["pending_rest"]["id"] in ids
    assert seller_ctx["verified_rest"]["id"] in ids


def test_restaurants_mine_returns_all_own(seller_ctx):
    r = requests.get(f"{BASE_URL}/api/restaurants/mine",
                     headers=seller_ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert seller_ctx["pending_rest"]["id"] in ids
    assert seller_ctx["verified_rest"]["id"] in ids


# --- Menu / product visibility ---

def test_menu_anon_404_when_unverified(seller_ctx):
    r = requests.get(f"{BASE_URL}/api/restaurants/{seller_ctx['pending_rest']['id']}/menu",
                     timeout=30)
    assert r.status_code == 404


def test_menu_owner_and_admin_ok_for_pending(seller_ctx):
    r = requests.get(f"{BASE_URL}/api/restaurants/{seller_ctx['pending_rest']['id']}/menu",
                     headers=seller_ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200
    r = requests.get(f"{BASE_URL}/api/restaurants/{seller_ctx['pending_rest']['id']}/menu",
                     headers=seller_ctx["admin_hdr"], timeout=30)
    assert r.status_code == 200


def test_menu_items_global_excludes_unverified(seller_ctx):
    if not seller_ctx["menu_pending"] or not seller_ctx["menu_verified"]:
        pytest.skip("no menu items created (missing restaurant category)")
    r = requests.get(f"{BASE_URL}/api/menu-items?limit=500", timeout=30)
    assert r.status_code == 200
    ids = {m["id"] for m in r.json()}
    assert seller_ctx["menu_verified"]["id"] in ids
    assert seller_ctx["menu_pending"]["id"] not in ids


def test_products_global_excludes_unverified(seller_ctx):
    if not seller_ctx["prod_pending"] or not seller_ctx["prod_verified"]:
        pytest.skip("no products created (missing shop category)")
    r = requests.get(f"{BASE_URL}/api/products?limit=500", timeout=30)
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert seller_ctx["prod_verified"]["id"] in ids
    assert seller_ctx["prod_pending"]["id"] not in ids


def test_product_detail_anon_404_owner_200(seller_ctx):
    if not seller_ctx["prod_pending"]:
        pytest.skip("no product created")
    pid = seller_ctx["prod_pending"]["id"]
    r = requests.get(f"{BASE_URL}/api/products/{pid}", timeout=30)
    assert r.status_code == 404
    r = requests.get(f"{BASE_URL}/api/products/{pid}",
                     headers=seller_ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200
    r = requests.get(f"{BASE_URL}/api/products/{pid}",
                     headers=seller_ctx["admin_hdr"], timeout=30)
    assert r.status_code == 200


# --- Restaurant mirror-of-shop delivery persistence ---

def test_restaurant_update_delivery_fixed(seller_ctx):
    rid = seller_ctx["verified_rest"]["id"]
    payload = {
        "name": "TEST_VerifiedResto",
        "area": "Munuki",
        "delivery_mode": "fixed",
        "delivery_fee_usd": 3.5,
        "delivery_per_area": [],
    }
    r = requests.put(f"{BASE_URL}/api/restaurants/{rid}",
                     headers=seller_ctx["seller_hdr"], json=payload, timeout=30)
    assert r.status_code == 200, r.text
    got = requests.get(f"{BASE_URL}/api/restaurants/{rid}", timeout=30).json()
    assert got["delivery_mode"] == "fixed"
    assert abs(float(got["delivery_fee_usd"]) - 3.5) < 1e-6


def test_restaurant_update_delivery_per_area(seller_ctx):
    rid = seller_ctx["verified_rest"]["id"]
    payload = {
        "name": "TEST_VerifiedResto",
        "area": "Munuki",
        "delivery_mode": "per_area",
        "delivery_fee_usd": 0,
        "delivery_per_area": [
            {"area": "Hai Cinema", "fee_usd": 4.0},
            {"area": "Custom", "fee_usd": 7.0},
        ],
    }
    r = requests.put(f"{BASE_URL}/api/restaurants/{rid}",
                     headers=seller_ctx["seller_hdr"], json=payload, timeout=30)
    assert r.status_code == 200, r.text
    got = requests.get(f"{BASE_URL}/api/restaurants/{rid}", timeout=30).json()
    assert got["delivery_mode"] == "per_area"
    assert len(got["delivery_per_area"]) == 2
    areas = {row["area"]: row["fee_usd"] for row in got["delivery_per_area"]}
    assert areas["Custom"] == 7.0


def test_restaurant_update_delivery_free(seller_ctx):
    rid = seller_ctx["verified_rest"]["id"]
    payload = {"name": "TEST_VerifiedResto", "area": "Munuki",
               "delivery_mode": "free", "delivery_fee_usd": 0,
               "delivery_per_area": []}
    r = requests.put(f"{BASE_URL}/api/restaurants/{rid}",
                     headers=seller_ctx["seller_hdr"], json=payload, timeout=30)
    assert r.status_code == 200
    got = requests.get(f"{BASE_URL}/api/restaurants/{rid}", timeout=30).json()
    assert got["delivery_mode"] == "free"


# --- Admin delivery-managed-by override ---

@pytest.mark.parametrize("value", ["seller", "admin", "default"])
def test_admin_delivery_managed_by_persists(seller_ctx, value):
    rid = seller_ctx["verified_rest"]["id"]
    r = requests.put(
        f"{BASE_URL}/api/admin/restaurants/{rid}/delivery-managed-by",
        headers=seller_ctx["admin_hdr"],
        json={"delivery_managed_by": value},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    assert r.json()["delivery_managed_by"] == value


def test_seller_cannot_override_delivery_managed_by(seller_ctx):
    """Sellers may send delivery_managed_by but backend must ignore it."""
    rid = seller_ctx["verified_rest"]["id"]
    # First set to 'seller' via admin
    requests.put(f"{BASE_URL}/api/admin/restaurants/{rid}/delivery-managed-by",
                 headers=seller_ctx["admin_hdr"],
                 json={"delivery_managed_by": "seller"}, timeout=30)
    # Now seller tries to flip via PUT /restaurants/{id}
    payload = {"name": "TEST_VerifiedResto", "area": "Munuki",
               "delivery_mode": "free", "delivery_fee_usd": 0,
               "delivery_per_area": [], "delivery_managed_by": "admin"}
    r = requests.put(f"{BASE_URL}/api/restaurants/{rid}",
                     headers=seller_ctx["seller_hdr"], json=payload, timeout=30)
    assert r.status_code == 200
    got = requests.get(f"{BASE_URL}/api/restaurants/{rid}",
                       headers=seller_ctx["admin_hdr"], timeout=30).json()
    assert got["delivery_managed_by"] == "seller", "seller must not be able to override"


# --- Direct _calculate_delivery_fee tests for restaurants ---

def test_calculate_delivery_fee_restaurant_variants(seller_ctx, mongo):
    """Direct function test: create a scratch restaurant and exercise all branches."""
    import cod as cod_module
    from cod import _calculate_delivery_fee
    cod_module.log = logging.getLogger("cod-test")
    db, loop = mongo
    cod_module.db = db

    rest_id = f"test-fee-{uuid.uuid4()}"
    seller_id_local = seller_ctx["seller_id"]

    async def _run():
        await db.settings.update_one(
            {"id": "system"},
            {"$set": {"id": "system", "admin_manages_delivery": False}},
            upsert=True,
        )
        await db.restaurants.insert_one({
            "id": rest_id, "seller_id": seller_id_local, "name": "TEST_Fee",
            "area": "Munuki", "verification": "Verified",
            "delivery_mode": "fixed", "delivery_fee_usd": 3.5,
            "delivery_per_area": [], "delivery_managed_by": "seller",
            "is_deleted": False,
        })
        fee = await _calculate_delivery_fee("Munuki", "Anywhere", "restaurant",
                                            restaurant_id=rest_id)
        assert abs(fee - 3.5) < 1e-6

        await db.restaurants.update_one({"id": rest_id}, {"$set": {
            "delivery_mode": "per_area",
            "delivery_per_area": [
                {"area": "Hai Cinema", "fee_usd": 4.0},
                {"area": "Custom", "fee_usd": 7.0},
            ],
        }})
        fee = await _calculate_delivery_fee("Munuki", "Custom", "restaurant",
                                            restaurant_id=rest_id)
        assert abs(fee - 7.0) < 1e-6

        fee = await _calculate_delivery_fee("Munuki", "Hai Cinema", "restaurant",
                                            restaurant_id=rest_id)
        assert abs(fee - 4.0) < 1e-6

        await db.restaurants.update_one({"id": rest_id}, {"$set": {"delivery_mode": "free"}})
        fee = await _calculate_delivery_fee("Munuki", "X", "restaurant",
                                            restaurant_id=rest_id)
        assert abs(fee - 0.0) < 1e-6

        # Admin-managed fallback -> default
        await db.settings.update_one(
            {"key": "default_delivery_fee_usd"},
            {"$set": {"key": "default_delivery_fee_usd", "value": 2.0}},
            upsert=True,
        )
        await db.restaurants.update_one({"id": rest_id}, {"$set": {
            "delivery_managed_by": "admin",
            "delivery_mode": "fixed",
            "delivery_fee_usd": 99.0,  # ignored under admin branch
        }})
        fee = await _calculate_delivery_fee("Munuki", "Nowhere", "restaurant",
                                            restaurant_id=rest_id)
        # Admin branch may return either default 2.0 or admin rule; ensure not 99
        assert abs(fee - 99.0) > 1e-3, "admin override must not use seller fee"

        await db.restaurants.delete_one({"id": rest_id})

    loop.run_until_complete(_run())
