from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal, Dict

import bcrypt
import jwt
import secrets
import re
from pathlib import Path as _FsPath
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, field_validator

import email_service
import cod

# Given a shop OR restaurant dict, decide whether the seller (who owns it)
# also handles delivery. When True, the seller IS the driver for orders on
# this entity and must see customer phone/address/area to deliver.
# When False, the platform's driver pool handles delivery and customer
# contact info stays redacted from the seller for privacy.
async def _seller_manages_delivery_for(shop=None, restaurant=None) -> bool:
    entity = shop or restaurant or {}
    managed_by = entity.get("delivery_managed_by") or "default"
    if managed_by == "seller":
        return True
    if managed_by == "admin":
        return False
    # "default" — follow the platform-wide toggle.
    sysettings = await db.settings.find_one({"id": "system"}, {"_id": 0}) or {}
    return not bool(sysettings.get("admin_manages_delivery", False))
import odoo_routes
import storage
from pages_seed import PAGES_DEFAULT, PAGE_SLUGS
from footer_seed import FOOTER_DEFAULT
from categories_seed import CATEGORIES_DEFAULT, CATEGORY_GROUPS


# ----------------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_DAYS = 7

app = FastAPI(title="JubaSquare API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("jubasquare")

DEFAULT_AREAS = ["Munuki", "Jebel", "Gudele", "Konyo Konyo", "Hai Cinema", "Nyakuron", "Atlabara"]

DEFAULT_HERO_SLIDES = [
    {
        "label": "Retail",
        "key": "slideRetail",
        "image_url": "https://images.unsplash.com/photo-1604719312566-8912e9227c6a?w=1600&q=80&auto=format&fit=crop",
    },
    {
        "label": "Wholesale",
        "key": "slideWholesale",
        "image_url": "https://images.unsplash.com/photo-1553413077-190dd305871c?w=1600&q=80&auto=format&fit=crop",
    },
    {
        "label": "Food",
        "key": "slideFood",
        "image_url": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=1600&q=80&auto=format&fit=crop",
    },
]

DEFAULT_HOMEPAGE = {
    "hero_slides": DEFAULT_HERO_SLIDES,
    "hero_tagline": "",   # empty => use i18n default
    "hero_title": "",
    "hero_subtitle": "",
    "announcement_bar": {"enabled": False, "text": "", "link": ""},
}

DEFAULT_SETTINGS = {
    "id": "system",
    "global_rate": 600.0,
    "currency_display": True,
    "auto_approve_shops": False,
    "require_verification": True,
    "allow_suspension": True,
    "verified_first": True,
    "require_doc_for_verification": False,
    "module_marketplace": True,
    "module_restaurants": True,
    "module_wholesale": True,
    "maintenance_mode": False,
    "login_attempt_limit": 5,
    "commission_rate": 0.10,
    # If TRUE → admin's Delivery Pricing rules apply to all orders.
    # If FALSE (default) → the seller's own shop-level delivery settings
    # (delivery_mode/delivery_fee_usd/delivery_per_area) are used, with the
    # admin's rules as a fallback only when the shop hasn't configured any.
    "admin_manages_delivery": False,
    "areas": DEFAULT_AREAS,
    "token_version": 1,
    "homepage": DEFAULT_HOMEPAGE,
    "message_filter": {
        "enabled": True,
        "blocked_words": ["spam", "scam", "fake"],  # Words to block
        "block_numbers": False,  # Block all numbers
        "max_numbers_per_message": 3,  # Maximum numbers allowed in one message
        "block_phone_patterns": True,  # Block phone number patterns
        "blocked_country_codes": ["+1", "+44", "+234", "+254", "+256"],  # Block specific country codes
    },
}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


async def get_settings() -> dict:
    s = await db.settings.find_one({"id": "system"}, {"_id": 0})
    return s or DEFAULT_SETTINGS


async def filter_message_content(text: str) -> tuple[bool, str]:
    """
    Check message against filter rules.
    Returns: (is_valid, error_message)
    """
    settings = await get_settings()
    filter_config = settings.get("message_filter", {})
    
    if not filter_config.get("enabled", True):
        return True, ""
    
    text_lower = text.lower()
    
    # Check blocked words
    blocked_words = filter_config.get("blocked_words", [])
    for word in blocked_words:
        if word.lower() in text_lower:
            return False, f"Message contains blocked word: '{word}'"
    
    # Count numbers in message
    numbers = re.findall(r'\d+', text)
    
    # Check if all numbers should be blocked
    if filter_config.get("block_numbers", False) and numbers:
        return False, "Numbers are not allowed in messages"
    
    # Check max numbers per message
    max_numbers = filter_config.get("max_numbers_per_message", 999)
    if len(numbers) > max_numbers:
        return False, f"Too many numbers in message (max {max_numbers} allowed)"
    
    # Check for phone number patterns
    if filter_config.get("block_phone_patterns", True):
        # Pattern: sequences of 7+ digits, optionally with spaces, dashes, or parentheses
        phone_patterns = [
            r'\d{7,}',  # 7 or more consecutive digits
            r'\d{3}[-\s]?\d{3}[-\s]?\d{4}',  # 555-123-4567 or 555 123 4567
            r'\(\d{3}\)[-\s]?\d{3}[-\s]?\d{4}',  # (555) 123-4567
        ]
        for pattern in phone_patterns:
            if re.search(pattern, text):
                return False, "Phone numbers are not allowed in messages"
    
    # Check for blocked country codes
    blocked_codes = filter_config.get("blocked_country_codes", [])
    for code in blocked_codes:
        if code in text:
            return False, f"Country code {code} is not allowed in messages"
    
    return True, ""


async def _rate_by_seller(seller_ids: list[str]) -> tuple[dict[str, float], float]:
    """Return ({seller_id: rate}, global_rate) for the given seller ids."""
    settings = await get_settings()
    global_rate = float(settings.get("global_rate", 600.0))
    if not seller_ids:
        return {}, global_rate
    rate_records = await db.exchange_rates.find(
        {"seller_id": {"$in": list({sid for sid in seller_ids if sid})}},
        {"_id": 0},
    ).to_list(2000)
    return (
        {r["seller_id"]: float(r.get("rate", global_rate)) for r in rate_records},
        global_rate,
    )



def effective_price_usd(item_doc: dict) -> float:
    """Return the price after applying an ACTIVE promo (if any) — otherwise
    the raw price_usd. Used by BOTH product and menu_item schemas since the
    Promo shape is identical. Never returns a negative price.

    Called by the order-create endpoints AFTER looking up the item from the
    DB, so a crafted client can't send a fake promo price.
    """
    raw = float(item_doc.get("price_usd", 0) or 0)
    promo = item_doc.get("promo") or {}
    if not promo.get("active"):
        return raw
    now_i = now_iso()
    starts = promo.get("starts_at")
    ends = promo.get("ends_at")
    if starts and now_i < starts:
        return raw
    if ends and now_i > ends:
        return raw
    ptype = promo.get("type", "percent")
    pval = float(promo.get("value", 0) or 0)
    if ptype == "percent":
        # Belt-and-braces clamp: even if a legacy doc stored value>100,
        # never charge the customer a negative amount.
        pval = min(100.0, max(0.0, pval))
        return max(0.0, round(raw * (1 - pval / 100.0), 4))
    # amount
    return max(0.0, round(raw - max(0.0, pval), 4))


def promo_is_live(promo: dict | None) -> bool:
    """Whether a promo is currently active + within date window."""
    if not promo or not promo.get("active"):
        return False
    now_i = now_iso()
    starts = promo.get("starts_at")
    ends = promo.get("ends_at")
    if starts and now_i < starts:
        return False
    if ends and now_i > ends:
        return False
    return True


async def enrich_marketplace_orders(orders: list[dict]) -> list[dict]:
    """Attach per-item `exchange_rate_ssp` (seller-specific) to each item so the
    customer/driver/seller UIs can format line totals using the right rate.
    Falls back to the global rate when the seller has no override.
    Also attaches `exchange_rate_ssp` to the ORDER itself using the primary
    (first) seller's rate — used by frontend to convert delivery fee + totals."""
    if not orders:
        return orders
    all_item_ids = {it.get("item_id") for o in orders for it in (o.get("items") or []) if it.get("item_id")}
    if not all_item_ids:
        return orders
    products = await db.products.find(
        {"id": {"$in": list(all_item_ids)}},
        {"_id": 0, "id": 1, "seller_id": 1},
    ).to_list(5000)
    seller_by_item = {p["id"]: p.get("seller_id") for p in products}
    rates, global_rate = await _rate_by_seller(list({sid for sid in seller_by_item.values() if sid}))
    for o in orders:
        primary_rate = None
        for it in (o.get("items") or []):
            seller_id = seller_by_item.get(it.get("item_id"))
            rate = rates.get(seller_id, global_rate) if seller_id else global_rate
            it["exchange_rate_ssp"] = rate
            if primary_rate is None:
                primary_rate = rate
        # Order-level rate = the first item's seller rate (typical single-shop
        # flow). Multi-seller orders share one delivery display; the primary
        # rate is a reasonable default for the aggregate delivery/total.
        o["exchange_rate_ssp"] = primary_rate if primary_rate is not None else global_rate
    return orders


async def enrich_restaurant_orders(orders: list[dict]) -> list[dict]:
    """Attach `exchange_rate_ssp` (seller of the restaurant) to each restaurant
    order and each of its items."""
    if not orders:
        return orders
    rest_ids = list({o.get("restaurant_id") for o in orders if o.get("restaurant_id")})
    rests = await db.restaurants.find(
        {"id": {"$in": rest_ids}},
        {"_id": 0, "id": 1, "seller_id": 1},
    ).to_list(2000)
    seller_by_rest = {r["id"]: r.get("seller_id") for r in rests}
    rates, global_rate = await _rate_by_seller(list({sid for sid in seller_by_rest.values() if sid}))
    for o in orders:
        seller_id = seller_by_rest.get(o.get("restaurant_id"))
        rate = rates.get(seller_id, global_rate) if seller_id else global_rate
        o["exchange_rate_ssp"] = rate
        for it in (o.get("items") or []):
            it["exchange_rate_ssp"] = rate
    return orders


async def create_notification(user_id: str, message: str, ntype: str = "alert", meta: Optional[dict] = None, push_category: Optional[str] = None, push_url: Optional[str] = None, push_title: Optional[str] = None) -> dict:
    """Insert an in-app notification for a single user and (best-effort) fire a Web Push.

    push_category: one of "orders" | "low_stock" | "promo" | "delivery" | "admin".
        If provided, we attempt to send a Web Push with the same message. If None, no push is sent.
    push_url: deep-link URL to open when the user clicks the push (defaults to "/" or the meta.link).
    push_title: title on the push. Defaults to "JubaSquare".
    """
    notif = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "message": message,
        "type": ntype,
        "meta": meta or {},
        "is_read": False,
        "created_at": now_iso(),
    }
    await db.notifications.insert_one(notif)
    notif.pop("_id", None)

    # Best-effort Web Push (fire-and-forget; failures are logged inside the helper).
    # If push_category isn't explicitly provided, infer from ntype so existing call
    # sites automatically get web-push behaviour on top of in-app.
    if push_category is None:
        push_category = {
            "order": "orders",
            "delivery": "delivery",
            "commission": "orders",
            "low_stock": "low_stock",
            "promo": "promo",
        }.get(ntype, "admin")
    try:
        await send_web_push_to_user(
            user_id,
            {
                "title": push_title or "JubaSquare",
                "body": message[:180],
                "url": push_url or (meta or {}).get("link") or "/",
                "tag": notif["id"],
            },
            category=push_category,
        )
    except Exception as e:
        log.warning(f"push notif failed: {e}")

    return notif


def _parse_iso(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


async def _generate_seller_unpaid_reminders(seller_id: str) -> int:
    """For each Unpaid (or Overdue) invoice older than 7 days, post a weekly reminder
    if no reminder notification was created for it within the last 7 days."""
    invoices = await db.invoices.find(
        {"seller_id": seller_id, "status": {"$in": ["Unpaid", "Overdue"]}},
        {"_id": 0},
    ).to_list(1000)
    if not invoices:
        return 0

    now = datetime.now(timezone.utc)
    week = timedelta(days=7)
    created = 0
    for inv in invoices:
        created_at = _parse_iso(inv.get("created_at") or "")
        if not created_at or (now - created_at) < week:
            continue
        # Most recent reminder notification for this invoice (kind = commission_reminder)
        last = await db.notifications.find_one(
            {"user_id": seller_id, "type": "commission", "meta.invoice_id": inv["id"], "meta.reminder": True},
            sort=[("created_at", -1)],
            projection={"_id": 0},
        )
        last_at = _parse_iso(last.get("created_at") if last else "") if last else None
        if last_at and (now - last_at) < week:
            continue
        amount = float(inv.get("commission") or inv.get("amount_owed") or 0)
        label = inv.get("week_label") or inv.get("shop_name") or ""
        await create_notification(
            user_id=seller_id,
            message=f"Reminder: Commission of USD {amount:.2f} is still unpaid — {label}",
            ntype="commission",
            meta={"invoice_id": inv["id"], "reminder": True},
        )
        created += 1
    return created


async def _generate_admin_unpaid_reminders(admin_id: str) -> int:
    """For each seller with one or more Unpaid (or Overdue) invoices older than 7 days,
    post one rolling weekly reminder for the admin (deduped per seller per 7d)."""
    pipeline = [
        {"$match": {"status": {"$in": ["Unpaid", "Overdue"]}}},
        {"$group": {
            "_id": "$seller_id",
            "amount_owed": {"$sum": "$commission"},
            "invoice_count": {"$sum": 1},
            "oldest_created_at": {"$min": "$created_at"},
        }},
    ]
    rows = await db.invoices.aggregate(pipeline).to_list(1000)
    now = datetime.now(timezone.utc)
    week = timedelta(days=7)
    created = 0
    for row in rows:
        sid = row["_id"]
        if not sid:
            continue
        oldest = _parse_iso(row.get("oldest_created_at") or "")
        if not oldest or (now - oldest) < week:
            continue
        last = await db.notifications.find_one(
            {"user_id": admin_id, "type": "commission", "meta.seller_id": sid, "meta.reminder": True},
            sort=[("created_at", -1)],
            projection={"_id": 0},
        )
        last_at = _parse_iso(last.get("created_at") if last else "") if last else None
        if last_at and (now - last_at) < week:
            continue
        seller = await db.users.find_one({"id": sid}, {"_id": 0, "name": 1, "email": 1})
        sname = (seller or {}).get("name") or (seller or {}).get("email") or "Seller"
        await create_notification(
            user_id=admin_id,
            message=f"{sname} has {row['invoice_count']} unpaid invoice(s) — USD {float(row.get('amount_owed') or 0):.2f} owed",
            ntype="commission",
            meta={"seller_id": sid, "amount_owed": float(row.get("amount_owed") or 0), "reminder": True},
        )
        created += 1
    return created


def create_token(user_id: str, role: str, email: str, tv: int) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "email": email,
        "tv": tv,
        "exp": datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    settings = await get_settings()
    if payload.get("tv", 1) != settings.get("token_version", 1):
        raise HTTPException(status_code=401, detail="Session invalidated by admin")

    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_role(*roles: str):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker


# ----------------------------------------------------------------------------
# Pagination helper — keeps low-resource hosts safe from giant responses.
# Default page = 50 items. Hard ceiling = 200. Negative skip clamped to 0.
# ----------------------------------------------------------------------------
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200


def clamp_pagination(limit: Optional[int], skip: Optional[int]) -> tuple[int, int]:
    try:
        page_size = int(limit) if limit is not None else DEFAULT_PAGE_LIMIT
    except (TypeError, ValueError):
        page_size = DEFAULT_PAGE_LIMIT
    try:
        offset = int(skip) if skip is not None else 0
    except (TypeError, ValueError):
        offset = 0
    page_size = max(1, min(page_size, MAX_PAGE_LIMIT))
    offset = max(0, offset)
    return page_size, offset


# ----------------------------------------------------------------------------
# In-process TTL cache for hot read endpoints
# ----------------------------------------------------------------------------
# Designed for low-resource hosts: a tiny dict-backed cache keyed by a string
# key. Values expire after `ttl_seconds`. No background sweeper — entries are
# checked on access. Memory footprint is ~O(number of cached endpoints) which
# is tiny because we cache only a handful of read-heavy public endpoints.
#
# Cache is process-local; if you run multiple uvicorn workers each gets its
# own copy. That is fine because TTL is small (60s) and the data is read-only
# from the public's perspective.
import time as _time
from typing import Awaitable, Callable, TypeVar

_T = TypeVar("_T")
_cache_store: dict[str, tuple[float, object]] = {}
DEFAULT_CACHE_TTL = 60.0  # seconds


async def cached(
    key: str,
    loader: Callable[[], Awaitable[_T]],
    ttl: float = DEFAULT_CACHE_TTL,
) -> _T:
    now = _time.time()
    hit = _cache_store.get(key)
    if hit is not None and now - hit[0] < ttl:
        return hit[1]  # type: ignore[return-value]
    value = await loader()
    _cache_store[key] = (now, value)
    return value


def cache_invalidate(*prefixes: str) -> int:
    """Drop all cached keys whose name starts with any of the given prefixes.
    Returns number of entries dropped. Called by admin write endpoints so
    public reads see fresh data immediately."""
    if not prefixes:
        _cache_store.clear()
        return 0
    keys = [k for k in _cache_store if any(k.startswith(p) for p in prefixes)]
    for k in keys:
        _cache_store.pop(k, None)
    return len(keys)


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------
class LoginIn(BaseModel):
    # Accept either an email OR a username. Renamed field remains "email" for
    # backward compatibility with existing frontend/tests; validation happens in
    # the /auth/login endpoint (usernames are only valid for admin accounts).
    email: str
    password: str


class SignupIn(BaseModel):
    """Public self-signup — customer accounts only.
    Sellers and drivers must be created by an admin via /api/admin/users."""
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=120)
    phone: Optional[str] = ""


class TokenIn(BaseModel):
    token: str


class EmailOnlyIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str = Field(min_length=6)


class ChangePwIn(BaseModel):
    current_password: str
    new_password: str


class ProfileIn(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


class DeliveryAreaFee(BaseModel):
    area: str
    fee_usd: float = 0.0


class SellerSection(BaseModel):
    """A seller-defined section (aka 'menu category' inside a restaurant or
    'product category' inside a shop). Distinct from the platform's global
    Categories collection — those group restaurants/shops on the marketplace,
    while these group items WITHIN one restaurant/shop (Starter,
    Recommendation, Promo, …). Max 6 per entity, validated on the endpoint."""
    id: str  # uuid, seller-generated
    name: str
    sort_order: int = 0


class Promo(BaseModel):
    """Time-limited discount configuration for a single product or menu item.
    Backend recomputes the effective price server-side at order time so the
    customer cannot forge a promo price.
    - `type='percent'` with `value=15.0` → 15% off
    - `type='amount'` with `value=1.50` → $1.50 off (never below $0)
    Both dates optional; None means 'no start floor' / 'no end'. A promo is
    considered ACTIVE when active=True AND now() is within [starts, ends]."""
    active: bool = False
    type: Literal["percent", "amount"] = "percent"
    value: float = 0.0
    starts_at: Optional[str] = None  # ISO 8601 UTC
    ends_at: Optional[str] = None    # ISO 8601 UTC

    @field_validator("value")
    @classmethod
    def _clamp_value(cls, v):
        # Guardrail so a mis-typed 200% doesn't accidentally give the item
        # away. Percentages clamped to [0,100]. Amounts clamped to >=0
        # (the effective-price helper still floors the final price at 0).
        try:
            v = float(v or 0)
        except (TypeError, ValueError):
            v = 0.0
        return max(0.0, v)



class ShopIn(BaseModel):
    name: str
    description: Optional[str] = ""
    image_url: Optional[str] = ""
    area: str
    # "category" and "kind" retained for backward compatibility only; not required
    category: Optional[str] = ""
    kind: Literal["retail", "wholesale"] = "retail"
    # Delivery configuration (per-shop)
    delivery_mode: Literal["free", "fixed", "per_area"] = "free"
    delivery_fee_usd: float = 0.0
    delivery_per_area: List[DeliveryAreaFee] = Field(default_factory=list)
    # Per-shop override for who runs the delivery. Defaults to "default" =
    # follow the platform-wide `admin_manages_delivery` setting. Set to
    # "seller" or "admin" to lock this shop to one mode regardless of the
    # global toggle. Admin-editable only.
    delivery_managed_by: Literal["default", "seller", "admin"] = "default"
    # Storefront fields (Round 7) — separate banner + logo + opening hours + open/closed
    banner_url: Optional[str] = ""
    logo_url: Optional[str] = ""
    opening_hours: Optional[str] = ""
    is_open: bool = True
    # Round 8 — published/public visibility (sellers can hide their shop without deleting)
    is_public: bool = True
    # Round 11 — receipt logo + estimated delivery. Same fields as Restaurant.
    receipt_show_logo: bool = False
    receipt_logo_url: Optional[str] = ""
    eta_mode: Literal["off", "fixed", "range"] = "off"
    eta_fixed_minutes: Optional[int] = None
    eta_min_minutes: Optional[int] = None
    eta_max_minutes: Optional[int] = None
    # Iter 27 — seller-defined PRODUCT SECTIONS (max 6). Groups products
    # within THIS shop (Featured, On Sale, Accessories…). Distinct from the
    # marketplace-level shop_category. Each product references one section
    # via product.product_section_id.
    product_sections: List[SellerSection] = Field(default_factory=list)


class ShopMessageIn(BaseModel):
    body: str
    subject: Optional[str] = ""
    customer_email: Optional[str] = ""  # used when sender is anonymous
    customer_phone: Optional[str] = ""
    customer_name: Optional[str] = ""


class MessageReplyIn(BaseModel):
    reply_body: str


class ShopCommissionIn(BaseModel):
    commission_rate: Optional[float] = None  # None = inherit global rate


class InvoiceFrequencyIn(BaseModel):
    frequency: Literal["daily", "weekly", "monthly", "quarterly", "yearly"]


class ShopInvoiceFrequencyIn(BaseModel):
    frequency: Optional[Literal["daily", "weekly", "monthly", "quarterly", "yearly"]] = None  # None = use global


class ProductIn(BaseModel):
    shop_id: str
    name: str
    category_id: str  # PRIMARY: UUID from categories.id (required)
    category: Optional[str] = ""  # DEPRECATED: backward compatibility only, NOT used for filtering
    price_usd: float
    image_url: Optional[str] = ""
    description: Optional[str] = ""
    stock: int = 100
    is_wholesale: bool = False
    min_order_qty: int = 1
    bulk_price_usd: Optional[float] = None
    mode: Literal["marketplace", "wholesale"] = "marketplace"
    pricing_tiers: List[dict] = Field(default_factory=list)
    # Iter 27 — Seller-defined section this product belongs to (max 6 per
    # shop, defined on Shop.product_sections). Optional; when empty the
    # customer sees the product under "Other" in the shop menu.
    product_section_id: Optional[str] = None
    # Iter 27 — Time-limited promotional discount. Applied server-side on
    # order create so a crafted client can't fake the price.
    promo: Optional[Promo] = None


class SideItem(BaseModel):
    name: str
    price_usd: float


class DeliveryPricing(BaseModel):
    """Delivery pricing configuration for restaurants"""
    type: Literal["free", "fixed", "per_area"] = "fixed"
    fixed_fee: Optional[float] = 0.0  # Used when type="fixed"
    area_fees: List[dict] = Field(default_factory=list)  # [{"area": "Munuki", "fee": 5.0}]


class OpeningHours(BaseModel):
    """Per-day opening hours. `closed=True` means the whole day is closed
    regardless of open/close time. `open` / `close` are 24h strings
    (e.g. "09:00", "22:30")."""
    closed: bool = False
    open: str = "09:00"
    close: str = "22:00"


class RestaurantIn(BaseModel):
    name: str
    category: Optional[str] = ""
    description: Optional[str] = ""
    image_url: Optional[str] = ""
    area: str
    is_open: bool = True
    delivery_pricing: Optional[DeliveryPricing] = Field(
        default_factory=lambda: DeliveryPricing(type="fixed", fixed_fee=2.0)
    )
    # New: mirror shop delivery model so sellers can pick free/fixed/per-area
    # for their own restaurants (same UI/UX as the Shop editor).
    delivery_mode: Literal["free", "fixed", "per_area"] = "free"
    delivery_fee_usd: float = 0.0
    delivery_per_area: List[DeliveryAreaFee] = Field(default_factory=list)
    delivery_managed_by: Literal["default", "seller", "admin"] = "default"
    # Weekly opening hours + optional auto-close by hours. When
    # `auto_close_by_hours` is on, the frontend / kitchen-dashboard hides
    # ordering (`is_open` is displayed as False) outside the configured
    # window for the current day.
    opening_hours_by_day: Optional[Dict[str, OpeningHours]] = None
    auto_close_by_hours: bool = False
    # Round 11 seller polish — customer-visible logo on the printed receipt
    # (toggle + URL). When `receipt_show_logo=True` the receipt template
    # renders `receipt_logo_url` (falls back to image_url) at the top.
    receipt_show_logo: bool = False
    receipt_logo_url: Optional[str] = ""
    # Estimated delivery time in minutes — surfaced on the customer's
    # checkout + order tracking pages. Either a fixed value or a range.
    # `eta_fixed_minutes` is used when set; otherwise the range is used.
    eta_mode: Literal["off", "fixed", "range"] = "off"
    eta_fixed_minutes: Optional[int] = None
    eta_min_minutes: Optional[int] = None
    eta_max_minutes: Optional[int] = None
    # Iter 27 — seller-defined MENU SECTIONS (max 6). Sellers create their
    # own groups like Starter / Recommendation / Promo and assign each
    # menu item to one via menu_item.menu_section_id.
    menu_sections: List[SellerSection] = Field(default_factory=list)


class MenuItemIn(BaseModel):
    restaurant_id: str
    name: str
    price_usd: float
    image_url: Optional[str] = ""
    description: Optional[str] = ""
    category_id: str  # PRIMARY: UUID from categories.id (required, group=restaurant)
    food_category: Optional[str] = ""  # DEPRECATED: backward compatibility only, NOT used for filtering
    side_items: List[SideItem] = Field(default_factory=list)
    # Kitchen prep time in minutes — used by the Kitchen Dashboard to show
    # a target-vs-actual timer per order. Optional; falls back to a global
    # default (or "—") when not set.
    prep_time_minutes: Optional[int] = None
    # Iter 26 — REQUIRED sides. When True, the customer MUST select between
    # sides_min_choices and sides_max_choices side items before checkout.
    # Use cases:
    #   • Pizza size (choose exactly one): sides_required=True, min=1, max=1
    #   • Burger meal (must pick fries, extras optional): min=1, max=null
    #   • Optional (default old behaviour): required=False
    sides_required: bool = False
    sides_min_choices: Optional[int] = None  # None → 1 when required
    sides_max_choices: Optional[int] = None  # None → unlimited
    # Iter 27 — Seller-defined menu section (max 6 per restaurant, defined
    # on Restaurant.menu_sections). Distinct from category_id which points
    # to the platform-level restaurant grouping.
    menu_section_id: Optional[str] = None
    # Iter 27 — Time-limited promotional discount.
    promo: Optional[Promo] = None


class OrderItemIn(BaseModel):
    item_type: Literal["product", "menu_item"]
    item_id: str
    name: str
    price_usd: float
    quantity: int
    image_url: Optional[str] = ""
    sides: List[SideItem] = Field(default_factory=list)


class OrderIn(BaseModel):
    items: List[OrderItemIn]
    area: str
    address: Optional[str] = ""
    phone: str
    note: Optional[str] = ""
    order_kind: Literal["marketplace", "restaurant", "wholesale"] = "marketplace"


class RestaurantOrderIn(BaseModel):
    """Restaurant-specific order model"""
    restaurant_id: str
    items: List[OrderItemIn]  # menu items with sides
    delivery_type: Literal["delivery", "pickup"] = "delivery"
    customer_name: str
    customer_phone: str
    customer_address: Optional[str] = ""  # Required for delivery
    customer_area: Optional[str] = ""  # NEW: Customer delivery area for pricing calculation
    payment_method: Literal["cash", "mobile_money"] = "cash"
    note: Optional[str] = ""


class RestaurantOrderQuoteIn(BaseModel):
    """Simplified model for quote calculation - no customer details needed"""
    restaurant_id: str
    items: List[OrderItemIn]
    delivery_type: Literal["delivery", "pickup"] = "delivery"
    customer_area: Optional[str] = ""  # Delivery area for fee calculation


class OrderStatusUpdate(BaseModel):
    """Update order status in kitchen dashboard"""
    status: Literal[
        "pending", "accepted", "cooking", "ready", "completed", "cancelled",
        "cancel_requested", "cancel_approved", "cancel_rejected",
    ]


class CancelRequestIn(BaseModel):
    """Seller requests cancellation of a restaurant order (status must be accepted/cooking/ready)"""
    reason: str = ""


class CancelRejectIn(BaseModel):
    """Admin rejects a cancellation request — order reverts to previous_status"""
    admin_note: str = ""


class StatusIn(BaseModel):
    status: Literal["Pending", "In Progress", "Delivered"]


class BlockEmailIn(BaseModel):
    email: EmailStr


class ExchangeRateIn(BaseModel):
    rate: float


class FavoriteIn(BaseModel):
    target_type: Literal["shop", "product", "restaurant"]
    target_id: str


class ReviewIn(BaseModel):
    """Review/rating for restaurant after order completion"""
    restaurant_id: str
    order_id: str  # Link to completed order
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = ""


class ProductReviewIn(BaseModel):
    """Review/rating for marketplace product"""
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = ""
    # List of image URLs (already uploaded via /api/upload). Max 5 photos per review.
    photos: Optional[List[str]] = None


class TrendingClickIn(BaseModel):
    """Track clicks for trending system"""
    target_type: Literal["restaurant", "product"]
    target_id: str


class OrderChatMessageIn(BaseModel):
    """A single chat message between customer and seller about an order."""
    seller_id: str
    body: str = Field(min_length=1, max_length=2000)


class SettingsIn(BaseModel):
    global_rate: Optional[float] = None
    currency_display: Optional[bool] = None
    auto_approve_shops: Optional[bool] = None
    require_verification: Optional[bool] = None
    allow_suspension: Optional[bool] = None
    verified_first: Optional[bool] = None
    require_doc_for_verification: Optional[bool] = None
    module_marketplace: Optional[bool] = None
    module_restaurants: Optional[bool] = None
    module_wholesale: Optional[bool] = None
    maintenance_mode: Optional[bool] = None
    login_attempt_limit: Optional[int] = None
    commission_rate: Optional[float] = None
    admin_manages_delivery: Optional[bool] = None


class InvoiceStatusIn(BaseModel):
    status: Literal["Paid", "Unpaid", "Overdue"]


class AreaIn(BaseModel):
    area: str


class SellerSettingsIn(BaseModel):
    low_stock_alert: Optional[bool] = None
    low_stock_threshold: Optional[int] = None
    auto_hide_out_of_stock: Optional[bool] = None
    order_notifications: Optional[bool] = None


class NotificationCreate(BaseModel):
    user_id: str
    message: str
    type: Literal["order", "commission", "alert"] = "alert"
    meta: Optional[dict] = None


class CustomerSettingsIn(BaseModel):
    default_area: Optional[str] = None
    order_notifications: Optional[bool] = None
    promotion_notifications: Optional[bool] = None
    dark_mode: Optional[bool] = None


class PageIn(BaseModel):
    title: str
    subtitle: Optional[str] = ""
    body_html: str
    # contact-specific structured fields (optional, only used by the contact page)
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_location: Optional[str] = None
    business_hours: Optional[str] = None


class FooterLink(BaseModel):
    label: str
    url: str


class FooterIn(BaseModel):
    tagline: Optional[str] = None
    social_facebook: Optional[str] = None
    social_instagram: Optional[str] = None
    social_twitter: Optional[str] = None
    shop_title: Optional[str] = None
    shop_links: Optional[List[FooterLink]] = None
    company_title: Optional[str] = None
    company_links: Optional[List[FooterLink]] = None
    legal_title: Optional[str] = None
    legal_links: Optional[List[FooterLink]] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_location: Optional[str] = None
    copyright_text: Optional[str] = None
    tagline_bottom: Optional[str] = None


# Admin user management models
class AdminUserCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6)
    role: Literal["customer", "seller", "admin", "driver"] = "customer"
    phone: Optional[str] = ""
    email_verified: bool = True  # Admin-created users are pre-verified


class AdminUserUpdateIn(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[Literal["customer", "seller", "admin", "driver"]] = None


class AdminResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=6)


class AdminUserStatusIn(BaseModel):
    is_active: bool


class AdminBulkDeleteUsersIn(BaseModel):
    user_ids: List[str] = Field(min_length=1)




# ----------------------------------------------------------------------------
# Auth endpoints
# ----------------------------------------------------------------------------
@api.post("/auth/login")
async def login(payload: LoginIn, request: Request, response: Response):
    raw_identifier = (payload.email or "").strip()
    is_email = "@" in raw_identifier
    email = raw_identifier.lower() if is_email else ""
    username = raw_identifier.lower() if not is_email else ""

    # Email-based blocked check (only meaningful for email login)
    if email:
        blocked = await db.blocked_emails.find_one({"email": email})
        if blocked:
            raise HTTPException(status_code=403, detail="This email has been blocked by admin")

    settings = await get_settings()
    limit = max(1, int(settings.get("login_attempt_limit", 5)))
    ip = request.client.host if request.client else "unknown"
    key = f"{ip}:{email or username}"
    rec = await db.login_attempts.find_one({"key": key})
    if rec and rec.get("count", 0) >= limit:
        last = rec.get("last_at")
        try:
            last_dt = datetime.fromisoformat(last) if isinstance(last, str) else last
        except Exception:
            last_dt = None
        if last_dt and (datetime.now(timezone.utc) - last_dt).total_seconds() < 900:
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
        await db.login_attempts.delete_one({"key": key})

    # Look up user by email OR by username (admin-only)
    if is_email:
        user = await db.users.find_one({"email": email})
    else:
        # Username login is admin-only. Look up by username field AND require admin role.
        user = await db.users.find_one({"username": username, "role": "admin"})

    if not user or not verify_password(payload.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"key": key},
            {"$inc": {"count": 1}, "$set": {"last_at": now_iso()}},
            upsert=True,
        )
        # Keep the error message intentionally generic
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Require verified email for non-admin roles
    if user.get("role") != "admin" and not user.get("email_verified", False):
        raise HTTPException(
            status_code=403,
            detail="Please verify your email before signing in. Check your inbox for the verification link.",
        )

    if user.get("suspended"):
        raise HTTPException(status_code=403, detail="Your account has been suspended. Contact support.")

    # Check if account is disabled by admin
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Your account has been disabled. Contact support.")

    # Check if user must change password (after admin temp password)
    if user.get("must_change_password", False):
        raise HTTPException(
            status_code=403,
            detail="You must change your password. Please use the 'Forgot password' feature to set a new password.",
        )

    await db.login_attempts.delete_one({"key": key})
    
    # Update last login timestamp
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login": now_iso()}})
    
    tv = settings.get("token_version", 1)
    token = create_token(user["id"], user["role"], user["email"], tv)
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=ACCESS_TOKEN_DAYS * 24 * 3600, path="/",
    )
    return {
        "token": token,
        "user": {
            "id": user["id"], "email": user["email"], "name": user["name"],
            "role": user["role"], "phone": user.get("phone", ""),
            "settings": user.get("settings", {}),
        },
    }


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


# --------------------------------------------------------------------
# Signup + email verification + password reset
# --------------------------------------------------------------------
VERIFICATION_TTL_HOURS = 48
RESET_TTL_MINUTES = 60


def _make_token() -> str:
    return secrets.token_urlsafe(32)


async def _find_valid_token(collection, token: str):
    rec = await collection.find_one({"token": token}, {"_id": 0})
    if not rec:
        return None
    try:
        exp = datetime.fromisoformat(rec["expires_at"])
    except Exception:
        return None
    if exp < datetime.now(timezone.utc):
        return None
    return rec


@api.post("/auth/signup")
async def signup(body: SignupIn):
    email = body.email.lower()
    blocked = await db.blocked_emails.find_one({"email": email})
    if blocked:
        raise HTTPException(403, "This email cannot be registered. Contact support.")
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "An account with this email already exists.")

    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "email": email,
        "name": body.name.strip(),
        "role": "customer",  # public signup is customer-only; sellers/drivers are admin-created
        "phone": (body.phone or "").strip(),
        "password_hash": hash_password(body.password),
        "email_verified": False,
        "is_active": True,
        "must_change_password": False,
        "settings": {},
        "created_at": now_iso(),
    }
    await db.users.insert_one(user)

    token = _make_token()
    await db.email_verifications.insert_one({
        "token": token,
        "user_id": uid,
        "email": email,
        "created_at": now_iso(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=VERIFICATION_TTL_HOURS)).isoformat(),
    })
    try:
        await email_service.send_verification_email(to=email, name=user["name"], token=token)
    except Exception as e:
        log.error(f"signup email send failed: {e}")

    return {
        "ok": True,
        "message": "Account created — please check your email to verify your address.",
        "email": email,
    }


@api.post("/auth/verify-email")
async def verify_email(body: TokenIn):
    rec = await _find_valid_token(db.email_verifications, body.token)
    if not rec:
        raise HTTPException(400, "Invalid or expired verification link.")
    await db.users.update_one({"id": rec["user_id"]}, {"$set": {"email_verified": True}})
    await db.email_verifications.delete_many({"user_id": rec["user_id"]})
    return {"ok": True, "message": "Email verified — you can now sign in."}


@api.post("/auth/resend-verification")
async def resend_verification(body: EmailOnlyIn):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    # Don't leak whether the account exists.
    if not user or user.get("email_verified"):
        return {"ok": True, "message": "If an account exists for this email, a verification link was sent."}
    await db.email_verifications.delete_many({"user_id": user["id"]})
    token = _make_token()
    await db.email_verifications.insert_one({
        "token": token,
        "user_id": user["id"],
        "email": email,
        "created_at": now_iso(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=VERIFICATION_TTL_HOURS)).isoformat(),
    })
    try:
        await email_service.send_verification_email(to=email, name=user.get("name", ""), token=token)
    except Exception as e:
        log.error(f"resend verification failed: {e}")
    return {"ok": True, "message": "If an account exists for this email, a verification link was sent."}


@api.post("/auth/forgot-password")
async def forgot_password(body: EmailOnlyIn):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    # Same generic response regardless of match, to prevent email enumeration
    if user:
        await db.password_resets.delete_many({"user_id": user["id"]})
        token = _make_token()
        await db.password_resets.insert_one({
            "token": token,
            "user_id": user["id"],
            "email": email,
            "created_at": now_iso(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=RESET_TTL_MINUTES)).isoformat(),
        })
        try:
            await email_service.send_password_reset_email(to=email, name=user.get("name", ""), token=token)
        except Exception as e:
            log.error(f"password reset email failed: {e}")
    return {"ok": True, "message": "If an account exists for this email, a reset link was sent."}


@api.post("/auth/reset-password")
async def reset_password(body: ResetPasswordIn):
    rec = await _find_valid_token(db.password_resets, body.token)
    if not rec:
        raise HTTPException(400, "Invalid or expired reset link. Please request a new one.")
    await db.users.update_one(
        {"id": rec["user_id"]},
        {"$set": {
            "password_hash": hash_password(body.new_password),
            "must_change_password": False,
        }},
    )
    await db.password_resets.delete_many({"user_id": rec["user_id"]})
    return {"ok": True, "message": "Password updated — you can now sign in."}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.post("/auth/change-password")
async def change_password(body: ChangePwIn, user: dict = Depends(get_current_user)):
    full = await db.users.find_one({"id": user["id"]})
    if not verify_password(body.current_password, full["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": hash_password(body.new_password)}},
    )
    return {"ok": True}


@api.put("/auth/profile")
async def update_profile(body: ProfileIn, user: dict = Depends(get_current_user)):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if update:
        await db.users.update_one({"id": user["id"]}, {"$set": update})
    refreshed = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    return refreshed


@api.put("/seller/settings")
async def update_seller_settings(body: SellerSettingsIn, user: dict = Depends(require_role("seller", "admin"))):
    update = {f"settings.{k}": v for k, v in body.model_dump().items() if v is not None}
    if update:
        await db.users.update_one({"id": user["id"]}, {"$set": update})
    refreshed = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    return refreshed


@api.put("/customer/settings")
async def update_customer_settings(body: CustomerSettingsIn, user: dict = Depends(get_current_user)):
    update = {f"settings.{k}": v for k, v in body.model_dump().items() if v is not None}
    if update:
        await db.users.update_one({"id": user["id"]}, {"$set": update})
    refreshed = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    return refreshed


# ----------------------------------------------------------------------------
# File uploads (seller product/shop images → local disk)
# ----------------------------------------------------------------------------
UPLOAD_DIR = _FsPath(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


@api.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...), user: dict = Depends(require_role("seller", "admin"))):
    name = file.filename or ""
    ext = _FsPath(name).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise HTTPException(400, f"Unsupported file type {ext}. Allowed: jpg, png, webp, gif.")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 5 MB).")
    if len(data) == 0:
        raise HTTPException(400, "Empty file.")
    fname = f"{uuid.uuid4().hex}{ext}"

    # Try Emergent Object Storage first (persistent across deploys). Fall
    # back to local disk only if the storage service is unreachable so
    # uploads never hard-fail during a transient outage.
    stored_in = "storage"
    storage_path = f"{storage.UPLOADS_PREFIX}/{fname}"
    try:
        content_type = file.content_type or storage.guess_content_type(fname)
        result = storage.put_object(storage_path, data, content_type)
        # Persist a DB pointer so we can look up + soft-delete later.
        await db.uploaded_files.insert_one({
            "id": str(uuid.uuid4()),
            "filename": fname,
            "storage_path": result.get("path", storage_path),
            "content_type": content_type,
            "size": result.get("size", len(data)),
            "uploaded_by": user["id"],
            "original_filename": name,
            "is_deleted": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logging.warning("Object storage upload failed, falling back to local disk: %s", e)
        dest = UPLOAD_DIR / fname
        with open(dest, "wb") as f:
            f.write(data)
        stored_in = "disk"

    # Return a RELATIVE URL. The browser resolves it against whatever
    # origin the page is served from — so it works on production
    # (jubasquare.com / www.jubasquare.com), preview, or custom domains
    # without env-var configuration. This avoids the class of bug where
    # request.url.netloc returned the internal K8s cluster hostname.
    public_url = f"/api/uploads/{fname}"
    return {"ok": True, "url": public_url, "filename": fname, "storage": stored_in}


@api.get("/uploads/{filename}")
async def serve_upload(filename: str):
    """Public read endpoint for uploaded images.

    1. Try Emergent Object Storage (canonical location for all NEW uploads).
    2. Fall back to `/app/backend/uploads/` on disk (legacy files still
       served this way until a scheduled backfill migrates them).
    3. Otherwise return 404.
    """
    # Basic sanity: no path traversal
    if "/" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")

    # Try object storage
    storage_path = f"{storage.UPLOADS_PREFIX}/{filename}"
    try:
        data, content_type = storage.get_object(storage_path)
        return Response(
            content=data,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )
    except Exception:
        pass  # fall through to disk fallback

    # Legacy disk fallback
    disk_path = UPLOAD_DIR / filename
    if disk_path.is_file():
        content_type = storage.guess_content_type(filename)
        with open(disk_path, "rb") as f:
            data = f.read()
        return Response(
            content=data,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    raise HTTPException(404, "File not found")
    return {"ok": True, "url": public_url, "filename": fname}


# ----------------------------------------------------------------------------
# Public: System settings (read-only public subset) + Areas
# ----------------------------------------------------------------------------
@api.get("/settings/public")
async def public_settings():
    async def _build():
        s = await get_settings()
        return {
            "global_rate": s.get("global_rate", 600.0),
            "currency_display": s.get("currency_display", True),
            "verified_first": s.get("verified_first", True),
            "module_marketplace": s.get("module_marketplace", True),
            "module_restaurants": s.get("module_restaurants", True),
            "module_wholesale": s.get("module_wholesale", True),
            "maintenance_mode": s.get("maintenance_mode", False),
            "areas": s.get("areas", DEFAULT_AREAS),
            "homepage": s.get("homepage", DEFAULT_HOMEPAGE),
        }
    return await cached("settings:public", _build)


@api.get("/homepage")
async def get_homepage_config():
    async def _build():
        s = await get_settings()
        return s.get("homepage", DEFAULT_HOMEPAGE)
    return await cached("homepage:config", _build)


@api.put("/admin/homepage")
async def update_homepage_config(payload: dict, user: dict = Depends(require_role("admin"))):
    # Sanitize hero_slides
    slides = payload.get("hero_slides")
    if slides is not None:
        if not isinstance(slides, list):
            raise HTTPException(400, "hero_slides must be a list")
        cleaned = []
        for i, s in enumerate(slides[:6]):  # max 6 slides
            if not isinstance(s, dict):
                continue
            cleaned.append({
                "label": str(s.get("label") or f"Slide {i+1}")[:40],
                "key": str(s.get("key") or "")[:40],
                "image_url": str(s.get("image_url") or "")[:1000],
            })
        payload["hero_slides"] = cleaned
    # Sanitize simple text fields
    for k in ("hero_tagline", "hero_title", "hero_subtitle"):
        if k in payload and payload[k] is not None:
            payload[k] = str(payload[k])[:500]
    # Sanitize announcement bar
    ab = payload.get("announcement_bar")
    if ab is not None:
        if not isinstance(ab, dict):
            raise HTTPException(400, "announcement_bar must be an object")
        payload["announcement_bar"] = {
            "enabled": bool(ab.get("enabled", False)),
            "text": str(ab.get("text") or "")[:500],
            "link": str(ab.get("link") or "")[:500],
        }
    current = await get_settings()
    hp = dict(current.get("homepage") or DEFAULT_HOMEPAGE)
    hp.update({k: v for k, v in payload.items() if k in ("hero_slides", "hero_tagline", "hero_title", "hero_subtitle", "announcement_bar")})
    await db.settings.update_one({"id": "system"}, {"$set": {"homepage": hp}}, upsert=True)
    # Invalidate caches
    cache_invalidate("homepage:", "settings:")
    return {"ok": True, "homepage": hp}



@api.get("/meta/areas")
async def get_areas():
    async def _build():
        s = await get_settings()
        return s.get("areas", DEFAULT_AREAS)
    return await cached("meta:areas", _build)


@api.get("/meta/health")
async def health():
    return {"ok": True, "service": "JubaSquare API"}


@api.get("/health")
async def api_health():
    """Simple health check for uptime monitoring / load balancers.
    Accessible publicly at `/api/health` (all backend routes on Emergent
    Kubernetes are exposed via the `/api/*` prefix).
    """
    return {"status": "ok"}


@app.get("/health", include_in_schema=False)
async def container_health():
    """Health check reachable directly on the container (bypasses the
    Kubernetes ingress `/api/*` rewrite). Used by internal readiness /
    liveness probes and local `curl http://localhost:8001/health`.
    """
    return {"status": "ok"}


# ----------------------------------------------------------------------------
# Pages (CMS) — admin-editable Terms / Privacy / Returns / About / Contact
# ----------------------------------------------------------------------------
def _public_page(p: dict) -> dict:
    """Strip _id, return only the public fields."""
    if not p:
        return None
    return {
        "slug": p.get("slug"),
        "title": p.get("title", ""),
        "subtitle": p.get("subtitle", ""),
        "body_html": p.get("body_html", ""),
        "contact_email": p.get("contact_email"),
        "contact_phone": p.get("contact_phone"),
        "contact_location": p.get("contact_location"),
        "business_hours": p.get("business_hours"),
        "last_updated": p.get("last_updated"),
    }


@api.get("/pages")
async def list_pages():
    """Public — returns minimal page list (for navigation/discovery). Cached 60s."""

    async def _build():
        docs = await db.pages.find({}, {"_id": 0}).to_list(50)
        return [
            {"slug": d.get("slug"), "title": d.get("title", ""), "last_updated": d.get("last_updated")}
            for d in docs
        ]

    return await cached("pages:list", _build)


@api.get("/pages/{slug}")
async def get_page(slug: str):
    async def _build():
        p = await db.pages.find_one({"slug": slug}, {"_id": 0})
        if not p:
            raise HTTPException(404, "Page not found")
        return _public_page(p)
    return await cached(f"pages:slug:{slug}", _build)


@api.put("/pages/{slug}")
async def update_page(slug: str, body: PageIn, user: dict = Depends(require_role("admin"))):
    if slug not in PAGE_SLUGS:
        raise HTTPException(400, f"Unknown page slug. Allowed: {', '.join(PAGE_SLUGS)}")
    update_doc = {
        "slug": slug,
        "title": body.title,
        "subtitle": body.subtitle or "",
        "body_html": body.body_html,
        "last_updated": now_iso(),
        "updated_by": user.get("id"),
    }
    if slug == "contact":
        update_doc["contact_email"] = body.contact_email or ""
        update_doc["contact_phone"] = body.contact_phone or ""
        update_doc["contact_location"] = body.contact_location or ""
        update_doc["business_hours"] = body.business_hours or ""
    await db.pages.update_one({"slug": slug}, {"$set": update_doc}, upsert=True)
    cache_invalidate("pages:")
    saved = await db.pages.find_one({"slug": slug}, {"_id": 0})
    return _public_page(saved)


@api.get("/admin/pages")
async def admin_list_pages(user: dict = Depends(require_role("admin"))):
    """Admin — returns full content of all pages (for the editor UI)."""
    docs = await db.pages.find({}, {"_id": 0}).to_list(50)
    by_slug = {d.get("slug"): _public_page(d) for d in docs}
    # Always return all known slugs (with default content if missing)
    out = []
    for slug in PAGE_SLUGS:
        if slug in by_slug:
            out.append(by_slug[slug])
        else:
            d = PAGES_DEFAULT[slug]
            out.append({**d, "last_updated": None})
    return out


# ----------------------------------------------------------------------------
# Footer (site-wide editable config)
# ----------------------------------------------------------------------------
def _footer_doc(d: dict) -> dict:
    """Strip _id; ensure all expected keys exist with sensible fallbacks."""
    if not d:
        d = {}
    merged = {**FOOTER_DEFAULT, **{k: v for k, v in d.items() if v is not None}}
    merged.pop("_id", None)
    return merged


@api.get("/site-config/footer")
async def get_footer():
    """Public — current footer config (with defaults filled in). Cached 60s."""

    async def _build():
        doc = await db.site_config.find_one({"id": "footer"}, {"_id": 0})
        return _footer_doc(doc)

    return await cached("footer:public", _build)


@api.put("/admin/site-config/footer")
async def update_footer(body: FooterIn, user: dict = Depends(require_role("admin"))):
    payload = {k: v for k, v in body.dict().items() if v is not None}
    # Ensure links are stored as plain dicts
    for key in ("shop_links", "company_links", "legal_links"):
        if key in payload and payload[key] is not None:
            payload[key] = [
                {"label": (lk.get("label") or "").strip(), "url": (lk.get("url") or "").strip()}
                for lk in payload[key]
                if (lk.get("label") or "").strip() and (lk.get("url") or "").strip()
            ]
    payload["id"] = "footer"
    payload["last_updated"] = now_iso()
    payload["updated_by"] = user.get("id")
    await db.site_config.update_one({"id": "footer"}, {"$set": payload}, upsert=True)
    cache_invalidate("footer:")
    saved = await db.site_config.find_one({"id": "footer"}, {"_id": 0})
    return _footer_doc(saved)


# ----------------------------------------------------------------------------
# Categories (admin-managed, hierarchical: 1 level of sub-categories)
# ----------------------------------------------------------------------------
ALLOWED_CATEGORY_GROUPS = {"retail", "wholesale", "restaurant"}


def _category_doc(c: dict) -> dict:
    """Strip Mongo internals & enforce shape."""
    if not c:
        return c
    return {
        "id": c.get("id"),
        "name": c.get("name", ""),
        "group": c.get("group", "retail"),
        "parent_id": c.get("parent_id"),
        "order": c.get("order", 0),
        "image_url": c.get("image_url") or "",
        "is_active": bool(c.get("is_active", True)),
        "created_at": c.get("created_at"),
        "updated_at": c.get("updated_at"),
    }


async def _categories_query(group: Optional[str], active_only: bool) -> list:
    q: dict = {}
    if group:
        if group not in ALLOWED_CATEGORY_GROUPS:
            raise HTTPException(status_code=400, detail=f"Unknown group. Must be one of: {sorted(ALLOWED_CATEGORY_GROUPS)}")
        q["group"] = group
    if active_only:
        q["$or"] = [{"is_active": {"$ne": False}}, {"is_active": {"$exists": False}}]
    cursor = db.categories.find(q, {"_id": 0}).sort([("group", 1), ("parent_id", 1), ("order", 1), ("name", 1)])
    return [_category_doc(c) async for c in cursor]


def _build_tree(flat: list) -> list:
    """Group sub-categories under parents. 1-level deep only."""
    by_parent = {}
    for c in flat:
        by_parent.setdefault(c.get("parent_id"), []).append(c)
    tops = by_parent.get(None, [])
    out = []
    for top in tops:
        children = by_parent.get(top["id"], [])
        out.append({**top, "children": children})
    return out


@api.get("/meta/categories")
async def get_categories():
    """Backward-compatible flat lists per group, plus structured tree. Cached
    for 60s — admin writes invalidate the `cat:` prefix immediately."""

    async def _build():
        flat = await _categories_query(None, active_only=True)
        by_group: dict = {g: [] for g in ALLOWED_CATEGORY_GROUPS}
        for c in flat:
            by_group.setdefault(c["group"], []).append(c)

        def _names(group_key: str) -> list:
            return [c["name"] for c in by_group.get(group_key, []) if not c.get("parent_id")]

        all_subs = [c["name"] for c in flat if c.get("parent_id")]
        food_top_subs = [c["name"] for c in flat if c.get("group") == "food" and not c.get("parent_id")]
        trees = {g: _build_tree([c for c in flat if c["group"] == g]) for g in ALLOWED_CATEGORY_GROUPS}

        return {
            "retail": _names("retail"),
            "wholesale": _names("wholesale"),
            "restaurant": _names("restaurant"),
            "food_subcategories": food_top_subs or all_subs,
            "groups": trees,
        }

    return await cached("cat:meta", _build)


@api.get("/categories")
async def list_categories(group: Optional[str] = None):
    """Public flat list of active categories. Cached for 60s."""
    key = f"cat:flat:{group or 'all'}"
    return await cached(key, lambda: _categories_query(group, active_only=True))


@api.get("/categories/tree")
async def categories_tree(group: Optional[str] = None):
    """Public tree (parent → children). Active only. Cached for 60s."""
    key = f"cat:tree:{group or 'all'}"

    async def _build():
        flat = await _categories_query(group, active_only=True)
        if group:
            return _build_tree(flat)
        return {g: _build_tree([c for c in flat if c["group"] == g]) for g in ALLOWED_CATEGORY_GROUPS}

    return await cached(key, _build)


@api.get("/admin/categories")
async def admin_list_categories(group: Optional[str] = None, user: dict = Depends(require_role("admin"))):
    """Admin: full list including inactive."""
    flat = await _categories_query(group, active_only=False)
    if group:
        return _build_tree(flat)
    return {g: _build_tree([c for c in flat if c["group"] == g]) for g in ALLOWED_CATEGORY_GROUPS}


class CategoryCreateIn(BaseModel):
    name: str
    group: str
    parent_id: Optional[str] = None
    image_url: Optional[str] = ""
    is_active: Optional[bool] = True
    order: Optional[int] = None


class CategoryUpdateIn(BaseModel):
    name: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    order: Optional[int] = None
    # parent_id intentionally NOT updatable in MVP — keeps tree integrity simple.


class CategoryReorderIn(BaseModel):
    group: str
    parent_id: Optional[str] = None
    ids: List[str]


async def _next_order(group: str, parent_id: Optional[str]) -> int:
    last = await db.categories.find_one(
        {"group": group, "parent_id": parent_id},
        sort=[("order", -1)],
    )
    return (last.get("order", 0) + 1) if last else 1


@api.post("/admin/categories")
async def admin_create_category(body: CategoryCreateIn, user: dict = Depends(require_role("admin"))):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if body.group not in ALLOWED_CATEGORY_GROUPS:
        raise HTTPException(status_code=400, detail=f"Unknown group. Must be one of: {sorted(ALLOWED_CATEGORY_GROUPS)}")

    parent = None
    if body.parent_id:
        parent = await db.categories.find_one({"id": body.parent_id})
        if not parent:
            raise HTTPException(status_code=404, detail="Parent category not found")
        if parent.get("group") != body.group:
            raise HTTPException(status_code=400, detail="Parent must be in the same group")
        if parent.get("parent_id"):
            raise HTTPException(status_code=400, detail="Sub-categories cannot have sub-categories (1 level only)")

    # Uniqueness within (group, parent_id)
    dup = await db.categories.find_one({
        "group": body.group, "parent_id": body.parent_id, "name": name
    })
    if dup:
        raise HTTPException(status_code=400, detail="A category with this name already exists in this group/parent")

    order_val = body.order if body.order is not None else await _next_order(body.group, body.parent_id)
    doc = {
        "id": str(uuid.uuid4()),
        "name": name,
        "group": body.group,
        "parent_id": body.parent_id,
        "order": order_val,
        "image_url": (body.image_url or "").strip(),
        "is_active": True if body.is_active is None else bool(body.is_active),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.categories.insert_one(doc)
    cache_invalidate("cat:")
    return _category_doc(doc)


@api.put("/admin/categories/{cat_id}")
async def admin_update_category(cat_id: str, body: CategoryUpdateIn, user: dict = Depends(require_role("admin"))):
    existing = await db.categories.find_one({"id": cat_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Category not found")

    updates: dict = {"updated_at": now_iso()}
    if body.name is not None:
        new_name = body.name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        # Uniqueness check (within same group/parent)
        dup = await db.categories.find_one({
            "group": existing.get("group"),
            "parent_id": existing.get("parent_id"),
            "name": new_name,
            "id": {"$ne": cat_id},
        })
        if dup:
            raise HTTPException(status_code=400, detail="A category with this name already exists")
        updates["name"] = new_name
    if body.image_url is not None:
        updates["image_url"] = body.image_url.strip()
    if body.is_active is not None:
        updates["is_active"] = bool(body.is_active)
    if body.order is not None:
        updates["order"] = int(body.order)

    await db.categories.update_one({"id": cat_id}, {"$set": updates})
    cache_invalidate("cat:")
    saved = await db.categories.find_one({"id": cat_id}, {"_id": 0})
    return _category_doc(saved)


@api.delete("/admin/categories/{cat_id}")
async def admin_delete_category(cat_id: str, force: bool = False, user: dict = Depends(require_role("admin"))):
    existing = await db.categories.find_one({"id": cat_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Category not found")

    # Block delete if it has children (unless force=true → also delete the children)
    child_count = await db.categories.count_documents({"parent_id": cat_id})
    if child_count > 0 and not force:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: this category has {child_count} sub-category(ies). Pass ?force=true to delete them all.",
        )

    if child_count > 0 and force:
        await db.categories.delete_many({"parent_id": cat_id})
    await db.categories.delete_one({"id": cat_id})
    cache_invalidate("cat:")
    return {"ok": True, "deleted_children": child_count if force else 0}


@api.post("/admin/categories/reorder")
async def admin_reorder_categories(body: CategoryReorderIn, user: dict = Depends(require_role("admin"))):
    if body.group not in ALLOWED_CATEGORY_GROUPS:
        raise HTTPException(status_code=400, detail="Unknown group")
    # Validate every id belongs to (group, parent_id)
    docs = await db.categories.find(
        {"id": {"$in": body.ids}, "group": body.group, "parent_id": body.parent_id},
        {"_id": 0, "id": 1},
    ).to_list(length=10000)
    found_ids = {d["id"] for d in docs}
    missing = [i for i in body.ids if i not in found_ids]
    if missing:
        raise HTTPException(status_code=400, detail=f"Some ids do not belong to this group/parent: {missing}")

    for idx, cid in enumerate(body.ids, start=1):
        await db.categories.update_one(
            {"id": cid},
            {"$set": {"order": idx, "updated_at": now_iso()}},
        )
    return {"ok": True, "reordered": len(body.ids)}


# ----------------------------------------------------------------------------
# Admin Category Data Integrity Tool
# ----------------------------------------------------------------------------
@api.get("/admin/categories/integrity")
async def check_category_integrity(user: dict = Depends(require_role("admin"))):
    """
    Admin debug tool: detect products/menu_items with missing or invalid category_id.
    
    Returns:
    - products_without_category_id: products that have no category_id field
    - products_with_invalid_category_id: products with category_id that doesn't exist
    - menu_items_without_category_id: menu items with no category_id field
    - menu_items_with_invalid_category_id: menu items with invalid category_id
    - orphan_products: products where category was deleted
    - orphan_menu_items: menu items where category was deleted
    """
    # Get all valid category IDs
    all_cats = await db.categories.find({}, {"_id": 0, "id": 1}).to_list(10000)
    valid_cat_ids = {c["id"] for c in all_cats}
    
    # Check products (project only the fields we actually read below)
    all_products = await db.products.find(
        {},
        {"_id": 0, "id": 1, "name": 1, "shop_id": 1, "category_id": 1, "category": 1},
    ).to_list(10000)
    products_without_category_id = []
    products_with_invalid_category_id = []
    
    for p in all_products:
        if "category_id" not in p or not p.get("category_id"):
            products_without_category_id.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "shop_id": p.get("shop_id"),
                "legacy_category": p.get("category", "N/A"),
            })
        elif p["category_id"] not in valid_cat_ids:
            products_with_invalid_category_id.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "shop_id": p.get("shop_id"),
                "category_id": p["category_id"],
                "legacy_category": p.get("category", "N/A"),
            })
    
    # Check menu items
    all_menu_items = await db.menu_items.find({}, {"_id": 0}).to_list(10000)
    menu_items_without_category_id = []
    menu_items_with_invalid_category_id = []
    
    for m in all_menu_items:
        if "category_id" not in m or not m.get("category_id"):
            menu_items_without_category_id.append({
                "id": m.get("id"),
                "name": m.get("name"),
                "restaurant_id": m.get("restaurant_id"),
                "legacy_food_category": m.get("food_category", "N/A"),
            })
        elif m["category_id"] not in valid_cat_ids:
            menu_items_with_invalid_category_id.append({
                "id": m.get("id"),
                "name": m.get("name"),
                "restaurant_id": m.get("restaurant_id"),
                "category_id": m["category_id"],
                "legacy_food_category": m.get("food_category", "N/A"),
            })
    
    return {
        "summary": {
            "total_products": len(all_products),
            "total_menu_items": len(all_menu_items),
            "total_categories": len(valid_cat_ids),
            "products_with_issues": len(products_without_category_id) + len(products_with_invalid_category_id),
            "menu_items_with_issues": len(menu_items_without_category_id) + len(menu_items_with_invalid_category_id),
        },
        "products_without_category_id": products_without_category_id,
        "products_with_invalid_category_id": products_with_invalid_category_id,
        "menu_items_without_category_id": menu_items_without_category_id,
        "menu_items_with_invalid_category_id": menu_items_with_invalid_category_id,
    }


class CategoryIdUpdateIn(BaseModel):
    category_id: str


@api.put("/admin/products/{product_id}/category-id")
async def reassign_product_category(
    product_id: str,
    body: CategoryIdUpdateIn,
    user: dict = Depends(require_role("admin"))
):
    """Admin tool: manually reassign a product's category_id."""
    # Validate category exists
    cat = await db.categories.find_one({"id": body.category_id})
    if not cat:
        raise HTTPException(400, f"Invalid category_id: {body.category_id}. Category does not exist.")
    
    # Update product
    result = await db.products.update_one(
        {"id": product_id},
        {"$set": {"category_id": body.category_id}}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Product not found")
    
    return {"ok": True, "product_id": product_id, "new_category_id": body.category_id}


@api.put("/admin/menu-items/{item_id}/category-id")
async def reassign_menu_item_category(
    item_id: str,
    body: CategoryIdUpdateIn,
    user: dict = Depends(require_role("admin"))
):
    """Admin tool: manually reassign a menu item's category_id."""
    # Validate category exists and is a restaurant category
    cat = await db.categories.find_one({"id": body.category_id})
    if not cat:
        raise HTTPException(400, f"Invalid category_id: {body.category_id}. Category does not exist.")
    if cat.get("group") != "restaurant":
        raise HTTPException(400, f"Invalid category_id: {body.category_id}. Must be a restaurant/food category (group=restaurant).")
    
    # Update menu item
    result = await db.menu_items.update_one(
        {"id": item_id},
        {"$set": {"category_id": body.category_id}}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Menu item not found")
    
    return {"ok": True, "menu_item_id": item_id, "new_category_id": body.category_id}


# ----------------------------------------------------------------------------
# Shops
# ----------------------------------------------------------------------------
def _sort_shops(shops, verified_first: bool):
    if not verified_first:
        return shops
    order = {"Verified": 0, "Pending": 1, "Rejected": 2}
    shops.sort(key=lambda s: order.get(s.get("verification", "Pending"), 1))
    return shops


@api.get("/shops")
async def list_shops(
    request: Request,
    category: Optional[str] = None,
    area: Optional[str] = None,
    kind: Optional[str] = None,
    limit: Optional[int] = None,
    skip: Optional[int] = None,
):
    # Public marketplace listing — exclude shops that the seller has hidden (is_public=False)
    # and shops that are soft-deleted. Legacy shops without these flags default to visible.
    # Also, when `require_verification` is enabled (default), only Verified shops are exposed
    # to customers. Admin users (authenticated) bypass this filter so they can moderate.
    # Sellers use `/shops/mine` to see their own shops regardless of verification status.
    lim, off = clamp_pagination(limit, skip)
    q: dict = {
        "$and": [
            {"$or": [{"is_public": {"$ne": False}}, {"is_public": {"$exists": False}}]},
            {"is_deleted": {"$ne": True}},
        ]
    }
    s = await get_settings()
    # Skip verification gate for admins so the admin dashboard sees pending/rejected too.
    caller_is_admin = False
    try:
        u = await get_current_user(request)
        caller_is_admin = u.get("role") == "admin"
    except HTTPException:
        pass
    if s.get("require_verification", True) and not caller_is_admin:
        q["$and"].append({"verification": "Verified"})
    if category:
        q["category"] = category
    if area:
        q["area"] = area
    if kind:
        q["kind"] = kind
    # Verified-first sort happens in Python; we have to fetch a wider window
    # than `limit` so the sort is meaningful, then slice.
    raw = await db.shops.find(q, {"_id": 0}).to_list(MAX_PAGE_LIMIT + off + lim)
    sorted_shops = _sort_shops(raw, s.get("verified_first", True))
    return sorted_shops[off : off + lim]


@api.get("/shops/mine")
async def my_shops(
    user: dict = Depends(require_role("seller", "admin")),
    limit: Optional[int] = None,
    skip: Optional[int] = None,
):
    lim, off = clamp_pagination(limit, skip)
    # Filter out soft-deleted shops for sellers
    query = {"seller_id": user["id"], "is_deleted": {"$ne": True}}
    return await db.shops.find(query, {"_id": 0}).skip(off).to_list(lim)



@api.get("/shops/{shop_id}")
async def get_shop(shop_id: str, request: Request):
    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0})
    if not shop:
        raise HTTPException(404, "Shop not found")
    # Soft-deleted or non-Verified shops are only visible to the owner or admin.
    # This lets the seller preview their storefront while it's Pending / Rejected,
    # but hides the shop from customers until it has been Verified.
    s = await get_settings()
    require_verified = s.get("require_verification", True)
    is_restricted = shop.get("is_deleted") or (
        require_verified and shop.get("verification") != "Verified"
    )
    if is_restricted:
        try:
            u = await get_current_user(request)
        except HTTPException:
            raise HTTPException(404, "Shop not found")
        if u.get("role") != "admin" and u.get("id") != shop.get("seller_id"):
            raise HTTPException(404, "Shop not found")
    return shop


@api.post("/shops")
async def create_shop(body: ShopIn, user: dict = Depends(require_role("seller", "admin"))):
    s = await get_settings()
    initial_status = "Verified" if s.get("auto_approve_shops") else "Pending"
    payload = body.model_dump()
    # Resolve delivery_managed_by="default" at write time based on the platform
    # toggle: when admins manage delivery globally, new shops default to
    # `admin`; otherwise sellers self-deliver by default. This gives sellers
    # the "seller manages" default they expect at signup.
    if (payload.get("delivery_managed_by") or "default") == "default":
        payload["delivery_managed_by"] = "admin" if s.get("admin_manages_delivery") else "seller"
    shop = {
        "id": str(uuid.uuid4()),
        "seller_id": user["id"],
        "verification": initial_status,
        "created_at": now_iso(),
        **payload,
        # Initialize Odoo connection as disabled by default
        "odoo_connection": {
            "enabled": False,
            "company_id": None,
            "company_name": None,
            "warehouse_id": None,
            "warehouse_name": None,
            "pricelist_id": None,
            "pricelist_name": None,
            "pos_config_id": None,
            "sync_products": False,
            "sync_stock": False,
            "send_orders": False,
            "send_delivery_updates": False,
            "last_sync_at": None,
            "sync_status": "not_configured",
            "sync_error": None
        }
    }
    await db.shops.insert_one(shop)
    shop.pop("_id", None)
    return shop


@api.put("/shops/{shop_id}")
async def update_shop(shop_id: str, body: ShopIn, user: dict = Depends(require_role("seller", "admin"))):
    shop = await db.shops.find_one({"id": shop_id})
    if not shop:
        raise HTTPException(404, "Shop not found")
    if user["role"] != "admin" and shop["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    updates = body.model_dump()
    # Iter 27 — Enforce the 6-section maximum, dedupe by id, and drop any
    # blank names. Sellers can only have 6 product-sections per shop.
    ps = updates.get("product_sections") or []
    seen = set()
    clean_ps = []
    for s in ps:
        if not s.get("id") or s["id"] in seen:
            continue
        name = (s.get("name") or "").strip()
        if not name:
            continue
        seen.add(s["id"])
        clean_ps.append({"id": s["id"], "name": name[:40], "sort_order": int(s.get("sort_order") or 0)})
    if len(clean_ps) > 6:
        raise HTTPException(400, "Maximum 6 product sections allowed")
    updates["product_sections"] = clean_ps
    # Updating a soft-deleted shop restores it and re-activates its products.
    was_deleted = bool(shop.get("is_deleted"))
    if was_deleted:
        updates["is_deleted"] = False
        updates["deleted_at"] = None
    await db.shops.update_one({"id": shop_id}, {"$set": updates})
    if was_deleted:
        await db.products.update_many({"shop_id": shop_id}, {"$set": {"is_active": True}})
    return await db.shops.find_one({"id": shop_id}, {"_id": 0})


class ShopVisibilityIn(BaseModel):
    is_public: bool


@api.patch("/shops/{shop_id}/visibility")
async def update_shop_visibility(shop_id: str, body: ShopVisibilityIn, user: dict = Depends(require_role("seller", "admin"))):
    shop = await db.shops.find_one({"id": shop_id})
    if not shop:
        raise HTTPException(404, "Shop not found")
    if user["role"] != "admin" and shop["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    await db.shops.update_one({"id": shop_id}, {"$set": {"is_public": bool(body.is_public)}})
    return await db.shops.find_one({"id": shop_id}, {"_id": 0})


@api.delete("/shops/{shop_id}")
async def delete_shop(shop_id: str, user: dict = Depends(require_role("seller", "admin"))):
    shop = await db.shops.find_one({"id": shop_id})
    if not shop:
        raise HTTPException(404, "Shop not found")
    if user["role"] != "admin" and shop["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    # Soft delete — keep the shop + its products so the seller can restore them
    # later by editing/updating the shop. Hidden from all public listings while deleted.
    await db.shops.update_one(
        {"id": shop_id},
        {"$set": {"is_deleted": True, "is_public": False, "deleted_at": now_iso()}},
    )
    await db.products.update_many(
        {"shop_id": shop_id},
        {"$set": {"is_active": False}},
    )
    return {"ok": True}


# ----------------------------------------------------------------------------
# Shop messages (customer → seller "Contact Seller" inbox)
# ----------------------------------------------------------------------------
@api.post("/shops/{shop_id}/messages")
async def send_shop_message(shop_id: str, body: ShopMessageIn, request: Request):
    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0})
    if not shop:
        raise HTTPException(404, "Shop not found")
    text = (body.body or "").strip()
    if len(text) < 2:
        raise HTTPException(400, "Message body is required")
    if len(text) > 2000:
        raise HTTPException(400, "Message too long (max 2000 chars)")

    # Apply message filter
    is_valid, error_msg = await filter_message_content(text)
    if not is_valid:
        raise HTTPException(400, error_msg)

    # Sender — logged-in user when present; otherwise use the supplied fields
    sender = {
        "customer_id": None,
        "customer_name": (body.customer_name or "").strip() or "Guest",
        "customer_email": (body.customer_email or "").strip(),
        "customer_phone": (body.customer_phone or "").strip(),
    }
    try:
        u = await get_current_user(request)
        sender["customer_id"] = u["id"]
        sender["customer_name"] = u.get("name") or sender["customer_name"]
        sender["customer_email"] = u.get("email") or sender["customer_email"]
    except HTTPException:
        # Anonymous — require at least an email for the seller to reply
        if not sender["customer_email"]:
            raise HTTPException(400, "Please provide an email so the shop can reply")

    msg = {
        "id": str(uuid.uuid4()),
        "shop_id": shop_id,
        "shop_name": shop.get("name", ""),
        "seller_id": shop["seller_id"],
        "subject": (body.subject or "").strip(),
        "body": text,
        "is_read": False,
        "sender_type": "customer",  # customer or seller
        "replied_at": None,  # When seller replied
        "reply_body": None,  # Seller's reply
        "conversation_status": "open",  # open, replied, closed
        "created_at": now_iso(),
        **sender,
    }
    await db.shop_messages.insert_one(msg)
    
    # Notify seller
    try:
        await create_notification(
            user_id=shop["seller_id"],
            message=f"New message from {sender['customer_name']} about {shop.get('name', 'your shop')}",
            ntype="message",
            meta={"message_id": msg["id"], "shop_id": shop_id},
        )
    except Exception:
        pass
    
    msg.pop("_id", None)
    return msg


@api.get("/messages/seller")
async def list_seller_messages(
    user: dict = Depends(require_role("seller", "admin")),
    limit: Optional[int] = None,
    skip: Optional[int] = None,
):
    lim, off = clamp_pagination(limit, skip)
    q: dict = {}
    if user["role"] != "admin":
        q["seller_id"] = user["id"]
    return await db.shop_messages.find(q, {"_id": 0}).sort("created_at", -1).skip(off).to_list(lim)


@api.get("/messages/seller/unread-count")
async def seller_unread_count(user: dict = Depends(require_role("seller", "admin"))):
    q: dict = {"is_read": False}
    if user["role"] != "admin":
        q["seller_id"] = user["id"]
    n = await db.shop_messages.count_documents(q)
    return {"count": n}


@api.put("/messages/{message_id}/read")
async def mark_message_read(message_id: str, user: dict = Depends(require_role("seller", "admin"))):
    msg = await db.shop_messages.find_one({"id": message_id})
    if not msg:
        raise HTTPException(404, "Message not found")
    if user["role"] != "admin" and msg.get("seller_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    await db.shop_messages.update_one({"id": message_id}, {"$set": {"is_read": True, "read_at": now_iso()}})
    return {"ok": True}


@api.delete("/messages/{message_id}")
async def delete_message(message_id: str, user: dict = Depends(require_role("seller", "admin"))):
    msg = await db.shop_messages.find_one({"id": message_id})
    if not msg:
        raise HTTPException(404, "Message not found")
    if user["role"] != "admin" and msg.get("seller_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    await db.shop_messages.delete_one({"id": message_id})
    return {"ok": True}


@api.post("/messages/{message_id}/reply")
async def reply_to_message(message_id: str, body: MessageReplyIn, user: dict = Depends(require_role("seller", "admin"))):
    """Seller replies to a customer message"""
    msg = await db.shop_messages.find_one({"id": message_id})
    if not msg:
        raise HTTPException(404, "Message not found")
    if user["role"] != "admin" and msg.get("seller_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    
    reply_text = (body.reply_body or "").strip()
    if len(reply_text) < 2:
        raise HTTPException(400, "Reply body is required")
    if len(reply_text) > 2000:
        raise HTTPException(400, "Reply too long (max 2000 chars)")
    
    # Apply message filter to reply
    is_valid, error_msg = await filter_message_content(reply_text)
    if not is_valid:
        raise HTTPException(400, error_msg)
    
    await db.shop_messages.update_one(
        {"id": message_id},
        {"$set": {
            "reply_body": reply_text,
            "replied_at": now_iso(),
            "conversation_status": "replied",
        }}
    )
    
    # Notify customer if they have an account
    if msg.get("customer_id"):
        try:
            await create_notification(
                user_id=msg["customer_id"],
                message=f"{msg.get('shop_name', 'Shop')} replied to your message",
                ntype="message",
                meta={"message_id": message_id, "shop_id": msg.get("shop_id")},
            )
        except Exception:
            pass
    
    return {"ok": True, "message": "Reply sent"}


@api.get("/messages/customer")
async def list_customer_messages(user: dict = Depends(get_current_user), limit: Optional[int] = None, skip: Optional[int] = None):
    """Get messages sent by the current customer"""
    if user["role"] != "customer":
        raise HTTPException(403, "Only customers can access this endpoint")
    
    lim, off = clamp_pagination(limit, skip)
    messages = await db.shop_messages.find(
        {"customer_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).skip(off).to_list(lim)
    
    return messages


@api.get("/messages/customer/unread-count")
async def customer_unread_count(user: dict = Depends(get_current_user)):
    """Count messages with replies that customer hasn't read"""
    if user["role"] != "customer":
        raise HTTPException(403, "Only customers can access this endpoint")
    
    # Count messages where seller has replied but customer hasn't marked as read
    count = await db.shop_messages.count_documents({
        "customer_id": user["id"],
        "conversation_status": "replied",
        "reply_read_by_customer": {"$ne": True}
    })
    
    return {"count": count}


@api.put("/messages/{message_id}/mark-reply-read")
async def mark_reply_read(message_id: str, user: dict = Depends(get_current_user)):
    """Customer marks seller's reply as read"""
    msg = await db.shop_messages.find_one({"id": message_id})
    if not msg:
        raise HTTPException(404, "Message not found")
    if msg.get("customer_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    
    await db.shop_messages.update_one(
        {"id": message_id},
        {"$set": {"reply_read_by_customer": True, "reply_read_at": now_iso()}}
    )
    
    return {"ok": True}


# ----------------------------------------------------------------------------
# Products
# ----------------------------------------------------------------------------
@api.get("/products")
async def list_products(category_id: Optional[str] = None, category: Optional[str] = None,
                        area: Optional[str] = None, shop_id: Optional[str] = None,
                        kind: Optional[str] = None, is_wholesale: Optional[bool] = None,
                        limit: Optional[int] = None, skip: Optional[int] = None):
    """
    List products with filtering.
    PRIMARY FILTER: category_id (UUID from categories table)
    DEPRECATED: category (string name, kept for backward compat only)
    """
    lim, off = clamp_pagination(limit, skip)
    q: dict = {}
    # PRIMARY: filter by category_id (single source of truth)
    if category_id:
        q["category_id"] = category_id
    # DEPRECATED: legacy category name filter (backward compat only)
    elif category:
        q["category"] = category
    if shop_id:
        q["shop_id"] = shop_id
    if is_wholesale is not None:
        q["is_wholesale"] = is_wholesale
    # Hide deactivated products from public listings (still queryable when caller
    # explicitly targets a single shop_id so the owner can manage them).
    if not shop_id:
        q["$or"] = [{"is_active": {"$ne": False}}, {"is_active": {"$exists": False}}]
    # Internal cap: post-filtering reduces the count, so we fetch a wider window
    # than the caller's page so pagination after filtering still has data.
    INTERNAL_CAP = 1000
    products = await db.products.find(q, {"_id": 0}).to_list(INTERNAL_CAP)

    if area or kind:
        shop_q = {}
        if area:
            shop_q["area"] = area
        if kind:
            shop_q["kind"] = kind
        shop_ids = {s["id"] for s in await db.shops.find(shop_q, {"_id": 0, "id": 1}).to_list(INTERNAL_CAP)}
        products = [p for p in products if p["shop_id"] in shop_ids]

    # Hide products from shops that are not public, or soft-deleted.
    # Also hide products from shops that are not Verified (when require_verification is on),
    # so customers only see products from approved shops. Sellers view their own products
    # via /products/mine which does not apply these filters.
    # Skip when caller is targeting a specific shop_id (so the owner's preview / private shop page still works).
    if not shop_id:
        s_gate = await get_settings()
        require_verified = s_gate.get("require_verification", True)
        hide_q: dict = {"$or": [{"is_public": False}, {"is_deleted": True}]}
        if require_verified:
            hide_q = {"$or": hide_q["$or"] + [{"verification": {"$ne": "Verified"}}]}
        hidden_shops = {sh["id"] for sh in await db.shops.find(
            hide_q, {"_id": 0, "id": 1}).to_list(INTERNAL_CAP)}
        if hidden_shops:
            products = [p for p in products if p["shop_id"] not in hidden_shops]

    # Auto-hide out-of-stock per seller setting
    seller_ids = list({p["seller_id"] for p in products})
    sellers = await db.users.find({"id": {"$in": seller_ids}}, {"_id": 0, "id": 1, "settings": 1}).to_list(INTERNAL_CAP)
    auto_hide = {u["id"]: bool((u.get("settings") or {}).get("auto_hide_out_of_stock")) for u in sellers}
    products = [p for p in products if not (auto_hide.get(p["seller_id"]) and p.get("stock", 0) <= 0)]

    # Embed per-seller exchange rate + shop verification (for verified-first sort)
    s = await get_settings()
    global_rate = float(s.get("global_rate", 600.0))
    rate_records = await db.exchange_rates.find(
        {"seller_id": {"$in": seller_ids}}, {"_id": 0}).to_list(INTERNAL_CAP)
    rate_by_seller = {r["seller_id"]: float(r.get("rate", global_rate)) for r in rate_records}

    shop_ids_in = list({p["shop_id"] for p in products})
    shops_meta = await db.shops.find(
        {"id": {"$in": shop_ids_in}}, {"_id": 0, "id": 1, "verification": 1}).to_list(INTERNAL_CAP)
    verif_by_shop = {sh["id"]: sh.get("verification", "Pending") for sh in shops_meta}

    for p in products:
        p["exchange_rate_ssp"] = rate_by_seller.get(p["seller_id"], global_rate)
        p["shop_verification"] = verif_by_shop.get(p["shop_id"], "Pending")

    # In-stock first: within the same verification tier, products WITH stock
    # come before out-of-stock products. Sellers can still choose to auto-hide
    # zero-stock items via their settings; when kept visible, they now sink
    # to the bottom so customers see purchasable items first.
    def _stock_key(p):
        return 0 if int(p.get("stock", 0) or 0) > 0 else 1

    # Verified-first sort if enabled
    if s.get("verified_first", True):
        order = {"Verified": 0, "Pending": 1, "Rejected": 2}
        products.sort(key=lambda p: (order.get(p.get("shop_verification", "Pending"), 1), _stock_key(p)))
    else:
        products.sort(key=_stock_key)
    # Final pagination slice
    return products[off : off + lim]


@api.get("/products/bulk-template")
async def products_bulk_template(fmt: str = "csv", user: dict = Depends(require_role("seller", "admin"))):
    """Return a CSV or XLSX template for bulk product upload.
    Query param `fmt`: 'csv' (default) or 'xlsx'.
    NOTE: This route MUST be declared before `/products/{product_id}` to avoid
    FastAPI matching 'bulk-template' as a product_id parameter.
    """
    from fastapi.responses import PlainTextResponse, Response
    headers = ["name", "category_name", "price_usd", "description", "stock", "image_url", "is_wholesale", "min_order_qty", "bulk_price_usd"]
    sample_rows = [
        ["Sample Product", "Groceries", 10.50, "A short description", 100, "", "false", 1, ""],
        ["Bulk Rice 50kg", "Groceries", 45.00, "Wholesale rice bag", 50, "", "true", 10, 42.00],
    ]
    if fmt.lower() == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from io import BytesIO
        wb = Workbook()
        ws = wb.active
        ws.title = "Products"
        ws.append(headers)
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="0E1A2B")
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        for r in sample_rows:
            ws.append(r)
        # Column widths for readability
        widths = [22, 18, 12, 32, 8, 30, 12, 14, 16]
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[chr(64 + i)].width = w
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return Response(
            content=buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=products_template.xlsx"},
        )
    # Default CSV
    import csv as _csv
    from io import StringIO
    buf = StringIO()
    w = _csv.writer(buf)
    w.writerow(headers)
    for r in sample_rows:
        w.writerow(r)
    return PlainTextResponse(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=products_template.csv"})


@api.get("/products/stock-update-template")
async def products_stock_update_template(fmt: str = "csv", user: dict = Depends(require_role("seller", "admin"))):
    """Return a CSV or XLSX template for bulk STOCK/PRICE update.
    Columns: product_id, stock, price_usd, bulk_price_usd
    - product_id is required; stock/price columns are optional (leave blank to skip that field).
    """
    from fastapi.responses import PlainTextResponse, Response
    headers = ["product_id", "stock", "price_usd", "bulk_price_usd"]
    sample_rows = [
        ["<paste product id here>", 100, 12.50, ""],
        ["<paste product id here>", 20, "", 8.75],
    ]
    if fmt.lower() == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from io import BytesIO
        wb = Workbook()
        ws = wb.active
        ws.title = "Stock Update"
        ws.append(headers)
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="0E1A2B")
            cell.alignment = Alignment(horizontal="center")
        for r in sample_rows:
            ws.append(r)
        for i, w in enumerate([40, 10, 12, 16], start=1):
            ws.column_dimensions[chr(64 + i)].width = w
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return Response(
            content=buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=stock_update_template.xlsx"},
        )
    import csv as _csv
    from io import StringIO
    buf = StringIO()
    w = _csv.writer(buf)
    w.writerow(headers)
    for r in sample_rows:
        w.writerow(r)
    return PlainTextResponse(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=stock_update_template.csv"})


@api.post("/products/bulk-stock-update")
async def bulk_stock_update(
    file: UploadFile = File(...),
    shop_id: str = Query(...),
    user: dict = Depends(require_role("seller", "admin")),
):
    """Bulk update stock/price for products in a shop from CSV or XLSX.
    Columns: product_id (required), stock, price_usd, bulk_price_usd (any of stock/price_usd/bulk_price_usd optional).
    """
    shop = await db.shops.find_one({"id": shop_id})
    if not shop:
        raise HTTPException(404, "Shop not found")
    if user["role"] != "admin" and shop["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")

    try:
        raw = await file.read()
        if len(raw) > 5 * 1024 * 1024:
            raise HTTPException(413, "File too large (max 5 MB)")
        _, rows_data = _rows_from_upload(raw, file.filename or "")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))

    results = {"total": 0, "updated": 0, "errors": [], "updated_ids": []}
    for idx, row in enumerate(rows_data, start=2):
        results["total"] += 1
        try:
            pid = (row.get("product_id") or "").strip()
            if not pid:
                raise ValueError("product_id is required")
            prod = await db.products.find_one({"id": pid, "shop_id": shop_id})
            if not prod:
                raise ValueError(f"product not found or not in this shop: {pid[:40]}")

            updates = {}
            stock_raw = (row.get("stock") or "").strip()
            if stock_raw != "":
                try:
                    updates["stock"] = max(0, int(float(stock_raw)))
                except Exception:
                    raise ValueError(f"invalid stock: '{stock_raw}'")

            price_raw = (row.get("price_usd") or "").strip()
            if price_raw != "":
                try:
                    v = float(price_raw)
                    if v < 0:
                        raise ValueError("negative price")
                    updates["price_usd"] = v
                except Exception:
                    raise ValueError(f"invalid price_usd: '{price_raw}'")

            bp_raw = (row.get("bulk_price_usd") or "").strip()
            if bp_raw != "":
                try:
                    v = float(bp_raw)
                    if v < 0:
                        raise ValueError("negative bulk price")
                    updates["bulk_price_usd"] = v
                except Exception:
                    raise ValueError(f"invalid bulk_price_usd: '{bp_raw}'")

            if not updates:
                raise ValueError("no fields to update (leave nothing blank on all columns)")

            await db.products.update_one({"id": pid}, {"$set": updates})
            results["updated"] += 1
            results["updated_ids"].append(pid)
        except Exception as e:
            results["errors"].append({"row": idx, "product_id": (row.get("product_id") or "").strip()[:40], "error": str(e)})

    return results


@api.get("/products/{product_id}")
async def get_product(product_id: str, request: Request):
    p = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Product not found")
    # Embed seller exchange rate
    s = await get_settings()
    global_rate = float(s.get("global_rate", 600.0))
    rec = await db.exchange_rates.find_one({"seller_id": p["seller_id"]}, {"_id": 0})
    p["exchange_rate_ssp"] = float(rec.get("rate", global_rate)) if rec else global_rate
    sh = await db.shops.find_one({"id": p["shop_id"]}, {"_id": 0, "verification": 1, "seller_id": 1, "is_public": 1, "is_deleted": 1})
    p["shop_verification"] = (sh or {}).get("verification", "Pending")
    # Gate product visibility on shop status: not Verified (when required) OR hidden OR deleted
    # means only owner/admin can view.
    require_verified = s.get("require_verification", True)
    restricted = (
        (sh or {}).get("is_deleted")
        or (sh or {}).get("is_public") is False
        or (require_verified and p["shop_verification"] != "Verified")
    )
    if restricted:
        try:
            u = await get_current_user(request)
        except HTTPException:
            raise HTTPException(404, "Product not found")
        if u.get("role") != "admin" and u.get("id") != (sh or {}).get("seller_id"):
            raise HTTPException(404, "Product not found")
    return p


@api.post("/products")
async def create_product(body: ProductIn, user: dict = Depends(require_role("seller", "admin"))):
    shop = await db.shops.find_one({"id": body.shop_id})
    if not shop:
        raise HTTPException(404, "Shop not found")
    if user["role"] != "admin" and shop["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    
    # VALIDATION: category_id must exist in categories collection
    cat = await db.categories.find_one({"id": body.category_id})
    if not cat:
        raise HTTPException(400, f"Invalid category_id: {body.category_id}. Category does not exist.")
    
    product = {
        "id": str(uuid.uuid4()),
        "seller_id": shop["seller_id"],
        "shop_kind": shop.get("kind", "retail"),
        "created_at": now_iso(),
        **body.model_dump(),
    }
    await db.products.insert_one(product)
    product.pop("_id", None)
    return product


def _rows_from_upload(raw: bytes, filename: str):
    """Parse CSV or XLSX bytes into a list of dict rows. Raises ValueError on failure."""
    lower = (filename or "").lower()
    # XLSX (or XLSM)
    if lower.endswith(".xlsx") or lower.endswith(".xlsm"):
        from openpyxl import load_workbook
        from io import BytesIO
        try:
            wb = load_workbook(BytesIO(raw), read_only=True, data_only=True)
            ws = wb.active
            it = ws.iter_rows(values_only=True)
            headers = None
            for row in it:
                if row and any(c is not None and str(c).strip() != "" for c in row):
                    headers = [str(c or "").strip() for c in row]
                    break
            if not headers:
                raise ValueError("Empty workbook")
            rows = []
            for row in it:
                if row is None or all(c is None or str(c).strip() == "" for c in row):
                    continue
                d = {}
                for i, h in enumerate(headers):
                    if not h:
                        continue
                    v = row[i] if i < len(row) else None
                    d[h] = "" if v is None else str(v)
                rows.append(d)
            return headers, rows
        except Exception as e:
            raise ValueError(f"Failed to parse XLSX: {e}")
    # CSV (default)
    import csv as _csv
    from io import StringIO
    try:
        text = raw.decode("utf-8-sig", errors="replace")
    except Exception as e:
        raise ValueError(f"Failed to decode file: {e}")
    reader = _csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV appears empty or malformed")
    headers = list(reader.fieldnames)
    rows = list(reader)
    return headers, rows


@api.post("/products/bulk-import")
async def bulk_import_products(
    request: Request,
    file: UploadFile = File(...),
    shop_id: str = Query(...),
    user: dict = Depends(require_role("seller", "admin")),
):
    """
    Bulk import products from CSV or XLSX.
    Columns: name, category_id (or category_name), price_usd, description, stock, image_url, is_wholesale, min_order_qty, bulk_price_usd
    """
    shop = await db.shops.find_one({"id": shop_id})
    if not shop:
        raise HTTPException(404, "Shop not found")
    if user["role"] != "admin" and shop["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")

    try:
        raw = await file.read()
        if len(raw) > 5 * 1024 * 1024:
            raise HTTPException(413, "File too large (max 5 MB)")
        _, rows_data = _rows_from_upload(raw, file.filename or "")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Preload categories for name→id lookup (retail group by default for products)
    all_cats = await db.categories.find({}, {"_id": 0}).to_list(1000)
    cat_by_id = {c["id"]: c for c in all_cats}
    cat_by_name = {(c.get("name") or "").strip().lower(): c for c in all_cats}

    results = {"total": 0, "created": 0, "errors": [], "created_ids": []}

    for idx, row in enumerate(rows_data, start=2):  # start=2 (row 1 = header)
        results["total"] += 1
        try:
            name = (row.get("name") or "").strip()
            if not name:
                raise ValueError("name is required")

            # Category resolution: try category_id first, then category_name
            cat_id = (row.get("category_id") or "").strip()
            if not cat_id:
                cat_name = (row.get("category_name") or row.get("category") or "").strip().lower()
                cat = cat_by_name.get(cat_name)
                if not cat:
                    raise ValueError(f"category not found: '{cat_name}' (provide category_id or valid category_name)")
                cat_id = cat["id"]
            elif cat_id not in cat_by_id:
                raise ValueError(f"category_id not found: {cat_id}")

            # Price
            price_raw = (row.get("price_usd") or row.get("price") or "").strip()
            try:
                price_usd = float(price_raw)
            except Exception:
                raise ValueError(f"invalid price_usd: '{price_raw}'")
            if price_usd < 0:
                raise ValueError("price_usd cannot be negative")

            stock_raw = (row.get("stock") or "100").strip()
            try:
                stock = int(float(stock_raw))
            except Exception:
                stock = 100

            is_wholesale = str(row.get("is_wholesale") or "").strip().lower() in ("1", "true", "yes", "y")
            min_qty_raw = (row.get("min_order_qty") or "1").strip()
            try:
                min_order_qty = max(1, int(float(min_qty_raw)))
            except Exception:
                min_order_qty = 1

            bulk_price = None
            bp_raw = (row.get("bulk_price_usd") or "").strip()
            if bp_raw:
                try:
                    bulk_price = float(bp_raw)
                except Exception:
                    bulk_price = None

            product = {
                "id": str(uuid.uuid4()),
                "seller_id": shop["seller_id"],
                "shop_id": shop_id,
                "shop_kind": shop.get("kind", "retail"),
                "name": name[:200],
                "category_id": cat_id,
                "category": cat_by_id[cat_id].get("name", ""),
                "price_usd": price_usd,
                "image_url": (row.get("image_url") or "").strip()[:1000],
                "description": (row.get("description") or "").strip()[:2000],
                "stock": stock,
                "is_wholesale": is_wholesale,
                "min_order_qty": min_order_qty,
                "bulk_price_usd": bulk_price,
                "mode": "wholesale" if is_wholesale else "marketplace",
                "pricing_tiers": [],
                "created_at": now_iso(),
            }
            await db.products.insert_one(product)
            results["created"] += 1
            results["created_ids"].append(product["id"])
        except Exception as e:
            results["errors"].append({"row": idx, "name": (row.get("name") or "").strip()[:80], "error": str(e)})

    # Mark onboarding: bulk_import_used (for the "Bulk import" step)
    if results["created"] > 0:
        try:
            await db.users.update_one(
                {"id": user["id"]},
                {"$set": {"meta.bulk_import_used": True}},
            )
        except Exception:
            pass

    return results


@api.put("/products/{product_id}")
async def update_product(product_id: str, body: ProductIn, user: dict = Depends(require_role("seller", "admin"))):
    p = await db.products.find_one({"id": product_id})
    if not p:
        raise HTTPException(404, "Product not found")
    if user["role"] != "admin" and p["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    
    # VALIDATION: category_id must exist in categories collection
    cat = await db.categories.find_one({"id": body.category_id})
    if not cat:
        raise HTTPException(400, f"Invalid category_id: {body.category_id}. Category does not exist.")
    
    await db.products.update_one({"id": product_id}, {"$set": body.model_dump()})
    return await db.products.find_one({"id": product_id}, {"_id": 0})


@api.delete("/products/{product_id}")
async def delete_product(product_id: str, user: dict = Depends(require_role("seller", "admin"))):
    p = await db.products.find_one({"id": product_id})
    if not p:
        raise HTTPException(404, "Product not found")
    if user["role"] != "admin" and p["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    await db.products.delete_one({"id": product_id})
    return {"ok": True}


# ----------------------------------------------------------------------------
# Restaurants & menu items
# ----------------------------------------------------------------------------
@api.get("/restaurants")
async def list_restaurants(request: Request, area: Optional[str] = None, category_id: Optional[str] = None,
                           category: Optional[str] = None,
                           limit: Optional[int] = None, skip: Optional[int] = None):
    """
    List restaurants with filtering.
    
    PRIMARY FILTER: category_id (UUID from categories table, group=restaurant)
    - When category_id is provided, returns restaurants that have menu_items with that category_id
    - Equivalent to: SELECT DISTINCT r.* FROM restaurants r
                     JOIN menu_items m ON m.restaurant_id = r.id
                     WHERE m.category_id = :category_id
    
    DEPRECATED: category (string name on restaurant doc, kept for backward compat only)
    """
    lim, off = clamp_pagination(limit, skip)
    
    # DEBUG: Log the filter being used
    import logging
    logger = logging.getLogger("uvicorn.error")
    logger.info(f"[RESTAURANTS FILTER] category_id={category_id}, category={category}, area={area}")
    
    s = await get_settings()
    # Skip verification gate for admins so the admin dashboard sees pending/rejected.
    caller_is_admin = False
    try:
        u = await get_current_user(request)
        caller_is_admin = u.get("role") == "admin"
    except HTTPException:
        pass
    require_verified = s.get("require_verification", True) and not caller_is_admin
    verified_filter: dict = {"verification": "Verified"} if require_verified else {}
    
    # PRIMARY: Filter by category_id through menu_items (database-driven)
    if category_id:
        logger.info(f"[RESTAURANTS FILTER] Using category_id filter: {category_id}")
        # Get all menu items with this category_id
        menu_items = await db.menu_items.find(
            {"category_id": category_id}, 
            {"_id": 0, "restaurant_id": 1}
        ).to_list(MAX_PAGE_LIMIT)
        
        logger.info(f"[RESTAURANTS FILTER] Found {len(menu_items)} menu items with category_id={category_id}")
        
        restaurant_ids = list({m["restaurant_id"] for m in menu_items})
        
        if not restaurant_ids:
            logger.info(f"[RESTAURANTS FILTER] No restaurants have menu items in category_id={category_id}")
            return []  # No restaurants have items in this category
        
        logger.info(f"[RESTAURANTS FILTER] Found {len(restaurant_ids)} unique restaurant IDs: {restaurant_ids}")
        
        # Fetch restaurants that have menu items in this category
        q: dict = {
            "id": {"$in": restaurant_ids},
            "is_deleted": {"$ne": True},
            **verified_filter,
        }
        if area:
            q["area"] = area
            
        rests = await db.restaurants.find(q, {"_id": 0}).to_list(MAX_PAGE_LIMIT + off + lim)
        logger.info(f"[RESTAURANTS FILTER] Returning {len(rests)} restaurants after filtering")
    else:
        logger.info("[RESTAURANTS FILTER] No category_id filter - returning all restaurants")
        # No category filter or legacy category filter
        q: dict = {"is_deleted": {"$ne": True}, **verified_filter}
        if area:
            q["area"] = area
        # DEPRECATED: legacy category name filter (backward compat only)
        if category:
            q["category"] = category
        rests = await db.restaurants.find(q, {"_id": 0}).to_list(MAX_PAGE_LIMIT + off + lim)
    
    # Verified-first sort
    if s.get("verified_first", True):
        order = {"Verified": 0, "Pending": 1, "Rejected": 2}
        rests.sort(key=lambda r: order.get(r.get("verification", "Pending"), 1))
    
    return rests[off : off + lim]


@api.get("/restaurants/mine")
async def my_restaurants(
    user: dict = Depends(require_role("seller", "admin")),
    limit: Optional[int] = None,
    skip: Optional[int] = None,
):
    """List restaurants owned by the current seller. Unlike the public
    `/restaurants` endpoint, this returns Pending / Rejected / non-Verified
    restaurants too, so the owner can view and manage them."""
    lim, off = clamp_pagination(limit, skip)
    q = {"seller_id": user["id"], "is_deleted": {"$ne": True}}
    return await db.restaurants.find(q, {"_id": 0}).skip(off).to_list(lim)


@api.get("/restaurants/{restaurant_id}")
async def get_restaurant(restaurant_id: str, request: Request):
    r = await db.restaurants.find_one({"id": restaurant_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Restaurant not found")
    # Hide non-Verified restaurants from customers (owner/admin still see them).
    s = await get_settings()
    require_verified = s.get("require_verification", True)
    is_restricted = r.get("is_deleted") or (
        require_verified and r.get("verification") != "Verified"
    )
    if is_restricted:
        try:
            u = await get_current_user(request)
        except HTTPException:
            raise HTTPException(404, "Restaurant not found")
        if u.get("role") != "admin" and u.get("id") != r.get("seller_id"):
            raise HTTPException(404, "Restaurant not found")
    # Apply auto-close-by-hours: overrides is_open=False when outside the
    # configured window for the current day. This is a derived flag (not
    # persisted) so it re-evaluates on every request.
    r["is_open_effective"] = _is_open_now(r)
    return r


def _is_open_now(restaurant: dict) -> bool:
    """Combines `is_open` with the auto-close-by-hours schedule.
    Returns False if the restaurant is manually closed OR (auto-close is on
    AND the current time is outside the day's window)."""
    if not restaurant.get("is_open", True):
        return False
    if not restaurant.get("auto_close_by_hours"):
        return True
    hours = (restaurant.get("opening_hours_by_day") or {})
    from datetime import datetime, timezone
    # Note: Juba is UTC+3. Adjust if the platform later needs multi-timezone.
    now = datetime.now(timezone.utc)
    # Rough Juba offset — good enough for opening-hours matching until we
    # store per-seller timezones.
    from datetime import timedelta as _td
    juba_now = now + _td(hours=3)
    day_key = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][juba_now.weekday()]
    cfg = hours.get(day_key)
    if not cfg or cfg.get("closed"):
        return False
    def _t(s: str) -> int:
        try:
            h, m = s.split(":")
            return int(h) * 60 + int(m)
        except Exception:
            return -1
    cur = juba_now.hour * 60 + juba_now.minute
    o = _t(cfg.get("open", "09:00"))
    c = _t(cfg.get("close", "22:00"))
    if o < 0 or c < 0:
        return True  # bad config → don't block
    if c <= o:
        # Overnight window (e.g. 20:00 → 02:00): open if past 'open' OR before 'close'
        return cur >= o or cur <= c
    return o <= cur <= c


@api.get("/restaurants/{restaurant_id}/menu")
async def get_menu(restaurant_id: str, request: Request, limit: Optional[int] = None, skip: Optional[int] = None):
    lim, off = clamp_pagination(limit, skip)
    # Gate menu access on the parent restaurant's verification state so customers
    # can't reach the menu of a non-Verified restaurant while sellers can still
    # preview their own.
    r = await db.restaurants.find_one(
        {"id": restaurant_id},
        {"_id": 0, "verification": 1, "seller_id": 1, "is_deleted": 1},
    )
    if not r:
        raise HTTPException(404, "Restaurant not found")
    s = await get_settings()
    require_verified = s.get("require_verification", True)
    is_restricted = r.get("is_deleted") or (
        require_verified and r.get("verification") != "Verified"
    )
    if is_restricted:
        try:
            u = await get_current_user(request)
        except HTTPException:
            raise HTTPException(404, "Restaurant not found")
        if u.get("role") != "admin" and u.get("id") != r.get("seller_id"):
            raise HTTPException(404, "Restaurant not found")
    items = await db.menu_items.find({"restaurant_id": restaurant_id}, {"_id": 0}).skip(off).to_list(lim)
    
    # Embed per-seller exchange rate (same as products endpoint)
    if items:
        seller_ids = list({m["seller_id"] for m in items})
        s = await get_settings()
        global_rate = float(s.get("global_rate", 600.0))
        rate_records = await db.exchange_rates.find(
            {"seller_id": {"$in": seller_ids}}, {"_id": 0}).to_list(1000)
        rate_by_seller = {r["seller_id"]: float(r.get("rate", global_rate)) for r in rate_records}
        
        for m in items:
            m["exchange_rate_ssp"] = rate_by_seller.get(m["seller_id"], global_rate)
    
    return items


@api.get("/menu-items")
async def list_menu_items(
    category_id: Optional[str] = None,
    food_category: Optional[str] = None,
    restaurant_id: Optional[str] = None,
    limit: Optional[int] = None,
    skip: Optional[int] = None,
):
    """
    Global list of restaurant menu items.
    
    PRIMARY FILTER: category_id (UUID from categories table, group=restaurant)
    DEPRECATED: food_category (string name, kept for backward compat only)
    """
    lim, off = clamp_pagination(limit, skip)
    q: dict = {}
    
    # PRIMARY: filter by category_id (single source of truth)
    if category_id:
        q["category_id"] = category_id
    # DEPRECATED: legacy food_category name filter (backward compat only)
    elif food_category:
        q["food_category"] = food_category
        
    if restaurant_id:
        q["restaurant_id"] = restaurant_id
    # Hide menu items belonging to soft-deleted restaurants, and (when
    # require_verification is enabled) non-Verified restaurants.
    _s = await get_settings()
    _hide_q: dict = {"$or": [{"is_deleted": True}]}
    if _s.get("require_verification", True):
        _hide_q["$or"].append({"verification": {"$ne": "Verified"}})
    hidden_rest = {
        r["id"]
        for r in await db.restaurants.find(
            _hide_q, {"_id": 0, "id": 1}
        ).to_list(MAX_PAGE_LIMIT)
    }
    items = await db.menu_items.find(q, {"_id": 0}).skip(off).to_list(lim)
    if hidden_rest:
        items = [m for m in items if m.get("restaurant_id") not in hidden_rest]
    
    # Embed per-seller exchange rate (same as products endpoint)
    if items:
        seller_ids = list({m["seller_id"] for m in items})
        s = await get_settings()
        global_rate = float(s.get("global_rate", 600.0))
        rate_records = await db.exchange_rates.find(
            {"seller_id": {"$in": seller_ids}}, {"_id": 0}).to_list(1000)
        rate_by_seller = {r["seller_id"]: float(r.get("rate", global_rate)) for r in rate_records}
        
        for m in items:
            m["exchange_rate_ssp"] = rate_by_seller.get(m["seller_id"], global_rate)
    
    return items


@api.post("/restaurants")
async def create_restaurant(body: RestaurantIn, user: dict = Depends(require_role("seller", "admin"))):
    s = await get_settings()
    initial_status = "Verified" if s.get("auto_approve_shops") else "Pending"
    payload = body.model_dump()
    if (payload.get("delivery_managed_by") or "default") == "default":
        payload["delivery_managed_by"] = "admin" if s.get("admin_manages_delivery") else "seller"
    r = {
        "id": str(uuid.uuid4()),
        "seller_id": user["id"],
        "verification": initial_status,
        "created_at": now_iso(),
        **payload,
        # Initialize Odoo connection as disabled by default
        "odoo_connection": {
            "enabled": False,
            "company_id": None,
            "company_name": None,
            "warehouse_id": None,
            "warehouse_name": None,
            "pricelist_id": None,
            "pricelist_name": None,
            "pos_config_id": None,
            "sync_products": False,
            "sync_stock": False,
            "send_orders": False,
            "send_delivery_updates": False,
            "last_sync_at": None,
            "sync_status": "not_configured",
            "sync_error": None
        }
    }
    await db.restaurants.insert_one(r)
    r.pop("_id", None)
    return r


@api.put("/restaurants/{restaurant_id}/toggle-open")
async def toggle_open(restaurant_id: str, user: dict = Depends(require_role("seller", "admin"))):
    r = await db.restaurants.find_one({"id": restaurant_id})
    if not r:
        raise HTTPException(404, "Restaurant not found")
    if user["role"] != "admin" and r["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    new_state = not r.get("is_open", True)
    await db.restaurants.update_one({"id": restaurant_id}, {"$set": {"is_open": new_state}})
    return {"is_open": new_state}



@api.put("/restaurants/{restaurant_id}")
async def update_restaurant(restaurant_id: str, body: RestaurantIn, user: dict = Depends(require_role("seller", "admin"))):
    """Update restaurant details (name, category, description, area, image, delivery_pricing)"""
    r = await db.restaurants.find_one({"id": restaurant_id})
    if not r:
        raise HTTPException(404, "Restaurant not found")
    if user["role"] != "admin" and r["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    
    update_data = {
        "name": body.name,
        "category": body.category,
        "description": body.description or "",
        "image_url": body.image_url or "",
        "area": body.area,
        "is_open": body.is_open,
        "delivery_pricing": body.delivery_pricing.model_dump() if body.delivery_pricing else None,
        # Mirror-of-shop delivery fields (seller-controlled). NOTE: only
        # admins can change `delivery_managed_by` — for sellers we ignore
        # any value they send and preserve whatever's already stored.
        "delivery_mode": body.delivery_mode,
        "delivery_fee_usd": float(body.delivery_fee_usd or 0),
        "delivery_per_area": [a.model_dump() for a in (body.delivery_per_area or [])],
        # Opening-hours schedule + auto-close toggle. Persisted as-is; the
        # `is_open_effective` derived flag is recomputed on every GET.
        "opening_hours_by_day": {
            k: v.model_dump() if hasattr(v, "model_dump") else v
            for k, v in (body.opening_hours_by_day or {}).items()
        },
        "auto_close_by_hours": bool(body.auto_close_by_hours),
        # Iter 25 additions — customer receipt logo + estimated delivery.
        "receipt_show_logo": bool(body.receipt_show_logo),
        "receipt_logo_url": (body.receipt_logo_url or "").strip(),
        "eta_mode": body.eta_mode or "off",
        "eta_fixed_minutes": body.eta_fixed_minutes,
        "eta_min_minutes": body.eta_min_minutes,
        "eta_max_minutes": body.eta_max_minutes,
    }
    # Iter 27 — Sanitise + enforce max 6 menu sections
    ms = [s.model_dump() for s in (body.menu_sections or [])]
    seen = set()
    clean_ms = []
    for s in ms:
        if not s.get("id") or s["id"] in seen:
            continue
        name = (s.get("name") or "").strip()
        if not name:
            continue
        seen.add(s["id"])
        clean_ms.append({"id": s["id"], "name": name[:40], "sort_order": int(s.get("sort_order") or 0)})
    if len(clean_ms) > 6:
        raise HTTPException(400, "Maximum 6 menu sections allowed")
    update_data["menu_sections"] = clean_ms
    if user["role"] == "admin":
        update_data["delivery_managed_by"] = body.delivery_managed_by
    await db.restaurants.update_one({"id": restaurant_id}, {"$set": update_data})
    return await db.restaurants.find_one({"id": restaurant_id}, {"_id": 0})



@api.delete("/restaurants/{restaurant_id}")
async def delete_restaurant(restaurant_id: str, user: dict = Depends(require_role("seller", "admin"))):
    """Soft delete a restaurant - marks it as deleted and deactivates its menu items"""
    r = await db.restaurants.find_one({"id": restaurant_id})
    if not r:
        raise HTTPException(404, "Restaurant not found")
    if user["role"] != "admin" and r["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    
    # Soft delete - similar to shops
    await db.restaurants.update_one(
        {"id": restaurant_id},
        {"$set": {"is_deleted": True, "is_open": False, "deleted_at": now_iso()}},
    )
    
    # Deactivate all menu items
    await db.menu_items.update_many(
        {"restaurant_id": restaurant_id},
        {"$set": {"is_active": False}},
    )
    
    return {"ok": True, "message": "Restaurant deleted - menu items deactivated"}


@api.post("/menu-items")
async def create_menu_item(body: MenuItemIn, user: dict = Depends(require_role("seller", "admin"))):
    r = await db.restaurants.find_one({"id": body.restaurant_id})
    if not r:
        raise HTTPException(404, "Restaurant not found")
    if user["role"] != "admin" and r["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    
    # VALIDATION: category_id must exist in categories collection (group=restaurant)
    cat = await db.categories.find_one({"id": body.category_id})
    if not cat:
        raise HTTPException(400, f"Invalid category_id: {body.category_id}. Category does not exist.")
    if cat.get("group") != "restaurant":
        raise HTTPException(400, f"Invalid category_id: {body.category_id}. Must be a restaurant/food category (group=restaurant).")
    
    item = {
        "id": str(uuid.uuid4()),
        "seller_id": r["seller_id"],
        "created_at": now_iso(),
        **body.model_dump(),
    }
    await db.menu_items.insert_one(item)
    item.pop("_id", None)
    return item


@api.put("/menu-items/{item_id}")
async def update_menu_item(item_id: str, body: MenuItemIn, user: dict = Depends(require_role("seller", "admin"))):
    item = await db.menu_items.find_one({"id": item_id})
    if not item:
        raise HTTPException(404, "Item not found")
    if user["role"] != "admin" and item["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    
    # VALIDATION: category_id must exist in categories collection (group=restaurant)
    cat = await db.categories.find_one({"id": body.category_id})
    if not cat:
        raise HTTPException(400, f"Invalid category_id: {body.category_id}. Category does not exist.")
    if cat.get("group") != "restaurant":
        raise HTTPException(400, f"Invalid category_id: {body.category_id}. Must be a restaurant/food category (group=restaurant).")
    
    await db.menu_items.update_one({"id": item_id}, {"$set": body.model_dump()})
    return await db.menu_items.find_one({"id": item_id}, {"_id": 0})


@api.delete("/menu-items/{item_id}")
async def delete_menu_item(item_id: str, user: dict = Depends(require_role("seller", "admin"))):
    item = await db.menu_items.find_one({"id": item_id})
    if not item:
        raise HTTPException(404, "Item not found")
    if user["role"] != "admin" and item["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    await db.menu_items.delete_one({"id": item_id})
    return {"ok": True}


# ----------------------------------------------------------------------------
# Restaurant Orders (separate from marketplace orders)
# ----------------------------------------------------------------------------
@api.post("/restaurant-orders/quote")
async def quote_restaurant_order(body: RestaurantOrderQuoteIn, user: dict = Depends(get_current_user)):
    """Calculate delivery fee preview for restaurant order without creating it."""
    if body.delivery_type == "pickup":
        return {"delivery_fee_usd": 0, "subtotal_usd": 0, "total_usd": 0}
    
    # Get restaurant area as pickup area
    restaurant = await db.restaurants.find_one({"id": body.restaurant_id})
    if not restaurant:
        raise HTTPException(404, "Restaurant not found")
    
    pickup_area = restaurant.get("area", "")
    delivery_area = body.customer_area or user.get("area", "")
    
    # Calculate using admin rules
    from cod import _calculate_delivery_fee
    delivery_fee = await _calculate_delivery_fee(
        pickup_area=pickup_area,
        delivery_area=delivery_area,
        order_type="restaurant",
        shop_id=None,
        restaurant_id=body.restaurant_id
    )
    
    # Calculate subtotal from items
    subtotal = sum(
        it.price_usd * it.quantity + sum(sd.price_usd for sd in (it.sides or [])) * it.quantity 
        for it in body.items
    )
    
    return {
        "delivery_fee_usd": round(delivery_fee, 2),
        "subtotal_usd": round(subtotal, 2),
        "total_usd": round(subtotal + delivery_fee, 2),
        "pickup_area": pickup_area,
        "delivery_area": delivery_area,
    }


@api.post("/restaurant-orders")
async def create_restaurant_order(body: RestaurantOrderIn, user: dict = Depends(get_current_user)):
    """Create a restaurant order (food delivery/pickup)"""
    # Validate restaurant exists
    restaurant = await db.restaurants.find_one({"id": body.restaurant_id})
    if not restaurant:
        raise HTTPException(404, "Restaurant not found")
    if restaurant.get("is_deleted"):
        raise HTTPException(404, "Restaurant not found")
    if not restaurant.get("is_open", True):
        raise HTTPException(400, "Restaurant is currently closed. Please try again later.")
    
    # SECURITY: Calculate delivery fee using admin pricing rules. Never trust frontend prices.
    from cod import _calculate_delivery_fee
    
    delivery_fee = 0.0
    pickup_area = ""
    delivery_area = ""
    
    if body.delivery_type == "delivery":
        # Get restaurant area as pickup area
        pickup_area = restaurant.get("area", "")
        # Get customer area from request body (preferred) or user profile fallback
        delivery_area = body.customer_area or user.get("area", "")
        
        # Calculate using admin rules
        delivery_fee = await _calculate_delivery_fee(
            pickup_area=pickup_area,
            delivery_area=delivery_area,
            order_type="restaurant",
            shop_id=None,
            restaurant_id=body.restaurant_id
        )
    
    # SECURITY: Recompute item prices from DB (never trust frontend prices).
    item_ids = [it.item_id for it in body.items]
    menu_db = await db.menu_items.find({"id": {"$in": item_ids}}, {"_id": 0}).to_list(2000)
    menu_by_id = {m["id"]: m for m in menu_db}
    secure_items = []
    subtotal = 0.0
    for item in body.items:
        m = menu_by_id.get(item.item_id)
        if not m:
            raise HTTPException(400, f"Menu item {item.item_id} not found")
        qty = max(1, int(item.quantity))
        # Effective price = raw price MINUS active promo (server-side, so a
        # crafted client can't fake a lower price). See effective_price_usd
        # in this file.
        price = effective_price_usd(m)
        sides_total = sum(float(s.price_usd) for s in (item.sides or []))
        # Iter 26 — REQUIRED-SIDES validation. When the menu item is
        # configured with `sides_required=True`, the customer must have
        # picked between sides_min_choices (default 1) and sides_max_choices
        # (default unlimited) side items. Reject the order otherwise so a
        # crafted frontend cannot bypass the rule.
        if m.get("sides_required"):
            allowed_names = {s.get("name") for s in (m.get("side_items") or [])}
            picked_names = [s.name for s in (item.sides or [])]
            invalid = [n for n in picked_names if n not in allowed_names]
            if invalid:
                raise HTTPException(400, f"Invalid sides for {m['name']}: {invalid}")
            min_n = m.get("sides_min_choices")
            if min_n is None: min_n = 1
            max_n = m.get("sides_max_choices")  # None → unlimited
            if len(picked_names) < min_n:
                raise HTTPException(400, f"{m['name']} requires at least {min_n} side item(s); got {len(picked_names)}")
            if max_n is not None and len(picked_names) > max_n:
                raise HTTPException(400, f"{m['name']} allows at most {max_n} side item(s); got {len(picked_names)}")
        line = (price + sides_total) * qty
        subtotal += line
        secure_items.append({
            "item_type": "menu_item",
            "item_id": m["id"],
            "name": m.get("name"),
            "price_usd": price,
            "quantity": qty,
            "image_url": m.get("image_url", ""),
            "sides": [s.model_dump() for s in (item.sides or [])],
        })

    total = subtotal + delivery_fee
    
    # Create order
    order = {
        "id": str(uuid.uuid4()),
        "restaurant_id": body.restaurant_id,
        "restaurant_name": restaurant.get("name"),
        "restaurant_area": restaurant.get("area", ""),
        "customer_id": user["id"],
        "customer_name": body.customer_name,
        "customer_phone": body.customer_phone,
        "customer_address": body.customer_address,
        "customer_area": delivery_area,  # NEW: Store delivery area
        "pickup_area": pickup_area,  # NEW: Store pickup area for pricing reference
        "delivery_area": delivery_area,  # NEW: Store delivery area for pricing reference
        "items": secure_items,
        "delivery_type": body.delivery_type,
        "payment_method": body.payment_method,
        "note": body.note,
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": total,
        "status": "pending",  # pending → accepted → cooking → ready → completed
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    
    await db.restaurant_orders.insert_one(order)
    order.pop("_id", None)

    # Initialize COD/driver fields on the restaurant order (single-seller, inline).
    try:
        cod_fields = await cod.initialize_restaurant_order_cod(order)
        await db.restaurant_orders.update_one({"id": order["id"]}, {"$set": cod_fields})
        order.update(cod_fields)
    except Exception as e:
        log.warning(f"restaurant COD init failed for order {order['id']}: {e}")
    
    # Track trending
    await db.trending_stats.update_one(
        {"target_type": "restaurant", "target_id": body.restaurant_id},
        {"$inc": {"order_count": 1}, "$set": {"updated_at": now_iso()}},
        upsert=True
    )
    
    return order


@api.get("/restaurant-orders")
async def list_restaurant_orders(user: dict = Depends(get_current_user)):
    """List user's restaurant orders"""
    if user["role"] == "customer":
        # Customer sees their own orders
        orders = await db.restaurant_orders.find(
            {"customer_id": user["id"]},
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        # Enrich with has_review flag so the UI can show "Reviewed" state
        order_ids = [o["id"] for o in orders]
        if order_ids:
            reviewed = await db.reviews.find(
                {"order_id": {"$in": order_ids}, "user_id": user["id"]},
                {"_id": 0, "order_id": 1, "id": 1, "rating": 1},
            ).to_list(len(order_ids))
            reviewed_map = {r["order_id"]: r for r in reviewed}
            for o in orders:
                rv = reviewed_map.get(o["id"])
                o["has_review"] = rv is not None
                if rv:
                    o["review_id"] = rv.get("id")
                    o["review_rating"] = rv.get("rating")
        # Redact seller/driver OTPs from customer view
        return await enrich_restaurant_orders(cod.redact_many_for_customer(orders))
    elif user["role"] in ["seller", "admin"]:
        # Seller sees orders for their restaurants
        restaurants = await db.restaurants.find(
            {"seller_id": user["id"]},
            {"_id": 0, "id": 1}
        ).to_list(100)
        restaurant_ids = [r["id"] for r in restaurants]
        
        if user["role"] == "admin":
            # Admin sees all orders
            orders = await db.restaurant_orders.find(
                {},
                {"_id": 0}
            ).sort("created_at", -1).to_list(200)
        else:
            # Seller sees only their restaurant orders
            orders = await db.restaurant_orders.find(
                {"restaurant_id": {"$in": restaurant_ids}},
                {"_id": 0}
            ).sort("created_at", -1).to_list(200)
    else:
        orders = []
    
    return await enrich_restaurant_orders(orders)


@api.get("/restaurant-orders/restaurant/{restaurant_id}")
async def list_restaurant_orders_by_restaurant(
    restaurant_id: str,
    status: Optional[str] = None,
    include_history: bool = False,
    user: dict = Depends(require_role("seller", "admin"))
):
    """List orders for a specific restaurant (Kitchen Dashboard).
    
    Args:
        include_history: If True, includes orders that have been handed to driver,
                        cancelled, or returned (for history panel)
    """
    # Verify seller owns the restaurant
    restaurant = await db.restaurants.find_one({"id": restaurant_id})
    if not restaurant:
        raise HTTPException(404, "Restaurant not found")
    
    if user["role"] != "admin" and restaurant["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    
    query = {"restaurant_id": restaurant_id}
    if status:
        query["status"] = status
    elif not include_history:
        # Exclude historical orders by default (only completed, cancelled, delivered, or returned)
        # Keep handed_to_driver in active view until delivery is confirmed
        query["$and"] = [
            {"status": {"$nin": ["completed", "cancelled", "cancel_approved"]}},
            {"delivery_status": {"$nin": ["delivered", "returned_to_seller"]}}
        ]
    
    orders = await db.restaurant_orders.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    # Sellers must not see customer phone/area/address UNLESS they manage
    # delivery for this restaurant (in that case, they ARE the driver).
    if user["role"] != "admin":
        seller_manages = await _seller_manages_delivery_for(restaurant=restaurant)
        for o in orders:
            cod.redact_for_seller(o, seller_manages_delivery=seller_manages)
    # Attach seller's exchange_rate_ssp so the Kitchen Dashboard receipt
    # renders SSP totals at the SELLER's rate (not the 600 fallback).
    return await enrich_restaurant_orders(orders)


@api.get("/restaurant-orders/{order_id}")
async def get_restaurant_order(order_id: str, user: dict = Depends(get_current_user)):
    """Get single restaurant order"""
    order = await db.restaurant_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order not found")
    
    # Check permissions
    if user["role"] == "customer" and order["customer_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    elif user["role"] == "seller":
        restaurant = await db.restaurants.find_one({"id": order["restaurant_id"]})
        if restaurant and restaurant["seller_id"] != user["id"]:
            raise HTTPException(403, "Forbidden")
        seller_manages = await _seller_manages_delivery_for(restaurant=restaurant)
        cod.redact_for_seller(order, seller_manages_delivery=seller_manages)
    
    # Attach the seller's exchange_rate_ssp so SSP renderings (receipts,
    # order pages) use the correct rate rather than the 600 fallback.
    enriched = await enrich_restaurant_orders([order])
    return enriched[0] if enriched else order


@api.put("/restaurant-orders/{order_id}/status")
async def update_restaurant_order_status(
    order_id: str,
    body: OrderStatusUpdate,
    user: dict = Depends(require_role("seller", "admin"))
):
    """Update restaurant order status (Kitchen Dashboard).
    Sellers may move forward (pending → accepted → cooking → ready → completed).
    Sellers may NOT set cancelled/cancel_approved/cancel_rejected directly —
    those go through the admin-approval flow at /restaurant-orders/{id}/request-cancel."""
    order = await db.restaurant_orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Order not found")

    # Verify seller owns the restaurant
    if user["role"] != "admin":
        restaurant = await db.restaurants.find_one({"id": order["restaurant_id"]})
        if not restaurant or restaurant["seller_id"] != user["id"]:
            raise HTTPException(403, "Forbidden")
        # Sellers cannot bypass the admin-approval flow
        if body.status in {"cancelled", "cancel_approved", "cancel_rejected"}:
            raise HTTPException(
                403,
                "Use POST /restaurant-orders/{id}/request-cancel — cancellations require admin approval.",
            )

    await db.restaurant_orders.update_one(
        {"id": order_id},
        {"$set": {"status": body.status, "updated_at": now_iso()}}
    )

    # Trigger invoice rebuild on completion so commission is captured.
    if body.status == "completed":
        try:
            await _rebuild_restaurant_invoices()
        except Exception as e:
            log.warning(f"Restaurant-invoice rebuild after completion failed: {e}")

    return {"ok": True, "status": body.status}


# ----------------------------------------------------------------------------
# Cancellation request flow (seller → admin approval)
# ----------------------------------------------------------------------------
@api.post("/restaurant-orders/{order_id}/request-cancel")
async def request_order_cancel(
    order_id: str,
    body: CancelRequestIn,
    user: dict = Depends(require_role("seller", "admin")),
):
    """Seller requests cancellation of an in-progress order.
    Allowed when current status ∈ {accepted, cooking, ready}. Stores previous_status
    so admin can either approve (→ cancel_approved) or reject (→ revert)."""
    order = await db.restaurant_orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Order not found")

    if user["role"] != "admin":
        restaurant = await db.restaurants.find_one({"id": order["restaurant_id"]})
        if not restaurant or restaurant["seller_id"] != user["id"]:
            raise HTTPException(403, "Forbidden")

    current = order.get("status")
    if current not in {"accepted", "cooking", "ready"}:
        raise HTTPException(400, f"Cannot request cancellation from status '{current}'")

    await db.restaurant_orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": "cancel_requested",
            "previous_status": current,
            "cancel_reason": body.reason or "",
            "cancel_requested_at": now_iso(),
            "updated_at": now_iso(),
        }},
    )

    # Notify customer that the seller has requested cancellation
    customer_id = order.get("customer_id")
    if customer_id:
        await create_notification(
            user_id=customer_id,
            message=f"The restaurant has requested to cancel your order #{order_id[:8]}. Awaiting admin review.",
            ntype="order",
            meta={"order_id": order_id, "kind": "restaurant", "cancel_request": True},
        )
    # Notify seller (acknowledgement) — useful for sellers acting via admin override too
    seller_id = None
    if order.get("restaurant_id"):
        rest = await db.restaurants.find_one({"id": order["restaurant_id"]})
        seller_id = (rest or {}).get("seller_id")
    if seller_id:
        await create_notification(
            user_id=seller_id,
            message=f"Cancellation request submitted for order #{order_id[:8]} — pending admin review.",
            ntype="order",
            meta={"order_id": order_id, "kind": "restaurant", "cancel_request": True},
        )
    return {"ok": True, "status": "cancel_requested", "previous_status": current}


@api.get("/admin/cancel-requests")
async def admin_list_cancel_requests(_: dict = Depends(require_role("admin"))):
    """All pending cancellation requests across restaurants."""
    return await db.restaurant_orders.find(
        {"status": "cancel_requested"}, {"_id": 0}
    ).sort("cancel_requested_at", -1).to_list(500)


@api.post("/admin/cancel-requests/{order_id}/approve")
async def admin_approve_cancel(order_id: str, _: dict = Depends(require_role("admin"))):
    """Admin approves cancellation → status becomes cancel_approved (terminal)."""
    order = await db.restaurant_orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Order not found")
    if order.get("status") != "cancel_requested":
        raise HTTPException(400, "No pending cancellation request")

    await db.restaurant_orders.update_one(
        {"id": order_id},
        {"$set": {"status": "cancel_approved", "cancel_outcome": "approved", "cancel_decided_at": now_iso(), "updated_at": now_iso()}},
    )
    # Notify customer
    customer_id = order.get("customer_id")
    if customer_id:
        await create_notification(
            user_id=customer_id,
            message=f"Your order #{order_id[:8]} was cancelled by the restaurant (admin-approved).",
            ntype="order",
            meta={"order_id": order_id, "kind": "restaurant", "cancel_approved": True},
        )
    # Notify seller
    restaurant = await db.restaurants.find_one({"id": order.get("restaurant_id")})
    seller_id = restaurant.get("seller_id") if restaurant else None
    if seller_id:
        await create_notification(
            user_id=seller_id,
            message=f"Cancellation approved for order #{order_id[:8]}.",
            ntype="order",
            meta={"order_id": order_id, "kind": "restaurant", "cancel_approved": True},
        )
    return {"ok": True, "status": "cancel_approved"}


@api.post("/admin/cancel-requests/{order_id}/reject")
async def admin_reject_cancel(order_id: str, body: CancelRejectIn, _: dict = Depends(require_role("admin"))):
    """Admin rejects cancellation → order status becomes cancel_denied and seller can take action."""
    order = await db.restaurant_orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Order not found")
    if order.get("status") != "cancel_requested":
        raise HTTPException(400, "No pending cancellation request")

    await db.restaurant_orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": "cancel_denied",
            "cancel_outcome": "rejected",
            "cancel_decided_at": now_iso(),
            "cancel_rejected_note": body.admin_note or "",
            "updated_at": now_iso(),
        }},
    )
    # Notify customer (per user requirement)
    customer_id = order.get("customer_id")
    if customer_id:
        await create_notification(
            user_id=customer_id,
            message=(
                f"Cancellation request for your order #{order_id[:8]} was rejected. "
                f"The restaurant will continue processing your order."
            ),
            ntype="order",
            meta={"order_id": order_id, "kind": "restaurant", "cancel_rejected": True},
        )
    # Notify seller
    restaurant = await db.restaurants.find_one({"id": order.get("restaurant_id")})
    seller_id = restaurant.get("seller_id") if restaurant else None
    if seller_id:
        msg = f"Cancellation rejected for order #{order_id[:8]}."
        if body.admin_note:
            msg += f" Reason: {body.admin_note}"
        await create_notification(
            user_id=seller_id, message=msg, ntype="order",
            meta={"order_id": order_id, "kind": "restaurant", "cancel_rejected": True},
        )
    return {"ok": True, "status": "cancel_denied"}


@api.post("/restaurant-orders/{order_id}/return-to-previous")
async def return_to_previous_status(order_id: str, user: dict = Depends(require_role("seller", "admin"))):
    """Seller returns denied cancellation order back to its previous status."""
    order = await db.restaurant_orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Order not found")
    if order.get("status") != "cancel_denied":
        raise HTTPException(400, "Order is not in cancel_denied status")
    
    # Verify seller owns the restaurant
    if user["role"] != "admin":
        restaurant = await db.restaurants.find_one({"id": order["restaurant_id"]})
        if not restaurant or restaurant["seller_id"] != user["id"]:
            raise HTTPException(403, "Forbidden")
    
    previous = order.get("previous_status") or "accepted"
    await db.restaurant_orders.update_one(
        {"id": order_id},
        {"$set": {"status": previous, "updated_at": now_iso()}},
    )
    return {"ok": True, "status": previous}


@api.post("/restaurant-orders/{order_id}/mark-received")
async def mark_order_received_by_customer(order_id: str, user: dict = Depends(require_role("seller", "admin"))):
    """Seller marks that customer received order (denied cancellation) → goes to completed."""
    order = await db.restaurant_orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Order not found")
    if order.get("status") != "cancel_denied":
        raise HTTPException(400, "Order is not in cancel_denied status")
    
    # Verify seller owns the restaurant
    if user["role"] != "admin":
        restaurant = await db.restaurants.find_one({"id": order["restaurant_id"]})
        if not restaurant or restaurant["seller_id"] != user["id"]:
            raise HTTPException(403, "Forbidden")
    
    await db.restaurant_orders.update_one(
        {"id": order_id},
        {"$set": {"status": "completed", "updated_at": now_iso()}},
    )
    
    # Trigger invoice rebuild
    try:
        await _rebuild_restaurant_invoices()
    except Exception as e:
        print(f"Invoice rebuild error: {e}")
    
    return {"ok": True, "status": "completed"}


# ----------------------------------------------------------------------------
# Reviews & Ratings
# ----------------------------------------------------------------------------
@api.post("/reviews")
async def create_review(body: ReviewIn, user: dict = Depends(get_current_user)):
    """Create a review for a restaurant (only after order completion)"""
    # Verify order exists and is completed
    order = await db.restaurant_orders.find_one({"id": body.order_id})
    if not order:
        raise HTTPException(404, "Order not found")
    
    if order["customer_id"] != user["id"]:
        raise HTTPException(403, "You can only review your own orders")
    
    if order["status"] != "completed":
        raise HTTPException(400, "You can only review completed orders")
    
    # Check if already reviewed
    existing = await db.reviews.find_one({"order_id": body.order_id})
    if existing:
        raise HTTPException(400, "You have already reviewed this order")
    
    review = {
        "id": str(uuid.uuid4()),
        "restaurant_id": body.restaurant_id,
        "order_id": body.order_id,
        "user_id": user["id"],
        "user_name": user.get("name", "Anonymous"),
        "rating": body.rating,
        "comment": body.comment,
        "created_at": now_iso(),
    }
    
    await db.reviews.insert_one(review)
    
    # Update restaurant average rating
    all_reviews = await db.reviews.find({"restaurant_id": body.restaurant_id}, {"_id": 0, "rating": 1}).to_list(1000)
    avg_rating = sum(r["rating"] for r in all_reviews) / len(all_reviews) if all_reviews else 0
    review_count = len(all_reviews)
    
    await db.restaurants.update_one(
        {"id": body.restaurant_id},
        {"$set": {"average_rating": round(avg_rating, 1), "review_count": review_count}}
    )
    
    review.pop("_id", None)
    return review


@api.get("/reviews")
async def list_restaurant_reviews(restaurant_id: str, limit: Optional[int] = 20, skip: Optional[int] = 0):
    """List reviews for a restaurant"""
    lim, off = clamp_pagination(limit, skip)
    reviews = await db.reviews.find(
        {"restaurant_id": restaurant_id},
        {"_id": 0}
    ).sort("created_at", -1).skip(off).limit(lim).to_list(lim)
    
    return reviews


# ----------------------------------------------------------------------------
# Favorites
# ----------------------------------------------------------------------------
@api.post("/favorites")
async def add_favorite(body: FavoriteIn, user: dict = Depends(get_current_user)):
    """Add a restaurant/shop/product to favorites"""
    # Check if already favorited
    existing = await db.favorites.find_one({
        "user_id": user["id"],
        "target_type": body.target_type,
        "target_id": body.target_id
    })
    
    if existing:
        return {"ok": True, "message": "Already in favorites", "id": existing["id"]}
    
    favorite = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "target_type": body.target_type,
        "target_id": body.target_id,
        "created_at": now_iso(),
    }
    
    await db.favorites.insert_one(favorite)
    favorite.pop("_id", None)
    return favorite


@api.delete("/favorites/{favorite_id}")
async def remove_favorite(favorite_id: str, user: dict = Depends(get_current_user)):
    """Remove from favorites"""
    fav = await db.favorites.find_one({"id": favorite_id})
    if not fav:
        raise HTTPException(404, "Favorite not found")
    
    if fav["user_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    
    await db.favorites.delete_one({"id": favorite_id})
    return {"ok": True}


@api.get("/favorites")
async def list_favorites(user: dict = Depends(get_current_user)):
    """List user's favorites"""
    favorites = await db.favorites.find(
        {"user_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    
    # Enrich with actual data
    enriched = []
    for fav in favorites:
        if fav["target_type"] == "restaurant":
            item = await db.restaurants.find_one({"id": fav["target_id"]}, {"_id": 0})
        elif fav["target_type"] == "shop":
            item = await db.shops.find_one({"id": fav["target_id"]}, {"_id": 0})
        elif fav["target_type"] == "product":
            item = await db.products.find_one({"id": fav["target_id"]}, {"_id": 0})
        else:
            item = None
        
        if item:
            enriched.append({
                "favorite_id": fav["id"],
                "target_type": fav["target_type"],
                "created_at": fav["created_at"],
                "item": item
            })
    
    return enriched


# ----------------------------------------------------------------------------
# Trending System
# ----------------------------------------------------------------------------
@api.post("/trending/click")
async def track_trending_click(body: TrendingClickIn):
    """Track a click for trending statistics (no auth required)"""
    await db.trending_stats.update_one(
        {"target_type": body.target_type, "target_id": body.target_id},
        {
            "$inc": {"click_count": 1},
            "$set": {"updated_at": now_iso()}
        },
        upsert=True
    )
    return {"ok": True}


# ----------------------------------------------------------------------------
# Orders
# ----------------------------------------------------------------------------


# ----------------------------------------------------------------------------
# Global search — restaurants + products + shops grouped, used by Header bar
# ----------------------------------------------------------------------------
import re as _re

@api.get("/search")
async def global_search(q: str = "", limit: int = 5):
    """Case-insensitive substring search on name (and description) across
    restaurants, shops and products. Returns up to `limit` of each group,
    excluding soft-deleted/hidden items. Returns empty lists for q='' or
    queries shorter than 2 chars so the UI can short-circuit."""
    q = (q or "").strip()
    if len(q) < 2:
        return {"restaurants": [], "shops": [], "products": [], "query": q}

    limit = max(1, min(int(limit or 5), 20))
    pat = _re.escape(q)
    name_rx = {"$regex": pat, "$options": "i"}
    desc_rx = {"$regex": pat, "$options": "i"}

    projection = {"_id": 0, "id": 1, "name": 1, "image_url": 1, "area": 1, "category": 1}

    # Restaurants — exclude soft-deleted, surface "Closed" badge but still show
    restaurants = await db.restaurants.find(
        {"$or": [{"name": name_rx}, {"description": desc_rx}], "is_deleted": {"$ne": True}},
        {**projection, "is_open": 1, "average_rating": 1, "review_count": 1},
    ).limit(limit).to_list(limit)

    # Shops — exclude hidden/deleted from public results
    shops = await db.shops.find(
        {
            "$or": [{"name": name_rx}, {"description": desc_rx}],
            "is_deleted": {"$ne": True},
            "is_public": {"$ne": False},
        },
        {**projection, "verification": 1},
    ).limit(limit).to_list(limit)

    # Products — exclude inactive
    products = await db.products.find(
        {
            "$or": [{"name": name_rx}, {"description": desc_rx}],
            "is_active": {"$ne": False},
        },
        {**projection, "price_usd": 1, "shop_id": 1, "is_wholesale": 1},
    ).limit(limit).to_list(limit)

    return {
        "restaurants": restaurants,
        "shops": shops,
        "products": products,
        "query": q,
    }


@api.get("/trending/restaurants")
async def get_trending_restaurants(limit: Optional[int] = 10):
    """Get trending restaurants (by clicks + orders)"""
    # Get top trending restaurants
    trending = await db.trending_stats.find(
        {"target_type": "restaurant"},
        {"_id": 0}
    ).sort([("click_count", -1), ("order_count", -1)]).limit(limit).to_list(limit)
    
    # Enrich with restaurant data
    restaurant_ids = [t["target_id"] for t in trending]
    restaurants = await db.restaurants.find(
        {"id": {"$in": restaurant_ids}, "is_deleted": {"$ne": True}},
        {"_id": 0}
    ).to_list(limit)
    
    # Sort by trending stats
    restaurant_map = {r["id"]: r for r in restaurants}
    result = []
    for t in trending:
        if t["target_id"] in restaurant_map:
            r = restaurant_map[t["target_id"]]
            r["trending_score"] = t.get("click_count", 0) + t.get("order_count", 0) * 2
            result.append(r)
    
    return result


@api.get("/trending/products")
async def get_trending_products(limit: Optional[int] = 10):
    """Get trending products (by clicks)"""
    trending = await db.trending_stats.find(
        {"target_type": "product"},
        {"_id": 0}
    ).sort("click_count", -1).limit(limit).to_list(limit)
    
    # Enrich with product data
    product_ids = [t["target_id"] for t in trending]
    products = await db.products.find(
        {"id": {"$in": product_ids}},
        {"_id": 0}
    ).to_list(limit)
    
    # Sort by trending stats
    product_map = {p["id"]: p for p in products}
    result = []
    for t in trending:
        if t["target_id"] in product_map:
            p = product_map[t["target_id"]]
            p["trending_score"] = t.get("click_count", 0)
            result.append(p)
    
    return result


# ----------------------------------------------------------------------------
# Orders
# ----------------------------------------------------------------------------
@api.post("/orders")
async def place_order(body: OrderIn, user: dict = Depends(get_current_user)):
    s = await get_settings()
    if s.get("maintenance_mode") and user["role"] != "admin":
        raise HTTPException(503, "Platform is under maintenance. Please try again later.")
    if not body.phone or not body.phone.strip():
        raise HTTPException(400, "Phone number is required")
    if not body.area or not body.area.strip():
        raise HTTPException(400, "Delivery area is required")
    if not body.items:
        raise HTTPException(400, "Cart is empty")

    # SECURITY: Recompute item prices from DB. Never trust frontend prices.
    item_ids = [it.item_id for it in body.items]
    products = await db.products.find({"id": {"$in": item_ids}}, {"_id": 0}).to_list(2000)
    products_by_id = {p["id"]: p for p in products}
    secure_items = []
    subtotal = 0.0
    for it in body.items:
        p = products_by_id.get(it.item_id)
        if not p:
            raise HTTPException(400, f"Item {it.item_id} not found")
        qty = max(1, int(it.quantity))
        # Effective price = raw MINUS any active promo (server-side recompute
        # so a crafted client cannot pass a lower price). See effective_price_usd.
        price = effective_price_usd(p)
        # Sides aren't standard on marketplace products; keep what was sent for note value 0.
        line_total = price * qty
        subtotal += line_total
        secure_items.append({
            "item_type": "product",
            "item_id": p["id"],
            "name": p.get("name"),
            "price_usd": price,
            "quantity": qty,
            "image_url": p.get("image_url", ""),
            "sides": [],
        })

    # SECURITY: Calculate delivery fee using admin pricing rules. Never trust frontend prices.
    # Import the helper from cod module
    from cod import _calculate_delivery_fee
    
    delivery_fee = 0.0
    delivery_breakdown: List[dict] = []
    shop_ids_in_order = list({p["shop_id"] for p in products})
    shops: List[dict] = []
    
    if shop_ids_in_order:
        shops = await db.shops.find({"id": {"$in": shop_ids_in_order}}, {"_id": 0}).to_list(500)
        for sh in shops:
            # Calculate delivery fee using admin rules
            # pickup_area = shop area, delivery_area = customer area
            pickup_area = sh.get("area", "")
            delivery_area = body.area
            
            fee = await _calculate_delivery_fee(
                pickup_area=pickup_area,
                delivery_area=delivery_area,
                order_type="marketplace",
                shop_id=sh["id"],
                restaurant_id=None
            )
            
            delivery_fee += fee
            delivery_breakdown.append({
                "shop_id": sh["id"],
                "shop_name": sh.get("name", "—"),
                "fee_usd": round(fee, 2),
                "pickup_area": pickup_area,
                "delivery_area": delivery_area,
            })

    total = round(subtotal + delivery_fee, 2)
    order = {
        "id": str(uuid.uuid4()),
        "customer_id": user["id"],
        "customer_name": user["name"],
        "customer_email": user["email"],
        "items": secure_items,
        "subtotal_usd": round(subtotal, 2),
        "delivery_fee_usd": round(delivery_fee, 2),
        "delivery_breakdown": delivery_breakdown,
        "total_usd": total,
        "area": body.area, "address": body.address, "phone": body.phone,
        "note": body.note, "order_kind": body.order_kind,
        "status": "Pending",
        # New COD/driver fields summarized on the parent order; per-seller
        # state lives on seller_order_splits.
        "payment_method": "cash_on_delivery",
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order)
    order.pop("_id", None)

    # Create per-seller splits with their own OTPs, statuses, commission.
    try:
        order["splits"] = await cod.create_marketplace_splits(order)
    except Exception as e:
        log.warning(f"split creation failed for order {order['id']}: {e}")
        order["splits"] = []

    # Notify each unique seller whose products are in this order
    notified_sellers = set()
    if shop_ids_in_order:
        for sh in shops:
            sid = sh.get("seller_id")
            if sid and sid not in notified_sellers:
                notified_sellers.add(sid)
                short_id = order["id"][:8]
                await create_notification(
                    user_id=sid,
                    message=f"New order received: Order #{short_id}",
                    ntype="order",
                    meta={"order_id": order["id"], "customer_name": user["name"], "shop_id": sh["id"]},
                )

    # Confirmation notification to the customer
    short_id = order["id"][:8]
    await create_notification(
        user_id=user["id"],
        message=f"Your order #{short_id} has been placed. Total: USD {total:.2f}.",
        ntype="order",
        meta={"order_id": order["id"], "status": "Pending"},
    )

    # Email: customer confirmation
    try:
        await email_service.send_order_confirmation_customer(
            to=user["email"], name=user.get("name", ""), order=order,
        )
    except Exception as e:
        log.warning(f"customer order email failed: {e}")

    # Email: notify each seller
    try:
        if shop_ids_in_order:
            for sh in shops:
                sid = sh.get("seller_id")
                if not sid:
                    continue
                seller = await db.users.find_one({"id": sid}, {"_id": 0, "email": 1, "name": 1, "settings": 1})
                if not seller or not seller.get("email"):
                    continue
                if (seller.get("settings") or {}).get("order_notifications") is False:
                    continue
                await email_service.send_order_notification_seller(
                    to=seller["email"],
                    seller_name=seller.get("name", ""),
                    order=order,
                    shop_name=sh.get("name", "your shop"),
                )
    except Exception as e:
        log.warning(f"seller order email failed: {e}")

    return order


@api.get("/orders/mine")
async def my_orders(
    user: dict = Depends(get_current_user),
    limit: Optional[int] = None,
    skip: Optional[int] = None,
):
    lim, off = clamp_pagination(limit, skip)
    rows = await db.orders.find({"customer_id": user["id"]}, {"_id": 0}).sort("created_at", -1).skip(off).to_list(lim)
    return await enrich_marketplace_orders(rows)


@api.get("/seller/low-stock-count")
async def seller_low_stock_count(
    threshold: int = 5,
    user: dict = Depends(require_role("seller", "admin")),
):
    """Lightweight: returns just the count of low-stock products for the seller.
    Used by the seller dashboard banner so we don't load every product on every
    tab change. Single aggregated query against an indexable field."""
    threshold = max(0, min(int(threshold or 0), 10_000))
    count = await db.products.count_documents({
        "seller_id": user["id"],
        "stock": {"$lte": threshold},
    })
    return {"count": int(count), "threshold": threshold}


@api.get("/orders/seller")
async def seller_orders(
    user: dict = Depends(require_role("seller", "admin")),
    limit: Optional[int] = None,
    skip: Optional[int] = None,
):
    lim, off = clamp_pagination(limit, skip)
    seller_products = await db.products.find({"seller_id": user["id"]}, {"_id": 0, "id": 1}).to_list(2000)
    seller_menu = await db.menu_items.find({"seller_id": user["id"]}, {"_id": 0, "id": 1}).to_list(2000)
    ids = {p["id"] for p in seller_products} | {m["id"] for m in seller_menu}
    if not ids:
        return []
    rows = await db.orders.find({"items.item_id": {"$in": list(ids)}}, {"_id": 0}).sort("created_at", -1).skip(off).to_list(lim)
    # Sellers must not see customer phone/area/address (privacy). Admins see
    # everything. Exception: when the seller is the driver for THIS order's
    # shop (delivery_managed_by=seller), they need customer contact info.
    if user["role"] != "admin":
        # Batch-load seller's shops with delivery config.
        seller_shops = {
            sh["id"]: sh
            async for sh in db.shops.find(
                {"seller_id": user["id"]},
                {"_id": 0, "id": 1, "delivery_managed_by": 1},
            )
        }
        sysettings = await db.settings.find_one({"id": "system"}, {"_id": 0}) or {}
        global_admin_manages = bool(sysettings.get("admin_manages_delivery", False))
        # For each order, resolve the shop(s) via product → shop_id lookup.
        prod_ids = {it["item_id"] for r in rows for it in (r.get("items") or []) if it.get("item_id") in ids}
        prod_to_shop = {
            p["id"]: p.get("shop_id")
            async for p in db.products.find(
                {"id": {"$in": list(prod_ids)}}, {"_id": 0, "id": 1, "shop_id": 1}
            )
        }

        def _order_seller_manages(order):
            for it in order.get("items") or []:
                sid = prod_to_shop.get(it.get("item_id"))
                sh = seller_shops.get(sid)
                if not sh:
                    continue
                mb = sh.get("delivery_managed_by") or "default"
                if mb == "seller":
                    return True
                if mb == "admin":
                    continue  # look at other items
                # "default" — follow platform toggle
                if not global_admin_manages:
                    return True
            return False

        for r in rows:
            cod.redact_for_seller(r, seller_manages_delivery=_order_seller_manages(r))
    return await enrich_marketplace_orders(rows)


@api.get("/seller/analytics")
async def seller_analytics(user: dict = Depends(require_role("seller", "admin"))):
    """Sales analytics for a seller.
    Returns:
      - totals: {today, week, month, all_time} for EARNING (USD, seller_earning_usd
        i.e. what the seller actually pockets after commission and any
        seller-kept delivery fee) + order count
      - revenue_series: last 30 days [{date:'YYYY-MM-DD', revenue, orders}]
      - top_products: [{id, name, image_url, quantity, revenue}] top 5
      - low_performers: 5 products with <=2 orders in last 30 days
      - low_stock: [{id, name, stock}] up to 10 with stock<5
    Money reported in USD. "Revenue" totals are seller EARNINGS (what they
    receive) — matches the "Your earning" chip shown on completed orders.
    Per-product breakdowns still use item.price_usd × qty (gross).
    """
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    today_iso = now.date().isoformat()
    week_start = (now - timedelta(days=7)).isoformat()
    month_start = (now - timedelta(days=30)).isoformat()

    seller_products = await db.products.find({"seller_id": user["id"]}, {"_id": 0}).to_list(2000)
    seller_menu = await db.menu_items.find({"seller_id": user["id"]}, {"_id": 0}).to_list(2000)
    pid_index = {p["id"]: p for p in seller_products}
    for m in seller_menu:
        pid_index[m["id"]] = m
    ids = list(pid_index.keys())
    if not ids:
        empty_totals = {"today": {"revenue": 0, "orders": 0}, "week": {"revenue": 0, "orders": 0}, "month": {"revenue": 0, "orders": 0}, "all_time": {"revenue": 0, "orders": 0}}
        return {
            "totals": empty_totals,
            "revenue_series": [],
            "by_channel": {
                "combined": {"totals": empty_totals, "revenue_series": []},
                "marketplace": {"totals": empty_totals, "revenue_series": []},
                "restaurant": {"totals": empty_totals, "revenue_series": []},
            },
            "top_products": [],
            "low_performers": [],
            "low_stock": [],
        }

    # Pull the seller's own splits + restaurant orders — these are the
    # single-source-of-truth for "what the seller earns". Analytics used to
    # sum item.price_usd × qty from db.orders which is GROSS revenue, not
    # earnings, and drifted from the "Your earning" chip shown on the
    # completed order in the wallet. Splits carry `seller_earning_usd`
    # already computed (subtotal − commission + delivery-if-self-managed).
    splits = await db.seller_order_splits.find(
        {"seller_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(5000)
    rest_orders = await db.restaurant_orders.find(
        {"seller_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(5000)

    # Also fetch original db.orders for the top-products / low-performers
    # breakdown (which is per-product gross qty × price — earnings do not
    # attribute per-product).
    orders_marketplace = await db.orders.find({"items.item_id": {"$in": ids}}, {"_id": 0}).sort("created_at", -1).to_list(5000)

    def item_revenue_usd(item):
        p = pid_index.get(item.get("item_id"))
        qty = int(item.get("quantity") or 1)
        unit = item.get("price_usd")
        if unit is None and p is not None:
            unit = p.get("price_usd") or 0
        try:
            return float(unit or 0) * qty, qty
        except Exception:
            return 0.0, qty

    def _empty_totals():
        return {
            "today": {"revenue": 0.0, "orders": 0},
            "week": {"revenue": 0.0, "orders": 0},
            "month": {"revenue": 0.0, "orders": 0},
            "all_time": {"revenue": 0.0, "orders": 0},
        }

    # by_channel tracks: combined (both), marketplace (shop splits), restaurant.
    by_channel = {
        "combined": _empty_totals(),
        "marketplace": _empty_totals(),
        "restaurant": _empty_totals(),
    }
    per_product = {}  # id -> {qty, revenue}
    days_bucket = {"combined": {}, "marketplace": {}, "restaurant": {}}
    for d in range(30):
        key = (now - timedelta(days=d)).date().isoformat()
        for ch in days_bucket:
            days_bucket[ch][key] = {"revenue": 0.0, "orders": 0}

    def _bump(channel: str, earning: float, created: str):
        bucket = by_channel[channel]
        bucket["all_time"]["revenue"] += earning
        bucket["all_time"]["orders"] += 1
        if created >= today_iso:
            bucket["today"]["revenue"] += earning
            bucket["today"]["orders"] += 1
        if created >= week_start:
            bucket["week"]["revenue"] += earning
            bucket["week"]["orders"] += 1
        if created >= month_start:
            bucket["month"]["revenue"] += earning
            bucket["month"]["orders"] += 1
            day_key = created[:10]
            if day_key in days_bucket[channel]:
                days_bucket[channel][day_key]["revenue"] += earning
                days_bucket[channel][day_key]["orders"] += 1

    # --- Earning aggregation: iterate splits + restaurant orders. Only
    # count DELIVERED rows so aborted/pending orders don't inflate totals.
    for row in splits:
        if row.get("delivery_status") != "delivered":
            continue
        earning = float(row.get("seller_earning_usd") or 0)
        created = row.get("created_at") or ""
        _bump("marketplace", earning, created)
        _bump("combined", earning, created)
    for row in rest_orders:
        if row.get("delivery_status") != "delivered":
            continue
        earning = float(row.get("seller_earning_usd") or 0)
        created = row.get("created_at") or ""
        _bump("restaurant", earning, created)
        _bump("combined", earning, created)

    # --- Per-product qty / gross-revenue (used for top/low product cards).
    for o in orders_marketplace:
        for it in (o.get("items") or []):
            if it.get("item_id") in pid_index:
                r, q = item_revenue_usd(it)
                pp = per_product.setdefault(it["item_id"], {"qty": 0, "revenue": 0.0})
                pp["qty"] += q
                pp["revenue"] += r

    # Round money for cleanliness
    for ch, tot in by_channel.items():
        for k in tot:
            tot[k]["revenue"] = round(tot[k]["revenue"], 2)

    # Combined series (default view) + per-channel series
    revenue_series = {
        ch: [{"date": d, "revenue": round(v["revenue"], 2), "orders": v["orders"]}
             for d, v in sorted(days_bucket[ch].items())]
        for ch in ("combined", "marketplace", "restaurant")
    }

    # Top products
    top_sorted = sorted(per_product.items(), key=lambda kv: kv[1]["revenue"], reverse=True)[:5]
    top_products = []
    for pid, stats in top_sorted:
        p = pid_index.get(pid, {})
        top_products.append({
            "id": pid,
            "name": p.get("name", "Unknown"),
            "image_url": p.get("image_url", ""),
            "quantity": stats["qty"],
            "revenue": round(stats["revenue"], 2),
        })

    # Low performers: seller's active products with <=2 orders in last 30 days
    low_performers = []
    for p in seller_products:
        pid = p["id"]
        qty = per_product.get(pid, {}).get("qty", 0)
        if qty <= 2:
            low_performers.append({
                "id": pid,
                "name": p.get("name", "Unknown"),
                "image_url": p.get("image_url", ""),
                "quantity": qty,
            })
    low_performers = sorted(low_performers, key=lambda x: x["quantity"])[:5]

    # Low stock
    low_stock = []
    for p in seller_products:
        s = int(p.get("stock") or 0)
        if s < 5:
            low_stock.append({"id": p["id"], "name": p.get("name", "Unknown"), "stock": s})
    low_stock = sorted(low_stock, key=lambda x: x["stock"])[:10]

    return {
        # New shape: per-channel breakdown. `totals` retained at top level =
        # combined so existing UIs don't break.
        "totals": by_channel["combined"],
        "revenue_series": revenue_series["combined"],
        "by_channel": {
            "combined": {"totals": by_channel["combined"], "revenue_series": revenue_series["combined"]},
            "marketplace": {"totals": by_channel["marketplace"], "revenue_series": revenue_series["marketplace"]},
            "restaurant": {"totals": by_channel["restaurant"], "revenue_series": revenue_series["restaurant"]},
        },
        "top_products": top_products,
        "low_performers": low_performers,
        "low_stock": low_stock,
    }


@api.get("/orders")
async def all_orders(
    _: dict = Depends(require_role("admin")),
    limit: Optional[int] = None,
    skip: Optional[int] = None,
):
    lim, off = clamp_pagination(limit, skip)
    return await db.orders.find({}, {"_id": 0}).sort("created_at", -1).skip(off).to_list(lim)


@api.put("/orders/{order_id}/status")
async def update_status(order_id: str, body: StatusIn, _: dict = Depends(require_role("seller", "admin"))):
    o = await db.orders.find_one({"id": order_id})
    if not o:
        raise HTTPException(404, "Order not found")
    prev_status = o.get("status")
    await db.orders.update_one({"id": order_id}, {"$set": {"status": body.status}})

    # Notify the customer when status actually changes
    if prev_status != body.status and o.get("customer_id"):
        short_id = order_id[:8]
        msgs = {
            "Pending": f"Order #{short_id} is awaiting confirmation.",
            "In Progress": f"Good news — Order #{short_id} is being prepared.",
            "Delivered": f"Order #{short_id} has been delivered. Enjoy! Tap to leave a review.",
        }
        await create_notification(
            user_id=o["customer_id"],
            message=msgs.get(body.status, f"Order #{short_id} status updated to {body.status}."),
            ntype="order",
            meta={"order_id": order_id, "status": body.status},
        )

    return await db.orders.find_one({"id": order_id}, {"_id": 0})


# ----------------------------------------------------------------------------
# Order Chat — internal two-way messaging between customer and seller(s)
# ----------------------------------------------------------------------------
async def _resolve_order_seller_ids(order_id: str) -> tuple[Optional[dict], list[str]]:
    """Return (order, [seller_ids]) for the given order, computing sellers from
    its items via products → shops. Returns (None, []) if the order is missing."""
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        return None, []
    item_ids = [it.get("item_id") for it in order.get("items", []) if it.get("item_id")]
    if not item_ids:
        return order, []
    products = await db.products.find({"id": {"$in": item_ids}}, {"_id": 0, "shop_id": 1}).to_list(2000)
    shop_ids = list({p.get("shop_id") for p in products if p.get("shop_id")})
    if not shop_ids:
        return order, []
    shops = await db.shops.find({"id": {"$in": shop_ids}}, {"_id": 0, "seller_id": 1}).to_list(500)
    seller_ids = list({s.get("seller_id") for s in shops if s.get("seller_id")})
    return order, seller_ids


@api.post("/orders/{order_id}/chat")
async def send_order_chat(order_id: str, body: OrderChatMessageIn, user: dict = Depends(get_current_user)):
    order, seller_ids = await _resolve_order_seller_ids(order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    is_customer = user["id"] == order.get("customer_id")
    is_seller = user["id"] in seller_ids and user["id"] == body.seller_id
    
    # Check if user is assigned driver
    is_driver = False
    if user["role"] == "driver":
        split_count = await db.seller_order_splits.count_documents({
            "order_id": order_id,
            "driver_id": user["id"]
        })
        rest_order_count = await db.restaurant_orders.count_documents({
            "id": order_id,
            "driver_id": user["id"]
        })
        is_driver = split_count > 0 or rest_order_count > 0
    
    if not (is_customer or is_seller or is_driver):
        raise HTTPException(403, "You are not part of this order conversation")
    if is_customer and body.seller_id not in seller_ids:
        raise HTTPException(400, "Invalid seller for this order")

    # Driver messages go to customer (use first seller_id as placeholder)
    msg = {
        "id": str(uuid.uuid4()),
        "order_id": order_id,
        "customer_id": order.get("customer_id"),
        "seller_id": body.seller_id if not is_driver else seller_ids[0] if seller_ids else None,
        "sender_id": user["id"],
        "sender_role": "customer" if is_customer else ("seller" if is_seller else "driver"),
        "body": body.body.strip(),
        "read_by_customer": is_customer,
        "read_by_seller": is_seller,
        "created_at": now_iso(),
    }
    await db.order_messages.insert_one(msg)
    msg.pop("_id", None)

    # Notify the other side
    if is_customer:
        await create_notification(
            user_id=body.seller_id,
            message=f"New message about Order #{order_id[:8]} from {user.get('name', 'a customer')}.",
            ntype="message",
            meta={"order_id": order_id, "seller_id": body.seller_id, "chat": True},
        )
    elif is_driver:
        # Driver sends message, notify customer
        await create_notification(
            user_id=order.get("customer_id"),
            message=f"Your driver sent a message about Order #{order_id[:8]}.",
            ntype="message",
            meta={"order_id": order_id, "chat": True},
        )
    else:
        await create_notification(
            user_id=order.get("customer_id"),
            message=f"New message about Order #{order_id[:8]} from the seller.",
            ntype="message",
            meta={"order_id": order_id, "seller_id": body.seller_id, "chat": True},
        )
    return msg


@api.get("/orders/{order_id}/chat")
async def get_order_chat(order_id: str, seller_id: str, user: dict = Depends(get_current_user)):
    order, seller_ids = await _resolve_order_seller_ids(order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    is_customer = user["id"] == order.get("customer_id")
    is_seller = user["id"] in seller_ids and user["id"] == seller_id
    
    # Check if user is assigned driver
    is_driver = False
    if user["role"] == "driver":
        split_count = await db.seller_order_splits.count_documents({
            "order_id": order_id,
            "driver_id": user["id"]
        })
        rest_order_count = await db.restaurant_orders.count_documents({
            "id": order_id,
            "driver_id": user["id"]
        })
        is_driver = split_count > 0 or rest_order_count > 0
    
    if not (is_customer or is_seller or is_driver):
        raise HTTPException(403, "You are not part of this order conversation")
    if is_customer and seller_id not in seller_ids:
        raise HTTPException(400, "Invalid seller for this order")

    messages = await db.order_messages.find(
        {"order_id": order_id, "seller_id": seller_id},
        {"_id": 0},
    ).sort("created_at", 1).to_list(2000)

    # Mark messages from the other side as read by me
    if is_driver:
        # Driver reads messages - don't mark anything as read for now
        pass
    else:
        read_field = "read_by_customer" if is_customer else "read_by_seller"
        await db.order_messages.update_many(
            {"order_id": order_id, "seller_id": seller_id, read_field: False},
            {"$set": {read_field: True}},
    )
    return messages


@api.get("/chats")
async def list_my_chats(user: dict = Depends(get_current_user)):
    """List all chat threads (one per order-seller pair) the current user is part of."""
    role = user.get("role")
    if role == "seller":
        match = {"seller_id": user["id"]}
        read_field = "read_by_seller"
    else:
        match = {"customer_id": user["id"]}
        read_field = "read_by_customer"

    pipeline = [
        {"$match": match},
        {"$sort": {"created_at": 1}},
        {
            "$group": {
                "_id": {"order_id": "$order_id", "seller_id": "$seller_id"},
                "customer_id": {"$last": "$customer_id"},
                "last_body": {"$last": "$body"},
                "last_role": {"$last": "$sender_role"},
                "last_at": {"$last": "$created_at"},
                "unread": {
                    "$sum": {"$cond": [{"$eq": [f"${read_field}", False]}, 1, 0]}
                },
            }
        },
        {"$sort": {"last_at": -1}},
        {"$limit": 100},
    ]
    raw = await db.order_messages.aggregate(pipeline).to_list(500)

    # Resolve counterparty names + order short id in one batch
    seller_ids = list({r["_id"]["seller_id"] for r in raw})
    customer_ids = list({r["customer_id"] for r in raw if r.get("customer_id")})
    sellers = await db.users.find({"id": {"$in": seller_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
    customers = await db.users.find({"id": {"$in": customer_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
    seller_map = {s["id"]: s.get("name", "Seller") for s in sellers}
    customer_map = {c["id"]: c.get("name", "Customer") for c in customers}

    out = []
    for r in raw:
        order_id = r["_id"]["order_id"]
        sid = r["_id"]["seller_id"]
        out.append({
            "order_id": order_id,
            "order_short_id": order_id[:8],
            "seller_id": sid,
            "customer_id": r.get("customer_id"),
            "counterparty_name": (
                seller_map.get(sid, "Seller") if role != "seller"
                else customer_map.get(r.get("customer_id"), "Customer")
            ),
            "last_message": r.get("last_body", ""),
            "last_at": r.get("last_at"),
            "last_role": r.get("last_role"),
            "unread": int(r.get("unread") or 0),
        })
    return out


@api.get("/chats/unread-count")
async def my_chat_unread_count(user: dict = Depends(get_current_user)):
    role = user.get("role")
    if role == "seller":
        q = {"seller_id": user["id"], "read_by_seller": False, "sender_role": "customer"}
    elif role == "driver":
        # Drivers see unread messages from customers
        q = {"sender_role": "customer", "read_by_seller": False}  # Using read_by_seller for drivers too
    else:
        # Customers see unread from sellers AND drivers
        q = {"customer_id": user["id"], "read_by_customer": False, "sender_role": {"$in": ["seller", "driver"]}}
    count = await db.order_messages.count_documents(q)
    return {"count": count}


@api.get("/orders/{order_id}/chat-sellers")
async def list_order_chat_sellers(order_id: str, user: dict = Depends(get_current_user)):
    """For an order, return the list of sellers the current user can chat with."""
    order, seller_ids = await _resolve_order_seller_ids(order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    
    # Check if user is customer, seller, or assigned driver
    is_customer = user["id"] == order.get("customer_id")
    is_seller = user["id"] in seller_ids
    
    # Check if user is assigned driver (check splits and restaurant_orders)
    is_driver = False
    if user["role"] == "driver":
        # Check if driver is assigned to any split or restaurant order for this order
        split_count = await db.seller_order_splits.count_documents({
            "order_id": order_id,
            "driver_id": user["id"]
        })
        rest_order_count = await db.restaurant_orders.count_documents({
            "id": order_id,  # For restaurant orders, the id IS the order_id
            "driver_id": user["id"]
        })
        is_driver = split_count > 0 or rest_order_count > 0
    
    if not (is_customer or is_seller or is_driver):
        raise HTTPException(403, "You are not part of this order")
    
    sellers = await db.users.find({"id": {"$in": seller_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(50)
    return [{"seller_id": s["id"], "name": s.get("name", "Seller")} for s in sellers]


# ----------------------------------------------------------------------------
# Reviews (product feedback)
# ----------------------------------------------------------------------------
@api.get("/products/{product_id}/reviews")
async def list_reviews(product_id: str, limit: Optional[int] = None, skip: Optional[int] = None):
    lim, off = clamp_pagination(limit, skip)
    # Aggregate stats across the FULL set so the average is correct, but only
    # return a paginated slice of review docs.
    cursor = db.reviews.find({"product_id": product_id}, {"_id": 0}).sort("created_at", -1)
    all_reviews = await cursor.to_list(MAX_PAGE_LIMIT * 5)  # internal cap for stats
    if not all_reviews:
        return {"reviews": [], "average": 0, "count": 0}
    avg = round(sum(r.get("rating", 0) for r in all_reviews) / len(all_reviews), 1)
    return {"reviews": all_reviews[off : off + lim], "average": avg, "count": len(all_reviews)}


@api.post("/products/{product_id}/reviews")
async def add_review(product_id: str, body: ProductReviewIn, user: dict = Depends(get_current_user)):
    if user["role"] != "customer":
        raise HTTPException(403, "Only customers can post reviews")
    p = await db.products.find_one({"id": product_id})
    if not p:
        raise HTTPException(404, "Product not found")
    review = {
        "id": str(uuid.uuid4()),
        "product_id": product_id,
        "user_id": user["id"],
        "user_name": user.get("name", "Customer"),
        "rating": int(body.rating),
        "comment": (body.comment or "").strip()[:1000],
        # Cap at 5 photos; each URL truncated to 1024 chars to keep the doc bounded.
        "photos": [str(u)[:1024] for u in (body.photos or [])][:5],
        "created_at": now_iso(),
    }
    await db.reviews.insert_one(review)
    # Roll up product reviews into the parent shop so shop cards can show ratings.
    if p.get("shop_id"):
        await _recompute_shop_rating(p["shop_id"])
    review.pop("_id", None)
    return review


@api.delete("/products/{product_id}/reviews/{review_id}")
async def delete_review(product_id: str, review_id: str, user: dict = Depends(get_current_user)):
    rv = await db.reviews.find_one({"id": review_id, "product_id": product_id})
    if not rv:
        raise HTTPException(404, "Review not found")
    if user["role"] != "admin" and rv.get("user_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    await db.reviews.delete_one({"id": review_id})
    # Keep shop roll-up in sync after deletion.
    p = await db.products.find_one({"id": product_id}, {"_id": 0, "shop_id": 1})
    if p and p.get("shop_id"):
        await _recompute_shop_rating(p["shop_id"])
    return {"ok": True}


async def _recompute_shop_rating(shop_id: str) -> None:
    """Recompute average_rating and review_count for a shop from its product reviews.

    Aggregates *all* reviews across every product of the shop, weighted equally.
    Persists {"average_rating": float|None, "review_count": int} on the shop doc.
    """
    products = await db.products.find({"shop_id": shop_id}, {"_id": 0, "id": 1}).to_list(2000)
    product_ids = [p["id"] for p in products]
    if not product_ids:
        await db.shops.update_one(
            {"id": shop_id},
            {"$set": {"average_rating": None, "review_count": 0}},
        )
        return
    pipeline = [
        {"$match": {"product_id": {"$in": product_ids}}},
        {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
    ]
    agg = await db.reviews.aggregate(pipeline).to_list(1)
    if agg:
        avg = round(float(agg[0].get("avg") or 0), 1)
        cnt = int(agg[0].get("count") or 0)
    else:
        avg, cnt = None, 0
    await db.shops.update_one(
        {"id": shop_id},
        {"$set": {"average_rating": avg if cnt > 0 else None, "review_count": cnt}},
    )


# ----------------------------------------------------------------------------
# Notifications (in-app)
# ----------------------------------------------------------------------------
@api.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user), limit: int = 50):
    # Lazy weekly reminder generation
    try:
        if user["role"] == "seller":
            await _generate_seller_unpaid_reminders(user["id"])
        elif user["role"] == "admin":
            await _generate_admin_unpaid_reminders(user["id"])
    except Exception as e:
        log.warning(f"reminder gen failed: {e}")

    items = await db.notifications.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 200))
    unread = await db.notifications.count_documents({"user_id": user["id"], "is_read": False})
    return {"items": items, "unread_count": unread}


@api.get("/notifications/unread-count")
async def notifications_unread_count(user: dict = Depends(get_current_user)):
    n = await db.notifications.count_documents({"user_id": user["id"], "is_read": False})
    return {"unread_count": n}


@api.put("/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: str, user: dict = Depends(get_current_user)):
    n = await db.notifications.find_one({"id": notif_id, "user_id": user["id"]})
    if not n:
        raise HTTPException(404, "Notification not found")
    await db.notifications.update_one({"id": notif_id}, {"$set": {"is_read": True}})
    return {"ok": True}


@api.put("/notifications/read-all")
async def mark_all_notifications_read(user: dict = Depends(get_current_user)):
    res = await db.notifications.update_many({"user_id": user["id"], "is_read": False}, {"$set": {"is_read": True}})
    return {"ok": True, "modified": res.modified_count}


@api.delete("/notifications/{notif_id}")
async def delete_notification(notif_id: str, user: dict = Depends(get_current_user)):
    res = await db.notifications.delete_one({"id": notif_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Notification not found")
    return {"ok": True}


# ============================================================
#  Web Push (VAPID) endpoints
# ============================================================

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY_PEM = os.environ.get("VAPID_PRIVATE_KEY_PEM", "").replace("\\n", "\n")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com")

try:
    from pywebpush import webpush as _webpush, WebPushException as _WebPushException
except Exception as _e:  # pragma: no cover
    _webpush = None
    _WebPushException = Exception


@api.get("/push/public-key")
async def get_push_public_key():
    """Return the VAPID public key (base64url) for the browser to subscribe."""
    return {"public_key": VAPID_PUBLIC_KEY}


class PushSubscribeIn(BaseModel):
    subscription: dict  # {endpoint, keys:{p256dh,auth}}
    # Per-category user preferences (all default True on first subscribe)
    prefs: Optional[Dict[str, bool]] = None


@api.post("/push/subscribe")
async def push_subscribe(payload: PushSubscribeIn, user: dict = Depends(get_current_user)):
    """Store the browser push subscription and (optionally) user preferences."""
    sub = payload.subscription or {}
    endpoint = (sub.get("endpoint") or "").strip()
    if not endpoint or not sub.get("keys", {}).get("p256dh") or not sub.get("keys", {}).get("auth"):
        raise HTTPException(400, "Invalid push subscription")
    prefs = payload.prefs or {}
    # Default: all-on
    all_prefs = {
        "orders": bool(prefs.get("orders", True)),
        "low_stock": bool(prefs.get("low_stock", True)),
        "promo": bool(prefs.get("promo", True)),
        "delivery": bool(prefs.get("delivery", True)),
        "admin": bool(prefs.get("admin", True)),
    }
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "role": user.get("role"),
        "endpoint": endpoint,
        "keys": sub.get("keys"),
        "user_agent": sub.get("userAgent", ""),
        "prefs": all_prefs,
        "created_at": now_iso(),
        "last_used_at": None,
    }
    # Upsert by (user_id, endpoint) to avoid duplicates on repeated subscribes
    await db.push_subscriptions.update_one(
        {"user_id": user["id"], "endpoint": endpoint},
        {"$set": {k: v for k, v in doc.items() if k not in ("id", "created_at")}, "$setOnInsert": {"id": doc["id"], "created_at": doc["created_at"]}},
        upsert=True,
    )
    return {"ok": True}


class PushUnsubscribeIn(BaseModel):
    endpoint: str


@api.post("/push/unsubscribe")
async def push_unsubscribe(payload: PushUnsubscribeIn, user: dict = Depends(get_current_user)):
    res = await db.push_subscriptions.delete_one({"user_id": user["id"], "endpoint": payload.endpoint})
    return {"ok": True, "removed": res.deleted_count}


class PushPrefsIn(BaseModel):
    prefs: Dict[str, bool]


@api.put("/push/prefs")
async def push_prefs_update(payload: PushPrefsIn, user: dict = Depends(get_current_user)):
    """Update push category preferences for all this user's subscriptions."""
    valid_keys = {"orders", "low_stock", "promo", "delivery", "admin"}
    updates = {f"prefs.{k}": bool(v) for k, v in payload.prefs.items() if k in valid_keys}
    if not updates:
        return {"ok": True, "modified": 0}
    res = await db.push_subscriptions.update_many({"user_id": user["id"]}, {"$set": updates})
    return {"ok": True, "modified": res.modified_count}


@api.get("/push/prefs")
async def push_prefs_get(user: dict = Depends(get_current_user)):
    """Return the current user's push subscription status + preferences."""
    sub = await db.push_subscriptions.find_one({"user_id": user["id"]}, {"_id": 0})
    if not sub:
        return {"subscribed": False, "prefs": {"orders": True, "low_stock": True, "promo": True, "delivery": True, "admin": True}}
    return {"subscribed": True, "prefs": sub.get("prefs") or {}, "endpoint": sub.get("endpoint")}


@api.post("/push/test")
async def push_test(user: dict = Depends(get_current_user)):
    """Send a test push notification to all this user's subscriptions."""
    sent = await send_web_push_to_user(user["id"], {
        "title": "JubaSquare",
        "body": "Test notification 🎉 — push is working!",
        "url": "/",
    })
    return {"ok": True, "sent": sent}


async def send_web_push_to_user(user_id: str, payload: dict, category: str = "admin") -> int:
    """Send a Web Push notification to every subscription of the given user.

    - `payload` is a dict with keys {title, body, url, tag?, requireInteraction?, icon?}.
    - `category` gates delivery based on the subscription's prefs (orders/low_stock/promo/delivery/admin).
    - Returns the number of endpoints successfully sent to.

    Silently drops subscriptions that return 404/410 (gone) so we don't retry forever.
    """
    if not _webpush or not VAPID_PRIVATE_KEY_PEM:
        return 0
    subs = await db.push_subscriptions.find({"user_id": user_id}, {"_id": 0}).to_list(50)
    sent = 0
    for sub in subs:
        prefs = sub.get("prefs") or {}
        if category and prefs.get(category, True) is False:
            continue
        try:
            _webpush(
                subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]},
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE_KEY_PEM,
                vapid_claims={"sub": VAPID_SUBJECT},
                ttl=60,
            )
            sent += 1
            await db.push_subscriptions.update_one({"endpoint": sub["endpoint"]}, {"$set": {"last_used_at": now_iso()}})
        except _WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (404, 410):
                # Endpoint is gone — remove it
                await db.push_subscriptions.delete_one({"endpoint": sub["endpoint"]})
            log.warning(f"webpush send failed ({code}): {e}")
        except Exception as e:
            log.warning(f"webpush unexpected error: {e}")
    return sent


@api.post("/admin/notifications/run-reminders")
async def admin_run_reminders(user: dict = Depends(require_role("admin"))):
    """Force-generate weekly unpaid-commission reminders for ALL sellers + the admin
    (ignores the 7-day grace window so admins can preview the reminder flow)."""
    sellers = await db.users.find({"role": "seller"}, {"_id": 0, "id": 1}).to_list(1000)
    seller_count = 0
    for s in sellers:
        invoices = await db.invoices.find(
            {"seller_id": s["id"], "status": {"$in": ["Unpaid", "Overdue"]}},
            {"_id": 0},
        ).to_list(1000)
        for inv in invoices:
            amount = float(inv.get("commission") or inv.get("amount_owed") or 0)
            label = inv.get("week_label") or inv.get("shop_name") or ""
            await create_notification(
                user_id=s["id"],
                message=f"Reminder: Commission of USD {amount:.2f} is still unpaid — {label}",
                ntype="commission",
                meta={"invoice_id": inv["id"], "reminder": True},
            )
            seller_count += 1

    # Admin-side digest
    pipeline = [
        {"$match": {"status": {"$in": ["Unpaid", "Overdue"]}}},
        {"$group": {"_id": "$seller_id", "amount_owed": {"$sum": "$commission"}, "invoice_count": {"$sum": 1}}},
    ]
    rows = await db.invoices.aggregate(pipeline).to_list(1000)
    admin_count = 0
    for row in rows:
        sid = row["_id"]
        if not sid:
            continue
        seller = await db.users.find_one({"id": sid}, {"_id": 0, "name": 1, "email": 1})
        sname = (seller or {}).get("name") or (seller or {}).get("email") or "Seller"
        await create_notification(
            user_id=user["id"],
            message=f"{sname} has {row['invoice_count']} unpaid invoice(s) — USD {float(row.get('amount_owed') or 0):.2f} owed",
            ntype="commission",
            meta={"seller_id": sid, "amount_owed": float(row.get("amount_owed") or 0), "reminder": True},
        )
        admin_count += 1
    return {"ok": True, "seller_reminders": seller_count, "admin_reminders": admin_count}


# ----------------------------------------------------------------------------
# Delivery quote (preview cart total based on area)
# ----------------------------------------------------------------------------
@api.post("/orders/quote")
async def quote_order(body: OrderIn, _: dict = Depends(get_current_user)):
    """Compute delivery fee preview for given items + area, without creating an order."""
    if not body.items:
        return {"subtotal_usd": 0, "delivery_fee_usd": 0, "total_usd": 0, "delivery_breakdown": []}
    subtotal = sum(it.price_usd * it.quantity + sum(sd.price_usd for sd in (it.sides or [])) * it.quantity for it in body.items)
    item_ids = [it.item_id for it in body.items]
    products = await db.products.find({"id": {"$in": item_ids}}, {"_id": 0}).to_list(2000)
    shop_ids_in_order = list({p["shop_id"] for p in products})
    
    # Use admin delivery pricing rules (same as actual order creation)
    from cod import _calculate_delivery_fee
    
    delivery_fee = 0.0
    breakdown = []
    if shop_ids_in_order and body.area:
        shops = await db.shops.find({"id": {"$in": shop_ids_in_order}}, {"_id": 0}).to_list(500)
        for sh in shops:
            # Calculate delivery fee using admin rules
            pickup_area = sh.get("area", "")
            delivery_area = body.area
            
            fee = await _calculate_delivery_fee(
                pickup_area=pickup_area,
                delivery_area=delivery_area,
                order_type="marketplace",
                shop_id=sh["id"],
                restaurant_id=None
            )
            
            delivery_fee += fee
            breakdown.append({
                "shop_id": sh["id"],
                "shop_name": sh.get("name", "—"),
                "fee_usd": round(fee, 2),
                "pickup_area": pickup_area,
                "delivery_area": delivery_area,
            })
    return {
        "subtotal_usd": round(subtotal, 2),
        "delivery_fee_usd": round(delivery_fee, 2),
        "total_usd": round(subtotal + delivery_fee, 2),
        "delivery_breakdown": breakdown,
    }


# ----------------------------------------------------------------------------
# Admin: settings, areas, shops, emails, force-logout
# ----------------------------------------------------------------------------
@api.get("/admin/settings")
async def admin_get_settings(_: dict = Depends(require_role("admin"))):
    return await get_settings()


# ----------------------------------------------------------------------------
# Admin: Integrations (Resend email config) — editable from UI
# ----------------------------------------------------------------------------
def _mask(s: str) -> str:
    if not s:
        return ""
    if len(s) <= 8:
        return "•" * len(s)
    return s[:4] + "•" * (len(s) - 8) + s[-4:]


@api.get("/admin/integrations")
async def admin_get_integrations(_: dict = Depends(require_role("admin"))):
    """Return a sanitized view of integration config (API key is masked)."""
    settings = await db.settings.find_one({"id": "system"}) or {}
    integ = settings.get("integrations") or {}
    env_key = (os.environ.get("RESEND_API_KEY") or "").strip()
    env_from = (os.environ.get("SENDER_EMAIL") or "").strip()
    effective_key = integ.get("resend_api_key") or env_key
    effective_from = integ.get("resend_from_email") or env_from or "noreply@jubasquare.com"
    return {
        "resend": {
            "api_key_masked": _mask(effective_key) if effective_key else "",
            "api_key_set": bool(effective_key),
            "from_email": effective_from,
            "source": "db" if integ.get("resend_api_key") else ("env" if env_key else "none"),
        },
        "hints": {
            "verify_domain_url": "https://resend.com/domains",
            "notes": "With onboarding@resend.dev, Resend only delivers to the email on your Resend account. Verify your own domain to send to anyone.",
        },
    }


class IntegrationsIn(BaseModel):
    resend_api_key: Optional[str] = None  # empty string clears it
    resend_from_email: Optional[str] = None


@api.post("/admin/integrations")
async def admin_update_integrations(body: IntegrationsIn, _: dict = Depends(require_role("admin"))):
    update: dict = {}
    if body.resend_api_key is not None:
        update["integrations.resend_api_key"] = body.resend_api_key.strip()
    if body.resend_from_email is not None:
        fe = body.resend_from_email.strip()
        if fe and "@" not in fe:
            raise HTTPException(400, "Sender email must be a valid email address.")
        update["integrations.resend_from_email"] = fe
    if not update:
        raise HTTPException(400, "Nothing to update.")
    await db.settings.update_one({"id": "system"}, {"$set": update}, upsert=True)
    return {"ok": True}


class TestEmailIn(BaseModel):
    to: EmailStr


@api.post("/admin/integrations/test-email")
async def admin_test_email(body: TestEmailIn, user: dict = Depends(require_role("admin"))):
    """Send a test email and return the real Resend response / error."""
    html = f"""<p>Hi {user.get('name', 'there')},</p>
<p>This is a test email from JubaSquare. If you see this, your Resend integration is working.</p>
<p style="color:#808080;font-size:12px">Sent at {now_iso()} to {body.to}.</p>"""
    result = await email_service.send_raw(
        to=str(body.to),
        subject="JubaSquare — Resend integration test",
        html=html,
    )
    return result


@api.get("/admin/health")
async def admin_health(_: dict = Depends(require_role("admin"))):
    """System health / performance snapshot for the admin dashboard.

    Returns:
      - mongo ping (ms) + estimated collection counts
      - integration fingerprints (which are configured)
      - Odoo webhook activity (last event, count in last 24h)
      - Web Push subscription count
    """
    import time as _t
    result = {
        "checked_at": now_iso(),
        "backend": {"status": "ok"},
        "mongo": {"status": "unknown", "ping_ms": None, "collections": {}},
        "integrations": {
            "resend_email": bool(os.environ.get("RESEND_API_KEY")),
            "odoo_webhook": bool(os.environ.get("ODOO_WEBHOOK_TOKEN")),
            "web_push": bool(os.environ.get("VAPID_PUBLIC_KEY") and os.environ.get("VAPID_PRIVATE_KEY_PEM")),
        },
        "odoo": {"last_event_at": None, "recent_events": 0},
    }
    try:
        t0 = _t.perf_counter()
        await db.command("ping")
        result["mongo"]["ping_ms"] = round((_t.perf_counter() - t0) * 1000, 2)
        result["mongo"]["status"] = "ok"
    except Exception as e:
        result["mongo"]["status"] = "error"
        result["mongo"]["error"] = str(e)[:200]
    for coll in ("users", "shops", "products", "orders", "categories", "notifications", "push_subscriptions"):
        try:
            result["mongo"]["collections"][coll] = await db[coll].estimated_document_count()
        except Exception:
            result["mongo"]["collections"][coll] = None
    try:
        last = await db.odoo_events.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
        if last:
            result["odoo"]["last_event_at"] = last.get("created_at")
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        result["odoo"]["recent_events"] = await db.odoo_events.count_documents({"created_at": {"$gte": since}})
    except Exception:
        pass
    return result


# ============================================================
#  Reports (Report Shop / Report Review)
# ============================================================

class ReportIn(BaseModel):
    target_type: Literal["shop", "review", "product"]
    target_id: str
    reason: str
    details: Optional[str] = None


@api.post("/reports")
async def create_report(payload: ReportIn, user: dict = Depends(get_current_user)):
    """Any authenticated user can file a report against a shop / review / product."""
    reason = (payload.reason or "").strip()
    if not reason or len(reason) > 200:
        raise HTTPException(400, "Reason is required (max 200 chars)")

    # Validate target exists
    target_id = payload.target_id.strip()
    if payload.target_type == "shop":
        exists = await db.shops.find_one({"id": target_id}, {"_id": 0, "id": 1, "name": 1})
    elif payload.target_type == "product":
        exists = await db.products.find_one({"id": target_id}, {"_id": 0, "id": 1, "name": 1})
    else:  # review
        exists = await db.reviews.find_one({"id": target_id}, {"_id": 0, "id": 1})
    if not exists:
        raise HTTPException(404, f"{payload.target_type} not found")

    # De-duplicate: same user + same target + open status = block
    dup = await db.reports.find_one({
        "reporter_id": user["id"],
        "target_type": payload.target_type,
        "target_id": target_id,
        "status": "open",
    })
    if dup:
        raise HTTPException(409, "You already reported this. Our team will review it soon.")

    doc = {
        "id": str(uuid.uuid4()),
        "target_type": payload.target_type,
        "target_id": target_id,
        "target_snapshot": {"name": exists.get("name")} if exists else {},
        "reporter_id": user["id"],
        "reporter_role": user.get("role"),
        "reason": reason,
        "details": (payload.details or "")[:2000],
        "status": "open",  # open | reviewed | dismissed | actioned
        "admin_notes": "",
        "created_at": now_iso(),
        "resolved_at": None,
    }
    await db.reports.insert_one(doc)
    doc.pop("_id", None)

    # Notify all admins
    admins = await db.users.find({"role": "admin"}, {"_id": 0, "id": 1}).to_list(100)
    for a in admins:
        await create_notification(
            a["id"],
            f"New {payload.target_type} report: {reason}",
            ntype="alert",
            meta={"link": "/admin?tab=reports", "report_id": doc["id"]},
            push_category="admin",
            push_url="/admin?tab=reports",
        )
    return doc


@api.get("/admin/reports")
async def admin_list_reports(status: Optional[str] = None, _: dict = Depends(require_role("admin"))):
    q = {}
    if status:
        q["status"] = status
    rows = await db.reports.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return rows


class ReportUpdateIn(BaseModel):
    status: Literal["open", "reviewed", "dismissed", "actioned"]
    admin_notes: Optional[str] = None


@api.put("/admin/reports/{report_id}")
async def admin_update_report(report_id: str, payload: ReportUpdateIn, _: dict = Depends(require_role("admin"))):
    r = await db.reports.find_one({"id": report_id})
    if not r:
        raise HTTPException(404, "Report not found")
    updates = {"status": payload.status}
    if payload.admin_notes is not None:
        updates["admin_notes"] = payload.admin_notes[:2000]
    if payload.status in ("dismissed", "actioned", "reviewed"):
        updates["resolved_at"] = now_iso()
    await db.reports.update_one({"id": report_id}, {"$set": updates})
    return {"ok": True, "status": payload.status}







@api.get("/admin/analytics")
async def admin_analytics(_: dict = Depends(require_role("admin"))):
    """Aggregated counts for the admin dashboard."""
    now = datetime.now(timezone.utc)
    since30 = now - timedelta(days=30)
    since30_iso = since30.isoformat()

    # Totals
    orders = await db.orders.find({}, {"_id": 0}).to_list(5000)
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(5000)
    shops_count = await db.shops.count_documents({})
    products_count = await db.products.count_documents({})
    restaurants_count = await db.restaurants.count_documents({})

    total_orders = len(orders)
    total_revenue_marketplace = sum(float(o.get("total_usd") or o.get("subtotal_usd") or 0) for o in orders)
    
    # Get total platform commission from payouts (COD system)
    payouts = await db.seller_payouts.find({}, {"_id": 0}).to_list(5000)
    total_commission_cod = sum(float(p.get("commission_deducted_usd") or 0) for p in payouts)
    
    # Combined revenue = marketplace orders + COD commission collected
    total_revenue = round(total_revenue_marketplace + total_commission_cod, 2)
    
    pending_orders = sum(1 for o in orders if o.get("status") == "Pending")
    
    # Count delivered orders from COD system (splits + restaurant_orders)
    delivered_splits = await db.seller_order_splits.count_documents({"delivery_status": "delivered"})
    delivered_restaurant_orders = await db.restaurant_orders.count_documents({"delivery_status": "delivered"})
    delivered_orders = sum(1 for o in orders if o.get("status") == "Delivered") + delivered_splits + delivered_restaurant_orders

    customers_count = sum(1 for u in users if u.get("role") == "customer")
    sellers_count = sum(1 for u in users if u.get("role") == "seller")

    # Orders per day (last 30 days)
    orders_per_day: dict = {}
    for o in orders:
        try:
            dt = datetime.fromisoformat(o["created_at"])
        except Exception:
            continue
        if dt < since30:
            continue
        key = dt.date().isoformat()
        orders_per_day.setdefault(key, {"day": key, "orders": 0, "revenue": 0.0})
        orders_per_day[key]["orders"] += 1
        orders_per_day[key]["revenue"] += float(o.get("total_usd") or o.get("subtotal_usd") or 0)

    # New users per day (last 30 days)
    users_per_day: dict = {}
    for u in users:
        try:
            dt = datetime.fromisoformat(u.get("created_at") or "")
            # Coerce naive datetimes to UTC so we can compare against since30
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if dt < since30:
            continue
        key = dt.date().isoformat()
        users_per_day.setdefault(key, {"day": key, "users": 0})
        users_per_day[key]["users"] += 1

    # Fill missing days with 0 for nicer charts
    opd_list = []
    upd_list = []
    for i in range(29, -1, -1):
        d = (now - timedelta(days=i)).date().isoformat()
        opd_list.append(orders_per_day.get(d, {"day": d, "orders": 0, "revenue": 0.0}))
        upd_list.append(users_per_day.get(d, {"day": d, "users": 0}))

    # Top sellers by revenue (from invoices, fallback to order aggregation)
    invoices = await db.invoices.find({}, {"_id": 0}).to_list(5000)
    seller_rev: dict = {}
    for inv in invoices:
        sid = inv.get("seller_id")
        if not sid:
            continue
        seller_rev[sid] = seller_rev.get(sid, 0.0) + float(inv.get("total_sales") or 0)
    top = sorted(seller_rev.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_sellers = []
    for sid, revenue in top:
        s = await db.users.find_one({"id": sid}, {"_id": 0, "name": 1, "email": 1})
        top_sellers.append({
            "seller_id": sid,
            "name": (s or {}).get("name") or (s or {}).get("email") or "Seller",
            "revenue_usd": round(revenue, 2),
        })

    # Pending shops for verification queue count
    pending_shops = await db.shops.count_documents({"verification": "Pending"})

    return {
        "totals": {
            "orders": total_orders,
            "revenue_usd": round(total_revenue, 2),
            "pending_orders": pending_orders,
            "delivered_orders": delivered_orders,
            "shops": shops_count,
            "products": products_count,
            "restaurants": restaurants_count,
            "customers": customers_count,
            "sellers": sellers_count,
            "pending_shops": pending_shops,
        },
        "orders_per_day": opd_list,
        "users_per_day": upd_list,
        "top_sellers": top_sellers,
    }


@api.put("/admin/settings")
async def admin_update_settings(body: SettingsIn, _: dict = Depends(require_role("admin"))):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if update:
        await db.settings.update_one({"id": "system"}, {"$set": update}, upsert=True)
        cache_invalidate("settings:", "meta:areas")
    return await get_settings()



# ----------------------------------------------------------------------------
# Admin User Management
# ----------------------------------------------------------------------------
@api.get("/admin/users")
async def admin_list_users(
    limit: Optional[int] = None,
    skip: Optional[int] = None,
    role: Optional[str] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    email_verified: Optional[bool] = None,
    _: dict = Depends(require_role("admin")),
):
    """List all users with filters and aggregated stats."""
    page_size, offset = clamp_pagination(limit, skip)
    
    # Build query
    query: dict = {}
    if role in {"customer", "seller", "admin"}:
        query["role"] = role
    if is_active is not None:
        query["is_active"] = is_active
    if email_verified is not None:
        query["email_verified"] = email_verified
    if search:
        # Search by name or email
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]
    
    # Get users
    users = await db.users.find(query, {"_id": 0, "password_hash": 0}).skip(offset).limit(page_size).to_list(page_size)
    
    # Aggregate stats for each user
    user_ids = [u["id"] for u in users]
    
    # Get order counts for customers
    orders_pipeline = [
        {"$match": {"customer_id": {"$in": user_ids}}},
        {"$group": {"_id": "$customer_id", "count": {"$sum": 1}}},
    ]
    orders_counts = {r["_id"]: r["count"] for r in await db.orders.aggregate(orders_pipeline).to_list(1000)}
    
    # Get sales totals for sellers (from invoices)
    invoices_pipeline = [
        {"$match": {"seller_id": {"$in": user_ids}}},
        {"$group": {"_id": "$seller_id", "total_sales": {"$sum": "$total_sales"}}},
    ]
    sales_totals = {r["_id"]: round(float(r.get("total_sales") or 0), 2) for r in await db.invoices.aggregate(invoices_pipeline).to_list(1000)}
    
    # Enrich user data
    for user in users:
        uid = user["id"]
        if user.get("role") == "customer":
            user["total_orders"] = orders_counts.get(uid, 0)
        elif user.get("role") == "seller":
            user["total_sales"] = sales_totals.get(uid, 0.0)
        # Ensure defaults for new fields
        user.setdefault("is_active", True)
        user.setdefault("must_change_password", False)
        user.setdefault("last_login", None)
    
    return users



@api.post("/admin/users")
async def admin_create_user(body: AdminUserCreateIn, _: dict = Depends(require_role("admin"))):
    """Admin creates a new user account (pre-verified)."""
    email = body.email.lower()
    
    # Check if email already exists
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(400, "An account with this email already exists")
    
    # Check if email is blocked
    blocked = await db.blocked_emails.find_one({"email": email})
    if blocked:
        raise HTTPException(403, "This email cannot be registered")
    
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "email": email,
        "name": body.name.strip(),
        "role": body.role,
        "phone": (body.phone or "").strip(),
        "password_hash": hash_password(body.password),
        "email_verified": body.email_verified,  # Admin-created users can be pre-verified
        "is_active": True,
        "must_change_password": False,
        "settings": {},
        "created_at": now_iso(),
    }
    await db.users.insert_one(user)
    
    return {
        "ok": True,
        "message": f"User {body.name} created successfully",
        "user": {
            "id": uid,
            "email": email,
            "name": body.name,
            "role": body.role,
        }
    }


@api.get("/admin/users/{user_id}")
async def admin_get_user(user_id: str, _: dict = Depends(require_role("admin"))):
    """Get single user with full details."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(404, "User not found")
    
    # Add stats
    if user.get("role") == "customer":
        user["total_orders"] = await db.orders.count_documents({"customer_id": user_id})
    elif user.get("role") == "seller":
        pipeline = [
            {"$match": {"seller_id": user_id}},
            {"$group": {"_id": None, "total": {"$sum": "$total_sales"}}},
        ]
        result = await db.invoices.aggregate(pipeline).to_list(1)
        user["total_sales"] = round(float(result[0]["total"]) if result else 0.0, 2)
    
    # Ensure defaults
    user.setdefault("is_active", True)
    user.setdefault("must_change_password", False)
    user.setdefault("last_login", None)
    
    return user


@api.put("/admin/users/{user_id}")
async def admin_update_user(user_id: str, body: AdminUserUpdateIn, admin: dict = Depends(require_role("admin"))):
    """Update user details (name, email, phone, role)."""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "User not found")
    
    # Prevent admin from changing their own role
    if user_id == admin["id"] and body.role and body.role != "admin":
        raise HTTPException(400, "You cannot change your own role")
    
    update: dict = {}
    if body.name:
        update["name"] = body.name.strip()
    if body.email:
        # Check email uniqueness
        existing = await db.users.find_one({"email": body.email.lower(), "id": {"$ne": user_id}})
        if existing:
            raise HTTPException(400, "Email already in use by another account")
        update["email"] = body.email.lower()
    if body.phone is not None:
        update["phone"] = body.phone.strip()
    if body.role:
        update["role"] = body.role
    
    if update:
        await db.users.update_one({"id": user_id}, {"$set": update})
    
    return await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})


@api.post("/admin/users/{user_id}/reset-password")
async def admin_reset_password_direct(user_id: str, body: AdminResetPasswordIn, admin: dict = Depends(require_role("admin"))):
    """Admin sets a new password directly for user."""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "User not found")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "password_hash": hash_password(body.new_password),
            "must_change_password": False,
        }},
    )
    
    return {"ok": True, "message": f"Password updated for {user.get('name') or user.get('email')}"}


@api.post("/admin/users/{user_id}/send-reset-email")
async def admin_send_password_reset_email(user_id: str, _: dict = Depends(require_role("admin"))):
    """Send password reset email to user."""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "User not found")
    
    email = user["email"]
    
    # Delete any existing password reset tokens for this user
    await db.password_resets.delete_many({"user_id": user_id})
    
    # Create new token
    token = _make_token()
    await db.password_resets.insert_one({
        "token": token,
        "user_id": user_id,
        "email": email,
        "created_at": now_iso(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=RESET_TTL_MINUTES)).isoformat(),
    })
    
    try:
        await email_service.send_password_reset_email(to=email, name=user.get("name", ""), token=token)
        return {"ok": True, "message": f"Password reset email sent to {email}"}
    except Exception as e:
        log.error(f"Admin password reset email failed: {e}")
        return {"ok": True, "message": f"Reset token created (email service unavailable). Token: {token}"}


@api.post("/admin/users/{user_id}/generate-temp-password")
async def admin_generate_temp_password(user_id: str, _: dict = Depends(require_role("admin"))):
    """Generate a temporary password for user."""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "User not found")
    
    # Generate random 12-character password
    import string
    temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "password_hash": hash_password(temp_password),
            "must_change_password": True,
        }},
    )
    
    return {
        "ok": True,
        "temp_password": temp_password,
        "message": f"Temporary password generated for {user.get('name') or user.get('email')}. User must change it on next login.",
    }


@api.put("/admin/users/{user_id}/status")
async def admin_update_user_status(user_id: str, body: AdminUserStatusIn, admin: dict = Depends(require_role("admin"))):
    """Enable or disable user account."""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "User not found")
    
    # Prevent admin from disabling themselves
    if user_id == admin["id"]:
        raise HTTPException(400, "You cannot disable your own account")
    
    await db.users.update_one({"id": user_id}, {"$set": {"is_active": body.is_active}})
    
    action = "enabled" if body.is_active else "disabled"
    return {"ok": True, "message": f"User {user.get('name') or user.get('email')} has been {action}"}


@api.get("/admin/users/{user_id}/delete-preview")
async def admin_delete_preview(user_id: str, admin: dict = Depends(require_role("admin"))):
    """Return a summary of what a hard-delete would cascade — used by the
    admin UI to show a confirmation modal ('this will also delete X shops,
    Y products, Z restaurants — cannot be undone')."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

    counts = {
        "notifications": await db.notifications.count_documents({"user_id": user_id}),
        "favorites": await db.favorites.count_documents({"user_id": user_id}),
        "reviews_written": await db.reviews.count_documents({"user_id": user_id}),
        "messages_sent": (
            await db.order_messages.count_documents({"sender_id": user_id})
            + await db.shop_messages.count_documents({"customer_id": user_id})
        ),
    }

    if user.get("role") == "seller":
        shops = await db.shops.find({"seller_id": user_id}, {"_id": 0, "id": 1}).to_list(1000)
        shop_ids = [s["id"] for s in shops]
        restaurants = await db.restaurants.find({"seller_id": user_id}, {"_id": 0, "id": 1}).to_list(1000)
        restaurant_ids = [r["id"] for r in restaurants]
        counts.update({
            "shops": len(shop_ids),
            "products": await db.products.count_documents({"shop_id": {"$in": shop_ids}}),
            "restaurants": len(restaurant_ids),
            "menu_items": await db.menu_items.count_documents({"restaurant_id": {"$in": restaurant_ids}}),
            "reviews_received": (
                await db.reviews.count_documents({"shop_id": {"$in": shop_ids}})
                + await db.reviews.count_documents({"restaurant_id": {"$in": restaurant_ids}})
            ),
            "invoices": (
                await db.invoices.count_documents({"seller_id": user_id})
                + await db.restaurant_invoices.count_documents({"seller_id": user_id})
            ),
            "payouts": await db.seller_payouts.count_documents({"seller_id": user_id}),
        })

    return {
        "user": {"id": user["id"], "email": user.get("email"), "name": user.get("name"), "role": user.get("role")},
        "counts": counts,
        "orders_kept": True,  # Orders are retained for historical/accounting records
    }


@api.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, admin: dict = Depends(require_role("admin"))):
    """Delete user account (hard delete with cascade)."""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "User not found")
    
    # Prevent admin from deleting themselves
    if user_id == admin["id"]:
        raise HTTPException(400, "You cannot delete your own account")
    
    await _cascade_delete_user(user)


async def _cascade_delete_user(user: dict) -> None:
    """Hard-delete a user + everything they own.

    - Users, notifications, favorites, email_verifications, password_resets,
      onboarding_progress, reports (authored by the user), order_messages
      (sent by them), shop_messages (sent by them as customer_id).
    - If seller: also delete their shops, products, restaurants, menu_items,
      reviews on those shops/products/restaurants, shop_messages & order_messages
      touching those shops, seller_payouts, seller_order_splits, invoices,
      restaurant_invoices.
    - Orders are KEPT for historical/accounting records — `seller_id` will
      orphan, but customer order history + platform revenue reports survive.
    """
    user_id = user["id"]

    # Per-user cleanup (applies to any role)
    await db.users.delete_one({"id": user_id})
    await db.notifications.delete_many({"user_id": user_id})
    await db.favorites.delete_many({"user_id": user_id})
    await db.email_verifications.delete_many({"user_id": user_id})
    await db.password_resets.delete_many({"user_id": user_id})
    await db.onboarding_progress.delete_many({"user_id": user_id})
    await db.reports.delete_many({"reporter_id": user_id})
    await db.reviews.delete_many({"user_id": user_id})
    await db.order_messages.delete_many({"sender_id": user_id})
    await db.shop_messages.delete_many({"customer_id": user_id})

    if user.get("role") != "seller":
        return

    # Seller cascade — gather owned entities first so we can filter dependents.
    shops = await db.shops.find({"seller_id": user_id}, {"_id": 0, "id": 1}).to_list(1000)
    shop_ids = [s["id"] for s in shops]
    products = await db.products.find({"shop_id": {"$in": shop_ids}}, {"_id": 0, "id": 1}).to_list(10000)
    product_ids = [p["id"] for p in products]
    restaurants = await db.restaurants.find({"seller_id": user_id}, {"_id": 0, "id": 1}).to_list(1000)
    restaurant_ids = [r["id"] for r in restaurants]

    # Delete owned entities
    await db.shops.delete_many({"seller_id": user_id})
    await db.products.delete_many({"shop_id": {"$in": shop_ids}})
    await db.restaurants.delete_many({"seller_id": user_id})
    await db.menu_items.delete_many({"restaurant_id": {"$in": restaurant_ids}})

    # Reviews left on any of those shops / products / restaurants
    await db.reviews.delete_many({"shop_id": {"$in": shop_ids}})
    await db.reviews.delete_many({"product_id": {"$in": product_ids}})
    await db.reviews.delete_many({"restaurant_id": {"$in": restaurant_ids}})

    # Messages tied to those shops
    await db.shop_messages.delete_many({"shop_id": {"$in": shop_ids}})
    await db.order_messages.delete_many({"seller_id": user_id})

    # Payouts / invoices / reports about the seller
    await db.seller_payouts.delete_many({"seller_id": user_id})
    await db.seller_order_splits.delete_many({"seller_id": user_id})
    await db.invoices.delete_many({"seller_id": user_id})
    await db.restaurant_invoices.delete_many({"seller_id": user_id})
    await db.reports.delete_many({"shop_id": {"$in": shop_ids}})


@api.post("/admin/users/bulk-delete")
async def admin_bulk_delete_users(body: AdminBulkDeleteUsersIn, admin: dict = Depends(require_role("admin"))):
    """Delete multiple user accounts at once (hard delete with cascade)."""
    user_ids = body.user_ids
    
    # Prevent admin from deleting themselves
    if admin["id"] in user_ids:
        raise HTTPException(400, "You cannot delete your own account")
    
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0}).to_list(1000)
    if not users:
        raise HTTPException(404, "No users found to delete")

    for u in users:
        await _cascade_delete_user(u)

    return {"deleted": len(users)}


@api.post("/admin/areas")
async def admin_add_area(body: AreaIn, _: dict = Depends(require_role("admin"))):
    s = await get_settings()
    areas = list(s.get("areas", DEFAULT_AREAS))
    if body.area in areas:
        raise HTTPException(400, "Area already exists")
    areas.append(body.area)
    await db.settings.update_one({"id": "system"}, {"$set": {"areas": areas}}, upsert=True)
    cache_invalidate("settings:", "meta:areas")
    return {"areas": areas}


@api.delete("/admin/areas")
async def admin_delete_area(area: str, _: dict = Depends(require_role("admin"))):
    s = await get_settings()
    areas = [a for a in s.get("areas", DEFAULT_AREAS) if a != area]
    await db.settings.update_one({"id": "system"}, {"$set": {"areas": areas}}, upsert=True)
    cache_invalidate("settings:", "meta:areas")
    return {"areas": areas}


@api.post("/admin/force-logout-all")
async def admin_force_logout(_: dict = Depends(require_role("admin"))):
    s = await get_settings()
    new_tv = int(s.get("token_version", 1)) + 1
    await db.settings.update_one({"id": "system"}, {"$set": {"token_version": new_tv}}, upsert=True)
    return {"ok": True, "token_version": new_tv}


@api.get("/admin/shops-and-restaurants")
async def admin_list_shops_and_restaurants(
    type_filter: Optional[str] = None,  # "shops", "restaurants", or None for all
    verification: Optional[str] = None,  # Filter by verification status
    limit: Optional[int] = None,
    skip: Optional[int] = None,
    _: dict = Depends(require_role("admin"))
):
    """Get both shops and restaurants for admin dashboard.
    
    Args:
        type_filter: Filter by type ("shops" or "restaurants"). None returns both.
        verification: Filter by verification status
        limit/skip: Pagination
    
    Returns:
        {
            "shops": [...],
            "restaurants": [...],
            "total_shops": int,
            "total_restaurants": int
        }
    """
    lim, off = clamp_pagination(limit, skip)
    
    result = {
        "shops": [],
        "restaurants": [],
        "total_shops": 0,
        "total_restaurants": 0
    }
    
    # Fetch shops if requested
    if type_filter is None or type_filter == "shops":
        shop_query = {"is_deleted": {"$ne": True}}
        if verification:
            shop_query["verification"] = verification
        
        result["shops"] = await db.shops.find(
            shop_query,
            {"_id": 0}
        ).skip(off).limit(lim).sort("created_at", -1).to_list(lim)
        result["total_shops"] = await db.shops.count_documents(shop_query)
    
    # Fetch restaurants if requested
    if type_filter is None or type_filter == "restaurants":
        rest_query = {}
        if verification:
            rest_query["verification"] = verification
        
        result["restaurants"] = await db.restaurants.find(
            rest_query,
            {"_id": 0}
        ).skip(off).limit(lim).sort("created_at", -1).to_list(lim)
        result["total_restaurants"] = await db.restaurants.count_documents(rest_query)
    
    return result


@api.put("/admin/shops/{shop_id}/verify")
async def admin_verify(shop_id: str, _: dict = Depends(require_role("admin"))):
    await db.shops.update_one({"id": shop_id}, {"$set": {"verification": "Verified"}})
    return await db.shops.find_one({"id": shop_id}, {"_id": 0})


@api.put("/admin/shops/{shop_id}/reject")
async def admin_reject(shop_id: str, _: dict = Depends(require_role("admin"))):
    await db.shops.update_one({"id": shop_id}, {"$set": {"verification": "Rejected"}})
    return await db.shops.find_one({"id": shop_id}, {"_id": 0})


class ShopDeliveryManagedByIn(BaseModel):
    delivery_managed_by: Literal["default", "seller", "admin"]


@api.put("/admin/shops/{shop_id}/delivery-managed-by")
async def admin_set_shop_delivery_managed_by(
    shop_id: str,
    body: ShopDeliveryManagedByIn,
    _: dict = Depends(require_role("admin")),
):
    """Per-shop override for who runs delivery. `default` follows the
    platform-wide `admin_manages_delivery` toggle; `seller` / `admin` lock
    the shop to that mode regardless of the global toggle."""
    result = await db.shops.update_one(
        {"id": shop_id},
        {"$set": {"delivery_managed_by": body.delivery_managed_by}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Shop not found")
    return await db.shops.find_one({"id": shop_id}, {"_id": 0})


@api.put("/admin/restaurants/{restaurant_id}/delivery-managed-by")
async def admin_set_restaurant_delivery_managed_by(
    restaurant_id: str,
    body: ShopDeliveryManagedByIn,
    _: dict = Depends(require_role("admin")),
):
    """Same as the shop endpoint, but for a restaurant."""
    result = await db.restaurants.update_one(
        {"id": restaurant_id},
        {"$set": {"delivery_managed_by": body.delivery_managed_by}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Restaurant not found")
    return await db.restaurants.find_one({"id": restaurant_id}, {"_id": 0})


@api.put("/admin/shops/{shop_id}/commission")
async def admin_shop_commission(shop_id: str, body: ShopCommissionIn, _: dict = Depends(require_role("admin"))):
    shop = await db.shops.find_one({"id": shop_id})
    if not shop:
        raise HTTPException(404, "Shop not found")
    rate = body.commission_rate
    if rate is not None and (rate < 0 or rate > 1):
        raise HTTPException(400, "Commission rate must be between 0 and 1")
    if rate is None:
        await db.shops.update_one({"id": shop_id}, {"$unset": {"commission_rate": ""}})
    else:
        await db.shops.update_one({"id": shop_id}, {"$set": {"commission_rate": float(rate)}})
    return await db.shops.find_one({"id": shop_id}, {"_id": 0})


@api.put("/admin/restaurants/{restaurant_id}/verify")
async def admin_verify_restaurant(restaurant_id: str, _: dict = Depends(require_role("admin"))):
    if not await db.restaurants.find_one({"id": restaurant_id}, {"_id": 0, "id": 1}):
        raise HTTPException(404, "Restaurant not found")
    await db.restaurants.update_one({"id": restaurant_id}, {"$set": {"verification": "Verified"}})
    return await db.restaurants.find_one({"id": restaurant_id}, {"_id": 0})


@api.put("/admin/restaurants/{restaurant_id}/reject")
async def admin_reject_restaurant(restaurant_id: str, _: dict = Depends(require_role("admin"))):
    if not await db.restaurants.find_one({"id": restaurant_id}, {"_id": 0, "id": 1}):
        raise HTTPException(404, "Restaurant not found")
    await db.restaurants.update_one({"id": restaurant_id}, {"$set": {"verification": "Rejected"}})
    return await db.restaurants.find_one({"id": restaurant_id}, {"_id": 0})


@api.put("/admin/restaurants/{restaurant_id}/commission")
async def admin_restaurant_commission(restaurant_id: str, body: ShopCommissionIn, _: dict = Depends(require_role("admin"))):
    rest = await db.restaurants.find_one({"id": restaurant_id})
    if not rest:
        raise HTTPException(404, "Restaurant not found")
    rate = body.commission_rate
    if rate is not None and (rate < 0 or rate > 1):
        raise HTTPException(400, "Commission rate must be between 0 and 1")
    if rate is None:
        await db.restaurants.update_one({"id": restaurant_id}, {"$unset": {"commission_rate": ""}})
    else:
        await db.restaurants.update_one({"id": restaurant_id}, {"$set": {"commission_rate": float(rate)}})
    return await db.restaurants.find_one({"id": restaurant_id}, {"_id": 0})


@api.put("/admin/invoice-frequency")
async def admin_set_global_invoice_frequency(body: InvoiceFrequencyIn, _: dict = Depends(require_role("admin"))):
    """Set global invoice frequency (daily, weekly, monthly, quarterly, yearly)"""
    await db.settings.update_one(
        {"id": "system"},
        {"$set": {"invoice_frequency": body.frequency}},
        upsert=True
    )
    cache_invalidate("settings:")
    return {"ok": True, "frequency": body.frequency}


@api.put("/admin/shops/{shop_id}/invoice-frequency")
async def admin_set_shop_invoice_frequency(shop_id: str, body: ShopInvoiceFrequencyIn, _: dict = Depends(require_role("admin"))):
    """Set per-shop invoice frequency override. None = use global setting."""
    shop = await db.shops.find_one({"id": shop_id})
    if not shop:
        raise HTTPException(404, "Shop not found")
    
    if body.frequency is None:
        await db.shops.update_one({"id": shop_id}, {"$unset": {"invoice_frequency": ""}})
    else:
        await db.shops.update_one({"id": shop_id}, {"$set": {"invoice_frequency": body.frequency}})
    
    return await db.shops.find_one({"id": shop_id}, {"_id": 0})


@api.put("/admin/restaurants/{restaurant_id}/invoice-frequency")
async def admin_set_restaurant_invoice_frequency(restaurant_id: str, body: ShopInvoiceFrequencyIn, _: dict = Depends(require_role("admin"))):
    """Set per-restaurant invoice frequency override. None = use global setting."""
    restaurant = await db.restaurants.find_one({"id": restaurant_id})
    if not restaurant:
        raise HTTPException(404, "Restaurant not found")
    
    if body.frequency is None:
        await db.restaurants.update_one({"id": restaurant_id}, {"$unset": {"invoice_frequency": ""}})
    else:
        await db.restaurants.update_one({"id": restaurant_id}, {"$set": {"invoice_frequency": body.frequency}})
    
    return await db.restaurants.find_one({"id": restaurant_id}, {"_id": 0})


# ----------------------------------------------------------------------------
# Admin Odoo Connection Management
# ----------------------------------------------------------------------------

class OdooConnectionUpdateIn(BaseModel):
    """Admin-only: Update Odoo connection settings for a shop/restaurant"""
    enabled: bool
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    warehouse_id: Optional[str] = None
    warehouse_name: Optional[str] = None
    pricelist_id: Optional[str] = None
    pricelist_name: Optional[str] = None
    pos_config_id: Optional[str] = None
    sync_products: bool = False
    sync_stock: bool = False
    send_orders: bool = False
    send_delivery_updates: bool = False


@api.put("/admin/shops/{shop_id}/odoo-connection")
async def admin_update_shop_odoo_connection(
    shop_id: str,
    body: OdooConnectionUpdateIn,
    _: dict = Depends(require_role("admin"))
):
    """Admin-only: Configure Odoo connection for a shop"""
    shop = await db.shops.find_one({"id": shop_id})
    if not shop:
        raise HTTPException(404, "Shop not found")
    
    odoo_connection = {
        "enabled": body.enabled,
        "company_id": body.company_id,
        "company_name": body.company_name,
        "warehouse_id": body.warehouse_id,
        "warehouse_name": body.warehouse_name,
        "pricelist_id": body.pricelist_id,
        "pricelist_name": body.pricelist_name,
        "pos_config_id": body.pos_config_id,
        "sync_products": body.sync_products,
        "sync_stock": body.sync_stock,
        "send_orders": body.send_orders,
        "send_delivery_updates": body.send_delivery_updates,
        "sync_status": "active" if body.enabled else "disabled",
        "last_sync_at": shop.get("odoo_connection", {}).get("last_sync_at"),
        "sync_error": None if body.enabled else shop.get("odoo_connection", {}).get("sync_error")
    }
    
    await db.shops.update_one({"id": shop_id}, {"$set": {"odoo_connection": odoo_connection}})
    return await db.shops.find_one({"id": shop_id}, {"_id": 0})


@api.put("/admin/restaurants/{restaurant_id}/odoo-connection")
async def admin_update_restaurant_odoo_connection(
    restaurant_id: str,
    body: OdooConnectionUpdateIn,
    _: dict = Depends(require_role("admin"))
):
    """Admin-only: Configure Odoo connection for a restaurant"""
    restaurant = await db.restaurants.find_one({"id": restaurant_id})
    if not restaurant:
        raise HTTPException(404, "Restaurant not found")
    
    odoo_connection = {
        "enabled": body.enabled,
        "company_id": body.company_id,
        "company_name": body.company_name,
        "warehouse_id": body.warehouse_id,
        "warehouse_name": body.warehouse_name,
        "pricelist_id": body.pricelist_id,
        "pricelist_name": body.pricelist_name,
        "pos_config_id": body.pos_config_id,
        "sync_products": body.sync_products,
        "sync_stock": body.sync_stock,
        "send_orders": body.send_orders,
        "send_delivery_updates": body.send_delivery_updates,
        "sync_status": "active" if body.enabled else "disabled",
        "last_sync_at": restaurant.get("odoo_connection", {}).get("last_sync_at"),
        "sync_error": None if body.enabled else restaurant.get("odoo_connection", {}).get("sync_error")
    }
    
    await db.restaurants.update_one({"id": restaurant_id}, {"$set": {"odoo_connection": odoo_connection}})
    return await db.restaurants.find_one({"id": restaurant_id}, {"_id": 0})


@api.get("/admin/blocked-emails")
async def list_blocked(_: dict = Depends(require_role("admin"))):
    return await db.blocked_emails.find({}, {"_id": 0}).to_list(500)


@api.post("/admin/block-email")
async def block_email(body: BlockEmailIn, user: dict = Depends(require_role("admin"))):
    email = body.email.lower()
    if email == (os.environ.get("ADMIN_EMAIL", "") or "").lower():
        raise HTTPException(400, "Cannot block the admin account")
    existing = await db.blocked_emails.find_one({"email": email})
    if existing:
        raise HTTPException(400, "Email already blocked")
    await db.blocked_emails.insert_one({"email": email, "blocked_at": now_iso()})
    return {"ok": True, "email": email}


@api.delete("/admin/block-email/{email}")
async def unblock_email(email: str, _: dict = Depends(require_role("admin"))):
    await db.blocked_emails.delete_one({"email": email.lower()})
    return {"ok": True}


# ----------------------------------------------------------------------------
# Exchange rate (seller-controlled, with global fallback)
# ----------------------------------------------------------------------------
@api.get("/exchange-rate")
async def get_rate(seller_id: Optional[str] = None):
    if seller_id:
        rec = await db.exchange_rates.find_one({"seller_id": seller_id}, {"_id": 0})
        if rec:
            return rec
    s = await get_settings()
    return {"seller_id": "__global__", "rate": float(s.get("global_rate", 600.0))}


@api.put("/exchange-rate")
async def set_rate(body: ExchangeRateIn, user: dict = Depends(require_role("seller"))):
    """Sellers set their own exchange rate for their products. Admins do not manage this."""
    await db.exchange_rates.update_one(
        {"seller_id": user["id"]},
        {"$set": {"seller_id": user["id"], "rate": float(body.rate), "updated_at": now_iso()}},
        upsert=True,
    )
    return {"seller_id": user["id"], "rate": body.rate}


# ----------------------------------------------------------------------------
# Invoices (weekly auto-generated)
# ----------------------------------------------------------------------------
def _iso_week_range(dt: datetime):
    """Return (monday_iso_date, sunday_iso_date, week_label) for given dt."""
    monday = dt - timedelta(days=dt.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6)
    label = f"{monday.strftime('%b %d')} – {sunday.strftime('%b %d, %Y')}"
    return monday.date().isoformat(), sunday.date().isoformat(), label


async def _rebuild_invoices():
    """Regenerate invoices from all orders. One invoice per (seller, shop, week).
    Each shop can override commission_rate; otherwise uses global settings rate."""
    settings = await get_settings()
    global_rate = float(settings.get("commission_rate", 0.10))

    products = await db.products.find({}, {"_id": 0}).to_list(5000)
    menu_items = await db.menu_items.find({}, {"_id": 0}).to_list(5000)
    restaurants = await db.restaurants.find({}, {"_id": 0}).to_list(500)
    shops = await db.shops.find({}, {"_id": 0}).to_list(500)
    shop_by_id = {s["id"]: s for s in shops}
    rest_by_id = {r["id"]: r for r in restaurants}

    # container_id -> effective commission rate (shop override or global)
    rate_for = {}
    for s in shops:
        r = s.get("commission_rate")
        rate_for[s["id"]] = float(r) if r is not None else global_rate
    for r in restaurants:
        rc = r.get("commission_rate")
        rate_for[r["id"]] = float(rc) if rc is not None else global_rate

    lookup = {}
    for p in products:
        shop = shop_by_id.get(p["shop_id"], {})
        lookup[p["id"]] = {"seller_id": p["seller_id"], "shop_id": p["shop_id"], "shop_name": shop.get("name", "—")}
    for m in menu_items:
        rest = rest_by_id.get(m["restaurant_id"], {})
        lookup[m["id"]] = {"seller_id": m["seller_id"], "shop_id": m["restaurant_id"], "shop_name": rest.get("name", "—")}

    orders = await db.orders.find({}, {"_id": 0}).to_list(5000)
    buckets: dict = {}
    for o in orders:
        try:
            created = datetime.fromisoformat(o["created_at"])
        except Exception:
            continue
        ws, we, label = _iso_week_range(created)
        for it in o.get("items", []):
            ref = lookup.get(it.get("item_id"))
            if not ref:
                continue
            key = (ref["seller_id"], ref["shop_id"], ws)
            b = buckets.setdefault(key, {
                "seller_id": ref["seller_id"], "shop_id": ref["shop_id"], "shop_name": ref["shop_name"],
                "week_start": ws, "week_end": we, "week_label": label,
                "total_sales": 0.0, "order_count": 0, "_orders": set(),
            })
            qty = int(it.get("quantity", 1))
            price = float(it.get("price_usd", 0))
            sides_total = sum(float(s.get("price_usd", 0)) for s in (it.get("sides") or []))
            b["total_sales"] += (price + sides_total) * qty
            b["_orders"].add(o["id"])

    existing = {
        (inv["seller_id"], inv["shop_id"], inv["week_start"]): inv
        for inv in await db.invoices.find({}, {"_id": 0}).to_list(5000)
    }

    await db.invoices.delete_many({})
    now = now_iso()
    for (seller_id, shop_id, ws), b in buckets.items():
        effective_rate = rate_for.get(shop_id, global_rate)
        commission = round(b["total_sales"] * effective_rate, 2)
        prev = existing.get((seller_id, shop_id, ws), {})
        await db.invoices.insert_one({
            "id": prev.get("id", str(uuid.uuid4())),
            "seller_id": seller_id,
            "shop_id": shop_id,
            "shop_name": b["shop_name"],
            "week_start": ws,
            "week_end": b["week_end"],
            "week_label": b["week_label"],
            "total_sales": round(b["total_sales"], 2),
            "commission": commission,
            "amount_owed": commission,
            "order_count": len(b["_orders"]),
            "commission_rate": effective_rate,
            "status": prev.get("status", "Unpaid"),
            "created_at": prev.get("created_at", now),
            "updated_at": now,
        })


@api.post("/admin/invoices/generate")
async def admin_regenerate_invoices(_: dict = Depends(require_role("admin"))):
    await _rebuild_invoices()
    count = await db.invoices.count_documents({})
    return {"ok": True, "count": count}


@api.get("/admin/invoices")
async def admin_list_invoices(status: Optional[str] = None, _: dict = Depends(require_role("admin"))):
    q: dict = {}
    if status in {"Paid", "Unpaid"}:
        q["status"] = status
    return await db.invoices.find(q, {"_id": 0}).sort("week_start", -1).to_list(1000)


@api.put("/admin/invoices/{invoice_id}/status")
async def admin_set_invoice_status(invoice_id: str, body: InvoiceStatusIn, _: dict = Depends(require_role("admin"))):
    inv = await db.invoices.find_one({"id": invoice_id})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    await db.invoices.update_one({"id": invoice_id}, {"$set": {"status": body.status, "updated_at": now_iso()}})

    sid = inv.get("seller_id")
    amount = float(inv.get("commission") or inv.get("amount_owed") or 0)
    label = inv.get("week_label") or inv.get("shop_name") or ""

    # Notify seller on status change
    if sid:
        if body.status == "Overdue":
            await create_notification(
                user_id=sid,
                message=f"Your commission invoice is overdue (USD {amount:.2f}) — {label}",
                ntype="commission",
                meta={"invoice_id": invoice_id},
            )
        elif body.status == "Paid":
            await create_notification(
                user_id=sid,
                message=f"Your commission invoice has been marked as paid (USD {amount:.2f}) — {label}. Thank you!",
                ntype="commission",
                meta={"invoice_id": invoice_id, "paid": True},
            )

    return await db.invoices.find_one({"id": invoice_id}, {"_id": 0})


@api.get("/admin/invoices/{invoice_id}")
async def admin_invoice_detail(invoice_id: str, _: dict = Depends(require_role("admin"))):
    inv = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    return inv


@api.get("/seller/invoices")
async def seller_list_invoices(user: dict = Depends(require_role("seller", "admin"))):
    return await db.invoices.find({"seller_id": user["id"]}, {"_id": 0}).sort("week_start", -1).to_list(500)




# ----------------------------------------------------------------------------
# Restaurant Invoices (separate weekly table for restaurant-order commissions)
# ----------------------------------------------------------------------------
async def _rebuild_restaurant_invoices():
    """Regenerate restaurant_invoices from all completed restaurant_orders.
    One invoice per (seller, restaurant, ISO-week). Mirrors _rebuild_invoices() but
    keeps restaurant commissions in a separate collection per product spec."""
    settings = await get_settings()
    global_rate = float(settings.get("commission_rate", 0.10))

    restaurants = await db.restaurants.find({}, {"_id": 0}).to_list(500)
    rest_by_id = {r["id"]: r for r in restaurants}

    rate_for = {}
    for r in restaurants:
        rc = r.get("commission_rate")
        rate_for[r["id"]] = float(rc) if rc is not None else global_rate

    orders = await db.restaurant_orders.find({"status": "completed"}, {"_id": 0}).to_list(5000)
    buckets: dict = {}
    for o in orders:
        try:
            created = datetime.fromisoformat(o["created_at"])
        except Exception:
            continue
        rest = rest_by_id.get(o.get("restaurant_id"))
        if not rest:
            continue
        seller_id = rest.get("seller_id")
        if not seller_id:
            continue
        ws, we, label = _iso_week_range(created)
        key = (seller_id, rest["id"], ws)
        b = buckets.setdefault(key, {
            "seller_id": seller_id,
            "restaurant_id": rest["id"],
            "restaurant_name": rest.get("name", "—"),
            "week_start": ws, "week_end": we, "week_label": label,
            "total_sales": 0.0, "order_count": 0, "_orders": set(),
        })
        # Restaurant orders already carry computed subtotal (items + sides);
        # delivery_fee is excluded from commissionable revenue.
        b["total_sales"] += float(o.get("subtotal") or 0)
        b["_orders"].add(o["id"])

    existing = {
        (inv["seller_id"], inv["restaurant_id"], inv["week_start"]): inv
        for inv in await db.restaurant_invoices.find({}, {"_id": 0}).to_list(5000)
    }

    await db.restaurant_invoices.delete_many({})
    now = now_iso()
    for (seller_id, restaurant_id, ws), b in buckets.items():
        effective_rate = rate_for.get(restaurant_id, global_rate)
        commission = round(b["total_sales"] * effective_rate, 2)
        prev = existing.get((seller_id, restaurant_id, ws), {})
        await db.restaurant_invoices.insert_one({
            "id": prev.get("id", str(uuid.uuid4())),
            "seller_id": seller_id,
            "restaurant_id": restaurant_id,
            "restaurant_name": b["restaurant_name"],
            "week_start": ws,
            "week_end": b["week_end"],
            "week_label": b["week_label"],
            "total_sales": round(b["total_sales"], 2),
            "commission": commission,
            "amount_owed": commission,
            "order_count": len(b["_orders"]),
            "commission_rate": effective_rate,
            "status": prev.get("status", "Unpaid"),
            "created_at": prev.get("created_at", now),
            "updated_at": now,
        })


@api.post("/admin/restaurant-invoices/generate")
async def admin_regenerate_restaurant_invoices(_: dict = Depends(require_role("admin"))):
    await _rebuild_restaurant_invoices()
    count = await db.restaurant_invoices.count_documents({})
    return {"ok": True, "count": count}


@api.get("/admin/restaurant-invoices")
async def admin_list_restaurant_invoices(status: Optional[str] = None, _: dict = Depends(require_role("admin"))):
    q: dict = {}
    if status in {"Paid", "Unpaid", "Overdue"}:
        q["status"] = status
    return await db.restaurant_invoices.find(q, {"_id": 0}).sort("week_start", -1).to_list(1000)


@api.put("/admin/restaurant-invoices/{invoice_id}/status")
async def admin_set_restaurant_invoice_status(
    invoice_id: str, body: InvoiceStatusIn, _: dict = Depends(require_role("admin"))
):
    inv = await db.restaurant_invoices.find_one({"id": invoice_id})
    if not inv:
        raise HTTPException(404, "Restaurant invoice not found")
    await db.restaurant_invoices.update_one(
        {"id": invoice_id},
        {"$set": {"status": body.status, "updated_at": now_iso()}},
    )

    sid = inv.get("seller_id")
    amount = float(inv.get("commission") or inv.get("amount_owed") or 0)
    label = inv.get("week_label") or inv.get("restaurant_name") or ""
    if sid:
        if body.status == "Paid":
            await create_notification(
                user_id=sid,
                message=f"Your restaurant commission invoice has been marked paid (USD {amount:.2f}) — {label}.",
                ntype="commission",
                meta={"restaurant_invoice_id": invoice_id, "paid": True},
            )
        elif body.status == "Overdue":
            await create_notification(
                user_id=sid,
                message=f"Your restaurant commission invoice is overdue (USD {amount:.2f}) — {label}.",
                ntype="commission",
                meta={"restaurant_invoice_id": invoice_id},
            )
    return await db.restaurant_invoices.find_one({"id": invoice_id}, {"_id": 0})


@api.get("/seller/restaurant-invoices")
async def seller_list_restaurant_invoices(user: dict = Depends(require_role("seller", "admin"))):
    return await db.restaurant_invoices.find(
        {"seller_id": user["id"]}, {"_id": 0}
    ).sort("week_start", -1).to_list(500)




# ----------------------------------------------------------------------------
# Seeding (production: only settings + a single admin account)
# ----------------------------------------------------------------------------
async def seed_production():
    """Create essential indexes + seed a single admin account from env.
    Idempotent: safe to call on every startup."""
    # Indexes
    await db.users.create_index("email", unique=True)
    # username is optional; used for admin username-login. Sparse+unique so
    # only records with a username value are enforced unique.
    await db.users.create_index("username", unique=True, sparse=True)
    await db.shops.create_index("id", unique=True)
    await db.products.create_index("id", unique=True)
    await db.restaurants.create_index("id", unique=True)
    await db.menu_items.create_index("id", unique=True)
    await db.orders.create_index("id", unique=True)
    await db.blocked_emails.create_index("email", unique=True)
    await db.favorites.create_index([("user_id", 1), ("target_type", 1), ("target_id", 1)])
    await db.invoices.create_index("id", unique=True)
    await db.restaurant_invoices.create_index("id", unique=True)
    await db.restaurant_invoices.create_index([("seller_id", 1), ("week_start", -1)])
    await db.reviews.create_index([("product_id", 1)])
    await db.reviews.create_index("id", unique=True)
    await db.notifications.create_index("id", unique=True)
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.email_verifications.create_index("token", unique=True)
    await db.email_verifications.create_index("user_id")
    await db.password_resets.create_index("token", unique=True)
    await db.password_resets.create_index("user_id")
    
    # New indexes for Phase 1
    await db.restaurant_orders.create_index("id", unique=True)
    await db.restaurant_orders.create_index([("restaurant_id", 1), ("status", 1)])
    await db.restaurant_orders.create_index([("customer_id", 1), ("created_at", -1)])
    await db.reviews.create_index([("restaurant_id", 1), ("created_at", -1)])
    # `order_id_1` used to be a NON-sparse unique index intended for
    # restaurant reviews (one review per order). Product reviews don't
    # carry an order_id, so every product review inserted `null` and
    # collided after the first insert (E11000 DuplicateKeyError → HTTP 500).
    # Migrate: drop the legacy index if it exists, then recreate as a
    # PARTIAL unique index — uniqueness is only enforced when order_id
    # is present and non-null (i.e. restaurant reviews only).
    try:
        info = await db.reviews.index_information()
        if "order_id_1" in info:
            legacy = info["order_id_1"]
            # If it's already a partial index we're good; otherwise recreate.
            if "partialFilterExpression" not in legacy:
                await db.reviews.drop_index("order_id_1")
    except Exception:
        pass  # missing index / permission — ignore, next call will create it.
    await db.reviews.create_index(
        "order_id",
        unique=True,
        partialFilterExpression={"order_id": {"$exists": True, "$type": "string"}},
        name="order_id_1",
    )
    await db.trending_stats.create_index([("target_type", 1), ("target_id", 1)], unique=True)

    # Global settings
    existing_s = await db.settings.find_one({"id": "system"})
    if not existing_s:
        await db.settings.insert_one(DEFAULT_SETTINGS.copy())

    # Pages (CMS) — seed defaults the FIRST time only. Once a page exists in
    # the DB, never overwrite it.
    await db.pages.create_index("slug", unique=True)
    for slug, default_doc in PAGES_DEFAULT.items():
        existing_page = await db.pages.find_one({"slug": slug})
        if not existing_page:
            await db.pages.insert_one({**default_doc, "last_updated": now_iso()})
            log.info(f"📄 Seeded default page: {slug}")

    # Site config — seed footer defaults the first time only
    await db.site_config.create_index("id", unique=True)
    existing_footer = await db.site_config.find_one({"id": "footer"})
    if not existing_footer:
        await db.site_config.insert_one({**FOOTER_DEFAULT, "last_updated": now_iso()})
        log.info("🦶 Seeded default footer config")

    # Categories — seed defaults the first time only (idempotent).
    await db.categories.create_index("id", unique=True)
    await db.categories.create_index([("group", 1), ("parent_id", 1), ("order", 1)])
    await db.categories.create_index([("group", 1), ("parent_id", 1), ("name", 1)], unique=True)
    for group_key in CATEGORY_GROUPS:
        existing_in_group = await db.categories.count_documents({"group": group_key})
        if existing_in_group > 0:
            continue  # never overwrite once any category in the group exists
        order_counter = 0
        for top in CATEGORIES_DEFAULT.get(group_key, []):
            order_counter += 1
            top_id = str(uuid.uuid4())
            await db.categories.insert_one({
                "id": top_id,
                "name": top["name"],
                "group": group_key,
                "parent_id": None,
                "order": order_counter,
                "image_url": top.get("image_url") or "",
                "is_active": True,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            })
            child_counter = 0
            for child in top.get("children", []) or []:
                child_counter += 1
                await db.categories.insert_one({
                    "id": str(uuid.uuid4()),
                    "name": child["name"],
                    "group": group_key,
                    "parent_id": top_id,
                    "order": child_counter,
                    "image_url": child.get("image_url") or "",
                    "is_active": True,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                })
        log.info(f"📁 Seeded default categories for group: {group_key}")

    # Admin account (from env)
    admin_email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD") or ""
    admin_username = (os.environ.get("ADMIN_USERNAME") or "admin").strip().lower()
    if not admin_email or not admin_password:
        log.warning("ADMIN_EMAIL / ADMIN_PASSWORD not set — no admin account will be seeded.")
        return

    existing = await db.users.find_one({"email": admin_email})
    if existing:
        # Make sure existing admin account stays an admin + is flagged verified + active,
        # but never overwrite the password after first seed. Also ensure username is set
        # so username-login works.
        set_fields = {"role": "admin", "email_verified": True, "is_active": True}
        if not existing.get("username"):
            set_fields["username"] = admin_username
        await db.users.update_one(
            {"email": admin_email},
            {"$set": set_fields},
        )
    else:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "username": admin_username,
            "name": "Admin",
            "role": "admin",
            "phone": "",
            "settings": {},
            "email_verified": True,
            "is_active": True,
            "must_change_password": False,
            "password_hash": hash_password(admin_password),
            "created_at": now_iso(),
        })
        log.info(f"✅ Seeded admin account: {admin_email} (username: {admin_username})")


@app.on_event("startup")
async def on_startup():
    await seed_production()
    # Init Emergent Object Storage session key (non-fatal — uploads fall
    # back to local disk if this fails).
    try:
        storage.init_storage()
    except Exception as exc:
        log.warning("Object storage init failed at startup: %s (uploads will use disk fallback)", exc)
    # Bind cod module's dependencies (only after server module is fully loaded)
    cod.bind(
        db_=db, log_=log,
        get_current_user_=get_current_user,
        require_role_=require_role,
        get_settings_=get_settings,
        create_notification_=create_notification,
        now_iso_=now_iso,
        hash_password_=hash_password,
    )
    cod.register_endpoints()
    await cod.seed_cod()
    try:
        await cod.backfill_existing_orders()
    except Exception as exc:
        log.warning(f"COD backfill skipped: {exc}")
    # Mount the COD router AFTER it's been rebuilt by register_endpoints.
    app.include_router(cod.router)
    
    # Register Odoo integration routes (webhook + admin)
    odoo_webhook_router = odoo_routes.create_odoo_routes(db, require_role)
    odoo_admin_router = odoo_routes.create_admin_odoo_routes(db, require_role, get_current_user)
    app.include_router(odoo_webhook_router)
    app.include_router(odoo_admin_router)
    log.info("✅ Odoo integration routes registered")
    
    # Backfill existing shops/restaurants with default Odoo connection settings
    try:
        default_odoo_connection = {
            "enabled": False,
            "company_id": None,
            "company_name": None,
            "warehouse_id": None,
            "warehouse_name": None,
            "pricelist_id": None,
            "pricelist_name": None,
            "pos_config_id": None,
            "sync_products": False,
            "sync_stock": False,
            "send_orders": False,
            "send_delivery_updates": False,
            "last_sync_at": None,
            "sync_status": "not_configured",
            "sync_error": None
        }
        
        # Backfill shops
        shops_updated = await db.shops.update_many(
            {"odoo_connection": {"$exists": False}},
            {"$set": {"odoo_connection": default_odoo_connection}}
        )
        if shops_updated.modified_count > 0:
            log.info(f"✅ Backfilled Odoo connection for {shops_updated.modified_count} shops")
        
        # Backfill restaurants
        restaurants_updated = await db.restaurants.update_many(
            {"odoo_connection": {"$exists": False}},
            {"$set": {"odoo_connection": default_odoo_connection}}
        )
        if restaurants_updated.modified_count > 0:
            log.info(f"✅ Backfilled Odoo connection for {restaurants_updated.modified_count} restaurants")
    except Exception as exc:
        log.warning(f"Odoo connection backfill skipped: {exc}")

    # Backfill shop ratings once on startup so existing shops without the
    # average_rating/review_count fields show ratings rolled-up from product
    # reviews. Cheap and idempotent — only touches shops that need it.
    try:
        pending = await db.shops.find(
            {"$or": [{"average_rating": {"$exists": False}}, {"review_count": {"$exists": False}}]},
            {"_id": 0, "id": 1},
        ).to_list(5000)
        for s in pending:
            await _recompute_shop_rating(s["id"])
        if pending:
            log.info(f"✅ Backfilled shop ratings for {len(pending)} shops")
    except Exception as exc:  # pragma: no cover — startup best-effort
        log.warning(f"shop rating backfill skipped: {exc}")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


# --- SEO: sitemap.xml + robots.txt served under /api so Kubernetes ingress routes them here ---

@api.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml(request: Request):
    """Dynamic sitemap of shops, restaurants, and products.
    Google can crawl a non-root sitemap as long as robots.txt points to it.
    """
    from fastapi.responses import Response as _Resp
    base = os.environ.get("FRONTEND_URL") or f"{request.url.scheme}://{request.headers.get('host','')}"
    base = base.rstrip("/")
    now = now_iso()
    static_paths = ["/", "/marketplace", "/shops", "/restaurants", "/about", "/contact", "/terms", "/privacy", "/returns"]
    urls = []
    for p in static_paths:
        urls.append(f"<url><loc>{base}{p}</loc><lastmod>{now[:10]}</lastmod><changefreq>daily</changefreq><priority>{'1.0' if p=='/' else '0.7'}</priority></url>")
    # Shops
    try:
        shops = await db.shops.find({"is_active": {"$ne": False}}, {"_id": 0, "id": 1, "updated_at": 1, "created_at": 1}).to_list(1000)
        for s in shops:
            lastmod = (s.get("updated_at") or s.get("created_at") or now)[:10]
            urls.append(f"<url><loc>{base}/shop/{s['id']}</loc><lastmod>{lastmod}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>")
    except Exception:
        pass
    # Products
    try:
        products = await db.products.find({}, {"_id": 0, "id": 1, "updated_at": 1, "created_at": 1}).limit(5000).to_list(5000)
        for p in products:
            lastmod = (p.get("updated_at") or p.get("created_at") or now)[:10]
            urls.append(f"<url><loc>{base}/product/{p['id']}</loc><lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq><priority>0.6</priority></url>")
    except Exception:
        pass

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls) +
        "\n</urlset>"
    )
    return _Resp(content=xml, media_type="application/xml")


@api.get("/robots.txt", include_in_schema=False)
async def robots_txt(request: Request):
    from fastapi.responses import PlainTextResponse
    base = os.environ.get("FRONTEND_URL") or f"{request.url.scheme}://{request.headers.get('host','')}"
    base = base.rstrip("/")
    txt = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /seller\n"
        "Disallow: /driver\n"
        "Disallow: /cart\n"
        "Disallow: /orders\n"
        "Disallow: /settings\n"
        "Disallow: /api/\n\n"
        f"Sitemap: {base}/api/sitemap.xml\n"
    )
    return PlainTextResponse(txt, media_type="text/plain")


# ============================================================
# Live Driver Tracking (P1 — customer sees driver on map + ETA)
# ============================================================
# Drivers POST their GPS every ~10 seconds while a delivery is
# `out_for_delivery`. Customers with an active order pull the
# latest known driver location + destination centroid to render
# a live map (Leaflet on the frontend).
#
# Storage strategy
# ----------------
# - `db.driver_locations`: one doc per driver with the *latest*
#   coordinates + a small `trail` of recent points (max 20) so
#   the map can animate. Overwrites on every ping.
# - No historical audit log — deliveries in this app are short
#   and per-order geo history isn't required. Adding a TTL-indexed
#   `driver_location_history` collection is an easy P2 upgrade.

# Approximate lat/lng for known Juba neighborhood centroids. Used as
# a destination fallback when the customer address doesn't have
# explicit coordinates. Source: publicly known landmark centroids.
JUBA_AREA_COORDS = {
    "Munuki":       (4.8720, 31.5720),
    "Jebel":        (4.8300, 31.5700),
    "Gudele":       (4.8800, 31.5300),
    "Konyo Konyo":  (4.8420, 31.5900),
    "Hai Cinema":   (4.8560, 31.5920),
    "Nyakuron":     (4.8480, 31.5810),
    "Atlabara":     (4.8620, 31.5860),
}
# Fallback centroid = downtown Juba if the area isn't in our list.
JUBA_DEFAULT_COORDS = (4.8517, 31.5825)


class DriverLocationIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy: Optional[float] = None  # meters, if the browser provides it


def _haversine_km(a: tuple, b: tuple) -> float:
    """Great-circle distance in kilometres between two (lat, lng) points."""
    import math
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _area_coords(area: Optional[str]) -> tuple:
    return JUBA_AREA_COORDS.get((area or "").strip(), JUBA_DEFAULT_COORDS)


@api.post("/driver/location")
async def post_driver_location(body: DriverLocationIn, user: dict = Depends(require_role("driver"))):
    """Driver → server: push current GPS position (called every ~10 s from
    the app). Live map is ONLY for admin-managed delivery — sellers who use
    their own external driver never push GPS here."""
    doc = await db.driver_locations.find_one({"driver_id": user["id"]}, {"_id": 0})
    trail = (doc or {}).get("trail", [])
    point = {"lat": body.lat, "lng": body.lng, "at": now_iso()}
    trail.append(point)
    trail = trail[-20:]  # keep last 20 pings only
    await db.driver_locations.update_one(
        {"driver_id": user["id"]},
        {"$set": {
            "driver_id": user["id"],
            "lat": body.lat,
            "lng": body.lng,
            "accuracy": body.accuracy,
            "updated_at": now_iso(),
            "trail": trail,
        }},
        upsert=True,
    )
    return {"ok": True}


@api.get("/customer/orders/{order_id}/live-tracking")
async def customer_live_tracking(order_id: str, user: dict = Depends(get_current_user)):
    """Return every in-progress driver assignment for this order, with
    the driver's current location + a destination centroid + a
    simple ETA (Haversine × 4 min per km)."""
    # Fetch order & authorize (customer or admin only)
    order = await db.orders.find_one({"id": order_id}, {"_id": 0}) \
        or await db.restaurant_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order not found")
    if user["role"] != "admin" and order.get("customer_id") != user["id"]:
        raise HTTPException(403, "Forbidden")

    # Destination = customer's delivery area centroid (fallback: downtown).
    dest_area = (order.get("delivery_address") or {}).get("area") or order.get("delivery_area") or order.get("area")
    dest_lat, dest_lng = _area_coords(dest_area)

    # Collect assignments: splits (marketplace) or the restaurant_order itself.
    assignments = []
    splits = await db.order_splits.find(
        {"parent_order_id": order_id},
        {"_id": 0, "id": 1, "driver_id": 1, "delivery_status": 1, "seller_id": 1, "shop_area": 1}
    ).to_list(50)
    for sp in splits:
        if sp.get("delivery_status") not in ("out_for_delivery", "picked_up"):
            continue
        assignments.append({
            "kind": "split",
            "id": sp["id"],
            "driver_id": sp.get("driver_id"),
            "status": sp.get("delivery_status"),
            "pickup_area": sp.get("shop_area"),
        })
    # Standalone restaurant order — the doc itself carries the driver.
    if order.get("driver_id") and order.get("status") in ("out_for_delivery", "picked_up"):
        assignments.append({
            "kind": "restaurant_order",
            "id": order["id"],
            "driver_id": order.get("driver_id"),
            "status": order.get("status"),
            "pickup_area": order.get("pickup_area"),
        })

    # Enrich with driver name + latest location + ETA.
    out = []
    for a in assignments:
        drv = a.get("driver_id")
        if not drv:
            continue
        loc = await db.driver_locations.find_one({"driver_id": drv}, {"_id": 0})
        drv_user = await db.users.find_one({"id": drv}, {"_id": 0, "name": 1})
        entry = {
            "assignment_kind": a["kind"],
            "assignment_id": a["id"],
            "driver_id": drv,
            "driver_name": (drv_user or {}).get("name", "Driver"),
            "status": a["status"],
            "destination": {"lat": dest_lat, "lng": dest_lng, "area": dest_area or "Juba"},
        }
        if loc and loc.get("lat") is not None:
            entry["driver_location"] = {"lat": loc["lat"], "lng": loc["lng"], "at": loc.get("updated_at")}
            km = _haversine_km((loc["lat"], loc["lng"]), (dest_lat, dest_lng))
            # 4 min per km ≈ 15 km/h — realistic Juba delivery speed on motorbike.
            eta_min = max(1, int(round(km * 4)))
            entry["distance_km"] = round(km, 2)
            entry["eta_minutes"] = eta_min
        else:
            entry["driver_location"] = None
        out.append(entry)

    return {
        "order_id": order_id,
        "destination": {"lat": dest_lat, "lng": dest_lng, "area": dest_area or "Juba"},
        "assignments": out,
    }




# ============================================================
# Seller Onboarding Guide — step-by-step guide + progress tracking
# ============================================================
# Nine canonical steps. Some are auto-detected from existing data
# (e.g. "shop" is complete when the seller has ≥1 shop); others are
# manually marked complete by the seller (e.g. "orders" — read the
# section explaining how to fulfill orders).
#
# The "core" steps required to earn the "Setup Verified" shop badge
# are: profile, shop, product, delivery, payout.

_ONBOARDING_STEPS = [
    {"id": "profile",   "core": True,  "auto": True},
    {"id": "shop",      "core": True,  "auto": True},
    {"id": "product",   "core": True,  "auto": True},
    {"id": "delivery",  "core": True,  "auto": True},
    {"id": "payout",    "core": True,  "auto": False},
    {"id": "orders",    "core": False, "auto": False},
    {"id": "analytics", "core": False, "auto": False},
    {"id": "bulk",      "core": False, "auto": True},
    {"id": "reviews",   "core": False, "auto": False},
]
_ONBOARDING_CORE_IDS = {s["id"] for s in _ONBOARDING_STEPS if s["core"]}


async def _compute_onboarding_progress(user_id: str) -> dict:
    """Compute a seller's onboarding progress by auto-detecting completed
    steps from existing collections + merging with manually-marked ones
    stored in db.onboarding_progress."""
    # Load user + manual progress in parallel would be nice, but keep it simple
    user = await db.users.find_one({"id": user_id}, {"_id": 0}) or {}
    progress = await db.onboarding_progress.find_one({"user_id": user_id}, {"_id": 0}) or {}
    manual_completed = set(progress.get("manual_completed") or [])
    wizard_dismissed = bool(progress.get("wizard_dismissed"))
    tour_completed = bool(progress.get("tour_completed"))

    # Auto-detection
    has_name = bool((user.get("name") or "").strip())
    has_phone = bool((user.get("phone") or "").strip())
    profile_done = has_name and has_phone

    shops = await db.shops.find({"seller_id": user_id}, {"_id": 0}).to_list(50)
    shop_done = len(shops) > 0

    product_done = False
    if shop_done:
        shop_ids = [s["id"] for s in shops]
        cnt = await db.products.count_documents({"shop_id": {"$in": shop_ids}})
        product_done = cnt > 0

    delivery_done = False
    for s in shops:
        mode = s.get("delivery_mode")
        if mode == "fixed" and float(s.get("delivery_fee_usd") or 0) > 0:
            delivery_done = True; break
        if mode == "per_area" and (s.get("delivery_per_area") or []):
            delivery_done = True; break
        if mode == "free":
            delivery_done = True; break

    bulk_done = bool((user.get("meta") or {}).get("bulk_import_used"))

    auto_status = {
        "profile": profile_done,
        "shop": shop_done,
        "product": product_done,
        "delivery": delivery_done,
        "bulk": bulk_done,
    }

    steps_out = []
    completed_count = 0
    core_completed = 0
    for s in _ONBOARDING_STEPS:
        done = auto_status.get(s["id"], False) or (s["id"] in manual_completed)
        if done:
            completed_count += 1
            if s["core"]:
                core_completed += 1
        steps_out.append({"id": s["id"], "done": done, "auto": s["auto"], "core": s["core"]})

    total = len(_ONBOARDING_STEPS)
    percent = int(round(100 * completed_count / total)) if total else 0
    badge_earned = core_completed >= len(_ONBOARDING_CORE_IDS)

    return {
        "steps": steps_out,
        "completed_count": completed_count,
        "total_count": total,
        "percent": percent,
        "wizard_dismissed": wizard_dismissed,
        "tour_completed": tour_completed,
        "badge_earned": badge_earned,
    }


@api.get("/seller/onboarding/progress")
async def get_onboarding_progress(user: dict = Depends(require_role("seller", "admin"))):
    return await _compute_onboarding_progress(user["id"])


class OnboardingStepIn(BaseModel):
    step_id: str


@api.post("/seller/onboarding/complete-step")
async def complete_onboarding_step(body: OnboardingStepIn, user: dict = Depends(require_role("seller", "admin"))):
    valid_ids = {s["id"] for s in _ONBOARDING_STEPS}
    if body.step_id not in valid_ids:
        raise HTTPException(status_code=400, detail="Unknown step_id")
    await db.onboarding_progress.update_one(
        {"user_id": user["id"]},
        {
            "$addToSet": {"manual_completed": body.step_id},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            "$setOnInsert": {"user_id": user["id"]},
        },
        upsert=True,
    )
    return await _compute_onboarding_progress(user["id"])


@api.post("/seller/onboarding/uncheck-step")
async def uncheck_onboarding_step(body: OnboardingStepIn, user: dict = Depends(require_role("seller", "admin"))):
    """Allow sellers to un-check a manually-completed step (mistakes happen)."""
    await db.onboarding_progress.update_one(
        {"user_id": user["id"]},
        {"$pull": {"manual_completed": body.step_id},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return await _compute_onboarding_progress(user["id"])


@api.post("/seller/onboarding/dismiss-wizard")
async def dismiss_onboarding_wizard(user: dict = Depends(require_role("seller", "admin"))):
    await db.onboarding_progress.update_one(
        {"user_id": user["id"]},
        {"$set": {"wizard_dismissed": True, "updated_at": datetime.now(timezone.utc).isoformat()},
         "$setOnInsert": {"user_id": user["id"]}},
        upsert=True,
    )
    return {"ok": True}


@api.post("/seller/onboarding/complete-tour")
async def complete_onboarding_tour(user: dict = Depends(require_role("seller", "admin"))):
    await db.onboarding_progress.update_one(
        {"user_id": user["id"]},
        {"$set": {"tour_completed": True, "updated_at": datetime.now(timezone.utc).isoformat()},
         "$setOnInsert": {"user_id": user["id"]}},
        upsert=True,
    )
    return {"ok": True}


# Uploaded images are now served via the /api/uploads/{filename} route
# defined earlier in this file. That route serves from Emergent Object
# Storage (canonical) with a legacy fallback to /app/backend/uploads/.

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
)
