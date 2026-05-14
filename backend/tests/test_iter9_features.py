"""
Iter9 — Test the 6 new features added in this iteration:
1. Customer Note flows through restaurant order doc (read by seller).
2. POST /seller/restaurant-orders/{id}/ready-for-pickup auto-assigns a driver
   via round-robin -> delivery_status='offered', driver_id set.
3. POST /driver/restaurant-orders/{id}/accept-offer -> delivery_status='assigned'.
4. POST /driver/restaurant-orders/{id}/decline-offer -> re-offered to next driver,
   or fallback to 'unassigned' + admin notification if only one driver exists.
5. Driver listing under /driver/assignments returns offered orders.
6. (Frontend lockdown / UI test-ids tested separately via Playwright.)
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or "https://driver-area-filter.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@LTG.com", "password": "Kokobleake1"}
DRIVER_DEFAULT = {"email": "driver@demo.com", "password": "1234"}

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "jubasquare_db")
_mongo = MongoClient(MONGO_URL)[DB_NAME]


# ---------------- helpers ----------------
def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    d = r.json()
    return d["token"], d["user"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _create_verified_user(role: str):
    suffix = uuid.uuid4().hex[:8]
    email = f"test_iter9_{role}_{suffix}@x.com"
    pw = "Pass1234!"
    r = requests.post(f"{API}/auth/signup", json={
        "email": email, "name": f"TEST {role} {suffix}", "password": pw,
        "role": role,
    }, timeout=20)
    assert r.status_code in (200, 201), f"signup failed: {r.status_code} {r.text}"
    _mongo.users.update_one({"email": email}, {"$set": {"email_verified": True, "role": role}})
    tok, user = _login({"email": email, "password": pw})
    return tok, user, email


# ---------------- fixtures ----------------
@pytest.fixture(scope="module")
def admin_ctx():
    tok, user = _login(ADMIN)
    return {"tok": tok, "user": user, "h": _h(tok)}


@pytest.fixture(scope="module")
def seller_ctx():
    tok, user, email = _create_verified_user("seller")
    yield {"tok": tok, "user": user, "h": _h(tok), "email": email}
    _mongo.users.delete_one({"email": email})


@pytest.fixture(scope="module")
def customer_ctx():
    tok, user, email = _create_verified_user("customer")
    yield {"tok": tok, "user": user, "h": _h(tok), "email": email}
    _mongo.users.delete_one({"email": email})


@pytest.fixture(scope="module")
def driver_ctx():
    """Use the seeded driver@demo.com."""
    tok, user = _login(DRIVER_DEFAULT)
    return {"tok": tok, "user": user, "h": _h(tok)}


@pytest.fixture(scope="module")
def second_driver_ctx(admin_ctx):
    """Create a second driver via POST /api/admin/drivers."""
    suffix = uuid.uuid4().hex[:6]
    email = f"test_iter9_driver_{suffix}@x.com"
    pw = "Pass1234!"
    body = {
        "email": email, "name": f"TEST driver {suffix}",
        "password": pw, "phone": "+211900999000",
    }
    r = requests.post(f"{API}/admin/drivers", headers=admin_ctx["h"], json=body, timeout=20)
    assert r.status_code in (200, 201), f"admin/drivers create: {r.status_code} {r.text}"
    tok, user = _login({"email": email, "password": pw})
    yield {"tok": tok, "user": user, "h": _h(tok), "email": email}
    _mongo.users.delete_one({"email": email})


@pytest.fixture(scope="module")
def restaurant(seller_ctx):
    body = {
        "name": f"TEST_Iter9_Restaurant_{uuid.uuid4().hex[:6]}",
        "category": "general",
        "area": "Juba",
        "is_open": True,
        "delivery_pricing": {"type": "fixed", "fixed_fee": 2.5},
    }
    r = requests.post(f"{API}/restaurants", headers=seller_ctx["h"], json=body, timeout=20)
    assert r.status_code in (200, 201), f"create restaurant: {r.status_code} {r.text}"
    rest = r.json()
    _mongo.restaurants.update_one(
        {"id": rest["id"]},
        {"$set": {"verification": "approved", "commission_rate": 0.20}},
    )
    yield rest
    _mongo.restaurants.delete_one({"id": rest["id"]})
    _mongo.menu_items.delete_many({"restaurant_id": rest["id"]})
    _mongo.restaurant_orders.delete_many({"restaurant_id": rest["id"]})


@pytest.fixture(scope="module")
def menu_item(seller_ctx, restaurant):
    cat = _mongo.categories.find_one({"group": "restaurant"})
    if not cat:
        cat_id = str(uuid.uuid4())
        _mongo.categories.insert_one({
            "id": cat_id, "name": "TEST_Cat_Iter9", "group": "restaurant",
        })
    else:
        cat_id = cat["id"]
    body = {
        "restaurant_id": restaurant["id"],
        "name": "TEST_Iter9_Burger",
        "price_usd": 10.0,
        "category_id": cat_id,
    }
    r = requests.post(f"{API}/menu-items", headers=seller_ctx["h"], json=body, timeout=20)
    assert r.status_code in (200, 201), f"menu-item: {r.status_code} {r.text}"
    yield r.json()
    _mongo.menu_items.delete_one({"id": r.json()["id"]})


def _place_order(customer_ctx, restaurant, menu_item, note=""):
    body = {
        "restaurant_id": restaurant["id"],
        "items": [{
            "item_type": "menu_item",
            "item_id": menu_item["id"],
            "name": menu_item["name"],
            "price_usd": menu_item["price_usd"],
            "quantity": 1,
            "sides": [],
        }],
        "delivery_type": "delivery",
        "customer_name": "Test Customer",
        "customer_phone": "+211900000001",
        "customer_address": "Test Addr",
        "customer_area": "Juba",
        "payment_method": "cash",
        "note": note,
    }
    return requests.post(f"{API}/restaurant-orders", headers=customer_ctx["h"], json=body, timeout=20)


def _seller_accept_and_prepare(seller_ctx, order_id):
    """Move order: pending -> accepted -> preparing (so ready-for-pickup is valid)."""
    # Try the seller status setter
    for status in ("accepted", "cooking"):
        r = requests.put(
            f"{API}/restaurant-orders/{order_id}/status",
            headers=seller_ctx["h"],
            json={"status": status},
            timeout=20,
        )
        # We tolerate 200 or no-op; print to help debug
        if r.status_code not in (200, 201):
            print(f"status->{status} returned {r.status_code} {r.text}")


# =========================================================
# Feature 1 — Customer Note saved in the order doc.
# =========================================================
class TestCustomerNote:
    def test_note_persisted_on_restaurant_order(self, customer_ctx, restaurant, menu_item):
        note_text = f"TEST_NOTE_{uuid.uuid4().hex[:6]} — extra spicy please"
        r = _place_order(customer_ctx, restaurant, menu_item, note=note_text)
        assert r.status_code in (200, 201), f"place order: {r.status_code} {r.text}"
        order = r.json()
        oid = order["id"]
        # Read directly from DB to make sure the note is stored
        doc = _mongo.restaurant_orders.find_one({"id": oid}, {"_id": 0})
        assert doc is not None
        assert doc.get("note") == note_text, f"note mismatch: got {doc.get('note')!r}"


# =========================================================
# Feature 2 — Auto-assign driver on ready-for-pickup.
# =========================================================
class TestAutoAssignDriver:
    def test_ready_for_pickup_auto_assigns_offered(
        self, seller_ctx, customer_ctx, restaurant, menu_item, driver_ctx
    ):
        r = _place_order(customer_ctx, restaurant, menu_item, note="auto-assign test")
        assert r.status_code in (200, 201)
        oid = r.json()["id"]

        # Ensure the order is past pending so ready-for-pickup is valid
        _seller_accept_and_prepare(seller_ctx, oid)

        # Trigger ready-for-pickup
        r2 = requests.post(
            f"{API}/seller/restaurant-orders/{oid}/ready-for-pickup",
            headers=seller_ctx["h"],
            timeout=20,
        )
        assert r2.status_code == 200, f"ready-for-pickup: {r2.status_code} {r2.text}"

        # Verify directly from Mongo to bypass any read-side redaction
        doc = _mongo.restaurant_orders.find_one({"id": oid}, {"_id": 0})
        assert doc is not None
        assert doc.get("seller_preparation_status") == "ready_for_pickup"
        assert doc.get("delivery_status") == "offered", (
            f"expected 'offered', got {doc.get('delivery_status')!r}"
        )
        assert doc.get("driver_id"), "driver_id should be set after auto-assign"


# =========================================================
# Feature 3 — Driver Accept.
# =========================================================
class TestDriverAccept:
    def test_driver_accept_offer(
        self, seller_ctx, customer_ctx, restaurant, menu_item, driver_ctx
    ):
        # Place + transition to ready_for_pickup
        r = _place_order(customer_ctx, restaurant, menu_item, note="accept test")
        oid = r.json()["id"]
        _seller_accept_and_prepare(seller_ctx, oid)
        r2 = requests.post(
            f"{API}/seller/restaurant-orders/{oid}/ready-for-pickup",
            headers=seller_ctx["h"], timeout=20,
        )
        assert r2.status_code == 200
        doc = _mongo.restaurant_orders.find_one({"id": oid}, {"_id": 0})
        assert doc.get("delivery_status") == "offered"

        # Force-assign to the seeded driver (round-robin may pick another in a multi-driver env)
        _mongo.restaurant_orders.update_one(
            {"id": oid},
            {"$set": {"driver_id": driver_ctx["user"]["id"],
                      "driver_name": driver_ctx["user"].get("name", ""),
                      "delivery_status": "offered"}},
        )

        # Driver accepts
        r3 = requests.post(
            f"{API}/driver/restaurant-orders/{oid}/accept-offer",
            headers=driver_ctx["h"], timeout=20,
        )
        assert r3.status_code == 200, f"accept-offer: {r3.status_code} {r3.text}"
        doc2 = _mongo.restaurant_orders.find_one({"id": oid}, {"_id": 0})
        assert doc2.get("delivery_status") == "assigned", (
            f"expected 'assigned' after accept, got {doc2.get('delivery_status')!r}"
        )


# =========================================================
# Feature 4 — Driver Decline → re-offered to next driver.
# =========================================================
class TestDriverDecline:
    def test_decline_reoffers_to_next_driver(
        self, seller_ctx, customer_ctx, restaurant, menu_item, driver_ctx, second_driver_ctx
    ):
        r = _place_order(customer_ctx, restaurant, menu_item, note="decline test")
        oid = r.json()["id"]
        _seller_accept_and_prepare(seller_ctx, oid)
        r2 = requests.post(
            f"{API}/seller/restaurant-orders/{oid}/ready-for-pickup",
            headers=seller_ctx["h"], timeout=20,
        )
        assert r2.status_code == 200

        # Force-assign to the first driver
        _mongo.restaurant_orders.update_one(
            {"id": oid},
            {"$set": {"driver_id": driver_ctx["user"]["id"],
                      "driver_name": driver_ctx["user"].get("name", ""),
                      "delivery_status": "offered"}},
        )

        r3 = requests.post(
            f"{API}/driver/restaurant-orders/{oid}/decline-offer",
            headers=driver_ctx["h"], timeout=20,
        )
        assert r3.status_code == 200, f"decline: {r3.status_code} {r3.text}"
        body = r3.json()
        # Either re-offered or unassigned
        doc = _mongo.restaurant_orders.find_one({"id": oid}, {"_id": 0})
        assert driver_ctx["user"]["id"] in (doc.get("declined_by") or [])

        next_did = body.get("reoffered_to")
        if next_did:
            # Re-offered: second driver should be the one
            assert doc.get("driver_id") == next_did
            assert doc.get("delivery_status") == "offered"
        else:
            # All declined → unassigned + admin notified
            assert doc.get("delivery_status") == "unassigned"
            assert doc.get("driver_id") in (None, "")

    def test_single_driver_fallback_unassigned(
        self, seller_ctx, customer_ctx, restaurant, menu_item, driver_ctx
    ):
        """Simulate single-driver: place fresh order, set declined_by to include
        all OTHER drivers, then decline — the order should fall to 'unassigned'."""
        # Deactivate all other drivers to simulate single-driver world
        other_drivers = list(_mongo.users.find(
            {"role": "driver", "is_active": True, "id": {"$ne": driver_ctx["user"]["id"]}},
            {"id": 1, "_id": 0},
        ))
        other_ids = [d["id"] for d in other_drivers]
        if other_ids:
            _mongo.users.update_many(
                {"id": {"$in": other_ids}}, {"$set": {"is_active": False}}
            )

        try:
            r = _place_order(customer_ctx, restaurant, menu_item, note="single-driver decline")
            oid = r.json()["id"]
            _seller_accept_and_prepare(seller_ctx, oid)
            requests.post(
                f"{API}/seller/restaurant-orders/{oid}/ready-for-pickup",
                headers=seller_ctx["h"], timeout=20,
            )
            # Force the seeded driver
            _mongo.restaurant_orders.update_one(
                {"id": oid},
                {"$set": {"driver_id": driver_ctx["user"]["id"],
                          "delivery_status": "offered"}},
            )
            r3 = requests.post(
                f"{API}/driver/restaurant-orders/{oid}/decline-offer",
                headers=driver_ctx["h"], timeout=20,
            )
            assert r3.status_code == 200
            doc = _mongo.restaurant_orders.find_one({"id": oid}, {"_id": 0})
            assert doc.get("delivery_status") == "unassigned"
            assert doc.get("driver_id") in (None, "")
        finally:
            if other_ids:
                _mongo.users.update_many(
                    {"id": {"$in": other_ids}}, {"$set": {"is_active": True}}
                )


# =========================================================
# Feature 5 — Driver sees offered orders in /driver/assignments.
# =========================================================
class TestDriverAssignmentsListing:
    def test_offered_orders_in_listing(
        self, seller_ctx, customer_ctx, restaurant, menu_item, driver_ctx
    ):
        r = _place_order(customer_ctx, restaurant, menu_item, note="listing test")
        oid = r.json()["id"]
        _seller_accept_and_prepare(seller_ctx, oid)
        requests.post(
            f"{API}/seller/restaurant-orders/{oid}/ready-for-pickup",
            headers=seller_ctx["h"], timeout=20,
        )
        _mongo.restaurant_orders.update_one(
            {"id": oid},
            {"$set": {"driver_id": driver_ctx["user"]["id"],
                      "delivery_status": "offered"}},
        )
        r2 = requests.get(f"{API}/driver/assignments", headers=driver_ctx["h"], timeout=20)
        assert r2.status_code == 200
        data = r2.json()
        ids = [o["id"] for o in (data.get("restaurant_orders") or [])]
        assert oid in ids, f"offered order {oid} missing from driver listing: {ids}"
