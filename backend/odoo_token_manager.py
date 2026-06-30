"""
Odoo Service Token Manager

Stores ONLY a SHA-256 hash of the raw token in MongoDB. The raw token is shown
to the admin exactly once when generated/rotated and never persisted. Webhook
calls present the raw token via the `X-JubaSquare-Odoo-Token` header; the
manager hashes the incoming value and compares against the active record.

Also supports `.env` ODOO_WEBHOOK_TOKEN as a fallback so existing deployments
keep working until an admin generates a DB-managed token.
"""
import os
import hmac
import hashlib
import secrets
import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

ENV_TOKEN = os.environ.get("ODOO_WEBHOOK_TOKEN", "")


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _mask(raw: str) -> str:
    """Return a masked preview that NEVER leaks more than 4 trailing chars."""
    if not raw:
        return ""
    tail = raw[-4:] if len(raw) >= 4 else raw
    return "*" * 12 + tail


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_raw_token() -> str:
    """Cryptographically secure 64-char hex token."""
    return secrets.token_hex(32)


class OdooTokenManager:
    """Thin wrapper around the `odoo_service_tokens` collection."""

    def __init__(self, db):
        self.db = db
        self.collection = db.odoo_service_tokens

    async def get_active(self) -> Optional[dict]:
        """Return the currently active token record (or None)."""
        return await self.collection.find_one({"is_active": True}, {"_id": 0})

    async def get_status(self) -> dict:
        """
        Return safe metadata about the active token for the admin UI.
        Never returns the raw token or its hash.
        """
        record = await self.get_active()
        if record:
            return {
                "status": "active",
                "source": "database",
                "masked_preview": record.get("masked_preview", ""),
                "created_at": record.get("created_at"),
                "last_rotated_at": record.get("last_rotated_at"),
                "created_by": record.get("created_by_email"),
            }
        if ENV_TOKEN:
            return {
                "status": "active",
                "source": "env",
                "masked_preview": _mask(ENV_TOKEN),
                "created_at": None,
                "last_rotated_at": None,
                "created_by": None,
            }
        return {
            "status": "not_generated",
            "source": None,
            "masked_preview": "",
            "created_at": None,
            "last_rotated_at": None,
            "created_by": None,
        }

    async def generate(self, admin_email: str) -> dict:
        """
        Create a new active token. If one already exists, returns an error
        signal — the caller should call rotate() instead.
        Returns {"raw_token": "...", "masked_preview": "...", ...}.
        """
        existing = await self.get_active()
        if existing:
            return {"error": "already_exists"}

        raw = generate_raw_token()
        record = {
            "token_hash": _sha256(raw),
            "masked_preview": _mask(raw),
            "is_active": True,
            "created_at": _now(),
            "last_rotated_at": None,
            "created_by_email": admin_email,
        }
        await self.collection.insert_one(record)
        return {
            "raw_token": raw,
            "masked_preview": record["masked_preview"],
            "created_at": record["created_at"],
            "last_rotated_at": None,
        }

    async def rotate(self, admin_email: str) -> dict:
        """
        Mark every existing token inactive and create a brand-new active one.
        After rotation any previously-issued token stops working immediately.
        Returns the new raw token (shown once).
        """
        await self.collection.update_many(
            {"is_active": True},
            {"$set": {"is_active": False, "rotated_out_at": _now()}},
        )
        raw = generate_raw_token()
        now = _now()
        record = {
            "token_hash": _sha256(raw),
            "masked_preview": _mask(raw),
            "is_active": True,
            "created_at": now,
            "last_rotated_at": now,
            "created_by_email": admin_email,
        }
        await self.collection.insert_one(record)
        return {
            "raw_token": raw,
            "masked_preview": record["masked_preview"],
            "created_at": now,
            "last_rotated_at": now,
        }

    async def verify(self, presented_token: str) -> bool:
        """
        Constant-time comparison of presented token against the active DB hash.
        Falls back to env ODOO_WEBHOOK_TOKEN only when no DB token is active.
        """
        if not presented_token:
            return False

        presented_hash = _sha256(presented_token)

        record = await self.get_active()
        if record:
            return hmac.compare_digest(presented_hash, record["token_hash"])

        # Fallback: env token (constant-time compare)
        if ENV_TOKEN:
            return hmac.compare_digest(presented_token, ENV_TOKEN)

        return False

    async def is_configured(self) -> bool:
        """True if either a DB token or env token exists."""
        if await self.get_active():
            return True
        return bool(ENV_TOKEN)
