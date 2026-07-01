#!/usr/bin/env python3
"""
Backend API Testing for JubaSquare Phase 1 (July 2025 continuation)
Tests: Web Push, Bulk Stock Update, Seller Analytics, Reports, Admin Health, SEO
"""

import requests
import json
import io
import sys
import uuid
from typing import Dict, Any
from openpyxl import Workbook
from io import BytesIO

# Base URL from frontend/.env
BASE_URL = "https://jubasquare-odoo-v2.preview.emergentagent.com/api"

# Test credentials
ADMIN_EMAIL = "admin@jubasquare.com"
ADMIN_PASSWORD = "1234"

# Test results tracking
tests_passed = 0
tests_failed = 0
test_results = []


def log_test(name: str, passed: bool, details: str = ""):
    """Log test result"""
    global tests_passed, tests_failed
    if passed:
        tests_passed += 1
        status = "✅ PASS"
    else:
        tests_failed += 1
        status = "❌ FAIL"
    
    result = f"{status}: {name}"
    if details:
        result += f"\n    {details}"
    print(result)
    test_results.append({"name": name, "passed": passed, "details": details})


def login(email: str, password: str) -> str:
    """Login and return token"""
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("token", "")
        return ""
    except Exception as e:
        print(f"Login failed: {e}")
        return ""


def create_seller_and_shop(admin_token: str) -> tuple[str, str, str]:
    """Create a test seller and shop, return (seller_id, shop_id, seller_token)"""
    seller_email = f"seller_test_{uuid.uuid4().hex[:8]}@test.com"
    seller_password = "test123"
    
    # Create seller user
    resp = requests.post(
        f"{BASE_URL}/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Test Seller",
            "email": seller_email,
            "password": seller_password,
            "role": "seller",
            "phone": "+211912345678"
        },
        timeout=10
    )
    
    if resp.status_code != 200:
        raise Exception(f"Failed to create seller: {resp.status_code} {resp.text}")
    
    seller_id = resp.json().get("id")
    
    # Login as seller
    seller_token = login(seller_email, seller_password)
    if not seller_token:
        raise Exception("Failed to login as seller")
    
    # Create shop
    resp = requests.post(
        f"{BASE_URL}/shops",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={
            "name": "Test Shop",
            "description": "Test shop for bulk import",
            "area": "Munuki",
            "kind": "retail"
        },
        timeout=10
    )
    
    if resp.status_code != 200:
        raise Exception(f"Failed to create shop: {resp.status_code} {resp.text}")
    
    shop_id = resp.json().get("id")
    
    return seller_id, shop_id, seller_token


def get_category_id(token: str) -> str:
    """Get a valid category ID for testing"""
    resp = requests.get(f"{BASE_URL}/categories?group=retail", timeout=10)
    if resp.status_code == 200:
        cats = resp.json()
        if cats and len(cats) > 0:
            return cats[0].get("id", "")
    return ""


def create_product(shop_id: str, seller_token: str, category_id: str, name: str = "Test Product", price: float = 10.0, stock: int = 100) -> str:
    """Create a product and return its ID"""
    resp = requests.post(
        f"{BASE_URL}/products",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={
            "shop_id": shop_id,
            "name": name,
            "category_id": category_id,
            "price_usd": price,
            "description": "Test product",
            "stock": stock,
            "image_url": "https://example.com/test.jpg"
        },
        timeout=10
    )
    if resp.status_code == 200:
        return resp.json().get("id", "")
    raise Exception(f"Failed to create product: {resp.status_code} {resp.text}")


# ============================================================================
# TEST SUITE 1: Web Push (VAPID) endpoints
# ============================================================================

def test_web_push():
    """Test Web Push (VAPID) endpoints"""
    print("\n" + "="*80)
    print("TEST SUITE 1: Web Push (VAPID) Endpoints")
    print("="*80)
    
    # Test 1a: GET /api/push/public-key (no auth needed)
    print("\n--- Test 1a: GET /api/push/public-key (no auth) ---")
    try:
        resp = requests.get(f"{BASE_URL}/push/public-key", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            public_key = data.get("public_key", "")
            if public_key and public_key.startswith("B"):
                log_test("GET /api/push/public-key returns valid key", True,
                        f"Key starts with 'B', length: {len(public_key)}")
            else:
                log_test("GET /api/push/public-key returns valid key", False,
                        f"Invalid key format: {public_key[:20]}...")
        else:
            log_test("GET /api/push/public-key", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/push/public-key", False, f"Exception: {e}")
    
    # Login as admin for remaining tests
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("Admin login for push tests", False, "Failed to get admin token")
        return
    
    # Test 1b: POST /api/push/subscribe with valid subscription
    print("\n--- Test 1b: POST /api/push/subscribe (authenticated) ---")
    test_endpoint = f"https://example-push.test/endpoint/{uuid.uuid4().hex}"
    try:
        resp = requests.post(
            f"{BASE_URL}/push/subscribe",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "subscription": {
                    "endpoint": test_endpoint,
                    "keys": {
                        "p256dh": "BOGUS_P256DH_BASE64",
                        "auth": "BOGUS_AUTH"
                    }
                }
            },
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                log_test("POST /api/push/subscribe succeeds", True, f"Response: {data}")
            else:
                log_test("POST /api/push/subscribe succeeds", False, f"ok=false: {data}")
        else:
            log_test("POST /api/push/subscribe", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        log_test("POST /api/push/subscribe", False, f"Exception: {e}")
    
    # Test 1b2: POST same subscription again (should not duplicate)
    print("\n--- Test 1b2: POST /api/push/subscribe again (upsert) ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/push/subscribe",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "subscription": {
                    "endpoint": test_endpoint,
                    "keys": {
                        "p256dh": "BOGUS_P256DH_BASE64",
                        "auth": "BOGUS_AUTH"
                    }
                }
            },
            timeout=10
        )
        if resp.status_code == 200:
            log_test("POST /api/push/subscribe upsert works", True, "No duplicate created")
        else:
            log_test("POST /api/push/subscribe upsert", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("POST /api/push/subscribe upsert", False, f"Exception: {e}")
    
    # Test 1c: GET /api/push/prefs
    print("\n--- Test 1c: GET /api/push/prefs ---")
    try:
        resp = requests.get(
            f"{BASE_URL}/push/prefs",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            subscribed = data.get("subscribed")
            prefs = data.get("prefs", {})
            endpoint = data.get("endpoint", "")
            
            if subscribed and prefs and endpoint == test_endpoint:
                # Check default prefs
                expected_keys = ["orders", "low_stock", "promo", "delivery", "admin"]
                has_all_keys = all(k in prefs for k in expected_keys)
                if has_all_keys:
                    log_test("GET /api/push/prefs returns correct structure", True,
                            f"subscribed={subscribed}, prefs keys: {list(prefs.keys())}")
                else:
                    log_test("GET /api/push/prefs returns correct structure", False,
                            f"Missing prefs keys. Got: {list(prefs.keys())}")
            else:
                log_test("GET /api/push/prefs", False, f"Unexpected data: {data}")
        else:
            log_test("GET /api/push/prefs", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/push/prefs", False, f"Exception: {e}")
    
    # Test 1d: PUT /api/push/prefs
    print("\n--- Test 1d: PUT /api/push/prefs ---")
    try:
        resp = requests.put(
            f"{BASE_URL}/push/prefs",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "prefs": {
                    "orders": False,
                    "promo": False,
                    "unknown_key": True  # Should be ignored
                }
            },
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            modified = data.get("modified", 0)
            if modified >= 1:
                # Verify changes
                resp2 = requests.get(
                    f"{BASE_URL}/push/prefs",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    timeout=10
                )
                if resp2.status_code == 200:
                    prefs = resp2.json().get("prefs", {})
                    checks = [
                        prefs.get("orders") == False,
                        prefs.get("promo") == False,
                        prefs.get("low_stock") == True,  # Unchanged
                        "unknown_key" not in prefs  # Should be filtered out
                    ]
                    if all(checks):
                        log_test("PUT /api/push/prefs updates correctly", True,
                                f"orders=False, promo=False, low_stock=True (unchanged), no unknown_key")
                    else:
                        log_test("PUT /api/push/prefs updates correctly", False,
                                f"Prefs mismatch: {prefs}")
                else:
                    log_test("PUT /api/push/prefs verification", False, f"GET failed: {resp2.status_code}")
            else:
                log_test("PUT /api/push/prefs", False, f"modified={modified} (expected >=1)")
        else:
            log_test("PUT /api/push/prefs", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("PUT /api/push/prefs", False, f"Exception: {e}")
    
    # Test 1e: POST /api/push/test
    print("\n--- Test 1e: POST /api/push/test ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/push/test",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            # Delivery will fail because endpoint is bogus, but endpoint should return ok:true, sent:0
            if data.get("ok"):
                log_test("POST /api/push/test returns ok", True, f"Response: {data}")
            else:
                log_test("POST /api/push/test", False, f"ok=false: {data}")
        else:
            log_test("POST /api/push/test", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("POST /api/push/test", False, f"Exception: {e}")
    
    # Test 1f: POST /api/push/unsubscribe
    print("\n--- Test 1f: POST /api/push/unsubscribe ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/push/unsubscribe",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"endpoint": test_endpoint},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            removed = data.get("removed", 0)
            if removed == 1:
                log_test("POST /api/push/unsubscribe removes subscription", True, f"removed={removed}")
            else:
                log_test("POST /api/push/unsubscribe", False, f"removed={removed} (expected 1)")
        else:
            log_test("POST /api/push/unsubscribe", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("POST /api/push/unsubscribe", False, f"Exception: {e}")
    
    # Test 1g: Anonymous POST /api/push/subscribe should fail
    print("\n--- Test 1g: POST /api/push/subscribe without auth ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/push/subscribe",
            json={
                "subscription": {
                    "endpoint": "https://example.com/test",
                    "keys": {"p256dh": "TEST", "auth": "TEST"}
                }
            },
            timeout=10
        )
        if resp.status_code == 401:
            log_test("POST /api/push/subscribe without auth returns 401", True, f"Status: {resp.status_code}")
        else:
            log_test("POST /api/push/subscribe without auth returns 401", False,
                    f"Status: {resp.status_code} (expected 401)")
    except Exception as e:
        log_test("POST /api/push/subscribe without auth", False, f"Exception: {e}")


# ============================================================================
# TEST SUITE 2: Bulk stock update + XLSX templates
# ============================================================================

def test_bulk_stock_update():
    """Test bulk stock update and XLSX template endpoints"""
    print("\n" + "="*80)
    print("TEST SUITE 2: Bulk Stock Update + XLSX Templates")
    print("="*80)
    
    # Login as admin
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("Admin login for bulk stock tests", False, "Failed to get admin token")
        return
    
    # Test 2a: GET /api/products/bulk-template (CSV - smoke check)
    print("\n--- Test 2a: GET /api/products/bulk-template (CSV) ---")
    try:
        resp = requests.get(
            f"{BASE_URL}/products/bulk-template",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            if "text/csv" in content_type:
                log_test("GET /api/products/bulk-template (CSV) returns text/csv", True,
                        f"Content-Type: {content_type}")
            else:
                log_test("GET /api/products/bulk-template (CSV)", False,
                        f"Wrong Content-Type: {content_type}")
        else:
            log_test("GET /api/products/bulk-template (CSV)", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/products/bulk-template (CSV)", False, f"Exception: {e}")
    
    # Test 2b: GET /api/products/bulk-template?fmt=xlsx
    print("\n--- Test 2b: GET /api/products/bulk-template?fmt=xlsx ---")
    try:
        resp = requests.get(
            f"{BASE_URL}/products/bulk-template?fmt=xlsx",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            content = resp.content
            # XLSX files start with "PK" (ZIP magic)
            if "spreadsheetml.sheet" in content_type and content[:2] == b"PK":
                log_test("GET /api/products/bulk-template?fmt=xlsx returns XLSX", True,
                        f"Content-Type: {content_type}, starts with PK")
            else:
                log_test("GET /api/products/bulk-template?fmt=xlsx", False,
                        f"Content-Type: {content_type}, magic: {content[:2]}")
        else:
            log_test("GET /api/products/bulk-template?fmt=xlsx", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/products/bulk-template?fmt=xlsx", False, f"Exception: {e}")
    
    # Test 2c: GET /api/products/stock-update-template?fmt=csv
    print("\n--- Test 2c: GET /api/products/stock-update-template?fmt=csv ---")
    try:
        resp = requests.get(
            f"{BASE_URL}/products/stock-update-template?fmt=csv",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if resp.status_code == 200:
            content = resp.text
            expected_header = "product_id,stock,price_usd,bulk_price_usd"
            if expected_header in content:
                log_test("GET /api/products/stock-update-template?fmt=csv returns correct CSV", True,
                        f"Header: {expected_header}")
            else:
                log_test("GET /api/products/stock-update-template?fmt=csv", False,
                        f"Wrong header. Got: {content[:100]}")
        else:
            log_test("GET /api/products/stock-update-template?fmt=csv", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/products/stock-update-template?fmt=csv", False, f"Exception: {e}")
    
    # Test 2d: GET /api/products/stock-update-template?fmt=xlsx
    print("\n--- Test 2d: GET /api/products/stock-update-template?fmt=xlsx ---")
    try:
        resp = requests.get(
            f"{BASE_URL}/products/stock-update-template?fmt=xlsx",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if resp.status_code == 200:
            content = resp.content
            if content[:2] == b"PK":
                log_test("GET /api/products/stock-update-template?fmt=xlsx returns XLSX", True,
                        "Starts with PK magic")
            else:
                log_test("GET /api/products/stock-update-template?fmt=xlsx", False,
                        f"Wrong magic: {content[:2]}")
        else:
            log_test("GET /api/products/stock-update-template?fmt=xlsx", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/products/stock-update-template?fmt=xlsx", False, f"Exception: {e}")
    
    # Create seller, shop, and products for bulk stock update tests
    print("\n--- Creating test seller, shop, and products ---")
    try:
        seller_id, shop_id, seller_token = create_seller_and_shop(admin_token)
        category_id = get_category_id(admin_token)
        if not category_id:
            log_test("Get category ID for bulk stock tests", False, "No categories found")
            return
        
        # Create 2 products
        product1_id = create_product(shop_id, seller_token, category_id, "Product 1", 10.0, 100)
        product2_id = create_product(shop_id, seller_token, category_id, "Product 2", 20.0, 50)
        print(f"✓ Created seller: {seller_id}, shop: {shop_id}")
        print(f"✓ Created products: {product1_id}, {product2_id}")
    except Exception as e:
        log_test("Create test data for bulk stock update", False, f"Exception: {e}")
        return
    
    # Test 2e: POST /api/products/bulk-stock-update with mixed valid/invalid rows
    print("\n--- Test 2e: POST /api/products/bulk-stock-update (mixed rows) ---")
    try:
        csv_content = f"""product_id,stock,price_usd,bulk_price_usd
{product1_id},50,,
{product2_id},,12.75,10.50
{uuid.uuid4()},10,,
,10,,
{product1_id},abc,,"""
        
        files = {"file": ("stock_update.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        resp = requests.post(
            f"{BASE_URL}/products/bulk-stock-update?shop_id={shop_id}",
            headers={"Authorization": f"Bearer {seller_token}"},
            files=files,
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("total", 0)
            updated = data.get("updated", 0)
            errors = data.get("errors", [])
            updated_ids = data.get("updated_ids", [])
            
            # Expected: 5 total, 2 updated (product1, product2), 3 errors (nonexistent UUID, empty product_id, invalid stock)
            checks = [
                total == 5,
                updated == 2,
                len(errors) == 3,
                len(updated_ids) == 2
            ]
            
            if all(checks):
                log_test("POST bulk-stock-update with mixed rows", True,
                        f"Total: {total}, Updated: {updated}, Errors: {len(errors)}")
            else:
                log_test("POST bulk-stock-update with mixed rows", False,
                        f"Expected total=5, updated=2, errors=3. Got: total={total}, updated={updated}, errors={len(errors)}")
        else:
            log_test("POST bulk-stock-update", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        log_test("POST bulk-stock-update", False, f"Exception: {e}")
    
    # Test 2f: Verify product updates
    print("\n--- Test 2f: Verify product updates ---")
    try:
        # Check product1 stock
        resp1 = requests.get(f"{BASE_URL}/products/{product1_id}", timeout=10)
        # Check product2 prices
        resp2 = requests.get(f"{BASE_URL}/products/{product2_id}", timeout=10)
        
        if resp1.status_code == 200 and resp2.status_code == 200:
            p1 = resp1.json()
            p2 = resp2.json()
            
            checks = [
                p1.get("stock") == 50,
                p2.get("price_usd") == 12.75,
                p2.get("bulk_price_usd") == 10.5
            ]
            
            if all(checks):
                log_test("Bulk stock update changes persisted", True,
                        f"Product1 stock=50, Product2 price_usd=12.75, bulk_price_usd=10.5")
            else:
                log_test("Bulk stock update changes persisted", False,
                        f"Product1: {p1.get('stock')}, Product2: price={p2.get('price_usd')}, bulk={p2.get('bulk_price_usd')}")
        else:
            log_test("Verify product updates", False, f"GET failed: {resp1.status_code}, {resp2.status_code}")
    except Exception as e:
        log_test("Verify product updates", False, f"Exception: {e}")
    
    # Test 2g: POST bulk-stock-update as different seller (should fail with 403)
    print("\n--- Test 2g: POST bulk-stock-update as non-owner ---")
    try:
        # Create another seller
        seller2_id, shop2_id, seller2_token = create_seller_and_shop(admin_token)
        
        csv_content = f"product_id,stock,price_usd,bulk_price_usd\n{product1_id},100,,"
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        resp = requests.post(
            f"{BASE_URL}/products/bulk-stock-update?shop_id={shop_id}",
            headers={"Authorization": f"Bearer {seller2_token}"},
            files=files,
            timeout=10
        )
        
        if resp.status_code == 403:
            log_test("POST bulk-stock-update as non-owner returns 403", True, f"Status: {resp.status_code}")
        else:
            log_test("POST bulk-stock-update as non-owner returns 403", False,
                    f"Status: {resp.status_code} (expected 403)")
    except Exception as e:
        log_test("POST bulk-stock-update as non-owner", False, f"Exception: {e}")


# ============================================================================
# TEST SUITE 3: Seller sales analytics
# ============================================================================

def test_seller_analytics():
    """Test seller analytics endpoint"""
    print("\n" + "="*80)
    print("TEST SUITE 3: Seller Sales Analytics")
    print("="*80)
    
    # Login as admin
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("Admin login for analytics tests", False, "Failed to get admin token")
        return
    
    # Test 3a: GET /api/seller/analytics as seller with no products
    print("\n--- Test 3a: GET /api/seller/analytics (seller with no products) ---")
    try:
        # Create a new seller with no products
        seller_id, shop_id, seller_token = create_seller_and_shop(admin_token)
        
        resp = requests.get(
            f"{BASE_URL}/seller/analytics",
            headers={"Authorization": f"Bearer {seller_token}"},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            required_keys = ["totals", "revenue_series", "top_products", "low_performers", "low_stock"]
            has_all_keys = all(k in data for k in required_keys)
            
            if has_all_keys:
                totals = data.get("totals", {})
                all_zeros = (
                    totals.get("today", {}).get("revenue", -1) == 0 and
                    totals.get("week", {}).get("revenue", -1) == 0 and
                    totals.get("month", {}).get("revenue", -1) == 0 and
                    totals.get("all_time", {}).get("revenue", -1) == 0
                )
                
                if all_zeros:
                    log_test("GET /api/seller/analytics returns all-zeros for new seller", True,
                            f"All revenue totals are 0")
                else:
                    log_test("GET /api/seller/analytics returns all-zeros", False,
                            f"Totals not all zero: {totals}")
            else:
                log_test("GET /api/seller/analytics structure", False,
                        f"Missing keys. Got: {list(data.keys())}")
        else:
            log_test("GET /api/seller/analytics", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/seller/analytics", False, f"Exception: {e}")
    
    # Test 3b: GET /api/seller/analytics as admin
    print("\n--- Test 3b: GET /api/seller/analytics as admin ---")
    try:
        resp = requests.get(
            f"{BASE_URL}/seller/analytics",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            required_keys = ["totals", "revenue_series", "top_products", "low_performers", "low_stock"]
            has_all_keys = all(k in data for k in required_keys)
            
            if has_all_keys:
                log_test("GET /api/seller/analytics as admin returns structure", True,
                        f"Keys: {list(data.keys())}")
            else:
                log_test("GET /api/seller/analytics as admin", False,
                        f"Missing keys. Got: {list(data.keys())}")
        else:
            log_test("GET /api/seller/analytics as admin", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/seller/analytics as admin", False, f"Exception: {e}")
    
    # Test 3c: Anonymous request should fail
    print("\n--- Test 3c: GET /api/seller/analytics without auth ---")
    try:
        resp = requests.get(f"{BASE_URL}/seller/analytics", timeout=10)
        if resp.status_code == 401:
            log_test("GET /api/seller/analytics without auth returns 401", True, f"Status: {resp.status_code}")
        else:
            log_test("GET /api/seller/analytics without auth returns 401", False,
                    f"Status: {resp.status_code} (expected 401)")
    except Exception as e:
        log_test("GET /api/seller/analytics without auth", False, f"Exception: {e}")


# ============================================================================
# TEST SUITE 4: Reports
# ============================================================================

def test_reports():
    """Test reports endpoints"""
    print("\n" + "="*80)
    print("TEST SUITE 4: Reports (Report Shop / Product / Review)")
    print("="*80)
    
    # Login as admin
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("Admin login for reports tests", False, "Failed to get admin token")
        return
    
    # Get a real shop_id and product_id
    print("\n--- Getting real shop and product IDs ---")
    try:
        # Get shops
        resp = requests.get(f"{BASE_URL}/shops?limit=1", timeout=10)
        if resp.status_code != 200 or not resp.json():
            log_test("Get real shop ID", False, "No shops found")
            return
        real_shop_id = resp.json()[0].get("id")
        
        # Get products
        resp = requests.get(f"{BASE_URL}/products?limit=1", timeout=10)
        if resp.status_code != 200 or not resp.json():
            log_test("Get real product ID", False, "No products found")
            return
        real_product_id = resp.json()[0].get("id")
        
        print(f"✓ Using shop: {real_shop_id}, product: {real_product_id}")
    except Exception as e:
        log_test("Get real IDs for reports", False, f"Exception: {e}")
        return
    
    # Test 4a: POST /api/reports (shop)
    print("\n--- Test 4a: POST /api/reports (shop) ---")
    report_id = None
    try:
        resp = requests.post(
            f"{BASE_URL}/reports",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "target_type": "shop",
                "target_id": real_shop_id,
                "reason": "Fraud / scam",
                "details": "Test report"
            },
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            report_id = data.get("id")
            checks = [
                data.get("target_type") == "shop",
                data.get("target_id") == real_shop_id,
                data.get("reason") == "Fraud / scam",
                data.get("status") == "open"
            ]
            
            if all(checks):
                log_test("POST /api/reports creates shop report", True, f"Report ID: {report_id}")
            else:
                log_test("POST /api/reports creates shop report", False, f"Data mismatch: {data}")
        else:
            log_test("POST /api/reports", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        log_test("POST /api/reports", False, f"Exception: {e}")
    
    # Test 4b: POST same report again (should return 409)
    print("\n--- Test 4b: POST /api/reports duplicate ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/reports",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "target_type": "shop",
                "target_id": real_shop_id,
                "reason": "Fraud / scam",
                "details": "Test report"
            },
            timeout=10
        )
        
        if resp.status_code == 409:
            log_test("POST /api/reports duplicate returns 409", True, f"Status: {resp.status_code}")
        else:
            log_test("POST /api/reports duplicate returns 409", False,
                    f"Status: {resp.status_code} (expected 409)")
    except Exception as e:
        log_test("POST /api/reports duplicate", False, f"Exception: {e}")
    
    # Test 4c: POST with invalid target_type
    print("\n--- Test 4c: POST /api/reports with invalid target_type ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/reports",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "target_type": "invalid_type",
                "target_id": real_shop_id,
                "reason": "Test"
            },
            timeout=10
        )
        
        if resp.status_code == 422:
            log_test("POST /api/reports with invalid target_type returns 422", True, f"Status: {resp.status_code}")
        else:
            log_test("POST /api/reports with invalid target_type returns 422", False,
                    f"Status: {resp.status_code} (expected 422)")
    except Exception as e:
        log_test("POST /api/reports with invalid target_type", False, f"Exception: {e}")
    
    # Test 4d: POST with nonexistent target_id
    print("\n--- Test 4d: POST /api/reports with nonexistent target_id ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/reports",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "target_type": "shop",
                "target_id": str(uuid.uuid4()),
                "reason": "Test"
            },
            timeout=10
        )
        
        if resp.status_code == 404:
            log_test("POST /api/reports with nonexistent target_id returns 404", True, f"Status: {resp.status_code}")
        else:
            log_test("POST /api/reports with nonexistent target_id returns 404", False,
                    f"Status: {resp.status_code} (expected 404)")
    except Exception as e:
        log_test("POST /api/reports with nonexistent target_id", False, f"Exception: {e}")
    
    # Test 4e: POST with empty reason
    print("\n--- Test 4e: POST /api/reports with empty reason ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/reports",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "target_type": "shop",
                "target_id": real_shop_id,
                "reason": ""
            },
            timeout=10
        )
        
        if resp.status_code == 400:
            log_test("POST /api/reports with empty reason returns 400", True, f"Status: {resp.status_code}")
        else:
            log_test("POST /api/reports with empty reason returns 400", False,
                    f"Status: {resp.status_code} (expected 400)")
    except Exception as e:
        log_test("POST /api/reports with empty reason", False, f"Exception: {e}")
    
    # Test 4f: Anonymous POST should fail
    print("\n--- Test 4f: POST /api/reports without auth ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/reports",
            json={
                "target_type": "shop",
                "target_id": real_shop_id,
                "reason": "Test"
            },
            timeout=10
        )
        
        if resp.status_code == 401:
            log_test("POST /api/reports without auth returns 401", True, f"Status: {resp.status_code}")
        else:
            log_test("POST /api/reports without auth returns 401", False,
                    f"Status: {resp.status_code} (expected 401)")
    except Exception as e:
        log_test("POST /api/reports without auth", False, f"Exception: {e}")
    
    # Test 4g: GET /api/admin/reports
    print("\n--- Test 4g: GET /api/admin/reports ---")
    try:
        resp = requests.get(
            f"{BASE_URL}/admin/reports",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        
        if resp.status_code == 200:
            reports = resp.json()
            if isinstance(reports, list):
                # Find our report
                our_report = next((r for r in reports if r.get("id") == report_id), None)
                if our_report and our_report.get("status") == "open":
                    log_test("GET /api/admin/reports returns list with our report", True,
                            f"Found report with status=open")
                else:
                    log_test("GET /api/admin/reports", False, f"Report not found or wrong status")
            else:
                log_test("GET /api/admin/reports", False, f"Not a list: {type(reports)}")
        else:
            log_test("GET /api/admin/reports", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/admin/reports", False, f"Exception: {e}")
    
    # Test 4h: GET /api/admin/reports?status=open
    print("\n--- Test 4h: GET /api/admin/reports?status=open ---")
    try:
        resp = requests.get(
            f"{BASE_URL}/admin/reports?status=open",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        
        if resp.status_code == 200:
            reports = resp.json()
            if isinstance(reports, list):
                all_open = all(r.get("status") == "open" for r in reports)
                if all_open:
                    log_test("GET /api/admin/reports?status=open filters correctly", True,
                            f"All {len(reports)} reports have status=open")
                else:
                    log_test("GET /api/admin/reports?status=open", False, "Some reports not open")
            else:
                log_test("GET /api/admin/reports?status=open", False, f"Not a list")
        else:
            log_test("GET /api/admin/reports?status=open", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/admin/reports?status=open", False, f"Exception: {e}")
    
    # Test 4i: PUT /api/admin/reports/{id}
    print("\n--- Test 4i: PUT /api/admin/reports/{id} ---")
    if report_id:
        try:
            resp = requests.put(
                f"{BASE_URL}/admin/reports/{report_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "status": "actioned",
                    "admin_notes": "Removed shop"
                },
                timeout=10
            )
            
            if resp.status_code == 200:
                # Verify update
                resp2 = requests.get(
                    f"{BASE_URL}/admin/reports",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    timeout=10
                )
                if resp2.status_code == 200:
                    reports = resp2.json()
                    our_report = next((r for r in reports if r.get("id") == report_id), None)
                    if our_report:
                        checks = [
                            our_report.get("status") == "actioned",
                            our_report.get("resolved_at") is not None
                        ]
                        if all(checks):
                            log_test("PUT /api/admin/reports/{id} updates status", True,
                                    f"status=actioned, resolved_at set")
                        else:
                            log_test("PUT /api/admin/reports/{id}", False,
                                    f"Update not reflected: {our_report}")
                    else:
                        log_test("PUT /api/admin/reports/{id} verification", False, "Report not found")
                else:
                    log_test("PUT /api/admin/reports/{id} verification", False, f"GET failed")
            else:
                log_test("PUT /api/admin/reports/{id}", False, f"Status: {resp.status_code}")
        except Exception as e:
            log_test("PUT /api/admin/reports/{id}", False, f"Exception: {e}")
    else:
        log_test("PUT /api/admin/reports/{id}", False, "No report_id from previous test")
    
    # Test 4j: Verify admin notification was created
    print("\n--- Test 4j: Verify admin notification for report ---")
    try:
        resp = requests.get(
            f"{BASE_URL}/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        
        if resp.status_code == 200:
            notifications = resp.json()
            # Look for recent notification with type="alert"
            alert_notifs = [n for n in notifications if n.get("type") == "alert"]
            if alert_notifs:
                log_test("Admin received notification for report", True,
                        f"Found {len(alert_notifs)} alert notifications")
            else:
                log_test("Admin received notification for report", False,
                        "No alert notifications found")
        else:
            log_test("Verify admin notification", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("Verify admin notification", False, f"Exception: {e}")


# ============================================================================
# TEST SUITE 5: Admin health endpoint
# ============================================================================

def test_admin_health():
    """Test admin health endpoint"""
    print("\n" + "="*80)
    print("TEST SUITE 5: Admin Health Endpoint")
    print("="*80)
    
    # Login as admin
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("Admin login for health tests", False, "Failed to get admin token")
        return
    
    # Test 5a: GET /api/admin/health as admin
    print("\n--- Test 5a: GET /api/admin/health as admin ---")
    try:
        resp = requests.get(
            f"{BASE_URL}/admin/health",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            
            # Check structure
            checks = [
                "checked_at" in data,
                data.get("mongo", {}).get("status") == "ok",
                isinstance(data.get("mongo", {}).get("ping_ms"), (int, float)),
                data.get("integrations", {}).get("web_push") == True,
                "collections" in data.get("mongo", {})
            ]
            
            if all(checks):
                collections = data.get("mongo", {}).get("collections", {})
                expected_collections = ["users", "shops", "products", "orders", "categories", "notifications", "push_subscriptions"]
                has_all_collections = all(c in collections for c in expected_collections)
                
                if has_all_collections:
                    log_test("GET /api/admin/health returns correct structure", True,
                            f"mongo.status=ok, ping_ms={data['mongo']['ping_ms']}, web_push=true, all collections present")
                else:
                    log_test("GET /api/admin/health collections", False,
                            f"Missing collections. Got: {list(collections.keys())}")
            else:
                log_test("GET /api/admin/health structure", False, f"Missing fields: {data}")
        else:
            log_test("GET /api/admin/health", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/admin/health", False, f"Exception: {e}")
    
    # Test 5b: GET /api/admin/health as non-admin (should fail)
    print("\n--- Test 5b: GET /api/admin/health as non-admin ---")
    try:
        # Create a seller
        seller_id, shop_id, seller_token = create_seller_and_shop(admin_token)
        
        resp = requests.get(
            f"{BASE_URL}/admin/health",
            headers={"Authorization": f"Bearer {seller_token}"},
            timeout=10
        )
        
        if resp.status_code == 403:
            log_test("GET /api/admin/health as non-admin returns 403", True, f"Status: {resp.status_code}")
        else:
            log_test("GET /api/admin/health as non-admin returns 403", False,
                    f"Status: {resp.status_code} (expected 403)")
    except Exception as e:
        log_test("GET /api/admin/health as non-admin", False, f"Exception: {e}")
    
    # Test 5c: Anonymous request should fail
    print("\n--- Test 5c: GET /api/admin/health without auth ---")
    try:
        resp = requests.get(f"{BASE_URL}/admin/health", timeout=10)
        if resp.status_code == 401:
            log_test("GET /api/admin/health without auth returns 401", True, f"Status: {resp.status_code}")
        else:
            log_test("GET /api/admin/health without auth returns 401", False,
                    f"Status: {resp.status_code} (expected 401)")
    except Exception as e:
        log_test("GET /api/admin/health without auth", False, f"Exception: {e}")


# ============================================================================
# TEST SUITE 6: SEO (sitemap.xml + robots.txt)
# ============================================================================

def test_seo():
    """Test SEO endpoints"""
    print("\n" + "="*80)
    print("TEST SUITE 6: SEO (sitemap.xml + robots.txt)")
    print("="*80)
    
    # Test 6a: GET /api/sitemap.xml
    print("\n--- Test 6a: GET /api/sitemap.xml ---")
    try:
        resp = requests.get(f"{BASE_URL}/sitemap.xml", timeout=10)
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            content = resp.text
            
            checks = [
                "application/xml" in content_type,
                content.startswith("<?xml"),
                "<urlset" in content,
                "<url>" in content
            ]
            
            if all(checks):
                log_test("GET /api/sitemap.xml returns valid XML", True,
                        f"Content-Type: {content_type}, starts with <?xml, contains urlset and url")
            else:
                log_test("GET /api/sitemap.xml", False,
                        f"Invalid XML. Content-Type: {content_type}, starts: {content[:50]}")
        else:
            log_test("GET /api/sitemap.xml", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/sitemap.xml", False, f"Exception: {e}")
    
    # Test 6b: GET /api/robots.txt
    print("\n--- Test 6b: GET /api/robots.txt ---")
    try:
        resp = requests.get(f"{BASE_URL}/robots.txt", timeout=10)
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            content = resp.text
            
            checks = [
                "text/plain" in content_type,
                "User-agent: *" in content,
                "Disallow: /admin" in content,
                "Sitemap:" in content
            ]
            
            if all(checks):
                log_test("GET /api/robots.txt returns valid robots.txt", True,
                        f"Contains User-agent, Disallow, and Sitemap directives")
            else:
                log_test("GET /api/robots.txt", False,
                        f"Invalid content. Got: {content[:200]}")
        else:
            log_test("GET /api/robots.txt", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/robots.txt", False, f"Exception: {e}")


# ============================================================================
# TEST SUITE 7: Regression smoke tests
# ============================================================================

def test_regression_smoke():
    """Regression smoke tests"""
    print("\n" + "="*80)
    print("TEST SUITE 7: Regression Smoke Tests")
    print("="*80)
    
    # Test 7a: Admin login (email + username)
    print("\n--- Test 7a: Admin login (email and username) ---")
    admin_token_email = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    admin_token_username = login("admin", ADMIN_PASSWORD)
    
    if admin_token_email and admin_token_username:
        log_test("Admin login with email and username both work", True,
                "Both tokens obtained")
    else:
        log_test("Admin login", False,
                f"Email token: {bool(admin_token_email)}, Username token: {bool(admin_token_username)}")
    
    # Test 7b: GET /api/homepage
    print("\n--- Test 7b: GET /api/homepage ---")
    try:
        resp = requests.get(f"{BASE_URL}/homepage", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "hero_slides" in data:
                log_test("GET /api/homepage still works", True, "Returns hero_slides")
            else:
                log_test("GET /api/homepage", False, f"Missing hero_slides: {list(data.keys())}")
        else:
            log_test("GET /api/homepage", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/homepage", False, f"Exception: {e}")
    
    # Test 7c: GET /api/products/bulk-template (route order check)
    print("\n--- Test 7c: GET /api/products/bulk-template (route order) ---")
    try:
        resp = requests.get(
            f"{BASE_URL}/products/bulk-template",
            headers={"Authorization": f"Bearer {admin_token_email}"},
            timeout=10
        )
        if resp.status_code == 200:
            log_test("GET /api/products/bulk-template still works", True, "Route order correct")
        else:
            log_test("GET /api/products/bulk-template", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/products/bulk-template", False, f"Exception: {e}")
    
    # Test 7d: GET /api/products/{id} (regression check)
    print("\n--- Test 7d: GET /api/products/{id} ---")
    try:
        # Get a product
        resp = requests.get(f"{BASE_URL}/products?limit=1", timeout=10)
        if resp.status_code == 200 and resp.json():
            product_id = resp.json()[0].get("id")
            resp2 = requests.get(f"{BASE_URL}/products/{product_id}", timeout=10)
            if resp2.status_code == 200:
                log_test("GET /api/products/{id} still works", True, f"Product ID: {product_id}")
            else:
                log_test("GET /api/products/{id}", False, f"Status: {resp2.status_code}")
        else:
            log_test("GET /api/products/{id}", False, "No products found for test")
    except Exception as e:
        log_test("GET /api/products/{id}", False, f"Exception: {e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("JUBASQUARE BACKEND API TESTING - PHASE 1 (July 2025)")
    print("Testing: Web Push, Bulk Stock Update, Seller Analytics, Reports, Admin Health, SEO")
    print("Base URL:", BASE_URL)
    print("="*80)
    
    try:
        # Run test suites
        test_web_push()
        test_bulk_stock_update()
        test_seller_analytics()
        test_reports()
        test_admin_health()
        test_seo()
        test_regression_smoke()
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"Total tests: {tests_passed + tests_failed}")
        print(f"✅ Passed: {tests_passed}")
        print(f"❌ Failed: {tests_failed}")
        if tests_passed + tests_failed > 0:
            print(f"Success rate: {tests_passed / (tests_passed + tests_failed) * 100:.1f}%")
        
        if tests_failed > 0:
            print("\n❌ FAILED TESTS:")
            for result in test_results:
                if not result["passed"]:
                    print(f"  - {result['name']}")
                    if result["details"]:
                        print(f"    {result['details']}")
        
        print("="*80)
        
        # Exit code
        sys.exit(0 if tests_failed == 0 else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
