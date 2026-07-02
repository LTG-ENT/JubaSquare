import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import api, { formatPrice, formatPriceAlt } from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import SeoMeta, { productSchema } from "@/components/SeoMeta";
import { useCart } from "@/context/CartContext";
import { useAuth } from "@/context/AuthContext";
import { Plus, Minus, Heart, ChevronLeft, Star, Store, Truck, Package } from "lucide-react";
import { toast } from "sonner";

function StarRating({ value, onChange, size = 18, readOnly = false }) {
  return (
    <div className="inline-flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          disabled={readOnly}
          onClick={() => !readOnly && onChange?.(n)}
          data-testid={readOnly ? undefined : `star-${n}`}
          className={`${readOnly ? "cursor-default" : "cursor-pointer hover:scale-110 transition"}`}
        >
          <Star
            className={`${value >= n ? "fill-[#E9C46A] text-[#E9C46A]" : "text-[var(--js-text-disabled)]"}`}
            style={{ width: size, height: size }}
          />
        </button>
      ))}
    </div>
  );
}

export default function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { addItem, exchangeRate, currency } = useCart();
  const { user } = useAuth();
  const [product, setProduct] = useState(null);
  const [shop, setShop] = useState(null);
  const [reviewData, setReviewData] = useState({ reviews: [], average: 0, count: 0 });
  const [qty, setQty] = useState(1);
  const [fav, setFav] = useState(false);
  const [draft, setDraft] = useState({ rating: 5, comment: "" });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.get(`/products/${id}`).then((r) => {
      if (cancelled) return;
      setProduct(r.data);
      setQty(r.data.min_order_qty || 1);
      if (r.data.shop_id) {
        api.get(`/shops/${r.data.shop_id}`).then((s) => !cancelled && setShop(s.data));
      }
    }).catch(() => {
      if (!cancelled) toast.error("Product not found");
    });
    api.get(`/products/${id}/reviews`).then((r) => !cancelled && setReviewData(r.data));
    return () => { cancelled = true; };
  }, [id]);

  useEffect(() => {
    if (!user || user.role !== "customer" || !product) return;
    api.get("/favorites?limit=200").then((r) => {
      const list = Array.isArray(r.data) ? r.data : [];
      setFav(!!list.find((f) => f.target_type === "product" && f.target_id === product.id));
    }).catch(() => {});
  }, [user, product]);

  if (!product) {
    return (
      <div className="min-h-screen flex flex-col">
        <Header />
        <div className="max-w-7xl mx-auto px-4 py-20 w-full flex-1 text-center text-[var(--js-text-secondary)]">
          Loading product...
        </div>
        <Footer />
      </div>
    );
  }

  const isWholesale = !!product.is_wholesale;
  const minQty = product.min_order_qty || 1;
  const meetsMin = qty >= minQty;
  const usesBulk = isWholesale && !!product.bulk_price_usd && meetsMin;
  const unitPrice = usesBulk ? product.bulk_price_usd : product.price_usd;
  const lowStock = (product.stock ?? 100) > 0 && (product.stock ?? 100) <= 5;
  const outOfStock = (product.stock ?? 100) <= 0;
  // Per-seller exchange rate (fallback to global)
  const rate = product.exchange_rate_ssp || exchangeRate;

  const onAdd = () => {
    if (isWholesale && !meetsMin) {
      toast.error(`Minimum order quantity is ${minQty}`);
      return;
    }
    const ok = addItem({
      item_type: "product",
      item_id: product.id,
      name: product.name,
      price_usd: unitPrice,
      image_url: product.image_url,
      exchange_rate_ssp: product.exchange_rate_ssp,
      is_wholesale: isWholesale,
      min_order_qty: isWholesale ? minQty : 1,
      quantity: qty,
    });
    if (ok) toast.success(`${qty}× ${product.name} added to cart`);
  };

  const toggleFav = async () => {
    if (!user) { toast.error("Login to save favorites"); return; }
    if (fav) {
      await api.delete(`/favorites?target_type=product&target_id=${product.id}`);
      setFav(false); toast.success("Removed from favorites");
    } else {
      await api.post("/favorites", { target_type: "product", target_id: product.id });
      setFav(true); toast.success("Added to favorites");
    }
  };

  const submitReview = async (e) => {
    e.preventDefault();
    if (!user) { navigate("/login"); return; }
    if (user.role !== "customer") { toast.error("Only customers can post reviews"); return; }
    setSubmitting(true);
    try {
      await api.post(`/products/${product.id}/reviews`, draft);
      toast.success("Review posted!");
      setDraft({ rating: 5, comment: "" });
      const r = await api.get(`/products/${product.id}/reviews`);
      setReviewData(r.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not post review");
    } finally {
      setSubmitting(false);
    }
  };

  // Build "specs" from description (split by sentence/period for display)
  const specsFromDesc = (product.description || "")
    .split(/[.\n]/)
    .map((s) => s.trim())
    .filter(Boolean);

  const deliveryInfo = (() => {
    if (!shop) return null;
    const mode = shop.delivery_mode || "free";
    if (mode === "free") return "Free delivery";
    if (mode === "fixed") return `Delivery from ${formatPrice(shop.delivery_fee_usd || 0, rate, currency)}`;
    if (mode === "per_area") {
      const fees = (shop.delivery_per_area || []).map((a) => a.fee_usd).filter((n) => n != null);
      if (fees.length === 0) return "Delivery available";
      const min = Math.min(...fees), max = Math.max(...fees);
      return min === max
        ? `Delivery: ${formatPrice(min, rate, currency)}`
        : `Delivery: ${formatPrice(min, rate, currency)} – ${formatPrice(max, rate, currency)} (varies by area)`;
    }
    return null;
  })();

  return (
    <div className="min-h-screen flex flex-col">
      {product && typeof window !== "undefined" && (
        <SeoMeta
          title={`${product.name} — JubaSquare`}
          description={(product.description || `Buy ${product.name} on JubaSquare.`).slice(0, 200)}
          canonical={`${window.location.origin}/product/${product.id}`}
          image={product.image_url || `${window.location.origin}/icons/icon-512.png`}
          type="product"
          schema={productSchema({ product, shop, origin: window.location.origin })}
        />
      )}
      <Header />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full flex-1">
        <button
          onClick={() => navigate(-1)}
          data-testid="back-btn"
          className="inline-flex items-center gap-1 text-sm text-[var(--js-text-secondary)] hover:text-[var(--js-text)] mb-4"
        >
          <ChevronLeft className="w-4 h-4" /> Back
        </button>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Image */}
          <div className="js-card overflow-hidden">
            <div className="aspect-square bg-[var(--js-subtle)] relative">
              <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" />
              <div className="absolute top-4 left-4 flex flex-col gap-2">
                {isWholesale && (
                  <span className="bg-[#2D6A4F] text-white text-xs font-bold px-3 py-1.5 rounded-full shadow-md">🟢 Wholesale</span>
                )}
                {outOfStock && (
                  <span className="bg-[#A3A39E] text-white text-xs font-bold px-3 py-1.5 rounded-full shadow-md">Out of stock</span>
                )}
                {!outOfStock && lowStock && (
                  <span className="bg-[#D90429] text-white text-xs font-bold px-3 py-1.5 rounded-full shadow-md">🔴 Low Stock</span>
                )}
              </div>
            </div>
          </div>

          {/* Info */}
          <div>
            {shop && (
              <Link to={`/shop/${shop.id}`} className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-[var(--js-text-secondary)] font-bold hover:text-[#C84B31] transition" data-testid="product-shop-link">
                <Store className="w-3 h-3" /> {shop.name}
              </Link>
            )}
            <h1 className="font-display font-bold text-3xl sm:text-4xl text-[var(--js-text)] mt-2" data-testid="product-name">
              {product.name}
            </h1>
            <p className="text-xs text-[var(--js-text-secondary)] mt-1">{product.category}</p>

            {reviewData.count > 0 && (
              <div className="mt-3 flex items-center gap-2" data-testid="review-summary">
                <StarRating value={Math.round(reviewData.average)} readOnly size={16} />
                <span className="text-sm font-semibold text-[var(--js-text)]">{reviewData.average}</span>
                <span className="text-xs text-[var(--js-text-secondary)]">({reviewData.count} review{reviewData.count !== 1 && "s"})</span>
              </div>
            )}

            <div className="mt-5 flex items-baseline gap-2">
              <p className="font-display font-bold text-4xl text-[var(--js-text)]" data-testid="product-price">
                {formatPrice(unitPrice, rate, currency)}
              </p>
              <p className="text-sm text-[var(--js-text-secondary)]">≈ {formatPriceAlt(unitPrice, rate, currency)}</p>
              {usesBulk && <span className="text-xs font-bold text-[#2D6A4F] bg-[#2D6A4F]/10 px-2 py-1 rounded-full">BULK PRICE</span>}
            </div>

            {isWholesale && (product.min_order_qty > 1 || product.bulk_price_usd) && (
              <div className="mt-3 grid grid-cols-2 gap-2 max-w-sm">
                {product.min_order_qty > 1 && (
                  <div className="bg-[var(--js-subtle)] rounded-xl p-3">
                    <p className="text-[10px] uppercase font-bold text-[var(--js-text-secondary)]">Minimum order</p>
                    <p className="font-bold text-[var(--js-text)]">{minQty} units</p>
                  </div>
                )}
                {product.bulk_price_usd && (
                  <div className="bg-[#2D6A4F]/10 rounded-xl p-3">
                    <p className="text-[10px] uppercase font-bold text-[#2D6A4F]">Bulk price</p>
                    <p className="font-bold text-[#2D6A4F]">{formatPrice(product.bulk_price_usd, rate, currency)}</p>
                  </div>
                )}
              </div>
            )}

            {isWholesale && Array.isArray(product.pricing_tiers) && product.pricing_tiers.length > 0 && (
              <div className="mt-4 max-w-md" data-testid="pricing-tiers">
                <p className="text-[10px] uppercase font-bold text-[var(--js-text-secondary)] tracking-wider mb-2">
                  Pricing tiers
                </p>
                <div className="border border-[var(--js-border)] rounded-xl overflow-hidden divide-y divide-[var(--js-border)]">
                  {[...product.pricing_tiers]
                    .sort((a, b) => (a.min_qty || 0) - (b.min_qty || 0))
                    .map((t, i) => (
                      <div
                        key={i}
                        data-testid={`pricing-tier-${i}`}
                        className="flex items-center justify-between px-3 py-2 text-sm bg-[var(--js-paper)]"
                      >
                        <span className="text-[var(--js-text-secondary)]">
                          <strong className="text-[var(--js-text)]">{t.min_qty}+</strong> units
                        </span>
                        <span className="font-bold text-[#2D6A4F]">
                          {formatPrice(t.price_usd, rate, currency)} <span className="text-xs font-normal text-[var(--js-text-secondary)]">/ unit</span>
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Quantity + Add to Cart */}
            <div className="mt-6 flex items-center gap-3">
              <div className="flex items-center gap-2 bg-[var(--js-subtle)] rounded-full px-2 py-1">
                <button onClick={() => setQty(Math.max(isWholesale ? minQty : 1, qty - 1))} data-testid="qty-minus" className="p-1.5 hover:bg-white rounded-full">
                  <Minus className="w-3.5 h-3.5" />
                </button>
                <span className="font-semibold text-sm w-8 text-center" data-testid="qty-value">{qty}</span>
                <button onClick={() => setQty(qty + 1)} data-testid="qty-plus" className="p-1.5 hover:bg-white rounded-full">
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>
              <button
                onClick={onAdd}
                disabled={outOfStock}
                data-testid="detail-add-to-cart"
                className="flex-1 bg-[#C84B31] hover:bg-[#A83A23] disabled:bg-[#A3A39E] text-white font-semibold px-6 py-3 rounded-full inline-flex items-center justify-center gap-2 transition shadow-sm hover:shadow-md"
              >
                <Plus className="w-4 h-4" /> Add to Cart
              </button>
              {user?.role === "customer" && (
                <button onClick={toggleFav} data-testid="detail-fav-toggle" className="p-3 bg-white border border-[var(--js-border)] rounded-full hover:bg-[var(--js-subtle)] transition">
                  <Heart className={`w-5 h-5 ${fav ? "fill-[#C84B31] text-[#C84B31]" : "text-[var(--js-text)]"}`} />
                </button>
              )}
            </div>

            {/* Delivery + Shop info */}
            <div className="mt-6 space-y-2 text-sm">
              {deliveryInfo && (
                <div className="flex items-center gap-2 text-[var(--js-text)]" data-testid="delivery-info">
                  <Truck className="w-4 h-4 text-[#2D6A4F]" /> <span className="font-semibold">{deliveryInfo}</span>
                </div>
              )}
              <div className="flex items-center gap-2 text-[var(--js-text-secondary)]">
                <Package className="w-4 h-4" /> Stock: <span className="font-semibold text-[var(--js-text)]">{product.stock ?? "—"}</span>
              </div>
            </div>
          </div>
        </div>

        {/* DESCRIPTION + SPECS */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-12">
          <div className="lg:col-span-2 js-card p-6">
            <h2 className="font-display font-semibold text-xl text-[var(--js-text)]">Description</h2>
            <p className="text-sm text-[var(--js-text-secondary)] mt-3 leading-relaxed whitespace-pre-line">
              {product.description || "No description available."}
            </p>
          </div>
          <div className="js-card p-6">
            <h2 className="font-display font-semibold text-xl text-[var(--js-text)]">Specifications</h2>
            <ul className="mt-3 space-y-2 text-sm">
              <li className="flex justify-between gap-2"><span className="text-[var(--js-text-secondary)]">Category</span><span className="font-semibold text-right">{product.category}</span></li>
              <li className="flex justify-between gap-2"><span className="text-[var(--js-text-secondary)]">Type</span><span className="font-semibold text-right">{isWholesale ? "Wholesale" : "Retail"}</span></li>
              {isWholesale && <li className="flex justify-between gap-2"><span className="text-[var(--js-text-secondary)]">Min order</span><span className="font-semibold text-right">{minQty}</span></li>}
              <li className="flex justify-between gap-2"><span className="text-[var(--js-text-secondary)]">Stock</span><span className="font-semibold text-right">{product.stock ?? "—"}</span></li>
              {shop && <li className="flex justify-between gap-2"><span className="text-[var(--js-text-secondary)]">Sold by</span><span className="font-semibold text-right">{shop.name}</span></li>}
              {shop && <li className="flex justify-between gap-2"><span className="text-[var(--js-text-secondary)]">Area</span><span className="font-semibold text-right">{shop.area}</span></li>}
              {specsFromDesc.length > 0 && specsFromDesc.slice(0, 5).map((s, i) => (
                <li key={i} className="text-[var(--js-text-secondary)] pt-1">• {s}</li>
              ))}
            </ul>
          </div>
        </div>

        {/* REVIEWS */}
        <div className="mt-12 js-card p-6" data-testid="reviews-section">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <h2 className="font-display font-semibold text-2xl text-[var(--js-text)]">
              Reviews & Feedback
              {reviewData.count > 0 && <span className="ml-2 text-sm text-[var(--js-text-secondary)]">({reviewData.count})</span>}
            </h2>
            {reviewData.count > 0 && (
              <div className="flex items-center gap-2">
                <StarRating value={Math.round(reviewData.average)} readOnly size={20} />
                <span className="font-semibold text-[var(--js-text)]">{reviewData.average} / 5</span>
              </div>
            )}
          </div>

          {/* Review form */}
          {user?.role === "customer" ? (
            <form onSubmit={submitReview} className="mt-6 bg-[var(--js-subtle)] rounded-2xl p-4 space-y-3" data-testid="review-form">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold">Your rating:</span>
                <StarRating value={draft.rating} onChange={(n) => setDraft({ ...draft, rating: n })} />
              </div>
              <textarea
                rows={3}
                value={draft.comment}
                onChange={(e) => setDraft({ ...draft, comment: e.target.value })}
                placeholder="Share your experience with this product..."
                data-testid="review-comment"
                className="js-input"
              />
              <button
                type="submit"
                disabled={submitting}
                data-testid="submit-review-btn"
                className="bg-[#C84B31] hover:bg-[#A83A23] disabled:bg-[#A3A39E] text-white font-semibold px-5 py-2.5 rounded-full transition"
              >
                {submitting ? "Posting..." : "Post review"}
              </button>
            </form>
          ) : (
            <div className="mt-6 bg-[var(--js-subtle)] rounded-2xl p-4 text-sm text-[var(--js-text-secondary)]">
              {user
                ? "Only customers can post reviews."
                : <><Link to="/login" className="text-[#C84B31] font-semibold hover:underline">Sign in</Link> as a customer to post a review.</>}
            </div>
          )}

          {/* Reviews list */}
          <div className="mt-6 space-y-4">
            {reviewData.reviews.length === 0 ? (
              <p className="text-sm text-[var(--js-text-secondary)]">No reviews yet — be the first!</p>
            ) : reviewData.reviews.map((rv) => (
              <div key={rv.id} className="border-t border-[var(--js-border)] pt-4" data-testid={`review-${rv.id}`}>
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 bg-[#C84B31] text-white font-bold text-sm rounded-full flex items-center justify-center">
                      {(rv.user_name || "C").charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <p className="font-semibold text-sm text-[var(--js-text)]">{rv.user_name}</p>
                      <p className="text-[10px] text-[var(--js-text-secondary)]">{new Date(rv.created_at).toLocaleDateString()}</p>
                    </div>
                  </div>
                  <StarRating value={rv.rating} readOnly size={14} />
                </div>
                {rv.comment && <p className="text-sm text-[var(--js-text)] mt-2 leading-relaxed">{rv.comment}</p>}
              </div>
            ))}
          </div>
        </div>
      </div>

      <Footer />
    </div>
  );
}
