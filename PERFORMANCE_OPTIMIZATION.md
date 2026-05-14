# Performance Optimization - Auto-Refresh Pages

## Summary

Optimized all pages with auto-refresh/polling functionality to improve performance, reduce unnecessary API calls, and preserve battery life on mobile devices.

## Key Improvements

### 1. **Visibility-Based Polling**
- Automatically pauses polling when browser tab/window is hidden
- Resumes immediately when user returns to the page
- **Benefit**: Saves bandwidth and CPU when users switch tabs or minimize browser

### 2. **Error Handling with Exponential Backoff**
- Implements exponential backoff on API errors
- Starts at normal interval (e.g., 15s)
- Doubles the interval on each consecutive error (15s → 30s → 60s → max 60s)
- Automatically resets to normal interval on success
- **Benefit**: Reduces server load during issues and prevents error spam

### 3. **Optimized Hook: `useOptimizedPolling`**
Created a reusable custom hook with:
- Automatic cleanup on unmount
- Configurable intervals per page
- Enable/disable toggle
- Manual trigger function
- **Location**: `/app/frontend/src/hooks/useOptimizedPolling.js`

## Pages Updated

### 1. **Customer Orders Page** (`/app/frontend/src/pages/Orders.jsx`)
- **Before**: Fixed 15s polling, always running
- **After**: Smart polling that pauses when hidden
- **Fetches**: Marketplace orders + Restaurant orders in parallel

### 2. **Driver Dashboard** (`/app/frontend/src/pages/DriverDashboard.jsx`)
- **Before**: Three separate intervals (assignments, requests, cash)
- **After**: Single optimized polling, all fetched in parallel
- **Fetches**: Assignments + Delivery requests + Cash summary

### 3. **Kitchen Dashboard** (`/app/frontend/src/pages/KitchenDashboard.jsx`)
- **Before**: Fixed 15s polling for orders + history
- **After**: Smart polling with visibility detection
- **Fetches**: Active orders + History in parallel

### 4. **Notification Bell** (`/app/frontend/src/components/NotificationBell.jsx`)
- **Before**: 30s polling always running
- **After**: Pauses when tab hidden, only polls when user present
- **Fetches**: Notifications

### 5. **Seller Wallet Tab** (`/app/frontend/src/components/SellerWalletTab.jsx`)
- **Before**: 12s fixed polling
- **After**: Smart 12s polling with visibility detection
- **Fetches**: Wallet + Splits + Restaurant orders + Payouts in parallel

### 6. **Admin Dashboard** (`/app/frontend/src/pages/AdminDashboard.jsx`)
- **Before**: 30s polling with manual cancellation flag
- **After**: Clean optimized polling
- **Fetches**: Admin alerts for tab badges

## Performance Impact

### Before Optimization:
- **Orders page (hidden tab)**: ~240 API calls per hour (wasted)
- **Driver dashboard (hidden)**: ~720 API calls per hour (3 endpoints × 240)
- **Total wasted calls**: ~1000+ API calls per hour per hidden tab

### After Optimization:
- **Hidden tabs**: 0 API calls
- **Visible tabs**: Normal polling continues
- **Error scenarios**: Automatic backoff reduces server load

## Example Usage of `useOptimizedPolling`

```javascript
import { useOptimizedPolling } from "@/hooks/useOptimizedPolling";

function MyComponent() {
  const refreshData = useCallback(async () => {
    const response = await api.get("/my-data");
    setData(response.data);
  }, []);

  // Optimized polling with 15s interval
  useOptimizedPolling(refreshData, 15000, {
    runOnMount: true,        // Run immediately on mount
    enabled: isAuthenticated // Only poll when logged in
  });

  return <div>...</div>;
}
```

## Technical Details

### Visibility Detection
Uses `document.visibilitychange` event:
- `document.hidden === true` → Pause polling
- `document.hidden === false` → Resume + immediate refresh

### Error Backoff Formula
```
newInterval = min(baseInterval × 2^errorCount, maxBackoff)
```
- Base: 15s
- After 1 error: 30s
- After 2 errors: 60s (stays at max)
- On success: Reset to 15s

## Migration Notes

All optimizations are **backward compatible**:
- Same functionality from user perspective
- No breaking changes
- Simply more efficient under the hood

## Testing Recommendations

1. **Visibility test**: 
   - Open page → switch tabs → wait → return
   - Verify immediate data refresh on return

2. **Error handling**:
   - Simulate API failures
   - Check console for backoff messages
   - Verify automatic recovery

3. **Battery/CPU**:
   - Leave tab hidden for extended period
   - Monitor network activity (should be zero)

## Future Improvements

Potential additions:
1. WebSocket support for real-time updates (eliminate polling)
2. Smart polling based on user activity (slower when idle)
3. Service Worker for background sync
4. Shared polling across multiple components

---

**Date**: May 14, 2026
**Status**: ✅ Implemented and Deployed
