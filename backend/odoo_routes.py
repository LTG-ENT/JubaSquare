"""
Odoo Integration API Routes for JubaSquare

Admin-only Odoo configuration and webhook endpoints.
Security: Webhook authentication, admin-only access to settings.
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Header, Request

from odoo_schema import (
    OdooConnectionSettings,
    OdooConnectionUpdate,
    OdooProductUpsert,
    OdooStockUpdate,
    OdooProductUnpublish,
    OdooSyncLog,
    OdooTestConnectionRequest,
    OdooRetryFailedRequest,
    WholesaleFields,
    PricingTier
)
from odoo_token_manager import OdooTokenManager

log = logging.getLogger(__name__)

# Legacy env-only token (used as a fallback inside OdooTokenManager)
ODOO_WEBHOOK_TOKEN = os.environ.get("ODOO_WEBHOOK_TOKEN", "")

def create_odoo_routes(db, require_role):
    """
    Create Odoo integration routes
    
    Args:
        db: MongoDB database instance
        require_role: Function to require specific role (e.g., require_role("admin"))
    """
    router = APIRouter(prefix="/api/odoo", tags=["odoo"])
    token_manager = OdooTokenManager(db)
    
    # ========================================================================
    # Webhook Authentication
    # ========================================================================
    
    async def verify_odoo_webhook(x_jubasquare_odoo_token: str = Header(None)):
        """Verify Odoo webhook request against DB token (or env fallback)."""
        if not await token_manager.is_configured():
            log.error("No Odoo service token configured (DB nor env)")
            raise HTTPException(status_code=500, detail="Odoo webhook not configured")
        
        if not x_jubasquare_odoo_token:
            log.warning("Odoo webhook request without token")
            raise HTTPException(status_code=401, detail="Missing Odoo token")
        
        if not await token_manager.verify(x_jubasquare_odoo_token):
            log.warning("Invalid Odoo webhook token attempt")
            raise HTTPException(status_code=403, detail="Invalid Odoo token")
        
        return True
    
    # ========================================================================
    # Health Check
    # ========================================================================
    
    @router.get("/health")
    async def odoo_health_check():
        """Public health check for Odoo integration"""
        configured = await token_manager.is_configured()
        return {
            "status": "ok",
            "service": "jubasquare-odoo-integration",
            "webhook_configured": configured,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # ========================================================================
    # Odoo → JubaSquare Webhooks
    # ========================================================================
    
    @router.post("/products/upsert")
    async def odoo_product_upsert(
        payload: OdooProductUpsert,
        _verified: bool = Depends(verify_odoo_webhook)
    ):
        """
        Webhook: Odoo sends product to create/update in JubaSquare
        Only affects shops/restaurants with Odoo enabled
        """
        log_id = str(uuid.uuid4())
        
        try:
            # Determine if shop or restaurant
            target_collection = None
            target_id = None
            entity_type = None
            
            if payload.shop_id:
                # Check if shop has Odoo enabled
                shop = await db.shops.find_one({"id": payload.shop_id}, {"odoo_connection": 1})
                if not shop or not shop.get("odoo_connection", {}).get("enabled"):
                    # Log as ignored
                    await db.odoo_sync_logs.insert_one({
                        "id": log_id,
                        "operation_type": "product_sync",
                        "direction": "odoo_to_juba",
                        "status": "ignored",
                        "shop_id": payload.shop_id,
                        "request_payload": payload.dict(),
                        "error_message": "Shop not connected to Odoo",
                        "created_at": datetime.utcnow()
                    })
                    return {"status": "ignored", "message": "Shop not connected to Odoo"}
                
                target_collection = db.products
                target_id = payload.shop_id
                entity_type = "shop"
            
            elif payload.restaurant_id:
                # Check if restaurant has Odoo enabled
                restaurant = await db.restaurants.find_one(
                    {"id": payload.restaurant_id},
                    {"odoo_connection": 1}
                )
                if not restaurant or not restaurant.get("odoo_connection", {}).get("enabled"):
                    # Log as ignored
                    await db.odoo_sync_logs.insert_one({
                        "id": log_id,
                        "operation_type": "product_sync",
                        "direction": "odoo_to_juba",
                        "status": "ignored",
                        "restaurant_id": payload.restaurant_id,
                        "request_payload": payload.dict(),
                        "error_message": "Restaurant not connected to Odoo",
                        "created_at": datetime.utcnow()
                    })
                    return {"status": "ignored", "message": "Restaurant not connected to Odoo"}
                
                target_collection = db.menu_items
                target_id = payload.restaurant_id
                entity_type = "restaurant"
            
            else:
                raise HTTPException(status_code=400, detail="Either shop_id or restaurant_id required")
            
            # Validate category_id
            if not payload.category_id:
                raise HTTPException(status_code=400, detail="category_id is required for product upsert")
            
            # Get seller_id from shop or restaurant
            seller_id = None
            if entity_type == "shop":
                shop = await db.shops.find_one({"id": payload.shop_id}, {"seller_id": 1})
                if not shop:
                    raise HTTPException(status_code=404, detail=f"Shop {payload.shop_id} not found")
                seller_id = shop.get("seller_id")
            else:  # restaurant
                restaurant = await db.restaurants.find_one({"id": payload.restaurant_id}, {"seller_id": 1})
                if not restaurant:
                    raise HTTPException(status_code=404, detail=f"Restaurant {payload.restaurant_id} not found")
                seller_id = restaurant.get("seller_id")
            if not seller_id:
                raise HTTPException(status_code=400, detail=f"Cannot derive seller_id from {entity_type}")
            
            # Prepare product/menu item data
            product_data = {
                "name": payload.name,
                "description": payload.description or "",
                "price_usd": payload.price,
                "image_url": payload.image_url or "",
                "stock": payload.stock_quantity if payload.stock_quantity is not None else 100,  # PRIMARY: stock field
                "stock_quantity": payload.stock_quantity if payload.stock_quantity is not None else 100,  # METADATA: for tracking
                "category_id": payload.category_id,  # REQUIRED
                "is_active": bool(payload.publish),  # Marketplace visibility — mirrors publish flag
                # Odoo sync fields
                "odoo_source": True,
                "odoo_product_id": payload.odoo_product_id,
                "odoo_product_sku": payload.odoo_product_sku,
                "odoo_publish": payload.publish,
                "odoo_hidden": not payload.publish,
                "odoo_sync_price": payload.sync_price,
                "odoo_sync_stock": payload.sync_stock,
                "odoo_sync_image": payload.sync_image,
                "odoo_sync_description": payload.sync_description,
                "odoo_last_sync_at": datetime.utcnow(),
                "odoo_sync_status": "synced" if payload.publish else "unpublished",
                "odoo_sync_error": None,
                # Wholesale fields (optional)
                "is_wholesale": payload.wholesale_enabled,
                "min_order_qty": payload.minimum_order_qty if payload.minimum_order_qty else 1,
                "bulk_price_usd": payload.bulk_price,
                "pricing_tiers": [tier.dict() for tier in payload.pricing_tiers] if payload.pricing_tiers else []
            }
            
            # Add entity-specific fields
            if entity_type == "shop":
                product_data["shop_id"] = payload.shop_id
                product_data["category"] = payload.category or ""  # Deprecated but keep for backward compat
                product_data["mode"] = payload.mode if payload.mode else ("wholesale" if payload.wholesale_enabled else "marketplace")
                product_data["seller_id"] = seller_id
            else:  # restaurant
                product_data["restaurant_id"] = payload.restaurant_id
                product_data["food_category"] = payload.food_category or ""  # Deprecated but keep for backward compat
                product_data["seller_id"] = seller_id
            
            # Check if product already exists (by odoo_product_id)
            existing_filter = {
                f"{entity_type}_id": target_id,
                "odoo_product_id": payload.odoo_product_id
            }
            existing = await target_collection.find_one(existing_filter)
            
            if existing:
                # Update existing product
                await target_collection.update_one(
                    {"id": existing["id"]},
                    {"$set": product_data}
                )
                product_id = existing["id"]
                action = "updated"
            else:
                # Create new product
                product_id = str(uuid.uuid4())
                product_data["id"] = product_id
                product_data["created_at"] = datetime.utcnow()
                await target_collection.insert_one(product_data)
                action = "created"
            
            # Log success
            await db.odoo_sync_logs.insert_one({
                "id": log_id,
                "operation_type": "product_sync",
                "direction": "odoo_to_juba",
                "status": "success",
                "shop_id": payload.shop_id,
                "restaurant_id": payload.restaurant_id,
                "product_id": product_id,
                "request_payload": payload.dict(),
                "response_payload": {"product_id": product_id, "action": action},
                "created_at": datetime.utcnow()
            })
            
            return {
                "status": "success",
                "product_id": product_id,
                "action": action,
                "log_id": log_id
            }
        
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Odoo product upsert error: {e}", exc_info=True)
            # Log failure
            await db.odoo_sync_logs.insert_one({
                "id": log_id,
                "operation_type": "product_sync",
                "direction": "odoo_to_juba",
                "status": "failed",
                "shop_id": payload.shop_id,
                "restaurant_id": payload.restaurant_id,
                "request_payload": payload.dict(),
                "error_message": str(e),
                "created_at": datetime.utcnow()
            })
            raise HTTPException(status_code=500, detail=f"Product upsert failed: {str(e)}")
    
    @router.post("/products/stock-update")
    async def odoo_stock_update(
        payload: OdooStockUpdate,
        _verified: bool = Depends(verify_odoo_webhook)
    ):
        """Webhook: Odoo sends stock update"""
        log_id = str(uuid.uuid4())
        
        try:
            # Similar logic to product upsert, but only update stock
            target_collection = None
            target_id = None
            
            if payload.shop_id:
                shop = await db.shops.find_one({"id": payload.shop_id}, {"odoo_connection": 1})
                if not shop or not shop.get("odoo_connection", {}).get("enabled"):
                    return {"status": "ignored", "message": "Shop not connected to Odoo"}
                target_collection = db.products
                target_id = payload.shop_id
                id_field = "shop_id"
            elif payload.restaurant_id:
                restaurant = await db.restaurants.find_one(
                    {"id": payload.restaurant_id},
                    {"odoo_connection": 1}
                )
                if not restaurant or not restaurant.get("odoo_connection", {}).get("enabled"):
                    return {"status": "ignored", "message": "Restaurant not connected to Odoo"}
                target_collection = db.menu_items
                target_id = payload.restaurant_id
                id_field = "restaurant_id"
            else:
                raise HTTPException(status_code=400, detail="Either shop_id or restaurant_id required")
            
            # Update stock
            result = await target_collection.update_one(
                {
                    id_field: target_id,
                    "odoo_product_id": payload.odoo_product_id,
                    "odoo_sync_stock": True  # Only update if sync_stock is enabled
                },
                {
                    "$set": {
                        "stock": payload.stock_quantity,  # PRIMARY: main stock field
                        "stock_quantity": payload.stock_quantity,  # METADATA: for tracking
                        "odoo_last_sync_at": datetime.utcnow()
                    }
                }
            )
            
            if result.matched_count == 0:
                return {"status": "ignored", "message": "Product not found or stock sync disabled"}
            
            # Log success
            await db.odoo_sync_logs.insert_one({
                "id": log_id,
                "operation_type": "stock_sync",
                "direction": "odoo_to_juba",
                "status": "success",
                "shop_id": payload.shop_id,
                "restaurant_id": payload.restaurant_id,
                "request_payload": payload.dict(),
                "created_at": datetime.utcnow()
            })
            
            return {"status": "success", "log_id": log_id}
        
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Odoo stock update error: {e}", exc_info=True)
            await db.odoo_sync_logs.insert_one({
                "id": log_id,
                "operation_type": "stock_sync",
                "direction": "odoo_to_juba",
                "status": "failed",
                "shop_id": payload.shop_id,
                "restaurant_id": payload.restaurant_id,
                "request_payload": payload.dict(),
                "error_message": str(e),
                "created_at": datetime.utcnow()
            })
            raise HTTPException(status_code=500, detail=f"Stock update failed: {str(e)}")
    
    @router.post("/products/unpublish")
    async def odoo_product_unpublish(
        payload: OdooProductUnpublish,
        _verified: bool = Depends(verify_odoo_webhook)
    ):
        """Webhook: Odoo requests to unpublish/hide product"""
        log_id = str(uuid.uuid4())
        
        try:
            target_collection = None
            target_id = None
            
            if payload.shop_id:
                target_collection = db.products
                target_id = payload.shop_id
                id_field = "shop_id"
            elif payload.restaurant_id:
                target_collection = db.menu_items
                target_id = payload.restaurant_id
                id_field = "restaurant_id"
            else:
                raise HTTPException(status_code=400, detail="Either shop_id or restaurant_id required")
            
            # Mark as unpublished
            result = await target_collection.update_one(
                {
                    id_field: target_id,
                    "odoo_product_id": payload.odoo_product_id
                },
                {
                    "$set": {
                        "odoo_publish": False,
                        "odoo_hidden": True,
                        "odoo_sync_status": "unpublished",
                        "odoo_last_sync_at": datetime.utcnow()
                    }
                }
            )
            
            await db.odoo_sync_logs.insert_one({
                "id": log_id,
                "operation_type": "product_sync",
                "direction": "odoo_to_juba",
                "status": "success",
                "shop_id": payload.shop_id,
                "restaurant_id": payload.restaurant_id,
                "request_payload": payload.dict(),
                "created_at": datetime.utcnow()
            })
            
            return {"status": "success", "log_id": log_id}
        
        except Exception as e:
            log.error(f"Odoo unpublish error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Unpublish failed: {str(e)}")
    
    # ========================================================================
    # Placeholder endpoints for future implementation
    # ========================================================================
    
    @router.post("/orders/status-update")
    async def odoo_order_status_update(
        _verified: bool = Depends(verify_odoo_webhook)
    ):
        """Webhook: Odoo sends order status update (placeholder)"""
        return {"status": "placeholder", "message": "Order status update endpoint - to be implemented"}
    
    @router.post("/delivery/status-update")
    async def odoo_delivery_status_update(
        _verified: bool = Depends(verify_odoo_webhook)
    ):
        """Webhook: Odoo sends delivery status update (placeholder)"""
        return {"status": "placeholder", "message": "Delivery status update endpoint - to be implemented"}
    
    @router.post("/invoice/status-update")
    async def odoo_invoice_status_update(
        _verified: bool = Depends(verify_odoo_webhook)
    ):
        """Webhook: Odoo sends invoice status update (placeholder)"""
        return {"status": "placeholder", "message": "Invoice status update endpoint - to be implemented"}
    
    return router


def create_admin_odoo_routes(db, require_role, get_current_user=None):
    """
    Create admin-only Odoo management routes
    
    Args:
        db: MongoDB database instance
        require_role: Function to require specific role (e.g., require_role("admin"))
        get_current_user: FastAPI dependency that resolves the current JWT user
    """
    router = APIRouter(prefix="/api/admin/odoo", tags=["admin-odoo"])
    token_manager = OdooTokenManager(db)
    
    # Service token authentication for Odoo module
    async def verify_admin_or_service_token(
        request: Request,
        x_jubasquare_odoo_token: str = Header(None)
    ):
        """Allow either admin JWT token or service token for Odoo endpoints"""
        # Try service token first
        if x_jubasquare_odoo_token:
            if not await token_manager.is_configured():
                raise HTTPException(status_code=500, detail="Service token not configured")
            if await token_manager.verify(x_jubasquare_odoo_token):
                return {"role": "odoo_service", "service": True}
            log.warning("Invalid service token attempt on admin Odoo endpoint")
            raise HTTPException(status_code=403, detail="Invalid service token")
        
        # Fall back to admin JWT — resolve the current user manually
        if get_current_user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        user = await get_current_user(request)
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin role required")
        return user
    
    # Admin-JWT-only dependency for token-management endpoints.
    # IMPORTANT: We deliberately do NOT accept the service token here so that
    # a leaked service token cannot be used to rotate itself.
    async def verify_admin_only(request: Request):
        if get_current_user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        user = await get_current_user(request)
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin role required")
        return user
    
    # ========================================================================
    # Service Token Management (admin-JWT-only)
    # ========================================================================
    
    @router.get("/service-token")
    async def get_service_token_status(user=Depends(verify_admin_only)):
        """Return masked status of the Odoo service token. Never returns raw token."""
        return await token_manager.get_status()
    
    @router.post("/service-token/generate")
    async def generate_service_token(user=Depends(verify_admin_only)):
        """
        Create a new Odoo service token. Returns the raw token EXACTLY ONCE.
        If an active token already exists, returns 409 — the admin must rotate.
        """
        result = await token_manager.generate(admin_email=user.get("email", ""))
        if result.get("error") == "already_exists":
            raise HTTPException(
                status_code=409,
                detail="A token already exists. Use rotate to replace it."
            )
        log.info(f"Odoo service token generated by {user.get('email')}")
        return {
            "raw_token": result["raw_token"],
            "masked_preview": result["masked_preview"],
            "created_at": result["created_at"],
            "warning": "Copy this token now. It will not be shown again."
        }
    
    @router.post("/service-token/rotate")
    async def rotate_service_token(user=Depends(verify_admin_only)):
        """
        Invalidate all existing tokens and issue a brand-new one.
        Returns the raw token EXACTLY ONCE. The previous token stops working immediately.
        """
        result = await token_manager.rotate(admin_email=user.get("email", ""))
        log.info(f"Odoo service token rotated by {user.get('email')}")
        return {
            "raw_token": result["raw_token"],
            "masked_preview": result["masked_preview"],
            "created_at": result["created_at"],
            "last_rotated_at": result["last_rotated_at"],
            "warning": "Copy this token now. It will not be shown again. Previous token has been revoked."
        }
    
    @router.get("/shops")
    async def get_odoo_shops(user=Depends(verify_admin_or_service_token)):
        """Get all shops with Odoo connection status"""
        shops = await db.shops.find(
            {},
            {"_id": 0, "id": 1, "name": 1, "seller_id": 1, "odoo_connection": 1}
        ).to_list(1000)
        return shops
    
    @router.get("/restaurants")
    async def get_odoo_restaurants(user=Depends(verify_admin_or_service_token)):
        """Get all restaurants with Odoo connection status"""
        restaurants = await db.restaurants.find(
            {},
            {"_id": 0, "id": 1, "name": 1, "seller_id": 1, "odoo_connection": 1}
        ).to_list(1000)
        return restaurants
    
    @router.get("/sync-logs")
    async def get_odoo_sync_logs(
        limit: int = 100,
        status: Optional[str] = None,
        operation_type: Optional[str] = None,
        user=Depends(verify_admin_or_service_token)
    ):
        """Get Odoo sync logs"""
        filter_query = {}
        if status:
            filter_query["status"] = status
        if operation_type:
            filter_query["operation_type"] = operation_type
        
        logs = await db.odoo_sync_logs.find(
            filter_query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return logs
    
    @router.post("/test-connection")
    async def test_odoo_connection(
        request: OdooTestConnectionRequest,
        user=Depends(verify_admin_or_service_token)
    ):
        """Test Odoo connection for a shop or restaurant"""
        log_id = str(uuid.uuid4())
        
        # Log test connection attempt
        await db.odoo_sync_logs.insert_one({
            "id": log_id,
            "operation_type": "test_connection",
            "direction": "juba_to_odoo",
            "status": "pending",
            "shop_id": request.shop_id,
            "restaurant_id": request.restaurant_id,
            "created_at": datetime.utcnow()
        })
        
        return {
            "status": "placeholder",
            "message": "Test connection - to be implemented by Odoo module",
            "log_id": log_id
        }
    
    @router.post("/retry-failed")
    async def retry_failed_syncs(
        request: OdooRetryFailedRequest,
        user=Depends(verify_admin_or_service_token)
    ):
        """Retry failed sync operations"""
        return {
            "status": "placeholder",
            "message": "Retry failed syncs - to be implemented"
        }
    
    @router.get("/products/pending")
    async def get_pending_product_syncs(user=Depends(verify_admin_or_service_token)):
        """
        Get products pending Odoo sync (i.e. odoo_source=True products where
        odoo_sync_status is 'failed' or 'pending' / not yet synced).
        """
        cursor = db.products.find(
            {
                "odoo_source": True,
                "odoo_sync_status": {"$in": ["failed", "pending"]},
            },
            {"_id": 0}
        ).limit(500)
        products = await cursor.to_list(500)

        cursor2 = db.menu_items.find(
            {
                "odoo_source": True,
                "odoo_sync_status": {"$in": ["failed", "pending"]},
            },
            {"_id": 0}
        ).limit(500)
        menu_items = await cursor2.to_list(500)

        return {"products": products, "menu_items": menu_items}

    @router.get("/orders/pending")
    async def get_pending_order_syncs(user=Depends(verify_admin_or_service_token)):
        """
        Get JubaSquare orders that need to be synced TO Odoo.
        Filters: seller's shop OR restaurant has odoo_connection.enabled=true
                 AND send_orders=true
                 AND order's odoo_sync_status is missing / "pending" / "failed".
        Returns a flat list of marketplace splits and restaurant orders.
        """
        connected_shop_ids = await db.shops.distinct(
            "id",
            {"odoo_connection.enabled": True, "odoo_connection.send_orders": True}
        )
        connected_restaurant_ids = await db.restaurants.distinct(
            "id",
            {"odoo_connection.enabled": True, "odoo_connection.send_orders": True}
        )

        pending = []

        if connected_shop_ids:
            splits = await db.seller_order_splits.find(
                {
                    "shop_id": {"$in": connected_shop_ids},
                    "$or": [
                        {"odoo_sync_status": {"$in": [None, "pending", "failed", "not_required"]}},
                        {"odoo_sync_status": {"$exists": False}},
                    ],
                },
                {"_id": 0}
            ).sort("created_at", -1).limit(500).to_list(500)
            for s in splits:
                s["entity_type"] = "shop_order_split"
            pending.extend(splits)

        if connected_restaurant_ids:
            r_orders = await db.restaurant_orders.find(
                {
                    "restaurant_id": {"$in": connected_restaurant_ids},
                    "$or": [
                        {"odoo_sync_status": {"$in": [None, "pending", "failed", "not_required"]}},
                        {"odoo_sync_status": {"$exists": False}},
                    ],
                },
                {"_id": 0}
            ).sort("created_at", -1).limit(500).to_list(500)
            for o in r_orders:
                o["entity_type"] = "restaurant_order"
            pending.extend(r_orders)

        return pending

    @router.get("/delivery-updates/pending")
    async def get_pending_delivery_updates(user=Depends(verify_admin_or_service_token)):
        """
        Get delivered orders whose delivery update has not yet been pushed to Odoo.
        Looks at seller_order_splits with delivery_status in
        {delivered, failed, returned} and odoo_sync_status not 'synced'.
        Only orders for shops/restaurants with odoo_connection.send_delivery_updates=true.
        """
        connected_shop_ids = await db.shops.distinct(
            "id",
            {"odoo_connection.enabled": True, "odoo_connection.send_delivery_updates": True}
        )
        connected_restaurant_ids = await db.restaurants.distinct(
            "id",
            {"odoo_connection.enabled": True, "odoo_connection.send_delivery_updates": True}
        )

        updates = []

        if connected_shop_ids:
            splits = await db.seller_order_splits.find(
                {
                    "shop_id": {"$in": connected_shop_ids},
                    "delivery_status": {"$in": ["delivered", "failed", "returned"]},
                    "$or": [
                        {"odoo_sync_status": {"$ne": "synced"}},
                        {"odoo_sync_status": {"$exists": False}},
                    ],
                },
                {"_id": 0}
            ).sort("delivered_at", -1).limit(500).to_list(500)
            for s in splits:
                s["entity_type"] = "shop_delivery"
            updates.extend(splits)

        if connected_restaurant_ids:
            r_orders = await db.restaurant_orders.find(
                {
                    "restaurant_id": {"$in": connected_restaurant_ids},
                    "delivery_status": {"$in": ["delivered", "failed", "returned"]},
                    "$or": [
                        {"odoo_sync_status": {"$ne": "synced"}},
                        {"odoo_sync_status": {"$exists": False}},
                    ],
                },
                {"_id": 0}
            ).sort("delivered_at", -1).limit(500).to_list(500)
            for o in r_orders:
                o["entity_type"] = "restaurant_delivery"
            updates.extend(r_orders)

        return updates

    @router.get("/payout-summaries/pending")
    async def get_pending_payout_summaries(user=Depends(verify_admin_or_service_token)):
        """
        Get seller payout summaries pending Odoo export.
        Returns seller_payouts with odoo_export_status not 'exported'.
        """
        payouts = await db.seller_payouts.find(
            {
                "$or": [
                    {"odoo_export_status": {"$in": [None, "not_exported", "pending", "failed"]}},
                    {"odoo_export_status": {"$exists": False}},
                ]
            },
            {"_id": 0}
        ).sort("created_at", -1).limit(500).to_list(500)
        return payouts

    @router.get("/driver-cash/pending")
    async def get_pending_driver_cash(user=Depends(verify_admin_or_service_token)):
        """
        Aggregate driver cash positions from seller_order_splits that have been
        delivered & cash collected but not yet marked exported to Odoo.
        Returns a list grouped by driver_id with totals.
        """
        pipeline = [
            {
                "$match": {
                    "delivery_status": "delivered",
                    "cash_collected_at": {"$ne": None},
                    "$or": [
                        {"odoo_export_status": {"$ne": "exported"}},
                        {"odoo_export_status": {"$exists": False}},
                    ],
                    "driver_id": {"$ne": None},
                }
            },
            {
                "$group": {
                    "_id": "$driver_id",
                    "cash_collected": {"$sum": {"$ifNull": ["$order_total_usd", 0]}},
                    "cash_handed_over": {"$sum": {"$ifNull": ["$cash_handed_over_usd", 0]}},
                    "delivery_count": {"$sum": 1},
                    "related_orders": {"$addToSet": "$order_id"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "driver_id": "$_id",
                    "cash_collected": 1,
                    "cash_handed_over": 1,
                    "cash_balance": {"$subtract": ["$cash_collected", "$cash_handed_over"]},
                    "delivery_count": 1,
                    "related_orders": 1,
                    "odoo_export_status": {"$literal": "not_exported"},
                }
            },
        ]
        try:
            rows = await db.seller_order_splits.aggregate(pipeline).to_list(500)
        except Exception as e:
            log.error(f"driver-cash aggregation failed: {e}")
            rows = []
        return rows

    return router
