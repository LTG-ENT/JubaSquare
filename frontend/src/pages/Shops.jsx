import { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import api from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import ShopCard from "@/components/ShopCard";
import AreaSelector from "@/components/AreaSelector";
import { useCart } from "@/context/CartContext";
import { Search, Store } from "lucide-react";

export default function Shops() {
  const { t } = useTranslation();
  const [shops, setShops] = useState([]);
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState("");
  const [activeCat, setActiveCat] = useState("All");
  const { area, setArea } = useCart();

  useEffect(() => {
    api.get("/shops?limit=200").then((r) => setShops(r.data));
    api.get("/products?limit=200").then((r) => setProducts(r.data));
  }, []);

  // Get unique categories from products (not shops)
  const cats = useMemo(() => {
    const allCategories = products.map(p => {
      // Extract parent category from "Parent > Sub" format
      if (p.category && p.category.includes(" > ")) {
        return p.category.split(" > ")[0];
      }
      return p.category;
    }).filter(Boolean);
    return ["All", ...new Set(allCategories)];
  }, [products]);

  const productsByShop = (shopId) => products.filter((p) => p.shop_id === shopId).slice(0, 4);

  // Filter shops based on products' categories
  const filtered = shops.filter((s) => {
    // If a category is selected, only show shops that have products in that category
    if (activeCat !== "All") {
      const shopProducts = products.filter(p => p.shop_id === s.id);
      const hasCategory = shopProducts.some(p => {
        if (p.category && p.category.includes(" > ")) {
          return p.category.split(" > ")[0] === activeCat;
        }
        return p.category === activeCat;
      });
      if (!hasCategory) return false;
    }
    if (search && !s.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-8">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--js-text-secondary)] font-bold mb-2">{t("shops")}</p>
            <h1 className="font-display font-bold text-3xl sm:text-4xl lg:text-5xl text-[var(--js-text)]">
              {t("allShopsInJuba")}
            </h1>
            <p className="text-sm text-[var(--js-text-secondary)] mt-2">
              {t("browseShopsSubtitle", { count: shops.length })}
            </p>
          </div>
          <AreaSelector value={area} onChange={setArea} />
        </div>

        {/* Sticky search bar */}
        <div className="sticky top-16 z-30 bg-[var(--js-bg)]/95 backdrop-blur-md py-3 -mx-4 px-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8 mb-4 border-b border-[var(--js-border)]">
          <div className="relative max-w-2xl">
            <Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-[var(--js-text-secondary)]" />
            <input
              data-testid="shops-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search shops by name..."
              className="w-full bg-white border border-[var(--js-border)] rounded-full pl-11 pr-4 py-2.5 text-sm focus:outline-none focus:border-[#C84B31] shadow-sm"
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mb-8">
          {cats.map((c) => (
            <button
              key={c}
              onClick={() => setActiveCat(c)}
              data-testid={`shops-cat-${c.replace(/\s+/g, "-").toLowerCase()}`}
              className={`px-4 py-2 rounded-full text-sm font-semibold transition ${
                activeCat === c
                  ? "bg-[#C84B31] text-white"
                  : "bg-white border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#C84B31]"
              }`}
            >
              {c}
            </button>
          ))}
        </div>

        {filtered.length === 0 ? (
          <div className="text-center py-20 text-[var(--js-text-secondary)]" data-testid="empty-shops">
            <Store className="w-12 h-12 mx-auto opacity-40" />
            <p className="mt-3">No shops found.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {filtered.map((s) => <ShopCard key={s.id} shop={s} productsPreview={productsByShop(s.id)} />)}
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
