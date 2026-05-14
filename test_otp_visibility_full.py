#!/usr/bin/env python3
"""
Full test for customer delivery OTP visibility fix with data setup
"""
import requests
import json
import sys

BASE_URL = "https://driver-area-filter.preview.emergentagent.com/api"

# Test credentials
ADMIN_EMAIL = "admin@ltg.com"
ADMIN_PASSWORD = "Kokobleake1"
CUSTOMER_EMAIL = "customer@demo.com"
CUSTOMER_PASSWORD = "123456"
SELLER_EMAIL = "seller@demo.com"
SELLER_PASSWORD = "123456"

admin_token = None
customer_token = None
seller_token = None
seller_id = None
shop_id = None
product_id = None
order_id = None
category_id = None


def log(msg: str):
    print(f"  {msg}")


def login(email: str, password: str):
    """Login and return token + user"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        data = resp.json()
        return data.get("token"), data.get("user")
    return None, None


def test_1_login_all():
    """Test 1: Login all users"""
    global admin_token, customer_token, seller_token, seller_id
    
    log("Logging in as admin...")
    admin_token, _ = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert admin_token, "Admin login failed"
    log("✅ Admin logged in")
    
    log("Logging in as customer...")
    customer_token, _ = login(CUSTOMER_EMAIL, CUSTOMER_PASSWORD)
    assert customer_token, "Customer login failed"
    log("✅ Customer logged in")
    
    log("Logging in as seller...")
    seller_token, seller_user = login(SELLER_EMAIL, SELLER_PASSWORD)
    assert seller_token, "Seller login failed"
    seller_id = seller_user.get("id")
    log(f"✅ Seller logged in (ID: {seller_id})")


def test_2_get_category():
    """Test 2: Get a retail category ID"""
    global category_id
    
    log("Fetching categories...")
    resp = requests.get(f"{BASE_URL}/categories?group=retail")
    assert resp.status_code == 200, f"Failed to fetch categories: {resp.status_code}"
    
    categories = resp.json()
    assert len(categories) > 0, "No retail categories found"
    
    category_id = categories[0]["id"]
    log(f"✅ Using category: {categories[0]['name']} ({category_id})")


def test_3_create_shop():
    """Test 3: Create a shop for the seller"""
    global shop_id
    
    log("Creating shop...")
    headers = {"Authorization": f"Bearer {seller_token}"}
    shop_data = {
        "name": "Test Shop for OTP Testing",
        "description": "A test shop",
        "category": "Electronics",
        "phone": "+211 900 000 100",
        "area": "Munuki",
        "address": "Test Address",
        "delivery_mode": "fixed",
        "delivery_fee_usd": 3.0
    }
    
    resp = requests.post(f"{BASE_URL}/shops", json=shop_data, headers=headers)
    assert resp.status_code == 200, f"Failed to create shop: {resp.status_code} - {resp.text}"
    
    shop_id = resp.json()["id"]
    log(f"✅ Shop created (ID: {shop_id})")
    
    # Verify shop as admin
    log("Verifying shop as admin...")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.put(f"{BASE_URL}/admin/shops/{shop_id}/verify", 
                       json={"verification": "Verified"}, 
                       headers=admin_headers)
    if resp.status_code == 200:
        log("✅ Shop verified")
    else:
        log(f"⚠️ Shop verification failed: {resp.status_code}")


def test_4_create_product():
    """Test 4: Create a product"""
    global product_id
    
    log("Creating product...")
    headers = {"Authorization": f"Bearer {seller_token}"}
    product_data = {
        "name": "Test Product for OTP",
        "description": "A test product",
        "category_id": category_id,
        "price_usd": 50.0,
        "stock": 100,
        "shop_id": shop_id,
        "is_wholesale": False,
        "image_url": "https://via.placeholder.com/300"
    }
    
    resp = requests.post(f"{BASE_URL}/products", json=product_data, headers=headers)
    assert resp.status_code == 200, f"Failed to create product: {resp.status_code} - {resp.text}"
    
    product_id = resp.json()["id"]
    log(f"✅ Product created (ID: {product_id})")


def test_5_place_cod_order():
    """Test 5: Place a COD order as customer"""
    global order_id
    
    log("Placing COD order as customer...")
    headers = {"Authorization": f"Bearer {customer_token}"}
    order_data = {
        "items": [
            {
                "item_type": "product",
                "item_id": product_id,
                "name": "Test Product for OTP",
                "quantity": 2,
                "price_usd": 50.0,
                "image_url": "https://via.placeholder.com/300"
            }
        ],
        "area": "Munuki",
        "address": "Customer Test Address",
        "phone": "+211 900 000 001",
        "order_kind": "marketplace"
    }
    
    resp = requests.post(f"{BASE_URL}/orders", json=order_data, headers=headers)
    assert resp.status_code == 200, f"Failed to place order: {resp.status_code} - {resp.text}"
    
    order = resp.json()
    order_id = order.get("id")
    log(f"✅ Order placed (ID: {order_id})")
    log(f"   Payment method: {order.get('payment_method')}")
    log(f"   Total: ${order.get('total_usd')}")


def test_6_customer_order_splits():
    """Test 6: Check GET /customer/orders/{order_id}/splits - CRITICAL TEST"""
    log(f"Fetching splits for order {order_id}...")
    headers = {"Authorization": f"Bearer {customer_token}"}
    resp = requests.get(f"{BASE_URL}/customer/orders/{order_id}/splits", headers=headers)
    
    assert resp.status_code == 200, f"Failed to fetch splits: {resp.status_code} - {resp.text}"
    
    splits = resp.json()
    log(f"✅ Fetched {len(splits)} splits")
    
    assert len(splits) > 0, "No splits found for order"
    
    # Check first split for OTP visibility
    split = splits[0]
    log(f"Checking split {split.get('id')}...")
    
    # Verify required fields
    assert "id" in split, "Split missing 'id' field"
    assert "delivery_status" in split, "Split missing 'delivery_status' field"
    log(f"  Delivery status: {split['delivery_status']}")
    
    # CRITICAL: Check customer_delivery_otp is present
    if "customer_delivery_otp" in split:
        log(f"  ✅ customer_delivery_otp is present: {split['customer_delivery_otp']}")
    else:
        log(f"  ❌ FAIL: customer_delivery_otp is NOT present")
        log(f"  Split keys: {list(split.keys())}")
        raise AssertionError("customer_delivery_otp missing from customer split response")
    
    # CRITICAL: Check seller_pickup_otp is NOT exposed
    if "seller_pickup_otp" in split and split["seller_pickup_otp"] is not None:
        log(f"  ❌ FAIL: seller_pickup_otp is EXPOSED: {split['seller_pickup_otp']}")
        raise AssertionError("seller_pickup_otp should NOT be exposed to customer")
    else:
        log(f"  ✅ seller_pickup_otp is correctly NOT exposed")
    
    # CRITICAL: Check return_otp is NOT exposed
    if "return_otp" in split and split["return_otp"] is not None:
        log(f"  ❌ FAIL: return_otp is EXPOSED: {split['return_otp']}")
        raise AssertionError("return_otp should NOT be exposed to customer")
    else:
        log(f"  ✅ return_otp is correctly NOT exposed")
    
    log(f"✅ Split OTP visibility is CORRECT")


def test_7_seller_wallet():
    """Test 7: Check GET /seller/wallet"""
    log("Fetching seller wallet...")
    headers = {"Authorization": f"Bearer {seller_token}"}
    resp = requests.get(f"{BASE_URL}/seller/wallet", headers=headers)
    assert resp.status_code == 200, f"Failed to fetch wallet: {resp.status_code} - {resp.text}"
    
    wallet = resp.json()
    log(f"✅ Seller wallet fetched")
    
    expected_fields = [
        "pending_cash_collection", "cash_with_driver", "ready_for_payout",
        "pending_payout", "paid_total", "commission_deducted", "returned_or_failed"
    ]
    
    for field in expected_fields:
        assert field in wallet, f"Wallet missing field: {field}"
    
    log(f"  pending_cash_collection: ${wallet['pending_cash_collection']}")
    log(f"✅ All wallet fields present")


def test_8_seller_splits():
    """Test 8: Check GET /seller/splits"""
    log("Fetching seller splits...")
    headers = {"Authorization": f"Bearer {seller_token}"}
    resp = requests.get(f"{BASE_URL}/seller/splits", headers=headers)
    assert resp.status_code == 200, f"Failed to fetch splits: {resp.status_code} - {resp.text}"
    
    splits = resp.json()
    log(f"✅ Seller has {len(splits)} splits")


def test_9_seller_restaurant_orders_cod():
    """Test 9: Check GET /seller/restaurant-orders-cod"""
    log("Fetching seller restaurant orders (COD)...")
    headers = {"Authorization": f"Bearer {seller_token}"}
    resp = requests.get(f"{BASE_URL}/seller/restaurant-orders-cod", headers=headers)
    assert resp.status_code == 200, f"Failed to fetch orders: {resp.status_code} - {resp.text}"
    
    orders = resp.json()
    log(f"✅ Seller has {len(orders)} restaurant orders (COD)")


def test_10_seller_payouts():
    """Test 10: Check GET /seller/payouts"""
    log("Fetching seller payouts...")
    headers = {"Authorization": f"Bearer {seller_token}"}
    resp = requests.get(f"{BASE_URL}/seller/payouts", headers=headers)
    assert resp.status_code == 200, f"Failed to fetch payouts: {resp.status_code} - {resp.text}"
    
    payouts = resp.json()
    log(f"✅ Seller has {len(payouts)} payouts")


def main():
    print("\n" + "="*80)
    print("FULL TEST: Customer Delivery OTP Visibility Fix (with data setup)")
    print("="*80 + "\n")
    
    tests = [
        ("Login All Users", test_1_login_all),
        ("Get Category", test_2_get_category),
        ("Create Shop", test_3_create_shop),
        ("Create Product", test_4_create_product),
        ("Place COD Order", test_5_place_cod_order),
        ("Customer Order Splits OTP Visibility", test_6_customer_order_splits),
        ("Seller Wallet", test_7_seller_wallet),
        ("Seller Splits", test_8_seller_splits),
        ("Seller Restaurant Orders COD", test_9_seller_restaurant_orders_cod),
        ("Seller Payouts", test_10_seller_payouts),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        print(f"\n{'─'*80}")
        print(f"Test: {name}")
        print(f"{'─'*80}")
        try:
            test_func()
            passed += 1
            print(f"✅ PASSED: {name}")
        except AssertionError as e:
            failed += 1
            print(f"❌ FAILED: {name}")
            print(f"   Error: {e}")
            break  # Stop on first failure
        except Exception as e:
            failed += 1
            print(f"❌ ERROR: {name}")
            print(f"   Error: {e}")
            break  # Stop on first failure
    
    print(f"\n{'='*80}")
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print(f"{'='*80}\n")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
