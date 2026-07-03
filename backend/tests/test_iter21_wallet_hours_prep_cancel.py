"""Iteration 21 backend tests.

Covers:
  1. /seller/splits and /seller/restaurant-orders-cod enrich each row with
     the seller's per-seller exchange_rate_ssp (falling back to global).
  2. delivery_managed_by='default' resolution on POST /shops and
     POST /restaurants (follows platform admin_manages_delivery toggle);
     explicit 'admin'/'seller' preserved.
  3. Cancel restaurant order at seller_preparation_status='ready_for_pickup':
       - seller-managed  → 200 (allowed)
       - admin-managed   → 400 (blocked)
  4. Restaurant opening_hours_by_day + auto_close_by_hours → GET returns
     is_open_effective (all-closed=False, all-day-open=True; default off →
     mirrors is_open).
  5. MenuItem prep_time_minutes echoes back on GET.
  6. Regression /api/health.
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
    pw = "TestPass!123"
    seller_email = f"test_iter21_sell_{uuid.uuid4().hex[:8]}@example.com"
    customer_email = f"test_iter21_cust_{uuid.uuid4().hex[:8]}@example.com"

    shop_seller = f"TEST_shopSell21_{uuid.uuid4().hex[:6]}"
    rest_seller = f"TEST_restSell21_{uuid.uuid4().hex[:6]}"
    rest_admin = f"TEST_restAdm21_{uuid.uuid4().hex[:6]}"

    split_id = f"TEST_split21_{uuid.uuid4().hex[:8]}"
    ro_seller_id = f"TEST_ro21s_{uuid.uuid4().hex[:8]}"
    ro_admin_id = f"TEST_ro21a_{uuid.uuid4().hex[:8]}"

    async def _setup():
        # Preserve original settings to restore later
        orig = await db.settings.find_one({"id": "system"}, {"_id": 0}) or {}
        await db.settings.update_one(
            {"id": "system"},
            {"$setOnInsert": {"id": "system"},
             "$set": {"admin_manages_delivery": False}},
            upsert=True,
        )
        await db.users.insert_many([
            {"id": seller_id, "email": seller_email, "name": "TEST Seller21",
             "role": "seller", "password_hash": _hash(pw),
             "email_verified": True, "is_active": True,
             "must_change_password": False, "settings": {}, "phone": ""},
            {"id": customer_id, "email": customer_email, "name": "TEST Cust21",
             "role": "customer", "password_hash": _hash(pw),
             "email_verified": True, "is_active": True,
             "must_change_password": False, "settings": {}, "phone": ""},
        ])
        common = {"seller_id": seller_id, "area": "Munuki",
                  "verification": "Verified", "is_deleted": False}
        await db.shops.insert_one({
            "id": shop_seller, "name": "TEST_SellerShop21",
            "delivery_managed_by": "seller", **common,
        })
        await db.restaurants.insert_many([
            {"id": rest_seller, "name": "TEST_SellerRest21",
             "delivery_managed_by": "seller", "is_open": True, **common},
            {"id": rest_admin, "name": "TEST_AdminRest21",
             "delivery_managed_by": "admin", "is_open": True, **common},
        ])
        # Per-seller exchange rate
        await db.exchange_rates.update_one(
            {"seller_id": seller_id},
            {"$set": {"seller_id": seller_id, "rate": 6500.0}},
            upsert=True,
        )
        # A split for the seller
        await db.seller_order_splits.insert_one({
            "id": split_id, "seller_id": seller_id, "shop_id": shop_seller,
            "order_id": f"TEST_ord21_{uuid.uuid4().hex[:6]}",
            "customer_id": customer_id, "customer_phone": "+2119",
            "customer_area": "Munuki", "customer_address": "Addr 1",
            "delivery_status": "unassigned",
            "seller_preparation_status": "pending",
            "pickup_status": "not_assigned",
            "payment_method": "cash_on_delivery",
            "order_total_usd": 10.0, "product_subtotal_usd": 10.0,
            "delivery_fee_usd": 0.0, "platform_commission_usd": 1.0,
            "seller_earning_usd": 9.0,
            "created_at": "2026-01-01T00:00:00+00:00",
        })
        # Restaurant orders: one seller-managed at ready_for_pickup (cancellable),
        # one admin-managed at ready_for_pickup (not cancellable).
        for ro_id, rest_id in [
            (ro_seller_id, rest_seller),
            (ro_admin_id, rest_admin),
        ]:
            await db.restaurant_orders.insert_one({
                "id": ro_id, "seller_id": seller_id, "restaurant_id": rest_id,
                "customer_id": customer_id, "customer_name": "TEST Cust",
                "customer_phone": "+21190", "customer_area": "Munuki",
                "customer_address": "Addr X",
                "status": "accepted", "delivery_status": "unassigned",
                "seller_preparation_status": "ready_for_pickup",
                "pickup_status": "not_assigned",
                "payment_method": "cash_on_delivery",
                "product_subtotal_usd": 10.0, "delivery_fee_usd": 2.0,
                "order_total_usd": 12.0, "platform_commission_usd": 1.0,
                "seller_earning_usd": 11.0,
                "created_at": "2026-01-01T00:00:00+00:00",
                "items": [], "total_usd": 12.0, "delivery_area": "Munuki",
            })
        return orig

    orig_settings = loop.run_until_complete(_setup())

    def _login(email):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": email, "password": pw}, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()["token"]

    seller_hdr = {"Authorization": f"Bearer {_login(seller_email)}"}
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}

    data = {
        "db": db, "loop": loop,
        "seller_id": seller_id, "customer_id": customer_id,
        "seller_hdr": seller_hdr, "admin_hdr": admin_hdr,
        "shop_seller": shop_seller,
        "rest_seller": rest_seller, "rest_admin": rest_admin,
        "split_id": split_id,
        "ro_seller": ro_seller_id, "ro_admin": ro_admin_id,
        "created_shops": [], "created_restaurants": [],
        "created_menu_items": [],
    }
    yield data

    async def _cleanup():
        await db.users.delete_many({"id": {"$in": [seller_id, customer_id]}})
        await db.shops.delete_many({"seller_id": seller_id})
        await db.restaurants.delete_many({"seller_id": seller_id})
        await db.seller_order_splits.delete_many({"seller_id": seller_id})
        await db.restaurant_orders.delete_many({"seller_id": seller_id})
        await db.exchange_rates.delete_many({"seller_id": seller_id})
        # Cleanup admin-created entities
        if data["created_shops"]:
            await db.shops.delete_many({"id": {"$in": data["created_shops"]}})
        if data["created_restaurants"]:
            await db.restaurants.delete_many(
                {"id": {"$in": data["created_restaurants"]}})
        if data["created_menu_items"]:
            await db.menu_items.delete_many(
                {"id": {"$in": data["created_menu_items"]}})
        # Restore settings admin_manages_delivery
        if orig_settings:
            await db.settings.update_one(
                {"id": "system"},
                {"$set": {"admin_manages_delivery":
                          bool(orig_settings.get("admin_manages_delivery",
                                                 False))}},
            )
    loop.run_until_complete(_cleanup())


# ============================================================
# 0. Health
# ============================================================
def test_health_ok():
    r = requests.get(f"{BASE_URL}/api/health", timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "ok"


# ============================================================
# 1. exchange_rate_ssp enrichment
# ============================================================
def test_seller_splits_enrich_exchange_rate(ctx):
    r = requests.get(f"{BASE_URL}/api/seller/splits",
                     headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    rows = r.json()
    ours = [x for x in rows if x["id"] == ctx["split_id"]]
    assert ours, "seeded split not returned"
    assert ours[0]["exchange_rate_ssp"] == 6500.0


def test_seller_rest_cod_enrich_exchange_rate(ctx):
    r = requests.get(f"{BASE_URL}/api/seller/restaurant-orders-cod",
                     headers=ctx["seller_hdr"], timeout=30)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert rows, "expected at least one restaurant order"
    for row in rows:
        assert row.get("exchange_rate_ssp") == 6500.0, row


# ============================================================
# 2. delivery_managed_by resolution — shops
# ============================================================
def _set_admin_manages(ctx, value: bool):
    async def _do():
        await ctx["db"].settings.update_one(
            {"id": "system"},
            {"$set": {"admin_manages_delivery": bool(value)}},
        )
    ctx["loop"].run_until_complete(_do())


def _make_shop_payload(name):
    return {
        "name": name, "description": "", "image_url": "",
        "area": "Munuki", "category": "", "kind": "retail",
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "delivery_per_area": [],
        "delivery_managed_by": "default",
        "is_open": True, "is_public": True,
    }


def test_shop_default_seller_when_admin_manages_false(ctx):
    _set_admin_manages(ctx, False)
    payload = _make_shop_payload(f"TEST_shopDefFalse_{uuid.uuid4().hex[:6]}")
    r = requests.post(f"{BASE_URL}/api/shops", headers=ctx["admin_hdr"],
                      json=payload, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    ctx["created_shops"].append(body["id"])
    assert body["delivery_managed_by"] == "seller"


def test_shop_default_admin_when_admin_manages_true(ctx):
    _set_admin_manages(ctx, True)
    payload = _make_shop_payload(f"TEST_shopDefTrue_{uuid.uuid4().hex[:6]}")
    r = requests.post(f"{BASE_URL}/api/shops", headers=ctx["admin_hdr"],
                      json=payload, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    ctx["created_shops"].append(body["id"])
    assert body["delivery_managed_by"] == "admin"
    _set_admin_manages(ctx, False)


def test_shop_explicit_admin_preserved(ctx):
    _set_admin_manages(ctx, False)  # ensure default would flip to "seller"
    payload = _make_shop_payload(f"TEST_shopExplAdm_{uuid.uuid4().hex[:6]}")
    payload["delivery_managed_by"] = "admin"
    r = requests.post(f"{BASE_URL}/api/shops", headers=ctx["admin_hdr"],
                      json=payload, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    ctx["created_shops"].append(body["id"])
    assert body["delivery_managed_by"] == "admin"


# ============================================================
# 3. delivery_managed_by resolution — restaurants
# ============================================================
def _make_rest_payload(name, **extras):
    p = {
        "name": name, "category": "", "description": "", "image_url": "",
        "area": "Munuki", "is_open": True,
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "delivery_per_area": [],
        "delivery_managed_by": "default",
    }
    p.update(extras)
    return p


def test_restaurant_default_seller_when_admin_manages_false(ctx):
    _set_admin_manages(ctx, False)
    p = _make_rest_payload(f"TEST_restDefF_{uuid.uuid4().hex[:6]}")
    r = requests.post(f"{BASE_URL}/api/restaurants", headers=ctx["admin_hdr"],
                      json=p, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    ctx["created_restaurants"].append(body["id"])
    assert body["delivery_managed_by"] == "seller"


def test_restaurant_default_admin_when_admin_manages_true(ctx):
    _set_admin_manages(ctx, True)
    p = _make_rest_payload(f"TEST_restDefT_{uuid.uuid4().hex[:6]}")
    r = requests.post(f"{BASE_URL}/api/restaurants", headers=ctx["admin_hdr"],
                      json=p, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    ctx["created_restaurants"].append(body["id"])
    assert body["delivery_managed_by"] == "admin"
    _set_admin_manages(ctx, False)


def test_restaurant_explicit_admin_preserved(ctx):
    _set_admin_manages(ctx, False)
    p = _make_rest_payload(f"TEST_restExplA_{uuid.uuid4().hex[:6]}",
                           delivery_managed_by="admin")
    r = requests.post(f"{BASE_URL}/api/restaurants", headers=ctx["admin_hdr"],
                      json=p, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    ctx["created_restaurants"].append(body["id"])
    assert body["delivery_managed_by"] == "admin"


# ============================================================
# 4. Cancel restaurant order at ready_for_pickup
# ============================================================
def test_cancel_ready_for_pickup_seller_managed_ok(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/restaurant-orders/{ctx['ro_seller']}/cancel",
        headers=ctx["seller_hdr"], json={"reason": "test"}, timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["seller_preparation_status"] == "cancelled"
    assert body["status"] == "cancelled"


def test_cancel_ready_for_pickup_admin_managed_blocked(ctx):
    r = requests.post(
        f"{BASE_URL}/api/seller/restaurant-orders/{ctx['ro_admin']}/cancel",
        headers=ctx["seller_hdr"], json={"reason": "test"}, timeout=30,
    )
    assert r.status_code == 400, r.text


# ============================================================
# 5. Opening hours + auto_close_by_hours → is_open_effective
# ============================================================
def test_restaurant_all_days_closed_is_open_effective_false(ctx):
    all_closed = {d: {"closed": True, "open": "09:00", "close": "22:00"}
                  for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    p = _make_rest_payload(
        f"TEST_restClosed_{uuid.uuid4().hex[:6]}",
        opening_hours_by_day=all_closed, auto_close_by_hours=True,
    )
    r = requests.post(f"{BASE_URL}/api/restaurants", headers=ctx["admin_hdr"],
                      json=p, timeout=30)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    ctx["created_restaurants"].append(rid)
    g = requests.get(f"{BASE_URL}/api/restaurants/{rid}",
                     headers=ctx["admin_hdr"], timeout=30)
    assert g.status_code == 200, g.text
    assert g.json().get("is_open_effective") is False


def test_restaurant_put_all_day_open_effective_true(ctx):
    # Create restaurant with default hours + auto_close off
    p = _make_rest_payload(f"TEST_restPutOpen_{uuid.uuid4().hex[:6]}")
    r = requests.post(f"{BASE_URL}/api/restaurants", headers=ctx["admin_hdr"],
                      json=p, timeout=30)
    assert r.status_code == 200
    rid = r.json()["id"]
    ctx["created_restaurants"].append(rid)
    # PUT all-day-open + auto_close_by_hours=True
    all_open = {d: {"closed": False, "open": "00:00", "close": "23:59"}
                for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    up = _make_rest_payload(
        p["name"],
        opening_hours_by_day=all_open, auto_close_by_hours=True,
    )
    pu = requests.put(f"{BASE_URL}/api/restaurants/{rid}",
                      headers=ctx["admin_hdr"], json=up, timeout=30)
    assert pu.status_code == 200, pu.text
    g = requests.get(f"{BASE_URL}/api/restaurants/{rid}",
                     headers=ctx["admin_hdr"], timeout=30)
    assert g.status_code == 200
    assert g.json().get("is_open_effective") is True


def test_restaurant_default_no_auto_close_mirrors_is_open(ctx):
    p = _make_rest_payload(f"TEST_restMirror_{uuid.uuid4().hex[:6]}",
                           is_open=True)
    r = requests.post(f"{BASE_URL}/api/restaurants", headers=ctx["admin_hdr"],
                      json=p, timeout=30)
    assert r.status_code == 200
    rid = r.json()["id"]
    ctx["created_restaurants"].append(rid)
    g = requests.get(f"{BASE_URL}/api/restaurants/{rid}",
                     headers=ctx["admin_hdr"], timeout=30)
    assert g.status_code == 200
    body = g.json()
    assert body.get("is_open_effective") is True
    assert body.get("auto_close_by_hours") is False


# ============================================================
# 6. MenuItem prep_time_minutes
# ============================================================
def test_menu_item_prep_time_persists(ctx):
    # Need a restaurant to attach menu to. Use rest_seller.
    payload = {
        "restaurant_id": ctx["rest_seller"],
        "name": f"TEST_mi_prep_{uuid.uuid4().hex[:6]}",
        "price_usd": 5.0, "image_url": "", "description": "",
        "category_id": "c78426ce-62cf-4573-bce4-e0148d873c5b", "food_category": "",
        "side_items": [], "prep_time_minutes": 20,
    }
    r = requests.post(f"{BASE_URL}/api/menu-items",
                      headers=ctx["admin_hdr"], json=payload, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    mid = body["id"]
    ctx["created_menu_items"].append(mid)
    assert body.get("prep_time_minutes") == 20
    # GET the menu item (via list — the API may not expose single GET)
    g = requests.get(
        f"{BASE_URL}/api/menu-items?restaurant_id={ctx['rest_seller']}",
        timeout=30,
    )
    assert g.status_code == 200, g.text
    ours = [x for x in g.json() if x["id"] == mid]
    assert ours and ours[0].get("prep_time_minutes") == 20


def test_menu_item_without_prep_time(ctx):
    payload = {
        "restaurant_id": ctx["rest_seller"],
        "name": f"TEST_mi_noprep_{uuid.uuid4().hex[:6]}",
        "price_usd": 5.0, "image_url": "", "description": "",
        "category_id": "c78426ce-62cf-4573-bce4-e0148d873c5b", "food_category": "",
        "side_items": [],
    }
    r = requests.post(f"{BASE_URL}/api/menu-items",
                      headers=ctx["admin_hdr"], json=payload, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    ctx["created_menu_items"].append(body["id"])
    assert body.get("prep_time_minutes") in (None,)
