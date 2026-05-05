"""
JubaSquare backend regression tests.
Covers: meta, auth (login/me/wrong pw/blocked), shops, products, restaurants,
orders (customer/seller/admin), admin shop verify/reject, block-email,
exchange rate, RBAC.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://juba-vendors.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@demo.com", "password": "1234"}
SELLER = {"email": "seller@demo.com", "password": "1234"}
CUSTOMER = {"email": "customer@demo.com", "password": "1234"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    return data["token"], data["user"]


@pytest.fixture(scope="session")
def admin_token():
    tok, _ = _login(ADMIN)
    return tok


@pytest.fixture(scope="session")
def seller_token_and_user():
    tok, user = _login(SELLER)
    return tok, user


@pytest.fixture(scope="session")
def customer_token():
    tok, _ = _login(CUSTOMER)
    return tok


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------------- META ----------------
class TestMeta:
    def test_health(self):
        r = requests.get(f"{API}/meta/health", timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_areas(self):
        r = requests.get(f"{API}/meta/areas", timeout=15)
        assert r.status_code == 200
        areas = r.json()
        assert isinstance(areas, list) and len(areas) >= 5
        assert "Munuki" in areas


# ---------------- AUTH ----------------
class TestAuth:
    def test_login_admin(self):
        r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "token" in d and d["user"]["role"] == "admin"
        assert "access_token" in r.cookies

    def test_login_seller(self):
        r = requests.post(f"{API}/auth/login", json=SELLER, timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "seller"

    def test_login_customer(self):
        r = requests.post(f"{API}/auth/login", json=CUSTOMER, timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "customer"

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": "admin@demo.com", "password": "wrong"}, timeout=15)
        assert r.status_code == 401

    def test_me_with_bearer(self, customer_token):
        r = requests.get(f"{API}/auth/me", headers=_h(customer_token), timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == "customer@demo.com"

    def test_me_unauthenticated(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401


# ---------------- PUBLIC LISTINGS ----------------
class TestListings:
    def test_shops_count_and_order(self):
        r = requests.get(f"{API}/shops", timeout=15)
        assert r.status_code == 200
        shops = r.json()
        assert len(shops) >= 5
        # verified before non-verified
        first_non_verified = next((i for i, s in enumerate(shops) if s.get("verification") != "Verified"), len(shops))
        first_verified_after = next((i for i, s in enumerate(shops[first_non_verified:], start=first_non_verified)
                                     if s.get("verification") == "Verified"), None)
        assert first_verified_after is None, "Verified shops must come first"

    def test_shops_filter_electronics(self):
        r = requests.get(f"{API}/shops", params={"category": "Electronics"}, timeout=15)
        assert r.status_code == 200
        for s in r.json():
            assert s["category"] == "Electronics"

    def test_products_count(self):
        r = requests.get(f"{API}/products", timeout=15)
        assert r.status_code == 200
        assert len(r.json()) >= 10

    def test_restaurants(self):
        r = requests.get(f"{API}/restaurants", timeout=15)
        assert r.status_code == 200
        rs = r.json()
        assert len(rs) >= 4
        assert any(x.get("is_open") is False for x in rs)

    def test_restaurant_menu(self):
        rs = requests.get(f"{API}/restaurants", timeout=15).json()
        rid = rs[0]["id"]
        r = requests.get(f"{API}/restaurants/{rid}/menu", timeout=15)
        assert r.status_code == 200
        assert len(r.json()) >= 2


# ---------------- CUSTOMER ORDERS ----------------
class TestCustomerOrders:
    def test_place_order_and_list_mine(self, customer_token):
        prods = requests.get(f"{API}/products", timeout=15).json()
        p = prods[0]
        payload = {
            "items": [{
                "item_type": "product", "item_id": p["id"], "name": p["name"],
                "price_usd": p["price_usd"], "quantity": 2, "image_url": p.get("image_url", ""),
            }],
            "area": "Munuki", "address": "Block 4", "phone": "+211900000000", "order_kind": "marketplace",
        }
        r = requests.post(f"{API}/orders", json=payload, headers=_h(customer_token), timeout=15)
        assert r.status_code == 200
        order = r.json()
        assert order["status"] == "Pending"
        assert order["subtotal_usd"] == round(p["price_usd"] * 2, 2)

        mine = requests.get(f"{API}/orders/mine", headers=_h(customer_token), timeout=15)
        assert mine.status_code == 200
        assert any(o["id"] == order["id"] for o in mine.json())


# ---------------- SELLER FLOW ----------------
class TestSellerFlow:
    def test_seller_shop_product_crud(self, seller_token_and_user):
        tok, _ = seller_token_and_user
        # create shop
        shop_payload = {"name": f"TEST_Shop_{uuid.uuid4().hex[:6]}", "category": "Electronics",
                        "description": "test", "image_url": "", "area": "Munuki"}
        r = requests.post(f"{API}/shops", json=shop_payload, headers=_h(tok), timeout=15)
        assert r.status_code == 200
        shop = r.json()
        assert shop["verification"] == "Pending"
        sid = shop["id"]

        # mine
        mine = requests.get(f"{API}/shops/mine", headers=_h(tok), timeout=15).json()
        assert any(s["id"] == sid for s in mine)

        # create product
        prod_payload = {"shop_id": sid, "name": "TEST_Prod", "category": "Electronics",
                        "price_usd": 10.0, "image_url": "", "description": "t", "stock": 5}
        r = requests.post(f"{API}/products", json=prod_payload, headers=_h(tok), timeout=15)
        assert r.status_code == 200
        pid = r.json()["id"]

        # update product
        prod_payload["price_usd"] = 12.5
        r = requests.put(f"{API}/products/{pid}", json=prod_payload, headers=_h(tok), timeout=15)
        assert r.status_code == 200 and r.json()["price_usd"] == 12.5

        # delete product
        r = requests.delete(f"{API}/products/{pid}", headers=_h(tok), timeout=15)
        assert r.status_code == 200

        # cleanup shop
        r = requests.delete(f"{API}/shops/{sid}", headers=_h(tok), timeout=15)
        assert r.status_code == 200

    def test_exchange_rate(self, seller_token_and_user):
        tok, user = seller_token_and_user
        r = requests.put(f"{API}/exchange-rate", json={"rate": 750}, headers=_h(tok), timeout=15)
        assert r.status_code == 200
        r = requests.get(f"{API}/exchange-rate", params={"seller_id": user["id"]}, timeout=15)
        assert r.status_code == 200 and r.json()["rate"] == 750
        # restore
        requests.put(f"{API}/exchange-rate", json={"rate": 600}, headers=_h(tok), timeout=15)

    def test_seller_orders_endpoint(self, seller_token_and_user):
        tok, _ = seller_token_and_user
        r = requests.get(f"{API}/orders/seller", headers=_h(tok), timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_seller_can_update_order_status(self, seller_token_and_user, customer_token):
        # create an order as customer first
        prods = requests.get(f"{API}/products", timeout=15).json()
        p = prods[0]
        payload = {
            "items": [{"item_type": "product", "item_id": p["id"], "name": p["name"],
                       "price_usd": p["price_usd"], "quantity": 1}],
            "area": "Munuki", "address": "x", "phone": "1", "order_kind": "marketplace",
        }
        order_id = requests.post(f"{API}/orders", json=payload, headers=_h(customer_token), timeout=15).json()["id"]
        tok, _ = seller_token_and_user
        r = requests.put(f"{API}/orders/{order_id}/status", json={"status": "In Progress"},
                         headers=_h(tok), timeout=15)
        assert r.status_code == 200 and r.json()["status"] == "In Progress"


# ---------------- ADMIN ----------------
class TestAdmin:
    def test_verify_and_reject_shop(self, admin_token, seller_token_and_user):
        tok, _ = seller_token_and_user
        sp = {"name": f"TEST_VShop_{uuid.uuid4().hex[:6]}", "category": "Fashion",
              "description": "", "image_url": "", "area": "Atlabara"}
        sid = requests.post(f"{API}/shops", json=sp, headers=_h(tok), timeout=15).json()["id"]

        r = requests.put(f"{API}/admin/shops/{sid}/verify", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200 and r.json()["verification"] == "Verified"
        r = requests.put(f"{API}/admin/shops/{sid}/reject", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200 and r.json()["verification"] == "Rejected"

        requests.delete(f"{API}/shops/{sid}", headers=_h(tok), timeout=15)

    def test_block_unblock_email(self, admin_token):
        email = f"block_{uuid.uuid4().hex[:6]}@test.com"
        # ensure clean
        requests.delete(f"{API}/admin/block-email/{email}", headers=_h(admin_token), timeout=15)
        r = requests.post(f"{API}/admin/block-email", json={"email": email}, headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
        # blocked email login should fail with 403 (no such user but blocked check is first)
        r2 = requests.post(f"{API}/auth/login", json={"email": email, "password": "x"}, timeout=15)
        assert r2.status_code == 403
        # unblock
        r = requests.delete(f"{API}/admin/block-email/{email}", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200

    def test_cannot_block_demo_account(self, admin_token):
        r = requests.post(f"{API}/admin/block-email", json={"email": "admin@demo.com"},
                          headers=_h(admin_token), timeout=15)
        assert r.status_code == 400

    def test_admin_orders_list(self, admin_token):
        r = requests.get(f"{API}/orders", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------- RBAC ----------------
class TestRBAC:
    def test_customer_blocked_from_admin(self, customer_token):
        r = requests.get(f"{API}/orders", headers=_h(customer_token), timeout=15)
        assert r.status_code == 403

    def test_customer_blocked_from_seller_orders(self, customer_token):
        r = requests.get(f"{API}/orders/seller", headers=_h(customer_token), timeout=15)
        assert r.status_code == 403

    def test_customer_blocked_from_admin_block_email(self, customer_token):
        r = requests.post(f"{API}/admin/block-email", json={"email": "x@y.com"},
                          headers=_h(customer_token), timeout=15)
        assert r.status_code == 403
