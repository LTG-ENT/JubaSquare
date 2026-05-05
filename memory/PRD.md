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

## Backlog (P1 / P2)
- **P1** Drop `ProductIn.mode` in favor of `is_wholesale` exclusively (two sources of truth risk)
- **P1** Deprecate `ShopIn.kind` field (iter4 phases out shop-level retail/wholesale)
- **P1** Apply pricing tiers to cart pricing server-side at checkout (currently UI only)
- **P2** Split `server.py` (1383 lines) into routers; split `SellerDashboard.jsx` (923 lines) into `pages/seller/*`
- **P2** Optimistic UI refresh on admin shop commission save
- **P2** Invoice detail page with line-item orders
- **P2** Email notifications, i18n, document upload for verification

## Test Credentials
See `/app/memory/test_credentials.md`.
