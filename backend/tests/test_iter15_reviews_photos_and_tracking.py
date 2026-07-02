"""Iteration 15 backend tests.

Covers:
  - Product review photos (POST/GET /api/products/{id}/reviews with photos:List[str])
  - Driver location beacon POST /api/driver/location (auth/role/validation/trail)
  - Live tracking GET /api/customer/orders/{order_id}/live-tracking
    (404, 403, empty assignments, split out_for_delivery, restaurant_order,
    destination = JUBA_AREA_COORDS/fallback, eta ~ dist*4 min/km)
  - Regression: iteration_14 core assertions (health, visibility gates)

All test data is prefixed TEST_ and cleaned up in fixture teardown.
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


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


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
    """Seed: seller (with verified shop + product), customer1, customer2, driver.
    Also create real orders (parent + split) and a restaurant_order with drivers assigned.
    """
    db, loop = mongo

    seller_id = str(uuid.uuid4())
    seller_email = f"test_iter15_seller_{uuid.uuid4().hex[:8]}@example.com"
    seller_pw = "TestPass!123"

    cust_id = str(uuid.uuid4())
    cust_email = f"test_iter15_cust_{uuid.uuid4().hex[:8]}@example.com"
    cust_pw = "TestPass!123"

    cust2_id = str(uuid.uuid4())
    cust2_email = f"test_iter15_cust2_{uuid.uuid4().hex[:8]}@example.com"

    driver_id = str(uuid.uuid4())
    driver_email = f"test_iter15_driver_{uuid.uuid4().hex[:8]}@example.com"
    driver_pw = "TestPass!123"

    shop_id = f"test-shop-{uuid.uuid4()}"
    product_id = f"test-prod-{uuid.uuid4()}"
    parent_order_id = f"test-order-{uuid.uuid4()}"
    split_id = f"test-split-{uuid.uuid4()}"
    rest_id = f"test-rest-{uuid.uuid4()}"
    rest_order_id = f"test-restorder-{uuid.uuid4()}"

    async def _setup():
        # Users
        common = {"phone": "", "email_verified": True, "is_active": True,
                  "must_change_password": False, "settings": {}}
        await db.users.insert_many([
            {"id": seller_id, "email": seller_email, "name": "TEST Seller",
             "role": "seller", "password_hash": _hash(seller_pw), **common},
            {"id": cust_id, "email": cust_email, "name": "TEST Customer",
             "role": "customer", "password_hash": _hash(cust_pw), **common},
            {"id": cust2_id, "email": cust2_email, "name": "TEST Customer2",
             "role": "customer", "password_hash": _hash(cust_pw), **common},
            {"id": driver_id, "email": driver_email, "name": "TEST Driver",
             "role": "driver", "password_hash": _hash(driver_pw), **common},
        ])
        # Shop (Verified) and product
        cat = await db.categories.find_one({"group": {"$ne": "restaurant"}},
                                           {"_id": 0, "id": 1})
        cat_id = cat["id"] if cat else "cat-fallback"
        await db.shops.insert_one({
            "id": shop_id, "seller_id": seller_id, "name": "TEST_Shop15",
            "area": "Munuki", "kind": "retail", "verification": "Verified",
            "is_deleted": False, "created_at": _now_iso(),
        })
        await db.products.insert_one({
            "id": product_id, "shop_id": shop_id, "seller_id": seller_id,
            "name": "TEST_Prod15", "category_id": cat_id, "price_usd": 10.0,
            "in_stock": True, "is_deleted": False, "created_at": _now_iso(),
        })
        # Parent order owned by cust_id
        await db.orders.insert_one({
            "id": parent_order_id,
            "customer_id": cust_id,
            "status": "confirmed",
            "delivery_address": {"area": "Hai Cinema", "text": "TEST addr"},
            "total_usd": 10.0,
            "created_at": _now_iso(),
        })
        # Split: driver assigned, out_for_delivery
        await db.order_splits.insert_one({
            "id": split_id,
            "parent_order_id": parent_order_id,
            "seller_id": seller_id,
            "shop_id": shop_id,
            "shop_area": "Munuki",
            "driver_id": driver_id,
            "delivery_status": "out_for_delivery",
            "created_at": _now_iso(),
        })
        # Restaurant + standalone restaurant_order
        await db.restaurants.insert_one({
            "id": rest_id, "seller_id": seller_id, "name": "TEST_Rest15",
            "area": "Nyakuron", "verification": "Verified",
            "delivery_mode": "free", "delivery_fee_usd": 0,
            "is_deleted": False, "created_at": _now_iso(),
        })
        await db.restaurant_orders.insert_one({
            "id": rest_order_id,
            "customer_id": cust_id,
            "restaurant_id": rest_id,
            "driver_id": driver_id,
            "status": "out_for_delivery",
            "pickup_area": "Nyakuron",
            "delivery_address": {"area": "SomeUnknownArea", "text": "TEST"},
            "total_usd": 6.0,
            "created_at": _now_iso(),
        })
        # Ensure no existing driver_locations doc for this driver
        await db.driver_locations.delete_one({"driver_id": driver_id})
    loop.run_until_complete(_setup())

    # Tokens
    def _login(email, pw):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": email, "password": pw}, timeout=30)
        assert r.status_code == 200, f"login failed for {email}: {r.text}"
        return r.json()["token"]

    seller_tok = _login(seller_email, seller_pw)
    cust_tok = _login(cust_email, cust_pw)
    cust2_tok = _login(cust2_email, cust_pw)
    driver_tok = _login(driver_email, driver_pw)

    data = {
        "seller_id": seller_id, "cust_id": cust_id, "cust2_id": cust2_id,
        "driver_id": driver_id,
        "shop_id": shop_id, "product_id": product_id,
        "parent_order_id": parent_order_id, "split_id": split_id,
        "rest_id": rest_id, "rest_order_id": rest_order_id,
        "admin_hdr": {"Authorization": f"Bearer {admin_token}"},
        "seller_hdr": {"Authorization": f"Bearer {seller_tok}"},
        "cust_hdr": {"Authorization": f"Bearer {cust_tok}"},
        "cust2_hdr": {"Authorization": f"Bearer {cust2_tok}"},
        "driver_hdr": {"Authorization": f"Bearer {driver_tok}"},
    }
    yield data

    async def _cleanup():
        await db.users.delete_many({"id": {"$in": [seller_id, cust_id, cust2_id, driver_id]}})
        await db.shops.delete_many({"seller_id": seller_id})
        await db.products.delete_many({"seller_id": seller_id})
        await db.restaurants.delete_many({"seller_id": seller_id})
        await db.orders.delete_many({"id": parent_order_id})
        await db.order_splits.delete_many({"parent_order_id": parent_order_id})
        await db.restaurant_orders.delete_many({"id": rest_order_id})
        await db.reviews.delete_many({"product_id": product_id})
        await db.driver_locations.delete_many({"driver_id": driver_id})
    loop.run_until_complete(_cleanup())


# ---------- Health / regression ----------

def test_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=10)
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


# ---------- Product review photos ----------

def test_review_with_photos_persists(ctx):
    photos = ["https://example.com/a.jpg", "https://example.com/b.jpg"]
    r = requests.post(f"{BASE_URL}/api/products/{ctx['product_id']}/reviews",
                      headers=ctx["cust_hdr"],
                      json={"rating": 5, "comment": "TEST photos", "photos": photos},
                      timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["photos"] == photos
    # Verify via GET list
    r = requests.get(f"{BASE_URL}/api/products/{ctx['product_id']}/reviews", timeout=30)
    assert r.status_code == 200
    reviews = r.json()["reviews"]
    match = [rv for rv in reviews if rv["id"] == body["id"]]
    assert match and match[0]["photos"] == photos


def test_review_truncates_to_5_photos(ctx):
    photos = [f"https://example.com/{i}.jpg" for i in range(8)]
    r = requests.post(f"{BASE_URL}/api/products/{ctx['product_id']}/reviews",
                      headers=ctx["cust_hdr"],
                      json={"rating": 4, "comment": "TEST trunc", "photos": photos},
                      timeout=30)
    assert r.status_code == 200, r.text
    assert len(r.json()["photos"]) == 5
    assert r.json()["photos"] == photos[:5]


def test_review_empty_photos_array(ctx):
    r = requests.post(f"{BASE_URL}/api/products/{ctx['product_id']}/reviews",
                      headers=ctx["cust_hdr"],
                      json={"rating": 3, "comment": "TEST empty", "photos": []},
                      timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["photos"] == []


def test_review_no_photos_field_defaults_empty(ctx):
    r = requests.post(f"{BASE_URL}/api/products/{ctx['product_id']}/reviews",
                      headers=ctx["cust_hdr"],
                      json={"rating": 3, "comment": "TEST no-field"},
                      timeout=30)
    assert r.status_code == 200
    assert r.json()["photos"] == []


# ---------- Driver location beacon ----------

def test_driver_location_anonymous_401(ctx):
    r = requests.post(f"{BASE_URL}/api/driver/location",
                      json={"lat": 4.85, "lng": 31.58}, timeout=30)
    assert r.status_code == 401


def test_driver_location_admin_forbidden_403(ctx):
    r = requests.post(f"{BASE_URL}/api/driver/location",
                      headers=ctx["admin_hdr"],
                      json={"lat": 4.85, "lng": 31.58}, timeout=30)
    assert r.status_code == 403


def test_driver_location_invalid_lat_422(ctx):
    r = requests.post(f"{BASE_URL}/api/driver/location",
                      headers=ctx["driver_hdr"],
                      json={"lat": 100.0, "lng": 31.58}, timeout=30)
    assert r.status_code == 422


def test_driver_location_success_and_trail(ctx, mongo):
    db, loop = mongo
    # Reset first
    async def _reset():
        await db.driver_locations.delete_one({"driver_id": ctx["driver_id"]})
    loop.run_until_complete(_reset())

    for i in range(25):  # more than 20 to test trail cap
        r = requests.post(f"{BASE_URL}/api/driver/location",
                          headers=ctx["driver_hdr"],
                          json={"lat": 4.85 + i * 0.0001, "lng": 31.58 + i * 0.0001,
                                "accuracy": 15.0}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}

    async def _check():
        doc = await db.driver_locations.find_one({"driver_id": ctx["driver_id"]})
        assert doc is not None
        assert isinstance(doc.get("trail"), list)
        assert len(doc["trail"]) == 20, f"trail size = {len(doc['trail'])}"
        # latest should be present
        assert abs(doc["lat"] - (4.85 + 24 * 0.0001)) < 1e-9
    loop.run_until_complete(_check())


# ---------- Live tracking ----------

def test_live_tracking_404_missing_order(ctx):
    r = requests.get(f"{BASE_URL}/api/customer/orders/does-not-exist/live-tracking",
                     headers=ctx["cust_hdr"], timeout=30)
    assert r.status_code == 404


def test_live_tracking_403_not_owner(ctx):
    r = requests.get(f"{BASE_URL}/api/customer/orders/{ctx['parent_order_id']}/live-tracking",
                     headers=ctx["cust2_hdr"], timeout=30)
    assert r.status_code == 403


def test_live_tracking_empty_when_no_out_for_delivery(ctx, mongo):
    """Flip split off out_for_delivery temporarily and check empty assignments."""
    db, loop = mongo

    async def _flip(status):
        await db.order_splits.update_one(
            {"id": ctx["split_id"]}, {"$set": {"delivery_status": status}}
        )
    loop.run_until_complete(_flip("preparing"))
    try:
        r = requests.get(
            f"{BASE_URL}/api/customer/orders/{ctx['parent_order_id']}/live-tracking",
            headers=ctx["cust_hdr"], timeout=30,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["assignments"] == []
        # destination should be Hai Cinema centroid
        assert abs(body["destination"]["lat"] - 4.8560) < 1e-3
        assert abs(body["destination"]["lng"] - 31.5920) < 1e-3
    finally:
        loop.run_until_complete(_flip("out_for_delivery"))


def test_live_tracking_split_returns_driver_and_eta(ctx, mongo):
    """Post a driver location (~1 km from Hai Cinema centroid) and verify eta ~= dist*4."""
    db, loop = mongo
    # Post known driver location
    r = requests.post(f"{BASE_URL}/api/driver/location",
                      headers=ctx["driver_hdr"],
                      json={"lat": 4.8560, "lng": 31.6020}, timeout=30)  # ~1.1km east of Hai Cinema
    assert r.status_code == 200

    r = requests.get(
        f"{BASE_URL}/api/customer/orders/{ctx['parent_order_id']}/live-tracking",
        headers=ctx["cust_hdr"], timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["assignments"]) >= 1
    # Find our split
    entry = next((a for a in body["assignments"]
                  if a.get("assignment_kind") == "split"
                  and a.get("driver_id") == ctx["driver_id"]), None)
    assert entry is not None, body
    assert entry["driver_location"]["lat"] == 4.8560
    assert entry["driver_location"]["lng"] == 31.6020
    assert entry["status"] == "out_for_delivery"
    assert "distance_km" in entry
    assert "eta_minutes" in entry
    expected_eta = max(1, round(entry["distance_km"] * 4))
    assert entry["eta_minutes"] == expected_eta
    # Destination area is Hai Cinema -> uses JUBA_AREA_COORDS
    assert abs(body["destination"]["lat"] - 4.8560) < 1e-3


def test_live_tracking_admin_can_access(ctx):
    r = requests.get(
        f"{BASE_URL}/api/customer/orders/{ctx['parent_order_id']}/live-tracking",
        headers=ctx["admin_hdr"], timeout=30,
    )
    assert r.status_code == 200


def test_live_tracking_restaurant_order_uses_fallback_dest(ctx):
    """Restaurant order with unknown area -> destination should be JUBA_DEFAULT_COORDS."""
    r = requests.get(
        f"{BASE_URL}/api/customer/orders/{ctx['rest_order_id']}/live-tracking",
        headers=ctx["cust_hdr"], timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Destination fallback (4.8517, 31.5825)
    assert abs(body["destination"]["lat"] - 4.8517) < 1e-3
    assert abs(body["destination"]["lng"] - 31.5825) < 1e-3
    # restaurant_order assignment kind
    kinds = {a.get("assignment_kind") for a in body["assignments"]}
    assert "restaurant_order" in kinds
    entry = next(a for a in body["assignments"] if a.get("assignment_kind") == "restaurant_order")
    assert entry["driver_id"] == ctx["driver_id"]
    assert entry["status"] == "out_for_delivery"


# ---------- Regression: iteration 14 quick sanity ----------

def test_regression_shops_anonymous_filters_pending():
    r = requests.get(f"{BASE_URL}/api/shops", timeout=30)
    assert r.status_code == 200
    for s in r.json():
        # Anonymous listing only shows Verified shops
        assert s.get("verification", "Verified") == "Verified", s
