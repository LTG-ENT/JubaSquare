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
