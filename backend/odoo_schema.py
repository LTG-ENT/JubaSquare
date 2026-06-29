"""
Odoo Integration Schema and Models for JubaSquare

This module defines all Odoo-related fields and models for shops, restaurants,
products, orders, and sync logs. Admin-only configuration.
"""
from typing import Optional, Literal, List
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# Odoo Connection Settings (for Shops & Restaurants)
# ============================================================================

class OdooConnectionSettings(BaseModel):
    """Odoo connection configuration for a shop or restaurant"""
    enabled: bool = False  # Connect this shop/restaurant to Odoo
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    warehouse_id: Optional[str] = None
    warehouse_name: Optional[str] = None
    pricelist_id: Optional[str] = None
    pricelist_name: Optional[str] = None
    pos_config_id: Optional[str] = None
    
    # Sync toggles
    sync_products: bool = False  # Sync products/menu items from Odoo
    sync_stock: bool = False  # Sync stock levels from Odoo
    send_orders: bool = False  # Send orders to Odoo
    send_delivery_updates: bool = False  # Send delivery updates to Odoo
    
    # Sync status
    last_sync_at: Optional[datetime] = None
    sync_status: Literal["not_configured", "active", "error", "disabled"] = "not_configured"
    sync_error: Optional[str] = None


# ============================================================================
# Product/Menu Item Odoo Fields
# ============================================================================

class OdooProductSync(BaseModel):
    """Odoo sync fields for products and menu items"""
    odoo_source: bool = False  # True if product comes from Odoo
    odoo_product_id: Optional[str] = None
    odoo_product_sku: Optional[str] = None
    odoo_publish: bool = False  # Publish in JubaSquare
    odoo_hidden: bool = False  # Hide in JubaSquare
    odoo_sync_price: bool = False
    odoo_sync_stock: bool = False
    odoo_sync_image: bool = False
    odoo_sync_description: bool = False
    odoo_last_sync_at: Optional[datetime] = None
    odoo_sync_status: Literal["not_synced", "synced", "failed", "unpublished"] = "not_synced"
    odoo_sync_error: Optional[str] = None


# ============================================================================
# Wholesale Fields (MOQ/Bulk Price optional)
# ============================================================================

class PricingTier(BaseModel):
    """Wholesale pricing tier"""
    quantity: int = Field(gt=0)
    price: float = Field(ge=0)


class WholesaleFields(BaseModel):
    """Wholesale product fields - all optional when is_wholesale=True"""
    is_wholesale: bool = False
    min_order_qty: Optional[int] = Field(default=None, gt=0)
    bulk_price_usd: Optional[float] = Field(default=None, ge=0)
    pricing_tiers: Optional[List[PricingTier]] = None


# ============================================================================
# Order Odoo Sync Fields
# ============================================================================

class OdooOrderSync(BaseModel):
    """Odoo sync fields for orders"""
    odoo_sync_status: Literal["not_required", "pending", "synced", "failed", "ignored"] = "not_required"
    odoo_sale_order_id: Optional[str] = None
    odoo_sale_order_name: Optional[str] = None
    odoo_sync_error: Optional[str] = None
    odoo_last_sync_at: Optional[datetime] = None
    odoo_attempt_count: int = 0
    sub_order_id: Optional[str] = None  # For split orders
    parent_order_id: Optional[str] = None


# ============================================================================
# Driver Delivery Update Odoo Fields
# ============================================================================

class OdooDeliverySync(BaseModel):
    """Odoo sync fields for delivery updates"""
    order_id: str
    sub_order_id: Optional[str] = None
    shop_id: Optional[str] = None
    restaurant_id: Optional[str] = None
    driver_id: str
    driver_name: str
    delivery_status: str
    proof_image_url: Optional[str] = None
    cash_collected: float = 0.0
    cash_handed_over: float = 0.0
    cash_balance: float = 0.0
    notes: Optional[str] = None
    odoo_sync_status: Literal["not_required", "pending", "synced", "failed", "ignored"] = "not_required"
    odoo_sync_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Seller Payout Summary (for potential Odoo export)
# ============================================================================

class SellerPayoutSummary(BaseModel):
    """Seller payout summary - prepared for potential Odoo export"""
    seller_id: str
    seller_name: str
    shop_id: str
    shop_name: str
    period_start: datetime
    period_end: datetime
    total_sales: float = 0.0
    commission_amount: float = 0.0
    refunds: float = 0.0
    penalties: float = 0.0
    adjustments: float = 0.0
    payout_due: float = 0.0  # total_sales - commission - refunds - penalties + adjustments
    payout_status: Literal["pending", "approved", "paid", "rejected", "on_hold"] = "pending"
    odoo_export_status: Literal["not_exported", "pending", "exported", "failed"] = "not_exported"
    odoo_export_error: Optional[str] = None
    odoo_last_export_at: Optional[datetime] = None


# ============================================================================
# Driver Cash Summary (for potential Odoo export)
# ============================================================================

class DriverCashSummary(BaseModel):
    """Driver cash summary - prepared for potential Odoo export"""
    driver_id: str
    driver_name: str
    period_start: datetime
    period_end: datetime
    cash_collected: float = 0.0
    cash_handed_over: float = 0.0
    cash_balance: float = 0.0  # collected - handed_over
    related_orders: List[str] = Field(default_factory=list)
    odoo_export_status: Literal["not_exported", "pending", "exported", "failed"] = "not_exported"
    odoo_export_error: Optional[str] = None


# ============================================================================
# Odoo Sync Log
# ============================================================================

class OdooSyncLog(BaseModel):
    """Log entry for Odoo sync operations"""
    id: str
    operation_type: Literal[
        "test_connection",
        "product_sync",
        "stock_sync",
        "order_sync",
        "delivery_update",
        "payout_summary",
        "driver_cash_summary",
        "webhook"
    ]
    direction: Literal["juba_to_odoo", "odoo_to_juba"]
    status: Literal["success", "failed", "ignored", "duplicate", "pending"]
    shop_id: Optional[str] = None
    restaurant_id: Optional[str] = None
    product_id: Optional[str] = None
    menu_item_id: Optional[str] = None
    order_id: Optional[str] = None
    sub_order_id: Optional[str] = None
    seller_id: Optional[str] = None
    driver_id: Optional[str] = None
    request_payload: Optional[dict] = None
    response_payload: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Webhook Payloads (from Odoo to JubaSquare)
# ============================================================================

class OdooProductUpsert(BaseModel):
    """Webhook payload for product upsert from Odoo"""
    shop_id: Optional[str] = None
    restaurant_id: Optional[str] = None
    odoo_product_id: str
    odoo_product_sku: Optional[str] = None
    name: str
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    stock_quantity: Optional[int] = None
    publish: bool = True
    # Wholesale fields
    wholesale_enabled: bool = False
    minimum_order_qty: Optional[int] = None
    bulk_price: Optional[float] = None
    pricing_tiers: Optional[List[PricingTier]] = None
    # Sync settings
    sync_price: bool = True
    sync_stock: bool = True
    sync_image: bool = True
    sync_description: bool = True


class OdooStockUpdate(BaseModel):
    """Webhook payload for stock update from Odoo"""
    shop_id: Optional[str] = None
    restaurant_id: Optional[str] = None
    odoo_product_id: str
    stock_quantity: int


class OdooProductUnpublish(BaseModel):
    """Webhook payload to unpublish product"""
    shop_id: Optional[str] = None
    restaurant_id: Optional[str] = None
    odoo_product_id: str


# ============================================================================
# Admin API Request/Response Models
# ============================================================================

class OdooConnectionUpdate(BaseModel):
    """Admin request to update Odoo connection settings"""
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


class OdooTestConnectionRequest(BaseModel):
    """Request to test Odoo connection"""
    shop_id: Optional[str] = None
    restaurant_id: Optional[str] = None


class OdooRetryFailedRequest(BaseModel):
    """Request to retry failed sync operations"""
    log_ids: Optional[List[str]] = None  # If None, retry all failed
    operation_type: Optional[str] = None  # Filter by type
