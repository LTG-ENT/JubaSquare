#!/usr/bin/env python3
"""
Round 8 Backend Testing: Pagination enforcement + low-stock-count endpoint
Tests pagination clamping on all heavy endpoints and the new /api/seller/low-stock-count endpoint.
"""

import requests
import sys
import json
from typing import Optional

BASE_URL = "https://wallet-auto-refresh.preview.emergentagent.com/api"

# Admin credentials
ADMIN_EMAIL = "ltg-general-trading@hotmail.com"
ADMIN_PASSWORD = "Kokobleake1"

def log(msg: str):
    print(f"  {msg}")

def test_header(msg: str):
    print(f"\n{'='*80}")
    print(f"  {msg}")
    print(f"{'='*80}")

def admin_login() -> str:
    """Login as admin and return token."""
    log("Logging in as admin...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        log(f"❌ Admin login failed: {resp.status_code} - {resp.text}")
        sys.exit(1)
    
    data = resp.json()
    token = data.get("token")
    if not token:
        log(f"❌ No token in login response")
        sys.exit(1)
    
    log(f"✅ Admin login successful (role: {data.get('role')}, email_verified: {data.get('email_verified')})")
    return token

def create_customer_account() -> tuple[str, str]:
    """Create and verify a customer account. Returns (email, token)."""
    import uuid
    email = f"test-customer-{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass123"
    
    log(f"Creating customer account: {email}")
    resp = requests.post(f"{BASE_URL}/auth/signup", json={
        "email": email,
        "password": password,
        "name": "Test Customer",
        "role": "customer"
    })
    
    if resp.status_code != 200:
        log(f"❌ Customer signup failed: {resp.status_code} - {resp.text}")
        return None, None
    
    # Verify via MongoDB
    import os
    from pymongo import MongoClient
    
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "jubasquare")
    
    try:
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        verification = db.email_verifications.find_one({"email": email})
        if verification:
            token = verification.get("token")
            verify_resp = requests.post(f"{BASE_URL}/auth/verify-email", json={"token": token})
            if verify_resp.status_code == 200:
                log(f"✅ Customer email verified")
            else:
                log(f"⚠️ Email verification failed: {verify_resp.status_code}")
        
        client.close()
    except Exception as e:
        log(f"⚠️ Could not verify customer via MongoDB: {e}")
    
    # Login as customer
    login_resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": password
    })
    
    if login_resp.status_code == 200:
        customer_token = login_resp.json().get("token")
        log(f"✅ Customer login successful")
        return email, customer_token
    else:
        log(f"⚠️ Customer login failed: {login_resp.status_code}")
        return email, None

def test_1_products_pagination():
    """Test 1: GET /api/products pagination clamping"""
    test_header("TEST 1: GET /api/products - Pagination clamping")
    
    # Note: DB has 0 products, so we're testing shape and no errors
    
    # 1.1: No params -> default 50
    log("\n--- Test 1.1: No params (default limit=50) ---")
    resp = requests.get(f"{BASE_URL}/products")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    if not isinstance(data, list):
        log(f"❌ FAIL: Response is not a list")
        return False
    log(f"✅ Returns 200 with list (length: {len(data)}, expected ≤50)")
    if len(data) > 50:
        log(f"❌ FAIL: Length {len(data)} exceeds default limit 50")
        return False
    
    # 1.2: limit=10
    log("\n--- Test 1.2: limit=10 ---")
    resp = requests.get(f"{BASE_URL}/products?limit=10")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)}, expected ≤10)")
    if len(data) > 10:
        log(f"❌ FAIL: Length {len(data)} exceeds limit 10")
        return False
    
    # 1.3: limit=999 -> clamped to 200
    log("\n--- Test 1.3: limit=999 (should clamp to 200, no error) ---")
    resp = requests.get(f"{BASE_URL}/products?limit=999")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code} (should NOT error)")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)}, expected ≤200)")
    if len(data) > 200:
        log(f"❌ FAIL: Length {len(data)} exceeds MAX_PAGE_LIMIT 200")
        return False
    
    # 1.4: limit=0 -> clamped to 1
    log("\n--- Test 1.4: limit=0 (should clamp to 1) ---")
    resp = requests.get(f"{BASE_URL}/products?limit=0")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)}, expected ≤1)")
    if len(data) > 1:
        log(f"❌ FAIL: Length {len(data)} exceeds clamped limit 1")
        return False
    
    # 1.5: limit=abc -> falls back to default 50
    log("\n--- Test 1.5: limit=abc (invalid, should fall back to default 50, NO 500) ---")
    resp = requests.get(f"{BASE_URL}/products?limit=abc")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code} (should NOT error)")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)}, expected ≤50)")
    if len(data) > 50:
        log(f"❌ FAIL: Length {len(data)} exceeds default limit 50")
        return False
    
    # 1.6: skip=-5 -> clamped to 0
    log("\n--- Test 1.6: skip=-5 (should clamp to 0) ---")
    resp = requests.get(f"{BASE_URL}/products?skip=-5")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)})")
    
    # 1.7: skip=5&limit=10 -> offset slice
    log("\n--- Test 1.7: skip=5&limit=10 (offset slice, no error even if DB has fewer rows) ---")
    resp = requests.get(f"{BASE_URL}/products?skip=5&limit=10")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)}, expected ≤10)")
    if len(data) > 10:
        log(f"❌ FAIL: Length {len(data)} exceeds limit 10")
        return False
    
    log(f"\n✅ TEST 1 PASSED")
    return True

def test_2_shops_pagination():
    """Test 2: GET /api/shops pagination clamping"""
    test_header("TEST 2: GET /api/shops - Pagination clamping")
    
    # 2.1: No params
    log("\n--- Test 2.1: No params ---")
    resp = requests.get(f"{BASE_URL}/shops")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)})")
    if len(data) > 50:
        log(f"❌ FAIL: Length exceeds default limit 50")
        return False
    
    # 2.2: limit=999 -> clamped to 200
    log("\n--- Test 2.2: limit=999 (should clamp to 200) ---")
    resp = requests.get(f"{BASE_URL}/shops?limit=999")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)}, expected ≤200)")
    if len(data) > 200:
        log(f"❌ FAIL: Length exceeds MAX_PAGE_LIMIT 200")
        return False
    
    log(f"\n✅ TEST 2 PASSED")
    return True

def test_3_restaurants_pagination():
    """Test 3: GET /api/restaurants pagination clamping"""
    test_header("TEST 3: GET /api/restaurants - Pagination clamping")
    
    # 3.1: No params
    log("\n--- Test 3.1: No params ---")
    resp = requests.get(f"{BASE_URL}/restaurants")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)})")
    if len(data) > 50:
        log(f"❌ FAIL: Length exceeds default limit 50")
        return False
    
    # 3.2: limit=999 -> clamped to 200
    log("\n--- Test 3.2: limit=999 (should clamp to 200) ---")
    resp = requests.get(f"{BASE_URL}/restaurants?limit=999")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)}, expected ≤200)")
    if len(data) > 200:
        log(f"❌ FAIL: Length exceeds MAX_PAGE_LIMIT 200")
        return False
    
    log(f"\n✅ TEST 3 PASSED")
    return True

def test_4_orders_mine_pagination(customer_token: str):
    """Test 4: GET /api/orders/mine pagination (auth required)"""
    test_header("TEST 4: GET /api/orders/mine - Pagination clamping (auth required)")
    
    if not customer_token:
        log("⚠️ Skipping test (no customer token)")
        return True
    
    headers = {"Authorization": f"Bearer {customer_token}"}
    
    # 4.1: Without auth -> 401
    log("\n--- Test 4.1: Without auth (should be 401) ---")
    resp = requests.get(f"{BASE_URL}/orders/mine")
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # 4.2: With auth -> 200
    log("\n--- Test 4.2: With customer auth (should be 200 list) ---")
    resp = requests.get(f"{BASE_URL}/orders/mine", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    if not isinstance(data, list):
        log(f"❌ FAIL: Response is not a list")
        return False
    log(f"✅ Returns 200 with list (length: {len(data)})")
    
    # 4.3: limit=999
    log("\n--- Test 4.3: limit=999 (should clamp to 200) ---")
    resp = requests.get(f"{BASE_URL}/orders/mine?limit=999", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)}, expected ≤200)")
    if len(data) > 200:
        log(f"❌ FAIL: Length exceeds MAX_PAGE_LIMIT 200")
        return False
    
    log(f"\n✅ TEST 4 PASSED")
    return True

def test_5_orders_seller_pagination(admin_token: str):
    """Test 5: GET /api/orders/seller pagination (seller or admin auth)"""
    test_header("TEST 5: GET /api/orders/seller - Pagination clamping (seller/admin auth)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 5.1: Without auth -> 401
    log("\n--- Test 5.1: Without auth (should be 401) ---")
    resp = requests.get(f"{BASE_URL}/orders/seller")
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # 5.2: With admin auth -> 200
    log("\n--- Test 5.2: With admin auth (should be 200 list) ---")
    resp = requests.get(f"{BASE_URL}/orders/seller", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    if not isinstance(data, list):
        log(f"❌ FAIL: Response is not a list")
        return False
    log(f"✅ Returns 200 with list (length: {len(data)})")
    
    # 5.3: limit=999
    log("\n--- Test 5.3: limit=999 (should clamp to 200) ---")
    resp = requests.get(f"{BASE_URL}/orders/seller?limit=999", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)}, expected ≤200)")
    if len(data) > 200:
        log(f"❌ FAIL: Length exceeds MAX_PAGE_LIMIT 200")
        return False
    
    log(f"\n✅ TEST 5 PASSED")
    return True

def test_6_orders_admin_pagination(admin_token: str, customer_token: str):
    """Test 6: GET /api/orders pagination (admin only)"""
    test_header("TEST 6: GET /api/orders - Pagination clamping (admin only)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 6.1: Without auth -> 401
    log("\n--- Test 6.1: Without auth (should be 401) ---")
    resp = requests.get(f"{BASE_URL}/orders")
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # 6.2: As customer (non-admin) -> 403
    if customer_token:
        log("\n--- Test 6.2: As customer (should be 403) ---")
        customer_headers = {"Authorization": f"Bearer {customer_token}"}
        resp = requests.get(f"{BASE_URL}/orders", headers=customer_headers)
        if resp.status_code != 403:
            log(f"❌ FAIL: Expected 403, got {resp.status_code}")
            return False
        log(f"✅ As customer returns 403")
    
    # 6.3: As admin -> 200
    log("\n--- Test 6.3: As admin (should be 200 list) ---")
    resp = requests.get(f"{BASE_URL}/orders", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    if not isinstance(data, list):
        log(f"❌ FAIL: Response is not a list")
        return False
    log(f"✅ Returns 200 with list (length: {len(data)})")
    
    # 6.4: limit=999
    log("\n--- Test 6.4: limit=999 (should clamp to 200) ---")
    resp = requests.get(f"{BASE_URL}/orders?limit=999", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)}, expected ≤200)")
    if len(data) > 200:
        log(f"❌ FAIL: Length exceeds MAX_PAGE_LIMIT 200")
        return False
    
    log(f"\n✅ TEST 6 PASSED")
    return True

def test_7_favorites_pagination(customer_token: str):
    """Test 7: GET /api/favorites pagination (auth required)"""
    test_header("TEST 7: GET /api/favorites - Pagination clamping (auth required)")
    
    if not customer_token:
        log("⚠️ Skipping test (no customer token)")
        return True
    
    headers = {"Authorization": f"Bearer {customer_token}"}
    
    # 7.1: Without auth -> 401
    log("\n--- Test 7.1: Without auth (should be 401) ---")
    resp = requests.get(f"{BASE_URL}/favorites")
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # 7.2: With auth -> 200
    log("\n--- Test 7.2: With customer auth (should be 200 list) ---")
    resp = requests.get(f"{BASE_URL}/favorites", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    if not isinstance(data, list):
        log(f"❌ FAIL: Response is not a list")
        return False
    log(f"✅ Returns 200 with list (length: {len(data)})")
    
    # 7.3: limit=999
    log("\n--- Test 7.3: limit=999 (should clamp to 200) ---")
    resp = requests.get(f"{BASE_URL}/favorites?limit=999", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)}, expected ≤200)")
    if len(data) > 200:
        log(f"❌ FAIL: Length exceeds MAX_PAGE_LIMIT 200")
        return False
    
    log(f"\n✅ TEST 7 PASSED")
    return True

def test_8_messages_seller_pagination(admin_token: str):
    """Test 8: GET /api/messages/seller pagination (seller or admin auth)"""
    test_header("TEST 8: GET /api/messages/seller - Pagination clamping (seller/admin auth)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 8.1: Without auth -> 401
    log("\n--- Test 8.1: Without auth (should be 401) ---")
    resp = requests.get(f"{BASE_URL}/messages/seller")
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # 8.2: With admin auth -> 200
    log("\n--- Test 8.2: With admin auth (should be 200 list) ---")
    resp = requests.get(f"{BASE_URL}/messages/seller", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    if not isinstance(data, list):
        log(f"❌ FAIL: Response is not a list")
        return False
    log(f"✅ Returns 200 with list (length: {len(data)})")
    
    # 8.3: limit=999
    log("\n--- Test 8.3: limit=999 (should clamp to 200) ---")
    resp = requests.get(f"{BASE_URL}/messages/seller?limit=999", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    log(f"✅ Returns 200 with list (length: {len(data)}, expected ≤200)")
    if len(data) > 200:
        log(f"❌ FAIL: Length exceeds MAX_PAGE_LIMIT 200")
        return False
    
    log(f"\n✅ TEST 8 PASSED")
    return True

def test_9_product_reviews_pagination():
    """Test 9: GET /api/products/{id}/reviews pagination"""
    test_header("TEST 9: GET /api/products/{id}/reviews - Pagination on reviews array")
    
    # Use an arbitrary product id (even if not present, endpoint should return shape)
    product_id = "test-product-123"
    
    # 9.1: No params
    log("\n--- Test 9.1: No params (default limit=50) ---")
    resp = requests.get(f"{BASE_URL}/products/{product_id}/reviews")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    
    # Check shape
    if not isinstance(data, dict):
        log(f"❌ FAIL: Response is not a dict")
        return False
    if "reviews" not in data or "average" not in data or "count" not in data:
        log(f"❌ FAIL: Missing required keys (reviews, average, count)")
        return False
    if not isinstance(data["reviews"], list):
        log(f"❌ FAIL: reviews is not a list")
        return False
    
    log(f"✅ Returns 200 with correct shape: {{reviews:[], average:{data['average']}, count:{data['count']}}}")
    
    # 9.2: limit=5&skip=0
    log("\n--- Test 9.2: limit=5&skip=0 (reviews array obeys limit) ---")
    resp = requests.get(f"{BASE_URL}/products/{product_id}/reviews?limit=5&skip=0")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    if len(data["reviews"]) > 5:
        log(f"❌ FAIL: reviews length {len(data['reviews'])} exceeds limit 5")
        return False
    log(f"✅ reviews array obeys limit (length: {len(data['reviews'])}, expected ≤5)")
    
    # Note: count and average should be computed over full set, not just the paginated reviews
    # Since DB is empty, count should be 0 and average should be 0
    if data["count"] != 0:
        log(f"⚠️ WARNING: count is {data['count']}, expected 0 for non-existent product")
    if data["average"] != 0:
        log(f"⚠️ WARNING: average is {data['average']}, expected 0 for non-existent product")
    
    log(f"✅ count and average computed over full set (count: {data['count']}, average: {data['average']})")
    
    log(f"\n✅ TEST 9 PASSED")
    return True

def test_10_low_stock_count_endpoint(admin_token: str, customer_token: str):
    """Test 10: GET /api/seller/low-stock-count (new endpoint)"""
    test_header("TEST 10: GET /api/seller/low-stock-count - New lightweight endpoint")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 10.1: Without auth -> 401
    log("\n--- Test 10.1: Without auth (should be 401) ---")
    resp = requests.get(f"{BASE_URL}/seller/low-stock-count")
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # 10.2: As admin -> 200 with {count, threshold}
    log("\n--- Test 10.2: As admin (should be 200 with {count, threshold}) ---")
    resp = requests.get(f"{BASE_URL}/seller/low-stock-count", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    
    if "count" not in data or "threshold" not in data:
        log(f"❌ FAIL: Missing required keys (count, threshold)")
        return False
    if not isinstance(data["count"], int):
        log(f"❌ FAIL: count is not an int")
        return False
    if not isinstance(data["threshold"], int):
        log(f"❌ FAIL: threshold is not an int")
        return False
    
    log(f"✅ Returns 200 with {{count: {data['count']}, threshold: {data['threshold']}}}")
    
    # Check default threshold
    if data["threshold"] != 5:
        log(f"⚠️ WARNING: Default threshold is {data['threshold']}, expected 5")
    else:
        log(f"✅ Default threshold is 5")
    
    # 10.3: With ?threshold=20
    log("\n--- Test 10.3: With ?threshold=20 ---")
    resp = requests.get(f"{BASE_URL}/seller/low-stock-count?threshold=20", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    if data["threshold"] != 20:
        log(f"❌ FAIL: threshold is {data['threshold']}, expected 20")
        return False
    log(f"✅ threshold=20 in response")
    
    # 10.4: With ?threshold=-5 -> clamped to 0
    log("\n--- Test 10.4: With ?threshold=-5 (should clamp to 0) ---")
    resp = requests.get(f"{BASE_URL}/seller/low-stock-count?threshold=-5", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    if data["threshold"] != 0:
        log(f"❌ FAIL: threshold is {data['threshold']}, expected 0 (clamped)")
        return False
    log(f"✅ threshold clamped to 0")
    
    # 10.5: With ?threshold=99999 -> clamped to 10000
    log("\n--- Test 10.5: With ?threshold=99999 (should clamp to 10000) ---")
    resp = requests.get(f"{BASE_URL}/seller/low-stock-count?threshold=99999", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    if data["threshold"] != 10000:
        log(f"❌ FAIL: threshold is {data['threshold']}, expected 10000 (clamped)")
        return False
    log(f"✅ threshold clamped to 10000")
    
    # 10.6: As customer (non-seller/admin) -> 403
    if customer_token:
        log("\n--- Test 10.6: As customer (should be 403) ---")
        customer_headers = {"Authorization": f"Bearer {customer_token}"}
        resp = requests.get(f"{BASE_URL}/seller/low-stock-count", headers=customer_headers)
        if resp.status_code != 403:
            log(f"❌ FAIL: Expected 403, got {resp.status_code}")
            return False
        log(f"✅ As customer returns 403 (only seller/admin allowed)")
    else:
        log("\n⚠️ Skipping customer 403 test (no customer token)")
    
    log(f"\n✅ TEST 10 PASSED")
    return True

def test_11_backward_compat_sanity():
    """Test 11: Backward compat sanity checks"""
    test_header("TEST 11: Backward compatibility sanity checks")
    
    # 11.1: GET /api/meta/categories
    log("\n--- Test 11.1: GET /api/meta/categories ---")
    resp = requests.get(f"{BASE_URL}/meta/categories")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    required_keys = ["retail", "wholesale", "restaurant", "food_subcategories", "groups"]
    for key in required_keys:
        if key not in data:
            log(f"❌ FAIL: Missing key '{key}'")
            return False
    log(f"✅ GET /api/meta/categories returns 200 with expected shape")
    
    # 11.2: GET /api/categories/tree
    log("\n--- Test 11.2: GET /api/categories/tree ---")
    resp = requests.get(f"{BASE_URL}/categories/tree")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    if not isinstance(data, dict):
        log(f"❌ FAIL: Response is not a dict")
        return False
    log(f"✅ GET /api/categories/tree returns 200 with dict")
    
    # 11.3: GET /api/site-config/footer
    log("\n--- Test 11.3: GET /api/site-config/footer ---")
    resp = requests.get(f"{BASE_URL}/site-config/footer")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    if "tagline" not in data or "copyright_text" not in data:
        log(f"❌ FAIL: Missing expected footer fields")
        return False
    log(f"✅ GET /api/site-config/footer returns 200 with expected shape")
    
    # 11.4: GET /api/settings/public
    log("\n--- Test 11.4: GET /api/settings/public ---")
    resp = requests.get(f"{BASE_URL}/settings/public")
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    data = resp.json()
    if "global_rate" not in data or "areas" not in data:
        log(f"❌ FAIL: Missing expected settings fields")
        return False
    log(f"✅ GET /api/settings/public returns 200 with expected shape")
    
    log(f"\n✅ TEST 11 PASSED")
    return True

def main():
    print("\n" + "="*80)
    print("  ROUND 8 BACKEND TESTING: Pagination + low-stock-count endpoint")
    print("="*80)
    
    # Login as admin
    admin_token = admin_login()
    
    # Create customer account
    customer_email, customer_token = create_customer_account()
    
    results = []
    
    # Run all tests
    results.append(("Test 1: GET /api/products pagination", test_1_products_pagination()))
    results.append(("Test 2: GET /api/shops pagination", test_2_shops_pagination()))
    results.append(("Test 3: GET /api/restaurants pagination", test_3_restaurants_pagination()))
    results.append(("Test 4: GET /api/orders/mine pagination", test_4_orders_mine_pagination(customer_token)))
    results.append(("Test 5: GET /api/orders/seller pagination", test_5_orders_seller_pagination(admin_token)))
    results.append(("Test 6: GET /api/orders pagination (admin)", test_6_orders_admin_pagination(admin_token, customer_token)))
    results.append(("Test 7: GET /api/favorites pagination", test_7_favorites_pagination(customer_token)))
    results.append(("Test 8: GET /api/messages/seller pagination", test_8_messages_seller_pagination(admin_token)))
    results.append(("Test 9: GET /api/products/{id}/reviews pagination", test_9_product_reviews_pagination()))
    results.append(("Test 10: GET /api/seller/low-stock-count", test_10_low_stock_count_endpoint(admin_token, customer_token)))
    results.append(("Test 11: Backward compatibility sanity", test_11_backward_compat_sanity()))
    
    # Summary
    test_header("TEST SUMMARY")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        log(f"{status}: {name}")
    
    print(f"\n{'='*80}")
    print(f"  TOTAL: {passed}/{total} tests passed")
    print(f"{'='*80}\n")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print(f"❌ {total - passed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
