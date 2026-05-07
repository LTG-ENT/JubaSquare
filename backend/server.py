from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

import bcrypt
import jwt
import secrets
import re
from pathlib import Path as _FsPath
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, UploadFile, File
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

import email_service
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
    "areas": DEFAULT_AREAS,
    "token_version": 1,
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


async def create_notification(user_id: str, message: str, ntype: str = "alert", meta: Optional[dict] = None) -> dict:
    """Insert a notification for a single user. Safe to call multiple times."""
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
# Models
# ----------------------------------------------------------------------------
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=120)
    role: Literal["customer", "seller"] = "customer"
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
    # Storefront fields (Round 7) — separate banner + logo + opening hours + open/closed
    banner_url: Optional[str] = ""
    logo_url: Optional[str] = ""
    opening_hours: Optional[str] = ""
    is_open: bool = True
    # Round 8 — published/public visibility (sellers can hide their shop without deleting)
    is_public: bool = True


class ShopMessageIn(BaseModel):
    body: str
    subject: Optional[str] = ""
    customer_email: Optional[str] = ""  # used when sender is anonymous
    customer_phone: Optional[str] = ""
    customer_name: Optional[str] = ""


class ShopCommissionIn(BaseModel):
    commission_rate: Optional[float] = None  # None = inherit global rate


class ProductIn(BaseModel):
    shop_id: str
    name: str
    category: str
    price_usd: float
    image_url: Optional[str] = ""
    description: Optional[str] = ""
    stock: int = 100
    is_wholesale: bool = False
    min_order_qty: int = 1
    bulk_price_usd: Optional[float] = None
    mode: Literal["marketplace", "wholesale"] = "marketplace"
    pricing_tiers: List[dict] = Field(default_factory=list)


class SideItem(BaseModel):
    name: str
    price_usd: float


class RestaurantIn(BaseModel):
    name: str
    category: str
    description: Optional[str] = ""
    image_url: Optional[str] = ""
    area: str
    is_open: bool = True


class MenuItemIn(BaseModel):
    restaurant_id: str
    name: str
    price_usd: float
    image_url: Optional[str] = ""
    description: Optional[str] = ""
    food_category: Optional[str] = ""
    side_items: List[SideItem] = Field(default_factory=list)


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
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = ""


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


# ----------------------------------------------------------------------------
# Auth endpoints
# ----------------------------------------------------------------------------
@api.post("/auth/login")
async def login(payload: LoginIn, request: Request, response: Response):
    email = payload.email.lower()
    blocked = await db.blocked_emails.find_one({"email": email})
    if blocked:
        raise HTTPException(status_code=403, detail="This email has been blocked by admin")

    settings = await get_settings()
    limit = max(1, int(settings.get("login_attempt_limit", 5)))
    ip = request.client.host if request.client else "unknown"
    key = f"{ip}:{email}"
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

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"key": key},
            {"$inc": {"count": 1}, "$set": {"last_at": now_iso()}},
            upsert=True,
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Require verified email for non-admin roles
    if user.get("role") != "admin" and not user.get("email_verified", False):
        raise HTTPException(
            status_code=403,
            detail="Please verify your email before signing in. Check your inbox for the verification link.",
        )

    if user.get("suspended"):
        raise HTTPException(status_code=403, detail="Your account has been suspended. Contact support.")

    await db.login_attempts.delete_one({"key": key})
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
        "role": body.role,  # customer | seller
        "phone": (body.phone or "").strip(),
        "password_hash": hash_password(body.password),
        "email_verified": False,
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
        {"$set": {"password_hash": hash_password(body.new_password)}},
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
    dest = UPLOAD_DIR / fname
    with open(dest, "wb") as f:
        f.write(data)
    # Build an absolute URL so the browser can load it directly without proxy rewrites.
    origin = (os.environ.get("FRONTEND_URL") or "").rstrip("/")
    if not origin:
        origin = f"{request.url.scheme}://{request.url.netloc}"
    public_url = f"{origin}/api/uploads/{fname}"
    return {"ok": True, "url": public_url, "filename": fname}


# ----------------------------------------------------------------------------
# Public: System settings (read-only public subset) + Areas
# ----------------------------------------------------------------------------
@api.get("/settings/public")
async def public_settings():
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
    }


@api.get("/meta/areas")
async def get_areas():
    s = await get_settings()
    return s.get("areas", DEFAULT_AREAS)


@api.get("/meta/health")
async def health():
    return {"ok": True, "service": "JubaSquare API"}


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
    """Public — returns minimal page list (for navigation/discovery)."""
    docs = await db.pages.find({}, {"_id": 0}).to_list(50)
    return [
        {"slug": d.get("slug"), "title": d.get("title", ""), "last_updated": d.get("last_updated")}
        for d in docs
    ]


@api.get("/pages/{slug}")
async def get_page(slug: str):
    p = await db.pages.find_one({"slug": slug}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Page not found")
    return _public_page(p)


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
    """Public — current footer config (with defaults filled in)."""
    doc = await db.site_config.find_one({"id": "footer"}, {"_id": 0})
    return _footer_doc(doc)


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
    saved = await db.site_config.find_one({"id": "footer"}, {"_id": 0})
    return _footer_doc(saved)


# ----------------------------------------------------------------------------
# Categories (admin-managed, hierarchical: 1 level of sub-categories)
# ----------------------------------------------------------------------------
ALLOWED_CATEGORY_GROUPS = {"retail", "wholesale", "restaurant", "food"}


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
    """Backward-compatible flat lists per group, plus structured tree."""
    flat = await _categories_query(None, active_only=True)
    by_group: dict = {g: [] for g in ALLOWED_CATEGORY_GROUPS}
    for c in flat:
        by_group.setdefault(c["group"], []).append(c)

    def _names(group_key: str) -> list:
        # Top-level names only (mirrors the old shape)
        return [c["name"] for c in by_group.get(group_key, []) if not c.get("parent_id")]

    # Aggregate all children across all groups for the legacy flat
    # "food_subcategories" array — anything that has a parent is treated as a sub.
    all_subs = [c["name"] for c in flat if c.get("parent_id")]
    food_top_subs = [c["name"] for c in flat if c.get("group") == "food" and not c.get("parent_id")]

    # Tree per group (each top-level with its children)
    trees = {g: _build_tree([c for c in flat if c["group"] == g]) for g in ALLOWED_CATEGORY_GROUPS}

    return {
        # legacy flat lists (still used by older UI code)
        "retail": _names("retail"),
        "wholesale": _names("wholesale"),
        "restaurant": _names("restaurant"),
        "food_subcategories": food_top_subs or all_subs,
        # new structured tree, keyed by group
        "groups": trees,
    }


@api.get("/categories")
async def list_categories(group: Optional[str] = None):
    """Public flat list of active categories."""
    return await _categories_query(group, active_only=True)


@api.get("/categories/tree")
async def categories_tree(group: Optional[str] = None):
    """Public tree (parent → children). Active only."""
    flat = await _categories_query(group, active_only=True)
    if group:
        return _build_tree(flat)
    return {g: _build_tree([c for c in flat if c["group"] == g]) for g in ALLOWED_CATEGORY_GROUPS}


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
    category: Optional[str] = None,
    area: Optional[str] = None,
    kind: Optional[str] = None,
    limit: Optional[int] = None,
    skip: Optional[int] = None,
):
    # Public marketplace listing — exclude shops that the seller has hidden (is_public=False).
    # Legacy shops without the flag default to visible.
    lim, off = clamp_pagination(limit, skip)
    q: dict = {"$or": [{"is_public": {"$ne": False}}, {"is_public": {"$exists": False}}]}
    if category:
        q["category"] = category
    if area:
        q["area"] = area
    if kind:
        q["kind"] = kind
    # Verified-first sort happens in Python; we have to fetch a wider window
    # than `limit` so the sort is meaningful, then slice.
    raw = await db.shops.find(q, {"_id": 0}).to_list(MAX_PAGE_LIMIT + off + lim)
    s = await get_settings()
    sorted_shops = _sort_shops(raw, s.get("verified_first", True))
    return sorted_shops[off : off + lim]


@api.get("/shops/mine")
async def my_shops(
    user: dict = Depends(require_role("seller", "admin")),
    limit: Optional[int] = None,
    skip: Optional[int] = None,
):
    lim, off = clamp_pagination(limit, skip)
    return await db.shops.find({"seller_id": user["id"]}, {"_id": 0}).skip(off).to_list(lim)



@api.get("/shops/{shop_id}")
async def get_shop(shop_id: str):
    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0})
    if not shop:
        raise HTTPException(404, "Shop not found")
    return shop


@api.post("/shops")
async def create_shop(body: ShopIn, user: dict = Depends(require_role("seller", "admin"))):
    s = await get_settings()
    initial_status = "Verified" if s.get("auto_approve_shops") else "Pending"
    shop = {
        "id": str(uuid.uuid4()),
        "seller_id": user["id"],
        "verification": initial_status,
        "created_at": now_iso(),
        **body.model_dump(),
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
    await db.shops.update_one({"id": shop_id}, {"$set": body.model_dump()})
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
    await db.shops.delete_one({"id": shop_id})
    await db.products.delete_many({"shop_id": shop_id})
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
        # Anonymous — require at least an email or phone for the seller to reply
        if not sender["customer_email"] and not sender["customer_phone"]:
            raise HTTPException(400, "Please provide an email or phone so the shop can reply")

    msg = {
        "id": str(uuid.uuid4()),
        "shop_id": shop_id,
        "shop_name": shop.get("name", ""),
        "seller_id": shop["seller_id"],
        "subject": (body.subject or "").strip(),
        "body": text,
        "is_read": False,
        "created_at": now_iso(),
        **sender,
    }
    await db.shop_messages.insert_one(msg)
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


# ----------------------------------------------------------------------------
# Products
# ----------------------------------------------------------------------------
@api.get("/products")
async def list_products(category: Optional[str] = None, area: Optional[str] = None,
                        shop_id: Optional[str] = None, kind: Optional[str] = None,
                        is_wholesale: Optional[bool] = None,
                        limit: Optional[int] = None, skip: Optional[int] = None):
    lim, off = clamp_pagination(limit, skip)
    q: dict = {}
    if category:
        q["category"] = category
    if shop_id:
        q["shop_id"] = shop_id
    if is_wholesale is not None:
        q["is_wholesale"] = is_wholesale
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

    # Hide products from shops that are not public (sellers can hide their shop without deleting).
    # Skip when caller is targeting a specific shop_id (so the owner's preview / private shop page still works).
    if not shop_id:
        hidden_shops = {s["id"] for s in await db.shops.find(
            {"is_public": False}, {"_id": 0, "id": 1}).to_list(INTERNAL_CAP)}
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

    # Verified-first sort if enabled
    if s.get("verified_first", True):
        order = {"Verified": 0, "Pending": 1, "Rejected": 2}
        products.sort(key=lambda p: order.get(p.get("shop_verification", "Pending"), 1))
    # Final pagination slice
    return products[off : off + lim]


@api.get("/products/{product_id}")
async def get_product(product_id: str):
    p = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Product not found")
    # Embed seller exchange rate
    s = await get_settings()
    global_rate = float(s.get("global_rate", 600.0))
    rec = await db.exchange_rates.find_one({"seller_id": p["seller_id"]}, {"_id": 0})
    p["exchange_rate_ssp"] = float(rec.get("rate", global_rate)) if rec else global_rate
    sh = await db.shops.find_one({"id": p["shop_id"]}, {"_id": 0, "verification": 1})
    p["shop_verification"] = (sh or {}).get("verification", "Pending")
    return p


@api.post("/products")
async def create_product(body: ProductIn, user: dict = Depends(require_role("seller", "admin"))):
    shop = await db.shops.find_one({"id": body.shop_id})
    if not shop:
        raise HTTPException(404, "Shop not found")
    if user["role"] != "admin" and shop["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
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


@api.put("/products/{product_id}")
async def update_product(product_id: str, body: ProductIn, user: dict = Depends(require_role("seller", "admin"))):
    p = await db.products.find_one({"id": product_id})
    if not p:
        raise HTTPException(404, "Product not found")
    if user["role"] != "admin" and p["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
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
async def list_restaurants(area: Optional[str] = None, category: Optional[str] = None,
                           limit: Optional[int] = None, skip: Optional[int] = None):
    lim, off = clamp_pagination(limit, skip)
    q: dict = {}
    if area:
        q["area"] = area
    if category:
        q["category"] = category
    rests = await db.restaurants.find(q, {"_id": 0}).to_list(MAX_PAGE_LIMIT + off + lim)
    s = await get_settings()
    if s.get("verified_first", True):
        order = {"Verified": 0, "Pending": 1, "Rejected": 2}
        rests.sort(key=lambda r: order.get(r.get("verification", "Pending"), 1))
    return rests[off : off + lim]


@api.get("/restaurants/{restaurant_id}")
async def get_restaurant(restaurant_id: str):
    r = await db.restaurants.find_one({"id": restaurant_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Restaurant not found")
    return r


@api.get("/restaurants/{restaurant_id}/menu")
async def get_menu(restaurant_id: str, limit: Optional[int] = None, skip: Optional[int] = None):
    lim, off = clamp_pagination(limit, skip)
    return await db.menu_items.find({"restaurant_id": restaurant_id}, {"_id": 0}).skip(off).to_list(lim)


@api.post("/restaurants")
async def create_restaurant(body: RestaurantIn, user: dict = Depends(require_role("seller", "admin"))):
    s = await get_settings()
    initial_status = "Verified" if s.get("auto_approve_shops") else "Pending"
    r = {
        "id": str(uuid.uuid4()),
        "seller_id": user["id"],
        "verification": initial_status,
        "created_at": now_iso(),
        **body.model_dump(),
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


@api.post("/menu-items")
async def create_menu_item(body: MenuItemIn, user: dict = Depends(require_role("seller", "admin"))):
    r = await db.restaurants.find_one({"id": body.restaurant_id})
    if not r:
        raise HTTPException(404, "Restaurant not found")
    if user["role"] != "admin" and r["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
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

    subtotal = sum(it.price_usd * it.quantity + sum(sd.price_usd for sd in (it.sides or [])) * it.quantity for it in body.items)

    # Compute per-shop delivery fee based on customer area
    delivery_fee = 0.0
    delivery_breakdown: List[dict] = []
    item_ids = [it.item_id for it in body.items]
    products = await db.products.find({"id": {"$in": item_ids}}, {"_id": 0}).to_list(2000)
    shop_ids_in_order = list({p["shop_id"] for p in products})
    if shop_ids_in_order:
        shops = await db.shops.find({"id": {"$in": shop_ids_in_order}}, {"_id": 0}).to_list(500)
        for sh in shops:
            mode = sh.get("delivery_mode", "free")
            fee = 0.0
            if mode == "fixed":
                fee = float(sh.get("delivery_fee_usd") or 0)
            elif mode == "per_area":
                for entry in sh.get("delivery_per_area", []) or []:
                    if (entry.get("area") or "").lower() == body.area.lower():
                        fee = float(entry.get("fee_usd") or 0)
                        break
            delivery_fee += fee
            delivery_breakdown.append({
                "shop_id": sh["id"],
                "shop_name": sh.get("name", "—"),
                "fee_usd": round(fee, 2),
                "mode": mode,
            })

    total = round(subtotal + delivery_fee, 2)
    order = {
        "id": str(uuid.uuid4()),
        "customer_id": user["id"],
        "customer_name": user["name"],
        "customer_email": user["email"],
        "items": [it.model_dump() for it in body.items],
        "subtotal_usd": round(subtotal, 2),
        "delivery_fee_usd": round(delivery_fee, 2),
        "delivery_breakdown": delivery_breakdown,
        "total_usd": total,
        "area": body.area, "address": body.address, "phone": body.phone,
        "note": body.note, "order_kind": body.order_kind,
        "status": "Pending", "created_at": now_iso(),
    }
    await db.orders.insert_one(order)
    order.pop("_id", None)

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
    return await db.orders.find({"customer_id": user["id"]}, {"_id": 0}).sort("created_at", -1).skip(off).to_list(lim)


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
    return await db.orders.find({"items.item_id": {"$in": list(ids)}}, {"_id": 0}).sort("created_at", -1).skip(off).to_list(lim)


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
# Favorites (customer)
# ----------------------------------------------------------------------------
@api.get("/favorites")
async def list_favorites(
    user: dict = Depends(get_current_user),
    limit: Optional[int] = None,
    skip: Optional[int] = None,
):
    lim, off = clamp_pagination(limit, skip)
    return await db.favorites.find({"user_id": user["id"]}, {"_id": 0}).skip(off).to_list(lim)


@api.post("/favorites")
async def add_favorite(body: FavoriteIn, user: dict = Depends(get_current_user)):
    existing = await db.favorites.find_one({
        "user_id": user["id"], "target_type": body.target_type, "target_id": body.target_id,
    })
    if existing:
        return {"ok": True, "already": True}
    await db.favorites.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "target_type": body.target_type,
        "target_id": body.target_id,
        "created_at": now_iso(),
    })
    return {"ok": True}


@api.delete("/favorites")
async def remove_favorite(target_type: str, target_id: str, user: dict = Depends(get_current_user)):
    await db.favorites.delete_one({
        "user_id": user["id"], "target_type": target_type, "target_id": target_id,
    })
    return {"ok": True}


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
async def add_review(product_id: str, body: ReviewIn, user: dict = Depends(get_current_user)):
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
        "created_at": now_iso(),
    }
    await db.reviews.insert_one(review)
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
    return {"ok": True}


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
    delivery_fee = 0.0
    breakdown = []
    if shop_ids_in_order and body.area:
        shops = await db.shops.find({"id": {"$in": shop_ids_in_order}}, {"_id": 0}).to_list(500)
        for sh in shops:
            mode = sh.get("delivery_mode", "free")
            fee = 0.0
            if mode == "fixed":
                fee = float(sh.get("delivery_fee_usd") or 0)
            elif mode == "per_area":
                for entry in sh.get("delivery_per_area", []) or []:
                    if (entry.get("area") or "").lower() == body.area.lower():
                        fee = float(entry.get("fee_usd") or 0)
                        break
            delivery_fee += fee
            breakdown.append({
                "shop_id": sh["id"],
                "shop_name": sh.get("name", "—"),
                "fee_usd": round(fee, 2),
                "mode": mode,
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
    total_revenue = sum(float(o.get("total_usd") or o.get("subtotal_usd") or 0) for o in orders)
    pending_orders = sum(1 for o in orders if o.get("status") == "Pending")
    delivered_orders = sum(1 for o in orders if o.get("status") == "Delivered")

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
    return await get_settings()


@api.post("/admin/areas")
async def admin_add_area(body: AreaIn, _: dict = Depends(require_role("admin"))):
    s = await get_settings()
    areas = list(s.get("areas", DEFAULT_AREAS))
    if body.area in areas:
        raise HTTPException(400, "Area already exists")
    areas.append(body.area)
    await db.settings.update_one({"id": "system"}, {"$set": {"areas": areas}}, upsert=True)
    return {"areas": areas}


@api.delete("/admin/areas")
async def admin_delete_area(area: str, _: dict = Depends(require_role("admin"))):
    s = await get_settings()
    areas = [a for a in s.get("areas", DEFAULT_AREAS) if a != area]
    await db.settings.update_one({"id": "system"}, {"$set": {"areas": areas}}, upsert=True)
    return {"areas": areas}


@api.post("/admin/force-logout-all")
async def admin_force_logout(_: dict = Depends(require_role("admin"))):
    s = await get_settings()
    new_tv = int(s.get("token_version", 1)) + 1
    await db.settings.update_one({"id": "system"}, {"$set": {"token_version": new_tv}}, upsert=True)
    return {"ok": True, "token_version": new_tv}


@api.put("/admin/shops/{shop_id}/verify")
async def admin_verify(shop_id: str, _: dict = Depends(require_role("admin"))):
    await db.shops.update_one({"id": shop_id}, {"$set": {"verification": "Verified"}})
    return await db.shops.find_one({"id": shop_id}, {"_id": 0})


@api.put("/admin/shops/{shop_id}/reject")
async def admin_reject(shop_id: str, _: dict = Depends(require_role("admin"))):
    await db.shops.update_one({"id": shop_id}, {"$set": {"verification": "Rejected"}})
    return await db.shops.find_one({"id": shop_id}, {"_id": 0})


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
# Seeding (production: only settings + a single admin account)
# ----------------------------------------------------------------------------
async def seed_production():
    """Create essential indexes + seed a single admin account from env.
    Idempotent: safe to call on every startup."""
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.shops.create_index("id", unique=True)
    await db.products.create_index("id", unique=True)
    await db.restaurants.create_index("id", unique=True)
    await db.menu_items.create_index("id", unique=True)
    await db.orders.create_index("id", unique=True)
    await db.blocked_emails.create_index("email", unique=True)
    await db.favorites.create_index([("user_id", 1), ("target_type", 1), ("target_id", 1)])
    await db.invoices.create_index("id", unique=True)
    await db.reviews.create_index([("product_id", 1)])
    await db.reviews.create_index("id", unique=True)
    await db.notifications.create_index("id", unique=True)
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.email_verifications.create_index("token", unique=True)
    await db.email_verifications.create_index("user_id")
    await db.password_resets.create_index("token", unique=True)
    await db.password_resets.create_index("user_id")

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
    if not admin_email or not admin_password:
        log.warning("ADMIN_EMAIL / ADMIN_PASSWORD not set — no admin account will be seeded.")
        return

    existing = await db.users.find_one({"email": admin_email})
    if existing:
        # Make sure existing admin account stays an admin + is flagged verified,
        # but never overwrite the password after first seed.
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"role": "admin", "email_verified": True}},
        )
    else:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "name": "Admin",
            "role": "admin",
            "phone": "",
            "settings": {},
            "email_verified": True,
            "password_hash": hash_password(admin_password),
            "created_at": now_iso(),
        })
        log.info(f"✅ Seeded admin account: {admin_email}")


@app.on_event("startup")
async def on_startup():
    await seed_production()


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


# Serve uploaded images under /api/uploads so they go through the Kubernetes
# ingress /api prefix and hit the backend (non-/api paths are routed to frontend).
app.mount("/api/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
)
