# JubaSquare — by L.T.G Enterprise

## Original Problem Statement
Multi-vendor marketplace + restaurant **demo** web app for local businesses in Juba, South Sudan. ZERO-setup showcase with 3-button instant login.

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async). Single-file `server.py` (~1346 lines) with auto-seeding.
- **Auth**: JWT (httpOnly cookie + Bearer fallback) + bcrypt + token-version (force-logout-all). Demo accounts seeded idempotently with password `1234`.
- **Frontend**: React 19 + React Router 7 + Tailwind. Outfit (display) + Manrope (body). Sonner toasts. lucide-react icons.
- **Persistence**: localStorage cart (lazy useState init), localStorage JWT, localStorage dark-mode flag.
- **Currency**: USD + SSP everywhere. Seller per-shop rate, admin global rate fallback.

## User Personas
- **Customer**: browses retail/wholesale, filters by Juba area, builds cart, places orders, tracks status, saves favorites.
- **Seller**: manages shops + products + menu items (3-mode toggle), updates order status, views weekly invoices with amount owed, sets exchange rate, low-stock alerts.
- **Admin**: verifies/rejects shops, blocks/unblocks emails, oversees all orders, controls platform settings (modules, maintenance, currency, areas, force-logout, login attempts, commission rate), manages invoices (filter, mark paid/unpaid, regenerate).

## What's Been Implemented

### Iteration 1 (2026-02)
- Demo seeding, full auth (login/logout/me/change-password/profile), shops/products/restaurants/menu CRUD, orders + status, per-seller exchange rate, admin verify/block. 25/25 tests pass.

### Iteration 2 (2026-02)
- Custom logo swap (shopping-cart + Juba bridge) across header/footer/login
- Expanded categories: 9 retail + 6 wholesale + 4 restaurant (seeded 9+3+4 shops)
- Wholesale module with bulk pricing, min-order-qty, verified-supplier filter
- Side items on menu items + in-modal menu search
- Mandatory phone+area on orders
- Admin Settings (currency, modules toggle, maintenance mode, login attempt limit, areas CRUD, auto-approve, force-logout-all, security toggles)
- Seller Settings (low-stock alert, auto-hide out-of-stock, order notifications)
- Customer Settings (default area, notif prefs, dark mode)
- Favorites system for products / shops / restaurants
- Brute-force protection (5 attempts → 15min lockout)
- 43/43 tests pass (25+18)

### Iteration 3 (2026-02)
- **Admin Invoices module**: weekly auto-generated invoices per shop per week, stat cards (count/sales/commission/unpaid), filter (All/Paid/Unpaid), mark-paid/unpaid, detail modal, regenerate button, configurable commission rate (default 10%)
- **Seller Invoices tab**: own invoices with Amount Owed column
- **Product 3-mode toggle**: Marketplace / Restaurant / Wholesale with distinct forms
  - Restaurant mode → creates menu item with food subcategory + side items editor
  - Wholesale mode → includes min_order_qty, bulk price, pricing tiers editor
  - Marketplace mode → normal retail product
- **16 food subcategories** (Fried Chicken, Burgers, Shawarma, Fries, etc.) exposed via `/api/meta/categories`
- **Pricing tiers** on wholesale products (list of {min_qty, price_usd})
- Mode badges (MARKETPLACE/WHOLESALE/RESTAURANT) on seller products table
- 58/58 tests pass (25+18+15)

## Backlog (P1 / P2)
- **P1** Apply wholesale pricing tiers in cart checkout (currently UI only)
- **P1** Server-side price validation against DB on /api/orders (anti-tampering)
- **P1** Commission rate [0,1] bound validator + % representation in admin UI
- **P1** Document upload for shop verification (needs object storage)
- **P2** Split `server.py` (1346 lines) into routers
- **P2** Split `SellerDashboard.jsx` (854 lines) into pages/seller/*.jsx
- **P2** Invoice detail page showing line-item orders (currently summary only)
- **P2** Email notifications (Resend/SendGrid)
- **P2** i18n / language switcher

## Test Credentials
See `/app/memory/test_credentials.md`.
