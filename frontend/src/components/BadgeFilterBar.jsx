import { useSearchParams } from "react-router-dom";

/**
 * BadgeFilterBar (Iter 30 Wave 2)
 * ---------------------------------
 * A chip row that lets customers filter the current listing by badge:
 *   • LTG only   → ?ltg=1
 *   • Deals only → ?deals=1
 *   • Wholesale  → ?wholesale=1     (only rendered when `showWholesale`)
 *   • Verified   → ?verified=1
 *
 * Each chip toggles its param on/off. Chips are visually distinct (LTG gold,
 * Deals red pulse, Wholesale blue, Verified green) so they mirror the card
 * badges.
 */
export default function BadgeFilterBar({ showWholesale = false }) {
  const [searchParams, setSearchParams] = useSearchParams();

  const toggle = (key) => {
    const next = new URLSearchParams(searchParams);
    if (next.get(key)) next.delete(key);
    else next.set(key, "1");
    setSearchParams(next);
  };

  const clearAll = () => {
    const next = new URLSearchParams(searchParams);
    ["ltg", "deals", "wholesale", "verified"].forEach((k) => next.delete(k));
    setSearchParams(next);
  };

  const active = {
    ltg: !!searchParams.get("ltg"),
    deals: !!searchParams.get("deals"),
    wholesale: !!searchParams.get("wholesale"),
    verified: !!searchParams.get("verified"),
  };
  const anyActive = active.ltg || active.deals || active.wholesale || active.verified;

  const chip = (key, label, icon, activeClass, inactiveClass) => (
    <button
      key={key}
      onClick={() => toggle(key)}
      data-testid={`badge-filter-${key}`}
      className={`inline-flex items-center gap-1.5 text-[11px] uppercase tracking-widest font-bold px-3 py-1.5 rounded-full transition-all duration-200 border ${
        active[key] ? activeClass : inactiveClass
      }`}
      aria-pressed={active[key]}
    >
      <span aria-hidden style={{ fontSize: 11 }}>{icon}</span>
      {label}
    </button>
  );

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="badge-filter-bar">
      <span className="text-[10px] uppercase tracking-widest text-[#5C5C5C] font-bold mr-1">Filter:</span>
      {chip(
        "ltg",
        "LTG",
        "★",
        "bg-gradient-to-r from-[#D4AF37] via-[#E9C46A] to-[#B8860B] text-white border-transparent shadow-md",
        "bg-white text-[#8B6B00] border-[#E9C46A]/50 hover:border-[#E9C46A]"
      )}
      {chip(
        "deals",
        "Deals",
        "🔥",
        "bg-gradient-to-r from-[#F5583E] via-[#C84B31] to-[#A83521] text-white border-transparent shadow-md",
        "bg-white text-[#C84B31] border-[#C84B31]/50 hover:border-[#C84B31]"
      )}
      {showWholesale &&
        chip(
          "wholesale",
          "Wholesale",
          "📦",
          "bg-gradient-to-r from-[#3D5A80] via-[#4C6EA7] to-[#293E5E] text-white border-transparent shadow-md",
          "bg-white text-[#3D5A80] border-[#3D5A80]/50 hover:border-[#3D5A80]"
        )}
      {chip(
        "verified",
        "Verified",
        "✓",
        "bg-[#2D6A4F] text-white border-transparent shadow-md",
        "bg-white text-[#2D6A4F] border-[#2D6A4F]/40 hover:border-[#2D6A4F]"
      )}
      {anyActive && (
        <button
          onClick={clearAll}
          data-testid="badge-filter-clear"
          className="text-[11px] font-semibold text-[#5C5C5C] hover:text-[#1A1A1A] underline underline-offset-2 ml-1"
        >
          Clear
        </button>
      )}
    </div>
  );
}
