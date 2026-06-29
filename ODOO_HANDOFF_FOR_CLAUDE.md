# JubaSquare ↔ Odoo 18 — Final Handoff Brief

**Purpose:** This brief is for the next AI (Claude) that will build the external Odoo 18 module. JubaSquare is now ready to receive and send data. **Do not modify the JubaSquare codebase further** — only consume the endpoints described below.

---

## 1. Base URLs & Authentication

| Layer | Base URL | Auth Header |
|---|---|---|
| Webhook (Odoo → JubaSquare) | `https://<jubasquare-host>/api/odoo` | `X-JubaSquare-Odoo-Token: PUT_SECURE_TOKEN_HERE` |
| Admin/Service (JubaSquare → Odoo polling) | `https://<jubasquare-host>/api/admin/odoo` | `X-JubaSquare-Odoo-Token: PUT_SECURE_TOKEN_HERE` (or admin JWT) |

`PUT_SECURE_TOKEN_HERE` = value of `ODOO_WEBHOOK_TOKEN` in JubaSquare `.env`. Never commit or print this value.

---

## 2. Endpoints Implemented & Ready

### Webhook (Odoo → JubaSquare)
- `GET  /api/odoo/health` *(public)* — health check
- `POST /api/odoo/products/upsert` — create/update shop product or restaurant menu item
- `POST /api/odoo/products/stock-update` — update stock only
- `POST /api/odoo/products/unpublish` — hide/unpublish

### Admin / Service (JubaSquare → Odoo)
- `GET /api/admin/odoo/shops` — list shops with `odoo_connection`
- `GET /api/admin/odoo/restaurants` — list restaurants with `odoo_connection`
- `GET /api/admin/odoo/sync-logs?limit=&status=&operation_type=` — recent sync log entries

### Placeholders (return `{"status":"placeholder",…}` — Claude must implement client-side logic to query/handle these as data becomes available)
- `POST /api/odoo/orders/status-update`
- `POST /api/odoo/delivery/status-update`
- `POST /api/odoo/invoice/status-update`
- `POST /api/admin/odoo/test-connection`
- `POST /api/admin/odoo/retry-failed`
- `GET  /api/admin/odoo/products/pending`
- `GET  /api/admin/odoo/orders/pending`
- `GET  /api/admin/odoo/delivery-updates/pending`
- `GET  /api/admin/odoo/payout-summaries/pending`
- `GET  /api/admin/odoo/driver-cash/pending`

---

## 3. Required Fields on Product Upsert

| Field | Type | Notes |
|---|---|---|
| `shop_id` OR `restaurant_id` | UUID | Exactly one. JubaSquare auto-derives `seller_id` from this. |
| `category_id` | UUID | **Required.** Must be a valid category UUID from `GET /api/categories/tree`. |
| `odoo_product_id` | string | Idempotency key for upserts. |
| `name`, `price` | string, number | Required. `price` is USD. |
| `stock_quantity` | int | Optional. Maps to JubaSquare's primary `stock` field. Defaults to **100** if omitted. |
| Wholesale fields | various | Optional: `wholesale_enabled`, `minimum_order_qty`, `bulk_price`, `pricing_tiers[]`. Sync MUST NOT fail if these are null. |
| Sync flags | bool | `sync_price`, `sync_stock`, `sync_image`, `sync_description` (default true). |

---

## 4. Data Mapping Confirmed

| External (Odoo payload) | Internal (JubaSquare DB) |
|---|---|
| `stock_quantity` | → `product.stock` (primary) + `product.stock_quantity` (metadata) |
| `category_id` | → `product.category_id` (required) |
| derived from shop/restaurant | → `product.seller_id` |
| `wholesale_enabled` | → `product.is_wholesale` + `product.mode` ("wholesale"\|"marketplace") |
| `publish` | → `product.odoo_publish`, `product.odoo_hidden=!publish` |

---

## 5. Response Codes

- `200` → success or `placeholder`
- `400` → missing required IDs (`shop_id`/`restaurant_id`)
- `401` → missing token
- `403` → invalid token
- `422` → Pydantic field validation (e.g. missing `category_id`)
- `500` → server/db error

`ignored` responses (HTTP 200) are returned when the target shop/restaurant has `odoo_connection.enabled=false` — Odoo module should treat these as "no-op", not errors.

---

## 6. Sample Payload Reference

See `/app/ODOO_SAMPLE_PAYLOADS.md` for complete request/response examples, including:
- Regular & wholesale product upserts (with `category_id`)
- Restaurant menu items
- Stock updates & unpublish
- Placeholder response examples for orders/delivery/payouts/cash

See `/app/ODOO_API_DOCUMENTATION.md` for full per-endpoint specs.

---

## 7. What's Out of Scope for Claude

- Do **not** modify JubaSquare's backend, database, or React app.
- Do **not** change endpoint paths or auth headers.
- All placeholder endpoints can be enhanced later by the JubaSquare team — Claude's Odoo module should call them defensively (handle `placeholder` status as "data not ready yet, retry later").

---

## 8. Smoke-Test Verification (run from JubaSquare host)

```bash
TOKEN="$(grep ODOO_WEBHOOK_TOKEN /app/backend/.env | cut -d= -f2)"
API="$REACT_APP_BACKEND_URL"

# Public health
curl -s "$API/api/odoo/health"

# Auth checks
curl -i "$API/api/admin/odoo/shops"                                            # 401
curl -i -H "X-JubaSquare-Odoo-Token: bad" "$API/api/admin/odoo/shops"          # 403
curl -i -H "X-JubaSquare-Odoo-Token: $TOKEN" "$API/api/admin/odoo/shops"       # 200
```

All four cases verified ✅ on 2026-06-29.
