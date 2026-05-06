#!/usr/bin/env python3
"""
Focused backend test for JubaSquare Round 2 changes.
Tests ONLY:
1. Per-seller exchange rate + shop verification embedded in product responses
2. Verified-first sort on /api/products and /api/restaurants
3. PUT /api/exchange-rate is seller-only (admin/customer get 403)
"""
import requests
import sys

BASE_URL = "https://publish-ready-34.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@demo.com"
SELLER_EMAIL = "seller@demo.com"
CUSTOMER_EMAIL = "customer@demo.com"
PASSWORD = "1234"

def login(email: str, password: str) -> str:
    """Login and return access token."""
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        print(f"❌ Login failed for {email}: {resp.status_code} {resp.text}")
        sys.exit(1)
    token = resp.cookies.get("access_token")
    if not token:
        print(f"❌ No access_token cookie returned for {email}")
        sys.exit(1)
    return token

def test_exchange_rate_and_verification_in_products():
    """
    Test 1: GET /api/products and GET /api/products/{id} embed exchange_rate_ssp and shop_verification.
    Also test that per-seller rate changes are reflected.
    """
    print("\n=== Test 1: Exchange rate + shop verification in product responses ===")
    
    seller_token = login(SELLER_EMAIL, PASSWORD)
    headers = {"Authorization": f"Bearer {seller_token}"}
    
    # Get seller's shops to find products
    shops_resp = requests.get(f"{BASE_URL}/shops/mine", headers=headers)
    if shops_resp.status_code != 200:
        print(f"❌ Failed to get seller shops: {shops_resp.status_code}")
        return False
    
    shops = shops_resp.json()
    if not shops:
        print("❌ Seller has no shops")
        return False
    
    seller_shop_id = shops[0]["id"]
    
    # Get products for this shop
    products_resp = requests.get(f"{BASE_URL}/products", params={"shop_id": seller_shop_id})
    if products_resp.status_code != 200:
        print(f"❌ GET /api/products failed: {products_resp.status_code}")
        return False
    
    products = products_resp.json()
    if not products:
        print("❌ No products found for seller's shop")
        return False
    
    # Check first product has both fields
    product = products[0]
    if "exchange_rate_ssp" not in product:
        print(f"❌ Product missing 'exchange_rate_ssp' field: {product}")
        return False
    if "shop_verification" not in product:
        print(f"❌ Product missing 'shop_verification' field: {product}")
        return False
    
    if not isinstance(product["exchange_rate_ssp"], (int, float)) or product["exchange_rate_ssp"] <= 0:
        print(f"❌ exchange_rate_ssp is not a positive number: {product['exchange_rate_ssp']}")
        return False
    
    if product["shop_verification"] not in ["Verified", "Pending", "Rejected"]:
        print(f"❌ shop_verification has invalid value: {product['shop_verification']}")
        return False
    
    print(f"✅ GET /api/products returns exchange_rate_ssp={product['exchange_rate_ssp']} and shop_verification={product['shop_verification']}")
    
    # Test GET /api/products/{id}
    product_id = product["id"]
    single_resp = requests.get(f"{BASE_URL}/products/{product_id}")
    if single_resp.status_code != 200:
        print(f"❌ GET /api/products/{product_id} failed: {single_resp.status_code}")
        return False
    
    single_product = single_resp.json()
    if "exchange_rate_ssp" not in single_product:
        print(f"❌ Single product missing 'exchange_rate_ssp' field")
        return False
    if "shop_verification" not in single_product:
        print(f"❌ Single product missing 'shop_verification' field")
        return False
    
    print(f"✅ GET /api/products/{product_id} returns exchange_rate_ssp={single_product['exchange_rate_ssp']} and shop_verification={single_product['shop_verification']}")
    
    # Test per-seller rate change
    original_rate = product["exchange_rate_ssp"]
    new_rate = 750.0
    
    # Set seller's rate to 750
    rate_resp = requests.put(f"{BASE_URL}/exchange-rate", json={"rate": new_rate}, headers=headers)
    if rate_resp.status_code != 200:
        print(f"❌ PUT /api/exchange-rate failed: {rate_resp.status_code} {rate_resp.text}")
        return False
    
    print(f"✅ Seller set exchange rate to {new_rate}")
    
    # Get products again and verify rate changed
    products_resp2 = requests.get(f"{BASE_URL}/products", params={"shop_id": seller_shop_id})
    if products_resp2.status_code != 200:
        print(f"❌ GET /api/products after rate change failed: {products_resp2.status_code}")
        return False
    
    products2 = products_resp2.json()
    if not products2:
        print("❌ No products found after rate change")
        return False
    
    updated_product = products2[0]
    if updated_product["exchange_rate_ssp"] != new_rate:
        print(f"❌ Product exchange_rate_ssp not updated. Expected {new_rate}, got {updated_product['exchange_rate_ssp']}")
        return False
    
    print(f"✅ After seller rate change, product exchange_rate_ssp updated to {new_rate}")
    
    # Restore original rate (or set to 600 as requested)
    restore_rate = 600.0
    restore_resp = requests.put(f"{BASE_URL}/exchange-rate", json={"rate": restore_rate}, headers=headers)
    if restore_resp.status_code != 200:
        print(f"⚠️  Warning: Failed to restore rate to {restore_rate}: {restore_resp.status_code}")
    else:
        print(f"✅ Restored seller exchange rate to {restore_rate}")
    
    return True

def test_verified_first_sort():
    """
    Test 2: GET /api/products and GET /api/restaurants sort verified items first.
    """
    print("\n=== Test 2: Verified-first sort ===")
    
    # Test products
    products_resp = requests.get(f"{BASE_URL}/products")
    if products_resp.status_code != 200:
        print(f"❌ GET /api/products failed: {products_resp.status_code}")
        return False
    
    products = products_resp.json()
    if not products:
        print("⚠️  No products found, cannot test verified-first sort")
    else:
        first_product = products[0]
        if "shop_verification" not in first_product:
            print(f"❌ First product missing shop_verification field")
            return False
        
        # Check that first product is Verified (or at least not Rejected if no Verified exist)
        first_verification = first_product["shop_verification"]
        print(f"✅ GET /api/products: first product has shop_verification={first_verification}")
        
        # Verify sort order: all Verified should come before Pending/Rejected
        verified_products = [p for p in products if p.get("shop_verification") == "Verified"]
        non_verified_products = [p for p in products if p.get("shop_verification") != "Verified"]
        
        if verified_products and non_verified_products:
            # Find index of last verified and first non-verified
            last_verified_idx = max(i for i, p in enumerate(products) if p.get("shop_verification") == "Verified")
            first_non_verified_idx = min(i for i, p in enumerate(products) if p.get("shop_verification") != "Verified")
            
            if first_non_verified_idx < last_verified_idx:
                print(f"❌ Products not sorted verified-first: non-verified at index {first_non_verified_idx}, verified at {last_verified_idx}")
                return False
            
            print(f"✅ Products correctly sorted: all {len(verified_products)} Verified products before {len(non_verified_products)} non-Verified")
    
    # Test restaurants
    restaurants_resp = requests.get(f"{BASE_URL}/restaurants")
    if restaurants_resp.status_code != 200:
        print(f"❌ GET /api/restaurants failed: {restaurants_resp.status_code}")
        return False
    
    restaurants = restaurants_resp.json()
    if not restaurants:
        print("⚠️  No restaurants found, cannot test verified-first sort")
    else:
        first_restaurant = restaurants[0]
        if "verification" not in first_restaurant:
            print(f"❌ First restaurant missing verification field")
            return False
        
        first_verification = first_restaurant["verification"]
        print(f"✅ GET /api/restaurants: first restaurant has verification={first_verification}")
        
        # Verify sort order
        verified_restaurants = [r for r in restaurants if r.get("verification") == "Verified"]
        non_verified_restaurants = [r for r in restaurants if r.get("verification") != "Verified"]
        
        if verified_restaurants and non_verified_restaurants:
            last_verified_idx = max(i for i, r in enumerate(restaurants) if r.get("verification") == "Verified")
            first_non_verified_idx = min(i for i, r in enumerate(restaurants) if r.get("verification") != "Verified")
            
            if first_non_verified_idx < last_verified_idx:
                print(f"❌ Restaurants not sorted verified-first: non-verified at index {first_non_verified_idx}, verified at {last_verified_idx}")
                return False
            
            print(f"✅ Restaurants correctly sorted: all {len(verified_restaurants)} Verified restaurants before {len(non_verified_restaurants)} non-Verified")
    
    return True

def test_exchange_rate_seller_only():
    """
    Test 3: PUT /api/exchange-rate is seller-only (admin and customer get 403).
    """
    print("\n=== Test 3: PUT /api/exchange-rate is seller-only ===")
    
    # Test admin cannot set rate
    admin_token = login(ADMIN_EMAIL, PASSWORD)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    admin_resp = requests.put(f"{BASE_URL}/exchange-rate", json={"rate": 700}, headers=admin_headers)
    if admin_resp.status_code == 200:
        print(f"❌ Admin was able to PUT /api/exchange-rate (should be 403): {admin_resp.status_code}")
        return False
    if admin_resp.status_code not in [401, 403]:
        print(f"⚠️  Admin got unexpected status code {admin_resp.status_code} (expected 403)")
    
    print(f"✅ Admin cannot PUT /api/exchange-rate (got {admin_resp.status_code})")
    
    # Test customer cannot set rate
    customer_token = login(CUSTOMER_EMAIL, PASSWORD)
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    
    customer_resp = requests.put(f"{BASE_URL}/exchange-rate", json={"rate": 700}, headers=customer_headers)
    if customer_resp.status_code == 200:
        print(f"❌ Customer was able to PUT /api/exchange-rate (should be 403): {customer_resp.status_code}")
        return False
    if customer_resp.status_code not in [401, 403]:
        print(f"⚠️  Customer got unexpected status code {customer_resp.status_code} (expected 403)")
    
    print(f"✅ Customer cannot PUT /api/exchange-rate (got {customer_resp.status_code})")
    
    # Test seller CAN set rate
    seller_token = login(SELLER_EMAIL, PASSWORD)
    seller_headers = {"Authorization": f"Bearer {seller_token}"}
    
    seller_resp = requests.put(f"{BASE_URL}/exchange-rate", json={"rate": 600}, headers=seller_headers)
    if seller_resp.status_code != 200:
        print(f"❌ Seller cannot PUT /api/exchange-rate: {seller_resp.status_code} {seller_resp.text}")
        return False
    
    resp_data = seller_resp.json()
    if "seller_id" not in resp_data or "rate" not in resp_data:
        print(f"❌ Seller PUT response missing fields: {resp_data}")
        return False
    
    if resp_data["rate"] != 600:
        print(f"❌ Seller PUT response has wrong rate: {resp_data['rate']}")
        return False
    
    print(f"✅ Seller can PUT /api/exchange-rate (got 200 with seller_id={resp_data['seller_id']}, rate={resp_data['rate']})")
    
    return True

def main():
    print("=" * 80)
    print("JubaSquare Backend Test - Round 2 Changes")
    print("Testing ONLY: exchange rate embedding, verified-first sort, seller-only rate endpoint")
    print("=" * 80)
    
    results = []
    
    # Test 1: Exchange rate + verification in products
    try:
        results.append(("Exchange rate + verification in products", test_exchange_rate_and_verification_in_products()))
    except Exception as e:
        print(f"❌ Test 1 exception: {e}")
        results.append(("Exchange rate + verification in products", False))
    
    # Test 2: Verified-first sort
    try:
        results.append(("Verified-first sort", test_verified_first_sort()))
    except Exception as e:
        print(f"❌ Test 2 exception: {e}")
        results.append(("Verified-first sort", False))
    
    # Test 3: Seller-only exchange rate endpoint
    try:
        results.append(("Seller-only exchange rate endpoint", test_exchange_rate_seller_only()))
    except Exception as e:
        print(f"❌ Test 3 exception: {e}")
        results.append(("Seller-only exchange rate endpoint", False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 80)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
