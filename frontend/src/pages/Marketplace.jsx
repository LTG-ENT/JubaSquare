import { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import ProductCard from "@/components/ProductCard";
import AreaSelector from "@/components/AreaSelector";
import { useCart } from "@/context/CartContext";
import { Search, X } from "lucide-react";

export default function Marketplace() {
  const [products, setProducts] = useState([]);
  const [shops, setShops] = useState([]);
  const [search, setSearch] = useState("");
  const [searchParams, setSearchParams] = useSearchParams();
  const { area, setArea } = useCart();

  const selectedCategory = searchParams.get("category") || "";
  const selectedShop = searchParams.get("shop") || "";

  useEffect(() => {
    api.get("/shops").then((r) => setShops(r.data));
  }, []);

  useEffect(() => {
    const params = {};
    if (selectedCategory) params.category = selectedCategory;
    if (selectedShop) params.shop_id = selectedShop;
    api.get("/products", { params }).then((r) => setProducts(r.data));
  }, [selectedCategory, selectedShop]);

  const categories = useMemo(() => [...new Set(shops.map((s) => s.category))], [shops]);

  const filtered = products.filter((p) => {
    if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const shopForProduct = (p) => shops.find((s) => s.id === p.shop_id);
  const activeShop = selectedShop ? shops.find((s) => s.id === selectedShop) : null;

  const setCategory = (cat) => {
    const next = new URLSearchParams(searchParams);
    if (cat) next.set("category", cat);
    else next.delete("category");
    next.delete("shop");
    setSearchParams(next);
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-8">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold mb-2">Marketplace</p>
            <h1 className="font-display font-bold text-3xl sm:text-4xl lg:text-5xl text-[#1A1A1A]">
              {activeShop ? activeShop.name : "All Products"}
            </h1>
            {activeShop && <p className="text-sm text-[#5C5C5C] mt-1">{activeShop.description}</p>}
          </div>
          <AreaSelector value={area} onChange={setArea} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-8">
          {/* Sidebar */}
          <aside className="space-y-6">
            <div>
              <div className="relative">
                <Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-[#5C5C5C]" />
                <input
                  data-testid="marketplace-search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search products..."
                  className="w-full bg-white border border-[#E2E2D9] rounded-full pl-11 pr-4 py-2.5 text-sm focus:outline-none focus:border-[#C84B31]"
                />
              </div>
            </div>

            <div>
              <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold mb-3">Categories</p>
              <div className="flex flex-col gap-1">
                <button
                  onClick={() => setCategory("")}
                  data-testid="category-all"
                  className={`text-left px-3 py-2 rounded-xl text-sm font-medium transition ${
                    !selectedCategory ? "bg-[#1A1A1A] text-white" : "text-[#1A1A1A] hover:bg-[#F2EBE5]"
                  }`}
                >
                  All categories
                </button>
                {categories.map((c) => (
                  <button
                    key={c}
                    onClick={() => setCategory(c)}
                    data-testid={`category-filter-${c.replace(/\s+/g, "-").toLowerCase()}`}
                    className={`text-left px-3 py-2 rounded-xl text-sm font-medium transition ${
                      selectedCategory === c ? "bg-[#1A1A1A] text-white" : "text-[#1A1A1A] hover:bg-[#F2EBE5]"
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>

            {(selectedCategory || selectedShop || search) && (
              <button
                onClick={() => { setSearchParams({}); setSearch(""); }}
                data-testid="clear-filters"
                className="text-xs text-[#C84B31] font-bold flex items-center gap-1 hover:underline"
              >
                <X className="w-3 h-3" /> Clear filters
              </button>
            )}
          </aside>

          {/* Grid */}
          <div>
            {filtered.length === 0 ? (
              <div className="text-center py-20 text-[#5C5C5C]" data-testid="empty-products">
                No products found.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {filtered.map((p) => (
                  <ProductCard key={p.id} product={p} shop={shopForProduct(p)} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
