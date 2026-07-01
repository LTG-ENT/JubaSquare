"""One-shot migrator: copies every collection from a source Mongo (container-local)
to a target Mongo (Atlas). Safe to re-run — for each doc it upserts by `id` field
(or by `_id` if `id` is absent).
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

SOURCE_URL = "mongodb://localhost:27017"
SOURCE_DB = "jubasquare"

TARGET_URL = "mongodb+srv://Admin:Kokob1234567890@jubasquare-database.llu96aj.mongodb.net/?appName=JubaSquare-Database&compressors=zlib"
TARGET_DB = "jubasquare"


async def main():
    src_c = AsyncIOMotorClient(SOURCE_URL)
    tgt_c = AsyncIOMotorClient(TARGET_URL, serverSelectionTimeoutMS=20000)
    src = src_c[SOURCE_DB]
    tgt = tgt_c[TARGET_DB]

    await tgt_c.admin.command("ping")
    print(f"✅ Connected to Atlas: {TARGET_DB}")

    collections = await src.list_collection_names()
    if not collections:
        print("⚠️  Source has no collections. Nothing to migrate.")
        return

    total = 0
    for name in collections:
        if name.startswith("system."):
            continue
        src_col = src[name]
        tgt_col = tgt[name]
        docs = await src_col.find({}).to_list(100000)
        count = 0
        for doc in docs:
            # Prefer domain-level `id` (UUID we generate) over Mongo `_id`.
            if "id" in doc:
                key = {"id": doc["id"]}
                doc_no_underscore = {k: v for k, v in doc.items() if k != "_id"}
                await tgt_col.update_one(key, {"$set": doc_no_underscore}, upsert=True)
            else:
                # Fall back to Mongo _id as the unique key.
                _id = doc.get("_id")
                doc_no_underscore = {k: v for k, v in doc.items() if k != "_id"}
                if doc_no_underscore:  # empty doc guard
                    await tgt_col.update_one({"_id": _id}, {"$set": doc_no_underscore}, upsert=True)
                else:
                    await tgt_col.update_one({"_id": _id}, {"$setOnInsert": {"_id": _id}}, upsert=True)
            count += 1
        total += count
        print(f"  • {name}: copied {count} doc(s)")

    print(f"\n✅ Migration complete: {total} documents across {len(collections)} collection(s).")
    print("You can now switch MONGO_URL in /app/backend/.env to the Atlas URL and restart backend.")


if __name__ == "__main__":
    asyncio.run(main())
