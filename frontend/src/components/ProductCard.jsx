import { Plus } from "lucide-react";
import { formatUSD, formatSSP } from "@/lib/api";
import { useCart } from "@/context/CartContext";
import { toast } from "sonner";

export default function ProductCard({ product, shop }) {
  const { addItem, exchangeRate } = useCart();

  const onAdd = () => {
    addItem({
      item_type: "product",
      item_id: product.id,
      name: product.name,
      price_usd: product.price_usd,
      image_url: product.image_url,
      quantity: 1,
    });
    toast.success(`${product.name} added to cart`);
  };

  return (
    <div
      data-testid={`product-card-${product.id}`}
      className="js-card overflow-hidden flex flex-col group"
    >
      <div className="aspect-[4/3] overflow-hidden bg-[#F2EBE5]">
        <img
          src={product.image_url}
          alt={product.name}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          loading="lazy"
        />
      </div>
      <div className="p-4 flex flex-col flex-1">
        <p className="text-[10px] uppercase tracking-[0.18em] text-[#5C5C5C] font-bold mb-1">
          {product.category}
        </p>
        <h3 className="font-display font-semibold text-base text-[#1A1A1A] leading-snug" data-testid="product-name">
          {product.name}
        </h3>
        {shop && (
          <p className="text-xs text-[#5C5C5C] mt-1">from {shop.name}</p>
        )}
        <div className="mt-3 flex items-end justify-between gap-2">
          <div>
            <p className="font-display font-bold text-lg text-[#1A1A1A]" data-testid="product-price-usd">
              {formatUSD(product.price_usd)}
            </p>
            <p className="text-xs text-[#5C5C5C]" data-testid="product-price-ssp">
              {formatSSP(product.price_usd, exchangeRate)}
            </p>
          </div>
          <button
            onClick={onAdd}
            data-testid={`add-to-cart-${product.id}`}
            className="bg-[#1A1A1A] hover:bg-[#C84B31] text-white rounded-full p-2.5 transition-colors"
            aria-label="Add to cart"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
