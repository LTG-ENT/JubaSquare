import { useEffect, useState, useMemo } from "react";
import api from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import RestaurantCard from "@/components/RestaurantCard";
import AreaSelector from "@/components/AreaSelector";
import { useCart } from "@/context/CartContext";

export default function Restaurants() {
  const [restaurants, setRestaurants] = useState([]);
  const [activeCat, setActiveCat] = useState("All");
  const { area, setArea } = useCart();

  useEffect(() => {
    api.get("/restaurants").then((r) => setRestaurants(r.data));
  }, []);

  const cats = useMemo(() => ["All", ...new Set(restaurants.map((r) => r.category))], [restaurants]);
  const filtered = activeCat === "All" ? restaurants : restaurants.filter((r) => r.category === activeCat);

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

        <div className="flex flex-wrap gap-2 mb-8">
          {cats.map((c) => (
            <button
              key={c}
              onClick={() => setActiveCat(c)}
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
        </div>

        {filtered.length === 0 ? (
          <div className="text-center py-20 text-[#5C5C5C]">No restaurants in this category.</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {filtered.map((r) => <RestaurantCard key={r.id} restaurant={r} />)}
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
