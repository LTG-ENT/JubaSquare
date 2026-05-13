import { useState } from "react";
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
  const [search, setSearch] = useState("");
  const [isFavorite, setIsFavorite] = useState(false);
  const [favoriteId, setFavoriteId] = useState(null);
  const [reviewsOpen, setReviewsOpen] = useState(false);
  const [reviews, setReviews] = useState([]);
  const [reviewsLoading, setReviewsLoading] = useState(false);
  const { addItem, exchangeRate, currency } = useCart();
  const { user } = useAuth();

  useEffect(() => {
    if (open && menu.length === 0) {
      api.get(`/restaurants/${restaurant.id}/menu`).then((r) => setMenu(r.data));
    }
  }, [open, restaurant.id, menu.length]);
  
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

  const filteredMenu = menu.filter((m) => !search || m.name.toLowerCase().includes(search.toLowerCase()));

  const addMenu = (item, sides) => {
    const success = addItem({
      item_type: "menu_item", item_id: item.id, name: item.name,
      price_usd: item.price_usd, image_url: item.image_url, quantity: 1,
      sides: sides || [],
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
          <div className="absolute top-3 left-3">
            <span data-testid={`restaurant-status-${restaurant.id}`} className={`text-xs font-bold px-3 py-1 rounded-full shadow-md ${restaurant.is_open ? "bg-[#2D6A4F] text-white" : "bg-[#A3A39E] text-white"}`}>
              {restaurant.is_open ? "● Open" : "● Closed"}
            </span>
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
              <img src={restaurant.image_url} alt={restaurant.name} className="w-full h-full object-cover" />
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

              <div className="flex items-center justify-between mt-6 mb-3">
                <h3 className="font-display font-semibold text-lg text-[var(--js-text)]">Menu</h3>
                <MiniCurrencyToggle />
              </div>
              <div className="space-y-3">
                {filteredMenu.map((item) => <MenuRow key={item.id} item={item} restaurant={restaurant} addMenu={addMenu} exchangeRate={exchangeRate} currency={currency} />)}
                {filteredMenu.length === 0 && menu.length > 0 && <p className="text-sm text-[var(--js-text-secondary)] text-center py-6">No items match "{search}"</p>}
                {menu.length === 0 && <p className="text-sm text-[var(--js-text-secondary)]">Loading menu...</p>}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function MenuRow({ item, restaurant, addMenu, exchangeRate, currency }) {
  const [expanded, setExpanded] = useState(false);
  const [pickedSides, setPickedSides] = useState([]);
  const hasSides = (item.side_items || []).length > 0;

  // Use item's embedded exchange rate (seller-specific) or fall back to global
  const itemRate = item.exchange_rate_ssp || exchangeRate;

  const toggleSide = (s) => {
    const exists = pickedSides.find((x) => x.name === s.name);
    if (exists) setPickedSides(pickedSides.filter((x) => x.name !== s.name));
    else setPickedSides([...pickedSides, s]);
  };

  const onPlusClick = () => {
    if (hasSides && !expanded) {
      setExpanded(true);
      return;
    }
    addMenu(item, pickedSides);
    setExpanded(false);
    setPickedSides([]);
  };

  const totalUsd = item.price_usd + pickedSides.reduce((s, x) => s + x.price_usd, 0);

  return (
    <div className="border border-[var(--js-border)] rounded-2xl p-3" data-testid={`menu-item-${item.id}`}>
      <div className="flex gap-3">
        <img src={item.image_url} alt={item.name} className="w-20 h-20 rounded-xl object-cover" />
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-[var(--js-text)]">{item.name}</p>
          <p className="text-xs text-[var(--js-text-secondary)] line-clamp-2 mt-0.5">{item.description}</p>
          <div className="mt-1 flex items-center gap-2">
            <span className="font-display font-bold text-[var(--js-text)]" data-testid={`menu-price-${item.id}`}>
              {formatPrice(totalUsd, itemRate, currency)}
            </span>
            <span className="text-xs text-[var(--js-text-secondary)]">
              ≈ {formatPriceAlt(totalUsd, itemRate, currency)}
            </span>
          </div>
        </div>
        <button
          disabled={!restaurant.is_open}
          onClick={onPlusClick}
          data-testid={`add-menu-${item.id}`}
          title={hasSides && !expanded ? "Choose sides" : "Add to cart"}
          className="self-center bg-[#1A1A1A] hover:bg-[#C84B31] text-white rounded-full p-2.5 transition disabled:bg-[#A3A39E] disabled:cursor-not-allowed"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>
      {expanded && hasSides && (
        <div className="mt-3 pt-3 border-t border-[var(--js-border)]">
          <p className="text-xs font-semibold text-[var(--js-text-secondary)] mb-2">Choose sides (optional):</p>
          <div className="flex flex-wrap gap-2">
            {item.side_items.map((s) => {
              const picked = pickedSides.find((x) => x.name === s.name);
              return (
                <button
                  key={s.name}
                  onClick={() => toggleSide(s)}
                  data-testid={`side-${item.id}-${s.name.replace(/\s+/g, "-").toLowerCase()}`}
                  className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition ${
                    picked ? "bg-[#C84B31] text-white border-[#C84B31]" : "bg-white border-[var(--js-border)] text-[var(--js-text)] hover:border-[#C84B31]"
                  }`}
                >
                  {picked ? "✓ " : "+ "}{s.name} {formatPrice(s.price_usd, itemRate, currency)}
                </button>
              );
            })}
          </div>
          <div className="mt-3 flex items-center justify-end gap-2">
            <button
              onClick={() => { setExpanded(false); setPickedSides([]); }}
              data-testid={`cancel-sides-${item.id}`}
              className="text-xs font-semibold text-[var(--js-text-secondary)] hover:text-[var(--js-text)] px-3 py-1.5"
            >
              Cancel
            </button>
            <button
              onClick={onPlusClick}
              data-testid={`confirm-sides-${item.id}`}
              className="text-xs font-bold bg-[#C84B31] hover:bg-[#A83A23] text-white rounded-full px-4 py-2 transition"
            >
              Add to cart
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
