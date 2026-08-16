# Online Payments for Non–South-Sudan Sellers — Feasibility & Plan

Status: **PLAN ONLY — nothing built yet** (user: "Plan now, build later")
Date: Jun 2026

## 1. The goal (UPDATED — Jun 2026)
Scope is **Juba-only for now** (no selling outside Juba yet), but with online card payments added:
- **Juba/local items**: customer may choose **Cash-on-Delivery OR card** (card optional, COD stays the default).
- **Imported items (goods that come from OUTSIDE South Sudan)**: **card-only** — no COD allowed. These items also carry extra charges: **shipping + customs + an interest/service fee** added on top of the item price.
- Money lands with **JubaSquare first** (aggregator model); JubaSquare pays sellers out manually via bank transfer, M-Pesa, or mobile money.

> IMPORTANT nuance vs. earlier draft: the online-payment / card-only rule now keys off the **ITEM'S ORIGIN** (domestic Juba vs imported), not the seller's country. A single seller could list both local and imported items.

### Fee model — DECIDED (Jun 2026)
- **Shipping**: set/edited by the **SELLER**, charged **per item**.
- **Customs**: set by **ADMIN** as a **percentage**, and configurable **per seller location / origin** (each origin location can have its own customs %). Applied to the total item price.
- **Interest fee**: set by **ADMIN** as a **percentage** (like customs), applied to the **total item price** (sum of all items).
- **Gateway**: **Pesapal** (confirmed). Settles to the Uganda bank account (UGX).

Implication: we need a small admin-managed table of **origin locations → { customs %, interest % }**, plus a per-product `is_imported` + `origin_location` field. Order total for imported items = items subtotal + per-item shipping (seller) + customs% (admin, by origin) + interest% (admin), all card-only.

### Open questions to resolve before building (UPDATED)
1. Do shipping/customs/interest fees count as **JubaSquare revenue**, or pass through to a shipper/customs authority?
2. Payment currency shown to the customer — USD, SSP, or UGX (Pesapal settles UGX).

## 2. User's confirmed constraints
- JubaSquare business entity is **registered in South Sudan only**, but has a **bank account in Uganda**.
- Payout model chosen: **aggregator** — all money to JubaSquare, then manual seller payouts (bank / M-Pesa / mobile money).
- Build later; plan first.

## 3. Key finding: which gateway is actually possible
- **Stripe is NOT an option** with the current setup. Stripe requires a company registered in a supported country (US/UK/EEA/Canada/CH). Neither South Sudan nor Uganda qualify, and a Ugandan *bank account* alone is not enough. (The `emergentintegrations` Stripe helper in the repo uses a shared test key and would NOT settle real money to a Ugandan bank — it's not usable here.)
- **East-African aggregator gateways ARE the fit** because the aggregator model needs just ONE merchant account (JubaSquare's), settling to the Uganda bank, and they natively do cards + M-Pesa + MTN/Airtel mobile money:
  - **Pesapal** — Uganda-based, very stable in East Africa, Visa/Mastercard/Amex + mobile money. Strong default choice.
  - **Flutterwave** — pan-African, great API, cards + mobile money. Fees ~1.4–3% local, ~3.8% intl cards.
  - **DPO Pay** — enterprise-grade, strong for international cards + multi-currency.
- All settle to a **UGX bank account (T+1 to T+3)**. During onboarding, confirm: intl-vs-local card fees, settlement currency, and Bank of Uganda (National Payment Systems Act) compliance docs.

> Decision needed from user: **which gateway** (recommend Pesapal or Flutterwave). This determines the exact integration playbook.

## 4. Current state of the codebase (what's already there)
- **Payments today = 100% COD.** `payment_method` only supports `"cash"` / `"mobile_money"` (both offline). No card gateway wired in backend or in `RestaurantCheckout.jsx` / `Cart.jsx`.
- **No `country` field** on shops/sellers — only Juba `area`. We cannot currently tell "seller is outside South Sudan." **This must be added.**
- **Payout side already exists** ✅ — `cod.py` + `/api/admin/payouts` (generate/list/mark-paid), `/api/seller/wallet`, `/api/seller/payouts`, `seller_payouts` collection with statuses `not_ready → ready_for_payout → pending_payout → paid`. The manual-payout half is largely done; we mainly need to record the payout *channel* (bank/M-Pesa/mobile money) + reference.
- Currency: USD/SSP toggle + per-seller `exchange_rate_ssp` already plumbed through orders/wallet.

## 5. What "make it possible" requires (build phases)

### Phase 0 — Business prerequisites (user does this, no code)
1. Open a **merchant account** with the chosen gateway (Pesapal/Flutterwave), settling to the Uganda bank.
2. Obtain API keys (public + secret) + webhook secret. These will be stored in `backend/.env`.
3. Decide platform commission % for online-paid orders (can reuse existing COD commission config).

### Phase 1 — Seller location + eligibility (backend + admin UI)
- Add `country` (and optional `city`) to Shop/Restaurant/seller model. Default existing = "South Sudan".
- Admin can set/edit a seller's country; add `online_payment_enabled` derived flag = `country != "South Sudan"`.
- Expose eligibility on public shop/product payloads so the cart knows.

### Phase 2 — Checkout: online payment option (backend + frontend)
- Cart/checkout computes: is **every** item from an online-eligible (non-SS) seller? Only then show **"Pay online (card / mobile money)"**. Mixed carts + SS-only carts stay COD. (Simplest first version: online payment only for single-seller eligible carts.)
- New backend endpoints (put in a **new `payments_routes.py`**, NOT in the 8,500-line `server.py`):
  - `POST /api/payments/checkout` — creates a gateway payment session/intent for the order, returns redirect/hosted-page URL.
  - `POST /api/payments/webhook` — gateway → us; verifies signature, marks order `payment_status = paid_online`, then runs the normal order-creation/split logic.
  - `GET /api/payments/verify/{ref}` — fallback poll for the return page.
- Order model: extend `payment_method` to include `"online_card"` / `"online_mobile_money"`; add `payment_status` states for online (`awaiting_payment`, `paid_online`, `payment_failed`, `refunded`).
- Only create the order/split as confirmed **after** the webhook confirms payment (avoid unpaid ghost orders).

### Phase 3 — Payouts for online-paid orders (reuse existing system)
- Online-paid seller earnings flow into the **existing seller wallet / payout pipeline**, but marked `funds_source = "online"` (money already with JubaSquare) vs COD (cash in the field).
- Extend payout record with **payout channel**: `bank_transfer` | `mpesa` | `mobile_money` + destination ref + optional proof. Add these fields to the seller's payout profile so admin knows where to send.
- Admin "mark paid" already exists — just capture the channel + reference on payout.

### Phase 4 — Refunds & cancellations
- Online-paid orders need a refund path (gateway refund API) when cancelled, instead of the COD "cash never collected" no-op.
- Admin refund button → calls gateway refund → sets `payment_status = refunded`.

## 6. Effort estimate (rough)
- Phase 1 (country + eligibility): small (~0.5 day).
- Phase 2 (gateway integration + checkout UI): medium — depends on gateway (~2–3 days incl. webhook + test).
- Phase 3 (payout channel fields): small (~0.5 day, reuses existing payout system).
- Phase 4 (refunds): small–medium (~1 day).

## 7. Open decisions before building
1. **Which gateway?** (recommend Pesapal or Flutterwave for Uganda + mobile money.)
2. First version scope: online payment for **single-seller eligible carts only**, or also mixed carts (harder — needs split capture)?
3. Which currency do buyers pay in for online orders (USD or UGX/SSP)? Gateway settles in UGX.
4. Commission % for online orders (same as COD, or different).

## 8. Integration note for the build session
- When building: use the `integration_expert` tool for the chosen gateway (Pesapal/Flutterwave) — do NOT hand-code the gateway. Auth (any new payment auth) also goes through `integration_expert`.
- Keep all payment endpoints in a **new `payments_routes.py`** module, mounted from `server.py`, to avoid growing the monolith.
