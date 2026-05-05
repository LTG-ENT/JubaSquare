import { useNavigate } from "react-router-dom";
import { useCart } from "@/context/CartContext";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import AreaSelector from "@/components/AreaSelector";
import { Minus, Plus, Trash2, ShoppingBag } from "lucide-react";
import api, { formatUSD, formatSSP } from "@/lib/api";
import { useState, useEffect } from "react";
import { toast } from "sonner";

export default function Cart() {
  const { items, removeItem, setQuantity, subtotalUSD, area, setArea, clear, exchangeRate, setExchangeRate } = useCart();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [note, setNote] = useState("");
  const [placing, setPlacing] = useState(false);

  useEffect(() => {
    api.get("/exchange-rate").then((r) => setExchangeRate(r.data?.rate || 600));
  }, [setExchangeRate]);

  const place = async () => {
    if (!user) { navigate("/login"); return; }
    if (items.length === 0) { toast.error("Cart is empty"); return; }
    setPlacing(true);
    try {
      const hasMenu = items.some((i) => i.item_type === "menu_item");
      const { data } = await api.post("/orders", {
        items: items.map((i) => ({
          item_type: i.item_type, item_id: i.item_id, name: i.name,
          price_usd: i.price_usd, quantity: i.quantity, image_url: i.image_url,
        })),
        area, address, phone, note,
        order_kind: hasMenu ? "restaurant" : "marketplace",
      });
      toast.success("Order placed successfully!");
      clear();
      navigate(`/orders?new=${data.id}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to place order");
    } finally {
      setPlacing(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <h1 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">Your cart</h1>
        <p className="text-sm text-[#5C5C5C] mt-1">{items.length} item{items.length !== 1 && "s"}</p>

        {items.length === 0 ? (
          <div className="mt-12 text-center py-20 bg-white rounded-3xl border border-[#E2E2D9]" data-testid="empty-cart">
            <ShoppingBag className="w-12 h-12 mx-auto text-[#A3A39E]" />
            <p className="font-display font-semibold text-xl text-[#1A1A1A] mt-4">Your cart is empty</p>
            <p className="text-sm text-[#5C5C5C] mt-1">Browse our marketplace or restaurants to add items.</p>
            <button
              onClick={() => navigate("/marketplace")}
              data-testid="cart-shop-now-btn"
              className="mt-6 bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-6 py-3 rounded-full transition"
            >
              Start shopping
            </button>
          </div>
        ) : (
          <div className="mt-8 grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
            <div className="space-y-3">
              {items.map((i) => (
                <div key={i.item_id} data-testid={`cart-item-${i.item_id}`} className="bg-white border border-[#E2E2D9] rounded-2xl p-4 flex gap-4">
                  <img src={i.image_url} alt={i.name} className="w-24 h-24 rounded-xl object-cover" />
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-[#1A1A1A]">{i.name}</p>
                    <p className="text-[10px] uppercase tracking-wider text-[#5C5C5C] font-bold mt-0.5">{i.item_type === "menu_item" ? "Menu Item" : "Product"}</p>
                    <div className="mt-2">
                      <p className="font-display font-bold text-[#1A1A1A]">{formatUSD(i.price_usd)}</p>
                      <p className="text-xs text-[#5C5C5C]">{formatSSP(i.price_usd, exchangeRate)}</p>
                    </div>
                  </div>
                  <div className="flex flex-col items-end justify-between">
                    <button onClick={() => removeItem(i.item_id)} data-testid={`remove-${i.item_id}`} className="p-2 hover:bg-[#F2EBE5] rounded-full">
                      <Trash2 className="w-4 h-4 text-[#C84B31]" />
                    </button>
                    <div className="flex items-center gap-2 bg-[#F2EBE5] rounded-full px-2 py-1">
                      <button onClick={() => setQuantity(i.item_id, i.quantity - 1)} data-testid={`qty-minus-${i.item_id}`} className="p-1 hover:bg-white rounded-full">
                        <Minus className="w-3 h-3" />
                      </button>
                      <span className="font-semibold text-sm w-6 text-center" data-testid={`qty-${i.item_id}`}>{i.quantity}</span>
                      <button onClick={() => setQuantity(i.item_id, i.quantity + 1)} data-testid={`qty-plus-${i.item_id}`} className="p-1 hover:bg-white rounded-full">
                        <Plus className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <aside className="bg-white border border-[#E2E2D9] rounded-3xl p-6 h-fit lg:sticky lg:top-24 space-y-4">
              <h2 className="font-display font-semibold text-xl text-[#1A1A1A]">Delivery</h2>

              <div>
                <label className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">Area</label>
                <AreaSelector value={area} onChange={setArea} testId="cart-area-selector" />
              </div>

              <div>
                <label className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">Address</label>
                <input
                  data-testid="cart-address-input"
                  value={address} onChange={(e) => setAddress(e.target.value)}
                  placeholder="Block & street..."
                  className="js-input"
                />
              </div>

              <div>
                <label className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">Phone</label>
                <input
                  data-testid="cart-phone-input"
                  value={phone} onChange={(e) => setPhone(e.target.value)}
                  placeholder="+211 ..."
                  className="js-input"
                />
              </div>

              <div>
                <label className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">Note (optional)</label>
                <textarea
                  data-testid="cart-note-input"
                  value={note} onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  className="js-input"
                />
              </div>

              <div className="border-t border-[#E2E2D9] pt-4 space-y-1.5">
                <div className="flex justify-between text-sm text-[#5C5C5C]">
                  <span>Subtotal</span>
                  <span data-testid="cart-subtotal-usd">{formatUSD(subtotalUSD)}</span>
                </div>
                <div className="flex justify-between text-sm text-[#5C5C5C]">
                  <span>SSP equivalent</span>
                  <span data-testid="cart-subtotal-ssp">{formatSSP(subtotalUSD, exchangeRate)}</span>
                </div>
                <div className="flex justify-between font-bold text-lg pt-2">
                  <span>Total</span>
                  <span className="font-display">{formatUSD(subtotalUSD)}</span>
                </div>
              </div>

              <button
                onClick={place}
                disabled={placing}
                data-testid="place-order-btn"
                className="w-full bg-[#C84B31] hover:bg-[#A83A23] disabled:bg-[#A3A39E] text-white font-semibold py-3.5 rounded-full transition"
              >
                {placing ? "Placing..." : `Place Order · ${formatUSD(subtotalUSD)}`}
              </button>
              {!user && <p className="text-xs text-center text-[#5C5C5C]">You'll be asked to login first.</p>}
            </aside>
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
