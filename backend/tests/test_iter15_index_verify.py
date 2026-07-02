"""Verify partial unique index on reviews.order_id and dedupe behavior."""
import os
import asyncio
import requests
import pytest
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip('/')
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def test_partial_index_exists():
    async def _run():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        info = await db.reviews.index_information()
        assert 'order_id_1' in info, f"order_id_1 index missing. Indexes: {list(info.keys())}"
        idx = info['order_id_1']
        assert 'partialFilterExpression' in idx, f"Index is not partial: {idx}"
        client.close()
    asyncio.run(_run())


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_product_review_twice_both_succeed():
    """Two product reviews back-to-back should both succeed (no order_id -> partial index skips)."""
    token = _login("admin@jubasquare.com", "1234")
    headers = {"Authorization": f"Bearer {token}"}

    # Get any product
    r = requests.get(f"{BASE_URL}/api/products", headers=headers)
    assert r.status_code == 200
    products = r.json()
    if not products:
        pytest.skip("No products available")
    pid = products[0].get("id") or products[0].get("_id")

    payload = {"rating": 5, "comment": "TEST_iter15_retest review", "photos": []}
    r1 = requests.post(f"{BASE_URL}/api/products/{pid}/reviews", json=payload, headers=headers)
    r2 = requests.post(f"{BASE_URL}/api/products/{pid}/reviews", json=payload, headers=headers)
    assert r1.status_code == 200, f"first: {r1.status_code} {r1.text}"
    assert r2.status_code == 200, f"second: {r2.status_code} {r2.text}"

    # Cleanup
    async def _cleanup():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        await db.reviews.delete_many({"comment": "TEST_iter15_retest review"})
        client.close()
    asyncio.run(_cleanup())
