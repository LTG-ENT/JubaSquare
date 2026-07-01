"""Tests for Seller Onboarding Guide endpoints (iteration 13)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://jubasquare-odoo-v2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@jubasquare.com"
ADMIN_PASSWORD = "1234"


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Try /api/auth/login (standard JubaSquare auth)
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in login response: {data}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module", autouse=True)
def reset_progress(admin_client):
    """Reset admin onboarding_progress state before running tests by un-checking known manual steps."""
    for sid in ("orders", "payout", "analytics", "reviews"):
        admin_client.post(f"{BASE_URL}/api/seller/onboarding/uncheck-step", json={"step_id": sid})
    yield


class TestOnboardingProgress:
    def test_get_progress_returns_9_steps(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/seller/onboarding/progress")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "steps" in data and isinstance(data["steps"], list)
        assert len(data["steps"]) == 9
        ids = [s["id"] for s in data["steps"]]
        expected = {"profile", "shop", "product", "delivery", "payout", "orders", "analytics", "bulk", "reviews"}
        assert set(ids) == expected
        # keys present
        for f in ("completed_count", "total_count", "percent", "wizard_dismissed", "tour_completed", "badge_earned"):
            assert f in data
        assert data["total_count"] == 9

    def test_auto_flags(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/seller/onboarding/progress")
        data = r.json()
        by_id = {s["id"]: s for s in data["steps"]}
        assert by_id["profile"]["auto"] is True
        assert by_id["shop"]["auto"] is True
        assert by_id["product"]["auto"] is True
        assert by_id["delivery"]["auto"] is True
        assert by_id["bulk"]["auto"] is True
        assert by_id["payout"]["auto"] is False
        assert by_id["orders"]["auto"] is False
        assert by_id["analytics"]["auto"] is False
        assert by_id["reviews"]["auto"] is False


class TestCompleteUncheckStep:
    def test_complete_orders_increases_percent(self, admin_client):
        # baseline
        r0 = admin_client.get(f"{BASE_URL}/api/seller/onboarding/progress")
        p0 = r0.json()
        base_percent = p0["percent"]

        # complete orders
        r = admin_client.post(f"{BASE_URL}/api/seller/onboarding/complete-step", json={"step_id": "orders"})
        assert r.status_code == 200, r.text
        p1 = r.json()
        orders_step = next(s for s in p1["steps"] if s["id"] == "orders")
        assert orders_step["done"] is True
        assert p1["percent"] > base_percent

    def test_uncheck_orders_reverts(self, admin_client):
        # ensure orders is completed first
        admin_client.post(f"{BASE_URL}/api/seller/onboarding/complete-step", json={"step_id": "orders"})
        r = admin_client.post(f"{BASE_URL}/api/seller/onboarding/uncheck-step", json={"step_id": "orders"})
        assert r.status_code == 200, r.text
        data = r.json()
        orders_step = next(s for s in data["steps"] if s["id"] == "orders")
        assert orders_step["done"] is False

    def test_unknown_step_id_rejected(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/seller/onboarding/complete-step", json={"step_id": "nonexistent"})
        assert r.status_code == 400


class TestWizardTour:
    def test_dismiss_wizard(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/seller/onboarding/dismiss-wizard")
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        # verify state
        p = admin_client.get(f"{BASE_URL}/api/seller/onboarding/progress").json()
        assert p["wizard_dismissed"] is True

    def test_complete_tour(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/seller/onboarding/complete-tour")
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        p = admin_client.get(f"{BASE_URL}/api/seller/onboarding/progress").json()
        assert p["tour_completed"] is True


class TestAuth:
    def test_progress_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/seller/onboarding/progress")
        assert r.status_code in (401, 403)
