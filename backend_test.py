#!/usr/bin/env python3
"""
Customer-only signup security tests
Tests that public signup is hardcoded to customer role and cannot be escalated
"""

import requests
import json
from typing import Dict, Any, Optional

BASE_URL = "https://jubasquare-odoo-v2.preview.emergentagent.com"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"

# Test results tracking
test_results = []

def log_test(test_name: str, passed: bool, details: str):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status}: {test_name}")
    print(f"   {details}")
    test_results.append({
        "test": test_name,
        "passed": passed,
        "details": details
    })

def get_admin_token() -> str:
    """Login as admin and get token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json()["token"]
    raise Exception(f"Admin login failed: {response.status_code} {response.text}")

def get_user_by_email(email: str, admin_token: str) -> Optional[Dict[str, Any]]:
    """Get user by email from admin users list"""
    response = requests.get(
        f"{BASE_URL}/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    if response.status_code == 200:
        users = response.json()
        for user in users:
            if user.get("email") == email:
                return user
    return None

def cleanup_test_user(email: str, admin_token: str):
    """Delete test user if exists"""
    user = get_user_by_email(email, admin_token)
    if user:
        user_id = user.get("id")
        if user_id:
            requests.delete(
                f"{BASE_URL}/api/admin/users/{user_id}",
                headers={"Authorization": f"Bearer {admin_token}"}
            )

print("=" * 80)
print("CUSTOMER-ONLY SIGNUP SECURITY TESTS")
print("=" * 80)
print(f"Base URL: {BASE_URL}")
print(f"Admin: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
print("=" * 80)

# Get admin token for verification
admin_token = get_admin_token()
print(f"\n✓ Admin token obtained")

# Test 1: Customer signup happy path
print("\n" + "=" * 80)
print("TEST 1: Customer signup happy path")
print("=" * 80)
test_email = "cust_test_A@example.com"
cleanup_test_user(test_email, admin_token)

response = requests.post(
    f"{BASE_URL}/api/auth/signup",
    json={
        "email": test_email,
        "password": "testpass123",
        "name": "Customer One",
        "phone": ""
    }
)

if response.status_code == 200:
    # Verify user was created with role="customer"
    user = get_user_by_email(test_email, admin_token)
    if user and user.get("role") == "customer":
        log_test(
            "Customer signup happy path",
            True,
            f"HTTP {response.status_code}. User created with role=customer. Response: {json.dumps(response.json(), indent=2)}"
        )
    else:
        log_test(
            "Customer signup happy path",
            False,
            f"HTTP {response.status_code} but user role is {user.get('role') if user else 'NOT FOUND'}"
        )
else:
    log_test(
        "Customer signup happy path",
        False,
        f"HTTP {response.status_code}. Response: {response.text}"
    )

# Test 2: Privilege escalation attempt - role:"seller"
print("\n" + "=" * 80)
print("TEST 2: Privilege escalation attempt - role:seller")
print("=" * 80)
test_email = "seller_attempt_B@jubasquare.test"
cleanup_test_user(test_email, admin_token)

response = requests.post(
    f"{BASE_URL}/api/auth/signup",
    json={
        "email": test_email,
        "password": "testpass123",
        "name": "Would Seller",
        "phone": "",
        "role": "seller"  # Attempt to escalate
    }
)

if response.status_code == 200:
    user = get_user_by_email(test_email, admin_token)
    if user and user.get("role") == "customer":
        log_test(
            "Privilege escalation blocked - seller",
            True,
            f"HTTP {response.status_code}. User created with role=customer (NOT seller). Escalation blocked. Response: {json.dumps(response.json(), indent=2)}"
        )
    else:
        log_test(
            "Privilege escalation blocked - seller",
            False,
            f"HTTP {response.status_code} but user role is {user.get('role') if user else 'NOT FOUND'}. SECURITY ISSUE: role escalation succeeded!"
        )
else:
    log_test(
        "Privilege escalation blocked - seller",
        False,
        f"HTTP {response.status_code}. Response: {response.text}"
    )

# Test 3: Privilege escalation attempt - role:"admin"
print("\n" + "=" * 80)
print("TEST 3: Privilege escalation attempt - role:admin")
print("=" * 80)
test_email = "admin_attempt_C@jubasquare.test"
cleanup_test_user(test_email, admin_token)

response = requests.post(
    f"{BASE_URL}/api/auth/signup",
    json={
        "email": test_email,
        "password": "testpass123",
        "name": "Attacker",
        "phone": "",
        "role": "admin"  # Attempt to escalate
    }
)

if response.status_code == 200:
    user = get_user_by_email(test_email, admin_token)
    if user and user.get("role") == "customer":
        log_test(
            "Privilege escalation blocked - admin",
            True,
            f"HTTP {response.status_code}. User created with role=customer (NOT admin). Escalation blocked. Response: {json.dumps(response.json(), indent=2)}"
        )
    else:
        log_test(
            "Privilege escalation blocked - admin",
            False,
            f"HTTP {response.status_code} but user role is {user.get('role') if user else 'NOT FOUND'}. SECURITY ISSUE: role escalation succeeded!"
        )
else:
    log_test(
        "Privilege escalation blocked - admin",
        False,
        f"HTTP {response.status_code}. Response: {response.text}"
    )

# Test 4: Privilege escalation attempt - role:"driver"
print("\n" + "=" * 80)
print("TEST 4: Privilege escalation attempt - role:driver")
print("=" * 80)
test_email = "driver_attempt_D@jubasquare.test"
cleanup_test_user(test_email, admin_token)

response = requests.post(
    f"{BASE_URL}/api/auth/signup",
    json={
        "email": test_email,
        "password": "testpass123",
        "name": "Fake Driver",
        "phone": "",
        "role": "driver"  # Attempt to escalate
    }
)

if response.status_code == 200:
    user = get_user_by_email(test_email, admin_token)
    if user and user.get("role") == "customer":
        log_test(
            "Privilege escalation blocked - driver",
            True,
            f"HTTP {response.status_code}. User created with role=customer (NOT driver). Escalation blocked. Response: {json.dumps(response.json(), indent=2)}"
        )
    else:
        log_test(
            "Privilege escalation blocked - driver",
            False,
            f"HTTP {response.status_code} but user role is {user.get('role') if user else 'NOT FOUND'}. SECURITY ISSUE: role escalation succeeded!"
        )
else:
    log_test(
        "Privilege escalation blocked - driver",
        False,
        f"HTTP {response.status_code}. Response: {response.text}"
    )

# Test 5a: Validation - missing name
print("\n" + "=" * 80)
print("TEST 5a: Validation - missing name")
print("=" * 80)
response = requests.post(
    f"{BASE_URL}/api/auth/signup",
    json={
        "email": "noname@jubasquare.test",
        "password": "testpass123",
        "phone": ""
    }
)

if response.status_code == 422:
    log_test(
        "Validation - missing name",
        True,
        f"HTTP {response.status_code} (422 Unprocessable Entity). Validation working. Response: {response.text[:200]}"
    )
else:
    log_test(
        "Validation - missing name",
        False,
        f"Expected HTTP 422, got {response.status_code}. Response: {response.text}"
    )

# Test 5b: Validation - short password
print("\n" + "=" * 80)
print("TEST 5b: Validation - short password")
print("=" * 80)
response = requests.post(
    f"{BASE_URL}/api/auth/signup",
    json={
        "email": "shortpw@jubasquare.test",
        "password": "abc",
        "name": "Short"
    }
)

if response.status_code == 422:
    log_test(
        "Validation - short password",
        True,
        f"HTTP {response.status_code} (422 Unprocessable Entity). Validation working. Response: {response.text[:200]}"
    )
else:
    log_test(
        "Validation - short password",
        False,
        f"Expected HTTP 422, got {response.status_code}. Response: {response.text}"
    )

# Test 5c: Validation - missing email
print("\n" + "=" * 80)
print("TEST 5c: Validation - missing email")
print("=" * 80)
response = requests.post(
    f"{BASE_URL}/api/auth/signup",
    json={
        "password": "testpass123",
        "name": "NoEmail"
    }
)

if response.status_code == 422:
    log_test(
        "Validation - missing email",
        True,
        f"HTTP {response.status_code} (422 Unprocessable Entity). Validation working. Response: {response.text[:200]}"
    )
else:
    log_test(
        "Validation - missing email",
        False,
        f"Expected HTTP 422, got {response.status_code}. Response: {response.text}"
    )

# Test 6: Duplicate email
print("\n" + "=" * 80)
print("TEST 6: Duplicate email")
print("=" * 80)
# Use the email from test 1
test_email = "cust_test_A@jubasquare.test"
response = requests.post(
    f"{BASE_URL}/api/auth/signup",
    json={
        "email": test_email,
        "password": "testpass123",
        "name": "Customer One Duplicate",
        "phone": ""
    }
)

if response.status_code == 400:
    log_test(
        "Duplicate email rejected",
        True,
        f"HTTP {response.status_code} (400 Bad Request). Duplicate detection working. Response: {response.text}"
    )
else:
    log_test(
        "Duplicate email rejected",
        False,
        f"Expected HTTP 400, got {response.status_code}. Response: {response.text}"
    )

# Test 7: Regression - admin-created seller still works
print("\n" + "=" * 80)
print("TEST 7: Regression - admin-created seller still works")
print("=" * 80)
test_email = "admin_created_seller_E@jubasquare.test"
cleanup_test_user(test_email, admin_token)

response = requests.post(
    f"{BASE_URL}/api/admin/users",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={
        "email": test_email,
        "password": "testpass123",
        "name": "Real Seller",
        "role": "seller",
        "phone": ""
    }
)

if response.status_code in [200, 201]:
    user = get_user_by_email(test_email, admin_token)
    if user and user.get("role") == "seller":
        log_test(
            "Admin-created seller works",
            True,
            f"HTTP {response.status_code}. Admin successfully created seller with role=seller. Response: {json.dumps(response.json(), indent=2)}"
        )
    else:
        log_test(
            "Admin-created seller works",
            False,
            f"HTTP {response.status_code} but user role is {user.get('role') if user else 'NOT FOUND'}"
        )
else:
    log_test(
        "Admin-created seller works",
        False,
        f"HTTP {response.status_code}. Response: {response.text}"
    )

# Test 8a: Regression smoke - admin login
print("\n" + "=" * 80)
print("TEST 8a: Regression smoke - admin login")
print("=" * 80)
response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"email": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
)

if response.status_code == 200 and "token" in response.json():
    log_test(
        "Admin login works",
        True,
        f"HTTP {response.status_code}. Admin login successful. Token obtained."
    )
else:
    log_test(
        "Admin login works",
        False,
        f"HTTP {response.status_code}. Response: {response.text}"
    )

# Test 8b: Regression smoke - homepage
print("\n" + "=" * 80)
print("TEST 8b: Regression smoke - homepage")
print("=" * 80)
response = requests.get(f"{BASE_URL}/api/homepage")

if response.status_code == 200:
    data = response.json()
    has_required_fields = all(k in data for k in ["hero_slides", "hero_tagline", "hero_title", "hero_subtitle"])
    if has_required_fields:
        log_test(
            "Homepage endpoint works",
            True,
            f"HTTP {response.status_code}. Homepage returns required fields."
        )
    else:
        log_test(
            "Homepage endpoint works",
            False,
            f"HTTP {response.status_code} but missing required fields. Got: {list(data.keys())}"
        )
else:
    log_test(
        "Homepage endpoint works",
        False,
        f"HTTP {response.status_code}. Response: {response.text}"
    )

# Test 8c: Regression smoke - public settings
print("\n" + "=" * 80)
print("TEST 8c: Regression smoke - public settings")
print("=" * 80)
response = requests.get(f"{BASE_URL}/api/settings/public")

if response.status_code == 200:
    data = response.json()
    has_required_fields = "maintenance_mode" in data and "homepage" in data
    if has_required_fields:
        log_test(
            "Public settings endpoint works",
            True,
            f"HTTP {response.status_code}. Settings returns maintenance_mode and homepage fields."
        )
    else:
        log_test(
            "Public settings endpoint works",
            False,
            f"HTTP {response.status_code} but missing required fields. Got: {list(data.keys())}"
        )
else:
    log_test(
        "Public settings endpoint works",
        False,
        f"HTTP {response.status_code}. Response: {response.text}"
    )

# Summary
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

passed = sum(1 for r in test_results if r["passed"])
total = len(test_results)
pass_rate = (passed / total * 100) if total > 0 else 0

print(f"\nTotal tests: {total}")
print(f"Passed: {passed}")
print(f"Failed: {total - passed}")
print(f"Pass rate: {pass_rate:.1f}%")

print("\n" + "=" * 80)
print("DETAILED RESULTS")
print("=" * 80)

for result in test_results:
    status = "✅ PASS" if result["passed"] else "❌ FAIL"
    print(f"\n{status}: {result['test']}")

if passed == total:
    print("\n" + "=" * 80)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 80)
    print("\nCONCLUSION:")
    print("✓ Public signup is hardcoded to customer role")
    print("✓ Privilege escalation attempts (seller/admin/driver) are blocked")
    print("✓ Validation works correctly (missing fields, short password)")
    print("✓ Duplicate email detection works")
    print("✓ Admin-created sellers still work (regression OK)")
    print("✓ Core endpoints working (admin login, homepage, settings)")
else:
    print("\n" + "=" * 80)
    print("⚠️  SOME TESTS FAILED")
    print("=" * 80)
    print("\nFailed tests:")
    for result in test_results:
        if not result["passed"]:
            print(f"  ❌ {result['test']}")
            print(f"     {result['details']}")
