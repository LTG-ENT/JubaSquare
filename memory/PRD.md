# JubaSquare — by L.T.G Enterprise

## Original Problem Statement
Multi-vendor marketplace + restaurant **demo** web app for local businesses in Juba, South Sudan. ZERO-setup showcase: pre-built shops, products, restaurants. Instant 3-button login (admin/seller/customer). Modern Shopify-like UI, light theme, mobile-first.

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async). Single-file `server.py` with auto-seeding on startup.
- **Auth**: JWT (httpOnly cookie + Bearer fallback) + bcrypt. 3 demo accounts seeded idempotently with password `1234`.
- **Frontend**: React 19 + React Router 7 + Tailwind. Outfit (display) + Manrope (body). Sonner toasts. lucide-react icons.
- **Persistence**: localStorage cart (lazy useState init), localStorage JWT.
- **Currency**: every price shown as USD + SSP. Seller controls exchange rate.

## User Personas
- **Customer**: browses, filters by Juba area, builds cart, places orders, tracks status.
- **Seller**: manages multiple shops + products, updates order status, sets exchange rate.
- **Admin**: verifies/rejects shops, blocks/unblocks emails, oversees all orders.

## Core Static Requirements
- 3 demo accounts only (no signup): admin/seller/customer @demo.com, password `1234`.
- 5 shops × 2 products + 4 restaurants × 2 menu items auto-seeded on startup.
- Juba areas: Munuki, Jebel, Gudele, Konyo Konyo, Hai Cinema, Nyakuron, Atlabara.
- Order statuses: Pending → In Progress → Delivered.
- Shop verification: Pending / Verified / Rejected (Verified shown first).
- Branding: "JubaSquare by L.T.G Enterprise" in header, footer, login.

## What's Been Implemented (Iteration 1 — 2026-02)
- ✅ Demo seeding (idempotent users, shops, products, restaurants, menu, sample order)
- ✅ Full auth: login/logout/me/change-password/profile, JWT cookie + Bearer
- ✅ Shops CRUD (seller scoped, admin override) with verification flow
- ✅ Products CRUD with category/area/shop filtering
- ✅ Restaurants + menu items + open/closed toggle
- ✅ Orders: place, customer/seller/admin views, status updates
- ✅ Per-seller exchange rate (USD ↔ SSP)
- ✅ Admin: verify/reject shops, block/unblock emails (demo accounts protected)
- ✅ Frontend pages: Home, Login, Marketplace, Restaurants, Cart, Orders, Seller Dashboard (5 tabs), Admin Dashboard (3 tabs)
- ✅ Cart persistence (lazy useState init — fixes StrictMode race)
- ✅ Backend regression suite: 25/25 pytest tests pass

## Backlog (P1 / P2)
- **P1** Order detail page + per-shop order grouping for sellers
- **P1** Wholesale module (mentioned briefly in spec)
- **P2** Restaurant Open/Closed scheduler + auto-toggle by hours
- **P2** Search across products + restaurants on the home page
- **P2** Image upload (currently URL only) — would require object storage
- **P2** Migrate FastAPI startup events to lifespan API
- **P2** Add brute-force lockout on login

## Test Credentials
See `/app/memory/test_credentials.md`.
