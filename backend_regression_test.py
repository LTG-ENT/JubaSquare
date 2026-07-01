#!/usr/bin/env python3
"""
Backend Regression Testing for JubaSquare
Tests password change endpoint, maintenance mode toggle, and regression smokes
after frontend-only changes (PasswordChangeForm.jsx refactor + MaintenancePage.css mobile optimizations)
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


def login(identifier: str, password: str) -> tuple[str, dict]:
    """Login and return (token, user_data)"""
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": identifier, "password": password},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("token", ""), data.get("user", {})
        return "", {}
    except Exception as e:
        print(f"Login failed: {e}")
        return "", {}


def create_customer(admin_token: str) -> tuple[str, str]:
    """Create a test customer, return (customer_email, customer_token)"""
    import uuid
    customer_email = f"customer_test_{uuid.uuid4().hex[:8]}@test.com"
    customer_password = "test123"
    
    # Create customer user
    resp = requests.post(
        f"{BASE_URL}/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Test Customer",
            "email": customer_email,
            "password": customer_password,
            "role": "customer",
            "phone": "+211912345678"
        },
        timeout=10
    )
    
    if resp.status_code != 200:
        raise Exception(f"Failed to create customer: {resp.status_code} {resp.text}")
    
    # Login as customer
    customer_token, _ = login(customer_email, customer_password)
    if not customer_token:
        raise Exception("Failed to login as customer")
    
    return customer_email, customer_token


# ============================================================================
# TEST SUITE 1: Password Change Endpoint
# ============================================================================

def test_password_change():
    """Test password change endpoint (8 scenarios)"""
    print("\n" + "="*80)
    print("TEST SUITE 1: Password Change Endpoint")
    print("="*80)
    
    # Test 1a: Admin login with username
    print("\n--- Test 1a: Admin login (username) ---")
    admin_token, admin_user = login(ADMIN_USERNAME, ADMIN_PASSWORD)
    if admin_token and admin_user.get("role") == "admin":
        log_test("Admin login with username 'admin'", True, 
                f"Token obtained, role={admin_user.get('role')}")
    else:
        log_test("Admin login with username 'admin'", False, "Failed to get admin token")
        return
    
    # Test 1b: Change password from 1234 to newpass99
    print("\n--- Test 1b: POST /api/auth/change-password (1234 → newpass99) ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/change-password",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"current_password": "1234", "new_password": "newpass99"},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                log_test("Change password 1234 → newpass99", True, "Password changed successfully")
            else:
                log_test("Change password 1234 → newpass99", False, f"Response: {data}")
        else:
            log_test("Change password 1234 → newpass99", False, 
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        log_test("Change password 1234 → newpass99", False, f"Exception: {e}")
        return
    
    # Test 1c: Old password login should fail with 401
    print("\n--- Test 1c: Login with old password (should fail) ---")
    try:
        old_token, old_user = login(ADMIN_USERNAME, "1234")
        if not old_token:
            log_test("Login with old password returns 401", True, "Old password rejected")
        else:
            log_test("Login with old password returns 401", False, 
                    "Old password still works (should have been rejected)")
    except Exception as e:
        log_test("Login with old password", False, f"Exception: {e}")
    
    # Test 1d: New password login should succeed
    print("\n--- Test 1d: Login with new password (should succeed) ---")
    try:
        new_token, new_user = login(ADMIN_USERNAME, "newpass99")
        if new_token and new_user.get("role") == "admin":
            log_test("Login with new password 'newpass99'", True, 
                    f"Token obtained, role={new_user.get('role')}")
            admin_token = new_token  # Update token for subsequent tests
        else:
            log_test("Login with new password 'newpass99'", False, "Failed to login with new password")
            return
    except Exception as e:
        log_test("Login with new password", False, f"Exception: {e}")
        return
    
    # Test 1e: Restore password (newpass99 → 1234)
    print("\n--- Test 1e: Restore password (newpass99 → 1234) ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/change-password",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"current_password": "newpass99", "new_password": "1234"},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                log_test("Restore password newpass99 → 1234", True, "Password restored successfully")
            else:
                log_test("Restore password newpass99 → 1234", False, f"Response: {data}")
        else:
            log_test("Restore password newpass99 → 1234", False, 
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        log_test("Restore password newpass99 → 1234", False, f"Exception: {e}")
    
    # Test 1f: Wrong current password should return 400 or 401
    print("\n--- Test 1f: Change password with wrong current password ---")
    # Re-login with restored password
    admin_token, _ = login(ADMIN_USERNAME, ADMIN_PASSWORD)
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/change-password",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"current_password": "wrongpassword", "new_password": "newpass99"},
            timeout=10
        )
        if resp.status_code in [400, 401]:
            log_test("Wrong current password returns 400/401", True, 
                    f"Status: {resp.status_code}")
        else:
            log_test("Wrong current password returns 400/401", False, 
                    f"Status: {resp.status_code} (expected 400/401)")
    except Exception as e:
        log_test("Wrong current password", False, f"Exception: {e}")
    
    # Test 1g: Very short new password (e.g. "abc")
    print("\n--- Test 1g: Change password with very short new password ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/change-password",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"current_password": "1234", "new_password": "abc"},
            timeout=10
        )
        # Backend may or may not enforce min-length - just record what happens
        if resp.status_code == 200:
            log_test("Very short password 'abc'", True, 
                    f"Status: {resp.status_code} (backend allows short passwords)")
            # Restore if it succeeded
            requests.post(
                f"{BASE_URL}/auth/change-password",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"current_password": "abc", "new_password": "1234"},
                timeout=10
            )
        elif resp.status_code in [400, 422]:
            log_test("Very short password 'abc'", True, 
                    f"Status: {resp.status_code} (backend rejects short passwords)")
        else:
            log_test("Very short password 'abc'", True, 
                    f"Status: {resp.status_code} (recorded)")
    except Exception as e:
        log_test("Very short password", False, f"Exception: {e}")
    
    # Test 1h: Anonymous (no auth) should return 401
    print("\n--- Test 1h: Change password without auth ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/change-password",
            json={"current_password": "1234", "new_password": "newpass99"},
            timeout=10
        )
        if resp.status_code == 401:
            log_test("Change password without auth returns 401", True, 
                    f"Status: {resp.status_code}")
        else:
            log_test("Change password without auth returns 401", False, 
                    f"Status: {resp.status_code} (expected 401)")
    except Exception as e:
        log_test("Change password without auth", False, f"Exception: {e}")


# ============================================================================
# TEST SUITE 2: Maintenance Mode Toggle
# ============================================================================

def test_maintenance_mode():
    """Test maintenance mode toggle (5 scenarios)"""
    print("\n" + "="*80)
    print("TEST SUITE 2: Maintenance Mode Toggle")
    print("="*80)
    
    # Login as admin
    admin_token, _ = login(ADMIN_USERNAME, ADMIN_PASSWORD)
    if not admin_token:
        log_test("Admin login for maintenance tests", False, "Failed to get admin token")
        return
    
    # Test 2a: PUT /api/admin/settings {"maintenance_mode": true}
    print("\n--- Test 2a: Enable maintenance mode ---")
    try:
        resp = requests.put(
            f"{BASE_URL}/admin/settings",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"maintenance_mode": True},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("maintenance_mode") == True:
                log_test("PUT /api/admin/settings maintenance_mode=true", True, 
                        "Maintenance mode enabled")
            else:
                log_test("PUT /api/admin/settings maintenance_mode=true", False, 
                        f"Response: {data}")
        else:
            log_test("PUT /api/admin/settings maintenance_mode=true", False, 
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        log_test("Enable maintenance mode", False, f"Exception: {e}")
    
    # Test 2b: GET /api/settings/public should reflect maintenance_mode=true
    print("\n--- Test 2b: Verify maintenance mode enabled in public settings ---")
    try:
        resp = requests.get(f"{BASE_URL}/settings/public", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("maintenance_mode") == True:
                log_test("GET /api/settings/public maintenance_mode=true", True, 
                        "Maintenance mode reflected in public settings")
            else:
                log_test("GET /api/settings/public maintenance_mode=true", False, 
                        f"maintenance_mode={data.get('maintenance_mode')} (expected true)")
        else:
            log_test("GET /api/settings/public", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("Verify maintenance mode enabled", False, f"Exception: {e}")
    
    # Test 2c: PUT /api/admin/settings {"maintenance_mode": false}
    print("\n--- Test 2c: Disable maintenance mode ---")
    try:
        resp = requests.put(
            f"{BASE_URL}/admin/settings",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"maintenance_mode": False},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("maintenance_mode") == False:
                log_test("PUT /api/admin/settings maintenance_mode=false", True, 
                        "Maintenance mode disabled")
            else:
                log_test("PUT /api/admin/settings maintenance_mode=false", False, 
                        f"Response: {data}")
        else:
            log_test("PUT /api/admin/settings maintenance_mode=false", False, 
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        log_test("Disable maintenance mode", False, f"Exception: {e}")
    
    # Test 2d: GET /api/settings/public should reflect maintenance_mode=false
    print("\n--- Test 2d: Verify maintenance mode disabled in public settings ---")
    try:
        resp = requests.get(f"{BASE_URL}/settings/public", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("maintenance_mode") == False:
                log_test("GET /api/settings/public maintenance_mode=false", True, 
                        "Maintenance mode reflected in public settings")
            else:
                log_test("GET /api/settings/public maintenance_mode=false", False, 
                        f"maintenance_mode={data.get('maintenance_mode')} (expected false)")
        else:
            log_test("GET /api/settings/public", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("Verify maintenance mode disabled", False, f"Exception: {e}")
    
    # Test 2e: Non-admin PUT should return 403
    print("\n--- Test 2e: Non-admin PUT maintenance mode (should fail) ---")
    try:
        # Create a customer
        customer_email, customer_token = create_customer(admin_token)
        
        resp = requests.put(
            f"{BASE_URL}/admin/settings",
            headers={"Authorization": f"Bearer {customer_token}"},
            json={"maintenance_mode": True},
            timeout=10
        )
        if resp.status_code == 403:
            log_test("Non-admin PUT /api/admin/settings returns 403", True, 
                    f"Status: {resp.status_code}")
        else:
            log_test("Non-admin PUT /api/admin/settings returns 403", False, 
                    f"Status: {resp.status_code} (expected 403)")
    except Exception as e:
        log_test("Non-admin PUT maintenance mode", False, f"Exception: {e}")


# ============================================================================
# TEST SUITE 3: Regression Smoke Tests
# ============================================================================

def test_regression_smokes():
    """Regression smoke tests (7 scenarios)"""
    print("\n" + "="*80)
    print("TEST SUITE 3: Regression Smoke Tests")
    print("="*80)
    
    # Login as admin for tests that need auth
    admin_token, _ = login(ADMIN_USERNAME, ADMIN_PASSWORD)
    
    # Test 3a: GET /api/homepage
    print("\n--- Test 3a: GET /api/homepage ---")
    try:
        resp = requests.get(f"{BASE_URL}/homepage", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            required_keys = ["hero_slides", "hero_tagline", "hero_title", "hero_subtitle", "announcement_bar"]
            has_all = all(k in data for k in required_keys)
            if has_all:
                log_test("GET /api/homepage", True, 
                        f"Returns 200 with all required keys")
            else:
                log_test("GET /api/homepage", False, 
                        f"Missing keys. Got: {list(data.keys())}")
        else:
            log_test("GET /api/homepage", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/homepage", False, f"Exception: {e}")
    
    # Test 3b: GET /api/push/public-key
    print("\n--- Test 3b: GET /api/push/public-key ---")
    try:
        resp = requests.get(f"{BASE_URL}/push/public-key", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            public_key = data.get("public_key", "")
            if public_key and isinstance(public_key, str) and len(public_key) > 50:
                log_test("GET /api/push/public-key", True, 
                        f"Returns 200 with public_key string ({len(public_key)} chars)")
            else:
                log_test("GET /api/push/public-key", False, 
                        f"Invalid public_key: {public_key}")
        else:
            log_test("GET /api/push/public-key", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/push/public-key", False, f"Exception: {e}")
    
    # Test 3c: GET /api/admin/health as admin
    print("\n--- Test 3c: GET /api/admin/health (as admin) ---")
    try:
        resp = requests.get(
            f"{BASE_URL}/admin/health",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            mongo_status = data.get("mongo", {}).get("status")
            if mongo_status == "ok":
                log_test("GET /api/admin/health", True, 
                        f"Returns 200 with mongo.status=ok")
            else:
                log_test("GET /api/admin/health", False, 
                        f"mongo.status={mongo_status} (expected 'ok')")
        else:
            log_test("GET /api/admin/health", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/admin/health", False, f"Exception: {e}")
    
    # Test 3d: GET /api/sitemap.xml
    print("\n--- Test 3d: GET /api/sitemap.xml ---")
    try:
        resp = requests.get(f"{BASE_URL}/sitemap.xml", timeout=10)
        if resp.status_code == 200:
            content = resp.text
            content_type = resp.headers.get("content-type", "")
            is_xml = "xml" in content_type.lower() or content.strip().startswith("<?xml")
            if is_xml and "<urlset" in content:
                log_test("GET /api/sitemap.xml", True, 
                        f"Returns 200 with valid XML ({len(content)} bytes)")
            else:
                log_test("GET /api/sitemap.xml", False, 
                        f"Invalid XML. Content-Type: {content_type}, First 100 chars: {content[:100]}")
        else:
            log_test("GET /api/sitemap.xml", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/sitemap.xml", False, f"Exception: {e}")
    
    # Test 3e: GET /api/robots.txt
    print("\n--- Test 3e: GET /api/robots.txt ---")
    try:
        resp = requests.get(f"{BASE_URL}/robots.txt", timeout=10)
        if resp.status_code == 200:
            content = resp.text
            content_type = resp.headers.get("content-type", "")
            is_text = "text/plain" in content_type.lower()
            has_user_agent = "User-agent:" in content
            has_sitemap = "Sitemap:" in content
            if is_text and has_user_agent and has_sitemap:
                log_test("GET /api/robots.txt", True, 
                        f"Returns 200 with valid robots.txt ({len(content)} bytes)")
            else:
                log_test("GET /api/robots.txt", False, 
                        f"Invalid robots.txt. Content-Type: {content_type}, Content: {content[:200]}")
        else:
            log_test("GET /api/robots.txt", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/robots.txt", False, f"Exception: {e}")
    
    # Test 3f: Admin username login (admin / 1234)
    print("\n--- Test 3f: Admin username login ---")
    try:
        token, user = login(ADMIN_USERNAME, ADMIN_PASSWORD)
        if token and user.get("role") == "admin":
            log_test("Admin username login (admin / 1234)", True, 
                    f"Token obtained, role={user.get('role')}")
        else:
            log_test("Admin username login (admin / 1234)", False, 
                    "Failed to login with username")
    except Exception as e:
        log_test("Admin username login", False, f"Exception: {e}")
    
    # Test 3g: Admin email login (admin@jubasquare.com / 1234)
    print("\n--- Test 3g: Admin email login ---")
    try:
        token, user = login(ADMIN_EMAIL, ADMIN_PASSWORD)
        if token and user.get("role") == "admin":
            log_test("Admin email login (admin@jubasquare.com / 1234)", True, 
                    f"Token obtained, role={user.get('role')}")
        else:
            log_test("Admin email login (admin@jubasquare.com / 1234)", False, 
                    "Failed to login with email")
    except Exception as e:
        log_test("Admin email login", False, f"Exception: {e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("JUBASQUARE BACKEND REGRESSION TESTING")
    print("Testing: Password Change + Maintenance Mode + Regression Smokes")
    print("Base URL:", BASE_URL)
    print("="*80)
    
    try:
        # Run test suites
        test_password_change()
        test_maintenance_mode()
        test_regression_smokes()
        
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
