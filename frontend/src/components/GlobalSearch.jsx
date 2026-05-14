import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Search, X, UtensilsCrossed, Store, Package } from "lucide-react";
import api from "@/lib/api";

/**
 * Header global search — debounced typeahead across restaurants/shops/products.
 *
 * Click on a result navigates to:
 *   - restaurant → /restaurants?focus={id}  (Restaurants page auto-opens the modal)
 *   - shop       → /shop/{id}
 *   - product    → /product/{id}
 */
export default function GlobalSearch() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState({ restaurants: [], shops: [], products: [] });
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef(null);
  const timerRef = useRef(null);

  // Debounced fetch
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!q || q.trim().length < 2) {
      setResults({ restaurants: [], shops: [], products: [] });
      setLoading(false);
      return;
    }
    setLoading(true);
    timerRef.current = setTimeout(() => {
      api.get(`/search?q=${encodeURIComponent(q.trim())}&limit=5`)
        .then((r) => setResults(r.data || { restaurants: [], shops: [], products: [] }))
        .catch(() => setResults({ restaurants: [], shops: [], products: [] }))
        .finally(() => setLoading(false));
    }, 200);
    return () => timerRef.current && clearTimeout(timerRef.current);
  }, [q]);

  // Click-outside to close
  useEffect(() => {
    const onClick = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const go = (path) => {
    setOpen(false);
    setQ("");
    navigate(path);
  };

  const total =
    results.restaurants.length + results.shops.length + results.products.length;
  const showDropdown = open && q.trim().length >= 2;

  return (
    <div className="relative" ref={boxRef} data-testid="global-search">
      <div className="relative">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/60 pointer-events-none" />
        <input
          type="search"
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder="Search restaurants, shops, products…"
          data-testid="global-search-input"
          className="w-full sm:w-56 md:w-64 lg:w-72 bg-white/10 hover:bg-white/15 focus:bg-white/15 border border-white/20 focus:border-white/40 placeholder:text-white/50 text-white text-sm rounded-full pl-9 pr-9 py-2 transition focus:outline-none"
        />
        {q && (
          <button
            onClick={() => { setQ(""); setOpen(false); }}
            data-testid="global-search-clear"
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-white/10"
            title="Clear"
          >
            <X className="w-3.5 h-3.5 text-white/70" />
          </button>
        )}
      </div>

      {showDropdown && (
        <div
          data-testid="global-search-dropdown"
          className="absolute left-0 right-0 mt-2 bg-white rounded-2xl shadow-2xl border border-[var(--js-border)] max-h-[70vh] overflow-y-auto z-50"
        >
          {loading && (
            <p className="p-4 text-sm text-[var(--js-text-secondary)]" data-testid="global-search-loading">
              Searching…
            </p>
          )}

          {!loading && total === 0 && (
            <p className="p-6 text-sm text-center text-[var(--js-text-secondary)]" data-testid="global-search-empty">
              No matches for <span className="font-semibold text-[var(--js-text)]">"{q}"</span>
            </p>
          )}

          {!loading && results.restaurants.length > 0 && (
            <SearchGroup
              icon={UtensilsCrossed}
              title="Restaurants"
              testid="group-restaurants"
            >
              {results.restaurants.map((r) => (
                <SearchRow
                  key={r.id}
                  testid={`search-result-restaurant-${r.id}`}
                  onClick={() => go(`/restaurants?focus=${r.id}`)}
                  imageUrl={r.image_url}
                  title={r.name}
                  subtitle={r.area}
                  badge={r.is_open ? null : "Closed"}
                />
              ))}
            </SearchGroup>
          )}

          {!loading && results.shops.length > 0 && (
            <SearchGroup icon={Store} title="Shops" testid="group-shops">
              {results.shops.map((s) => (
                <SearchRow
                  key={s.id}
                  testid={`search-result-shop-${s.id}`}
                  onClick={() => go(`/shop/${s.id}`)}
                  imageUrl={s.image_url}
                  title={s.name}
                  subtitle={s.area}
                  badge={s.verification === "Verified" ? "✓ Verified" : null}
                />
              ))}
            </SearchGroup>
          )}

          {!loading && results.products.length > 0 && (
            <SearchGroup icon={Package} title="Products" testid="group-products">
              {results.products.map((p) => (
                <SearchRow
                  key={p.id}
                  testid={`search-result-product-${p.id}`}
                  onClick={() => go(`/product/${p.id}`)}
                  imageUrl={p.image_url}
                  title={p.name}
                  subtitle={p.is_wholesale ? "Wholesale" : "Retail"}
                  price={typeof p.price_usd === "number" ? `$${p.price_usd.toFixed(2)}` : null}
                />
              ))}
            </SearchGroup>
          )}
        </div>
      )}
    </div>
  );
}

function SearchGroup({ icon: Icon, title, testid, children }) {
  return (
    <div data-testid={testid}>
      <div className="px-4 pt-3 pb-1 flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-[var(--js-text-secondary)] font-bold">
        <Icon className="w-3 h-3" /> {title}
      </div>
      {children}
    </div>
  );
}

function SearchRow({ testid, onClick, imageUrl, title, subtitle, badge, price }) {
  return (
    <button
      onClick={onClick}
      data-testid={testid}
      className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-[var(--js-subtle)] text-left transition"
    >
      <div className="w-10 h-10 rounded-lg bg-[var(--js-subtle)] overflow-hidden shrink-0">
        {imageUrl ? (
          <img src={imageUrl} alt="" className="w-full h-full object-cover" />
        ) : null}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-[var(--js-text)] truncate">{title}</p>
        {subtitle && <p className="text-xs text-[var(--js-text-secondary)] truncate">{subtitle}</p>}
      </div>
      {price && (
        <span className="text-sm font-bold text-[var(--js-text)] shrink-0">{price}</span>
      )}
      {badge && (
        <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-[var(--js-subtle)] text-[var(--js-text)] shrink-0">
          {badge}
        </span>
      )}
    </button>
  );
}
