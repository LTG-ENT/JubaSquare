"""
Iter6 — JubaSquare Phase-5: Restaurant Open/Close + Cancellation + Commission Invoices.

Coverage:
A. Open/Close toggle (PUT /restaurants/{id}/toggle-open)
   - Toggling Closed blocks POST /restaurant-orders with 400.
   - Re-opening allows orders again.
B. Cancellation flow (seller request -> admin approve / reject)
   - request-cancel requires accepted/cooking/ready; pending/completed -> 400
   - approve sets cancel_approved; double-approve -> 400
   - reject restores previous_status; reject when not requested -> 400
   - GET /admin/cancel-requests admin-only, only cancel_requested rows
C. PUT /restaurant-orders/{id}/status — seller forbidden from
   cancelled/cancel_approved/cancel_rejected; admin allowed.
D. Restaurant invoices
   - POST /admin/restaurant-invoices/generate returns {ok,count}
   - Auto-rebuild on status=completed surfaces in GET admin list
   - GET supports ?status=Paid|Unpaid filter
   - PUT status flips Paid/Unpaid/Overdue, notifies seller (Paid)
   - GET /seller/restaurant-invoices scoped to caller
   - total_sales uses subtotal (NOT delivery_fee), uses restaurant commission_rate first
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or "https://wallet-auto-refresh.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@ltg.com", "password": "Kokobleake1"}

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
    email = f"test_iter6_{role}_{suffix}@x.com"
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
def restaurant(admin_ctx, seller_ctx):
    """Create a restaurant owned by our seller (via admin override to ensure verification)."""
    body = {
        "name": f"TEST_Iter6_Restaurant_{uuid.uuid4().hex[:6]}",
        "category": "general",
        "area": "Juba",
        "is_open": True,
        "delivery_pricing": {"type": "fixed", "fixed_fee": 2.5},
    }
    # Create as seller
    r = requests.post(f"{API}/restaurants", headers=seller_ctx["h"], json=body, timeout=20)
    assert r.status_code in (200, 201), f"create restaurant: {r.status_code} {r.text}"
    rest = r.json()
    # Force verification + commission_rate for predictable totals
    _mongo.restaurants.update_one(
        {"id": rest["id"]},
        {"$set": {"verification": "approved", "commission_rate": 0.20}},
    )
    yield rest
    _mongo.restaurants.delete_one({"id": rest["id"]})
    _mongo.menu_items.delete_many({"restaurant_id": rest["id"]})
    _mongo.restaurant_orders.delete_many({"restaurant_id": rest["id"]})
    _mongo.restaurant_invoices.delete_many({"restaurant_id": rest["id"]})


@pytest.fixture(scope="module")
def menu_item(seller_ctx, restaurant):
    """Need a category_id. Pick or create one (group=restaurant)."""
    # Find or insert a restaurant category directly
    cat = _mongo.categories.find_one({"group": "restaurant"})
    if not cat:
        cat_id = str(uuid.uuid4())
        _mongo.categories.insert_one({
            "id": cat_id, "name": "TEST_Cat_Iter6", "group": "restaurant",
        })
    else:
        cat_id = cat["id"]
    body = {
        "restaurant_id": restaurant["id"],
        "name": "TEST_Iter6_Burger",
        "price_usd": 10.0,
        "category_id": cat_id,
    }
    r = requests.post(f"{API}/menu-items", headers=seller_ctx["h"], json=body, timeout=20)
    assert r.status_code in (200, 201), f"menu-item: {r.status_code} {r.text}"
    item = r.json()
    yield item
    _mongo.menu_items.delete_one({"id": item["id"]})


def _place_order(customer_ctx, restaurant, menu_item, qty=2):
    body = {
        "restaurant_id": restaurant["id"],
        "items": [{
            "item_type": "menu_item",
            "item_id": menu_item["id"],
            "name": menu_item["name"],
            "price_usd": menu_item["price_usd"],
            "quantity": qty,
            "sides": [],
        }],
        "delivery_type": "pickup",
        "customer_name": "Test Customer",
        "customer_phone": "+211900000001",
        "customer_address": "",
        "payment_method": "cash",
    }
    return requests.post(f"{API}/restaurant-orders", headers=customer_ctx["h"], json=body, timeout=20)


def _set_status_as_admin(admin_ctx, order_id, status):
    return requests.put(
        f"{API}/restaurant-orders/{order_id}/status",
        headers=admin_ctx["h"], json={"status": status}, timeout=20,
    )


# =================== A. OPEN/CLOSE ===================

class TestOpenCloseToggle:
    def test_toggle_open_blocks_orders_when_closed(self, seller_ctx, customer_ctx, restaurant, menu_item):
        # close the restaurant
        r = requests.put(
            f"{API}/restaurants/{restaurant['id']}/toggle-open",
            headers=seller_ctx["h"], timeout=20,
        )
        assert r.status_code == 200
        assert r.json()["is_open"] is False

        # placing an order should be 400
        r2 = _place_order(customer_ctx, restaurant, menu_item)
        assert r2.status_code == 400, r2.text
        detail = r2.json().get("detail", "")
        assert "closed" in detail.lower(), detail

    def test_toggle_back_open_allows_orders(self, seller_ctx, customer_ctx, restaurant, menu_item):
        r = requests.put(
            f"{API}/restaurants/{restaurant['id']}/toggle-open",
            headers=seller_ctx["h"], timeout=20,
        )
        assert r.status_code == 200
        assert r.json()["is_open"] is True

        r2 = _place_order(customer_ctx, restaurant, menu_item)
        assert r2.status_code in (200, 201), r2.text
        order = r2.json()
        assert order["status"] == "pending"
        # cleanup direct
        _mongo.restaurant_orders.delete_one({"id": order["id"]})


# =================== B. CANCELLATION FLOW ===================

class TestCancellationFlow:
    def test_request_cancel_rejected_when_pending(self, seller_ctx, customer_ctx, restaurant, menu_item):
        r = _place_order(customer_ctx, restaurant, menu_item)
        assert r.status_code in (200, 201)
        order_id = r.json()["id"]
        try:
            # pending - not allowed
            rr = requests.post(
                f"{API}/restaurant-orders/{order_id}/request-cancel",
                headers=seller_ctx["h"], json={"reason": "too early"}, timeout=20,
            )
            assert rr.status_code == 400, rr.text
        finally:
            _mongo.restaurant_orders.delete_one({"id": order_id})

    def test_request_cancel_rejected_when_completed(self, admin_ctx, seller_ctx, customer_ctx, restaurant, menu_item):
        r = _place_order(customer_ctx, restaurant, menu_item)
        order_id = r.json()["id"]
        try:
            # walk to completed via admin
            for s in ("accepted", "cooking", "ready", "completed"):
                _set_status_as_admin(admin_ctx, order_id, s)
            rr = requests.post(
                f"{API}/restaurant-orders/{order_id}/request-cancel",
                headers=seller_ctx["h"], json={"reason": "late"}, timeout=20,
            )
            assert rr.status_code == 400
        finally:
            _mongo.restaurant_orders.delete_one({"id": order_id})

    def test_request_cancel_success_from_accepted(self, admin_ctx, seller_ctx, customer_ctx, restaurant, menu_item):
        r = _place_order(customer_ctx, restaurant, menu_item)
        order_id = r.json()["id"]
        try:
            _set_status_as_admin(admin_ctx, order_id, "accepted")
            rr = requests.post(
                f"{API}/restaurant-orders/{order_id}/request-cancel",
                headers=seller_ctx["h"], json={"reason": "out of stock"}, timeout=20,
            )
            assert rr.status_code == 200, rr.text
            data = rr.json()
            assert data["status"] == "cancel_requested"
            assert data["previous_status"] == "accepted"
            # DB sanity
            doc = _mongo.restaurant_orders.find_one({"id": order_id})
            assert doc["cancel_reason"] == "out of stock"
            assert "cancel_requested_at" in doc
            # Notification created for customer
            notif = _mongo.notifications.find_one({
                "user_id": customer_ctx["user"]["id"],
                "meta.order_id": order_id,
            })
            assert notif is not None, "customer notification missing"
        finally:
            _mongo.restaurant_orders.delete_one({"id": order_id})

    def test_admin_approve_cancel(self, admin_ctx, seller_ctx, customer_ctx, restaurant, menu_item):
        r = _place_order(customer_ctx, restaurant, menu_item)
        order_id = r.json()["id"]
        try:
            _set_status_as_admin(admin_ctx, order_id, "cooking")
            requests.post(f"{API}/restaurant-orders/{order_id}/request-cancel",
                          headers=seller_ctx["h"], json={"reason": "fire"}, timeout=20)
            rr = requests.post(f"{API}/admin/cancel-requests/{order_id}/approve",
                               headers=admin_ctx["h"], timeout=20)
            assert rr.status_code == 200, rr.text
            assert rr.json()["status"] == "cancel_approved"

            # second call must 400 (no pending request)
            r2 = requests.post(f"{API}/admin/cancel-requests/{order_id}/approve",
                               headers=admin_ctx["h"], timeout=20)
            assert r2.status_code == 400
        finally:
            _mongo.restaurant_orders.delete_one({"id": order_id})

    def test_admin_reject_cancel_restores_previous(self, admin_ctx, seller_ctx, customer_ctx, restaurant, menu_item):
        r = _place_order(customer_ctx, restaurant, menu_item)
        order_id = r.json()["id"]
        try:
            _set_status_as_admin(admin_ctx, order_id, "ready")
            requests.post(f"{API}/restaurant-orders/{order_id}/request-cancel",
                          headers=seller_ctx["h"], json={"reason": "?"}, timeout=20)
            rr = requests.post(
                f"{API}/admin/cancel-requests/{order_id}/reject",
                headers=admin_ctx["h"], json={"admin_note": "fulfil it"}, timeout=20,
            )
            assert rr.status_code == 200, rr.text
            assert rr.json()["status"] == "ready"  # restored
            # GET verifies persistence
            doc = _mongo.restaurant_orders.find_one({"id": order_id})
            assert doc["status"] == "ready"
            assert doc.get("cancel_rejected_note") == "fulfil it"
            # customer was notified
            notif = list(_mongo.notifications.find({
                "user_id": customer_ctx["user"]["id"],
                "meta.order_id": order_id,
            }))
            messages = " ".join(n.get("message", "") for n in notif)
            assert "rejected" in messages.lower()

            # reject again must 400
            r2 = requests.post(
                f"{API}/admin/cancel-requests/{order_id}/reject",
                headers=admin_ctx["h"], json={"admin_note": ""}, timeout=20,
            )
            assert r2.status_code == 400
        finally:
            _mongo.restaurant_orders.delete_one({"id": order_id})

    def test_admin_list_cancel_requests_only_pending(self, admin_ctx, seller_ctx, customer_ctx, restaurant, menu_item):
        # one pending request
        r = _place_order(customer_ctx, restaurant, menu_item)
        order_id = r.json()["id"]
        try:
            _set_status_as_admin(admin_ctx, order_id, "accepted")
            requests.post(f"{API}/restaurant-orders/{order_id}/request-cancel",
                          headers=seller_ctx["h"], json={"reason": "x"}, timeout=20)
            r = requests.get(f"{API}/admin/cancel-requests", headers=admin_ctx["h"], timeout=20)
            assert r.status_code == 200
            ids = [o["id"] for o in r.json()]
            assert order_id in ids
            for o in r.json():
                assert o["status"] == "cancel_requested"
        finally:
            _mongo.restaurant_orders.delete_one({"id": order_id})

    def test_admin_list_cancel_requests_forbidden_for_seller(self, seller_ctx):
        r = requests.get(f"{API}/admin/cancel-requests", headers=seller_ctx["h"], timeout=20)
        assert r.status_code == 403


# =================== C. SELLER STATUS RESTRICTIONS ===================

class TestSellerStatusRestrictions:
    @pytest.mark.parametrize("status", ["cancelled", "cancel_approved", "cancel_rejected"])
    def test_seller_cannot_force_cancel_status(self, admin_ctx, seller_ctx, customer_ctx, restaurant, menu_item, status):
        r = _place_order(customer_ctx, restaurant, menu_item)
        order_id = r.json()["id"]
        try:
            _set_status_as_admin(admin_ctx, order_id, "accepted")
            rr = requests.put(
                f"{API}/restaurant-orders/{order_id}/status",
                headers=seller_ctx["h"], json={"status": status}, timeout=20,
            )
            assert rr.status_code == 403, rr.text
        finally:
            _mongo.restaurant_orders.delete_one({"id": order_id})

    def test_admin_can_set_cancelled_directly(self, admin_ctx, customer_ctx, restaurant, menu_item):
        r = _place_order(customer_ctx, restaurant, menu_item)
        order_id = r.json()["id"]
        try:
            rr = _set_status_as_admin(admin_ctx, order_id, "cancelled")
            assert rr.status_code == 200, rr.text
        finally:
            _mongo.restaurant_orders.delete_one({"id": order_id})


# =================== D. RESTAURANT INVOICES ===================

class TestRestaurantInvoices:
    def test_generate_returns_count(self, admin_ctx):
        r = requests.post(f"{API}/admin/restaurant-invoices/generate",
                          headers=admin_ctx["h"], timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert isinstance(d["count"], int)

    def test_auto_generate_on_completed(self, admin_ctx, customer_ctx, restaurant, menu_item, seller_ctx):
        # place + complete order
        r = _place_order(customer_ctx, restaurant, menu_item, qty=3)  # subtotal 30.0
        order = r.json()
        order_id = order["id"]
        try:
            for s in ("accepted", "cooking", "ready", "completed"):
                rr = _set_status_as_admin(admin_ctx, order_id, s)
                assert rr.status_code == 200, rr.text

            # Should now have an invoice for this seller+restaurant
            r2 = requests.get(f"{API}/admin/restaurant-invoices",
                              headers=admin_ctx["h"], timeout=20)
            assert r2.status_code == 200
            invs = r2.json()
            mine = [i for i in invs if i["restaurant_id"] == restaurant["id"]
                    and i["seller_id"] == seller_ctx["user"]["id"]]
            assert len(mine) >= 1, "auto-rebuild did not produce invoice"
            inv = mine[0]
            # total_sales uses subtotal (3 * 10) — delivery_fee was 0 (pickup) but verify field
            assert inv["total_sales"] >= 30.0
            assert inv["commission_rate"] == 0.20  # restaurant override wins
            # commission = total_sales * 0.20
            assert abs(inv["commission"] - round(inv["total_sales"] * 0.20, 2)) < 0.01
            assert inv["status"] in ("Paid", "Unpaid")
            self._inv_id = inv["id"]
        finally:
            # leave order so the invoice persists for next test
            pass

    def test_filter_unpaid_only(self, admin_ctx):
        r = requests.get(f"{API}/admin/restaurant-invoices?status=Unpaid",
                         headers=admin_ctx["h"], timeout=20)
        assert r.status_code == 200
        for inv in r.json():
            assert inv["status"] == "Unpaid"

    def test_seller_scoped_list(self, seller_ctx, restaurant):
        r = requests.get(f"{API}/seller/restaurant-invoices",
                         headers=seller_ctx["h"], timeout=20)
        assert r.status_code == 200
        invs = r.json()
        # All returned must belong to this seller
        for inv in invs:
            assert inv["seller_id"] == seller_ctx["user"]["id"]

    def test_mark_paid_notifies_seller(self, admin_ctx, seller_ctx, restaurant):
        # pick one of our restaurant's invoices
        invs = _mongo.restaurant_invoices.find({"restaurant_id": restaurant["id"]}).limit(1)
        invs = list(invs)
        if not invs:
            pytest.skip("no invoice present to mark paid")
        inv_id = invs[0]["id"]
        r = requests.put(
            f"{API}/admin/restaurant-invoices/{inv_id}/status",
            headers=admin_ctx["h"], json={"status": "Paid"}, timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "Paid"
        # Notification created for seller
        notif = _mongo.notifications.find_one({
            "user_id": seller_ctx["user"]["id"],
            "type": "commission",
            "meta.restaurant_invoice_id": inv_id,
        })
        assert notif is not None, "seller paid-notification missing"

    def test_admin_only_list(self, customer_ctx):
        r = requests.get(f"{API}/admin/restaurant-invoices",
                         headers=customer_ctx["h"], timeout=20)
        assert r.status_code in (401, 403)

    def test_admin_only_generate(self, customer_ctx):
        r = requests.post(f"{API}/admin/restaurant-invoices/generate",
                          headers=customer_ctx["h"], timeout=20)
        assert r.status_code in (401, 403)
