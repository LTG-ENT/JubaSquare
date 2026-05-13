"""
JubaSquare iteration 4 feature tests:
- Unified products list with is_wholesale filter (24 = 18 retail + 6 wholesale)
- ProductIn accepts is_wholesale + persists (default false)
- PUT /api/admin/shops/{id}/commission set/clear/out-of-bounds; per-shop rate applied
  to invoices on regenerate while other shops use global; clearing reverts to global
- ShopIn no longer requires category (minimal body succeeds)
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://wallet-auto-refresh.preview.emergentagent.com").rstrip("/")
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


# ---------- Unified product list with is_wholesale filter ----------
class TestProductsUnifiedListing:
    def test_no_filter_returns_all(self):
        r = requests.get(f"{API}/products", timeout=15)
        assert r.status_code == 200
        prods = r.json()
        assert isinstance(prods, list)
        # seed has 24 products (18 retail + 6 wholesale)
        retail = [p for p in prods if not p.get("is_wholesale")]
        ws = [p for p in prods if p.get("is_wholesale")]
        assert len(prods) >= 24, f"expected ≥24 products, got {len(prods)}"
        assert len(retail) >= 18, f"retail count: {len(retail)}"
        assert len(ws) >= 6, f"wholesale count: {len(ws)}"

    def test_filter_wholesale_true(self):
        r = requests.get(f"{API}/products", params={"is_wholesale": "true"}, timeout=15)
        assert r.status_code == 200
        prods = r.json()
        assert len(prods) >= 6
        for p in prods:
            assert p.get("is_wholesale") is True, f"non-wholesale leaked: {p.get('name')}"

    def test_filter_wholesale_false(self):
        r = requests.get(f"{API}/products", params={"is_wholesale": "false"}, timeout=15)
        assert r.status_code == 200
        prods = r.json()
        assert len(prods) >= 18
        for p in prods:
            assert p.get("is_wholesale") is False, f"wholesale leaked: {p.get('name')}"


# ---------- ProductIn is_wholesale flag persists ----------
class TestProductWholesaleFlag:
    def test_create_wholesale_true(self, seller_tu):
        tok, me = seller_tu
        shops = requests.get(f"{API}/shops", timeout=15).json()
        mine = [s for s in shops if s.get("seller_id") == me["id"]]
        assert mine, "seller must own at least one shop"
        shop = mine[0]
        payload = {
            "shop_id": shop["id"],
            "name": f"TEST_WS_{uuid.uuid4().hex[:5]}",
            "category": "Groceries",
            "price_usd": 5.0,
            "is_wholesale": True,
            "min_order_qty": 10,
            "bulk_price_usd": 4.0,
            "pricing_tiers": [{"min_qty": 10, "price_usd": 4}],
        }
        r = requests.post(f"{API}/products", json=payload, headers=_h(tok), timeout=15)
        assert r.status_code == 200, r.text
        p = r.json()
        pid = p["id"]
        try:
            assert p.get("is_wholesale") is True
            assert p.get("min_order_qty") == 10
            assert p.get("bulk_price_usd") == 4.0
            # GET round-trip via filter
            lst = requests.get(f"{API}/products", params={"is_wholesale": "true"}, timeout=15).json()
            assert any(x["id"] == pid for x in lst)
        finally:
            requests.delete(f"{API}/products/{pid}", headers=_h(tok), timeout=15)

    def test_create_default_retail(self, seller_tu):
        tok, me = seller_tu
        shops = requests.get(f"{API}/shops", timeout=15).json()
        mine = [s for s in shops if s.get("seller_id") == me["id"]]
        shop = mine[0]
        payload = {
            "shop_id": shop["id"],
            "name": f"TEST_RT_{uuid.uuid4().hex[:5]}",
            "category": "Groceries",
            "price_usd": 3.0,
        }
        r = requests.post(f"{API}/products", json=payload, headers=_h(tok), timeout=15)
        assert r.status_code == 200, r.text
        p = r.json()
        pid = p["id"]
        try:
            assert p.get("is_wholesale") is False
            lst = requests.get(f"{API}/products", params={"is_wholesale": "false"}, timeout=15).json()
            assert any(x["id"] == pid for x in lst)
        finally:
            requests.delete(f"{API}/products/{pid}", headers=_h(tok), timeout=15)


# ---------- ShopIn minimal (no category) accepted ----------
class TestShopInMinimal:
    def test_create_shop_no_category(self, seller_tu):
        tok, _ = seller_tu
        body = {
            "name": f"TEST_Shop_{uuid.uuid4().hex[:5]}",
            "area": "Munuki",
            "description": "minimal",
            "image_url": "",
        }
        r = requests.post(f"{API}/shops", json=body, headers=_h(tok), timeout=15)
        assert r.status_code == 200, r.text
        s = r.json()
        sid = s["id"]
        try:
            assert s["name"] == body["name"]
            # GET back
            g = requests.get(f"{API}/shops/{sid}", timeout=15)
            assert g.status_code == 200
        finally:
            requests.delete(f"{API}/shops/{sid}", headers=_h(tok), timeout=15)


# ---------- Per-shop commission ----------
class TestShopCommission:
    def test_set_clear_out_of_bounds(self, admin_tok):
        shops = requests.get(f"{API}/shops", timeout=15).json()
        assert shops
        sid = shops[0]["id"]
        try:
            # Set 0.15
            r = requests.put(f"{API}/admin/shops/{sid}/commission",
                             json={"commission_rate": 0.15}, headers=_h(admin_tok), timeout=15)
            assert r.status_code == 200, r.text
            assert abs(r.json().get("commission_rate", 0) - 0.15) < 1e-9
            # GET via /shops returns the rate
            g = requests.get(f"{API}/shops/{sid}", timeout=15).json()
            assert abs(g.get("commission_rate", 0) - 0.15) < 1e-9

            # Clear via null
            r2 = requests.put(f"{API}/admin/shops/{sid}/commission",
                              json={"commission_rate": None}, headers=_h(admin_tok), timeout=15)
            assert r2.status_code == 200
            g2 = requests.get(f"{API}/shops/{sid}", timeout=15).json()
            assert g2.get("commission_rate") in (None,) or "commission_rate" not in g2

            # Out of bounds
            r3 = requests.put(f"{API}/admin/shops/{sid}/commission",
                              json={"commission_rate": 1.5}, headers=_h(admin_tok), timeout=15)
            assert r3.status_code == 400
        finally:
            requests.put(f"{API}/admin/shops/{sid}/commission",
                         json={"commission_rate": None}, headers=_h(admin_tok), timeout=15)

    def test_per_shop_rate_applied_to_invoices(self, admin_tok):
        # Find a shop that has invoices
        invs = requests.get(f"{API}/admin/invoices", headers=_h(admin_tok), timeout=15).json()
        if not invs:
            pytest.skip("no invoices to test against")
        target_shop_id = invs[0].get("shop_id")
        assert target_shop_id, f"invoice missing shop_id: {invs[0]}"

        # Snapshot global rate
        settings = requests.get(f"{API}/admin/settings", headers=_h(admin_tok), timeout=15).json()
        global_rate = float(settings.get("commission_rate", 0.10))

        try:
            # Set per-shop rate to 0.20
            r = requests.put(f"{API}/admin/shops/{target_shop_id}/commission",
                             json={"commission_rate": 0.20}, headers=_h(admin_tok), timeout=15)
            assert r.status_code == 200
            # Regenerate invoices
            rg = requests.post(f"{API}/admin/invoices/generate",
                               headers=_h(admin_tok), timeout=20)
            assert rg.status_code == 200
            after = requests.get(f"{API}/admin/invoices", headers=_h(admin_tok), timeout=15).json()
            target_invs = [i for i in after if i.get("shop_id") == target_shop_id]
            other_invs = [i for i in after if i.get("shop_id") != target_shop_id]
            assert target_invs, "no invoices for target shop after regen"
            for inv in target_invs:
                assert abs(inv["commission_rate"] - 0.20) < 1e-9, \
                    f"target shop rate not 0.20 -> {inv['commission_rate']}"
            for inv in other_invs:
                assert abs(inv["commission_rate"] - global_rate) < 1e-9, \
                    f"other shop drifted: {inv['commission_rate']} != {global_rate}"

            # Clear and regen -> all back to global
            requests.put(f"{API}/admin/shops/{target_shop_id}/commission",
                         json={"commission_rate": None}, headers=_h(admin_tok), timeout=15)
            requests.post(f"{API}/admin/invoices/generate",
                          headers=_h(admin_tok), timeout=20)
            final = requests.get(f"{API}/admin/invoices", headers=_h(admin_tok), timeout=15).json()
            for inv in final:
                assert abs(inv["commission_rate"] - global_rate) < 1e-9, \
                    f"clear-then-regen: shop {inv['shop_id']} rate={inv['commission_rate']}"
        finally:
            requests.put(f"{API}/admin/shops/{target_shop_id}/commission",
                         json={"commission_rate": None}, headers=_h(admin_tok), timeout=15)
            requests.post(f"{API}/admin/invoices/generate",
                          headers=_h(admin_tok), timeout=20)
