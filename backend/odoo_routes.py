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
from fastapi import APIRouter, HTTPException, Depends, Header

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

log = logging.getLogger(__name__)

# Odoo webhook secret token (from environment)
ODOO_WEBHOOK_TOKEN = os.environ.get("ODOO_WEBHOOK_TOKEN", "")

def create_odoo_routes(db, admin_only):
    """
    Create Odoo integration routes
    
    Args:
        db: MongoDB database instance
        admin_only: Dependency for admin-only routes
    """
    router = APIRouter(prefix="/api/odoo", tags=["odoo"])
    
    # ========================================================================
    # Webhook Authentication
    # ========================================================================
    
    async def verify_odoo_webhook(x_jubasquare_odoo_token: str = Header(None)):
        """Verify Odoo webhook request"""
        if not ODOO_WEBHOOK_TOKEN:
            log.error("ODOO_WEBHOOK_TOKEN not configured")
            raise HTTPException(status_code=500, detail="Odoo webhook not configured")
        
        if not x_jubasquare_odoo_token:
            log.warning("Odoo webhook request without token")
            raise HTTPException(status_code=401, detail="Missing Odoo token")
        
        if x_jubasquare_odoo_token != ODOO_WEBHOOK_TOKEN:
            log.warning(f"Invalid Odoo webhook token attempt")
            raise HTTPException(status_code=403, detail="Invalid Odoo token")
        
        return True
    
    # ========================================================================
    # Health Check
    # ========================================================================
    
    @router.get("/health")
    async def odoo_health_check():
        """Public health check for Odoo integration"""
        return {
            "status": "ok",
            "service": "jubasquare-odoo-integration",
            "webhook_configured": bool(ODOO_WEBHOOK_TOKEN),
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
            
            # Prepare product/menu item data
            product_data = {
                "name": payload.name,
                "description": payload.description or "",
                "price_usd": payload.price,
                "image_url": payload.image_url or "",
                "stock_quantity": payload.stock_quantity if payload.stock_quantity is not None else 0,
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
                "min_order_qty": payload.minimum_order_qty,
                "bulk_price_usd": payload.bulk_price,
                "pricing_tiers": [tier.dict() for tier in payload.pricing_tiers] if payload.pricing_tiers else None
            }
            
            # Add shop_id or restaurant_id
            if entity_type == "shop":
                product_data["shop_id"] = payload.shop_id
            else:
                product_data["restaurant_id"] = payload.restaurant_id
            
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
                        "stock_quantity": payload.stock_quantity,
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


def create_admin_odoo_routes(db, admin_only):
    """
    Create admin-only Odoo management routes
    
    Args:
        db: MongoDB database instance
        admin_only: Dependency for admin-only routes
    """
    router = APIRouter(prefix="/api/admin/odoo", tags=["admin-odoo"])
    
    @router.get("/shops")
    async def get_odoo_shops(user=Depends(admin_only)):
        """Get all shops with Odoo connection status"""
        shops = await db.shops.find(
            {},
            {"_id": 0, "id": 1, "name": 1, "odoo_connection": 1}
        ).to_list(1000)
        return shops
    
    @router.get("/restaurants")
    async def get_odoo_restaurants(user=Depends(admin_only)):
        """Get all restaurants with Odoo connection status"""
        restaurants = await db.restaurants.find(
            {},
            {"_id": 0, "id": 1, "name": 1, "odoo_connection": 1}
        ).to_list(1000)
        return restaurants
    
    @router.get("/sync-logs")
    async def get_odoo_sync_logs(
        limit: int = 100,
        status: Optional[str] = None,
        operation_type: Optional[str] = None,
        user=Depends(admin_only)
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
        user=Depends(admin_only)
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
        user=Depends(admin_only)
    ):
        """Retry failed sync operations"""
        return {
            "status": "placeholder",
            "message": "Retry failed syncs - to be implemented"
        }
    
    @router.get("/products/pending")
    async def get_pending_product_syncs(user=Depends(admin_only)):
        """Get products pending Odoo sync"""
        return {"status": "placeholder", "message": "Pending products - to be implemented"}
    
    @router.get("/orders/pending")
    async def get_pending_order_syncs(user=Depends(admin_only)):
        """Get orders pending Odoo sync"""
        return {"status": "placeholder", "message": "Pending orders - to be implemented"}
    
    return router
