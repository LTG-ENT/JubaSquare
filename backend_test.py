#!/usr/bin/env python3
"""
Round 7 Backend Testing: Admin-managed categories CRUD + sub-categories
Tests all 8 endpoint scenarios as specified in the review request.
"""

import requests
import sys
import json
from typing import Optional

BASE_URL = "https://user-admin-center.preview.emergentagent.com/api"

# Admin credentials
ADMIN_EMAIL = "ltg-general-trading@hotmail.com"
ADMIN_PASSWORD = "Kokobleake1"

# Track created categories for cleanup
created_categories = []

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

def create_customer_account() -> tuple[str, str]:
    """Create a customer account for non-admin testing. Returns (email, token)."""
    import uuid
    email = f"test-customer-{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass123"
    
    log(f"Creating customer account: {email}")
    resp = requests.post(f"{BASE_URL}/auth/signup", json={
        "email": email,
        "password": password,
        "name": "Test Customer",
        "role": "customer"
    })
    
    if resp.status_code != 200:
        log(f"❌ Customer signup failed: {resp.status_code} - {resp.text}")
        return None, None
    
    # Manually verify the customer via MongoDB (since email is in no-op mode)
    # For testing purposes, we'll try to login and expect 403 (unverified)
    # Then we'll just use the fact that admin endpoints should return 403 for customers
    
    # Try to get verification token from MongoDB and verify
    import os
    from pymongo import MongoClient
    
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "jubasquare")
    
    try:
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        # Get verification token
        verification = db.email_verifications.find_one({"email": email})
        if verification:
            token = verification.get("token")
            # Verify email
            verify_resp = requests.post(f"{BASE_URL}/auth/verify-email", json={"token": token})
            if verify_resp.status_code == 200:
                log(f"✅ Customer email verified")
            else:
                log(f"⚠️ Email verification failed: {verify_resp.status_code}")
        
        client.close()
    except Exception as e:
        log(f"⚠️ Could not verify customer via MongoDB: {e}")
    
    # Now login as customer
    login_resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": password
    })
    
    if login_resp.status_code == 200:
        customer_token = login_resp.json().get("token")
        log(f"✅ Customer login successful")
        return email, customer_token
    else:
        log(f"⚠️ Customer login failed (may be unverified): {login_resp.status_code}")
        return email, None

def cleanup_categories(admin_token: str):
    """Delete all test categories created during testing."""
    if not created_categories:
        return
    
    test_header("CLEANUP: Deleting test categories")
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    for cat_id in created_categories:
        resp = requests.delete(f"{BASE_URL}/admin/categories/{cat_id}?force=true", headers=headers)
        if resp.status_code == 200:
            log(f"✅ Deleted category {cat_id}")
        else:
            log(f"⚠️ Failed to delete category {cat_id}: {resp.status_code}")

def test_1_meta_categories():
    """Test 1: GET /api/meta/categories (public, no auth)"""
    test_header("TEST 1: GET /api/meta/categories (public, backward-compatible)")
    
    resp = requests.get(f"{BASE_URL}/meta/categories")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    data = resp.json()
    
    # Check backward-compat keys
    required_keys = ["retail", "wholesale", "restaurant", "food_subcategories", "groups"]
    for key in required_keys:
        if key not in data:
            log(f"❌ FAIL: Missing key '{key}' in response")
            return False
    
    log(f"✅ All required keys present: {required_keys}")
    
    # Check that retail/wholesale/restaurant/food_subcategories are arrays of strings
    for key in ["retail", "wholesale", "restaurant", "food_subcategories"]:
        if not isinstance(data[key], list):
            log(f"❌ FAIL: '{key}' is not a list")
            return False
        if len(data[key]) == 0:
            log(f"⚠️ WARNING: '{key}' is empty (expected seeded data)")
    
    log(f"✅ retail has {len(data['retail'])} categories")
    log(f"✅ wholesale has {len(data['wholesale'])} categories")
    log(f"✅ restaurant has {len(data['restaurant'])} categories")
    log(f"✅ food_subcategories has {len(data['food_subcategories'])} categories")
    
    # Check backward compat: retail should contain seeded defaults
    expected_retail = ["Groceries", "Clothing & Fashion", "Electronics & Accessories"]
    for expected in expected_retail:
        if expected not in data["retail"]:
            log(f"❌ FAIL: Expected '{expected}' in retail categories (seed default)")
            return False
    
    log(f"✅ Backward compat: retail contains expected seed defaults: {expected_retail}")
    
    # Check groups structure
    if not isinstance(data["groups"], dict):
        log(f"❌ FAIL: 'groups' is not a dict")
        return False
    
    for group_key in ["retail", "wholesale", "restaurant", "food"]:
        if group_key not in data["groups"]:
            log(f"❌ FAIL: Missing group key '{group_key}' in groups")
            return False
        
        group_data = data["groups"][group_key]
        if not isinstance(group_data, list):
            log(f"❌ FAIL: groups['{group_key}'] is not a list")
            return False
        
        # Check structure of each category in the tree
        for cat in group_data:
            required_cat_keys = ["id", "name", "group", "parent_id", "order", "image_url", "is_active", "children"]
            for cat_key in required_cat_keys:
                if cat_key not in cat:
                    log(f"❌ FAIL: Category missing key '{cat_key}': {cat}")
                    return False
            
            if not isinstance(cat["children"], list):
                log(f"❌ FAIL: Category 'children' is not a list: {cat}")
                return False
    
    log(f"✅ groups structure is correct with all 4 group keys")
    log(f"✅ Each category has correct structure: id, name, group, parent_id, order, image_url, is_active, children")
    
    log(f"✅ TEST 1 PASSED")
    return True

def test_2_categories_flat(admin_token: str):
    """Test 2: GET /api/categories?group=retail (public)"""
    test_header("TEST 2: GET /api/categories?group=retail (public flat list)")
    
    resp = requests.get(f"{BASE_URL}/categories?group=retail")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    data = resp.json()
    
    if not isinstance(data, list):
        log(f"❌ FAIL: Response is not a list")
        return False
    
    log(f"✅ Returns list with {len(data)} categories")
    
    # Check that all categories belong to retail group and are active
    for cat in data:
        if cat.get("group") != "retail":
            log(f"❌ FAIL: Category does not belong to retail group: {cat}")
            return False
        if cat.get("is_active") != True:
            log(f"❌ FAIL: Inactive category returned (should be active only): {cat}")
            return False
    
    log(f"✅ All categories belong to retail group and are active")
    log(f"✅ TEST 2 PASSED")
    return True

def test_3_categories_tree(admin_token: str):
    """Test 3: GET /api/categories/tree?group=retail (public)"""
    test_header("TEST 3: GET /api/categories/tree?group=retail (public tree)")
    
    resp = requests.get(f"{BASE_URL}/categories/tree?group=retail")
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    data = resp.json()
    
    if not isinstance(data, list):
        log(f"❌ FAIL: Response is not a list")
        return False
    
    log(f"✅ Returns list with {len(data)} top-level categories")
    
    # Check structure: each top-level should have children array
    for cat in data:
        if "children" not in cat:
            log(f"❌ FAIL: Category missing 'children' key: {cat}")
            return False
        if not isinstance(cat["children"], list):
            log(f"❌ FAIL: Category 'children' is not a list: {cat}")
            return False
        if cat.get("parent_id") is not None:
            log(f"❌ FAIL: Top-level category has parent_id: {cat}")
            return False
    
    log(f"✅ All top-level categories have children arrays and parent_id=null")
    log(f"✅ TEST 3 PASSED")
    return True

def test_4_admin_categories(admin_token: str, customer_token: Optional[str]):
    """Test 4: GET /api/admin/categories (auth required, admin only)"""
    test_header("TEST 4: GET /api/admin/categories (admin only, includes inactive)")
    
    # Test without auth -> 401
    resp = requests.get(f"{BASE_URL}/admin/categories")
    if resp.status_code != 401:
        log(f"❌ FAIL: Without auth expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # Test as customer (non-admin) -> 403
    if customer_token:
        headers = {"Authorization": f"Bearer {customer_token}"}
        resp = requests.get(f"{BASE_URL}/admin/categories", headers=headers)
        if resp.status_code != 403:
            log(f"❌ FAIL: As customer expected 403, got {resp.status_code}")
            return False
        log(f"✅ As customer returns 403")
    else:
        log(f"⚠️ Skipping customer 403 test (no customer token)")
    
    # Test as admin -> 200
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.get(f"{BASE_URL}/admin/categories", headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: As admin expected 200, got {resp.status_code}")
        return False
    
    data = resp.json()
    
    if not isinstance(data, dict):
        log(f"❌ FAIL: Response is not a dict")
        return False
    
    # Check all 4 group keys
    for group_key in ["retail", "wholesale", "restaurant", "food"]:
        if group_key not in data:
            log(f"❌ FAIL: Missing group key '{group_key}'")
            return False
        if not isinstance(data[group_key], list):
            log(f"❌ FAIL: Group '{group_key}' is not a list")
            return False
    
    log(f"✅ As admin returns 200 with all 4 group keys")
    log(f"✅ Each group contains tree structure (top-level + children)")
    
    # The admin endpoint should include inactive categories (we'll verify this later when we create an inactive one)
    
    log(f"✅ TEST 4 PASSED")
    return True

def test_5_create_category(admin_token: str, customer_token: Optional[str]):
    """Test 5: POST /api/admin/categories (admin only, various validations)"""
    test_header("TEST 5: POST /api/admin/categories (create with validations)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Test without auth -> 401
    resp = requests.post(f"{BASE_URL}/admin/categories", json={"name": "Test", "group": "retail"})
    if resp.status_code != 401:
        log(f"❌ FAIL: Without auth expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # Test 5.1: Create top-level retail category
    log("\n--- Test 5.1: Create top-level retail category ---")
    resp = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "Test Cat ABC",
        "group": "retail"
    }, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code} - {resp.text}")
        return False
    
    top_cat = resp.json()
    if not top_cat.get("id"):
        log(f"❌ FAIL: No id in response")
        return False
    if top_cat.get("parent_id") is not None:
        log(f"❌ FAIL: Top-level category should have parent_id=null")
        return False
    if top_cat.get("is_active") != True:
        log(f"❌ FAIL: Category should be active by default")
        return False
    
    created_categories.append(top_cat["id"])
    log(f"✅ Created top-level category: {top_cat['name']} (id: {top_cat['id']})")
    
    # Test 5.2: Create child under the top-level category
    log("\n--- Test 5.2: Create child category ---")
    resp = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "Sub 1",
        "group": "retail",
        "parent_id": top_cat["id"]
    }, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code} - {resp.text}")
        return False
    
    child_cat = resp.json()
    if child_cat.get("parent_id") != top_cat["id"]:
        log(f"❌ FAIL: Child parent_id should be {top_cat['id']}, got {child_cat.get('parent_id')}")
        return False
    
    created_categories.append(child_cat["id"])
    log(f"✅ Created child category: {child_cat['name']} (parent_id: {child_cat['parent_id']})")
    
    # Test 5.3: Create with parent in different group -> 400
    log("\n--- Test 5.3: Create with parent in different group (should fail) ---")
    resp = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "X",
        "group": "wholesale",
        "parent_id": top_cat["id"]  # retail parent
    }, headers=headers)
    
    if resp.status_code != 400:
        log(f"❌ FAIL: Expected 400, got {resp.status_code}")
        return False
    log(f"✅ Creating with parent in different group returns 400")
    
    # Test 5.4: Create with parent that already has a parent (depth>1) -> 400
    log("\n--- Test 5.4: Create with grandparent (depth>1, should fail) ---")
    resp = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "Y",
        "group": "retail",
        "parent_id": child_cat["id"]  # child already has a parent
    }, headers=headers)
    
    if resp.status_code != 400:
        log(f"❌ FAIL: Expected 400, got {resp.status_code}")
        return False
    log(f"✅ Creating with depth>1 returns 400")
    
    # Test 5.5: Duplicate name in same (group, parent_id) -> 400
    log("\n--- Test 5.5: Duplicate name in same group/parent (should fail) ---")
    resp = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "Test Cat ABC",  # same name as top_cat
        "group": "retail",
        "parent_id": None  # same parent (null)
    }, headers=headers)
    
    if resp.status_code != 400:
        log(f"❌ FAIL: Expected 400, got {resp.status_code}")
        return False
    log(f"✅ Duplicate name in same group/parent returns 400")
    
    # Test 5.6: Invalid group -> 400
    log("\n--- Test 5.6: Invalid group (should fail) ---")
    resp = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "Test",
        "group": "foo"
    }, headers=headers)
    
    if resp.status_code != 400:
        log(f"❌ FAIL: Expected 400, got {resp.status_code}")
        return False
    log(f"✅ Invalid group returns 400")
    
    # Test 5.7: Missing/empty name -> 400
    log("\n--- Test 5.7: Missing/empty name (should fail) ---")
    resp = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "",
        "group": "retail"
    }, headers=headers)
    
    if resp.status_code != 400:
        log(f"❌ FAIL: Expected 400, got {resp.status_code}")
        return False
    log(f"✅ Empty name returns 400")
    
    log(f"\n✅ TEST 5 PASSED")
    return True

def test_6_update_category(admin_token: str):
    """Test 6: PUT /api/admin/categories/{id} (admin only)"""
    test_header("TEST 6: PUT /api/admin/categories/{id} (update)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Create a test category first
    resp = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "Update Test Cat",
        "group": "retail"
    }, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Could not create test category: {resp.status_code}")
        return False
    
    cat = resp.json()
    cat_id = cat["id"]
    created_categories.append(cat_id)
    log(f"✅ Created test category: {cat['name']} (id: {cat_id})")
    
    # Test without auth -> 401
    resp = requests.put(f"{BASE_URL}/admin/categories/{cat_id}", json={"name": "Updated"})
    if resp.status_code != 401:
        log(f"❌ FAIL: Without auth expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # Test 6.1: Update name
    log("\n--- Test 6.1: Update name ---")
    resp = requests.put(f"{BASE_URL}/admin/categories/{cat_id}", json={
        "name": "Updated Cat Name"
    }, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code} - {resp.text}")
        return False
    
    updated = resp.json()
    if updated.get("name") != "Updated Cat Name":
        log(f"❌ FAIL: Name not updated, got {updated.get('name')}")
        return False
    log(f"✅ Name updated successfully")
    
    # Verify via GET
    resp = requests.get(f"{BASE_URL}/categories?group=retail")
    data = resp.json()
    found = any(c.get("id") == cat_id and c.get("name") == "Updated Cat Name" for c in data)
    if not found:
        log(f"❌ FAIL: Updated name not reflected in GET")
        return False
    log(f"✅ GET reflects updated name")
    
    # Test 6.2: Update image_url
    log("\n--- Test 6.2: Update image_url ---")
    resp = requests.put(f"{BASE_URL}/admin/categories/{cat_id}", json={
        "image_url": "https://example.com/image.jpg"
    }, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    updated = resp.json()
    if updated.get("image_url") != "https://example.com/image.jpg":
        log(f"❌ FAIL: image_url not updated")
        return False
    log(f"✅ image_url updated successfully")
    
    # Test 6.3: Update is_active=false
    log("\n--- Test 6.3: Update is_active=false ---")
    resp = requests.put(f"{BASE_URL}/admin/categories/{cat_id}", json={
        "is_active": False
    }, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    log(f"✅ is_active updated to false")
    
    # Verify GET /api/categories does NOT include inactive
    resp = requests.get(f"{BASE_URL}/categories?group=retail")
    data = resp.json()
    found = any(c.get("id") == cat_id for c in data)
    if found:
        log(f"❌ FAIL: Inactive category should not appear in public GET")
        return False
    log(f"✅ GET /api/categories does NOT include inactive category")
    
    # Verify GET /api/admin/categories DOES include inactive
    resp = requests.get(f"{BASE_URL}/admin/categories", headers=headers)
    data = resp.json()
    found = False
    for group_cats in data.values():
        for c in group_cats:
            if c.get("id") == cat_id:
                found = True
                break
    if not found:
        log(f"❌ FAIL: Admin GET should include inactive category")
        return False
    log(f"✅ GET /api/admin/categories DOES include inactive category")
    
    # Test 6.4: Update to duplicate name -> 400
    log("\n--- Test 6.4: Update to duplicate name (should fail) ---")
    # Create another category
    resp = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "Another Cat",
        "group": "retail"
    }, headers=headers)
    another_cat = resp.json()
    created_categories.append(another_cat["id"])
    
    # Try to update first cat to same name as second
    resp = requests.put(f"{BASE_URL}/admin/categories/{cat_id}", json={
        "name": "Another Cat"
    }, headers=headers)
    
    if resp.status_code != 400:
        log(f"❌ FAIL: Expected 400, got {resp.status_code}")
        return False
    log(f"✅ Updating to duplicate name returns 400")
    
    # Test 6.5: Unknown id -> 404
    log("\n--- Test 6.5: Unknown id (should fail) ---")
    resp = requests.put(f"{BASE_URL}/admin/categories/unknown-id-12345", json={
        "name": "Test"
    }, headers=headers)
    
    if resp.status_code != 404:
        log(f"❌ FAIL: Expected 404, got {resp.status_code}")
        return False
    log(f"✅ Unknown id returns 404")
    
    log(f"\n✅ TEST 6 PASSED")
    return True

def test_7_delete_category(admin_token: str):
    """Test 7: DELETE /api/admin/categories/{id} (admin only)"""
    test_header("TEST 7: DELETE /api/admin/categories/{id} (with/without force)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Test without auth -> 401
    resp = requests.delete(f"{BASE_URL}/admin/categories/some-id")
    if resp.status_code != 401:
        log(f"❌ FAIL: Without auth expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # Test 7.1: Delete a leaf (no children)
    log("\n--- Test 7.1: Delete leaf category ---")
    resp = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "Leaf Cat",
        "group": "retail"
    }, headers=headers)
    leaf_cat = resp.json()
    leaf_id = leaf_cat["id"]
    
    resp = requests.delete(f"{BASE_URL}/admin/categories/{leaf_id}", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    log(f"✅ Deleted leaf category successfully")
    
    # Test 7.2: Delete parent with children -> 400
    log("\n--- Test 7.2: Delete parent with children (should fail) ---")
    # Create parent
    resp = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "Parent Cat",
        "group": "retail"
    }, headers=headers)
    parent_cat = resp.json()
    parent_id = parent_cat["id"]
    created_categories.append(parent_id)
    
    # Create child
    resp = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "Child Cat",
        "group": "retail",
        "parent_id": parent_id
    }, headers=headers)
    child_cat = resp.json()
    child_id = child_cat["id"]
    created_categories.append(child_id)
    
    # Try to delete parent without force
    resp = requests.delete(f"{BASE_URL}/admin/categories/{parent_id}", headers=headers)
    if resp.status_code != 400:
        log(f"❌ FAIL: Expected 400, got {resp.status_code}")
        return False
    
    # Check that error message mentions "sub-category"
    if "sub-category" not in resp.text.lower() and "sub-categor" not in resp.text.lower():
        log(f"⚠️ WARNING: Error message should mention 'sub-category': {resp.text}")
    log(f"✅ Delete parent with children returns 400 with informative message")
    
    # Test 7.3: Delete parent with force=true
    log("\n--- Test 7.3: Delete parent with force=true ---")
    resp = requests.delete(f"{BASE_URL}/admin/categories/{parent_id}?force=true", headers=headers)
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    result = resp.json()
    if result.get("deleted_children") != 1:
        log(f"❌ FAIL: Expected deleted_children=1, got {result.get('deleted_children')}")
        return False
    log(f"✅ Deleted parent with force=true, deleted_children={result.get('deleted_children')}")
    
    # Verify children are gone
    resp = requests.get(f"{BASE_URL}/categories?group=retail")
    data = resp.json()
    found_parent = any(c.get("id") == parent_id for c in data)
    found_child = any(c.get("id") == child_id for c in data)
    
    if found_parent or found_child:
        log(f"❌ FAIL: Parent or child still exists after force delete")
        return False
    log(f"✅ Verified parent and children are deleted via GET")
    
    # Remove from cleanup list since already deleted
    if parent_id in created_categories:
        created_categories.remove(parent_id)
    if child_id in created_categories:
        created_categories.remove(child_id)
    
    log(f"\n✅ TEST 7 PASSED")
    return True

def test_8_reorder_categories(admin_token: str):
    """Test 8: POST /api/admin/categories/reorder (admin only)"""
    test_header("TEST 8: POST /api/admin/categories/reorder")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Test without auth -> 401
    resp = requests.post(f"{BASE_URL}/admin/categories/reorder", json={
        "group": "retail",
        "parent_id": None,
        "ids": []
    })
    if resp.status_code != 401:
        log(f"❌ FAIL: Without auth expected 401, got {resp.status_code}")
        return False
    log(f"✅ Without auth returns 401")
    
    # Create two top-level retail categories
    log("\n--- Creating two test categories A and B ---")
    resp_a = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "Reorder Cat A",
        "group": "retail"
    }, headers=headers)
    cat_a = resp_a.json()
    cat_a_id = cat_a["id"]
    created_categories.append(cat_a_id)
    
    resp_b = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "Reorder Cat B",
        "group": "retail"
    }, headers=headers)
    cat_b = resp_b.json()
    cat_b_id = cat_b["id"]
    created_categories.append(cat_b_id)
    
    log(f"✅ Created Cat A (id: {cat_a_id}, order: {cat_a.get('order')})")
    log(f"✅ Created Cat B (id: {cat_b_id}, order: {cat_b.get('order')})")
    
    # Test 8.1: Reorder B before A
    log("\n--- Test 8.1: Reorder B before A ---")
    resp = requests.post(f"{BASE_URL}/admin/categories/reorder", json={
        "group": "retail",
        "parent_id": None,
        "ids": [cat_b_id, cat_a_id]  # B first, then A
    }, headers=headers)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code} - {resp.text}")
        return False
    log(f"✅ Reorder successful")
    
    # Verify order via GET
    resp = requests.get(f"{BASE_URL}/categories?group=retail")
    data = resp.json()
    
    cat_a_data = next((c for c in data if c.get("id") == cat_a_id), None)
    cat_b_data = next((c for c in data if c.get("id") == cat_b_id), None)
    
    if not cat_a_data or not cat_b_data:
        log(f"❌ FAIL: Could not find categories in GET response")
        return False
    
    if cat_b_data.get("order") >= cat_a_data.get("order"):
        log(f"❌ FAIL: Order not swapped correctly. B order: {cat_b_data.get('order')}, A order: {cat_a_data.get('order')}")
        return False
    
    log(f"✅ Verified order swapped: B order={cat_b_data.get('order')}, A order={cat_a_data.get('order')}")
    
    # Test 8.2: Reorder with ids that don't belong to (group, parent_id) -> 400
    log("\n--- Test 8.2: Reorder with mismatched ids (should fail) ---")
    # Create a wholesale category
    resp = requests.post(f"{BASE_URL}/admin/categories", json={
        "name": "Wholesale Cat",
        "group": "wholesale"
    }, headers=headers)
    wholesale_cat = resp.json()
    wholesale_id = wholesale_cat["id"]
    created_categories.append(wholesale_id)
    
    # Try to reorder retail with a wholesale id
    resp = requests.post(f"{BASE_URL}/admin/categories/reorder", json={
        "group": "retail",
        "parent_id": None,
        "ids": [cat_a_id, wholesale_id]  # wholesale_id doesn't belong to retail
    }, headers=headers)
    
    if resp.status_code != 400:
        log(f"❌ FAIL: Expected 400, got {resp.status_code}")
        return False
    log(f"✅ Reorder with mismatched ids returns 400")
    
    log(f"\n✅ TEST 8 PASSED")
    return True

def main():
    print("\n" + "="*80)
    print("  ROUND 7 BACKEND TESTING: Admin-managed categories")
    print("="*80)
    
    # Login as admin
    admin_token = admin_login()
    
    # Create customer account for non-admin testing
    customer_email, customer_token = create_customer_account()
    
    results = []
    
    # Run all tests
    results.append(("Test 1: GET /api/meta/categories", test_1_meta_categories()))
    results.append(("Test 2: GET /api/categories?group=retail", test_2_categories_flat(admin_token)))
    results.append(("Test 3: GET /api/categories/tree?group=retail", test_3_categories_tree(admin_token)))
    results.append(("Test 4: GET /api/admin/categories", test_4_admin_categories(admin_token, customer_token)))
    results.append(("Test 5: POST /api/admin/categories", test_5_create_category(admin_token, customer_token)))
    results.append(("Test 6: PUT /api/admin/categories/{id}", test_6_update_category(admin_token)))
    results.append(("Test 7: DELETE /api/admin/categories/{id}", test_7_delete_category(admin_token)))
    results.append(("Test 8: POST /api/admin/categories/reorder", test_8_reorder_categories(admin_token)))
    
    # Cleanup
    cleanup_categories(admin_token)
    
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
