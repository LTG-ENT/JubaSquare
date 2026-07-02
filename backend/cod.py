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

import os
import uuid
import secrets
import logging
from datetime import datetime, timezone
from typing import List, Optional, Literal, Any

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field, EmailStr

log = logging.getLogger(__name__)


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


async def _enrich_rate(rows: list[dict]) -> list[dict]:
    """Attach `exchange_rate_ssp` to each row using its seller_id.
    Used for splits / restaurant-orders responses so the driver and admin UIs
    can format totals with the right seller-specific rate."""
    if not rows:
        return rows
    seller_ids = list({r.get("seller_id") for r in rows if r.get("seller_id")})
    settings = await get_settings()
    global_rate = float(settings.get("global_rate", 600.0))
    rates: dict[str, float] = {}
    if seller_ids:
        recs = await db.exchange_rates.find(
            {"seller_id": {"$in": seller_ids}}, {"_id": 0},
        ).to_list(2000)
        rates = {r["seller_id"]: float(r.get("rate", global_rate)) for r in recs}
    for r in rows:
        sid = r.get("seller_id")
        r["exchange_rate_ssp"] = rates.get(sid, global_rate) if sid else global_rate
    return rows


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
    "assignment_status": "unassigned",  # unassigned | offered_to_driver | accepted_by_driver | rejected_by_driver | manually_assigned
    "driver_response_status": None,  # pending | accepted | rejected
    "driver_accepted_at": None,
    "driver_rejected_at": None,
    "driver_reject_reason": None,
    "declined_driver_ids": [],  # List of driver IDs who rejected this delivery
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

# Fields that must NEVER reach the customer (seller/driver OTPs).
# Customer should only see customer_delivery_otp.
CUSTOMER_PRIVATE_KEYS = (
    "seller_pickup_otp",
    "return_otp",
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


def redact_for_customer(doc: dict) -> dict:
    """Remove seller/driver OTPs from a doc before returning to customer.
    Returns the same dict (mutated). Keep customer_delivery_otp intact."""
    if not doc:
        return doc
    for k in CUSTOMER_PRIVATE_KEYS:
        if k in doc:
            doc[k] = None
    return doc


def redact_many_for_customer(rows: list) -> list:
    for r in rows:
        redact_for_customer(r)
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
        b.get("shop_id"): {
            "fee_usd": float(b.get("fee_usd", 0)),
            "pickup_area": b.get("pickup_area", ""),
            "delivery_area": b.get("delivery_area", ""),
        }
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
        delivery_info = delivery_by_shop.get(shop_id, {"fee_usd": 0.0, "pickup_area": "", "delivery_area": ""})
        delivery_fee = delivery_info["fee_usd"]
        pickup_area = delivery_info["pickup_area"]
        delivery_area = delivery_info["delivery_area"]
        
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
            "pickup_area": pickup_area,  # NEW: Store pickup area for pricing reference
            "delivery_area": delivery_area,  # NEW: Store delivery area for pricing reference
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
    picture_b64: str | None = None  # Optional photo of delivered package
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


class PayoutOTPConfirmIn(BaseModel):
    otp: str = Field(min_length=4, max_length=8)


class PayoutFrequencyIn(BaseModel):
    payout_frequency: Optional[Literal["daily", "weekly", "monthly"]] = None  # None = use global default


class DriverAcceptRejectIn(BaseModel):
    action: Literal["accept", "reject"]
    reject_reason: Optional[str] = None


class DeliveryPricingRuleIn(BaseModel):
    pickup_area: str = Field(min_length=1, max_length=100)
    delivery_area: str = Field(min_length=1, max_length=100)
    order_type: Literal["marketplace", "restaurant", "all"] = "all"
    shop_id: Optional[str] = None
    restaurant_id: Optional[str] = None
    delivery_fee_usd: float = Field(ge=0)
    active: bool = True


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
        await _enrich_rate(rows)
        return rows

    @new_router.get("/admin/order-splits/{split_id}")
    async def get_split(split_id: str, _: dict = admin_dep):
        s = await _find_split(split_id)
        await _enrich_rate([s])
        return s

    @new_router.post("/admin/order-splits/{split_id}/assign-driver")
    async def assign_driver_to_split(split_id: str, body: AssignDriverIn, _: dict = admin_dep):
        """Admin assigns (or re-assigns) driver to a split. Re-assignment is
        allowed as long as the order has not yet been picked up by a driver."""
        split = await _find_split(split_id)
        # Block re-assignment only once the driver has physically picked it up.
        if split.get("pickup_status") == "picked_up":
            raise HTTPException(400, "Cannot re-assign — order has already been picked up by the driver")
        
        driver = await db.users.find_one({"id": body.driver_id, "role": "driver"}, {"_id": 0, "name": 1, "id": 1})
        if not driver:
            raise HTTPException(404, "Driver not found")
        
        now = now_iso()
        update = {
            "driver_id": driver["id"],
            "driver_name": driver["name"],
            "assigned_at": now,
            "assignment_status": "offered_to_driver",  # Driver must accept
            "driver_response_status": "pending",
            "delivery_status": "offered",
            "updated_at": now,
        }
        await db.seller_order_splits.update_one({"id": split_id}, {"$set": update})
        
        # Update driver's last_offered_at for round-robin
        await db.users.update_one(
            {"id": driver["id"]},
            {"$set": {"last_offered_at": now}}
        )
        
        try:
            await create_notification(
                user_id=driver["id"],
                message=f"New delivery request: {split['shop_name']} → {split.get('customer_name', '')}. Please accept or reject.",
                ntype="delivery_request",
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
        rows = await db.restaurant_orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        await _enrich_rate(rows)
        return rows

    @new_router.post("/admin/restaurant-orders/{order_id}/assign-driver")
    async def assign_driver_to_rest(order_id: str, body: AssignDriverIn, _: dict = admin_dep):
        """Admin assigns (or re-assigns) driver to a restaurant order. Re-assignment
        is allowed as long as the order has not yet been picked up."""
        o = await _find_rest_order(order_id)
        if o.get("pickup_status") == "picked_up":
            raise HTTPException(400, "Cannot re-assign — order has already been picked up by the driver")
        
        driver = await db.users.find_one({"id": body.driver_id, "role": "driver"}, {"_id": 0, "name": 1, "id": 1})
        if not driver:
            raise HTTPException(404, "Driver not found")
        
        now = now_iso()
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": {
                "driver_id": driver["id"],
                "driver_name": driver["name"],
                "assigned_at": now,
                "assignment_status": "offered_to_driver",
                "driver_response_status": "pending",
                "delivery_status": "offered",
                "updated_at": now,
            }},
        )
        
        # Update driver's last_offered_at for round-robin
        await db.users.update_one(
            {"id": driver["id"]},
            {"$set": {"last_offered_at": now}}
        )
        
        try:
            await create_notification(
                user_id=driver["id"],
                message=f"New delivery request: {o.get('restaurant_name', 'Restaurant')} → {o.get('customer_name', 'Customer')}. Please accept or reject.",
                ntype="delivery_request",
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

    @new_router.post("/admin/payouts/{payout_id}/generate-otp")
    async def generate_payout_collection_otp(payout_id: str, admin: dict = admin_dep):
        """Admin clicks 'Generate OTP' on a payout. Backend generates a 4-digit OTP
        and stores it on the payout doc. The seller will say this OTP to the admin
        when they show up in person; admin enters it via /confirm-otp to mark paid.
        OTP is also sent to the seller as a notification so they can find it."""
        p = await db.seller_payouts.find_one({"id": payout_id})
        if not p:
            raise HTTPException(404, "Payout not found")
        if p.get("status") == "paid":
            raise HTTPException(400, "Payout is already paid")
        otp = gen_otp()  # 4-digit
        now = now_iso()
        await db.seller_payouts.update_one(
            {"id": payout_id},
            {"$set": {
                "collection_otp": otp,
                "collection_otp_generated_at": now,
                "collection_otp_generated_by": admin["id"],
                "updated_at": now,
            }},
        )
        try:
            await create_notification(
                user_id=p["seller_id"],
                message=f"Payout collection OTP: {otp} — show this to the admin when you collect USD {p['amount_usd']:.2f}.",
                ntype="commission",
                meta={"payout_id": payout_id, "otp": otp},
            )
        except Exception:
            pass
        return {"ok": True, "otp": otp}

    @new_router.post("/admin/payouts/{payout_id}/confirm-otp")
    async def confirm_payout_collection_otp(payout_id: str, body: PayoutOTPConfirmIn, admin: dict = admin_dep):
        """Admin enters the OTP the seller said. If it matches the OTP we stored,
        the payout flips to 'paid'."""
        p = await db.seller_payouts.find_one({"id": payout_id})
        if not p:
            raise HTTPException(404, "Payout not found")
        if p.get("status") == "paid":
            return {"ok": True, "already_paid": True}
        stored = p.get("collection_otp")
        if not stored:
            raise HTTPException(400, "No OTP generated for this payout yet")
        if body.otp.strip() != stored:
            raise HTTPException(400, "OTP does not match. Ask the seller to re-check.")
        now = now_iso()
        await db.seller_payouts.update_one(
            {"id": payout_id},
            {"$set": {
                "status": "paid",
                "paid_at": now,
                "paid_by": admin["id"],
                "paid_via": "in_person_otp",
                "updated_at": now,
            }},
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
                message=f"Payout USD {p['amount_usd']:.2f} collected in person. Receipt is in your wallet.",
                ntype="commission",
                meta={"payout_id": payout_id},
            )
        except Exception:
            pass
        return await db.seller_payouts.find_one({"id": payout_id}, {"_id": 0})

    @new_router.put("/admin/shops/{shop_id}/payout-frequency")
    async def admin_set_shop_payout_frequency(shop_id: str, body: PayoutFrequencyIn, _: dict = admin_dep):
        """Set per-shop payout cadence. None = use global default."""
        shop = await db.shops.find_one({"id": shop_id})
        if not shop:
            raise HTTPException(404, "Shop not found")
        if body.payout_frequency is None:
            await db.shops.update_one({"id": shop_id}, {"$unset": {"payout_frequency": ""}})
        else:
            await db.shops.update_one({"id": shop_id}, {"$set": {"payout_frequency": body.payout_frequency}})
        return await db.shops.find_one({"id": shop_id}, {"_id": 0})

    @new_router.put("/admin/restaurants/{restaurant_id}/payout-frequency")
    async def admin_set_restaurant_payout_frequency(restaurant_id: str, body: PayoutFrequencyIn, _: dict = admin_dep):
        """Set per-restaurant payout cadence. None = use global default."""
        rest = await db.restaurants.find_one({"id": restaurant_id})
        if not rest:
            raise HTTPException(404, "Restaurant not found")
        if body.payout_frequency is None:
            await db.restaurants.update_one({"id": restaurant_id}, {"$unset": {"payout_frequency": ""}})
        else:
            await db.restaurants.update_one({"id": restaurant_id}, {"$set": {"payout_frequency": body.payout_frequency}})
        return await db.restaurants.find_one({"id": restaurant_id}, {"_id": 0})

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
        
        now = now_iso()
        update_fields = {
            "seller_preparation_status": "accepted",
            "updated_at": now,
        }
        
        # NEW: If no driver assigned yet, broadcast to all drivers
        if not s.get("driver_id"):
            update_fields.update({
                "assignment_status": "offered_to_all_drivers",
                "delivery_status": "offered",
                "driver_response_status": "pending",
            })
        
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": update_fields},
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
        
        now = now_iso()
        update_fields = {
            "seller_preparation_status": "accepted",
            "updated_at": now,
        }
        
        # NEW: If no driver assigned yet, broadcast to all drivers
        if not o.get("driver_id"):
            update_fields.update({
                "assignment_status": "offered_to_all_drivers",
                "delivery_status": "offered",
                "driver_response_status": "pending",
            })
        
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": update_fields},
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
        await _enrich_rate(splits)
        await _enrich_rate(rest_orders)
        return {"splits": splits, "restaurant_orders": rest_orders}

    @new_router.get("/driver/delivery-requests")
    async def driver_delivery_requests(user: dict = driver_dep):
        """Get pending delivery requests that driver needs to accept/reject.
        
        Returns:
        - Orders offered specifically to this driver (assignment_status='offered_to_driver')
        - Orders offered to ALL drivers (assignment_status='offered_to_all_drivers')
        """
        # Find splits offered specifically to this driver
        splits_direct = await db.seller_order_splits.find({
            "driver_id": user["id"],
            "assignment_status": "offered_to_driver",
            "driver_response_status": "pending"
        }, {"_id": 0}).sort("assigned_at", -1).to_list(500)
        
        # Find splits offered to ALL drivers (broadcast/pool)
        splits_broadcast = await db.seller_order_splits.find({
            "assignment_status": "offered_to_all_drivers",
            "driver_response_status": "pending",
            "seller_preparation_status": "accepted"  # Only show if seller accepted
        }, {"_id": 0}).sort("created_at", -1).to_list(500)
        
        # Find restaurant orders offered specifically to this driver
        rest_direct = await db.restaurant_orders.find({
            "driver_id": user["id"],
            "assignment_status": "offered_to_driver",
            "driver_response_status": "pending"
        }, {"_id": 0}).sort("assigned_at", -1).to_list(500)
        
        # Find restaurant orders offered to ALL drivers (broadcast/pool)
        rest_broadcast = await db.restaurant_orders.find({
            "assignment_status": "offered_to_all_drivers",
            "driver_response_status": "pending",
            "seller_preparation_status": "accepted"  # Only show if seller accepted
        }, {"_id": 0}).sort("created_at", -1).to_list(500)
        
        # Combine and sanitize
        splits = splits_direct + splits_broadcast
        rest_orders = rest_direct + rest_broadcast
        
        # Sanitize: hide commission & seller_earning for drivers
        for s in splits:
            for k in ("commission_rate", "platform_commission_usd", "seller_earning_usd"):
                s.pop(k, None)
        for o in rest_orders:
            for k in ("commission_rate", "platform_commission_usd", "seller_earning_usd"):
                o.pop(k, None)
        await _enrich_rate(splits)
        await _enrich_rate(rest_orders)
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
        await _enrich_rate([s])
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
        await _enrich_rate([o])
        return o

    # ---- Driver actions on a split ----
    @new_router.post("/driver/restaurant-orders/{order_id}/accept-offer")
    async def driver_accept_offer_rest(order_id: str, user: dict = driver_dep):
        """Driver accepts a pending offered restaurant order.
        
        Handles both:
        - Direct offers (assignment_status='offered_to_driver' with specific driver_id)
        - Broadcast offers (assignment_status='offered_to_all_drivers')
        """
        o = await _find_rest_order(order_id)
        
        # Check if this is a broadcast offer or direct offer
        is_broadcast = o.get("assignment_status") == "offered_to_all_drivers"
        
        if is_broadcast:
            # For broadcast: Any driver can accept, first come first served
            if o.get("driver_response_status") != "pending":
                raise HTTPException(400, f"This order has already been claimed by another driver")
        else:
            # For direct offer: Must be offered to this specific driver
            _check_driver_owns(o, user)
            if o.get("delivery_status") != "offered":
                raise HTTPException(400, f"Order is not in 'offered' state (current: {o.get('delivery_status')})")
        
        now = now_iso()
        
        # Atomic update with race condition handling
        result = await db.restaurant_orders.update_one(
            {
                "id": order_id,
                "driver_response_status": "pending"  # Ensures only one driver can claim
            },
            {"$set": {
                "driver_id": user["id"],  # Assign to this driver
                "driver_name": user.get("name", "Unknown"),
                "assignment_status": "accepted_by_driver",
                "driver_response_status": "accepted",
                "delivery_status": "assigned",
                "pickup_status": "pending_pickup",
                "driver_accepted_at": now,
                "updated_at": now,
            }},
        )
        
        # Check if update succeeded (race condition check)
        if result.modified_count == 0:
            raise HTTPException(400, "This order was just claimed by another driver. Please check for other available orders.")
        
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

    # ---- Driver accept/decline for marketplace splits ----
    @new_router.post("/driver/splits/{split_id}/accept-offer")
    async def driver_accept_offer_split(split_id: str, user: dict = driver_dep):
        """Driver accepts a pending offered split — flips assignment_status to accepted_by_driver.
        
        Handles both:
        - Direct offers (assignment_status='offered_to_driver' with specific driver_id)
        - Broadcast offers (assignment_status='offered_to_all_drivers')
        """
        s = await _find_split(split_id)
        
        # Check if this is a broadcast offer or direct offer
        is_broadcast = s.get("assignment_status") == "offered_to_all_drivers"
        
        if is_broadcast:
            # For broadcast: Any driver can accept, first come first served
            if s.get("driver_response_status") != "pending":
                raise HTTPException(400, f"This order has already been claimed by another driver")
        else:
            # For direct offer: Must be offered to this specific driver
            _check_driver_owns(s, user)
            if s.get("assignment_status") != "offered_to_driver":
                raise HTTPException(400, f"Split is not offered (current: {s.get('assignment_status')})")
        
        now = now_iso()
        
        # Atomic update with race condition handling
        result = await db.seller_order_splits.update_one(
            {
                "id": split_id,
                "driver_response_status": "pending"  # Ensures only one driver can claim
            },
            {"$set": {
                "driver_id": user["id"],  # Assign to this driver
                "driver_name": user.get("name", "Unknown"),
                "assignment_status": "accepted_by_driver",
                "driver_response_status": "accepted",
                "driver_accepted_at": now,
                "delivery_status": "assigned",
                "pickup_status": "pending_pickup",
                "updated_at": now,
            }},
        )
        
        # Check if update succeeded (race condition check)
        if result.modified_count == 0:
            raise HTTPException(400, "This order was just claimed by another driver. Please check for other available orders.")
        
        # Create audit log
        try:
            await db.audit_logs.insert_one({
                "id": str(uuid.uuid4()),
                "action": "driver_accepted",
                "entity_type": "seller_order_split",
                "entity_id": split_id,
                "order_id": s.get("order_id"),
                "user_id": user["id"],
                "user_role": "driver",
                "user_email": user.get("email"),
                "timestamp": now,
                "notes": f"Driver {user.get('name', 'Unknown')} accepted delivery" + (" (from broadcast pool)" if is_broadcast else ""),
                "_id_": None,
            })
        except Exception as e:
            print(f"Audit log failed: {e}")
        
        try:
            await create_notification(
                user_id=s.get("seller_id"),
                message=f"Driver accepted delivery for order from {s.get('shop_name', 'your shop')}",
                ntype="order",
                meta={"split_id": split_id, "order_id": s.get("order_id")},
            )
        except Exception:
            pass
        
        return await _find_split(split_id)

    @new_router.post("/driver/splits/{split_id}/decline-offer")
    async def driver_decline_offer_split(split_id: str, body: DriverAcceptRejectIn, user: dict = driver_dep):
        """Driver declines the offered split. Re-offer to next driver."""
        s = await _find_split(split_id)
        _check_driver_owns(s, user)
        if s.get("assignment_status") != "offered_to_driver":
            raise HTTPException(400, f"Split is not offered (current: {s.get('assignment_status')})")
        
        # Mark as rejected and add to declined list
        declined_ids = s.get("declined_driver_ids", [])
        if user["id"] not in declined_ids:
            declined_ids.append(user["id"])
        
        now = now_iso()
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": {
                "assignment_status": "rejected_by_driver",
                "driver_response_status": "rejected",
                "driver_rejected_at": now,
                "driver_reject_reason": body.reject_reason or "No reason provided",
                "declined_driver_ids": declined_ids,
                "driver_id": None,
                "driver_name": None,
                "delivery_status": "needs_driver_assignment",
                "updated_at": now,
            }},
        )
        
        # Try to assign to next driver (round-robin excluding declined drivers)
        next_driver = await _next_round_robin_driver(declined_by=declined_ids)
        if next_driver:
            await db.seller_order_splits.update_one(
                {"id": split_id},
                {"$set": {
                    "driver_id": next_driver["id"],
                    "driver_name": next_driver["name"],
                    "assigned_at": now,
                    "assignment_status": "offered_to_driver",
                    "driver_response_status": "pending",
                    "delivery_status": "offered",
                    "updated_at": now,
                }},
            )
            await db.users.update_one(
                {"id": next_driver["id"]},
                {"$set": {"last_offered_at": now}}
            )
            try:
                await create_notification(
                    user_id=next_driver["id"],
                    message=f"New delivery request: {s.get('shop_name', 'Shop')} → {s.get('customer_name', 'Customer')}",
                    ntype="delivery_request",
                    meta={"split_id": split_id, "order_type": "marketplace"},
                )
            except Exception:
                pass
        else:
            # No drivers left - needs manual assignment
            await db.seller_order_splits.update_one(
                {"id": split_id},
                {"$set": {"assignment_status": "needs_manual_assignment"}},
            )
            try:
                admins = await db.users.find({"role": "admin"}, {"_id": 0, "id": 1}).to_list(50)
                for a in admins:
                    await create_notification(
                        user_id=a["id"],
                        message=f"All drivers declined split #{split_id[:8]} — needs manual assignment.",
                        ntype="order",
                        meta={"split_id": split_id, "order_type": "marketplace"},
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
        
        # Build update dict
        update_dict = {
            "delivery_status": "delivered",
            "proof_of_delivery_status": "submitted",
            "signature_b64": body.signature_b64,
            "receiver_name": body.receiver_name.strip(),
            "delivered_at": now,
            "updated_at": now,
        }
        
        # Add picture if provided
        if body.picture_b64:
            update_dict["delivery_picture_b64"] = body.picture_b64
        
        # Auto-collect cash for COD orders
        if s.get("payment_method") == "cash_on_delivery":
            update_dict["payment_status"] = "collected_by_driver"
            update_dict["cash_handover_status"] = "pending"
            update_dict["cash_collected_at"] = now
        
        await db.seller_order_splits.update_one(
            {"id": split_id},
            {"$set": update_dict},
        )
        
        # Create audit log
        try:
            await db.audit_logs.insert_one({
                "id": str(uuid.uuid4()),
                "action": "delivered",
                "entity_type": "seller_order_split",
                "entity_id": split_id,
                "order_id": s.get("order_id"),
                "user_id": user["id"],
                "user_role": "driver",
                "user_email": user.get("email"),
                "timestamp": now,
                "notes": f"Delivered to {body.receiver_name.strip()}",
                "_id_": None,
            })
        except Exception as e:
            print(f"Audit log failed: {e}")
        
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
        """DEPRECATED: Cash is now auto-collected when delivery is confirmed.
        This endpoint is kept for backward compatibility but does nothing."""
        s = await _find_split(split_id)
        _check_driver_owns(s, user)
        # If already collected or delivered, just return success
        if s.get("payment_status") in ("collected_by_driver", "received_by_admin"):
            return await _find_split(split_id)
        # Otherwise, if delivered, mark as collected
        if s.get("delivery_status") == "delivered":
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
        
        # Build update dict
        update_dict = {
            "delivery_status": "delivered",
            "proof_of_delivery_status": "submitted",
            "signature_b64": body.signature_b64,
            "receiver_name": body.receiver_name.strip(),
            "delivered_at": now,
            "status": "completed",  # legacy status field
            "updated_at": now,
        }
        
        # Add picture if provided
        if body.picture_b64:
            update_dict["delivery_picture_b64"] = body.picture_b64
        
        # Auto-collect cash for COD orders
        if o.get("payment_method") == "cash_on_delivery":
            update_dict["payment_status"] = "collected_by_driver"
            update_dict["cash_handover_status"] = "pending"
            update_dict["cash_collected_at"] = now
        
        await db.restaurant_orders.update_one(
            {"id": order_id},
            {"$set": update_dict},
        )
        
        # Create audit log
        try:
            await db.audit_logs.insert_one({
                "id": str(uuid.uuid4()),
                "action": "delivered",
                "entity_type": "restaurant_order",
                "entity_id": order_id,
                "order_id": order_id,
                "user_id": user["id"],
                "user_role": "driver",
                "user_email": user.get("email"),
                "timestamp": now,
                "notes": f"Delivered to {body.receiver_name.strip()}",
                "_id_": None,
            })
        except Exception as e:
            print(f"Audit log failed: {e}")
        
        return await _find_rest_order(order_id)

    @new_router.post("/driver/restaurant-orders/{order_id}/cash-collected")
    async def driver_cash_rest(order_id: str, user: dict = driver_dep):
        """DEPRECATED: Cash is now auto-collected when delivery is confirmed.
        This endpoint is kept for backward compatibility but does nothing."""
        o = await _find_rest_order(order_id)
        _check_driver_owns(o, user)
        # If already collected or delivered, just return success
        if o.get("payment_status") in ("collected_by_driver", "received_by_admin"):
            return await _find_rest_order(order_id)
        # Otherwise, if delivered, mark as collected
        if o.get("delivery_status") == "delivered":
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
        rows = await db.seller_order_splits.find({"order_id": order_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
        return redact_many_for_customer(rows)

    # ---------------------------------------------------------------------------
    # Admin: Delivery Pricing Rules Management
    # ---------------------------------------------------------------------------
    @new_router.get("/admin/delivery-pricing-rules")
    async def admin_get_delivery_pricing_rules(_: dict = admin_dep):
        """Get all delivery pricing rules."""
        rules = await db.delivery_pricing_rules.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        return rules

    @new_router.post("/admin/delivery-pricing-rules")
    async def admin_create_delivery_pricing_rule(body: DeliveryPricingRuleIn, user: dict = admin_dep):
        """Create a new delivery pricing rule."""
        rule_id = str(uuid.uuid4())
        now = now_iso()
        rule = {
            "id": rule_id,
            "pickup_area": body.pickup_area.strip(),
            "delivery_area": body.delivery_area.strip(),
            "order_type": body.order_type,
            "shop_id": body.shop_id,
            "restaurant_id": body.restaurant_id,
            "delivery_fee_usd": body.delivery_fee_usd,
            "active": body.active,
            "created_at": now,
            "updated_at": now,
            "created_by_admin_id": user["id"],
        }
        await db.delivery_pricing_rules.insert_one(rule)
        rule.pop("_id", None)
        return rule

    @new_router.put("/admin/delivery-pricing-rules/{rule_id}")
    async def admin_update_delivery_pricing_rule(rule_id: str, body: DeliveryPricingRuleIn, user: dict = admin_dep):
        """Update an existing delivery pricing rule."""
        existing = await db.delivery_pricing_rules.find_one({"id": rule_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Delivery pricing rule not found")
        update = {
            "pickup_area": body.pickup_area.strip(),
            "delivery_area": body.delivery_area.strip(),
            "order_type": body.order_type,
            "shop_id": body.shop_id,
            "restaurant_id": body.restaurant_id,
            "delivery_fee_usd": body.delivery_fee_usd,
            "active": body.active,
            "updated_at": now_iso(),
        }
        await db.delivery_pricing_rules.update_one({"id": rule_id}, {"$set": update})
        updated = await db.delivery_pricing_rules.find_one({"id": rule_id}, {"_id": 0})
        return updated

    @new_router.delete("/admin/delivery-pricing-rules/{rule_id}")
    async def admin_delete_delivery_pricing_rule(rule_id: str, _: dict = admin_dep):
        """Delete a delivery pricing rule."""
        result = await db.delivery_pricing_rules.delete_one({"id": rule_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Delivery pricing rule not found")
        return {"ok": True}

    @new_router.get("/admin/delivery-pricing-rules/default-fee")
    async def admin_get_default_delivery_fee(_: dict = admin_dep):
        """Get the default delivery fee."""
        settings = await db.settings.find_one({"key": "default_delivery_fee_usd"}, {"_id": 0})
        return {"default_delivery_fee_usd": settings.get("value", 2.0) if settings else 2.0}

    @new_router.post("/admin/delivery-pricing-rules/default-fee")
    async def admin_set_default_delivery_fee(body: dict, _: dict = admin_dep):
        """Set the default delivery fee."""
        fee = float(body.get("default_delivery_fee_usd", 2.0))
        if fee < 0:
            raise HTTPException(400, "Delivery fee cannot be negative")
        await db.settings.update_one(
            {"key": "default_delivery_fee_usd"},
            {"$set": {"key": "default_delivery_fee_usd", "value": fee, "updated_at": now_iso()}},
            upsert=True
        )
        return {"default_delivery_fee_usd": fee}

    # ---------------------------------------------------------------------------
    # Admin alerts (badge counts for dashboard tabs)
    # ---------------------------------------------------------------------------
    @new_router.get("/admin/alerts")
    async def admin_alerts(_: dict = admin_dep):
        """Counts powering admin tab badges:
        - orders_needing_driver: splits/orders waiting for driver assignment
        - cash_pending: splits/orders where driver collected cash but admin hasn't received yet
        - payouts_ready: payouts in pending/ready state and seller splits/orders ready_for_payout but not yet generated
        - disputes_open: splits with dispute_status == "opened"
        - cancellations_open: restaurant orders with status == "cancel_requested"
        """
        # Orders needing driver = unassigned OR driver rejected and needs reassignment
        needs_driver_q = {
            "$or": [
                {"delivery_status": "unassigned"},
                {"delivery_status": "needs_driver_assignment"},
                {"assignment_status": "rejected_by_driver"},
            ]
        }
        splits_needing = await db.seller_order_splits.count_documents(needs_driver_q)
        rests_needing = await db.restaurant_orders.count_documents(
            {**needs_driver_q, "payment_method": PAYMENT_METHOD_COD}
        )

        # Cash pending handover
        splits_cash_pending = await db.seller_order_splits.count_documents({"cash_handover_status": "pending"})
        rests_cash_pending = await db.restaurant_orders.count_documents({"cash_handover_status": "pending"})

        # Payouts ready: existing payouts in pending status + splits/orders ready_for_payout that have not been bundled
        payouts_pending = await db.seller_payouts.count_documents({"status": {"$in": ["pending", "ready"]}})
        splits_ready_for_payout = await db.seller_order_splits.count_documents(
            {"payout_status": "ready_for_payout", "payout_id": None}
        )
        rests_ready_for_payout = await db.restaurant_orders.count_documents(
            {"payout_status": "ready_for_payout", "payout_id": None}
        )

        # Disputes
        disputes_splits = await db.seller_order_splits.count_documents({"dispute_status": "opened"})
        disputes_rests = await db.restaurant_orders.count_documents({"dispute_status": "opened"})

        # Cancellation requests (restaurant orders awaiting admin decision)
        cancel_requests = await db.restaurant_orders.count_documents({"status": "cancel_requested"})

        return {
            "orders_needing_driver": int(splits_needing + rests_needing),
            "cash_pending": int(splits_cash_pending + rests_cash_pending),
            "payouts_ready": int(payouts_pending + splits_ready_for_payout + rests_ready_for_payout),
            "disputes_open": int(disputes_splits + disputes_rests),
            "cancellations_open": int(cancel_requests),
        }

    # ---------------------------------------------------------------------------
    # Driver cash summary (for "Cash to hand over" section on Driver Dashboard)
    # ---------------------------------------------------------------------------
    @new_router.get("/driver/cash-summary")
    async def driver_cash_summary(user: dict = driver_dep):
        """Returns the driver's pending-vs-handed-over cash totals + per-order list."""
        splits_pending = await db.seller_order_splits.find(
            {"driver_id": user["id"], "cash_handover_status": "pending"},
            {"_id": 0, "id": 1, "order_id": 1, "shop_name": 1, "customer_name": 1, "order_total_usd": 1, "cash_collected_at": 1},
        ).sort("cash_collected_at", -1).to_list(500)
        rest_pending = await db.restaurant_orders.find(
            {"driver_id": user["id"], "cash_handover_status": "pending"},
            {"_id": 0, "id": 1, "restaurant_name": 1, "customer_name": 1, "order_total_usd": 1, "cash_collected_at": 1},
        ).sort("cash_collected_at", -1).to_list(500)
        # Already handed over today (since 00:00 UTC) for context
        today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
        splits_received = await db.seller_order_splits.count_documents({
            "driver_id": user["id"], "cash_handover_status": "received", "cash_received_at": {"$gte": today_iso},
        })
        rests_received = await db.restaurant_orders.count_documents({
            "driver_id": user["id"], "cash_handover_status": "received", "cash_received_at": {"$gte": today_iso},
        })
        pending_total = round(
            sum(float(s.get("order_total_usd", 0)) for s in splits_pending)
            + sum(float(o.get("order_total_usd", 0)) for o in rest_pending),
            2,
        )
        return {
            "pending_total_usd": pending_total,
            "pending_count": int(len(splits_pending) + len(rest_pending)),
            "received_today_count": int(splits_received + rests_received),
            "items": [
                *[{"kind": "marketplace", **s} for s in splits_pending],
                *[{"kind": "restaurant", **o} for o in rest_pending],
            ],
        }

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
    
    # Get system settings for global rate
    sysconf = await get_settings()
    global_rate = float(sysconf.get("global_rate", 600.0))
    
    # Get all sellers' exchange rates
    seller_ids_list = list(by_seller.keys())
    rate_records = await db.exchange_rates.find(
        {"seller_id": {"$in": seller_ids_list}}, {"_id": 0}
    ).to_list(1000)
    rate_by_seller = {r["seller_id"]: float(r.get("rate", global_rate)) for r in rate_records}
    
    for sid, bucket in by_seller.items():
        if not bucket["splits"] and not bucket["rests"]:
            continue
        seller = await db.users.find_one({"id": sid}, {"_id": 0, "name": 1, "email": 1})
        seller_rate = rate_by_seller.get(sid, global_rate)
        
        print(f"💰 [PAYOUT] Seller {sid}: rate={seller_rate}, amount=${bucket['amount']}, SSP={bucket['amount'] * seller_rate}")
        
        payout = {
            "id": str(uuid.uuid4()),
            "seller_id": sid,
            "seller_name": (seller or {}).get("name", ""),
            "seller_email": (seller or {}).get("email", ""),
            "split_ids": bucket["splits"],
            "restaurant_order_ids": bucket["rests"],
            "amount_usd": round(bucket["amount"], 2),
            "commission_deducted_usd": round(bucket["commission"], 2),
            "exchange_rate_ssp": seller_rate,  # NEW: Seller's exchange rate for SSP conversion
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
# Delivery Fee Calculation Helper
# ---------------------------------------------------------------------------
async def _calculate_delivery_fee(
    pickup_area: str,
    delivery_area: str,
    order_type: str,
    shop_id: str = None,
    restaurant_id: str = None
) -> float:
    """Calculate delivery fee based on the platform-wide delivery mode.

    Two modes controlled by `settings.admin_manages_delivery`:

    - **admin_manages_delivery == True**: Admin's `delivery_pricing_rules`
      govern the fee for every shop. (Existing behavior.)
    - **admin_manages_delivery == False (default)**: Sellers deliver
      themselves — read the shop's own delivery_mode / delivery_fee_usd /
      delivery_per_area. If the shop hasn't configured anything, the
      admin's rules are used as a graceful fallback so orders don't stall.

    The seller-delivery branch applies only to shop orders (order_type
    == 'product'/'wholesale'/'shop'). Restaurants always fall through to
    the admin/rule-based pricing since restaurant_id is passed instead.
    """
    # Normalize areas (trim and lowercase for matching)
    pickup_area_norm = (pickup_area or "").strip().lower()
    delivery_area_norm = (delivery_area or "").strip().lower()

    # Load the global toggle
    sysettings = await db.settings.find_one({"id": "system"}, {"_id": 0}) or {}
    admin_manages_global = bool(sysettings.get("admin_manages_delivery", False))

    # Per-shop override (highest priority). "default" → follow global toggle.
    shop_managed_by = "default"
    if shop_id:
        shop_doc = await db.shops.find_one({"id": shop_id}, {"_id": 0, "delivery_managed_by": 1}) or {}
        shop_managed_by = (shop_doc.get("delivery_managed_by") or "default").lower()

    if shop_managed_by == "seller":
        admin_manages = False
    elif shop_managed_by == "admin":
        admin_manages = True
    else:
        admin_manages = admin_manages_global

    # --- Seller-managed branch ----------------------------------------
    if not admin_manages and shop_id:
        shop = await db.shops.find_one({"id": shop_id}, {"_id": 0}) or {}
        mode = (shop.get("delivery_mode") or "").strip().lower()
        if mode == "free":
            log.info(f"[DELIVERY FEE] Seller-managed: shop {shop_id[:8]} → FREE")
            return 0.0
        if mode == "fixed":
            fee = float(shop.get("delivery_fee_usd") or 0)
            log.info(f"[DELIVERY FEE] Seller-managed: shop {shop_id[:8]} → fixed {fee}")
            return fee
        if mode == "per_area":
            for row in (shop.get("delivery_per_area") or []):
                if (row.get("area") or "").strip().lower() == delivery_area_norm:
                    fee = float(row.get("fee_usd") or 0)
                    log.info(f"[DELIVERY FEE] Seller-managed: shop {shop_id[:8]} → per-area '{delivery_area}' = {fee}")
                    return fee
            log.warning(f"[DELIVERY FEE] Seller-managed: shop {shop_id[:8]} has no rule for '{delivery_area}'; falling back to admin rules")
        # If mode is unset/unknown → fall through to admin logic below
    # -------------------------------------------------------------------

    pickup_area = pickup_area_norm
    delivery_area = delivery_area_norm

    # Log for debugging
    print(f"🚚 [DELIVERY FEE] Calculating: pickup={pickup_area}, delivery={delivery_area}, type={order_type}, shop={shop_id}, restaurant={restaurant_id}")
    log.info(f"[DELIVERY FEE] Calculating: pickup={pickup_area}, delivery={delivery_area}, type={order_type}, shop={shop_id}, restaurant={restaurant_id}")
    
    # Try shop/restaurant-specific rule first
    if shop_id:
        rule = await db.delivery_pricing_rules.find_one({
            "shop_id": shop_id,
            "pickup_area": {"$regex": f"^{pickup_area}$", "$options": "i"},
            "delivery_area": {"$regex": f"^{delivery_area}$", "$options": "i"},
            "active": True
        }, {"_id": 0})
        if rule:
            log.info(f"[DELIVERY FEE] Found shop-specific rule: {rule['delivery_fee_usd']}")
            return float(rule["delivery_fee_usd"])
    
    if restaurant_id:
        rule = await db.delivery_pricing_rules.find_one({
            "restaurant_id": restaurant_id,
            "pickup_area": {"$regex": f"^{pickup_area}$", "$options": "i"},
            "delivery_area": {"$regex": f"^{delivery_area}$", "$options": "i"},
            "active": True
        }, {"_id": 0})
        if rule:
            log.info(f"[DELIVERY FEE] Found restaurant-specific rule: {rule['delivery_fee_usd']}")
            return float(rule["delivery_fee_usd"])
    
    # Try order type + area rule
    query = {
        "order_type": order_type,
        "pickup_area": {"$regex": f"^{pickup_area}$", "$options": "i"},
        "delivery_area": {"$regex": f"^{delivery_area}$", "$options": "i"},
        "shop_id": None,
        "restaurant_id": None,
        "active": True
    }
    log.info(f"[DELIVERY FEE] Searching order-type rule with query: {query}")
    rule = await db.delivery_pricing_rules.find_one(query, {"_id": 0})
    if rule:
        log.info(f"[DELIVERY FEE] Found order-type rule: {rule['delivery_fee_usd']}")
        return float(rule["delivery_fee_usd"])
    else:
        log.warning(f"[DELIVERY FEE] No order-type rule found for {order_type}")
    
    # Try generic area rule (order_type = 'all')
    query_all = {
        "order_type": "all",
        "pickup_area": {"$regex": f"^{pickup_area}$", "$options": "i"},
        "delivery_area": {"$regex": f"^{delivery_area}$", "$options": "i"},
        "shop_id": None,
        "restaurant_id": None,
        "active": True
    }
    log.info(f"[DELIVERY FEE] Searching generic rule with query: {query_all}")
    rule = await db.delivery_pricing_rules.find_one(query_all, {"_id": 0})
    if rule:
        log.info(f"[DELIVERY FEE] Found generic rule: {rule['delivery_fee_usd']}")
        return float(rule["delivery_fee_usd"])
    else:
        log.warning(f"[DELIVERY FEE] No generic (all) rule found")
    
    # Fallback to default
    print(f"🚚 [DELIVERY FEE] No rule found, using default")
    log.warning(f"[DELIVERY FEE] No rule found, using default")
    settings = await db.settings.find_one({"key": "default_delivery_fee_usd"}, {"_id": 0})
    default_fee = float(settings.get("value", 0.0)) if settings else 0.0
    print(f"🚚 [DELIVERY FEE] Default fee from settings: {default_fee}")
    log.info(f"[DELIVERY FEE] Default fee: {default_fee}")
    return default_fee


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

    await db.delivery_pricing_rules.create_index("id", unique=True)
    await db.delivery_pricing_rules.create_index([("pickup_area", 1), ("delivery_area", 1)])
    await db.delivery_pricing_rules.create_index([("shop_id", 1)])
    await db.delivery_pricing_rules.create_index([("restaurant_id", 1)])
    await db.delivery_pricing_rules.create_index([("active", 1)])

    # Demo driver — disabled for production. Toggle back on by setting
    # SEED_DEMO_DRIVER=1 in backend/.env if you need a demo driver account
    # (development/local testing).
    if os.environ.get("SEED_DEMO_DRIVER") == "1":
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
