import { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import RestaurantCard from "@/components/RestaurantCard";
import AreaSelector from "@/components/AreaSelector";
import { useCart } from "@/context/CartContext";

/**
 * Restaurants page — fully DB-driven categories.
 *
 * Routing contract (single source of truth = DB `categories` collection):
 *   /restaurants?category_id=<uuid>   →  primary (used by Header mega-menu)
 *   /restaurants?category=<name>      →  legacy fallback, still accepted
 *
 * Category state inside the page is always keyed by category id so the active
 * chip stays in sync regardless of how the URL was reached.
 */
export default function Restaurants() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [restaurants, setRestaurants] = useState([]);
  const [menuItems, setMenuItems] = useState([]);
  const [loading, setLoading] = useState(false);
  // Admin-managed restaurant categories — full objects so we can map id ↔ name.
  const [dbCategories, setDbCategories] = useState([]);
  // `activeCatId === "all"` means show every restaurant. Otherwise it is the
  // DB category id whose menu items the user wants to filter by.
  const [activeCatId, setActiveCatId] = useState("all");
  const [sortBy, setSortBy] = useState("recommended");
  const { area, setArea } = useCart();

  // Fetch all data on mount OR when activeCatId changes.
  // NEW: Use backend filtering with category_id for better performance.
  useEffect(() => {
    // CRITICAL: Clear old data immediately to prevent showing unfiltered results
    setRestaurants([]);
    setLoading(true);
    
    // Fetch restaurants with category_id filter (if not "all")
    const restaurantsUrl = activeCatId && activeCatId !== "all"
      ? `/restaurants?limit=200&category_id=${activeCatId}`
      : "/restaurants?limit=200";
    
    api.get(restaurantsUrl)
      .then((r) => {
        setRestaurants(r.data);
        setLoading(false);
      })
      .catch(() => {
        setRestaurants([]);
        setLoading(false);
      });
    
    // Menu items are only used for empty state detection now (not for filtering)
    // But we still need them to detect if a category has ANY menu items
    const menuUrl = activeCatId && activeCatId !== "all"
      ? `/menu-items?limit=200&category_id=${activeCatId}`
      : "/menu-items?limit=200";
    
    api.get(menuUrl).then((r) => {
      setMenuItems(Array.isArray(r.data) ? r.data : []);
    }).catch(() => setMenuItems([]));
  }, [activeCatId]); // Re-fetch when category changes

  // Fetch categories once on mount
  useEffect(() => {
    api
      .get("/categories/tree?group=restaurant")
      .then((r) => {
        const tree = Array.isArray(r.data) ? r.data : [];
        // Keep id + name only — that is all the page needs.
        setDbCategories(tree.map((c) => ({ id: c.id, name: c.name })));
      })
      .catch(() => setDbCategories([]));
  }, []);

  // Resolve activeCatId from the URL whenever it changes OR whenever the
  // category list arrives. We support both `category_id` (preferred) and
  // `category` (legacy name match) so old bookmarks still work.
  useEffect(() => {
    const id = searchParams.get("category_id");
    const name = searchParams.get("category");
    if (id) {
      setActiveCatId(id);
      // eslint-disable-next-line no-console
      console.debug("[Restaurants] activeCatId from URL category_id:", id);
      return;
    }
    if (name && dbCategories.length > 0) {
      const match = dbCategories.find(
        (c) => c.name.toLowerCase() === name.toLowerCase(),
      );
      if (match) {
        setActiveCatId(match.id);
        // eslint-disable-next-line no-console
        console.debug("[Restaurants] activeCatId resolved from name:", name, "→", match.id);
        return;
      }
    }
    setActiveCatId("all");
  }, [searchParams, dbCategories]);

  // Resolve active id → name for display purposes only
  const activeCatName = useMemo(() => {
    if (activeCatId === "all") return "All";
    return dbCategories.find((c) => c.id === activeCatId)?.name || "";
  }, [activeCatId, dbCategories]);

  // Chips = "All" + every admin-defined top-level restaurant category.
  const chips = useMemo(
    () => [{ id: "all", name: "All" }, ...dbCategories],
    [dbCategories],
  );

  // NO FILTERING NEEDED - backend already filtered by category_id
  // We just use restaurants directly
  const filtered = restaurants;

  // Backend already sorts verified-first; apply client sort on top.
  const sorted = useMemo(() => {
    const arr = [...filtered];
    if (sortBy === "name_asc") arr.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    else if (sortBy === "delivery_time") arr.sort((a, b) => (a.delivery_time_min || 99) - (b.delivery_time_min || 99));
    else if (sortBy === "rating") arr.sort((a, b) => (b.rating || 0) - (a.rating || 0));
    return arr;
  }, [filtered, sortBy]);

  const onChipClick = (chip) => {
    if (chip.id === "all") {
      setActiveCatId("all");
      setSearchParams({});
    } else {
      setActiveCatId(chip.id);
      setSearchParams({ category_id: chip.id });
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-8">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold mb-2">Food & Restaurants</p>
            <h1 className="font-display font-bold text-3xl sm:text-4xl lg:text-5xl text-[#1A1A1A]">
              Hot meals, served fresh.
            </h1>
            <p className="text-sm text-[#5C5C5C] mt-2">From local favorites to fast food — order it your way.</p>
          </div>
          <AreaSelector value={area} onChange={setArea} />
        </div>

        <div className="flex flex-wrap gap-2 mb-8 items-center">
          {chips.map((chip) => {
            const slug = chip.name.replace(/\s+/g, "-").toLowerCase();
            const isActive = activeCatId === chip.id;
            return (
              <button
                key={chip.id}
                onClick={() => onChipClick(chip)}
                data-testid={`restaurant-cat-${slug}`}
                data-category-id={chip.id}
                className={`px-4 py-2 rounded-full text-sm font-semibold transition ${
                  isActive
                    ? "bg-[#C84B31] text-white"
                    : "bg-white border border-[#E2E2D9] text-[#1A1A1A] hover:border-[#C84B31]"
                }`}
              >
                {chip.name}
              </button>
            );
          })}

          <div className="ml-auto flex items-center gap-2">
            <label className="text-xs font-semibold text-[#5C5C5C]">Sort by</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              data-testid="restaurants-sort-by"
              className="bg-white border border-[#E2E2D9] rounded-full px-4 py-2 text-sm font-semibold focus:outline-none focus:border-[#C84B31] shadow-sm cursor-pointer"
            >
              <option value="recommended">Recommended (verified first)</option>
              <option value="rating">Top rated</option>
              <option value="delivery_time">Fastest delivery</option>
              <option value="name_asc">Name: A → Z</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-20" data-testid="restaurants-loading">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-gray-200 border-t-[#C84B31]"></div>
            <p className="text-[#5C5C5C] mt-4">Loading restaurants...</p>
          </div>
        ) : sorted.length === 0 ? (
          <div className="text-center py-20 text-[#5C5C5C]" data-testid="restaurants-empty">
            No restaurants in this category.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {sorted.map((r) => <RestaurantCard key={r.id} restaurant={r} />)}
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
