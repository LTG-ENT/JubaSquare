# Odoo → JubaSquare "Customer Order Sync" — Prompt for Claude

Paste the block below into Claude (or any other AI assistant) as-is. It's
self-contained and Claude will produce a full Odoo custom module ready to
install in your existing Odoo instance.

---

## Prompt to paste into Claude

You are an Odoo 16/17 developer. Build a custom module named
`jubasquare_orders` that pushes each newly-created / paid Sale Order from
Odoo to the JubaSquare marketplace as a "customer order" via HTTP so
JubaSquare's Kitchen Dashboard / seller flow lights up automatically.

## 1. Module goal

Whenever a Sale Order (`sale.order`) is confirmed (or when its state moves
to `sale` or `done`), post the order to:

```
POST https://jubasquare.com/api/odoo/orders/inbound
Content-Type: application/json
Authorization: Bearer <ODOO_JS_API_KEY>
```

The JubaSquare backend expects this payload (design it to match — the
target endpoint will need to be built on the JubaSquare side too):

```json
{
  "odoo_order_id": "SO0123",
  "odoo_partner_id": 42,
  "customer_name": "Peter Deng",
  "customer_phone": "+211-925-000-000",
  "customer_email": "peter@example.com",
  "delivery_area": "Munuki",
  "delivery_address": "Main St, Block 3, House 12",
  "notes": "Please call before delivery",
  "payment_method": "cash_on_delivery",
  "delivery_type": "delivery",
  "currency": "USD",
  "exchange_rate_ssp": 6500,
  "subtotal_usd": 26.00,
  "delivery_fee_usd": 2.50,
  "total_usd": 28.50,
  "items": [
    {
      "sku": "BURGER-01",
      "name": "Cheese Burger",
      "quantity": 2,
      "price_usd": 10.00,
      "sides": [
        { "name": "Fries", "price_usd": 3.00 }
      ]
    }
  ],
  "meta": {
    "source": "odoo",
    "odoo_db": "your_odoo_db_name",
    "created_at": "2026-02-01T10:30:00Z"
  }
}
```

## 2. Module structure

```
jubasquare_orders/
  __manifest__.py
  __init__.py
  models/
    __init__.py
    res_config_settings.py        # Add API URL + API key + shop/restaurant mapping
    sale_order.py                 # Override confirm/action_confirm to push
    jubasquare_sync_log.py        # Log every push (status, response, retry)
  data/
    ir_config_parameter.xml       # Default config values
    ir_cron.xml                   # Retry-failed-pushes cron every 15 min
  security/
    ir.model.access.csv
  views/
    res_config_settings_view.xml  # Settings screen
    jubasquare_sync_log_view.xml  # Log tree/form
    sale_order_view.xml           # Add "Push to JubaSquare" button + status field
```

## 3. Settings (Odoo → Settings → General → JubaSquare)

Fields on `res.config.settings`:

| Field                          | Type     | Purpose                                          |
|--------------------------------|----------|--------------------------------------------------|
| `js_api_url`                   | Char     | e.g. `https://jubasquare.com/api`                |
| `js_api_key`                   | Char     | Bearer token issued by JubaSquare admin          |
| `js_default_restaurant_id`     | Char     | JubaSquare restaurant UUID to route orders to    |
| `js_default_shop_id`           | Char     | (optional) JubaSquare marketplace shop UUID      |
| `js_auto_push_on_confirm`      | Boolean  | When True: push immediately on `action_confirm`  |
| `js_push_only_paid`            | Boolean  | Skip pushing until `invoice_status == 'invoiced'`|
| `js_exchange_rate_ssp`         | Float    | Latest USD→SSP rate to include in payload        |

Store as `ir.config_parameter` with prefix `jubasquare.` so upgrades stay clean.

## 4. Sale Order override

In `models/sale_order.py`:

- Add fields:
  - `js_pushed = Boolean(default=False, copy=False)`
  - `js_push_state = Selection([('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'), ('skipped', 'Skipped')], default='pending', copy=False)`
  - `js_last_response = Text(readonly=True, copy=False)`
  - `js_external_id = Char(readonly=True, copy=False)` — id returned by JubaSquare
- Override `action_confirm`:
  1. Call `super().action_confirm()`
  2. If `js_auto_push_on_confirm` and (not `js_push_only_paid` OR invoice paid) → call `self._push_to_jubasquare()`
- Method `_push_to_jubasquare(self)`:
  1. Build payload from `self` — map order lines, taxes, delivery line, sides (product template attribute lines), currency conversion using `js_exchange_rate_ssp`.
  2. `requests.post(url, json=payload, headers={Authorization: Bearer …}, timeout=15)`.
  3. On 2xx → `js_pushed=True`, `js_push_state='sent'`, `js_external_id=response.get('id')`, `js_last_response=<truncated body>`.
  4. On non-2xx or exception → `js_push_state='failed'`, `js_last_response=<err>`, create `jubasquare.sync.log` record for retry.
  5. Always create a `jubasquare.sync.log` row.
- Add a manual button "Push to JubaSquare" on the Sale Order form (visible when `js_push_state in ('pending','failed')`).

## 5. Sides / product configurator

Odoo doesn't natively support "side options" the way JubaSquare does. Two
options — pick whichever fits your data model:
- (A) Use product variants and treat a "Cheese Burger + Fries" as one variant.
- (B) Use `product.template.attribute.line` with attribute type `radio` and
  pass the selected attribute values as `sides` on the payload.

Recommend (B) so pricing stays flexible. Loop `order.order_line` and for
each line with `product_no_variant_attribute_value_ids`, populate the
`sides` list.

## 6. Log model

`jubasquare_sync_log` with fields: order_id (Many2one), payload (Text),
status (Selection), response (Text), retry_count (Int), created_at
(Datetime). Kept for debugging and retries.

Add a cron `js_retry_failed_pushes` (every 15 min) that scans logs where
`status='failed'` AND `retry_count < 5` and re-invokes `_push_to_jubasquare`
on the order.

## 7. Security

Give `sales_team.group_sale_manager` full access to the log model.
Give `sales_team.group_sale_salesman` read-only.
`ir.model.access.csv` should list both.

## 8. Manifest

```python
{
    'name': 'JubaSquare Orders Sync',
    'version': '1.0.0',
    'summary': 'Push confirmed Sale Orders to JubaSquare in real time',
    'depends': ['sale_management', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/res_config_settings_view.xml',
        'views/jubasquare_sync_log_view.xml',
        'views/sale_order_view.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
```

## 9. Deliverables

Return each file in a fenced code block with the file path as the header,
e.g.:

```python
# jubasquare_orders/models/sale_order.py
...
```

Include:
- Copy-pasteable module ready to zip and install.
- A short README with install steps, how to obtain the API key from
  JubaSquare admin, and how to test end-to-end (create SO → confirm →
  verify order appears in the JubaSquare seller kitchen dashboard).
- A troubleshooting section for common failure modes: SSL, bad token,
  rate limit, exchange rate missing.

Do NOT invent JubaSquare endpoints beyond `POST /api/odoo/orders/inbound`.
Assume it accepts the exact payload above.

---

## Also please tell me:

At the very end of your reply, list every JubaSquare-side change I still
need to make to complete the integration (e.g. new endpoint
`POST /api/odoo/orders/inbound` with what fields to accept, a settings
screen for the shared API key, mapping between `odoo_order_id` and my
internal restaurant_order id, retry idempotency via
`odoo_order_id` as a unique index, etc.). Keep it terse — 5-8 bullets.
