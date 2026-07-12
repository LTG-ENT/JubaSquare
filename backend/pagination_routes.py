"""
Iter 35 — Paginated seller dashboard endpoints.

Legacy endpoints return raw arrays (or arrays capped at limit=200/500), which
caused sellers with >200 products/orders to see truncated data and forced the
client to fetch entire lists just to render one page.

These `*/paged` endpoints return a stable envelope so the client can render
classic page-number pagination without over-fetching:

    { "items": [...page slice...], "total": <int>, "page": <int>, "page_size": <int> }

`page` is 1-indexed. `page_size` is capped server-side to `MAX_PAGE_SIZE`.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

log = logging.getLogger(__name__)

MAX_PAGE_SIZE = 200  # hard upper bound
DEFAULT_PAGE_SIZE = 50


def _clamp(page: Optional[int], page_size: Optional[int]) -> tuple[int, int]:
    p = max(1, int(page or 1))
    ps = int(page_size or DEFAULT_PAGE_SIZE)
    if ps <= 0:
        ps = DEFAULT_PAGE_SIZE
    ps = min(ps, MAX_PAGE_SIZE)
    return p, ps


def _escape_regex(s: str) -> str:
    import re
    return re.escape(s or "")


def create_pagination_routes(db, require_role, get_current_user):
    router = APIRouter(prefix="/api", tags=["seller-paginated"])

    # ------------------------------------------------------------------
    # Products (marketplace + wholesale) — across all the seller's shops
    # ------------------------------------------------------------------
    @router.get("/seller/products/paged")
    async def seller_products_paged(
        user: dict = Depends(require_role("seller", "admin")),
        page: int = Query(1, ge=1),
        page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
        shop_id: Optional[str] = None,
        q: Optional[str] = None,
        stock: Optional[str] = None,  # "all" | "low" | "out"
        low_threshold: int = 5,
    ):
        p, ps = _clamp(page, page_size)

        # Seller may own many shops; look them up once so we can scope.
        seller_shop_ids: list[str] = []
        if user["role"] == "admin" and not shop_id:
            # Admin without shop filter → allow all shops. Skip the shop lookup.
            pass
        else:
            shops = await db.shops.find(
                {"seller_id": user["id"]}, {"_id": 0, "id": 1, "name": 1, "kind": 1}
            ).to_list(1000)
            seller_shop_ids = [s["id"] for s in shops]

        mongo: dict = {}
        if shop_id:
            mongo["shop_id"] = shop_id
        elif seller_shop_ids:
            mongo["shop_id"] = {"$in": seller_shop_ids}
        else:
            return {"items": [], "total": 0, "page": p, "page_size": ps}

        if q:
            regex = {"$regex": _escape_regex(q.strip()), "$options": "i"}
            mongo["$or"] = [{"name": regex}, {"category": regex}]

        if stock == "out":
            mongo["stock"] = {"$lte": 0}
        elif stock == "low":
            mongo["stock"] = {"$gt": 0, "$lte": max(1, int(low_threshold or 5))}

        total = await db.products.count_documents(mongo)
        skip = (p - 1) * ps

        cursor = (
            db.products.find(mongo, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(ps)
        )
        items = await cursor.to_list(ps)

        # Embed shop_name + kind so the seller UI can label the row without
        # a second round trip.
        if items:
            need_shop_ids = list({p["shop_id"] for p in items if p.get("shop_id")})
            shops_meta = await db.shops.find(
                {"id": {"$in": need_shop_ids}},
                {"_id": 0, "id": 1, "name": 1, "kind": 1},
            ).to_list(len(need_shop_ids))
            by_id = {s["id"]: s for s in shops_meta}
            for it in items:
                sh = by_id.get(it.get("shop_id")) or {}
                it["shop_name"] = sh.get("name", "")
                it["shop_kind"] = sh.get("kind", "")

        return {"items": items, "total": total, "page": p, "page_size": ps}

    # ------------------------------------------------------------------
    # Menu items — across all the seller's restaurants
    # ------------------------------------------------------------------
    @router.get("/seller/menu-items/paged")
    async def seller_menu_items_paged(
        user: dict = Depends(require_role("seller", "admin")),
        page: int = Query(1, ge=1),
        page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
        restaurant_id: Optional[str] = None,
        q: Optional[str] = None,
    ):
        p, ps = _clamp(page, page_size)

        seller_rest_ids: list[str] = []
        if not (user["role"] == "admin" and not restaurant_id):
            rests = await db.restaurants.find(
                {"seller_id": user["id"]}, {"_id": 0, "id": 1, "name": 1}
            ).to_list(1000)
            seller_rest_ids = [r["id"] for r in rests]

        mongo: dict = {}
        if restaurant_id:
            mongo["restaurant_id"] = restaurant_id
        elif seller_rest_ids:
            mongo["restaurant_id"] = {"$in": seller_rest_ids}
        else:
            return {"items": [], "total": 0, "page": p, "page_size": ps}

        if q:
            regex = {"$regex": _escape_regex(q.strip()), "$options": "i"}
            mongo["$or"] = [{"name": regex}, {"food_category": regex}]

        total = await db.menu_items.count_documents(mongo)
        skip = (p - 1) * ps
        items = await (
            db.menu_items.find(mongo, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(ps)
            .to_list(ps)
        )

        if items:
            need_rest_ids = list({it["restaurant_id"] for it in items if it.get("restaurant_id")})
            rest_meta = await db.restaurants.find(
                {"id": {"$in": need_rest_ids}}, {"_id": 0, "id": 1, "name": 1}
            ).to_list(len(need_rest_ids))
            by_id = {r["id"]: r for r in rest_meta}
            for it in items:
                r = by_id.get(it.get("restaurant_id")) or {}
                it["restaurant_name"] = r.get("name", "")

        return {"items": items, "total": total, "page": p, "page_size": ps}

    # ------------------------------------------------------------------
    # Orders (marketplace orders — same as /orders/seller, but with total)
    # ------------------------------------------------------------------
    @router.get("/seller/orders/paged")
    async def seller_orders_paged(
        user: dict = Depends(require_role("seller", "admin")),
        page: int = Query(1, ge=1),
        page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    ):
        p, ps = _clamp(page, page_size)

        # Gather product + menu ids owned by this seller (same logic as /orders/seller)
        prod_ids = [
            p["id"] async for p in db.products.find({"seller_id": user["id"]}, {"_id": 0, "id": 1})
        ]
        menu_ids = [
            m["id"] async for m in db.menu_items.find({"seller_id": user["id"]}, {"_id": 0, "id": 1})
        ]
        item_ids = list(set(prod_ids) | set(menu_ids))
        if not item_ids:
            return {"items": [], "total": 0, "page": p, "page_size": ps}

        mongo = {"items.item_id": {"$in": item_ids}}
        total = await db.orders.count_documents(mongo)
        skip = (p - 1) * ps
        items = await (
            db.orders.find(mongo, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(ps)
            .to_list(ps)
        )

        # Embed current stock for referenced products so the client can render
        # the "stock alert" filter without a follow-up round trip per order.
        referenced_ids = list({
            it["item_id"]
            for o in items
            for it in (o.get("items") or [])
            if it.get("item_type") == "product" and it.get("item_id")
        })
        stock_map: dict[str, int] = {}
        if referenced_ids:
            docs = await db.products.find(
                {"id": {"$in": referenced_ids}}, {"_id": 0, "id": 1, "stock": 1}
            ).to_list(len(referenced_ids))
            stock_map = {d["id"]: int(d.get("stock") or 0) for d in docs}

        return {
            "items": items,
            "total": total,
            "page": p,
            "page_size": ps,
            "stock_map": stock_map,
        }

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    @router.get("/notifications/paged")
    async def notifications_paged(
        user: dict = Depends(get_current_user),
        page: int = Query(1, ge=1),
        page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    ):
        p, ps = _clamp(page, page_size)
        mongo = {"user_id": user["id"]}
        total = await db.notifications.count_documents(mongo)
        unread = await db.notifications.count_documents({**mongo, "is_read": False})
        skip = (p - 1) * ps
        items = await (
            db.notifications.find(mongo, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(ps)
            .to_list(ps)
        )
        return {"items": items, "total": total, "unread_count": unread, "page": p, "page_size": ps}

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------
    @router.get("/messages/seller/paged")
    async def seller_messages_paged(
        user: dict = Depends(require_role("seller", "admin")),
        page: int = Query(1, ge=1),
        page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    ):
        p, ps = _clamp(page, page_size)
        mongo: dict = {}
        if user["role"] != "admin":
            mongo["seller_id"] = user["id"]
        total = await db.shop_messages.count_documents(mongo)
        unread = await db.shop_messages.count_documents({**mongo, "is_read": False})
        skip = (p - 1) * ps
        items = await (
            db.shop_messages.find(mongo, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(ps)
            .to_list(ps)
        )
        return {"items": items, "total": total, "unread_count": unread, "page": p, "page_size": ps}

    # ------------------------------------------------------------------
    # Invoices (marketplace + restaurant)
    # ------------------------------------------------------------------
    @router.get("/seller/invoices/paged")
    async def seller_invoices_paged(
        user: dict = Depends(require_role("seller", "admin")),
        page: int = Query(1, ge=1),
        page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    ):
        p, ps = _clamp(page, page_size)
        mongo = {"seller_id": user["id"]}
        total = await db.invoices.count_documents(mongo)
        skip = (p - 1) * ps
        items = await (
            db.invoices.find(mongo, {"_id": 0})
            .sort("week_start", -1)
            .skip(skip)
            .limit(ps)
            .to_list(ps)
        )
        # Aggregate stats across ALL invoices (not just current page)
        agg = await db.invoices.aggregate([
            {"$match": mongo},
            {"$group": {
                "_id": None,
                "total_sales": {"$sum": "$total_sales"},
                "total_commission": {"$sum": "$commission"},
                "amount_owed": {
                    "$sum": {"$cond": [{"$eq": ["$status", "Unpaid"]}, "$amount_owed", 0]}
                },
            }},
        ]).to_list(1)
        stats = agg[0] if agg else {"total_sales": 0, "total_commission": 0, "amount_owed": 0}
        return {
            "items": items,
            "total": total,
            "page": p,
            "page_size": ps,
            "stats": {
                "total_sales": stats.get("total_sales", 0),
                "total_commission": stats.get("total_commission", 0),
                "amount_owed": stats.get("amount_owed", 0),
            },
        }

    @router.get("/seller/restaurant-invoices/paged")
    async def seller_restaurant_invoices_paged(
        user: dict = Depends(require_role("seller", "admin")),
        page: int = Query(1, ge=1),
        page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    ):
        p, ps = _clamp(page, page_size)
        mongo = {"seller_id": user["id"]}
        total = await db.restaurant_invoices.count_documents(mongo)
        skip = (p - 1) * ps
        items = await (
            db.restaurant_invoices.find(mongo, {"_id": 0})
            .sort("week_start", -1)
            .skip(skip)
            .limit(ps)
            .to_list(ps)
        )
        agg = await db.restaurant_invoices.aggregate([
            {"$match": mongo},
            {"$group": {
                "_id": None,
                "total_sales": {"$sum": "$total_sales"},
                "total_commission": {"$sum": "$commission"},
                "amount_owed": {
                    "$sum": {"$cond": [{"$eq": ["$status", "Unpaid"]}, "$amount_owed", 0]}
                },
            }},
        ]).to_list(1)
        stats = agg[0] if agg else {"total_sales": 0, "total_commission": 0, "amount_owed": 0}
        return {
            "items": items,
            "total": total,
            "page": p,
            "page_size": ps,
            "stats": {
                "total_sales": stats.get("total_sales", 0),
                "total_commission": stats.get("total_commission", 0),
                "amount_owed": stats.get("amount_owed", 0),
            },
        }

    return router
