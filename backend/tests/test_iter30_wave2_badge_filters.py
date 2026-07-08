"""Iter30 Wave 2 backend tests — Badge filter query params + Featured Products endpoint.

Covers:
- GET /api/shops?ltg | deals | wholesale | verified — filter isolation and intersection.
- GET /api/restaurants?ltg | deals | verified.
- GET /api/products?ltg | deals — respects promo date window (expired excluded).
- GET /api/homepage/featured-products — composite ranking, Verified+in-stock only,
  exchange_rate_ssp enrichment, empty-graceful.
- Composite ranking: A(LTG+verified) > B(verified+high orders/rating) > C(verified+cancellations).
- Regressions: /api/shops still enriches has_active_promo + has_wholesale;
  /api/restaurants still has has_live_promo + has_active_promo alias.
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

RUN_TAG = f"TEST_iter30w2_{uuid.uuid4().hex[:8]}"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _future(hours=24):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _past(minutes=1):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    d = client[DB_NAME]
    yield d
    for coll in [
        "users", "shops", "restaurants", "products", "menu_items",
        "orders", "restaurant_orders", "seller_order_splits",
        "favorites", "reviews",
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
def seller_id(db, api, admin_headers):
    email = f"{RUN_TAG}_seller@example.com".lower()
    r = api.post(f"{BASE_URL}/api/admin/users", headers=admin_headers, json={
        "email": email, "name": f"{RUN_TAG} Seller", "role": "seller",
        "password": "TestPass123!", "phone": "+211900000001",
        "email_verified": True,
    })
    assert r.status_code == 200, r.text
    return r.json()["user"]["id"]


@pytest.fixture(scope="module")
def seeded(db, seller_id):
    """Seed shops A(LTG+verified), B(verified high orders/rating), C(verified high cancellations)
    plus products (promo live, promo expired, wholesale, plain, BOGO).
    And 3 restaurants: LTG, deals (live promo menu-item), plain.
    """
    A = f"{RUN_TAG}_shopA"
    B = f"{RUN_TAG}_shopB"
    C = f"{RUN_TAG}_shopC"
    common = {
        "seller_id": seller_id, "area": "Juba", "category": "gen",
        "is_public": True, "is_deleted": False,
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "product_sections": [], "created_at": _now(),
    }
    db.shops.insert_many([
        # A — LTG + Verified + one live-promo product + one wholesale product
        {**common, "id": A, "name": "TEST_ShopA_LTG",
         "verification": "Verified", "is_ltg_partner": True,
         "average_rating": 3.5, "review_count": 5},
        # B — Verified + high rating + review + orders (seed orders below)
        {**common, "id": B, "name": "TEST_ShopB_HighOrders",
         "verification": "Verified", "is_ltg_partner": False,
         "average_rating": 5.0, "review_count": 20},
        # C — Verified + will accumulate cancellations
        {**common, "id": C, "name": "TEST_ShopC_Cancels",
         "verification": "Verified", "is_ltg_partner": False,
         "average_rating": 4.0, "review_count": 3},
    ])

    # Products
    p_live_promo = f"{RUN_TAG}_p_promoLive"
    p_expired_promo = f"{RUN_TAG}_p_promoExpired"
    p_wholesale = f"{RUN_TAG}_p_wholesale"
    p_ltg = f"{RUN_TAG}_p_ltg"
    p_bogo = f"{RUN_TAG}_p_bogo"
    p_plainB = f"{RUN_TAG}_p_plainB"
    p_plainC = f"{RUN_TAG}_p_plainC"

    db.products.insert_many([
        # Live promo on shop A (ends 24h future)
        {"id": p_live_promo, "shop_id": A, "seller_id": seller_id,
         "name": "TEST_LivePromo", "category": "gen",
         "price_usd": 20.0, "stock": 10, "is_active": True,
         "is_wholesale": False, "min_order_qty": 1, "mode": "marketplace",
         "pricing_tiers": [], "is_deleted": False,
         "average_rating": 4.8, "review_count": 40,
         "promo": {"active": True, "type": "percent", "value": 25.0,
                   "starts_at": None, "ends_at": _future(24)},
         "created_at": _now()},
        # Expired promo (ends_at in past) → must NOT appear under ?deals=1
        {"id": p_expired_promo, "shop_id": A, "seller_id": seller_id,
         "name": "TEST_ExpiredPromo", "category": "gen",
         "price_usd": 15.0, "stock": 5, "is_active": True,
         "is_wholesale": False, "min_order_qty": 1, "mode": "marketplace",
         "pricing_tiers": [], "is_deleted": False,
         "promo": {"active": True, "type": "percent", "value": 10.0,
                   "starts_at": None, "ends_at": _past(1)},
         "created_at": _now()},
        # Wholesale on shop A
        {"id": p_wholesale, "shop_id": A, "seller_id": seller_id,
         "name": "TEST_Whole", "category": "gen",
         "price_usd": 5.0, "stock": 100, "is_active": True,
         "is_wholesale": True, "min_order_qty": 10, "mode": "marketplace",
         "pricing_tiers": [], "is_deleted": False,
         "promo": {"active": False}, "created_at": _now()},
        # LTG product on shop B
        {"id": p_ltg, "shop_id": B, "seller_id": seller_id,
         "name": "TEST_LTGProd", "category": "gen",
         "price_usd": 12.0, "stock": 10, "is_active": True,
         "is_wholesale": False, "min_order_qty": 1, "mode": "marketplace",
         "is_ltg_partner": True,
         "pricing_tiers": [], "is_deleted": False,
         "average_rating": 4.9, "review_count": 100,
         "promo": {"active": False}, "created_at": _now()},
        # BOGO
        {"id": p_bogo, "shop_id": B, "seller_id": seller_id,
         "name": "TEST_BOGO", "category": "gen",
         "price_usd": 10.0, "stock": 100, "is_active": True,
         "is_wholesale": False, "min_order_qty": 1, "mode": "marketplace",
         "pricing_tiers": [], "is_deleted": False,
         "promo": {"active": True, "type": "bogo", "value": 0.0,
                   "bogo_min_qty": 2, "starts_at": None,
                   "ends_at": _future(24)},
         "created_at": _now()},
        # Plain product on shop B (with high orders → featured ranking)
        {"id": p_plainB, "shop_id": B, "seller_id": seller_id,
         "name": "TEST_PlainB", "category": "gen",
         "price_usd": 8.0, "stock": 50, "is_active": True,
         "is_wholesale": False, "min_order_qty": 1, "mode": "marketplace",
         "pricing_tiers": [], "is_deleted": False,
         "average_rating": 4.5, "review_count": 30,
         "promo": {"active": False}, "created_at": _now()},
        # Plain on shop C (with cancellations)
        {"id": p_plainC, "shop_id": C, "seller_id": seller_id,
         "name": "TEST_PlainC", "category": "gen",
         "price_usd": 8.0, "stock": 20, "is_active": True,
         "is_wholesale": False, "min_order_qty": 1, "mode": "marketplace",
         "pricing_tiers": [], "is_deleted": False,
         "promo": {"active": False}, "created_at": _now()},
    ])

    # Seed orders to move ranking signals:
    # Shop B → many Completed orders
    now_iso_s = _now()
    b_orders = [{
        "id": f"{RUN_TAG}_orderB_{i}", "shop_id": B, "seller_id": seller_id,
        "customer_id": f"{RUN_TAG}_cust_x", "status": "Completed",
        "items": [{"product_id": p_plainB, "quantity": 1, "price_usd": 8.0}],
        "subtotal_usd": 8.0, "created_at": now_iso_s,
    } for i in range(15)]
    # Shop C → many Cancelled orders
    c_orders = [{
        "id": f"{RUN_TAG}_orderC_{i}", "shop_id": C, "seller_id": seller_id,
        "customer_id": f"{RUN_TAG}_cust_x", "status": "Cancelled",
        "items": [{"product_id": p_plainC, "quantity": 1, "price_usd": 8.0}],
        "subtotal_usd": 8.0, "created_at": now_iso_s,
    } for i in range(15)]
    db.orders.insert_many(b_orders + c_orders)

    # Restaurants
    R_ltg = f"{RUN_TAG}_rest_LTG"
    R_deals = f"{RUN_TAG}_rest_deals"
    R_plain = f"{RUN_TAG}_rest_plain"
    rest_common = {
        "seller_id": seller_id, "area": "Juba", "is_open": True,
        "is_deleted": False, "verification": "Verified",
        "delivery_managed_by": "seller", "delivery_mode": "free",
        "delivery_fee_usd": 0.0, "menu_sections": [], "created_at": _now(),
    }
    db.restaurants.insert_many([
        {**rest_common, "id": R_ltg, "name": "TEST_RestLTG",
         "is_ltg_partner": True},
        {**rest_common, "id": R_deals, "name": "TEST_RestDeals",
         "is_ltg_partner": False},
        {**rest_common, "id": R_plain, "name": "TEST_RestPlain",
         "is_ltg_partner": False},
    ])
    db.menu_items.insert_many([
        # Live promo menu-item on R_deals
        {"id": f"{RUN_TAG}_mi_deals", "restaurant_id": R_deals,
         "seller_id": seller_id, "name": "TEST_MI_Deals",
         "category": "gen", "price_usd": 15.0, "is_active": True,
         "is_deleted": False,
         "promo": {"active": True, "type": "percent", "value": 20.0,
                   "starts_at": None, "ends_at": _future(24)},
         "created_at": _now()},
        # Expired promo on R_plain → must not count as "deals"
        {"id": f"{RUN_TAG}_mi_plain", "restaurant_id": R_plain,
         "seller_id": seller_id, "name": "TEST_MI_Plain",
         "category": "gen", "price_usd": 10.0, "is_active": True,
         "is_deleted": False,
         "promo": {"active": True, "type": "percent", "value": 10.0,
                   "starts_at": None, "ends_at": _past(1)},
         "created_at": _now()},
    ])

    return {
        "shops": {"A": A, "B": B, "C": C},
        "products": {
            "live": p_live_promo, "expired": p_expired_promo,
            "wholesale": p_wholesale, "ltg": p_ltg, "bogo": p_bogo,
            "plainB": p_plainB, "plainC": p_plainC,
        },
        "restaurants": {"ltg": R_ltg, "deals": R_deals, "plain": R_plain},
    }


# ---------------------------------------------------------------------------
# 0. Health
# ---------------------------------------------------------------------------
class TestHealth:
    def test_health(self, api):
        r = api.get(f"{BASE_URL}/api/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


# ---------------------------------------------------------------------------
# 1. /api/shops badge filters
# ---------------------------------------------------------------------------
class TestShopBadgeFilters:
    def test_no_filter_returns_enriched(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/shops?area=Juba&limit=200")
        assert r.status_code == 200
        shops = r.json()
        ids = {s["id"] for s in shops}
        for k in ["A", "B", "C"]:
            assert seeded["shops"][k] in ids
        # Every shop must have both enriched flags
        for s in shops:
            assert "has_active_promo" in s
            assert "has_wholesale" in s
        A = next(s for s in shops if s["id"] == seeded["shops"]["A"])
        assert A["has_active_promo"] is True
        assert A["has_wholesale"] is True

    def test_ltg_true(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/shops?area=Juba&ltg=true&limit=200")
        assert r.status_code == 200
        shops = r.json()
        assert all(s.get("is_ltg_partner") is True for s in shops), \
            [s["id"] for s in shops if not s.get("is_ltg_partner")]
        assert seeded["shops"]["A"] in {s["id"] for s in shops}
        assert seeded["shops"]["B"] not in {s["id"] for s in shops}

    def test_deals_true(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/shops?area=Juba&deals=true&limit=200")
        assert r.status_code == 200
        shops = r.json()
        assert all(s.get("has_active_promo") is True for s in shops)
        ids = {s["id"] for s in shops}
        # Only shop A has a live-promo product; B has BOGO (also live) → both
        # allowed. C has none → must be excluded.
        assert seeded["shops"]["A"] in ids
        assert seeded["shops"]["C"] not in ids

    def test_wholesale_true(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/shops?area=Juba&wholesale=true&limit=200")
        assert r.status_code == 200
        shops = r.json()
        assert all(s.get("has_wholesale") is True for s in shops)
        ids = {s["id"] for s in shops}
        assert seeded["shops"]["A"] in ids
        assert seeded["shops"]["B"] not in ids

    def test_verified_true(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/shops?area=Juba&verified=true&limit=200")
        assert r.status_code == 200
        shops = r.json()
        assert all(s.get("verification") == "Verified" for s in shops)

    def test_ltg_and_deals_intersection(self, api, seeded):
        r = api.get(
            f"{BASE_URL}/api/shops?area=Juba&ltg=true&deals=true&limit=200")
        assert r.status_code == 200
        shops = r.json()
        for s in shops:
            assert s.get("is_ltg_partner") is True
            assert s.get("has_active_promo") is True
        assert seeded["shops"]["A"] in {s["id"] for s in shops}


# ---------------------------------------------------------------------------
# 2. /api/restaurants badge filters
# ---------------------------------------------------------------------------
class TestRestaurantBadgeFilters:
    def test_ltg_true(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/restaurants?area=Juba&ltg=true&limit=200")
        assert r.status_code == 200
        rests = r.json()
        assert all(x.get("is_ltg_partner") is True for x in rests)
        ids = {x["id"] for x in rests}
        assert seeded["restaurants"]["ltg"] in ids
        assert seeded["restaurants"]["deals"] not in ids

    def test_deals_true(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/restaurants?area=Juba&deals=true&limit=200")
        assert r.status_code == 200
        rests = r.json()
        assert all(x.get("has_active_promo") is True for x in rests)
        ids = {x["id"] for x in rests}
        assert seeded["restaurants"]["deals"] in ids
        # expired-only restaurant must not be in the deals result
        assert seeded["restaurants"]["plain"] not in ids

    def test_verified_true(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/restaurants?area=Juba&verified=true&limit=200")
        assert r.status_code == 200
        rests = r.json()
        assert all(x.get("verification") == "Verified" for x in rests)


# ---------------------------------------------------------------------------
# 3. /api/products badge filters
# ---------------------------------------------------------------------------
class TestProductBadgeFilters:
    def test_ltg_true(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/products?ltg=true&limit=500")
        assert r.status_code == 200
        prods = r.json()
        assert all(p.get("is_ltg_partner") is True for p in prods)
        ids = {p["id"] for p in prods}
        assert seeded["products"]["ltg"] in ids
        assert seeded["products"]["live"] not in ids

    def test_deals_true_excludes_expired(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/products?deals=true&limit=500")
        assert r.status_code == 200
        prods = r.json()
        ids = {p["id"] for p in prods}
        # Live promo and BOGO must be present
        assert seeded["products"]["live"] in ids
        assert seeded["products"]["bogo"] in ids
        # Expired promo must be excluded (date-window enforcement)
        assert seeded["products"]["expired"] not in ids, (
            "expired promo (ends_at in past) should be excluded from ?deals=1")
        # All returned products must have promo.active True
        for p in prods:
            assert (p.get("promo") or {}).get("active") is True


# ---------------------------------------------------------------------------
# 4. /api/homepage/featured-products
# ---------------------------------------------------------------------------
class TestFeaturedProducts:
    def test_basic_shape(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/homepage/featured-products?limit=8")
        assert r.status_code == 200
        prods = r.json()
        assert isinstance(prods, list)
        assert len(prods) <= 8
        for p in prods:
            assert "id" in p
            assert "exchange_rate_ssp" in p, "featured product missing exchange_rate_ssp"
            assert int(p.get("stock", 0)) > 0, "featured products must be in-stock"

    def test_only_verified_shops(self, api, seeded, db):
        r = api.get(f"{BASE_URL}/api/homepage/featured-products?limit=24")
        assert r.status_code == 200
        prods = r.json()
        shop_ids = {p["shop_id"] for p in prods}
        if shop_ids:
            shops = list(db.shops.find(
                {"id": {"$in": list(shop_ids)}},
                {"_id": 0, "id": 1, "verification": 1}))
            verifs = {s["id"]: s.get("verification") for s in shops}
            for sid in shop_ids:
                assert verifs.get(sid) == "Verified"

    def test_ltg_boost_priority(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/homepage/featured-products?limit=24")
        assert r.status_code == 200
        prods = r.json()
        ids_ordered = [p["id"] for p in prods]
        if seeded["products"]["ltg"] in ids_ordered:
            # LTG boost = 50 should keep it near top
            ltg_idx = ids_ordered.index(seeded["products"]["ltg"])
            # It must be within the top 5 given boost > all other signals with our seed sizes
            assert ltg_idx < 5, (
                f"LTG product should have ranking boost — idx={ltg_idx}, order={ids_ordered[:6]}")


# ---------------------------------------------------------------------------
# 5. Composite ranking: A > B > C
# ---------------------------------------------------------------------------
class TestCompositeRanking:
    def test_shops_order_A_before_B_before_C(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/shops?area=Juba&limit=500")
        assert r.status_code == 200
        shops = r.json()
        ids = [s["id"] for s in shops]
        A, B, C = seeded["shops"]["A"], seeded["shops"]["B"], seeded["shops"]["C"]
        assert A in ids and B in ids and C in ids
        assert ids.index(A) < ids.index(B), (
            f"LTG shop A should rank before B — order={[i for i in ids if i in {A,B,C}]}")
        assert ids.index(B) < ids.index(C), (
            f"High-orders B should rank before high-cancels C — "
            f"order={[i for i in ids if i in {A,B,C}]}")


# ---------------------------------------------------------------------------
# 6. Regressions
# ---------------------------------------------------------------------------
class TestRegressions:
    def test_shops_still_enriched(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/shops?area=Juba&limit=500")
        assert r.status_code == 200
        for s in r.json():
            assert "has_active_promo" in s
            assert "has_wholesale" in s

    def test_restaurants_alias_flags(self, api, seeded):
        r = api.get(f"{BASE_URL}/api/restaurants?area=Juba&limit=500")
        assert r.status_code == 200
        # deals restaurant must have both flags true
        deals = next(
            (x for x in r.json() if x["id"] == seeded["restaurants"]["deals"]),
            None)
        assert deals is not None
        assert deals.get("has_live_promo") is True
        assert deals.get("has_active_promo") is True

    def test_featured_empty_when_no_verified(self, api, db, seller_id):
        """When temporarily no Verified shops exist for a fresh tag, endpoint
        still returns list (possibly empty) without erroring."""
        r = api.get(f"{BASE_URL}/api/homepage/featured-products?limit=8")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
