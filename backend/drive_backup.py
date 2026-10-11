"""Automatic database backups to the admin's Google Drive (OAuth, drive.file scope)."""
import asyncio
import base64
import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

log = logging.getLogger("drive_backup")

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]
REQUIRED_SCOPE = "https://www.googleapis.com/auth/drive.file"
FOLDER_NAME = "JubaSquare Backups"
KEEP_LAST = 14
CONFIG_ID = "default"
SKIP_COLLECTIONS = {"drive_backup_config", "drive_oauth_states"}


class ScheduleIn(BaseModel):
    enabled: bool
    frequency: Literal["daily", "weekly"] = "daily"


class ConnectIn(BaseModel):
    origin: str


def _fernet() -> Fernet:
    key = hashlib.sha256(("drive-backup:" + os.environ["JWT_SECRET"]).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _enc(v: Optional[str]) -> Optional[str]:
    return _fernet().encrypt(v.encode()).decode() if v else None


def _dec(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    try:
        return _fernet().decrypt(v.encode()).decode()
    except InvalidToken:
        return None


def _client_config(redirect_uri: str) -> dict:
    return {"web": {
        "client_id": os.environ.get("GOOGLE_DRIVE_CLIENT_ID"),
        "client_secret": os.environ.get("GOOGLE_DRIVE_CLIENT_SECRET"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [redirect_uri],
    }}


def register(api, db, require_role, now_iso, create_notification, build_backup_payload):
    admin_dep = Depends(require_role("admin"))

    async def _config() -> dict:
        return await db.drive_backup_config.find_one({"id": CONFIG_ID}, {"_id": 0}) or {}

    async def _credentials():
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GoogleRequest
        cfg = await _config()
        refresh = _dec(cfg.get("refresh_token"))
        if not refresh:
            raise RuntimeError("Google Drive is not connected")
        creds = Credentials(
            token=_dec(cfg.get("access_token")), refresh_token=refresh,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ.get("GOOGLE_DRIVE_CLIENT_ID"),
            client_secret=os.environ.get("GOOGLE_DRIVE_CLIENT_SECRET"),
            scopes=SCOPES,
        )
        if not creds.valid:
            await asyncio.to_thread(creds.refresh, GoogleRequest())
            await db.drive_backup_config.update_one({"id": CONFIG_ID}, {"$set": {
                "access_token": _enc(creds.token), "updated_at": now_iso()}})
        return creds

    def _upload_and_prune(creds, folder_id: Optional[str], name: str, body: bytes) -> dict:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload
        svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        if folder_id:
            try:
                f = svc.files().get(fileId=folder_id, fields="id,trashed").execute()
                if f.get("trashed"):
                    folder_id = None
            except Exception:
                folder_id = None
        if not folder_id:
            folder_id = svc.files().create(
                body={"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}, fields="id",
            ).execute()["id"]
        media = MediaIoBaseUpload(io.BytesIO(body), mimetype="application/json", resumable=True, chunksize=8 * 1024 * 1024)
        created = svc.files().create(
            body={"name": name, "parents": [folder_id]}, media_body=media, fields="id,name,size,webViewLink",
        ).execute()
        files = svc.files().list(
            q=f"'{folder_id}' in parents and trashed=false and mimeType='application/json'",
            orderBy="createdTime desc", fields="files(id,name)", pageSize=200,
        ).execute().get("files", [])
        deleted = 0
        for old in files[KEEP_LAST:]:
            try:
                svc.files().delete(fileId=old["id"]).execute()
                deleted += 1
            except Exception as e:
                log.warning(f"drive prune failed for {old.get('name')}: {e}")
        return {"folder_id": folder_id, "file": created, "pruned": deleted}

    async def _alert_admins(msg: str):
        admins = await db.users.find({"role": "admin"}, {"_id": 0, "id": 1}).to_list(50)
        for a in admins:
            try:
                await create_notification(user_id=a["id"], message=msg, ntype="alert",
                                          meta={"link": "/admin?tab=settings"})
            except Exception:
                pass

    async def run_backup(run_id: str):
        try:
            creds = await _credentials()
            payload = await build_backup_payload()
            body = json.dumps(payload, default=str).encode()
            name = f"jubasquare-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
            cfg = await _config()
            res = await asyncio.to_thread(_upload_and_prune, creds, cfg.get("folder_id"), name, body)
            await db.drive_backup_config.update_one({"id": CONFIG_ID}, {"$set": {
                "folder_id": res["folder_id"], "last_success_at": now_iso()}})
            await db.drive_backup_runs.update_one({"id": run_id}, {"$set": {
                "status": "success", "finished_at": now_iso(), "file_name": name,
                "size_bytes": len(body), "drive_file_id": res["file"].get("id"),
                "web_link": res["file"].get("webViewLink"), "pruned": res["pruned"],
            }})
        except Exception as e:
            err = str(e)[:500]
            if "invalid_grant" in err:
                err = "Google Drive access expired or was revoked. Please reconnect Google Drive."
            log.error(f"drive backup {run_id} failed: {err}")
            await db.drive_backup_runs.update_one({"id": run_id}, {"$set": {
                "status": "failed", "finished_at": now_iso(), "error": err}})
            await _alert_admins(f"Google Drive backup FAILED: {err[:160]}")

    async def _start_run(trigger: str) -> Optional[str]:
        stale = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        if await db.drive_backup_runs.find_one({"status": "running", "started_at": {"$gt": stale}}):
            return None
        run_id = str(uuid.uuid4())
        await db.drive_backup_runs.insert_one({"id": run_id, "status": "running", "trigger": trigger, "started_at": now_iso()})
        return run_id

    @api.get("/admin/drive-backup/status")
    async def drive_status(_: dict = admin_dep):
        cfg = await _config()
        runs = await db.drive_backup_runs.find({}, {"_id": 0}).sort("started_at", -1).to_list(20)
        return {
            "configured": bool(os.environ.get("GOOGLE_DRIVE_CLIENT_ID") and os.environ.get("GOOGLE_DRIVE_CLIENT_SECRET")),
            "connected": bool(_dec(cfg.get("refresh_token"))),
            "account_email": cfg.get("account_email"),
            "connected_at": cfg.get("connected_at"),
            "enabled": bool(cfg.get("enabled", False)),
            "frequency": cfg.get("frequency", "daily"),
            "last_success_at": cfg.get("last_success_at"),
            "keep_last": KEEP_LAST,
            "folder_name": FOLDER_NAME,
            "runs": runs,
        }

    @api.post("/admin/drive-backup/connect")
    async def drive_connect(body: ConnectIn, user: dict = admin_dep):
        from google_auth_oauthlib.flow import Flow
        if not os.environ.get("GOOGLE_DRIVE_CLIENT_ID"):
            raise HTTPException(400, "Google Drive client credentials are not configured")
        origin = body.origin.rstrip("/")
        if not origin.startswith("https://"):
            raise HTTPException(400, "Invalid origin")
        redirect_uri = f"{origin}/api/oauth/drive/callback"
        flow = Flow.from_client_config(_client_config(redirect_uri), scopes=SCOPES, redirect_uri=redirect_uri)
        state = secrets.token_urlsafe(24)
        url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent", state=state)
        await db.drive_oauth_states.insert_one({
            "state": state, "admin_id": user["id"], "origin": origin, "redirect_uri": redirect_uri,
            "code_verifier": getattr(flow, "code_verifier", None), "created_at": now_iso(),
        })
        return {"authorization_url": url, "redirect_uri": redirect_uri}

    @api.get("/oauth/drive/callback")
    async def drive_callback(state: str = Query(...), code: Optional[str] = None, error: Optional[str] = None):
        from google_auth_oauthlib.flow import Flow
        st = await db.drive_oauth_states.find_one_and_delete({"state": state})
        if not st:
            raise HTTPException(400, "Invalid or expired OAuth state")
        back = f"{st['origin']}/admin?tab=settings"
        if error or not code:
            return RedirectResponse(f"{back}&drive=error")
        try:
            flow = Flow.from_client_config(_client_config(st["redirect_uri"]), scopes=None, redirect_uri=st["redirect_uri"])
            if st.get("code_verifier"):
                flow.code_verifier = st["code_verifier"]
            await asyncio.to_thread(flow.fetch_token, code=code)
            creds = flow.credentials
            if REQUIRED_SCOPE not in set(creds.scopes or []):
                return RedirectResponse(f"{back}&drive=scope")
            email = None
            try:
                from googleapiclient.discovery import build
                info = await asyncio.to_thread(
                    lambda: build("oauth2", "v2", credentials=creds, cache_discovery=False).userinfo().get().execute())
                email = info.get("email")
            except Exception:
                pass
            cfg = await _config()
            update = {
                "id": CONFIG_ID, "access_token": _enc(creds.token), "account_email": email,
                "connected_at": now_iso(), "connected_by": st["admin_id"], "updated_at": now_iso(),
            }
            if creds.refresh_token:
                update["refresh_token"] = _enc(creds.refresh_token)
            if cfg.get("account_email") and cfg.get("account_email") != email:
                update["folder_id"] = None
            await db.drive_backup_config.update_one({"id": CONFIG_ID}, {"$set": update}, upsert=True)
            return RedirectResponse(f"{back}&drive=connected")
        except Exception as e:
            log.error(f"drive oauth callback failed: {e}")
            return RedirectResponse(f"{back}&drive=error")

    @api.post("/admin/drive-backup/disconnect")
    async def drive_disconnect(_: dict = admin_dep):
        await db.drive_backup_config.update_one({"id": CONFIG_ID}, {"$set": {
            "refresh_token": None, "access_token": None, "account_email": None, "enabled": False,
            "folder_id": None, "updated_at": now_iso()}})
        return {"ok": True}

    @api.put("/admin/drive-backup/schedule")
    async def drive_schedule(body: ScheduleIn, _: dict = admin_dep):
        cfg = await _config()
        if body.enabled and not _dec(cfg.get("refresh_token")):
            raise HTTPException(400, "Connect Google Drive first")
        await db.drive_backup_config.update_one({"id": CONFIG_ID}, {"$set": {
            "id": CONFIG_ID, "enabled": body.enabled, "frequency": body.frequency, "updated_at": now_iso()}}, upsert=True)
        return {"ok": True, "enabled": body.enabled, "frequency": body.frequency}

    @api.post("/admin/drive-backup/run")
    async def drive_run_now(background_tasks: BackgroundTasks, _: dict = admin_dep):
        cfg = await _config()
        if not _dec(cfg.get("refresh_token")):
            raise HTTPException(400, "Connect Google Drive first")
        run_id = await _start_run("manual")
        if not run_id:
            raise HTTPException(409, "A backup is already running")
        background_tasks.add_task(run_backup, run_id)
        return {"ok": True, "run_id": run_id}

    @api.post("/cron/drive-backup")
    async def cron_drive_backup(request: Request, background_tasks: BackgroundTasks):
        # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
        secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
        auth = request.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        if not secret or not hmac.compare_digest(token, secret):
            raise HTTPException(401, "Unauthorized")
        webhook_id = request.headers.get("X-Webhook-Id")
        if webhook_id and await db.drive_backup_runs.find_one({"webhook_id": webhook_id}):
            return {"ok": True, "duplicate": True}
        cfg = await _config()
        if not cfg.get("enabled") or not _dec(cfg.get("refresh_token")):
            return {"ok": True, "skipped": "disabled"}
        min_gap = timedelta(hours=20) if cfg.get("frequency", "daily") == "daily" else timedelta(days=6, hours=20)
        last = cfg.get("last_success_at")
        if last and datetime.fromisoformat(last) > datetime.now(timezone.utc) - min_gap:
            return {"ok": True, "skipped": "not_due"}
        run_id = await _start_run("scheduled")
        if not run_id:
            return {"ok": True, "skipped": "running"}
        if webhook_id:
            await db.drive_backup_runs.update_one({"id": run_id}, {"$set": {"webhook_id": webhook_id}})
        background_tasks.add_task(run_backup, run_id)
        return {"ok": True, "queued": True, "run_id": run_id}
