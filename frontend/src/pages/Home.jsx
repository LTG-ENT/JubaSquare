import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import api, { safeArray } from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import ShopCard from "@/components/ShopCard";
import WholesaleCard from "@/components/WholesaleCard";
import RestaurantCard from "@/components/RestaurantCard";
import TrendingRestaurants from "@/components/TrendingRestaurants";
import AreaSelector from "@/components/AreaSelector";
import { useCart } from "@/context/CartContext";
import { ArrowRight, Sparkles, Package } from "lucide-react";

const HERO_SLIDES = [
  {
    label: "Retail",
    key: "slideRetail",
    img: "https://images.unsplash.com/photo-1604719312566-8912e9227c6a?w=1600&q=80&auto=format&fit=crop",
    // grocery / store shelves
  },
  {
    label: "Wholesale",
    key: "slideWholesale",
    img: "https://images.unsplash.com/photo-1553413077-190dd305871c?w=1600&q=80&auto=format&fit=crop",
    // warehouse pallets
  },
  {
    label: "Food",
    key: "slideFood",
    img: "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=1600&q=80&auto=format&fit=crop",
    // restaurant dish
  },
];

const CATEGORY_ICONS = {
  "Groceries": "https://images.unsplash.com/photo-1542838132-92c53300491e?w=400&q=80",
  "Clothing & Fashion": "https://images.unsplash.com/photo-1757140447782-8503452b2204?w=400&q=80",
  "Shoes & Bags": "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=400&q=80",
  "Beauty & Cosmetics": "https://images.unsplash.com/photo-1522335789203-aaa57d0aacae?w=400&q=80",
  "Electronics & Accessories": "https://images.unsplash.com/photo-1761641466573-f240b6e446de?w=400&q=80",
  "Home Essentials": "https://images.pexels.com/photos/15108276/pexels-photo-15108276.jpeg?auto=compress&w=400",
  "Health & Pharmacy": "https://images.unsplash.com/photo-1646392206581-2527b1cae5cb?w=400&q=80",
  "Building & Materials": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=400&q=80",
  "Automotive": "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?w=400&q=80",
};

export default function Home() {
  const { t } = useTranslation();
  const [shops, setShops] = useState([]);
  const [restaurants, setRestaurants] = useState([]);
  const [wholesaleProducts, setWholesaleProducts] = useState([]);
  const [allProducts, setAllProducts] = useState([]);
  const [retailCats, setRetailCats] = useState([]); // [{id,name,image_url,children:[]}]
  const [slideIdx, setSlideIdx] = useState(0);
  const [heroConfig, setHeroConfig] = useState(null);
  const { area, setArea } = useCart();

  useEffect(() => {
    api.get("/shops?kind=retail&limit=24").then((r) => setShops(safeArray(r.data)));
    api.get("/restaurants?limit=24").then((r) => setRestaurants(safeArray(r.data)));
    api.get("/products?is_wholesale=true&limit=24").then((r) => setWholesaleProducts(safeArray(r.data)));
    api.get("/products?limit=48").then((r) => setAllProducts(safeArray(r.data)));
    api
      .get("/categories/tree?group=retail")
      .then((r) => setRetailCats(Array.isArray(r.data) ? r.data : []))
      .catch(() => setRetailCats([]));
    api.get("/homepage").then((r) => setHeroConfig(r.data)).catch(() => setHeroConfig(null));
  }, []);

  // Effective slides: admin-managed first, fall back to defaults
  const adminSlides = (heroConfig?.hero_slides || []).filter((s) => s?.image_url);
  const slides = adminSlides.length > 0
    ? adminSlides.map((s) => ({ label: s.label || "Slide", key: s.key || "slideRetail", img: s.image_url }))
    : HERO_SLIDES;

  // Cycle hero background every 3.5s
  useEffect(() => {
    const id = setInterval(() => {
      setSlideIdx((i) => (i + 1) % slides.length);
    }, 3500);
    return () => clearInterval(id);
  }, [slides.length]);

  // Prefer admin-managed retail categories. Fall back to shop-derived list if
  // the DB happens to be empty.
  const shopCategories = [...new Set(shops.map((s) => s.category))].filter(Boolean);
  const categories =
    retailCats.length > 0
      ? retailCats.map((c) => ({ name: c.name, image_url: c.image_url || CATEGORY_ICONS[c.name] || "" }))
      : shopCategories.map((name) => ({ name, image_url: CATEGORY_ICONS[name] || "" }));
  const productsByShop = (shopId) => allProducts.filter((p) => p.shop_id === shopId).slice(0, 4);

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      {/* HERO */}
      <section className="relative">
        <div className="absolute inset-0 overflow-hidden">
          {slides.map((s, i) => (
            <img
              key={s.label + i}
              src={s.img}
              alt=""
              className={`absolute inset-0 w-full h-full object-cover transition-all duration-[1400ms] ease-in-out ${
                i === slideIdx ? "opacity-100 scale-100" : "opacity-0 scale-105"
              }`}
            />
          ))}
          <div className="absolute inset-0 bg-gradient-to-r from-[#0E1A2B]/95 via-[#0E1A2B]/80 to-[#0E1A2B]/40" />
        </div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 sm:py-28 lg:py-36">
          <div className="max-w-2xl fade-up">
            <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur border border-white/20 rounded-full px-3 py-1.5 mb-6">
              <Sparkles className="w-3.5 h-3.5 text-[#E9C46A]" />
              <span className="text-[11px] uppercase tracking-[0.18em] text-white font-bold">
                {heroConfig?.hero_tagline || t("heroTagline")}
              </span>
            </div>
            <h1 className="font-display font-bold text-4xl sm:text-5xl lg:text-6xl text-white tracking-tight">
              {heroConfig?.hero_title || t("heroTitle")}{" "}
              <span className="relative inline-block align-baseline" style={{ minWidth: "4ch" }}>
                {slides.map((s, i) => (
                  <span
                    key={s.label + i}
                    aria-hidden={i !== slideIdx}
                    className={`text-[#E9C46A] transition-all duration-700 ease-out ${
                      i === slideIdx
                        ? "opacity-100 translate-y-0 relative"
                        : "opacity-0 translate-y-3 absolute left-0 top-0"
                    }`}
                  >
                    {s.key ? t(s.key) : s.label}
                  </span>
                ))}
              </span>
            </h1>
            <p className="text-white/90 text-base sm:text-lg mt-5 max-w-xl">
              {heroConfig?.hero_subtitle || t("heroSubtitle")}
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to="/marketplace"
                data-testid="hero-marketplace-btn"
                className="bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-7 py-3.5 rounded-full inline-flex items-center gap-2 transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5"
              >
                {t("startShopping")} <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                to="/marketplace?view=wholesale"
                data-testid="hero-wholesale-btn"
                className="bg-[#1E3A5F] hover:bg-[#2A4D77] text-white font-semibold px-7 py-3.5 rounded-full inline-flex items-center gap-2 transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5 border border-white/20"
              >
                <Package className="w-4 h-4" /> {t("exploreWholesale")}
              </Link>
            </div>
            <div className="mt-8 flex items-center gap-3">
              <span className="text-white/70 text-sm">{t("browsingIn")}</span>
              <AreaSelector value={area} onChange={setArea} testId="home-area-selector" />
            </div>

            {/* Slide indicators */}
            <div className="mt-6 flex items-center gap-2" data-testid="hero-slide-indicators">
              {slides.map((s, i) => (
                <button
                  key={s.label + i}
                  onClick={() => setSlideIdx(i)}
                  data-testid={`hero-slide-dot-${(s.label || 'slide').toLowerCase()}`}
                  aria-label={`Show ${s.label} slide`}
                  className={`h-1.5 rounded-full transition-all duration-500 ${
                    i === slideIdx ? "w-10 bg-[#E9C46A]" : "w-4 bg-white/30 hover:bg-white/50"
                  }`}
                />
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* CATEGORIES */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20 w-full">
        <div className="flex items-end justify-between flex-wrap gap-4 mb-8">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold mb-2">{t("browse")}</p>
            <h2 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">{t("shopByCategory")}</h2>
          </div>
          <Link to="/marketplace" className="text-sm font-semibold text-[#C84B31] hover:underline" data-testid="see-all-categories">
            {t("seeAll")} →
          </Link>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {categories.map((cat) => (
            <Link
              key={cat.name}
              to={`/marketplace?category=${encodeURIComponent(cat.name)}`}
              data-testid={`category-card-${cat.name.replace(/\s+/g, "-").toLowerCase()}`}
              className="js-card overflow-hidden flex flex-col hover:-translate-y-1 hover:shadow-xl transition-all duration-300"
            >
              <div className="aspect-square overflow-hidden bg-[#F2EBE5]">
                {cat.image_url ? (
                  <img
                    src={cat.image_url}
                    alt={cat.name}
                    className="w-full h-full object-cover hover:scale-110 transition-transform duration-500"
                    onError={(e) => {
                      e.target.style.display = "none";
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-3xl font-display text-[#5C5C5C]/50">
                    {cat.name.charAt(0)}
                  </div>
                )}
              </div>
              <div className="p-3 text-center">
                <p className="font-display font-semibold text-sm text-[#1A1A1A]">{cat.name}</p>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* BULK DEALS (WHOLESALE) */}
      {wholesaleProducts.length > 0 && (
        <section className="bg-[#F2F8F4] py-16 sm:py-20 w-full border-y border-[#2D6A4F]/10">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-end justify-between flex-wrap gap-4 mb-8">
              <div>
                <span className="inline-flex items-center gap-1.5 bg-[#2D6A4F] text-white text-[10px] uppercase tracking-[0.2em] font-bold px-3 py-1.5 rounded-full mb-3">
                  <Package className="w-3 h-3" /> {t("wholesale")}
                </span>
                <h2 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">{t("bulkDeals")}</h2>
                <p className="text-sm text-[#5C5C5C] mt-1">{t("bulkDealsSub")}</p>
              </div>
              <Link to="/marketplace?view=wholesale" data-testid="see-all-wholesale" className="text-sm font-semibold text-[#2D6A4F] hover:underline">
                {t("exploreAllWholesale")} →
              </Link>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {wholesaleProducts.slice(0, 4).map((p) => (
                <WholesaleCard key={p.id} product={p} shop={shops.find((s) => s.id === p.shop_id)} />
              ))}
            </div>
          </div>
        </section>
      )}

      {/* FEATURED SHOPS */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20 w-full">
        <div className="flex items-end justify-between flex-wrap gap-4 mb-8">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold mb-2">{t("featured")}</p>
            <h2 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">{t("verifiedShops")}</h2>
          </div>
          <Link to="/shops" className="text-sm font-semibold text-[#C84B31] hover:underline">{t("viewAllShops")} →</Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {shops.slice(0, 6).map((s) => (
            <ShopCard key={s.id} shop={s} productsPreview={productsByShop(s.id)} />
          ))}
        </div>
      </section>

      {/* TRENDING — auto-hides when there isn't enough data */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
        <TrendingRestaurants limit={6} />
      </div>

      {/* FOOD & RESTAURANTS */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16 w-full">
        <div className="flex items-end justify-between flex-wrap gap-4 mb-8">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold mb-2">{t("hungry")}</p>
            <h2 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">{t("foodRestaurants")}</h2>
          </div>
          <Link to="/restaurants" className="text-sm font-semibold text-[#C84B31] hover:underline">{t("allRestaurants")} →</Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {restaurants.slice(0, 4).map((r) => <RestaurantCard key={r.id} restaurant={r} />)}
        </div>
      </section>

      <Footer />
    </div>
  );
}
