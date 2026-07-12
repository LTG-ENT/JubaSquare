"""Iter 35 — Paginated seller dashboard endpoints tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://jubasquare-odoo-v2.preview.emergentagent.com").rstrip("/")

SELLER_EMAIL = "seller-attrtest@jubasquare.com"
SELLER_PW = "Test1234!"
ADMIN_EMAIL = "admin@jubasquare.com"
ADMIN_PW = "1234"


@pytest.fixture(scope="module")
def seller_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": SELLER_EMAIL, "password": SELLER_PW}, timeout=20)
    assert r.status_code == 200, f"Seller login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"No token in response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def seller_headers(seller_token):
    return {"Authorization": f"Bearer {seller_token}"}


@pytest.fixture(scope="module")
def anon_headers():
    return {}


# ------- Envelope shape tests -------

def _assert_paged_envelope(data, extra_keys=()):
    for k in ("items", "total", "page", "page_size"):
        assert k in data, f"Missing key {k} in envelope"
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)
    for k in extra_keys:
        assert k in data, f"Missing extra key {k}"


class TestProductsPaged:
    def test_default(self, seller_headers):
        r = requests.get(f"{BASE_URL}/api/seller/products/paged", headers=seller_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        _assert_paged_envelope(d)
        assert d["page"] == 1
        assert d["page_size"] == 50
        # This seller has 2 products
        assert d["total"] >= 0
        if d["items"]:
            it = d["items"][0]
            assert "shop_name" in it
            assert "shop_kind" in it

    def test_page_size_clamp(self, seller_headers):
        r = requests.get(f"{BASE_URL}/api/seller/products/paged?page_size=500", headers=seller_headers, timeout=20)
        # FastAPI Query(le=200) will 422 if user requests >200
        assert r.status_code in (200, 422)
        if r.status_code == 200:
            assert r.json()["page_size"] <= 200

    def test_search_filter(self, seller_headers):
        r = requests.get(f"{BASE_URL}/api/seller/products/paged?q=Galaxy", headers=seller_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        _assert_paged_envelope(d)

    def test_stock_out(self, seller_headers):
        r = requests.get(f"{BASE_URL}/api/seller/products/paged?stock=out", headers=seller_headers, timeout=20)
        assert r.status_code == 200
        for it in r.json()["items"]:
            assert (it.get("stock") or 0) <= 0

    def test_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/seller/products/paged", timeout=20)
        assert r.status_code in (401, 403)


class TestMenuItemsPaged:
    def test_default(self, seller_headers):
        r = requests.get(f"{BASE_URL}/api/seller/menu-items/paged", headers=seller_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        _assert_paged_envelope(d)
        if d["items"]:
            assert "restaurant_name" in d["items"][0]

    def test_search(self, seller_headers):
        r = requests.get(f"{BASE_URL}/api/seller/menu-items/paged?q=Peri", headers=seller_headers, timeout=20)
        assert r.status_code == 200


class TestOrdersPaged:
    def test_default(self, seller_headers):
        r = requests.get(f"{BASE_URL}/api/seller/orders/paged", headers=seller_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        _assert_paged_envelope(d, extra_keys=("stock_map",))
        assert isinstance(d["stock_map"], dict)


class TestNotificationsPaged:
    def test_default(self, seller_headers):
        r = requests.get(f"{BASE_URL}/api/notifications/paged", headers=seller_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        _assert_paged_envelope(d, extra_keys=("unread_count",))
        assert isinstance(d["unread_count"], int)


class TestMessagesPaged:
    def test_default(self, seller_headers):
        r = requests.get(f"{BASE_URL}/api/messages/seller/paged", headers=seller_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        _assert_paged_envelope(d, extra_keys=("unread_count",))


class TestInvoicesPaged:
    def test_shop_invoices(self, seller_headers):
        r = requests.get(f"{BASE_URL}/api/seller/invoices/paged", headers=seller_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        _assert_paged_envelope(d, extra_keys=("stats",))
        s = d["stats"]
        for k in ("total_sales", "total_commission", "amount_owed"):
            assert k in s

    def test_restaurant_invoices(self, seller_headers):
        r = requests.get(f"{BASE_URL}/api/seller/restaurant-invoices/paged", headers=seller_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        _assert_paged_envelope(d, extra_keys=("stats",))


class TestRoleEnforcement:
    def test_products_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/seller/products/paged", timeout=20)
        assert r.status_code in (401, 403)

    def test_menu_items_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/seller/menu-items/paged", timeout=20)
        assert r.status_code in (401, 403)

    def test_orders_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/seller/orders/paged", timeout=20)
        assert r.status_code in (401, 403)

    def test_invoices_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/seller/invoices/paged", timeout=20)
        assert r.status_code in (401, 403)

    def test_messages_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/messages/seller/paged", timeout=20)
        assert r.status_code in (401, 403)
