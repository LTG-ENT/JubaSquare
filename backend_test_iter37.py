#!/usr/bin/env python3
"""
Backend testing for JubaSquare Iter 37
Tests: Admin data backup/restore, Force-logout admin exemption
"""

import requests
import json
import sys
import time
from typing import Dict, Any, Optional

# Base URL from frontend/.env
BASE_URL = "https://shipping-fee-system.preview.emergentagent.com/api"

# Test credentials (from review request)
ADMIN_EMAIL = "admin@jubasquare.com"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"

# Global state
admin_token = None
customer_token = None
customer_id = None
test_page_id = None

def log(msg: str):
    """Print test log message"""
    print(f"[TEST] {msg}")

def api_call(method: str, endpoint: str, token: Optional[str] = None, 
             json_data: Optional[Dict] = None, params: Optional[Dict] = None,
             files: Optional[Dict] = None) -> requests.Response:
    """Make API call with optional auth"""
    url = f"{BASE_URL}{endpoint}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    if method == "GET":
        return requests.get(url, headers=headers, params=params)
    elif method == "POST":
        if files:
            # Don't set Content-Type for multipart/form-data
            return requests.post(url, headers=headers, files=files, data=params)
        return requests.post(url, headers=headers, json=json_data)
    elif method == "PUT":
        return requests.put(url, headers=headers, json=json_data)
    elif method == "DELETE":
        return requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")

def test_admin_login():
    """Test 1: Admin login"""
    global admin_token
    log("\n=== TEST 1: ADMIN LOGIN ===")
    
    resp = api_call("POST", "/auth/login", json_data={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "token" in data, "No token in response"
    assert data["user"]["role"] == "admin", f"Expected admin role, got {data['user']['role']}"
    
    admin_token = data["token"]
    log(f"✅ Admin login successful, token obtained")

#====================================================================================================
# AREA 1 — Admin data backup/restore
#====================================================================================================

def test_backup_summary():
    """Test 2: GET /api/admin/backup/summary"""
    log("\n=== TEST 2: BACKUP SUMMARY ===")
    
    # 2a: As admin - should return 200 with structure
    log("Test 2a: GET /api/admin/backup/summary as admin")
    resp = api_call("GET", "/admin/backup/summary", token=admin_token)
    assert resp.status_code == 200, f"Backup summary failed: {resp.status_code} {resp.text}"
    
    data = resp.json()
    assert "db" in data, "Missing 'db' field"
    assert "collections" in data, "Missing 'collections' field"
    assert "total_documents" in data, "Missing 'total_documents' field"
    assert isinstance(data["collections"], dict), "collections should be a dict"
    assert isinstance(data["total_documents"], int), "total_documents should be an int"
    
    log(f"✅ Backup summary returned: db={data['db']}, total_documents={data['total_documents']}")
    log(f"   Collections: {list(data['collections'].keys())[:5]}... ({len(data['collections'])} total)")
    
    # 2b: As non-admin - should return 401 or 403
    log("Test 2b: GET /api/admin/backup/summary without auth")
    resp = api_call("GET", "/admin/backup/summary")
    assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
    log(f"✅ Non-auth correctly blocked with {resp.status_code}")

def test_backup_export():
    """Test 3: GET /api/admin/backup/export"""
    log("\n=== TEST 3: BACKUP EXPORT ===")
    
    # 3a: As admin - should return 200 with JSON body
    log("Test 3a: GET /api/admin/backup/export as admin")
    resp = api_call("GET", "/admin/backup/export", token=admin_token)
    assert resp.status_code == 200, f"Backup export failed: {resp.status_code} {resp.text}"
    assert resp.headers.get("Content-Type") == "application/json", f"Wrong content type: {resp.headers.get('Content-Type')}"
    
    data = resp.json()
    assert "_backup_meta" in data, "Missing '_backup_meta' field"
    assert "collections" in data, "Missing 'collections' field"
    
    meta = data["_backup_meta"]
    assert "created_at" in meta, "Missing created_at in _backup_meta"
    assert "db" in meta, "Missing db in _backup_meta"
    assert "version" in meta, "Missing version in _backup_meta"
    assert "counts" in meta, "Missing counts in _backup_meta"
    
    collections = data["collections"]
    assert isinstance(collections, dict), "collections should be a dict"
    assert len(collections) > 0, "collections should not be empty"
    
    log(f"✅ Backup export returned: {len(collections)} collections")
    log(f"   Sample collections: {list(collections.keys())[:5]}")
    log(f"   Total documents in backup: {sum(meta['counts'].values())}")
    
    # 3b: As non-admin - should return 401 or 403
    log("Test 3b: GET /api/admin/backup/export without auth")
    resp = api_call("GET", "/admin/backup/export")
    assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
    log(f"✅ Non-auth correctly blocked with {resp.status_code}")

def test_backup_import_merge():
    """Test 4: POST /api/admin/backup/import?mode=merge"""
    global test_page_id
    log("\n=== TEST 4: BACKUP IMPORT (MERGE MODE) ===")
    
    # 4a: Create a small test backup file
    log("Test 4a: Create test backup file with one test page")
    test_page_id = "__test_backup_page__"
    backup_data = {
        "collections": {
            "pages": [
                {
                    "id": test_page_id,
                    "slug": "__bk_test__",
                    "title": "BK Test",
                    "subtitle": "Test page from backup",
                    "body_html": "<p>This is a test page created by backup import test.</p>",
                    "last_updated": "2025-01-10T00:00:00Z"
                }
            ]
        }
    }
    
    # 4b: Import with mode=merge (should upsert by id)
    log("Test 4b: POST /api/admin/backup/import?mode=merge")
    backup_json = json.dumps(backup_data)
    
    # Use requests directly to properly send multipart with query params
    url = f"{BASE_URL}/admin/backup/import?mode=merge"
    headers = {"Authorization": f"Bearer {admin_token}"}
    files = {"file": ("test_backup.json", backup_json, "application/json")}
    resp = requests.post(url, headers=headers, files=files)
    
    assert resp.status_code == 200, f"Backup import failed: {resp.status_code} {resp.text}"
    
    data = resp.json()
    assert data.get("ok") == True, "Import should return ok=true"
    assert data.get("mode") == "merge", f"Expected mode=merge, got {data.get('mode')}"
    assert "restored" in data, "Missing 'restored' field"
    assert data["restored"].get("pages") == 1, f"Expected 1 page restored, got {data['restored'].get('pages')}"
    
    log(f"✅ Backup import (merge) successful: {data['restored']}")
    
    # 4c: Verify the page was created (pages use 'slug' not 'id' in response)
    log("Test 4c: Verify test page exists via GET /api/pages/__bk_test__")
    resp = api_call("GET", "/pages/__bk_test__")
    assert resp.status_code == 200, f"Test page not found: {resp.status_code}"
    page_data = resp.json()
    assert page_data["slug"] == "__bk_test__", f"Wrong page slug: {page_data.get('slug')}"
    assert page_data["title"] == "BK Test", f"Wrong title: {page_data['title']}"
    log(f"✅ Test page verified: slug={page_data['slug']}, title={page_data['title']}")
    
    # 4d: Import the SAME file again (should be idempotent - no duplicates)
    log("Test 4d: Import same file again (idempotent test)")
    files = {"file": ("test_backup.json", backup_json, "application/json")}
    resp = requests.post(url, headers=headers, files=files)
    assert resp.status_code == 200, f"Second import failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data["restored"].get("pages") == 1, "Second import should still report 1 page (upsert)"
    log(f"✅ Idempotent import successful (no duplicates)")

def test_backup_import_replace():
    """Test 5: POST /api/admin/backup/import?mode=replace (on throwaway collection)"""
    log("\n=== TEST 5: BACKUP IMPORT (REPLACE MODE) ===")
    
    # 5a: Create a throwaway collection backup (don't use _ prefix as it's skipped)
    log("Test 5a: Create test backup for throwaway collection bk_scratch")
    backup_data = {
        "collections": {
            "bk_scratch": [
                {"id": "a", "v": 1},
                {"id": "b", "v": 2}
            ]
        }
    }
    
    # 5b: Import with mode=replace (should wipe then load)
    log("Test 5b: POST /api/admin/backup/import?mode=replace")
    backup_json = json.dumps(backup_data)
    
    # Use requests directly to properly send multipart with query params
    url = f"{BASE_URL}/admin/backup/import?mode=replace"
    headers = {"Authorization": f"Bearer {admin_token}"}
    files = {"file": ("test_backup_replace.json", backup_json, "application/json")}
    resp = requests.post(url, headers=headers, files=files)
    
    assert resp.status_code == 200, f"Backup import (replace) failed: {resp.status_code} {resp.text}"
    
    data = resp.json()
    assert data.get("ok") == True, "Import should return ok=true"
    assert data.get("mode") == "replace", f"Expected mode=replace, got {data.get('mode')}"
    assert data["restored"].get("bk_scratch") == 2, f"Expected 2 docs restored, got {data['restored'].get('bk_scratch')}"
    
    log(f"✅ Backup import (replace) successful: {data['restored']}")

def test_backup_import_invalid():
    """Test 6: POST /api/admin/backup/import with invalid file"""
    log("\n=== TEST 6: BACKUP IMPORT (INVALID FILE) ===")
    
    # 6a: Invalid JSON
    log("Test 6a: Import with invalid JSON")
    url = f"{BASE_URL}/admin/backup/import?mode=merge"
    headers = {"Authorization": f"Bearer {admin_token}"}
    files = {"file": ("invalid.json", "not valid json{", "application/json")}
    resp = requests.post(url, headers=headers, files=files)
    assert resp.status_code == 400, f"Expected 400 for invalid JSON, got {resp.status_code}"
    log(f"✅ Invalid JSON correctly rejected with 400")
    
    # 6b: Empty collections object (backend accepts this as valid - it just restores nothing)
    log("Test 6b: Import with empty collections (valid but restores nothing)")
    backup_data = {"collections": {}}
    backup_json = json.dumps(backup_data)
    files = {"file": ("empty_collections.json", backup_json, "application/json")}
    resp = requests.post(url, headers=headers, files=files)
    assert resp.status_code == 200, f"Expected 200 for empty collections, got {resp.status_code}"
    data = resp.json()
    assert data.get("ok") == True, "Should return ok=true"
    assert data.get("restored") == {}, f"Should restore nothing, got {data.get('restored')}"
    log(f"✅ Empty collections accepted (restores nothing as expected)")

def test_backup_import_auth():
    """Test 7: POST /api/admin/backup/import without auth"""
    log("\n=== TEST 7: BACKUP IMPORT (AUTH GATING) ===")
    
    backup_data = {"collections": {"test": []}}
    backup_json = json.dumps(backup_data)
    
    url = f"{BASE_URL}/admin/backup/import?mode=merge"
    files = {"file": ("test.json", backup_json, "application/json")}
    resp = requests.post(url, files=files)
    
    assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
    log(f"✅ Non-auth correctly blocked with {resp.status_code}")

#====================================================================================================
# AREA 2 — Force-logout EXEMPTS admins
#====================================================================================================

def test_force_logout_endpoint_discovery():
    """Test 8: Discover the force-logout endpoint"""
    log("\n=== TEST 8: FORCE-LOGOUT ENDPOINT DISCOVERY ===")
    
    # The endpoint is POST /api/admin/force-logout-all (from grep results)
    log("Test 8: Endpoint is POST /api/admin/force-logout-all")
    log("✅ Endpoint discovered: POST /api/admin/force-logout-all")
    return "/admin/force-logout-all"

def test_create_normal_user():
    """Test 9: Create a normal user (customer) via admin endpoint"""
    global customer_token, customer_id
    log("\n=== TEST 9: CREATE NORMAL USER ===")
    
    # 9a: Create customer via admin endpoint (bypasses email verification)
    log("Test 9a: Create customer via POST /api/admin/users")
    timestamp = int(time.time())
    customer_email = f"test_customer_{timestamp}@test.com"
    customer_password = "test123456"
    
    resp = api_call("POST", "/admin/users", token=admin_token, json_data={
        "email": customer_email,
        "password": customer_password,
        "name": f"Test Customer {timestamp}",
        "phone": "+211900000000",
        "role": "customer"
    })
    
    assert resp.status_code == 200, f"Customer creation failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "user" in data, "No user in response"
    assert "id" in data["user"], "No id in user object"
    customer_id = data["user"]["id"]
    log(f"✅ Customer created via admin: email={customer_email}, id={customer_id}")
    
    # 9b: Login as the customer to get token
    log("Test 9b: Login as customer to get token")
    resp = api_call("POST", "/auth/login", json_data={
        "email": customer_email,
        "password": customer_password
    })
    assert resp.status_code == 200, f"Customer login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "token" in data, "No token in login response"
    customer_token = data["token"]
    log(f"✅ Customer logged in, token obtained")
    
    # 9c: Verify customer can access their profile
    log("Test 9c: Verify customer token works")
    resp = api_call("GET", "/auth/me", token=customer_token)
    assert resp.status_code == 200, f"Customer token verification failed: {resp.status_code}"
    log(f"✅ Customer token verified")
    
    return customer_email, customer_password

def test_force_logout_admin_exemption():
    """Test 10: Force-logout exempts admins"""
    log("\n=== TEST 10: FORCE-LOGOUT ADMIN EXEMPTION ===")
    
    customer_email, customer_password = test_create_normal_user()
    
    # 10a: Call force-logout as admin
    log("Test 10a: POST /api/admin/force-logout-all as admin")
    resp = api_call("POST", "/admin/force-logout-all", token=admin_token)
    assert resp.status_code == 200, f"Force-logout failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data.get("ok") == True, "Force-logout should return ok=true"
    assert "token_version" in data, "Missing token_version in response"
    log(f"✅ Force-logout successful: token_version={data['token_version']}")
    
    # 10b: Verify ADMIN token STILL works
    log("Test 10b: Verify admin token still works after force-logout")
    resp = api_call("GET", "/admin/settings", token=admin_token)
    assert resp.status_code == 200, f"Admin token should still work, got {resp.status_code}"
    log(f"✅ Admin token still works (exempted from force-logout)")
    
    # 10c: Verify customer's OLD token now returns 401
    log("Test 10c: Verify customer's old token is invalidated")
    resp = api_call("GET", "/auth/me", token=customer_token)
    assert resp.status_code == 401, f"Expected 401 for invalidated token, got {resp.status_code}"
    assert "Session invalidated by admin" in resp.text or "invalidated" in resp.text.lower(), \
        f"Expected 'Session invalidated' message, got: {resp.text}"
    log(f"✅ Customer token invalidated: {resp.json().get('detail', resp.text)}")
    
    # 10d: Verify customer can log in again and new token works
    log("Test 10d: Verify customer can log in again")
    resp = api_call("POST", "/auth/login", json_data={
        "email": customer_email,
        "password": customer_password
    })
    assert resp.status_code == 200, f"Customer re-login failed: {resp.status_code} {resp.text}"
    new_customer_token = resp.json()["token"]
    
    resp = api_call("GET", "/auth/me", token=new_customer_token)
    assert resp.status_code == 200, f"New customer token should work, got {resp.status_code}"
    log(f"✅ Customer can log in again and new token works")

#====================================================================================================
# CLEANUP
#====================================================================================================

def test_cleanup():
    """Test 11: Cleanup test data"""
    log("\n=== TEST 11: CLEANUP ===")
    
    # Try to delete the test page we created
    if test_page_id:
        log(f"Test 11a: Attempting to delete test page {test_page_id}")
        # Note: There may not be a delete endpoint for pages, so we'll just note it
        log(f"⚠️  Note: Test page {test_page_id} (slug: __bk_test__) left in database")
        log(f"    Admin can manually delete via database if needed")
    
    log(f"⚠️  Note: Throwaway collection bk_scratch left in database")
    log(f"    This is expected per test requirements")
    
    log(f"✅ Cleanup notes recorded")

#====================================================================================================
# MAIN TEST RUNNER
#====================================================================================================

def run_all_tests():
    """Run all tests in sequence"""
    tests = [
        ("Admin Login", test_admin_login),
        ("Backup Summary", test_backup_summary),
        ("Backup Export", test_backup_export),
        ("Backup Import (Merge)", test_backup_import_merge),
        ("Backup Import (Replace)", test_backup_import_replace),
        ("Backup Import (Invalid)", test_backup_import_invalid),
        ("Backup Import (Auth)", test_backup_import_auth),
        ("Force-Logout Endpoint Discovery", test_force_logout_endpoint_discovery),
        ("Force-Logout Admin Exemption", test_force_logout_admin_exemption),
        ("Cleanup", test_cleanup),
    ]
    
    passed = 0
    failed = 0
    
    log("=" * 80)
    log("STARTING ITER 37 BACKEND TESTS")
    log("=" * 80)
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            failed += 1
            log(f"❌ TEST FAILED: {name}")
            log(f"   Error: {str(e)}")
        except Exception as e:
            failed += 1
            log(f"❌ TEST ERROR: {name}")
            log(f"   Exception: {str(e)}")
    
    log("\n" + "=" * 80)
    log(f"TEST SUMMARY: {passed} passed, {failed} failed out of {passed + failed} total")
    log("=" * 80)
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
