# RCA — run ebecb026-2dae-4abb-8f98-0ef591515d10 (shipping-fee-system)

## Symptom
Redeploy failed at `deploy_k8s` → pods never became ready → `health_check` never ran. Backend crashes on startup in a loop; nginx then returns `connect() failed (111: Connection refused)` on `/health`, so K8s times out waiting for the deployment to be ready.

## Root cause (verified)
The FastAPI backend aborts during startup (`on_startup` → `seed_production()`), on the very first write:

```
File "/app/backend/server.py", line 8291, in seed_production
    await db.users.create_index("email", unique=True)
pymongo.errors.OperationFailure: not authorized on jubasquare to execute command
{ createIndexes: "users", ... }, 'code': 13, 'codeName': 'Unauthorized', '$db': "jubasquare"
```

The app connected to a MongoDB database literally named **`jubasquare`**, and the authenticated Mongo user is **not authorized** on that database (`code 13 Unauthorized`). `Application startup failed. Exiting.` → the container dies → CrashLoop.

### Why the DB name is wrong
- DB selection in `backend/server.py`:
  ```python
  load_dotenv(ROOT_DIR / ".env")          # line 5 — loads the .env BAKED INTO the image
  mongo_url = os.environ["MONGO_URL"]      # line 56
  db = client[os.environ["DB_NAME"]]       # line 58
  ```
- The preview `backend/.env` is shipped inside the image (`COPY . /app`) and contains:
  ```
  MONGO_URL="mongodb+srv://Admin:...@jubasquare-database.llu96aj.mongodb.net/..."
  DB_NAME="jubasquare"
  ```
- The **actual production database** (verified live with a read-only `list_collections` against the last SUCCESSFUL run e738240e) is **`shipping-fee-system-jubasquare`** — 28 collections with real data (users, orders, products, restaurants, invoices, …). That is the Emergent-managed/provisioned DB the healthy app has always used.
- This failed run instead talked to db **`jubasquare`**, which is the value from the baked `.env` — NOT the provisioned production DB name. The Mongo user has no rights on `jubasquare`, so the first `create_index` throws `Unauthorized` and startup aborts.

### Why it regressed now (not on prior deploys)
Prior images deployed fine with the same provisioned DB. This run's new source added a startup seeding routine (`seed_production()` at server.py:8291, invoked from `on_startup` at server.py:8500) that issues **index-creation (write) commands against the DB during startup**. Combined with the app resolving `DB_NAME` to `jubasquare` instead of `shipping-fee-system-jubasquare`, the first privileged write now hard-fails and takes the whole process down. Earlier builds either didn't seed indexes on boot or weren't resolving to the `jubasquare` name.

## Verified vs inferred
- VERIFIED: the crashing call, the `Unauthorized`/`$db: "jubasquare"` error, the DB-selection code + baked `.env` values, and that the real production DB is `shipping-fee-system-jubasquare` (28 collections, confirmed via read-only mongo query on the active run).
- INFERRED: the exact reason this run's container ended up with `DB_NAME=jubasquare` rather than the provisioned name. `load_dotenv()` defaults to `override=False`, so an injected `DB_NAME` should win — meaning either the platform `DB_NAME` secret was not present/effective for this run, or it has been changed to `jubasquare`. The deployed secret values on a failed run are not inspectable from the deployer tools, so this one link is not independently confirmed.
- NOT REPRODUCIBLE in the eph sandbox: no production secrets are injected there, so the authenticated-but-unauthorized condition against the real Atlas cannot be exercised. This is a DB/secret-class fault, diagnosed from logs + a live read of the production DB — not sandbox-reproduced.

## Fix (hand-off)

### A. Code (E1 applies in source) — remove the ambiguity so prod DB selection is deterministic
1. **Stop shipping a conflicting `backend/.env` into the image.** The baked file carries the user's external Atlas `MONGO_URL` and `DB_NAME="jubasquare"`, which can shadow/stand in for the platform-provisioned production values. Options (pick one):
   - Remove `MONGO_URL`/`DB_NAME` from `backend/.env`, OR
   - Exclude `.env` from the deployed image so only platform-injected secrets are used.
   This guarantees the app can never silently fall back to db `jubasquare`.
2. **Harden `seed_production()`** (defense-in-depth): wrap the `create_index` calls so a permission/transient error is logged and does NOT abort `on_startup` (today a single failed index call kills the whole backend and fails the deploy).

### B. Secrets (User, Deployment Panel → Secrets) — confirm the production DB identity
- Ensure `DB_NAME = shipping-fee-system-jubasquare` (the provisioned prod DB that holds the real data), and `MONGO_URL` points at the Emergent-managed connection string the healthy app has been using — NOT the external `jubasquare-database.llu96aj.mongodb.net` from the preview `.env`. Save, then redeploy.
- If the app is intentionally meant to use the user's OWN Atlas (`jubasquare-database...`), then the `Admin` user on that cluster must be granted `readWrite` on database `jubasquare` (an Atlas / third-party action) — but note the live production data currently lives in `shipping-fee-system-jubasquare`, so switching clusters/DB names would also require migrating that data.

## Why I did not re-run resume_pipeline
Nothing I can re-run changes the outcome: the image + preserved secrets are identical, so a rebuild crashes on the same `create_index` Unauthorized. There is no manifest defect to correct, and I have no tool to edit secrets. Fix belongs to E1 (code) and the user (secrets), after which a redeploy will pass.
