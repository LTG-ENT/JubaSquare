import { useState } from "react";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import { formatPrice, formatPriceAlt } from "@/lib/api";
import { useCart } from "@/context/CartContext";
import { toast } from "sonner";

export default function WholesaleCard({ product, shop }) {
  const { addItem, exchangeRate, currency } = useCart();
  const [qty, setQty] = useState(product.min_order_qty || 1);
  const rate = product.exchange_rate_ssp || exchangeRate;

  const meetsMin = qty >= (product.min_order_qty || 1);
  const usesBulk = !!product.bulk_price_usd && meetsMin;
  const unitPrice = usesBulk ? product.bulk_price_usd : product.price_usd;

  const onAdd = (e) => {
    e.preventDefault(); e.stopPropagation();
    if (!meetsMin) {
      toast.error(`Minimum order quantity is ${product.min_order_qty}`);
      return;
    }
    const ok = addItem({
      item_type: "product",
      item_id: product.id,
      name: product.name,
      price_usd: unitPrice,
      image_url: product.image_url,
      quantity: qty,
    });
    if (ok) toast.success(`${qty}× ${product.name} added`);
  };

  return (
    <Link
      to={`/product/${product.id}`}
      data-testid={`wholesale-card-${product.id}`}
      className="js-card overflow-hidden flex flex-col cursor-pointer hover:-translate-y-1 hover:shadow-xl transition-all duration-300 group"
    >
      <div className="aspect-[4/3] overflow-hidden bg-[var(--js-subtle)] relative">
        <img src={product.image_url} alt={product.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" loading="lazy" />
        <span className="absolute top-3 left-3 bg-[#2D6A4F] text-white text-[10px] font-bold px-2 py-1 rounded-full shadow-md">
          🟢 Wholesale
        </span>
        {shop?.verification === "Verified" && (
          <span className="absolute top-3 right-3 bg-white/95 text-[#2D6A4F] text-[10px] font-bold px-2 py-1 rounded-full shadow">✓ Verified</span>
        )}
      </div>
      <div className="p-4 flex flex-col flex-1">
        <h3 className="font-display font-semibold text-base text-[var(--js-text)] leading-snug line-clamp-2">{product.name}</h3>
        {shop && <p className="text-xs text-[var(--js-text-secondary)] mt-0.5 truncate">{shop.name}</p>}

        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div className="bg-[var(--js-subtle)] rounded-lg p-2">
            <p className="text-[var(--js-text-secondary)]">Min Qty</p>
            <p className="font-bold text-[var(--js-text)]" data-testid="min-qty">{product.min_order_qty}</p>
          </div>
          <div className="bg-[#2D6A4F]/10 rounded-lg p-2">
            <p className="text-[#2D6A4F]">Bulk price</p>
            <p className="font-bold text-[#2D6A4F]">{product.bulk_price_usd ? formatPrice(product.bulk_price_usd, rate, currency) : "—"}</p>
          </div>
        </div>

        <div className="mt-3 flex items-end justify-between gap-2">
          <div>
            <p className="font-display font-bold text-lg text-[var(--js-text)]">
              {formatPrice(unitPrice, rate, currency)}
              {usesBulk && <span className="text-xs text-[#2D6A4F] ml-1">bulk</span>}
            </p>
            <p className="text-[11px] text-[var(--js-text-secondary)]">≈ {formatPriceAlt(unitPrice, rate, currency)} / unit</p>
          </div>
        </div>

        <div className="mt-3 flex items-center gap-2" onClick={(e) => e.preventDefault()}>
          <input
            type="number" min={product.min_order_qty || 1}
            value={qty} onChange={(e) => setQty(parseInt(e.target.value) || 1)}
            onClick={(e) => e.stopPropagation()}
            data-testid={`wholesale-qty-${product.id}`}
            className="js-input flex-1 py-2 text-sm"
          />
          <button onClick={onAdd} data-testid={`wholesale-add-${product.id}`} className="bg-[#C84B31] hover:bg-[#A83A23] text-white text-xs font-bold rounded-full px-3 py-2 inline-flex items-center gap-1 transition">
            <Plus className="w-3.5 h-3.5" /> Add
          </button>
        </div>
      </div>
    </Link>
  );
}
