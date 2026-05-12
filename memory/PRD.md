# JubaSquare — by L.T.G Enterprise

## Original Problem Statement
Multi-vendor marketplace + restaurant **demo** web app for Juba, South Sudan. ZERO-setup showcase, 3-button instant login.

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async). `server.py` (~1383 lines) — auto-seeds.
- **Auth**: JWT cookie+Bearer + bcrypt + token-version (force-logout-all). Demo accounts password `1234`.
- **Frontend**: React 19 + React Router 7 + Tailwind. Outfit/Manrope. Sonner. lucide-react.
- **Currency**: USD + SSP everywhere. Seller per-shop rate, admin global fallback.

## User Personas
- **Customer**: browse unified marketplace (retail + wholesale toggle), filter by Juba area, cart, orders, favorites, restaurant ordering with sides.
- **Seller**: own Shops (product-selling) and Restaurants (menu-selling); per-item wholesale toggle; weekly invoices with amount owed.
- **Admin**: verify shops, block emails, platform settings, invoices (filter/mark paid/unpaid/regenerate), per-shop custom commission overriding global.

## What's Been Implemented

### Iter 1 (Feb 2026)
Core auth + shops/products/restaurants CRUD + orders + per-seller exchange rate + admin verify/block. 25/25 tests.

### Iter 2 (Feb 2026)
Custom logo, expanded categories, wholesale module, side items, mandatory phone+area, admin/seller/customer settings (modules, maintenance, brute-force, areas, force-logout, low-stock alert, auto-hide, dark mode), favorites. 43/43 tests.

### Iter 3 (Feb 2026)
Invoices module (admin + seller) auto-generated per shop/week. Product 3-mode form (marketplace/restaurant/wholesale). 16 food subcategories. Wholesale pricing tiers. 58/58 tests.

### Iter 4 (Feb 2026) — **Unified shopping + per-shop commission**
- **Marketplace unified**: single `/marketplace` page with filter chips (All / Retail only / Wholesale only). Wholesale products render `WholesaleCard` (min-qty + bulk price + verified-supplier badge) inline with regular `ProductCard` via `product.is_wholesale` flag
- **`/wholesale` route** → React Router Navigate to `/marketplace?view=wholesale`. Wholesale nav link removed from Header
- **Admin clickable shops**: shop rows open detail modal with custom commission rate input (per-shop override; decimal 0–1). Save regenerates invoices for that shop at the new rate. Empty = inherit global rate
- **Seller Shop form**: dropped "Category" field; replaced with **Shop / Restaurant type toggle** — routes to `POST /api/shops` or `POST /api/restaurants`
- **Seller Product form** (unified): single "Add Item" button; modal has a unified Business select (optgroups: 🛍️ Shops / 🍽️ Restaurants). When a Restaurant is picked → shows food-category (16 options) + side items editor. When a Shop is picked → shows unified retail category + "Enable wholesale pricing" toggle; turning it ON reveals MOQ + bulk price + pricing tiers
- **Unified categories**: wholesale + retail share the 9-category list (Groceries, Clothing & Fashion, …)
- **Backend**:
  - `ShopIn.category` now optional (backward-compat); `ShopCommissionIn` model; `PUT /api/admin/shops/{id}/commission` endpoint with 0–1 bound validator
  - `ProductIn.is_wholesale` new flag + `/api/products?is_wholesale=true|false` filter
  - `_rebuild_invoices()` applies `shop.commission_rate` when set, else global rate
- 66/66 tests pass (25+18+15+8)

### Iter 5 (Feb 2026) — **Standalone Shop Pages + Internal Messaging + Visibility toggle**
- **Public Shop Page** at `/shop/:shop_id` with hero banner + logo, OPEN/CLOSED status, opening hours, COD-only banner, products grid filtered to that shop, search.
- **Contact Seller modal** (one-way customer→seller messaging). Anonymous senders redirected to `/login?next=/shop/:id`; logged-in customers post directly. Body required (2–2000 chars).
- **SellerShopEdit** page at `/seller/shop/:shop_id/edit` — full storefront editor for name, description, area, logo (square), banner (wide), default photo, opening hours, OPEN/CLOSED toggle, and delivery model (free / fixed / per-area). Owner-only (admin override).
- **Messages tab in Seller Dashboard** with unread badge (`/api/messages/seller/unread-count`), filter (All / Unread), mark-read & delete actions; click-to-call (tel:) and click-to-email (mailto:) on each message.
- **Backend**: `ShopIn` extended with `banner_url`, `logo_url`, `opening_hours`, `is_open`, `is_public`; `shop_messages` collection + endpoints `POST /shops/{id}/messages` (anon-allowed but requires email/phone), `GET /messages/seller`, `GET /messages/seller/unread-count`, `PUT /messages/{id}/read`, `DELETE /messages/{id}`; `PATCH /shops/{id}/visibility` to toggle `is_public`. Public `GET /shops` and `/products` (without `shop_id`) now exclude hidden shops.
- **Frontend**: routes wired in `App.js`; SellerDashboard now exposes "Edit Shop Page" + "View public" links per shop card and a green/grey **public visibility toggle** with HIDDEN badge; ShopPage shows "Shop unavailable" to non-owners when hidden, and a preview banner to the owner; ShopCard (the marketplace shop card) now links directly to `/shop/:id` instead of the filtered marketplace.
- 87/87 tests pass (25+18+15+8+21). All iter5 frontend flows green.

### Iter 6 (Feb 2026) — **Hierarchical categories + Low-resource optimization**
- DB-backed hierarchical categories (`categories` collection + seeder); admin CRUD UI; hover mega-menu on Home nav.
- React `lazy()` + Suspense routing with `RouteLoader`.
- Backend pagination on all list endpoints (default 50); lightweight `/api/seller/low-stock-count`.
- 60s TTL in-memory cache on `/meta/categories`, `/categories/tree`, `/meta/areas`, `/pages`, `/site-config/footer`.
- Frontend request deduplication + safe-array fallback in `lib/api.js`.
- `DEPLOY.md` + `.env.example` for self-hosting.

### Iter 6.1 (Feb 2026) — Bug fix
- **SellerDashboard Modal** — fixed scroll issue when many delivery areas added in shop create/edit form. Modal now uses `flex flex-col` with sticky header and a dedicated `flex-1 min-h-0 overflow-y-auto` body so long forms scroll reliably on mobile + desktop.
- **Area dropdown** — replaced native `<select>` with custom `AreaSelectField` component. Now scrollable (max-h-72 with overflow), searchable, dark-mode aware, fetches areas dynamically from `/api/meta/areas` (so admin-added areas show up). Used in `SellerShopEdit.jsx` (Storefront identity Area + Per-area delivery rows) and `SellerDashboard.jsx` (New business modal Area + Per-area delivery rows).
- **Shop soft-delete** — `DELETE /api/shops/{id}` no longer hard-deletes. Sets `is_deleted=True`, `is_public=False`, and deactivates all of the shop's products (`is_active=False`). Public `/shops` and `/products` listings now exclude deleted shops + their products. Seller's `/shops/mine` still includes them so the seller can restore. `PUT /api/shops/{id}` auto-restores a deleted shop (sets `is_deleted=False`) and re-activates its products. Frontend shows a red "DELETED" badge on the shop card and explains the restore flow in the visibility section.

### Iter 6.2 (Feb 2026) — Restaurant category removed + Router crash fix
- **Removed the "Restaurant category" concept entirely**. Restaurants are now classified purely by their menu items' `food_category`. The Restaurants page filter chips are built dynamically from menu items.
- **Backend**: `RestaurantIn.category` is now optional (`Optional[str] = ""`). Existing restaurants with a category are unaffected (field still stored but unused in UI).
- **Frontend**: removed Food Category select from the Seller "New business" modal; `RestaurantCard` no longer shows the category badge nor links to category-filtered pages; `onEdit` no longer carries the `category` field.
- **Root-cause fix for "Cannot destructure property 'basename' of useContext(...) as it is null" crash**: the Seller Dashboard modal referenced `RESTAURANT_CATEGORIES` which was never declared, throwing a `ReferenceError`. That error bubbled up to `ErrorBoundary` (rendered above `<BrowserRouter>`), whose fallback used a `<Link>` — requiring Router context that didn't exist. `ErrorBoundary` now uses a plain `<a href="/">` so any future unhandled error degrades gracefully instead of cascading into a Router error. Smoke-tested: opening the modal and clicking "Restaurant" no longer crashes.

### Iter 6.3 (Feb 2026) — Restaurant categories unified as single source of truth (DB)
- Added `GET /api/menu-items` (filterable by `food_category`, `restaurant_id`, paginated) so frontend can derive which restaurants/menu items use which categories.
- Removed every hardcoded restaurant-category fallback in `SellerDashboard.jsx` (`"Fast Food"`, `"Fried Chicken"`). Defaults are now `Object.keys(restaurantCategoriesMap)[0] || ""`.
- `Restaurants.jsx` chips show **"All" + ALL admin-defined restaurant categories** from `/categories/tree?group=restaurant`. Categories are NOT hidden when empty (per user spec) — instead a clicked-but-empty category renders a "No restaurants in this category" state.
- `CategoriesNavMenu.jsx` Header mega-menu Restaurant tab also renders all admin categories.
- Restaurant filtering on click: `restaurants.filter(r => menuItems.some(m => m.restaurant_id === r.id && m.food_category === selected))`.
- Auto-sync: admin `POST/PUT/DELETE /api/admin/categories` already calls `cache_invalidate("cat:")`, so any new admin category (e.g., adding "BBQ") appears on next page mount without redeploy.

### Iter 6.8 (Feb 2026) — Trending UI + Customer Order-Updates banner
- **Trending Restaurants UI**: new `TrendingRestaurants.jsx` component fetches `/trending/restaurants?limit=6`, auto-hides when fewer than 2 entries. Mounted on Home (above Food & Restaurants) and on /restaurants (only when no category filter is active). Each card carries a `#1 ★ 9` rank badge with `trending_score` (clicks + 2× orders).
- **Customer "Order updates" banner** on `/orders` for restaurant orders:
  - 🟡 Warning when `status === 'cancel_requested'` — shows previous status + restaurant's reason.
  - 🔴 Error when `cancel_approved` / `cancelled` — confirms the order is cancelled and customer wasn't charged.
  - 🟢 Success when `cancel_outcome === 'rejected'` — shows status restored to previous, optional admin note.
- **Backend**: `admin_approve_cancel` / `admin_reject_cancel` now stamp `cancel_outcome: "approved" | "rejected"` so the frontend can detect rejection cleanly (replaces the fragile heuristic).
- **Bug fix**: latent `ReferenceError: s.text` in `Orders.jsx` (a marketplace-only variable was referenced inside the restaurant branch) — replaced with hardcoded `text-white` since restaurant status pills already specify their own bg colour.

### Iter 6.7 (Feb 2026) — Global search + cancellation modal polish
- **Global search** in Header (desktop + mobile menu): debounced typeahead against new `GET /api/search?q=…&limit=5` endpoint.
  - Backend: case-insensitive regex match on `name`/`description` across restaurants, shops and products. Excludes soft-deleted/hidden/inactive rows. Short-circuits to empty arrays for queries < 2 chars.
  - Frontend: `GlobalSearch.jsx` renders results grouped by type with icons; click navigates to `/product/:id`, `/shop/:id`, or `/restaurants?focus=:id`.
  - `RestaurantCard` now accepts `initialOpen` so the Restaurants page auto-opens the focused restaurant's modal when `?focus=<id>` is present.
- **Cancellation reason modal** in KitchenDashboard: replaced the `window.prompt` flow with a proper modal (`cancel-modal`) — textarea with 500-char counter, warning panel showing current status, "Keep order" / "Send to admin" buttons, disabled-while-submitting state. Eliminates the bug where pressing Esc silently lost the reason.
- **Bug-fix in same iteration**: `loadOrders` now re-syncs `selectedOrder` from the freshly-fetched list so the detail panel reflects the new status (Accept → Cancel-Pending) without requiring a manual re-click. Removed the post-submit `setSelectedOrder(null)` so the pending banner appears immediately.

### Iter 6.6 (Feb 2026) — Advanced restaurant features (P1 batch)
- **Open/Close toggle (Kitchen Dashboard)**: `restaurant-open-toggle` button in the KitchenDashboard header flips `is_open` via the existing `PUT /api/restaurants/{id}/toggle-open`. `POST /api/restaurant-orders` now returns HTTP 400 *"Restaurant is currently closed…"* when `is_open=false`, blocking customer ordering. Toast confirms the state change on the seller side.
- **Order Cancellation with admin approval**:
  - Extended `OrderStatusUpdate.Literal` to include `cancel_requested`, `cancel_approved`, `cancel_rejected`.
  - New seller endpoint: `POST /api/restaurant-orders/{id}/request-cancel` (body `{reason}`). Only allowed when current status ∈ {accepted, cooking, ready}; stores `previous_status` + `cancel_reason` + `cancel_requested_at`; notifies customer **and** seller.
  - Seller is **blocked** from setting `cancelled/cancel_approved/cancel_rejected` via the normal status update (HTTP 403) — must go through the admin flow.
  - Admin endpoints: `GET /api/admin/cancel-requests`, `POST /api/admin/cancel-requests/{id}/approve` (→ `cancel_approved`, notifies both parties), `POST /api/admin/cancel-requests/{id}/reject` with `{admin_note}` (→ reverts to `previous_status`, notifies customer per user requirement).
  - KitchenDashboard: `request-cancel-btn` shown when status ∈ {accepted, cooking, ready}; `cancel-pending-banner` replaces actions while awaiting admin review; stat cards now lazily render cancellation buckets only when count>0.
  - AdminDashboard: new `cancellations` tab with `approve-cancel-{id}` / `reject-cancel-{id}` rows.
- **Commission Invoices for completed restaurant orders** — *separate* weekly table per user choice:
  - New collection `db.restaurant_invoices` + dedicated `_rebuild_restaurant_invoices()` that aggregates `restaurant_orders` with `status="completed"` by `(seller_id, restaurant_id, ISO-week)`. `total_sales` excludes delivery fee. `commission_rate` prefers per-restaurant override, falls back to global.
  - Auto-triggered on `PUT /api/restaurant-orders/{id}/status` → `completed`.
  - Endpoints: `GET/POST /api/admin/restaurant-invoices(/generate)`, `PUT /api/admin/restaurant-invoices/{id}/status` (whitelist `{Paid, Unpaid, Overdue}`), `GET /api/seller/restaurant-invoices`.
  - AdminDashboard Invoices tab: `invoice-kind-toggle` between `Shop invoices` (existing) and `Restaurant invoices` (new pane with regenerate + mark-paid).
  - SellerDashboard Invoices tab: matching `seller-invoice-kind-toggle`.
- **Tests**: 20/20 new pytest in `/app/backend/tests/test_iter6_features.py` pass (107 total backend tests on file).

### Iter 6.5 (Feb 2026) — Cart isolation hardening (marketplace ⇄ restaurant)
- **Bug fixed**: customers could mix marketplace/wholesale products and restaurant menu items in a single cart, breaking checkout. The previous `CartContext.addItem` only blocked across-restaurant mixing; marketplace items were always allowed to slip through.
- `CartContext.jsx` rewrite of `addItem`:
  - Computes `activeMode` from `items.length` (so a stale `cartMode` after a manual clear can't lock the user out).
  - Blocks marketplace adds when `activeMode === "restaurant"`.
  - Blocks restaurant adds when `activeMode === "marketplace"`.
  - Keeps existing cross-restaurant block.
  - All three blocks share `toast.error(..., { id: "cart-isolation" })` so rapid clicks don't stack toasts.
  - Self-heal `useEffect` resets `cartMode/restaurantId/restaurantName` to null whenever `items.length` hits 0.
- Callers updated to honor the new boolean return (`ProductCard`, `WholesaleCard`, `ProductDetail`, `Favorites`): success toasts only fire when `addItem` returned `true`. `RestaurantCard` already did this.
- Verified e2e via Playwright: marketplace-first then menu-add → blocked; restaurant-first then product-add → blocked; cart count stays at 1 in both cases.

### Iter 7 hotfix (Feb 2026) — AdminSettingsTab Dark Mode build fix
- **Bug**: `AdminSettingsTab.jsx` was unbuildable. Previous edit inserted the entire `DarkModeToggle` function body in the middle of `GlobalInvoiceFrequency`'s `<button>` JSX (between `disabled={saving}` and `className=...`), orphaning the button's closing tag → `SyntaxError: Unexpected token (1153:23)`.
- **Fix** (`AdminSettingsTab.jsx`):
  - Closed `GlobalInvoiceFrequency`'s `<button>` properly and let the component finish.
  - Moved `DarkModeToggle` out to its own top-level function after `GlobalInvoiceFrequency`.
  - Trimmed direct `document.body` style mutation; toggle now only flips `dark` class on `<html>` + persists `darkMode` in `localStorage` + honors `prefers-color-scheme` on first load. Added `data-testid` on toggle wrapper and switch.
- **Verified e2e** (Playwright, admin@ltg.com): switch click → `html.classList.contains('dark') === true`, `localStorage.darkMode === 'true'`, toast "Dark mode enabled"; second click reverses both. Build is green (only pre-existing eslint `react-hooks/exhaustive-deps` warnings remain).
- **Note**: Tailwind `dark:` variants aren't yet applied across the app — Dark Mode currently sets the class only. Wiring dark CSS variables / `dark:` utilities across components is **P2 backlog**.

### Iter 6.4 (Feb 2026) — Header dropdown navigates by category_id
- `CategoriesNavMenu.jsx`: restaurant-group links now use `/restaurants?category_id=<uuid>` instead of `/restaurants?category=<name>`. Retail/wholesale still use name-based params (separate concern).
- `Restaurants.jsx`: rewrote state to be keyed by category id. Reads `category_id` from URL first; falls back to legacy `category=name` if present. Resolves id → category name (using the live DB list) to filter menu items. Active chip syncs reliably regardless of how the URL was reached.
- Result: clicking any admin-defined category from the Header mega-menu opens `/restaurants?category_id=<id>` and the matching chip becomes active and filters correctly. Verified for Drinks (1 card), Local Food (empty state), and the newly-added admin category "test" appeared automatically.

## Backlog (P1 / P2)
- **P1** Unread message badge polling / realtime updates on Messages tab
- **P1** COD-only checkout enforcement on `/shop/:shop_id` order flow (currently only banner)
- **P1** Pagination on `GET /api/messages/seller` (currently 500-item cap)
- **P1** Rate-limit `POST /shops/{id}/messages` (anti-spam) + `Field(max_length=...)` on `ShopMessageIn`
- **P1** Switch `PUT /shops/{id}` to PATCH semantics (currently full-replace via ShopIn) so partial edits can't clobber unset fields
- **P1** Re-raise non-auth `HTTPException` in `send_shop_message` (e.g. blocked-email user shouldn't silently fall to anonymous branch)
- **P1** Drop `ProductIn.mode` in favor of `is_wholesale` exclusively (two sources of truth risk)
- **P1** Deprecate `ShopIn.kind` field (iter4 phases out shop-level retail/wholesale)
- **P1** Apply pricing tiers to cart pricing server-side at checkout (currently UI only)
- **P2** Split `server.py` (~2230 lines) into routers; split `SellerDashboard.jsx` (~1700 lines) into `pages/seller/*` (MessagesTab, ShopsTab, ProductsTab, …)
- **P2** Optimistic UI refresh on admin shop commission save
- **P2** Invoice detail page with line-item orders
- **P2** Email notifications, i18n, document upload for verification

## Test Credentials
See `/app/memory/test_credentials.md`.
