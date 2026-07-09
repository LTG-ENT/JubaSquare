import { useState, useMemo } from "react";
import { MapPin, X, Plus, Search, Star, Heart } from "lucide-react";
import api, { formatPrice, formatPriceAlt } from "@/lib/api";
import { useCart } from "@/context/CartContext";
import { useAuth } from "@/context/AuthContext";
import { useEffect } from "react";
import { toast } from "sonner";

function MiniCurrencyToggle() {
  const { currency, toggleCurrency } = useCart();
  return (
    <button
      onClick={(e) => { e.stopPropagation(); toggleCurrency(); }}
      data-testid="menu-currency-toggle"
      title={`Switch to ${currency === "SSP" ? "USD" : "SSP"}`}
      className="inline-flex items-center gap-1 bg-[var(--js-subtle)] border border-[var(--js-border)] rounded-full px-1 py-1 text-[10px] font-bold"
    >
      <span
        className={`px-2 py-0.5 rounded-full transition ${
          currency === "SSP" ? "bg-[#E9C46A] text-[#1A1A1A]" : "text-[var(--js-text-secondary)]"
        }`}
        data-testid="menu-currency-ssp"
      >SSP</span>
      <span
        className={`px-2 py-0.5 rounded-full transition ${
          currency === "USD" ? "bg-[#E9C46A] text-[#1A1A1A]" : "text-[var(--js-text-secondary)]"
        }`}
        data-testid="menu-currency-usd"
      >USD</span>
    </button>
  );
}

export default function RestaurantCard({ restaurant, initialOpen = false, rank = null, trendingScore = null }) {
  const [open, setOpen] = useState(initialOpen);
  const [menu, setMenu] = useState([]);
  const [menuCategories, setMenuCategories] = useState([]);  // {id, name}
  const [activeMenuCat, setActiveMenuCat] = useState("all");
  const [search, setSearch] = useState("");
  const [attrSel, setAttrSel] = useState({}); // Iter 33.2 — {attrKey: [values]} menu filters
  const [isFavorite, setIsFavorite] = useState(false);
  const [favoriteId, setFavoriteId] = useState(null);
  const [reviewsOpen, setReviewsOpen] = useState(false);
  const [reviews, setReviews] = useState([]);
  const [reviewsLoading, setReviewsLoading] = useState(false);
  const { addItem, exchangeRate, currency } = useCart();
  const { user } = useAuth();

  useEffect(() => {
    if (open && menu.length === 0) {
      api.get(`/restaurants/${restaurant.id}/menu`).then((r) => {
        const items = r.data || [];
        setMenu(items);
        // Iter 27 — Prefer SELLER-DEFINED sections (max 6) from the
        // restaurant doc itself. These live on `restaurant.menu_sections`
        // and each menu item points to one via `menu_section_id`.
        // Fall back to platform category grouping only if no sections
        // exist (legacy restaurants).
        const sellerSections = (restaurant.menu_sections || [])
          .slice()
          .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
        // Iter 30 Wave 2 — hide empty promo sections from the tab bar.
        // A promo section is only shown when there's at least one menu
        // item that currently has a live promo.
        const nowIso = new Date().toISOString();
        const promoLive = (m) => {
          const p = m.promo || {};
          if (!p.active) return false;
          if (p.starts_at && nowIso < p.starts_at) return false;
          if (p.ends_at && nowIso > p.ends_at) return false;
          return true;
        };
        const anyLivePromoInList = items.some(promoLive);
        const visibleSellerSections = sellerSections.filter(
          (s) => !s.is_promo_section || anyLivePromoInList
        );
        if (sellerSections.length) {
          setMenuCategories(visibleSellerSections.map((s) => ({ id: s.id, name: s.name })));
          return;
        }
        const catIds = Array.from(new Set(items.map((m) => m.category_id).filter(Boolean)));
        if (catIds.length) {
          api.get("/categories/tree?group=restaurant").then((cr) => {
            const flat = [];
            const walk = (nodes) => (nodes || []).forEach((n) => { flat.push({ id: n.id, name: n.name }); walk(n.children); });
            walk(cr.data || []);
            const byId = Object.fromEntries(flat.map((c) => [c.id, c.name]));
            setMenuCategories(catIds.map((id) => ({ id, name: byId[id] || "Other" })));
          }).catch(() => {
            setMenuCategories(catIds.map((id) => ({ id, name: "Menu" })));
          });
        }
      });
    }
  }, [open, restaurant.id, menu.length, restaurant.menu_sections]);
  
  // Check if restaurant is favorited
  useEffect(() => {
    if (user) {
      api.get("/favorites").then((r) => {
        const fav = r.data.find(f => f.target_type === "restaurant" && f.target_id === restaurant.id);
        if (fav) {
          setIsFavorite(true);
          setFavoriteId(fav.favorite_id);
        }
      }).catch(() => {});
    }
  }, [user, restaurant.id]);
  
  const toggleFavorite = async (e) => {
    e.stopPropagation();
    
    if (!user) {
      toast.error("Please login to save favorites");
      return;
    }
    
    try {
      if (isFavorite && favoriteId) {
        await api.delete(`/favorites/${favoriteId}`);
        setIsFavorite(false);
        setFavoriteId(null);
        toast.success("Removed from favorites");
      } else {
        const { data } = await api.post("/favorites", {
          target_type: "restaurant",
          target_id: restaurant.id
        });
        setIsFavorite(true);
        setFavoriteId(data.id);
        toast.success("Added to favorites");
      }
    } catch (err) {
      toast.error("Failed to update favorites");
    }
  };
  
  // Track click for trending
  const handleCardClick = () => {
    api.post("/trending/click", {
      target_type: "restaurant",
      target_id: restaurant.id
    }).catch(() => {});
    
    setOpen(true);
  };

  // Iter 33.2 — attribute filter chips derived from the menu items themselves
  // (no extra API call): distinct values per attribute key.
  const menuFacets = useMemo(() => {
    const map = new Map();
    menu.forEach((m) => {
      Object.entries(m.attributes || {}).forEach(([k, v]) => {
        const vals = Array.isArray(v) ? v : [v];
        vals.forEach((val) => {
          if (val === "" || val == null) return;
          if (!map.has(k)) map.set(k, new Set());
          map.get(k).add(String(val));
        });
      });
    });
    return [...map.entries()].map(([k, set]) => ({
      key: k,
      name: k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      values: [...set].sort(),
    }));
  }, [menu]);

  // Iter 27 — When the restaurant has seller-defined sections, filter by
  // menu_section_id (fall back to category_id on legacy items).
  const useSellerSections = (restaurant.menu_sections || []).length > 0;
  const filteredMenu = menu.filter((m) => {
    if (search && !m.name.toLowerCase().includes(search.toLowerCase())) return false;
    // Iter 33.2 — attribute chip filters (AND across keys, OR within a key)
    for (const [k, vals] of Object.entries(attrSel)) {
      if (!vals.length) continue;
      const v = (m.attributes || {})[k];
      const list = Array.isArray(v) ? v : v != null ? [v] : [];
      if (!vals.some((x) => list.map(String).includes(x))) return false;
    }
    if (activeMenuCat === "all") return true;
    if (useSellerSections) return m.menu_section_id === activeMenuCat;
    return m.category_id === activeMenuCat;
  });

  // Group filtered items by category so the drawer shows section headers.
  // Iter 28 — sections flagged `is_promo_section` are auto-populated with
  // items that currently have a LIVE promo. Hidden when no live promos.
  const nowIsoForGrouping = new Date().toISOString();
  const hasLivePromo = (m) => {
    const pr = m.promo || {};
    if (!pr.active) return false;
    if (pr.starts_at && nowIsoForGrouping < pr.starts_at) return false;
    if (pr.ends_at && nowIsoForGrouping > pr.ends_at) return false;
    return true;
  };
  const groupedMenu = useMemo(() => {
    // Promo-section case: if the active category IS a promo section, only
    // items with live promos.
    if (activeMenuCat !== "all") {
      const activeSection = (restaurant.menu_sections || []).find((s) => s.id === activeMenuCat);
      if (activeSection?.is_promo_section) {
        return [{ cat: activeSection, items: filteredMenu.filter(hasLivePromo) }];
      }
      return [{
        cat: menuCategories.find((c) => c.id === activeMenuCat) || { id: activeMenuCat, name: "Menu" },
        items: filteredMenu,
      }];
    }
    const buckets = new Map();
    filteredMenu.forEach((m) => {
      const key = (useSellerSections ? m.menu_section_id : m.category_id) || "_uncat";
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(m);
    });
    const rows = [];
    menuCategories.forEach((c) => {
      // Look up the raw seller-section to check the is_promo_section flag.
      const sellerSection = (restaurant.menu_sections || []).find((s) => s.id === c.id);
      if (sellerSection?.is_promo_section) {
        const promoItems = filteredMenu.filter(hasLivePromo);
        if (promoItems.length) rows.push({ cat: c, items: promoItems });
        return;
      }
      const items = buckets.get(c.id);
      if (items && items.length) rows.push({ cat: c, items });
    });
    if (buckets.has("_uncat")) {
      rows.push({ cat: { id: "_uncat", name: "Other" }, items: buckets.get("_uncat") });
    }
    return rows;
  }, [filteredMenu, menuCategories, activeMenuCat, useSellerSections, restaurant.menu_sections]);

  const addMenu = (item, sides) => {
    const success = addItem({
      item_type: "menu_item", item_id: item.id, name: item.name,
      price_usd: item.price_usd, image_url: item.image_url, quantity: 1,
      sides: sides || [],
      exchange_rate_ssp: item.exchange_rate_ssp, // Preserve seller's exchange rate
    }, {
      restaurant_id: restaurant.id,
      restaurant_name: restaurant.name,
    });
    
    if (success) {
      toast.success(`${item.name} added to cart`);
    }
  };

  return (
    <>
      <div data-testid={`restaurant-card-${restaurant.id}`} className="js-card overflow-hidden flex flex-col group cursor-pointer" onClick={handleCardClick}>
        <div className="aspect-[16/10] overflow-hidden bg-[var(--js-subtle)] relative">
          <img src={restaurant.image_url} alt={restaurant.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" loading="lazy" />
          <div className="absolute top-3 left-3 flex items-center gap-2">
            <span data-testid={`restaurant-status-${restaurant.id}`} className={`text-xs font-bold px-3 py-1 rounded-full shadow-md ${restaurant.is_open ? "bg-[#2D6A4F] text-white" : "bg-[#A3A39E] text-white"}`}>
              {restaurant.is_open ? "● Open" : "● Closed"}
            </span>
            {restaurant.is_ltg_partner && (
              <span
                data-testid={`restaurant-ltg-${restaurant.id}`}
                className="text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded-full text-white shadow-lg bg-gradient-to-r from-[#D4AF37] via-[#E9C46A] to-[#B8860B]"
                title="Part of LTG"
              >
                ★ PART OF LTG
              </span>
            )}
            {restaurant.has_live_promo && (
              <span
                data-testid={`restaurant-deals-${restaurant.id}`}
                className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded-full text-white shadow-[0_2px_8px_rgba(200,75,49,0.45)] bg-gradient-to-r from-[#E14B31] via-[#C84B31] to-[#B23A21]"
                title="This restaurant has active promos"
              >
                <span aria-hidden style={{ fontSize: 10 }}>🔥</span>DEALS
              </span>
            )}
          </div>
          {/* Heart Icon for Favorites */}
          <button
            onClick={toggleFavorite}
            className="absolute top-3 right-3 w-10 h-10 rounded-full bg-white/90 backdrop-blur-sm hover:bg-white flex items-center justify-center transition shadow-lg z-10"
            title={isFavorite ? "Remove from favorites" : "Add to favorites"}
          >
            <Heart 
              className={`w-5 h-5 transition ${
                isFavorite 
                  ? "fill-red-500 text-red-500" 
                  : "text-gray-600"
              }`}
            />
          </button>
          {/* Trending rank badge — positioned at the bottom-right of the image */}
          {rank != null && (
            <div
              data-testid={`trending-rank-${restaurant.id}`}
              className="absolute bottom-3 right-3 z-10 inline-flex items-center gap-1 bg-[#1A1A1A]/90 backdrop-blur text-white text-[11px] font-bold px-2.5 py-1 rounded-full shadow-md"
            >
              #{rank}
              {trendingScore != null && (
                <span className="ml-1 text-[#E9C46A]">★ {trendingScore}</span>
              )}
            </div>
          )}
        </div>
        <div className="p-4">
          <h3 className="font-display font-semibold text-lg text-[var(--js-text)]">{restaurant.name}</h3>
          <p className="text-sm text-[var(--js-text-secondary)] mt-1 line-clamp-2">{restaurant.description}</p>
          <div className="mt-3 flex items-center gap-3 text-xs text-[var(--js-text-secondary)]">
            <div className="flex items-center gap-1">
              <MapPin className="w-3 h-3" /> {restaurant.area}
            </div>
            {restaurant.average_rating ? (
              <div className="flex items-center gap-1" data-testid={`restaurant-rating-${restaurant.id}`}>
                <Star className="w-3.5 h-3.5 fill-[#E9C46A] text-[#E9C46A]" />
                <span className="font-semibold text-[var(--js-text)]">{restaurant.average_rating}</span>
                <span className="text-[var(--js-text-secondary)]">({restaurant.review_count || 0})</span>
              </div>
            ) : (
              <div className="flex items-center gap-1 text-[var(--js-text-secondary)]" data-testid={`restaurant-no-reviews-${restaurant.id}`}>
                <Star className="w-3.5 h-3.5 text-[var(--js-text-secondary)]" />
                <span className="italic">No reviews yet</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {open && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={() => setOpen(false)} data-testid={`restaurant-modal-${restaurant.id}`}>
          <div className="bg-white rounded-t-3xl sm:rounded-3xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="aspect-[16/8] overflow-hidden relative">
              <img src={restaurant.image_url} alt={restaurant.name} loading="lazy" className="w-full h-full object-cover" />
              <button onClick={() => setOpen(false)} className="absolute top-4 right-4 bg-white/90 backdrop-blur rounded-full p-2 hover:bg-white" data-testid="close-restaurant-modal">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h2 className="font-display font-bold text-2xl text-[var(--js-text)]">{restaurant.name}</h2>
                  <p className="text-sm text-[var(--js-text-secondary)] mt-1">📍 {restaurant.area}</p>
                  {/* Clickable rating chip */}
                  <button
                    type="button"
                    onClick={() => {
                      const next = !reviewsOpen;
                      setReviewsOpen(next);
                      if (next && reviews.length === 0 && !reviewsLoading) {
                        setReviewsLoading(true);
                        api.get(`/reviews?restaurant_id=${restaurant.id}&limit=20`)
                          .then((r) => setReviews(Array.isArray(r.data) ? r.data : []))
                          .catch(() => setReviews([]))
                          .finally(() => setReviewsLoading(false));
                      }
                    }}
                    data-testid={`open-restaurant-reviews-${restaurant.id}`}
                    className="mt-2 inline-flex items-center gap-2 text-sm font-semibold text-[var(--js-text)] hover:text-[#C84B31] transition"
                  >
                    {restaurant.average_rating ? (
                      <>
                        <Star className="w-4 h-4 fill-[#E9C46A] text-[#E9C46A]" />
                        <span>{restaurant.average_rating}</span>
                        <span className="text-[var(--js-text-secondary)]">({restaurant.review_count || 0} {restaurant.review_count === 1 ? "review" : "reviews"})</span>
                      </>
                    ) : (
                      <>
                        <Star className="w-4 h-4 text-[var(--js-text-secondary)]" />
                        <span className="italic text-[var(--js-text-secondary)] font-normal">No reviews yet</span>
                      </>
                    )}
                    <span className="text-[11px] text-[#C84B31] underline-offset-2 hover:underline">
                      {reviewsOpen ? "Hide" : (restaurant.review_count ? "View" : "")}
                    </span>
                  </button>
                </div>
                <span className={`text-xs font-bold px-3 py-1 rounded-full shrink-0 ${restaurant.is_open ? "bg-[#2D6A4F] text-white" : "bg-[#A3A39E] text-white"}`}>
                  {restaurant.is_open ? "Open" : "Closed"}
                </span>
              </div>

              {/* Reviews panel — appears below the header when the rating chip is clicked */}
              {reviewsOpen && (
                <div data-testid={`restaurant-reviews-panel-${restaurant.id}`} className="mt-4 border border-[var(--js-border)] rounded-2xl p-4 bg-[var(--js-subtle)]">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--js-text-secondary)] font-bold">Customer reviews</p>
                    {restaurant.average_rating && (
                      <div className="flex items-center gap-1 text-xs font-bold">
                        <Star className="w-3.5 h-3.5 fill-[#E9C46A] text-[#E9C46A]" />
                        {restaurant.average_rating} · {restaurant.review_count || 0}
                      </div>
                    )}
                  </div>
                  {reviewsLoading ? (
                    <p className="text-sm text-[var(--js-text-secondary)] py-2">Loading reviews...</p>
                  ) : reviews.length === 0 ? (
                    <p className="text-sm text-[var(--js-text-secondary)] py-2 italic">No reviews yet. Be the first to review after your order arrives!</p>
                  ) : (
                    <ul className="space-y-3 max-h-72 overflow-y-auto pr-1">
                      {reviews.map((rv) => (
                        <li key={rv.id} className="bg-white border border-[var(--js-border)] rounded-xl p-3" data-testid={`review-${rv.id}`}>
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-sm font-semibold text-[var(--js-text)] truncate">{rv.user_name || "Customer"}</span>
                            <span className="inline-flex items-center gap-0.5 text-xs font-bold text-[#1A1A1A] bg-[#E9C46A]/30 px-2 py-0.5 rounded-full">
                              <Star className="w-3 h-3 fill-[#E9C46A] text-[#E9C46A]" /> {rv.rating}
                            </span>
                          </div>
                          {rv.comment && <p className="text-sm text-[var(--js-text-secondary)] mt-1 whitespace-pre-wrap">{rv.comment}</p>}
                          {rv.created_at && (
                            <p className="text-[11px] text-[var(--js-text-secondary)] mt-1.5">{new Date(rv.created_at).toLocaleDateString()}</p>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              <div className="mt-5 relative">
                <Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-[var(--js-text-secondary)]" />
                <input
                  data-testid="menu-search"
                  value={search} onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search food items..."
                  className="w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-full pl-11 pr-4 py-2.5 text-sm focus:outline-none focus:border-[#C84B31]"
                />
              </div>

              {/* Iter 33.2 — attribute filter chips (Spice Level, Dietary...) */}
              {menuFacets.length > 0 && (
                <div className="mt-3 space-y-2" data-testid="menu-attr-filters">
                  {menuFacets.map((f) => (
                    <div key={f.key} className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">
                        {f.name}:
                      </span>
                      {f.values.map((v) => {
                        const on = (attrSel[f.key] || []).includes(v);
                        return (
                          <button
                            key={v}
                            onClick={() =>
                              setAttrSel((prev) => {
                                const cur = prev[f.key] || [];
                                const next = on ? cur.filter((x) => x !== v) : [...cur, v];
                                const out = { ...prev };
                                if (next.length) out[f.key] = next;
                                else delete out[f.key];
                                return out;
                              })
                            }
                            data-testid={`menu-attr-${f.key}-${v.replace(/\s+/g, "-").toLowerCase()}`}
                            className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border transition ${
                              on
                                ? "bg-[#1A1A1A] text-white border-[#1A1A1A]"
                                : "bg-white text-[var(--js-text)] border-[var(--js-border)] hover:border-[#1A1A1A]"
                            }`}
                          >
                            {v}
                          </button>
                        );
                      })}
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between mt-6 mb-3">
                <h3 className="font-display font-semibold text-lg text-[var(--js-text)]">Menu</h3>
                <MiniCurrencyToggle />
              </div>
              {menuCategories.length > 1 && (
                <div className="flex flex-wrap gap-2 mb-3" data-testid={`menu-categories-${restaurant.id}`}>
                  <button
                    onClick={() => setActiveMenuCat("all")}
                    data-testid={`menu-cat-${restaurant.id}-all`}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition ${
                      activeMenuCat === "all"
                        ? "bg-[#C84B31] text-white border-[#C84B31]"
                        : "bg-white border-[var(--js-border)] text-[var(--js-text)] hover:border-[#C84B31]"
                    }`}
                  >All</button>
                  {menuCategories.map((c) => (
                    <button
                      key={c.id}
                      onClick={() => setActiveMenuCat(c.id)}
                      data-testid={`menu-cat-${restaurant.id}-${c.id}`}
                      className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition ${
                        activeMenuCat === c.id
                          ? "bg-[#C84B31] text-white border-[#C84B31]"
                          : "bg-white border-[var(--js-border)] text-[var(--js-text)] hover:border-[#C84B31]"
                      }`}
                    >{c.name}</button>
                  ))}
                </div>
              )}
              <div className="space-y-4">
                {groupedMenu.map(({ cat, items }) => (
                  <div key={cat.id} data-testid={`menu-section-${cat.id}`}>
                    {menuCategories.length > 1 && (
                      <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--js-text-secondary)] mb-2">{cat.name}</p>
                    )}
                    <div className="space-y-3">
                      {items.map((item) => <MenuRow key={item.id} item={item} restaurant={restaurant} addMenu={addMenu} exchangeRate={exchangeRate} currency={currency} />)}
                    </div>
                  </div>
                ))}
                {filteredMenu.length === 0 && menu.length > 0 && <p className="text-sm text-[var(--js-text-secondary)] text-center py-6">No items match your filter.</p>}
                {menu.length === 0 && <p className="text-sm text-[var(--js-text-secondary)]">Loading menu...</p>}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function PromoBadge({ promo, rate, currency, className = "" }) {
  // Iter 28 — Improved badge look: mini flame glyph + gradient + shadow +
  // countdown-style feel. Reused everywhere (menu, product card, cart).
  if (!promo) return null;
  const label = promo.type === "percent"
    ? `−${Math.round(promo.value || 0)}%`
    : promo.type === "amount"
      ? `−${formatPrice(promo.value || 0, rate, currency)}`
      : `BUY ${promo.bogo_min_qty || 2}+ GET 1 FREE`;
  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full text-white shadow-[0_2px_6px_rgba(200,75,49,0.35)] bg-gradient-to-r from-[#E14B31] via-[#C84B31] to-[#B23A21] ${className}`}
      title={promo.ends_at ? `Promo ends ${new Date(promo.ends_at).toLocaleString()}` : "Limited-time promo"}
    >
      <span aria-hidden style={{ fontSize: 10 }}>🔥</span>{label}
    </span>
  );
}

function MenuRow({ item, restaurant, addMenu, exchangeRate, currency }) {
  const hasSides = (item.side_items || []).length > 0;
  const sidesRequired = !!item.sides_required && hasSides;
  const minChoices = sidesRequired ? (item.sides_min_choices ?? 1) : 0;
  const maxChoices = sidesRequired ? (item.sides_max_choices ?? null) : null;
  // If sides are required, expand the sides section immediately so the
  // customer sees exactly what they must pick.
  const [expanded, setExpanded] = useState(sidesRequired);
  const [pickedSides, setPickedSides] = useState([]);

  // Use item's embedded exchange rate (seller-specific) or fall back to global
  const itemRate = item.exchange_rate_ssp || exchangeRate;

  // Iter 27 — Promo pricing. When a promo is active + within date window,
  // display a strikethrough on the raw price and use the discounted price
  // for all totals. Backend re-computes on order-create so the customer
  // is charged the same value they see here.
  const nowIso = new Date().toISOString();
  const p = item.promo || {};
  const promoLive = !!p.active && (!p.starts_at || nowIso >= p.starts_at) && (!p.ends_at || nowIso <= p.ends_at);
  const rawPrice = item.price_usd;
  const effectivePrice = !promoLive ? rawPrice : (
    p.type === "percent"
      ? Math.max(0, rawPrice * (1 - (p.value || 0) / 100))
      : Math.max(0, rawPrice - (p.value || 0))
  );
  // Iter 28 — badge rendering delegated to <PromoBadge/> below.

  const toggleSide = (s) => {
    const exists = pickedSides.find((x) => x.name === s.name);
    if (exists) {
      setPickedSides(pickedSides.filter((x) => x.name !== s.name));
      return;
    }
    // Enforce max: when maxChoices=1 (e.g. pizza size), replace the
    // previous choice instead of appending. Otherwise ignore the click
    // once the ceiling is hit.
    if (maxChoices != null && pickedSides.length >= maxChoices) {
      if (maxChoices === 1) {
        setPickedSides([s]);
      }
      return;
    }
    setPickedSides([...pickedSides, s]);
  };

  const canAdd = !sidesRequired || (
    pickedSides.length >= minChoices &&
    (maxChoices == null || pickedSides.length <= maxChoices)
  );

  const onPlusClick = () => {
    if (hasSides && !expanded) {
      setExpanded(true);
      return;
    }
    if (!canAdd) return;  // guarded by disabled=true but be safe
    addMenu(item, pickedSides);
    setExpanded(sidesRequired);  // stay expanded if required for next click
    setPickedSides([]);
  };

  const totalUsd = effectivePrice + pickedSides.reduce((s, x) => s + x.price_usd, 0);

  // Human-readable requirement hint
  const requirementHint = sidesRequired && (() => {
    if (maxChoices === minChoices) return `Choose exactly ${minChoices}`;
    if (maxChoices == null) return `Choose at least ${minChoices}`;
    return `Choose ${minChoices}–${maxChoices}`;
  })();

  return (
    <div className="border border-[var(--js-border)] rounded-2xl p-3" data-testid={`menu-item-${item.id}`}>
      <div className="flex gap-3">
        <img src={item.image_url} alt={item.name} className="w-20 h-20 rounded-xl object-cover" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-semibold text-[var(--js-text)]">{item.name}</p>
            {sidesRequired && (
              <span className="text-[9px] font-bold uppercase tracking-widest bg-[#C84B31] text-white px-1.5 py-0.5 rounded" title="Sides required">
                Required
              </span>
            )}
            {promoLive && (
              <PromoBadge promo={p} rate={itemRate} currency={currency} />
            )}
          </div>
          <p className="text-xs text-[var(--js-text-secondary)] line-clamp-2 mt-0.5">{item.description}</p>
          <div className="mt-1 flex items-center gap-2">
            <span className="font-display font-bold text-[var(--js-text)]" data-testid={`menu-price-${item.id}`}>
              {formatPrice(totalUsd, itemRate, currency)}
            </span>
            {promoLive && pickedSides.length === 0 && (
              <span className="text-xs line-through text-[var(--js-text-secondary)]">
                {formatPrice(rawPrice, itemRate, currency)}
              </span>
            )}
            <span className="text-xs text-[var(--js-text-secondary)]">
              ≈ {formatPriceAlt(totalUsd, itemRate, currency)}
            </span>
          </div>
        </div>
        <button
          disabled={!restaurant.is_open || (expanded && !canAdd)}
          onClick={onPlusClick}
          data-testid={`add-menu-${item.id}`}
          title={sidesRequired && !canAdd ? requirementHint : (hasSides && !expanded ? "Choose sides" : "Add to cart")}
          className="self-center bg-[#1A1A1A] hover:bg-[#C84B31] text-white rounded-full p-2.5 transition disabled:bg-[#A3A39E] disabled:cursor-not-allowed"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>
      {expanded && hasSides && (
        <div className="mt-3 pt-3 border-t border-[var(--js-border)]">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-[var(--js-text-secondary)]">
              {sidesRequired ? requirementHint : "Choose sides (optional):"}
            </p>
            {sidesRequired && (
              <p className={`text-xs font-bold ${canAdd ? "text-emerald-700" : "text-[#C84B31]"}`}
                 data-testid={`menu-item-${item.id}-picked-count`}>
                {pickedSides.length}/{maxChoices ?? "∞"}
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {item.side_items.map((s) => {
              const picked = pickedSides.find((x) => x.name === s.name);
              const atMax = !picked && maxChoices != null && pickedSides.length >= maxChoices && maxChoices !== 1;
              return (
                <button
                  key={s.name}
                  onClick={() => toggleSide(s)}
                  disabled={atMax}
                  data-testid={`side-${item.id}-${s.name.replace(/\s+/g, "-").toLowerCase()}`}
                  className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition ${
                    picked
                      ? "bg-[#C84B31] text-white border-[#C84B31]"
                      : atMax
                        ? "bg-gray-100 border-[var(--js-border)] text-gray-400 cursor-not-allowed"
                        : "bg-white border-[var(--js-border)] text-[var(--js-text)] hover:border-[#C84B31]"
                  }`}
                >
                  {picked ? "✓ " : "+ "}{s.name} {formatPrice(s.price_usd, itemRate, currency)}
                </button>
              );
            })}
          </div>
          <div className="mt-3 flex items-center justify-end gap-2">
            <button
              onClick={() => { setExpanded(sidesRequired); setPickedSides([]); }}
              data-testid={`cancel-sides-${item.id}`}
              className={`text-xs font-semibold text-[var(--js-text-secondary)] hover:text-[var(--js-text)] px-3 py-1.5 ${sidesRequired ? "hidden" : ""}`}
            >
              Cancel
            </button>
            <button
              onClick={onPlusClick}
              disabled={!canAdd}
              data-testid={`confirm-sides-${item.id}`}
              className="text-xs font-bold bg-[#C84B31] hover:bg-[#A83A23] text-white rounded-full px-4 py-2 transition disabled:bg-[#A3A39E] disabled:cursor-not-allowed"
            >
              Add to cart
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
