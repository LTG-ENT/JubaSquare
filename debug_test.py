#!/usr/bin/env python3
"""Debug script to investigate test failures"""

import requests
import time
import json

BASE_URL = "https://jubasquare-odoo-v2.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Get admin token
resp = requests.post(
    f"{API_BASE}/auth/login",
    json={"email": "admin", "password": "1234"},
    timeout=10
)
admin_token = resp.json().get("token")
print(f"Admin token: {admin_token[:20]}...")

# Test 1: Check admin/users response structure
print("\n=== Testing GET /api/admin/users ===")
resp = requests.get(
    f"{API_BASE}/admin/users",
    headers={"Authorization": f"Bearer {admin_token}"},
    timeout=10
)
print(f"Status: {resp.status_code}")
print(f"Response type: {type(resp.json())}")
data = resp.json()
if isinstance(data, dict):
    print(f"Keys: {data.keys()}")
    if "items" in data:
        print(f"Number of items: {len(data['items'])}")
        if data['items']:
            print(f"First item keys: {data['items'][0].keys()}")
elif isinstance(data, list):
    print(f"Number of users: {len(data)}")
    if data:
        print(f"First user keys: {data[0].keys()}")

# Test 2: Create a test user and check if it appears
print("\n=== Testing user creation ===")
ts = int(time.time())
test_email = f"debug_{ts}@example.com"
resp = requests.post(
    f"{API_BASE}/auth/signup",
    json={
        "email": test_email,
        "password": "testpass123",
        "name": "Debug User",
        "phone": ""
    },
    timeout=10
)
print(f"Signup status: {resp.status_code}")
print(f"Signup response: {resp.json()}")

# Check if user appears in admin list
resp = requests.get(
    f"{API_BASE}/admin/users",
    headers={"Authorization": f"Bearer {admin_token}"},
    timeout=10
)
users_data = resp.json()
if isinstance(users_data, dict) and "items" in users_data:
    users = users_data["items"]
else:
    users = users_data

found = False
for user in users:
    if user.get("email") == test_email:
        print(f"✓ Found user: {user}")
        found = True
        break

if not found:
    print(f"✗ User {test_email} not found in list")
    print(f"Total users in list: {len(users)}")

# Test 3: Try to login as the new user
print("\n=== Testing customer login ===")
resp = requests.post(
    f"{API_BASE}/auth/login",
    json={"email": test_email, "password": "testpass123"},
    timeout=10
)
print(f"Login status: {resp.status_code}")
print(f"Login response: {resp.json() if resp.status_code == 200 else resp.text}")

# Test 4: Check bulk template endpoints
print("\n=== Testing bulk template endpoints ===")
resp = requests.get(f"{API_BASE}/products/bulk-template", timeout=10)
print(f"CSV template status: {resp.status_code}")
if resp.status_code != 200:
    print(f"CSV template error: {resp.text[:200]}")

resp = requests.get(f"{API_BASE}/products/bulk-template?fmt=xlsx", timeout=10)
print(f"XLSX template status: {resp.status_code}")
if resp.status_code != 200:
    print(f"XLSX template error: {resp.text[:200]}")

# Test 5: Check admin user creation
print("\n=== Testing admin user creation ===")
ts = int(time.time())
seller_email = f"seller_debug_{ts}@example.com"
resp = requests.post(
    f"{API_BASE}/admin/users",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={
        "email": seller_email,
        "password": "testpass123",
        "name": "Debug Seller",
        "role": "seller",
        "phone": ""
    },
    timeout=10
)
print(f"Admin user creation status: {resp.status_code}")
print(f"Admin user creation response: {resp.json() if resp.status_code in [200, 201] else resp.text[:200]}")
