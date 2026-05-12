"""
Iter5 — JubaSquare Round 7: Shop Pages, Shop Edit, and Shop Messaging.

Coverage:
1) Shop GET/PUT round-trip of new storefront fields:
   banner_url, logo_url, opening_hours, is_open + delivery settings.
2) Auth-protected PUT /api/shops/{id} (only owner or admin).
3) Anonymous shop messages: requires email OR phone (400 if both missing);
   2-char minimum and 2000-char maximum body validation.
4) Logged-in user messages — no email needed.
5) GET /api/messages/seller — seller scoped to own shops; admin sees all.
6) GET /api/messages/seller/unread-count — {count: N}.
7) PUT /api/messages/{id}/read — owner / admin only; 404 unknown; 403 not owner.
8) DELETE /api/messages/{id} — same auth rules; data actually removed.
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or "https://category-bulletproof.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "ltg-general-trading@hotmail.com", "password": "Kokobleake1"}

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "jubasquare_db")
_mongo = MongoClient(MONGO_URL)[DB_NAME]


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    d = r.json()
    return d["token"], d["user"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _create_verified_user(role: str):
    """Sign up a fresh user then flip email_verified=True directly in DB."""
    suffix = uuid.uuid4().hex[:8]
    email = f"test_iter5_{role}_{suffix}@x.com"
    pw = "Pass1234!"
    r = requests.post(f"{API}/auth/signup", json={
        "email": email, "name": f"TEST {role} {suffix}", "password": pw,
        "role": role, "phone": "0",
    }, timeout=20)
    assert r.status_code == 200, f"signup failed: {r.text}"
    _mongo.users.update_one({"email": email}, {"$set": {"email_verified": True}})
    return _login({"email": email, "password": pw})


@pytest.fixture(scope="module")
def admin_ctx():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def seller_ctx():
    tok, user = _create_verified_user("seller")
    yield tok, user
    _mongo.users.delete_one({"id": user["id"]})


@pytest.fixture(scope="module")
def customer_ctx():
    tok, user = _create_verified_user("customer")
    yield tok, user
    _mongo.users.delete_one({"id": user["id"]})


@pytest.fixture(scope="module")
def seller_shop(seller_ctx):
    """Create a fresh shop owned by the seller for iter5 tests."""
    tok, _ = seller_ctx
    payload = {
        "name": f"TEST_Iter5_Shop_{uuid.uuid4().hex[:6]}",
        "description": "iter5 fixture shop",
        "image_url": "https://example.com/i.jpg",
        "area": "Munuki",
        "category": "General",
    }
    r = requests.post(f"{API}/shops", json=payload, headers=_h(tok), timeout=20)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    yield sid
    # teardown
    requests.delete(f"{API}/shops/{sid}", headers=_h(tok), timeout=20)


# -------------------- 1. Shop GET/PUT new fields round-trip --------------------
class TestShopStorefrontFields:
    def test_put_persists_new_fields(self, seller_ctx, seller_shop):
        tok, _ = seller_ctx
        payload = {
            "name": f"TEST_Iter5_Shop_renamed_{uuid.uuid4().hex[:4]}",
            "description": "new desc",
            "image_url": "https://example.com/i.jpg",
            "area": "Atlabara",
            "category": "General",
            "banner_url": "https://example.com/banner.jpg",
            "logo_url": "https://example.com/logo.png",
            "opening_hours": "Mon-Fri 9-5",
            "is_open": False,
            "delivery_mode": "fixed",
            "delivery_fee_usd": 4.5,
        }
        r = requests.put(f"{API}/shops/{seller_shop}", json=payload, headers=_h(tok), timeout=20)
        assert r.status_code == 200, r.text

        g = requests.get(f"{API}/shops/{seller_shop}", timeout=20)
        assert g.status_code == 200
        s = g.json()
        assert s["banner_url"] == "https://example.com/banner.jpg"
        assert s["logo_url"] == "https://example.com/logo.png"
        assert s["opening_hours"] == "Mon-Fri 9-5"
        assert s["is_open"] is False
        assert s["delivery_mode"] == "fixed"
        assert s["delivery_fee_usd"] == 4.5
        assert s["area"] == "Atlabara"

    def test_put_per_area_persists(self, seller_ctx, seller_shop):
        tok, _ = seller_ctx
        payload = {
            "name": "TEST_Iter5_PerArea",
            "description": "",
            "image_url": "",
            "area": "Munuki",
            "category": "General",
            "is_open": True,
            "delivery_mode": "per_area",
            "delivery_per_area": [
                {"area": "Munuki", "fee_usd": 1.5},
                {"area": "Atlabara", "fee_usd": 3.0},
            ],
        }
        r = requests.put(f"{API}/shops/{seller_shop}", json=payload, headers=_h(tok), timeout=20)
        assert r.status_code == 200, r.text
        s = requests.get(f"{API}/shops/{seller_shop}", timeout=20).json()
        assert s["delivery_mode"] == "per_area"
        assert len(s["delivery_per_area"]) == 2
        assert any(a["area"] == "Munuki" and a["fee_usd"] == 1.5 for a in s["delivery_per_area"])


# -------------------- 2. PUT /api/shops/{id} auth --------------------
class TestShopUpdateAuth:
    def test_other_seller_cannot_update_shop(self, customer_ctx, seller_shop):
        # customer is not seller — should be blocked at role gate (403)
        tok, _ = customer_ctx
        payload = {"name": "hijack", "description": "", "image_url": "", "area": "Munuki", "category": "x"}
        r = requests.put(f"{API}/shops/{seller_shop}", json=payload, headers=_h(tok), timeout=20)
        assert r.status_code in (401, 403), r.text

    def test_admin_can_update_any_shop(self, admin_ctx, seller_shop):
        tok, _ = admin_ctx
        payload = {
            "name": "TEST_Iter5_AdminEdit",
            "description": "edited by admin",
            "image_url": "",
            "area": "Munuki",
            "category": "General",
            "is_open": True,
        }
        r = requests.put(f"{API}/shops/{seller_shop}", json=payload, headers=_h(tok), timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["description"] == "edited by admin"

    def test_unauth_cannot_update(self, seller_shop):
        payload = {"name": "x", "description": "", "image_url": "", "area": "Munuki", "category": "x"}
        r = requests.put(f"{API}/shops/{seller_shop}", json=payload, timeout=20)
        assert r.status_code == 401


# -------------------- 3. Shop messages — anonymous --------------------
class TestShopMessagesAnonymous:
    def test_anon_requires_email_or_phone(self, seller_shop):
        r = requests.post(f"{API}/shops/{seller_shop}/messages",
                          json={"body": "Hello, are you open today?"}, timeout=20)
        assert r.status_code == 400
        assert "email" in r.text.lower() or "phone" in r.text.lower()

    def test_anon_with_email_accepted(self, seller_shop):
        r = requests.post(f"{API}/shops/{seller_shop}/messages",
                          json={"body": "Hi from guest", "customer_email": "guest@x.com",
                                "customer_name": "Guest A"},
                          timeout=20)
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["body"] == "Hi from guest"
        assert m["customer_email"] == "guest@x.com"
        assert m["is_read"] is False
        assert m["shop_id"] == seller_shop

    def test_anon_with_phone_accepted(self, seller_shop):
        r = requests.post(f"{API}/shops/{seller_shop}/messages",
                          json={"body": "Phone-only ping", "customer_phone": "+211900000000"},
                          timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["customer_phone"] == "+211900000000"

    def test_body_too_short(self, seller_shop):
        r = requests.post(f"{API}/shops/{seller_shop}/messages",
                          json={"body": "a", "customer_email": "g@x.com"}, timeout=20)
        assert r.status_code == 400

    def test_body_too_long(self, seller_shop):
        r = requests.post(f"{API}/shops/{seller_shop}/messages",
                          json={"body": "a" * 2001, "customer_email": "g@x.com"}, timeout=20)
        assert r.status_code == 400

    def test_unknown_shop(self):
        r = requests.post(f"{API}/shops/{uuid.uuid4().hex}/messages",
                          json={"body": "hello", "customer_email": "g@x.com"}, timeout=20)
        assert r.status_code == 404


# -------------------- 4. Shop messages — logged-in --------------------
class TestShopMessagesLoggedIn:
    def test_logged_in_no_email_needed(self, customer_ctx, seller_shop):
        tok, user = customer_ctx
        r = requests.post(f"{API}/shops/{seller_shop}/messages",
                          json={"body": "Hi from customer", "subject": "Question"},
                          headers=_h(tok), timeout=20)
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["customer_id"] == user["id"]
        assert m["customer_email"] == user["email"]
        assert m["subject"] == "Question"


# -------------------- 5/6. Seller messages list + unread count --------------------
class TestSellerInbox:
    def test_seller_lists_only_own_shop_messages(self, seller_ctx, customer_ctx, seller_shop):
        # seed an inbound message
        ctok, _ = customer_ctx
        requests.post(f"{API}/shops/{seller_shop}/messages",
                      json={"body": "Inbox seed iter5"},
                      headers=_h(ctok), timeout=20)

        stok, suser = seller_ctx
        r = requests.get(f"{API}/messages/seller", headers=_h(stok), timeout=20)
        assert r.status_code == 200
        msgs = r.json()
        assert isinstance(msgs, list)
        assert len(msgs) >= 1
        for m in msgs:
            assert m["seller_id"] == suser["id"]

    def test_admin_sees_all(self, admin_ctx):
        tok, _ = admin_ctx
        r = requests.get(f"{API}/messages/seller", headers=_h(tok), timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_unread_count_returns_count_key(self, seller_ctx):
        tok, _ = seller_ctx
        r = requests.get(f"{API}/messages/seller/unread-count", headers=_h(tok), timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "count" in d and isinstance(d["count"], int) and d["count"] >= 0

    def test_customer_blocked_from_seller_inbox(self, customer_ctx):
        tok, _ = customer_ctx
        r = requests.get(f"{API}/messages/seller", headers=_h(tok), timeout=20)
        assert r.status_code == 403


# -------------------- 7. PUT mark-as-read --------------------
class TestMessageRead:
    def _seed_message(self, seller_shop):
        r = requests.post(f"{API}/shops/{seller_shop}/messages",
                          json={"body": "Read-test seed", "customer_email": "g@x.com"},
                          timeout=20)
        assert r.status_code == 200
        return r.json()["id"]

    def test_mark_as_read_decrements_count(self, seller_ctx, seller_shop):
        tok, _ = seller_ctx
        before = requests.get(f"{API}/messages/seller/unread-count",
                              headers=_h(tok), timeout=20).json()["count"]
        mid = self._seed_message(seller_shop)
        mid_ct = requests.get(f"{API}/messages/seller/unread-count",
                              headers=_h(tok), timeout=20).json()["count"]
        assert mid_ct == before + 1
        r = requests.put(f"{API}/messages/{mid}/read", headers=_h(tok), timeout=20)
        assert r.status_code == 200
        after = requests.get(f"{API}/messages/seller/unread-count",
                             headers=_h(tok), timeout=20).json()["count"]
        assert after == before

    def test_mark_unknown_404(self, seller_ctx):
        tok, _ = seller_ctx
        r = requests.put(f"{API}/messages/{uuid.uuid4().hex}/read",
                         headers=_h(tok), timeout=20)
        assert r.status_code == 404

    def test_mark_other_seller_403(self, admin_ctx, seller_ctx, seller_shop):
        # Create a second seller-owned shop via admin (admin owns shops too)
        atok, auser = admin_ctx
        # Send a message to the seller's shop, then try marking it as read by a non-owner.
        # We'll use the customer route — the customer can't mark anyway (403 by role).
        # To test 403 specifically, create another shop owned by admin and message it,
        # then seller (who doesn't own it) tries to mark it.
        sp = {"name": f"TEST_AdminShop_{uuid.uuid4().hex[:5]}",
              "description": "", "image_url": "", "area": "Munuki", "category": "G"}
        ar = requests.post(f"{API}/shops", json=sp, headers=_h(atok), timeout=20)
        assert ar.status_code == 200, ar.text
        admin_sid = ar.json()["id"]
        try:
            mr = requests.post(f"{API}/shops/{admin_sid}/messages",
                               json={"body": "to admin shop", "customer_email": "g@x.com"},
                               timeout=20)
            assert mr.status_code == 200
            mid = mr.json()["id"]

            stok, _ = seller_ctx
            r = requests.put(f"{API}/messages/{mid}/read", headers=_h(stok), timeout=20)
            assert r.status_code == 403
        finally:
            requests.delete(f"{API}/shops/{admin_sid}", headers=_h(atok), timeout=20)


# -------------------- 8. DELETE message --------------------
class TestMessageDelete:
    def test_delete_removes_message(self, seller_ctx, seller_shop):
        tok, _ = seller_ctx
        r = requests.post(f"{API}/shops/{seller_shop}/messages",
                          json={"body": "delete me", "customer_email": "g@x.com"}, timeout=20)
        mid = r.json()["id"]
        d = requests.delete(f"{API}/messages/{mid}", headers=_h(tok), timeout=20)
        assert d.status_code == 200

        # Verify gone in seller list
        msgs = requests.get(f"{API}/messages/seller", headers=_h(tok), timeout=20).json()
        assert not any(m["id"] == mid for m in msgs)

    def test_delete_unknown_404(self, seller_ctx):
        tok, _ = seller_ctx
        r = requests.delete(f"{API}/messages/{uuid.uuid4().hex}", headers=_h(tok), timeout=20)
        assert r.status_code == 404
