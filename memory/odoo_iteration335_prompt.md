# Odoo module — Iter 33.5 update prompt for Claude

Copy the block below into a Claude conversation with your Odoo
`jubasquare_orders` addon repo attached. It teaches Claude the new
**delivery status webhook**, **shop delivery-in-days** field and the
**strict per-area delivery** rule shipped in Iter 33.5.

Pair with earlier prompts in `/app/memory/`:
- `odoo_kitchen_control_prompt.md`
- `odoo_iteration28_prompt.md`
- `odoo_iteration31_prompt.md`
- `odoo_iteration33_prompt.md`
- **This file** — delivery status + delivery-days + per-area strict mode.

---

## PROMPT (copy from here down)

I have an Odoo addon called `jubasquare_orders` that syncs products, menu
items, shops and restaurants to my JubaSquare marketplace over REST
webhooks. You already know the baseline payload (name, price, stock,
category_id, attributes, kitchen actions, etc.). JubaSquare shipped three
delivery-related upgrades in Iter 33.5 that the addon must support.
Analyze the existing addon first, then extend it — do NOT rebuild or
duplicate existing sync logic.

### Upgrade 1 — Delivery status webhook (NEW)

Endpoint: `POST /api/odoo/delivery/status-update`
Auth: `X-Jubasquare-Odoo-Token` service header (same as other webhooks).

When Odoo marks a delivery done, failed or returned (either through the
warehouse UI or an automated route), POST to this webhook so the seller's
JubaSquare wallet leaves the "Pending Cash Collection" bucket immediately.

Body:
```json
{
  "order_id": "<jubasquare order id>",           // required
  "sub_order_id": "<seller_order_splits.id>",    // optional; when present targets a shop split, else targets a restaurant order
  "delivery_status": "delivered",                // one of: delivered | delivery_failed | returned_to_seller
  "cash_collected": true,                        // optional; default true when delivery_status=delivered
  "reason": "Handed to customer at 5pm"          // optional; stored on failed / returned rows
}
```

Response 200:
```json
{ "status": "success", "delivery_status": "delivered", "cash_collected": true, "entity_type": "restaurant_order", "log_id": "<uuid>" }
```

Errors:
- `400` — bad `delivery_status` value or missing `order_id`.
- `404` — no matching order.

Side effects when `delivery_status=delivered` + `cash_collected=true`:
- Sets `payment_status = collected_by_seller`
- Sets `cash_collected_at = now`
- Sets `payout_status = ready_for_payout`
- The seller's `/api/seller/wallet` bucket "Pending Cash Collection"
  drops that row on the next fetch.

Integration point in the addon:
- Fire this webhook whenever an Odoo stock.picking transitions to `done`
  for a JubaSquare-linked SO, OR whenever a warehouse ops user clicks
  "Mark delivered" in the JubaSquare kanban.
- Store the returned `log_id` on the Odoo record for auditing.
- Retry with exponential backoff (max 5 attempts) on 5xx.

### Upgrade 2 — Shop delivery timeframe in DAYS (payload change)

Shops now expose a `delivery_days_*` block that mirrors the existing
restaurant `eta_*` block, but in DAYS not minutes. Restaurants keep
minute-based ETA (they deliver same-day); shops ship over days.

New shop fields (all optional; when omitted the field is unchanged):
- `delivery_days_mode`: `"off" | "fixed" | "range"` (default `"off"`)
- `delivery_days_fixed`: int (used when mode = `fixed`)
- `delivery_days_min`: int (used when mode = `range`)
- `delivery_days_max`: int (used when mode = `range`)

Update the shop-upsert flow so Odoo warehouse-lead-time templates are
translated into these fields. Example mapping:
- Odoo lead time 1 day → `{"delivery_days_mode":"fixed","delivery_days_fixed":1}`
- Odoo lead time 2–5 days → `{"delivery_days_mode":"range","delivery_days_min":2,"delivery_days_max":5}`

Note: The old shop `eta_mode / eta_fixed_minutes / eta_min_minutes /
eta_max_minutes` fields still exist in the schema for backward
compatibility but are NO LONGER SHOWN in the JubaSquare shop UI —
restaurants alone use them. Do not push minute-based ETAs for shops.

### Upgrade 3 — Strict per-area delivery (no silent fallback)

Behavior change on `/api/orders/quote` and checkout endpoints: when a
shop's `delivery_mode == "per_area"` and the customer's area is not
listed in `delivery_per_area`, the server now returns HTTP 400 with

```
{"detail": "We can't deliver to <area> yet. Please choose another area or contact the seller."}
```

(Previously it silently fell back to the admin's platform rules.)

Impact on Odoo:
- If your addon quotes deliveries locally BEFORE calling JubaSquare,
  mirror this check: fail the quote when the destination area is not in
  the shop's per_area list. Do not assume a default fee.
- When creating an Odoo sales order out of a JubaSquare order, trust
  `delivery_fee_usd` verbatim — do not recompute.

### Acceptance tests

1. Complete an Odoo delivery → JubaSquare seller wallet's "Pending Cash
   Collection" drops the order's amount within one refresh cycle;
   `payout_status` for that split/order = `ready_for_payout`.
2. Push a shop with `delivery_days_mode="range", delivery_days_min=2,
   delivery_days_max=5` → JubaSquare product / cart pages show
   "Arrives in 2–5 days".
3. Attempt a checkout quote for a per_area shop where the customer area
   is missing from `delivery_per_area` → the API responds 400 with the
   deliverability message. The Odoo addon logs the rejection but does
   not create an SO.
