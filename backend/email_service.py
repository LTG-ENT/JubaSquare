"""
JubaSquare — lightweight Resend email helper.

Config priority (looked up on every send):
  1. Database settings doc ({id: "system"}.integrations.resend_api_key / resend_from_email)
  2. Env vars RESEND_API_KEY / SENDER_EMAIL

All send_* functions are NO-OPS when no API key is configured (dev mode).
They log a warning instead of raising, so the app keeps working.
"""

import os
import asyncio
import logging
from typing import Optional, Dict

import resend
from motor.motor_asyncio import AsyncIOMotorClient

log = logging.getLogger("jubasquare.email")

_ENV_API_KEY = (os.environ.get("RESEND_API_KEY") or "").strip()
_ENV_SENDER = (os.environ.get("SENDER_EMAIL") or "noreply@jubasquare.com").strip()

# NOTE: DO NOT capture FRONTEND_URL at module-load time — the env var may
# be empty in preview but set correctly in production. Use get_frontend_url()
# at every send so the current value is always read.
_PROD_FALLBACK = "https://jubasquare.com"


def get_frontend_url() -> str:
    """Return the public URL of the frontend, checked at call time.

    Order of resolution:
      1. FRONTEND_URL (canonical)
      2. APP_URL / SITE_URL / PUBLIC_URL (common aliases we accept for
         convenience — some hosting providers use different names)
      3. REACT_APP_BACKEND_URL as a last-resort dev fallback so preview
         email links still work end-to-end
      4. Hardcoded production domain — guarantees we NEVER emit a broken
         `http:///verify-email?...` link even when every env var is empty.
    """
    for key in ("FRONTEND_URL", "APP_URL", "SITE_URL", "PUBLIC_URL", "REACT_APP_BACKEND_URL"):
        v = (os.environ.get(key) or "").strip().rstrip("/")
        if v and v not in ("http://", "https://"):
            return v
    log.warning("No FRONTEND_URL/APP_URL/SITE_URL configured — falling back to %s", _PROD_FALLBACK)
    return _PROD_FALLBACK

# Lazy Mongo client — created on first use
_mongo_client: Optional[AsyncIOMotorClient] = None
_db_cache = None


def _get_db():
    global _mongo_client, _db_cache
    if _db_cache is None:
        _mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        _db_cache = _mongo_client[os.environ.get("DB_NAME", "jubasquare_db")]
    return _db_cache


async def get_config() -> Dict[str, str]:
    """Returns {api_key, from_email} — DB overrides env, env is fallback."""
    api_key = _ENV_API_KEY
    sender = _ENV_SENDER
    try:
        settings = await _get_db().settings.find_one({"id": "system"})
        integ = (settings or {}).get("integrations", {}) or {}
        if integ.get("resend_api_key"):
            api_key = integ["resend_api_key"].strip()
        if integ.get("resend_from_email"):
            sender = integ["resend_from_email"].strip()
    except Exception as e:
        log.warning(f"email_service: failed to read DB config, using env fallback: {e}")
    return {"api_key": api_key, "from_email": sender or "noreply@jubasquare.com"}


# --------------------------------------------------------------------
# Core send helper
# --------------------------------------------------------------------
async def send_raw(to: str, subject: str, html: str) -> Dict:
    """Low-level send. Returns {ok, id|error}."""
    cfg = await get_config()
    api_key = cfg["api_key"]
    if not api_key:
        log.info(f"[email disabled] would send to={to} subject={subject!r}")
        return {"ok": False, "error": "RESEND_API_KEY is not configured. Go to Admin → Integrations to set it."}
    resend.api_key = api_key
    try:
        params = {
            "from": cfg["from_email"],
            "to": [to],
            "subject": subject,
            "html": html,
        }
        email = await asyncio.to_thread(resend.Emails.send, params)
        eid = email.get("id") if isinstance(email, dict) else None
        log.info(f"email sent id={eid} to={to} subject={subject!r}")
        return {"ok": True, "id": eid}
    except Exception as e:
        log.error(f"email send failed to={to}: {e}")
        return {"ok": False, "error": str(e)}


async def _send(to: str, subject: str, html: str) -> Optional[str]:
    r = await send_raw(to, subject, html)
    return r.get("id") if r.get("ok") else None


# --------------------------------------------------------------------
# Branded shell
# --------------------------------------------------------------------
def _shell(title: str, body_html: str, cta_label: Optional[str] = None, cta_url: Optional[str] = None, preheader: str = "") -> str:
    btn_html = ""
    if cta_label and cta_url:
        btn_html = f"""
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:28px 0;">
          <tr><td bgcolor="#C84B31" style="border-radius:8px;">
            <a href="{cta_url}" target="_blank"
               style="display:inline-block;padding:14px 28px;font-family:Arial,sans-serif;font-size:15px;
                      font-weight:bold;color:#ffffff;text-decoration:none;border-radius:8px;">
              {cta_label}
            </a>
          </td></tr>
        </table>
        """
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title></head>
<body style="margin:0;padding:0;background:#F4F1EA;font-family:Arial,Helvetica,sans-serif;color:#1A1A1A;">
  <div style="display:none;max-height:0;overflow:hidden;">{preheader}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#F4F1EA">
    <tr><td align="center" style="padding:40px 16px;">
      <table role="presentation" width="560" cellspacing="0" cellpadding="0" border="0"
             style="max-width:560px;background:#ffffff;border-radius:14px;overflow:hidden;
                    box-shadow:0 4px 16px rgba(0,0,0,0.06);">
        <tr><td bgcolor="#0E1A2B" style="padding:22px 28px;">
          <table role="presentation" width="100%"><tr>
            <td style="color:#ffffff;font-size:20px;font-weight:bold;letter-spacing:0.5px;">JubaSquare</td>
            <td align="right" style="color:#E9C46A;font-size:10px;letter-spacing:2px;font-weight:bold;">
              BY L.T.G ENTERPRISE
            </td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:36px 32px;">
          <h1 style="margin:0 0 16px 0;font-size:22px;color:#1A1A1A;">{title}</h1>
          <div style="font-size:15px;line-height:1.65;color:#404040;">{body_html}</div>
          {btn_html}
          <p style="font-size:12px;color:#808080;margin-top:30px;line-height:1.6;">
            If you didn't request this, you can safely ignore this email.
          </p>
        </td></tr>
        <tr><td bgcolor="#F4F1EA" style="padding:18px 28px;text-align:center;font-size:11px;color:#808080;">
          © {_year()} JubaSquare — Juba's Marketplace · <a href="{get_frontend_url()}" style="color:#C84B31;text-decoration:none;">jubasquare.com</a>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _year() -> int:
    from datetime import datetime
    return datetime.utcnow().year


# --------------------------------------------------------------------
# Public send functions
# --------------------------------------------------------------------
async def send_verification_email(to: str, name: str, token: str) -> Optional[str]:
    link = f"{get_frontend_url()}/verify-email?token={token}"
    body = f"""
      <p>Hi {name or 'there'},</p>
      <p>Welcome to JubaSquare! Please confirm your email address to activate your account.</p>
    """
    html = _shell(
        title="Verify your email",
        body_html=body,
        cta_label="Verify my email",
        cta_url=link,
        preheader="Confirm your email to activate your JubaSquare account.",
    )
    return await _send(to, "Verify your JubaSquare email", html)


async def send_password_reset_email(to: str, name: str, token: str) -> Optional[str]:
    link = f"{get_frontend_url()}/reset-password?token={token}"
    body = f"""
      <p>Hi {name or 'there'},</p>
      <p>We got a request to reset your JubaSquare password. This link expires in 1 hour.</p>
    """
    html = _shell(
        title="Reset your password",
        body_html=body,
        cta_label="Reset password",
        cta_url=link,
        preheader="Reset your JubaSquare password.",
    )
    return await _send(to, "Reset your JubaSquare password", html)


async def send_order_confirmation_customer(to: str, name: str, order: dict) -> Optional[str]:
    order_id = order.get("id", "")[:8]
    total = float(order.get("total_usd", 0))
    subtotal = float(order.get("subtotal_usd", 0))
    delivery = float(order.get("delivery_fee_usd", 0))
    items_html = "".join(
        f"""<tr>
              <td style="padding:6px 0;">{it.get('quantity', 1)}× {it.get('name', 'Item')}</td>
              <td align="right" style="padding:6px 0;">${float(it.get('price_usd', 0)) * int(it.get('quantity', 1)):.2f}</td>
            </tr>"""
        for it in order.get("items", [])
    )
    body = f"""
      <p>Hi {name or 'there'},</p>
      <p>Thanks for your order! We've notified the seller(s) — you'll receive another email when your order is on its way.</p>
      <table width="100%" style="border-collapse:collapse;margin:18px 0;border:1px solid #EEE;border-radius:8px;">
        <tr><td style="padding:14px 16px;background:#F4F1EA;font-weight:bold;">Order #{order_id}</td></tr>
        <tr><td style="padding:14px 16px;">
          <table width="100%" style="font-size:14px;">{items_html}</table>
          <hr style="border:none;border-top:1px solid #EEE;margin:10px 0;">
          <table width="100%" style="font-size:14px;">
            <tr><td>Subtotal</td><td align="right">${subtotal:.2f}</td></tr>
            <tr><td>Delivery</td><td align="right">${delivery:.2f}</td></tr>
            <tr><td style="font-weight:bold;padding-top:6px;">Total</td><td align="right" style="font-weight:bold;padding-top:6px;">${total:.2f}</td></tr>
          </table>
        </td></tr>
      </table>
      <p style="font-size:13px;color:#666;">Payment method: <strong>Cash on Delivery</strong></p>
    """
    html = _shell(
        title=f"Order confirmed — #{order_id}",
        body_html=body,
        cta_label="View my orders",
        cta_url=f"{get_frontend_url()}/orders",
        preheader=f"Your order #{order_id} has been placed (${total:.2f}).",
    )
    return await _send(to, f"Order confirmed — #{order_id}", html)


async def send_order_notification_seller(to: str, seller_name: str, order: dict, shop_name: str) -> Optional[str]:
    order_id = order.get("id", "")[:8]
    body = f"""
      <p>Hi {seller_name or 'there'},</p>
      <p>You've received a new order for <strong>{shop_name}</strong>.</p>
      <p>Customer: {order.get('customer_name', '—')} · {order.get('phone', '—')}<br>
      Delivery area: {order.get('area', '—')}<br>
      Total (all shops): ${float(order.get('total_usd', 0)):.2f}</p>
    """
    html = _shell(
        title=f"New order — #{order_id}",
        body_html=body,
        cta_label="Open seller dashboard",
        cta_url=f"{get_frontend_url()}/seller",
        preheader=f"New order received for {shop_name}.",
    )
    return await _send(to, f"New order received — #{order_id}", html)
