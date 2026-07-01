"""
JubaSquare backend regression tests.
Covers: meta, auth (login/me/wrong pw/blocked), shops, products, restaurants,
orders (customer/seller/admin), admin shop verify/reject, block-email,
exchange rate, RBAC.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://jubasquare-odoo-v2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@demo.com", "password": "1234"}
SELLER = {"email": "seller@demo.com", "password": "1234"}
CUSTOMER = {"email": "customer@demo.com", "password": "1234"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    return data["token"], data["user"]


@pytest.fixture(scope="session")
def admin_token():
    tok, _ = _login(ADMIN)
    return tok


@pytest.fixture(scope="session")
def seller_token_and_user():
    tok, user = _login(SELLER)
    return tok, user


@pytest.fixture(scope="session")
def customer_token():
    tok, _ = _login(CUSTOMER)
    return tok


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------------- META ----------------
class TestMeta:
    def test_health(self):
        r = requests.get(f"{API}/meta/health", timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_areas(self):
        r = requests.get(f"{API}/meta/areas", timeout=15)
        assert r.status_code == 200
        areas = r.json()
        assert isinstance(areas, list) and len(areas) >= 5
        assert "Munuki" in areas


# ---------------- AUTH ----------------
class TestAuth:
    def test_login_admin(self):
        r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "token" in d and d["user"]["role"] == "admin"
        assert "access_token" in r.cookies

    def test_login_seller(self):
        r = requests.post(f"{API}/auth/login", json=SELLER, timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "seller"

    def test_login_customer(self):
        r = requests.post(f"{API}/auth/login", json=CUSTOMER, timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "customer"

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": "admin@demo.com", "password": "wrong"}, timeout=15)
        assert r.status_code == 401

    def test_me_with_bearer(self, customer_token):
        r = requests.get(f"{API}/auth/me", headers=_h(customer_token), timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == "customer@demo.com"

    def test_me_unauthenticated(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401


# ---------------- PUBLIC LISTINGS ----------------
class TestListings:
    def test_shops_count_and_order(self):
        r = requests.get(f"{API}/shops", timeout=15)
        assert r.status_code == 200
        shops = r.json()
        assert len(shops) >= 5
        # verified before non-verified
        first_non_verified = next((i for i, s in enumerate(shops) if s.get("verification") != "Verified"), len(shops))
        first_verified_after = next((i for i, s in enumerate(shops[first_non_verified:], start=first_non_verified)
                                     if s.get("verification") == "Verified"), None)
        assert first_verified_after is None, "Verified shops must come first"

    def test_shops_filter_electronics(self):
        r = requests.get(f"{API}/shops", params={"category": "Electronics"}, timeout=15)
        assert r.status_code == 200
        for s in r.json():
            assert s["category"] == "Electronics"

    def test_products_count(self):
        r = requests.get(f"{API}/products", timeout=15)
        assert r.status_code == 200
        assert len(r.json()) >= 10

    def test_restaurants(self):
        r = requests.get(f"{API}/restaurants", timeout=15)
        assert r.status_code == 200
        rs = r.json()
        assert len(rs) >= 4
        assert any(x.get("is_open") is False for x in rs)

    def test_restaurant_menu(self):
        rs = requests.get(f"{API}/restaurants", timeout=15).json()
        rid = rs[0]["id"]
        r = requests.get(f"{API}/restaurants/{rid}/menu", timeout=15)
        assert r.status_code == 200
        assert len(r.json()) >= 2


# ---------------- CUSTOMER ORDERS ----------------
class TestCustomerOrders:
    def test_place_order_and_list_mine(self, customer_token):
        prods = requests.get(f"{API}/products", timeout=15).json()
        p = prods[0]
        payload = {
            "items": [{
                "item_type": "product", "item_id": p["id"], "name": p["name"],
                "price_usd": p["price_usd"], "quantity": 2, "image_url": p.get("image_url", ""),
            }],
            "area": "Munuki", "address": "Block 4", "phone": "+211900000000", "order_kind": "marketplace",
        }
        r = requests.post(f"{API}/orders", json=payload, headers=_h(customer_token), timeout=15)
        assert r.status_code == 200
        order = r.json()
        assert order["status"] == "Pending"
        assert order["subtotal_usd"] == round(p["price_usd"] * 2, 2)

        mine = requests.get(f"{API}/orders/mine", headers=_h(customer_token), timeout=15)
        assert mine.status_code == 200
        assert any(o["id"] == order["id"] for o in mine.json())


# ---------------- SELLER FLOW ----------------
class TestSellerFlow:
    def test_seller_shop_product_crud(self, seller_token_and_user):
        tok, _ = seller_token_and_user
        # create shop
        shop_payload = {"name": f"TEST_Shop_{uuid.uuid4().hex[:6]}", "category": "Electronics",
                        "description": "test", "image_url": "", "area": "Munuki"}
        r = requests.post(f"{API}/shops", json=shop_payload, headers=_h(tok), timeout=15)
        assert r.status_code == 200
        shop = r.json()
        assert shop["verification"] == "Pending"
        sid = shop["id"]

        # mine
        mine = requests.get(f"{API}/shops/mine", headers=_h(tok), timeout=15).json()
        assert any(s["id"] == sid for s in mine)

        # create product
        prod_payload = {"shop_id": sid, "name": "TEST_Prod", "category": "Electronics",
                        "price_usd": 10.0, "image_url": "", "description": "t", "stock": 5}
        r = requests.post(f"{API}/products", json=prod_payload, headers=_h(tok), timeout=15)
        assert r.status_code == 200
        pid = r.json()["id"]

        # update product
        prod_payload["price_usd"] = 12.5
        r = requests.put(f"{API}/products/{pid}", json=prod_payload, headers=_h(tok), timeout=15)
        assert r.status_code == 200 and r.json()["price_usd"] == 12.5

        # delete product
        r = requests.delete(f"{API}/products/{pid}", headers=_h(tok), timeout=15)
        assert r.status_code == 200

        # cleanup shop
        r = requests.delete(f"{API}/shops/{sid}", headers=_h(tok), timeout=15)
        assert r.status_code == 200

    def test_exchange_rate(self, seller_token_and_user):
        tok, user = seller_token_and_user
        r = requests.put(f"{API}/exchange-rate", json={"rate": 750}, headers=_h(tok), timeout=15)
        assert r.status_code == 200
        r = requests.get(f"{API}/exchange-rate", params={"seller_id": user["id"]}, timeout=15)
        assert r.status_code == 200 and r.json()["rate"] == 750
        # restore
        requests.put(f"{API}/exchange-rate", json={"rate": 600}, headers=_h(tok), timeout=15)

    def test_seller_orders_endpoint(self, seller_token_and_user):
        tok, _ = seller_token_and_user
        r = requests.get(f"{API}/orders/seller", headers=_h(tok), timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_seller_can_update_order_status(self, seller_token_and_user, customer_token):
        # create an order as customer first
        prods = requests.get(f"{API}/products", timeout=15).json()
        p = prods[0]
        payload = {
            "items": [{"item_type": "product", "item_id": p["id"], "name": p["name"],
                       "price_usd": p["price_usd"], "quantity": 1}],
            "area": "Munuki", "address": "x", "phone": "1", "order_kind": "marketplace",
        }
        order_id = requests.post(f"{API}/orders", json=payload, headers=_h(customer_token), timeout=15).json()["id"]
        tok, _ = seller_token_and_user
        r = requests.put(f"{API}/orders/{order_id}/status", json={"status": "In Progress"},
                         headers=_h(tok), timeout=15)
        assert r.status_code == 200 and r.json()["status"] == "In Progress"


# ---------------- ADMIN ----------------
class TestAdmin:
    def test_verify_and_reject_shop(self, admin_token, seller_token_and_user):
        tok, _ = seller_token_and_user
        sp = {"name": f"TEST_VShop_{uuid.uuid4().hex[:6]}", "category": "Fashion",
              "description": "", "image_url": "", "area": "Atlabara"}
        sid = requests.post(f"{API}/shops", json=sp, headers=_h(tok), timeout=15).json()["id"]

        r = requests.put(f"{API}/admin/shops/{sid}/verify", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200 and r.json()["verification"] == "Verified"
        r = requests.put(f"{API}/admin/shops/{sid}/reject", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200 and r.json()["verification"] == "Rejected"

        requests.delete(f"{API}/shops/{sid}", headers=_h(tok), timeout=15)

    def test_block_unblock_email(self, admin_token):
        email = f"block_{uuid.uuid4().hex[:6]}@test.com"
        # ensure clean
        requests.delete(f"{API}/admin/block-email/{email}", headers=_h(admin_token), timeout=15)
        r = requests.post(f"{API}/admin/block-email", json={"email": email}, headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
        # blocked email login should fail with 403 (no such user but blocked check is first)
        r2 = requests.post(f"{API}/auth/login", json={"email": email, "password": "x"}, timeout=15)
        assert r2.status_code == 403
        # unblock
        r = requests.delete(f"{API}/admin/block-email/{email}", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200

    def test_cannot_block_demo_account(self, admin_token):
        r = requests.post(f"{API}/admin/block-email", json={"email": "admin@demo.com"},
                          headers=_h(admin_token), timeout=15)
        assert r.status_code == 400

    def test_admin_orders_list(self, admin_token):
        r = requests.get(f"{API}/orders", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------- RBAC ----------------
class TestRBAC:
    def test_customer_blocked_from_admin(self, customer_token):
        r = requests.get(f"{API}/orders", headers=_h(customer_token), timeout=15)
        assert r.status_code == 403

    def test_customer_blocked_from_seller_orders(self, customer_token):
        r = requests.get(f"{API}/orders/seller", headers=_h(customer_token), timeout=15)
        assert r.status_code == 403

    def test_customer_blocked_from_admin_block_email(self, customer_token):
        r = requests.post(f"{API}/admin/block-email", json={"email": "x@y.com"},
                          headers=_h(customer_token), timeout=15)
        assert r.status_code == 403


# ---------------- SHOP DELIVERY PRICING ----------------
class TestShopDeliveryPricing:
    def test_shop_delivery_fixed_mode(self, seller_token_and_user):
        """Test shop with fixed delivery fee"""
        tok, _ = seller_token_and_user
        # Get first existing shop
        shops = requests.get(f"{API}/shops/mine", headers=_h(tok), timeout=15).json()
        assert len(shops) > 0, "Seller must have at least one shop"
        shop_id = shops[0]["id"]
        
        # Update shop with fixed delivery mode
        update_payload = {
            "name": shops[0]["name"],
            "category": shops[0].get("category", "General"),
            "description": shops[0].get("description", ""),
            "image_url": shops[0].get("image_url", ""),
            "area": shops[0]["area"],
            "delivery_mode": "fixed",
            "delivery_fee_usd": 3.5
        }
        r = requests.put(f"{API}/shops/{shop_id}", json=update_payload, headers=_h(tok), timeout=15)
        assert r.status_code == 200, f"Failed to update shop: {r.text}"
        
        # Verify GET returns the delivery fields
        r = requests.get(f"{API}/shops/{shop_id}", timeout=15)
        assert r.status_code == 200
        shop = r.json()
        assert shop["delivery_mode"] == "fixed"
        assert shop["delivery_fee_usd"] == 3.5
        
    def test_shop_delivery_per_area_mode(self, seller_token_and_user):
        """Test shop with per-area delivery pricing"""
        tok, _ = seller_token_and_user
        shops = requests.get(f"{API}/shops/mine", headers=_h(tok), timeout=15).json()
        shop_id = shops[0]["id"]
        
        # Update with per_area mode
        update_payload = {
            "name": shops[0]["name"],
            "category": shops[0].get("category", "General"),
            "description": shops[0].get("description", ""),
            "image_url": shops[0].get("image_url", ""),
            "area": shops[0]["area"],
            "delivery_mode": "per_area",
            "delivery_per_area": [
                {"area": "Munuki", "fee_usd": 2.0},
                {"area": "Atlabara", "fee_usd": 5.0}
            ]
        }
        r = requests.put(f"{API}/shops/{shop_id}", json=update_payload, headers=_h(tok), timeout=15)
        assert r.status_code == 200, f"Failed to update shop: {r.text}"
        
        # Verify GET returns the per_area config
        r = requests.get(f"{API}/shops/{shop_id}", timeout=15)
        assert r.status_code == 200
        shop = r.json()
        assert shop["delivery_mode"] == "per_area"
        assert len(shop["delivery_per_area"]) == 2
        assert any(a["area"] == "Munuki" and a["fee_usd"] == 2.0 for a in shop["delivery_per_area"])
        assert any(a["area"] == "Atlabara" and a["fee_usd"] == 5.0 for a in shop["delivery_per_area"])
        
    def test_shop_delivery_free_mode(self, seller_token_and_user):
        """Test shop with free delivery (should clear fee fields)"""
        tok, _ = seller_token_and_user
        shops = requests.get(f"{API}/shops/mine", headers=_h(tok), timeout=15).json()
        shop_id = shops[0]["id"]
        
        # Update with free mode
        update_payload = {
            "name": shops[0]["name"],
            "category": shops[0].get("category", "General"),
            "description": shops[0].get("description", ""),
            "image_url": shops[0].get("image_url", ""),
            "area": shops[0]["area"],
            "delivery_mode": "free"
        }
        r = requests.put(f"{API}/shops/{shop_id}", json=update_payload, headers=_h(tok), timeout=15)
        assert r.status_code == 200, f"Failed to update shop: {r.text}"
        
        # Verify GET returns free mode with zero/empty fees
        r = requests.get(f"{API}/shops/{shop_id}", timeout=15)
        assert r.status_code == 200
        shop = r.json()
        assert shop["delivery_mode"] == "free"
        assert shop.get("delivery_fee_usd", 0) == 0
        assert shop.get("delivery_per_area", []) == []


# ---------------- PRODUCT REVIEWS ----------------
class TestProductReviews:
    def test_get_reviews_empty(self):
        """Test GET reviews for a product with no reviews"""
        prods = requests.get(f"{API}/products", timeout=15).json()
        assert len(prods) > 0
        product_id = prods[0]["id"]
        
        r = requests.get(f"{API}/products/{product_id}/reviews", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "reviews" in data
        assert "average" in data
        assert "count" in data
        assert isinstance(data["reviews"], list)
        
    def test_post_review_as_customer(self, customer_token):
        """Test POST review as customer (should succeed)"""
        prods = requests.get(f"{API}/products", timeout=15).json()
        product_id = prods[0]["id"]
        
        review_payload = {
            "rating": 5,
            "comment": "Excellent product! Very satisfied with my purchase."
        }
        r = requests.post(f"{API}/products/{product_id}/reviews", 
                         json=review_payload, headers=_h(customer_token), timeout=15)
        assert r.status_code == 200, f"Failed to post review: {r.text}"
        review = r.json()
        assert review["rating"] == 5
        assert "Excellent product" in review["comment"]
        assert "id" in review
        assert "user_name" in review
        assert "created_at" in review
        
    def test_post_review_as_seller_fails(self, seller_token_and_user):
        """Test POST review as seller (should fail 403)"""
        tok, _ = seller_token_and_user
        prods = requests.get(f"{API}/products", timeout=15).json()
        product_id = prods[0]["id"]
        
        review_payload = {"rating": 5, "comment": "Test"}
        r = requests.post(f"{API}/products/{product_id}/reviews", 
                         json=review_payload, headers=_h(tok), timeout=15)
        assert r.status_code == 403, "Seller should not be able to post reviews"
        
    def test_post_review_without_auth_fails(self):
        """Test POST review without authentication (should fail 401)"""
        prods = requests.get(f"{API}/products", timeout=15).json()
        product_id = prods[0]["id"]
        
        review_payload = {"rating": 5, "comment": "Test"}
        r = requests.post(f"{API}/products/{product_id}/reviews", 
                         json=review_payload, timeout=15)
        assert r.status_code == 401, "Unauthenticated user should not be able to post reviews"
        
    def test_post_review_invalid_rating(self, customer_token):
        """Test POST review with invalid rating (should fail 422)"""
        prods = requests.get(f"{API}/products", timeout=15).json()
        product_id = prods[0]["id"]
        
        # Test rating > 5
        r = requests.post(f"{API}/products/{product_id}/reviews", 
                         json={"rating": 6, "comment": "Test"}, 
                         headers=_h(customer_token), timeout=15)
        assert r.status_code == 422, "Rating > 5 should fail validation"
        
        # Test rating < 1
        r = requests.post(f"{API}/products/{product_id}/reviews", 
                         json={"rating": 0, "comment": "Test"}, 
                         headers=_h(customer_token), timeout=15)
        assert r.status_code == 422, "Rating < 1 should fail validation"
        
    def test_reviews_average_calculation(self, customer_token):
        """Test that review average is calculated correctly"""
        prods = requests.get(f"{API}/products", timeout=15).json()
        # Find a product with few or no reviews
        product_id = prods[-1]["id"] if len(prods) > 1 else prods[0]["id"]
        
        # Get initial state
        r = requests.get(f"{API}/products/{product_id}/reviews", timeout=15)
        initial_data = r.json()
        initial_count = initial_data["count"]
        
        # Post a 5-star review
        r = requests.post(f"{API}/products/{product_id}/reviews", 
                         json={"rating": 5, "comment": "Great!"}, 
                         headers=_h(customer_token), timeout=15)
        assert r.status_code == 200
        
        # Get reviews and verify average
        r = requests.get(f"{API}/products/{product_id}/reviews", timeout=15)
        data = r.json()
        assert data["count"] == initial_count + 1
        assert len(data["reviews"]) == initial_count + 1
        # Average should reflect the new review
        assert data["average"] > 0
        
    def test_post_review_empty_comment(self, customer_token):
        """Test POST review with empty comment (should succeed)"""
        prods = requests.get(f"{API}/products", timeout=15).json()
        product_id = prods[1]["id"] if len(prods) > 1 else prods[0]["id"]
        
        r = requests.post(f"{API}/products/{product_id}/reviews", 
                         json={"rating": 4, "comment": ""}, 
                         headers=_h(customer_token), timeout=15)
        assert r.status_code == 200, "Empty comment should be allowed"
        review = r.json()
        assert review["rating"] == 4
        
    def test_delete_review_as_owner(self, customer_token):
        """Test DELETE review as the review owner (should succeed)"""
        prods = requests.get(f"{API}/products", timeout=15).json()
        product_id = prods[2]["id"] if len(prods) > 2 else prods[0]["id"]
        
        # Create a review
        r = requests.post(f"{API}/products/{product_id}/reviews", 
                         json={"rating": 3, "comment": "To be deleted"}, 
                         headers=_h(customer_token), timeout=15)
        assert r.status_code == 200
        review_id = r.json()["id"]
        
        # Delete the review
        r = requests.delete(f"{API}/products/{product_id}/reviews/{review_id}", 
                           headers=_h(customer_token), timeout=15)
        assert r.status_code == 200, f"Failed to delete review: {r.text}"
        
    def test_delete_review_as_non_owner_fails(self, customer_token, seller_token_and_user):
        """Test DELETE review as another user (should fail 403)"""
        tok, _ = seller_token_and_user
        prods = requests.get(f"{API}/products", timeout=15).json()
        product_id = prods[3]["id"] if len(prods) > 3 else prods[0]["id"]
        
        # Create a review as customer
        r = requests.post(f"{API}/products/{product_id}/reviews", 
                         json={"rating": 4, "comment": "Customer review"}, 
                         headers=_h(customer_token), timeout=15)
        assert r.status_code == 200
        review_id = r.json()["id"]
        
        # Try to delete as seller (should fail)
        r = requests.delete(f"{API}/products/{product_id}/reviews/{review_id}", 
                           headers=_h(tok), timeout=15)
        assert r.status_code == 403, "Non-owner should not be able to delete review"


# ---------------- ORDER DELIVERY FEE & QUOTE ----------------
class TestOrderDeliveryFee:
    def test_order_quote_with_fixed_delivery(self, customer_token, seller_token_and_user):
        """Test order quote with fixed delivery fee"""
        tok, _ = seller_token_and_user
        
        # Setup: Set a shop to fixed delivery mode
        shops = requests.get(f"{API}/shops/mine", headers=_h(tok), timeout=15).json()
        shop_id = shops[0]["id"]
        shop_update = {
            "name": shops[0]["name"],
            "category": shops[0].get("category", "General"),
            "description": shops[0].get("description", ""),
            "image_url": shops[0].get("image_url", ""),
            "area": shops[0]["area"],
            "delivery_mode": "fixed",
            "delivery_fee_usd": 3.5
        }
        requests.put(f"{API}/shops/{shop_id}", json=shop_update, headers=_h(tok), timeout=15)
        
        # Get a product from this shop
        prods = requests.get(f"{API}/products", params={"shop_id": shop_id}, timeout=15).json()
        assert len(prods) > 0, f"Shop {shop_id} must have products"
        p = prods[0]
        
        # Request quote
        quote_payload = {
            "items": [{
                "item_type": "product",
                "item_id": p["id"],
                "name": p["name"],
                "price_usd": p["price_usd"],
                "quantity": 2,
                "image_url": p.get("image_url", ""),
                "sides": []
            }],
            "area": "Munuki",
            "address": "Test address",
            "phone": "+211900000001",
            "order_kind": "marketplace"
        }
        r = requests.post(f"{API}/orders/quote", json=quote_payload, 
                         headers=_h(customer_token), timeout=15)
        assert r.status_code == 200, f"Quote failed: {r.text}"
        quote = r.json()
        
        # Verify quote structure
        assert "subtotal_usd" in quote
        assert "delivery_fee_usd" in quote
        assert "total_usd" in quote
        assert "delivery_breakdown" in quote
        
        # Verify delivery fee
        assert quote["delivery_fee_usd"] == 3.5
        expected_total = round(p["price_usd"] * 2 + 3.5, 2)
        assert quote["total_usd"] == expected_total
        
        # Verify breakdown
        assert len(quote["delivery_breakdown"]) == 1
        breakdown = quote["delivery_breakdown"][0]
        assert breakdown["shop_id"] == shop_id
        assert breakdown["fee_usd"] == 3.5
        assert breakdown["mode"] == "fixed"
        
    def test_order_quote_with_per_area_delivery_matching(self, customer_token, seller_token_and_user):
        """Test order quote with per-area delivery (matching area)"""
        tok, _ = seller_token_and_user
        
        # Setup: Set shop to per_area mode
        shops = requests.get(f"{API}/shops/mine", headers=_h(tok), timeout=15).json()
        shop_id = shops[0]["id"]
        shop_update = {
            "name": shops[0]["name"],
            "category": shops[0].get("category", "General"),
            "description": shops[0].get("description", ""),
            "image_url": shops[0].get("image_url", ""),
            "area": shops[0]["area"],
            "delivery_mode": "per_area",
            "delivery_per_area": [
                {"area": "Munuki", "fee_usd": 2.0},
                {"area": "Atlabara", "fee_usd": 5.0}
            ]
        }
        requests.put(f"{API}/shops/{shop_id}", json=shop_update, headers=_h(tok), timeout=15)
        
        # Get product
        prods = requests.get(f"{API}/products", params={"shop_id": shop_id}, timeout=15).json()
        p = prods[0]
        
        # Quote for Atlabara (should get 5.0 fee)
        quote_payload = {
            "items": [{
                "item_type": "product",
                "item_id": p["id"],
                "name": p["name"],
                "price_usd": p["price_usd"],
                "quantity": 1,
                "image_url": p.get("image_url", ""),
                "sides": []
            }],
            "area": "Atlabara",
            "address": "Test",
            "phone": "+211900000002",
            "order_kind": "marketplace"
        }
        r = requests.post(f"{API}/orders/quote", json=quote_payload, 
                         headers=_h(customer_token), timeout=15)
        assert r.status_code == 200
        quote = r.json()
        assert quote["delivery_fee_usd"] == 5.0
        
        # Quote for Munuki (should get 2.0 fee)
        quote_payload["area"] = "Munuki"
        r = requests.post(f"{API}/orders/quote", json=quote_payload, 
                         headers=_h(customer_token), timeout=15)
        assert r.status_code == 200
        quote = r.json()
        assert quote["delivery_fee_usd"] == 2.0
        
    def test_order_quote_with_per_area_delivery_unknown_area(self, customer_token, seller_token_and_user):
        """Test order quote with per-area delivery (unknown area should be 0)"""
        tok, _ = seller_token_and_user
        
        shops = requests.get(f"{API}/shops/mine", headers=_h(tok), timeout=15).json()
        shop_id = shops[0]["id"]
        prods = requests.get(f"{API}/products", params={"shop_id": shop_id}, timeout=15).json()
        p = prods[0]
        
        # Quote for unknown area
        quote_payload = {
            "items": [{
                "item_type": "product",
                "item_id": p["id"],
                "name": p["name"],
                "price_usd": p["price_usd"],
                "quantity": 1,
                "image_url": p.get("image_url", ""),
                "sides": []
            }],
            "area": "UnknownArea",
            "address": "Test",
            "phone": "+211900000003",
            "order_kind": "marketplace"
        }
        r = requests.post(f"{API}/orders/quote", json=quote_payload, 
                         headers=_h(customer_token), timeout=15)
        assert r.status_code == 200
        quote = r.json()
        assert quote["delivery_fee_usd"] == 0.0
        
    def test_order_quote_with_free_delivery(self, customer_token, seller_token_and_user):
        """Test order quote with free delivery mode"""
        tok, _ = seller_token_and_user
        
        # Setup: Set shop to free mode
        shops = requests.get(f"{API}/shops/mine", headers=_h(tok), timeout=15).json()
        shop_id = shops[0]["id"]
        shop_update = {
            "name": shops[0]["name"],
            "category": shops[0].get("category", "General"),
            "description": shops[0].get("description", ""),
            "image_url": shops[0].get("image_url", ""),
            "area": shops[0]["area"],
            "delivery_mode": "free"
        }
        requests.put(f"{API}/shops/{shop_id}", json=shop_update, headers=_h(tok), timeout=15)
        
        prods = requests.get(f"{API}/products", params={"shop_id": shop_id}, timeout=15).json()
        p = prods[0]
        
        quote_payload = {
            "items": [{
                "item_type": "product",
                "item_id": p["id"],
                "name": p["name"],
                "price_usd": p["price_usd"],
                "quantity": 1,
                "image_url": p.get("image_url", ""),
                "sides": []
            }],
            "area": "Munuki",
            "address": "Test",
            "phone": "+211900000004",
            "order_kind": "marketplace"
        }
        r = requests.post(f"{API}/orders/quote", json=quote_payload, 
                         headers=_h(customer_token), timeout=15)
        assert r.status_code == 200
        quote = r.json()
        assert quote["delivery_fee_usd"] == 0.0
        
    def test_order_quote_multiple_shops(self, customer_token, seller_token_and_user):
        """Test order quote with items from multiple shops (delivery fees should sum)"""
        tok, _ = seller_token_and_user
        
        # Get all seller shops
        shops = requests.get(f"{API}/shops/mine", headers=_h(tok), timeout=15).json()
        
        # If only one shop, create another
        if len(shops) < 2:
            new_shop = {
                "name": f"TEST_MultiShop_{uuid.uuid4().hex[:6]}",
                "category": "General",
                "description": "Test shop",
                "image_url": "",
                "area": "Munuki",
                "delivery_mode": "fixed",
                "delivery_fee_usd": 2.5
            }
            r = requests.post(f"{API}/shops", json=new_shop, headers=_h(tok), timeout=15)
            assert r.status_code == 200
            new_shop_id = r.json()["id"]
            
            # Create a product in new shop
            prod_payload = {
                "shop_id": new_shop_id,
                "name": "TEST_Product",
                "category": "General",
                "price_usd": 10.0,
                "image_url": "",
                "description": "Test",
                "stock": 10
            }
            r = requests.post(f"{API}/products", json=prod_payload, headers=_h(tok), timeout=15)
            assert r.status_code == 200
            
            shops = requests.get(f"{API}/shops/mine", headers=_h(tok), timeout=15).json()
        
        # Setup two shops with different delivery fees
        shop1_id = shops[0]["id"]
        shop2_id = shops[1]["id"]
        
        # Shop 1: fixed 3.0
        shop1_update = {
            "name": shops[0]["name"],
            "category": shops[0].get("category", "General"),
            "description": shops[0].get("description", ""),
            "image_url": shops[0].get("image_url", ""),
            "area": shops[0]["area"],
            "delivery_mode": "fixed",
            "delivery_fee_usd": 3.0
        }
        requests.put(f"{API}/shops/{shop1_id}", json=shop1_update, headers=_h(tok), timeout=15)
        
        # Shop 2: fixed 2.5
        shop2_update = {
            "name": shops[1]["name"],
            "category": shops[1].get("category", "General"),
            "description": shops[1].get("description", ""),
            "image_url": shops[1].get("image_url", ""),
            "area": shops[1]["area"],
            "delivery_mode": "fixed",
            "delivery_fee_usd": 2.5
        }
        requests.put(f"{API}/shops/{shop2_id}", json=shop2_update, headers=_h(tok), timeout=15)
        
        # Get products from both shops
        prods1 = requests.get(f"{API}/products", params={"shop_id": shop1_id}, timeout=15).json()
        prods2 = requests.get(f"{API}/products", params={"shop_id": shop2_id}, timeout=15).json()
        assert len(prods1) > 0 and len(prods2) > 0
        
        p1 = prods1[0]
        p2 = prods2[0]
        
        # Quote with items from both shops
        quote_payload = {
            "items": [
                {
                    "item_type": "product",
                    "item_id": p1["id"],
                    "name": p1["name"],
                    "price_usd": p1["price_usd"],
                    "quantity": 1,
                    "image_url": p1.get("image_url", ""),
                    "sides": []
                },
                {
                    "item_type": "product",
                    "item_id": p2["id"],
                    "name": p2["name"],
                    "price_usd": p2["price_usd"],
                    "quantity": 1,
                    "image_url": p2.get("image_url", ""),
                    "sides": []
                }
            ],
            "area": "Munuki",
            "address": "Test",
            "phone": "+211900000005",
            "order_kind": "marketplace"
        }
        r = requests.post(f"{API}/orders/quote", json=quote_payload, 
                         headers=_h(customer_token), timeout=15)
        assert r.status_code == 200
        quote = r.json()
        
        # Delivery fee should be sum of both shops
        assert quote["delivery_fee_usd"] == 5.5  # 3.0 + 2.5
        
        # Breakdown should have 2 entries
        assert len(quote["delivery_breakdown"]) == 2
        shop_ids_in_breakdown = {b["shop_id"] for b in quote["delivery_breakdown"]}
        assert shop1_id in shop_ids_in_breakdown
        assert shop2_id in shop_ids_in_breakdown
        
    def test_actual_order_with_delivery_fee(self, customer_token, seller_token_and_user):
        """Test actual order creation includes delivery fee and breakdown"""
        tok, _ = seller_token_and_user
        
        # Setup shop with fixed delivery
        shops = requests.get(f"{API}/shops/mine", headers=_h(tok), timeout=15).json()
        shop_id = shops[0]["id"]
        shop_update = {
            "name": shops[0]["name"],
            "category": shops[0].get("category", "General"),
            "description": shops[0].get("description", ""),
            "image_url": shops[0].get("image_url", ""),
            "area": shops[0]["area"],
            "delivery_mode": "fixed",
            "delivery_fee_usd": 4.0
        }
        requests.put(f"{API}/shops/{shop_id}", json=shop_update, headers=_h(tok), timeout=15)
        
        prods = requests.get(f"{API}/products", params={"shop_id": shop_id}, timeout=15).json()
        p = prods[0]
        
        # Create actual order
        order_payload = {
            "items": [{
                "item_type": "product",
                "item_id": p["id"],
                "name": p["name"],
                "price_usd": p["price_usd"],
                "quantity": 2,
                "image_url": p.get("image_url", ""),
                "sides": []
            }],
            "area": "Munuki",
            "address": "123 Test Street",
            "phone": "+211900000006",
            "order_kind": "marketplace"
        }
        r = requests.post(f"{API}/orders", json=order_payload, 
                         headers=_h(customer_token), timeout=15)
        assert r.status_code == 200, f"Order creation failed: {r.text}"
        order = r.json()
        
        # Verify order has delivery fields
        assert "delivery_fee_usd" in order
        assert "delivery_breakdown" in order
        assert order["delivery_fee_usd"] == 4.0
        
        # Verify total = subtotal + delivery
        expected_subtotal = round(p["price_usd"] * 2, 2)
        expected_total = round(expected_subtotal + 4.0, 2)
        assert order["subtotal_usd"] == expected_subtotal
        assert order["total_usd"] == expected_total
        
        # Verify breakdown
        assert len(order["delivery_breakdown"]) == 1
        assert order["delivery_breakdown"][0]["shop_id"] == shop_id
        assert order["delivery_breakdown"][0]["fee_usd"] == 4.0
        
        # Verify via GET /orders/mine
        r = requests.get(f"{API}/orders/mine", headers=_h(customer_token), timeout=15)
        assert r.status_code == 200
        orders = r.json()
        created_order = next((o for o in orders if o["id"] == order["id"]), None)
        assert created_order is not None
        assert created_order["delivery_fee_usd"] == 4.0
        assert created_order["total_usd"] == expected_total
