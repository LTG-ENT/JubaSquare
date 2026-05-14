#!/usr/bin/env python3
"""
Setup test accounts for testing
"""

import requests

BASE_URL = "https://driver-area-filter.preview.emergentagent.com/api"

def create_account(email, password, name, role="customer"):
    """Create a test account via signup"""
    try:
        response = requests.post(
            f"{BASE_URL}/auth/signup",
            json={
                "email": email,
                "password": password,
                "name": name,
                "role": role
            },
            timeout=10
        )
        if response.status_code in [200, 201]:
            print(f"✅ Created {role} account: {email}")
            return True
        elif response.status_code == 400 and "already exists" in response.text.lower():
            print(f"ℹ️  Account already exists: {email}")
            return True
        else:
            print(f"❌ Failed to create {email}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception creating {email}: {e}")
        return False

def main():
    print("Setting up test accounts...")
    
    # Create seller account
    create_account("seller@demo.com", "Demo1234!", "Demo Seller", "seller")
    
    # Create customer account
    create_account("customer@demo.com", "Demo1234!", "Demo Customer", "customer")
    
    print("\nSetup complete!")

if __name__ == "__main__":
    main()
