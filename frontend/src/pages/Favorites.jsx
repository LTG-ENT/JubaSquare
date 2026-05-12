import { useEffect, useState } from "react";
import { Heart } from "lucide-react";
import api, { formatUSD, formatSSP } from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { useCart } from "@/context/CartContext";
import { Link } from "react-router-dom";
import { toast } from "sonner";

export default function Favorites() {
  const [favs, setFavs] = useState([]);
  const [products, setProducts] = useState([]);
  const [shops, setShops] = useState([]);
  const [restaurants, setRestaurants] = useState([]);
  const { exchangeRate, addItem } = useCart();

  const load = async () => {
    const [f, p, s, r] = await Promise.all([
      api.get("/favorites?limit=200"),
      api.get("/products?limit=200"),
      api.get("/shops?limit=200"),
      api.get("/restaurants?limit=200"),
    ]);
    setFavs(f.data); setProducts(p.data); setShops(s.data); setRestaurants(r.data);
  };
  useEffect(() => { load(); }, []);

  const remove = async (target_type, target_id) => {
    await api.delete(`/favorites?target_type=${target_type}&target_id=${target_id}`);
    toast.success("Removed");
    load();
  };

  const productById = Object.fromEntries(products.map((p) => [p.id, p]));
  const shopById = Object.fromEntries(shops.map((s) => [s.id, s]));
  const restaurantById = Object.fromEntries(restaurants.map((r) => [r.id, r]));

  const favProducts = favs.filter((f) => f.target_type === "product").map((f) => productById[f.target_id]).filter(Boolean);
  const favShops = favs.filter((f) => f.target_type === "shop").map((f) => shopById[f.target_id]).filter(Boolean);
  const favRestaurants = favs.filter((f) => f.target_type === "restaurant").map((f) => restaurantById[f.target_id]).filter(Boolean);

  const Empty = () => (
    <div className="text-center py-20 bg-white rounded-3xl border border-[var(--js-border)]" data-testid="empty-favorites">
      <Heart className="w-12 h-12 mx-auto text-[var(--js-text-disabled)]" />
      <p className="font-display font-semibold text-xl text-[var(--js-text)] mt-4">No favorites yet</p>
      <p className="text-sm text-[var(--js-text-secondary)] mt-1">Tap the heart icon on any product, shop or restaurant to save it.</p>
      <Link to="/marketplace" className="inline-block mt-5 bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-6 py-3 rounded-full">Browse marketplace</Link>
    </div>
  );

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <h1 className="font-display font-bold text-3xl sm:text-4xl text-[var(--js-text)]">My favorites</h1>
        <p className="text-sm text-[var(--js-text-secondary)] mt-1">{favs.length} saved item{favs.length !== 1 && "s"}</p>

        {favs.length === 0 ? <div className="mt-10"><Empty /></div> : (
          <div className="mt-8 space-y-10">
            {favProducts.length > 0 && (
              <section>
                <h2 className="font-display font-semibold text-xl text-[var(--js-text)] mb-4">Products</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                  {favProducts.map((p) => (
                    <div key={p.id} className="js-card overflow-hidden" data-testid={`fav-product-${p.id}`}>
                      <img src={p.image_url} alt="" className="aspect-[4/3] w-full object-cover" />
                      <div className="p-3">
                        <p className="font-semibold text-sm text-[var(--js-text)]">{p.name}</p>
                        <p className="font-display font-bold text-[var(--js-text)] mt-1">{formatUSD(p.price_usd)}</p>
                        <p className="text-xs text-[var(--js-text-secondary)]">{formatSSP(p.price_usd, exchangeRate)}</p>
                        <div className="flex gap-2 mt-3">
                          <button
                            onClick={() => { const ok = addItem({ item_type: "product", item_id: p.id, name: p.name, price_usd: p.price_usd, image_url: p.image_url, quantity: 1 }); if (ok) toast.success("Added"); }}
                            data-testid={`fav-add-cart-${p.id}`}
                            className="flex-1 bg-[#1A1A1A] text-white text-xs font-semibold py-2 rounded-full">Add to cart</button>
                          <button onClick={() => remove("product", p.id)} data-testid={`fav-remove-product-${p.id}`} className="bg-[var(--js-subtle)] text-[var(--js-text)] text-xs font-semibold px-3 py-2 rounded-full">Remove</button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
            {favShops.length > 0 && (
              <section>
                <h2 className="font-display font-semibold text-xl text-[var(--js-text)] mb-4">Shops</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                  {favShops.map((s) => (
                    <div key={s.id} className="js-card overflow-hidden" data-testid={`fav-shop-${s.id}`}>
                      <img src={s.image_url} alt="" className="aspect-[16/10] w-full object-cover" />
                      <div className="p-4 flex items-start justify-between gap-2">
                        <div>
                          <p className="font-display font-semibold text-[var(--js-text)]">{s.name}</p>
                          <p className="text-xs text-[var(--js-text-secondary)]">{s.category}</p>
                        </div>
                        <button onClick={() => remove("shop", s.id)} data-testid={`fav-remove-shop-${s.id}`} className="bg-[var(--js-subtle)] text-[var(--js-text)] text-xs font-semibold px-3 py-1.5 rounded-full shrink-0">Remove</button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
            {favRestaurants.length > 0 && (
              <section>
                <h2 className="font-display font-semibold text-xl text-[var(--js-text)] mb-4">Restaurants</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                  {favRestaurants.map((r) => (
                    <div key={r.id} className="js-card overflow-hidden" data-testid={`fav-restaurant-${r.id}`}>
                      <img src={r.image_url} alt="" className="aspect-[16/10] w-full object-cover" />
                      <div className="p-4 flex items-start justify-between gap-2">
                        <div>
                          <p className="font-display font-semibold text-[var(--js-text)]">{r.name}</p>
                          <p className="text-xs text-[var(--js-text-secondary)]">{r.category}</p>
                        </div>
                        <button onClick={() => remove("restaurant", r.id)} data-testid={`fav-remove-restaurant-${r.id}`} className="bg-[var(--js-subtle)] text-[var(--js-text)] text-xs font-semibold px-3 py-1.5 rounded-full shrink-0">Remove</button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
