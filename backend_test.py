#!/usr/bin/env python3
"""
Backend test for Iter 6.11 - Shop rating rollup from product reviews
"""
import requests
import json
import sys
from typing import Optional

# Backend URL
BASE_URL = "https://cash-delivery-flow.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
CUSTOMER_EMAIL = "test_customer_1778609646@example.com"
CUSTOMER_PASSWORD = "TestPass123!"
SELLER_EMAIL = "test_seller_1778609646@example.com"
SELLER_PASSWORD = "TestPass123!"
ADMIN_EMAIL = "admin@ltg.com"
ADMIN_PASSWORD = "Kokobleake1"

# Test state
customer_token = None
customer2_token = None
seller_token = None
admin_token = None
shop_id = None
product_id = None
review1_id = None
review2_id = None
customer2_email = None


def log(msg: str):
    print(f"  {msg}")


def login(email: str, password: str) -> Optional[str]:
    """Login and return token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        return resp.json().get("token")
    return None


def test_1_login_users():
    """Test 1: Login existing test users"""
    global customer_token, seller_token, admin_token
    
    log("Logging in as customer...")
    customer_token = login(CUSTOMER_EMAIL, CUSTOMER_PASSWORD)
    assert customer_token, "Customer login failed"
    log(f"✅ Customer logged in")
    
    log("Logging in as seller...")
    seller_token = login(SELLER_EMAIL, SELLER_PASSWORD)
    assert seller_token, "Seller login failed"
    log(f"✅ Seller logged in")
    
    log("Logging in as admin...")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert admin_token, "Admin login failed"
    log(f"✅ Admin logged in")


def test_2_create_shop_and_product():
    """Test 2: Create a shop and product as seller"""
    global shop_id, product_id
    
    log("Creating shop as seller...")
    resp = requests.post(
        f"{BASE_URL}/shops",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={
            "name": "Test Shop for Rating Rollup",
            "description": "Testing shop rating aggregation",
            "category": "Electronics & Accessories",
            "phone": "+211912345678",
            "location": "Juba",
            "delivery_mode": "free"
        }
    )
    assert resp.status_code == 200, f"Shop creation failed: {resp.status_code} {resp.text}"
    shop_id = resp.json()["id"]
    log(f"✅ Shop created: {shop_id}")
    
    log("Creating product in shop...")
    resp = requests.post(
        f"{BASE_URL}/products",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={
            "name": "Test Product for Reviews",
            "description": "Testing product reviews",
            "price_usd": 50.0,
            "category": "Electronics & Accessories",
            "stock": 100,
            "shop_id": shop_id,
            "is_wholesale": False
        }
    )
    assert resp.status_code == 200, f"Product creation failed: {resp.status_code} {resp.text}"
    product_id = resp.json()["id"]
    log(f"✅ Product created: {product_id}")


def test_3_verify_shop_initial_state():
    """Test 3: Verify shop has no ratings initially (or null/0 from backfill)"""
    log(f"Getting shop {shop_id}...")
    resp = requests.get(f"{BASE_URL}/shops/{shop_id}")
    assert resp.status_code == 200, f"Shop GET failed: {resp.status_code}"
    shop = resp.json()
    
    # Shop should have average_rating and review_count fields (from backfill or creation)
    # Since no reviews yet, should be null/0
    avg = shop.get("average_rating")
    cnt = shop.get("review_count", 0)
    log(f"✅ Shop initial state: average_rating={avg}, review_count={cnt}")
    assert avg is None or avg == 0, f"Expected null or 0 average_rating, got {avg}"
    assert cnt == 0, f"Expected 0 review_count, got {cnt}"


def test_4_post_first_review():
    """Test 4: POST first review (rating=4) and verify shop updates"""
    global review1_id
    
    log(f"Posting review (rating=4) as customer...")
    resp = requests.post(
        f"{BASE_URL}/products/{product_id}/reviews",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"rating": 4, "comment": "Good product"}
    )
    assert resp.status_code == 200, f"Review POST failed: {resp.status_code} {resp.text}"
    review1_id = resp.json()["id"]
    log(f"✅ Review created: {review1_id}")
    
    log(f"Getting shop {shop_id} to verify rating update...")
    resp = requests.get(f"{BASE_URL}/shops/{shop_id}")
    assert resp.status_code == 200, f"Shop GET failed: {resp.status_code}"
    shop = resp.json()
    
    avg = shop.get("average_rating")
    cnt = shop.get("review_count")
    log(f"✅ Shop after 1st review: average_rating={avg}, review_count={cnt}")
    assert avg == 4.0, f"Expected average_rating=4.0, got {avg}"
    assert cnt == 1, f"Expected review_count=1, got {cnt}"


def test_5_create_second_customer():
    """Test 5: Create a second customer for additional review"""
    global customer2_token, customer2_email
    
    import time
    customer2_email = f"test_customer2_{int(time.time())}@example.com"
    
    log(f"Creating second customer: {customer2_email}...")
    resp = requests.post(
        f"{BASE_URL}/auth/signup",
        json={
            "email": customer2_email,
            "password": "TestPass123!",
            "name": "Test Customer 2",
            "role": "customer"
        }
    )
    assert resp.status_code == 200, f"Signup failed: {resp.status_code} {resp.text}"
    log(f"✅ Second customer created")
    
    # Manually verify email in MongoDB
    log("Manually verifying email in MongoDB...")
    import subprocess
    cmd = f'mongosh jubasquare_db --quiet --eval "db.users.updateOne({{email: \\"{customer2_email}\\"}}, {{\\$set: {{email_verified: true}}}})"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    log(f"MongoDB update result: {result.stdout.strip()}")
    
    log("Logging in as second customer...")
    customer2_token = login(customer2_email, "TestPass123!")
    assert customer2_token, "Second customer login failed"
    log(f"✅ Second customer logged in")


def test_6_post_second_review():
    """Test 6: POST second review (rating=2) and verify shop average updates"""
    global review2_id
    
    log(f"Posting review (rating=2) as second customer...")
    resp = requests.post(
        f"{BASE_URL}/products/{product_id}/reviews",
        headers={"Authorization": f"Bearer {customer2_token}"},
        json={"rating": 2, "comment": "Not great"}
    )
    assert resp.status_code == 200, f"Review POST failed: {resp.status_code} {resp.text}"
    review2_id = resp.json()["id"]
    log(f"✅ Review created: {review2_id}")
    
    log(f"Getting shop {shop_id} to verify rating update...")
    resp = requests.get(f"{BASE_URL}/shops/{shop_id}")
    assert resp.status_code == 200, f"Shop GET failed: {resp.status_code}"
    shop = resp.json()
    
    avg = shop.get("average_rating")
    cnt = shop.get("review_count")
    log(f"✅ Shop after 2nd review: average_rating={avg}, review_count={cnt}")
    # Average of 4 and 2 is 3.0
    assert avg == 3.0, f"Expected average_rating=3.0, got {avg}"
    assert cnt == 2, f"Expected review_count=2, got {cnt}"


def test_7_delete_first_review():
    """Test 7: DELETE first review and verify shop updates"""
    log(f"Deleting first review {review1_id} as original author...")
    resp = requests.delete(
        f"{BASE_URL}/products/{product_id}/reviews/{review1_id}",
        headers={"Authorization": f"Bearer {customer_token}"}
    )
    assert resp.status_code == 200, f"Review DELETE failed: {resp.status_code} {resp.text}"
    log(f"✅ Review deleted")
    
    log(f"Getting shop {shop_id} to verify rating update...")
    resp = requests.get(f"{BASE_URL}/shops/{shop_id}")
    assert resp.status_code == 200, f"Shop GET failed: {resp.status_code}"
    shop = resp.json()
    
    avg = shop.get("average_rating")
    cnt = shop.get("review_count")
    log(f"✅ Shop after deleting 1st review: average_rating={avg}, review_count={cnt}")
    # Only review with rating=2 remains
    assert avg == 2.0, f"Expected average_rating=2.0, got {avg}"
    assert cnt == 1, f"Expected review_count=1, got {cnt}"


def test_8_delete_last_review():
    """Test 8: DELETE last review and verify shop resets to null/0"""
    log(f"Deleting last review {review2_id} as admin...")
    resp = requests.delete(
        f"{BASE_URL}/products/{product_id}/reviews/{review2_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200, f"Review DELETE failed: {resp.status_code} {resp.text}"
    log(f"✅ Review deleted")
    
    log(f"Getting shop {shop_id} to verify rating reset...")
    resp = requests.get(f"{BASE_URL}/shops/{shop_id}")
    assert resp.status_code == 200, f"Shop GET failed: {resp.status_code}"
    shop = resp.json()
    
    avg = shop.get("average_rating")
    cnt = shop.get("review_count")
    log(f"✅ Shop after deleting last review: average_rating={avg}, review_count={cnt}")
    # No reviews left, should be null and 0
    assert avg is None, f"Expected average_rating=null, got {avg}"
    assert cnt == 0, f"Expected review_count=0, got {cnt}"


def test_9_restaurant_review_regression():
    """Test 9: Verify restaurant reviews still work (no regression)"""
    log("Testing restaurant review regression...")
    
    # Get existing restaurant from iter 6.9
    restaurant_id = "0703d00d-1d9c-438f-bc75-7413b2dba13c"
    
    log(f"Getting reviews for restaurant {restaurant_id}...")
    resp = requests.get(f"{BASE_URL}/reviews", params={"restaurant_id": restaurant_id})
    assert resp.status_code == 200, f"Restaurant reviews GET failed: {resp.status_code} {resp.text}"
    reviews = resp.json()
    log(f"✅ Restaurant reviews GET works: {len(reviews)} reviews found")
    
    # Note: We can't POST a new restaurant review without a completed order,
    # but verifying GET works is sufficient for regression check


def cleanup():
    """Cleanup: Delete test shop, product, and second customer"""
    log("\n=== CLEANUP ===")
    
    if shop_id and seller_token:
        log(f"Deleting shop {shop_id}...")
        resp = requests.delete(
            f"{BASE_URL}/shops/{shop_id}",
            headers={"Authorization": f"Bearer {seller_token}"}
        )
        if resp.status_code == 200:
            log(f"✅ Shop deleted")
        else:
            log(f"⚠️ Shop deletion failed: {resp.status_code}")
    
    if customer2_email and admin_token:
        log(f"Deleting second customer {customer2_email}...")
        # Get user ID first
        import subprocess
        cmd = f'mongosh jubasquare_db --quiet --eval "db.users.findOne({{email: \\"{customer2_email}\\"}}).id"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        user_id = result.stdout.strip()
        if user_id:
            resp = requests.delete(
                f"{BASE_URL}/admin/users/{user_id}",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            if resp.status_code == 200:
                log(f"✅ Second customer deleted")
            else:
                log(f"⚠️ Customer deletion failed: {resp.status_code}")


def main():
    tests = [
        ("Login users", test_1_login_users),
        ("Create shop and product", test_2_create_shop_and_product),
        ("Verify shop initial state", test_3_verify_shop_initial_state),
        ("POST first review (rating=4)", test_4_post_first_review),
        ("Create second customer", test_5_create_second_customer),
        ("POST second review (rating=2)", test_6_post_second_review),
        ("DELETE first review", test_7_delete_first_review),
        ("DELETE last review", test_8_delete_last_review),
        ("Restaurant review regression", test_9_restaurant_review_regression),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print('='*60)
        try:
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
            print(f"   Exception: {e}")
    
    # Cleanup
    try:
        cleanup()
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")
    
    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print('='*60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
