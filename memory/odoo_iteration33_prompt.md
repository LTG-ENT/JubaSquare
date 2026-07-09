# Odoo module — Iter 33 update prompt for Claude

Copy the block below into a Claude conversation with your Odoo
`jubasquare_orders` addon repo attached. It teaches Claude the new
**dynamic attribute system** and **hierarchical categories** added to
JubaSquare in Iter 33 so the addon can sync them.

Pair with earlier prompts in `/app/memory/`:
- `odoo_kitchen_control_prompt.md`
- `odoo_iteration28_prompt.md`
- `odoo_iteration31_prompt.md` (full product payload baseline)
- **This file** — attributes + nested categories delta.

---

## PROMPT (copy from here down)

I have an Odoo addon called `jubasquare_orders` that syncs products, menu
items, shops and restaurants to my JubaSquare marketplace over REST webhooks.
You already know the baseline payload for `POST /api/odoo/products/upsert`
(name, price, stock_quantity, category_id, publish, wholesale fields, promo,
sections, sides, prep_time_minutes, is_ltg_partner). JubaSquare has now
shipped two upgrades that the addon must support. Analyze the existing addon
first, then extend it — do NOT rebuild or duplicate existing sync logic.

### Upgrade 1 — Hierarchical categories (unlimited depth)

JubaSquare categories are now a tree: each category has `parent_id`,
`path` (list of ancestor UUIDs) and `depth`. Business types stay separate:
`retail`, `wholesale`, `restaurant`.

- `GET /api/categories/tree?group=<retail|wholesale|restaurant>` now returns
  a FULLY RECURSIVE tree: every node has `children: [...]` nested to any
  depth (previously only 1 level).
- `category_id` in the product upsert payload is unchanged (still a required
  JubaSquare category UUID) but it may now point to any node in the tree,
  e.g. Electronics → Mobile Phones → Smartphones.
- Server-side validation was tightened:
  - Shop products are REJECTED (HTTP 400) if `category_id` belongs to the
    `restaurant` group.
  - Menu items still REQUIRE a `restaurant` group category.

**What to change in the addon:**
1. Update the category fetch/cache (model `jubasquare.category` or wherever
   the addon stores remote categories) to walk `children` recursively and
   store `parent_id`, `depth`, and a computed `display_path` like
   `"Electronics > Mobile Phones > Smartphones"`.
2. In the product form's JubaSquare category selector, show `display_path`
   so users pick the right nested node. Keep storing only the UUID.
3. Filter selectable categories by business type of the target
   (shop kind retail/wholesale vs restaurant).

### Upgrade 2 — Dynamic product attributes

JubaSquare now has admin-defined attributes (Brand, Storage, RAM, Color,
Material, Spice Level, ...). Each attribute has:

- `key` — stable snake_case identifier (THIS is what the API uses)
- `name` — display label
- `type` — one of: `text`, `number`, `decimal`, `dropdown`, `multi_select`,
  `boolean`, `color`, `date`, `measurement`, `dimensions`, `weight`
- `options` — allowed values for `dropdown` / `multi_select` / `color`
- `unit`, `required`, `filterable`, `searchable`, `inherited`

**New discovery endpoint (public, no auth):**

```
GET /api/categories/{category_id}/attributes
→ {
    "category_id": "...",
    "business_type": "retail",
    "groups": [{"id": "...", "name": "Technical Specifications", "order": 1}],
    "attributes": [
      {"key": "brand", "name": "Brand", "type": "dropdown",
       "options": ["Samsung","Apple","Tecno","Infinix","Huawei","Itel","Nokia","Other"],
       "group_id": "...", "unit": "", "required": false,
       "inherited": false, "global": false, "order": 1},
      ...
    ]
  }
```

Attributes are inherited down the tree — call it with the product's exact
`category_id` and you get the complete effective list.

**Upsert payload change — `POST /api/odoo/products/upsert` now accepts an
optional top-level `attributes` object** (works for BOTH shop products and
restaurant menu items):

```json
{
  "...": "all existing fields unchanged",
  "category_id": "uuid-of-smartphones",
  "attributes": {
    "brand": "Samsung",
    "model": "Galaxy S24",
    "storage": "256GB",
    "ram": "8GB",
    "color": "Black",
    "condition": "New"
  }
}
```

Value formats by type:
| type | JSON value |
|---|---|
| text / date / dimensions / color / dropdown | string |
| number / decimal / weight / measurement | number (float) |
| boolean | true / false |
| multi_select | array of strings, e.g. `["Halal","Vegan"]` |

Server behavior (important for error handling):
- Omit the `attributes` key entirely → existing values on JubaSquare are
  left untouched (backwards compatible; old module versions keep working).
- Send `"attributes": {}` → clears all attribute values.
- Unknown keys are silently dropped.
- `dropdown` / `multi_select` / `color` values MUST match the attribute's
  `options` list (when non-empty) or the whole upsert fails with HTTP 400
  `{"detail": "Invalid value 'X' for attribute 'Y'"}` — log this to the
  existing sync-log model and surface it in the sync status UI.
- `required` flags are NOT enforced on the Odoo path (only in the seller UI),
  so partial attribute data is fine.

**What to build in the addon:**
1. A `jubasquare.attribute` model caching the remote attribute definitions
   per category (key, name, type, options, unit, group name, required).
   Add a "Refresh attributes" server action that re-fetches
   `GET /api/categories/{id}/attributes` for the product's selected category.
2. A mapping layer from Odoo's native `product.attribute` /
   `product.template.attribute.line` values to JubaSquare keys:
   model `jubasquare.attribute.mapping` {odoo_attribute_id, jubasquare_key},
   plus a per-product fallback: a One2many of simple key/value lines
   (`jubasquare.product.attribute.value`: key selection from the cached
   definitions, typed value widget matching `type`) shown in a
   "JubaSquare Attributes" notebook tab on product.template.
3. Extend the existing payload builder so the `attributes` dict is included
   only when at least one value is set (never send an empty dict on update
   unless the user explicitly clears values).
4. Validate dropdown/multi_select values client-side against cached
   `options` before pushing, to avoid 400 round-trips.
5. Keep everything backwards compatible: no changes to auth
   (`X-Jubasquare-Odoo-Token` header), endpoints, or existing fields.

### Acceptance tests
- Push a product with category `Electronics > Mobile Phones` and
  `{"brand":"Samsung","storage":"256GB"}` → appears on JubaSquare with those
  specs on the product page and in marketplace filters.
- Push again WITHOUT the attributes key → values on JubaSquare unchanged.
- Push an invalid option (`"storage":"999TB"`) → sync log records the 400
  with the server's detail message; product row shows failed status.
- Menu item push with `{"spice_level":"Hot","dietary_type":["Halal"]}` works.
- Category selector shows 3-level nested paths and only categories of the
  correct business type.
