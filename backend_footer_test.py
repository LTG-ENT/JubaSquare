#!/usr/bin/env python3
"""
Backend API tests for JubaSquare Footer endpoints (Round 6).
Tests GET /api/site-config/footer and PUT /api/admin/site-config/footer.
"""

import requests
import sys
import time
from typing import Optional

# Backend URL from frontend/.env
BASE_URL = "https://user-admin-center.preview.emergentagent.com/api"

# Admin credentials
ADMIN_EMAIL = "ltg-general-trading@hotmail.com"
ADMIN_PASSWORD = "Kokobleake1"

# Expected default values from footer_seed.py
EXPECTED_DEFAULTS = {
    "tagline": "Juba's marketplace for retail, wholesale and food delivery — built for South Sudan.",
    "social_facebook": "https://facebook.com/",
    "social_instagram": "https://instagram.com/",
    "social_twitter": "https://twitter.com/",
    "shop_title": "Shop",
    "company_title": "Company",
    "legal_title": "Legal",
    "contact_title": "Get in touch",
    "contact_email": "ltg-general-trading@hotmail.com",
    "contact_phone": "+211 9XX XXX XXX",
    "contact_location": "Juba, South Sudan 🇸🇸",
    "copyright_text": "© {year} L.T.G General Trading. All rights reserved.",
    "tagline_bottom": "Built with ❤ for Juba — Cash on Delivery supported.",
}

# Test counters
tests_passed = 0
tests_failed = 0


def log_test(name: str, passed: bool, details: str = ""):
    """Log test result."""
    global tests_passed, tests_failed
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"  → {details}")
    if passed:
        tests_passed += 1
    else:
        tests_failed += 1


def login(email: str, password: str) -> Optional[str]:
    """Login and return access token."""
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("token")
        else:
            print(f"Login failed: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None


def test_get_footer_public():
    """Test GET /api/site-config/footer (public, no auth)."""
    print("\n=== Test 1: GET /api/site-config/footer (public) ===")
    
    try:
        resp = requests.get(f"{BASE_URL}/site-config/footer", timeout=10)
        
        # Should return 200
        log_test(
            "GET /api/site-config/footer returns 200",
            resp.status_code == 200,
            f"Status: {resp.status_code}"
        )
        
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        
        # Check required fields are present
        required_fields = [
            "tagline", "social_facebook", "social_instagram", "social_twitter",
            "shop_title", "shop_links", "company_title", "company_links",
            "legal_title", "legal_links", "contact_title", "contact_email",
            "contact_phone", "contact_location", "copyright_text", "tagline_bottom"
        ]
        
        missing_fields = [f for f in required_fields if f not in data]
        log_test(
            "All required fields present",
            len(missing_fields) == 0,
            f"Missing: {missing_fields}" if missing_fields else "All fields present"
        )
        
        # Check _id is NOT in response
        log_test(
            "_id field not in response",
            "_id" not in data,
            "_id field correctly excluded" if "_id" not in data else "_id field present (should be excluded)"
        )
        
        # Check shop_links is a non-empty list
        shop_links = data.get("shop_links", [])
        log_test(
            "shop_links is non-empty list",
            isinstance(shop_links, list) and len(shop_links) > 0,
            f"shop_links has {len(shop_links)} items"
        )
        
        # Check shop_links contains expected defaults (Marketplace, All Shops, etc.)
        if isinstance(shop_links, list) and len(shop_links) > 0:
            labels = [link.get("label", "") for link in shop_links]
            has_marketplace = "Marketplace" in labels
            log_test(
                "shop_links contains 'Marketplace'",
                has_marketplace,
                f"Labels: {labels}"
            )
        
        # Check company_links is a non-empty list
        company_links = data.get("company_links", [])
        log_test(
            "company_links is non-empty list",
            isinstance(company_links, list) and len(company_links) > 0,
            f"company_links has {len(company_links)} items"
        )
        
        # Check legal_links is a non-empty list
        legal_links = data.get("legal_links", [])
        log_test(
            "legal_links is non-empty list",
            isinstance(legal_links, list) and len(legal_links) > 0,
            f"legal_links has {len(legal_links)} items"
        )
        
        # Check copyright_text contains {year} placeholder
        copyright_text = data.get("copyright_text", "")
        log_test(
            "copyright_text contains {year} placeholder",
            "{year}" in copyright_text,
            f"copyright_text: {copyright_text}"
        )
        
        # Verify default values match footer_seed.py
        for key, expected_value in EXPECTED_DEFAULTS.items():
            if key not in ["shop_links", "company_links", "legal_links"]:  # Skip list fields
                actual_value = data.get(key)
                log_test(
                    f"Default value for '{key}' matches seed",
                    actual_value == expected_value,
                    f"Expected: {expected_value}, Got: {actual_value}"
                )
        
        return data
        
    except Exception as e:
        log_test("GET /api/site-config/footer", False, f"Exception: {e}")
        return None


def test_put_footer_no_auth():
    """Test PUT /api/admin/site-config/footer without auth (should return 401)."""
    print("\n=== Test 2: PUT /api/admin/site-config/footer (no auth) ===")
    
    try:
        resp = requests.put(
            f"{BASE_URL}/admin/site-config/footer",
            json={"tagline": "Test tagline"},
            timeout=10
        )
        
        log_test(
            "PUT without auth returns 401",
            resp.status_code == 401,
            f"Status: {resp.status_code}"
        )
        
    except Exception as e:
        log_test("PUT without auth", False, f"Exception: {e}")


def test_put_footer_admin():
    """Test PUT /api/admin/site-config/footer with admin auth."""
    print("\n=== Test 3: PUT /api/admin/site-config/footer (admin auth) ===")
    
    # Login as admin
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        log_test("Admin login", False, "Failed to get admin token")
        return None
    
    log_test("Admin login", True, "Got admin token")
    
    # Test 1: Partial update (tagline only)
    try:
        test_tagline = "Test tagline 2026"
        resp = requests.put(
            f"{BASE_URL}/admin/site-config/footer",
            json={"tagline": test_tagline},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        
        log_test(
            "PUT with admin token returns 200",
            resp.status_code == 200,
            f"Status: {resp.status_code}"
        )
        
        if resp.status_code == 200:
            data = resp.json()
            log_test(
                "Response reflects updated tagline",
                data.get("tagline") == test_tagline,
                f"tagline: {data.get('tagline')}"
            )
            
            # Check last_updated field is present
            log_test(
                "last_updated field present",
                "last_updated" in data,
                f"last_updated: {data.get('last_updated')}"
            )
    
    except Exception as e:
        log_test("PUT partial update", False, f"Exception: {e}")
    
    # Test 2: Verify persistence with GET
    try:
        time.sleep(0.5)  # Small delay
        resp = requests.get(f"{BASE_URL}/site-config/footer", timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            log_test(
                "GET after PUT shows persisted tagline",
                data.get("tagline") == test_tagline,
                f"tagline: {data.get('tagline')}"
            )
    
    except Exception as e:
        log_test("GET after PUT", False, f"Exception: {e}")
    
    # Test 3: Update with shop_links including empty rows (should be filtered)
    try:
        test_links = [
            {"label": "Real Link", "url": "/real"},
            {"label": "", "url": ""},  # Empty row - should be filtered
            {"label": "X", "url": ""},  # Partial empty - should be filtered
            {"label": "", "url": "/empty-label"},  # Partial empty - should be filtered
            {"label": "Another Real", "url": "/another"}
        ]
        
        resp = requests.put(
            f"{BASE_URL}/admin/site-config/footer",
            json={"shop_links": test_links},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            shop_links = data.get("shop_links", [])
            
            # Should only have 2 valid links
            log_test(
                "Empty link rows filtered out",
                len(shop_links) == 2,
                f"Expected 2 links, got {len(shop_links)}: {shop_links}"
            )
            
            # Check the valid links are present
            if len(shop_links) == 2:
                labels = [link.get("label") for link in shop_links]
                log_test(
                    "Valid links preserved",
                    "Real Link" in labels and "Another Real" in labels,
                    f"Labels: {labels}"
                )
    
    except Exception as e:
        log_test("PUT with empty rows", False, f"Exception: {e}")
    
    # Test 4: Verify last_updated changes on each PUT
    try:
        # Get current last_updated
        resp1 = requests.get(f"{BASE_URL}/site-config/footer", timeout=10)
        if resp1.status_code == 200:
            last_updated_1 = resp1.json().get("last_updated")
            
            time.sleep(1)  # Wait 1 second
            
            # Make another update
            resp2 = requests.put(
                f"{BASE_URL}/admin/site-config/footer",
                json={"tagline_bottom": "Updated bottom tagline"},
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10
            )
            
            if resp2.status_code == 200:
                last_updated_2 = resp2.json().get("last_updated")
                
                log_test(
                    "last_updated changes after PUT",
                    last_updated_2 != last_updated_1,
                    f"Before: {last_updated_1}, After: {last_updated_2}"
                )
    
    except Exception as e:
        log_test("last_updated timestamp", False, f"Exception: {e}")
    
    return admin_token


def test_restore_defaults(admin_token: str, original_footer: dict):
    """Restore footer to original defaults."""
    print("\n=== Test 4: Restore footer to defaults ===")
    
    if not admin_token or not original_footer:
        log_test("Restore defaults", False, "Missing admin token or original footer")
        return
    
    try:
        # Restore all fields from original
        restore_payload = {
            "tagline": original_footer.get("tagline"),
            "social_facebook": original_footer.get("social_facebook"),
            "social_instagram": original_footer.get("social_instagram"),
            "social_twitter": original_footer.get("social_twitter"),
            "shop_title": original_footer.get("shop_title"),
            "shop_links": original_footer.get("shop_links"),
            "company_title": original_footer.get("company_title"),
            "company_links": original_footer.get("company_links"),
            "legal_title": original_footer.get("legal_title"),
            "legal_links": original_footer.get("legal_links"),
            "contact_title": original_footer.get("contact_title"),
            "contact_email": original_footer.get("contact_email"),
            "contact_phone": original_footer.get("contact_phone"),
            "contact_location": original_footer.get("contact_location"),
            "copyright_text": original_footer.get("copyright_text"),
            "tagline_bottom": original_footer.get("tagline_bottom"),
        }
        
        resp = requests.put(
            f"{BASE_URL}/admin/site-config/footer",
            json=restore_payload,
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        
        log_test(
            "Restore defaults successful",
            resp.status_code == 200,
            f"Status: {resp.status_code}"
        )
        
        # Verify restoration
        if resp.status_code == 200:
            time.sleep(0.5)
            resp_verify = requests.get(f"{BASE_URL}/site-config/footer", timeout=10)
            if resp_verify.status_code == 200:
                data = resp_verify.json()
                log_test(
                    "Defaults restored correctly",
                    data.get("tagline") == original_footer.get("tagline"),
                    f"tagline: {data.get('tagline')}"
                )
    
    except Exception as e:
        log_test("Restore defaults", False, f"Exception: {e}")


def test_seed_idempotency():
    """Verify seed values match footer_seed.py defaults."""
    print("\n=== Test 5: Seed idempotency ===")
    
    try:
        resp = requests.get(f"{BASE_URL}/site-config/footer", timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            
            # Check shop_links default count (should have 4 items from seed)
            shop_links = data.get("shop_links", [])
            expected_shop_count = 4  # Marketplace, All Shops, Wholesale, Food & Restaurants
            
            log_test(
                "shop_links has expected default count",
                len(shop_links) >= expected_shop_count,
                f"Expected at least {expected_shop_count}, got {len(shop_links)}"
            )
            
            # Check company_links default count (should have 3 items from seed)
            company_links = data.get("company_links", [])
            expected_company_count = 3  # About, Contact, Become a seller
            
            log_test(
                "company_links has expected default count",
                len(company_links) >= expected_company_count,
                f"Expected at least {expected_company_count}, got {len(company_links)}"
            )
            
            # Check legal_links default count (should have 3 items from seed)
            legal_links = data.get("legal_links", [])
            expected_legal_count = 3  # Terms, Privacy, Return Policy
            
            log_test(
                "legal_links has expected default count",
                len(legal_links) >= expected_legal_count,
                f"Expected at least {expected_legal_count}, got {len(legal_links)}"
            )
            
            # Check copyright_text format
            copyright_text = data.get("copyright_text", "")
            log_test(
                "copyright_text matches seed format",
                "L.T.G General Trading" in copyright_text and "{year}" in copyright_text,
                f"copyright_text: {copyright_text}"
            )
    
    except Exception as e:
        log_test("Seed idempotency", False, f"Exception: {e}")


def main():
    """Run all footer endpoint tests."""
    print("=" * 80)
    print("JubaSquare Footer Endpoints Test Suite (Round 6)")
    print("=" * 80)
    
    # Test 1: GET footer (public)
    original_footer = test_get_footer_public()
    
    # Test 2: PUT without auth (should fail)
    test_put_footer_no_auth()
    
    # Test 3: PUT with admin auth
    admin_token = test_put_footer_admin()
    
    # Test 4: Restore defaults
    if original_footer and admin_token:
        test_restore_defaults(admin_token, original_footer)
    
    # Test 5: Seed idempotency
    test_seed_idempotency()
    
    # Summary
    print("\n" + "=" * 80)
    print(f"TESTS COMPLETED: {tests_passed + tests_failed} total")
    print(f"✅ PASSED: {tests_passed}")
    print(f"❌ FAILED: {tests_failed}")
    print("=" * 80)
    
    # Exit with appropriate code
    sys.exit(0 if tests_failed == 0 else 1)


if __name__ == "__main__":
    main()
