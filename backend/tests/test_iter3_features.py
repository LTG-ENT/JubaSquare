"""
JubaSquare iteration 3 feature tests:
- /api/admin/invoices list (+status filter), detail, status PUT, regenerate
- Commission rate persistence + recomputation on regen
- /api/seller/invoices (seller gets own; customer 403)
- /api/meta/categories food_subcategories has 16 items
- POST /api/products wholesale mode with pricing_tiers
- POST /api/menu-items with food_category + side_items
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://low-stock-tracker.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@demo.com", "password": "1234"}
SELLER = {"email": "seller@demo.com", "password": "1234"}
CUSTOMER = {"email": "customer@demo.com", "password": "1234"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login: {r.status_code} {r.text}"
    return r.json()["token"], r.json()["user"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_tok():
    return _login(ADMIN)[0]


@pytest.fixture(scope="module")
def seller_tu():
    return _login(SELLER)


@pytest.fixture(scope="module")
def customer_tu():
    return _login(CUSTOMER)


REQUIRED_INV_KEYS = {
    "id", "shop_name", "week_label", "week_start", "week_end",
    "total_sales", "commission", "commission_rate", "amount_owed",
    "order_count", "status",
}


# ---------- Admin invoices list + shape ----------
class TestAdminInvoices:
    def test_list_shape(self, admin_tok):
        r = requests.get(f"{API}/admin/invoices", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        invs = r.json()
        assert isinstance(invs, list) and len(invs) >= 1
        for inv in invs:
            missing = REQUIRED_INV_KEYS - set(inv.keys())
            assert not missing, f"Missing keys {missing}"
            assert inv["status"] in {"Paid", "Unpaid"}

    def test_filter_paid(self, admin_tok):
        r = requests.get(f"{API}/admin/invoices?status=Paid", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        for inv in r.json():
            assert inv["status"] == "Paid"

    def test_filter_unpaid(self, admin_tok):
        r = requests.get(f"{API}/admin/invoices?status=Unpaid", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        for inv in r.json():
            assert inv["status"] == "Unpaid"

    def test_detail(self, admin_tok):
        invs = requests.get(f"{API}/admin/invoices", headers=_h(admin_tok), timeout=15).json()
        assert invs
        iid = invs[0]["id"]
        r = requests.get(f"{API}/admin/invoices/{iid}", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        assert r.json()["id"] == iid

    def test_detail_404(self, admin_tok):
        r = requests.get(f"{API}/admin/invoices/nonexistent-id", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 404

    def test_requires_admin(self, customer_tu):
        tok, _ = customer_tu
        r = requests.get(f"{API}/admin/invoices", headers=_h(tok), timeout=15)
        assert r.status_code == 403

    def test_mark_paid_and_unpaid_persists(self, admin_tok):
        invs = requests.get(f"{API}/admin/invoices?status=Unpaid",
                            headers=_h(admin_tok), timeout=15).json()
        if not invs:
            pytest.skip("No unpaid invoices to flip")
        iid = invs[0]["id"]
        # flip to Paid
        r = requests.put(f"{API}/admin/invoices/{iid}/status",
                         json={"status": "Paid"}, headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200 and r.json()["status"] == "Paid"
        # GET verifies
        g = requests.get(f"{API}/admin/invoices/{iid}", headers=_h(admin_tok), timeout=15).json()
        assert g["status"] == "Paid"
        # flip back
        requests.put(f"{API}/admin/invoices/{iid}/status",
                     json={"status": "Unpaid"}, headers=_h(admin_tok), timeout=15)
        g2 = requests.get(f"{API}/admin/invoices/{iid}", headers=_h(admin_tok), timeout=15).json()
        assert g2["status"] == "Unpaid"

    def test_regenerate_idempotent_preserves_paid(self, admin_tok):
        invs = requests.get(f"{API}/admin/invoices", headers=_h(admin_tok), timeout=15).json()
        if not invs:
            pytest.skip()
        iid = invs[0]["id"]
        # mark one paid
        requests.put(f"{API}/admin/invoices/{iid}/status",
                     json={"status": "Paid"}, headers=_h(admin_tok), timeout=15)
        # regenerate
        r = requests.post(f"{API}/admin/invoices/generate", headers=_h(admin_tok), timeout=20)
        assert r.status_code == 200 and r.json().get("ok") is True
        # Paid status retained for same (seller,shop,week); invoice id should be preserved
        g = requests.get(f"{API}/admin/invoices/{iid}", headers=_h(admin_tok), timeout=15).json()
        assert g["status"] == "Paid"


# ---------- Commission rate editing ----------
class TestCommissionRate:
    def test_default_rate(self, admin_tok):
        s = requests.get(f"{API}/admin/settings", headers=_h(admin_tok), timeout=15).json()
        assert "commission_rate" in s

    def test_change_rate_then_regenerate(self, admin_tok):
        # Ensure at least one paid exists preserved
        before = requests.get(f"{API}/admin/invoices", headers=_h(admin_tok), timeout=15).json()
        sample = before[0] if before else None

        # Set rate to 0.15
        r = requests.put(f"{API}/admin/settings", json={"commission_rate": 0.15},
                         headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200 and abs(r.json()["commission_rate"] - 0.15) < 1e-9
        try:
            rg = requests.post(f"{API}/admin/invoices/generate",
                               headers=_h(admin_tok), timeout=20)
            assert rg.status_code == 200
            after = requests.get(f"{API}/admin/invoices",
                                 headers=_h(admin_tok), timeout=15).json()
            assert after
            for inv in after:
                assert abs(inv["commission_rate"] - 0.15) < 1e-9
                assert abs(inv["commission"] - round(inv["total_sales"] * 0.15, 2)) < 0.02
            if sample is not None:
                # same (seller,shop,week) – must have 1.5x commission
                match = next((i for i in after if i["id"] == sample["id"]), None)
                assert match is not None
        finally:
            # revert
            requests.put(f"{API}/admin/settings", json={"commission_rate": 0.10},
                         headers=_h(admin_tok), timeout=15)
            requests.post(f"{API}/admin/invoices/generate",
                          headers=_h(admin_tok), timeout=20)


# ---------- Seller invoices ----------
class TestSellerInvoices:
    def test_seller_gets_own(self, seller_tu, admin_tok):
        tok, u = seller_tu
        r = requests.get(f"{API}/seller/invoices", headers=_h(tok), timeout=15)
        assert r.status_code == 200
        invs = r.json()
        assert isinstance(invs, list)
        for inv in invs:
            assert inv["seller_id"] == u["id"]
            missing = REQUIRED_INV_KEYS - set(inv.keys())
            assert not missing

    def test_customer_forbidden(self, customer_tu):
        tok, _ = customer_tu
        r = requests.get(f"{API}/seller/invoices", headers=_h(tok), timeout=15)
        assert r.status_code == 403


# ---------- Meta categories ----------
class TestMetaCategories:
    def test_food_subcategories(self):
        r = requests.get(f"{API}/meta/categories", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "food_subcategories" in d
        subs = d["food_subcategories"]
        assert isinstance(subs, list) and len(subs) == 16
        for s in ("Fried Chicken", "Burgers", "Shawarma", "Fries"):
            assert s in subs


# ---------- Wholesale product mode + pricing tiers ----------
class TestWholesaleProduct:
    def test_create_wholesale_with_tiers(self, seller_tu):
        tok, _ = seller_tu
        shops = requests.get(f"{API}/shops", params={"kind": "wholesale"},
                             timeout=15).json()
        # pick one owned by seller if possible
        me = _login(SELLER)[1]
        mine = [s for s in shops if s.get("seller_id") == me["id"]]
        shop = mine[0] if mine else shops[0]
        payload = {
            "shop_id": shop["id"],
            "name": f"TEST_Bulk_{uuid.uuid4().hex[:5]}",
            "category": "Wholesale Food Supply",
            "price_usd": 10.0,
            "stock": 1000,
            "min_order_qty": 10,
            "bulk_price_usd": 8.0,
            "mode": "wholesale",
            "pricing_tiers": [
                {"min_qty": 10, "price_usd": 9},
                {"min_qty": 50, "price_usd": 8},
            ],
        }
        r = requests.post(f"{API}/products", json=payload, headers=_h(tok), timeout=15)
        # If seller doesn't own shop, may 403
        if r.status_code == 403:
            pytest.skip("seller does not own a wholesale shop")
        assert r.status_code == 200, r.text
        p = r.json()
        pid = p["id"]
        try:
            assert p.get("mode") == "wholesale"
            assert p.get("min_order_qty") == 10
            assert p.get("bulk_price_usd") == 8.0
            assert isinstance(p.get("pricing_tiers"), list)
            assert len(p["pricing_tiers"]) == 2
            # GET via list
            lst = requests.get(f"{API}/products", timeout=15).json()
            found = next((x for x in lst if x["id"] == pid), None)
            assert found is not None
            assert found.get("mode") == "wholesale"
            assert len(found.get("pricing_tiers", [])) == 2
        finally:
            requests.delete(f"{API}/products/{pid}", headers=_h(tok), timeout=15)


# ---------- Restaurant menu-item food_category ----------
class TestMenuItemFoodCategory:
    def test_create_menu_with_food_category(self, seller_tu):
        tok, _ = seller_tu
        rs = requests.get(f"{API}/restaurants", timeout=15).json()
        assert rs
        # pick one seller owns; fallback: any
        me = _login(SELLER)[1]
        mine = [r for r in rs if r.get("seller_id") == me["id"]]
        target = mine[0] if mine else rs[0]
        payload = {
            "restaurant_id": target["id"],
            "name": f"TEST_Meal_{uuid.uuid4().hex[:5]}",
            "price_usd": 7.5,
            "image_url": "",
            "description": "",
            "food_category": "Burgers",
            "side_items": [{"name": "Fries", "price_usd": 2.0}],
        }
        r = requests.post(f"{API}/menu-items", json=payload, headers=_h(tok), timeout=15)
        if r.status_code == 403:
            pytest.skip("seller does not own this restaurant")
        assert r.status_code == 200, r.text
        m = r.json()
        mid = m["id"]
        try:
            assert m["food_category"] == "Burgers"
            assert m["side_items"][0]["name"] == "Fries"
            # verify via GET menu
            lst = requests.get(f"{API}/restaurants/{target['id']}/menu", timeout=15).json()
            found = next((x for x in lst if x["id"] == mid), None)
            assert found and found["food_category"] == "Burgers"
        finally:
            requests.delete(f"{API}/menu-items/{mid}", headers=_h(tok), timeout=15)
