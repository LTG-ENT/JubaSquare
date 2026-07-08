# Odoo module — Iter 31 update prompt for Claude

Copy the block below and paste it into a fresh Claude conversation with your
Odoo `jubasquare_orders` addon repo attached. Claude will produce the model
patches, XML forms, and controller changes needed to fully sync every new
JubaSquare field.

Pair this with the earlier prompts still in `/app/memory/`:
- `odoo_kitchen_control_prompt.md` — kitchen state-machine + push endpoints
- `odoo_iteration28_prompt.md` — data-model diff for LTG, sections, BOGO, sides
- **This file** — final consolidated diff for Iter 31 (adds `is_ltg_partner` on
  products, prep_time_minutes, and confirmed field shape for everything).

---

## Goal

Upgrade the `jubasquare_orders` Odoo addon so pushing a product / menu item /
shop / restaurant to JubaSquare carries **every field** JubaSquare stores as
of Iter 31, and receiving order updates handles BOGO free-quantity lines.

## Endpoints already live on JubaSquare (no code changes needed on my side)

- `POST /api/odoo/products/upsert` — the workhorse. Handles BOTH shop products
  and restaurant menu items. Distinguishes by presence of `shop_id` vs
  `restaurant_id` in the payload.
- `POST /api/odoo/shops/upsert` — shop metadata including `product_sections`.
- `POST /api/odoo/restaurants/upsert` — restaurant metadata including
  `menu_sections`.
- `POST /api/odoo/kitchen/<action>` — accept / reject / start / ready.
- Auth header: `X-Jubasquare-Odoo-Token: <service token>` (rotate via
  `POST /api/admin/odoo/service-token/rotate` — raw returned once, then hashed).

## Full payload spec — `POST /api/odoo/products/upsert`

```json
{
  "shop_id": "sh_...",              // exactly one of shop_id / restaurant_id
  "restaurant_id": "r_...",         //
  "odoo_product_id": "12345",       // Odoo product.template id
  "odoo_product_sku": "SKU-42",
  "name": "Chicken Wrap",
  "description": "…",
  "price": 4.5,                     // USD unit price
  "image_url": "https://…",         // publicly reachable image
  "stock_quantity": 42,
  "publish": true,

  "category_id": "cat_...",         // REQUIRED — JubaSquare category UUID
  "category":       "Meals",        // deprecated, ignored if category_id set
  "food_category":  "Fast Food",    // deprecated

  "mode": "marketplace",            // "marketplace" | "wholesale" (shop only)

  "wholesale_enabled": false,
  "minimum_order_qty": 5,
  "bulk_price": 3.9,
  "pricing_tiers": [
    {"min_qty": 10, "price": 3.5},
    {"min_qty": 50, "price": 3.2}
  ],

  "sync_price": true,
  "sync_stock": true,
  "sync_image": true,
  "sync_description": true,

  /* ---------- Iter 31 additions (all optional) ---------- */

  "promo": {
    "active": true,
    "type": "bogo",                 // "percent" | "amount" | "bogo"
    "value": 0,                     // % for percent, USD for amount, ignored for bogo
    "bogo_min_qty": 3,              // customer must have ≥3 paid to get 1 free
    "starts_at": "2026-02-10T00:00:00Z",   // ISO 8601 or null
    "ends_at":   "2026-02-17T23:59:59Z"
  },

  "product_section_id": "sec_...",  // shop products only
  "menu_section_id":    "sec_...",  // restaurant menu items only
  "sides_required":     true,       // restaurant only — customer MUST pick sides
  "side_items": [                   // restaurant only
    {"id": "si_1", "name": "Fries",     "price_usd": 1.0, "is_default": true},
    {"id": "si_2", "name": "Coleslaw",  "price_usd": 0.5, "is_default": false}
  ],
  "prep_time_minutes": 12,          // restaurant only — used by ETA + kitchen

  "is_ltg_partner": true            // admin-only boost; DO NOT send unless the
                                    // Odoo user has explicit admin permission
}
```

All Iter 31 fields default to "don't touch" when omitted. That is: an existing
BOGO promo in JubaSquare is **preserved** if the next Odoo upsert omits `promo`.
Only explicit `null` values overwrite. Test coverage: iter31 backend suite,
18/18 pass.

## Odoo model additions

### `jubasquare.product.template` (extending `product.template`)

```python
class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Iter 31 — Promo
    js_promo_active       = fields.Boolean(string="Promo active")
    js_promo_type         = fields.Selection([
        ("percent", "Percent %"),
        ("amount",  "Flat $ off"),
        ("bogo",    "Buy N Get 1 Free"),
    ], string="Promo type", default="percent")
    js_promo_value        = fields.Float(string="Promo value")
    js_promo_bogo_min_qty = fields.Integer(string="BOGO min qty", default=2)
    js_promo_starts_at    = fields.Datetime(string="Promo starts")
    js_promo_ends_at      = fields.Datetime(string="Promo ends")

    # Iter 31 — Sections
    js_product_section_id = fields.Char(string="Product section (shop)")
    js_menu_section_id    = fields.Char(string="Menu section (restaurant)")

    # Iter 31 — Restaurant menu specifics
    js_sides_required     = fields.Boolean(string="Sides required")
    js_side_items_json    = fields.Text(string="Side items (JSON)")
    js_prep_time_minutes  = fields.Integer(string="Prep time (min)")

    # Iter 31 — Admin boost
    js_is_ltg_partner     = fields.Boolean(
        string="Part of LTG",
        groups="base.group_system",
    )
```

### `res.partner` (shop / restaurant partner records)

```python
    # Shop-level "Part of LTG" flag (admin only)
    js_is_ltg_partner_shop = fields.Boolean(
        string="Shop Part of LTG",
        groups="base.group_system",
    )
    # Section catalog on the partner (One2many)
    js_sections_ids = fields.One2many(
        "jubasquare.section", "partner_id", string="Sections"
    )
```

### New model — `jubasquare.section`

```python
class JubasquareSection(models.Model):
    _name  = "jubasquare.section"
    _order = "sort_order, id"

    partner_id       = fields.Many2one("res.partner", ondelete="cascade", required=True)
    js_id            = fields.Char(required=True, index=True)
    name             = fields.Char(required=True)
    sort_order       = fields.Integer(default=0)
    is_promo_section = fields.Boolean(default=False)
```

## Order line — mirror BOGO on invoice

When JubaSquare pushes an order update, each line now includes a
`free_quantity` field and a `promo_applied` snapshot.

Add on `sale.order.line`:

```python
    js_free_quantity   = fields.Integer(string="Free qty (BOGO)", default=0)
    js_promo_applied   = fields.Text(string="Promo applied (JSON snapshot)")
```

Render on invoice PDF (report template `sale.report_saleorder_document`):

```xml
<t t-if="line.js_free_quantity > 0">
  <br/>
  <span class="text-muted">
    + <t t-esc="line.js_free_quantity"/> FREE (BOGO)
  </span>
</t>
```

## Serialization helper (share via mixin)

```python
def _to_jubasquare_product_payload(self):
    self.ensure_one()
    payload = {
        "odoo_product_id":   str(self.id),
        "odoo_product_sku":  self.default_code or None,
        "name":              self.name,
        "description":       self.description_sale or "",
        "price":             float(self.list_price),
        "image_url":         self.js_image_url or None,
        "stock_quantity":    int(self.qty_available or 0),
        "publish":           bool(self.website_published),
        "category_id":       self.js_category_id,   # your existing field
        "mode":              self.js_mode or "marketplace",
        "wholesale_enabled": bool(self.js_wholesale_enabled),
        "minimum_order_qty": int(self.js_min_order_qty or 0) or None,
        "bulk_price":        float(self.js_bulk_price) if self.js_bulk_price else None,
    }
    # Iter 31 — optional fields
    if self.js_promo_active:
        payload["promo"] = {
            "active": True,
            "type":   self.js_promo_type,
            "value":  float(self.js_promo_value or 0),
            "bogo_min_qty": int(self.js_promo_bogo_min_qty or 2),
            "starts_at": self.js_promo_starts_at and self.js_promo_starts_at.isoformat(),
            "ends_at":   self.js_promo_ends_at   and self.js_promo_ends_at.isoformat(),
        }
    if self.js_product_section_id:
        payload["product_section_id"] = self.js_product_section_id
    if self.js_menu_section_id:
        payload["menu_section_id"] = self.js_menu_section_id
    if self.js_sides_required:
        payload["sides_required"] = True
    if self.js_side_items_json:
        payload["side_items"] = json.loads(self.js_side_items_json)
    if self.js_prep_time_minutes:
        payload["prep_time_minutes"] = int(self.js_prep_time_minutes)
    # Admin-only field — only serialize if the user has system rights
    if self.env.user.has_group("base.group_system") and self.js_is_ltg_partner:
        payload["is_ltg_partner"] = True
    return payload
```

## Backwards compatibility contract

- Every Iter 31 field is optional in the JubaSquare API.
- Omitting a field = "don't touch it".
- Sending `null` explicitly = "clear it".
- Older Odoo modules that never learned about Iter 31 keep working unchanged.

## Manifest

Bump `__manifest__.py`:

```python
{
    "name": "JubaSquare Sync",
    "version": "18.0.31.0",
    "depends": ["sale_management", "stock", "web"],
    ...
}
```

## Testing

Use these cURL calls as smoke tests (replace `$BASE` and `$TOKEN`):

```bash
# 1. Simple BOGO push
curl -X POST "$BASE/api/odoo/products/upsert" \
  -H "Content-Type: application/json" \
  -H "X-Jubasquare-Odoo-Token: $TOKEN" \
  -d '{
    "shop_id": "sh_demo",
    "odoo_product_id": "10001",
    "name": "3-for-2 Widget",
    "price": 5.00,
    "category_id": "cat_retail_general",
    "publish": true,
    "promo": {"active": true, "type": "bogo", "bogo_min_qty": 3}
  }'

# 2. Restaurant menu item with sections + required sides
curl -X POST "$BASE/api/odoo/products/upsert" \
  -H "Content-Type: application/json" \
  -H "X-Jubasquare-Odoo-Token: $TOKEN" \
  -d '{
    "restaurant_id": "r_demo",
    "odoo_product_id": "20001",
    "name": "Chicken Wrap",
    "price": 4.50,
    "category_id": "cat_food_fastfood",
    "publish": true,
    "menu_section_id": "sec_lunch",
    "sides_required": true,
    "side_items": [
      {"id": "si_fries",   "name": "Fries",    "price_usd": 1.0, "is_default": true},
      {"id": "si_coke",    "name": "Coke",     "price_usd": 1.5, "is_default": false}
    ],
    "prep_time_minutes": 12
  }'

# 3. Backwards-compat: NO Iter 31 fields → existing promo/section preserved
curl -X POST "$BASE/api/odoo/products/upsert" \
  -H "Content-Type: application/json" \
  -H "X-Jubasquare-Odoo-Token: $TOKEN" \
  -d '{
    "shop_id": "sh_demo",
    "odoo_product_id": "10001",
    "name": "3-for-2 Widget (renamed)",
    "price": 5.50,
    "category_id": "cat_retail_general",
    "publish": true
  }'
```

That's it. Ship it. 🚀
