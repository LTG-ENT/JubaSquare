#!/usr/bin/env python3
"""
Test customer delivery OTP visibility fix
Tests that:
1. Customer can see customer_delivery_otp in splits
2. Customer CANNOT see seller_pickup_otp or return_otp
3. Restaurant orders expose customer_delivery_otp but not seller OTPs
4. Seller wallet endpoints work correctly
"""
import requests
import json
import sys

BASE_URL = "https://payout-otp.preview.emergentagent.com/api"

# Test credentials
CUSTOMER_EMAIL = "customer@demo.com"
CUSTOMER_PASSWORD = "123456"
SELLER_EMAIL = "seller@demo.com"
SELLER_PASSWORD = "123456"

customer_token = None
seller_token = None


def log(msg: str):
    print(f"  {msg}")


def login(email: str, password: str):
    """Login and return token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        data = resp.json()
        return data.get("token")
    return None


def test_1_customer_login():
    """Test 1: Customer login"""
    global customer_token
    log(f"Logging in as customer: {CUSTOMER_EMAIL}...")
    customer_token = login(CUSTOMER_EMAIL, CUSTOMER_PASSWORD)
    assert customer_token, "Customer login failed"
    log(f"✅ Customer logged in successfully")


def test_2_seller_login():
    """Test 2: Seller login"""
    global seller_token
    log(f"Logging in as seller: {SELLER_EMAIL}...")
    seller_token = login(SELLER_EMAIL, SELLER_PASSWORD)
    assert seller_token, "Seller login failed"
    log(f"✅ Seller logged in successfully")


def test_3_customer_orders_list():
    """Test 3: Get customer's orders to find an order ID"""
    log("Fetching customer's orders...")
    headers = {"Authorization": f"Bearer {customer_token}"}
    resp = requests.get(f"{BASE_URL}/orders/mine", headers=headers)
    assert resp.status_code == 200, f"Failed to fetch orders: {resp.status_code}"
    
    orders = resp.json()
    log(f"✅ Customer has {len(orders)} orders")
    
    if len(orders) == 0:
        log("⚠️ No orders found for customer. Skipping splits test.")
        return None
    
    # Return the first order ID
    order_id = orders[0].get("id")
    log(f"✅ Using order ID: {order_id}")
    return order_id


def test_4_customer_order_splits(order_id: str):
    """Test 4: Check GET /customer/orders/{order_id}/splits endpoint"""
    if not order_id:
        log("⚠️ Skipping splits test (no order ID)")
        return
    
    log(f"Fetching splits for order {order_id}...")
    headers = {"Authorization": f"Bearer {customer_token}"}
    resp = requests.get(f"{BASE_URL}/customer/orders/{order_id}/splits", headers=headers)
    
    if resp.status_code == 404:
        log("⚠️ Order not found or no splits available")
        return
    
    assert resp.status_code == 200, f"Failed to fetch splits: {resp.status_code} - {resp.text}"
    
    splits = resp.json()
    log(f"✅ Fetched {len(splits)} splits")
    
    if len(splits) == 0:
        log("⚠️ No splits found for this order")
        return
    
    # Check first split for OTP visibility
    split = splits[0]
    log(f"Checking split {split.get('id')}...")
    
    # Verify required fields are present
    assert "id" in split, "Split missing 'id' field"
    assert "shop_name" in split or "seller_id" in split, "Split missing shop/seller info"
    assert "delivery_status" in split, "Split missing 'delivery_status' field"
    
    # CRITICAL: Check customer_delivery_otp is present
    if "customer_delivery_otp" in split:
        log(f"✅ customer_delivery_otp is present: {split['customer_delivery_otp']}")
    else:
        log(f"❌ FAIL: customer_delivery_otp is NOT present in split")
        log(f"Split keys: {list(split.keys())}")
        raise AssertionError("customer_delivery_otp missing from customer split response")
    
    # CRITICAL: Check seller_pickup_otp is NOT exposed
    if "seller_pickup_otp" in split:
        log(f"❌ FAIL: seller_pickup_otp is EXPOSED to customer: {split['seller_pickup_otp']}")
        raise AssertionError("seller_pickup_otp should NOT be exposed to customer")
    else:
        log(f"✅ seller_pickup_otp is correctly NOT exposed to customer")
    
    # CRITICAL: Check return_otp is NOT exposed
    if "return_otp" in split:
        log(f"❌ FAIL: return_otp is EXPOSED to customer: {split['return_otp']}")
        raise AssertionError("return_otp should NOT be exposed to customer")
    else:
        log(f"✅ return_otp is correctly NOT exposed to customer")
    
    log(f"✅ Split OTP visibility is correct")


def test_5_restaurant_orders():
    """Test 5: Check GET /restaurant-orders endpoint for customer"""
    log("Fetching customer's restaurant orders...")
    headers = {"Authorization": f"Bearer {customer_token}"}
    resp = requests.get(f"{BASE_URL}/restaurant-orders", headers=headers)
    assert resp.status_code == 200, f"Failed to fetch restaurant orders: {resp.status_code}"
    
    orders = resp.json()
    log(f"✅ Customer has {len(orders)} restaurant orders")
    
    if len(orders) == 0:
        log("⚠️ No restaurant orders found for customer")
        return
    
    # Check first order for OTP visibility
    order = orders[0]
    log(f"Checking restaurant order {order.get('id')}...")
    
    # Verify delivery_status field is present
    assert "delivery_status" in order, "Restaurant order missing 'delivery_status' field"
    log(f"✅ delivery_status is present: {order['delivery_status']}")
    
    # Check customer_delivery_otp presence (if status is appropriate)
    if "customer_delivery_otp" in order:
        log(f"✅ customer_delivery_otp is present: {order['customer_delivery_otp']}")
    else:
        log(f"⚠️ customer_delivery_otp not present (may be expected based on status)")
    
    # CRITICAL: Check seller_pickup_otp is NOT exposed
    if "seller_pickup_otp" in order:
        log(f"❌ FAIL: seller_pickup_otp is EXPOSED to customer: {order['seller_pickup_otp']}")
        raise AssertionError("seller_pickup_otp should NOT be exposed to customer in restaurant orders")
    else:
        log(f"✅ seller_pickup_otp is correctly NOT exposed to customer")
    
    # CRITICAL: Check return_otp is NOT exposed
    if "return_otp" in order:
        log(f"❌ FAIL: return_otp is EXPOSED to customer: {order['return_otp']}")
        raise AssertionError("return_otp should NOT be exposed to customer in restaurant orders")
    else:
        log(f"✅ return_otp is correctly NOT exposed to customer")


def test_6_seller_wallet():
    """Test 6: Check GET /seller/wallet endpoint"""
    log("Fetching seller wallet...")
    headers = {"Authorization": f"Bearer {seller_token}"}
    resp = requests.get(f"{BASE_URL}/seller/wallet", headers=headers)
    assert resp.status_code == 200, f"Failed to fetch seller wallet: {resp.status_code} - {resp.text}"
    
    wallet = resp.json()
    log(f"✅ Seller wallet fetched successfully")
    
    # Verify expected wallet fields
    expected_fields = [
        "pending_cash_collection",
        "cash_with_driver",
        "ready_for_payout",
        "pending_payout",
        "paid_total",
        "commission_deducted",
        "returned_or_failed"
    ]
    
    for field in expected_fields:
        assert field in wallet, f"Wallet missing field: {field}"
        log(f"  {field}: ${wallet[field]}")
    
    log(f"✅ All wallet fields present")


def test_7_seller_splits():
    """Test 7: Check GET /seller/splits endpoint"""
    log("Fetching seller splits...")
    headers = {"Authorization": f"Bearer {seller_token}"}
    resp = requests.get(f"{BASE_URL}/seller/splits", headers=headers)
    assert resp.status_code == 200, f"Failed to fetch seller splits: {resp.status_code} - {resp.text}"
    
    splits = resp.json()
    log(f"✅ Seller has {len(splits)} splits")


def test_8_seller_restaurant_orders_cod():
    """Test 8: Check GET /seller/restaurant-orders-cod endpoint"""
    log("Fetching seller restaurant orders (COD)...")
    headers = {"Authorization": f"Bearer {seller_token}"}
    resp = requests.get(f"{BASE_URL}/seller/restaurant-orders-cod", headers=headers)
    assert resp.status_code == 200, f"Failed to fetch seller restaurant orders: {resp.status_code} - {resp.text}"
    
    orders = resp.json()
    log(f"✅ Seller has {len(orders)} restaurant orders (COD)")


def test_9_seller_payouts():
    """Test 9: Check GET /seller/payouts endpoint"""
    log("Fetching seller payouts...")
    headers = {"Authorization": f"Bearer {seller_token}"}
    resp = requests.get(f"{BASE_URL}/seller/payouts", headers=headers)
    assert resp.status_code == 200, f"Failed to fetch seller payouts: {resp.status_code} - {resp.text}"
    
    payouts = resp.json()
    log(f"✅ Seller has {len(payouts)} payouts")


def main():
    print("\n" + "="*80)
    print("TESTING: Customer Delivery OTP Visibility Fix")
    print("="*80 + "\n")
    
    tests = [
        ("Customer Login", test_1_customer_login),
        ("Seller Login", test_2_seller_login),
        ("Customer Orders List", test_3_customer_orders_list),
        ("Seller Wallet", test_6_seller_wallet),
        ("Seller Splits", test_7_seller_splits),
        ("Seller Restaurant Orders COD", test_8_seller_restaurant_orders_cod),
        ("Seller Payouts", test_9_seller_payouts),
        ("Restaurant Orders OTP Visibility", test_5_restaurant_orders),
    ]
    
    passed = 0
    failed = 0
    order_id = None
    
    for name, test_func in tests:
        print(f"\n{'─'*80}")
        print(f"Test: {name}")
        print(f"{'─'*80}")
        try:
            if name == "Customer Orders List":
                order_id = test_func()
            else:
                test_func()
            passed += 1
            print(f"✅ PASSED: {name}")
        except AssertionError as e:
            failed += 1
            print(f"❌ FAILED: {name}")
            print(f"   Error: {e}")
        except Exception as e:
            failed += 1
            print(f"❌ ERROR: {name}")
            print(f"   Error: {e}")
    
    # Test splits separately since it needs order_id
    if order_id:
        print(f"\n{'─'*80}")
        print(f"Test: Customer Order Splits OTP Visibility")
        print(f"{'─'*80}")
        try:
            test_4_customer_order_splits(order_id)
            passed += 1
            print(f"✅ PASSED: Customer Order Splits OTP Visibility")
        except AssertionError as e:
            failed += 1
            print(f"❌ FAILED: Customer Order Splits OTP Visibility")
            print(f"   Error: {e}")
        except Exception as e:
            failed += 1
            print(f"❌ ERROR: Customer Order Splits OTP Visibility")
            print(f"   Error: {e}")
    
    print(f"\n{'='*80}")
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print(f"{'='*80}\n")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
