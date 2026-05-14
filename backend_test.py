#!/usr/bin/env python3
"""
Backend API Test Suite for Continuation Features
Tests:
1. Kitchen History Endpoint (GET /api/restaurant-orders/restaurant/{restaurant_id}?include_history=true)
2. Admin Shops & Restaurants Combined Endpoint (GET /api/admin/shops-and-restaurants)
3. OTP Endpoints (smoke test)
"""

import requests
import json
from typing import Optional

# Backend URL
BASE_URL = "https://driver-area-filter.preview.emergentagent.com/api"

# Test credentials
ADMIN_EMAIL = "admin@ltg.com"  # Case-sensitive, from backend/.env
ADMIN_PASSWORD = "Kokobleake1"
SELLER_EMAIL = "seller@demo.com"
SELLER_PASSWORD = "Demo1234!"

# Global tokens
admin_token = None
seller_token = None

def login(email: str, password: str) -> Optional[str]:
    """Login and return token"""
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("token")
        else:
            print(f"❌ Login failed for {email}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Login exception for {email}: {e}")
        return None

def test_kitchen_history_endpoint():
    """Test GET /api/restaurant-orders/restaurant/{restaurant_id}?include_history=true"""
    print("\n" + "="*80)
    print("TEST 1: Kitchen History Endpoint")
    print("="*80)
    
    global seller_token
    
    # Login as seller
    print("\n1.1 Login as seller...")
    seller_token = login(SELLER_EMAIL, SELLER_PASSWORD)
    if not seller_token:
        print("❌ FAILED: Could not login as seller")
        return False
    print("✅ Seller login successful")
    
    headers = {"Authorization": f"Bearer {seller_token}"}
    
    # Create a test restaurant for the seller
    print("\n1.2 Create test restaurant...")
    try:
        # Create a restaurant
        create_response = requests.post(
            f"{BASE_URL}/restaurants",
            headers=headers,
            json={
                "name": "Test Restaurant for History",
                "description": "Test restaurant for kitchen history endpoint",
                "cuisine_type": "African",
                "area": "Juba",
                "address": "Test Address, Juba",
                "phone": "+211912345678",
                "delivery_fee_usd": 2.0
            },
            timeout=10
        )
        if create_response.status_code not in [200, 201]:
            # If restaurant already exists, try to get it
            if create_response.status_code == 400 and "already exists" in create_response.text.lower():
                print("⚠️  Restaurant already exists, fetching all restaurants...")
                all_rest = requests.get(f"{BASE_URL}/restaurants", timeout=10)
                if all_rest.status_code == 200:
                    restaurants = all_rest.json()
                    # Find one that belongs to this seller (we'll just use the first one)
                    if restaurants:
                        restaurant_id = restaurants[0]["id"]
                        print(f"✅ Using existing restaurant: {restaurant_id}")
                    else:
                        print(f"❌ FAILED: No restaurants found")
                        return False
                else:
                    print(f"❌ FAILED: Could not get restaurants: {all_rest.status_code}")
                    return False
            else:
                print(f"❌ FAILED: Could not create restaurant: {create_response.status_code} - {create_response.text}")
                return False
        else:
            restaurant = create_response.json()
            restaurant_id = restaurant["id"]
            print(f"✅ Created restaurant: {restaurant_id}")
    except Exception as e:
        print(f"❌ FAILED: Exception creating restaurant: {e}")
        return False
    
    # Test 1.3: Get orders WITHOUT include_history (should exclude historical orders)
    print(f"\n1.3 Test WITHOUT include_history param...")
    try:
        response = requests.get(
            f"{BASE_URL}/restaurant-orders/restaurant/{restaurant_id}",
            headers=headers,
            timeout=10
        )
        if response.status_code != 200:
            print(f"❌ FAILED: GET without include_history returned {response.status_code}: {response.text}")
            return False
        
        orders_without_history = response.json()
        print(f"✅ GET without include_history returned {len(orders_without_history)} orders")
        
        # Verify no historical orders (handed_to_driver, completed, cancelled)
        historical_statuses = ["handed_to_driver", "completed", "cancelled", "cancel_approved"]
        historical_delivery = ["delivered", "returned_to_seller"]
        
        for order in orders_without_history:
            if order.get("seller_preparation_status") in ["handed_to_driver"]:
                print(f"❌ FAILED: Found order with seller_preparation_status=handed_to_driver without include_history")
                return False
            if order.get("status") in ["completed", "cancelled", "cancel_approved"]:
                print(f"❌ FAILED: Found order with status={order.get('status')} without include_history")
                return False
            if order.get("delivery_status") in ["delivered", "returned_to_seller"]:
                print(f"❌ FAILED: Found order with delivery_status={order.get('delivery_status')} without include_history")
                return False
        
        print("✅ Verified: No historical orders in response without include_history")
        
    except Exception as e:
        print(f"❌ FAILED: Exception in test without include_history: {e}")
        return False
    
    # Test 1.4: Get orders WITH include_history=true (should include all orders)
    print(f"\n1.4 Test WITH include_history=true...")
    try:
        response = requests.get(
            f"{BASE_URL}/restaurant-orders/restaurant/{restaurant_id}?include_history=true",
            headers=headers,
            timeout=10
        )
        if response.status_code != 200:
            print(f"❌ FAILED: GET with include_history=true returned {response.status_code}: {response.text}")
            return False
        
        orders_with_history = response.json()
        print(f"✅ GET with include_history=true returned {len(orders_with_history)} orders")
        
        # Verify count is >= without history
        if len(orders_with_history) < len(orders_without_history):
            print(f"❌ FAILED: include_history=true returned fewer orders ({len(orders_with_history)}) than without ({len(orders_without_history)})")
            return False
        
        print(f"✅ Verified: include_history=true returned >= orders ({len(orders_with_history)} >= {len(orders_without_history)})")
        
        # Check if any historical orders exist
        has_historical = False
        for order in orders_with_history:
            if (order.get("seller_preparation_status") == "handed_to_driver" or
                order.get("status") in ["completed", "cancelled", "cancel_approved"] or
                order.get("delivery_status") in ["delivered", "returned_to_seller"]):
                has_historical = True
                print(f"✅ Found historical order: status={order.get('status')}, seller_prep={order.get('seller_preparation_status')}, delivery={order.get('delivery_status')}")
                break
        
        if not has_historical and len(orders_with_history) > 0:
            print("⚠️  Note: No historical orders found in the system (this is OK if no orders have been completed yet)")
        
    except Exception as e:
        print(f"❌ FAILED: Exception in test with include_history: {e}")
        return False
    
    print("\n✅ PASSED: Kitchen History Endpoint tests completed successfully")
    return True

def test_admin_shops_restaurants_endpoint():
    """Test GET /api/admin/shops-and-restaurants"""
    print("\n" + "="*80)
    print("TEST 2: Admin Shops & Restaurants Combined Endpoint")
    print("="*80)
    
    global admin_token
    
    # Login as admin
    print("\n2.1 Login as admin...")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        print("❌ FAILED: Could not login as admin")
        return False
    print("✅ Admin login successful")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Test 2.2: Get both shops and restaurants (no type_filter)
    print("\n2.2 Test WITHOUT type_filter (should return both)...")
    try:
        response = requests.get(
            f"{BASE_URL}/admin/shops-and-restaurants",
            headers=headers,
            timeout=10
        )
        if response.status_code != 200:
            print(f"❌ FAILED: GET without type_filter returned {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        
        # Verify response structure
        required_keys = ["shops", "restaurants", "total_shops", "total_restaurants"]
        for key in required_keys:
            if key not in data:
                print(f"❌ FAILED: Missing key '{key}' in response")
                return False
        
        print(f"✅ Response has correct structure: {required_keys}")
        print(f"   - shops: {len(data['shops'])} items, total_shops: {data['total_shops']}")
        print(f"   - restaurants: {len(data['restaurants'])} items, total_restaurants: {data['total_restaurants']}")
        
        # Verify both arrays are populated (if data exists)
        if data['total_shops'] > 0 and len(data['shops']) == 0:
            print(f"❌ FAILED: total_shops={data['total_shops']} but shops array is empty")
            return False
        
        if data['total_restaurants'] > 0 and len(data['restaurants']) == 0:
            print(f"❌ FAILED: total_restaurants={data['total_restaurants']} but restaurants array is empty")
            return False
        
        print("✅ Verified: Both shops and restaurants returned when no type_filter")
        
    except Exception as e:
        print(f"❌ FAILED: Exception in test without type_filter: {e}")
        return False
    
    # Test 2.3: Get only shops (type_filter="shops")
    print("\n2.3 Test WITH type_filter='shops' (should return only shops)...")
    try:
        response = requests.get(
            f"{BASE_URL}/admin/shops-and-restaurants?type_filter=shops",
            headers=headers,
            timeout=10
        )
        if response.status_code != 200:
            print(f"❌ FAILED: GET with type_filter=shops returned {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        
        # Verify restaurants array is empty
        if len(data['restaurants']) != 0:
            print(f"❌ FAILED: type_filter=shops but restaurants array has {len(data['restaurants'])} items")
            return False
        
        # Verify total_restaurants is 0
        if data['total_restaurants'] != 0:
            print(f"❌ FAILED: type_filter=shops but total_restaurants={data['total_restaurants']}")
            return False
        
        print(f"✅ Verified: Only shops returned (shops: {len(data['shops'])}, restaurants: 0)")
        
    except Exception as e:
        print(f"❌ FAILED: Exception in test with type_filter=shops: {e}")
        return False
    
    # Test 2.4: Get only restaurants (type_filter="restaurants")
    print("\n2.4 Test WITH type_filter='restaurants' (should return only restaurants)...")
    try:
        response = requests.get(
            f"{BASE_URL}/admin/shops-and-restaurants?type_filter=restaurants",
            headers=headers,
            timeout=10
        )
        if response.status_code != 200:
            print(f"❌ FAILED: GET with type_filter=restaurants returned {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        
        # Verify shops array is empty
        if len(data['shops']) != 0:
            print(f"❌ FAILED: type_filter=restaurants but shops array has {len(data['shops'])} items")
            return False
        
        # Verify total_shops is 0
        if data['total_shops'] != 0:
            print(f"❌ FAILED: type_filter=restaurants but total_shops={data['total_shops']}")
            return False
        
        print(f"✅ Verified: Only restaurants returned (restaurants: {len(data['restaurants'])}, shops: 0)")
        
    except Exception as e:
        print(f"❌ FAILED: Exception in test with type_filter=restaurants: {e}")
        return False
    
    # Test 2.5: Test pagination
    print("\n2.5 Test pagination (limit=2)...")
    try:
        response = requests.get(
            f"{BASE_URL}/admin/shops-and-restaurants?limit=2",
            headers=headers,
            timeout=10
        )
        if response.status_code != 200:
            print(f"❌ FAILED: GET with limit=2 returned {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        
        # Verify pagination works (should return at most 2 items per array)
        if len(data['shops']) > 2:
            print(f"❌ FAILED: limit=2 but shops array has {len(data['shops'])} items")
            return False
        
        if len(data['restaurants']) > 2:
            print(f"❌ FAILED: limit=2 but restaurants array has {len(data['restaurants'])} items")
            return False
        
        print(f"✅ Verified: Pagination works (shops: {len(data['shops'])}, restaurants: {len(data['restaurants'])})")
        
    except Exception as e:
        print(f"❌ FAILED: Exception in pagination test: {e}")
        return False
    
    print("\n✅ PASSED: Admin Shops & Restaurants Combined Endpoint tests completed successfully")
    return True

def test_otp_endpoints_smoke():
    """Smoke test for OTP endpoints"""
    print("\n" + "="*80)
    print("TEST 3: OTP Endpoints (Smoke Test)")
    print("="*80)
    
    global admin_token
    
    # Ensure admin is logged in
    if not admin_token:
        print("\n3.1 Login as admin...")
        admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
        if not admin_token:
            print("❌ FAILED: Could not login as admin")
            return False
        print("✅ Admin login successful")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Test 3.2: Check if generate-otp endpoint exists (expect 404 for non-existent payout)
    print("\n3.2 Test POST /api/admin/payouts/{id}/generate-otp endpoint exists...")
    try:
        fake_payout_id = "nonexistent-payout-id"
        response = requests.post(
            f"{BASE_URL}/admin/payouts/{fake_payout_id}/generate-otp",
            headers=headers,
            timeout=10
        )
        
        # We expect 404 (payout not found) which means endpoint exists
        if response.status_code == 404:
            print("✅ Endpoint exists (returned 404 for non-existent payout as expected)")
        elif response.status_code == 401:
            print("❌ FAILED: Endpoint returned 401 (auth issue)")
            return False
        elif response.status_code == 405:
            print("❌ FAILED: Endpoint returned 405 (method not allowed - endpoint may not exist)")
            return False
        else:
            print(f"✅ Endpoint exists (returned {response.status_code})")
        
    except Exception as e:
        print(f"❌ FAILED: Exception testing generate-otp endpoint: {e}")
        return False
    
    # Test 3.3: Check if confirm-otp endpoint exists (expect 404 for non-existent payout)
    print("\n3.3 Test POST /api/admin/payouts/{id}/confirm-otp endpoint exists...")
    try:
        fake_payout_id = "nonexistent-payout-id"
        response = requests.post(
            f"{BASE_URL}/admin/payouts/{fake_payout_id}/confirm-otp",
            headers=headers,
            json={"otp": "1234"},
            timeout=10
        )
        
        # We expect 404 (payout not found) or 422 (validation error) which means endpoint exists
        if response.status_code in [404, 422]:
            print(f"✅ Endpoint exists (returned {response.status_code} as expected)")
        elif response.status_code == 401:
            print("❌ FAILED: Endpoint returned 401 (auth issue)")
            return False
        elif response.status_code == 405:
            print("❌ FAILED: Endpoint returned 405 (method not allowed - endpoint may not exist)")
            return False
        else:
            print(f"✅ Endpoint exists (returned {response.status_code})")
        
    except Exception as e:
        print(f"❌ FAILED: Exception testing confirm-otp endpoint: {e}")
        return False
    
    print("\n✅ PASSED: OTP Endpoints smoke tests completed successfully")
    return True

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("BACKEND API TEST SUITE - CONTINUATION FEATURES")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    
    results = {
        "Kitchen History Endpoint": False,
        "Admin Shops & Restaurants Endpoint": False,
        "OTP Endpoints (Smoke Test)": False
    }
    
    # Run tests
    try:
        results["Kitchen History Endpoint"] = test_kitchen_history_endpoint()
    except Exception as e:
        print(f"\n❌ EXCEPTION in Kitchen History test: {e}")
    
    try:
        results["Admin Shops & Restaurants Endpoint"] = test_admin_shops_restaurants_endpoint()
    except Exception as e:
        print(f"\n❌ EXCEPTION in Admin Shops & Restaurants test: {e}")
    
    try:
        results["OTP Endpoints (Smoke Test)"] = test_otp_endpoints_smoke()
    except Exception as e:
        print(f"\n❌ EXCEPTION in OTP Endpoints test: {e}")
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    total_tests = len(results)
    passed_tests = sum(1 for passed in results.values() if passed)
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total_tests - passed_tests} test(s) failed")
        return 1

if __name__ == "__main__":
    exit(main())
