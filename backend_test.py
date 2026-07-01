#!/usr/bin/env python3
"""
Backend API Testing for JubaSquare - Homepage Customization & Bulk Product Import
Tests the two new features added in this iteration.
"""

import requests
import json
import io
import sys
from typing import Dict, Any

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
    import uuid
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


# ============================================================================
# TEST SUITE 1: Homepage Customization API
# ============================================================================

def test_homepage_customization():
    """Test homepage customization endpoints"""
    print("\n" + "="*80)
    print("TEST SUITE 1: Homepage Customization API")
    print("="*80)
    
    # Test 1a: GET /api/homepage (public, no auth)
    print("\n--- Test 1a: GET /api/homepage (public) ---")
    try:
        resp = requests.get(f"{BASE_URL}/homepage", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            has_slides = "hero_slides" in data and isinstance(data["hero_slides"], list)
            has_tagline = "hero_tagline" in data
            has_title = "hero_title" in data
            has_subtitle = "hero_subtitle" in data
            has_announcement = "announcement_bar" in data and isinstance(data["announcement_bar"], dict)
            
            if has_slides and has_tagline and has_title and has_subtitle and has_announcement:
                # Check default slides
                slides = data["hero_slides"]
                has_retail = any(s.get("label") == "Retail" for s in slides)
                has_wholesale = any(s.get("label") == "Wholesale" for s in slides)
                has_food = any(s.get("label") == "Food" for s in slides)
                
                if has_retail and has_wholesale and has_food:
                    log_test("GET /api/homepage returns correct structure with 3 default slides", True,
                            f"Slides: {len(slides)}, Keys: {list(data.keys())}")
                else:
                    log_test("GET /api/homepage returns correct structure with 3 default slides", False,
                            f"Missing default slides. Found: {[s.get('label') for s in slides]}")
            else:
                log_test("GET /api/homepage returns correct structure", False,
                        f"Missing keys. Got: {list(data.keys())}")
        else:
            log_test("GET /api/homepage returns 200", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/homepage", False, f"Exception: {e}")
    
    # Login as admin for remaining tests
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("Admin login", False, "Failed to get admin token")
        return
    log_test("Admin login", True, "Token obtained")
    
    # Test 1b: PUT /api/admin/homepage as admin
    print("\n--- Test 1b: PUT /api/admin/homepage (admin) ---")
    try:
        test_payload = {
            "hero_slides": [
                {
                    "label": "Test Slide",
                    "key": "slideTest",
                    "image_url": "https://example.com/test.jpg"
                }
            ],
            "hero_tagline": "Test Tagline",
            "hero_title": "Test Title",
            "hero_subtitle": "Test Subtitle",
            "announcement_bar": {
                "enabled": True,
                "text": "Free delivery today",
                "link": "/marketplace"
            }
        }
        
        resp = requests.put(
            f"{BASE_URL}/admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=test_payload,
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok") and "homepage" in data:
                hp = data["homepage"]
                checks = [
                    hp.get("hero_tagline") == "Test Tagline",
                    hp.get("hero_title") == "Test Title",
                    hp.get("hero_subtitle") == "Test Subtitle",
                    len(hp.get("hero_slides", [])) == 1,
                    hp.get("announcement_bar", {}).get("enabled") == True,
                    hp.get("announcement_bar", {}).get("text") == "Free delivery today"
                ]
                if all(checks):
                    log_test("PUT /api/admin/homepage updates config", True,
                            f"All fields updated correctly")
                else:
                    log_test("PUT /api/admin/homepage updates config", False,
                            f"Some fields not updated. Response: {hp}")
            else:
                log_test("PUT /api/admin/homepage returns ok:true", False, f"Response: {data}")
        else:
            log_test("PUT /api/admin/homepage returns 200", False,
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        log_test("PUT /api/admin/homepage", False, f"Exception: {e}")
    
    # Test 1c: GET /api/homepage again to verify persistence
    print("\n--- Test 1c: GET /api/homepage (verify persistence) ---")
    try:
        resp = requests.get(f"{BASE_URL}/homepage", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            checks = [
                data.get("hero_tagline") == "Test Tagline",
                data.get("hero_title") == "Test Title",
                data.get("hero_subtitle") == "Test Subtitle",
                len(data.get("hero_slides", [])) == 1,
                data.get("announcement_bar", {}).get("text") == "Free delivery today"
            ]
            if all(checks):
                log_test("GET /api/homepage reflects PUT changes", True, "All changes persisted")
            else:
                log_test("GET /api/homepage reflects PUT changes", False,
                        f"Changes not persisted. Got: {data}")
        else:
            log_test("GET /api/homepage after PUT", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/homepage after PUT", False, f"Exception: {e}")
    
    # Test 1d: GET /api/settings/public includes homepage
    print("\n--- Test 1d: GET /api/settings/public includes homepage ---")
    try:
        resp = requests.get(f"{BASE_URL}/settings/public", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "homepage" in data:
                hp = data["homepage"]
                if hp.get("hero_tagline") == "Test Tagline":
                    log_test("GET /api/settings/public includes homepage", True,
                            "Homepage object present with correct data")
                else:
                    log_test("GET /api/settings/public includes homepage", False,
                            f"Homepage data mismatch: {hp}")
            else:
                log_test("GET /api/settings/public includes homepage", False,
                        f"Missing homepage key. Keys: {list(data.keys())}")
        else:
            log_test("GET /api/settings/public", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/settings/public", False, f"Exception: {e}")
    
    # Test 1e: PUT without auth should fail
    print("\n--- Test 1e: PUT /api/admin/homepage without auth ---")
    try:
        resp = requests.put(
            f"{BASE_URL}/admin/homepage",
            json={"hero_title": "Unauthorized"},
            timeout=10
        )
        if resp.status_code in [401, 403]:
            log_test("PUT /api/admin/homepage without auth returns 401/403", True,
                    f"Status: {resp.status_code}")
        else:
            log_test("PUT /api/admin/homepage without auth returns 401/403", False,
                    f"Status: {resp.status_code} (expected 401/403)")
    except Exception as e:
        log_test("PUT /api/admin/homepage without auth", False, f"Exception: {e}")
    
    # Test 1f: Create a customer and try PUT (should fail with 403)
    print("\n--- Test 1f: PUT /api/admin/homepage as non-admin ---")
    try:
        # Create customer
        import uuid
        customer_email = f"customer_test_{uuid.uuid4().hex[:8]}@test.com"
        resp = requests.post(
            f"{BASE_URL}/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Test Customer",
                "email": customer_email,
                "password": "test123",
                "role": "customer",
                "phone": "+211912345679"
            },
            timeout=10
        )
        
        if resp.status_code == 200:
            customer_token = login(customer_email, "test123")
            if customer_token:
                resp = requests.put(
                    f"{BASE_URL}/admin/homepage",
                    headers={"Authorization": f"Bearer {customer_token}"},
                    json={"hero_title": "Customer attempt"},
                    timeout=10
                )
                if resp.status_code == 403:
                    log_test("PUT /api/admin/homepage as customer returns 403", True,
                            f"Status: {resp.status_code}")
                else:
                    log_test("PUT /api/admin/homepage as customer returns 403", False,
                            f"Status: {resp.status_code} (expected 403)")
            else:
                log_test("PUT /api/admin/homepage as customer", False, "Failed to login as customer")
        else:
            log_test("PUT /api/admin/homepage as customer", False, "Failed to create customer")
    except Exception as e:
        log_test("PUT /api/admin/homepage as customer", False, f"Exception: {e}")
    
    # Test 1g: Sanitization - more than 6 slides should be capped
    print("\n--- Test 1g: PUT with >6 slides (sanitization) ---")
    try:
        slides = [{"label": f"Slide {i}", "key": f"slide{i}", "image_url": f"https://example.com/{i}.jpg"}
                  for i in range(10)]
        resp = requests.put(
            f"{BASE_URL}/admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"hero_slides": slides},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            hp = data.get("homepage", {})
            slide_count = len(hp.get("hero_slides", []))
            if slide_count == 6:
                log_test("PUT with >6 slides caps to 6", True, f"Capped to {slide_count} slides")
            else:
                log_test("PUT with >6 slides caps to 6", False,
                        f"Expected 6 slides, got {slide_count}")
        else:
            log_test("PUT with >6 slides", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("PUT with >6 slides", False, f"Exception: {e}")
    
    # Test 1h: Sanitization - invalid hero_slides type should return 400
    print("\n--- Test 1h: PUT with invalid hero_slides type ---")
    try:
        resp = requests.put(
            f"{BASE_URL}/admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"hero_slides": "not a list"},
            timeout=10
        )
        if resp.status_code == 400:
            log_test("PUT with invalid hero_slides type returns 400", True,
                    f"Status: {resp.status_code}")
        else:
            log_test("PUT with invalid hero_slides type returns 400", False,
                    f"Status: {resp.status_code} (expected 400)")
    except Exception as e:
        log_test("PUT with invalid hero_slides type", False, f"Exception: {e}")
    
    # Restore defaults
    print("\n--- Restoring default homepage config ---")
    try:
        resp = requests.put(
            f"{BASE_URL}/admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "hero_slides": [
                    {"label": "Retail", "key": "slideRetail", "image_url": "https://images.unsplash.com/photo-1604719312566-8912e9227c6a?w=1600&q=80&auto=format&fit=crop"},
                    {"label": "Wholesale", "key": "slideWholesale", "image_url": "https://images.unsplash.com/photo-1553413077-190dd305871c?w=1600&q=80&auto=format&fit=crop"},
                    {"label": "Food", "key": "slideFood", "image_url": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=1600&q=80&auto=format&fit=crop"}
                ],
                "hero_tagline": "",
                "hero_title": "",
                "hero_subtitle": "",
                "announcement_bar": {"enabled": False, "text": "", "link": ""}
            },
            timeout=10
        )
        if resp.status_code == 200:
            print("✓ Defaults restored")
        else:
            print(f"⚠ Failed to restore defaults: {resp.status_code}")
    except Exception as e:
        print(f"⚠ Exception restoring defaults: {e}")


# ============================================================================
# TEST SUITE 2: Bulk Product Import
# ============================================================================

def test_bulk_product_import():
    """Test bulk product import endpoints"""
    print("\n" + "="*80)
    print("TEST SUITE 2: Bulk Product Import")
    print("="*80)
    
    # Login as admin
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("Admin login for bulk import", False, "Failed to get admin token")
        return
    
    # Test 2a: GET /api/products/bulk-template
    print("\n--- Test 2a: GET /api/products/bulk-template ---")
    try:
        resp = requests.get(
            f"{BASE_URL}/products/bulk-template",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if resp.status_code == 200:
            content = resp.text
            has_header = "name,category_name,price_usd" in content
            has_sample = "Sample Product" in content or "Bulk Rice" in content
            if has_header and has_sample:
                log_test("GET /api/products/bulk-template returns CSV", True,
                        f"Content length: {len(content)} bytes")
            else:
                log_test("GET /api/products/bulk-template returns CSV", False,
                        f"Missing expected content. Got: {content[:200]}")
        else:
            log_test("GET /api/products/bulk-template", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/products/bulk-template", False, f"Exception: {e}")
    
    # Create seller and shop for testing
    print("\n--- Creating test seller and shop ---")
    try:
        seller_id, shop_id, seller_token = create_seller_and_shop(admin_token)
        print(f"✓ Created seller: {seller_id}, shop: {shop_id}")
    except Exception as e:
        log_test("Create seller and shop", False, f"Exception: {e}")
        return
    
    # Get a valid category
    category_id = get_category_id(admin_token)
    if not category_id:
        log_test("Get category ID", False, "No categories found")
        return
    print(f"✓ Using category ID: {category_id}")
    
    # Test 2b: POST /api/products/bulk-import with mixed valid/invalid rows
    print("\n--- Test 2b: POST /api/products/bulk-import (mixed rows) ---")
    try:
        csv_content = f"""name,category_name,category_id,price_usd,description,stock,image_url,is_wholesale,min_order_qty,bulk_price_usd
Valid Product 1,Groceries,,10.50,Test product 1,100,https://example.com/1.jpg,false,1,
Valid Product 2,,{category_id},20.00,Test product 2,50,https://example.com/2.jpg,false,1,
,Groceries,,15.00,Missing name,100,,false,1,
Invalid Category Product,NonExistentCategory,,25.00,Bad category,100,,false,1,
Invalid Price Product,Groceries,,not_a_number,Bad price,100,,false,1,
Wholesale Product,Groceries,,45.00,Bulk item,50,,true,10,42.00"""
        
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        resp = requests.post(
            f"{BASE_URL}/products/bulk-import?shop_id={shop_id}",
            headers={"Authorization": f"Bearer {seller_token}"},
            files=files,
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("total", 0)
            created = data.get("created", 0)
            errors = data.get("errors", [])
            created_ids = data.get("created_ids", [])
            
            # Expected: 6 total, 3 created (Valid 1, Valid 2, Wholesale), 3 errors (missing name, invalid category, invalid price)
            checks = [
                total == 6,
                created == 3,
                len(errors) == 3,
                len(created_ids) == 3
            ]
            
            if all(checks):
                log_test("POST bulk-import with mixed rows", True,
                        f"Total: {total}, Created: {created}, Errors: {len(errors)}")
                
                # Verify error details
                error_types = [e.get("error", "") for e in errors]
                has_name_error = any("name is required" in e for e in error_types)
                has_category_error = any("category not found" in e for e in error_types)
                has_price_error = any("invalid price_usd" in e for e in error_types)
                
                if has_name_error and has_category_error and has_price_error:
                    log_test("Bulk import error messages are descriptive", True,
                            f"All expected error types present")
                else:
                    log_test("Bulk import error messages are descriptive", False,
                            f"Missing error types. Got: {error_types}")
            else:
                log_test("POST bulk-import with mixed rows", False,
                        f"Expected total=6, created=3, errors=3. Got: total={total}, created={created}, errors={len(errors)}")
        else:
            log_test("POST bulk-import", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        log_test("POST bulk-import", False, f"Exception: {e}")
    
    # Test 2c: Verify created products exist
    print("\n--- Test 2c: Verify created products ---")
    try:
        resp = requests.get(f"{BASE_URL}/products?shop_id={shop_id}", timeout=10)
        if resp.status_code == 200:
            products = resp.json()
            if len(products) >= 3:
                # Check for wholesale product
                wholesale_products = [p for p in products if p.get("is_wholesale")]
                if len(wholesale_products) > 0:
                    wp = wholesale_products[0]
                    has_min_qty = wp.get("min_order_qty") == 10
                    has_bulk_price = wp.get("bulk_price_usd") == 42.00
                    if has_min_qty and has_bulk_price:
                        log_test("Wholesale product created with correct fields", True,
                                f"min_order_qty: {wp.get('min_order_qty')}, bulk_price_usd: {wp.get('bulk_price_usd')}")
                    else:
                        log_test("Wholesale product created with correct fields", False,
                                f"Fields mismatch: {wp}")
                else:
                    log_test("Wholesale product created", False, "No wholesale products found")
            else:
                log_test("Created products exist", False, f"Expected >=3 products, got {len(products)}")
        else:
            log_test("GET products after bulk import", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("Verify created products", False, f"Exception: {e}")
    
    # Test 2d: POST bulk-import for shop not owned by seller (should fail with 403)
    print("\n--- Test 2d: POST bulk-import for non-owned shop ---")
    try:
        # Create another seller
        seller2_id, shop2_id, seller2_token = create_seller_and_shop(admin_token)
        
        # Try to import to shop2 using seller1's token
        csv_content = "name,category_name,price_usd\nTest,Groceries,10.00"
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        resp = requests.post(
            f"{BASE_URL}/products/bulk-import?shop_id={shop2_id}",
            headers={"Authorization": f"Bearer {seller_token}"},
            files=files,
            timeout=10
        )
        
        if resp.status_code == 403:
            log_test("POST bulk-import for non-owned shop returns 403", True,
                    f"Status: {resp.status_code}")
        else:
            log_test("POST bulk-import for non-owned shop returns 403", False,
                    f"Status: {resp.status_code} (expected 403)")
    except Exception as e:
        log_test("POST bulk-import for non-owned shop", False, f"Exception: {e}")
    
    # Test 2e: POST bulk-import without auth
    print("\n--- Test 2e: POST bulk-import without auth ---")
    try:
        csv_content = "name,category_name,price_usd\nTest,Groceries,10.00"
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        resp = requests.post(
            f"{BASE_URL}/products/bulk-import?shop_id={shop_id}",
            files=files,
            timeout=10
        )
        
        if resp.status_code in [401, 403]:
            log_test("POST bulk-import without auth returns 401/403", True,
                    f"Status: {resp.status_code}")
        else:
            log_test("POST bulk-import without auth returns 401/403", False,
                    f"Status: {resp.status_code} (expected 401/403)")
    except Exception as e:
        log_test("POST bulk-import without auth", False, f"Exception: {e}")
    
    # Test 2f: POST bulk-import with corrupt file
    print("\n--- Test 2f: POST bulk-import with corrupt file ---")
    try:
        # Send binary garbage
        files = {"file": ("test.csv", io.BytesIO(b"\x00\x01\x02\x03\x04"), "text/csv")}
        resp = requests.post(
            f"{BASE_URL}/products/bulk-import?shop_id={shop_id}",
            headers={"Authorization": f"Bearer {seller_token}"},
            files=files,
            timeout=10
        )
        
        # Should either return 400 or 200 with all errors
        if resp.status_code in [400, 200]:
            if resp.status_code == 200:
                data = resp.json()
                # Should have errors or zero created
                if data.get("created", 0) == 0 or len(data.get("errors", [])) > 0:
                    log_test("POST bulk-import with corrupt file handles gracefully", True,
                            f"Status: {resp.status_code}, Response: {data}")
                else:
                    log_test("POST bulk-import with corrupt file handles gracefully", False,
                            f"Unexpected success: {data}")
            else:
                log_test("POST bulk-import with corrupt file returns 400", True,
                        f"Status: {resp.status_code}")
        else:
            log_test("POST bulk-import with corrupt file", False,
                    f"Status: {resp.status_code} (expected 400 or 200 with errors)")
    except Exception as e:
        log_test("POST bulk-import with corrupt file", False, f"Exception: {e}")


# ============================================================================
# TEST SUITE 3: Regression Smoke Tests
# ============================================================================

def test_regression_smoke():
    """Smoke tests for existing endpoints"""
    print("\n" + "="*80)
    print("TEST SUITE 3: Regression Smoke Tests")
    print("="*80)
    
    # Test 3a: Admin login
    print("\n--- Test 3a: POST /api/auth/login (admin) ---")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if admin_token:
        log_test("POST /api/auth/login for admin", True, "Token obtained")
    else:
        log_test("POST /api/auth/login for admin", False, "Failed to get token")
    
    # Test 3b: GET /api/settings/public
    print("\n--- Test 3b: GET /api/settings/public ---")
    try:
        resp = requests.get(f"{BASE_URL}/settings/public", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            required_keys = ["module_marketplace", "currency_display", "homepage"]
            has_all = all(k in data for k in required_keys)
            if has_all:
                log_test("GET /api/settings/public returns expected fields", True,
                        f"Keys present: {required_keys}")
            else:
                log_test("GET /api/settings/public returns expected fields", False,
                        f"Missing keys. Got: {list(data.keys())}")
        else:
            log_test("GET /api/settings/public", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/settings/public", False, f"Exception: {e}")
    
    # Test 3c: GET /api/products
    print("\n--- Test 3c: GET /api/products ---")
    try:
        resp = requests.get(f"{BASE_URL}/products?limit=5", timeout=10)
        if resp.status_code == 200:
            products = resp.json()
            if isinstance(products, list):
                log_test("GET /api/products returns list", True, f"Count: {len(products)}")
            else:
                log_test("GET /api/products returns list", False, f"Type: {type(products)}")
        else:
            log_test("GET /api/products", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/products", False, f"Exception: {e}")
    
    # Test 3d: GET /api/shops
    print("\n--- Test 3d: GET /api/shops ---")
    try:
        resp = requests.get(f"{BASE_URL}/shops?limit=5", timeout=10)
        if resp.status_code == 200:
            shops = resp.json()
            if isinstance(shops, list):
                log_test("GET /api/shops returns list", True, f"Count: {len(shops)}")
            else:
                log_test("GET /api/shops returns list", False, f"Type: {type(shops)}")
        else:
            log_test("GET /api/shops", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/shops", False, f"Exception: {e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("JUBASQUARE BACKEND API TESTING")
    print("Testing: Homepage Customization & Bulk Product Import")
    print("Base URL:", BASE_URL)
    print("="*80)
    
    try:
        # Run test suites
        test_homepage_customization()
        test_bulk_product_import()
        test_regression_smoke()
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"Total tests: {tests_passed + tests_failed}")
        print(f"✅ Passed: {tests_passed}")
        print(f"❌ Failed: {tests_failed}")
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
