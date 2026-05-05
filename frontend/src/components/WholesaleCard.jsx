import { useState, useEffect, useMemo } from "react";
import { Plus } from "lucide-react";
import { formatUSD, formatSSP } from "@/lib/api";
import { useCart } from "@/context/CartContext";
import api from "@/lib/api";
import { toast } from "sonner";

export default function WholesaleCard({ product, shop }) {
  const { addItem, exchangeRate } = useCart();
  const [qty, setQty] = useState(product.min_order_qty || 1);

  const meetsMin = qty >= (product.min_order_qty || 1);
  const usesBulk = !!product.bulk_price_usd && meetsMin;
  const unitPrice = usesBulk ? product.bulk_price_usd : product.price_usd;

  const onAdd = () => {
    if (!meetsMin) {
      toast.error(`Minimum order quantity is ${product.min_order_qty}`);
      return;
    }
    addItem({
      item_type: "product",
      item_id: product.id,
      name: product.name,
      price_usd: unitPrice,
      image_url: product.image_url,
      quantity: qty,
    });
    toast.success(`${qty}× ${product.name} added`);
  };

  return (
    <div data-testid={`wholesale-card-${product.id}`} className="js-card overflow-hidden flex flex-col">
      <div className="aspect-[4/3] overflow-hidden bg-[var(--js-subtle)] relative">
        <img src={product.image_url} alt={product.name} className="w-full h-full object-cover hover:scale-105 transition-transform duration-500" loading="lazy" />
        {shop?.verification === "Verified" && (
          <span className="absolute top-3 left-3 bg-[#2D6A4F] text-white text-[10px] font-bold px-2 py-1 rounded-full">✓ Verified Supplier</span>
        )}
      </div>
      <div className="p-4 flex flex-col flex-1">
        <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--js-text-secondary)] font-bold mb-1">{product.category}</p>
        <h3 className="font-display font-semibold text-base text-[var(--js-text)] leading-snug">{product.name}</h3>
        {shop && <p className="text-xs text-[var(--js-text-secondary)] mt-0.5">from {shop.name}</p>}

        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div className="bg-[var(--js-subtle)] rounded-lg p-2">
            <p className="text-[var(--js-text-secondary)]">Min Qty</p>
            <p className="font-bold text-[var(--js-text)]" data-testid="min-qty">{product.min_order_qty}</p>
          </div>
          <div className="bg-[#2D6A4F]/10 rounded-lg p-2">
            <p className="text-[#2D6A4F]">Bulk price</p>
            <p className="font-bold text-[#2D6A4F]">{product.bulk_price_usd ? formatUSD(product.bulk_price_usd) : "—"}</p>
          </div>
        </div>

        <div className="mt-3 flex items-end justify-between gap-2">
          <div>
            <p className="font-display font-bold text-lg text-[var(--js-text)]">{formatUSD(unitPrice)}{usesBulk && <span className="text-xs text-[#2D6A4F] ml-1">bulk</span>}</p>
            <p className="text-xs text-[var(--js-text-secondary)]">{formatSSP(unitPrice, exchangeRate)} / unit</p>
          </div>
        </div>

        <div className="mt-3 flex items-center gap-2">
          <input
            type="number" min={product.min_order_qty || 1}
            value={qty} onChange={(e) => setQty(parseInt(e.target.value) || 1)}
            data-testid={`wholesale-qty-${product.id}`}
            className="js-input flex-1 py-2 text-sm"
          />
          <button onClick={onAdd} data-testid={`wholesale-add-${product.id}`} className="bg-[#1A1A1A] hover:bg-[#C84B31] text-white rounded-full p-2.5 transition-colors">
            <Plus className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
