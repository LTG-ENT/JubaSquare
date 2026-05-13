"""
Cash-on-Delivery + Driver + Payout system for JubaSquare.

Adds:
- Driver role + driver dashboard
- Per-seller order splits with full state machine (pickup / handover /
  delivery / return / cash / payout)
- Marketplace + restaurant orders share the same COD flow
- Seller wallet + admin-controlled payouts
- Backend price recalculation (do not trust frontend prices)

Endpoints exposed:
    Admin   /api/admin/drivers              CRUD + list
            /api/admin/order-splits         list + assign + cash receive
            /api/admin/restaurant-orders-cod (same for restaurant orders)
            /api/admin/cash-handovers       pending list
            /api/admin/payouts              generate / list / mark paid
            /api/admin/disputes             open + resolve
    Driver  /api/driver/assignments         list + detail
            /api/driver/splits/{id}/...     pickup / out-for-delivery /
                                            deliver / cash-collected /
                                            delivery-failed / return-to-seller
    Seller  /api/seller/splits              list + accept / preparing /
                                            ready-for-pickup / handed-to-driver
            /api/seller/wallet              aggregated buckets
            /api/seller/payouts             history
"""
from __future__ import annotations

import uuid
import secrets
from datetime import datetime
from typing import List, Optional, Literal, Any

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field, EmailStr


# ---------------------------------------------------------------------------
# Module-level request body models (must NOT live inside route closures —
# FastAPI's dependency-analyser fails to recognise closure-scoped BaseModel
# subclasses as request bodies and treats them as query params instead).
# ---------------------------------------------------------------------------
class CancelBody(BaseModel):
    reason: Optional[str] = ""


# ---------------------------------------------------------------------------
# Injected dependencies. server.py calls cod.bind(...) once at startup.
# ---------------------------------------------------------------------------
db: Any = None
log: Any = None
get_current_user: Any = None
require_role: Any = None
get_settings: Any = None
create_notification: Any = None
now_iso: Any = None
hash_password: Any = None


def bind(*, db_, log_, get_current_user_, require_role_, get_settings_,
         create_notification_, now_iso_, hash_password_):
    global db, log, get_current_user, require_role, get_settings
    global create_notification, now_iso, hash_password
    db = db_
    log = log_
    get_current_user = get_current_user_
    require_role = require_role_
    get_settings = get_settings_
    create_notification = create_notification_
    now_iso = now_iso_
    hash_password = hash_password_


router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Constants & defaults
# ---------------------------------------------------------------------------
PAYMENT_METHOD_COD = "cash_on_delivery"

PAYMENT_STATUSES = {"pending_collection", "collected_by_driver", "received_by_admin", "failed"}
CASH_HANDOVER_STATUSES = {"not_required", "pending", "received"}
PICKUP_STATUSES = {"not_assigned", "pending_pickup", "picked_up", "pickup_failed"}
SELLER_PREP_STATUSES = {"pending", "accepted", "preparing", "ready_for_pickup", "handed_to_driver", "cancelled"}
SELLER_HANDOVER_STATUSES = {"pending", "handed_to_driver", "disputed"}
DELIVERY_STATUSES = {
    "unassigned", "offered", "assigned", "pending_pickup", "picked_up", "out_for_delivery",
    "delivered", "delivery_failed", "return_to_seller_pending", "returned_to_seller", "failed",
}
POD_STATUSES = {"not_required", "pending", "submitted", "disputed"}
RETURN_STATUSES = {"not_required", "pending_return", "return_to_seller_pending", "returned", "return_disputed"}
PAYOUT_STATUSES = {"not_ready", "ready_for_payout", "pending_payout", "paid", "paused", "cancelled"}
DISPUTE_STATUSES = {"none", "opened", "resolved"}

FAILURE_REASONS = {
    "customer_not_available", "customer_refused_to_pay", "customer_phone_unreachable",
    "wrong_address", "customer_cancelled_at_delivery", "product_damaged",
    "driver_problem", "seller_gave_wrong_item", "other",
}

DEFAULT_COD_FIELDS = {
    "payment_method": PAYMENT_METHOD_COD,
    "payment_status": "pending_collection",
    "cash_handover_status": "not_required",  # flipped to "pending" when cash collected
    "pickup_status": "not_assigned",
    "seller_preparation_status": "pending",
    "seller_handover_status": "pending",
    "delivery_status": "unassigned",
    "proof_of_delivery_status": "not_required",
    "return_status": "not_required",
    "payout_status": "not_ready",
    "dispute_status": "none",
    "driver_id": None,
    "driver_name": None,
    "assigned_at": None,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def gen_otp() -> str:
    """4-digit OTP — easy to type, sufficient for COD purposes."""
    return f"{secrets.randbelow(10000):04d}"


def _strip(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc.pop("_id", None)
    return doc


# Fields that must NEVER reach the seller (they only see customer name).
# Admin and driver still see them.
SELLER_PRIVATE_KEYS = (
    "customer_phone",
    "customer_area",
    "customer_address",
    "phone",        # legacy fields on raw orders
    "area",
    "address",
)


def redact_for_seller(doc: dict) -> dict:
    """Remove customer phone / area / address from a doc before returning to seller.
    Returns the same dict (mutated). Keep customer_name intact."""
    if not doc:
        return doc
    for k in SELLER_PRIVATE_KEYS:
        if k in doc:
            doc[k] = None
    return doc


def redact_many_for_seller(rows: list) -> list:
    for r in rows:
        redact_for_seller(r)
    return rows


# Statuses where the seller (and customer) can still cancel the order
# themselves. Anything later means the order is en route or settled.
CANCELLABLE_PREP_STATUSES = {"pending", "accepted", "preparing"}


async def _next_round_robin_driver(declined_by: list[str] | None = None) -> dict | None:
    """Pick the next active driver using round-robin by least-recently-assigned.
    Excludes any driver_id present in `declined_by`. Returns the driver doc or None."""
    declined = set(declined_by or [])
    drivers = await db.users.find(
        {"role": "driver", "is_active": True},
        {"_id": 0, "id": 1, "name": 1, "phone": 1, "last_offered_at": 1},
    ).to_list(500)
    drivers = [d for d in drivers if d["id"] not in declined]
    if not drivers:
        return None
    # Drivers never offered before float to the top; otherwise sort by
    # `last_offered_at` ascending (the longest-idle driver gets the next order).
    drivers.sort(key=lambda d: d.get("last_offered_at") or "")
    return drivers[0]


async def _offer_order_to_driver(
    *, kind: str, order_id: str, driver: dict
) -> None:
    """Mark the order as 'offered' to this driver and bump the driver's
    last_offered_at timestamp (drives the round-robin). `kind` is either
    'split' or 'rest'."""
    now = now_iso()
    coll = db.seller_order_splits if kind == "split" else db.restaurant_orders
    await coll.update_one(
        {"id": order_id},
        {"$set": {
            "driver_id": driver["id"],
            "driver_name": driver.get("name") or "",
            "delivery_status": "offered",
            "pickup_status": "pending_pickup",
            "assigned_at": now,
            "updated_at": now,
        }},
    )
    await db.users.update_one(
        {"id": driver["id"]},
        {"$set": {"last_offered_at": now}},
    )
    try:
        await create_notification(
            user_id=driver["id"],
            message=(
                "New delivery offered — open Driver Dashboard to Accept or Decline."
            ),
            ntype="order",
            meta={
                "order_id": order_id,
                "order_type": ("restaurant" if kind == "rest" else "marketplace"),
                "auto_offered": True,
            },
        )
    except Exception:
        pass


async def auto_assign_rest_order(order_id: str) -> dict | None:
    """Try to auto-assign a restaurant order to the next round-robin driver,
    skipping anyone in declined_by. Returns the driver picked, or None if no
    drivers are available (order stays in 'unassigned')."""
    o = await db.restaurant_orders.find_one({"id": order_id}, {"_id": 0})
    if not o:
        return None
    if o.get("delivery_status") not in {"unassigned", "delivery_failed"}:
        return None
    driver = await _next_round_robin_driver(declined_by=o.get("declined_by") or [])
    if not driver:
        return None
    await _offer_order_to_driver(kind="rest", order_id=order_id, driver=driver)
    return driver


async def _enforce_dispute_pause(split_id: str) -> None:
    s = await db.seller_order_splits.find_one({"id": split_id}, {"_id": 0})
    if not s:
        return
    if s.get("dispute_status") == "opened":
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {"payout_status": "paused", "updated_at": now_iso()}},
        )


async def maybe_mark_split_ready(split_id: str) -> None:
    """Flip a split's payout_status → ready_for_payout when ALL conditions
    are satisfied.

    Conditions (per spec):
      - pickup_status == picked_up
      - seller_handover_status == handed_to_driver
      - delivery_status == delivered
      - proof_of_delivery_status == submitted
      - payment_status == received_by_admin
      - cash_handover_status == received
      - dispute_status in {none, resolved}
      - return_status == not_required
    """
    s = await db.seller_order_splits.find_one({"id": split_id}, {"_id": 0})
    if not s:
        return
    if s.get("payout_status") in {"ready_for_payout", "pending_payout", "paid", "paused", "cancelled"}:
        return
    ok = (
        s.get("pickup_status") == "picked_up"
        and s.get("seller_handover_status") == "handed_to_driver"
        and s.get("delivery_status") == "delivered"
        and s.get("proof_of_delivery_status") == "submitted"
        and s.get("payment_status") == "received_by_admin"
        and s.get("cash_handover_status") == "received"
        and s.get("dispute_status") in {"none", "resolved"}
        and s.get("return_status") in {"not_required"}
    )
    if ok:
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {"payout_status": "ready_for_payout", "updated_at": now_iso()}},
        )


# ---------------------------------------------------------------------------
# Split creation (marketplace orders → per-seller splits)
# Uses DB prices, NOT frontend prices.
# ---------------------------------------------------------------------------
async def create_marketplace_splits(order: dict) -> List[dict]:
    item_ids = [it.get("item_id") for it in (order.get("items") or [])]
    if not item_ids:
        return []

    products = await db.products.find({"id": {"$in": item_ids}}, {"_id": 0}).to_list(2000)
    products_by_id = {p["id"]: p for p in products}
    shop_ids = list({p["shop_id"] for p in products})
    shops = await db.shops.find({"id": {"$in": shop_ids}}, {"_id": 0}).to_list(500)
    shops_by_id = {s["id"]: s for s in shops}

    sysconf = await get_settings()
    global_rate = float(sysconf.get("commission_rate", 0.10))

    delivery_by_shop = {
        b.get("shop_id"): float(b.get("fee_usd", 0))
        for b in (order.get("delivery_breakdown") or [])
    }

    # Bucket items by (seller, shop)
    buckets: dict = {}
    for it in order.get("items", []):
        p = products_by_id.get(it.get("item_id"))
        if not p:
            continue
        shop = shops_by_id.get(p["shop_id"], {})
        seller_id = shop.get("seller_id")
        if not seller_id:
            continue
        key = (seller_id, p["shop_id"])
        b = buckets.setdefault(key, {
            "seller_id": seller_id,
            "shop_id": p["shop_id"],
            "shop_name": shop.get("name", "—"),
            "shop_area": shop.get("area", ""),
            "items": [],
            "product_subtotal": 0.0,
        })
        qty = max(1, int(it.get("quantity", 1)))
        price = float(p.get("price_usd", 0))  # DB price — security
        sides = it.get("sides") or []
        # Recompute sides against menu/product? Marketplace products don't
        # have sides, so we keep what was sent for the line note but treat
        # their value as 0 here.
        line_total = price * qty
        b["items"].append({
            "item_id": p["id"],
            "name": p.get("name"),
            "price_usd": price,
            "quantity": qty,
            "image_url": p.get("image_url", ""),
            "line_total_usd": round(line_total, 2),
            "sides": sides,
        })
        b["product_subtotal"] += line_total

    splits: List[dict] = []
    for (seller_id, shop_id), b in buckets.items():
        delivery_fee = delivery_by_shop.get(shop_id, 0.0)
        shop = shops_by_id.get(shop_id, {})
        commission_rate = shop.get("commission_rate")
        rate = float(commission_rate) if commission_rate is not None else global_rate
        product_subtotal = round(b["product_subtotal"], 2)
        platform_commission = round(product_subtotal * rate, 2)
        seller_earning = round(product_subtotal - platform_commission, 2)
        order_total = round(product_subtotal + delivery_fee, 2)

        split = {
            "id": str(uuid.uuid4()),
            "order_id": order["id"],
            "order_type": "marketplace",
            "customer_id": order.get("customer_id"),
            "customer_name": order.get("customer_name"),
            "customer_email": order.get("customer_email"),
            "customer_phone": order.get("phone"),
            "customer_area": order.get("area"),
            "customer_address": order.get("address"),
            "seller_id": seller_id,
            "shop_id": shop_id,
            "shop_name": b["shop_name"],
            "shop_area": b["shop_area"],
            "items": b["items"],
            "product_subtotal_usd": product_subtotal,
            "delivery_fee_usd": round(delivery_fee, 2),
            "order_total_usd": order_total,
            "commission_rate": rate,
            "platform_commission_usd": platform_commission,
            "seller_earning_usd": seller_earning,
            "seller_pickup_otp": gen_otp(),
            "customer_delivery_otp": gen_otp(),
            "return_otp": gen_otp(),
            "signature_b64": None,
            "receiver_name": None,
            "failure_reason": None,
            "failure_note": None,
            "delivered_at": None,
            "cash_collected_at": None,
            "cash_received_at": None,
            "payout_id": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            **DEFAULT_COD_FIELDS,
        }
        await db.seller_order_splits.insert_one(split)
        split.pop("_id", None)
        splits.append(split)
        try:
            await create_notification(
                user_id=seller_id,
                message=f"New order assigned: {b['shop_name']} ({short(split['id'])}) — USD {order_total:.2f}",
                ntype="order",
                meta={"split_id": split["id"], "order_id": order["id"]},
            )
        except Exception:
            pass
    return splits


def short(_id: str) -> str:
    return (_id or "")[:8]


# ---------------------------------------------------------------------------
# Restaurant-order COD fields initializer
# Restaurant orders are single-seller — fields live inline on the doc.
# ---------------------------------------------------------------------------
async def initialize_restaurant_order_cod(order: dict) -> dict:
    """Populate the new COD/driver fields on a restaurant_orders doc.
    Recomputes prices from DB menu_items for security."""
    rest = await db.restaurants.find_one({"id": order.get("restaurant_id")}, {"_id": 0}) or {}
    seller_id = rest.get("seller_id")
    item_ids = [it.get("item_id") for it in (order.get("items") or [])]
    menu_items = await db.menu_items.find({"id": {"$in": item_ids}}, {"_id": 0}).to_list(2000)
    menu_by_id = {m["id"]: m for m in menu_items}

    sysconf = await get_settings()
    global_rate = float(sysconf.get("commission_rate", 0.10))
    rate = rest.get("commission_rate")
    rate = float(rate) if rate is not None else global_rate

    # Recompute subtotal using DB prices
    subtotal = 0.0
    secure_items = []
    for it in order.get("items", []):
        m = menu_by_id.get(it.get("item_id"))
        if not m:
            continue
        qty = max(1, int(it.get("quantity", 1)))
        price = float(m.get("price_usd", 0))
        sides_total = 0.0
        for sd in (it.get("sides") or []):
            sides_total += float(sd.get("price_usd", 0))
        line = (price + sides_total) * qty
        subtotal += line
        secure_items.append({
            "item_id": m["id"],
            "name": m.get("name"),
            "price_usd": price,
            "quantity": qty,
            "image_url": m.get("image_url", ""),
            "line_total_usd": round(line, 2),
            "sides": it.get("sides") or [],
        })

    product_subtotal = round(subtotal, 2)
    delivery_fee = float(order.get("delivery_fee", 0))
    order_total = round(product_subtotal + delivery_fee, 2)
    platform_commission = round(product_subtotal * rate, 2)
    seller_earning = round(product_subtotal - platform_commission, 2)

    cod_fields = {
        "items_secure": secure_items,
        "product_subtotal_usd": product_subtotal,
        "delivery_fee_usd": delivery_fee,
        "order_total_usd": order_total,
        "seller_id": seller_id,
        "shop_name": rest.get("name", "—"),
        "shop_area": rest.get("area", ""),
        "customer_area": rest.get("area", ""),  # restaurants don't always carry area; fallback
        "commission_rate": rate,
        "platform_commission_usd": platform_commission,
        "seller_earning_usd": seller_earning,
        "seller_pickup_otp": gen_otp(),
        "customer_delivery_otp": gen_otp(),
        "return_otp": gen_otp(),
        "signature_b64": None,
        "receiver_name": None,
        "failure_reason": None,
        "failure_note": None,
        "delivered_at": None,
        "cash_collected_at": None,
        "cash_received_at": None,
        "payout_id": None,
        **DEFAULT_COD_FIELDS,
    }
    # Restaurant orders use their own area from customer_address if present
    if order.get("customer_address"):
        cod_fields["customer_address"] = order["customer_address"]
    return cod_fields


# ---------------------------------------------------------------------------
# Common helpers: unified "assignment" abstraction across splits + rest orders
# ---------------------------------------------------------------------------
async def _find_split(split_id: str) -> dict:
    s = await db.seller_order_splits.find_one({"id": split_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Order split not found")
    return s


async def _find_rest_order(order_id: str) -> dict:
    o = await db.restaurant_orders.find_one({"id": order_id}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Restaurant order not found")
    return o


def _check_driver_owns(doc: dict, user: dict) -> None:
    if doc.get("driver_id") != user["id"]:
        raise HTTPException(403, "This delivery is not assigned to you")


def _check_seller_owns(doc: dict, user: dict) -> None:
    if doc.get("seller_id") != user["id"] and user.get("role") != "admin":
        raise HTTPException(403, "This order does not belong to your shop")


# ===========================================================================
# Models
# ===========================================================================
class AssignDriverIn(BaseModel):
    driver_id: str


class OTPIn(BaseModel):
    otp: str = Field(min_length=1, max_length=12)


class DeliverIn(BaseModel):
    otp: str = Field(min_length=1, max_length=12)
    signature_b64: str = Field(min_length=10)
    receiver_name: str = Field(min_length=1, max_length=120)


class DeliveryFailedIn(BaseModel):
    reason: Literal[
        "customer_not_available", "customer_refused_to_pay", "customer_phone_unreachable",
        "wrong_address", "customer_cancelled_at_delivery", "product_damaged",
        "driver_problem", "seller_gave_wrong_item", "other",
    ]
    note: Optional[str] = ""


class DriverCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6)
    phone: Optional[str] = ""


class DisputeOpenIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class PayoutGenerateIn(BaseModel):
    seller_id: Optional[str] = None  # if None, generate for all eligible sellers


# ===========================================================================
# ADMIN — drivers
# ===========================================================================
@router.get("/admin/drivers")
async def admin_list_drivers(_: dict = Depends(lambda: None)):
    pass  # placeholder, replaced below by re-decoration after bind()


# We define endpoints with a factory to inject the auth dependency at runtime.
# (FastAPI evaluates Depends() at decoration time, so we must wrap functions
# in a helper that's added AFTER bind() is called.)
# To keep things simple, we just instantiate dependency objects lazily using a
# local helper that reaches into the module-level require_role / get_current_user.

def _admin_dep():
    return Depends(require_role("admin"))


def _driver_dep():
    return Depends(require_role("driver"))


def _seller_dep():
    return Depends(require_role("seller", "admin"))


def _any_dep():
    return Depends(get_current_user)


# Because we need bind() to have run before _admin_dep() can resolve, we
# rebuild the router after bind. Simpler: build all endpoints inside a
# register() function that the server calls after bind.
def register_endpoints():
    """Called by server.py after bind(). Re-create the router with all
    endpoints using the resolved dependencies."""
    global router
    new_router = APIRouter(prefix="/api")

    admin_dep = Depends(require_role("admin"))
    driver_dep = Depends(require_role("driver"))
    seller_dep = Depends(require_role("seller", "admin"))

    # -------- ADMIN: drivers --------
    @new_router.get("/admin/drivers")
    async def list_drivers(_: dict = admin_dep):
        rows = await db.users.find(
            {"role": "driver"},
            {"_id": 0, "password_hash": 0},
        ).sort("created_at", -1).to_list(500)
        # Augment with stats
        for r in rows:
            r["active_deliveries"] = await db.seller_order_splits.count_documents({
                "driver_id": r["id"],
                "delivery_status": {"$in": ["assigned", "pending_pickup", "picked_up", "out_for_delivery"]},
            }) + await db.restaurant_orders.count_documents({
                "driver_id": r["id"],
                "delivery_status": {"$in": ["assigned", "pending_pickup", "picked_up", "out_for_delivery"]},
            })
            r["cash_pending_handover_usd"] = await _driver_cash_pending(r["id"])
        return rows

    @new_router.post("/admin/drivers")
    async def create_driver(body: DriverCreateIn, _: dict = admin_dep):
        email = body.email.lower()
        exists = await db.users.find_one({"email": email})
        if exists:
            raise HTTPException(400, "Email already registered")
        user = {
            "id": str(uuid.uuid4()),
            "email": email,
            "name": body.name,
            "phone": body.phone or "",
            "role": "driver",
            "settings": {},
            "email_verified": True,
            "is_active": True,
            "must_change_password": False,
            "password_hash": hash_password(body.password),
            "created_at": now_iso(),
        }
        await db.users.insert_one(user)
        user.pop("_id", None)
        user.pop("password_hash", None)
        return user

    @new_router.put("/admin/drivers/{driver_id}/status")
    async def driver_status(driver_id: str, body: dict, _: dict = admin_dep):
        await db.users.update_one(
            {"id": driver_id, "role": "driver"},
            {"$set": {"is_active": bool(body.get("is_active", True))}},
        )
        return {"ok": True}

    @new_router.delete("/admin/drivers/{driver_id}")
    async def driver_delete(driver_id: str, _: dict = admin_dep):
        # Refuse if has active assignments
        active = await db.seller_order_splits.count_documents({
            "driver_id": driver_id,
            "delivery_status": {"$in": ["assigned", "pending_pickup", "picked_up", "out_for_delivery"]},
        })
        if active:
            raise HTTPException(400, "Driver has active deliveries — reassign them first")
        await db.users.delete_one({"id": driver_id, "role": "driver"})
        return {"ok": True}

    # -------- ADMIN: order splits --------
    @new_router.get("/admin/order-splits")
    async def list_splits(
        status: Optional[str] = None,
        unassigned_only: bool = False,
        seller_id: Optional[str] = None,
        _: dict = admin_dep,
    ):
        q: dict = {}
        if status:
            q["delivery_status"] = status
        if unassigned_only:
            q["delivery_status"] = "unassigned"
        if seller_id:
            q["seller_id"] = seller_id
        rows = await db.seller_order_splits.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        return rows

    @new_router.get("/admin/order-splits/{split_id}")
    async def get_split(split_id: str, _: dict = admin_dep):
        return await _find_split(split_id)

    @new_router.post("/admin/order-splits/{split_id}/assign-driver")
    async def assign_driver_to_split(split_id: str, body: AssignDriverIn, _: dict = admin_dep):
        split = await _find_split(split_id)
        if split.get("delivery_status") not in {"unassigned", "delivery_failed"}:
            # allow re-assignment if previous failed, but otherwise driver only set once
            if split.get("driver_id"):
                raise HTTPException(400, f"Split already assigned (status: {split.get('delivery_status')})")
        driver = await db.users.find_one({"id": body.driver_id, "role": "driver"}, {"_id": 0, "name": 1, "id": 1})
        if not driver:
            raise HTTPException(404, "Driver not found")
        update = {
            "driver_id": driver["id"],
            "driver_name": driver["name"],
            "assigned_at": now_iso(),
            "delivery_status": "assigned",
            "pickup_status": "pending_pickup",
            "updated_at": now_iso(),
        }
        await db.seller_order_splits.update_one({"id": split_id}, {"$set": update})
        try:
            await create_notification(
                user_id=driver["id"],
                message=f"New delivery assigned: {split['shop_name']} → {split.get('customer_name', '')}",
                ntype="order",
                meta={"split_id": split_id, "order_type": "marketplace"},
            )
        except Exception:
            pass
        return await _find_split(split_id)

    # -------- ADMIN: restaurant orders COD --------
    @new_router.get("/admin/restaurant-orders-cod")
    async def list_rest_orders_cod(
        status: Optional[str] = None,
        unassigned_only: bool = False,
        _: dict = admin_dep,
    ):
        q: dict = {"payment_method": PAYMENT_METHOD_COD}
        if status:
            q["delivery_status"] = status
        if unassigned_only:
            q["delivery_status"] = "unassigned"
        return await db.restaurant_orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)

    @new_router.post("/admin/restaurant-orders/{order_id}/assign-driver")
    async def assign_driver_to_rest(order_id: str, body: AssignDriverIn, _: dict = admin_dep):
        o = await _find_rest_order(order_id)
        if o.get("driver_id") and o.get("delivery_status") not in {"unassigned", "delivery_failed"}:
            raise HTTPException(400, f"Order already assigned (status: {o.get('delivery_status')})")
        driver = await db.users.find_one({"id": body.driver_id, "role": "driver"}, {"_id": 0, "name": 1, "id": 1})
        if not driver:
            raise HTTPException(404, "Driver not found")
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {
                "driver_id": driver["id"],
                "driver_name": driver["name"],
                "assigned_at": now_iso(),
                "delivery_status": "assigned",
                "pickup_status": "pending_pickup",
                "updated_at": now_iso(),
            }},
        )
        try:
            await create_notification(
                user_id=driver["id"],
                message=f"New restaurant delivery: {o.get('restaurant_name', '')}",
                ntype="order",
                meta={"order_id": order_id, "order_type": "restaurant"},
            )
        except Exception:
            pass
        return await _find_rest_order(order_id)

    # -------- ADMIN: cash handovers --------
    @new_router.get("/admin/cash-handovers")
    async def list_cash_handovers(_: dict = admin_dep):
        splits = await db.seller_order_splits.find(
            {"cash_handover_status": "pending"}, {"_id": 0},
        ).sort("cash_collected_at", -1).to_list(500)
        rest_orders = await db.restaurant_orders.find(
            {"cash_handover_status": "pending"}, {"_id": 0},
        ).sort("cash_collected_at", -1).to_list(500)
        return {
            "splits": splits,
            "restaurant_orders": rest_orders,
            "totals": {
                "splits_count": len(splits),
                "splits_usd": round(sum(s.get("order_total_usd", 0) for s in splits), 2),
                "restaurant_orders_count": len(rest_orders),
                "restaurant_orders_usd": round(sum(o.get("order_total_usd", 0) for o in rest_orders), 2),
            },
        }

    @new_router.post("/admin/cash-handovers/split/{split_id}/receive")
    async def receive_cash_split(split_id: str, admin: dict = admin_dep):
        s = await _find_split(split_id)
        if s.get("cash_handover_status") != "pending":
            raise HTTPException(400, "No pending cash on this split")
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {
                "cash_handover_status": "received",
                "payment_status": "received_by_admin",
                "cash_received_at": now_iso(),
                "cash_received_by": admin["id"],
                "updated_at": now_iso(),
            }},
        )
        await db.driver_cash_receipts.insert_one({
            "id": str(uuid.uuid4()),
            "type": "split",
            "ref_id": split_id,
            "driver_id": s.get("driver_id"),
            "amount_usd": s.get("order_total_usd", 0),
            "received_by": admin["id"],
            "received_at": now_iso(),
            "order_id": s.get("order_id"),
        })
        await maybe_mark_split_ready(split_id)
        return await _find_split(split_id)

    @new_router.post("/admin/cash-handovers/restaurant-order/{order_id}/receive")
    async def receive_cash_rest(order_id: str, admin: dict = admin_dep):
        o = await _find_rest_order(order_id)
        if o.get("cash_handover_status") != "pending":
            raise HTTPException(400, "No pending cash on this order")
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {
                "cash_handover_status": "received",
                "payment_status": "received_by_admin",
                "cash_received_at": now_iso(),
                "cash_received_by": admin["id"],
                "updated_at": now_iso(),
            }},
        )
        await db.driver_cash_receipts.insert_one({
            "id": str(uuid.uuid4()),
            "type": "restaurant_order",
            "ref_id": order_id,
            "driver_id": o.get("driver_id"),
            "amount_usd": o.get("order_total_usd", 0),
            "received_by": admin["id"],
            "received_at": now_iso(),
        })
        await _maybe_mark_rest_ready(order_id)
        return await _find_rest_order(order_id)

    @new_router.get("/admin/cash-receipts")
    async def list_cash_receipts(_: dict = admin_dep):
        return await db.driver_cash_receipts.find({}, {"_id": 0}).sort("received_at", -1).to_list(500)

    # -------- ADMIN: payouts --------
    @new_router.post("/admin/payouts/generate")
    async def generate_payouts(body: PayoutGenerateIn, _: dict = admin_dep):
        return await _generate_payouts(body.seller_id)

    @new_router.get("/admin/payouts")
    async def list_all_payouts(_: dict = admin_dep, status: Optional[str] = None):
        q: dict = {}
        if status:
            q["status"] = status
        return await db.seller_payouts.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)

    @new_router.get("/admin/payouts/{payout_id}")
    async def get_payout(payout_id: str, _: dict = admin_dep):
        p = await db.seller_payouts.find_one({"id": payout_id}, {"_id": 0})
        if not p:
            raise HTTPException(404, "Payout not found")
        p["splits"] = await db.seller_order_splits.find(
            {"payout_id": payout_id, "order_type": "marketplace"}, {"_id": 0},
        ).to_list(500)
        p["restaurant_orders"] = await db.restaurant_orders.find(
            {"payout_id": payout_id}, {"_id": 0},
        ).to_list(500)
        return p

    @new_router.post("/admin/payouts/{payout_id}/mark-paid")
    async def mark_payout_paid(payout_id: str, admin: dict = admin_dep):
        p = await db.seller_payouts.find_one({"id": payout_id})
        if not p:
            raise HTTPException(404, "Payout not found")
        if p.get("status") == "paid":
            return {"ok": True, "already_paid": True}
        now = now_iso()
        await db.seller_payouts.update_one(
            {"id": payout_id},
            {"$set": {"status": "paid", "paid_at": now, "paid_by": admin["id"], "updated_at": now}},
        )
        await db.seller_order_splits.update_many(
            {"payout_id": payout_id},
            {"$set": {"payout_status": "paid", "updated_at": now}},
        )
        await db.restaurant_orders.update_many(
            {"payout_id": payout_id},
            {"$set": {"payout_status": "paid", "updated_at": now}},
        )
        try:
            await create_notification(
                user_id=p["seller_id"],
                message=f"Payout USD {p['amount_usd']:.2f} marked as paid. Thank you!",
                ntype="commission",
                meta={"payout_id": payout_id},
            )
        except Exception:
            pass
        return await db.seller_payouts.find_one({"id": payout_id}, {"_id": 0})

    # -------- ADMIN: disputes --------
    @new_router.post("/admin/disputes/split/{split_id}/open")
    async def open_dispute_split(split_id: str, body: DisputeOpenIn, _: dict = admin_dep):
        s = await _find_split(split_id)
        if s.get("dispute_status") == "opened":
            raise HTTPException(400, "Dispute already open")
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {
                "dispute_status": "opened",
                "dispute_reason": body.reason,
                "dispute_opened_at": now_iso(),
                "payout_status": "paused",
                "updated_at": now_iso(),
            }},
        )
        return await _find_split(split_id)

    @new_router.post("/admin/disputes/split/{split_id}/resolve")
    async def resolve_dispute_split(split_id: str, _: dict = admin_dep):
        s = await _find_split(split_id)
        if s.get("dispute_status") != "opened":
            raise HTTPException(400, "No open dispute")
        # Re-evaluate payout eligibility: if was paused only because of dispute,
        # send it back to not_ready and let maybe_mark_split_ready re-promote it.
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {
                "dispute_status": "resolved",
                "dispute_resolved_at": now_iso(),
                "payout_status": "not_ready",
                "updated_at": now_iso(),
            }},
        )
        await maybe_mark_split_ready(split_id)
        return await _find_split(split_id)

    # ===========================================================================
    # SELLER — splits, wallet, payouts
    # ===========================================================================
    @new_router.get("/seller/splits")
    async def seller_splits(user: dict = seller_dep, status: Optional[str] = None):
        q: dict = {"seller_id": user["id"]}
        if status:
            q["delivery_status"] = status
        rows = await db.seller_order_splits.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        return redact_many_for_seller(rows)

    @new_router.get("/seller/restaurant-orders-cod")
    async def seller_rest_cod(user: dict = seller_dep):
        rows = await db.restaurant_orders.find(
            {"seller_id": user["id"]}, {"_id": 0},
        ).sort("created_at", -1).to_list(500)
        return redact_many_for_seller(rows)

    @new_router.post("/seller/splits/{split_id}/accept")
    async def seller_accept(split_id: str, user: dict = seller_dep):
        s = await _find_split(split_id)
        _check_seller_owns(s, user)
        if s.get("seller_preparation_status") not in {"pending"}:
            raise HTTPException(400, f"Cannot accept from status {s.get('seller_preparation_status')}")
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {"seller_preparation_status": "accepted", "updated_at": now_iso()}},
        )
        return await _find_split(split_id)

    @new_router.post("/seller/splits/{split_id}/preparing")
    async def seller_preparing(split_id: str, user: dict = seller_dep):
        s = await _find_split(split_id)
        _check_seller_owns(s, user)
        if s.get("seller_preparation_status") not in {"pending", "accepted"}:
            raise HTTPException(400, f"Cannot move to preparing from {s.get('seller_preparation_status')}")
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {"seller_preparation_status": "preparing", "updated_at": now_iso()}},
        )
        return await _find_split(split_id)

    @new_router.post("/seller/splits/{split_id}/ready-for-pickup")
    async def seller_ready(split_id: str, user: dict = seller_dep):
        s = await _find_split(split_id)
        _check_seller_owns(s, user)
        if s.get("seller_preparation_status") not in {"pending", "accepted", "preparing"}:
            raise HTTPException(400, f"Cannot mark ready from {s.get('seller_preparation_status')}")
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {"seller_preparation_status": "ready_for_pickup", "updated_at": now_iso()}},
        )
        return await _find_split(split_id)

    @new_router.post("/seller/splits/{split_id}/handed-to-driver")
    async def seller_handed(split_id: str, user: dict = seller_dep):
        s = await _find_split(split_id)
        _check_seller_owns(s, user)
        if s.get("pickup_status") != "picked_up":
            raise HTTPException(400, "Driver has not confirmed pickup yet")
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {
                "seller_handover_status": "handed_to_driver",
                "seller_preparation_status": "handed_to_driver",
                "updated_at": now_iso(),
            }},
        )
        await maybe_mark_split_ready(split_id)
        return await _find_split(split_id)

    @new_router.post("/seller/splits/{split_id}/return-received")
    async def seller_return_received(split_id: str, body: OTPIn, user: dict = seller_dep):
        s = await _find_split(split_id)
        _check_seller_owns(s, user)
        if s.get("return_status") != "return_to_seller_pending":
            raise HTTPException(400, "No return in progress on this split")
        if (body.otp or "").strip() != (s.get("return_otp") or ""):
            raise HTTPException(400, "Invalid return OTP")
        now = now_iso()
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {
                "return_status": "returned",
                "delivery_status": "returned_to_seller",
                "payout_status": "cancelled",
                "returned_to_seller_at": now,
                "updated_at": now,
            }},
        )
        return await _find_split(split_id)

    # Seller wallet
    @new_router.get("/seller/wallet")
    async def seller_wallet(user: dict = seller_dep):
        return await _compute_seller_wallet(user["id"])

    @new_router.get("/seller/payouts")
    async def seller_payouts(user: dict = seller_dep):
        return await db.seller_payouts.find(
            {"seller_id": user["id"]}, {"_id": 0},
        ).sort("created_at", -1).to_list(500)

    # === Seller actions for restaurant orders (same buttons, inline) ===
    @new_router.post("/seller/restaurant-orders/{order_id}/accept")
    async def rest_accept(order_id: str, user: dict = seller_dep):
        o = await _find_rest_order(order_id)
        _check_seller_owns(o, user)
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {"seller_preparation_status": "accepted", "updated_at": now_iso()}},
        )
        return await _find_rest_order(order_id)

    @new_router.post("/seller/restaurant-orders/{order_id}/preparing")
    async def rest_prep(order_id: str, user: dict = seller_dep):
        o = await _find_rest_order(order_id)
        _check_seller_owns(o, user)
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {"seller_preparation_status": "preparing", "updated_at": now_iso()}},
        )
        return await _find_rest_order(order_id)

    @new_router.post("/seller/restaurant-orders/{order_id}/ready-for-pickup")
    async def rest_ready(order_id: str, user: dict = seller_dep):
        o = await _find_rest_order(order_id)
        _check_seller_owns(o, user)
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {"seller_preparation_status": "ready_for_pickup", "updated_at": now_iso()}},
        )
        # Auto-assign a driver via round-robin if none is yet committed.
        fresh = await db.restaurant_orders.find_one({"id": order_id}, {"_id": 0})
        if fresh and fresh.get("delivery_status") in {"unassigned", "delivery_failed"}:
            await auto_assign_rest_order(order_id)
        return await _find_rest_order(order_id)

    @new_router.post("/seller/restaurant-orders/{order_id}/handed-to-driver")
    async def rest_handed(order_id: str, user: dict = seller_dep):
        o = await _find_rest_order(order_id)
        _check_seller_owns(o, user)
        if o.get("pickup_status") != "picked_up":
            raise HTTPException(400, "Driver has not confirmed pickup yet")
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {
                "seller_handover_status": "handed_to_driver",
                "seller_preparation_status": "handed_to_driver",
                "updated_at": now_iso(),
            }},
        )
        await _maybe_mark_rest_ready(order_id)
        return await _find_rest_order(order_id)

    @new_router.post("/seller/restaurant-orders/{order_id}/return-received")
    async def rest_return_received(order_id: str, body: OTPIn, user: dict = seller_dep):
        o = await _find_rest_order(order_id)
        _check_seller_owns(o, user)
        if o.get("return_status") != "return_to_seller_pending":
            raise HTTPException(400, "No return in progress")
        if (body.otp or "").strip() != (o.get("return_otp") or ""):
            raise HTTPException(400, "Invalid return OTP")
        now = now_iso()
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {
                "return_status": "returned",
                "delivery_status": "returned_to_seller",
                "payout_status": "cancelled",
                "returned_to_seller_at": now,
                "updated_at": now,
            }},
        )
        return await _find_rest_order(order_id)

    # ===========================================================================
    # DRIVER — assignments + actions
    # ===========================================================================
    @new_router.get("/driver/assignments")
    async def driver_assignments(user: dict = driver_dep, status: Optional[str] = None):
        q_split = {"driver_id": user["id"]}
        q_rest = {"driver_id": user["id"]}
        if status:
            q_split["delivery_status"] = status
            q_rest["delivery_status"] = status
        splits = await db.seller_order_splits.find(q_split, {"_id": 0}).sort("assigned_at", -1).to_list(500)
        rest_orders = await db.restaurant_orders.find(q_rest, {"_id": 0}).sort("assigned_at", -1).to_list(500)
        # Sanitize: hide commission & seller_earning for drivers
        for s in splits:
            for k in ("commission_rate", "platform_commission_usd", "seller_earning_usd"):
                s.pop(k, None)
        for o in rest_orders:
            for k in ("commission_rate", "platform_commission_usd", "seller_earning_usd"):
                o.pop(k, None)
        return {"splits": splits, "restaurant_orders": rest_orders}

    @new_router.get("/driver/assignments/split/{split_id}")
    async def driver_split_detail(split_id: str, user: dict = driver_dep):
        s = await _find_split(split_id)
        _check_driver_owns(s, user)
        # Add seller phone for the driver to call
        seller = await db.users.find_one({"id": s.get("seller_id")}, {"_id": 0, "phone": 1, "name": 1})
        s["seller_phone"] = (seller or {}).get("phone", "")
        s["seller_name"] = (seller or {}).get("name", "")
        for k in ("commission_rate", "platform_commission_usd", "seller_earning_usd"):
            s.pop(k, None)
        return s

    @new_router.get("/driver/assignments/restaurant-order/{order_id}")
    async def driver_rest_detail(order_id: str, user: dict = driver_dep):
        o = await _find_rest_order(order_id)
        _check_driver_owns(o, user)
        seller = await db.users.find_one({"id": o.get("seller_id")}, {"_id": 0, "phone": 1, "name": 1})
        o["seller_phone"] = (seller or {}).get("phone", "")
        o["seller_name"] = (seller or {}).get("name", "")
        for k in ("commission_rate", "platform_commission_usd", "seller_earning_usd"):
            o.pop(k, None)
        return o

    # ---- Driver actions on a split ----
    @new_router.post("/driver/restaurant-orders/{order_id}/accept-offer")
    async def driver_accept_offer_rest(order_id: str, user: dict = driver_dep):
        """Driver accepts a pending offered restaurant order — flips
        delivery_status from 'offered' → 'assigned'. Pickup OTP is still
        required at the pickup step."""
        o = await _find_rest_order(order_id)
        _check_driver_owns(o, user)
        if o.get("delivery_status") != "offered":
            raise HTTPException(400, f"Order is not in 'offered' state (current: {o.get('delivery_status')})")
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {
                "delivery_status": "assigned",
                "driver_accepted_at": now_iso(),
                "updated_at": now_iso(),
            }},
        )
        try:
            await create_notification(
                user_id=o.get("seller_id"),
                message=f"A driver has accepted your delivery for order #{order_id[:8]}",
                ntype="order",
                meta={"order_id": order_id, "kind": "restaurant"},
            )
        except Exception:
            pass
        return await _find_rest_order(order_id)

    @new_router.post("/driver/restaurant-orders/{order_id}/decline-offer")
    async def driver_decline_offer_rest(order_id: str, user: dict = driver_dep):
        """Driver declines the offered restaurant order. The order is then
        re-offered to the next available driver via round-robin (excluding
        anyone who has already declined it). If no driver remains, the order
        reverts to 'unassigned' and admin will see it as unassigned again."""
        o = await _find_rest_order(order_id)
        _check_driver_owns(o, user)
        if o.get("delivery_status") != "offered":
            raise HTTPException(400, f"Order is not in 'offered' state (current: {o.get('delivery_status')})")
        declined_by = list(o.get("declined_by") or [])
        if user["id"] not in declined_by:
            declined_by.append(user["id"])
        # Detach this driver from the order first.
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {
                "driver_id": None,
                "driver_name": None,
                "delivery_status": "unassigned",
                "pickup_status": "not_assigned",
                "assigned_at": None,
                "declined_by": declined_by,
                "updated_at": now_iso(),
            }},
        )
        # Try to offer it to the next driver in line.
        next_driver = await auto_assign_rest_order(order_id)
        if not next_driver:
            try:
                # Notify admins so they can intervene if no driver accepted.
                admins = await db.users.find({"role": "admin"}, {"_id": 0, "id": 1}).to_list(50)
                for a in admins:
                    await create_notification(
                        user_id=a["id"],
                        message=f"All drivers declined order #{order_id[:8]} — needs manual assignment.",
                        ntype="order",
                        meta={"order_id": order_id, "kind": "restaurant"},
                    )
            except Exception:
                pass
        return {"ok": True, "reoffered_to": (next_driver or {}).get("id")}

    @new_router.post("/driver/splits/{split_id}/pickup")
    async def driver_pickup(split_id: str, body: OTPIn, user: dict = driver_dep):
        s = await _find_split(split_id)
        _check_driver_owns(s, user)
        if s.get("seller_preparation_status") != "ready_for_pickup":
            raise HTTPException(400, "Seller has not marked the order ready for pickup yet")
        if (body.otp or "").strip() != (s.get("seller_pickup_otp") or ""):
            raise HTTPException(400, "Invalid seller pickup OTP")
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {
                "pickup_status": "picked_up",
                "delivery_status": "picked_up",
                "proof_of_delivery_status": "pending",
                "picked_up_at": now_iso(),
                "updated_at": now_iso(),
            }},
        )
        try:
            await create_notification(
                user_id=s["seller_id"],
                message=f"Driver picked up order #{short(split_id)} — please confirm handover",
                ntype="order",
                meta={"split_id": split_id},
            )
        except Exception:
            pass
        return await _find_split(split_id)

    @new_router.post("/driver/splits/{split_id}/out-for-delivery")
    async def driver_out(split_id: str, user: dict = driver_dep):
        s = await _find_split(split_id)
        _check_driver_owns(s, user)
        if s.get("pickup_status") != "picked_up":
            raise HTTPException(400, "Mark pickup first")
        if s.get("seller_handover_status") != "handed_to_driver":
            raise HTTPException(400, "Seller has not confirmed handover yet")
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {"delivery_status": "out_for_delivery", "updated_at": now_iso()}},
        )
        return await _find_split(split_id)

    @new_router.post("/driver/splits/{split_id}/deliver")
    async def driver_deliver(split_id: str, body: DeliverIn, user: dict = driver_dep):
        s = await _find_split(split_id)
        _check_driver_owns(s, user)
        # Strict gating per spec
        if s.get("pickup_status") != "picked_up":
            raise HTTPException(400, "Pickup not confirmed")
        if s.get("seller_handover_status") != "handed_to_driver":
            raise HTTPException(400, "Seller handover not confirmed")
        if (body.otp or "").strip() != (s.get("customer_delivery_otp") or ""):
            raise HTTPException(400, "Invalid customer delivery OTP")
        if not body.signature_b64 or len(body.signature_b64) < 10:
            raise HTTPException(400, "Customer signature required")
        if not body.receiver_name.strip():
            raise HTTPException(400, "Receiver name required")
        now = now_iso()
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {
                "delivery_status": "delivered",
                "proof_of_delivery_status": "submitted",
                "signature_b64": body.signature_b64,
                "receiver_name": body.receiver_name.strip(),
                "delivered_at": now,
                "updated_at": now,
            }},
        )
        try:
            await create_notification(
                user_id=s["customer_id"],
                message=f"Your order from {s['shop_name']} has been delivered. Enjoy!",
                ntype="order",
                meta={"split_id": split_id, "order_id": s.get("order_id")},
            )
        except Exception:
            pass
        return await _find_split(split_id)

    @new_router.post("/driver/splits/{split_id}/cash-collected")
    async def driver_cash(split_id: str, user: dict = driver_dep):
        s = await _find_split(split_id)
        _check_driver_owns(s, user)
        if s.get("delivery_status") != "delivered":
            raise HTTPException(400, "Mark delivered first before collecting cash")
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {
                "payment_status": "collected_by_driver",
                "cash_handover_status": "pending",
                "cash_collected_at": now_iso(),
                "updated_at": now_iso(),
            }},
        )
        return await _find_split(split_id)

    @new_router.post("/driver/splits/{split_id}/delivery-failed")
    async def driver_failed(split_id: str, body: DeliveryFailedIn, user: dict = driver_dep):
        s = await _find_split(split_id)
        _check_driver_owns(s, user)
        # If picked up already → must return to seller
        next_return = s.get("pickup_status") == "picked_up"
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {
                "delivery_status": "delivery_failed",
                "failure_reason": body.reason,
                "failure_note": body.note or "",
                "return_status": "pending_return" if next_return else "not_required",
                "updated_at": now_iso(),
            }},
        )
        return await _find_split(split_id)

    @new_router.post("/driver/splits/{split_id}/return-to-seller")
    async def driver_return(split_id: str, user: dict = driver_dep):
        """Driver starts the return process: status becomes return_to_seller_pending.
        Seller must verify by entering return_otp via /seller/splits/{id}/return-received."""
        s = await _find_split(split_id)
        _check_driver_owns(s, user)
        if s.get("return_status") not in {"pending_return"}:
            raise HTTPException(400, "Return not applicable on this split")
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {
                "return_status": "return_to_seller_pending",
                "delivery_status": "return_to_seller_pending",
                "updated_at": now_iso(),
            }},
        )
        return await _find_split(split_id)

    # ---- Driver actions on a restaurant order (mirror of splits) ----
    @new_router.post("/driver/restaurant-orders/{order_id}/pickup")
    async def driver_pickup_rest(order_id: str, body: OTPIn, user: dict = driver_dep):
        o = await _find_rest_order(order_id)
        _check_driver_owns(o, user)
        if o.get("seller_preparation_status") != "ready_for_pickup":
            raise HTTPException(400, "Seller has not marked the order ready for pickup yet")
        if (body.otp or "").strip() != (o.get("seller_pickup_otp") or ""):
            raise HTTPException(400, "Invalid seller pickup OTP")
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {
                "pickup_status": "picked_up",
                "delivery_status": "picked_up",
                "proof_of_delivery_status": "pending",
                "picked_up_at": now_iso(),
                "updated_at": now_iso(),
            }},
        )
        return await _find_rest_order(order_id)

    @new_router.post("/driver/restaurant-orders/{order_id}/out-for-delivery")
    async def driver_out_rest(order_id: str, user: dict = driver_dep):
        o = await _find_rest_order(order_id)
        _check_driver_owns(o, user)
        if o.get("pickup_status") != "picked_up":
            raise HTTPException(400, "Mark pickup first")
        if o.get("seller_handover_status") != "handed_to_driver":
            raise HTTPException(400, "Seller has not confirmed handover yet")
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {"delivery_status": "out_for_delivery", "updated_at": now_iso()}},
        )
        return await _find_rest_order(order_id)

    @new_router.post("/driver/restaurant-orders/{order_id}/deliver")
    async def driver_deliver_rest(order_id: str, body: DeliverIn, user: dict = driver_dep):
        o = await _find_rest_order(order_id)
        _check_driver_owns(o, user)
        if o.get("pickup_status") != "picked_up":
            raise HTTPException(400, "Pickup not confirmed")
        if o.get("seller_handover_status") != "handed_to_driver":
            raise HTTPException(400, "Seller handover not confirmed")
        if (body.otp or "").strip() != (o.get("customer_delivery_otp") or ""):
            raise HTTPException(400, "Invalid customer delivery OTP")
        if not body.signature_b64 or len(body.signature_b64) < 10:
            raise HTTPException(400, "Customer signature required")
        if not body.receiver_name.strip():
            raise HTTPException(400, "Receiver name required")
        now = now_iso()
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {
                "delivery_status": "delivered",
                "proof_of_delivery_status": "submitted",
                "signature_b64": body.signature_b64,
                "receiver_name": body.receiver_name.strip(),
                "delivered_at": now,
                "status": "completed",  # legacy status field
                "updated_at": now,
            }},
        )
        return await _find_rest_order(order_id)

    @new_router.post("/driver/restaurant-orders/{order_id}/cash-collected")
    async def driver_cash_rest(order_id: str, user: dict = driver_dep):
        o = await _find_rest_order(order_id)
        _check_driver_owns(o, user)
        if o.get("delivery_status") != "delivered":
            raise HTTPException(400, "Mark delivered first")
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {
                "payment_status": "collected_by_driver",
                "cash_handover_status": "pending",
                "cash_collected_at": now_iso(),
                "updated_at": now_iso(),
            }},
        )
        return await _find_rest_order(order_id)

    @new_router.post("/driver/restaurant-orders/{order_id}/delivery-failed")
    async def driver_failed_rest(order_id: str, body: DeliveryFailedIn, user: dict = driver_dep):
        o = await _find_rest_order(order_id)
        _check_driver_owns(o, user)
        next_return = o.get("pickup_status") == "picked_up"
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {
                "delivery_status": "delivery_failed",
                "failure_reason": body.reason,
                "failure_note": body.note or "",
                "return_status": "pending_return" if next_return else "not_required",
                "updated_at": now_iso(),
            }},
        )
        return await _find_rest_order(order_id)

    @new_router.post("/driver/restaurant-orders/{order_id}/return-to-seller")
    async def driver_return_rest(order_id: str, user: dict = driver_dep):
        o = await _find_rest_order(order_id)
        _check_driver_owns(o, user)
        if o.get("return_status") not in {"pending_return"}:
            raise HTTPException(400, "Return not applicable")
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {
                "return_status": "return_to_seller_pending",
                "delivery_status": "return_to_seller_pending",
                "updated_at": now_iso(),
            }},
        )
        return await _find_rest_order(order_id)

    # ===========================================================================
    # CANCEL — seller / customer / admin
    # ===========================================================================
    async def _cancel_split(s: dict, by_role: str, by_user_id: str, reason: str = "") -> dict:
        """Cancel a split. Admin can do it anytime; seller/customer only while
        seller_preparation_status is in CANCELLABLE_PREP_STATUSES.
        If the item was already picked up, refuse — must use return-to-seller
        flow instead."""
        if s.get("delivery_status") in {"delivered", "returned_to_seller"}:
            raise HTTPException(400, "Order already finalized — cannot cancel")
        if s.get("pickup_status") == "picked_up":
            raise HTTPException(400, "Item already picked up by driver. Use the return-to-seller flow.")
        if by_role != "admin" and s.get("seller_preparation_status") not in CANCELLABLE_PREP_STATUSES:
            raise HTTPException(400, "Too late to cancel — order is already past 'ready for pickup'. Contact admin.")
        now = now_iso()
        update = {
            "seller_preparation_status": "cancelled",
            "delivery_status": "failed",
            "payout_status": "cancelled",
            "return_status": "not_required",
            "cancelled_at": now,
            "cancelled_by_role": by_role,
            "cancelled_by_user_id": by_user_id,
            "cancel_reason": (reason or "")[:500],
            "updated_at": now,
        }
        await db.seller_order_splits.update_one({"id": s["id"]}, {"$set": update})
        # Notify the other party
        try:
            if by_role == "customer":
                await create_notification(user_id=s["seller_id"], message=f"Customer cancelled order from {s.get('shop_name','')}", ntype="order", meta={"split_id": s["id"]})
            elif by_role == "seller":
                await create_notification(user_id=s["customer_id"], message=f"Seller cancelled your order from {s.get('shop_name','')}", ntype="order", meta={"split_id": s["id"]})
            elif by_role == "admin":
                await create_notification(user_id=s["seller_id"], message=f"Admin cancelled order from {s.get('shop_name','')}", ntype="order", meta={"split_id": s["id"]})
                await create_notification(user_id=s["customer_id"], message=f"Admin cancelled your order from {s.get('shop_name','')}", ntype="order", meta={"split_id": s["id"]})
        except Exception:
            pass
        # If ALL splits of the parent marketplace order are now cancelled, flip
        # the parent order's status too.
        if s.get("order_type") == "marketplace":
            sibs = await db.seller_order_splits.find({"order_id": s["order_id"]}, {"_id": 0, "seller_preparation_status": 1}).to_list(50)
            if sibs and all(x.get("seller_preparation_status") == "cancelled" for x in sibs):
                await db.orders.update_one({"id": s["order_id"]}, {"$set": {"status": "Cancelled", "updated_at": now}})
        return await db.seller_order_splits.find_one({"id": s["id"]}, {"_id": 0})

    async def _cancel_rest_order(o: dict, by_role: str, by_user_id: str, reason: str = "") -> dict:
        if o.get("delivery_status") in {"delivered", "returned_to_seller"}:
            raise HTTPException(400, "Order already finalized — cannot cancel")
        if o.get("pickup_status") == "picked_up":
            raise HTTPException(400, "Item already picked up by driver. Use the return-to-seller flow.")
        if by_role != "admin" and o.get("seller_preparation_status") not in CANCELLABLE_PREP_STATUSES:
            raise HTTPException(400, "Too late to cancel — order is already past 'ready for pickup'. Contact admin.")
        now = now_iso()
        update = {
            "seller_preparation_status": "cancelled",
            "delivery_status": "failed",
            "payout_status": "cancelled",
            "return_status": "not_required",
            "status": "cancelled",  # legacy status field
            "cancelled_at": now,
            "cancelled_by_role": by_role,
            "cancelled_by_user_id": by_user_id,
            "cancel_reason": (reason or "")[:500],
            "updated_at": now,
        }
        await db.restaurant_orders.update_one({"id": o["id"]}, {"$set": update})
        try:
            if by_role == "customer":
                await create_notification(user_id=o["seller_id"], message=f"Customer cancelled order at {o.get('restaurant_name','')}", ntype="order", meta={"order_id": o["id"], "kind": "restaurant"})
            elif by_role == "seller":
                await create_notification(user_id=o["customer_id"], message=f"Restaurant cancelled your order ({o.get('restaurant_name','')})", ntype="order", meta={"order_id": o["id"], "kind": "restaurant"})
            elif by_role == "admin":
                await create_notification(user_id=o["seller_id"], message=f"Admin cancelled order at {o.get('restaurant_name','')}", ntype="order", meta={"order_id": o["id"], "kind": "restaurant"})
                await create_notification(user_id=o["customer_id"], message=f"Admin cancelled your order ({o.get('restaurant_name','')})", ntype="order", meta={"order_id": o["id"], "kind": "restaurant"})
        except Exception:
            pass
        return await db.restaurant_orders.find_one({"id": o["id"]}, {"_id": 0})

    # ---- Seller cancels ----
    @new_router.post("/seller/splits/{split_id}/cancel")
    async def seller_cancel_split(split_id: str, body: CancelBody, user: dict = seller_dep):
        s = await _find_split(split_id)
        _check_seller_owns(s, user)
        return await _cancel_split(s, "seller", user["id"], body.reason or "")

    @new_router.post("/seller/restaurant-orders/{order_id}/cancel")
    async def seller_cancel_rest(order_id: str, body: CancelBody, user: dict = seller_dep):
        o = await _find_rest_order(order_id)
        _check_seller_owns(o, user)
        return await _cancel_rest_order(o, "seller", user["id"], body.reason or "")

    # ---- Customer cancels ----
    @new_router.post("/customer/splits/{split_id}/cancel")
    async def customer_cancel_split(split_id: str, body: CancelBody, user: dict = Depends(get_current_user)):
        s = await _find_split(split_id)
        if s.get("customer_id") != user["id"]:
            raise HTTPException(403, "Not your order")
        return await _cancel_split(s, "customer", user["id"], body.reason or "")

    @new_router.post("/customer/orders/{order_id}/cancel")
    async def customer_cancel_order(order_id: str, body: CancelBody, user: dict = Depends(get_current_user)):
        """Cancel an entire marketplace order — only succeeds if EVERY split is
        still cancellable. Returns per-split outcomes."""
        order = await db.orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            raise HTTPException(404, "Order not found")
        if order.get("customer_id") != user["id"]:
            raise HTTPException(403, "Not your order")
        splits = await db.seller_order_splits.find({"order_id": order_id}, {"_id": 0}).to_list(50)
        if not splits:
            raise HTTPException(400, "Order has no splits (legacy order)")
        results = []
        for s in splits:
            try:
                r = await _cancel_split(s, "customer", user["id"], body.reason or "")
                results.append({"split_id": s["id"], "ok": True, "split": r})
            except HTTPException as exc:
                results.append({"split_id": s["id"], "ok": False, "error": exc.detail})
        return {"order_id": order_id, "results": results}

    @new_router.post("/customer/restaurant-orders/{order_id}/cancel")
    async def customer_cancel_rest(order_id: str, body: CancelBody, user: dict = Depends(get_current_user)):
        o = await _find_rest_order(order_id)
        if o.get("customer_id") != user["id"]:
            raise HTTPException(403, "Not your order")
        return await _cancel_rest_order(o, "customer", user["id"], body.reason or "")

    # ---- Admin cancels (anytime) ----
    @new_router.post("/admin/order-splits/{split_id}/cancel")
    async def admin_cancel_split(split_id: str, body: CancelBody, user: dict = admin_dep):
        s = await _find_split(split_id)
        return await _cancel_split(s, "admin", user["id"], body.reason or "")

    @new_router.post("/admin/restaurant-orders/{order_id}/cancel")
    async def admin_cancel_rest(order_id: str, body: CancelBody, user: dict = admin_dep):
        o = await _find_rest_order(order_id)
        return await _cancel_rest_order(o, "admin", user["id"], body.reason or "")

    # ===========================================================================
    # CUSTOMER — read own splits (with full details, customer is the owner)
    # ===========================================================================
    @new_router.get("/customer/orders/{order_id}/splits")
    async def customer_order_splits(order_id: str, user: dict = Depends(get_current_user)):
        order = await db.orders.find_one({"id": order_id}, {"_id": 0})
        if not order or order.get("customer_id") != user["id"]:
            raise HTTPException(404, "Order not found")
        return await db.seller_order_splits.find({"order_id": order_id}, {"_id": 0}).sort("created_at", -1).to_list(50)

    # Replace module-level router
    global router
    router = new_router


# ---------------------------------------------------------------------------
# Internal helpers (used by endpoints above)
# ---------------------------------------------------------------------------
async def _driver_cash_pending(driver_id: str) -> float:
    cur = db.seller_order_splits.find(
        {"driver_id": driver_id, "cash_handover_status": "pending"},
        {"_id": 0, "order_total_usd": 1},
    )
    splits = await cur.to_list(500)
    total = sum(float(s.get("order_total_usd", 0)) for s in splits)
    cur2 = db.restaurant_orders.find(
        {"driver_id": driver_id, "cash_handover_status": "pending"},
        {"_id": 0, "order_total_usd": 1},
    )
    rests = await cur2.to_list(500)
    total += sum(float(o.get("order_total_usd", 0)) for o in rests)
    return round(total, 2)


async def _maybe_mark_rest_ready(order_id: str) -> None:
    o = await db.restaurant_orders.find_one({"id": order_id}, {"_id": 0})
    if not o:
        return
    if o.get("payout_status") in {"ready_for_payout", "pending_payout", "paid", "paused", "cancelled"}:
        return
    ok = (
        o.get("pickup_status") == "picked_up"
        and o.get("seller_handover_status") == "handed_to_driver"
        and o.get("delivery_status") == "delivered"
        and o.get("proof_of_delivery_status") == "submitted"
        and o.get("payment_status") == "received_by_admin"
        and o.get("cash_handover_status") == "received"
        and o.get("dispute_status") in {"none", "resolved"}
        and o.get("return_status") in {"not_required"}
    )
    if ok:
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {"payout_status": "ready_for_payout", "updated_at": now_iso()}},
        )


async def _compute_seller_wallet(seller_id: str) -> dict:
    """Aggregate wallet buckets for a seller.

    Returns USD amounts (seller_earning_usd) per bucket:
      pending_cash_collection — splits/orders with cash not yet collected
      cash_with_driver        — collected but not yet handed to admin
      ready_for_payout
      pending_payout
      paid_total
      commission_deducted     — sum of platform_commission_usd over delivered orders
      returned_or_failed
    """
    splits = await db.seller_order_splits.find(
        {"seller_id": seller_id}, {"_id": 0},
    ).to_list(5000)
    rests = await db.restaurant_orders.find(
        {"seller_id": seller_id}, {"_id": 0},
    ).to_list(5000)

    def amt(rows, cond):
        return round(sum(float(r.get("seller_earning_usd", 0)) for r in rows if cond(r)), 2)

    def total_amt(rows, cond):
        return round(sum(float(r.get("order_total_usd", 0)) for r in rows if cond(r)), 2)

    all_rows = splits + rests

    pending_cash_collection = total_amt(
        all_rows,
        lambda r: r.get("payment_status") == "pending_collection"
        and r.get("delivery_status") in {"unassigned", "assigned", "pending_pickup", "picked_up", "out_for_delivery"},
    )
    cash_with_driver = total_amt(
        all_rows,
        lambda r: r.get("cash_handover_status") == "pending",
    )
    ready_for_payout = amt(all_rows, lambda r: r.get("payout_status") == "ready_for_payout")
    pending_payout = amt(all_rows, lambda r: r.get("payout_status") == "pending_payout")
    paid_total = amt(all_rows, lambda r: r.get("payout_status") == "paid")
    commission_deducted = round(sum(
        float(r.get("platform_commission_usd", 0)) for r in all_rows
        if r.get("delivery_status") == "delivered"
    ), 2)
    returned_or_failed = total_amt(
        all_rows,
        lambda r: r.get("delivery_status") in {"returned_to_seller", "delivery_failed", "failed"}
        or r.get("return_status") in {"returned", "return_disputed"},
    )

    return {
        "currency": "USD",
        "pending_cash_collection": pending_cash_collection,
        "cash_with_driver": cash_with_driver,
        "ready_for_payout": ready_for_payout,
        "pending_payout": pending_payout,
        "paid_total": paid_total,
        "commission_deducted": commission_deducted,
        "returned_or_failed": returned_or_failed,
        "counts": {
            "ready_splits": sum(1 for r in splits if r.get("payout_status") == "ready_for_payout"),
            "ready_restaurant_orders": sum(1 for r in rests if r.get("payout_status") == "ready_for_payout"),
        },
    }


async def _generate_payouts(seller_id: Optional[str]) -> dict:
    """Create a `seller_payouts` doc per seller from all their
    `ready_for_payout` splits + restaurant orders.

    Splits with dispute_status='opened' are excluded (paused).
    """
    q_split: dict = {"payout_status": "ready_for_payout"}
    q_rest: dict = {"payout_status": "ready_for_payout"}
    if seller_id:
        q_split["seller_id"] = seller_id
        q_rest["seller_id"] = seller_id
    splits = await db.seller_order_splits.find(q_split, {"_id": 0}).to_list(5000)
    rests = await db.restaurant_orders.find(q_rest, {"_id": 0}).to_list(5000)

    # Group by seller
    by_seller: dict[str, dict] = {}
    for s in splits:
        sid = s.get("seller_id")
        if not sid:
            continue
        bucket = by_seller.setdefault(sid, {"splits": [], "rests": [], "amount": 0.0, "commission": 0.0})
        bucket["splits"].append(s["id"])
        bucket["amount"] += float(s.get("seller_earning_usd", 0))
        bucket["commission"] += float(s.get("platform_commission_usd", 0))
    for o in rests:
        sid = o.get("seller_id")
        if not sid:
            continue
        bucket = by_seller.setdefault(sid, {"splits": [], "rests": [], "amount": 0.0, "commission": 0.0})
        bucket["rests"].append(o["id"])
        bucket["amount"] += float(o.get("seller_earning_usd", 0))
        bucket["commission"] += float(o.get("platform_commission_usd", 0))

    created = []
    now = now_iso()
    for sid, bucket in by_seller.items():
        if not bucket["splits"] and not bucket["rests"]:
            continue
        seller = await db.users.find_one({"id": sid}, {"_id": 0, "name": 1, "email": 1})
        payout = {
            "id": str(uuid.uuid4()),
            "seller_id": sid,
            "seller_name": (seller or {}).get("name", ""),
            "seller_email": (seller or {}).get("email", ""),
            "split_ids": bucket["splits"],
            "restaurant_order_ids": bucket["rests"],
            "amount_usd": round(bucket["amount"], 2),
            "commission_deducted_usd": round(bucket["commission"], 2),
            "status": "pending_payout",
            "created_at": now,
            "updated_at": now,
            "paid_at": None,
            "paid_by": None,
        }
        await db.seller_payouts.insert_one(payout)
        payout.pop("_id", None)
        if bucket["splits"]:
            await db.seller_order_splits.update_many(
                {"id": {"$in": bucket["splits"]}},
                {"$set": {"payout_status": "pending_payout", "payout_id": payout["id"], "updated_at": now}},
            )
        if bucket["rests"]:
            await db.restaurant_orders.update_many(
                {"id": {"$in": bucket["rests"]}},
                {"$set": {"payout_status": "pending_payout", "payout_id": payout["id"], "updated_at": now}},
            )
        created.append(payout)
        try:
            await create_notification(
                user_id=sid,
                message=f"A payout of USD {payout['amount_usd']:.2f} is pending — admin will pay you shortly.",
                ntype="commission",
                meta={"payout_id": payout["id"]},
            )
        except Exception:
            pass
    return {"created": len(created), "payouts": created}


# ---------------------------------------------------------------------------
# Backfill — runs at startup, idempotent
# ---------------------------------------------------------------------------
async def backfill_existing_orders():
    """Add default COD fields to any pre-existing marketplace order that has
    no `seller_order_splits` yet, and any restaurant order missing the new
    COD fields."""
    # Marketplace: only create splits for orders that don't have any yet.
    cursor = db.orders.find({}, {"_id": 0, "id": 1})
    async for o in cursor:
        existing = await db.seller_order_splits.count_documents({"order_id": o["id"]})
        if existing > 0:
            continue
        full = await db.orders.find_one({"id": o["id"]}, {"_id": 0})
        try:
            await create_marketplace_splits(full)
        except Exception as e:
            log.warning(f"backfill split for order {o['id']} failed: {e}")

    # Restaurant orders: add COD fields if missing.
    cursor2 = db.restaurant_orders.find(
        {"payment_method": {"$ne": PAYMENT_METHOD_COD}},
        {"_id": 0, "id": 1},
    )
    async for o in cursor2:
        full = await db.restaurant_orders.find_one({"id": o["id"]}, {"_id": 0})
        if not full:
            continue
        try:
            cod = await initialize_restaurant_order_cod(full)
            await db.restaurant_orders.update_one({"id": o["id"]}, {"$set": cod})
        except Exception as e:
            log.warning(f"backfill restaurant order {o['id']} failed: {e}")


# ---------------------------------------------------------------------------
# Index creation + driver seed (called from server.seed_production)
# ---------------------------------------------------------------------------
async def seed_cod():
    await db.seller_order_splits.create_index("id", unique=True)
    await db.seller_order_splits.create_index([("seller_id", 1), ("created_at", -1)])
    await db.seller_order_splits.create_index([("driver_id", 1), ("delivery_status", 1)])
    await db.seller_order_splits.create_index([("order_id", 1)])
    await db.seller_order_splits.create_index([("payout_status", 1)])

    await db.seller_payouts.create_index("id", unique=True)
    await db.seller_payouts.create_index([("seller_id", 1), ("created_at", -1)])

    await db.driver_cash_receipts.create_index("id", unique=True)
    await db.driver_cash_receipts.create_index([("driver_id", 1), ("received_at", -1)])

    # Demo driver
    demo_email = "driver@demo.com"
    if not await db.users.find_one({"email": demo_email}):
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": demo_email,
            "name": "Demo Driver",
            "phone": "+211900000001",
            "role": "driver",
            "settings": {},
            "email_verified": True,
            "is_active": True,
            "must_change_password": False,
            "password_hash": hash_password("1234"),
            "created_at": now_iso(),
        })
        if log:
            log.info("🚚 Seeded demo driver: driver@demo.com / 1234")
