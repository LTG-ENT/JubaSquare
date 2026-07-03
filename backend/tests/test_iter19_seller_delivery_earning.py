"""Iteration 19 backend tests — Seller earning includes delivery fee when
seller manages delivery.

Directly invokes cod.create_marketplace_splits and cod.initialize_restaurant_order_cod
after binding cod with minimal test deps (own db, in-test get_settings).

Also runs a health check against the live API to ensure the FastAPI process
is up.
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

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
import cod  # noqa: E402

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


async def _noop_notif(**kw):
    return None


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def db(event_loop):
    client = AsyncIOMotorClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="session")
def bound(db):
    """Return a helper that binds cod with a per-test admin_manages_delivery setting."""

    def _bind(admin_manages_delivery=False, commission_rate=0.10):
        async def _get_settings():
            return {
                "commission_rate": commission_rate,
                "admin_manages_delivery": admin_manages_delivery,
                "global_rate": 600.0,
            }

        cod.bind(
            db_=db,
            log_=None,
            get_current_user_=None,
            require_role_=None,
            get_settings_=_get_settings,
            create_notification_=_noop_notif,
            now_iso_=now_iso,
            hash_password_=lambda x: "",
        )

    return _bind


@pytest.fixture(scope="session")
def seed(db, event_loop):
    """Seed shops, restaurants, products, menu items for all tests."""
    seller_id = f"TEST_seller_{uuid.uuid4().hex[:8]}"

    shop_seller = f"TEST_shopSell_{uuid.uuid4().hex[:6]}"
    shop_admin = f"TEST_shopAdm_{uuid.uuid4().hex[:6]}"

    rest_seller = f"TEST_restSell_{uuid.uuid4().hex[:6]}"
    rest_admin = f"TEST_restAdm_{uuid.uuid4().hex[:6]}"
    rest_default = f"TEST_restDef_{uuid.uuid4().hex[:6]}"
    rest_default_cr10 = f"TEST_restDefCR10_{uuid.uuid4().hex[:6]}"

    product_id = f"TEST_prod_{uuid.uuid4().hex[:6]}"
    menu_item_id = f"TEST_menu_{uuid.uuid4().hex[:6]}"

    async def _setup():
        await db.shops.insert_many([
            {"id": shop_seller, "seller_id": seller_id, "name": "TEST SellerShop",
             "area": "Munuki", "delivery_managed_by": "seller"},
            {"id": shop_admin, "seller_id": seller_id, "name": "TEST AdminShop",
             "area": "Munuki", "delivery_managed_by": "admin"},
        ])
        await db.restaurants.insert_many([
            {"id": rest_seller, "seller_id": seller_id, "name": "TEST SellerRest",
             "area": "Munuki", "delivery_managed_by": "seller"},
            {"id": rest_admin, "seller_id": seller_id, "name": "TEST AdminRest",
             "area": "Munuki", "delivery_managed_by": "admin"},
            {"id": rest_default, "seller_id": seller_id, "name": "TEST DefaultRest",
             "area": "Munuki", "delivery_managed_by": "default"},
            {"id": rest_default_cr10, "seller_id": seller_id, "name": "TEST DefaultRest CR10",
             "area": "Munuki", "delivery_managed_by": "seller", "commission_rate": 0.10},
        ])
        # Product $20 (marketplace)
        await db.products.insert_one({
            "id": product_id, "shop_id": shop_seller, "name": "TEST Product",
            "price_usd": 20.0, "image_url": "",
        })
        # Also same product in admin shop scenario (we'll rebind shop_id)
        await db.products.insert_one({
            "id": product_id + "_admin", "shop_id": shop_admin, "name": "TEST Product Admin",
            "price_usd": 20.0, "image_url": "",
        })
        # Menu item: $10 base with $3 side to reach $13 subtotal
        await db.menu_items.insert_one({
            "id": menu_item_id, "restaurant_id": rest_seller,
            "name": "TEST Menu", "price_usd": 10.0, "image_url": "",
        })
        # duplicates for other restaurants (same id fine since we lookup by item_id,
        # but menu_items are unique; create separate menu ids per restaurant)

    event_loop.run_until_complete(_setup())

    data = {
        "seller_id": seller_id,
        "shop_seller": shop_seller,
        "shop_admin": shop_admin,
        "rest_seller": rest_seller,
        "rest_admin": rest_admin,
        "rest_default": rest_default,
        "rest_default_cr10": rest_default_cr10,
        "product_id": product_id,
        "product_id_admin": product_id + "_admin",
        "menu_item_id": menu_item_id,
    }
    yield data

    async def _cleanup():
        await db.shops.delete_many({"seller_id": seller_id})
        await db.restaurants.delete_many({"seller_id": seller_id})
        await db.products.delete_many({"id": {"$in": [product_id, product_id + "_admin"]}})
        await db.menu_items.delete_many({"id": menu_item_id})
        await db.seller_order_splits.delete_many({"seller_id": seller_id})
    event_loop.run_until_complete(_cleanup())


# ============================================================
# Health
# ============================================================

def test_health_ok():
    r = requests.get(f"{BASE_URL}/api/health", timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "ok"


# ============================================================
# Restaurant orders — initialize_restaurant_order_cod
# ============================================================

def test_rest_seller_managed_earns_delivery(bound, seed, event_loop, db):
    """seller-managed + 0% commission -> earning = subtotal + delivery."""
    bound(admin_manages_delivery=False, commission_rate=0.0)

    order = {
        "id": f"TEST_ord_{uuid.uuid4().hex[:6]}",
        "restaurant_id": seed["rest_seller"],
        "items": [{"item_id": seed["menu_item_id"], "quantity": 1,
                   "sides": [{"name": "extra", "price_usd": 3.0}]}],
        "delivery_fee": 2.50,
    }
    cod_fields = event_loop.run_until_complete(cod.initialize_restaurant_order_cod(order))
    assert cod_fields["product_subtotal_usd"] == 13.0
    assert cod_fields["delivery_fee_usd"] == 2.50
    assert cod_fields["platform_commission_usd"] == 0.0
    assert cod_fields["seller_earning_usd"] == 15.5
    assert cod_fields["order_total_usd"] == 15.5


def test_rest_admin_managed_no_delivery_earning(bound, seed, event_loop):
    """admin-managed -> earning excludes delivery."""
    # move menu item to rest_admin for this call
    async def _prep():
        await cod.db.menu_items.insert_one({
            "id": seed["menu_item_id"] + "_adm",
            "restaurant_id": seed["rest_admin"],
            "name": "TEST Menu", "price_usd": 10.0, "image_url": "",
        })
    bound(admin_manages_delivery=False, commission_rate=0.0)
    event_loop.run_until_complete(_prep())

    order = {
        "id": f"TEST_ord_{uuid.uuid4().hex[:6]}",
        "restaurant_id": seed["rest_admin"],
        "items": [{"item_id": seed["menu_item_id"] + "_adm", "quantity": 1,
                   "sides": [{"name": "extra", "price_usd": 3.0}]}],
        "delivery_fee": 2.50,
    }
    cod_fields = event_loop.run_until_complete(cod.initialize_restaurant_order_cod(order))
    assert cod_fields["product_subtotal_usd"] == 13.0
    assert cod_fields["delivery_fee_usd"] == 2.50
    assert cod_fields["seller_earning_usd"] == 13.0
    assert cod_fields["order_total_usd"] == 15.5

    event_loop.run_until_complete(
        cod.db.menu_items.delete_one({"id": seed["menu_item_id"] + "_adm"}))


def test_rest_default_admin_manages_false_seller_earns_delivery(bound, seed, event_loop):
    """default + admin_manages_delivery=False -> seller keeps delivery."""
    async def _prep():
        await cod.db.menu_items.insert_one({
            "id": seed["menu_item_id"] + "_def1",
            "restaurant_id": seed["rest_default"],
            "name": "TEST Menu", "price_usd": 10.0, "image_url": "",
        })
    bound(admin_manages_delivery=False, commission_rate=0.0)
    event_loop.run_until_complete(_prep())

    order = {
        "id": f"TEST_ord_{uuid.uuid4().hex[:6]}",
        "restaurant_id": seed["rest_default"],
        "items": [{"item_id": seed["menu_item_id"] + "_def1", "quantity": 1,
                   "sides": [{"name": "s", "price_usd": 3.0}]}],
        "delivery_fee": 2.50,
    }
    cod_fields = event_loop.run_until_complete(cod.initialize_restaurant_order_cod(order))
    assert cod_fields["seller_earning_usd"] == 15.5

    event_loop.run_until_complete(
        cod.db.menu_items.delete_one({"id": seed["menu_item_id"] + "_def1"}))


def test_rest_default_admin_manages_true_seller_no_delivery(bound, seed, event_loop):
    """default + admin_manages_delivery=True -> platform keeps delivery."""
    async def _prep():
        await cod.db.menu_items.insert_one({
            "id": seed["menu_item_id"] + "_def2",
            "restaurant_id": seed["rest_default"],
            "name": "TEST Menu", "price_usd": 10.0, "image_url": "",
        })
    bound(admin_manages_delivery=True, commission_rate=0.0)
    event_loop.run_until_complete(_prep())

    order = {
        "id": f"TEST_ord_{uuid.uuid4().hex[:6]}",
        "restaurant_id": seed["rest_default"],
        "items": [{"item_id": seed["menu_item_id"] + "_def2", "quantity": 1,
                   "sides": [{"name": "s", "price_usd": 3.0}]}],
        "delivery_fee": 2.50,
    }
    cod_fields = event_loop.run_until_complete(cod.initialize_restaurant_order_cod(order))
    assert cod_fields["seller_earning_usd"] == 13.0

    event_loop.run_until_complete(
        cod.db.menu_items.delete_one({"id": seed["menu_item_id"] + "_def2"}))


def test_rest_seller_managed_10pct_commission(bound, seed, event_loop):
    """seller-managed + 10% (per-restaurant override) -> earning = 13 - 1.30 + 2.50 = 14.20."""
    async def _prep():
        await cod.db.menu_items.insert_one({
            "id": seed["menu_item_id"] + "_cr10",
            "restaurant_id": seed["rest_default_cr10"],
            "name": "TEST Menu", "price_usd": 10.0, "image_url": "",
        })
    # commission_rate on restaurant overrides sysconf; default is 0.10 anyway
    bound(admin_manages_delivery=False, commission_rate=0.10)
    event_loop.run_until_complete(_prep())

    order = {
        "id": f"TEST_ord_{uuid.uuid4().hex[:6]}",
        "restaurant_id": seed["rest_default_cr10"],
        "items": [{"item_id": seed["menu_item_id"] + "_cr10", "quantity": 1,
                   "sides": [{"name": "s", "price_usd": 3.0}]}],
        "delivery_fee": 2.50,
    }
    cod_fields = event_loop.run_until_complete(cod.initialize_restaurant_order_cod(order))
    assert cod_fields["product_subtotal_usd"] == 13.0
    assert cod_fields["platform_commission_usd"] == 1.30
    assert cod_fields["seller_earning_usd"] == 14.20

    event_loop.run_until_complete(
        cod.db.menu_items.delete_one({"id": seed["menu_item_id"] + "_cr10"}))


# ============================================================
# Marketplace splits — create_marketplace_splits
# ============================================================

def test_marketplace_seller_managed_earns_delivery(bound, seed, event_loop):
    """seller-managed shop + 0% commission -> earning = 20 + 3.50."""
    bound(admin_manages_delivery=False, commission_rate=0.0)

    order = {
        "id": f"TEST_ord_{uuid.uuid4().hex[:6]}",
        "customer_id": "TEST_cust",
        "customer_name": "TEST",
        "customer_email": "x@x.com",
        "phone": "", "area": "", "address": "",
        "items": [{"item_id": seed["product_id"], "quantity": 1}],
        "delivery_breakdown": [
            {"shop_id": seed["shop_seller"], "fee_usd": 3.50,
             "pickup_area": "Munuki", "delivery_area": "Munuki"},
        ],
    }
    splits = event_loop.run_until_complete(cod.create_marketplace_splits(order))
    assert len(splits) == 1
    s = splits[0]
    assert s["product_subtotal_usd"] == 20.0
    assert s["delivery_fee_usd"] == 3.50
    assert s["platform_commission_usd"] == 0.0
    assert s["seller_earning_usd"] == 23.50
    assert s["order_total_usd"] == 23.50


def test_marketplace_admin_managed_no_delivery_earning(bound, seed, event_loop):
    """admin-managed shop + 0% commission -> earning = 20 (delivery excluded)."""
    bound(admin_manages_delivery=False, commission_rate=0.0)

    order = {
        "id": f"TEST_ord_{uuid.uuid4().hex[:6]}",
        "customer_id": "TEST_cust",
        "customer_name": "TEST",
        "customer_email": "x@x.com",
        "phone": "", "area": "", "address": "",
        "items": [{"item_id": seed["product_id_admin"], "quantity": 1}],
        "delivery_breakdown": [
            {"shop_id": seed["shop_admin"], "fee_usd": 3.50,
             "pickup_area": "Munuki", "delivery_area": "Munuki"},
        ],
    }
    splits = event_loop.run_until_complete(cod.create_marketplace_splits(order))
    assert len(splits) == 1
    s = splits[0]
    assert s["product_subtotal_usd"] == 20.0
    assert s["delivery_fee_usd"] == 3.50
    assert s["seller_earning_usd"] == 20.0
    assert s["order_total_usd"] == 23.50
