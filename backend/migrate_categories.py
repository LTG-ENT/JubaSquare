#!/usr/bin/env python3
"""
One-time migration script: Convert category names to category_id for products and menu_items.

This script:
1. Reads all products with category (string name)
2. Looks up matching category by name and appropriate group (retail/wholesale)
3. Sets category_id field
4. Same process for menu_items (group=restaurant)
5. Idempotent: skips items that already have category_id

Usage:
    python3 migrate_categories.py [--dry-run]

Options:
    --dry-run    Show what would be migrated without making changes
"""

import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/")


async def migrate_products(db, dry_run=False):
    """Migrate products: category (string) -> category_id (UUID)"""
    print("\n=== MIGRATING PRODUCTS ===")
    
    # Get all categories for lookup
    all_cats = await db.categories.find({}, {"_id": 0}).to_list(10000)
    cat_by_name_and_group = {}
    for c in all_cats:
        key = (c["name"].lower(), c["group"])
        cat_by_name_and_group[key] = c["id"]
    
    print(f"Loaded {len(all_cats)} categories for lookup")
    
    # Get all products that need migration (no category_id or category_id is empty)
    products = await db.products.find({
        "$or": [
            {"category_id": {"$exists": False}},
            {"category_id": ""},
            {"category_id": None}
        ]
    }, {"_id": 0}).to_list(10000)
    
    print(f"Found {len(products)} products without category_id")
    
    migrated = 0
    failed = []
    
    for p in products:
        product_id = p.get("id")
        legacy_category = p.get("category", "").strip()
        shop_kind = p.get("shop_kind", "retail")  # retail or wholesale
        
        if not legacy_category:
            failed.append({
                "id": product_id,
                "name": p.get("name"),
                "reason": "No legacy category field to migrate from"
            })
            continue
        
        # Try to match category by name and shop_kind
        # For retail shops, look in retail group; for wholesale, look in wholesale group
        group = shop_kind if shop_kind in ["retail", "wholesale"] else "retail"
        key = (legacy_category.lower(), group)
        
        category_id = cat_by_name_and_group.get(key)
        
        if not category_id:
            # Try alternative: if it's a retail shop but category doesn't exist in retail,
            # check if it exists in wholesale (and vice versa)
            alt_group = "wholesale" if group == "retail" else "retail"
            alt_key = (legacy_category.lower(), alt_group)
            category_id = cat_by_name_and_group.get(alt_key)
        
        if category_id:
            if dry_run:
                print(f"[DRY RUN] Would update product {product_id} ({p.get('name')[:30]}...): category='{legacy_category}' -> category_id={category_id}")
            else:
                await db.products.update_one(
                    {"id": product_id},
                    {"$set": {"category_id": category_id}}
                )
                print(f"✓ Migrated product {product_id}: '{legacy_category}' -> {category_id}")
            migrated += 1
        else:
            failed.append({
                "id": product_id,
                "name": p.get("name"),
                "legacy_category": legacy_category,
                "shop_kind": shop_kind,
                "reason": f"No matching category found in groups: {group}, {alt_group}"
            })
    
    print(f"\n✓ Products migrated: {migrated}")
    if failed:
        print(f"✗ Products failed: {len(failed)}")
        print("\nFailed products:")
        for f in failed:
            print(f"  - {f['id']} ({f['name'][:50]}): {f['reason']}")
    
    return migrated, failed


async def migrate_menu_items(db, dry_run=False):
    """Migrate menu_items: food_category (string) -> category_id (UUID)"""
    print("\n=== MIGRATING MENU ITEMS ===")
    
    # Get all restaurant categories for lookup
    restaurant_cats = await db.categories.find(
        {"group": "restaurant"},
        {"_id": 0}
    ).to_list(10000)
    
    cat_by_name = {c["name"].lower(): c["id"] for c in restaurant_cats}
    print(f"Loaded {len(restaurant_cats)} restaurant categories for lookup")
    
    # Get all menu items that need migration
    menu_items = await db.menu_items.find({
        "$or": [
            {"category_id": {"$exists": False}},
            {"category_id": ""},
            {"category_id": None}
        ]
    }, {"_id": 0}).to_list(10000)
    
    print(f"Found {len(menu_items)} menu items without category_id")
    
    migrated = 0
    failed = []
    
    for m in menu_items:
        item_id = m.get("id")
        legacy_food_category = m.get("food_category", "").strip()
        
        if not legacy_food_category:
            failed.append({
                "id": item_id,
                "name": m.get("name"),
                "reason": "No legacy food_category field to migrate from"
            })
            continue
        
        category_id = cat_by_name.get(legacy_food_category.lower())
        
        if category_id:
            if dry_run:
                print(f"[DRY RUN] Would update menu_item {item_id} ({m.get('name')[:30]}...): food_category='{legacy_food_category}' -> category_id={category_id}")
            else:
                await db.menu_items.update_one(
                    {"id": item_id},
                    {"$set": {"category_id": category_id}}
                )
                print(f"✓ Migrated menu_item {item_id}: '{legacy_food_category}' -> {category_id}")
            migrated += 1
        else:
            failed.append({
                "id": item_id,
                "name": m.get("name"),
                "legacy_food_category": legacy_food_category,
                "reason": f"No matching restaurant category found for '{legacy_food_category}'"
            })
    
    print(f"\n✓ Menu items migrated: {migrated}")
    if failed:
        print(f"✗ Menu items failed: {len(failed)}")
        print("\nFailed menu items:")
        for f in failed:
            print(f"  - {f['id']} ({f['name'][:50]}): {f['reason']}")
    
    return migrated, failed


async def main():
    dry_run = "--dry-run" in sys.argv
    
    if dry_run:
        print("=== DRY RUN MODE - NO CHANGES WILL BE MADE ===\n")
    else:
        print("=== MIGRATION MODE - CHANGES WILL BE SAVED ===\n")
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client.jubasquare
    
    try:
        # Migrate products
        products_migrated, products_failed = await migrate_products(db, dry_run)
        
        # Migrate menu items
        menu_items_migrated, menu_items_failed = await migrate_menu_items(db, dry_run)
        
        # Summary
        print("\n" + "=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)
        print(f"Products migrated: {products_migrated}")
        print(f"Products failed: {len(products_failed)}")
        print(f"Menu items migrated: {menu_items_migrated}")
        print(f"Menu items failed: {len(menu_items_failed)}")
        print("=" * 60)
        
        if dry_run:
            print("\nℹ️  This was a dry run. Run without --dry-run to apply changes.")
        else:
            print("\n✓ Migration complete!")
            
            if products_failed or menu_items_failed:
                print("\n⚠️  Some items failed to migrate. Use the admin debug tool:")
                print("   GET /api/admin/categories/integrity")
                print("   PUT /api/admin/products/{id}/category-id")
                print("   PUT /api/admin/menu-items/{id}/category-id")
    
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
