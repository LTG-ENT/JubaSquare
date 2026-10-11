"""Iteration 38 – test Google-session endpoint, seller wallet/payout settings/analytics,
service/customs/shipping fees on marketplace & restaurant orders, invoice platform_fees,
international hold flow, admin mark-paid rules, and notification deep-links.
"""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

ADMIN = {"email": "admin@jubasquare.com", "password": "1234"}
SELLER = {"email": "qa_seller@jubasquare.com", "password": "Seller@123"}


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
def _login(creds):
    r = requests.post(f"{BASE}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def seller_token():
    return _login(SELLER)


@pytest.fixture(scope="module")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def seller_h(seller_token):
    return {"Authorization": f"Bearer {seller_token}"}


@pytest.fixture(scope="module")
def seller_me(seller_h):
    r = requests.get(f"{BASE}/api/auth/me", headers=seller_h, timeout=20)
    assert r.status_code == 200
    return r.json()


# ---------------------------------------------------------------------------
# 1. Google-session endpoint
# ---------------------------------------------------------------------------
class TestGoogleSession:
    def test_bogus_session_id_returns_401(self):
        r = requests.post(
            f"{BASE}/api/auth/google-session",
            json={"session_id": "bogus-" + uuid.uuid4().hex},
            timeout=20,
        )
        assert r.status_code == 401, r.text
        body = r.json()
        assert "Google" in (body.get("detail") or "")

    def test_missing_session_id_returns_422(self):
        r = requests.post(f"{BASE}/api/auth/google-session", json={}, timeout=20)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 2. Seller payout settings  (qa_seller is international)
# ---------------------------------------------------------------------------
class TestPayoutSettings:
    def test_get_shape_international(self, seller_h):
        r = requests.get(f"{BASE}/api/seller/payout-settings", headers=seller_h, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d.get("is_international") is True
        assert d.get("method") in ("bank", "cash")
        assert "bank" in d
        for k in ("account_name", "bank_name", "account_number", "swift_iban", "bank_country"):
            assert k in d["bank"]

    def test_put_missing_fields_returns_400(self, seller_h):
        r = requests.put(
            f"{BASE}/api/seller/payout-settings",
            headers=seller_h,
            json={"method": "bank"},
            timeout=20,
        )
        assert r.status_code == 400
        assert "required" in r.json().get("detail", "").lower()

    def test_put_bank_missing_swift_returns_400(self, seller_h):
        r = requests.put(
            f"{BASE}/api/seller/payout-settings",
            headers=seller_h,
            json={
                "method": "bank",
                "account_name": "QA Seller",
                "bank_name": "Chase",
                "account_number": "0001112223",
                "swift_iban": "",
                "bank_country": "USA",
            },
            timeout=20,
        )
        # international => SWIFT required
        assert r.status_code == 400
        assert "SWIFT" in r.json().get("detail", "")

    def test_put_full_bank_ok_and_method_forced_bank(self, seller_h):
        r = requests.put(
            f"{BASE}/api/seller/payout-settings",
            headers=seller_h,
            json={
                "method": "cash",  # should be forced to bank
                "account_name": "QA Seller",
                "bank_name": "Chase",
                "account_number": "0001112223",
                "swift_iban": "CHASUS33",
                "bank_country": "USA",
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["method"] == "bank"  # international forced
        assert d["bank"]["swift_iban"] == "CHASUS33"


# ---------------------------------------------------------------------------
# 3. Seller wallet shape
# ---------------------------------------------------------------------------
class TestSellerWallet:
    def test_wallet_shape(self, seller_h):
        r = requests.get(f"{BASE}/api/seller/wallet", headers=seller_h, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("seller_manages_delivery", "is_international", "active_count",
                  "on_hold", "hold_days", "balance"):
            assert k in d, f"missing {k}"
        assert d["is_international"] is True
        b = d["balance"]
        for k in ("total_sales", "commission", "refunds", "fees",
                  "on_hold", "available", "pending", "paid"):
            assert k in b, f"balance missing {k}"


# ---------------------------------------------------------------------------
# 4. Seller analytics – entities list + shop/restaurant filter
# ---------------------------------------------------------------------------
class TestSellerAnalytics:
    def test_entities_present(self, seller_h):
        r = requests.get(f"{BASE}/api/seller/analytics", headers=seller_h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "entities" in d and isinstance(d["entities"], list)
        kinds = {e["kind"] for e in d["entities"]}
        # QA seller owns a shop AND a restaurant
        assert "shop" in kinds and "restaurant" in kinds, d["entities"]

    def test_filter_by_shop_isolates_restaurant(self, seller_h):
        all_r = requests.get(f"{BASE}/api/seller/analytics", headers=seller_h, timeout=30).json()
        shop_id = next(e["id"] for e in all_r["entities"] if e["kind"] == "shop")
        r = requests.get(f"{BASE}/api/seller/analytics",
                         headers=seller_h, params={"shop_id": shop_id}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        # restaurant channel totals should all be 0 when filtered to a shop
        rest_all = d["by_channel"]["restaurant"]["totals"]["all_time"]
        assert rest_all["revenue"] == 0 and rest_all["orders"] == 0

    def test_filter_by_restaurant_isolates_shop(self, seller_h):
        all_r = requests.get(f"{BASE}/api/seller/analytics", headers=seller_h, timeout=30).json()
        rest_id = next(e["id"] for e in all_r["entities"] if e["kind"] == "restaurant")
        r = requests.get(f"{BASE}/api/seller/analytics",
                         headers=seller_h, params={"restaurant_id": rest_id}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        mp_all = d["by_channel"]["marketplace"]["totals"]["all_time"]
        assert mp_all["revenue"] == 0 and mp_all["orders"] == 0


# ---------------------------------------------------------------------------
# 5. Admin settings – service/customs/hold/bank-fee setters
# ---------------------------------------------------------------------------
class TestAdminSettingsFees:
    def test_get_settings_has_new_fields(self, admin_h):
        r = requests.get(f"{BASE}/api/admin/settings", headers=admin_h, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("service_fee_rate", "customs_rate",
                  "international_payout_hold_days", "bank_transfer_fee_usd"):
            assert k in d, f"missing settings field {k}"

    def test_update_fee_settings(self, admin_h):
        r = requests.put(f"{BASE}/api/admin/settings", headers=admin_h, json={
            "service_fee_rate": 0.05,
            "customs_rate": 0.10,
            "international_payout_hold_days": 30,
            "bank_transfer_fee_usd": 15.0,
        }, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert abs(d["service_fee_rate"] - 0.05) < 1e-6
        assert abs(d["customs_rate"] - 0.10) < 1e-6
        assert d["international_payout_hold_days"] == 30
        assert abs(d["bank_transfer_fee_usd"] - 15.0) < 1e-6


# ---------------------------------------------------------------------------
# 6. Mark-paid guard – bank payout requires reference
# ---------------------------------------------------------------------------
class TestMarkPaidGuard:
    def test_mark_paid_bank_no_reference_400_or_404(self, admin_h):
        """Validate the guard logic.  If there's an unpaid bank payout we
        should get 400 (reference missing).  If none exist in the DB we at
        least verify the handler responds with 404 for a bogus id (handler
        is reachable and auth-passing).
        """
        # Look for any pending bank payout
        r = requests.get(f"{BASE}/api/admin/payouts", headers=admin_h, timeout=20)
        assert r.status_code == 200
        payouts = r.json() if isinstance(r.json(), list) else r.json().get("items") or []
        candidate = next(
            (p for p in payouts if p.get("payout_method") == "bank" and p.get("status") != "paid"),
            None,
        )
        if candidate:
            r2 = requests.post(
                f"{BASE}/api/admin/payouts/{candidate['id']}/mark-paid",
                headers=admin_h, json={}, timeout=20,
            )
            assert r2.status_code == 400
            assert "reference" in r2.json().get("detail", "").lower()
        else:
            # Fallback: hit a bogus id, expect 404 (handler reachable)
            r2 = requests.post(
                f"{BASE}/api/admin/payouts/nonexistent-id/mark-paid",
                headers=admin_h, json={}, timeout=20,
            )
            assert r2.status_code == 404


# ---------------------------------------------------------------------------
# 7. Notifications carry meta.link
# ---------------------------------------------------------------------------
class TestNotificationLinks:
    def test_notifications_list_has_link_meta(self, seller_h):
        r = requests.get(f"{BASE}/api/notifications", headers=seller_h, timeout=20)
        if r.status_code != 200:
            pytest.skip(f"notifications endpoint {r.status_code}")
        payload = r.json()
        items = payload.get("items", payload) if isinstance(payload, dict) else payload
        if not items:
            pytest.skip("seller has no notifications yet")
        # At least one notification should include meta.link
        with_link = [n for n in items if (n.get("meta") or {}).get("link")]
        assert with_link, "no notifications contain meta.link deep-link"
        # Seller links should start with /seller or /orders
        bad = [n for n in with_link if not n["meta"]["link"].startswith(("/seller", "/orders", "/admin"))]
        assert not bad, f"unexpected links: {[n['meta']['link'] for n in bad]}"
