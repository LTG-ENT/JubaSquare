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


def create_token(user_id: str, role: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "email": email,
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


class ProductIn(BaseModel):
    shop_id: str
    name: str
    category: str
    price_usd: float
    image_url: Optional[str] = ""
    description: Optional[str] = ""
    stock: int = 100


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


class OrderItemIn(BaseModel):
    item_type: Literal["product", "menu_item"]
    item_id: str
    name: str
    price_usd: float
    quantity: int
    image_url: Optional[str] = ""


class OrderIn(BaseModel):
    items: List[OrderItemIn]
    area: str
    address: Optional[str] = ""
    phone: Optional[str] = ""
    note: Optional[str] = ""
    order_kind: Literal["marketplace", "restaurant"] = "marketplace"


class StatusIn(BaseModel):
    status: Literal["Pending", "In Progress", "Delivered"]


class BlockEmailIn(BaseModel):
    email: EmailStr


class ExchangeRateIn(BaseModel):
    rate: float  # SSP per 1 USD


# ----------------------------------------------------------------------------
# Auth endpoints
# ----------------------------------------------------------------------------
@api.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    email = payload.email.lower()
    blocked = await db.blocked_emails.find_one({"email": email})
    if blocked:
        raise HTTPException(status_code=403, detail="This email has been blocked by admin")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(user["id"], user["role"], user["email"])
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=ACCESS_TOKEN_DAYS * 24 * 3600,
        path="/",
    )
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "phone": user.get("phone", ""),
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


# ----------------------------------------------------------------------------
# Shops
# ----------------------------------------------------------------------------
@api.get("/shops")
async def list_shops(category: Optional[str] = None, area: Optional[str] = None):
    q: dict = {}
    if category:
        q["category"] = category
    if area:
        q["area"] = area
    shops = await db.shops.find(q, {"_id": 0}).to_list(500)
    # sort: verified first, then pending, then rejected
    order = {"Verified": 0, "Pending": 1, "Rejected": 2}
    shops.sort(key=lambda s: order.get(s.get("verification", "Pending"), 1))
    return shops


@api.get("/shops/mine")
async def my_shops(user: dict = Depends(require_role("seller", "admin"))):
    shops = await db.shops.find({"seller_id": user["id"]}, {"_id": 0}).to_list(500)
    return shops


@api.get("/shops/{shop_id}")
async def get_shop(shop_id: str):
    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0})
    if not shop:
        raise HTTPException(404, "Shop not found")
    return shop


@api.post("/shops")
async def create_shop(body: ShopIn, user: dict = Depends(require_role("seller", "admin"))):
    shop = {
        "id": str(uuid.uuid4()),
        "seller_id": user["id"],
        "verification": "Pending",
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
    updated = await db.shops.find_one({"id": shop_id}, {"_id": 0})
    return updated


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
async def list_products(category: Optional[str] = None, area: Optional[str] = None, shop_id: Optional[str] = None):
    q: dict = {}
    if category:
        q["category"] = category
    if shop_id:
        q["shop_id"] = shop_id
    products = await db.products.find(q, {"_id": 0}).to_list(1000)
    # filter by area via shop
    if area:
        shop_ids = {s["id"] for s in await db.shops.find({"area": area}, {"_id": 0, "id": 1}).to_list(500)}
        products = [p for p in products if p["shop_id"] in shop_ids]
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
    updated = await db.products.find_one({"id": product_id}, {"_id": 0})
    return updated


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
    r = {
        "id": str(uuid.uuid4()),
        "seller_id": user["id"],
        "verification": "Pending",
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
    updated = await db.menu_items.find_one({"id": item_id}, {"_id": 0})
    return updated


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
    subtotal = sum(it.price_usd * it.quantity for it in body.items)
    order = {
        "id": str(uuid.uuid4()),
        "customer_id": user["id"],
        "customer_name": user["name"],
        "customer_email": user["email"],
        "items": [it.model_dump() for it in body.items],
        "subtotal_usd": round(subtotal, 2),
        "area": body.area,
        "address": body.address,
        "phone": body.phone,
        "note": body.note,
        "order_kind": body.order_kind,
        "status": "Pending",
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order)
    order.pop("_id", None)
    return order


@api.get("/orders/mine")
async def my_orders(user: dict = Depends(get_current_user)):
    return await db.orders.find({"customer_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.get("/orders/seller")
async def seller_orders(user: dict = Depends(require_role("seller", "admin"))):
    # Find orders that contain items from any of seller's products / menu items
    seller_products = await db.products.find({"seller_id": user["id"]}, {"_id": 0, "id": 1}).to_list(1000)
    seller_menu = await db.menu_items.find({"seller_id": user["id"]}, {"_id": 0, "id": 1}).to_list(1000)
    ids = {p["id"] for p in seller_products} | {m["id"] for m in seller_menu}
    if not ids:
        return []
    orders = await db.orders.find({"items.item_id": {"$in": list(ids)}}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return orders


@api.get("/orders")
async def all_orders(user: dict = Depends(require_role("admin"))):
    return await db.orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api.put("/orders/{order_id}/status")
async def update_status(order_id: str, body: StatusIn, user: dict = Depends(require_role("seller", "admin"))):
    o = await db.orders.find_one({"id": order_id})
    if not o:
        raise HTTPException(404, "Order not found")
    await db.orders.update_one({"id": order_id}, {"$set": {"status": body.status}})
    updated = await db.orders.find_one({"id": order_id}, {"_id": 0})
    return updated


# ----------------------------------------------------------------------------
# Admin: shop verification & email block
# ----------------------------------------------------------------------------
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
# Exchange rate (per seller)
# ----------------------------------------------------------------------------
@api.get("/exchange-rate")
async def get_rate(seller_id: Optional[str] = None):
    """Public endpoint to fetch a seller's rate, or the global default."""
    if seller_id:
        rec = await db.exchange_rates.find_one({"seller_id": seller_id}, {"_id": 0})
        if rec:
            return rec
    rec = await db.exchange_rates.find_one({"seller_id": "__global__"}, {"_id": 0})
    return rec or {"seller_id": "__global__", "rate": 600.0}


@api.put("/exchange-rate")
async def set_rate(body: ExchangeRateIn, user: dict = Depends(require_role("seller", "admin"))):
    seller_id = "__global__" if user["role"] == "admin" else user["id"]
    await db.exchange_rates.update_one(
        {"seller_id": seller_id},
        {"$set": {"seller_id": seller_id, "rate": float(body.rate), "updated_at": now_iso()}},
        upsert=True,
    )
    return {"seller_id": seller_id, "rate": body.rate}


# ----------------------------------------------------------------------------
# Areas & meta
# ----------------------------------------------------------------------------
JUBA_AREAS = ["Munuki", "Jebel", "Gudele", "Konyo Konyo", "Hai Cinema", "Nyakuron", "Atlabara"]


@api.get("/meta/areas")
async def get_areas():
    return JUBA_AREAS


@api.get("/meta/health")
async def health():
    return {"ok": True, "service": "JubaSquare API"}


# ----------------------------------------------------------------------------
# Seeding
# ----------------------------------------------------------------------------
DEMO_USERS = [
    {"email": "admin@demo.com", "password": "1234", "name": "Demo Admin", "role": "admin"},
    {"email": "seller@demo.com", "password": "1234", "name": "Demo Seller", "role": "seller"},
    {"email": "customer@demo.com", "password": "1234", "name": "Demo Customer", "role": "customer"},
]

SHOP_SEEDS = [
    {
        "name": "Juba Tech Hub",
        "category": "Electronics",
        "description": "Latest electronics, mobile phones and accessories.",
        "area": "Munuki",
        "image_url": "https://images.unsplash.com/photo-1761641466573-f240b6e446de?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzNzl8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBlbGVjdHJvbmljcyUyMGRldmljZXN8ZW58MHx8fHwxNzc3OTQwNjI4fDA&ixlib=rb-4.1.0&q=85",
        "verification": "Verified",
        "products": [
            {
                "name": "Samsung Galaxy A55",
                "category": "Electronics",
                "price_usd": 380.0,
                "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=800&q=80",
                "description": "6.5\" AMOLED, 128GB, dual SIM smartphone.",
            },
            {
                "name": "Wireless Headphones",
                "category": "Electronics",
                "price_usd": 65.0,
                "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800&q=80",
                "description": "Over-ear bluetooth headphones with 40h battery.",
            },
        ],
    },
    {
        "name": "Nile Fashion House",
        "category": "Fashion",
        "description": "Trendy clothing for men and women.",
        "area": "Atlabara",
        "image_url": "https://images.unsplash.com/photo-1757140447782-8503452b2204?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMzV8MHwxfHNlYXJjaHwzfHxhZnJpY2FuJTIwZmFzaGlvbiUyMGNsb3RoaW5nfGVufDB8fHx8MTc3Nzk0MDYyM3ww&ixlib=rb-4.1.0&q=85",
        "verification": "Verified",
        "products": [
            {
                "name": "Premium Cotton T-Shirt",
                "category": "Fashion",
                "price_usd": 18.0,
                "image_url": "https://images.unsplash.com/photo-1581655353564-df123a1eb820?w=800&q=80",
                "description": "Soft 100% cotton, multiple colors available.",
            },
            {
                "name": "Slim Fit Jeans",
                "category": "Fashion",
                "price_usd": 42.0,
                "image_url": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=800&q=80",
                "description": "Comfortable stretch denim, classic blue.",
            },
        ],
    },
    {
        "name": "Equatoria Home Essentials",
        "category": "Home Essentials",
        "description": "Furniture, kitchenware and home goods.",
        "area": "Gudele",
        "image_url": "https://images.pexels.com/photos/15108276/pexels-photo-15108276.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        "verification": "Verified",
        "products": [
            {
                "name": "Wooden Dining Chair",
                "category": "Home Essentials",
                "price_usd": 55.0,
                "image_url": "https://images.unsplash.com/photo-1503602642458-232111445657?w=800&q=80",
                "description": "Solid mahogany dining chair, hand-finished.",
            },
            {
                "name": "Premium Kitchen Set",
                "category": "Home Essentials",
                "price_usd": 89.0,
                "image_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&q=80",
                "description": "12-piece non-stick cookware set.",
            },
        ],
    },
    {
        "name": "Juba Pharmacy Plus",
        "category": "Pharmacy",
        "description": "Trusted medicines and health products.",
        "area": "Hai Cinema",
        "image_url": "https://images.unsplash.com/photo-1646392206581-2527b1cae5cb?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjh8MHwxfHNlYXJjaHwxfHxwaGFybWFjeSUyMHBpbGxzJTIwbWVkaWNpbmV8ZW58MHx8fHwxNzc3OTQwNjI5fDA&ixlib=rb-4.1.0&q=85",
        "verification": "Verified",
        "products": [
            {
                "name": "Paracetamol 500mg (Pack of 20)",
                "category": "Pharmacy",
                "price_usd": 4.5,
                "image_url": "https://images.unsplash.com/photo-1587854692152-cbe660dbde88?w=800&q=80",
                "description": "Pain & fever relief tablets.",
            },
            {
                "name": "Multivitamin Bottle (60 caps)",
                "category": "Pharmacy",
                "price_usd": 12.0,
                "image_url": "https://images.unsplash.com/photo-1550572017-edd951b55104?w=800&q=80",
                "description": "Daily multivitamins for adults.",
            },
        ],
    },
    {
        "name": "Sahel Auto Parts",
        "category": "Automotive",
        "description": "Quality car parts and accessories.",
        "area": "Jebel",
        "image_url": "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?w=800&q=80",
        "verification": "Pending",
        "products": [
            {
                "name": "Heavy-Duty Car Battery",
                "category": "Automotive",
                "price_usd": 145.0,
                "image_url": "https://images.unsplash.com/photo-1632823469847-2c40beb9e6ec?w=800&q=80",
                "description": "12V 70Ah maintenance-free battery.",
            },
            {
                "name": "All-Season Tire (Set of 4)",
                "category": "Automotive",
                "price_usd": 320.0,
                "image_url": "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?w=800&q=80",
                "description": "R15 all-season tires, durable tread.",
            },
        ],
    },
]

RESTAURANT_SEEDS = [
    {
        "name": "Juba Burger Joint",
        "category": "Fast Food",
        "description": "Juicy burgers and crispy fries.",
        "area": "Konyo Konyo",
        "is_open": True,
        "verification": "Verified",
        "image_url": "https://images.unsplash.com/photo-1571091718767-18b5b1457add?w=800&q=80",
        "menu": [
            {
                "name": "Classic Beef Burger",
                "price_usd": 8.5,
                "image_url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=800&q=80",
                "description": "Beef patty, cheese, lettuce, special sauce.",
            },
            {
                "name": "Crispy French Fries",
                "price_usd": 3.5,
                "image_url": "https://images.unsplash.com/photo-1576107232684-1279f390859f?w=800&q=80",
                "description": "Golden hand-cut fries with sea salt.",
            },
        ],
    },
    {
        "name": "Mama Africa Kitchen",
        "category": "Local Food",
        "description": "Authentic South Sudanese home cooking.",
        "area": "Nyakuron",
        "is_open": True,
        "verification": "Verified",
        "image_url": "https://images.unsplash.com/photo-1726177975126-0053e054bc1a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDF8MHwxfHNlYXJjaHwzfHxhZnJpY2FuJTIwbG9jYWwlMjBmb29kJTIwZGlzaHxlbnwwfHx8fDE3Nzc5NDA2MjN8MA&ixlib=rb-4.1.0&q=85",
        "menu": [
            {
                "name": "Rice & Grilled Chicken",
                "price_usd": 7.0,
                "image_url": "https://images.unsplash.com/photo-1604908176997-125f25cc6f3d?w=800&q=80",
                "description": "Spiced jasmine rice with grilled chicken.",
            },
            {
                "name": "Stewed Beans Plate",
                "price_usd": 5.0,
                "image_url": "https://images.unsplash.com/photo-1543339308-43e59d6b73a6?w=800&q=80",
                "description": "Slow-cooked beans with onions & spices.",
            },
        ],
    },
    {
        "name": "Cool Sips Drinks",
        "category": "Drinks",
        "description": "Refreshing juices, smoothies and sodas.",
        "area": "Munuki",
        "is_open": True,
        "verification": "Verified",
        "image_url": "https://images.unsplash.com/photo-1622597467836-f3285f2131b8?w=800&q=80",
        "menu": [
            {
                "name": "Fresh Mango Juice",
                "price_usd": 3.0,
                "image_url": "https://images.unsplash.com/photo-1546173159-315724a31696?w=800&q=80",
                "description": "100% fresh mango, no added sugar.",
            },
            {
                "name": "Cold Soda 500ml",
                "price_usd": 1.5,
                "image_url": "https://images.unsplash.com/photo-1581636625402-29b2a704ef13?w=800&q=80",
                "description": "Chilled bottled soda — your choice of flavor.",
            },
        ],
    },
    {
        "name": "Nile Bakery",
        "category": "Bakery",
        "description": "Fresh bread and cakes baked daily.",
        "area": "Atlabara",
        "is_open": False,
        "verification": "Verified",
        "image_url": "https://images.unsplash.com/photo-1628690570377-a8d5bd19768c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDF8MHwxfHNlYXJjaHwyfHxhZnJpY2FuJTIwbG9jYWwlMjBmb29kJTIwZGlzaHxlbnwwfHx8fDE3Nzc5NDA2MjN8MA&ixlib=rb-4.1.0&q=85",
        "menu": [
            {
                "name": "Fresh Sourdough Loaf",
                "price_usd": 4.0,
                "image_url": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=800&q=80",
                "description": "Crusty sourdough, baked this morning.",
            },
            {
                "name": "Chocolate Celebration Cake",
                "price_usd": 22.0,
                "image_url": "https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=800&q=80",
                "description": "Rich chocolate layered cake — serves 8.",
            },
        ],
    },
]


async def seed_demo():
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.shops.create_index("id", unique=True)
    await db.products.create_index("id", unique=True)
    await db.restaurants.create_index("id", unique=True)
    await db.menu_items.create_index("id", unique=True)
    await db.orders.create_index("id", unique=True)
    await db.blocked_emails.create_index("email", unique=True)

    # Users
    user_ids: dict = {}
    for u in DEMO_USERS:
        existing = await db.users.find_one({"email": u["email"]})
        if existing:
            # Always reset password hash to ensure demo password works
            await db.users.update_one(
                {"email": u["email"]},
                {"$set": {"password_hash": hash_password(u["password"]), "name": u["name"], "role": u["role"]}},
            )
            user_ids[u["role"]] = existing["id"]
        else:
            uid = str(uuid.uuid4())
            await db.users.insert_one({
                "id": uid,
                "email": u["email"],
                "name": u["name"],
                "role": u["role"],
                "phone": "",
                "password_hash": hash_password(u["password"]),
                "created_at": now_iso(),
            })
            user_ids[u["role"]] = uid

    seller_id = user_ids["seller"]

    # Shops + products (idempotent — skip if shop with same name exists)
    for s in SHOP_SEEDS:
        existing = await db.shops.find_one({"name": s["name"]})
        if existing:
            continue
        shop_id = str(uuid.uuid4())
        await db.shops.insert_one({
            "id": shop_id,
            "seller_id": seller_id,
            "name": s["name"],
            "category": s["category"],
            "description": s["description"],
            "area": s["area"],
            "image_url": s["image_url"],
            "verification": s.get("verification", "Pending"),
            "created_at": now_iso(),
        })
        for p in s["products"]:
            await db.products.insert_one({
                "id": str(uuid.uuid4()),
                "shop_id": shop_id,
                "seller_id": seller_id,
                "name": p["name"],
                "category": p["category"],
                "price_usd": p["price_usd"],
                "image_url": p["image_url"],
                "description": p["description"],
                "stock": 100,
                "created_at": now_iso(),
            })

    # Restaurants + menu items
    for r in RESTAURANT_SEEDS:
        existing = await db.restaurants.find_one({"name": r["name"]})
        if existing:
            continue
        rid = str(uuid.uuid4())
        await db.restaurants.insert_one({
            "id": rid,
            "seller_id": seller_id,
            "name": r["name"],
            "category": r["category"],
            "description": r["description"],
            "area": r["area"],
            "is_open": r["is_open"],
            "image_url": r["image_url"],
            "verification": r.get("verification", "Verified"),
            "created_at": now_iso(),
        })
        for m in r["menu"]:
            await db.menu_items.insert_one({
                "id": str(uuid.uuid4()),
                "restaurant_id": rid,
                "seller_id": seller_id,
                "name": m["name"],
                "price_usd": m["price_usd"],
                "image_url": m["image_url"],
                "description": m["description"],
                "created_at": now_iso(),
            })

    # Default exchange rate (seller-controlled)
    existing_rate = await db.exchange_rates.find_one({"seller_id": seller_id})
    if not existing_rate:
        await db.exchange_rates.insert_one({
            "seller_id": seller_id,
            "rate": 600.0,
            "updated_at": now_iso(),
        })

    # Sample orders for demo realism
    customer_id = user_ids["customer"]
    if await db.orders.count_documents({}) == 0:
        sample_products = await db.products.find({}, {"_id": 0}).to_list(2)
        if sample_products:
            await db.orders.insert_one({
                "id": str(uuid.uuid4()),
                "customer_id": customer_id,
                "customer_name": "Demo Customer",
                "customer_email": "customer@demo.com",
                "items": [{
                    "item_type": "product",
                    "item_id": sample_products[0]["id"],
                    "name": sample_products[0]["name"],
                    "price_usd": sample_products[0]["price_usd"],
                    "quantity": 1,
                    "image_url": sample_products[0]["image_url"],
                }],
                "subtotal_usd": sample_products[0]["price_usd"],
                "area": "Munuki",
                "address": "Block 4, Munuki",
                "phone": "+211 9XX XXX XXX",
                "note": "",
                "order_kind": "marketplace",
                "status": "Delivered",
                "created_at": now_iso(),
            })

    log.info("✅ JubaSquare demo data seeded successfully")


@app.on_event("startup")
async def on_startup():
    await seed_demo()


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


# ----------------------------------------------------------------------------
# Mount router & CORS
# ----------------------------------------------------------------------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
)
