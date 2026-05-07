"""
JubaSquare iteration 2 feature tests:
- /api/settings/public, /api/admin/settings (RBAC + persistence + auto_approve_shops)
- /api/admin/areas add/remove
- /api/admin/force-logout-all (token_version invalidation)
- /api/seller/settings (auto-hide out of stock)
- /api/customer/settings persistence
- /api/favorites GET/POST/DELETE + duplicate
- shops?kind=retail/wholesale counts
- products?kind=wholesale with bulk_price_usd & min_order_qty
- order validation (phone/area/empty items) + sides subtotal
- maintenance_mode blocks customer 503
"""
import os
import uuid
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://admin-categories-4.preview.emergentagent.com").rstrip("/")
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


# ---------- public settings ----------
class TestPublicSettings:
    def test_public_settings_shape(self):
        r = requests.get(f"{API}/settings/public", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("global_rate", "module_marketplace", "module_wholesale",
                  "module_restaurants", "maintenance_mode", "areas"):
            assert k in d
        assert isinstance(d["areas"], list)


# ---------- admin settings RBAC + persistence ----------
class TestAdminSettings:
    def test_admin_settings_requires_admin(self, customer_tu):
        tok, _ = customer_tu
        r = requests.get(f"{API}/admin/settings", headers=_h(tok), timeout=15)
        assert r.status_code == 403

    def test_admin_settings_full(self, admin_tok):
        r = requests.get(f"{API}/admin/settings", headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "login_attempt_limit" in d and "token_version" in d

    def test_auto_approve_shops_persistence(self, admin_tok, seller_tu):
        r = requests.put(f"{API}/admin/settings", json={"auto_approve_shops": True},
                         headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200 and r.json()["auto_approve_shops"] is True
        s_tok, _ = seller_tu
        sp = {"name": f"TEST_Auto_{uuid.uuid4().hex[:6]}", "category": "Electronics",
              "description": "", "image_url": "", "area": "Munuki"}
        sr = requests.post(f"{API}/shops", json=sp, headers=_h(s_tok), timeout=15)
        assert sr.status_code == 200
        shop = sr.json()
        try:
            assert shop["verification"] == "Verified"
        finally:
            requests.delete(f"{API}/shops/{shop['id']}", headers=_h(s_tok), timeout=15)
            requests.put(f"{API}/admin/settings", json={"auto_approve_shops": False},
                         headers=_h(admin_tok), timeout=15)


# ---------- admin areas ----------
class TestAdminAreas:
    def test_add_remove_area(self, admin_tok):
        name = f"TEST_Area_{uuid.uuid4().hex[:4]}"
        r = requests.post(f"{API}/admin/areas", json={"area": name},
                          headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200 and name in r.json()["areas"]
        r2 = requests.delete(f"{API}/admin/areas/{name}", headers=_h(admin_tok), timeout=15)
        assert r2.status_code == 200 and name not in r2.json()["areas"]


# ---------- seller settings + auto-hide out-of-stock ----------
class TestSellerSettings:
    def test_settings_persist(self, seller_tu):
        tok, _ = seller_tu
        r = requests.put(f"{API}/seller/settings",
                         json={"low_stock_alert": True, "auto_hide_out_of_stock": False},
                         headers=_h(tok), timeout=15)
        assert r.status_code == 200
        s = r.json().get("settings", {})
        assert s.get("low_stock_alert") is True
        assert s.get("auto_hide_out_of_stock") is False

    def test_auto_hide_out_of_stock(self, seller_tu):
        tok, _ = seller_tu
        # enable auto-hide
        requests.put(f"{API}/seller/settings", json={"auto_hide_out_of_stock": True},
                     headers=_h(tok), timeout=15)
        prods = requests.get(f"{API}/products", timeout=15).json()
        # pick one seller-owned retail product
        target = next((p for p in prods if p["shop_kind"] == "retail"), None)
        assert target is not None
        original_stock = target.get("stock", 100)
        upd = {"shop_id": target["shop_id"], "name": target["name"],
               "category": target["category"], "price_usd": target["price_usd"],
               "image_url": target.get("image_url", ""), "description": target.get("description", ""),
               "stock": 0, "min_order_qty": target.get("min_order_qty", 1),
               "bulk_price_usd": target.get("bulk_price_usd")}
        r = requests.put(f"{API}/products/{target['id']}", json=upd, headers=_h(tok), timeout=15)
        assert r.status_code == 200
        try:
            after = requests.get(f"{API}/products", timeout=15).json()
            assert not any(p["id"] == target["id"] for p in after), "stock=0 product should be hidden"
        finally:
            upd["stock"] = original_stock
            requests.put(f"{API}/products/{target['id']}", json=upd, headers=_h(tok), timeout=15)
            requests.put(f"{API}/seller/settings", json={"auto_hide_out_of_stock": False},
                         headers=_h(tok), timeout=15)


# ---------- customer settings ----------
class TestCustomerSettings:
    def test_persist(self, customer_tu):
        tok, _ = customer_tu
        r = requests.put(f"{API}/customer/settings",
                         json={"default_area": "Jebel", "dark_mode": True},
                         headers=_h(tok), timeout=15)
        assert r.status_code == 200
        s = r.json().get("settings", {})
        assert s.get("default_area") == "Jebel" and s.get("dark_mode") is True


# ---------- favorites ----------
class TestFavorites:
    def test_add_list_dup_remove(self, customer_tu):
        tok, _ = customer_tu
        prods = requests.get(f"{API}/products", timeout=15).json()
        pid = prods[0]["id"]
        # ensure clean
        requests.delete(f"{API}/favorites", params={"target_type": "product", "target_id": pid},
                        headers=_h(tok), timeout=15)
        r1 = requests.post(f"{API}/favorites",
                           json={"target_type": "product", "target_id": pid},
                           headers=_h(tok), timeout=15)
        assert r1.status_code == 200 and r1.json().get("ok") is True
        assert not r1.json().get("already")
        r2 = requests.post(f"{API}/favorites",
                           json={"target_type": "product", "target_id": pid},
                           headers=_h(tok), timeout=15)
        assert r2.json().get("already") is True
        rl = requests.get(f"{API}/favorites", headers=_h(tok), timeout=15)
        assert rl.status_code == 200
        assert any(f["target_id"] == pid for f in rl.json())
        rd = requests.delete(f"{API}/favorites",
                             params={"target_type": "product", "target_id": pid},
                             headers=_h(tok), timeout=15)
        assert rd.status_code == 200


# ---------- shops/products kind ----------
class TestKindFilters:
    def test_retail_count(self):
        r = requests.get(f"{API}/shops", params={"kind": "retail"}, timeout=15)
        assert r.status_code == 200
        assert len(r.json()) == 9

    def test_wholesale_count(self):
        r = requests.get(f"{API}/shops", params={"kind": "wholesale"}, timeout=15)
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_wholesale_products(self):
        r = requests.get(f"{API}/products", params={"kind": "wholesale"}, timeout=15)
        assert r.status_code == 200
        prods = r.json()
        assert len(prods) == 6
        for p in prods:
            assert "min_order_qty" in p
            assert "bulk_price_usd" in p


# ---------- order validation ----------
class TestOrderValidation:
    def _payload(self, items=None, phone="+211900", area="Munuki"):
        return {"items": items if items is not None else [
            {"item_type": "product", "item_id": "x", "name": "X",
             "price_usd": 1.0, "quantity": 1}],
                "area": area, "address": "a", "phone": phone, "order_kind": "marketplace"}

    def test_missing_phone(self, customer_tu):
        tok, _ = customer_tu
        r = requests.post(f"{API}/orders", json=self._payload(phone=""),
                          headers=_h(tok), timeout=15)
        assert r.status_code == 400
        assert "Phone" in r.json().get("detail", "")

    def test_missing_area(self, customer_tu):
        tok, _ = customer_tu
        r = requests.post(f"{API}/orders", json=self._payload(area=""),
                          headers=_h(tok), timeout=15)
        assert r.status_code == 400
        assert "area" in r.json().get("detail", "").lower()

    def test_empty_items(self, customer_tu):
        tok, _ = customer_tu
        r = requests.post(f"{API}/orders", json=self._payload(items=[]),
                          headers=_h(tok), timeout=15)
        assert r.status_code == 400
        assert "Cart" in r.json().get("detail", "")

    def test_order_with_sides_subtotal(self, customer_tu):
        tok, _ = customer_tu
        rs = requests.get(f"{API}/restaurants", timeout=15).json()
        rid = rs[0]["id"]
        menu = requests.get(f"{API}/restaurants/{rid}/menu", timeout=15).json()
        m = menu[0]
        payload = {"items": [{
            "item_type": "menu_item", "item_id": m["id"], "name": m["name"],
            "price_usd": m["price_usd"], "quantity": 2,
            "sides": [{"name": "Fries", "price_usd": 2.0}]}],
            "area": "Munuki", "address": "x", "phone": "1", "order_kind": "restaurant"}
        r = requests.post(f"{API}/orders", json=payload, headers=_h(tok), timeout=15)
        assert r.status_code == 200
        order = r.json()
        # 2 * (price + 2.0)
        expected = round((m["price_usd"] + 2.0) * 2, 2)
        assert order["subtotal_usd"] == expected
        assert order["items"][0]["sides"][0]["name"] == "Fries"


# ---------- maintenance mode ----------
class TestMaintenance:
    def test_maintenance_blocks_customer(self, admin_tok, customer_tu):
        requests.put(f"{API}/admin/settings", json={"maintenance_mode": True},
                     headers=_h(admin_tok), timeout=15)
        try:
            tok, _ = customer_tu
            prods = requests.get(f"{API}/products", timeout=15).json()
            p = prods[0]
            payload = {"items": [{"item_type": "product", "item_id": p["id"],
                                  "name": p["name"], "price_usd": p["price_usd"], "quantity": 1}],
                       "area": "Munuki", "address": "x", "phone": "1", "order_kind": "marketplace"}
            r = requests.post(f"{API}/orders", json=payload, headers=_h(tok), timeout=15)
            assert r.status_code == 503
            # admin can still place
            ar = requests.post(f"{API}/orders", json=payload, headers=_h(admin_tok), timeout=15)
            assert ar.status_code == 200
        finally:
            requests.put(f"{API}/admin/settings", json={"maintenance_mode": False},
                         headers=_h(admin_tok), timeout=15)


# ---------- force logout invalidates old tokens (LAST) ----------
class TestZForceLogout:
    def test_force_logout_invalidates_old_tokens(self):
        old_tok, _ = _login(SELLER)
        r0 = requests.get(f"{API}/auth/me", headers=_h(old_tok), timeout=15)
        assert r0.status_code == 200
        admin_tok, _ = _login(ADMIN)
        r1 = requests.post(f"{API}/admin/force-logout-all", headers=_h(admin_tok), timeout=15)
        assert r1.status_code == 200
        r2 = requests.get(f"{API}/auth/me", headers=_h(old_tok), timeout=15)
        assert r2.status_code == 401
        assert "invalidated" in r2.json().get("detail", "").lower()
