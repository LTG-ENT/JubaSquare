# Odoo module — Iter 33.11 update prompt for Claude

Copy the block below into a Claude conversation with your Odoo
`jubasquare_orders` (or equivalent JubaSquare sync) addon attached. It
teaches Claude the FULL current schema for **nested categories** and the
**dynamic attribute system** (including the two-mode measurement type
shipped in Iter 33.11) so the Odoo side stays in lockstep with the
JubaSquare marketplace.

Companion prompts already in `/app/memory/`:
- `odoo_kitchen_control_prompt.md`
- `odoo_iteration28_prompt.md`
- `odoo_iteration31_prompt.md`
- `odoo_iteration33_prompt.md`
- `odoo_iteration335_prompt.md`
- **THIS FILE** — nested categories + attributes + measurement fields.

---

## PROMPT (copy from here down)

I have an Odoo addon that syncs products, shops, restaurants and orders
with JubaSquare via REST webhooks. It ALREADY handles flat category names,
prices, stock, images and the Iter 33.5 delivery webhook. It does NOT yet
handle the **hierarchical (nested) category tree** or the **dynamic
attribute system**, and both concepts must land on the Odoo side so:
  - Odoo can be the source of truth for the taxonomy (create/rename/move
    categories → mirrored to JubaSquare).
  - Odoo product templates can carry `category_id` (leaf) + `attributes`
    dict (dynamic fields) → mirrored to JubaSquare's `products.attributes`.

Study the existing addon first, then extend it. Do NOT rebuild what
already works.

### 1. Category taxonomy (nested)

JubaSquare `categories` schema (each doc):
```json
{
  "id":          "<uuid>",
  "name":        "Electronics & Accessories",
  "parent_id":   null | "<uuid>",         // null for top-level
  "path":        "<pid>/<gpid>/…",         // "/"-joined ancestor ids, top-level = "" or missing
  "depth":       0 | 1 | 2 | …,
  "group":       "retail" | "wholesale" | "restaurant",
  "description": "<optional short blurb>",
  "image_url":   "<optional>",
  "order":       0,
  "is_active":   true
}
```

Webhooks JubaSquare exposes today are ONLY the following (see
`/app/backend/odoo_routes.py`):

- `POST /api/odoo/products/upsert`
- `POST /api/odoo/products/stock-update`
- `POST /api/odoo/products/unpublish`
- `POST /api/odoo/orders/status-update`
- `POST /api/odoo/kitchen/{action}`
- `POST /api/odoo/delivery/status-update`
- `POST /api/odoo/invoice/status-update`

For CATEGORY and ATTRIBUTE writes you MUST use the JubaSquare admin REST
API and authenticate as an admin using the JWT you already mint for
regular service calls (see `service-token/generate` under
`/api/odoo/service-token/generate`). Base URL: `https://www.jubasquare.com`.

Category endpoints (`/app/backend/server.py`):
- `GET  /api/categories/tree?group=retail|wholesale|restaurant` — full tree
- `POST /api/admin/categories` — body: `{name, parent_id, group, description?, image_url?, order?}`
- `PUT  /api/admin/categories/{id}` — same body, partial
- `POST /api/admin/categories/{id}/move` — body: `{new_parent_id, new_order?}`
- `POST /api/admin/categories/reorder` — body: `{parent_id, ordered_ids: [...]}`
- `DELETE /api/admin/categories/{id}`

Attribute + group endpoints (`/app/backend/attributes_routes.py`):
- `GET  /api/attributes` — list
- `POST /api/admin/attributes` — body matches `AttributeIn` (see schema
  above; server auto-slugs `key`, handles cross-group name reuse).
- `PUT  /api/admin/attributes/{id}` — partial update via `AttributeUpdateIn`.
- `DELETE /api/admin/attributes/{id}`
- `POST /api/admin/attribute-groups` — body: `{name, business_type, order?}`
- `PUT  /api/admin/attribute-groups/{id}`
- `DELETE /api/admin/attribute-groups/{id}`

All admin endpoints require `Authorization: Bearer <jwt>` where the JWT
represents a user with `role="admin"`. The Odoo module already stores an
admin bearer token per the earlier iterations — reuse it.

**Do not** attempt to invent `POST /api/odoo/webhook/category-upsert` or
similar routes. If you truly need webhook-shaped endpoints for
categories/attributes, propose them separately; for now, hit the admin API
directly.

Odoo integration requirements:
1. Extend the Odoo `product.category` model (or a shadow model
   `jubasquare.category`) so it stores the JubaSquare `id` + `path` + `depth`
   AFTER a successful upsert (needed for future updates + delete).
2. When an Odoo category is created or renamed, hit `POST /api/admin/categories`
   (or `PUT /api/admin/categories/{id}` if you already know the id) with
   the current parent's JubaSquare `id` under `parent_id`. Retry with
   exponential backoff (max 5) on 5xx.
3. When an Odoo category is archived or unlinked, call
   `DELETE /api/admin/categories/{id}` (soft-cascade-deletes on the
   server).
4. Wholesale + Restaurant taxonomies live under `group:"wholesale"` /
   `group:"restaurant"`. Map your Odoo category tree accordingly (usually
   one root per business type).
5. Do NOT flatten the tree — JubaSquare relies on `parent_id` to build the
   sidebar and to run category-descendant queries. Root categories send
   `parent_id: null`.

### 2. Dynamic attribute system (Iter 33 → 33.11)

JubaSquare has separate `attribute_groups` and `attributes` collections
plus per-product `attributes` dict values.

**attribute_groups** schema:
```json
{ "id": "<uuid>", "name": "Technical Specifications", "business_type": "retail", "order": 0 }
```

**attributes** schema (full — includes 33.11 measurement fields):
```json
{
  "id":                "<uuid>",
  "key":               "brand",                   // auto-slugged from name; suffixed with group slug on cross-group name reuse
  "name":              "Brand",
  "description":       "<optional>",
  "type":              "text" | "number" | "decimal" | "dropdown" | "multi_select"
                     | "boolean" | "date" | "color" | "weight" | "dimensions"
                     | "measurement",
  "business_type":     "retail" | "wholesale" | "restaurant",
  "category_ids":      ["<uuid>", ...],           // empty = applies to every category in this business_type
  "group_id":          "<uuid>" | null,
  "options":           ["Samsung","Apple", …],    // dropdown / multi_select / color
  "unit":              "kg" | "cm" | "",          // legacy single unit (still supported)
  "measurement_mode":  "single" | "dimensions",   // measurement type only
  "unit_options":      ["cm","m","in"],           // measurement + weight/dimensions — customer/seller picks one per value
  "required":          false,
  "filterable":        true,
  "searchable":        false,
  "show_on_all":       false,                     // customer sees this filter on Marketplace even when no category is picked
  "order":             0,
  "is_active":         true
}
```

**Product `attributes` value dict** (stored on `products.attributes`):
```json
{
  "brand":        "Samsung",
  "storage":      128,                    // number
  "colors":       ["black", "gold"],      // multi_select
  "warranty":     true,                    // boolean
  "size":         { "value": 12.5, "unit": "cm" },              // measurement (single mode)
  "package_size": {                                              // measurement (dimensions mode)
    "length": { "value": 30, "unit": "cm" },
    "width":  { "value": 20, "unit": "cm" },
    "height": { "value": 10, "unit": "cm" }
  }
}
```

Attribute writes go to the ADMIN REST API — not to a `/api/odoo/webhook/*`
route. See "Webhooks JubaSquare exposes today" section above for the full
list of admin endpoints (`POST /api/admin/attributes`,
`POST /api/admin/attribute-groups`, `DELETE …/{id}`, etc.). Authenticate
with a JWT for an `admin` role account.

Odoo integration requirements:
1. Model `jubasquare.attribute.group` mirroring the above with a `name` +
   `business_type` selection field + JubaSquare `id`.
2. Model `jubasquare.attribute` mirroring the schema. Field mapping:
   - `type` — selection matching the 11 types above.
   - `business_type` — selection retail/wholesale/restaurant.
   - `category_ids` — many2many to `jubasquare.category`.
   - `options` — comma-separated char (parsed to list on push).
   - `unit_options` — comma-separated char.
   - `measurement_mode` — selection `single`/`dimensions` (only visible
     when `type == "measurement"`).
   - Booleans: `required`, `filterable`, `searchable`, `show_on_all`,
     `is_active`.
3. On save / rename, hit `POST /api/admin/attributes` (or `PUT
   /api/admin/attributes/{id}` when updating). On archive / unlink, call
   `DELETE /api/admin/attributes/{id}`.
4. On product save (`product.template`), collect the values of any
   attributes assigned to the product's category (via `category_ids` OR
   the empty-array wildcard) and post them under `attributes` on the
   `POST /api/odoo/webhook/product-upsert` payload. Follow the shape above
   EXACTLY — especially for `measurement`:
   - single mode → `{"value": <number>, "unit": "<from unit_options>"}`
   - dimensions mode → nested `length/width/height` each `{value, unit}`.
5. Do NOT compute or store attribute keys yourself. Always send `name`
   (and optionally `id`) — JubaSquare returns the canonical `key` in its
   response so you can persist it back to Odoo for future updates.

### 3. Iter 33.11 measurement acceptance tests

1. Create an admin attribute of type `measurement`, mode `dimensions`,
   `unit_options=["cm","m","in"]` via `POST /api/admin/attributes` from
   the Odoo module → response 200 with the new `id` and `key`.
2. Assign it to two categories under the Retail tree via `category_ids`.
3. On a matching product, populate:
   `{package_size: {length: {value:30,unit:"cm"}, width:{value:20,unit:"cm"}, height:{value:10,unit:"cm"}}}`
   and push `POST /api/odoo/products/upsert`. Response 200. GET the
   JubaSquare product → the same dict comes back.
4. Change the attribute to `measurement_mode="single"`,
   `unit_options=["kg","g","lb"]` via `PUT /api/admin/attributes/{id}` →
   JubaSquare updates in place; existing product values continue to
   validate as long as their unit is in the NEW `unit_options`.

### 4. Retry + idempotency

- Every upsert is idempotent by `id`. Store the JubaSquare `id` on the
  Odoo record on first successful sync.
- Failed pushes: retry with exponential back-off (base 30s, factor 2, max
  5 attempts). Persist the queue in Odoo (`ir.cron` job) so a JubaSquare
  outage doesn't lose changes.
- Log every push + response `status` in an audit model
  (`jubasquare.sync.log`) so admins can see what synced when.

### Deliverables

- Migration script that seeds `jubasquare.category` +
  `jubasquare.attribute.group` + `jubasquare.attribute` from
  JubaSquare's current data via:
  - `GET /api/categories/tree?group=retail|wholesale|restaurant` (public, no auth)
  - `GET /api/attributes?business_type=<...>` (public, no auth)
  - `GET /api/admin/attribute-groups?business_type=<...>` (admin JWT required)
- Bi-directional sync jobs (Odoo → JubaSquare via the webhooks above;
  JubaSquare → Odoo via a scheduled `pull` if you want to accept JubaSquare
  admin edits back into Odoo — optional).
- End-to-end test for the four Iter 33.11 acceptance tests above.

Write clean, idiomatic Odoo 16/17 Python. Preserve every existing sync
path — the goal here is to ADD attributes + nested categories, not rework
what already works.
