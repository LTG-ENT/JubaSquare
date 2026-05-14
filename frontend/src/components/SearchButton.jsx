import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Search, X, UtensilsCrossed, Store, Package } from "lucide-react";
import api from "@/lib/api";

/**
 * Compact search button that opens a modal with full search functionality
 */
export default function SearchButton() {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [q, setQ] = useState("");
  const [results, setResults] = useState({ restaurants: [], shops: [], products: [] });
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
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

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Close on Escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === "Escape") setIsOpen(false);
    };
    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      return () => document.removeEventListener("keydown", handleEscape);
    }
  }, [isOpen]);

  const go = (path) => {
    navigate(path);
    setIsOpen(false);
    setQ("");
  };

  const totalCount = results.restaurants.length + results.shops.length + results.products.length;

  return (
    <>
      {/* Search Icon Button */}
      <button
        onClick={() => setIsOpen(true)}
        data-testid="search-button"
        className="p-2 rounded-full hover:bg-white/10 transition"
        title="Search"
      >
        <Search className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
      </button>

      {/* Search Modal */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-2xl mx-4 mt-20 bg-white rounded-2xl shadow-2xl overflow-hidden">
            {/* Search Input */}
            <div className="relative border-b border-[var(--js-border)]">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[var(--js-text-secondary)]" />
              <input
                ref={inputRef}
                type="search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search restaurants, shops, products…"
                data-testid="search-modal-input"
                className="w-full pl-12 pr-12 py-4 text-base text-[var(--js-text)] placeholder:text-[var(--js-text-secondary)] focus:outline-none"
              />
              <button
                onClick={() => setIsOpen(false)}
                className="absolute right-4 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-[var(--js-subtle)] transition"
              >
                <X className="w-5 h-5 text-[var(--js-text-secondary)]" />
              </button>
            </div>

            {/* Results */}
            <div className="max-h-[60vh] overflow-y-auto">
              {loading && (
                <div className="p-8 text-center text-[var(--js-text-secondary)]">
                  Searching...
                </div>
              )}

              {!loading && q.trim().length >= 2 && totalCount === 0 && (
                <div className="p-8 text-center text-[var(--js-text-secondary)]">
                  No results found for "{q}"
                </div>
              )}

              {!loading && totalCount > 0 && (
                <div className="p-2">
                  {/* Restaurants */}
                  {results.restaurants.length > 0 && (
                    <div className="mb-4">
                      <div className="px-3 py-2 text-xs uppercase font-bold text-[var(--js-text-secondary)] tracking-wider">
                        Restaurants
                      </div>
                      {results.restaurants.map((r) => (
                        <button
                          key={r.id}
                          onClick={() => go(`/restaurants?focus=${r.id}`)}
                          className="w-full flex items-center gap-3 px-3 py-3 hover:bg-[var(--js-subtle)] rounded-lg transition text-left"
                        >
                          <div className="w-10 h-10 rounded-full bg-[#C84B31]/10 flex items-center justify-center shrink-0">
                            <UtensilsCrossed className="w-5 h-5 text-[#C84B31]" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="font-semibold text-[var(--js-text)] truncate">{r.name}</p>
                            {r.cuisine && (
                              <p className="text-sm text-[var(--js-text-secondary)] truncate">{r.cuisine}</p>
                            )}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Shops */}
                  {results.shops.length > 0 && (
                    <div className="mb-4">
                      <div className="px-3 py-2 text-xs uppercase font-bold text-[var(--js-text-secondary)] tracking-wider">
                        Shops
                      </div>
                      {results.shops.map((s) => (
                        <button
                          key={s.id}
                          onClick={() => go(`/shop/${s.id}`)}
                          className="w-full flex items-center gap-3 px-3 py-3 hover:bg-[var(--js-subtle)] rounded-lg transition text-left"
                        >
                          <div className="w-10 h-10 rounded-full bg-[#2A9D8F]/10 flex items-center justify-center shrink-0">
                            <Store className="w-5 h-5 text-[#2A9D8F]" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="font-semibold text-[var(--js-text)] truncate">{s.name}</p>
                            {s.category && (
                              <p className="text-sm text-[var(--js-text-secondary)] truncate">{s.category}</p>
                            )}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Products */}
                  {results.products.length > 0 && (
                    <div className="mb-4">
                      <div className="px-3 py-2 text-xs uppercase font-bold text-[var(--js-text-secondary)] tracking-wider">
                        Products
                      </div>
                      {results.products.map((p) => (
                        <button
                          key={p.id}
                          onClick={() => go(`/product/${p.id}`)}
                          className="w-full flex items-center gap-3 px-3 py-3 hover:bg-[var(--js-subtle)] rounded-lg transition text-left"
                        >
                          <div className="w-10 h-10 rounded-full bg-[#E9C46A]/20 flex items-center justify-center shrink-0">
                            <Package className="w-5 h-5 text-[#E9C46A]" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="font-semibold text-[var(--js-text)] truncate">{p.name}</p>
                            {p.shop_name && (
                              <p className="text-sm text-[var(--js-text-secondary)] truncate">from {p.shop_name}</p>
                            )}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Hint when empty */}
              {!loading && q.trim().length < 2 && (
                <div className="p-8 text-center text-[var(--js-text-secondary)]">
                  Type at least 2 characters to search
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
