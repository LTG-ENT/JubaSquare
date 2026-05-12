#!/usr/bin/env python3
"""
Backend test for Iter 6.9: GET /api/restaurant-orders has_review enrichment
"""
import requests
import json
import time
from pymongo import MongoClient
import os

# Configuration
BASE_URL = "https://order-updates-hub.preview.emergentagent.com/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")

# Test credentials
ADMIN_EMAIL = "admin@ltg.com"
ADMIN_PASSWORD = "Kokobleake1"

# Test user credentials (will be created)
CUSTOMER_EMAIL = f"test_customer_{int(time.time())}@example.com"
CUSTOMER_PASSWORD = "TestPass123!"
CUSTOMER_NAME = "Test Customer"

SELLER_EMAIL = f"test_seller_{int(time.time())}@example.com"
SELLER_PASSWORD = "TestPass123!"
SELLER_NAME = "Test Seller"

# MongoDB client
mongo_client = MongoClient(MONGO_URL)
db = mongo_client["jubasquare_db"]

def print_test(msg):
    print(f"\n{'='*80}")
    print(f"TEST: {msg}")
    print('='*80)

def print_result(passed, msg):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {msg}")

def signup_user(email, password, name, role="customer"):
    """Sign up a new user"""
    response = requests.post(f"{BASE_URL}/auth/signup", json={
        "email": email,
        "password": password,
        "name": name,
        "phone": "+211912345678",
        "role": role
    })
    return response

def verify_email_in_db(email):
    """Manually verify email in MongoDB (since SMTP is in no-op mode)"""
    result = db.users.update_one(
        {"email": email},
        {"$set": {"email_verified": True}}
    )
    return result.modified_count > 0

def login_user(email, password):
    """Login and return token"""
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": password
    })
    if response.status_code == 200:
        return response.json()["token"]
    return None

def create_restaurant(token, name):
    """Create a restaurant as seller"""
    response = requests.post(
        f"{BASE_URL}/restaurants",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "description": "Test restaurant for review testing",
            "category": "International",
            "area": "Juba",
            "image_url": "https://via.placeholder.com/400x300",
            "is_open": True,
            "delivery_pricing": {
                "type": "fixed",
                "fixed_fee": 2.0
            }
        }
    )
    return response

def add_menu_item(token, restaurant_id, name, price, category_id):
    """Add a menu item to restaurant"""
    response = requests.post(
        f"{BASE_URL}/menu-items",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "restaurant_id": restaurant_id,
            "name": name,
            "description": "Test menu item",
            "price_usd": price,
            "category_id": category_id,
            "image_url": "https://via.placeholder.com/300x200"
        }
    )
    return response

def place_restaurant_order(token, restaurant_id, items, customer_name, customer_phone):
    """Place a restaurant order as customer"""
    response = requests.post(
        f"{BASE_URL}/restaurant-orders",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "restaurant_id": restaurant_id,
            "items": items,
            "delivery_type": "delivery",
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "customer_address": "456 Customer Street, Juba",
            "payment_method": "cash",
            "note": "Test order for review testing"
        }
    )
    return response

def update_order_status(token, order_id, status):
    """Update restaurant order status"""
    response = requests.put(
        f"{BASE_URL}/restaurant-orders/{order_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": status}
    )
    return response

def get_restaurant_orders(token):
    """Get restaurant orders"""
    response = requests.get(
        f"{BASE_URL}/restaurant-orders",
        headers={"Authorization": f"Bearer {token}"}
    )
    return response

def create_review(token, restaurant_id, order_id, rating, comment):
    """Create a review for a restaurant order"""
    response = requests.post(
        f"{BASE_URL}/reviews",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "restaurant_id": restaurant_id,
            "order_id": order_id,
            "rating": rating,
            "comment": comment
        }
    )
    return response

def run_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("ITER 6.9 BACKEND TEST: GET /api/restaurant-orders has_review enrichment")
    print("="*80)
    
    # Get a restaurant category_id for menu items
    restaurant_category = db.categories.find_one({"group": "restaurant"}, {"_id": 0, "id": 1})
    if not restaurant_category:
        print("ERROR: No restaurant categories found in database")
        return
    category_id = restaurant_category["id"]
    print(f"Using category_id: {category_id}")
    
    # Test 1: Create customer account
    print_test("Create customer account via signup")
    response = signup_user(CUSTOMER_EMAIL, CUSTOMER_PASSWORD, CUSTOMER_NAME, "customer")
    print_result(response.status_code == 200, f"Customer signup: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
        return
    
    # Verify email in DB
    verified = verify_email_in_db(CUSTOMER_EMAIL)
    print_result(verified, f"Customer email verified in DB: {verified}")
    
    # Login customer
    customer_token = login_user(CUSTOMER_EMAIL, CUSTOMER_PASSWORD)
    print_result(customer_token is not None, f"Customer login successful: {customer_token is not None}")
    if not customer_token:
        return
    
    # Test 2: Create seller account
    print_test("Create seller account via signup")
    response = signup_user(SELLER_EMAIL, SELLER_PASSWORD, SELLER_NAME, "seller")
    print_result(response.status_code == 200, f"Seller signup: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
        return
    
    # Verify email in DB
    verified = verify_email_in_db(SELLER_EMAIL)
    print_result(verified, f"Seller email verified in DB: {verified}")
    
    # Login seller
    seller_token = login_user(SELLER_EMAIL, SELLER_PASSWORD)
    print_result(seller_token is not None, f"Seller login successful: {seller_token is not None}")
    if not seller_token:
        return
    
    # Test 3: Create restaurant as seller
    print_test("Create restaurant as seller")
    response = create_restaurant(seller_token, "Test Restaurant for Reviews")
    print_result(response.status_code == 200, f"Restaurant creation: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
        return
    
    restaurant = response.json()
    restaurant_id = restaurant["id"]
    print(f"Restaurant ID: {restaurant_id}")
    
    # Test 4: Add menu items
    print_test("Add menu items to restaurant")
    response = add_menu_item(seller_token, restaurant_id, "Grilled Chicken", 15.0, category_id)
    print_result(response.status_code == 200, f"Menu item 1 added: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
        return
    
    menu_item_1 = response.json()
    menu_item_1_id = menu_item_1["id"]
    
    response = add_menu_item(seller_token, restaurant_id, "Caesar Salad", 8.0, category_id)
    print_result(response.status_code == 200, f"Menu item 2 added: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
        return
    
    menu_item_2 = response.json()
    menu_item_2_id = menu_item_2["id"]
    
    # Test 5: Place restaurant order as customer
    print_test("Place restaurant order as customer")
    order_items = [
        {
            "item_type": "menu_item",
            "item_id": menu_item_1_id,
            "name": "Grilled Chicken",
            "price_usd": 15.0,
            "quantity": 2,
            "image_url": "https://via.placeholder.com/300x200"
        },
        {
            "item_type": "menu_item",
            "item_id": menu_item_2_id,
            "name": "Caesar Salad",
            "price_usd": 8.0,
            "quantity": 1,
            "image_url": "https://via.placeholder.com/300x200"
        }
    ]
    response = place_restaurant_order(customer_token, restaurant_id, order_items, CUSTOMER_NAME, "+211987654321")
    print_result(response.status_code == 200, f"Order placement: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
        return
    
    order = response.json()
    order_id = order["id"]
    print(f"Order ID: {order_id}")
    print(f"Order status: {order['status']}")
    
    # Test 6: Place a second order (to test multiple orders)
    print_test("Place second restaurant order as customer")
    order_items_2 = [
        {
            "item_type": "menu_item",
            "item_id": menu_item_1_id,
            "name": "Grilled Chicken",
            "price_usd": 15.0,
            "quantity": 1,
            "image_url": "https://via.placeholder.com/300x200"
        }
    ]
    response = place_restaurant_order(customer_token, restaurant_id, order_items_2, CUSTOMER_NAME, "+211987654321")
    print_result(response.status_code == 200, f"Second order placement: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
        return
    
    order_2 = response.json()
    order_2_id = order_2["id"]
    print(f"Order 2 ID: {order_2_id}")
    
    # Test 7: GET /api/restaurant-orders as customer (before any reviews)
    print_test("GET /api/restaurant-orders as customer (no reviews yet)")
    response = get_restaurant_orders(customer_token)
    print_result(response.status_code == 200, f"GET restaurant-orders: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
        return
    
    orders = response.json()
    print(f"Number of orders returned: {len(orders)}")
    
    # Verify all orders have has_review=false
    all_have_has_review = all("has_review" in o for o in orders)
    print_result(all_have_has_review, f"All orders have 'has_review' field: {all_have_has_review}")
    
    all_false = all(o.get("has_review") == False for o in orders)
    print_result(all_false, f"All orders have has_review=false: {all_false}")
    
    # Test 8: Try to review a non-completed order (should fail)
    print_test("Try to POST /api/reviews for non-completed order (should fail with 400)")
    response = create_review(customer_token, restaurant_id, order_id, 5, "Great food!")
    print_result(response.status_code == 400, f"Review non-completed order blocked: {response.status_code} == 400")
    if response.status_code == 400:
        print(f"Error message: {response.json().get('detail', 'N/A')}")
    
    # Test 9: Update order status to completed (as seller)
    print_test("Update order status to completed (seller flow)")
    
    # pending → accepted
    response = update_order_status(seller_token, order_id, "accepted")
    print_result(response.status_code == 200, f"Status → accepted: {response.status_code}")
    
    # accepted → cooking
    response = update_order_status(seller_token, order_id, "cooking")
    print_result(response.status_code == 200, f"Status → cooking: {response.status_code}")
    
    # cooking → ready
    response = update_order_status(seller_token, order_id, "ready")
    print_result(response.status_code == 200, f"Status → ready: {response.status_code}")
    
    # ready → completed
    response = update_order_status(seller_token, order_id, "completed")
    print_result(response.status_code == 200, f"Status → completed: {response.status_code}")
    if response.status_code == 200:
        print(f"Order {order_id} is now completed")
    
    # Test 10: POST /api/reviews for completed order
    print_test("POST /api/reviews for completed order")
    response = create_review(customer_token, restaurant_id, order_id, 5, "Excellent food and service!")
    print_result(response.status_code == 200, f"Review creation: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
        return
    
    review = response.json()
    review_id = review["id"]
    review_rating = review["rating"]
    print(f"Review ID: {review_id}")
    print(f"Review rating: {review_rating}")
    
    # Test 11: GET /api/restaurant-orders as customer (after review)
    print_test("GET /api/restaurant-orders as customer (after review)")
    response = get_restaurant_orders(customer_token)
    print_result(response.status_code == 200, f"GET restaurant-orders: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
        return
    
    orders = response.json()
    print(f"Number of orders returned: {len(orders)}")
    
    # Find the reviewed order
    reviewed_order = next((o for o in orders if o["id"] == order_id), None)
    if reviewed_order:
        has_review = reviewed_order.get("has_review")
        has_review_id = "review_id" in reviewed_order
        has_review_rating = "review_rating" in reviewed_order
        
        print_result(has_review == True, f"Reviewed order has has_review=true: {has_review}")
        print_result(has_review_id, f"Reviewed order has review_id field: {has_review_id}")
        print_result(has_review_rating, f"Reviewed order has review_rating field: {has_review_rating}")
        
        if has_review_id:
            print(f"review_id: {reviewed_order.get('review_id')}")
            print_result(reviewed_order.get('review_id') == review_id, f"review_id matches: {reviewed_order.get('review_id') == review_id}")
        
        if has_review_rating:
            print(f"review_rating: {reviewed_order.get('review_rating')}")
            print_result(reviewed_order.get('review_rating') == review_rating, f"review_rating matches: {reviewed_order.get('review_rating') == review_rating}")
    else:
        print_result(False, f"Could not find reviewed order {order_id} in response")
    
    # Find the non-reviewed order
    non_reviewed_order = next((o for o in orders if o["id"] == order_2_id), None)
    if non_reviewed_order:
        has_review = non_reviewed_order.get("has_review")
        print(f"Non-reviewed order data: {non_reviewed_order}")
        print_result(has_review == False, f"Non-reviewed order has has_review=false: {has_review}")
    else:
        print_result(False, f"Could not find non-reviewed order {order_2_id} in response")
    
    # Test 12: Try to POST /api/reviews again for same order (should fail)
    print_test("Try to POST /api/reviews again for same order (should fail with 400)")
    response = create_review(customer_token, restaurant_id, order_id, 4, "Updated review")
    print_result(response.status_code == 400, f"Duplicate review blocked: {response.status_code} == 400")
    if response.status_code == 400:
        print(f"Error message: {response.json().get('detail', 'N/A')}")
    
    # Test 13: Try to review someone else's order (create another customer)
    print_test("Try to POST /api/reviews for someone else's order (should fail with 403)")
    
    # Create another customer
    other_customer_email = f"other_customer_{int(time.time())}@example.com"
    response = signup_user(other_customer_email, "TestPass123!", "Other Customer", "customer")
    if response.status_code == 200:
        verify_email_in_db(other_customer_email)
        other_customer_token = login_user(other_customer_email, "TestPass123!")
        
        if other_customer_token:
            response = create_review(other_customer_token, restaurant_id, order_id, 5, "Trying to review someone else's order")
            print_result(response.status_code == 403, f"Review other's order blocked: {response.status_code} == 403")
            if response.status_code == 403:
                print(f"Error message: {response.json().get('detail', 'N/A')}")
        else:
            print_result(False, "Could not login other customer")
    else:
        print_result(False, "Could not create other customer")
    
    # Test 14: GET /api/restaurant-orders as seller (should not error)
    print_test("GET /api/restaurant-orders as seller (seller branch sanity check)")
    response = get_restaurant_orders(seller_token)
    print_result(response.status_code == 200, f"Seller GET restaurant-orders: {response.status_code}")
    if response.status_code == 200:
        seller_orders = response.json()
        print(f"Seller sees {len(seller_orders)} orders")
        # Seller branch may or may not have has_review - just verify no error
        print_result(True, "Seller branch does not error")
    
    # Test 15: GET /api/restaurant-orders as admin (should not error)
    print_test("GET /api/restaurant-orders as admin (admin branch sanity check)")
    admin_token = login_user(ADMIN_EMAIL, ADMIN_PASSWORD)
    if admin_token:
        response = get_restaurant_orders(admin_token)
        print_result(response.status_code == 200, f"Admin GET restaurant-orders: {response.status_code}")
        if response.status_code == 200:
            admin_orders = response.json()
            print(f"Admin sees {len(admin_orders)} orders")
            print_result(True, "Admin branch does not error")
    else:
        print_result(False, "Could not login admin")
    
    print("\n" + "="*80)
    print("ALL TESTS COMPLETED")
    print("="*80)

if __name__ == "__main__":
    run_tests()
