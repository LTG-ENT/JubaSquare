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

### Iter 30 — Wave 3: Growth Insights email, Restore user, Search relevance (Feb 8, 2026)
20/20 backend tests pass (`/app/test_reports/iteration_33.json`).

- ✅ **Weekly Growth Insights email** — sellers receive a Resend-powered email with 7-day KPIs (orders, revenue, cancels, favorites, avg rating, review count) versus the prior 7 days, top-5 selling products, and personalized tips (high cancel-rate warning, no-orders nudge, low-rating call-to-action).
  - `_compute_seller_growth_metrics(seller_id, days=7)` aggregates from `seller_order_splits`, `restaurant_orders`, `favorites`, `orders` (with `items.seller_id` filter for top-sellers).
  - `GET /api/seller/growth-insights` — seller preview.
  - `POST /api/admin/growth-insights/send/{seller_id}` — admin single-seller send (+ `dry_run:true` option).
  - `POST /api/admin/growth-insights/send-all` — batch send; skips zero-activity + invalid-email sellers; returns `{sent, skipped, failed, total_sellers}`.
  - "Send now" button on Admin → Users panel (`data-testid="send-growth-insights-btn"`).
  - `_pct_delta` supports `lower_is_better` so cancellation drops correctly render green.
- ✅ **Restore soft-deleted user** — `POST /api/admin/users/{id}/restore` reverses the soft cascade: user unflagged, owned shops/restaurants/products/menu_items un-flagged too. Idempotent for already-active users. Admin-only.
  - Admin UI: "Show deleted users" toggle + `DELETED` pill on rows + "Restore user" menu action.
- ✅ **Search relevance** — `/api/search` now over-fetches 3× limit, then Python-sorts each collection by tier: exact-prefix name (0) > substring name (1) > description match (2) > other (3). LTG partner, Verified status, and active-promo flags tie-break equal-relevance rows. Soft-deleted and non-public entries excluded.


### Iter 30 — Wave 2: LTG shelf, featured products, badge filters, ranking (Feb 8, 2026)
19/19 backend tests pass (`/app/test_reports/iteration_32.json`).

- ✅ **Filter-by-badge chip row** — new `<BadgeFilterBar>` component. Chips: `★ LTG` (gold), `🔥 Deals` (red gradient), `📦 Wholesale` (blue, shops+marketplace only), `✓ Verified` (green). Each toggles the corresponding URL param and calls `GET /api/{shops|restaurants|products}?{ltg|deals|wholesale|verified}=true`. Wired into Marketplace, Shops, Restaurants.
- ✅ **Composite recommendation ranking** — `/api/shops` now enriches EVERY candidate (not just the page slice) with real signals — `orders_count`, `cancelled_orders`, `favorite_count` — before running `_sort_shops`. Score = `LTG*40 + verified*20 + rating × log(1+reviews) × 3 + favs×0.5 + orders×0.3 − cancelled×0.5`. Verified: A(LTG)>B(high-orders)>C(high-cancellations) in tests.
- ✅ **Homepage LTG shelf** — new gold-gradient section on Home.jsx lists LTG shops + LTG restaurants. Auto-hides when both lists are empty.
- ✅ **Homepage featured products** — new `GET /api/homepage/featured-products?limit=N` endpoint returns Verified-shop, in-stock products sorted by `LTG*50 + rating×review-weight×5 + completed_orders×1.5 + favs×0.5 − cancellations×2`. Includes `exchange_rate_ssp` for pricing. Home renders a "Top-Rated Products" grid (auto-hidden when empty).
- ✅ **Empty promo section auto-hide** — RestaurantCard menu tab bar skips any `is_promo_section=true` section that has no live-promo items. Prevents customers seeing a "Promo" tab that lands them on an empty list.
- ✅ **Server-side deal enforcement** — `/api/products?deals=true` filters by `promo.active=true` at Mongo and re-checks `promo.starts_at/ends_at` window in Python via `promo_is_live`, so expired promos never leak into the deals view.


### Iter 30 — Wave 1: Badges, deal filters, review-on-delivered, LTG on products (Feb 8, 2026)
20/20 backend tests pass (`/app/test_reports/iteration_31.json`).

- ✅ **Shop/Restaurant card badges** — top-right stack: `LTG` (gold) + `DEALS` (fire gradient, animated) + `WHOLESALE` (blue, shops only) + `Verified` (green). Backend enriches `/api/shops` with `has_active_promo` + `has_wholesale` and `/api/restaurants` with `has_live_promo` + `has_active_promo` in a single aggregate per page.
- ✅ **Marketplace filter fixes** — (a) "All categories" now also clears `?deals=1`, (b) "Deals only" toggles ON/OFF on second click, (c) category tree refetches by `typeFilter` — Retail shows retail-only, Wholesale shows wholesale-only, All merges both.
- ✅ **Marketplace order review unblocked** — Orders.jsx marketplace path now honors `o.delivery_status==='delivered'` (or all splits delivered) in addition to `o.status`. Status badge, timeline, `isDelivered` and "Review" CTA all light up on self-delivered shop orders. Restaurant path already handled this.
- ✅ **Punchier promo badge** — ProductCard shows a full "🔥 −25% OFF" / "SAVE $X" / "2+1 FREE" ribbon top-left with pulse animation (`js-deal-badge`, 2.2s ease-in-out infinite, respects prefers-reduced-motion).
- ✅ **LTG per-product** — Product model gets `is_ltg_partner: bool`. New `PUT /api/admin/products/{id}/ltg-partner` admin-only endpoint. Product list sort now boosts LTG-partner products to the top of their verification tier. Gold LTG pill renders on ProductCard.
- ✅ **Favorites hardening** — `GET /api/favorites` filters out soft-deleted targets AND auto-cleans favorites pointing to hard-deleted items on the fly. Empty favorites for real customers who added favorites on removed items now stops appearing as orphans.


### Iter 29 — Seller onboarding wired + Soft-cascade user delete (Feb 8, 2026)
19/19 backend tests pass (`/app/test_reports/iteration_30.json`).

- ✅ **Seller onboarding (P2.1)** — Confirmed already wired end-to-end from prior work:
  - `SellerFirstLoginWizard.jsx` — auto-showing 3-slide modal (setup shop → add product → configure delivery) on first login; persists dismissal server-side.
  - `SellerDashboardTour.jsx` — react-joyride interactive tour hitting `data-testid`'s on every dashboard tab.
  - `SellerOnboardingCard.jsx` — persistent progress card w/ % complete, per-step checklist, "Setup Verified" badge at 100%.
  - `SellerGuide.jsx` — full-page fallback guide.
  - Backend endpoints already exist: `GET /seller/onboarding/progress`, `POST /seller/onboarding/complete-step`, `.../uncheck-step`, `.../dismiss-wizard`, `.../complete-tour`.
- ✅ **Soft-cascade user delete (P2.2, chose b + auto)** — `DELETE /api/admin/users/{id}` and `POST /api/admin/users/bulk-delete` now soft-delete:
  - User record retained + anonymized (`email` → `deleted+{id}@removed.local`, `name` → `[Deleted user]`, `phone` → null, `password_hash` → `!disabled!`, `is_deleted=true`, `deleted_at`, `deleted_by`). `username`/`avatar_url` are `$unset` (not `$set:null`) to avoid unique-sparse index collisions.
  - **Wiped**: notifications, favorites, email_verifications, password_resets, onboarding_progress, carts, web_push_subscriptions, shop_messages (as customer).
  - **Soft-flagged** (`is_deleted=true`, `deleted_at`): owned shops, restaurants, products, menu_items — hidden from public listings but recoverable.
  - **Retained** (for accounting): orders, restaurant_orders, seller_order_splits, seller_payouts, invoices, restaurant_invoices, reviews.
  - Login blocked for soft-deleted users (401 "Invalid email or password"); `get_current_user` also rejects lingering sessions.
  - `GET /api/admin/users` hides deleted by default; `include_deleted=true` shows them for audit.
  - Bulk delete returns `{deleted, soft_deleted:true, succeeded:[...], failed:[...]}` with per-user error isolation.
  - Idempotent: re-deleting already-deleted user returns `{ok:true, soft_deleted:true, already:true}` without erroring.


### Iter 28 — LTG partner, BOGO promo, favorites fixes, section limit → 10 (Feb 8, 2026)
25/25 backend tests pass (`/app/test_reports/iteration_28.json`).

- ✅ **"Part of LTG" partner badge** — `is_ltg_partner` boolean on shops + restaurants. Admin-only toggles at `PUT /admin/shops/{id}/ltg-partner` and `PUT /admin/restaurants/{id}/ltg-partner`. LTG shops/restaurants are boosted to the top of listings and rendered with a gold "★ PART OF LTG" pill on ShopCard/RestaurantCard.
- ✅ **BOGO promo type** — `Promo.type` now supports `'bogo'` with `bogo_min_qty` (default 2). Server-side `bogo_free_quantity()` grants 1 free unit per `bogo_min_qty` paid units. Payload never trusts the client — computed on `/orders` and `/restaurant-orders` create.
- ✅ **Section limit raised 6 → 10** — both shop `product_sections` and restaurant `menu_sections`. 11th section is rejected (400).
- ✅ **Promo-only sections** — `SellerSection.is_promo_section=True` auto-populates that section on the storefront from any item whose `promo.active` is true. No manual assignment needed.
- ✅ **Favorites payload fix** — `GET /api/favorites` now returns `{favorite_id, target_type, created_at, item}`. Favorites page no longer drops items when they fall outside a 200-limit sub-query.
- ✅ **Favorites query-DELETE** — new `DELETE /api/favorites?target_type=&target_id=` handler (path-based DELETE preserved). Fixes silent 404 from ProductCard / ProductDetail / Favorites Remove buttons.
- ✅ **Review eligibility on self-delivery** — `canReview = status === 'completed' || delivery_status === 'delivered'`. Customers can now review shop-flow orders that were self-delivered by the seller (they land in `delivered`, not `completed`).
- ✅ **Top 4 shop products with images** — Shops.jsx + Home.jsx now sort each shop's featured strip by `order_count desc` and filter to items with an `image_url`, so ShopCard's preview always shows real top-sellers.
- ✅ **Odoo Iter 28 sync prompt** — `/app/memory/odoo_iteration28_prompt.md` gives the user's Odoo developer the full schema-diff (LTG, sections, promo/BOGO, sides_required, free_quantity on invoice lines).


## Completed (Feb 2026, this fork)

### Iter 27 — Seller sections + time-limited promo (Feb 8, 2026)
22/22 backend tests pass (`/app/test_reports/iteration_27.json`).

- ✅ **Seller-defined sections** — new `menu_sections` on Restaurant (up to 6) and `product_sections` on Shop (up to 6). Each item references one via `menu_section_id`/`product_section_id`.
- ✅ **Backend enforcement** — `PUT /restaurants/{id}` and `PUT /shops/{id}` sanitise (drop empty names + dupes + trim to 40 chars) and reject payloads over the 6-section limit (400).
- ✅ **Time-limited promo on any item** — new `Promo` block on Menu items + Products: `{active, type: 'percent'|'amount', value, starts_at, ends_at}`. `effective_price_usd` helper computes the discounted price server-side on both `/restaurant-orders` and `/orders` create, so a crafted client can never bypass the promo → charged what the customer sees.
- ✅ **Promo safety** — `Promo.value` clamped to ≥0 via Pydantic validator; percent additionally clamped to ≤100 inside `effective_price_usd`. Negative-price safety guaranteed even for legacy docs.
- ✅ **Seller UI** — `MenuSectionsEditor` + `ShopSectionsEditor` (add/rename/reorder/remove, 6-max). `SectionPicker` + `PromoEditor` added to the menu-item and product forms with % / $ toggle and start/end datetime pickers.
- ✅ **Customer UI** — RestaurantCard menu drawer prefers seller sections over platform categories. ProductCard + MenuRow show emerald promo badge (e.g. `-25%`), strikethrough on the original price, and add the discounted price to cart.

### Iter 26 — Menu categorization + required sides (Feb 8, 2026)
13/13 backend tests pass (`/app/test_reports/iteration_26.json`).

- ✅ **Menu grouped by category** — `RestaurantCard.jsx` menu drawer now looks up each item's `category_id` in `/categories/tree?group=restaurant`, renders a chip filter (All + one per category) and section headers when >1 category is present.
- ✅ **Required sides on menu items** — three new `MenuItemIn` fields:
  - `sides_required` (bool)
  - `sides_min_choices` (int|null; default 1 when required)
  - `sides_max_choices` (int|null; null = unlimited)
- ✅ **Backend enforcement** — `POST /api/restaurant-orders` rejects orders that violate the min/max constraint or use invalid side names (400 error). Untrusted frontend can no longer bypass.
- ✅ **Seller UI** — new `RequiredSidesEditor` in SellerDashboard menu-item form. Preset hints: "Pizza size → min 1, max 1", "Burger meal → min 1, max blank". Toggle only enabled once at least one side item exists.
- ✅ **Customer UI** — `MenuRow` auto-expands when sides are required, shows "Required" badge + live counter (n/max), disables Add-to-cart until requirement met. For max=1 (e.g. pizza size), selecting a new side replaces the previous choice.

### Iter 25 — Kitchen PWA install + Odoo control + receipt logo + ETA + in-stock sort + favorites (Feb 7, 2026)
22/22 backend tests pass (`/app/test_reports/iteration_25.json`).

- ✅ **Kitchen Dashboard PWA install** — `beforeinstallprompt` captured on the Kitchen page only (`kitchen-install-pwa` testid). "Installed" chip when already running as PWA. Manifest already existed.
- ✅ **Restaurant order number** — prominent badge (`O-YYMMDD-XXXXX` format matching receipt) on every kitchen lane card + detail modal.
- ✅ **Odoo controls Kitchen state machine** — `POST /api/odoo/kitchen/{accept|preparing|ready|complete|cancel}` with body `{order_id, sub_order_id?, reason?}` — auth via existing `X-Jubasquare-Odoo-Token`. Updates the doc's `seller_preparation_status`, `status`, stage timestamps (accepted_at/preparing_started_at/ready_at/delivered_at/cash_collected_at) and writes to `odoo_sync_logs`. Complete also sets `delivery_status=delivered` + `payment_status=collected_by_seller`. Cancel accepts reason, sets `cancellation_reason` + `cancelled_by='odoo'`.
- ✅ **Customer receipt logo (toggle + URL)** — new `receipt_show_logo` + `receipt_logo_url` fields on Shop & Restaurant. Rendered in Kitchen Dashboard receipt AND SellerWalletTab print receipt. Fields also enriched onto splits/restaurant-orders via `_enrich_rate` so the wallet doesn't need a shop lookup.
- ✅ **Estimated delivery time** — `eta_mode` (off | fixed | range) + minute fields on Shop & Restaurant. New UI editors on both edit pages. Shown as an emerald chip on Restaurant Checkout + on Orders (customer). Snapshot enriched onto splits/orders.
- ✅ **`PUT /api/restaurants/{id}` persistence bug** — explicit whitelist was dropping the new iter25 fields; added all six. Shop PUT already used `body.model_dump()`.
- ✅ **Marketplace in-stock sort** — `/api/products` sorts products with stock>0 before out-of-stock (within same verification tier).
- ✅ **Favorites link in Header** — customer role now sees a Favorites entry in the quick menu → routes to the existing `/favorites` page.

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
