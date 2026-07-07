# Prompt to give Claude — Update Odoo `jubasquare_orders` module for Kitchen Control

Copy everything below and paste into Claude. The prompt is written so Claude can
extend your existing Odoo add-on module without any additional context.

---

## Goal

Extend the existing Odoo `jubasquare_orders` add-on so that restaurant staff
sitting in Odoo (POS / Sales / a custom board) can drive the kitchen state
machine on JubaSquare **without opening the Kitchen Dashboard on the web**.

You already have:

- `POST /api/odoo/orders/status-update` — used to acknowledge a sync.
- `GET /api/admin/odoo/orders/pending` — used to pull new orders from JubaSquare.
- Service-token auth via header `X-Jubasquare-Odoo-Token` (verified by the
  `verify_odoo_webhook` dependency).

We are adding a **new** endpoint you can call to move an order forward:

```
POST {JUBASQUARE_BASE_URL}/api/odoo/kitchen/{action}
Headers:
  Content-Type: application/json
  X-Jubasquare-Odoo-Token: <the service token you already store>
Body (JSON):
  {
    "order_id": "<jubasquare parent order id (marketplace) OR restaurant order id>",
    "sub_order_id": "<optional; pass this to target a marketplace seller_order_split>",
    "reason": "<required only for action='cancel'>"
  }
Response 200:
  { "status": "success", "action": "<action>", "log_id": "<uuid>", "entity_type": "restaurant_order|seller_order_split" }
Errors:
  400 → unknown action, missing order_id, or missing X-Jubasquare-Odoo-Token
  401/403 → invalid service token
  404 → no matching order
  500 → webhook not configured on JubaSquare
```

### Valid actions and what they do on the JubaSquare side

| action        | seller_preparation_status | status      | Extra fields set                                                                 |
|---------------|---------------------------|-------------|----------------------------------------------------------------------------------|
| `accept`      | `accepted`                | `accepted`  | `accepted_at`                                                                    |
| `preparing`   | `preparing`               | `cooking`   | `preparing_started_at`                                                           |
| `ready`       | `ready_for_pickup`        | `ready`     | `ready_at`                                                                       |
| `complete`    | `handed_to_driver`        | `delivered` | `delivery_status='delivered'`, `payment_status='collected_by_seller'`, `delivered_at`, `cash_collected_at` |
| `cancel`      | `cancelled`               | `cancelled` | `cancellation_reason=<reason>`, `cancelled_at`, `cancelled_by='odoo'`            |

Rules:
- `sub_order_id` is optional. When present, we look up in
  `seller_order_splits` (matched with `id=sub_order_id AND order_id=order_id`)
  — this is the correct target for marketplace/shop orders.
- When `sub_order_id` is absent, we update `restaurant_orders` where
  `id=order_id`.
- `reason` is required only for `action='cancel'`. If it's missing we
  default to `"Cancelled via Odoo"`.
- Every call writes an audit row to `odoo_sync_logs` with
  `{kind:'kitchen_action', action, entity_type, matched, reason}`.

## What you need to add to the module

1. **Model additions**  
   On `jubasquare.order` (or wherever you already store the mirrored order):
   ```python
   jubasquare_state = fields.Selection([
       ('pending', 'Pending'),
       ('accepted', 'Accepted'),
       ('preparing', 'Preparing'),
       ('ready', 'Ready for pickup'),
       ('delivered', 'Delivered'),
       ('cancelled', 'Cancelled'),
   ], default='pending', readonly=True)
   jubasquare_last_sync = fields.Datetime(readonly=True)
   ```

2. **A helper method on the model** that POSTs to the new endpoint and
   updates `jubasquare_state` on success. Do NOT swallow HTTP errors — log
   them and raise a `UserError` so the staff know when a click didn't work.

   ```python
   def _call_kitchen_action(self, action, reason=None):
       base = self.env['ir.config_parameter'].sudo().get_param('jubasquare.base_url').rstrip('/')
       token = self.env['ir.config_parameter'].sudo().get_param('jubasquare.service_token')
       payload = {'order_id': self.jubasquare_order_id}
       if self.jubasquare_sub_order_id:
           payload['sub_order_id'] = self.jubasquare_sub_order_id
       if reason:
           payload['reason'] = reason
       resp = requests.post(
           f'{base}/api/odoo/kitchen/{action}',
           json=payload,
           headers={'X-Jubasquare-Odoo-Token': token},
           timeout=15,
       )
       if resp.status_code != 200:
           raise UserError(f'JubaSquare returned {resp.status_code}: {resp.text}')
       body = resp.json()
       self.write({
           'jubasquare_state': {
               'accept':'accepted', 'preparing':'preparing', 'ready':'ready',
               'complete':'delivered', 'cancel':'cancelled',
           }[action],
           'jubasquare_last_sync': fields.Datetime.now(),
       })
       return body
   ```

3. **Five ActionButton methods** on the model, each calling the helper
   above:
   - `action_kitchen_accept` → `self._call_kitchen_action('accept')`
   - `action_kitchen_preparing`
   - `action_kitchen_ready`
   - `action_kitchen_complete`
   - `action_kitchen_cancel(reason)` — pop a wizard asking for a reason
     string, then call the helper with that reason.

4. **XML view additions** — Odoo form/list buttons that call those methods.
   Show only the buttons that are legal for the current `jubasquare_state`
   (e.g. hide "Accept" once state has moved past `pending`). Follow the
   state matrix:

   ```
   pending    → [Accept]  [Cancel]
   accepted   → [Start Preparing]  [Cancel]
   preparing  → [Ready for Pickup]  [Cancel]
   ready      → [Complete Delivery]  [Cancel]
   delivered  → (no actions)
   cancelled  → (no actions)
   ```

5. **Optional but recommended:** in your existing 5-minute polling job that
   already pulls from `/api/admin/odoo/orders/pending`, when an incoming
   order lands, INSERT it into your table with `jubasquare_state='pending'`
   so the buttons above show up immediately.

6. **Config parameters** — reuse whatever you're using today:
   - `jubasquare.base_url` — the JubaSquare API base (e.g.
     `https://jubasquare.com`).
   - `jubasquare.service_token` — the raw token you generated once via
     `POST /api/admin/odoo/service-token/generate` on JubaSquare.

## Testing checklist

- Fire `accept` on a real order → JubaSquare Kitchen Dashboard should
  immediately show the order in the "Accepted" lane.
- Fire `preparing` → moves to "Preparing" lane.
- Fire `ready` → moves to "Ready for pickup".
- Fire `complete` → the order disappears from the active queue (delivered).
- Fire `cancel` with a reason → the customer sees a cancellation with your
  reason.
- Try a wrong `order_id` → you must get a UserError with a 404 in the
  message (not a silent success).

## Documentation

Add a short section (5–8 bullets) at the top of the module README noting:
- Which endpoints the module talks to,
- Where the service token is configured,
- How to rotate the token if it leaks,
- That `jubasquare_state` is read-only in the UI and only mutated by the
  helper method,
- That the buttons no-op offline (return `UserError`) — no queued/retry
  logic is bundled.

That's the whole change. Do not touch the existing `orders/pending` puller
— it stays the same. Do not implement pushing FROM Odoo to JubaSquare for
new orders; JubaSquare is the source of truth for order creation.
