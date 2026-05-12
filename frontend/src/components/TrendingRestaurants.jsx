import { useEffect, useState } from "react";
import { Flame } from "lucide-react";
import api from "@/lib/api";
import RestaurantCard from "@/components/RestaurantCard";

/**
 * "Trending now" carousel. Fetches from /trending/restaurants which is
 * populated by:
 *   - click_count  (incremented when a customer opens a restaurant card)
 *   - order_count  (incremented when a customer creates a restaurant order)
 *
 * Renders nothing while loading and nothing if there are < 2 trending entries
 * so the section doesn't look empty on a fresh install.
 */
export default function TrendingRestaurants({ limit = 6, title = "Trending now", subtitle = "Most ordered & visited this week" }) {
  const [items, setItems] = useState(null); // null → still loading

  useEffect(() => {
    let cancelled = false;
    api
      .get(`/trending/restaurants?limit=${limit}`)
      .then((r) => {
        if (cancelled) return;
        const arr = Array.isArray(r.data) ? r.data.filter((x) => !x.is_deleted) : [];
        setItems(arr);
      })
      .catch(() => !cancelled && setItems([]));
    return () => { cancelled = true; };
  }, [limit]);

  // Hide the section entirely if no data — avoids an awkward empty block.
  if (!items || items.length < 2) return null;

  return (
    <section
      data-testid="trending-restaurants"
      className="py-6"
    >
      <div className="flex items-end justify-between flex-wrap gap-4 mb-6">
        <div>
          <div className="inline-flex items-center gap-2 bg-[#C84B31]/10 text-[#C84B31] text-[10px] uppercase tracking-[0.2em] font-bold px-3 py-1 rounded-full mb-3">
            <Flame className="w-3 h-3" /> Trending
          </div>
          <h2 className="font-display font-bold text-3xl sm:text-4xl text-[var(--js-text)]">{title}</h2>
          <p className="text-sm text-[var(--js-text-secondary)] mt-1">{subtitle}</p>
        </div>
      </div>

      {/* Horizontal-scrollable rail on small screens, grid on large */}
      <div className="flex sm:grid sm:grid-cols-2 lg:grid-cols-3 gap-5 overflow-x-auto sm:overflow-visible -mx-4 px-4 sm:mx-0 sm:px-0 snap-x snap-mandatory">
        {items.slice(0, limit).map((r, idx) => (
          <div
            key={r.id}
            data-testid={`trending-restaurant-${r.id}`}
            className="shrink-0 w-[85%] sm:w-auto snap-center"
          >
            <RestaurantCard restaurant={r} rank={idx + 1} trendingScore={r.trending_score ?? null} />
          </div>
        ))}
      </div>
    </section>
  );
}
