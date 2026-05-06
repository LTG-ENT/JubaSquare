"""
JubaSquare Round 3 Production Backend Tests
Tests: Auth flows, production seed, image upload, order emails, admin analytics
"""

import os
import sys
import asyncio
import io
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import requests

# Configuration
BACKEND_URL = "https://publish-ready-34.preview.emergentagent.com/api"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "jubasquare_db"

# Admin credentials (seeded from env)
ADMIN_EMAIL = "ltg-general-trading@hotmail.com"
ADMIN_PASSWORD = "Kokobleake1"

# Test data
TEST_CUSTOMER_EMAIL = "sarah.johnson@example.com"
TEST_CUSTOMER_PASSWORD = "SecurePass123"
TEST_CUSTOMER_NAME = "Sarah Johnson"

TEST_SELLER_EMAIL = "mike.traders@example.com"
TEST_SELLER_PASSWORD = "SellerPass456"
TEST_SELLER_NAME = "Mike's Trading Co"

# MongoDB client
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# Test results
test_results = []


def log_test(name: str, passed: bool, details: str = ""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({"name": name, "passed": passed, "details": details})
    print(f"{status}: {name}")
    if details:
        print(f"  → {details}")


async def get_verification_token(email: str) -> str:
    """Retrieve verification token from MongoDB"""
    rec = await db.email_verifications.find_one({"email": email})
    if not rec:
        raise Exception(f"No verification token found for {email}")
    return rec["token"]


async def get_reset_token(email: str) -> str:
    """Retrieve password reset token from MongoDB"""
    rec = await db.password_resets.find_one({"email": email})
    if not rec:
        raise Exception(f"No reset token found for {email}")
    return rec["token"]


def create_test_image() -> bytes:
    """Create a small valid PNG image (1x1 pixel)"""
    # 1x1 transparent PNG
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d494844520000000100000001"
        "08060000001f15c4890000000a49444154789c6300010000"
        "00050001d5a2f5e90000000049454e44ae426082"
    )


async def test_1_production_seed():
    """Test 1: Production seed check - admin login works, collections are empty"""
    print("\n=== TEST 1: Production Seed Check ===")
    
    # Test 1.1: Admin login works
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            admin_token = data.get("token")
            user = data.get("user", {})
            
            if user.get("role") == "admin" and user.get("email") == ADMIN_EMAIL.lower():
                log_test("1.1 Admin login", True, f"Admin logged in successfully, email_verified={user.get('email_verified', False)}")
            else:
                log_test("1.1 Admin login", False, f"Admin role or email mismatch: {user}")
                return None
        else:
            log_test("1.1 Admin login", False, f"Status {resp.status_code}: {resp.text}")
            return None
    except Exception as e:
        log_test("1.1 Admin login", False, f"Exception: {e}")
        return None
    
    # Test 1.2: GET /api/shops returns empty array
    try:
        resp = requests.get(f"{BACKEND_URL}/shops", timeout=10)
        if resp.status_code == 200:
            shops = resp.json()
            if shops == []:
                log_test("1.2 Shops collection empty", True, "GET /api/shops returned []")
            else:
                log_test("1.2 Shops collection empty", False, f"Expected [], got {len(shops)} shops")
        else:
            log_test("1.2 Shops collection empty", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("1.2 Shops collection empty", False, f"Exception: {e}")
    
    # Test 1.3: GET /api/products returns empty array
    try:
        resp = requests.get(f"{BACKEND_URL}/products", timeout=10)
        if resp.status_code == 200:
            products = resp.json()
            if products == []:
                log_test("1.3 Products collection empty", True, "GET /api/products returned []")
            else:
                log_test("1.3 Products collection empty", False, f"Expected [], got {len(products)} products")
        else:
            log_test("1.3 Products collection empty", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("1.3 Products collection empty", False, f"Exception: {e}")
    
    # Test 1.4: GET /api/restaurants returns empty array
    try:
        resp = requests.get(f"{BACKEND_URL}/restaurants", timeout=10)
        if resp.status_code == 200:
            restaurants = resp.json()
            if restaurants == []:
                log_test("1.4 Restaurants collection empty", True, "GET /api/restaurants returned []")
            else:
                log_test("1.4 Restaurants collection empty", False, f"Expected [], got {len(restaurants)} restaurants")
        else:
            log_test("1.4 Restaurants collection empty", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("1.4 Restaurants collection empty", False, f"Exception: {e}")
    
    return admin_token


async def test_2_signup_verification():
    """Test 2: Signup + email verification gating"""
    print("\n=== TEST 2: Signup + Email Verification ===")
    
    # Test 2.1: Signup customer account
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/signup",
            json={
                "email": TEST_CUSTOMER_EMAIL,
                "password": TEST_CUSTOMER_PASSWORD,
                "name": TEST_CUSTOMER_NAME,
                "role": "customer"
            },
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok") and data.get("email") == TEST_CUSTOMER_EMAIL.lower():
                log_test("2.1 Customer signup", True, f"Account created for {TEST_CUSTOMER_EMAIL}")
            else:
                log_test("2.1 Customer signup", False, f"Unexpected response: {data}")
                return None, None
        else:
            log_test("2.1 Customer signup", False, f"Status {resp.status_code}: {resp.text}")
            return None, None
    except Exception as e:
        log_test("2.1 Customer signup", False, f"Exception: {e}")
        return None, None
    
    # Test 2.2: Try to login before verification (should fail with 403)
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/login",
            json={"email": TEST_CUSTOMER_EMAIL, "password": TEST_CUSTOMER_PASSWORD},
            timeout=10
        )
        if resp.status_code == 403:
            log_test("2.2 Login before verification blocked", True, "Got 403 as expected")
        else:
            log_test("2.2 Login before verification blocked", False, f"Expected 403, got {resp.status_code}")
    except Exception as e:
        log_test("2.2 Login before verification blocked", False, f"Exception: {e}")
    
    # Test 2.3: Fetch verification token from MongoDB
    try:
        token = await get_verification_token(TEST_CUSTOMER_EMAIL.lower())
        log_test("2.3 Verification token in MongoDB", True, f"Token retrieved: {token[:16]}...")
    except Exception as e:
        log_test("2.3 Verification token in MongoDB", False, f"Exception: {e}")
        return None, None
    
    # Test 2.4: Verify email with token
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/verify-email",
            json={"token": token},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                log_test("2.4 Email verification", True, "Email verified successfully")
            else:
                log_test("2.4 Email verification", False, f"Unexpected response: {data}")
                return None, None
        else:
            log_test("2.4 Email verification", False, f"Status {resp.status_code}: {resp.text}")
            return None, None
    except Exception as e:
        log_test("2.4 Email verification", False, f"Exception: {e}")
        return None, None
    
    # Test 2.5: Login now works
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/login",
            json={"email": TEST_CUSTOMER_EMAIL, "password": TEST_CUSTOMER_PASSWORD},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            customer_token = data.get("token")
            user = data.get("user", {})
            if user.get("role") == "customer":
                log_test("2.5 Login after verification", True, f"Customer logged in successfully")
            else:
                log_test("2.5 Login after verification", False, f"Role mismatch: {user}")
                return None, None
        else:
            log_test("2.5 Login after verification", False, f"Status {resp.status_code}: {resp.text}")
            return None, None
    except Exception as e:
        log_test("2.5 Login after verification", False, f"Exception: {e}")
        return None, None
    
    # Test 2.6: Try to verify again with same token (should fail)
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/verify-email",
            json={"token": token},
            timeout=10
        )
        if resp.status_code == 400:
            log_test("2.6 Duplicate verification blocked", True, "Got 400 as expected")
        else:
            log_test("2.6 Duplicate verification blocked", False, f"Expected 400, got {resp.status_code}")
    except Exception as e:
        log_test("2.6 Duplicate verification blocked", False, f"Exception: {e}")
    
    # Test 2.7: Signup with same email (should fail)
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/signup",
            json={
                "email": TEST_CUSTOMER_EMAIL,
                "password": "AnotherPass",
                "name": "Another Name",
                "role": "customer"
            },
            timeout=10
        )
        if resp.status_code == 400:
            log_test("2.7 Duplicate signup blocked", True, "Got 400 as expected")
        else:
            log_test("2.7 Duplicate signup blocked", False, f"Expected 400, got {resp.status_code}")
    except Exception as e:
        log_test("2.7 Duplicate signup blocked", False, f"Exception: {e}")
    
    # Test 2.8: Resend verification for already-verified email (should return generic message)
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/resend-verification",
            json={"email": TEST_CUSTOMER_EMAIL},
            timeout=10
        )
        if resp.status_code == 200:
            log_test("2.8 Resend verification (already verified)", True, "Got 200 with generic message")
        else:
            log_test("2.8 Resend verification (already verified)", False, f"Expected 200, got {resp.status_code}")
    except Exception as e:
        log_test("2.8 Resend verification (already verified)", False, f"Exception: {e}")
    
    # Test 2.9: Signup seller account
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/signup",
            json={
                "email": TEST_SELLER_EMAIL,
                "password": TEST_SELLER_PASSWORD,
                "name": TEST_SELLER_NAME,
                "role": "seller"
            },
            timeout=10
        )
        if resp.status_code == 200:
            log_test("2.9 Seller signup", True, f"Seller account created for {TEST_SELLER_EMAIL}")
        else:
            log_test("2.9 Seller signup", False, f"Status {resp.status_code}: {resp.text}")
            return customer_token, None
    except Exception as e:
        log_test("2.9 Seller signup", False, f"Exception: {e}")
        return customer_token, None
    
    # Test 2.10: Verify seller email
    try:
        seller_token_verify = await get_verification_token(TEST_SELLER_EMAIL.lower())
        resp = requests.post(
            f"{BACKEND_URL}/auth/verify-email",
            json={"token": seller_token_verify},
            timeout=10
        )
        if resp.status_code == 200:
            log_test("2.10 Seller email verification", True, "Seller email verified")
        else:
            log_test("2.10 Seller email verification", False, f"Status {resp.status_code}")
            return customer_token, None
    except Exception as e:
        log_test("2.10 Seller email verification", False, f"Exception: {e}")
        return customer_token, None
    
    # Test 2.11: Seller login
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/login",
            json={"email": TEST_SELLER_EMAIL, "password": TEST_SELLER_PASSWORD},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            seller_token = data.get("token")
            log_test("2.11 Seller login", True, "Seller logged in successfully")
            return customer_token, seller_token
        else:
            log_test("2.11 Seller login", False, f"Status {resp.status_code}")
            return customer_token, None
    except Exception as e:
        log_test("2.11 Seller login", False, f"Exception: {e}")
        return customer_token, None


async def test_3_forgot_reset_password(customer_token: str):
    """Test 3: Forgot + reset password"""
    print("\n=== TEST 3: Forgot + Reset Password ===")
    
    # Test 3.1: Request password reset
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/forgot-password",
            json={"email": TEST_CUSTOMER_EMAIL},
            timeout=10
        )
        if resp.status_code == 200:
            log_test("3.1 Forgot password request", True, "Got 200 with generic message")
        else:
            log_test("3.1 Forgot password request", False, f"Status {resp.status_code}")
            return
    except Exception as e:
        log_test("3.1 Forgot password request", False, f"Exception: {e}")
        return
    
    # Test 3.2: Fetch reset token from MongoDB
    try:
        reset_token = await get_reset_token(TEST_CUSTOMER_EMAIL.lower())
        log_test("3.2 Reset token in MongoDB", True, f"Token retrieved: {reset_token[:16]}...")
    except Exception as e:
        log_test("3.2 Reset token in MongoDB", False, f"Exception: {e}")
        return
    
    # Test 3.3: Reset password with token
    new_password = "NewSecurePass999"
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/reset-password",
            json={"token": reset_token, "new_password": new_password},
            timeout=10
        )
        if resp.status_code == 200:
            log_test("3.3 Reset password", True, "Password reset successfully")
        else:
            log_test("3.3 Reset password", False, f"Status {resp.status_code}: {resp.text}")
            return
    except Exception as e:
        log_test("3.3 Reset password", False, f"Exception: {e}")
        return
    
    # Test 3.4: Login with OLD password (should fail)
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/login",
            json={"email": TEST_CUSTOMER_EMAIL, "password": TEST_CUSTOMER_PASSWORD},
            timeout=10
        )
        if resp.status_code == 401:
            log_test("3.4 Login with old password blocked", True, "Got 401 as expected")
        else:
            log_test("3.4 Login with old password blocked", False, f"Expected 401, got {resp.status_code}")
    except Exception as e:
        log_test("3.4 Login with old password blocked", False, f"Exception: {e}")
    
    # Test 3.5: Login with NEW password (should work)
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/login",
            json={"email": TEST_CUSTOMER_EMAIL, "password": new_password},
            timeout=10
        )
        if resp.status_code == 200:
            log_test("3.5 Login with new password", True, "Login successful with new password")
        else:
            log_test("3.5 Login with new password", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("3.5 Login with new password", False, f"Exception: {e}")
    
    # Test 3.6: Forgot password for non-existent email (should still return 200)
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/forgot-password",
            json={"email": "nonexistent@example.com"},
            timeout=10
        )
        if resp.status_code == 200:
            log_test("3.6 Forgot password (non-existent email)", True, "Got 200 generic message (no enumeration)")
        else:
            log_test("3.6 Forgot password (non-existent email)", False, f"Expected 200, got {resp.status_code}")
    except Exception as e:
        log_test("3.6 Forgot password (non-existent email)", False, f"Exception: {e}")


async def test_4_image_upload(seller_token: str, customer_token: str):
    """Test 4: Image upload"""
    print("\n=== TEST 4: Image Upload ===")
    
    if not seller_token:
        log_test("4.x Image upload tests", False, "Seller token not available")
        return None
    
    # Test 4.1: Upload as seller (should succeed)
    try:
        image_data = create_test_image()
        files = {"file": ("test_product.png", io.BytesIO(image_data), "image/png")}
        headers = {"Authorization": f"Bearer {seller_token}"}
        
        resp = requests.post(
            f"{BACKEND_URL}/upload",
            files=files,
            headers=headers,
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok") and data.get("url"):
                image_url = data["url"]
                log_test("4.1 Upload as seller", True, f"Image uploaded: {image_url}")
            else:
                log_test("4.1 Upload as seller", False, f"Unexpected response: {data}")
                return None
        else:
            log_test("4.1 Upload as seller", False, f"Status {resp.status_code}: {resp.text}")
            return None
    except Exception as e:
        log_test("4.1 Upload as seller", False, f"Exception: {e}")
        return None
    
    # Test 4.2: Fetch uploaded image (should return image bytes)
    try:
        resp = requests.get(image_url, timeout=10)
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
            log_test("4.2 Fetch uploaded image", True, f"Image accessible at {image_url}")
        else:
            log_test("4.2 Fetch uploaded image", False, f"Status {resp.status_code}, content-type: {resp.headers.get('content-type')}")
    except Exception as e:
        log_test("4.2 Fetch uploaded image", False, f"Exception: {e}")
    
    # Test 4.3: Upload as customer (should fail with 403)
    try:
        image_data = create_test_image()
        files = {"file": ("test_customer.png", io.BytesIO(image_data), "image/png")}
        headers = {"Authorization": f"Bearer {customer_token}"}
        
        resp = requests.post(
            f"{BACKEND_URL}/upload",
            files=files,
            headers=headers,
            timeout=10
        )
        
        if resp.status_code == 403:
            log_test("4.3 Upload as customer blocked", True, "Got 403 as expected")
        else:
            log_test("4.3 Upload as customer blocked", False, f"Expected 403, got {resp.status_code}")
    except Exception as e:
        log_test("4.3 Upload as customer blocked", False, f"Exception: {e}")
    
    # Test 4.4: Upload without auth (should fail with 401)
    try:
        image_data = create_test_image()
        files = {"file": ("test_noauth.png", io.BytesIO(image_data), "image/png")}
        
        resp = requests.post(
            f"{BACKEND_URL}/upload",
            files=files,
            timeout=10
        )
        
        if resp.status_code == 401:
            log_test("4.4 Upload without auth blocked", True, "Got 401 as expected")
        else:
            log_test("4.4 Upload without auth blocked", False, f"Expected 401, got {resp.status_code}")
    except Exception as e:
        log_test("4.4 Upload without auth blocked", False, f"Exception: {e}")
    
    # Test 4.5: Upload .txt file (should fail with 400)
    try:
        txt_data = b"This is a text file"
        files = {"file": ("test.txt", io.BytesIO(txt_data), "text/plain")}
        headers = {"Authorization": f"Bearer {seller_token}"}
        
        resp = requests.post(
            f"{BACKEND_URL}/upload",
            files=files,
            headers=headers,
            timeout=10
        )
        
        if resp.status_code == 400:
            log_test("4.5 Upload .txt file blocked", True, "Got 400 as expected (unsupported file type)")
        else:
            log_test("4.5 Upload .txt file blocked", False, f"Expected 400, got {resp.status_code}")
    except Exception as e:
        log_test("4.5 Upload .txt file blocked", False, f"Exception: {e}")
    
    # Test 4.6: Upload file > 5MB (should fail with 413)
    try:
        large_data = b"X" * (6 * 1024 * 1024)  # 6 MB
        files = {"file": ("large.png", io.BytesIO(large_data), "image/png")}
        headers = {"Authorization": f"Bearer {seller_token}"}
        
        resp = requests.post(
            f"{BACKEND_URL}/upload",
            files=files,
            headers=headers,
            timeout=15
        )
        
        if resp.status_code == 413:
            log_test("4.6 Upload large file blocked", True, "Got 413 as expected (file too large)")
        else:
            log_test("4.6 Upload large file blocked", False, f"Expected 413, got {resp.status_code}")
    except Exception as e:
        log_test("4.6 Upload large file blocked", False, f"Exception: {e}")
    
    return image_url


async def test_5_order_emails(seller_token: str, customer_token: str, image_url: str):
    """Test 5: Order emails (no-op OK)"""
    print("\n=== TEST 5: Order Emails ===")
    
    if not seller_token or not customer_token:
        log_test("5.x Order email tests", False, "Seller or customer token not available")
        return
    
    # Test 5.1: Create a shop as seller
    try:
        headers = {"Authorization": f"Bearer {seller_token}"}
        resp = requests.post(
            f"{BACKEND_URL}/shops",
            json={
                "name": "Mike's Electronics Store",
                "description": "Quality electronics and accessories",
                "image_url": image_url or "",
                "area": "Munuki",
                "category": "Electronics & Accessories",
                "kind": "retail"
            },
            headers=headers,
            timeout=10
        )
        
        if resp.status_code == 200:
            shop = resp.json()
            shop_id = shop.get("id")
            log_test("5.1 Create shop", True, f"Shop created: {shop_id}")
        else:
            log_test("5.1 Create shop", False, f"Status {resp.status_code}: {resp.text}")
            return
    except Exception as e:
        log_test("5.1 Create shop", False, f"Exception: {e}")
        return
    
    # Test 5.2: Create a product in the shop
    try:
        headers = {"Authorization": f"Bearer {seller_token}"}
        resp = requests.post(
            f"{BACKEND_URL}/products",
            json={
                "shop_id": shop_id,
                "name": "Wireless Bluetooth Headphones",
                "category": "Electronics & Accessories",
                "price_usd": 45.00,
                "image_url": image_url or "",
                "description": "High-quality wireless headphones with noise cancellation",
                "stock": 50,
                "is_wholesale": False,
                "min_order_qty": 1
            },
            headers=headers,
            timeout=10
        )
        
        if resp.status_code == 200:
            product = resp.json()
            product_id = product.get("id")
            log_test("5.2 Create product", True, f"Product created: {product_id}")
        else:
            log_test("5.2 Create product", False, f"Status {resp.status_code}: {resp.text}")
            return
    except Exception as e:
        log_test("5.2 Create product", False, f"Exception: {e}")
        return
    
    # Test 5.3: Place order as customer (should trigger email calls, but they're no-ops)
    try:
        headers = {"Authorization": f"Bearer {customer_token}"}
        resp = requests.post(
            f"{BACKEND_URL}/orders",
            json={
                "items": [
                    {
                        "item_type": "product",
                        "item_id": product_id,
                        "name": "Wireless Bluetooth Headphones",
                        "price_usd": 45.00,
                        "quantity": 2,
                        "image_url": image_url or "",
                        "sides": []
                    }
                ],
                "area": "Munuki",
                "address": "123 Main Street, Munuki",
                "phone": "+211912345678",
                "note": "Please call before delivery",
                "order_kind": "marketplace"
            },
            headers=headers,
            timeout=10
        )
        
        if resp.status_code in [200, 201]:
            order = resp.json()
            order_id = order.get("id")
            log_test("5.3 Place order (with email calls)", True, f"Order placed: {order_id}, no exceptions from email service")
        else:
            log_test("5.3 Place order (with email calls)", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("5.3 Place order (with email calls)", False, f"Exception: {e}")


async def test_6_admin_analytics(admin_token: str):
    """Test 6: Admin analytics endpoint"""
    print("\n=== TEST 6: Admin Analytics ===")
    
    if not admin_token:
        log_test("6.x Admin analytics tests", False, "Admin token not available")
        return
    
    # Test 6.1: GET /api/admin/analytics as customer (should fail with 403)
    try:
        # Login as customer first
        resp = requests.post(
            f"{BACKEND_URL}/auth/login",
            json={"email": TEST_CUSTOMER_EMAIL, "password": "NewSecurePass999"},
            timeout=10
        )
        if resp.status_code == 200:
            customer_token = resp.json().get("token")
            headers = {"Authorization": f"Bearer {customer_token}"}
            
            resp = requests.get(
                f"{BACKEND_URL}/admin/analytics",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code == 403:
                log_test("6.1 Analytics as customer blocked", True, "Got 403 as expected")
            else:
                log_test("6.1 Analytics as customer blocked", False, f"Expected 403, got {resp.status_code}")
        else:
            log_test("6.1 Analytics as customer blocked", False, "Could not login as customer")
    except Exception as e:
        log_test("6.1 Analytics as customer blocked", False, f"Exception: {e}")
    
    # Test 6.2: GET /api/admin/analytics as admin (should succeed)
    try:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(
            f"{BACKEND_URL}/admin/analytics",
            headers=headers,
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            
            # Validate structure
            required_keys = ["totals", "orders_per_day", "users_per_day", "top_sellers"]
            missing_keys = [k for k in required_keys if k not in data]
            
            if missing_keys:
                log_test("6.2 Analytics structure", False, f"Missing keys: {missing_keys}")
                return
            
            # Validate totals
            totals = data.get("totals", {})
            required_totals = [
                "orders", "revenue_usd", "customers", "sellers", "shops", 
                "products", "pending_orders", "delivered_orders", "pending_shops"
            ]
            missing_totals = [k for k in required_totals if k not in totals]
            
            if missing_totals:
                log_test("6.2 Analytics totals structure", False, f"Missing totals: {missing_totals}")
            else:
                log_test("6.2 Analytics totals structure", True, f"All totals present: orders={totals['orders']}, revenue=${totals['revenue_usd']:.2f}")
            
            # Validate orders_per_day
            orders_per_day = data.get("orders_per_day", [])
            if len(orders_per_day) == 30:
                # Check structure of first item
                if orders_per_day and all(k in orders_per_day[0] for k in ["day", "orders", "revenue"]):
                    log_test("6.3 Analytics orders_per_day", True, f"30 days present with correct structure")
                else:
                    log_test("6.3 Analytics orders_per_day", False, f"Structure mismatch in orders_per_day")
            else:
                log_test("6.3 Analytics orders_per_day", False, f"Expected 30 days, got {len(orders_per_day)}")
            
            # Validate users_per_day
            users_per_day = data.get("users_per_day", [])
            if len(users_per_day) == 30:
                if users_per_day and all(k in users_per_day[0] for k in ["day", "users"]):
                    log_test("6.4 Analytics users_per_day", True, f"30 days present with correct structure")
                else:
                    log_test("6.4 Analytics users_per_day", False, f"Structure mismatch in users_per_day")
            else:
                log_test("6.4 Analytics users_per_day", False, f"Expected 30 days, got {len(users_per_day)}")
            
            # Validate top_sellers
            top_sellers = data.get("top_sellers", [])
            if isinstance(top_sellers, list):
                if len(top_sellers) == 0 or all(k in top_sellers[0] for k in ["seller_id", "name", "revenue_usd"]):
                    log_test("6.5 Analytics top_sellers", True, f"{len(top_sellers)} top sellers with correct structure")
                else:
                    log_test("6.5 Analytics top_sellers", False, f"Structure mismatch in top_sellers")
            else:
                log_test("6.5 Analytics top_sellers", False, f"top_sellers is not a list")
            
        else:
            log_test("6.2 Analytics as admin", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("6.2 Analytics as admin", False, f"Exception: {e}")


async def main():
    """Run all tests"""
    print("=" * 70)
    print("JubaSquare Round 3 Production Backend Tests")
    print("=" * 70)
    
    try:
        # Test 1: Production seed
        admin_token = await test_1_production_seed()
        
        # Test 2: Signup + verification
        customer_token, seller_token = await test_2_signup_verification()
        
        # Test 3: Forgot + reset password
        await test_3_forgot_reset_password(customer_token)
        
        # Test 4: Image upload
        image_url = await test_4_image_upload(seller_token, customer_token)
        
        # Test 5: Order emails
        await test_5_order_emails(seller_token, customer_token, image_url)
        
        # Test 6: Admin analytics
        await test_6_admin_analytics(admin_token)
        
    finally:
        client.close()
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for t in test_results if t["passed"])
    failed = sum(1 for t in test_results if not t["passed"])
    total = len(test_results)
    
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
    
    if failed > 0:
        print("\n❌ FAILED TESTS:")
        for t in test_results:
            if not t["passed"]:
                print(f"  - {t['name']}: {t['details']}")
    
    print("\n" + "=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
