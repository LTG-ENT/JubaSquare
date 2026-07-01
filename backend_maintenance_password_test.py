#!/usr/bin/env python3
"""
Backend API Testing for JubaSquare - Maintenance Mode + Password Change Regression
Formal verification of maintenance-mode + password change work.
"""

import requests
import json
import sys
from typing import Dict, Any

# Base URL from frontend/.env
BASE_URL = "https://jubasquare-odoo-v2.preview.emergentagent.com/api"

# Test credentials
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
        resp = requests.post(f"{BASE_URL}/auth/login", json={"email": identifier, "password": password}, timeout=10)
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
# TEST SUITE 1: Settings Toggle (Maintenance Mode)
# ============================================================================

def test_maintenance_mode():
    """Test maintenance mode settings toggle"""
    print("\n" + "="*80)
    print("TEST SUITE 1: Maintenance Mode Settings Toggle")
    print("="*80)
    
    # Test 1a: Login as admin
    print("\n--- Test 1a: POST /api/auth/login (admin) ---")
    admin_token, admin_user = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if admin_token and admin_user.get("role") == "admin":
        log_test("Admin login with email", True, f"Token obtained, role: {admin_user.get('role')}")
    else:
        log_test("Admin login with email", False, "Failed to get admin token")
        return
    
    # Test 1b: GET /api/settings/public - note current maintenance_mode
    print("\n--- Test 1b: GET /api/settings/public (initial state) ---")
    initial_maintenance_mode = None
    try:
        resp = requests.get(f"{BASE_URL}/settings/public", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "maintenance_mode" in data:
                initial_maintenance_mode = data["maintenance_mode"]
                log_test("GET /api/settings/public returns maintenance_mode", True,
                        f"Current maintenance_mode: {initial_maintenance_mode}")
            else:
                log_test("GET /api/settings/public returns maintenance_mode", False,
                        f"Missing maintenance_mode key. Keys: {list(data.keys())}")
                return
        else:
            log_test("GET /api/settings/public", False, f"Status: {resp.status_code}")
            return
    except Exception as e:
        log_test("GET /api/settings/public", False, f"Exception: {e}")
        return
    
    # Test 1c: PUT /api/admin/settings {"maintenance_mode": true}
    print("\n--- Test 1c: PUT /api/admin/settings (enable maintenance) ---")
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
                log_test("PUT /api/admin/settings enables maintenance_mode", True,
                        f"Response: maintenance_mode={data.get('maintenance_mode')}")
            else:
                log_test("PUT /api/admin/settings enables maintenance_mode", False,
                        f"Response doesn't echo maintenance_mode:true. Got: {data}")
        else:
            log_test("PUT /api/admin/settings", False,
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        log_test("PUT /api/admin/settings", False, f"Exception: {e}")
    
    # Test 1d: GET /api/settings/public - verify cache invalidation
    print("\n--- Test 1d: GET /api/settings/public (verify cache invalidation) ---")
    try:
        resp = requests.get(f"{BASE_URL}/settings/public", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("maintenance_mode") == True:
                log_test("GET /api/settings/public reflects maintenance_mode:true", True,
                        "Cache invalidation works")
            else:
                log_test("GET /api/settings/public reflects maintenance_mode:true", False,
                        f"Expected true, got: {data.get('maintenance_mode')}")
        else:
            log_test("GET /api/settings/public after PUT", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/settings/public after PUT", False, f"Exception: {e}")
    
    # Test 1e: PUT /api/admin/settings {"maintenance_mode": false}
    print("\n--- Test 1e: PUT /api/admin/settings (disable maintenance) ---")
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
                log_test("PUT /api/admin/settings disables maintenance_mode", True,
                        f"Response: maintenance_mode={data.get('maintenance_mode')}")
            else:
                log_test("PUT /api/admin/settings disables maintenance_mode", False,
                        f"Response doesn't echo maintenance_mode:false. Got: {data}")
        else:
            log_test("PUT /api/admin/settings", False,
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        log_test("PUT /api/admin/settings", False, f"Exception: {e}")
    
    # Test 1f: GET /api/settings/public - verify maintenance_mode:false again
    print("\n--- Test 1f: GET /api/settings/public (verify disabled) ---")
    try:
        resp = requests.get(f"{BASE_URL}/settings/public", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("maintenance_mode") == False:
                log_test("GET /api/settings/public reflects maintenance_mode:false", True,
                        "Cache invalidation works for disable")
            else:
                log_test("GET /api/settings/public reflects maintenance_mode:false", False,
                        f"Expected false, got: {data.get('maintenance_mode')}")
        else:
            log_test("GET /api/settings/public after disable", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/settings/public after disable", False, f"Exception: {e}")
    
    # Test 1g: Non-admin cannot flip maintenance mode
    print("\n--- Test 1g: PUT /api/admin/settings as non-admin (should fail) ---")
    try:
        customer_email, customer_token = create_customer(admin_token)
        print(f"✓ Created customer: {customer_email}")
        
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
        log_test("Non-admin PUT /api/admin/settings", False, f"Exception: {e}")
    
    # Restore initial state
    print(f"\n--- Restoring initial maintenance_mode: {initial_maintenance_mode} ---")
    try:
        resp = requests.put(
            f"{BASE_URL}/admin/settings",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"maintenance_mode": initial_maintenance_mode},
            timeout=10
        )
        if resp.status_code == 200:
            print(f"✓ Restored maintenance_mode to {initial_maintenance_mode}")
        else:
            print(f"⚠ Failed to restore: {resp.status_code}")
    except Exception as e:
        print(f"⚠ Exception restoring: {e}")


# ============================================================================
# TEST SUITE 2: Password Change Regression
# ============================================================================

def test_password_change():
    """Test password change endpoint regression"""
    print("\n" + "="*80)
    print("TEST SUITE 2: Password Change Endpoint Regression")
    print("="*80)
    
    # Test 2a: Login as admin and change password
    print("\n--- Test 2a: POST /api/auth/change-password (valid) ---")
    admin_token, _ = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("Admin login for password change", False, "Failed to get admin token")
        return
    
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/change-password",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"current_password": ADMIN_PASSWORD, "new_password": "newtest123"},
            timeout=10
        )
        
        if resp.status_code == 200:
            log_test("POST /api/auth/change-password with valid current password", True,
                    f"Status: {resp.status_code}")
        else:
            log_test("POST /api/auth/change-password with valid current password", False,
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
            return
    except Exception as e:
        log_test("POST /api/auth/change-password", False, f"Exception: {e}")
        return
    
    # Test 2b: Login with old password (should fail)
    print("\n--- Test 2b: Login with old password (should fail) ---")
    old_token, _ = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not old_token:
        log_test("Login with old password returns 401", True,
                "Old password correctly rejected")
    else:
        log_test("Login with old password returns 401", False,
                "Old password still works (password change didn't take effect)")
    
    # Test 2c: Login with new password (should succeed)
    print("\n--- Test 2c: Login with new password (should succeed) ---")
    new_token, new_user = login(ADMIN_EMAIL, "newtest123")
    if new_token and new_user.get("role") == "admin":
        log_test("Login with new password succeeds", True,
                f"New password works, role: {new_user.get('role')}")
    else:
        log_test("Login with new password succeeds", False,
                "New password doesn't work")
        return
    
    # Test 2d: Change password back to original
    print("\n--- Test 2d: Change password back to original ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/change-password",
            headers={"Authorization": f"Bearer {new_token}"},
            json={"current_password": "newtest123", "new_password": ADMIN_PASSWORD},
            timeout=10
        )
        
        if resp.status_code == 200:
            log_test("Change password back to original", True,
                    "Password restored successfully")
        else:
            log_test("Change password back to original", False,
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
            return
    except Exception as e:
        log_test("Change password back to original", False, f"Exception: {e}")
        return
    
    # Verify original password works again
    print("\n--- Verifying original password works ---")
    verify_token, _ = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if verify_token:
        print("✓ Original password restored and working")
    else:
        print("⚠ Failed to login with original password")
    
    # Test 2e: Wrong current password
    print("\n--- Test 2e: POST /api/auth/change-password (wrong current password) ---")
    admin_token, _ = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/change-password",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"current_password": "wrongpassword", "new_password": "anything"},
            timeout=10
        )
        
        if resp.status_code in [400, 401]:
            log_test("POST /api/auth/change-password with wrong current password returns 400/401", True,
                    f"Status: {resp.status_code}")
        else:
            log_test("POST /api/auth/change-password with wrong current password returns 400/401", False,
                    f"Status: {resp.status_code} (expected 400 or 401)")
    except Exception as e:
        log_test("POST /api/auth/change-password with wrong password", False, f"Exception: {e}")
    
    # Test 2f: Anonymous (no auth)
    print("\n--- Test 2f: POST /api/auth/change-password (no auth) ---")
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/change-password",
            json={"current_password": ADMIN_PASSWORD, "new_password": "anything"},
            timeout=10
        )
        
        if resp.status_code == 401:
            log_test("POST /api/auth/change-password without auth returns 401", True,
                    f"Status: {resp.status_code}")
        else:
            log_test("POST /api/auth/change-password without auth returns 401", False,
                    f"Status: {resp.status_code} (expected 401)")
    except Exception as e:
        log_test("POST /api/auth/change-password without auth", False, f"Exception: {e}")


# ============================================================================
# TEST SUITE 3: Regression Smokes
# ============================================================================

def test_regression_smokes():
    """Smoke tests for prior features"""
    print("\n" + "="*80)
    print("TEST SUITE 3: Regression Smoke Tests")
    print("="*80)
    
    # Login as admin for some tests
    admin_token, _ = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    
    # Test 3a: GET /api/homepage
    print("\n--- Test 3a: GET /api/homepage ---")
    try:
        resp = requests.get(f"{BASE_URL}/homepage", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "hero_slides" in data:
                log_test("GET /api/homepage returns 200", True,
                        f"Keys: {list(data.keys())}")
            else:
                log_test("GET /api/homepage returns 200", False,
                        f"Missing hero_slides. Keys: {list(data.keys())}")
        else:
            log_test("GET /api/homepage", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/homepage", False, f"Exception: {e}")
    
    # Test 3b: GET /api/products/bulk-template (CSV) - requires auth
    print("\n--- Test 3b: GET /api/products/bulk-template (CSV) ---")
    if admin_token:
        try:
            resp = requests.get(
                f"{BASE_URL}/products/bulk-template",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10
            )
            if resp.status_code == 200:
                content_type = resp.headers.get("Content-Type", "")
                if "text/csv" in content_type:
                    log_test("GET /api/products/bulk-template returns CSV", True,
                            f"Content-Type: {content_type}, Length: {len(resp.text)} bytes")
                else:
                    log_test("GET /api/products/bulk-template returns CSV", False,
                            f"Content-Type: {content_type} (expected text/csv)")
            else:
                log_test("GET /api/products/bulk-template", False, f"Status: {resp.status_code}")
        except Exception as e:
            log_test("GET /api/products/bulk-template", False, f"Exception: {e}")
    else:
        log_test("GET /api/products/bulk-template", False, "No admin token available")
    
    # Test 3c: GET /api/products/bulk-template?fmt=xlsx
    print("\n--- Test 3c: GET /api/products/bulk-template?fmt=xlsx ---")
    if admin_token:
        try:
            resp = requests.get(
                f"{BASE_URL}/products/bulk-template?fmt=xlsx",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10
            )
            if resp.status_code == 200:
                content_type = resp.headers.get("Content-Type", "")
                # Check for XLSX magic bytes (PK)
                starts_with_pk = resp.content[:2] == b'PK'
                if "spreadsheetml" in content_type and starts_with_pk:
                    log_test("GET /api/products/bulk-template?fmt=xlsx returns XLSX", True,
                            f"Content-Type: {content_type}, Starts with PK: {starts_with_pk}")
                else:
                    log_test("GET /api/products/bulk-template?fmt=xlsx returns XLSX", False,
                            f"Content-Type: {content_type}, Starts with PK: {starts_with_pk}")
            else:
                log_test("GET /api/products/bulk-template?fmt=xlsx", False, f"Status: {resp.status_code}")
        except Exception as e:
            log_test("GET /api/products/bulk-template?fmt=xlsx", False, f"Exception: {e}")
    else:
        log_test("GET /api/products/bulk-template?fmt=xlsx", False, "No admin token available")
    
    # Test 3d: GET /api/products/stock-update-template?fmt=xlsx
    print("\n--- Test 3d: GET /api/products/stock-update-template?fmt=xlsx ---")
    if admin_token:
        try:
            resp = requests.get(
                f"{BASE_URL}/products/stock-update-template?fmt=xlsx",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10
            )
            if resp.status_code == 200:
                content_type = resp.headers.get("Content-Type", "")
                starts_with_pk = resp.content[:2] == b'PK'
                if "spreadsheetml" in content_type and starts_with_pk:
                    log_test("GET /api/products/stock-update-template?fmt=xlsx returns XLSX", True,
                            f"Content-Type: {content_type}, Starts with PK: {starts_with_pk}")
                else:
                    log_test("GET /api/products/stock-update-template?fmt=xlsx returns XLSX", False,
                            f"Content-Type: {content_type}, Starts with PK: {starts_with_pk}")
            else:
                log_test("GET /api/products/stock-update-template?fmt=xlsx", False, f"Status: {resp.status_code}")
        except Exception as e:
            log_test("GET /api/products/stock-update-template?fmt=xlsx", False, f"Exception: {e}")
    else:
        log_test("GET /api/products/stock-update-template?fmt=xlsx", False, "No admin token available")
    
    # Test 3e: GET /api/push/public-key
    print("\n--- Test 3e: GET /api/push/public-key ---")
    try:
        resp = requests.get(f"{BASE_URL}/push/public-key", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "public_key" in data and isinstance(data["public_key"], str):
                log_test("GET /api/push/public-key returns public_key", True,
                        f"public_key length: {len(data['public_key'])} chars")
            else:
                log_test("GET /api/push/public-key returns public_key", False,
                        f"Response: {data}")
        else:
            log_test("GET /api/push/public-key", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/push/public-key", False, f"Exception: {e}")
    
    # Test 3f: GET /api/admin/health (as admin)
    print("\n--- Test 3f: GET /api/admin/health (as admin) ---")
    if admin_token:
        try:
            resp = requests.get(
                f"{BASE_URL}/admin/health",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                mongo_status = data.get("mongo", {}).get("status")
                mongo_ping = data.get("mongo", {}).get("ping_ms")
                if mongo_status == "ok" and isinstance(mongo_ping, (int, float)):
                    log_test("GET /api/admin/health returns mongo status", True,
                            f"mongo.status={mongo_status}, mongo.ping_ms={mongo_ping}")
                else:
                    log_test("GET /api/admin/health returns mongo status", False,
                            f"mongo.status={mongo_status}, mongo.ping_ms={mongo_ping}")
            else:
                log_test("GET /api/admin/health", False, f"Status: {resp.status_code}")
        except Exception as e:
            log_test("GET /api/admin/health", False, f"Exception: {e}")
    else:
        log_test("GET /api/admin/health", False, "No admin token available")
    
    # Test 3g: GET /api/sitemap.xml
    print("\n--- Test 3g: GET /api/sitemap.xml ---")
    try:
        resp = requests.get(f"{BASE_URL}/sitemap.xml", timeout=10)
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            content = resp.text
            is_xml = content.startswith("<?xml") and "<urlset" in content
            if "xml" in content_type and is_xml:
                log_test("GET /api/sitemap.xml returns XML", True,
                        f"Content-Type: {content_type}, Valid XML: {is_xml}")
            else:
                log_test("GET /api/sitemap.xml returns XML", False,
                        f"Content-Type: {content_type}, Valid XML: {is_xml}")
        else:
            log_test("GET /api/sitemap.xml", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/sitemap.xml", False, f"Exception: {e}")
    
    # Test 3h: GET /api/robots.txt
    print("\n--- Test 3h: GET /api/robots.txt ---")
    try:
        resp = requests.get(f"{BASE_URL}/robots.txt", timeout=10)
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            content = resp.text
            has_user_agent = "User-agent:" in content
            has_sitemap = "Sitemap:" in content
            if "text/plain" in content_type and has_user_agent and has_sitemap:
                log_test("GET /api/robots.txt returns valid robots.txt", True,
                        f"Content-Type: {content_type}, Has User-agent: {has_user_agent}, Has Sitemap: {has_sitemap}")
            else:
                log_test("GET /api/robots.txt returns valid robots.txt", False,
                        f"Content-Type: {content_type}, Has User-agent: {has_user_agent}, Has Sitemap: {has_sitemap}")
        else:
            log_test("GET /api/robots.txt", False, f"Status: {resp.status_code}")
    except Exception as e:
        log_test("GET /api/robots.txt", False, f"Exception: {e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("JUBASQUARE BACKEND API TESTING")
    print("Testing: Maintenance Mode + Password Change Regression")
    print("Base URL:", BASE_URL)
    print("="*80)
    
    try:
        # Run test suites
        test_maintenance_mode()
        test_password_change()
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
