"""Iter28 backend tests — Regression + happy-path validation.

Covers:
- Backend health, admin login.
- Admin-only LTG toggle for shops & restaurants; non-admin gets 403.
- LTG partner sort priority (LTG first) on /api/shops and /api/restaurants.
- Sections limit (max 10) on shops product_sections and restaurants menu_sections.
- is_promo_section flag round-trips.
- Promo type='bogo' with bogo_min_qty=2 (buy 2 -> 1 free) via /api/orders.
- Promo type='percent' value=10 discount via /api/orders.
- Favorites POST creates; GET returns {favorite_id, target_type, created_at, item}.
- DELETE /api/favorites?target_type=X&target_id=Y returns {ok, deleted}.
- DELETE /api/favorites/{favorite_id} still works.
- Review eligibility: delivery_status='delivered' allows POST /reviews.
- Regression: /api/shops, /api/restaurants, /api/products return 200.
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

RUN_TAG = f"TEST_iter28_{uuid.uuid4().hex[:8]}"


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    d = client[DB_NAME]
    yield d
    for coll in [
        "users", "shops", "restaurants", "products", "menu_items",
        "orders", "restaurant_orders", "seller_order_splits",
        "favorites", "reviews", "categories", "exchange_rates",
    ]:
        d[coll].delete_many({"id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"email": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"seller_id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"shop_id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"restaurant_id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"user_id": {"$regex": f"^{RUN_TAG}"}})
        d[coll].delete_many({"customer_id": {"$regex": f"^{RUN_TAG}"}})
    client.close()


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Block cookie storage — backend prefers cookie over Authorization header,
    # and cross-user logins on same session would overwrite each other.
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
    seller_id = r.json()["user"]["id"]
    lr = api.post(f"{BASE_URL}/api/auth/login",
                  json={"email": email, "password": password})
    assert lr.status_code == 200, lr.text
    tok = lr.json()["token"]
    return {"id": seller_id, "email": email, "token": tok,
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
    assert lg.status_code == 200, lg.text
    tok = lg.json()["token"]
    return {"id": lg.json()["user"]["id"], "email": email, "token": tok,
            "headers": {"Authorization": f"Bearer {tok}",
                        "Content-Type": "application/json"}}


@pytest.fixture(scope="module")
def food_cat(db):
    cid = f"{RUN_TAG}_cat_food"
    db.categories.insert_one({
        "id": cid, "name": "TestFood", "slug": f"{RUN_TAG}_food",
        "group": "restaurant", "created_at": _now(),
    })
    return cid


@pytest.fixture(scope="module")
def shop_cat(db):
    cid = f"{RUN_TAG}_cat_shop"
    db.categories.insert_one({
        "id": cid, "name": "TestShopCat", "slug": f"{RUN_TAG}_shopcat",
        "group": "shop", "created_at": _now(),
    })
    return cid


@pytest.fixture(scope="module")
def ltg_shop_id(db, seller_ctx, shop_cat):
    """Two shops: one LTG one non-LTG (both verified) to check ordering."""
    sid_ltg = f"{RUN_TAG}_shop_ltg"
    sid_reg = f"{RUN_TAG}_shop_reg"
    common = {
        "seller_id": seller_ctx["id"], "area": "Juba", "category": "gen",
        "verification": "Verified", "is_public": True, "is_deleted": False,
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "product_sections": [], "created_at": _now(),
    }
    db.shops.insert_one({**common, "id": sid_ltg, "name": "TEST_LTG_Shop",
                         "is_ltg_partner": False})
    db.shops.insert_one({**common, "id": sid_reg, "name": "TEST_Regular_Shop",
                         "is_ltg_partner": False})
    return {"ltg": sid_ltg, "reg": sid_reg}


@pytest.fixture(scope="module")
def ltg_restaurant_ids(db, seller_ctx):
    rid_ltg = f"{RUN_TAG}_rest_ltg"
    rid_reg = f"{RUN_TAG}_rest_reg"
    common = {
        "seller_id": seller_ctx["id"], "area": "Juba", "is_open": True,
        "is_deleted": False, "verification": "Verified",
        "delivery_managed_by": "seller",
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "menu_sections": [], "created_at": _now(),
    }
    db.restaurants.insert_one({**common, "id": rid_ltg,
                               "name": "TEST_LTG_Rest",
                               "is_ltg_partner": False})
    db.restaurants.insert_one({**common, "id": rid_reg,
                               "name": "TEST_Regular_Rest",
                               "is_ltg_partner": False})
    return {"ltg": rid_ltg, "reg": rid_reg}


# ==========================================================================
# 1) Health + auth
# ==========================================================================
class TestHealthAuth:
    def test_health(self, api):
        r = api.get(f"{BASE_URL}/api/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_admin_login_email(self, api):
        r = api.post(f"{BASE_URL}/api/auth/login",
                     json={"email": "admin@jubasquare.com", "password": "1234"})
        assert r.status_code == 200
        assert "token" in r.json()

    def test_admin_login_username(self, api):
        r = api.post(f"{BASE_URL}/api/auth/login",
                     json={"email": "admin", "password": "1234"})
        assert r.status_code == 200


# ==========================================================================
# 2) Admin LTG toggle — shops
# ==========================================================================
class TestLTGShops:
    def test_toggle_shop_ltg(self, api, admin_headers, ltg_shop_id, db):
        sid = ltg_shop_id["ltg"]
        r = api.put(f"{BASE_URL}/api/admin/shops/{sid}/ltg-partner",
                    headers=admin_headers, json={"is_ltg_partner": True})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        assert j["is_ltg_partner"] is True
        # Persistence check
        doc = db.shops.find_one({"id": sid})
        assert doc["is_ltg_partner"] is True

    def test_toggle_shop_ltg_404(self, api, admin_headers):
        r = api.put(f"{BASE_URL}/api/admin/shops/nonexistent-id/ltg-partner",
                    headers=admin_headers, json={"is_ltg_partner": True})
        assert r.status_code == 404

    def test_non_admin_cannot_toggle_shop_ltg(self, api, seller_ctx, ltg_shop_id):
        sid = ltg_shop_id["ltg"]
        r = api.put(f"{BASE_URL}/api/admin/shops/{sid}/ltg-partner",
                    headers=seller_ctx["headers"], json={"is_ltg_partner": True})
        assert r.status_code == 403

    def test_ltg_shop_appears_first(self, api, ltg_shop_id):
        r = api.get(f"{BASE_URL}/api/shops?area=Juba&limit=200")
        assert r.status_code == 200
        shops = r.json()
        # Find both, LTG must appear before regular.
        ltg_idx = next((i for i, s in enumerate(shops) if s["id"] == ltg_shop_id["ltg"]), -1)
        reg_idx = next((i for i, s in enumerate(shops) if s["id"] == ltg_shop_id["reg"]), -1)
        assert ltg_idx != -1, "LTG shop missing from /api/shops"
        assert reg_idx != -1, "Regular shop missing from /api/shops"
        assert ltg_idx < reg_idx, f"LTG shop must come before non-LTG (ltg={ltg_idx}, reg={reg_idx})"
        # Also validate is_ltg_partner flag
        assert shops[ltg_idx]["is_ltg_partner"] is True

    def test_toggle_shop_ltg_off(self, api, admin_headers, ltg_shop_id):
        # Toggle back off to leave state predictable
        sid = ltg_shop_id["ltg"]
        r = api.put(f"{BASE_URL}/api/admin/shops/{sid}/ltg-partner",
                    headers=admin_headers, json={"is_ltg_partner": False})
        assert r.status_code == 200
        assert r.json()["is_ltg_partner"] is False


# ==========================================================================
# 3) Admin LTG toggle — restaurants
# ==========================================================================
class TestLTGRestaurants:
    def test_toggle_restaurant_ltg(self, api, admin_headers, ltg_restaurant_ids, db):
        rid = ltg_restaurant_ids["ltg"]
        r = api.put(f"{BASE_URL}/api/admin/restaurants/{rid}/ltg-partner",
                    headers=admin_headers, json={"is_ltg_partner": True})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True and j["is_ltg_partner"] is True
        doc = db.restaurants.find_one({"id": rid})
        assert doc["is_ltg_partner"] is True

    def test_non_admin_cannot_toggle_restaurant_ltg(self, api, seller_ctx, ltg_restaurant_ids):
        rid = ltg_restaurant_ids["ltg"]
        r = api.put(f"{BASE_URL}/api/admin/restaurants/{rid}/ltg-partner",
                    headers=seller_ctx["headers"], json={"is_ltg_partner": True})
        assert r.status_code == 403

    def test_ltg_restaurant_appears_first(self, api, ltg_restaurant_ids):
        r = api.get(f"{BASE_URL}/api/restaurants?area=Juba&limit=200")
        assert r.status_code == 200
        rests = r.json()
        ltg_idx = next((i for i, x in enumerate(rests) if x["id"] == ltg_restaurant_ids["ltg"]), -1)
        reg_idx = next((i for i, x in enumerate(rests) if x["id"] == ltg_restaurant_ids["reg"]), -1)
        assert ltg_idx != -1
        assert reg_idx != -1
        assert ltg_idx < reg_idx, f"LTG restaurant must come before non-LTG"


# ==========================================================================
# 4) Sections limit + is_promo_section round-trip
# ==========================================================================
class TestSectionsLimit:
    def test_shop_10_sections_ok(self, api, seller_ctx, db):
        # create a shop first via admin so it's owned by seller
        sid = f"{RUN_TAG}_shop_sections"
        db.shops.insert_one({
            "id": sid, "seller_id": seller_ctx["id"], "name": "TEST_Shop_Sec",
            "area": "Juba", "category": "gen", "is_public": True, "is_deleted": False,
            "delivery_mode": "free", "delivery_fee_usd": 0.0,
            "verification": "Verified", "product_sections": [], "created_at": _now(),
        })
        sections = [
            {"id": f"sec-{i}", "name": f"Section {i}", "sort_order": i,
             "is_promo_section": (i == 0)}
            for i in range(10)
        ]
        r = api.put(f"{BASE_URL}/api/shops/{sid}",
                    headers=seller_ctx["headers"],
                    json={"name": "TEST_Shop_Sec", "area": "Juba",
                          "delivery_mode": "free", "delivery_fee_usd": 0.0,
                          "product_sections": sections})
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["product_sections"]) == 10
        assert body["product_sections"][0]["is_promo_section"] is True
        # Round-trip via GET
        g = api.get(f"{BASE_URL}/api/shops/{sid}")
        assert g.status_code == 200
        assert len(g.json()["product_sections"]) == 10
        assert g.json()["product_sections"][0]["is_promo_section"] is True

    def test_shop_11_sections_rejected(self, api, seller_ctx, db):
        sid = f"{RUN_TAG}_shop_sections"
        sections = [
            {"id": f"sec-{i}", "name": f"Section {i}", "sort_order": i}
            for i in range(11)
        ]
        r = api.put(f"{BASE_URL}/api/shops/{sid}",
                    headers=seller_ctx["headers"],
                    json={"name": "TEST_Shop_Sec", "area": "Juba",
                          "delivery_mode": "free", "delivery_fee_usd": 0.0,
                          "product_sections": sections})
        assert r.status_code == 400
        assert "10" in (r.text)

    def test_restaurant_10_sections_ok(self, api, seller_ctx, ltg_restaurant_ids):
        rid = ltg_restaurant_ids["reg"]
        sections = [
            {"id": f"msec-{i}", "name": f"Menu {i}", "sort_order": i,
             "is_promo_section": (i == 1)}
            for i in range(10)
        ]
        r = api.put(f"{BASE_URL}/api/restaurants/{rid}",
                    headers=seller_ctx["headers"],
                    json={"name": "TEST_Regular_Rest", "area": "Juba",
                          "is_open": True, "delivery_mode": "free",
                          "delivery_fee_usd": 0.0,
                          "menu_sections": sections})
        assert r.status_code == 200, r.text
        assert len(r.json()["menu_sections"]) == 10
        # is_promo_section round-trip
        promo_sections = [s for s in r.json()["menu_sections"] if s["is_promo_section"]]
        assert len(promo_sections) == 1

    def test_restaurant_11_sections_rejected(self, api, seller_ctx, ltg_restaurant_ids):
        rid = ltg_restaurant_ids["reg"]
        sections = [
            {"id": f"msec-{i}", "name": f"Menu {i}"} for i in range(11)
        ]
        r = api.put(f"{BASE_URL}/api/restaurants/{rid}",
                    headers=seller_ctx["headers"],
                    json={"name": "TEST_Regular_Rest", "area": "Juba",
                          "is_open": True, "delivery_mode": "free",
                          "delivery_fee_usd": 0.0,
                          "menu_sections": sections})
        assert r.status_code == 400


# ==========================================================================
# 5) Promo BOGO + Percent enforcement via /api/orders (marketplace)
# ==========================================================================
@pytest.fixture(scope="module")
def bogo_product_id(db, seller_ctx, ltg_shop_id, shop_cat):
    pid = f"{RUN_TAG}_prod_bogo"
    db.products.insert_one({
        "id": pid, "shop_id": ltg_shop_id["reg"],
        "seller_id": seller_ctx["id"], "name": "TEST_BOGO_Prod",
        "category_id": shop_cat, "category": "gen",
        "price_usd": 10.0, "stock": 100, "is_active": True,
        "is_wholesale": False, "min_order_qty": 1,
        "mode": "marketplace", "pricing_tiers": [],
        "promo": {"active": True, "type": "bogo", "value": 0.0,
                  "bogo_min_qty": 2, "starts_at": None, "ends_at": None},
        "created_at": _now(),
    })
    return pid


@pytest.fixture(scope="module")
def percent_product_id(db, seller_ctx, ltg_shop_id, shop_cat):
    pid = f"{RUN_TAG}_prod_pct"
    db.products.insert_one({
        "id": pid, "shop_id": ltg_shop_id["reg"],
        "seller_id": seller_ctx["id"], "name": "TEST_Percent_Prod",
        "category_id": shop_cat, "category": "gen",
        "price_usd": 100.0, "stock": 100, "is_active": True,
        "is_wholesale": False, "min_order_qty": 1,
        "mode": "marketplace", "pricing_tiers": [],
        "promo": {"active": True, "type": "percent", "value": 10.0,
                  "bogo_min_qty": 2, "starts_at": None, "ends_at": None},
        "created_at": _now(),
    })
    return pid


class TestPromoEnforcement:
    def test_bogo_2_qty_grants_1_free(self, api, customer_ctx, bogo_product_id):
        """Buy 2 units of $10 BOGO(min_qty=2) product → line total = 1×$10 = $10."""
        r = api.post(f"{BASE_URL}/api/orders", headers=customer_ctx["headers"], json={
            "items": [{"item_type": "product", "item_id": bogo_product_id,
                       "name": "irrelevant", "price_usd": 999.0,
                       "quantity": 2}],
            "area": "Juba", "phone": "+211900000002", "note": "",
            "order_kind": "marketplace",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        # 2 units, min_qty=2 → 1 free → charge for 1 × 10.0 = 10.0
        assert body["subtotal_usd"] == 10.0, f"expected 10.0 got {body['subtotal_usd']}"
        # returned price_usd is the raw (no percent discount)
        assert body["items"][0]["price_usd"] == 10.0

    def test_percent_promo_discounts(self, api, customer_ctx, percent_product_id):
        r = api.post(f"{BASE_URL}/api/orders", headers=customer_ctx["headers"], json={
            "items": [{"item_type": "product", "item_id": percent_product_id,
                       "name": "irrelevant", "price_usd": 999.0,
                       "quantity": 1}],
            "area": "Juba", "phone": "+211900000002", "note": "",
            "order_kind": "marketplace",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        # 100 - 10% = 90
        assert body["subtotal_usd"] == 90.0, f"expected 90.0 got {body['subtotal_usd']}"
        assert body["items"][0]["price_usd"] == 90.0


# ==========================================================================
# 6) Favorites — POST/GET shape, DELETE by query, DELETE by path
# ==========================================================================
class TestFavorites:
    def test_favorites_create_and_shape(self, api, customer_ctx, bogo_product_id):
        # Add favorite for product
        r = api.post(f"{BASE_URL}/api/favorites", headers=customer_ctx["headers"],
                     json={"target_type": "product", "target_id": bogo_product_id})
        assert r.status_code == 200, r.text
        assert r.json().get("id") or r.json().get("ok")

        # Enriched GET
        g = api.get(f"{BASE_URL}/api/favorites", headers=customer_ctx["headers"])
        assert g.status_code == 200
        favs = g.json()
        assert isinstance(favs, list)
        assert len(favs) >= 1
        entry = next((f for f in favs if f["item"]["id"] == bogo_product_id), None)
        assert entry is not None, f"favorited product not in list: {favs}"
        # Shape check
        assert "favorite_id" in entry
        assert "target_type" in entry
        assert "created_at" in entry
        assert "item" in entry
        assert entry["target_type"] == "product"
        assert entry["item"] is not None
        assert entry["item"]["id"] == bogo_product_id

    def test_favorites_delete_by_query(self, api, customer_ctx, bogo_product_id):
        r = api.delete(
            f"{BASE_URL}/api/favorites",
            headers=customer_ctx["headers"],
            params={"target_type": "product", "target_id": bogo_product_id},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["deleted"] == 1
        # Confirm gone
        g = api.get(f"{BASE_URL}/api/favorites", headers=customer_ctx["headers"])
        assert bogo_product_id not in [f["item"]["id"] for f in g.json() if f.get("item")]

    def test_favorites_delete_by_path(self, api, customer_ctx, percent_product_id):
        # Add
        r = api.post(f"{BASE_URL}/api/favorites", headers=customer_ctx["headers"],
                     json={"target_type": "product", "target_id": percent_product_id})
        assert r.status_code == 200
        fav_id = r.json()["id"]
        # Delete by path
        d = api.delete(f"{BASE_URL}/api/favorites/{fav_id}",
                       headers=customer_ctx["headers"])
        assert d.status_code == 200
        assert d.json()["ok"] is True


# ==========================================================================
# 7) Review eligibility — delivery_status='delivered' OR status='completed'
# ==========================================================================
class TestReviewEligibility:
    def test_review_allowed_when_delivered_but_not_completed(
            self, api, customer_ctx, ltg_restaurant_ids, db):
        rid = ltg_restaurant_ids["reg"]
        oid = f"{RUN_TAG}_order_delivered"
        db.restaurant_orders.insert_one({
            "id": oid, "restaurant_id": rid,
            "customer_id": customer_ctx["id"],
            "customer_name": "T", "customer_phone": "+2110",
            "items": [], "subtotal": 0, "delivery_fee": 0, "total": 0,
            "status": "accepted",           # NOT completed
            "delivery_status": "delivered", # but delivered → should allow
            "created_at": _now(),
        })
        r = api.post(f"{BASE_URL}/api/reviews", headers=customer_ctx["headers"],
                     json={"restaurant_id": rid, "order_id": oid,
                           "rating": 5, "comment": "great!"})
        assert r.status_code == 200, r.text
        assert r.json()["rating"] == 5

    def test_review_rejected_when_neither(self, api, customer_ctx,
                                          ltg_restaurant_ids, db):
        rid = ltg_restaurant_ids["reg"]
        oid = f"{RUN_TAG}_order_pending"
        db.restaurant_orders.insert_one({
            "id": oid, "restaurant_id": rid,
            "customer_id": customer_ctx["id"],
            "customer_name": "T", "customer_phone": "+2110",
            "items": [], "subtotal": 0, "delivery_fee": 0, "total": 0,
            "status": "accepted", "delivery_status": "pending",
            "created_at": _now(),
        })
        r = api.post(f"{BASE_URL}/api/reviews", headers=customer_ctx["headers"],
                     json={"restaurant_id": rid, "order_id": oid,
                           "rating": 4, "comment": "n/a"})
        assert r.status_code == 400


# ==========================================================================
# 8) Regression — list endpoints return 200 with no schema errors
# ==========================================================================
class TestListRegressions:
    def test_shops_200(self, api):
        r = api.get(f"{BASE_URL}/api/shops?limit=50")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_restaurants_200(self, api):
        r = api.get(f"{BASE_URL}/api/restaurants?limit=50")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_products_200(self, api):
        r = api.get(f"{BASE_URL}/api/products?limit=50")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
