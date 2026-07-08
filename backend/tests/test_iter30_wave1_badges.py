"""Iter30 Wave1 backend tests — Badge flags, LTG product toggle, favorites orphan cleanup.

Covers:
- Backend health + admin login.
- GET /api/shops enrichment: has_active_promo + has_wholesale flags.
- GET /api/restaurants: has_live_promo + has_active_promo alias.
- PUT /api/admin/products/{id}/ltg-partner admin toggle + 403 for non-admin.
- LTG-first sort on /api/products.
- Favorites orphan cleanup on hard-delete + soft-delete filtering.
- Favorites happy path GET/POST shape.
- /api/products?is_wholesale=true|false filter isolation.
- Regression: LTG toggle for shops/restaurants still works.
- Regression: /api/shops returns 200 with no products (has_active_promo/has_wholesale default false).
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

RUN_TAG = f"TEST_iter30w1_{uuid.uuid4().hex[:8]}"


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    d = client[DB_NAME]
    yield d
    # Hard cleanup - API delete is soft-delete
    for coll in [
        "users", "shops", "restaurants", "products", "menu_items",
        "orders", "restaurant_orders", "seller_order_splits",
        "favorites", "reviews", "categories",
    ]:
        for key in ("id", "email", "seller_id", "shop_id", "restaurant_id",
                    "user_id", "customer_id", "target_id"):
            d[coll].delete_many({key: {"$regex": f"^{RUN_TAG}"}})
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


@pytest.fixture(scope="module")
def seller_ctx(api, admin_headers):
    email = f"{RUN_TAG}_seller@example.com".lower()
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/admin/users", headers=admin_headers, json={
        "email": email, "name": f"{RUN_TAG} Seller", "role": "seller",
        "password": password, "phone": "+211900000001", "email_verified": True,
    })
    assert r.status_code == 200, r.text
    sid = r.json()["user"]["id"]
    lg = api.post(f"{BASE_URL}/api/auth/login",
                  json={"email": email, "password": password})
    tok = lg.json()["token"]
    return {"id": sid, "email": email, "token": tok,
            "headers": {"Authorization": f"Bearer {tok}",
                        "Content-Type": "application/json"}}


@pytest.fixture(scope="module")
def customer_ctx(api, db):
    email = f"{RUN_TAG}_cust@example.com".lower()
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "name": f"{RUN_TAG} Cust",
        "password": password, "phone": "+211900000002",
    })
    assert r.status_code == 200, r.text
    db.users.update_one({"email": email}, {"$set": {"email_verified": True}})
    lg = api.post(f"{BASE_URL}/api/auth/login",
                  json={"email": email, "password": password})
    tok = lg.json()["token"]
    return {"id": lg.json()["user"]["id"], "email": email, "token": tok,
            "headers": {"Authorization": f"Bearer {tok}",
                        "Content-Type": "application/json"}}


# Two shops: one with promo + wholesale product, one with plain retail product only.
@pytest.fixture(scope="module")
def seeded_shops(db, seller_ctx):
    s_promo = f"{RUN_TAG}_shop_promo"
    s_plain = f"{RUN_TAG}_shop_plain"
    common = {
        "seller_id": seller_ctx["id"], "area": "Juba", "category": "gen",
        "verification": "Verified", "is_public": True, "is_deleted": False,
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "product_sections": [], "created_at": _now(),
    }
    db.shops.insert_one({**common, "id": s_promo, "name": "TEST_PromoShop",
                         "is_ltg_partner": False})
    db.shops.insert_one({**common, "id": s_plain, "name": "TEST_PlainShop",
                         "is_ltg_partner": False})

    # Promo shop → 1 promo product + 1 wholesale product
    db.products.insert_many([
        {
            "id": f"{RUN_TAG}_p_promo", "shop_id": s_promo,
            "seller_id": seller_ctx["id"], "name": "TEST_PromoP",
            "category": "gen", "price_usd": 20.0, "stock": 10,
            "is_active": True, "is_wholesale": False, "min_order_qty": 1,
            "mode": "marketplace", "pricing_tiers": [], "is_deleted": False,
            "promo": {"active": True, "type": "percent", "value": 25.0,
                      "bogo_min_qty": 2, "starts_at": None, "ends_at": None},
            "created_at": _now(),
        },
        {
            "id": f"{RUN_TAG}_p_whole", "shop_id": s_promo,
            "seller_id": seller_ctx["id"], "name": "TEST_WholeP",
            "category": "gen", "price_usd": 5.0, "stock": 100,
            "is_active": True, "is_wholesale": True, "min_order_qty": 10,
            "mode": "marketplace", "pricing_tiers": [], "is_deleted": False,
            "promo": {"active": False}, "created_at": _now(),
        },
        # Plain shop: retail-only, no promo
        {
            "id": f"{RUN_TAG}_p_plain", "shop_id": s_plain,
            "seller_id": seller_ctx["id"], "name": "TEST_PlainP",
            "category": "gen", "price_usd": 12.0, "stock": 10,
            "is_active": True, "is_wholesale": False, "min_order_qty": 1,
            "mode": "marketplace", "pricing_tiers": [], "is_deleted": False,
            "promo": {"active": False}, "created_at": _now(),
        },
    ])
    return {"promo": s_promo, "plain": s_plain}


@pytest.fixture(scope="module")
def seeded_restaurant(db, seller_ctx):
    rid = f"{RUN_TAG}_rest_promo"
    db.restaurants.insert_one({
        "id": rid, "seller_id": seller_ctx["id"], "name": "TEST_PromoRest",
        "area": "Juba", "is_open": True, "is_deleted": False,
        "verification": "Verified", "delivery_managed_by": "seller",
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "menu_sections": [], "is_ltg_partner": False, "created_at": _now(),
    })
    db.menu_items.insert_one({
        "id": f"{RUN_TAG}_mi", "restaurant_id": rid,
        "seller_id": seller_ctx["id"], "name": "TEST_MI",
        "category": "gen", "price_usd": 15.0, "is_active": True,
        "is_deleted": False,
        "promo": {"active": True, "type": "percent", "value": 20.0,
                  "starts_at": None, "ends_at": None},
        "created_at": _now(),
    })
    return rid


# =============================================================================
# 1. Health + admin
# =============================================================================
class TestHealth:
    def test_health(self, api):
        r = api.get(f"{BASE_URL}/api/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_admin_login(self, api):
        r = api.post(f"{BASE_URL}/api/auth/login",
                     json={"email": "admin@jubasquare.com", "password": "1234"})
        assert r.status_code == 200 and "token" in r.json()


# =============================================================================
# 2. /api/shops enrichment — has_active_promo + has_wholesale
# =============================================================================
class TestShopsEnrichment:
    def test_shops_flags(self, api, seeded_shops):
        r = api.get(f"{BASE_URL}/api/shops?area=Juba&limit=200")
        assert r.status_code == 200
        shops = r.json()
        promo_shop = next((s for s in shops if s["id"] == seeded_shops["promo"]), None)
        plain_shop = next((s for s in shops if s["id"] == seeded_shops["plain"]), None)
        assert promo_shop is not None, "seeded promo shop missing"
        assert plain_shop is not None, "seeded plain shop missing"

        # Promo shop should have BOTH flags true
        assert promo_shop.get("has_active_promo") is True, (
            f"promo shop has_active_promo != True: {promo_shop.get('has_active_promo')}")
        assert promo_shop.get("has_wholesale") is True, (
            f"promo shop has_wholesale != True: {promo_shop.get('has_wholesale')}")

        # Plain shop → both false
        assert plain_shop.get("has_active_promo") is False
        assert plain_shop.get("has_wholesale") is False


# =============================================================================
# 3. /api/restaurants — has_live_promo + has_active_promo alias
# =============================================================================
class TestRestaurantEnrichment:
    def test_restaurant_promo_flags(self, api, seeded_restaurant):
        r = api.get(f"{BASE_URL}/api/restaurants?area=Juba&limit=200")
        assert r.status_code == 200
        rests = r.json()
        our = next((x for x in rests if x["id"] == seeded_restaurant), None)
        assert our is not None
        assert our.get("has_live_promo") is True
        assert our.get("has_active_promo") is True  # alias


# =============================================================================
# 4. /admin/products/{id}/ltg-partner toggle
# =============================================================================
class TestProductLTGToggle:
    def test_admin_toggle_product_ltg_on(self, api, admin_headers, seeded_shops, db):
        pid = f"{RUN_TAG}_p_plain"
        r = api.put(f"{BASE_URL}/api/admin/products/{pid}/ltg-partner",
                    headers=admin_headers, json={"is_ltg_partner": True})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        assert j["is_ltg_partner"] is True
        doc = db.products.find_one({"id": pid})
        assert doc["is_ltg_partner"] is True

    def test_ltg_products_sort_first(self, api, seeded_shops):
        # Get products list — LTG-toggled p_plain must come before non-LTG within same verified tier
        r = api.get(f"{BASE_URL}/api/products?limit=500")
        assert r.status_code == 200
        prods = r.json()
        ltg_idx = next((i for i, p in enumerate(prods) if p["id"] == f"{RUN_TAG}_p_plain"), -1)
        promo_idx = next((i for i, p in enumerate(prods) if p["id"] == f"{RUN_TAG}_p_promo"), -1)
        assert ltg_idx != -1, "LTG product missing from list"
        assert promo_idx != -1, "Non-LTG product missing from list"
        # both are in Verified shops → LTG must come first
        assert ltg_idx < promo_idx, (
            f"LTG product should sort before non-LTG (ltg_idx={ltg_idx}, promo_idx={promo_idx})")

    def test_product_ltg_404(self, api, admin_headers):
        r = api.put(f"{BASE_URL}/api/admin/products/nonexistent-xyz/ltg-partner",
                    headers=admin_headers, json={"is_ltg_partner": True})
        assert r.status_code == 404

    def test_product_ltg_403_customer(self, api, customer_ctx, seeded_shops):
        pid = f"{RUN_TAG}_p_plain"
        r = api.put(f"{BASE_URL}/api/admin/products/{pid}/ltg-partner",
                    headers=customer_ctx["headers"], json={"is_ltg_partner": True})
        assert r.status_code == 403

    def test_product_ltg_403_seller(self, api, seller_ctx, seeded_shops):
        pid = f"{RUN_TAG}_p_plain"
        r = api.put(f"{BASE_URL}/api/admin/products/{pid}/ltg-partner",
                    headers=seller_ctx["headers"], json={"is_ltg_partner": True})
        assert r.status_code == 403

    def test_toggle_off_persistence(self, api, admin_headers, seeded_shops, db):
        pid = f"{RUN_TAG}_p_plain"
        r = api.put(f"{BASE_URL}/api/admin/products/{pid}/ltg-partner",
                    headers=admin_headers, json={"is_ltg_partner": False})
        assert r.status_code == 200
        assert r.json()["is_ltg_partner"] is False
        # re-enable for downstream tests
        api.put(f"{BASE_URL}/api/admin/products/{pid}/ltg-partner",
                headers=admin_headers, json={"is_ltg_partner": True})


# =============================================================================
# 5. Favorites — orphan cleanup + soft-delete filter + happy path
# =============================================================================
class TestFavoritesOrphanCleanup:
    def test_favorites_happy_path(self, api, customer_ctx, seeded_shops):
        pid = f"{RUN_TAG}_p_promo"
        r = api.post(f"{BASE_URL}/api/favorites", headers=customer_ctx["headers"],
                     json={"target_type": "product", "target_id": pid})
        assert r.status_code == 200, r.text
        g = api.get(f"{BASE_URL}/api/favorites", headers=customer_ctx["headers"])
        assert g.status_code == 200
        favs = g.json()
        entry = next((f for f in favs if f["item"]["id"] == pid), None)
        assert entry is not None
        assert "favorite_id" in entry
        assert entry["target_type"] == "product"
        assert "created_at" in entry
        assert entry["item"]["id"] == pid

    def test_hard_delete_product_orphan_cleanup(self, api, customer_ctx, seller_ctx,
                                                 seeded_shops, db):
        # Create a fresh disposable product favorited by customer
        pid = f"{RUN_TAG}_p_orphan"
        db.products.insert_one({
            "id": pid, "shop_id": seeded_shops["promo"],
            "seller_id": seller_ctx["id"], "name": "TEST_Orphan",
            "category": "gen", "price_usd": 3.0, "stock": 5,
            "is_active": True, "is_wholesale": False, "min_order_qty": 1,
            "mode": "marketplace", "pricing_tiers": [], "is_deleted": False,
            "promo": {"active": False}, "created_at": _now(),
        })
        r = api.post(f"{BASE_URL}/api/favorites", headers=customer_ctx["headers"],
                     json={"target_type": "product", "target_id": pid})
        assert r.status_code == 200
        fav_id = r.json().get("id")
        assert fav_id

        # Hard-delete the product
        db.products.delete_one({"id": pid})

        # Verify GET filters the orphan out
        g = api.get(f"{BASE_URL}/api/favorites", headers=customer_ctx["headers"])
        assert g.status_code == 200
        remaining_target_ids = [f["item"]["id"] for f in g.json() if f.get("item")]
        assert pid not in remaining_target_ids

        # Cleanup should have removed the favorite record from db
        assert db.favorites.find_one({"id": fav_id}) is None, (
            "orphan favorite record should have been auto-deleted")

    def test_soft_delete_shop_hidden_from_favorites(self, api, customer_ctx,
                                                     seller_ctx, db):
        sid = f"{RUN_TAG}_shop_soft"
        db.shops.insert_one({
            "id": sid, "seller_id": seller_ctx["id"], "name": "TEST_SoftShop",
            "area": "Juba", "category": "gen", "verification": "Verified",
            "is_public": True, "is_deleted": False,
            "delivery_mode": "free", "delivery_fee_usd": 0.0,
            "product_sections": [], "created_at": _now(),
        })
        r = api.post(f"{BASE_URL}/api/favorites", headers=customer_ctx["headers"],
                     json={"target_type": "shop", "target_id": sid})
        assert r.status_code == 200
        # Soft-delete
        db.shops.update_one({"id": sid}, {"$set": {"is_deleted": True}})
        g = api.get(f"{BASE_URL}/api/favorites", headers=customer_ctx["headers"])
        assert g.status_code == 200
        remaining = [f["item"]["id"] for f in g.json() if f.get("item")]
        assert sid not in remaining, "soft-deleted shop should not appear in favorites"


# =============================================================================
# 6. /api/products?is_wholesale filter isolation
# =============================================================================
class TestWholesaleFilter:
    def test_wholesale_true_only(self, api):
        r = api.get(f"{BASE_URL}/api/products?is_wholesale=true&limit=500")
        assert r.status_code == 200
        prods = r.json()
        # every returned product must be is_wholesale True
        offenders = [p for p in prods if p.get("is_wholesale") is not True]
        assert not offenders, f"is_wholesale=true leaked non-wholesale: {[p['id'] for p in offenders][:5]}"

    def test_wholesale_false_only(self, api):
        r = api.get(f"{BASE_URL}/api/products?is_wholesale=false&limit=500")
        assert r.status_code == 200
        prods = r.json()
        offenders = [p for p in prods if p.get("is_wholesale") is True]
        assert not offenders, f"is_wholesale=false leaked wholesale: {[p['id'] for p in offenders][:5]}"


# =============================================================================
# 7. Regression — LTG toggle for shops and restaurants
# =============================================================================
class TestLTGRegression:
    def test_shop_ltg_toggle_regression(self, api, admin_headers, seeded_shops, db):
        sid = seeded_shops["promo"]
        r = api.put(f"{BASE_URL}/api/admin/shops/{sid}/ltg-partner",
                    headers=admin_headers, json={"is_ltg_partner": True})
        assert r.status_code == 200
        assert r.json()["is_ltg_partner"] is True
        # Verify it appears first in /api/shops
        listing = api.get(f"{BASE_URL}/api/shops?area=Juba&limit=200").json()
        promo_idx = next((i for i, s in enumerate(listing) if s["id"] == sid), -1)
        plain_idx = next((i for i, s in enumerate(listing) if s["id"] == seeded_shops["plain"]), -1)
        assert promo_idx != -1 and plain_idx != -1
        assert promo_idx < plain_idx, "LTG shop should sort first"
        # Toggle off
        api.put(f"{BASE_URL}/api/admin/shops/{sid}/ltg-partner",
                headers=admin_headers, json={"is_ltg_partner": False})

    def test_restaurant_ltg_toggle_regression(self, api, admin_headers,
                                              seeded_restaurant, db):
        rid = seeded_restaurant
        r = api.put(f"{BASE_URL}/api/admin/restaurants/{rid}/ltg-partner",
                    headers=admin_headers, json={"is_ltg_partner": True})
        assert r.status_code == 200
        assert r.json()["is_ltg_partner"] is True
        api.put(f"{BASE_URL}/api/admin/restaurants/{rid}/ltg-partner",
                headers=admin_headers, json={"is_ltg_partner": False})


# =============================================================================
# 8. Regression — shops list still 200 for shop with no products
# =============================================================================
class TestNoProductShopRegression:
    def test_empty_shop_defaults(self, api, seller_ctx, db):
        sid = f"{RUN_TAG}_shop_empty"
        db.shops.insert_one({
            "id": sid, "seller_id": seller_ctx["id"], "name": "TEST_EmptyShop",
            "area": "Juba", "category": "gen", "verification": "Verified",
            "is_public": True, "is_deleted": False,
            "delivery_mode": "free", "delivery_fee_usd": 0.0,
            "product_sections": [], "created_at": _now(),
        })
        r = api.get(f"{BASE_URL}/api/shops?area=Juba&limit=200")
        assert r.status_code == 200
        empty = next((s for s in r.json() if s["id"] == sid), None)
        assert empty is not None
        assert empty.get("has_active_promo") is False
        assert empty.get("has_wholesale") is False


# =============================================================================
# 9. Regression — sections limit 10 + BOGO promo server-side
# =============================================================================
class TestPromoSectionsRegression:
    def test_bogo_promo_free_qty(self, api, customer_ctx, seller_ctx,
                                 seeded_shops, db):
        pid = f"{RUN_TAG}_p_bogo"
        db.products.insert_one({
            "id": pid, "shop_id": seeded_shops["promo"],
            "seller_id": seller_ctx["id"], "name": "TEST_BOGO",
            "category": "gen", "price_usd": 10.0, "stock": 100,
            "is_active": True, "is_wholesale": False, "min_order_qty": 1,
            "mode": "marketplace", "pricing_tiers": [], "is_deleted": False,
            "promo": {"active": True, "type": "bogo", "value": 0.0,
                      "bogo_min_qty": 2, "starts_at": None, "ends_at": None},
            "created_at": _now(),
        })
        r = api.post(f"{BASE_URL}/api/orders", headers=customer_ctx["headers"], json={
            "items": [{"item_type": "product", "item_id": pid,
                       "name": "irrelevant", "price_usd": 999.0, "quantity": 2}],
            "area": "Juba", "phone": "+211900000002", "note": "",
            "order_kind": "marketplace",
        })
        assert r.status_code == 200, r.text
        assert r.json()["subtotal_usd"] == 10.0

    def test_sections_11_rejected(self, api, seller_ctx, seeded_shops):
        sid = seeded_shops["plain"]
        sections = [{"id": f"sec-{i}", "name": f"S{i}"} for i in range(11)]
        r = api.put(f"{BASE_URL}/api/shops/{sid}",
                    headers=seller_ctx["headers"],
                    json={"name": "TEST_PlainShop", "area": "Juba",
                          "delivery_mode": "free", "delivery_fee_usd": 0.0,
                          "product_sections": sections})
        assert r.status_code == 400
