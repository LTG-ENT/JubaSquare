#!/usr/bin/env python3
"""
Admin User Management Backend Testing
Tests all 8 new admin user management endpoints + login flow updates
"""

import requests
import sys
import json
import time
from typing import Optional

BASE_URL = "https://category-bulletproof.preview.emergentagent.com/api"

# Admin credentials
ADMIN_EMAIL = "ltg-general-trading@hotmail.com"
ADMIN_PASSWORD = "Kokobleake1"

# Track created users for cleanup
created_users = []

def log(msg: str):
    print(f"  {msg}")

def test_header(msg: str):
    print(f"\n{'='*80}")
    print(f"  {msg}")
    print(f"{'='*80}")

def admin_login() -> str:
    """Login as admin and return token."""
    log("Logging in as admin...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        log(f"❌ Admin login failed: {resp.status_code} - {resp.text}")
        sys.exit(1)
    
    data = resp.json()
    token = data.get("token")
    if not token:
        log(f"❌ No token in login response")
        sys.exit(1)
    
    log(f"✅ Admin login successful")
    return token

def create_test_user(role: str = "customer", verify: bool = True) -> tuple[str, str, str]:
    """Create a test user and return (user_id, email, password)."""
    import uuid
    import time
    email = f"test-{role}-{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass123"
    
    log(f"Creating {role} account: {email}")
    resp = requests.post(f"{BASE_URL}/auth/signup", json={
        "email": email,
        "password": password,
        "name": f"Test {role.title()}",
        "phone": "+211912345678",
        "role": role
    })
    
    if resp.status_code != 200:
        log(f"❌ Signup failed: {resp.status_code} - {resp.text}")
        return None, None, None
    
    # Get user_id from MongoDB
    import os
    from pymongo import MongoClient
    from dotenv import load_dotenv
    
    # Load environment variables from backend .env
    load_dotenv("/app/backend/.env")
    
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "jubasquare_db")
    
    try:
        # Wait a moment for the database write to complete
        time.sleep(0.5)
        
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        user = db.users.find_one({"email": email})
        if not user:
            log(f"❌ User not found in database")
            return None, None, None
        
        user_id = user.get("id")
        
        if verify:
            # Get verification token and verify
            verification = db.email_verifications.find_one({"email": email})
            if verification:
                token = verification.get("token")
                verify_resp = requests.post(f"{BASE_URL}/auth/verify-email", json={"token": token})
                if verify_resp.status_code == 200:
                    log(f"✅ Email verified for {email}")
                else:
                    log(f"⚠️ Email verification failed: {verify_resp.status_code}")
        
        client.close()
        created_users.append(user_id)
        log(f"✅ Created {role}: {email} (id: {user_id})")
        return user_id, email, password
        
    except Exception as e:
        log(f"❌ Error creating user: {e}")
        return None, None, None

def cleanup_users(admin_token: str):
    """Delete all test users created during testing."""
    if not created_users:
        return
    
    test_header("CLEANUP: Deleting test users")
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    for user_id in created_users:
        resp = requests.delete(f"{BASE_URL}/admin/users/{user_id}", headers=headers)
        if resp.status_code == 200:
            log(f"✅ Deleted user {user_id}")
        else:
            log(f"⚠️ Failed to delete user {user_id}: {resp.status_code}")

def test_1_list_users(admin_token: str):
    """Test 1: GET /api/admin/users - List users with filters"""
    test_header("TEST 1: GET /api/admin/users (list with filters)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Test 1.1: Without auth -> 401
    log("\n--- Test 1.1: Without auth (expect 401) ---")
    resp = requests.get(f"{BASE_URL}/admin/users")
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # Test 1.2: As customer -> 403
    log("\n--- Test 1.2: As customer (expect 403) ---")
    customer_id, customer_email, customer_pass = create_test_user("customer", verify=True)
    if customer_id:
        # Login as customer
        login_resp = requests.post(f"{BASE_URL}/auth/login", json={
            "email": customer_email,
            "password": customer_pass
        })
        if login_resp.status_code == 200:
            customer_token = login_resp.json().get("token")
            customer_headers = {"Authorization": f"Bearer {customer_token}"}
            resp = requests.get(f"{BASE_URL}/admin/users", headers=customer_headers)
            if resp.status_code != 403:
                log(f"❌ FAIL: Expected 403, got {resp.status_code}")
                return False
            log(f"✅ As customer returns 403")
        else:
            log(f"⚠️ Customer login failed, skipping 403 test")
    
    # Test 1.3: As admin with no filters -> 200
    log("\n--- Test 1.3: As admin with no filters (expect 200) ---")
    resp = requests.get(f"{BASE_URL}/admin/users", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    users = resp.json()
    if not isinstance(users, list):
        log(f"❌ FAIL: Response is not a list")
        return False
    
    log(f"✅ Returns list with {len(users)} users")
    
    # Verify response structure
    if len(users) > 0:
        user = users[0]
        required_fields = ["id", "name", "email", "role", "is_active", "email_verified", "created_at"]
        for field in required_fields:
            if field not in user:
                log(f"❌ FAIL: Missing field '{field}' in user response")
                return False
        log(f"✅ User response includes all required fields: {required_fields}")
        
        # Check for stats fields
        if user.get("role") == "customer" and "total_orders" not in user:
            log(f"❌ FAIL: Customer missing 'total_orders' field")
            return False
        if user.get("role") == "seller" and "total_sales" not in user:
            log(f"❌ FAIL: Seller missing 'total_sales' field")
            return False
        log(f"✅ Stats fields present for user roles")
    
    # Test 1.4: Filter by role=customer
    log("\n--- Test 1.4: Filter by role=customer ---")
    resp = requests.get(f"{BASE_URL}/admin/users?role=customer", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    users = resp.json()
    for user in users:
        if user.get("role") != "customer":
            log(f"❌ FAIL: Non-customer user in filtered results: {user.get('role')}")
            return False
    log(f"✅ Role filter works: {len(users)} customers")
    
    # Test 1.5: Filter by is_active=false
    log("\n--- Test 1.5: Filter by is_active=false ---")
    resp = requests.get(f"{BASE_URL}/admin/users?is_active=false", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    users = resp.json()
    log(f"✅ is_active filter works: {len(users)} inactive users")
    
    # Test 1.6: Filter by email_verified=true
    log("\n--- Test 1.6: Filter by email_verified=true ---")
    resp = requests.get(f"{BASE_URL}/admin/users?email_verified=true", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    users = resp.json()
    for user in users:
        if not user.get("email_verified"):
            log(f"❌ FAIL: Unverified user in filtered results")
            return False
    log(f"✅ email_verified filter works: {len(users)} verified users")
    
    # Test 1.7: Search by name/email
    log("\n--- Test 1.7: Search by 'admin' ---")
    resp = requests.get(f"{BASE_URL}/admin/users?search=admin", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    users = resp.json()
    log(f"✅ Search works: {len(users)} users matching 'admin'")
    
    log(f"\n✅ TEST 1 PASSED")
    return True

def test_2_get_user(admin_token: str):
    """Test 2: GET /api/admin/users/{user_id} - Get single user"""
    test_header("TEST 2: GET /api/admin/users/{user_id} (get single user)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Create a test user
    user_id, email, password = create_test_user("customer", verify=True)
    if not user_id:
        log(f"❌ FAIL: Could not create test user")
        return False
    
    # Test 2.1: Without auth -> 401
    log("\n--- Test 2.1: Without auth (expect 401) ---")
    resp = requests.get(f"{BASE_URL}/admin/users/{user_id}")
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # Test 2.2: As admin for existing user -> 200
    log("\n--- Test 2.2: As admin for existing user (expect 200) ---")
    resp = requests.get(f"{BASE_URL}/admin/users/{user_id}", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    user = resp.json()
    required_fields = ["id", "name", "email", "role", "is_active", "email_verified", "created_at", "total_orders"]
    for field in required_fields:
        if field not in user:
            log(f"❌ FAIL: Missing field '{field}' in response")
            return False
    
    log(f"✅ Returns user with full details and stats")
    
    # Test 2.3: Non-existent user -> 404
    log("\n--- Test 2.3: Non-existent user (expect 404) ---")
    resp = requests.get(f"{BASE_URL}/admin/users/nonexistent-id-12345", headers=headers)
    if resp.status_code != 404:
        log(f"❌ FAIL: Expected 404, got {resp.status_code}")
        return False
    log(f"✅ Non-existent user returns 404")
    
    log(f"\n✅ TEST 2 PASSED")
    return True

def test_3_update_user(admin_token: str):
    """Test 3: PUT /api/admin/users/{user_id} - Update user"""
    test_header("TEST 3: PUT /api/admin/users/{user_id} (update user)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Create test users
    user1_id, user1_email, _ = create_test_user("customer", verify=True)
    user2_id, user2_email, _ = create_test_user("customer", verify=True)
    
    if not user1_id or not user2_id:
        log(f"❌ FAIL: Could not create test users")
        return False
    
    # Test 3.1: Without auth -> 401
    log("\n--- Test 3.1: Without auth (expect 401) ---")
    resp = requests.put(f"{BASE_URL}/admin/users/{user1_id}", json={"name": "Updated"})
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # Test 3.2: Update name, email, phone
    log("\n--- Test 3.2: Update name, email, phone ---")
    new_email = f"updated-{user1_email}"
    resp = requests.put(f"{BASE_URL}/admin/users/{user1_id}", json={
        "name": "Updated Name",
        "email": new_email,
        "phone": "+211987654321"
    }, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code} - {resp.text}")
        return False
    
    user = resp.json()
    if user.get("name") != "Updated Name":
        log(f"❌ FAIL: Name not updated")
        return False
    if user.get("email") != new_email.lower():
        log(f"❌ FAIL: Email not updated")
        return False
    if user.get("phone") != "+211987654321":
        log(f"❌ FAIL: Phone not updated")
        return False
    
    log(f"✅ Name, email, phone updated successfully")
    
    # Test 3.3: Update role
    log("\n--- Test 3.3: Update role ---")
    resp = requests.put(f"{BASE_URL}/admin/users/{user1_id}", json={
        "role": "seller"
    }, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    user = resp.json()
    if user.get("role") != "seller":
        log(f"❌ FAIL: Role not updated")
        return False
    
    log(f"✅ Role updated successfully")
    
    # Test 3.4: Email uniqueness (duplicate email should return 400)
    log("\n--- Test 3.4: Duplicate email (expect 400) ---")
    resp = requests.put(f"{BASE_URL}/admin/users/{user1_id}", json={
        "email": user2_email
    }, headers=headers)
    
    if resp.status_code != 400:
        log(f"❌ FAIL: Expected 400, got {resp.status_code}")
        return False
    
    log(f"✅ Duplicate email returns 400")
    
    # Test 3.5: Admin changing own role (should return 400)
    log("\n--- Test 3.5: Admin changing own role (expect 400) ---")
    # Get admin user_id
    resp = requests.get(f"{BASE_URL}/admin/users?search={ADMIN_EMAIL}", headers=headers)
    admin_users = resp.json()
    admin_user_id = None
    for u in admin_users:
        if u.get("email") == ADMIN_EMAIL:
            admin_user_id = u.get("id")
            break
    
    if admin_user_id:
        resp = requests.put(f"{BASE_URL}/admin/users/{admin_user_id}", json={
            "role": "customer"
        }, headers=headers)
        
        if resp.status_code != 400:
            log(f"❌ FAIL: Expected 400, got {resp.status_code}")
            return False
        
        log(f"✅ Admin changing own role returns 400")
    else:
        log(f"⚠️ Could not find admin user, skipping self-role-change test")
    
    log(f"\n✅ TEST 3 PASSED")
    return True

def test_4_reset_password(admin_token: str):
    """Test 4: POST /api/admin/users/{user_id}/reset-password - Direct password reset"""
    test_header("TEST 4: POST /api/admin/users/{user_id}/reset-password (direct reset)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Create test user
    user_id, email, old_password = create_test_user("customer", verify=True)
    if not user_id:
        log(f"❌ FAIL: Could not create test user")
        return False
    
    # Test 4.1: Without auth -> 401
    log("\n--- Test 4.1: Without auth (expect 401) ---")
    resp = requests.post(f"{BASE_URL}/admin/users/{user_id}/reset-password", json={
        "new_password": "newpass123"
    })
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # Test 4.2: Valid password reset (min 6 chars)
    log("\n--- Test 4.2: Valid password reset ---")
    new_password = "newpass123"
    resp = requests.post(f"{BASE_URL}/admin/users/{user_id}/reset-password", json={
        "new_password": new_password
    }, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code} - {resp.text}")
        return False
    
    result = resp.json()
    if not result.get("ok"):
        log(f"❌ FAIL: Response ok is not true")
        return False
    
    log(f"✅ Password reset successful")
    
    # Test 4.3: Verify password is updated and must_change_password = false
    log("\n--- Test 4.3: Verify new password works and must_change_password=false ---")
    # Try login with new password
    login_resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": new_password
    })
    
    if login_resp.status_code != 200:
        log(f"❌ FAIL: Login with new password failed: {login_resp.status_code}")
        return False
    
    log(f"✅ New password works")
    
    # Check must_change_password field
    resp = requests.get(f"{BASE_URL}/admin/users/{user_id}", headers=headers)
    user = resp.json()
    if user.get("must_change_password") != False:
        log(f"❌ FAIL: must_change_password should be false, got {user.get('must_change_password')}")
        return False
    
    log(f"✅ must_change_password is false")
    
    log(f"\n✅ TEST 4 PASSED")
    return True

def test_5_send_reset_email(admin_token: str):
    """Test 5: POST /api/admin/users/{user_id}/send-reset-email - Send email reset"""
    test_header("TEST 5: POST /api/admin/users/{user_id}/send-reset-email (send email)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Create test user
    user_id, email, password = create_test_user("customer", verify=True)
    if not user_id:
        log(f"❌ FAIL: Could not create test user")
        return False
    
    # Test 5.1: Without auth -> 401
    log("\n--- Test 5.1: Without auth (expect 401) ---")
    resp = requests.post(f"{BASE_URL}/admin/users/{user_id}/send-reset-email")
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # Test 5.2: As admin -> 200
    log("\n--- Test 5.2: As admin (expect 200) ---")
    resp = requests.post(f"{BASE_URL}/admin/users/{user_id}/send-reset-email", headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code} - {resp.text}")
        return False
    
    result = resp.json()
    if not result.get("ok"):
        log(f"❌ FAIL: Response ok is not true")
        return False
    
    log(f"✅ Send reset email returns 200 with success message")
    
    # Test 5.3: Verify token created in password_resets collection
    log("\n--- Test 5.3: Verify token in password_resets collection ---")
    import os
    from pymongo import MongoClient
    from dotenv import load_dotenv
    
    # Load environment variables from backend .env
    load_dotenv("/app/backend/.env")
    
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "jubasquare_db")
    
    try:
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        reset = db.password_resets.find_one({"user_id": user_id})
        if not reset:
            log(f"❌ FAIL: No password reset token found in database")
            return False
        
        if not reset.get("token"):
            log(f"❌ FAIL: Token is empty")
            return False
        
        log(f"✅ Token created in password_resets collection")
        
        client.close()
    except Exception as e:
        log(f"❌ FAIL: Error checking database: {e}")
        return False
    
    log(f"\n✅ TEST 5 PASSED")
    return True

def test_6_generate_temp_password(admin_token: str):
    """Test 6: POST /api/admin/users/{user_id}/generate-temp-password - Generate temp"""
    test_header("TEST 6: POST /api/admin/users/{user_id}/generate-temp-password (generate temp)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Create test user
    user_id, email, old_password = create_test_user("customer", verify=True)
    if not user_id:
        log(f"❌ FAIL: Could not create test user")
        return False
    
    # Test 6.1: Without auth -> 401
    log("\n--- Test 6.1: Without auth (expect 401) ---")
    resp = requests.post(f"{BASE_URL}/admin/users/{user_id}/generate-temp-password")
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # Test 6.2: As admin -> 200 with temp_password
    log("\n--- Test 6.2: As admin (expect 200 with temp_password) ---")
    resp = requests.post(f"{BASE_URL}/admin/users/{user_id}/generate-temp-password", headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code} - {resp.text}")
        return False
    
    result = resp.json()
    if not result.get("ok"):
        log(f"❌ FAIL: Response ok is not true")
        return False
    
    temp_password = result.get("temp_password")
    if not temp_password:
        log(f"❌ FAIL: No temp_password in response")
        return False
    
    log(f"✅ Returns temp_password: {temp_password}")
    
    # Test 6.3: Verify temp password is 12 characters
    log("\n--- Test 6.3: Verify temp password is 12 characters ---")
    if len(temp_password) != 12:
        log(f"❌ FAIL: Temp password should be 12 chars, got {len(temp_password)}")
        return False
    
    log(f"✅ Temp password is 12 characters")
    
    # Test 6.4: Verify must_change_password = true
    log("\n--- Test 6.4: Verify must_change_password=true ---")
    resp = requests.get(f"{BASE_URL}/admin/users/{user_id}", headers=headers)
    user = resp.json()
    if user.get("must_change_password") != True:
        log(f"❌ FAIL: must_change_password should be true, got {user.get('must_change_password')}")
        return False
    
    log(f"✅ must_change_password is true")
    
    log(f"\n✅ TEST 6 PASSED")
    return True

def test_7_update_status(admin_token: str):
    """Test 7: PUT /api/admin/users/{user_id}/status - Enable/Disable"""
    test_header("TEST 7: PUT /api/admin/users/{user_id}/status (enable/disable)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Create test user
    user_id, email, password = create_test_user("customer", verify=True)
    if not user_id:
        log(f"❌ FAIL: Could not create test user")
        return False
    
    # Test 7.1: Without auth -> 401
    log("\n--- Test 7.1: Without auth (expect 401) ---")
    resp = requests.put(f"{BASE_URL}/admin/users/{user_id}/status", json={"is_active": False})
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # Test 7.2: Disable user (is_active = false)
    log("\n--- Test 7.2: Disable user ---")
    resp = requests.put(f"{BASE_URL}/admin/users/{user_id}/status", json={
        "is_active": False
    }, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code} - {resp.text}")
        return False
    
    result = resp.json()
    if not result.get("ok"):
        log(f"❌ FAIL: Response ok is not true")
        return False
    
    log(f"✅ User disabled successfully")
    
    # Verify is_active is false
    resp = requests.get(f"{BASE_URL}/admin/users/{user_id}", headers=headers)
    user = resp.json()
    if user.get("is_active") != False:
        log(f"❌ FAIL: is_active should be false")
        return False
    
    log(f"✅ Verified is_active=false")
    
    # Test 7.3: Enable user (is_active = true)
    log("\n--- Test 7.3: Enable user ---")
    resp = requests.put(f"{BASE_URL}/admin/users/{user_id}/status", json={
        "is_active": True
    }, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    log(f"✅ User enabled successfully")
    
    # Test 7.4: Admin disabling own account (should return 400)
    log("\n--- Test 7.4: Admin disabling own account (expect 400) ---")
    # Get admin user_id
    resp = requests.get(f"{BASE_URL}/admin/users?search={ADMIN_EMAIL}", headers=headers)
    admin_users = resp.json()
    admin_user_id = None
    for u in admin_users:
        if u.get("email") == ADMIN_EMAIL:
            admin_user_id = u.get("id")
            break
    
    if admin_user_id:
        resp = requests.put(f"{BASE_URL}/admin/users/{admin_user_id}/status", json={
            "is_active": False
        }, headers=headers)
        
        if resp.status_code != 400:
            log(f"❌ FAIL: Expected 400, got {resp.status_code}")
            return False
        
        log(f"✅ Admin disabling own account returns 400")
    else:
        log(f"⚠️ Could not find admin user, skipping self-disable test")
    
    log(f"\n✅ TEST 7 PASSED")
    return True

def test_8_delete_user(admin_token: str):
    """Test 8: DELETE /api/admin/users/{user_id} - Delete user"""
    test_header("TEST 8: DELETE /api/admin/users/{user_id} (delete with cascade)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Test 8.1: Without auth -> 401
    log("\n--- Test 8.1: Without auth (expect 401) ---")
    resp = requests.delete(f"{BASE_URL}/admin/users/some-id")
    if resp.status_code != 401:
        log(f"❌ FAIL: Expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # Test 8.2: Delete customer user
    log("\n--- Test 8.2: Delete customer user ---")
    customer_id, customer_email, _ = create_test_user("customer", verify=True)
    if not customer_id:
        log(f"❌ FAIL: Could not create customer")
        return False
    
    resp = requests.delete(f"{BASE_URL}/admin/users/{customer_id}", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code} - {resp.text}")
        return False
    
    result = resp.json()
    if not result.get("ok"):
        log(f"❌ FAIL: Response ok is not true")
        return False
    
    log(f"✅ Customer deleted successfully")
    
    # Verify user is deleted
    resp = requests.get(f"{BASE_URL}/admin/users/{customer_id}", headers=headers)
    if resp.status_code != 404:
        log(f"❌ FAIL: Deleted user should return 404, got {resp.status_code}")
        return False
    
    log(f"✅ Verified user is deleted (404)")
    
    # Remove from cleanup list
    if customer_id in created_users:
        created_users.remove(customer_id)
    
    # Test 8.3: Delete seller user (verify cascade: shops, products deleted)
    log("\n--- Test 8.3: Delete seller user with cascade ---")
    seller_id, seller_email, seller_pass = create_test_user("seller", verify=True)
    if not seller_id:
        log(f"❌ FAIL: Could not create seller")
        return False
    
    # Login as seller and create a shop
    login_resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": seller_email,
        "password": seller_pass
    })
    
    if login_resp.status_code == 200:
        seller_token = login_resp.json().get("token")
        seller_headers = {"Authorization": f"Bearer {seller_token}"}
        
        # Create a shop
        shop_resp = requests.post(f"{BASE_URL}/shops", json={
            "name": "Test Shop for Deletion",
            "description": "Test shop",
            "category": "Electronics"
        }, headers=seller_headers)
        
        if shop_resp.status_code == 200:
            shop = shop_resp.json()
            shop_id = shop.get("id")
            log(f"✅ Created shop: {shop_id}")
            
            # Create a product
            product_resp = requests.post(f"{BASE_URL}/products", json={
                "name": "Test Product",
                "description": "Test",
                "price_usd": 10.0,
                "stock": 100,
                "category": "Electronics",
                "shop_id": shop_id
            }, headers=seller_headers)
            
            if product_resp.status_code == 200:
                product = product_resp.json()
                product_id = product.get("id")
                log(f"✅ Created product: {product_id}")
            else:
                log(f"⚠️ Could not create product: {product_resp.status_code}")
        else:
            log(f"⚠️ Could not create shop: {shop_resp.status_code}")
    else:
        log(f"⚠️ Seller login failed: {login_resp.status_code}")
    
    # Delete seller
    resp = requests.delete(f"{BASE_URL}/admin/users/{seller_id}", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code} - {resp.text}")
        return False
    
    log(f"✅ Seller deleted successfully")
    
    # Verify shops and products are deleted
    shops_resp = requests.get(f"{BASE_URL}/shops")
    shops = shops_resp.json()
    seller_shops = [s for s in shops if s.get("seller_id") == seller_id]
    if len(seller_shops) > 0:
        log(f"❌ FAIL: Seller shops should be deleted, found {len(seller_shops)}")
        return False
    
    log(f"✅ Verified seller shops are deleted")
    
    # Remove from cleanup list
    if seller_id in created_users:
        created_users.remove(seller_id)
    
    # Test 8.4: Admin deleting own account (should return 400)
    log("\n--- Test 8.4: Admin deleting own account (expect 400) ---")
    # Get admin user_id
    resp = requests.get(f"{BASE_URL}/admin/users?search={ADMIN_EMAIL}", headers=headers)
    admin_users = resp.json()
    admin_user_id = None
    for u in admin_users:
        if u.get("email") == ADMIN_EMAIL:
            admin_user_id = u.get("id")
            break
    
    if admin_user_id:
        resp = requests.delete(f"{BASE_URL}/admin/users/{admin_user_id}", headers=headers)
        
        if resp.status_code != 400:
            log(f"❌ FAIL: Expected 400, got {resp.status_code}")
            return False
        
        log(f"✅ Admin deleting own account returns 400")
    else:
        log(f"⚠️ Could not find admin user, skipping self-delete test")
    
    log(f"\n✅ TEST 8 PASSED")
    return True

def test_9_login_flow_updates(admin_token: str):
    """Test 9: Login flow updates - Verify new checks"""
    test_header("TEST 9: Login flow updates (disabled, must_change_password, last_login)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Test 9.1: Disabled user login (expect 403)
    log("\n--- Test 9.1: Disabled user login (expect 403) ---")
    user_id, email, password = create_test_user("customer", verify=True)
    if not user_id:
        log(f"❌ FAIL: Could not create test user")
        return False
    
    # Disable the user
    resp = requests.put(f"{BASE_URL}/admin/users/{user_id}/status", json={
        "is_active": False
    }, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Could not disable user")
        return False
    
    # Try to login
    login_resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": password
    })
    
    if login_resp.status_code != 403:
        log(f"❌ FAIL: Expected 403, got {login_resp.status_code}")
        return False
    
    error_detail = login_resp.json().get("detail", "")
    if "disabled" not in error_detail.lower():
        log(f"❌ FAIL: Error message should mention 'disabled', got: {error_detail}")
        return False
    
    log(f"✅ Disabled user login returns 403 with 'account disabled' message")
    
    # Test 9.2: Verify last_login timestamp is updated after successful login
    log("\n--- Test 9.2: Verify last_login timestamp updates ---")
    # Re-enable the user
    resp = requests.put(f"{BASE_URL}/admin/users/{user_id}/status", json={
        "is_active": True
    }, headers=headers)
    
    # Get user before login
    resp = requests.get(f"{BASE_URL}/admin/users/{user_id}", headers=headers)
    user_before = resp.json()
    last_login_before = user_before.get("last_login")
    
    # Wait a moment
    time.sleep(1)
    
    # Login
    login_resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": password
    })
    
    if login_resp.status_code != 200:
        log(f"❌ FAIL: Login failed: {login_resp.status_code}")
        return False
    
    # Get user after login
    resp = requests.get(f"{BASE_URL}/admin/users/{user_id}", headers=headers)
    user_after = resp.json()
    last_login_after = user_after.get("last_login")
    
    if last_login_after == last_login_before:
        log(f"❌ FAIL: last_login timestamp should be updated")
        return False
    
    log(f"✅ last_login timestamp updated after successful login")
    
    # Test 9.3: User with must_change_password=true cannot login (expect 403)
    log("\n--- Test 9.3: User with must_change_password=true (expect 403) ---")
    user2_id, email2, password2 = create_test_user("customer", verify=True)
    if not user2_id:
        log(f"❌ FAIL: Could not create test user")
        return False
    
    # Generate temp password (sets must_change_password=true)
    resp = requests.post(f"{BASE_URL}/admin/users/{user2_id}/generate-temp-password", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Could not generate temp password")
        return False
    
    temp_password = resp.json().get("temp_password")
    
    # Try to login with temp password
    login_resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email2,
        "password": temp_password
    })
    
    if login_resp.status_code != 403:
        log(f"❌ FAIL: Expected 403, got {login_resp.status_code}")
        return False
    
    error_detail = login_resp.json().get("detail", "")
    if "change your password" not in error_detail.lower():
        log(f"❌ FAIL: Error message should mention 'change your password', got: {error_detail}")
        return False
    
    log(f"✅ User with must_change_password=true cannot login (403)")
    
    log(f"\n✅ TEST 9 PASSED")
    return True

def main():
    print("\n" + "="*80)
    print("  ADMIN USER MANAGEMENT BACKEND TESTING")
    print("="*80)
    
    # Login as admin
    admin_token = admin_login()
    
    results = []
    
    # Run all tests
    results.append(("Test 1: GET /api/admin/users (list with filters)", test_1_list_users(admin_token)))
    results.append(("Test 2: GET /api/admin/users/{user_id}", test_2_get_user(admin_token)))
    results.append(("Test 3: PUT /api/admin/users/{user_id}", test_3_update_user(admin_token)))
    results.append(("Test 4: POST /api/admin/users/{user_id}/reset-password", test_4_reset_password(admin_token)))
    results.append(("Test 5: POST /api/admin/users/{user_id}/send-reset-email", test_5_send_reset_email(admin_token)))
    results.append(("Test 6: POST /api/admin/users/{user_id}/generate-temp-password", test_6_generate_temp_password(admin_token)))
    results.append(("Test 7: PUT /api/admin/users/{user_id}/status", test_7_update_status(admin_token)))
    results.append(("Test 8: DELETE /api/admin/users/{user_id}", test_8_delete_user(admin_token)))
    results.append(("Test 9: Login flow updates", test_9_login_flow_updates(admin_token)))
    
    # Cleanup
    cleanup_users(admin_token)
    
    # Summary
    test_header("TEST SUMMARY")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        log(f"{status}: {name}")
    
    print(f"\n{'='*80}")
    print(f"  TOTAL: {passed}/{total} tests passed")
    print(f"{'='*80}\n")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print(f"❌ {total - passed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
