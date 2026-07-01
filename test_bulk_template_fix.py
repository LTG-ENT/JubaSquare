#!/usr/bin/env python3
"""
Test script for bulk-template endpoint fix
Tests that /api/products/bulk-template is correctly matched before /api/products/{product_id}
"""

import requests
import sys

BASE_URL = "https://jubasquare-odoo-v2.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@jubasquare.com"
ADMIN_PASSWORD = "1234"

def login(email: str, password: str) -> str:
    """Login and return token"""
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("token", "")
        return ""
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return ""

def test_bulk_template_endpoint():
    """Test the bulk-template endpoint"""
    print("\n" + "="*80)
    print("TEST: GET /api/products/bulk-template")
    print("="*80)
    
    # Login as admin
    print("\n1. Logging in as admin...")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        print("❌ FAILED: Could not login as admin")
        return False
    print("✅ Admin login successful")
    
    # Test 1: GET /api/products/bulk-template as admin
    print("\n2. Testing GET /api/products/bulk-template as admin...")
    try:
        resp = requests.get(
            f"{BASE_URL}/products/bulk-template",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        
        print(f"   Status code: {resp.status_code}")
        print(f"   Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
        print(f"   Content length: {len(resp.text)} bytes")
        
        if resp.status_code != 200:
            print(f"❌ FAILED: Expected status 200, got {resp.status_code}")
            print(f"   Response: {resp.text[:500]}")
            return False
        
        # Check Content-Type
        content_type = resp.headers.get('Content-Type', '')
        if 'text/csv' not in content_type:
            print(f"❌ FAILED: Expected Content-Type text/csv, got {content_type}")
            return False
        
        # Check content
        content = resp.text
        lines = content.strip().split('\n')
        
        print(f"   Number of lines: {len(lines)}")
        print(f"   First line (header): {lines[0] if lines else 'N/A'}")
        
        # Check header
        if not lines or not lines[0].startswith("name,category_name,price_usd"):
            print(f"❌ FAILED: Header does not start with 'name,category_name,price_usd'")
            print(f"   Got: {lines[0] if lines else 'N/A'}")
            return False
        
        # Check for at least 2 sample rows (header + 2 data rows = 3 lines minimum)
        if len(lines) < 3:
            print(f"❌ FAILED: Expected at least 3 lines (header + 2 sample rows), got {len(lines)}")
            return False
        
        print(f"   Sample row 1: {lines[1][:80]}...")
        print(f"   Sample row 2: {lines[2][:80]}...")
        
        print("✅ PASSED: GET /api/products/bulk-template returns correct CSV")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: Exception: {e}")
        return False

def test_product_by_id_no_regression():
    """Test that GET /api/products/{product_id} still works"""
    print("\n" + "="*80)
    print("TEST: GET /api/products/{product_id} (no regression)")
    print("="*80)
    
    # First, get a real product ID
    print("\n1. Getting a real product ID...")
    try:
        resp = requests.get(f"{BASE_URL}/products?limit=1", timeout=10)
        if resp.status_code != 200:
            print(f"❌ FAILED: Could not fetch products list: {resp.status_code}")
            return False
        
        products = resp.json()
        if not products or len(products) == 0:
            print("❌ FAILED: No products found in database")
            return False
        
        product_id = products[0].get("id")
        product_name = products[0].get("name", "Unknown")
        print(f"✅ Found product: {product_name} (ID: {product_id})")
        
    except Exception as e:
        print(f"❌ FAILED: Exception getting products: {e}")
        return False
    
    # Test 2: GET /api/products/{product_id}
    print(f"\n2. Testing GET /api/products/{product_id}...")
    try:
        resp = requests.get(f"{BASE_URL}/products/{product_id}", timeout=10)
        
        print(f"   Status code: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"❌ FAILED: Expected status 200, got {resp.status_code}")
            print(f"   Response: {resp.text[:500]}")
            return False
        
        data = resp.json()
        if data.get("id") != product_id:
            print(f"❌ FAILED: Product ID mismatch. Expected {product_id}, got {data.get('id')}")
            return False
        
        print(f"   Product name: {data.get('name')}")
        print(f"   Product ID: {data.get('id')}")
        print("✅ PASSED: GET /api/products/{product_id} works correctly")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: Exception: {e}")
        return False

def test_nonexistent_product_404():
    """Test that GET /api/products/nonexistent-id returns 404"""
    print("\n" + "="*80)
    print("TEST: GET /api/products/nonexistent-id-xyz (should return 404)")
    print("="*80)
    
    print("\n1. Testing GET /api/products/nonexistent-id-xyz...")
    try:
        resp = requests.get(f"{BASE_URL}/products/nonexistent-id-xyz", timeout=10)
        
        print(f"   Status code: {resp.status_code}")
        
        if resp.status_code != 404:
            print(f"❌ FAILED: Expected status 404, got {resp.status_code}")
            print(f"   Response: {resp.text[:500]}")
            return False
        
        print("✅ PASSED: GET /api/products/nonexistent-id-xyz returns 404")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: Exception: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("BULK-TEMPLATE ENDPOINT FIX VERIFICATION")
    print("Base URL:", BASE_URL)
    print("="*80)
    
    results = []
    
    # Test 1: bulk-template endpoint
    results.append(("GET /api/products/bulk-template", test_bulk_template_endpoint()))
    
    # Test 2: product by ID (no regression)
    results.append(("GET /api/products/{product_id}", test_product_by_id_no_regression()))
    
    # Test 3: nonexistent product 404
    results.append(("GET /api/products/nonexistent-id-xyz", test_nonexistent_product_404()))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    failed = sum(1 for _, result in results if not result)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {len(results)} tests")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print("="*80)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
