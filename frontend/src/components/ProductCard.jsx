import { useEffect, useState } from "react";
import { Plus, Heart } from "lucide-react";
import { formatUSD, formatSSP } from "@/lib/api";
import api from "@/lib/api";
import { useCart } from "@/context/CartContext";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

export default function ProductCard({ product, shop }) {
  const { addItem, exchangeRate } = useCart();
  const { user } = useAuth();
  const [fav, setFav] = useState(false);

  useEffect(() => {
    if (!user || user.role !== "customer") return;
    api.get("/favorites").then((r) => {
      setFav(!!r.data.find((f) => f.target_type === "product" && f.target_id === product.id));
    }).catch(() => {});
  }, [user, product.id]);

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

  return (
    <div data-testid={`product-card-${product.id}`} className="js-card overflow-hidden flex flex-col group">
      <div className="aspect-[4/3] overflow-hidden bg-[var(--js-subtle)] relative">
        <img src={product.image_url} alt={product.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" loading="lazy" />
        {user?.role === "customer" && (
          <button onClick={toggleFav} data-testid={`fav-toggle-${product.id}`} className="absolute top-3 right-3 bg-white/90 backdrop-blur rounded-full p-2 hover:bg-white transition">
            <Heart className={`w-4 h-4 ${fav ? "fill-[#C84B31] text-[#C84B31]" : "text-[var(--js-text)]"}`} />
          </button>
        )}
      </div>
      <div className="p-4 flex flex-col flex-1">
        <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--js-text-secondary)] font-bold mb-1">{product.category}</p>
        <h3 className="font-display font-semibold text-base text-[var(--js-text)] leading-snug">{product.name}</h3>
        {shop && <p className="text-xs text-[var(--js-text-secondary)] mt-1">from {shop.name}</p>}
        <div className="mt-3 flex items-end justify-between gap-2">
          <div>
            <p className="font-display font-bold text-lg text-[var(--js-text)]" data-testid="product-price-usd">{formatUSD(product.price_usd)}</p>
            <p className="text-xs text-[var(--js-text-secondary)]" data-testid="product-price-ssp">{formatSSP(product.price_usd, exchangeRate)}</p>
          </div>
          <button onClick={onAdd} data-testid={`add-to-cart-${product.id}`} className="bg-[#1A1A1A] hover:bg-[#C84B31] text-white rounded-full p-2.5 transition-colors">
            <Plus className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
