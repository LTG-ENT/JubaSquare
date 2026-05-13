"""
Iter10 — Test the new endpoints + regressions for this iteration:
  * GET  /api/admin/alerts                                       (new)
  * GET  /api/driver/cash-summary                                (new)
  * GET/POST/PUT/DELETE /api/admin/delivery-pricing-rules        (moved out of dead code)
  * GET/POST /api/admin/delivery-pricing-rules/default-fee
  * GET  /api/admin/cash-handovers + /api/admin/payouts          (regression)
  * POST /api/customer/orders/{id}/cancel +
    POST /api/customer/restaurant-orders/{id}/cancel             (regression)
"""
import os
import uuid
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or "https://wallet-auto-refresh.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@LTG.com", "password": "Kokobleake1"}
DRIVER = {"email": "driver@demo.com", "password": "1234"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    d = r.json()
    return d["token"], d["user"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_h():
    tok, _ = _login(ADMIN)
    return _h(tok)


@pytest.fixture(scope="module")
def driver_h():
    tok, _ = _login(DRIVER)
    return _h(tok)


# ---------------------- Admin Alerts ----------------------
class TestAdminAlerts:
    def test_alerts_schema(self, admin_h):
        r = requests.get(f"{API}/admin/alerts", headers=admin_h, timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        for k in ("orders_needing_driver", "cash_pending", "payouts_ready",
                  "disputes_open", "cancellations_open"):
            assert k in data, f"missing key {k} in alerts payload"
            assert isinstance(data[k], int), f"{k} should be int, got {type(data[k])}"
            assert data[k] >= 0


# ---------------------- Driver Cash Summary ----------------------
class TestDriverCashSummary:
    def test_cash_summary_schema(self, driver_h):
        r = requests.get(f"{API}/driver/cash-summary", headers=driver_h, timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        for k in ("pending_total_usd", "pending_count", "received_today_count", "items"):
            assert k in data, f"missing key {k}"
        assert isinstance(data["items"], list)
        assert isinstance(data["pending_total_usd"], (int, float))
        assert isinstance(data["pending_count"], int)
        assert isinstance(data["received_today_count"], int)
        # If items exist, each should have an order_total_usd
        for it in data["items"]:
            assert "kind" in it
            assert it["kind"] in ("marketplace", "restaurant")

    def test_cash_summary_requires_driver_auth(self, admin_h):
        r = requests.get(f"{API}/driver/cash-summary", headers=admin_h, timeout=20)
        # Admin is not a driver; expect 401/403
        assert r.status_code in (401, 403), f"got {r.status_code} {r.text}"


# ---------------------- Delivery Pricing Rules CRUD ----------------------
class TestDeliveryPricingRulesCRUD:
    def test_list_then_create_update_delete(self, admin_h):
        # LIST
        r0 = requests.get(f"{API}/admin/delivery-pricing-rules", headers=admin_h, timeout=20)
        assert r0.status_code == 200, f"{r0.status_code} {r0.text}"
        initial = r0.json()
        assert isinstance(initial, list)

        # CREATE
        body = {
            "pickup_area": f"TEST_PU_{uuid.uuid4().hex[:6]}",
            "delivery_area": f"TEST_DL_{uuid.uuid4().hex[:6]}",
            "order_type": "marketplace",
            "shop_id": None,
            "restaurant_id": None,
            "delivery_fee_usd": 4.25,
            "active": True,
        }
        r1 = requests.post(f"{API}/admin/delivery-pricing-rules", headers=admin_h,
                           json=body, timeout=20)
        assert r1.status_code in (200, 201), f"{r1.status_code} {r1.text}"
        rule = r1.json()
        assert rule["pickup_area"] == body["pickup_area"]
        assert rule["delivery_fee_usd"] == body["delivery_fee_usd"]
        assert "id" in rule
        rid = rule["id"]

        # Verify in LIST
        r1b = requests.get(f"{API}/admin/delivery-pricing-rules", headers=admin_h, timeout=20)
        assert r1b.status_code == 200
        ids = [x["id"] for x in r1b.json()]
        assert rid in ids

        # UPDATE
        body2 = {**body, "delivery_fee_usd": 6.75, "active": False}
        r2 = requests.put(f"{API}/admin/delivery-pricing-rules/{rid}", headers=admin_h,
                          json=body2, timeout=20)
        assert r2.status_code == 200, f"{r2.status_code} {r2.text}"
        updated = r2.json()
        assert updated["delivery_fee_usd"] == 6.75
        assert updated["active"] is False

        # DELETE
        r3 = requests.delete(f"{API}/admin/delivery-pricing-rules/{rid}",
                             headers=admin_h, timeout=20)
        assert r3.status_code == 200, f"{r3.status_code} {r3.text}"
        # Verify gone
        r4 = requests.get(f"{API}/admin/delivery-pricing-rules", headers=admin_h, timeout=20)
        ids2 = [x["id"] for x in r4.json()]
        assert rid not in ids2


class TestDefaultDeliveryFee:
    def test_get_then_set(self, admin_h):
        r0 = requests.get(f"{API}/admin/delivery-pricing-rules/default-fee",
                          headers=admin_h, timeout=20)
        assert r0.status_code == 200, f"{r0.status_code} {r0.text}"
        d0 = r0.json()
        assert "default_delivery_fee_usd" in d0
        original = float(d0["default_delivery_fee_usd"])

        # SET to 3.5
        r1 = requests.post(f"{API}/admin/delivery-pricing-rules/default-fee",
                           headers=admin_h, json={"default_delivery_fee_usd": 3.5},
                           timeout=20)
        assert r1.status_code == 200, f"{r1.status_code} {r1.text}"
        assert float(r1.json()["default_delivery_fee_usd"]) == 3.5

        # Confirm round-trip
        r2 = requests.get(f"{API}/admin/delivery-pricing-rules/default-fee",
                          headers=admin_h, timeout=20)
        assert float(r2.json()["default_delivery_fee_usd"]) == 3.5

        # Restore
        requests.post(f"{API}/admin/delivery-pricing-rules/default-fee",
                      headers=admin_h, json={"default_delivery_fee_usd": original},
                      timeout=20)


# ---------------------- Regression: cash-handovers + payouts ----------------------
class TestRegressionCashAndPayouts:
    def test_cash_handovers_listing(self, admin_h):
        r = requests.get(f"{API}/admin/cash-handovers", headers=admin_h, timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        # Returns dict or list — just sanity check it parses and has stable shape
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_payouts_listing(self, admin_h):
        r = requests.get(f"{API}/admin/payouts", headers=admin_h, timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert isinstance(data, (list, dict))


# ---------------------- Regression: customer cancel endpoints exist ----------------------
class TestRegressionCustomerCancelRoutes:
    """We don't need to drive a full order; we just want to confirm the routes are
    wired in (i.e. NOT 404) and require auth (i.e. NOT 500)."""

    def test_marketplace_cancel_route_registered(self):
        fake = uuid.uuid4().hex
        r = requests.post(f"{API}/customer/orders/{fake}/cancel", timeout=20)
        # Unauthenticated: must be 401/403, NOT 404 (route exists)
        assert r.status_code in (401, 403, 422), f"unexpected: {r.status_code} {r.text}"

    def test_restaurant_cancel_route_registered(self):
        fake = uuid.uuid4().hex
        r = requests.post(f"{API}/customer/restaurant-orders/{fake}/cancel", timeout=20)
        assert r.status_code in (401, 403, 422), f"unexpected: {r.status_code} {r.text}"
