# JubaSquare Odoo 18 Integration - API Documentation

**Version:** 1.0  
**Date:** May 14, 2026  
**Webhook Token Location:** Backend environment variable `ODOO_WEBHOOK_TOKEN`

---

## Security & Authentication

### Webhook Authentication
All Odoo → JubaSquare webhook endpoints require:
- **Header:** `X-JubaSquare-Odoo-Token`
- **Value:** The secure token from backend `.env` file (64-character hex string)
- **Location:** This token is stored in `/app/backend/.env` as `ODOO_WEBHOOK_TOKEN`

**⚠️ CRITICAL: Never expose this token in frontend, logs, or UI. Backend only.**

### Admin Authentication
All admin endpoints require:
- **Header:** `Authorization: Bearer {jwt_token}`
- **Role:** User must have `role: "admin"`

---

## API Endpoint Summary

### Webhook Endpoints (Odoo → JubaSquare)
```
GET  /api/odoo/health                      # Health check
POST /api/odoo/products/upsert             # Create/update product
POST /api/odoo/products/stock-update       # Update stock levels
POST /api/odoo/products/unpublish          # Hide/unpublish product
POST /api/odoo/orders/status-update        # Update order status (placeholder)
POST /api/odoo/delivery/status-update      # Update delivery status (placeholder)
POST /api/odoo/invoice/status-update       # Update invoice status (placeholder)
```

### Admin Endpoints (JubaSquare Admin → Odoo)
```
GET  /api/admin/odoo/shops                        # List shops with Odoo status
GET  /api/admin/odoo/restaurants                  # List restaurants with Odoo status
GET  /api/admin/odoo/sync-logs                    # View sync operation logs
POST /api/admin/odoo/test-connection              # Test Odoo connection
POST /api/admin/odoo/retry-failed                 # Retry failed operations
GET  /api/admin/odoo/products/pending             # Get pending product syncs (placeholder)
GET  /api/admin/odoo/orders/pending               # Get pending order syncs (placeholder)
GET  /api/admin/odoo/delivery-updates/pending     # Get pending delivery updates (placeholder)
GET  /api/admin/odoo/payout-summaries/pending     # Get pending seller payouts (placeholder)
GET  /api/admin/odoo/driver-cash/pending          # Get pending driver cash summaries (placeholder)
```

---

## Webhook Endpoints (Odoo → JubaSquare)

### 1. Health Check

**Endpoint:** `GET /api/odoo/health`  
**Authentication:** None (public)  
**Purpose:** Check if JubaSquare Odoo integration is available

**Response:**
```json
{
  "status": "ok",
  "service": "jubasquare-odoo-integration",
  "webhook_configured": true,
  "timestamp": "2026-05-14T12:00:00.000000"
}
```

---

### 2. Product Upsert

**Endpoint:** `POST /api/odoo/products/upsert`  
**Authentication:** Required  
**Headers:**
```
X-JubaSquare-Odoo-Token: {your_webhook_token}
Content-Type: application/json
```

**Purpose:** Create new product or update existing product from Odoo

**Request Body:**
```json
{
  "shop_id": "uuid-string",                    // Required if not restaurant
  "restaurant_id": "uuid-string",              // Required if not shop
  "odoo_product_id": "123",                    // Required - Odoo product ID
  "odoo_product_sku": "SKU-001",               // Optional - Product SKU
  "name": "Product Name",                      // Required
  "description": "Product description",        // Optional
  "price": 29.99,                              // Required - Price in USD
  "image_url": "https://example.com/img.jpg",  // Optional
  "stock_quantity": 100,                       // Optional - Default 0
  "publish": true,                             // Optional - Default true
  "wholesale_enabled": false,                  // Optional - Default false
  "minimum_order_qty": 10,                     // Optional - Can be null even if wholesale_enabled=true
  "bulk_price": 25.00,                         // Optional - Can be null
  "pricing_tiers": [                           // Optional - Can be null or empty
    {
      "quantity": 50,
      "price": 23.00
    },
    {
      "quantity": 100,
      "price": 20.00
    }
  ],
  "sync_price": true,                          // Optional - Default true
  "sync_stock": true,                          // Optional - Default true
  "sync_image": true,                          // Optional - Default true
  "sync_description": true                     // Optional - Default true
}
```

**Success Response (200):**
```json
{
  "status": "success",
  "product_id": "uuid-of-product",
  "action": "created",                         // or "updated"
  "log_id": "uuid-of-log-entry"
}
```

**Ignored Response (200):**
```json
{
  "status": "ignored",
  "message": "Shop not connected to Odoo"
}
```

**Error Response (401):**
```json
{
  "detail": "Missing Odoo token"
}
```

**Error Response (403):**
```json
{
  "detail": "Invalid Odoo token"
}
```

**Error Response (400):**
```json
{
  "detail": "Either shop_id or restaurant_id required"
}
```

**Error Response (500):**
```json
{
  "detail": "Product upsert failed: {error_details}"
}
```

**Rules:**
- Only processes if shop/restaurant has `odoo_connection.enabled = true`
- If shop/restaurant not connected, returns `status: "ignored"` (NOT an error)
- Updates existing product if `odoo_product_id` matches
- Creates new product if no match found
- Wholesale fields (MOQ, bulk_price, pricing_tiers) are **always optional**
- Product can be `wholesale_enabled: true` with all wholesale fields `null`

---

### 3. Stock Update

**Endpoint:** `POST /api/odoo/products/stock-update`  
**Authentication:** Required  
**Headers:**
```
X-JubaSquare-Odoo-Token: {your_webhook_token}
Content-Type: application/json
```

**Purpose:** Update stock quantity for existing product

**Request Body:**
```json
{
  "shop_id": "uuid-string",           // Required if not restaurant
  "restaurant_id": "uuid-string",     // Required if not shop
  "odoo_product_id": "123",           // Required
  "stock_quantity": 50                // Required
}
```

**Success Response (200):**
```json
{
  "status": "success",
  "log_id": "uuid-of-log-entry"
}
```

**Ignored Response (200):**
```json
{
  "status": "ignored",
  "message": "Product not found or stock sync disabled"
}
```

**Rules:**
- Only updates if shop/restaurant has `odoo_connection.enabled = true`
- Only updates if product has `odoo_sync_stock = true`
- Returns "ignored" if conditions not met (NOT an error)

---

### 4. Product Unpublish

**Endpoint:** `POST /api/odoo/products/unpublish`  
**Authentication:** Required  
**Headers:**
```
X-JubaSquare-Odoo-Token: {your_webhook_token}
Content-Type: application/json
```

**Purpose:** Hide/unpublish product in JubaSquare

**Request Body:**
```json
{
  "shop_id": "uuid-string",           // Required if not restaurant
  "restaurant_id": "uuid-string",     // Required if not shop
  "odoo_product_id": "123"            // Required
}
```

**Success Response (200):**
```json
{
  "status": "success",
  "log_id": "uuid-of-log-entry"
}
```

**Error Response (500):**
```json
{
  "detail": "Unpublish failed: {error_details}"
}
```

**Rules:**
- Sets `odoo_publish = false` and `odoo_hidden = true`
- Sets `odoo_sync_status = "unpublished"`

---

### 5-7. Placeholder Endpoints

**Endpoints:**
- `POST /api/odoo/orders/status-update`
- `POST /api/odoo/delivery/status-update`
- `POST /api/odoo/invoice/status-update`

**Authentication:** Required  
**Status:** Placeholder - return success message  
**Purpose:** Reserved for future Odoo module implementation

**Response (200):**
```json
{
  "status": "placeholder",
  "message": "Order status update endpoint - to be implemented"
}
```

---

## Admin Endpoints (JubaSquare → Odoo Module)

### 8. Get Odoo-Connected Shops

**Endpoint:** `GET /api/admin/odoo/shops`  
**Authentication:** Admin required  
**Headers:**
```
Authorization: Bearer {admin_jwt_token}
```

**Purpose:** List all shops with their Odoo connection status

**Response (200):**
```json
[
  {
    "id": "shop-uuid-1",
    "name": "Tech Shop",
    "odoo_connection": {
      "enabled": true,
      "company_id": "1",
      "company_name": "My Company",
      "warehouse_id": "WH/01",
      "warehouse_name": "Main Warehouse",
      "pricelist_id": "1",
      "pricelist_name": "Public Pricelist",
      "pos_config_id": "pos_config_1",
      "sync_products": true,
      "sync_stock": true,
      "send_orders": true,
      "send_delivery_updates": true,
      "last_sync_at": "2026-05-14T12:00:00.000000",
      "sync_status": "active",
      "sync_error": null
    }
  },
  {
    "id": "shop-uuid-2",
    "name": "Fashion Store",
    "odoo_connection": {
      "enabled": false,
      "company_id": null,
      "company_name": null,
      "warehouse_id": null,
      "warehouse_name": null,
      "pricelist_id": null,
      "pricelist_name": null,
      "pos_config_id": null,
      "sync_products": false,
      "sync_stock": false,
      "send_orders": false,
      "send_delivery_updates": false,
      "last_sync_at": null,
      "sync_status": "not_configured",
      "sync_error": null
    }
  }
]
```

---

### 9. Get Odoo-Connected Restaurants

**Endpoint:** `GET /api/admin/odoo/restaurants`  
**Authentication:** Admin required  
**Headers:**
```
Authorization: Bearer {admin_jwt_token}
```

**Purpose:** List all restaurants with their Odoo connection status

**Response:** Same structure as shops endpoint, but with restaurant data

---

### 10. Get Sync Logs

**Endpoint:** `GET /api/admin/odoo/sync-logs`  
**Authentication:** Admin required  
**Query Parameters:**
- `limit` (optional, default: 100) - Max number of logs
- `status` (optional) - Filter by status: success/failed/pending/ignored/duplicate
- `operation_type` (optional) - Filter by type: product_sync/stock_sync/order_sync/test_connection/webhook

**Example Request:**
```
GET /api/admin/odoo/sync-logs?limit=50&status=failed&operation_type=product_sync
Authorization: Bearer {admin_jwt_token}
```

**Response (200):**
```json
[
  {
    "id": "log-uuid-1",
    "operation_type": "product_sync",
    "direction": "odoo_to_juba",
    "status": "success",
    "shop_id": "shop-uuid",
    "restaurant_id": null,
    "product_id": "product-uuid",
    "menu_item_id": null,
    "order_id": null,
    "sub_order_id": null,
    "seller_id": null,
    "driver_id": null,
    "request_payload": {
      "odoo_product_id": "123",
      "name": "Product Name",
      "price": 29.99
    },
    "response_payload": {
      "product_id": "product-uuid",
      "action": "created"
    },
    "error_message": null,
    "created_at": "2026-05-14T12:00:00.000000"
  },
  {
    "id": "log-uuid-2",
    "operation_type": "stock_sync",
    "direction": "odoo_to_juba",
    "status": "failed",
    "shop_id": "shop-uuid",
    "restaurant_id": null,
    "product_id": null,
    "menu_item_id": null,
    "order_id": null,
    "sub_order_id": null,
    "seller_id": null,
    "driver_id": null,
    "request_payload": {
      "odoo_product_id": "456",
      "stock_quantity": 100
    },
    "response_payload": null,
    "error_message": "Product not found",
    "created_at": "2026-05-14T11:55:00.000000"
  }
]
```

---

### 11. Test Connection

**Endpoint:** `POST /api/admin/odoo/test-connection`  
**Authentication:** Admin required  
**Headers:**
```
Authorization: Bearer {admin_jwt_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "shop_id": "shop-uuid",          // Required if testing shop
  "restaurant_id": "restaurant-uuid"  // Required if testing restaurant
}
```

**Response (200):**
```json
{
  "status": "placeholder",
  "message": "Test connection - to be implemented by Odoo module",
  "log_id": "log-uuid"
}
```

**Purpose:** Test if Odoo can communicate with this shop/restaurant. Your Odoo module should implement the actual connection test logic.

---

### 12. Retry Failed Syncs

**Endpoint:** `POST /api/admin/odoo/retry-failed`  
**Authentication:** Admin required  
**Headers:**
```
Authorization: Bearer {admin_jwt_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "log_ids": ["log-uuid-1", "log-uuid-2"],  // Optional - specific logs to retry
  "operation_type": "product_sync"          // Optional - filter by type
}
```

**Response (200):**
```json
{
  "status": "placeholder",
  "message": "Retry failed syncs - to be implemented"
}
```

**Purpose:** Retry failed sync operations. Your Odoo module should implement the retry logic.

---

### 13-17. Pending Data Endpoints (Placeholders)

**Endpoints:**
- `GET /api/admin/odoo/products/pending`
- `GET /api/admin/odoo/orders/pending`
- `GET /api/admin/odoo/delivery-updates/pending`
- `GET /api/admin/odoo/payout-summaries/pending`
- `GET /api/admin/odoo/driver-cash/pending`

**Authentication:** Admin required  
**Status:** Placeholder  
**Purpose:** Your Odoo module can call these to fetch pending data from JubaSquare

**Response:**
```json
{
  "status": "placeholder",
  "message": "Pending {resource} - to be implemented"
}
```

---

## Important Rules & Behaviors

### 1. Connection Status
- **Default:** All shops/restaurants have `odoo_connection.enabled = false`
- **Admin Control:** Only admin can enable Odoo for specific shops/restaurants
- **Per-Entity:** Each shop/restaurant has independent Odoo configuration

### 2. Sync Status Values
- `not_configured` - Odoo not enabled
- `disabled` - Odoo was enabled but now disabled
- `active` - Odoo enabled and working
- `error` - Odoo enabled but last sync failed

### 3. Order Sync Status
- **Not connected:** `odoo_sync_status = "ignored"` (NOT "failed")
- **Connected:** `odoo_sync_status = "pending"` until Odoo confirms
- **After confirm:** `odoo_sync_status = "synced"`
- **On error:** `odoo_sync_status = "failed"`

### 4. Wholesale Product Rules
- Product can have `is_wholesale = true` with all these as `null`:
  - `min_order_qty`
  - `bulk_price_usd`
  - `pricing_tiers`
- Odoo sync **MUST NOT fail** if wholesale fields are empty
- All wholesale fields are **optional** when `wholesale_enabled = true`

### 5. Security
- **Webhook token:** Never exposed to frontend, stored only in backend `.env`
- **Admin endpoints:** Require admin JWT token
- **Seller blocking:** Sellers cannot access Odoo settings via API or UI
- **Driver blocking:** Drivers cannot access Odoo settings
- **Customer blocking:** Customers cannot access Odoo settings

### 6. Ignored vs Failed
- **Ignored:** Shop/restaurant not connected to Odoo (expected, not an error)
- **Failed:** Shop/restaurant is connected but operation failed (needs investigation)

---

## Error Codes Reference

| Code | Meaning |
|------|---------|
| 200 | Success or Ignored (both are OK) |
| 400 | Bad request (missing required fields) |
| 401 | Missing authentication token |
| 403 | Invalid authentication token |
| 404 | Resource not found |
| 500 | Server error (sync failed) |

---

## Integration Flow

### Product Sync (Odoo → JubaSquare)
1. Odoo detects product change
2. Odoo calls `POST /api/odoo/products/upsert`
3. JubaSquare checks if shop/restaurant has Odoo enabled
4. If not enabled: Return `status: "ignored"`
5. If enabled: Create/update product, return `status: "success"`
6. Log operation in `odoo_sync_logs` collection

### Order Sync (JubaSquare → Odoo)
1. Customer places order in JubaSquare
2. JubaSquare checks if shop/restaurant has Odoo enabled
3. If not enabled: Set `odoo_sync_status = "ignored"`
4. If enabled: Set `odoo_sync_status = "pending"`
5. Your Odoo module fetches pending orders (implement endpoint)
6. Your Odoo module confirms order via webhook
7. JubaSquare updates `odoo_sync_status = "synced"`

---

## Environment Variables

**Backend `.env` Required:**
```bash
ODOO_WEBHOOK_TOKEN=f1dcc35149542ed7afa011c171641617bb00913912f54be470c8efb04770fe9a
```

**⚠️ SECURITY:** This token is 64-character hex. Rotate before production deployment. Never commit to Git.

---

## Testing the Integration

### 1. Test Health Endpoint
```bash
curl http://localhost:8001/api/odoo/health
```

### 2. Test Product Upsert
```bash
curl -X POST http://localhost:8001/api/odoo/products/upsert \
  -H "X-JubaSquare-Odoo-Token: your_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_id": "shop-uuid",
    "odoo_product_id": "123",
    "name": "Test Product",
    "price": 29.99,
    "publish": true
  }'
```

### 3. Test Admin Endpoints (requires admin login)
```bash
# Get admin JWT token first
TOKEN=$(curl -X POST http://localhost:8001/api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@LTG.com","password":"Kokobleake1"}' \
  | jq -r '.token')

# Get shops with Odoo status
curl http://localhost:8001/api/admin/odoo/shops \
  -H "Authorization: Bearer $TOKEN"

# Get sync logs
curl http://localhost:8001/api/admin/odoo/sync-logs?limit=10 \
  -H "Authorization: Bearer $TOKEN"
```

---

## Database Schema Reference

### Shop/Restaurant Odoo Connection
```python
{
  "odoo_connection": {
    "enabled": bool,
    "company_id": str | null,
    "company_name": str | null,
    "warehouse_id": str | null,
    "warehouse_name": str | null,
    "pricelist_id": str | null,
    "pricelist_name": str | null,
    "pos_config_id": str | null,
    "sync_products": bool,
    "sync_stock": bool,
    "send_orders": bool,
    "send_delivery_updates": bool,
    "last_sync_at": datetime | null,
    "sync_status": "not_configured" | "active" | "error" | "disabled",
    "sync_error": str | null
  }
}
```

### Product Odoo Fields
```python
{
  "odoo_source": bool,           # True if from Odoo
  "odoo_product_id": str | null,
  "odoo_product_sku": str | null,
  "odoo_publish": bool,
  "odoo_hidden": bool,
  "odoo_sync_price": bool,
  "odoo_sync_stock": bool,
  "odoo_sync_image": bool,
  "odoo_sync_description": bool,
  "odoo_last_sync_at": datetime | null,
  "odoo_sync_status": "not_synced" | "synced" | "failed" | "unpublished",
  "odoo_sync_error": str | null
}
```

### Order Odoo Fields
```python
{
  "odoo_sync_status": "not_required" | "pending" | "synced" | "failed" | "ignored",
  "odoo_sale_order_id": str | null,
  "odoo_sale_order_name": str | null,
  "odoo_sync_error": str | null,
  "odoo_last_sync_at": datetime | null,
  "odoo_attempt_count": int
}
```

---

**End of Documentation**

For questions or issues, refer to:
- Backend schema: `/app/backend/odoo_schema.py`
- Backend routes: `/app/backend/odoo_routes.py`
- Frontend UI: `/app/frontend/src/pages/AdminDashboard.jsx` (OdooConnectionSection)
