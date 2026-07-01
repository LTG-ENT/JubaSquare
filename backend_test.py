#!/usr/bin/env python3
"""
Backend API Testing for JubaSquare
Tests customer-only signup, maintenance mode toggle, and regression smokes
"""

import requests
import time
import sys
from typing import Dict, Any, Optional

# Base URL from review request
BASE_URL = "https://jubasquare-odoo-v2.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Admin credentials
ADMIN_EMAIL = "admin@jubasquare.com"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"

# Test results tracking
test_results = []
admin_token = None


def log_test(test_num: int, name: str, passed: bool, details: str = ""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"Test {test_num}: {status} - {name}"
    if details:
        result += f"\n  Details: {details}"
    print(result)
    test_results.append({
        "test_num": test_num,
        "name": name,
        "passed": passed,
        "details": details
    })


def get_admin_token() -> Optional[str]:
    """Login as admin and get token"""
    global admin_token
    if admin_token:
        return admin_token
    
    try:
        resp = requests.post(
            f"{API_BASE}/auth/login",
            json={"email": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            admin_token = data.get("token")
            return admin_token
    except Exception as e:
        print(f"Failed to get admin token: {e}")
    return None


def cleanup_test_user(email: str):
    """Attempt to delete test user via admin API"""
    token = get_admin_token()
    if not token:
        return
    
    try:
        # Get user list
        resp = requests.get(
            f"{API_BASE}/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if resp.status_code == 200:
            users = resp.json()
            for user in users:
                if user.get("email") == email:
                    user_id = user.get("id")
                    # Try to delete
                    requests.delete(
                        f"{API_BASE}/admin/users/{user_id}",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10
                    )
                    break
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
# FEATURE 1: Customer-only public signup
# ═══════════════════════════════════════════════════════════════════

def test_1_customer_signup_happy_path():
    """Test 1: Customer signup happy path"""
    ts = int(time.time())
    email = f"cust_{ts}_A@example.com"
    
    try:
        # Signup
        resp = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": email,
                "password": "testpass123",
                "name": "Customer One",
                "phone": ""
            },
            timeout=10
        )
        
        if resp.status_code != 200:
            log_test(1, "Customer signup happy path", False, 
                    f"Signup failed: {resp.status_code} - {resp.text[:200]}")
            return
        
        data = resp.json()
        if not data.get("ok"):
            log_test(1, "Customer signup happy path", False, 
                    f"Response ok=false: {data}")
            return
        
        # Small delay to ensure DB write completes
        time.sleep(0.5)
        
        # Login as admin and verify role
        token = get_admin_token()
        if not token:
            log_test(1, "Customer signup happy path", False, 
                    "Could not get admin token to verify")
            return
        
        resp = requests.get(
            f"{API_BASE}/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        if resp.status_code != 200:
            log_test(1, "Customer signup happy path", False, 
                    f"Admin users list failed: {resp.status_code}")
            return
        
        users = resp.json()
        found_user = None
        for user in users:
            if user.get("email") == email:
                found_user = user
                break
        
        if not found_user:
            log_test(1, "Customer signup happy path", False, 
                    f"User {email} not found in admin list (total users: {len(users)})")
            return
        
        if found_user.get("role") != "customer":
            log_test(1, "Customer signup happy path", False, 
                    f"Role is {found_user.get('role')}, expected 'customer'")
            return
        
        log_test(1, "Customer signup happy path", True, 
                f"User created with role=customer")
        
    except Exception as e:
        log_test(1, "Customer signup happy path", False, f"Exception: {e}")


def test_2_privilege_escalation_seller():
    """Test 2: Privilege escalation attempt (role=seller)"""
    ts = int(time.time())
    email = f"seller_{ts}_B@example.com"
    
    try:
        resp = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": email,
                "password": "testpass123",
                "name": "Would Seller",
                "phone": "",
                "role": "seller"  # Attempt to escalate
            },
            timeout=10
        )
        
        if resp.status_code != 200:
            log_test(2, "Privilege escalation (seller)", False, 
                    f"Signup failed: {resp.status_code}")
            return
        
        # Small delay
        time.sleep(0.5)
        
        # Verify role is customer, not seller
        token = get_admin_token()
        if not token:
            log_test(2, "Privilege escalation (seller)", False, 
                    "Could not get admin token")
            return
        
        resp = requests.get(
            f"{API_BASE}/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        users = resp.json()
        found_user = None
        for user in users:
            if user.get("email") == email:
                found_user = user
                break
        
        if not found_user:
            log_test(2, "Privilege escalation (seller)", False, 
                    f"User not found (total users: {len(users)})")
            return
        
        role = found_user.get("role")
        if role == "seller":
            log_test(2, "Privilege escalation (seller)", False, 
                    f"SECURITY ISSUE: Role escalation succeeded! Role is 'seller'")
            return
        
        if role != "customer":
            log_test(2, "Privilege escalation (seller)", False, 
                    f"Role is {role}, expected 'customer'")
            return
        
        log_test(2, "Privilege escalation (seller)", True, 
                f"Role correctly forced to 'customer', not 'seller'")
        
    except Exception as e:
        log_test(2, "Privilege escalation (seller)", False, f"Exception: {e}")


def test_3_privilege_escalation_admin():
    """Test 3: Privilege escalation attempt (role=admin)"""
    ts = int(time.time())
    email = f"esc_{ts}_C@example.com"
    
    try:
        resp = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": email,
                "password": "testpass123",
                "name": "Attacker",
                "phone": "",
                "role": "admin"  # Attempt to escalate
            },
            timeout=10
        )
        
        if resp.status_code != 200:
            log_test(3, "Privilege escalation (admin)", False, 
                    f"Signup failed: {resp.status_code}")
            return
        
        # Small delay
        time.sleep(0.5)
        
        # Verify role is customer, not admin
        token = get_admin_token()
        resp = requests.get(
            f"{API_BASE}/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        users = resp.json()
        found_user = None
        for user in users:
            if user.get("email") == email:
                found_user = user
                break
        
        if not found_user:
            log_test(3, "Privilege escalation (admin)", False, 
                    f"User not found (total users: {len(users)})")
            return
        
        role = found_user.get("role")
        if role == "admin":
            log_test(3, "Privilege escalation (admin)", False, 
                    f"CRITICAL SECURITY ISSUE: Role escalation to admin succeeded!")
            return
        
        if role != "customer":
            log_test(3, "Privilege escalation (admin)", False, 
                    f"Role is {role}, expected 'customer'")
            return
        
        log_test(3, "Privilege escalation (admin)", True, 
                f"Role correctly forced to 'customer', not 'admin'")
        
    except Exception as e:
        log_test(3, "Privilege escalation (admin)", False, f"Exception: {e}")


def test_4_privilege_escalation_driver():
    """Test 4: Privilege escalation attempt (role=driver)"""
    ts = int(time.time())
    email = f"drv_{ts}_D@example.com"
    
    try:
        resp = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": email,
                "password": "testpass123",
                "name": "Fake Driver",
                "phone": "",
                "role": "driver"  # Attempt to escalate
            },
            timeout=10
        )
        
        if resp.status_code != 200:
            log_test(4, "Privilege escalation (driver)", False, 
                    f"Signup failed: {resp.status_code}")
            return
        
        # Small delay
        time.sleep(0.5)
        
        # Verify role is customer, not driver
        token = get_admin_token()
        resp = requests.get(
            f"{API_BASE}/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        users = resp.json()
        found_user = None
        for user in users:
            if user.get("email") == email:
                found_user = user
                break
        
        if not found_user:
            log_test(4, "Privilege escalation (driver)", False, 
                    f"User not found (total users: {len(users)})")
            return
        
        role = found_user.get("role")
        if role == "driver":
            log_test(4, "Privilege escalation (driver)", False, 
                    f"SECURITY ISSUE: Role escalation to driver succeeded!")
            return
        
        if role != "customer":
            log_test(4, "Privilege escalation (driver)", False, 
                    f"Role is {role}, expected 'customer'")
            return
        
        log_test(4, "Privilege escalation (driver)", True, 
                f"Role correctly forced to 'customer', not 'driver'")
        
    except Exception as e:
        log_test(4, "Privilege escalation (driver)", False, f"Exception: {e}")


def test_5_validation_errors():
    """Test 5: Validation errors"""
    ts = int(time.time())
    
    # Test 5a: Missing name
    try:
        resp = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": f"noname_{ts}@example.com",
                "password": "testpass123",
                "phone": ""
            },
            timeout=10
        )
        
        if resp.status_code != 422:
            log_test(5, "Validation (missing name)", False, 
                    f"Expected 422, got {resp.status_code}")
            return
        
        print("  5a: Missing name → 422 ✓")
        
    except Exception as e:
        log_test(5, "Validation (missing name)", False, f"Exception: {e}")
        return
    
    # Test 5b: Short password
    try:
        resp = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": f"shortpw_{ts}@example.com",
                "password": "abc",
                "name": "Short"
            },
            timeout=10
        )
        
        if resp.status_code != 422:
            log_test(5, "Validation (short password)", False, 
                    f"Expected 422, got {resp.status_code}")
            return
        
        print("  5b: Short password → 422 ✓")
        
    except Exception as e:
        log_test(5, "Validation (short password)", False, f"Exception: {e}")
        return
    
    # Test 5c: Missing email
    try:
        resp = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "password": "testpass123",
                "name": "NoEmail"
            },
            timeout=10
        )
        
        if resp.status_code != 422:
            log_test(5, "Validation (missing email)", False, 
                    f"Expected 422, got {resp.status_code}")
            return
        
        print("  5c: Missing email → 422 ✓")
        
        log_test(5, "Validation errors", True, 
                "All 3 validation tests passed (missing name, short password, missing email)")
        
    except Exception as e:
        log_test(5, "Validation errors", False, f"Exception: {e}")


def test_6_duplicate_email():
    """Test 6: Duplicate email"""
    ts = int(time.time())
    email = f"duplicate_{ts}@example.com"
    
    try:
        # First signup
        resp = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": email,
                "password": "testpass123",
                "name": "First User",
                "phone": ""
            },
            timeout=10
        )
        
        if resp.status_code != 200:
            log_test(6, "Duplicate email", False, 
                    f"First signup failed: {resp.status_code}")
            return
        
        # Second signup with same email
        resp = requests.post(
            f"{API_BASE}/auth/signup",
            json={
                "email": email,
                "password": "testpass123",
                "name": "Second User",
                "phone": ""
            },
            timeout=10
        )
        
        if resp.status_code != 400:
            log_test(6, "Duplicate email", False, 
                    f"Expected 400 for duplicate, got {resp.status_code}")
            return
        
        log_test(6, "Duplicate email", True, 
                "Duplicate email correctly rejected with 400")
        
    except Exception as e:
        log_test(6, "Duplicate email", False, f"Exception: {e}")


def test_7_admin_created_seller():
    """Test 7: Admin-created seller still works"""
    ts = int(time.time())
    email = f"seller_admin_{ts}_E@example.com"
    
    try:
        token = get_admin_token()
        if not token:
            log_test(7, "Admin-created seller", False, 
                    "Could not get admin token")
            return
        
        resp = requests.post(
            f"{API_BASE}/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": email,
                "password": "testpass123",
                "name": "Real Seller",
                "role": "seller",
                "phone": ""
            },
            timeout=10
        )
        
        if resp.status_code not in [200, 201]:
            log_test(7, "Admin-created seller", False, 
                    f"Admin user creation failed: {resp.status_code} - {resp.text[:200]}")
            return
        
        # Small delay
        time.sleep(0.5)
        
        # Verify role
        resp = requests.get(
            f"{API_BASE}/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        users = resp.json()
        found_user = None
        for user in users:
            if user.get("email") == email:
                found_user = user
                break
        
        if not found_user:
            log_test(7, "Admin-created seller", False, 
                    f"User not found after creation (total users: {len(users)})")
            return
        
        role = found_user.get("role")
        if role != "seller":
            log_test(7, "Admin-created seller", False, 
                    f"Role is {role}, expected 'seller'")
            return
        
        log_test(7, "Admin-created seller", True, 
                "Admin can still create sellers with role='seller'")
        
    except Exception as e:
        log_test(7, "Admin-created seller", False, f"Exception: {e}")


# ═══════════════════════════════════════════════════════════════════
# FEATURE 2: Maintenance mode toggle regression
# ═══════════════════════════════════════════════════════════════════

def test_8_maintenance_mode_enable():
    """Test 8: Enable maintenance mode"""
    try:
        token = get_admin_token()
        if not token:
            log_test(8, "Enable maintenance mode", False, 
                    "Could not get admin token")
            return
        
        resp = requests.put(
            f"{API_BASE}/admin/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={"maintenance_mode": True},
            timeout=10
        )
        
        if resp.status_code != 200:
            log_test(8, "Enable maintenance mode", False, 
                    f"PUT failed: {resp.status_code} - {resp.text[:200]}")
            return
        
        data = resp.json()
        if not data.get("maintenance_mode"):
            log_test(8, "Enable maintenance mode", False, 
                    f"Response doesn't show maintenance_mode=true: {data}")
            return
        
        log_test(8, "Enable maintenance mode", True, 
                "PUT /api/admin/settings with maintenance_mode=true succeeded")
        
    except Exception as e:
        log_test(8, "Enable maintenance mode", False, f"Exception: {e}")


def test_9_maintenance_mode_public_check_enabled():
    """Test 9: Public settings shows maintenance_mode=true"""
    try:
        resp = requests.get(
            f"{API_BASE}/settings/public",
            timeout=10
        )
        
        if resp.status_code != 200:
            log_test(9, "Public settings (enabled)", False, 
                    f"GET failed: {resp.status_code}")
            return
        
        data = resp.json()
        if not data.get("maintenance_mode"):
            log_test(9, "Public settings (enabled)", False, 
                    f"maintenance_mode is not true: {data.get('maintenance_mode')}")
            return
        
        log_test(9, "Public settings (enabled)", True, 
                "GET /api/settings/public shows maintenance_mode=true (cache invalidation works)")
        
    except Exception as e:
        log_test(9, "Public settings (enabled)", False, f"Exception: {e}")


def test_10_maintenance_mode_disable():
    """Test 10: Disable maintenance mode"""
    try:
        token = get_admin_token()
        if not token:
            log_test(10, "Disable maintenance mode", False, 
                    "Could not get admin token")
            return
        
        resp = requests.put(
            f"{API_BASE}/admin/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={"maintenance_mode": False},
            timeout=10
        )
        
        if resp.status_code != 200:
            log_test(10, "Disable maintenance mode", False, 
                    f"PUT failed: {resp.status_code}")
            return
        
        data = resp.json()
        if data.get("maintenance_mode") is not False:
            log_test(10, "Disable maintenance mode", False, 
                    f"Response doesn't show maintenance_mode=false: {data}")
            return
        
        log_test(10, "Disable maintenance mode", True, 
                "PUT /api/admin/settings with maintenance_mode=false succeeded")
        
    except Exception as e:
        log_test(10, "Disable maintenance mode", False, f"Exception: {e}")


def test_11_maintenance_mode_public_check_disabled():
    """Test 11: Public settings shows maintenance_mode=false"""
    try:
        resp = requests.get(
            f"{API_BASE}/settings/public",
            timeout=10
        )
        
        if resp.status_code != 200:
            log_test(11, "Public settings (disabled)", False, 
                    f"GET failed: {resp.status_code}")
            return
        
        data = resp.json()
        if data.get("maintenance_mode") is not False:
            log_test(11, "Public settings (disabled)", False, 
                    f"maintenance_mode is not false: {data.get('maintenance_mode')}")
            return
        
        log_test(11, "Public settings (disabled)", True, 
                "GET /api/settings/public shows maintenance_mode=false")
        
    except Exception as e:
        log_test(11, "Public settings (disabled)", False, f"Exception: {e}")


def test_12_maintenance_mode_non_admin():
    """Test 12: Non-admin cannot toggle maintenance mode"""
    ts = int(time.time())
    email = f"customer_{ts}@example.com"
    
    try:
        # Create a customer via admin API (so email_verified=True)
        token = get_admin_token()
        if not token:
            log_test(12, "Non-admin maintenance toggle", False, 
                    "Could not get admin token")
            return
        
        resp = requests.post(
            f"{API_BASE}/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": email,
                "password": "testpass123",
                "name": "Test Customer",
                "role": "customer",
                "phone": ""
            },
            timeout=10
        )
        
        if resp.status_code not in [200, 201]:
            log_test(12, "Non-admin maintenance toggle", False, 
                    f"Customer creation failed: {resp.status_code}")
            return
        
        # Login as customer
        resp = requests.post(
            f"{API_BASE}/auth/login",
            json={"email": email, "password": "testpass123"},
            timeout=10
        )
        
        if resp.status_code != 200:
            log_test(12, "Non-admin maintenance toggle", False, 
                    f"Customer login failed: {resp.status_code}")
            return
        
        customer_token = resp.json().get("token")
        
        # Try to toggle maintenance mode
        resp = requests.put(
            f"{API_BASE}/admin/settings",
            headers={"Authorization": f"Bearer {customer_token}"},
            json={"maintenance_mode": True},
            timeout=10
        )
        
        if resp.status_code != 403:
            log_test(12, "Non-admin maintenance toggle", False, 
                    f"Expected 403, got {resp.status_code}")
            return
        
        log_test(12, "Non-admin maintenance toggle", True, 
                "Customer correctly denied with 403")
        
    except Exception as e:
        log_test(12, "Non-admin maintenance toggle", False, f"Exception: {e}")


# ═══════════════════════════════════════════════════════════════════
# REGRESSION SMOKES
# ═══════════════════════════════════════════════════════════════════

def test_13_admin_login_username():
    """Test 13: Admin login with username"""
    try:
        resp = requests.post(
            f"{API_BASE}/auth/login",
            json={"email": "admin", "password": "1234"},
            timeout=10
        )
        
        if resp.status_code != 200:
            log_test(13, "Admin login (username)", False, 
                    f"Login failed: {resp.status_code}")
            return
        
        data = resp.json()
        if not data.get("token"):
            log_test(13, "Admin login (username)", False, 
                    "No token in response")
            return
        
        log_test(13, "Admin login (username)", True, 
                f"Login successful with token")
        
    except Exception as e:
        log_test(13, "Admin login (username)", False, f"Exception: {e}")


def test_14_admin_login_email():
    """Test 14: Admin login with email"""
    try:
        resp = requests.post(
            f"{API_BASE}/auth/login",
            json={"email": "admin@jubasquare.com", "password": "1234"},
            timeout=10
        )
        
        if resp.status_code != 200:
            log_test(14, "Admin login (email)", False, 
                    f"Login failed: {resp.status_code}")
            return
        
        data = resp.json()
        if not data.get("token"):
            log_test(14, "Admin login (email)", False, 
                    "No token in response")
            return
        
        log_test(14, "Admin login (email)", True, 
                f"Login successful with token")
        
    except Exception as e:
        log_test(14, "Admin login (email)", False, f"Exception: {e}")


def test_15_homepage():
    """Test 15: GET /api/homepage"""
    try:
        resp = requests.get(f"{API_BASE}/homepage", timeout=10)
        
        if resp.status_code != 200:
            log_test(15, "GET /api/homepage", False, 
                    f"Failed: {resp.status_code}")
            return
        
        data = resp.json()
        if "hero_slides" not in data:
            log_test(15, "GET /api/homepage", False, 
                    "Missing hero_slides in response")
            return
        
        log_test(15, "GET /api/homepage", True, 
                f"Returns 200 with hero_slides")
        
    except Exception as e:
        log_test(15, "GET /api/homepage", False, f"Exception: {e}")


def test_16_bulk_template_csv():
    """Test 16: GET /api/products/bulk-template (CSV)"""
    try:
        resp = requests.get(f"{API_BASE}/products/bulk-template", timeout=10)
        
        if resp.status_code != 200:
            log_test(16, "Bulk template (CSV)", False, 
                    f"Failed: {resp.status_code}")
            return
        
        content_type = resp.headers.get("Content-Type", "")
        if "text/csv" not in content_type:
            log_test(16, "Bulk template (CSV)", False, 
                    f"Wrong Content-Type: {content_type}")
            return
        
        log_test(16, "Bulk template (CSV)", True, 
                f"Returns 200 text/csv")
        
    except Exception as e:
        log_test(16, "Bulk template (CSV)", False, f"Exception: {e}")


def test_17_bulk_template_xlsx():
    """Test 17: GET /api/products/bulk-template?fmt=xlsx"""
    try:
        resp = requests.get(f"{API_BASE}/products/bulk-template?fmt=xlsx", timeout=10)
        
        if resp.status_code != 200:
            log_test(17, "Bulk template (XLSX)", False, 
                    f"Failed: {resp.status_code}")
            return
        
        content_type = resp.headers.get("Content-Type", "")
        if "spreadsheetml" not in content_type:
            log_test(17, "Bulk template (XLSX)", False, 
                    f"Wrong Content-Type: {content_type}")
            return
        
        # Check for PK header (ZIP magic bytes)
        if not resp.content.startswith(b"PK"):
            log_test(17, "Bulk template (XLSX)", False, 
                    "Not a valid XLSX file (missing PK header)")
            return
        
        log_test(17, "Bulk template (XLSX)", True, 
                f"Returns 200 xlsx with PK header")
        
    except Exception as e:
        log_test(17, "Bulk template (XLSX)", False, f"Exception: {e}")


def test_18_push_public_key():
    """Test 18: GET /api/push/public-key"""
    try:
        resp = requests.get(f"{API_BASE}/push/public-key", timeout=10)
        
        if resp.status_code != 200:
            log_test(18, "Push public key", False, 
                    f"Failed: {resp.status_code}")
            return
        
        data = resp.json()
        if "public_key" not in data:
            log_test(18, "Push public key", False, 
                    "Missing public_key in response")
            return
        
        log_test(18, "Push public key", True, 
                f"Returns 200 with public_key")
        
    except Exception as e:
        log_test(18, "Push public key", False, f"Exception: {e}")


def test_19_admin_health():
    """Test 19: GET /api/admin/health"""
    try:
        token = get_admin_token()
        if not token:
            log_test(19, "Admin health", False, 
                    "Could not get admin token")
            return
        
        resp = requests.get(
            f"{API_BASE}/admin/health",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        if resp.status_code != 200:
            log_test(19, "Admin health", False, 
                    f"Failed: {resp.status_code}")
            return
        
        data = resp.json()
        mongo_status = data.get("mongo", {}).get("status")
        if mongo_status != "ok":
            log_test(19, "Admin health", False, 
                    f"mongo.status is {mongo_status}, expected 'ok'")
            return
        
        log_test(19, "Admin health", True, 
                f"Returns 200 with mongo.status='ok'")
        
    except Exception as e:
        log_test(19, "Admin health", False, f"Exception: {e}")


def test_20_sitemap():
    """Test 20: GET /api/sitemap.xml"""
    try:
        resp = requests.get(f"{API_BASE}/sitemap.xml", timeout=10)
        
        if resp.status_code != 200:
            log_test(20, "Sitemap", False, 
                    f"Failed: {resp.status_code}")
            return
        
        content_type = resp.headers.get("Content-Type", "")
        if "xml" not in content_type:
            log_test(20, "Sitemap", False, 
                    f"Wrong Content-Type: {content_type}")
            return
        
        if not resp.text.startswith("<?xml"):
            log_test(20, "Sitemap", False, 
                    "Not valid XML (doesn't start with <?xml)")
            return
        
        log_test(20, "Sitemap", True, 
                f"Returns 200 xml")
        
    except Exception as e:
        log_test(20, "Sitemap", False, f"Exception: {e}")


def test_21_robots():
    """Test 21: GET /api/robots.txt"""
    try:
        resp = requests.get(f"{API_BASE}/robots.txt", timeout=10)
        
        if resp.status_code != 200:
            log_test(21, "Robots.txt", False, 
                    f"Failed: {resp.status_code}")
            return
        
        content_type = resp.headers.get("Content-Type", "")
        if "text/plain" not in content_type:
            log_test(21, "Robots.txt", False, 
                    f"Wrong Content-Type: {content_type}")
            return
        
        log_test(21, "Robots.txt", True, 
                f"Returns 200 text/plain")
        
    except Exception as e:
        log_test(21, "Robots.txt", False, f"Exception: {e}")


# ═══════════════════════════════════════════════════════════════════
# MAIN TEST RUNNER
# ═══════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("JubaSquare Backend API Testing")
    print(f"Base URL: {BASE_URL}")
    print("=" * 70)
    print()
    
    print("FEATURE 1: Customer-only public signup (7 tests)")
    print("-" * 70)
    test_1_customer_signup_happy_path()
    test_2_privilege_escalation_seller()
    test_3_privilege_escalation_admin()
    test_4_privilege_escalation_driver()
    test_5_validation_errors()
    test_6_duplicate_email()
    test_7_admin_created_seller()
    print()
    
    print("FEATURE 2: Maintenance mode toggle regression (5 tests)")
    print("-" * 70)
    test_8_maintenance_mode_enable()
    test_9_maintenance_mode_public_check_enabled()
    test_10_maintenance_mode_disable()
    test_11_maintenance_mode_public_check_disabled()
    test_12_maintenance_mode_non_admin()
    print()
    
    print("REGRESSION SMOKES (9 tests)")
    print("-" * 70)
    test_13_admin_login_username()
    test_14_admin_login_email()
    test_15_homepage()
    test_16_bulk_template_csv()
    test_17_bulk_template_xlsx()
    test_18_push_public_key()
    test_19_admin_health()
    test_20_sitemap()
    test_21_robots()
    print()
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in test_results if r["passed"])
    failed = sum(1 for r in test_results if not r["passed"])
    total = len(test_results)
    
    print(f"Total: {total} tests")
    print(f"Passed: {passed} ({passed*100//total}%)")
    print(f"Failed: {failed}")
    print()
    
    if failed > 0:
        print("FAILED TESTS:")
        for r in test_results:
            if not r["passed"]:
                print(f"  Test {r['test_num']}: {r['name']}")
                if r["details"]:
                    print(f"    {r['details']}")
        print()
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
