# JubaSquare — Product Requirements (PRD)

Branch: `with-odoo-v2` · **PRODUCTION deployed** at https://jubasquare.com

## Product intent
A multilingual (English/Arabic RTL) Juba-focused marketplace connecting shops, restaurants, wholesale suppliers, drivers, and customers. Odoo-integrated. Runs on React + FastAPI + MongoDB Atlas, deployed via Emergent.

## Core personas
- **Customer**: browses, orders, pays cash-on-delivery or wallet, tracks deliveries.
- **Seller**: manages shops/restaurants, products/menu items, delivery pricing, orders, payouts.
- **Driver**: accepts assignments, delivers COD orders, hands cash to admin.
- **Admin**: verifies shops/restaurants, manages global settings, commissions, payouts, delivery rules.

## Established feature areas
- Auth (JWT-based email + password + email verification), Odoo integration, wallet, Web Push/PWA, Notifications.
- Cash-on-Delivery flow with per-seller order splits (`/app/backend/cod.py`).
- Hybrid Delivery: Admin OR Seller manages delivery per-shop / per-restaurant. Modes: free / fixed / per_area.
- Emergent Object Storage for uploads (survives redeploys).
- Cascade deletes on user removal.
- Multilingual UI + Arabic RTL support.

## Completed (Feb 2026, this fork)

### Iter 24 — Analytics by channel + wallet print receipts + OTP back-fill (Feb 4, 2026)
Reported by user; 8/8 backend tests pass (`/app/test_reports/iteration_24.json`).

- ✅ **Leftover Driver Pickup OTP on legacy splits** — `_enrich_rate` in `cod.py` now back-fills `delivery_managed_by` at read time (one batched query per side; falls back to platform default via `settings.admin_manages_delivery`). Legacy splits created before the field was persisted now correctly report `sellerIsDriver=true` → OTP hides. Admin-driver flow still shows OTP.
- ✅ **Restaurant orders persist delivery_managed_by** — `initialize_restaurant_order_cod` now stores the resolved 'seller'/'admin' value at creation, matching splits.
- ✅ **Sales Analytics split by channel** — `/api/seller/analytics` returns `by_channel: {combined, marketplace, restaurant}` with each carrying its own `totals` + `revenue_series`. Backwards-compatible top-level `totals` still equals combined.
- ✅ **Analytics currency toggle** — `SellerAnalyticsTab.jsx` now respects `useCart().currency` + `exchangeRate`. Stat cards, chart Y-axis, and tooltips all reflect the toggle.
- ✅ **Analytics channel selector** — segmented control (All / Shops / Restaurants) drives the stat cards + revenue chart.
- ✅ **Analytics Print** — dedicated print view lists all three channels + top products + low stock; SSP/USD-aware with the seller's rate.
- ✅ **Wallet: Print Receipt on Completed orders** — `SellerWalletTab.jsx` adds a Print button (data-testid `print-completed-<id>`) on each Completed row and inside the detail modal (data-testid `wallet-print-receipt`). Thermal-friendly HTML template mirrors the Kitchen Dashboard customer receipt style; works for both marketplace splits and restaurant orders.

### Iter 23 — Shop-flow currency/timeline/self-deliver bug batch (Feb 4, 2026)
Reported by user; all 11/11 backend tests pass (`/app/test_reports/iteration_23.json`).

- ✅ **Wallet item price SSP 372 → 4,030 bug** — root cause was a misplaced paren in `SellerWalletTab.jsx` (`formatPrice(a || (b, c, d))` — the comma operator collapsed to just `currency`, so `formatPrice` ran with rate=undefined → default 600 fallback). Fixed to `formatPrice(line_total_usd ?? price*qty, detail.exchange_rate_ssp || exchangeRate, currency)`.
- ✅ **Sales Analytics $0.62 → $5.38** — `/api/seller/analytics` now sums `seller_earning_usd` from delivered `seller_order_splits` + `restaurant_orders` (what the seller actually pockets) instead of raw item revenue from `db.orders`. Per-product cards still use gross for the top/low-product breakdown, documented in the endpoint docstring.
- ✅ **Customer sees 1,200 SSP delivery instead of 13,000** — `enrich_marketplace_orders` now attaches an **order-level** `exchange_rate_ssp` (from the primary seller), and `Orders.jsx` uses `o.exchange_rate_ssp` (not the global `exchangeRate`) for delivery-fee + total SSP conversion. Same fix applied to the restaurant order section.
- ✅ **Customer timeline never advances past 'Placed'** — `OrderStatusTimeline` now accepts a `preparationStatus` prop. `Orders.jsx` computes `maxPrep` across splits and passes it: `accepted`/`preparing` → step 1, `ready_for_pickup`/`handed_to_driver` → step 2, `delivered` → step 3. Same wiring for restaurant orders using `o.seller_preparation_status`.
- ✅ **Customer sees own phone instead of driver's** — computed `driverContact` from splits (`seller_driver_phone` || `driver_phone`) and displays it prefixed with `Driver ·`. Falls back to customer phone only when no driver assigned.
- ✅ **Split stays in 'Active' after cash collected** — new "Completed" sub-tab in `SellerWalletTab.jsx` between "Active Orders" and "Cancelled Orders". Active filter excludes rows where `delivery_status === 'delivered'`. Completed table shows delivery time + payout status + View action.
- ✅ **Driver Pickup OTP visible when seller = driver** — hidden entirely when `delivery_managed_by === 'seller'`. Replaced by two buttons: `Send for delivery` (data-testid `wallet-self-deliver-start`) and `Cash collected from driver` (`wallet-self-deliver-complete`). No admin driver user is required for the seller-managed path.
- ✅ **Seller-driver contact persistence** — `POST /seller/splits/{id}/self-deliver-start` (and restaurant twin) now accept optional Body `{driver_name, driver_phone}` and persist as `seller_driver_name` / `seller_driver_phone` on the split — surfaced to the customer via the driver-contact chip.
- ✅ **Split creation persists `delivery_managed_by`** — resolved value ('seller' or 'admin') is stored on the split at creation for downstream UIs to read without re-consulting shop settings.
- ✅ **Targeted dark-mode patch** — outer `bg-white` containers in `Orders.jsx` + wallet detail modal now have `dark:bg-[var(--js-panel)]` + `dark:border-[var(--js-border)]`. Full sweep still pending (see backlog).

### Iter 22 — Odoo pull-sync enrichment + Customer Receipt polish (Feb 3, 2026)
- ✅ **Missing `Body` import** — `odoo_routes.py` was crashing on startup with `NameError: name 'Body' is not defined` (imported in fix). Backend now boots clean.
- ✅ **GET /api/admin/odoo/orders/pending** — now returns the enriched Odoo-consumable envelope per shop split / restaurant order: `{sub_order_id, order_id, entity_type, odoo_order_ref, customer_*, delivery_area/address, payment_method, delivery_type, currency='USD', exchange_rate_ssp, subtotal_usd, delivery_fee_usd, total_usd, items[{sku, odoo_product_id, name, quantity, price_usd, sides[]}], meta.source='jubasquare'}`. SKU/`odoo_product_id` are resolved via a batched product/menu-item lookup. Only orders with `odoo_connection.enabled=true AND send_orders=true` are exposed.
- ✅ **POST /api/odoo/orders/status-update** — Odoo can now ack a sync: `{order_id, sub_order_id?, status:"synced"|"failed"}` updates `seller_order_splits` (when `sub_order_id`) or `restaurant_orders` (fallback) with `odoo_sync_status` + `odoo_last_sync_at`, and writes an `odoo_sync_logs` entry. Requires the DB-managed service token via `X-Jubasquare-Odoo-Token` header (admin JWT alone is intentionally not accepted here).
- ✅ **Kitchen Dashboard Customer Receipt redesign** — clean monochrome inline-SVG icons (store, clipboard, clock, user, phone, pin, cash, note, bag), replaced colored emoji, tighter layout matching user's reference design; USD/SSP currency toggle preserved.
- ✅ 18/18 backend tests pass (`/app/test_reports/iteration_22.json`).

### Iter 14 — Restaurant delivery mirror + verification visibility gate
- ✅ "Mirror Shops" restaurant delivery — `_calculate_delivery_fee` supports restaurant-level free/fixed/per_area + `delivery_managed_by`.
- ✅ `GET /api/restaurants/mine` — seller's own restaurants regardless of verification.
- ✅ `SellerRestaurantEdit.jsx` (route `/seller/restaurant/:restaurant_id/edit`).
- ✅ Only Verified shops/restaurants visible to customers. Anon requests to unverified detail routes → 404. Owner/admin bypass.
- ✅ 24/24 backend tests pass (`/app/test_reports/iteration_14.json`).

### Iter 15/16 — Reviews with photos + Live Driver Tracking + polish
- ✅ **Side-options input sizing** — name input widened (flex-3), price narrowed (flex-1).
- ✅ **Verification banner** on `ShopPage` — owner/admin see a Pending or Rejected banner with CTA to `/seller` for KYC.
- ✅ **Product reviews with photos** — `ProductReviewIn` accepts `photos:List[str]` (capped at 5, URL length capped at 1024). Frontend `ReviewPhotoUpload` compresses to 1600 px JPEG @ q82 client-side, then uploads to Object Storage.
- ✅ **Live Driver Tracking** — new endpoints:
  - `POST /api/driver/location` (driver-only): pushes `{lat, lng, accuracy}` every ~10 s. Stores latest + last-20 trail in `db.driver_locations`.
  - `GET /api/customer/orders/{order_id}/live-tracking` (customer/admin): returns per-assignment `driver_location`, `destination`, `distance_km`, `eta_minutes` (Haversine × 4 min/km).
  - Frontend: `DriverGeoBeacon` (silent geolocation watcher on `DriverDashboard`), `LiveTrackingMap` (Leaflet map on `Orders.jsx` for `out_for_delivery` orders). `JUBA_AREA_COORDS` centroid map for known Juba areas.
- ✅ **Reviews index migration** — legacy non-sparse unique index `reviews.order_id_1` migrated to a **partial** unique index (`{order_id: {$type: 'string'}}`) so product reviews (no order_id) can coexist with per-order restaurant-review dedupe. Idempotent on startup.
- ✅ 16/16 backend tests pass (`/app/test_reports/iteration_16.json`).

## P1 Backlog
- (none — Phase 2 P1 items shipped)

## P2 / Refactor
- Split `/app/backend/server.py` (~6,900 lines) into domain routers (`shops.py`, `restaurants.py`, `products.py`, `reviews.py`, `driver_tracking.py`, `admin.py`).
- Expand `JUBA_AREA_COORDS` — missing Rock City, Tongping, Kator, Lologo, etc. (users in those areas currently get downtown fallback ETA).
- Deprecate legacy `delivery_pricing` on RestaurantIn now that mirror-shops is authoritative.
- Batch driver lookups in `customer_live_tracking` (`$in` instead of per-assignment `find_one`).
- `post_driver_location` — consolidate to single `findOneAndUpdate` with `$push`+`$slice`.
- SSRF hardening: validate review photo URLs are same-origin or `/api/uploads/`.

## Key files
- `/app/backend/server.py` — main API router, all new endpoints for iter14–16.
- `/app/backend/cod.py` — cash-on-delivery + delivery fee calculator.
- `/app/backend/storage.py` — Emergent Object Storage.
- `/app/backend/email_service.py` — Resend email integration.
- `/app/frontend/src/pages/SellerShopEdit.jsx` — shop editor (with delivery).
- `/app/frontend/src/pages/SellerRestaurantEdit.jsx` — restaurant editor (with delivery mirror).
- `/app/frontend/src/pages/SellerDashboard.jsx` — seller landing.
- `/app/frontend/src/pages/AdminDashboard.jsx` — admin console.
- `/app/frontend/src/pages/ShopPage.jsx` — customer shop preview + owner verification banner.
- `/app/frontend/src/pages/ProductDetail.jsx` — product detail + reviews with photos.
- `/app/frontend/src/pages/Orders.jsx` — customer order tracking (live map).
- `/app/frontend/src/pages/DriverDashboard.jsx` — driver assignments + geolocation beacon.
- `/app/frontend/src/components/ReviewPhotoUpload.jsx` — multi-photo upload with compression.
- `/app/frontend/src/components/DriverGeoBeacon.jsx` — silent watchPosition sender.
- `/app/frontend/src/components/LiveTrackingMap.jsx` — Leaflet map + ETA.

## Critical guardrails (do not break)
1. All upload URLs must be relative (`/api/uploads/...`).
2. Never use `<input type="url">` for image URL fields; use `type="text"` + `noValidate` on the form.
3. `_calculate_delivery_fee` is the single source of truth for delivery pricing.
4. The `reviews.order_id_1` index MUST remain a partial index; do not recreate as unfiltered unique or you'll break product reviews again.
5. Preserve `.git` / `.emergent` folders.

## 3rd-party integrations
- MongoDB Atlas, Resend, Stripe, Emergent Object Storage (via EMERGENT_LLM_KEY).
- **New**: OpenStreetMap tiles via react-leaflet on the customer tracking map (no key needed).

## Test credentials
See `/app/memory/test_credentials.md` — admin only.
