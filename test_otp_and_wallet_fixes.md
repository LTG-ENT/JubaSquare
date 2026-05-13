# Test Plan: Customer OTP Visibility & Seller Wallet Auto-Refresh

## Test 1: Customer Delivery OTP Visibility (Marketplace)

**Setup:**
1. Create/login as customer
2. Create/login as seller (with shop and products)
3. Create/login as admin
4. Create/login as driver

**Test Steps:**
1. Customer places marketplace order with COD payment
2. Admin assigns driver to the split
3. Seller accepts → preparing → ready_for_pickup
4. Driver picks up (with seller_pickup_otp)
5. Seller marks handed_to_driver
6. **TEST**: Driver marks out_for_delivery
   - **EXPECTED**: Customer sees delivery OTP on Orders page for that split
   - **EXPECTED**: OTP shows shop name and the 4-digit code
   - **EXPECTED**: Message says "Give this code only to the driver when you receive items from this shop"
7. Driver delivers (with customer_delivery_otp)
   - **EXPECTED**: OTP disappears from customer Orders page after delivered

**What to verify:**
- ✅ OTP NOT shown when split is: pending, assigned, picked_up, handed_to_driver
- ✅ OTP IS shown when split is: out_for_delivery
- ✅ OTP NOT shown when split is: delivered, cancelled, failed, returned
- ✅ Customer NEVER sees seller_pickup_otp or return_otp
- ✅ Multiple splits show multiple OTP boxes (one per shop)

## Test 2: Customer Delivery OTP Visibility (Restaurant)

**Setup:**
1. Create/login as customer
2. Create restaurant order with COD payment
3. Admin assigns driver

**Test Steps:**
1. Restaurant accepts → cooking → ready
2. Driver picks up
3. Restaurant marks handed_to_driver
4. **TEST**: Driver marks out_for_delivery
   - **EXPECTED**: Customer sees delivery OTP on Orders page
   - **EXPECTED**: OTP shows restaurant name and 4-digit code
5. Driver delivers
   - **EXPECTED**: OTP disappears after delivered

## Test 3: Seller Wallet Auto-Refresh

**Setup:**
1. Login as seller
2. Have at least one active marketplace or restaurant order assigned to driver
3. Open Seller Dashboard → Wallet tab → Active Orders sub-tab

**Test Steps:**
1. **Without refreshing the page**, have driver/admin update order status (e.g., driver marks delivered)
2. Wait 12-15 seconds
   - **EXPECTED**: Active Orders list updates automatically
   - **EXPECTED**: No full-page loading spinner (silent refresh)
   - **EXPECTED**: Wallet summary stats update (e.g., cash_with_driver → ready_for_payout)
3. **Without refreshing the page**, have admin confirm cash received
4. Wait 12-15 seconds
   - **EXPECTED**: Wallet shows updated payout status
5. Seller performs action (e.g., marks preparing)
   - **EXPECTED**: Data refreshes immediately (no need to wait for polling)

**What to verify:**
- ✅ Polling runs every 10-15 seconds
- ✅ Refresh is silent (no loading spinner after initial load)
- ✅ Uses seller-safe endpoints only (NOT admin endpoints)
- ✅ Immediate refresh after seller actions
- ✅ Detail modal updates from refreshed seller data (not admin endpoints)

## Test 4: OrderChatButton Removed

**Test Steps:**
1. Login as customer
2. Go to Orders page
3. Find a marketplace order
   - **EXPECTED**: No "Chat" or "Contact Seller" button visible
   - **EXPECTED**: Only Cancel and Total shown

## Test 5: No Regressions

**Quick checks:**
- Customer can still place orders
- Customer can still cancel orders (before ready_for_pickup)
- Seller can still see and manage orders in Wallet
- Driver can still complete delivery flow
- Reviews still work
- Payment still works

---

## Backend Endpoints Used

**Customer (for OTP):**
- GET /customer/orders/{order_id}/splits - Returns splits with customer_delivery_otp
- GET /restaurant-orders - Returns restaurant orders with customer_delivery_otp

**Seller (for wallet):**
- GET /seller/wallet
- GET /seller/splits
- GET /seller/restaurant-orders-cod
- GET /seller/payouts
- POST /seller/splits/{id}/accept|preparing|ready-for-pickup|handed-to-driver
- POST /seller/restaurant-orders/{id}/accept|preparing|ready-for-pickup|handed-to-driver

**NOT USED from seller views:**
- ❌ GET /admin/order-splits (removed)
- ❌ GET /admin/restaurant-orders-cod (removed)

---

## Success Criteria

✅ Customer sees OTP ONLY when delivery_status = "out_for_delivery"  
✅ Customer NEVER sees seller_pickup_otp or return_otp  
✅ OTP hides after delivered/cancelled/failed/returned  
✅ Marketplace orders show OTP per split (with shop name)  
✅ Restaurant orders show OTP with restaurant name  
✅ Seller Wallet auto-refreshes every 10-15 seconds  
✅ No admin endpoints called from SellerWalletTab  
✅ OrderChatButton removed from Orders.jsx  
✅ No regressions in existing flows
