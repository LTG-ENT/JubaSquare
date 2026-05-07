import { useEffect, useState, useMemo } from "react";
import api from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import WholesaleCard from "@/components/WholesaleCard";
import AreaSelector from "@/components/AreaSelector";
import { useCart } from "@/context/CartContext";
import { Search, Package } from "lucide-react";

export default function Wholesale() {
  const [products, setProducts] = useState([]);
  const [shops, setShops] = useState([]);
  const [search, setSearch] = useState("");
  const [activeCat, setActiveCat] = useState("All");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const { area, setArea } = useCart();

  useEffect(() => {
    api.get("/shops?kind=wholesale&limit=200").then((r) => setShops(r.data));
    api.get("/products?kind=wholesale&limit=200").then((r) => setProducts(r.data));
  }, []);

  const cats = useMemo(() => ["All", ...new Set(shops.map((s) => s.category))], [shops]);
  const shopById = useMemo(() => Object.fromEntries(shops.map((s) => [s.id, s])), [shops]);

  const filtered = products.filter((p) => {
    if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false;
    const shop = shopById[p.shop_id];
    if (!shop) return false;
    if (activeCat !== "All" && shop.category !== activeCat) return false;
    if (verifiedOnly && shop.verification !== "Verified") return false;
    return true;
  });

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-8">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--js-text-secondary)] font-bold mb-2 inline-flex items-center gap-2"><Package className="w-3 h-3" /> Wholesale</p>
            <h1 className="font-display font-bold text-3xl sm:text-4xl lg:text-5xl text-[var(--js-text)]">Bulk supply at trade prices.</h1>
            <p className="text-sm text-[var(--js-text-secondary)] mt-2">For retailers, restaurants, and contractors. Mind the minimum order quantity for each item.</p>
          </div>
          <AreaSelector value={area} onChange={setArea} />
        </div>

        <div className="flex flex-wrap items-center gap-3 mb-8">
          <div className="relative flex-1 min-w-[240px]">
            <Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-[var(--js-text-secondary)]" />
            <input
              data-testid="wholesale-search"
              value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Search wholesale products..."
              className="w-full bg-white border border-[var(--js-border)] rounded-full pl-11 pr-4 py-2.5 text-sm focus:outline-none focus:border-[#C84B31]"
            />
          </div>
          <label className="inline-flex items-center gap-2 text-sm font-semibold cursor-pointer" data-testid="verified-only-toggle">
            <span className="js-switch">
              <input type="checkbox" checked={verifiedOnly} onChange={(e) => setVerifiedOnly(e.target.checked)} />
              <span className="slider" />
            </span>
            Verified suppliers only
          </label>
        </div>

        <div className="flex flex-wrap gap-2 mb-8">
          {cats.map((c) => (
            <button
              key={c} onClick={() => setActiveCat(c)}
              data-testid={`wholesale-cat-${c.replace(/\s+/g, "-").toLowerCase()}`}
              className={`px-4 py-2 rounded-full text-sm font-semibold transition ${
                activeCat === c ? "bg-[#C84B31] text-white" : "bg-white border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#C84B31]"
              }`}
            >{c}</button>
          ))}
        </div>

        {filtered.length === 0 ? (
          <p className="text-center py-20 text-[var(--js-text-secondary)]">No wholesale products match your filters.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map((p) => <WholesaleCard key={p.id} product={p} shop={shopById[p.shop_id]} />)}
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
