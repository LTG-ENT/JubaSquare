"""
JubaSquare Object Storage (Emergent-managed, S3-compatible).

Stores all user-uploaded images (shop logos/banners, product images,
category images, homepage slides, avatars) in Emergent's persistent
object store so they survive container redeploys.

Legacy files in /app/backend/uploads/ remain readable via a graceful
disk fallback in server.py's `/api/uploads/{filename}` handler.
"""
from __future__ import annotations

import os
import logging
from typing import Optional, Tuple

import requests

log = logging.getLogger("jubasquare.storage")

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = "jubasquare"
UPLOADS_PREFIX = f"{APP_NAME}/uploads"

# Module-level session key — set once by init_storage(), reused for all calls.
_storage_key: Optional[str] = None


MIME_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp",
}


def _emergent_key() -> str:
    key = (os.environ.get("EMERGENT_LLM_KEY") or "").strip()
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY is not configured — cannot init object storage.")
    return key


def init_storage(force: bool = False) -> str:
    """Fetch (or refresh) the session-scoped storage key.

    Called once at FastAPI startup. Safe to call again if a `403 Forbidden`
    comes back — pass `force=True` to re-init.
    """
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": _emergent_key()}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    log.info("Object storage initialized (app=%s)", APP_NAME)
    return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Upload `data` to `path`. Returns the storage response (path/size/etag)."""
    key = init_storage()
    try:
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type or "application/octet-stream"},
            data=data,
            timeout=120,
        )
        if resp.status_code == 403:
            # Session key expired — re-init once and retry.
            key = init_storage(force=True)
            resp = requests.put(
                f"{STORAGE_URL}/objects/{path}",
                headers={"X-Storage-Key": key, "Content-Type": content_type or "application/octet-stream"},
                data=data,
                timeout=120,
            )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        log.error("Object storage upload failed for %s: %s", path, e)
        raise


def get_object(path: str) -> Tuple[bytes, str]:
    """Download `path`. Returns `(content_bytes, content_type)`.

    Raises `requests.exceptions.HTTPError` (404 for missing objects).
    """
    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=60,
    )
    if resp.status_code == 403:
        key = init_storage(force=True)
        resp = requests.get(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key},
            timeout=60,
        )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def guess_content_type(filename: str) -> str:
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    return MIME_TYPES.get(ext, "application/octet-stream")
