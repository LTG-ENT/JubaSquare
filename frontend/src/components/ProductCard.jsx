import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Heart } from "lucide-react";
import { formatPrice, formatPriceAlt } from "@/lib/api";
import api from "@/lib/api";
import { useCart } from "@/context/CartContext";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

export default function ProductCard({ product, shop }) {
  const { addItem, exchangeRate, currency } = useCart();
  const { user } = useAuth();
  const [fav, setFav] = useState(false);
  // Use per-seller exchange rate if embedded, fallback to global cart rate
  const rate = product.exchange_rate_ssp || exchangeRate;

  useEffect(() => {
    if (!user || user.role !== "customer") return;
    api.get("/favorites?limit=200").then((r) => {
      const list = Array.isArray(r.data) ? r.data : [];
      setFav(!!list.find((f) => f.target_type === "product" && f.target_id === product.id));
    }).catch(() => {});
  }, [user, product.id]);

  const onAdd = (e) => {
    e.preventDefault(); e.stopPropagation();
    // Wholesale items must be added at their minimum-order quantity, not 1.
    const initialQty = product.is_wholesale ? Math.max(1, product.min_order_qty || 1) : 1;
    // Apply active promo to the price added to cart. Backend re-verifies at
    // order-create so the customer can never be charged more than the
    // displayed promo price.
    const pm = product.promo || {};
    const nowIso = new Date().toISOString();
    const promoLive = !!pm.active && (!pm.starts_at || nowIso >= pm.starts_at) && (!pm.ends_at || nowIso <= pm.ends_at);
    const effective = !promoLive ? product.price_usd : (
      pm.type === "percent"
        ? Math.max(0, product.price_usd * (1 - (pm.value || 0) / 100))
        : Math.max(0, product.price_usd - (pm.value || 0))
    );
    const ok = addItem({
      item_type: "product",
      item_id: product.id,
      name: product.name,
      price_usd: effective,
      image_url: product.image_url,
      exchange_rate_ssp: product.exchange_rate_ssp,
      // Propagate wholesale constraints so the cart can honor the floor.
      is_wholesale: !!product.is_wholesale,
      min_order_qty: product.is_wholesale ? Math.max(1, product.min_order_qty || 1) : 1,
      quantity: initialQty,
    });
    if (ok) {
      const suffix = initialQty > 1 ? ` (min. order ${initialQty} units)` : "";
      toast.success(`${product.name} added to cart${suffix}`);
    }
  };

  const toggleFav = async (e) => {
    e.preventDefault(); e.stopPropagation();
    if (!user) { toast.error("Login to save favorites"); return; }
    if (fav) {
      await api.delete(`/favorites?target_type=product&target_id=${product.id}`);
      setFav(false); toast.success("Removed from favorites");
    } else {
      await api.post("/favorites", { target_type: "product", target_id: product.id });
      setFav(true); toast.success("Added to favorites");
    }
  };

  const isWholesale = !!product.is_wholesale;
  const lowStock = (product.stock ?? 100) > 0 && (product.stock ?? 100) <= 5;
  const outOfStock = (product.stock ?? 100) <= 0;

  return (
    <Link
      to={`/product/${product.id}`}
      data-testid={`product-card-${product.id}`}
      className="js-card overflow-hidden flex flex-col group cursor-pointer hover:-translate-y-1 hover:shadow-xl transition-all duration-300"
    >
      <div className="aspect-[4/3] overflow-hidden bg-[var(--js-subtle)] relative">
        <img
          src={product.image_url}
          alt={product.name}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          loading="lazy"
        />

        {/* Badges */}
        <div className="absolute top-3 left-3 flex flex-col gap-1.5">
          {isWholesale && (
            <span data-testid={`badge-wholesale-${product.id}`} className="bg-[#2D6A4F] text-white text-[10px] font-bold px-2 py-1 rounded-full shadow-md">
              🟢 Wholesale
            </span>
          )}
          {outOfStock && (
            <span data-testid={`badge-out-${product.id}`} className="bg-[#A3A39E] text-white text-[10px] font-bold px-2 py-1 rounded-full shadow-md">
              Out of stock
            </span>
          )}
          {!outOfStock && lowStock && (
            <span data-testid={`badge-lowstock-${product.id}`} className="bg-[#D90429] text-white text-[10px] font-bold px-2 py-1 rounded-full shadow-md">
              🔴 Low Stock
            </span>
          )}
        </div>

        {user?.role === "customer" && (
          <button
            onClick={toggleFav}
            data-testid={`fav-toggle-${product.id}`}
            className="absolute top-3 right-3 bg-white/90 backdrop-blur rounded-full p-2 hover:bg-white transition shadow"
          >
            <Heart className={`w-4 h-4 ${fav ? "fill-[#C84B31] text-[#C84B31]" : "text-[var(--js-text)]"}`} />
          </button>
        )}
      </div>

      <div className="p-4 flex flex-col flex-1">
        <h3 className="font-display font-semibold text-base text-[var(--js-text)] leading-snug line-clamp-2">{product.name}</h3>
        {shop && (
          <p className="text-xs text-[var(--js-text-secondary)] mt-1 truncate">{shop.name}</p>
        )}

        {/* Iter 27 — Live promo pricing. Backend also recomputes at
            checkout so the customer is charged what they see here. */}
        {(() => {
          const p = product.promo || {};
          const now = new Date().toISOString();
          const promoLive = !!p.active && (!p.starts_at || now >= p.starts_at) && (!p.ends_at || now <= p.ends_at);
          const effective = !promoLive ? product.price_usd : (
            p.type === "percent"
              ? Math.max(0, product.price_usd * (1 - (p.value || 0) / 100))
              : Math.max(0, product.price_usd - (p.value || 0))
          );
          return (
            <div className="mt-3 flex items-end justify-between gap-2 mt-auto">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <p className="font-display font-bold text-lg text-[var(--js-text)]" data-testid={`product-price-${product.id}`}>
                    {formatPrice(effective, rate, currency)}
                  </p>
                  {promoLive && (
                    <span
                      className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full text-white shadow-[0_2px_6px_rgba(200,75,49,0.35)] bg-gradient-to-r from-[#E14B31] via-[#C84B31] to-[#B23A21]"
                      data-testid={`product-promo-${product.id}`}
                      title={p.ends_at ? `Ends ${new Date(p.ends_at).toLocaleString()}` : "Limited-time promo"}
                    >
                      <span aria-hidden style={{ fontSize: 10 }}>🔥</span>
                      {p.type === "percent" ? `−${Math.round(p.value || 0)}%` : p.type === "amount" ? `−${formatPrice(p.value || 0, rate, currency)}` : `BUY ${p.bogo_min_qty || 2}+ GET 1 FREE`}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-[var(--js-text-secondary)]">
                  {promoLive && (
                    <span className="line-through mr-1">{formatPrice(product.price_usd, rate, currency)}</span>
                  )}
                  ≈ {formatPriceAlt(effective, rate, currency)}
                </p>
              </div>
              <button
                onClick={onAdd}
                disabled={outOfStock}
                data-testid={`add-to-cart-${product.id}`}
                className="shrink-0 inline-flex items-center gap-1.5 bg-[#C84B31] hover:bg-[#A83A23] disabled:bg-[#A3A39E] disabled:cursor-not-allowed text-white text-xs font-bold rounded-full px-3 py-2 transition shadow-sm hover:shadow-md"
              >
                <Plus className="w-3.5 h-3.5" /> Add
              </button>
            </div>
          );
        })()}
      </div>
    </Link>
  );
}
