"""Iter 30 Wave 3 backend tests — Growth Insights weekly email + Search
relevance boost + Restore soft-deleted user.

Covers:
  * GET /api/health, admin login
  * POST /api/admin/users/{seller_id}/restore
      - restores soft-deleted seller and un-flags owned shop/restaurant/
        product/menu_item (is_deleted=false + is_public/is_open/is_active/
        is_available=true, restored_at set)
      - GET /api/admin/users default returns the restored user again
      - restore on non-deleted user → {ok:true, restored:false,
        already_active:true} (idempotent, no error)
      - restore is admin-only (seller / customer → 403)
  * GET /api/seller/growth-insights
      - seller-auth: correct JSON shape with numeric fields
      - customer → 403, anonymous → 401
  * POST /api/admin/growth-insights/send/{seller_id}
      - dry_run=true returns metrics without sending
      - dry_run=false responds 200 with {ok, email_id, seller_id} shape
        even when RESEND_API_KEY is missing (ok:false, email_id:null),
        NOT 500
      - soft-deleted seller → 400 'Seller is soft-deleted'
  * POST /api/admin/growth-insights/send-all
      - returns {ok:true, sent, skipped, failed, total_sellers}
      - seller with zero activity → in skipped[reason='no activity']
      - seller with invalid/empty email → in skipped[reason='no valid email']
  * GET /api/search relevance:
      - exact-prefix name > substring name > description-only
      - LTG partner tie-breaks equal-relevance rows
      - soft-deleted + is_public=false shops excluded
  * Regression:
      - /api/shops badge filters (ltg, deals, wholesale, verified) still work
      - /api/homepage/featured-products returns list<=limit
      - Soft-cascade delete flow still blocks login + hides shop
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

RUN_TAG = f"TEST_iter30w3_{uuid.uuid4().hex[:8]}"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    d = client[DB_NAME]
    yield d
    # Hard-teardown all seeded rows (RUN_TAG prefixed IDs / emails).
    for coll in [
        "users", "shops", "restaurants", "products", "menu_items",
        "orders", "restaurant_orders", "seller_order_splits",
        "favorites", "reviews", "notifications", "carts",
        "onboarding_progress", "email_verifications", "password_resets",
        "web_push_subscriptions", "shop_messages",
    ]:
        try:
            d[coll].delete_many({"id": {"$regex": f"^{RUN_TAG}"}})
            d[coll].delete_many({"email": {"$regex": RUN_TAG}})
            d[coll].delete_many({"seller_id": {"$regex": f"^{RUN_TAG}"}})
            d[coll].delete_many({"shop_id": {"$regex": f"^{RUN_TAG}"}})
            d[coll].delete_many({"user_id": {"$regex": f"^{RUN_TAG}"}})
        except Exception:
            pass
    # Purge anonymized deleted user rows we may have created.
    try:
        d["users"].delete_many({"name": "[Deleted user]", "deleted_by": {"$exists": True},
                                 "email": {"$regex": "@removed.local$"}})
    except Exception:
        pass
    client.close()


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    from requests.cookies import RequestsCookieJar

    class BlockingJar(RequestsCookieJar):
        def set_cookie(self, cookie, *a, **kw):
            return None
    s.cookies = BlockingJar()
    return s


@pytest.fixture(scope="module")
def admin_headers(api):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": "admin@jubasquare.com", "password": "1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}",
            "Content-Type": "application/json"}


def _make_seller(api, admin_headers, suffix):
    email = f"{RUN_TAG}_{suffix}@example.com".lower()
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/admin/users", headers=admin_headers, json={
        "email": email, "name": f"{RUN_TAG} {suffix}",
        "role": "seller", "password": password,
        "phone": "+211900000010", "email_verified": True,
    })
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    lr = api.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert lr.status_code == 200, lr.text
    tok = lr.json()["token"]
    return {"id": uid, "email": email, "password": password, "token": tok,
            "headers": {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}}


def _make_customer(api, suffix):
    email = f"{RUN_TAG}_{suffix}@example.com".lower()
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "name": f"{RUN_TAG} {suffix}",
        "password": password, "phone": "+211900000030",
    })
    assert r.status_code == 200, r.text
    # Auto-verify via DB (email service is disabled)
    client = MongoClient(MONGO_URL); d = client[DB_NAME]
    d.users.update_one({"email": email}, {"$set": {"email_verified": True}})
    client.close()
    lr = api.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert lr.status_code == 200, lr.text
    tok = lr.json()["token"]
    return {"email": email, "token": tok,
            "headers": {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}}


# ==========================================================================
# 0) Health + admin login
# ==========================================================================
class TestHealthAuth:
    def test_health(self, api):
        r = api.get(f"{BASE_URL}/api/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_admin_login(self, api):
        r = api.post(f"{BASE_URL}/api/auth/login",
                     json={"email": "admin@jubasquare.com", "password": "1234"})
        assert r.status_code == 200
        assert "token" in r.json()


# ==========================================================================
# 1) Restore soft-deleted seller
# ==========================================================================
@pytest.fixture(scope="module")
def restore_seller(api, admin_headers, db):
    """Create seller + shop + restaurant + product + menu_item, then
    soft-delete via API. All fixtures used by TestRestore below."""
    seller = _make_seller(api, admin_headers, "restore1")
    shop_id = f"{RUN_TAG}_rshop"
    prod_id = f"{RUN_TAG}_rprod"
    rest_id = f"{RUN_TAG}_rrest"
    menu_id = f"{RUN_TAG}_rmenu"
    db.shops.insert_one({
        "id": shop_id, "seller_id": seller["id"], "name": f"{RUN_TAG}_RShop",
        "area": "Juba", "category": "gen", "is_public": True, "is_deleted": False,
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "verification": "Verified", "product_sections": [], "created_at": _now(),
    })
    db.products.insert_one({
        "id": prod_id, "shop_id": shop_id, "seller_id": seller["id"],
        "name": f"{RUN_TAG}_RProd", "category_id": "cat_x", "category": "gen",
        "price_usd": 10.0, "stock": 5, "is_active": True, "is_deleted": False,
        "is_wholesale": False, "mode": "marketplace", "created_at": _now(),
    })
    db.restaurants.insert_one({
        "id": rest_id, "seller_id": seller["id"], "name": f"{RUN_TAG}_RRest",
        "area": "Juba", "is_open": True, "is_deleted": False,
        "verification": "Verified", "created_at": _now(),
    })
    db.menu_items.insert_one({
        "id": menu_id, "restaurant_id": rest_id, "seller_id": seller["id"],
        "name": f"{RUN_TAG}_RMenu", "price_usd": 5.0, "is_available": True,
        "is_deleted": False, "created_at": _now(),
    })
    # Soft-delete via API
    r = api.delete(f"{BASE_URL}/api/admin/users/{seller['id']}", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json().get("soft_deleted") is True
    return {"seller": seller, "shop_id": shop_id, "prod_id": prod_id,
            "rest_id": rest_id, "menu_id": menu_id}


class TestRestore:
    def test_restore_flips_flags(self, api, admin_headers, db, restore_seller):
        sid = restore_seller["seller"]["id"]
        r = api.post(f"{BASE_URL}/api/admin/users/{sid}/restore", headers=admin_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("restored") is True
        assert body.get("user_id") == sid

        u = db.users.find_one({"id": sid})
        assert u["is_deleted"] is False
        assert u["is_active"] is True
        assert u.get("restored_at")

        sh = db.shops.find_one({"id": restore_seller["shop_id"]})
        assert sh["is_deleted"] is False
        assert sh["is_public"] is True

        rest = db.restaurants.find_one({"id": restore_seller["rest_id"]})
        assert rest["is_deleted"] is False
        assert rest["is_open"] is True

        prod = db.products.find_one({"id": restore_seller["prod_id"]})
        assert prod["is_deleted"] is False
        assert prod["is_active"] is True

        menu = db.menu_items.find_one({"id": restore_seller["menu_id"]})
        assert menu["is_deleted"] is False
        assert menu["is_available"] is True

    def test_restored_seller_visible_in_default_admin_users(self, api, admin_headers, restore_seller):
        # After restore, seller shows up on default (non-include_deleted) list
        r = api.get(f"{BASE_URL}/api/admin/users?limit=1000", headers=admin_headers)
        assert r.status_code == 200
        items = r.json().get("items", r.json()) if isinstance(r.json(), dict) else r.json()
        # Response could be list-like or {items:[...]}; handle both
        if isinstance(items, dict):
            items = items.get("items", [])
        ids = [u.get("id") for u in items]
        assert restore_seller["seller"]["id"] in ids

    def test_restore_non_deleted_is_idempotent(self, api, admin_headers, restore_seller):
        # Second restore on same (now-active) seller must not error.
        sid = restore_seller["seller"]["id"]
        r = api.post(f"{BASE_URL}/api/admin/users/{sid}/restore", headers=admin_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("restored") is False
        assert body.get("already_active") is True

    def test_restore_forbidden_for_non_admin(self, api, admin_headers, db):
        # New seller + customer to test 403
        seller = _make_seller(api, admin_headers, "restore_perm_s")
        customer = _make_customer(api, "restore_perm_c")
        target_id = seller["id"]

        r_seller = api.post(f"{BASE_URL}/api/admin/users/{target_id}/restore",
                            headers=seller["headers"])
        assert r_seller.status_code == 403, r_seller.text

        r_cust = api.post(f"{BASE_URL}/api/admin/users/{target_id}/restore",
                          headers=customer["headers"])
        assert r_cust.status_code == 403, r_cust.text


# ==========================================================================
# 2) Growth Insights
# ==========================================================================
@pytest.fixture(scope="module")
def growth_seller(api, admin_headers, db):
    """Seller with a shop, product, seller_order_split (completed), and one
    cancelled split — inside the curr window."""
    seller = _make_seller(api, admin_headers, "growth1")
    shop_id = f"{RUN_TAG}_gshop"
    prod_id = f"{RUN_TAG}_gprod"
    db.shops.insert_one({
        "id": shop_id, "seller_id": seller["id"], "name": f"{RUN_TAG}_GShop",
        "area": "Juba", "category": "gen", "is_public": True, "is_deleted": False,
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "verification": "Verified", "product_sections": [], "created_at": _now(),
        "average_rating": 4.5, "review_count": 6,
    })
    db.products.insert_one({
        "id": prod_id, "shop_id": shop_id, "seller_id": seller["id"],
        "name": f"{RUN_TAG}_GProd", "category_id": "cat_x", "category": "gen",
        "price_usd": 10.0, "stock": 5, "is_active": True, "is_deleted": False,
        "is_wholesale": False, "mode": "marketplace", "created_at": _now(),
    })
    # completed split in curr window
    db.seller_order_splits.insert_one({
        "id": f"{RUN_TAG}_gsplit1", "seller_id": seller["id"],
        "order_id": f"{RUN_TAG}_gorder1", "shop_id": shop_id,
        "seller_earning_usd": 20.0, "delivery_status": "Delivered",
        "created_at": _iso_days_ago(2),
    })
    # cancelled split in curr window
    db.seller_order_splits.insert_one({
        "id": f"{RUN_TAG}_gsplit2", "seller_id": seller["id"],
        "order_id": f"{RUN_TAG}_gorder2", "shop_id": shop_id,
        "seller_earning_usd": 0.0, "delivery_status": "cancelled",
        "created_at": _iso_days_ago(3),
    })
    # A favorite in the curr window (customer favorites the shop)
    db.favorites.insert_one({
        "id": f"{RUN_TAG}_gfav1", "user_id": f"{RUN_TAG}_ghost_cust",
        "target_id": shop_id, "target_type": "shop",
        "created_at": _iso_days_ago(1),
    })
    return {"seller": seller, "shop_id": shop_id, "prod_id": prod_id}


class TestGrowthInsightsPreview:
    def test_seller_preview_shape(self, api, growth_seller):
        r = api.get(f"{BASE_URL}/api/seller/growth-insights",
                    headers=growth_seller["seller"]["headers"])
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("seller_id", "shop_name", "curr", "prev", "top_products", "window"):
            assert k in body, f"missing {k}"
        for section in ("curr", "prev"):
            s = body[section]
            for k in ("orders", "revenue_usd", "cancelled", "favorites", "rating", "review_count"):
                assert k in s, f"{section}.{k} missing"
                assert isinstance(s[k], (int, float)), f"{section}.{k} is {type(s[k])}"
        # curr must reflect the 1 completed split + 1 cancelled + 1 favorite we seeded
        assert body["curr"]["orders"] >= 1
        assert body["curr"]["cancelled"] >= 1
        assert body["curr"]["favorites"] >= 1
        assert body["curr"]["revenue_usd"] >= 20.0
        assert isinstance(body["top_products"], list)

    def test_preview_forbidden_for_customer(self, api, admin_headers):
        cust = _make_customer(api, "growth_cust")
        r = api.get(f"{BASE_URL}/api/seller/growth-insights", headers=cust["headers"])
        assert r.status_code == 403

    def test_preview_requires_auth(self, api):
        r = api.get(f"{BASE_URL}/api/seller/growth-insights")
        assert r.status_code == 401


class TestGrowthInsightsSend:
    def test_dry_run_returns_metrics(self, api, admin_headers, growth_seller):
        r = api.post(
            f"{BASE_URL}/api/admin/growth-insights/send/{growth_seller['seller']['id']}",
            headers=admin_headers, json={"dry_run": True},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("dry_run") is True
        assert "metrics" in body
        assert body["metrics"]["curr"]["orders"] >= 1

    def test_send_no_resend_config_still_200(self, api, admin_headers, growth_seller):
        # Without dry_run — email_service returns ok:false when RESEND_API_KEY
        # is missing. Endpoint must still respond 200 with the shape.
        r = api.post(
            f"{BASE_URL}/api/admin/growth-insights/send/{growth_seller['seller']['id']}",
            headers=admin_headers, json={"dry_run": False},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "ok" in body
        assert "email_id" in body
        assert body.get("seller_id") == growth_seller["seller"]["id"]
        # ok may be True or False depending on RESEND_API_KEY presence — both OK.

    def test_send_on_soft_deleted_seller_400(self, api, admin_headers, db):
        seller = _make_seller(api, admin_headers, "growth_soft")
        # soft-delete
        r = api.delete(f"{BASE_URL}/api/admin/users/{seller['id']}", headers=admin_headers)
        assert r.status_code == 200
        r = api.post(f"{BASE_URL}/api/admin/growth-insights/send/{seller['id']}",
                     headers=admin_headers, json={"dry_run": True})
        assert r.status_code == 400
        assert "soft-deleted" in r.text.lower()

    def test_send_all_shape_and_categories(self, api, admin_headers, db, growth_seller):
        # Add a "no activity" seller and a "no valid email" seller to force
        # both skip-reason branches.
        no_act = _make_seller(api, admin_headers, "growth_noact")
        # Directly insert a seller with an invalid email so send-all sees it.
        bad_id = f"{RUN_TAG}_bademail"
        db.users.insert_one({
            "id": bad_id, "email": "", "name": "no email seller",
            "role": "seller", "is_active": True, "is_deleted": False,
            "email_verified": True, "password_hash": "!disabled!",
            "created_at": _now(),
        })

        r = api.post(f"{BASE_URL}/api/admin/growth-insights/send-all",
                     headers=admin_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert isinstance(body.get("sent"), int)
        assert isinstance(body.get("skipped"), list)
        assert isinstance(body.get("failed"), list)
        assert isinstance(body.get("total_sellers"), int)

        skipped_reasons = {(sk.get("seller_id"), sk.get("reason")) for sk in body["skipped"]}
        assert (no_act["id"], "no activity") in skipped_reasons, \
            f"expected no_activity skip; got {skipped_reasons}"
        assert (bad_id, "no valid email") in skipped_reasons, \
            f"expected no_valid_email skip; got {skipped_reasons}"


# ==========================================================================
# 3) Search relevance ranking
# ==========================================================================
@pytest.fixture(scope="module")
def search_seed(db, api, admin_headers):
    """Seed shops for relevance ranking tests."""
    seller = _make_seller(api, admin_headers, "search_seller")
    sid = seller["id"]
    docs = [
        # q='fresh' scenario
        {"id": f"{RUN_TAG}_s_prefix", "seller_id": sid, "name": "Fresh Foods",
         "description": "veggies", "area": "Juba", "is_public": True,
         "is_deleted": False, "verification": "Verified"},
        {"id": f"{RUN_TAG}_s_sub", "seller_id": sid, "name": "Refreshing Fresh",
         "description": "juice bar", "area": "Juba", "is_public": True,
         "is_deleted": False, "verification": "Verified"},
        {"id": f"{RUN_TAG}_s_desc", "seller_id": sid, "name": "Deli Zone",
         "description": "fresh imported deli goods", "area": "Juba",
         "is_public": True, "is_deleted": False, "verification": "Verified"},
        # q='alpha' — LTG tie-break scenario
        {"id": f"{RUN_TAG}_s_alpha_ltg", "seller_id": sid, "name": "Alpha Bravo",
         "area": "Juba", "is_public": True, "is_deleted": False,
         "verification": "Verified", "is_ltg_partner": True},
        {"id": f"{RUN_TAG}_s_alpha_plain", "seller_id": sid, "name": "Alpha Charlie",
         "area": "Juba", "is_public": True, "is_deleted": False,
         "verification": "Verified", "is_ltg_partner": False},
        # Excluded — soft-deleted
        {"id": f"{RUN_TAG}_s_del", "seller_id": sid, "name": "Fresh Deleted",
         "area": "Juba", "is_public": True, "is_deleted": True,
         "verification": "Verified"},
        # Excluded — is_public=False
        {"id": f"{RUN_TAG}_s_priv", "seller_id": sid, "name": "Fresh Private",
         "area": "Juba", "is_public": False, "is_deleted": False,
         "verification": "Verified"},
    ]
    db.shops.insert_many(docs)
    yield {"seller": seller}


class TestSearchRelevance:
    def test_prefix_beats_substring_beats_desc(self, api, search_seed):
        r = api.get(f"{BASE_URL}/api/search?q=fresh&limit=5")
        assert r.status_code == 200
        shops = r.json().get("shops", [])
        names = [s["name"] for s in shops]
        # Filter to our seed rows only (env may have other 'fresh' shops)
        ours = [n for n in names if n in {"Fresh Foods", "Refreshing Fresh", "Deli Zone"}]
        assert "Fresh Foods" in ours
        assert "Refreshing Fresh" in ours
        assert "Deli Zone" in ours
        assert ours.index("Fresh Foods") < ours.index("Refreshing Fresh"), \
            f"expected prefix first; order={ours}"
        assert ours.index("Refreshing Fresh") < ours.index("Deli Zone"), \
            f"expected substring before desc; order={ours}"

    def test_ltg_tie_breaks(self, api, search_seed):
        r = api.get(f"{BASE_URL}/api/search?q=alpha&limit=5")
        assert r.status_code == 200
        shops = r.json().get("shops", [])
        names = [s["name"] for s in shops]
        ours = [n for n in names if n in {"Alpha Bravo", "Alpha Charlie"}]
        assert len(ours) == 2
        assert ours[0] == "Alpha Bravo", f"LTG shop should rank first: {ours}"

    def test_soft_deleted_and_private_excluded(self, api, search_seed):
        r = api.get(f"{BASE_URL}/api/search?q=fresh&limit=20")
        assert r.status_code == 200
        names = [s["name"] for s in r.json().get("shops", [])]
        assert "Fresh Deleted" not in names
        assert "Fresh Private" not in names


# ==========================================================================
# 4) Regression: shops badge filters + featured-products + soft-cascade
# ==========================================================================
class TestRegression:
    def test_shops_ltg_verified_filters(self, api):
        r1 = api.get(f"{BASE_URL}/api/shops?ltg=true&limit=200")
        assert r1.status_code == 200
        assert all((s.get("is_ltg_partner") is True) for s in r1.json())

        r2 = api.get(f"{BASE_URL}/api/shops?verified=true&limit=200")
        assert r2.status_code == 200
        assert all((s.get("verification") == "Verified") for s in r2.json())

    def test_shops_wholesale_deals_filters_run(self, api):
        # These may return empty (env-dependent) but should not 500.
        r = api.get(f"{BASE_URL}/api/shops?wholesale=true&limit=50")
        assert r.status_code == 200
        r = api.get(f"{BASE_URL}/api/shops?deals=true&limit=50")
        assert r.status_code == 200

    def test_featured_products(self, api):
        r = api.get(f"{BASE_URL}/api/homepage/featured-products?limit=8")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        assert len(body) <= 8

    def test_soft_cascade_still_blocks_login(self, api, admin_headers, db):
        seller = _make_seller(api, admin_headers, "cascade1")
        # Seed a shop under the seller so we can verify it is hidden after delete.
        shop_id = f"{RUN_TAG}_cshop"
        db.shops.insert_one({
            "id": shop_id, "seller_id": seller["id"], "name": f"{RUN_TAG}_CShop",
            "area": "Juba", "is_public": True, "is_deleted": False,
            "verification": "Verified", "created_at": _now(),
        })
        # Delete
        r = api.delete(f"{BASE_URL}/api/admin/users/{seller['id']}", headers=admin_headers)
        assert r.status_code == 200
        # Login blocked
        lr = api.post(f"{BASE_URL}/api/auth/login",
                      json={"email": seller["email"], "password": seller["password"]})
        assert lr.status_code == 401
        # Shop no longer in public listing
        sh = db.shops.find_one({"id": shop_id})
        assert sh["is_deleted"] is True
