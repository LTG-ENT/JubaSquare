#!/usr/bin/env python3
"""
Backend API Testing for JubaSquare
Tests the customer-only public signup enforcement
"""

import requests
import sys
import json
from typing import Optional

# Base URL from environment
BASE_URL = "https://jubasquare-odoo-v2.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Admin credentials
ADMIN_EMAIL = "admin@jubasquare.com"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"

# Test tracking
tests_passed = 0
tests_failed = 0
test_results = []


def log_test(test_name: str, passed: bool, details: str = ""):
    """Log test result"""
    global tests_passed, tests_failed
    if passed:
        tests_passed += 1
        status = "✅ PASS"
    else:
        tests_failed += 1
        status = "❌ FAIL"
    
    result = f"{status}: {test_name}"
    if details:
        result += f"\n    {details}"
    print(result)
    test_results.append({"test": test_name, "passed": passed, "details": details})


def admin_login() -> Optional[str]:
    """Login as admin and return token"""
    try:
        response = requests.post(
            f"{API_BASE}/auth/login",
            json={"email": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("token")
        else:
            print(f"❌ Admin login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Admin login error: {e}")
        return None


def get_user_by_email(email: str, admin_token: str) -> Optional[dict]:
    """Get user details by email using admin endpoint"""
    try:
        response = requests.get(
            f"{API_BASE}/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"search": email},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            users = data.get("users", [])
            for user in users:
                if user.get("email") == email:
                    return user
        return None
    except Exception as e:
        print(f"    Error fetching user: {e}")
        return None


def delete_user_by_email(email: str, admin_token: str) -> bool:
    """Delete a user by email (cleanup)"""
    try:
        user = get_user_by_email(email, admin_token)
        if user:
            user_id = user.get("id")
            response = requests.delete(
                f"{API_BASE}/admin/users/{user_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10
            )
            return response.status_code in [200, 204]
        return True  # User doesn't exist, consider it cleaned up
    except Exception as e:
        print(f"    Error deleting user: {e}")
        return False


def test_customer_signup_happy_path(admin_token: str):
    """Test 1: Customer signup — happy path"""
    test_name = "Test 1: Customer signup happy path"
    email = "cust_test_1@jubasquare.test"
    
    # Cleanup first
    delete_user_by_email(email, admin_token)
    
    try:
        # Signup
        response = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": email,
                "password": "testpass123",
                "name": "Customer One",
                "phone": ""
            },
            timeout=10
        )
        
        if response.status_code != 200:
            log_test(test_name, False, f"Signup failed: {response.status_code} - {response.text}")
            return
        
        data = response.json()
        if not data.get("ok"):
            log_test(test_name, False, f"Signup response ok=false: {data}")
            return
        
        if data.get("email") != email:
            log_test(test_name, False, f"Email mismatch: expected {email}, got {data.get('email')}")
            return
        
        # Verify role as admin
        user = get_user_by_email(email, admin_token)
        if not user:
            log_test(test_name, False, "User not found after signup")
            return
        
        if user.get("role") != "customer":
            log_test(test_name, False, f"Role mismatch: expected 'customer', got '{user.get('role')}'")
            return
        
        log_test(test_name, True, f"User created with role=customer")
        
    except Exception as e:
        log_test(test_name, False, f"Exception: {e}")


def test_attempted_seller_signup(admin_token: str):
    """Test 2: Attempted seller signup via public endpoint — MUST become customer"""
    test_name = "Test 2: Attempted seller signup (role field ignored)"
    email = "seller_test_1@jubasquare.test"
    
    # Cleanup first
    delete_user_by_email(email, admin_token)
    
    try:
        # Attempt to signup with role="seller"
        response = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": email,
                "password": "testpass123",
                "name": "Seller Two",
                "phone": "",
                "role": "seller"  # This should be IGNORED
            },
            timeout=10
        )
        
        if response.status_code != 200:
            log_test(test_name, False, f"Signup failed: {response.status_code} - {response.text}")
            return
        
        data = response.json()
        if not data.get("ok"):
            log_test(test_name, False, f"Signup response ok=false: {data}")
            return
        
        # Verify role as admin - MUST be customer, not seller
        user = get_user_by_email(email, admin_token)
        if not user:
            log_test(test_name, False, "User not found after signup")
            return
        
        if user.get("role") != "customer":
            log_test(test_name, False, f"Role mismatch: expected 'customer' (role field should be ignored), got '{user.get('role')}'")
            return
        
        log_test(test_name, True, f"Role field ignored, user created with role=customer (not seller)")
        
    except Exception as e:
        log_test(test_name, False, f"Exception: {e}")


def test_attempted_admin_signup(admin_token: str):
    """Test 3: Attempted admin signup via public endpoint — MUST become customer (privilege escalation guard)"""
    test_name = "Test 3: Attempted admin signup (privilege escalation guard)"
    email = "escalate_test_1@jubasquare.test"
    
    # Cleanup first
    delete_user_by_email(email, admin_token)
    
    try:
        # Attempt to signup with role="admin"
        response = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": email,
                "password": "testpass123",
                "name": "Attacker",
                "phone": "",
                "role": "admin"  # This should be IGNORED
            },
            timeout=10
        )
        
        if response.status_code != 200:
            log_test(test_name, False, f"Signup failed: {response.status_code} - {response.text}")
            return
        
        data = response.json()
        if not data.get("ok"):
            log_test(test_name, False, f"Signup response ok=false: {data}")
            return
        
        # Verify role as admin - MUST be customer, NOT admin
        user = get_user_by_email(email, admin_token)
        if not user:
            log_test(test_name, False, "User not found after signup")
            return
        
        if user.get("role") == "admin":
            log_test(test_name, False, f"SECURITY ISSUE: User was created with role=admin (privilege escalation)")
            return
        
        if user.get("role") != "customer":
            log_test(test_name, False, f"Role mismatch: expected 'customer', got '{user.get('role')}'")
            return
        
        log_test(test_name, True, f"Privilege escalation prevented, user created with role=customer (not admin)")
        
    except Exception as e:
        log_test(test_name, False, f"Exception: {e}")


def test_attempted_driver_signup(admin_token: str):
    """Test 4: Attempted driver signup via public endpoint — MUST become customer"""
    test_name = "Test 4: Attempted driver signup (role field ignored)"
    email = "driver_test_1@jubasquare.test"
    
    # Cleanup first
    delete_user_by_email(email, admin_token)
    
    try:
        # Attempt to signup with role="driver"
        response = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": email,
                "password": "testpass123",
                "name": "Would Be Driver",
                "phone": "",
                "role": "driver"  # This should be IGNORED
            },
            timeout=10
        )
        
        if response.status_code != 200:
            log_test(test_name, False, f"Signup failed: {response.status_code} - {response.text}")
            return
        
        data = response.json()
        if not data.get("ok"):
            log_test(test_name, False, f"Signup response ok=false: {data}")
            return
        
        # Verify role as admin - MUST be customer, not driver
        user = get_user_by_email(email, admin_token)
        if not user:
            log_test(test_name, False, "User not found after signup")
            return
        
        if user.get("role") != "customer":
            log_test(test_name, False, f"Role mismatch: expected 'customer', got '{user.get('role')}'")
            return
        
        log_test(test_name, True, f"Role field ignored, user created with role=customer (not driver)")
        
    except Exception as e:
        log_test(test_name, False, f"Exception: {e}")


def test_missing_required_fields():
    """Test 5: Missing required fields"""
    test_name = "Test 5: Missing required fields"
    
    try:
        # Test 5a: Missing name
        response = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": "noname@jubasquare.test",
                "password": "testpass123",
                "phone": ""
            },
            timeout=10
        )
        
        if response.status_code != 422:
            log_test(f"{test_name} (5a: missing name)", False, f"Expected 422, got {response.status_code}")
        else:
            log_test(f"{test_name} (5a: missing name)", True, "Correctly rejected with 422")
        
        # Test 5b: Missing email
        response = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "password": "testpass123",
                "name": "NoEmail"
            },
            timeout=10
        )
        
        if response.status_code != 422:
            log_test(f"{test_name} (5b: missing email)", False, f"Expected 422, got {response.status_code}")
        else:
            log_test(f"{test_name} (5b: missing email)", True, "Correctly rejected with 422")
        
        # Test 5c: Short password
        response = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": "shortpw@jubasquare.test",
                "password": "abc",
                "name": "Short"
            },
            timeout=10
        )
        
        if response.status_code != 422:
            log_test(f"{test_name} (5c: short password)", False, f"Expected 422, got {response.status_code}")
        else:
            log_test(f"{test_name} (5c: short password)", True, "Correctly rejected with 422")
        
    except Exception as e:
        log_test(test_name, False, f"Exception: {e}")


def test_duplicate_email(admin_token: str):
    """Test 6: Duplicate email"""
    test_name = "Test 6: Duplicate email"
    email = "cust_test_1@jubasquare.test"  # Reuse email from test 1
    
    try:
        # Attempt to signup with same email
        response = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": email,
                "password": "testpass123",
                "name": "Duplicate User",
                "phone": ""
            },
            timeout=10
        )
        
        if response.status_code != 400:
            log_test(test_name, False, f"Expected 400, got {response.status_code}")
            return
        
        data = response.json()
        detail = data.get("detail", "").lower()
        if "already exists" not in detail and "exist" not in detail:
            log_test(test_name, False, f"Expected 'already exists' message, got: {detail}")
            return
        
        log_test(test_name, True, "Duplicate email correctly rejected with 400")
        
    except Exception as e:
        log_test(test_name, False, f"Exception: {e}")


def test_admin_created_seller(admin_token: str):
    """Test 7: Regression: admin-created seller still works"""
    test_name = "Test 7: Admin-created seller (regression check)"
    email = "seller_admin_created_1@jubasquare.test"
    
    # Cleanup first
    delete_user_by_email(email, admin_token)
    
    try:
        # Admin creates a seller
        response = requests.post(
            f"{API_BASE}/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": email,
                "password": "testpass123",
                "name": "Real Seller",
                "role": "seller",
                "phone": ""
            },
            timeout=10
        )
        
        if response.status_code not in [200, 201]:
            log_test(test_name, False, f"Admin user creation failed: {response.status_code} - {response.text}")
            return
        
        data = response.json()
        if not data.get("ok"):
            log_test(test_name, False, f"Admin user creation response ok=false: {data}")
            return
        
        # Verify role
        user = get_user_by_email(email, admin_token)
        if not user:
            log_test(test_name, False, "User not found after admin creation")
            return
        
        if user.get("role") != "seller":
            log_test(test_name, False, f"Role mismatch: expected 'seller', got '{user.get('role')}'")
            return
        
        log_test(test_name, True, "Admin can still create sellers with role=seller")
        
    except Exception as e:
        log_test(test_name, False, f"Exception: {e}")


def test_regression_smokes(admin_token: str):
    """Test 8: Regression smokes: existing endpoints still work"""
    test_name = "Test 8: Regression smoke tests"
    
    try:
        # Test 8a: Admin login
        response = requests.post(
            f"{API_BASE}/auth/login",
            json={"email": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10
        )
        
        if response.status_code != 200:
            log_test(f"{test_name} (8a: admin login)", False, f"Expected 200, got {response.status_code}")
        else:
            log_test(f"{test_name} (8a: admin login)", True, "Admin login works")
        
        # Test 8b: GET /api/homepage
        response = requests.get(f"{API_BASE}/homepage", timeout=10)
        
        if response.status_code != 200:
            log_test(f"{test_name} (8b: GET /api/homepage)", False, f"Expected 200, got {response.status_code}")
        else:
            log_test(f"{test_name} (8b: GET /api/homepage)", True, "Homepage endpoint works")
        
        # Test 8c: GET /api/settings/public
        response = requests.get(f"{API_BASE}/settings/public", timeout=10)
        
        if response.status_code != 200:
            log_test(f"{test_name} (8c: GET /api/settings/public)", False, f"Expected 200, got {response.status_code}")
        else:
            log_test(f"{test_name} (8c: GET /api/settings/public)", True, "Public settings endpoint works")
        
    except Exception as e:
        log_test(test_name, False, f"Exception: {e}")


def cleanup_test_users(admin_token: str):
    """Cleanup test users"""
    print("\n" + "="*80)
    print("CLEANUP: Deleting test users...")
    print("="*80)
    
    test_emails = [
        "cust_test_1@jubasquare.test",
        "seller_test_1@jubasquare.test",
        "escalate_test_1@jubasquare.test",
        "driver_test_1@jubasquare.test",
        "seller_admin_created_1@jubasquare.test",
    ]
    
    for email in test_emails:
        if delete_user_by_email(email, admin_token):
            print(f"  ✓ Deleted {email}")
        else:
            print(f"  ⚠ Could not delete {email} (may not exist)")


def main():
    """Run all tests"""
    print("="*80)
    print("JUBASQUARE BACKEND TESTING: Customer-Only Public Signup Enforcement")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"API Base: {API_BASE}")
    print("="*80)
    
    # Login as admin
    print("\n🔐 Logging in as admin...")
    admin_token = admin_login()
    if not admin_token:
        print("❌ FATAL: Could not login as admin. Aborting tests.")
        sys.exit(1)
    print("✅ Admin login successful\n")
    
    # Run tests
    print("="*80)
    print("RUNNING TESTS")
    print("="*80 + "\n")
    
    test_customer_signup_happy_path(admin_token)
    test_attempted_seller_signup(admin_token)
    test_attempted_admin_signup(admin_token)
    test_attempted_driver_signup(admin_token)
    test_missing_required_fields()
    test_duplicate_email(admin_token)
    test_admin_created_seller(admin_token)
    test_regression_smokes(admin_token)
    
    # Cleanup
    cleanup_test_users(admin_token)
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total tests: {tests_passed + tests_failed}")
    print(f"✅ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")
    print("="*80)
    
    if tests_failed > 0:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("\n✅ ALL TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
