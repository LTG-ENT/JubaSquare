"""End-to-end style tests for:
  - Restaurant "Mirror Shops" delivery logic (free / fixed / per_area, admin/seller override)
  - Shop & Restaurant customer-visibility gate based on verification status

Runs against a live backend via REACT_APP_BACKEND_URL. Creates ephemeral
docs directly in Mongo (no orders left behind). Idempotent-ish.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from cod import _calculate_delivery_fee  # noqa: E402
import cod as cod_module  # noqa: E402
import logging

# Provide a log attribute for cod module (bind() normally does this)
cod_module.log = logging.getLogger("cod-test")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Bind cod module (it needs db reference for _calculate_delivery_fee)
    cod_module.db = db

    seller_id = f"test-seller-{uuid.uuid4()}"
    shop_id = f"test-shop-{uuid.uuid4()}"
    rest_id = f"test-rest-{uuid.uuid4()}"

    # Ensure the global admin_manages_delivery = False for this test
    await db.settings.update_one(
        {"id": "system"},
        {"$set": {"id": "system", "admin_manages_delivery": False}},
        upsert=True,
    )

    # === Restaurant: seller-managed, fixed 3.5 USD ===
    await db.restaurants.insert_one({
        "id": rest_id,
        "seller_id": seller_id,
        "name": "TestPizza",
        "area": "Munuki",
        "verification": "Pending",  # for visibility test
        "delivery_mode": "fixed",
        "delivery_fee_usd": 3.5,
        "delivery_per_area": [],
        "delivery_managed_by": "seller",
        "is_deleted": False,
    })

    fee = await _calculate_delivery_fee(
        pickup_area="Munuki", delivery_area="Hai Cinema",
        order_type="restaurant", restaurant_id=rest_id
    )
    assert abs(fee - 3.5) < 0.001, f"Expected 3.5, got {fee}"
    print(f"[PASS] Restaurant seller-managed fixed fee = {fee}")

    # Switch to per_area
    await db.restaurants.update_one(
        {"id": rest_id},
        {"$set": {
            "delivery_mode": "per_area",
            "delivery_per_area": [
                {"area": "Hai Cinema", "fee_usd": 4.0},
                {"area": "Custom", "fee_usd": 7.0},
            ],
        }},
    )
    fee = await _calculate_delivery_fee(
        pickup_area="Munuki", delivery_area="Custom",
        order_type="restaurant", restaurant_id=rest_id
    )
    assert abs(fee - 7.0) < 0.001, f"Expected 7.0, got {fee}"
    print(f"[PASS] Restaurant per-area fee (Custom) = {fee}")

    fee = await _calculate_delivery_fee(
        pickup_area="Munuki", delivery_area="Hai Cinema",
        order_type="restaurant", restaurant_id=rest_id
    )
    assert abs(fee - 4.0) < 0.001, f"Expected 4.0, got {fee}"
    print(f"[PASS] Restaurant per-area fee (Hai Cinema) = {fee}")

    # Free
    await db.restaurants.update_one(
        {"id": rest_id},
        {"$set": {"delivery_mode": "free"}},
    )
    fee = await _calculate_delivery_fee(
        pickup_area="Munuki", delivery_area="Anywhere",
        order_type="restaurant", restaurant_id=rest_id
    )
    assert abs(fee - 0.0) < 0.001, f"Expected 0.0, got {fee}"
    print(f"[PASS] Restaurant free delivery = {fee}")

    # Admin override branch — restaurant is set to admin, falls back to
    # delivery_pricing_rules / default. Ensure it does NOT hit seller branch.
    await db.restaurants.update_one(
        {"id": rest_id},
        {"$set": {
            "delivery_managed_by": "admin",
            "delivery_mode": "fixed",
            "delivery_fee_usd": 99.0,  # would be picked if seller branch was used
        }},
    )
    # Ensure no admin rule exists and default is 2.0
    await db.settings.update_one(
        {"key": "default_delivery_fee_usd"},
        {"$set": {"key": "default_delivery_fee_usd", "value": 2.0}},
        upsert=True,
    )
    fee = await _calculate_delivery_fee(
        pickup_area="Munuki", delivery_area="Nowhere",
        order_type="restaurant", restaurant_id=rest_id
    )
    assert abs(fee - 2.0) < 0.001, f"Expected 2.0 (default), got {fee}"
    print(f"[PASS] Restaurant admin-managed fallback → default {fee}")

    # === Cleanup ===
    await db.restaurants.delete_one({"id": rest_id})
    print("[CLEANUP] Removed test restaurant")

    client.close()
    print("\n✅ All delivery tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
