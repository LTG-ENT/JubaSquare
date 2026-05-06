import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api, { formatUSD } from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Package, MapPin, Phone, Truck, CheckCircle2, Clock, Star, X } from "lucide-react";
import { toast } from "sonner";

const STATUS_STYLES = {
  Pending: { bg: "bg-[#E9C46A]", text: "text-[#1A1A1A]", icon: Clock },
  "In Progress": { bg: "bg-[#2A9D8F]", text: "text-white", icon: Truck },
  Delivered: { bg: "bg-[#2D6A4F]", text: "text-white", icon: CheckCircle2 },
};

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

export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [searchParams] = useSearchParams();
  const newId = searchParams.get("new");
  const [reviewItem, setReviewItem] = useState(null);
  const [reviewedIds, setReviewedIds] = useState(new Set()); // session-only set of product_ids the user reviewed via this page

  useEffect(() => {
    api.get("/orders/mine").then((r) => setOrders(r.data));
  }, []);

  const onReviewSubmitted = (productId) => {
    setReviewedIds((prev) => {
      const n = new Set(prev);
      n.add(productId);
      return n;
    });
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <h1 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">My orders</h1>
        <p className="text-sm text-[#5C5C5C] mt-1">{orders.length} order{orders.length !== 1 && "s"}</p>

        {orders.length === 0 ? (
          <div className="mt-12 text-center py-20 bg-white rounded-3xl border border-[#E2E2D9]" data-testid="empty-orders">
            <Package className="w-12 h-12 mx-auto text-[#A3A39E]" />
            <p className="font-display font-semibold text-xl text-[#1A1A1A] mt-4">No orders yet</p>
            <p className="text-sm text-[#5C5C5C] mt-1">When you place an order, it will appear here.</p>
          </div>
        ) : (
          <div className="mt-8 space-y-4">
            {orders.map((o) => {
              const s = STATUS_STYLES[o.status] || STATUS_STYLES.Pending;
              const Icon = s.icon;
              const isNew = o.id === newId;
              const isDelivered = o.status === "Delivered";
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

                  <div className="space-y-2 mb-4">
                    {o.items.map((i, idx) => {
                      const reviewable = isDelivered && i.item_type === "product";
                      const reviewed = reviewedIds.has(i.item_id);
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
                          <span className="font-semibold text-[#1A1A1A] tabular-nums">{formatUSD(i.price_usd * i.quantity)}</span>
                        </div>
                      );
                    })}
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-[#E2E2D9]">
                    <div className="flex flex-wrap gap-3 text-xs text-[#5C5C5C]">
                      <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" /> {o.area}</span>
                      {o.phone && <span className="inline-flex items-center gap-1"><Phone className="w-3 h-3" /> {o.phone}</span>}
                    </div>
                    <p className="font-display font-bold text-lg text-[#1A1A1A]">{formatUSD(o.subtotal_usd)}</p>
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
    </div>
  );
}
