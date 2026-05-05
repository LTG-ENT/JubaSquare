import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import ShopCard from "@/components/ShopCard";
import WholesaleCard from "@/components/WholesaleCard";
import RestaurantCard from "@/components/RestaurantCard";
import AreaSelector from "@/components/AreaSelector";
import { useCart } from "@/context/CartContext";
import { ArrowRight, Sparkles, Package } from "lucide-react";

const HERO_IMG =
  "https://images.unsplash.com/photo-1693064972579-0c1c85c636e8?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Njl8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBhZnJpY2FuJTIwbWFya2V0cGxhY2V8ZW58MHx8fHwxNzc3OTQwNjI4fDA&ixlib=rb-4.1.0&q=85";

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
  const [shops, setShops] = useState([]);
  const [restaurants, setRestaurants] = useState([]);
  const [wholesaleProducts, setWholesaleProducts] = useState([]);
  const [allProducts, setAllProducts] = useState([]);
  const { area, setArea } = useCart();

  useEffect(() => {
    api.get("/shops?kind=retail").then((r) => setShops(r.data));
    api.get("/restaurants").then((r) => setRestaurants(r.data));
    api.get("/products?is_wholesale=true").then((r) => setWholesaleProducts(r.data));
    api.get("/products").then((r) => setAllProducts(r.data));
  }, []);

  const categories = [...new Set(shops.map((s) => s.category))];
  const productsByShop = (shopId) => allProducts.filter((p) => p.shop_id === shopId).slice(0, 4);

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      {/* HERO */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <img src={HERO_IMG} alt="" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-r from-[#0E1A2B]/95 via-[#0E1A2B]/80 to-[#0E1A2B]/40" />
        </div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 sm:py-28 lg:py-36">
          <div className="max-w-2xl fade-up">
            <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur border border-white/20 rounded-full px-3 py-1.5 mb-6">
              <Sparkles className="w-3.5 h-3.5 text-[#E9C46A]" />
              <span className="text-[11px] uppercase tracking-[0.18em] text-white font-bold">
                Juba's Trusted Marketplace
              </span>
            </div>
            <h1 className="font-display font-bold text-4xl sm:text-5xl lg:text-6xl text-white tracking-tight">
              Shop Everything in Juba — <span className="text-[#E9C46A]">Retail & Wholesale</span>
            </h1>
            <p className="text-white/90 text-base sm:text-lg mt-5 max-w-xl">
              From groceries to electronics, buy from trusted local shops.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to="/marketplace"
                data-testid="hero-marketplace-btn"
                className="bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-7 py-3.5 rounded-full inline-flex items-center gap-2 transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5"
              >
                Start Shopping <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                to="/marketplace?view=wholesale"
                data-testid="hero-wholesale-btn"
                className="bg-[#1E3A5F] hover:bg-[#2A4D77] text-white font-semibold px-7 py-3.5 rounded-full inline-flex items-center gap-2 transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5 border border-white/20"
              >
                <Package className="w-4 h-4" /> Explore Wholesale
              </Link>
            </div>
            <div className="mt-8 flex items-center gap-3">
              <span className="text-white/70 text-sm">Browsing in:</span>
              <AreaSelector value={area} onChange={setArea} testId="home-area-selector" />
            </div>
          </div>
        </div>
      </section>

      {/* CATEGORIES */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20 w-full">
        <div className="flex items-end justify-between flex-wrap gap-4 mb-8">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold mb-2">Browse</p>
            <h2 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">Shop by category</h2>
          </div>
          <Link to="/marketplace" className="text-sm font-semibold text-[#C84B31] hover:underline" data-testid="see-all-categories">
            See all →
          </Link>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {categories.map((cat) => (
            <Link
              key={cat}
              to={`/marketplace?category=${encodeURIComponent(cat)}`}
              data-testid={`category-card-${cat.replace(/\s+/g, "-").toLowerCase()}`}
              className="js-card overflow-hidden flex flex-col hover:-translate-y-1 hover:shadow-xl transition-all duration-300"
            >
              <div className="aspect-square overflow-hidden bg-[#F2EBE5]">
                <img
                  src={CATEGORY_ICONS[cat] || ""}
                  alt={cat}
                  className="w-full h-full object-cover hover:scale-110 transition-transform duration-500"
                />
              </div>
              <div className="p-3 text-center">
                <p className="font-display font-semibold text-sm text-[#1A1A1A]">{cat}</p>
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
                  <Package className="w-3 h-3" /> Wholesale
                </span>
                <h2 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">Bulk Deals (Wholesale)</h2>
                <p className="text-sm text-[#5C5C5C] mt-1">Buy more, pay less.</p>
              </div>
              <Link to="/marketplace?view=wholesale" data-testid="see-all-wholesale" className="text-sm font-semibold text-[#2D6A4F] hover:underline">
                Explore all wholesale →
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
            <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold mb-2">Featured</p>
            <h2 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">Verified shops in Juba</h2>
          </div>
          <Link to="/shops" className="text-sm font-semibold text-[#C84B31] hover:underline">View all shops →</Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {shops.slice(0, 6).map((s) => (
            <ShopCard key={s.id} shop={s} productsPreview={productsByShop(s.id)} />
          ))}
        </div>
      </section>

      {/* FOOD & RESTAURANTS */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16 w-full">
        <div className="flex items-end justify-between flex-wrap gap-4 mb-8">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold mb-2">Hungry?</p>
            <h2 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">Food & Restaurants</h2>
          </div>
          <Link to="/restaurants" className="text-sm font-semibold text-[#C84B31] hover:underline">All restaurants →</Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {restaurants.slice(0, 4).map((r) => <RestaurantCard key={r.id} restaurant={r} />)}
        </div>
      </section>

      <Footer />
    </div>
  );
}
