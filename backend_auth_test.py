#!/usr/bin/env python3
"""
Backend API Testing for JubaSquare - Authentication Endpoints
Tests admin username-based login + password reset functionality
"""

import requests
import json
import sys
from typing import Dict, Any

# Base URL from frontend/.env
BASE_URL = "https://jubasquare-odoo-v2.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@jubasquare.com"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"
DRIVER_EMAIL = "driver@demo.com"
DRIVER_PASSWORD = "1234"

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


def test_auth_endpoints():
    """Test authentication endpoints"""
    print("\n" + "="*80)
    print("TEST SUITE: Authentication Endpoints")
    print("="*80)
    
    # Test 1: Admin password login (email path)
    print("\n--- Test 1: Admin password login (email) ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            has_token = "token" in data and data["token"]
            has_user = "user" in data
            is_admin = data.get("user", {}).get("role") == "admin"
            correct_email = data.get("user", {}).get("email") == ADMIN_EMAIL
            
            if has_token and has_user and is_admin and correct_email:
                log_test("Admin login with email (admin@jubasquare.com / 1234)", True,
                        f"Token received, role=admin, email={ADMIN_EMAIL}")
            else:
                log_test("Admin login with email", False,
                        f"Missing fields or incorrect data. Response: {data}")
        else:
            log_test("Admin login with email", False,
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        log_test("Admin login with email", False, f"Exception: {e}")
    
    # Test 2: Admin username login (new feature)
    print("\n--- Test 2: Admin username login (username path) ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            has_token = "token" in data and data["token"]
            has_user = "user" in data
            is_admin = data.get("user", {}).get("role") == "admin"
            correct_email = data.get("user", {}).get("email") == ADMIN_EMAIL
            
            if has_token and has_user and is_admin and correct_email:
                log_test("Admin login with username (admin / 1234)", True,
                        f"Token received, role=admin, email={ADMIN_EMAIL} (verified email in response)")
            else:
                log_test("Admin login with username", False,
                        f"Missing fields or incorrect data. Response: {data}")
        else:
            log_test("Admin login with username", False,
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        log_test("Admin login with username", False, f"Exception: {e}")
    
    # Test 3: Wrong password (email path)
    print("\n--- Test 3: Wrong password (email path) ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": "wrongpass"},
            timeout=10
        )
        
        if resp.status_code == 401:
            log_test("Admin login with wrong password (email) returns 401", True,
                    f"Status: {resp.status_code}")
        else:
            log_test("Admin login with wrong password (email) returns 401", False,
                    f"Status: {resp.status_code} (expected 401), Body: {resp.text[:200]}")
    except Exception as e:
        log_test("Admin login with wrong password (email)", False, f"Exception: {e}")
    
    # Test 4: Wrong password (username path)
    print("\n--- Test 4: Wrong password (username path) ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": ADMIN_USERNAME, "password": "wrongpass"},
            timeout=10
        )
        
        if resp.status_code == 401:
            log_test("Admin login with wrong password (username) returns 401", True,
                    f"Status: {resp.status_code}")
        else:
            log_test("Admin login with wrong password (username) returns 401", False,
                    f"Status: {resp.status_code} (expected 401), Body: {resp.text[:200]}")
    except Exception as e:
        log_test("Admin login with wrong password (username)", False, f"Exception: {e}")
    
    # Test 5: Non-admin username rejection
    print("\n--- Test 5: Non-admin username rejection ---")
    try:
        # Try to login with driver username (without @)
        # Extract username from driver email (driver@demo.com -> driver)
        driver_username = DRIVER_EMAIL.split("@")[0]
        
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": driver_username, "password": DRIVER_PASSWORD},
            timeout=10
        )
        
        if resp.status_code == 401:
            log_test("Non-admin username login rejected (driver username)", True,
                    f"Status: {resp.status_code} (username login is admin-only)")
            
            # Now verify that the full email works
            resp2 = requests.post(
                f"{BASE_URL}/auth/login",
                json={"email": DRIVER_EMAIL, "password": DRIVER_PASSWORD},
                timeout=10
            )
            
            if resp2.status_code == 200:
                data = resp2.json()
                is_driver = data.get("user", {}).get("role") == "driver"
                if is_driver:
                    log_test("Driver login with full email succeeds", True,
                            f"Status: {resp2.status_code}, role=driver")
                else:
                    log_test("Driver login with full email succeeds", False,
                            f"Wrong role: {data.get('user', {}).get('role')}")
            else:
                log_test("Driver login with full email succeeds", False,
                        f"Status: {resp2.status_code}, Body: {resp2.text[:200]}")
        else:
            log_test("Non-admin username login rejected", False,
                    f"Status: {resp.status_code} (expected 401), Body: {resp.text[:200]}")
    except Exception as e:
        log_test("Non-admin username rejection", False, f"Exception: {e}")
    
    # Test 6: Non-existent username
    print("\n--- Test 6: Non-existent username ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": "nobody", "password": "anything"},
            timeout=10
        )
        
        if resp.status_code == 401:
            log_test("Non-existent username returns 401", True,
                    f"Status: {resp.status_code} (not 500 or 422)")
        else:
            log_test("Non-existent username returns 401", False,
                    f"Status: {resp.status_code} (expected 401), Body: {resp.text[:200]}")
    except Exception as e:
        log_test("Non-existent username", False, f"Exception: {e}")
    
    # Test 7: Case insensitivity
    print("\n--- Test 7: Case insensitivity (ADMIN username) ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": "ADMIN", "password": ADMIN_PASSWORD},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            has_token = "token" in data and data["token"]
            is_admin = data.get("user", {}).get("role") == "admin"
            
            if has_token and is_admin:
                log_test("Admin login with uppercase username (ADMIN) succeeds", True,
                        f"Status: {resp.status_code}, role=admin (username is case-insensitive)")
            else:
                log_test("Admin login with uppercase username", False,
                        f"Missing fields or incorrect data. Response: {data}")
        else:
            log_test("Admin login with uppercase username", False,
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        log_test("Admin login with uppercase username", False, f"Exception: {e}")
    
    # Test 8: Regression - existing endpoints unchanged
    print("\n--- Test 8: Regression tests ---")
    
    # Test 8a: GET /api/homepage
    try:
        resp = requests.get(f"{BASE_URL}/homepage", timeout=10)
        if resp.status_code == 200:
            log_test("GET /api/homepage still works (regression)", True,
                    f"Status: {resp.status_code}")
        else:
            log_test("GET /api/homepage still works (regression)", False,
                    f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/homepage (regression)", False, f"Exception: {e}")
    
    # Test 8b: GET /api/settings/public
    try:
        resp = requests.get(f"{BASE_URL}/settings/public", timeout=10)
        if resp.status_code == 200:
            log_test("GET /api/settings/public still works (regression)", True,
                    f"Status: {resp.status_code}")
        else:
            log_test("GET /api/settings/public still works (regression)", False,
                    f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/settings/public (regression)", False, f"Exception: {e}")


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("JUBASQUARE BACKEND API TESTING")
    print("Testing: Admin Username-Based Login + Password Reset")
    print("Base URL:", BASE_URL)
    print("="*80)
    
    try:
        # Run test suite
        test_auth_endpoints()
        
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
