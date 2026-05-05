# JubaSquare — by L.T.G Enterprise

## Original Problem Statement
Multi-vendor marketplace + restaurant **demo** web app for local businesses in Juba, South Sudan. ZERO-setup showcase: pre-built shops, products, restaurants. Instant 3-button login (admin/seller/customer). Modern Shopify-like UI, light theme, mobile-first.

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async). Single-file `server.py` with auto-seeding on startup.
- **Auth**: JWT (httpOnly cookie + Bearer fallback) + bcrypt + token-version (force-logout-all). Demo accounts seeded idempotently with password `1234`.
- **Frontend**: React 19 + React Router 7 + Tailwind. Outfit (display) + Manrope (body). Sonner toasts. lucide-react icons.
- **Persistence**: localStorage cart (lazy useState init), localStorage JWT.
- **Currency**: USD + SSP everywhere. Seller per-shop rate, admin global rate fallback.

## User Personas
- **Customer**: browses retail/wholesale, filters by Juba area, builds cart, places orders, tracks status, saves favorites.
- **Seller**: manages multiple retail/wholesale shops + products + menu items, updates order status, sets exchange rate, low-stock alerts.
- **Admin**: verifies/rejects shops, blocks/unblocks emails, oversees all orders, controls platform settings (modules, maintenance, currency, areas, force-logout, login attempts).

## What's Been Implemented

### Iteration 1 (2026-02)
- Demo seeding (idempotent)
- Full auth: login/logout/me/change-password/profile (JWT cookie + Bearer)
- Shops CRUD, Products CRUD, Restaurants + menu items + open/closed
- Orders: place / customer-seller-admin views / status updates
- Per-seller exchange rate
- Admin: verify/reject shops, block/unblock emails
- Frontend pages: Home, Login, Marketplace, Restaurants, Cart, Orders, Seller Dashboard (5 tabs), Admin Dashboard (3 tabs)
- 25/25 backend pytest tests pass

### Iteration 2 (2026-02)
- **New custom logo** (shopping-cart-bridge) across header / footer / login
- **Expanded categories**: 9 retail + 6 wholesale + 4 restaurant (seeded 9 retail shops + 3 wholesale shops + 4 restaurants)
- **Wholesale module**: dedicated page with bulk pricing, min-order-quantity, supplier verification filter
- **Side items** on restaurant menu items + **menu search** inside restaurant modal
- **Mandatory phone + area** validation on order placement (backend 400 + frontend toast)
- **Admin Settings panel**: currency, modules toggle (marketplace/wholesale/restaurants), maintenance mode, login attempt limit, areas mgmt, auto-approve shops, force-logout-all (token versioning)
- **Seller Settings**: low-stock alert + threshold, auto-hide out-of-stock products, order notifications
- **Customer Settings**: default Juba area, notification prefs, **dark mode toggle** (data-theme on html)
- **Favorites system** (products / shops / restaurants) with heart icon on product cards + dedicated /favorites page
- **Brute-force protection** (5 failed attempts → 15-min lockout per IP+email; admin-configurable)
- 43/43 backend pytest tests pass (25 regression + 18 new)

## Backlog (P1 / P2)
- **P1** Document upload for shop verification (needs object storage)
- **P1** Per-shop order grouping for sellers + order detail page
- **P2** Image upload for products / shops (currently URL only)
- **P2** Restaurant open/closed scheduler with auto-toggle
- **P2** Email notifications (Resend / SendGrid)
- **P2** Split server.py into routers (auth/admin/shops/products/etc.) — currently 1176 lines
- **P2** Server-side price validation against DB on /api/orders
- **P2** i18n / language switcher

## Test Credentials
See `/app/memory/test_credentials.md`.
