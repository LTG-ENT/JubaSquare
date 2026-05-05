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
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr


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
# Models
# ----------------------------------------------------------------------------
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ChangePwIn(BaseModel):
    current_password: str
    new_password: str


class ProfileIn(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


class ShopIn(BaseModel):
    name: str
    category: str
    description: Optional[str] = ""
    image_url: Optional[str] = ""
    area: str
    kind: Literal["retail", "wholesale"] = "retail"


class ProductIn(BaseModel):
    shop_id: str
    name: str
    category: str
    price_usd: float
    image_url: Optional[str] = ""
    description: Optional[str] = ""
    stock: int = 100
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
    status: Literal["Paid", "Unpaid"]


class AreaIn(BaseModel):
    area: str


class SellerSettingsIn(BaseModel):
    low_stock_alert: Optional[bool] = None
    low_stock_threshold: Optional[int] = None
    auto_hide_out_of_stock: Optional[bool] = None
    order_notifications: Optional[bool] = None


class CustomerSettingsIn(BaseModel):
    default_area: Optional[str] = None
    order_notifications: Optional[bool] = None
    promotion_notifications: Optional[bool] = None
    dark_mode: Optional[bool] = None


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


@api.get("/meta/categories")
async def get_categories():
    return {
        "retail": [
            "Groceries",
            "Clothing & Fashion",
            "Shoes & Bags",
            "Beauty & Cosmetics",
            "Electronics & Accessories",
            "Home Essentials",
            "Health & Pharmacy",
            "Building & Materials",
            "Automotive",
        ],
        "wholesale": [
            "Wholesale Food Supply",
            "Wholesale Electronics",
            "Wholesale Clothing",
            "Restaurant Supplies",
            "Construction Materials",
            "General Bulk Goods",
        ],
        "restaurant": ["Fast Food", "Local Food", "Drinks", "Bakery"],
        "food_subcategories": [
            "Fried Chicken",
            "Burgers",
            "Shawarma",
            "Fries",
            "Sandwiches",
            "Kisra & Stews",
            "Asida",
            "Goat Meat Dishes",
            "Fish Dishes",
            "Pizza & Pasta",
            "Rice Meals",
            "Drinks & Cafés",
            "Cakes & Desserts",
            "Grills & BBQ",
            "Asian Food",
            "Healthy Food",
        ],
    }


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
async def list_shops(category: Optional[str] = None, area: Optional[str] = None, kind: Optional[str] = None):
    q: dict = {}
    if category:
        q["category"] = category
    if area:
        q["area"] = area
    if kind:
        q["kind"] = kind
    shops = await db.shops.find(q, {"_id": 0}).to_list(500)
    s = await get_settings()
    return _sort_shops(shops, s.get("verified_first", True))


@api.get("/shops/mine")
async def my_shops(user: dict = Depends(require_role("seller", "admin"))):
    return await db.shops.find({"seller_id": user["id"]}, {"_id": 0}).to_list(500)


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
# Products
# ----------------------------------------------------------------------------
@api.get("/products")
async def list_products(category: Optional[str] = None, area: Optional[str] = None,
                        shop_id: Optional[str] = None, kind: Optional[str] = None):
    q: dict = {}
    if category:
        q["category"] = category
    if shop_id:
        q["shop_id"] = shop_id
    products = await db.products.find(q, {"_id": 0}).to_list(2000)

    if area or kind:
        shop_q = {}
        if area:
            shop_q["area"] = area
        if kind:
            shop_q["kind"] = kind
        shop_ids = {s["id"] for s in await db.shops.find(shop_q, {"_id": 0, "id": 1}).to_list(500)}
        products = [p for p in products if p["shop_id"] in shop_ids]

    # Auto-hide out-of-stock per seller setting
    seller_ids = list({p["seller_id"] for p in products})
    sellers = await db.users.find({"id": {"$in": seller_ids}}, {"_id": 0, "id": 1, "settings": 1}).to_list(500)
    auto_hide = {u["id"]: bool((u.get("settings") or {}).get("auto_hide_out_of_stock")) for u in sellers}
    products = [p for p in products if not (auto_hide.get(p["seller_id"]) and p.get("stock", 0) <= 0)]
    return products


@api.get("/products/{product_id}")
async def get_product(product_id: str):
    p = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Product not found")
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
async def list_restaurants(area: Optional[str] = None, category: Optional[str] = None):
    q: dict = {}
    if area:
        q["area"] = area
    if category:
        q["category"] = category
    return await db.restaurants.find(q, {"_id": 0}).to_list(500)


@api.get("/restaurants/{restaurant_id}")
async def get_restaurant(restaurant_id: str):
    r = await db.restaurants.find_one({"id": restaurant_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Restaurant not found")
    return r


@api.get("/restaurants/{restaurant_id}/menu")
async def get_menu(restaurant_id: str):
    return await db.menu_items.find({"restaurant_id": restaurant_id}, {"_id": 0}).to_list(500)


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
    order = {
        "id": str(uuid.uuid4()),
        "customer_id": user["id"],
        "customer_name": user["name"],
        "customer_email": user["email"],
        "items": [it.model_dump() for it in body.items],
        "subtotal_usd": round(subtotal, 2),
        "area": body.area, "address": body.address, "phone": body.phone,
        "note": body.note, "order_kind": body.order_kind,
        "status": "Pending", "created_at": now_iso(),
    }
    await db.orders.insert_one(order)
    order.pop("_id", None)
    return order


@api.get("/orders/mine")
async def my_orders(user: dict = Depends(get_current_user)):
    return await db.orders.find({"customer_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.get("/orders/seller")
async def seller_orders(user: dict = Depends(require_role("seller", "admin"))):
    seller_products = await db.products.find({"seller_id": user["id"]}, {"_id": 0, "id": 1}).to_list(2000)
    seller_menu = await db.menu_items.find({"seller_id": user["id"]}, {"_id": 0, "id": 1}).to_list(2000)
    ids = {p["id"] for p in seller_products} | {m["id"] for m in seller_menu}
    if not ids:
        return []
    return await db.orders.find({"items.item_id": {"$in": list(ids)}}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.get("/orders")
async def all_orders(_: dict = Depends(require_role("admin"))):
    return await db.orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api.put("/orders/{order_id}/status")
async def update_status(order_id: str, body: StatusIn, _: dict = Depends(require_role("seller", "admin"))):
    o = await db.orders.find_one({"id": order_id})
    if not o:
        raise HTTPException(404, "Order not found")
    await db.orders.update_one({"id": order_id}, {"$set": {"status": body.status}})
    return await db.orders.find_one({"id": order_id}, {"_id": 0})


# ----------------------------------------------------------------------------
# Favorites (customer)
# ----------------------------------------------------------------------------
@api.get("/favorites")
async def list_favorites(user: dict = Depends(get_current_user)):
    return await db.favorites.find({"user_id": user["id"]}, {"_id": 0}).to_list(500)


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
# Admin: settings, areas, shops, emails, force-logout
# ----------------------------------------------------------------------------
@api.get("/admin/settings")
async def admin_get_settings(_: dict = Depends(require_role("admin"))):
    return await get_settings()


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


@api.delete("/admin/areas/{area}")
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


@api.get("/admin/blocked-emails")
async def list_blocked(_: dict = Depends(require_role("admin"))):
    return await db.blocked_emails.find({}, {"_id": 0}).to_list(500)


@api.post("/admin/block-email")
async def block_email(body: BlockEmailIn, _: dict = Depends(require_role("admin"))):
    email = body.email.lower()
    if email in {"admin@demo.com", "seller@demo.com", "customer@demo.com"}:
        raise HTTPException(400, "Cannot block demo accounts")
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
async def set_rate(body: ExchangeRateIn, user: dict = Depends(require_role("seller", "admin"))):
    if user["role"] == "admin":
        await db.settings.update_one({"id": "system"}, {"$set": {"global_rate": float(body.rate)}}, upsert=True)
        return {"seller_id": "__global__", "rate": body.rate}
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
    """Regenerate invoices from all orders. One invoice per (seller, shop, week)."""
    settings = await get_settings()
    rate = float(settings.get("commission_rate", 0.10))

    # Map item_id -> (seller_id, shop_id, shop_name)
    products = await db.products.find({}, {"_id": 0}).to_list(5000)
    menu_items = await db.menu_items.find({}, {"_id": 0}).to_list(5000)
    restaurants = await db.restaurants.find({}, {"_id": 0}).to_list(500)
    shops = await db.shops.find({}, {"_id": 0}).to_list(500)
    shop_by_id = {s["id"]: s for s in shops}
    rest_by_id = {r["id"]: r for r in restaurants}

    lookup = {}
    for p in products:
        shop = shop_by_id.get(p["shop_id"], {})
        lookup[p["id"]] = {"seller_id": p["seller_id"], "shop_id": p["shop_id"], "shop_name": shop.get("name", "—")}
    for m in menu_items:
        rest = rest_by_id.get(m["restaurant_id"], {})
        lookup[m["id"]] = {"seller_id": m["seller_id"], "shop_id": m["restaurant_id"], "shop_name": rest.get("name", "—")}

    orders = await db.orders.find({}, {"_id": 0}).to_list(5000)
    buckets: dict = {}  # (seller_id, shop_id, week_start) -> accumulator
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

    # Preserve existing paid/unpaid status
    existing = {
        (inv["seller_id"], inv["shop_id"], inv["week_start"]): inv
        for inv in await db.invoices.find({}, {"_id": 0}).to_list(5000)
    }

    await db.invoices.delete_many({})
    now = now_iso()
    for (seller_id, shop_id, ws), b in buckets.items():
        commission = round(b["total_sales"] * rate, 2)
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
            "commission_rate": rate,
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
    await db.invoices.update_one({"id": invoice_id}, {"$set": {"status": body.status, "updated_at": now_iso()}})
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
# Seeding
# ----------------------------------------------------------------------------
DEMO_USERS = [
    {"email": "admin@demo.com", "password": "1234", "name": "Demo Admin", "role": "admin"},
    {"email": "seller@demo.com", "password": "1234", "name": "Demo Seller", "role": "seller"},
    {"email": "customer@demo.com", "password": "1234", "name": "Demo Customer", "role": "customer"},
]

# 9 retail + 3 wholesale shops
RETAIL_SHOP_SEEDS = [
    {
        "name": "Juba Fresh Market", "category": "Groceries", "area": "Munuki",
        "description": "Daily groceries, fresh produce and household staples.",
        "image_url": "https://images.unsplash.com/photo-1542838132-92c53300491e?w=800&q=80",
        "verification": "Verified",
        "products": [
            {"name": "Basmati Rice 5kg", "price_usd": 14.0, "image_url": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=800&q=80", "description": "Premium long-grain basmati rice."},
            {"name": "Cooking Oil 5L", "price_usd": 18.5, "image_url": "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=800&q=80", "description": "Refined sunflower cooking oil."},
        ],
    },
    {
        "name": "Nile Fashion House", "category": "Clothing & Fashion", "area": "Atlabara",
        "description": "Trendy clothing for men and women.",
        "image_url": "https://images.unsplash.com/photo-1757140447782-8503452b2204?w=800&q=80",
        "verification": "Verified",
        "products": [
            {"name": "Premium Cotton T-Shirt", "price_usd": 18.0, "image_url": "https://images.unsplash.com/photo-1581655353564-df123a1eb820?w=800&q=80", "description": "100% cotton, multiple colors."},
            {"name": "Slim Fit Jeans", "price_usd": 42.0, "image_url": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=800&q=80", "description": "Classic blue stretch denim."},
        ],
    },
    {
        "name": "Step Up Shoes & Bags", "category": "Shoes & Bags", "area": "Hai Cinema",
        "description": "Footwear and bags for every occasion.",
        "image_url": "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=800&q=80",
        "verification": "Verified",
        "products": [
            {"name": "Running Sneakers", "price_usd": 65.0, "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&q=80", "description": "Lightweight, breathable running shoes."},
            {"name": "Leather Tote Bag", "price_usd": 49.0, "image_url": "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=800&q=80", "description": "Genuine leather tote, spacious interior."},
        ],
    },
    {
        "name": "Glow Beauty Hub", "category": "Beauty & Cosmetics", "area": "Nyakuron",
        "description": "Skincare, makeup and personal care.",
        "image_url": "https://images.unsplash.com/photo-1522335789203-aaa57d0aacae?w=800&q=80",
        "verification": "Verified",
        "products": [
            {"name": "Hydrating Face Cream", "price_usd": 22.0, "image_url": "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=800&q=80", "description": "Daily moisturizer for all skin types."},
            {"name": "Lipstick Set (3-pack)", "price_usd": 16.0, "image_url": "https://images.unsplash.com/photo-1586495777744-4413f21062fa?w=800&q=80", "description": "Long-lasting matte lipsticks."},
        ],
    },
    {
        "name": "Juba Tech Hub", "category": "Electronics & Accessories", "area": "Munuki",
        "description": "Latest electronics, mobile phones and accessories.",
        "image_url": "https://images.unsplash.com/photo-1761641466573-f240b6e446de?w=800&q=80",
        "verification": "Verified",
        "products": [
            {"name": "Samsung Galaxy A55", "price_usd": 380.0, "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=800&q=80", "description": "6.5\" AMOLED, 128GB smartphone."},
            {"name": "Wireless Headphones", "price_usd": 65.0, "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800&q=80", "description": "Over-ear bluetooth, 40h battery."},
        ],
    },
    {
        "name": "Equatoria Home Essentials", "category": "Home Essentials", "area": "Gudele",
        "description": "Furniture, kitchenware and home goods.",
        "image_url": "https://images.pexels.com/photos/15108276/pexels-photo-15108276.jpeg?auto=compress&w=940",
        "verification": "Verified",
        "products": [
            {"name": "Wooden Dining Chair", "price_usd": 55.0, "image_url": "https://images.unsplash.com/photo-1503602642458-232111445657?w=800&q=80", "description": "Solid mahogany dining chair."},
            {"name": "Premium Kitchen Set", "price_usd": 89.0, "image_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&q=80", "description": "12-piece non-stick cookware set."},
        ],
    },
    {
        "name": "Juba Pharmacy Plus", "category": "Health & Pharmacy", "area": "Hai Cinema",
        "description": "Trusted medicines and health products.",
        "image_url": "https://images.unsplash.com/photo-1646392206581-2527b1cae5cb?w=800&q=80",
        "verification": "Verified",
        "products": [
            {"name": "Paracetamol 500mg (Pack of 20)", "price_usd": 4.5, "image_url": "https://images.unsplash.com/photo-1587854692152-cbe660dbde88?w=800&q=80", "description": "Pain & fever relief tablets."},
            {"name": "Multivitamin Bottle (60 caps)", "price_usd": 12.0, "image_url": "https://images.unsplash.com/photo-1550572017-edd951b55104?w=800&q=80", "description": "Daily multivitamins for adults."},
        ],
    },
    {
        "name": "Build Mart", "category": "Building & Materials", "area": "Jebel",
        "description": "Cement, steel, paint, plumbing and electrical supplies.",
        "image_url": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=800&q=80",
        "verification": "Verified",
        "products": [
            {"name": "Cement Bag 50kg", "price_usd": 12.0, "image_url": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=800&q=80", "description": "OPC grade 42.5N cement."},
            {"name": "Premium White Paint 20L", "price_usd": 58.0, "image_url": "https://images.unsplash.com/photo-1562259949-e8e7689d7828?w=800&q=80", "description": "Interior emulsion, washable finish."},
        ],
    },
    {
        "name": "Sahel Auto Parts", "category": "Automotive", "area": "Jebel",
        "description": "Quality car parts and accessories.",
        "image_url": "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?w=800&q=80",
        "verification": "Pending",
        "products": [
            {"name": "Heavy-Duty Car Battery", "price_usd": 145.0, "image_url": "https://images.unsplash.com/photo-1632823469847-2c40beb9e6ec?w=800&q=80", "description": "12V 70Ah maintenance-free battery."},
            {"name": "All-Season Tire (Set of 4)", "price_usd": 320.0, "image_url": "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?w=800&q=80", "description": "R15 all-season tires, durable tread."},
        ],
    },
]

WHOLESALE_SHOP_SEEDS = [
    {
        "name": "Bulk Foods SS", "category": "Wholesale Food Supply", "area": "Konyo Konyo",
        "description": "Bulk groceries and food supply for retailers.",
        "image_url": "https://images.unsplash.com/photo-1542838132-92c53300491e?w=800&q=80",
        "verification": "Verified",
        "products": [
            {"name": "Sugar 50kg Bag", "price_usd": 55.0, "bulk_price_usd": 48.0, "min_order_qty": 5, "image_url": "https://images.unsplash.com/photo-1610736703229-30bbcd1a2b96?w=800&q=80", "description": "Refined white sugar, food-grade."},
            {"name": "Wheat Flour 50kg", "price_usd": 42.0, "bulk_price_usd": 36.0, "min_order_qty": 10, "image_url": "https://images.unsplash.com/photo-1600326145552-327c4df2c246?w=800&q=80", "description": "All-purpose wheat flour."},
        ],
    },
    {
        "name": "Mega Electronics WSL", "category": "Wholesale Electronics", "area": "Munuki",
        "description": "Wholesale supplier of consumer electronics.",
        "image_url": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&q=80",
        "verification": "Verified",
        "products": [
            {"name": "Smartphone Box (10 pcs)", "price_usd": 2800.0, "bulk_price_usd": 2500.0, "min_order_qty": 1, "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=800&q=80", "description": "Mid-range smartphones, retailer pack."},
            {"name": "USB Cable Carton (100 pcs)", "price_usd": 180.0, "bulk_price_usd": 150.0, "min_order_qty": 2, "image_url": "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?w=800&q=80", "description": "USB-C charging cables, 1m."},
        ],
    },
    {
        "name": "Builders Supply Co", "category": "Construction Materials", "area": "Jebel",
        "description": "Construction-grade materials at wholesale rates.",
        "image_url": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=800&q=80",
        "verification": "Pending",
        "products": [
            {"name": "Cement Pallet (40 bags)", "price_usd": 480.0, "bulk_price_usd": 420.0, "min_order_qty": 1, "image_url": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=800&q=80", "description": "OPC 42.5N, full pallet."},
            {"name": "Steel Rod Bundle (100 pcs)", "price_usd": 1200.0, "bulk_price_usd": 1080.0, "min_order_qty": 1, "image_url": "https://images.unsplash.com/photo-1565728744382-61accd4aa148?w=800&q=80", "description": "12mm reinforcing steel rods."},
        ],
    },
]

RESTAURANT_SEEDS = [
    {
        "name": "Juba Burger Joint", "category": "Fast Food", "area": "Konyo Konyo", "is_open": True,
        "verification": "Verified", "description": "Juicy burgers and crispy fries.",
        "image_url": "https://images.unsplash.com/photo-1571091718767-18b5b1457add?w=800&q=80",
        "menu": [
            {"name": "Classic Beef Burger", "price_usd": 8.5, "image_url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=800&q=80",
             "description": "Beef patty, cheese, lettuce, special sauce.",
             "side_items": [{"name": "Fries", "price_usd": 2.0}, {"name": "Coke", "price_usd": 1.5}, {"name": "BBQ Sauce", "price_usd": 0.5}]},
            {"name": "Crispy French Fries", "price_usd": 3.5, "image_url": "https://images.unsplash.com/photo-1576107232684-1279f390859f?w=800&q=80",
             "description": "Golden hand-cut fries with sea salt.",
             "side_items": [{"name": "Ketchup", "price_usd": 0.5}, {"name": "Mayo", "price_usd": 0.5}]},
        ],
    },
    {
        "name": "Mama Africa Kitchen", "category": "Local Food", "area": "Nyakuron", "is_open": True,
        "verification": "Verified", "description": "Authentic South Sudanese home cooking.",
        "image_url": "https://images.unsplash.com/photo-1726177975126-0053e054bc1a?w=800&q=80",
        "menu": [
            {"name": "Rice & Grilled Chicken", "price_usd": 7.0, "image_url": "https://images.unsplash.com/photo-1604908176997-125f25cc6f3d?w=800&q=80",
             "description": "Spiced jasmine rice with grilled chicken.",
             "side_items": [{"name": "Salad", "price_usd": 1.5}, {"name": "Soda", "price_usd": 1.0}]},
            {"name": "Stewed Beans Plate", "price_usd": 5.0, "image_url": "https://images.unsplash.com/photo-1543339308-43e59d6b73a6?w=800&q=80",
             "description": "Slow-cooked beans with onions & spices.",
             "side_items": [{"name": "Bread Roll", "price_usd": 0.5}]},
        ],
    },
    {
        "name": "Cool Sips Drinks", "category": "Drinks", "area": "Munuki", "is_open": True,
        "verification": "Verified", "description": "Refreshing juices, smoothies and sodas.",
        "image_url": "https://images.unsplash.com/photo-1622597467836-f3285f2131b8?w=800&q=80",
        "menu": [
            {"name": "Fresh Mango Juice", "price_usd": 3.0, "image_url": "https://images.unsplash.com/photo-1546173159-315724a31696?w=800&q=80",
             "description": "100% fresh mango, no added sugar.", "side_items": []},
            {"name": "Cold Soda 500ml", "price_usd": 1.5, "image_url": "https://images.unsplash.com/photo-1581636625402-29b2a704ef13?w=800&q=80",
             "description": "Chilled bottled soda.", "side_items": []},
        ],
    },
    {
        "name": "Nile Bakery", "category": "Bakery", "area": "Atlabara", "is_open": False,
        "verification": "Verified", "description": "Fresh bread and cakes baked daily.",
        "image_url": "https://images.unsplash.com/photo-1628690570377-a8d5bd19768c?w=800&q=80",
        "menu": [
            {"name": "Fresh Sourdough Loaf", "price_usd": 4.0, "image_url": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=800&q=80",
             "description": "Crusty sourdough, baked this morning.", "side_items": []},
            {"name": "Chocolate Celebration Cake", "price_usd": 22.0, "image_url": "https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=800&q=80",
             "description": "Rich chocolate layered cake — serves 8.", "side_items": []},
        ],
    },
]


async def seed_demo():
    await db.users.create_index("email", unique=True)
    await db.shops.create_index("id", unique=True)
    await db.products.create_index("id", unique=True)
    await db.restaurants.create_index("id", unique=True)
    await db.menu_items.create_index("id", unique=True)
    await db.orders.create_index("id", unique=True)
    await db.blocked_emails.create_index("email", unique=True)
    await db.favorites.create_index([("user_id", 1), ("target_type", 1), ("target_id", 1)])
    await db.invoices.create_index("id", unique=True)

    # Settings
    existing_s = await db.settings.find_one({"id": "system"})
    if not existing_s:
        await db.settings.insert_one(DEFAULT_SETTINGS.copy())

    # Users
    user_ids: dict = {}
    for u in DEMO_USERS:
        existing = await db.users.find_one({"email": u["email"]})
        if existing:
            await db.users.update_one(
                {"email": u["email"]},
                {"$set": {"password_hash": hash_password(u["password"]), "name": u["name"], "role": u["role"]}},
            )
            user_ids[u["role"]] = existing["id"]
        else:
            uid = str(uuid.uuid4())
            await db.users.insert_one({
                "id": uid, "email": u["email"], "name": u["name"], "role": u["role"],
                "phone": "", "settings": {},
                "password_hash": hash_password(u["password"]), "created_at": now_iso(),
            })
            user_ids[u["role"]] = uid

    seller_id = user_ids["seller"]

    def _seed_shops(shop_list, kind):
        return shop_list, kind

    async def _insert_shop_set(shop_list, kind):
        for s in shop_list:
            existing = await db.shops.find_one({"name": s["name"]})
            if existing:
                continue
            shop_id = str(uuid.uuid4())
            await db.shops.insert_one({
                "id": shop_id, "seller_id": seller_id,
                "name": s["name"], "category": s["category"], "description": s["description"],
                "area": s["area"], "image_url": s["image_url"],
                "verification": s.get("verification", "Pending"),
                "kind": kind, "created_at": now_iso(),
            })
            for p in s["products"]:
                await db.products.insert_one({
                    "id": str(uuid.uuid4()), "shop_id": shop_id, "seller_id": seller_id,
                    "shop_kind": kind, "name": p["name"], "category": s["category"],
                    "price_usd": p["price_usd"],
                    "bulk_price_usd": p.get("bulk_price_usd"),
                    "min_order_qty": p.get("min_order_qty", 1),
                    "image_url": p["image_url"], "description": p["description"],
                    "stock": 100, "created_at": now_iso(),
                })

    await _insert_shop_set(RETAIL_SHOP_SEEDS, "retail")
    await _insert_shop_set(WHOLESALE_SHOP_SEEDS, "wholesale")

    for r in RESTAURANT_SEEDS:
        existing = await db.restaurants.find_one({"name": r["name"]})
        if existing:
            continue
        rid = str(uuid.uuid4())
        await db.restaurants.insert_one({
            "id": rid, "seller_id": seller_id,
            "name": r["name"], "category": r["category"], "description": r["description"],
            "area": r["area"], "is_open": r["is_open"], "image_url": r["image_url"],
            "verification": r.get("verification", "Verified"), "created_at": now_iso(),
        })
        for m in r["menu"]:
            await db.menu_items.insert_one({
                "id": str(uuid.uuid4()), "restaurant_id": rid, "seller_id": seller_id,
                "name": m["name"], "price_usd": m["price_usd"], "image_url": m["image_url"],
                "description": m["description"], "side_items": m.get("side_items", []),
                "created_at": now_iso(),
            })

    existing_rate = await db.exchange_rates.find_one({"seller_id": seller_id})
    if not existing_rate:
        await db.exchange_rates.insert_one({"seller_id": seller_id, "rate": 600.0, "updated_at": now_iso()})

    # Sample order
    customer_id = user_ids["customer"]
    if await db.orders.count_documents({}) == 0:
        # Create a few orders spread across the last 3 weeks so invoices look realistic
        sample_products = await db.products.find({"mode": {"$ne": "wholesale"}} if False else {}, {"_id": 0}).to_list(20)
        now = datetime.now(timezone.utc)
        seed_orders = [
            (sample_products[0] if sample_products else None, 1, "Delivered", now - timedelta(days=14)),
            (sample_products[1] if len(sample_products) > 1 else None, 2, "Delivered", now - timedelta(days=13)),
            (sample_products[2] if len(sample_products) > 2 else None, 1, "Delivered", now - timedelta(days=8)),
            (sample_products[3] if len(sample_products) > 3 else None, 3, "Delivered", now - timedelta(days=6)),
            (sample_products[4] if len(sample_products) > 4 else None, 1, "In Progress", now - timedelta(days=2)),
            (sample_products[5] if len(sample_products) > 5 else None, 2, "Pending", now - timedelta(days=1)),
        ]
        for prod, qty, status, when in seed_orders:
            if not prod:
                continue
            await db.orders.insert_one({
                "id": str(uuid.uuid4()), "customer_id": customer_id,
                "customer_name": "Demo Customer", "customer_email": "customer@demo.com",
                "items": [{"item_type": "product", "item_id": prod["id"], "name": prod["name"],
                           "price_usd": prod["price_usd"], "quantity": qty,
                           "image_url": prod["image_url"], "sides": []}],
                "subtotal_usd": round(prod["price_usd"] * qty, 2),
                "area": "Munuki", "address": "Block 4, Munuki", "phone": "+211 9XX XXX XXX",
                "note": "", "order_kind": "marketplace", "status": status,
                "created_at": when.isoformat(),
            })

    # Regenerate invoices from seeded orders. Mark the oldest as Paid for demo realism.
    if await db.invoices.count_documents({}) == 0:
        await _rebuild_invoices()
        invs = await db.invoices.find({}, {"_id": 0}).sort("week_start", 1).to_list(100)
        # Mark first third as Paid
        paid_cutoff = max(1, len(invs) // 3)
        for i in invs[:paid_cutoff]:
            await db.invoices.update_one({"id": i["id"]}, {"$set": {"status": "Paid"}})

    log.info("✅ JubaSquare demo data seeded successfully (retail + wholesale + restaurants + invoices)")


@app.on_event("startup")
async def on_startup():
    await seed_demo()


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
)
