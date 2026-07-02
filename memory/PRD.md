# JubaSquare — Product Requirements (PRD)

Branch: `with-odoo-v2`

## Product intent
A multilingual (English/Arabic RTL) Juba-focused marketplace connecting shops, restaurants, wholesale suppliers, drivers and customers. Odoo-integrated. Runs on React + FastAPI + MongoDB Atlas, deployed via Emergent.

## Core personas
- **Customer**: browses, orders, pays cash-on-delivery or wallet, tracks deliveries.
- **Seller**: manages shops/restaurants, products/menu items, delivery pricing, orders, payouts.
- **Driver**: accepts assignments, delivers COD orders, hands cash to admin.
- **Admin**: verifies shops/restaurants, manages global settings, commissions, payouts, delivery rules.

## Established feature areas
- Auth (JWT-based email + password + email verification), Odoo integration, wallet, Web Push/PWA, Notifications.
- Cash-on-Delivery flow with per-seller order splits (see `/app/backend/cod.py`).
- Hybrid Delivery: Admin OR Seller manages delivery per-shop / per-restaurant. Modes: free / fixed / per_area.
- Emergent Object Storage for uploads (survives redeploys).
- Cascade deletes on user removal.
- Multilingual UI + Arabic RTL support.

## Completed (Feb 2026, this fork)
- ✅ Verified "Mirror Shops" restaurant delivery logic (backend `_calculate_delivery_fee` supports restaurant-level free/fixed/per_area + `delivery_managed_by` override). All 4 delivery scenarios pass (fixed 3.5, per_area x2 rates, free, admin-fallback → default).
- ✅ New endpoint `GET /api/restaurants/mine` — sellers see own restaurants regardless of verification.
- ✅ New page `SellerRestaurantEdit.jsx` (route `/seller/restaurant/:restaurant_id/edit`) — mirror of `SellerShopEdit`, letting sellers configure delivery model for restaurants (free/fixed/per_area).
- ✅ Shop/Restaurant customer-visibility gate:
  - Only **Verified** shops/restaurants appear in `/api/shops`, `/api/restaurants`, `/api/products`, `/api/menu-items`, `/api/restaurants/{id}/menu`.
  - Anonymous access to unverified shop/restaurant/product detail returns 404.
  - Owners (seller_id match) and admins bypass the gate for their own resources.
  - Admin list endpoints (`/api/shops`, `/api/restaurants`) bypass the gate when authenticated with role=admin.
- ✅ All 24/24 backend regression tests pass (`/app/test_reports/iteration_14.json`).

## P1 Backlog
- Product reviews with photos (extend review models + photo compression on upload).
- Live Driver Map (real-time geolocation reporting every 10s, Leaflet map on tracking page, ETA calc).

## P2 / Refactor
- Break `/app/backend/server.py` (now ~6750 lines) into routers (`shops.py`, `restaurants.py`, `products.py`, `admin.py`, etc.).
- Deprecate legacy `delivery_pricing` on RestaurantIn now that mirror-shops mode is authoritative.
- Consider caching admin-flag per-request for `list_restaurants` / `list_shops` (currently invokes `get_current_user` per anon call).
- `list_menu_items` scans `MAX_PAGE_LIMIT` restaurants each call; move to aggregation/cache.

## Key files
- `/app/backend/server.py` — main API router.
- `/app/backend/cod.py` — cash-on-delivery + delivery fee calculator.
- `/app/backend/storage.py` — Emergent Object Storage.
- `/app/backend/email_service.py` — Resend email integration.
- `/app/frontend/src/pages/SellerShopEdit.jsx` — shop editor (with delivery).
- `/app/frontend/src/pages/SellerRestaurantEdit.jsx` — NEW restaurant editor (with delivery mirror).
- `/app/frontend/src/pages/SellerDashboard.jsx` — seller landing; now uses `/restaurants/mine`.
- `/app/frontend/src/pages/AdminDashboard.jsx` — admin console with per-shop / per-restaurant delivery override toggle.

## Critical guardrails (do not break)
1. All upload URLs must be relative (`/api/uploads/...`).
2. Never use `<input type="url">` for image URL fields; use `type="text"` + `noValidate` on the form.
3. `_calculate_delivery_fee` is the single source of truth for delivery pricing — always trace via `cod.py` when touching delivery logic.
4. Preserve `.git` / `.emergent` folders. Only edit `.env` when strictly necessary.

## 3rd-party integrations
- MongoDB Atlas, Resend, Stripe, Emergent Object Storage (via EMERGENT_LLM_KEY).

## Test credentials
See `/app/memory/test_credentials.md` — admin only. Sellers/customers sign up fresh in production.
