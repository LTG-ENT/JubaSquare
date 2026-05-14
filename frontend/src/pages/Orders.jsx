import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api, { formatUSD, formatPrice, extractErrorMessage } from "@/lib/api";
import { useCart } from "@/context/CartContext";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import OrderStatusTimeline from "@/components/OrderStatusTimeline";
import { Package, MapPin, Phone, Truck, CheckCircle2, Clock, Star, X, XCircle, KeyRound } from "lucide-react";
import { toast } from "sonner";

const STATUS_STYLES = {
  Pending: { bg: "bg-[#E9C46A]", text: "text-[#1A1A1A]", icon: Clock },
  "In Progress": { bg: "bg-[#2A9D8F]", text: "text-white", icon: Truck },
  Delivered: { bg: "bg-[#2D6A4F]", text: "text-white", icon: CheckCircle2 },
  Cancelled: { bg: "bg-[#D90429]", text: "text-white", icon: XCircle },
};

// Marketplace parent statuses that may still be cancellable by the customer.
// (Backend validates each split individually based on seller_preparation_status.)
const CUSTOMER_CANCELLABLE_MP_STATUSES = new Set(["Pending"]);

// Restaurant order statuses where the customer can still cancel.
const CUSTOMER_CANCELLABLE_REST_STATUSES = new Set(["pending", "accepted", "cooking"]);

function CancelOrderModal({ order, kind, onClose, onCancelled }) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const url =
        kind === "restaurant"
          ? `/customer/restaurant-orders/${order.id}/cancel`
          : `/customer/orders/${order.id}/cancel`;
      const { data } = await api.post(url, { reason: reason.trim() });

      // Marketplace returns { order_id, results: [{ok, error}] } per split.
      if (kind === "marketplace" && data?.results) {
        const okCount = data.results.filter((r) => r.ok).length;
        const failCount = data.results.length - okCount;
        if (okCount === 0) {
          const firstErr = data.results.find((r) => !r.ok)?.error || "Could not cancel any item";
          toast.error(firstErr);
        } else if (failCount > 0) {
          toast.warning(`Cancelled ${okCount}/${data.results.length} shop(s). Some items were already past pickup.`);
        } else {
          toast.success("Order cancelled");
        }
      } else {
        toast.success("Order cancelled");
      }
      onCancelled(order.id);
      onClose();
    } catch (err) {
      toast.error(extractErrorMessage(err, "Failed to cancel order"));
    } finally {
      setSubmitting(false);
    }
  };

  const shortId = (order.id || "").slice(0, 8).toUpperCase();

  return (
    <div className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose}>
      <div
        data-testid="cancel-order-modal"
        className="bg-white rounded-t-3xl sm:rounded-3xl w-full max-w-md max-h-[90vh] overflow-y-auto p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-[10px] uppercase tracking-[0.18em] text-[#5C5C5C] font-bold">Cancel order</p>
            <h3 className="font-display font-bold text-xl text-[#1A1A1A] mt-1">Order #{shortId}</h3>
            <p className="text-xs text-[#5C5C5C] mt-1">
              You can only cancel before the {kind === "restaurant" ? "restaurant" : "seller"} marks it as ready for pickup.
            </p>
          </div>
          <button onClick={onClose} data-testid="close-cancel-modal" className="p-2 hover:bg-[#F2EBE5] rounded-full">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-[#5C5C5C] block mb-1">Reason (optional)</label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              data-testid="cancel-reason-input"
              maxLength={500}
              rows={3}
              placeholder="Let the seller know why you're cancelling..."
              className="w-full bg-[#F8F5F0] border border-[#E2E2D9] rounded-2xl px-4 py-3 text-sm focus:outline-none focus:border-[#C84B31]"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              data-testid="keep-order-btn"
              className="text-sm font-semibold text-[#5C5C5C] px-4 py-2.5 rounded-full hover:bg-[#F2EBE5]"
            >
              Keep order
            </button>
            <button
              type="submit"
              disabled={submitting}
              data-testid="confirm-cancel-order-btn"
              className="bg-[#D90429] hover:bg-[#A8001E] disabled:bg-[#A3A39E] text-white text-sm font-semibold px-5 py-2.5 rounded-full"
            >
              {submitting ? "Cancelling..." : "Cancel order"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function StarRating({ value, onChange, testId = "star-rating" }) {
  return (
    <div className="flex items-center gap-1" data-testid={testId}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(n)}
          data-testid={`${testId}-${n}`}
          className="p-1 transition-transform hover:scale-110"
          aria-label={`${n} stars`}
        >
          <Star className={`w-7 h-7 ${n <= value ? "fill-[#E9C46A] text-[#E9C46A]" : "text-[#A3A39E]"}`} />
        </button>
      ))}
    </div>
  );
}

function ReviewModal({ item, onClose, onSubmitted }) {
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post(`/products/${item.item_id}/reviews`, { rating, comment });
      toast.success("Thanks for your review!");
      onSubmitted(item.item_id);
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to submit review");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose}>
      <div className="bg-white rounded-t-3xl sm:rounded-3xl w-full max-w-md max-h-[90vh] overflow-y-auto p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-[10px] uppercase tracking-[0.18em] text-[#5C5C5C] font-bold">Leave a review</p>
            <h3 className="font-display font-bold text-xl text-[#1A1A1A] mt-1">{item.name}</h3>
          </div>
          <button onClick={onClose} data-testid="close-review-modal" className="p-2 hover:bg-[#F2EBE5] rounded-full"><X className="w-4 h-4" /></button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div className="flex items-center gap-3">
            <img src={item.image_url} alt={item.name} className="w-16 h-16 rounded-xl object-cover border border-[#E2E2D9]" />
            <div className="text-sm text-[#5C5C5C]">How was the product?</div>
          </div>

          <div>
            <label className="text-xs font-semibold text-[#5C5C5C] block mb-1">Rating</label>
            <StarRating value={rating} onChange={setRating} testId="review-rating" />
          </div>

          <div>
            <label className="text-xs font-semibold text-[#5C5C5C] block mb-1">Comment (optional)</label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              data-testid="review-comment-input"
              maxLength={1000}
              rows={4}
              placeholder="Share what you liked or what could be better..."
              className="w-full bg-[#F8F5F0] border border-[#E2E2D9] rounded-2xl px-4 py-3 text-sm focus:outline-none focus:border-[#C84B31]"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="text-sm font-semibold text-[#5C5C5C] px-4 py-2.5 rounded-full hover:bg-[#F2EBE5]">Cancel</button>
            <button
              type="submit"
              disabled={submitting}
              data-testid="submit-review-btn"
              className="bg-[#C84B31] hover:bg-[#A83A23] disabled:bg-[#A3A39E] text-white text-sm font-semibold px-5 py-2.5 rounded-full"
            >
              {submitting ? "Submitting..." : "Post review"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function RestaurantReviewModal({ order, onClose, onSubmitted }) {
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const { data } = await api.post(`/reviews`, {
        restaurant_id: order.restaurant_id,
        order_id: order.id,
        rating,
        comment,
      });
      toast.success("Thanks for your review!");
      onSubmitted(order.id, data);
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to submit review");
    } finally {
      setSubmitting(false);
    }
  };
  const itemsPreview = (order.items || []).slice(0, 3).map((it) => `${it.quantity}× ${it.name}`).join(", ");

  return (
    <div className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose}>
      <div className="bg-white rounded-t-3xl sm:rounded-3xl w-full max-w-md max-h-[90vh] overflow-y-auto p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-[10px] uppercase tracking-[0.18em] text-[#5C5C5C] font-bold">Leave a review</p>
            <h3 className="font-display font-bold text-xl text-[#1A1A1A] mt-1">{order.restaurant_name || "Restaurant"}</h3>
            <p className="text-xs text-[#5C5C5C] mt-1">Order #{(order.id || "").slice(0, 8).toUpperCase()}</p>
          </div>
          <button onClick={onClose} data-testid="close-restaurant-review-modal" className="p-2 hover:bg-[#F2EBE5] rounded-full"><X className="w-4 h-4" /></button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          {itemsPreview && (
            <div className="bg-[#F8F5F0] border border-[#E2E2D9] rounded-2xl px-4 py-3">
              <p className="text-[10px] uppercase tracking-[0.18em] text-[#5C5C5C] font-bold mb-1">You ordered</p>
              <p className="text-sm text-[#1A1A1A]">{itemsPreview}{(order.items || []).length > 3 ? ` +${order.items.length - 3} more` : ""}</p>
            </div>
          )}

          <div>
            <label className="text-xs font-semibold text-[#5C5C5C] block mb-1">How was your experience?</label>
            <StarRating value={rating} onChange={setRating} testId="restaurant-review-rating" />
          </div>

          <div>
            <label className="text-xs font-semibold text-[#5C5C5C] block mb-1">Comment (optional)</label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              data-testid="restaurant-review-comment-input"
              maxLength={1000}
              rows={4}
              placeholder="Tell others about the food, service, delivery time..."
              className="w-full bg-[#F8F5F0] border border-[#E2E2D9] rounded-2xl px-4 py-3 text-sm focus:outline-none focus:border-[#C84B31]"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="text-sm font-semibold text-[#5C5C5C] px-4 py-2.5 rounded-full hover:bg-[#F2EBE5]">Cancel</button>
            <button
              type="submit"
              disabled={submitting}
              data-testid="submit-restaurant-review-btn"
              className="bg-[#C84B31] hover:bg-[#A83A23] disabled:bg-[#A3A39E] text-white text-sm font-semibold px-5 py-2.5 rounded-full"
            >
              {submitting ? "Submitting..." : "Post review"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Orders() {
  const [marketplaceOrders, setMarketplaceOrders] = useState([]);
  const [restaurantOrders, setRestaurantOrders] = useState([]);
  const [searchParams] = useSearchParams();
  const newId = searchParams.get("new");
  const [reviewItem, setReviewItem] = useState(null);
  const [restaurantReviewOrder, setRestaurantReviewOrder] = useState(null);
  const [reviewedIds, setReviewedIds] = useState(new Set()); // session-only set of product_ids the user reviewed via this page
  const [reviewedOrderIds, setReviewedOrderIds] = useState(new Set()); // restaurant order ids reviewed in this session (merged with has_review from backend)
  const [activeTab, setActiveTab] = useState("all"); // "all", "marketplace", "restaurant"
  const [cancelTarget, setCancelTarget] = useState(null); // { order, kind }
  const [orderSplits, setOrderSplits] = useState({}); // { orderId: [splits] }
  
  // Get currency and exchange rate from CartContext with defaults
  const { currency = "USD", exchangeRate = 1 } = useCart() || {};

  const refreshOrders = () => {
    api.get("/orders/mine?limit=200").then((r) => setMarketplaceOrders(r.data)).catch(() => setMarketplaceOrders([]));
    api.get("/restaurant-orders").then((r) => setRestaurantOrders(r.data)).catch(() => setRestaurantOrders([]));
  };

  // Fetch splits for marketplace orders to show OTPs
  const fetchOrderSplits = async (orderId) => {
    try {
      const { data } = await api.get(`/customer/orders/${orderId}/splits`);
      setOrderSplits(prev => ({ ...prev, [orderId]: data }));
    } catch (err) {
      // Silently fail - splits may not exist yet or order may not be COD
      setOrderSplits(prev => ({ ...prev, [orderId]: [] }));
    }
  };

  useEffect(() => {
    refreshOrders();
  }, []);

  // Fetch splits for all marketplace orders
  useEffect(() => {
    marketplaceOrders.forEach(order => {
      if (!orderSplits[order.id]) {
        fetchOrderSplits(order.id);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [marketplaceOrders]);

  const onOrderCancelled = () => {
    refreshOrders();
  };

  const allOrders = [...marketplaceOrders, ...restaurantOrders].sort((a, b) => 
    new Date(b.created_at) - new Date(a.created_at)
  );

  const displayOrders = activeTab === "all" ? allOrders :
                        activeTab === "marketplace" ? marketplaceOrders :
                        restaurantOrders;

  const onReviewSubmitted = (productId) => {
    setReviewedIds((prev) => {
      const n = new Set(prev);
      n.add(productId);
      return n;
    });
  };

  const onRestaurantReviewSubmitted = (orderId) => {
    setReviewedOrderIds((prev) => {
      const n = new Set(prev);
      n.add(orderId);
      return n;
    });
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <h1 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">My orders</h1>
        <p className="text-sm text-[#5C5C5C] mt-1">{allOrders.length} order{allOrders.length !== 1 && "s"}</p>
        
        {/* Order Type Tabs */}
        <div className="flex gap-2 mt-6 mb-6">
          <button
            onClick={() => setActiveTab("all")}
            className={`px-4 py-2 rounded-full text-sm font-semibold transition ${
              activeTab === "all"
                ? "bg-[#C84B31] text-white"
                : "bg-[var(--js-subtle)] text-[var(--js-text)] hover:bg-[var(--js-border)]"
            }`}
          >
            All ({allOrders.length})
          </button>
          <button
            onClick={() => setActiveTab("marketplace")}
            className={`px-4 py-2 rounded-full text-sm font-semibold transition ${
              activeTab === "marketplace"
                ? "bg-[#C84B31] text-white"
                : "bg-[var(--js-subtle)] text-[var(--js-text)] hover:bg-[var(--js-border)]"
            }`}
          >
            Marketplace ({marketplaceOrders.length})
          </button>
          <button
            onClick={() => setActiveTab("restaurant")}
            className={`px-4 py-2 rounded-full text-sm font-semibold transition ${
              activeTab === "restaurant"
                ? "bg-[#C84B31] text-white"
                : "bg-[var(--js-subtle)] text-[var(--js-text)] hover:bg-[var(--js-border)]"
            }`}
          >
            Restaurants ({restaurantOrders.length})
          </button>
        </div>

        {displayOrders.length === 0 ? (
          <div className="mt-12 text-center py-20 bg-white rounded-3xl border border-[#E2E2D9]" data-testid="empty-orders">
            <Package className="w-12 h-12 mx-auto text-[#A3A39E]" />
            <p className="font-display font-semibold text-xl text-[#1A1A1A] mt-4">No orders yet</p>
            <p className="text-sm text-[#5C5C5C] mt-1">When you place an order, it will appear here.</p>
          </div>
        ) : (
          <div className="mt-8 space-y-4">
            {displayOrders.map((o) => {
              // Check if this is a restaurant order
              const isRestaurant = !!o.restaurant_id;
              
              if (isRestaurant) {
                // Restaurant order display
                const STATUS_CONFIG = {
                  pending: { label: "Pending", bg: "bg-yellow-500" },
                  accepted: { label: "Accepted", bg: "bg-blue-500" },
                  cooking: { label: "Cooking", bg: "bg-orange-500" },
                  ready: { label: "Ready", bg: "bg-green-500" },
                  completed: { label: "Completed", bg: "bg-gray-500" },
                  cancel_requested: { label: "Cancellation pending", bg: "bg-yellow-600" },
                  cancel_approved: { label: "Cancelled", bg: "bg-red-500" },
                  cancelled: { label: "Cancelled", bg: "bg-red-500" },
                };
                const config = STATUS_CONFIG[o.status] || STATUS_CONFIG.pending;
                const canReview = o.status === "completed" || o.delivery_status === "delivered";
                const canCancel = CUSTOMER_CANCELLABLE_REST_STATUSES.has(o.status) && o.delivery_status !== "delivered";

                // Show delivery OTP if driver is out for delivery
                const showDeliveryOtp = o.delivery_status === "out_for_delivery";

                // Cancellation banner content for the customer.
                let updateBanner = null;
                if (o.status === "cancel_requested") {
                  updateBanner = {
                    tone: "warning",
                    title: "The restaurant has requested to cancel this order",
                    body: (
                      <>
                        Waiting for admin review. If approved, you won't be charged. If rejected,
                        the order will be restored to <span className="font-semibold">{o.previous_status || "its previous status"}</span>.
                        {o.cancel_reason && (
                          <span className="block mt-1"><span className="font-semibold">Restaurant's reason:</span> {o.cancel_reason}</span>
                        )}
                      </>
                    ),
                  };
                } else if (o.status === "cancel_approved" || o.status === "cancelled") {
                  updateBanner = {
                    tone: "error",
                    title: "This order was cancelled",
                    body: <>The restaurant cancelled this order and admin approved it. You have not been charged.</>,
                  };
                } else if (o.cancel_outcome === "rejected") {
                  updateBanner = {
                    tone: "success",
                    title: "Cancellation request rejected",
                    body: (
                      <>
                        The restaurant requested to cancel, but admin rejected — your order is back to <span className="font-semibold">{o.status}</span> and will be fulfilled.
                        {o.cancel_rejected_note && (
                          <span className="block mt-1"><span className="font-semibold">Admin note:</span> {o.cancel_rejected_note}</span>
                        )}
                      </>
                    ),
                  };
                }

                const toneClasses = {
                  warning: "bg-yellow-50 border-yellow-300 text-yellow-900",
                  error: "bg-red-50 border-red-300 text-red-800",
                  success: "bg-green-50 border-green-300 text-green-800",
                };

                return (
                  <div
                    key={o.id}
                    data-testid={`restaurant-order-${o.id}`}
                    className="bg-white border border-[#E2E2D9] rounded-3xl p-5 sm:p-6"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
                      <div>
                        <p className="text-[10px] uppercase tracking-[0.18em] text-[#5C5C5C] font-bold">RESTAURANT</p>
                        <p className="font-display font-semibold text-lg text-[#1A1A1A]">{o.restaurant_name}</p>
                        <p className="text-xs text-[#5C5C5C] mt-0.5">{new Date(o.created_at).toLocaleString()}</p>
                      </div>
                      <div
                        data-testid={`restaurant-order-status-${o.id}`}
                        className={`${config.bg} text-white px-3 py-1.5 rounded-full text-xs font-bold flex items-center gap-1`}
                      >
                        {config.label}
                      </div>
                    </div>

                    <div className="mb-4">
                      <OrderStatusTimeline
                        kind="restaurant"
                        status={o.status}
                        deliveryStatus={o.delivery_status}
                        cancelled={o.status === "cancel_approved" || o.status === "cancelled"}
                      />
                    </div>

                    {updateBanner && (
                      <div
                        data-testid={`order-update-banner-${o.id}`}
                        className={`rounded-2xl border p-4 mb-4 ${toneClasses[updateBanner.tone]}`}
                      >
                        <p className="font-bold text-sm">{updateBanner.title}</p>
                        <p className="text-xs mt-1 leading-relaxed">{updateBanner.body}</p>
                      </div>
                    )}

                    {/* Delivery OTP Display for Restaurant Orders */}
                    {showDeliveryOtp && o.customer_delivery_otp && (
                      <div
                        data-testid={`restaurant-delivery-otp-${o.id}`}
                        className="bg-[#E9C46A]/10 border-2 border-[#E9C46A] rounded-2xl p-4 mb-4"
                      >
                        <div className="flex items-start gap-3">
                          <div className="bg-[#E9C46A] rounded-full p-2">
                            <KeyRound className="w-5 h-5 text-[#1A1A1A]" />
                          </div>
                          <div className="flex-1">
                            <p className="font-bold text-sm text-[#1A1A1A] mb-1">Your delivery OTP</p>
                            <p className="text-2xl font-bold text-[#C84B31] tracking-wider mb-2">{o.customer_delivery_otp}</p>
                            <p className="text-xs text-[#5C5C5C]">
                              Give this code only to the driver when you receive your order.
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="border-t border-[#E2E2D9] pt-4 space-y-2">
                      {o.items.map((item, idx) => (
                        <div key={idx} className="flex justify-between text-sm">
                          <span className="text-[#5C5C5C]">{item.quantity}x {item.name}</span>
                          <span className="font-medium text-[#1A1A1A]">{formatPrice(item.price_usd * item.quantity, item.exchange_rate_ssp || o.exchange_rate_ssp || exchangeRate, currency)}</span>
                        </div>
                      ))}
                    </div>

                    {/* Order Summary: subtotal + delivery + total */}
                    {(() => {
                      const restRate = o.exchange_rate_ssp || exchangeRate;
                      const subtotal = typeof o.subtotal === "number" ? o.subtotal : (o.items || []).reduce((s, it) => s + (it.price_usd || 0) * (it.quantity || 0), 0);
                      const deliveryFee = typeof o.delivery_fee === "number" ? o.delivery_fee : 0;
                      const orderTotal = typeof o.total === "number" ? o.total : (subtotal + deliveryFee);
                      const totalDisplay = currency === "USD"
                        ? formatPrice(orderTotal, restRate, currency)
                        : `${currency} ${Math.round((subtotal * restRate) + (deliveryFee * exchangeRate)).toLocaleString("en-US")}`;
                      return (
                        <div className="mt-4 pt-3 border-t border-[#E2E2D9] space-y-1.5 text-sm" data-testid={`rest-order-summary-${o.id}`}>
                          <div className="flex justify-between text-[#5C5C5C]">
                            <span>Subtotal</span>
                            <span className="font-medium text-[#1A1A1A]">{formatPrice(subtotal, restRate, currency)}</span>
                          </div>
                          <div className="flex justify-between text-[#5C5C5C]">
                            <span>Delivery fee</span>
                            <span className="font-medium text-[#1A1A1A]">{deliveryFee === 0 ? "FREE" : formatPrice(deliveryFee, exchangeRate, currency)}</span>
                          </div>
                          <div className="flex justify-between pt-1.5 border-t border-[#E2E2D9]">
                            <span className="font-bold text-[#1A1A1A]">Total</span>
                            <span className="font-bold text-[#C84B31]">{totalDisplay}</span>
                          </div>
                        </div>
                      );
                    })()}

                    <div className="flex items-center justify-between mt-4 pt-4 border-t border-[#E2E2D9]">
                      <div className="text-xs text-[#5C5C5C]">
                        {o.customer_area && <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" /> {o.customer_area}</span>}
                      </div>
                      <div className="flex items-center gap-2">
                        {canCancel && (
                          <button
                            onClick={() => setCancelTarget({ order: o, kind: "restaurant" })}
                            data-testid={`cancel-restaurant-order-${o.id}`}
                            className="inline-flex items-center gap-1 text-xs font-semibold text-[#D90429] hover:text-white hover:bg-[#D90429] border border-[#D90429] px-3 py-1.5 rounded-full transition"
                          >
                            <XCircle className="w-3.5 h-3.5" /> Cancel
                          </button>
                        )}
                        {canReview && (
                          (o.has_review || reviewedOrderIds.has(o.id)) ? (
                            <span
                              data-testid={`restaurant-order-${o.id}-reviewed`}
                              className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#2D6A4F] bg-[#2D6A4F]/10 px-3 py-1.5 rounded-full"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" /> Reviewed
                            </span>
                          ) : (
                            <button
                              onClick={() => setRestaurantReviewOrder(o)}
                              data-testid={`write-restaurant-review-${o.id}`}
                              className="bg-[#E9C46A] hover:bg-[#D4B05A] text-[#0E1A2B] text-sm font-semibold px-4 py-2 rounded-full flex items-center gap-1"
                            >
                              <Star className="w-4 h-4" /> Write Review
                            </button>
                          )
                        )}
                      </div>
                    </div>
                  </div>
                );
              }
              
              // Marketplace order display (original code)
              const s = STATUS_STYLES[o.status] || STATUS_STYLES.Pending;
              const Icon = s.icon;
              const isNew = o.id === newId;
              const isDelivered = o.status === "Delivered";
              
              // Get splits for this order to check if all delivered and show OTPs
              const splits = orderSplits[o.id] || [];
              const allSplitsDelivered = splits.length > 0 && splits.every(s => s.delivery_status === "delivered");
              const canCancelMp = CUSTOMER_CANCELLABLE_MP_STATUSES.has(o.status) && !allSplitsDelivered;
              const splitsOutForDelivery = splits.filter(s => s.delivery_status === "out_for_delivery");

              return (
                <div
                  key={o.id}
                  data-testid={`order-${o.id}`}
                  className={`bg-white border rounded-3xl p-5 sm:p-6 ${
                    isNew ? "border-[#C84B31] shadow-[0_8px_24px_rgba(200,75,49,0.15)]" : "border-[#E2E2D9]"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.18em] text-[#5C5C5C] font-bold">{o.order_kind}</p>
                      <p className="font-display font-semibold text-lg text-[#1A1A1A]">Order #{o.id.slice(0, 8).toUpperCase()}</p>
                      <p className="text-xs text-[#5C5C5C] mt-0.5">{new Date(o.created_at).toLocaleString()}</p>
                    </div>
                    <span className={`inline-flex items-center gap-1.5 ${s.bg} ${s.text} font-bold text-xs px-3 py-1.5 rounded-full`} data-testid={`order-status-${o.id}`}>
                      <Icon className="w-3.5 h-3.5" /> {o.status}
                    </span>
                  </div>

                  <div className="mb-4">
                    <OrderStatusTimeline
                      kind="marketplace"
                      status={o.status}
                      deliveryStatus={splitsOutForDelivery.length > 0 ? "out_for_delivery" : (splits[0]?.delivery_status)}
                      cancelled={o.status === "Cancelled"}
                    />
                  </div>

                  {/* Delivery OTP Display for Marketplace Splits */}
                  {splitsOutForDelivery.length > 0 && (
                    <div className="mb-4 space-y-2">
                      {splitsOutForDelivery.map((split, idx) => (
                        <div
                          key={split.id}
                          data-testid={`marketplace-delivery-otp-${split.id}`}
                          className="bg-[#E9C46A]/10 border-2 border-[#E9C46A] rounded-2xl p-4"
                        >
                          <div className="flex items-start gap-3">
                            <div className="bg-[#E9C46A] rounded-full p-2">
                              <KeyRound className="w-5 h-5 text-[#1A1A1A]" />
                            </div>
                            <div className="flex-1">
                              <p className="font-bold text-sm text-[#1A1A1A] mb-1">
                                Delivery OTP - {split.shop_name || "Shop"}
                              </p>
                              <p className="text-2xl font-bold text-[#C84B31] tracking-wider mb-2">
                                {split.customer_delivery_otp}
                              </p>
                              <p className="text-xs text-[#5C5C5C]">
                                Give this code only to the driver when you receive items from this shop.
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="space-y-2 mb-4">
                    {o.items.map((i, idx) => {
                      const reviewable = isDelivered && i.item_type === "product";
                      const reviewed = reviewedIds.has(i.item_id);
                      const itemRate = i.exchange_rate_ssp || exchangeRate;
                      return (
                        <div key={idx} className="flex items-center gap-3 text-sm">
                          <img src={i.image_url} alt={i.name} className="w-12 h-12 rounded-lg object-cover" />
                          <div className="flex-1 min-w-0 truncate">
                            <span className="font-semibold text-[#1A1A1A]">{i.name}</span>
                            <span className="text-[#5C5C5C]"> × {i.quantity}</span>
                          </div>
                          {reviewable && (
                            reviewed ? (
                              <span
                                data-testid={`order-${o.id}-item-${i.item_id}-reviewed`}
                                className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#2D6A4F] bg-[#2D6A4F]/10 px-2.5 py-1 rounded-full"
                              >
                                <CheckCircle2 className="w-3 h-3" /> Reviewed
                              </span>
                            ) : (
                              <button
                                onClick={() => setReviewItem(i)}
                                data-testid={`leave-review-${o.id}-${i.item_id}`}
                                className="inline-flex items-center gap-1 text-[11px] font-bold text-[#C84B31] hover:text-white hover:bg-[#C84B31] border border-[#C84B31] px-2.5 py-1 rounded-full transition"
                              >
                                <Star className="w-3 h-3" /> Review
                              </button>
                            )
                          )}
                          <span className="font-semibold text-[#1A1A1A] tabular-nums">{formatPrice(i.price_usd * i.quantity, itemRate, currency)}</span>
                        </div>
                      );
                    })}
                  </div>

                  {/* Order Summary: subtotal + delivery + total */}
                  {(() => {
                    const subtotal = typeof o.subtotal_usd === "number" ? o.subtotal_usd : 0;
                    const deliveryFee = typeof o.delivery_fee_usd === "number" ? o.delivery_fee_usd : 0;
                    const orderTotal = typeof o.total_usd === "number" ? o.total_usd : (subtotal + deliveryFee);
                    // Per-seller subtotal in SSP (each item uses its own seller rate)
                    const subtotalSSP = (o.items || []).reduce((sum, it) => sum + (it.price_usd || 0) * (it.quantity || 0) * (it.exchange_rate_ssp || exchangeRate), 0);
                    const totalDisplay = currency === "USD"
                      ? formatPrice(orderTotal, exchangeRate, currency)
                      : `${currency} ${Math.round(subtotalSSP + (deliveryFee * exchangeRate)).toLocaleString("en-US")}`;
                    const subtotalDisplay = currency === "USD"
                      ? formatPrice(subtotal, exchangeRate, currency)
                      : `${currency} ${Math.round(subtotalSSP).toLocaleString("en-US")}`;
                    return (
                      <div className="mb-4 pt-3 border-t border-[#E2E2D9] space-y-1.5 text-sm" data-testid={`mp-order-summary-${o.id}`}>
                        <div className="flex justify-between text-[#5C5C5C]">
                          <span>Subtotal</span>
                          <span className="font-medium text-[#1A1A1A]">{subtotalDisplay}</span>
                        </div>
                        <div className="flex justify-between text-[#5C5C5C]">
                          <span>Delivery fee</span>
                          <span className="font-medium text-[#1A1A1A]">{deliveryFee === 0 ? "FREE" : formatPrice(deliveryFee, exchangeRate, currency)}</span>
                        </div>
                        <div className="flex justify-between pt-1.5 border-t border-[#E2E2D9]">
                          <span className="font-bold text-[#1A1A1A]">Total</span>
                          <span className="font-bold text-[#C84B31]">{totalDisplay}</span>
                        </div>
                      </div>
                    );
                  })()}

                  <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-[#E2E2D9]">
                    <div className="flex flex-wrap gap-3 text-xs text-[#5C5C5C]">
                      <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" /> {o.area}</span>
                      {o.phone && <span className="inline-flex items-center gap-1"><Phone className="w-3 h-3" /> {o.phone}</span>}
                    </div>
                    <div className="flex items-center gap-3">
                      {canCancelMp && (
                        <button
                          onClick={() => setCancelTarget({ order: o, kind: "marketplace" })}
                          data-testid={`cancel-marketplace-order-${o.id}`}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-[#D90429] hover:text-white hover:bg-[#D90429] border border-[#D90429] px-3 py-1.5 rounded-full transition"
                        >
                          <XCircle className="w-3.5 h-3.5" /> Cancel
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      <Footer />

      {reviewItem && (
        <ReviewModal
          item={reviewItem}
          onClose={() => setReviewItem(null)}
          onSubmitted={onReviewSubmitted}
        />
      )}

      {restaurantReviewOrder && (
        <RestaurantReviewModal
          order={restaurantReviewOrder}
          onClose={() => setRestaurantReviewOrder(null)}
          onSubmitted={onRestaurantReviewSubmitted}
        />
      )}

      {cancelTarget && (
        <CancelOrderModal
          order={cancelTarget.order}
          kind={cancelTarget.kind}
          onClose={() => setCancelTarget(null)}
          onCancelled={onOrderCancelled}
        />
      )}
    </div>
  );
}
