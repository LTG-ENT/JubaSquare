import { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import RestaurantCard from "@/components/RestaurantCard";
import AreaSelector from "@/components/AreaSelector";
import { useCart } from "@/context/CartContext";

export default function Restaurants() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [restaurants, setRestaurants] = useState([]);
  const [menuItems, setMenuItems] = useState([]);
  const [activeCat, setActiveCat] = useState(searchParams.get("category") || "All");
  const [sortBy, setSortBy] = useState("recommended");
  const { area, setArea } = useCart();

  useEffect(() => {
    api.get("/restaurants?limit=200").then((r) => setRestaurants(r.data));
    // Fetch all menu items to determine restaurant categories
    api.get("/products?limit=1000").then((r) => {
      // Filter only restaurant menu items (food_category field exists)
      const menuData = r.data.filter(p => p.food_category);
      setMenuItems(menuData);
    });
  }, []);

  // Update activeCat when URL params change
  useEffect(() => {
    const cat = searchParams.get("category");
    if (cat) setActiveCat(cat);
  }, [searchParams]);

  // Get categories from menu items' food_category (not restaurant.category)
  const cats = useMemo(() => {
    const foodCategories = new Set(menuItems.map(m => m.food_category).filter(Boolean));
    return ["All", ...Array.from(foodCategories)];
  }, [menuItems]);

  // Filter restaurants by checking if they have menu items in the selected category
  const filtered = useMemo(() => {
    if (activeCat === "All") return restaurants;
    
    // Get restaurant IDs that have menu items in this category
    const restaurantIds = new Set(
      menuItems
        .filter(m => m.food_category === activeCat)
        .map(m => m.restaurant_id)
    );
    
    return restaurants.filter(r => restaurantIds.has(r.id));
  }, [activeCat, restaurants, menuItems]);

  // Backend already sorts verified-first. Apply client sort options.
  const sorted = useMemo(() => {
    const arr = [...filtered];
    if (sortBy === "name_asc") arr.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    else if (sortBy === "delivery_time") arr.sort((a, b) => (a.delivery_time_min || 99) - (b.delivery_time_min || 99));
    else if (sortBy === "rating") arr.sort((a, b) => (b.rating || 0) - (a.rating || 0));
    return arr;
  }, [filtered, sortBy]);

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
          {cats.map((c) => (
            <button
              key={c}
              onClick={() => {
                setActiveCat(c);
                if (c === "All") {
                  setSearchParams({});
                } else {
                  setSearchParams({ category: c });
                }
              }}
              data-testid={`restaurant-cat-${c.replace(/\s+/g, "-").toLowerCase()}`}
              className={`px-4 py-2 rounded-full text-sm font-semibold transition ${
                activeCat === c
                  ? "bg-[#C84B31] text-white"
                  : "bg-white border border-[#E2E2D9] text-[#1A1A1A] hover:border-[#C84B31]"
              }`}
            >
              {c}
            </button>
          ))}

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

        {sorted.length === 0 ? (
          <div className="text-center py-20 text-[#5C5C5C]">No restaurants in this category.</div>
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
