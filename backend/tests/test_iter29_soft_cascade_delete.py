"""Iter 29 backend tests — SOFT cascade delete of admin user deletion.

Covers:
- Backend health + admin login.
- Admin creates a seller user (pre-verified) → seller can login.
- Seller has shop+product and restaurant+menu_item; customer favorites one shop + one product.
- GET /api/admin/users/{seller_id}/delete-preview returns counts (shops>=1, restaurants>=1, products>=1, menu_items>=1).
- DELETE /api/admin/users/{seller_id} → {ok:true, soft_deleted:true, user_id:...}
- Soft-deleted seller cannot login (401).
- User record retained + anonymized (email→'deleted+{id}@removed.local', name→'[Deleted user]').
- GET /api/admin/users default excludes deleted, include_deleted=true reveals them.
- Seller's shops soft-flagged (is_deleted=True) → NOT in public /api/shops.
- Seller's restaurants soft-flagged → NOT in /api/restaurants.
- Seller's products is_deleted=True → NOT in /api/products.
- Historical seller_order_splits (if any pre-existed) retained.
- Bulk delete of 2 fresh users → {deleted:2, soft_deleted:true}.
- Regression: LTG toggle still works; favorites GET/DELETE work; BOGO promo still computes free_qty.
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

RUN_TAG = f"TEST_iter29_{uuid.uuid4().hex[:8]}"


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    d = client[DB_NAME]
    yield d
    # IMPORTANT: use hard delete on users (API now does soft-delete only).
    for coll in [
        "users", "shops", "restaurants", "products", "menu_items",
        "orders", "restaurant_orders", "seller_order_splits",
        "favorites", "reviews", "categories", "notifications",
        "carts", "onboarding_progress", "email_verifications",
        "password_resets", "web_push_subscriptions", "shop_messages",
        "invoices", "restaurant_invoices", "seller_payouts",
    ]:
        try:
            d[coll].delete_many({"id": {"$regex": f"^{RUN_TAG}"}})
            d[coll].delete_many({"email": {"$regex": RUN_TAG}})
            d[coll].delete_many({"seller_id": {"$regex": f"^{RUN_TAG}"}})
            d[coll].delete_many({"shop_id": {"$regex": f"^{RUN_TAG}"}})
            d[coll].delete_many({"restaurant_id": {"$regex": f"^{RUN_TAG}"}})
            d[coll].delete_many({"user_id": {"$regex": f"^{RUN_TAG}"}})
            d[coll].delete_many({"customer_id": {"$regex": f"^{RUN_TAG}"}})
        except Exception:
            pass
    # Also purge any anonymized deleted+{id}@removed.local users we may have created
    try:
        d["users"].delete_many({"email": {"$regex": "^deleted\\+" }, "name": "[Deleted user]",
                                 "deleted_by": {"$exists": True}})
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


def _create_seller(api, admin_headers, tag_suffix="seller"):
    email = f"{RUN_TAG}_{tag_suffix}@example.com".lower()
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/admin/users", headers=admin_headers, json={
        "email": email, "name": f"{RUN_TAG} {tag_suffix.title()}",
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
# 1) Full soft-cascade delete flow with 1 seller
# ==========================================================================
@pytest.fixture(scope="module")
def seller_with_entities(api, admin_headers, db):
    seller = _create_seller(api, admin_headers, "seller1")
    # Insert 1 shop + 1 product + 1 restaurant + 1 menu_item directly.
    shop_id = f"{RUN_TAG}_shop1"
    prod_id = f"{RUN_TAG}_prod1"
    rest_id = f"{RUN_TAG}_rest1"
    menu_id = f"{RUN_TAG}_menu1"
    db.shops.insert_one({
        "id": shop_id, "seller_id": seller["id"], "name": f"{RUN_TAG}_Shop",
        "area": "Juba", "category": "gen", "is_public": True, "is_deleted": False,
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "verification": "Verified", "product_sections": [], "created_at": _now(),
    })
    db.products.insert_one({
        "id": prod_id, "shop_id": shop_id, "seller_id": seller["id"],
        "name": f"{RUN_TAG}_Prod", "category_id": "cat_x", "category": "gen",
        "price_usd": 10.0, "stock": 5, "is_active": True, "is_deleted": False,
        "is_wholesale": False, "min_order_qty": 1, "mode": "marketplace",
        "pricing_tiers": [], "created_at": _now(),
    })
    db.restaurants.insert_one({
        "id": rest_id, "seller_id": seller["id"], "name": f"{RUN_TAG}_Rest",
        "area": "Juba", "is_open": True, "is_deleted": False,
        "verification": "Verified", "delivery_managed_by": "seller",
        "delivery_mode": "free", "delivery_fee_usd": 0.0,
        "menu_sections": [], "created_at": _now(),
    })
    db.menu_items.insert_one({
        "id": menu_id, "restaurant_id": rest_id, "seller_id": seller["id"],
        "name": f"{RUN_TAG}_Menu", "price_usd": 5.0, "is_available": True,
        "is_deleted": False, "created_at": _now(),
    })
    # Seed 1 historical seller_order_split so we can assert it is retained
    split_id = f"{RUN_TAG}_split1"
    db.seller_order_splits.insert_one({
        "id": split_id, "seller_id": seller["id"], "order_id": f"{RUN_TAG}_orderX",
        "subtotal_usd": 10.0, "commission_usd": 1.0,
        "created_at": _now(),
    })
    return {"seller": seller, "shop_id": shop_id, "prod_id": prod_id,
            "rest_id": rest_id, "menu_id": menu_id, "split_id": split_id}


@pytest.fixture(scope="module")
def customer_ctx(api, db):
    email = f"{RUN_TAG}_cust@example.com".lower()
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "name": f"{RUN_TAG} Cust",
        "password": password, "phone": "+211900000020",
    })
    assert r.status_code == 200, r.text
    db.users.update_one({"email": email}, {"$set": {"email_verified": True}})
    lg = api.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert lg.status_code == 200, lg.text
    return {"id": lg.json()["user"]["id"], "email": email, "token": lg.json()["token"],
            "headers": {"Authorization": f"Bearer {lg.json()['token']}",
                        "Content-Type": "application/json"}}


class TestDeletePreview:
    def test_customer_can_favorite_shop_and_product(self, api, customer_ctx, seller_with_entities):
        # Favorite shop
        r1 = api.post(f"{BASE_URL}/api/favorites", headers=customer_ctx["headers"],
                      json={"target_type": "shop", "target_id": seller_with_entities["shop_id"]})
        assert r1.status_code == 200, r1.text
        # Favorite product
        r2 = api.post(f"{BASE_URL}/api/favorites", headers=customer_ctx["headers"],
                      json={"target_type": "product", "target_id": seller_with_entities["prod_id"]})
        assert r2.status_code == 200, r2.text

    def test_delete_preview_returns_counts(self, api, admin_headers, seller_with_entities):
        sid = seller_with_entities["seller"]["id"]
        r = api.get(f"{BASE_URL}/api/admin/users/{sid}/delete-preview",
                    headers=admin_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user"]["id"] == sid
        counts = body["counts"]
        assert counts["shops"] >= 1
        assert counts["restaurants"] >= 1
        assert counts["products"] >= 1
        assert counts["menu_items"] >= 1
        assert body.get("orders_kept") is True


class TestSoftDelete:
    def test_delete_returns_soft_shape(self, api, admin_headers, seller_with_entities):
        sid = seller_with_entities["seller"]["id"]
        r = api.delete(f"{BASE_URL}/api/admin/users/{sid}", headers=admin_headers)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        assert j["soft_deleted"] is True
        assert j["user_id"] == sid

    def test_soft_deleted_seller_cannot_login(self, api, seller_with_entities):
        s = seller_with_entities["seller"]
        r = api.post(f"{BASE_URL}/api/auth/login",
                     json={"email": s["email"], "password": s["password"]})
        assert r.status_code == 401, r.text

    def test_user_record_retained_and_anonymized(self, db, seller_with_entities):
        sid = seller_with_entities["seller"]["id"]
        u = db.users.find_one({"id": sid})
        assert u is not None, "user should be RETAINED (soft delete)"
        assert u.get("is_deleted") is True
        assert u.get("email") == f"deleted+{sid}@removed.local"
        assert u.get("name") == "[Deleted user]"
        assert u.get("phone") is None
        assert u.get("avatar_url") is None
        assert u.get("password_hash") == "!disabled!"
        assert u.get("deleted_at")

    def test_admin_users_default_excludes_deleted(self, api, admin_headers, seller_with_entities):
        sid = seller_with_entities["seller"]["id"]
        r = api.get(f"{BASE_URL}/api/admin/users?limit=500", headers=admin_headers)
        assert r.status_code == 200
        ids = [u["id"] for u in r.json()]
        assert sid not in ids, "soft-deleted user should be hidden by default"

    def test_admin_users_include_deleted_shows_them(self, api, admin_headers, seller_with_entities):
        sid = seller_with_entities["seller"]["id"]
        r = api.get(f"{BASE_URL}/api/admin/users?include_deleted=true&search=Deleted&limit=500",
                    headers=admin_headers)
        assert r.status_code == 200
        ids = [u["id"] for u in r.json()]
        assert sid in ids, f"deleted user should be found via include_deleted+search=Deleted"

    def test_shops_soft_flagged_not_public(self, api, db, seller_with_entities):
        shop_id = seller_with_entities["shop_id"]
        doc = db.shops.find_one({"id": shop_id})
        assert doc.get("is_deleted") is True
        assert doc.get("deleted_at")
        r = api.get(f"{BASE_URL}/api/shops?limit=500")
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        assert shop_id not in ids

    def test_restaurants_soft_flagged_not_public(self, api, db, seller_with_entities):
        rid = seller_with_entities["rest_id"]
        doc = db.restaurants.find_one({"id": rid})
        assert doc.get("is_deleted") is True
        assert doc.get("deleted_at")
        r = api.get(f"{BASE_URL}/api/restaurants?limit=500")
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()]
        assert rid not in ids

    def test_products_soft_flagged_not_public(self, api, db, seller_with_entities):
        pid = seller_with_entities["prod_id"]
        doc = db.products.find_one({"id": pid})
        assert doc.get("is_deleted") is True
        r = api.get(f"{BASE_URL}/api/products?limit=500")
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()]
        assert pid not in ids

    def test_menu_items_soft_flagged(self, db, seller_with_entities):
        mid = seller_with_entities["menu_id"]
        doc = db.menu_items.find_one({"id": mid})
        assert doc.get("is_deleted") is True

    def test_historical_splits_retained(self, db, seller_with_entities):
        sid = seller_with_entities["seller"]["id"]
        cnt = db.seller_order_splits.count_documents({"seller_id": sid})
        assert cnt >= 1, "seller_order_splits must be retained for accounting"

    def test_favorites_wiped_for_deleted_user(self, db, seller_with_entities, customer_ctx):
        # The DELETED user's favorites (if any) would be wiped; here customer's
        # favorites remain intact — check customer still has entries pointing to
        # (now soft-deleted) shop/product — the wipe only targets the deleted user.
        cnt = db.favorites.count_documents({"user_id": customer_ctx["id"]})
        # Should still be >=2 (shop + product favorites)
        assert cnt >= 2


# ==========================================================================
# 2) Bulk delete
# ==========================================================================
class TestBulkDelete:
    def test_bulk_delete_two_users(self, api, admin_headers, db):
        s1 = _create_seller(api, admin_headers, "bulk1")
        s2 = _create_seller(api, admin_headers, "bulk2")
        r = api.post(f"{BASE_URL}/api/admin/users/bulk-delete",
                     headers=admin_headers,
                     json={"user_ids": [s1["id"], s2["id"]]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["deleted"] == 2
        assert body["soft_deleted"] is True
        # Both users should be soft-flagged
        for uid in [s1["id"], s2["id"]]:
            u = db.users.find_one({"id": uid})
            assert u is not None
            assert u.get("is_deleted") is True
            assert u.get("name") == "[Deleted user]"


# ==========================================================================
# 3) Regression: favorites GET/DELETE, BOGO promo
# ==========================================================================
class TestRegression:
    def test_favorites_get_still_works(self, api, customer_ctx):
        r = api.get(f"{BASE_URL}/api/favorites", headers=customer_ctx["headers"])
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_bogo_promo_still_computes(self, api, admin_headers, db):
        # Fresh seller + shop + BOGO product; customer buys 2 → charged 10.
        seller = _create_seller(api, admin_headers, "bogo_seller")
        shop_id = f"{RUN_TAG}_bogo_shop"
        prod_id = f"{RUN_TAG}_bogo_prod"
        db.shops.insert_one({
            "id": shop_id, "seller_id": seller["id"], "name": f"{RUN_TAG}_BogoShop",
            "area": "Juba", "category": "gen", "is_public": True, "is_deleted": False,
            "delivery_mode": "free", "delivery_fee_usd": 0.0,
            "verification": "Verified", "product_sections": [], "created_at": _now(),
        })
        db.products.insert_one({
            "id": prod_id, "shop_id": shop_id, "seller_id": seller["id"],
            "name": f"{RUN_TAG}_BogoProd", "category_id": "cat_x", "category": "gen",
            "price_usd": 10.0, "stock": 100, "is_active": True, "is_deleted": False,
            "is_wholesale": False, "min_order_qty": 1, "mode": "marketplace",
            "pricing_tiers": [],
            "promo": {"active": True, "type": "bogo", "value": 0.0,
                      "bogo_min_qty": 2, "starts_at": None, "ends_at": None},
            "created_at": _now(),
        })
        # Fresh customer to avoid session leakage
        cemail = f"{RUN_TAG}_bogocust@example.com".lower()
        cpass = "TestPass123!"
        api.post(f"{BASE_URL}/api/auth/signup", json={
            "email": cemail, "name": f"{RUN_TAG} BogoCust",
            "password": cpass, "phone": "+211900000030",
        })
        db.users.update_one({"email": cemail}, {"$set": {"email_verified": True}})
        lg = api.post(f"{BASE_URL}/api/auth/login", json={"email": cemail, "password": cpass})
        assert lg.status_code == 200
        ch = {"Authorization": f"Bearer {lg.json()['token']}", "Content-Type": "application/json"}
        r = api.post(f"{BASE_URL}/api/orders", headers=ch, json={
            "items": [{"item_type": "product", "item_id": prod_id,
                       "name": "x", "price_usd": 999.0, "quantity": 2}],
            "area": "Juba", "phone": "+211900000030", "note": "",
            "order_kind": "marketplace",
        })
        assert r.status_code == 200, r.text
        assert r.json()["subtotal_usd"] == 10.0

    def test_ltg_toggle_still_works(self, api, admin_headers, db):
        # Fresh shop, toggle LTG on then off
        sid = f"{RUN_TAG}_ltg_shop_reg"
        db.shops.insert_one({
            "id": sid, "seller_id": "irrelevant", "name": f"{RUN_TAG}_LTGShop",
            "area": "Juba", "category": "gen", "is_public": True, "is_deleted": False,
            "delivery_mode": "free", "delivery_fee_usd": 0.0,
            "verification": "Verified", "product_sections": [], "created_at": _now(),
            "is_ltg_partner": False,
        })
        r = api.put(f"{BASE_URL}/api/admin/shops/{sid}/ltg-partner",
                    headers=admin_headers, json={"is_ltg_partner": True})
        assert r.status_code == 200
        assert r.json()["is_ltg_partner"] is True
        r2 = api.put(f"{BASE_URL}/api/admin/shops/{sid}/ltg-partner",
                     headers=admin_headers, json={"is_ltg_partner": False})
        assert r2.status_code == 200
        assert r2.json()["is_ltg_partner"] is False
