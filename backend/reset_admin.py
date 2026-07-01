"""One-shot admin password reset (development only).
Reads ADMIN_EMAIL / ADMIN_PASSWORD from env and force-updates the admin user's
password_hash so we can log back in. Also sets username to ADMIN_USERNAME or 'admin'.
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def main():
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    admin_email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD") or "1234"
    admin_username = (os.environ.get("ADMIN_USERNAME") or "admin").strip().lower()

    if not admin_email:
        print("ADMIN_EMAIL not set")
        return

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        print(f"No user for {admin_email}; nothing to reset (startup seed will create one).")
        return

    await db.users.update_one(
        {"email": admin_email},
        {
            "$set": {
                "password_hash": hash_password(admin_password),
                "role": "admin",
                "email_verified": True,
                "is_active": True,
                "must_change_password": False,
                "username": admin_username,
            }
        },
    )
    print(f"Reset password for {admin_email} (username: {admin_username})")


if __name__ == "__main__":
    asyncio.run(main())
