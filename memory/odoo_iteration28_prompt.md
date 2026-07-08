# Prompt to give Claude — Update Odoo `jubasquare_orders` module for Iteration 28

Copy everything below and paste into Claude. It extends the existing Odoo
add-on with the **new schema fields** JubaSquare added in Iteration 28: LTG
partner badge, menu/product sections (with promo-only sections and a limit of
10 sections), Limited-Time Promos (percent / amount / BOGO — Buy N Get 1 Free),
required side items, and the new Kitchen-Control endpoints.

Pair this with the previously-shared `odoo_kitchen_control_prompt.md` — that
prompt handles the state-machine calls. This prompt handles the **data model
sync** so orders exported to Odoo carry every JubaSquare field correctly.

---

## Goal

Extend the existing Odoo `jubasquare_orders` add-on so that products, menu
items, shops and restaurants pushed from Odoo to JubaSquare (and back) carry
the new Iteration 28 fields without losing information.

You already have:

- `POST /api/odoo/products/upsert` — push shop products from Odoo.
- `POST /api/odoo/menu-items/upsert` — push restaurant menu items from Odoo.
- `POST /api/odoo/shops/upsert` — push shop entities.
- `POST /api/odoo/restaurants/upsert` — push restaurant entities.
- Service-token auth via header `X-Jubasquare-Odoo-Token` (verified by
  `verify_odoo_webhook`).

You are adding support for these **new fields**.

---

## 1. LTG (Local Top Growth) partner badge

Fields (both `shops` and `restaurants`):

```python
is_ltg_partner: bool = False   # admin-controlled boost
```

- Odoo can read this flag but only JubaSquare **admins** can toggle it.
- When true, the entity is boosted to the top of the customer-facing shop /
  restaurant recommendation lists and a golden "★ Part of LTG" badge is
  rendered on the card.
- **Do NOT overwrite this field from Odoo unless the payload explicitly
  contains a truthy value.** Preferred behaviour: omit it from `upsert`
  payloads unless the Odoo user has explicit permission.

Odoo model additions (`jubasquare.shop` and `jubasquare.restaurant`):

```python
is_ltg_partner = fields.Boolean(
    string="Part of LTG",
    default=False,
    help="Local Top Growth partner. Admin-managed on JubaSquare."
)
```

---

## 2. Menu / Product sections (max 10)

Both restaurants and shops now support **sections** (a.k.a. custom
sub-categories that appear on the storefront). A section is:

```json
{
  "id": "sec_<uuid>",
  "name": "Weekend Specials",
  "sort_order": 1,
  "is_promo_section": false
}
```

- Restaurants use the field `menu_sections` (list of section dicts).
- Shops use the field `product_sections` (list of section dicts).
- **Hard limit:** 10 sections per seller.
- When `is_promo_section` is true, the storefront auto-populates that section
  with every item whose active promo has `promo.active == true` — the seller
  does **not** need to manually assign items into it.

### Item ↔ section assignment

Each `menu_item` / `product` gets a new nullable field:

```python
menu_section_id: Optional[str] = None    # restaurants
product_section_id: Optional[str] = None # shops
```

Odoo should:

- Add a `Section` many2one to `jubasquare.section` on both product & menu-item
  models.
- Serialize as `menu_section_id` / `product_section_id` when pushing to
  JubaSquare.
- Reject writes where the referenced section does not exist on the parent
  shop / restaurant (400).

---

## 3. Limited-Time Promos (percent / amount / BOGO)

New object embedded on both `menu_items` and `products`:

```python
class Promo(BaseModel):
    active: bool = False
    type: Literal["percent", "amount", "bogo"] = "percent"
    value: float = 0.0             # % for 'percent', USD for 'amount'
    bogo_min_qty: int = 2          # only used when type == 'bogo'
    start_at: Optional[str] = None # ISO datetime, optional
    end_at: Optional[str] = None   # ISO datetime, optional
```

Semantics:

| type       | Rule                                                                                     |
|------------|------------------------------------------------------------------------------------------|
| `percent`  | Effective price = `price_usd * (1 - value/100)`                                          |
| `amount`   | Effective price = `max(0, price_usd - value)`                                            |
| `bogo`     | For every `bogo_min_qty` units paid, grant 1 additional unit free. Never exceeds cart qty. |

Backend already computes `bogo_free_quantity(item, qty)` server-side; Odoo
does not need to compute the free unit locally, but its **invoice** must
mirror it — see §5.

### Odoo model additions

```python
promo_active     = fields.Boolean(string="Promo Active")
promo_type       = fields.Selection([
    ('percent', 'Percent %'),
    ('amount',  'Amount off (USD)'),
    ('bogo',    'Buy N Get 1 Free'),
], default='percent', string="Promo Type")
promo_value       = fields.Float(string="Promo Value")
promo_bogo_min_qty = fields.Integer(string="BOGO Min Qty", default=2)
promo_start_at    = fields.Datetime(string="Promo Starts")
promo_end_at      = fields.Datetime(string="Promo Ends")
```

Serialize into the nested `promo` object when upserting:

```python
{
  "promo": {
    "active": rec.promo_active,
    "type": rec.promo_type,
    "value": rec.promo_value,
    "bogo_min_qty": rec.promo_bogo_min_qty,
    "start_at": rec.promo_start_at and rec.promo_start_at.isoformat(),
    "end_at":   rec.promo_end_at   and rec.promo_end_at.isoformat(),
  }
}
```

---

## 4. Required side items

Menu items (and shop products) can now declare **required** side item groups:

```python
sides_required: bool = False   # when true, customer MUST pick from each group
side_groups: List[dict] = []   # each group: {id, name, min_pick, max_pick, options: [...]}
```

Odoo action:

- Add a boolean `sides_required` on `jubasquare.menu.item`.
- When set to true, the JubaSquare checkout will block customers from adding
  the item without picking sides. No further Odoo change is required; simply
  ensure the field is serialized as `sides_required` on upsert.

---

## 5. Order line changes — invoice mirroring

When JubaSquare pushes an order to Odoo via
`POST /api/odoo/orders/status-update` (already implemented), the payload now
includes:

```json
"items": [
  {
    "menu_item_id": "...",
    "name": "...",
    "quantity": 3,
    "free_quantity": 1,             // NEW — BOGO free units
    "unit_price_usd": 4.5,
    "promo_applied": {              // NEW — for audit / receipt
      "type": "bogo",
      "value": 0,
      "bogo_min_qty": 2
    },
    "line_total_usd": 13.5          // already discounted (excludes free unit)
  }
]
```

Required Odoo behaviour:

- Add an integer `free_quantity` on the sale-order-line.
- When rendering the receipt / invoice PDF, print BOGO lines as:

  ```
  3 × Chicken Wrap  @ $4.50   $13.50
     + 1 FREE (BOGO)
  ```

- The `unit_price_usd` on the invoice line is the customer-paid price after
  `percent` / `amount` reduction. Do **not** re-apply the discount inside Odoo.

---

## 6. Migration checklist

1. `models/jubasquare_shop.py` — add `is_ltg_partner`, `product_sections`.
2. `models/jubasquare_restaurant.py` — add `is_ltg_partner`, `menu_sections`.
3. `models/jubasquare_section.py` — new model, one2many from shop/restaurant.
4. `models/jubasquare_product.py` — add `product_section_id`, promo fields.
5. `models/jubasquare_menu_item.py` — add `menu_section_id`, `sides_required`,
   promo fields.
6. `models/sale_order_line.py` — add `free_quantity`, `promo_applied` JSON.
7. `report/jubasquare_invoice_template.xml` — render BOGO line variants.
8. `data/ir.model.access.csv` — grant read on `jubasquare.section` to seller
   users.

Bump the module `__manifest__.py` version to `18.0.28.0`.

---

## 7. Sample cURL calls (for smoke tests)

```bash
BASE="https://jubasquare.com"
TOKEN="<your service token>"

# Upsert a menu item with a BOGO promo assigned to a section
curl -X POST "$BASE/api/odoo/menu-items/upsert" \
  -H "Content-Type: application/json" \
  -H "X-Jubasquare-Odoo-Token: $TOKEN" \
  -d '{
    "restaurant_id": "r_...",
    "id": "m_...",
    "name": "Chicken Wrap",
    "price_usd": 4.5,
    "menu_section_id": "sec_...",
    "sides_required": true,
    "promo": {
      "active": true, "type": "bogo", "bogo_min_qty": 2
    }
  }'
```

```bash
# Push a section
curl -X POST "$BASE/api/odoo/restaurants/upsert" \
  -H "Content-Type: application/json" \
  -H "X-Jubasquare-Odoo-Token: $TOKEN" \
  -d '{
    "id": "r_...",
    "menu_sections": [
      {"id": "sec_1", "name": "Weekend Specials", "sort_order": 1, "is_promo_section": false},
      {"id": "sec_2", "name": "On Promo Now",     "sort_order": 2, "is_promo_section": true}
    ]
  }'
```

---

## 8. Backwards compatibility

- All new fields default to safe values (`false`, `null`, `[]`, `0`). Old Odoo
  installations that omit them continue to work; JubaSquare treats missing =
  absent.
- Field names in payloads MUST be exactly as documented above (snake_case).
- Never send `is_ltg_partner` unless the Odoo user is a system admin — see §1.

That's it. Ship it. 🚀
