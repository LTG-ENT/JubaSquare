# Odoo 18 Integration - Sample Payloads

Complete JSON examples for all Odoo ↔ JubaSquare operations.

---

## 1. Product Upsert (Odoo → JubaSquare)

### Regular Product (Not Wholesale)
```json
{
  "shop_id": "550e8400-e29b-41d4-a716-446655440000",
  "odoo_product_id": "123",
  "odoo_product_sku": "TECH-LAPTOP-001",
  "name": "Gaming Laptop Pro 15",
  "description": "High-performance gaming laptop with RTX 4070, 32GB RAM, 1TB SSD",
  "price": 1299.99,
  "image_url": "https://cdn.example.com/products/laptop-gaming-pro-15.jpg",
  "stock_quantity": 25,
  "publish": true,
  "wholesale_enabled": false,
  "sync_price": true,
  "sync_stock": true,
  "sync_image": true,
  "sync_description": true
}
```

### Wholesale Product (Complete)
```json
{
  "shop_id": "550e8400-e29b-41d4-a716-446655440000",
  "odoo_product_id": "456",
  "odoo_product_sku": "BULK-CABLE-USB-C",
  "name": "USB-C Cable 2m - Bulk Pack",
  "description": "High-quality USB-C to USB-C cable, 100W fast charging",
  "price": 8.99,
  "image_url": "https://cdn.example.com/products/usb-c-cable.jpg",
  "stock_quantity": 5000,
  "publish": true,
  "wholesale_enabled": true,
  "minimum_order_qty": 50,
  "bulk_price": 7.50,
  "pricing_tiers": [
    {
      "quantity": 100,
      "price": 6.99
    },
    {
      "quantity": 500,
      "price": 6.50
    },
    {
      "quantity": 1000,
      "price": 5.99
    }
  ],
  "sync_price": true,
  "sync_stock": true,
  "sync_image": true,
  "sync_description": true
}
```

### Wholesale Product (Minimal - No MOQ/Pricing)
```json
{
  "shop_id": "550e8400-e29b-41d4-a716-446655440000",
  "odoo_product_id": "789",
  "name": "Generic Wholesale Item",
  "description": "Marked as wholesale but pricing not configured yet",
  "price": 15.00,
  "stock_quantity": 100,
  "publish": true,
  "wholesale_enabled": true,
  "minimum_order_qty": null,
  "bulk_price": null,
  "pricing_tiers": null,
  "sync_price": true,
  "sync_stock": true
}
```

### Restaurant Menu Item
```json
{
  "restaurant_id": "660e8400-e29b-41d4-a716-446655440001",
  "odoo_product_id": "MENU-001",
  "odoo_product_sku": "PIZZA-MARGHERITA",
  "name": "Margherita Pizza",
  "description": "Classic pizza with tomato sauce, mozzarella, and fresh basil",
  "price": 12.99,
  "image_url": "https://cdn.example.com/menu/margherita-pizza.jpg",
  "stock_quantity": 999,
  "publish": true,
  "wholesale_enabled": false,
  "sync_price": true,
  "sync_stock": false,
  "sync_image": true,
  "sync_description": true
}
```

---

## 2. Stock Update (Odoo → JubaSquare)

### Shop Product Stock Update
```json
{
  "shop_id": "550e8400-e29b-41d4-a716-446655440000",
  "odoo_product_id": "123",
  "stock_quantity": 18
}
```

### Restaurant Menu Item Stock Update
```json
{
  "restaurant_id": "660e8400-e29b-41d4-a716-446655440001",
  "odoo_product_id": "MENU-001",
  "stock_quantity": 0
}
```

---

## 3. Product Unpublish (Odoo → JubaSquare)

### Unpublish Shop Product
```json
{
  "shop_id": "550e8400-e29b-41d4-a716-446655440000",
  "odoo_product_id": "123"
}
```

### Unpublish Menu Item
```json
{
  "restaurant_id": "660e8400-e29b-41d4-a716-446655440001",
  "odoo_product_id": "MENU-001"
}
```

---

## 4. Order Status Update (Placeholder - Odoo → JubaSquare)

### Order Confirmed in Odoo
```json
{
  "shop_id": "550e8400-e29b-41d4-a716-446655440000",
  "order_id": "770e8400-e29b-41d4-a716-446655440002",
  "odoo_sale_order_id": "SO12345",
  "odoo_sale_order_name": "S00012",
  "status": "confirmed",
  "confirmed_at": "2026-05-14T12:30:00.000000"
}
```

### Order Processing Update
```json
{
  "shop_id": "550e8400-e29b-41d4-a716-446655440000",
  "order_id": "770e8400-e29b-41d4-a716-446655440002",
  "odoo_sale_order_id": "SO12345",
  "status": "processing",
  "updated_at": "2026-05-14T13:00:00.000000"
}
```

---

## 5. Delivery Status Update (Placeholder - Odoo → JubaSquare)

### Delivery Dispatched
```json
{
  "order_id": "770e8400-e29b-41d4-a716-446655440002",
  "delivery_id": "DEL-12345",
  "status": "dispatched",
  "tracking_number": "TRACK123456789",
  "dispatched_at": "2026-05-14T14:00:00.000000"
}
```

### Delivery Completed
```json
{
  "order_id": "770e8400-e29b-41d4-a716-446655440002",
  "delivery_id": "DEL-12345",
  "status": "delivered",
  "delivered_at": "2026-05-14T16:30:00.000000",
  "proof_of_delivery_url": "https://cdn.example.com/pod/DEL-12345.jpg"
}
```

---

## 6. Invoice Status Update (Placeholder - Odoo → JubaSquare)

### Invoice Created
```json
{
  "order_id": "770e8400-e29b-41d4-a716-446655440002",
  "invoice_id": "INV-12345",
  "invoice_number": "INV/2026/05/00123",
  "status": "open",
  "amount_total": 1350.50,
  "currency": "USD",
  "due_date": "2026-05-28T23:59:59.000000",
  "invoice_url": "https://odoo.example.com/invoices/INV-12345"
}
```

### Invoice Paid
```json
{
  "order_id": "770e8400-e29b-41d4-a716-446655440002",
  "invoice_id": "INV-12345",
  "status": "paid",
  "paid_at": "2026-05-20T10:15:00.000000",
  "payment_method": "bank_transfer"
}
```

---

## 7. Pending Orders Response (JubaSquare → Odoo)

### GET /api/admin/odoo/orders/pending Response
```json
[
  {
    "order_id": "770e8400-e29b-41d4-a716-446655440002",
    "shop_id": "550e8400-e29b-41d4-a716-446655440000",
    "shop_name": "Tech Store Pro",
    "customer_id": "880e8400-e29b-41d4-a716-446655440003",
    "customer_name": "John Doe",
    "customer_email": "john.doe@example.com",
    "customer_phone": "+211 123 456 789",
    "total_amount": 1350.50,
    "currency": "USD",
    "payment_method": "cash_on_delivery",
    "delivery_address": {
      "street": "123 Main Street",
      "area": "Juba Central",
      "city": "Juba",
      "country": "South Sudan",
      "postal_code": null,
      "notes": "Gate 2, Building A"
    },
    "items": [
      {
        "product_id": "prod-uuid-1",
        "odoo_product_id": "123",
        "product_name": "Gaming Laptop Pro 15",
        "quantity": 1,
        "unit_price": 1299.99,
        "subtotal": 1299.99
      },
      {
        "product_id": "prod-uuid-2",
        "odoo_product_id": "456",
        "product_name": "USB-C Cable",
        "quantity": 5,
        "unit_price": 8.99,
        "subtotal": 44.95
      }
    ],
    "delivery_fee": 5.56,
    "odoo_sync_status": "pending",
    "created_at": "2026-05-14T12:00:00.000000"
  },
  {
    "order_id": "770e8400-e29b-41d4-a716-446655440004",
    "restaurant_id": "660e8400-e29b-41d4-a716-446655440001",
    "restaurant_name": "Pizza Palace",
    "customer_id": "880e8400-e29b-41d4-a716-446655440005",
    "customer_name": "Jane Smith",
    "customer_email": "jane.smith@example.com",
    "customer_phone": "+211 987 654 321",
    "total_amount": 45.50,
    "currency": "USD",
    "payment_method": "mobile_money",
    "delivery_address": {
      "street": "456 Oak Avenue",
      "area": "Munuki",
      "city": "Juba",
      "country": "South Sudan",
      "postal_code": null,
      "notes": "Call when you arrive"
    },
    "items": [
      {
        "menu_item_id": "menu-uuid-1",
        "odoo_product_id": "MENU-001",
        "item_name": "Margherita Pizza",
        "quantity": 2,
        "unit_price": 12.99,
        "subtotal": 25.98
      },
      {
        "menu_item_id": "menu-uuid-2",
        "odoo_product_id": "MENU-002",
        "item_name": "Garlic Bread",
        "quantity": 1,
        "unit_price": 5.99,
        "subtotal": 5.99
      }
    ],
    "delivery_fee": 3.00,
    "odoo_sync_status": "pending",
    "created_at": "2026-05-14T12:15:00.000000"
  }
]
```

---

## 8. Pending Delivery Updates Response (JubaSquare → Odoo)

### GET /api/admin/odoo/delivery-updates/pending Response
```json
[
  {
    "delivery_update_id": "del-update-uuid-1",
    "order_id": "770e8400-e29b-41d4-a716-446655440002",
    "sub_order_id": null,
    "shop_id": "550e8400-e29b-41d4-a716-446655440000",
    "shop_name": "Tech Store Pro",
    "driver_id": "driver-uuid-1",
    "driver_name": "Ahmed Hassan",
    "driver_phone": "+211 555 123 456",
    "delivery_status": "delivered",
    "proof_image_url": "https://cdn.jubasquare.com/delivery-proof/abc123.jpg",
    "cash_collected": 1350.50,
    "cash_handed_over": 1350.50,
    "cash_balance": 0.00,
    "customer_signature": "base64_encoded_signature_data",
    "notes": "Customer was very satisfied",
    "delivered_at": "2026-05-14T16:30:00.000000",
    "odoo_sync_status": "pending"
  },
  {
    "delivery_update_id": "del-update-uuid-2",
    "order_id": "770e8400-e29b-41d4-a716-446655440006",
    "sub_order_id": null,
    "restaurant_id": "660e8400-e29b-41d4-a716-446655440001",
    "restaurant_name": "Pizza Palace",
    "driver_id": "driver-uuid-2",
    "driver_name": "Mohammed Ali",
    "driver_phone": "+211 555 789 012",
    "delivery_status": "failed",
    "proof_image_url": null,
    "cash_collected": 0.00,
    "cash_handed_over": 0.00,
    "cash_balance": 0.00,
    "customer_signature": null,
    "notes": "Customer was not home, will retry tomorrow",
    "attempted_at": "2026-05-14T18:00:00.000000",
    "odoo_sync_status": "pending"
  }
]
```

---

## 9. Seller Payout Summary Response (JubaSquare → Odoo)

### GET /api/admin/odoo/payout-summaries/pending Response
```json
[
  {
    "payout_summary_id": "payout-uuid-1",
    "seller_id": "seller-uuid-1",
    "seller_name": "Tech Store LLC",
    "seller_email": "seller@techstore.com",
    "shop_id": "550e8400-e29b-41d4-a716-446655440000",
    "shop_name": "Tech Store Pro",
    "period_start": "2026-05-01T00:00:00.000000",
    "period_end": "2026-05-31T23:59:59.000000",
    "total_sales": 15890.75,
    "commission_amount": 1589.08,
    "commission_rate": 0.10,
    "refunds": 250.00,
    "penalties": 50.00,
    "adjustments": 100.00,
    "payout_due": 14101.67,
    "currency": "USD",
    "order_count": 127,
    "payout_status": "approved",
    "odoo_export_status": "not_exported",
    "created_at": "2026-06-01T00:00:00.000000"
  },
  {
    "payout_summary_id": "payout-uuid-2",
    "seller_id": "seller-uuid-2",
    "seller_name": "Pizza Palace Ltd",
    "seller_email": "owner@pizzapalace.com",
    "restaurant_id": "660e8400-e29b-41d4-a716-446655440001",
    "restaurant_name": "Pizza Palace",
    "period_start": "2026-05-01T00:00:00.000000",
    "period_end": "2026-05-31T23:59:59.000000",
    "total_sales": 8450.30,
    "commission_amount": 845.03,
    "commission_rate": 0.10,
    "refunds": 125.00,
    "penalties": 0.00,
    "adjustments": 0.00,
    "payout_due": 7480.27,
    "currency": "USD",
    "order_count": 342,
    "payout_status": "approved",
    "odoo_export_status": "not_exported",
    "created_at": "2026-06-01T00:00:00.000000"
  }
]
```

**Payout Calculation:**
```
payout_due = total_sales - commission_amount - refunds - penalties + adjustments
```

---

## 10. Driver Cash Summary Response (JubaSquare → Odoo)

### GET /api/admin/odoo/driver-cash/pending Response
```json
[
  {
    "cash_summary_id": "cash-uuid-1",
    "driver_id": "driver-uuid-1",
    "driver_name": "Ahmed Hassan",
    "driver_email": "ahmed.hassan@example.com",
    "driver_phone": "+211 555 123 456",
    "period_start": "2026-05-14T00:00:00.000000",
    "period_end": "2026-05-14T23:59:59.000000",
    "cash_collected": 5450.75,
    "cash_handed_over": 5000.00,
    "cash_balance": 450.75,
    "currency": "USD",
    "related_orders": [
      "770e8400-e29b-41d4-a716-446655440002",
      "770e8400-e29b-41d4-a716-446655440007",
      "770e8400-e29b-41d4-a716-446655440008",
      "770e8400-e29b-41d4-a716-446655440009"
    ],
    "delivery_count": 18,
    "cod_order_count": 12,
    "successful_deliveries": 17,
    "failed_deliveries": 1,
    "odoo_export_status": "not_exported",
    "created_at": "2026-05-15T00:00:00.000000"
  },
  {
    "cash_summary_id": "cash-uuid-2",
    "driver_id": "driver-uuid-2",
    "driver_name": "Mohammed Ali",
    "driver_email": "mohammed.ali@example.com",
    "driver_phone": "+211 555 789 012",
    "period_start": "2026-05-14T00:00:00.000000",
    "period_end": "2026-05-14T23:59:59.000000",
    "cash_collected": 3280.50,
    "cash_handed_over": 3280.50,
    "cash_balance": 0.00,
    "currency": "USD",
    "related_orders": [
      "770e8400-e29b-41d4-a716-446655440010",
      "770e8400-e29b-41d4-a716-446655440011",
      "770e8400-e29b-41d4-a716-446655440012"
    ],
    "delivery_count": 15,
    "cod_order_count": 8,
    "successful_deliveries": 14,
    "failed_deliveries": 1,
    "odoo_export_status": "not_exported",
    "created_at": "2026-05-15T00:00:00.000000"
  }
]
```

**Cash Balance Calculation:**
```
cash_balance = cash_collected - cash_handed_over
```

---

## Error Response Examples

### Authentication Error (401)
```json
{
  "detail": "Missing Odoo token"
}
```

### Authorization Error (403)
```json
{
  "detail": "Invalid Odoo token"
}
```

### Validation Error (400)
```json
{
  "detail": "Either shop_id or restaurant_id required"
}
```

### Not Found Error (404)
```json
{
  "detail": "Shop not found"
}
```

### Server Error (500)
```json
{
  "detail": "Product upsert failed: Database connection timeout"
}
```

---

## Webhook Response Examples

### Success Response
```json
{
  "status": "success",
  "product_id": "prod-uuid-123",
  "action": "created",
  "log_id": "log-uuid-456"
}
```

### Ignored Response (Not an Error)
```json
{
  "status": "ignored",
  "message": "Shop not connected to Odoo"
}
```

### Placeholder Response
```json
{
  "status": "placeholder",
  "message": "Order status update endpoint - to be implemented"
}
```

---

## Common Patterns

### Shop vs Restaurant Detection
```python
# Always provide exactly ONE of these:
{"shop_id": "uuid"}           # For marketplace shops
{"restaurant_id": "uuid"}     # For restaurants

# Never both, never neither
```

### Optional vs Required Fields
```python
# Always required:
- shop_id OR restaurant_id
- odoo_product_id (for existing products)
- name (for new products)
- price (for new products)

# Always optional:
- description
- image_url
- stock_quantity (defaults to 0)
- all wholesale fields (MOQ, bulk_price, pricing_tiers)
- all sync flags (default to true)
```

### Wholesale Product Flexibility
```python
# All valid:
{"wholesale_enabled": false}                          # Regular product
{"wholesale_enabled": true, "minimum_order_qty": 10}  # With MOQ only
{"wholesale_enabled": true, "bulk_price": 25.00}      # With bulk price only
{"wholesale_enabled": true, "pricing_tiers": [...]}   # With tiers only
{"wholesale_enabled": true}                           # Wholesale flag only (all fields null)

# Product sync MUST NOT fail if wholesale_enabled is true but all fields are null
```

---

**End of Sample Payloads**

Use these examples as reference when building your Odoo 18 module.
