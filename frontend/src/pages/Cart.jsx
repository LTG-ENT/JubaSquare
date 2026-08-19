import { useNavigate } from "react-router-dom";
import { useCart } from "@/context/CartContext";
import { useAuth } from "@/context/AuthContext";
import { useTranslation } from "react-i18next";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import AreaSelector from "@/components/AreaSelector";
import { Minus, Plus, Trash2, ShoppingBag, Truck, ArrowLeft } from "lucide-react";
import api, { formatPrice, formatPriceAlt, wholesaleUnitPrice } from "@/lib/api";
import { useState, useEffect } from "react";
import { toast } from "sonner";

export default function Cart() {
  const { items, removeItem, setQuantity, subtotalUSD, subtotalSSP, area, setArea, clear, exchangeRate, setExchangeRate, currency, cartMode, restaurantId } = useCart();
  const { user } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  
  // Redirect to RestaurantCheckout if cart is in restaurant mode
  useEffect(() => {
    if (cartMode === "restaurant" && restaurantId && items.length > 0) {
      navigate("/restaurant-checkout");
    }
  }, [cartMode, restaurantId, items.length, navigate]);
  
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [note, setNote] = useState("");
  const [placing, setPlacing] = useState(false);
  const [quote, setQuote] = useState({ delivery_fee_usd: 0, total_usd: subtotalUSD, delivery_breakdown: [] });

  useEffect(() => {
    api.get("/exchange-rate").then((r) => setExchangeRate(r.data?.rate || 600));
  }, [setExchangeRate]);

  // Recompute delivery quote when items or area change
  useEffect(() => {
    if (!user || items.length === 0 || !area) {
      setQuote({ delivery_fee_usd: 0, total_usd: subtotalUSD, delivery_breakdown: [] });
      return;
    }
    const t = setTimeout(async () => {
      try {
        const hasMenu = items.some((i) => i.item_type === "menu_item");
        const isWholesale = items.some((i) => (i.quantity || 1) >= 5);
        const { data } = await api.post("/orders/quote", {
          items: items.map((i) => ({
            item_type: i.item_type, item_id: i.item_id, name: i.name,
            price_usd: i.price_usd, quantity: i.quantity, image_url: i.image_url,
            sides: i.sides || [],
          })),
          area, address: address || "", phone: phone || "x",
          order_kind: hasMenu ? "restaurant" : (isWholesale ? "wholesale" : "marketplace"),
        });
        setQuote(data);
      } catch {
        // user may not be logged in — fallback
        setQuote({ delivery_fee_usd: 0, total_usd: subtotalUSD, delivery_breakdown: [] });
      }
    }, 250);
    return () => clearTimeout(t);
  }, [items, area, user, subtotalUSD, address, phone]);

  const place = async () => {
    if (!user) { navigate("/login"); return; }
    if (items.length === 0) { toast.error(t("toastCartEmpty")); return; }
    if (!phone.trim()) { toast.error(t("toastPhoneRequired")); return; }
    if (!area || !area.trim()) { toast.error(t("toastAreaRequired")); return; }
    setPlacing(true);
    try {
      const hasMenu = items.some((i) => i.item_type === "menu_item");
      const isWholesale = items.some((i) => (i.quantity || 1) >= 5);
      const { data } = await api.post("/orders", {
        items: items.map((i) => ({
          item_type: i.item_type, item_id: i.item_id, name: i.name,
          price_usd: i.price_usd, quantity: i.quantity, image_url: i.image_url,
          sides: i.sides || [],
        })),
        area, address, phone, note,
        order_kind: hasMenu ? "restaurant" : (isWholesale ? "wholesale" : "marketplace"),
      });
      toast.success(t("toastOrderPlaced"));
      clear();
      navigate(`/orders?new=${data.id}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || t("toastFailedPlaceOrder"));
    } finally {
      setPlacing(false);
    }
  };

  const total = (quote.total_usd ?? subtotalUSD);

  // SSP-equivalent total = sum-of-lines-at-per-shop-rate + delivery (at global rate)
  const deliveryFeeUSD = quote.delivery_fee_usd || 0;
  const totalSSP = subtotalSSP + deliveryFeeUSD * (exchangeRate || 600);

  // Formatters that honor per-line rates when displaying SSP totals
  const fmtSubtotal = currency === "USD"
    ? `$${subtotalUSD.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : `SSP ${Math.round(subtotalSSP).toLocaleString()}`;
  const fmtSubtotalAlt = currency === "USD"
    ? `SSP ${Math.round(subtotalSSP).toLocaleString()}`
    : `$${subtotalUSD.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const fmtTotal = currency === "USD"
    ? `$${total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : `SSP ${Math.round(totalSSP).toLocaleString()}`;
  const fmtTotalAlt = currency === "USD"
    ? `SSP ${Math.round(totalSSP).toLocaleString()}`
    : `$${total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <button
          onClick={() => navigate(-1)}
          data-testid="cart-back-btn"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-[#5C5C5C] hover:text-[#1A1A1A] mb-4 -mt-2"
        >
          <ArrowLeft className="w-4 h-4" /> {t("back")}
        </button>
        <h1 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">{t("yourCart")}</h1>
        <p className="text-sm text-[#5C5C5C] mt-1">{t("itemCount", { count: items.length })}</p>

        {items.length === 0 ? (
          <div className="mt-12 text-center py-20 bg-white rounded-3xl border border-[#E2E2D9]" data-testid="empty-cart">
            <ShoppingBag className="w-12 h-12 mx-auto text-[#A3A39E]" />
            <p className="font-display font-semibold text-xl text-[#1A1A1A] mt-4">{t("cartEmpty")}</p>
            <p className="text-sm text-[#5C5C5C] mt-1">{t("cartEmptyHint")}</p>
            <button
              onClick={() => navigate("/marketplace")}
              data-testid="cart-shop-now-btn"
              className="mt-6 bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-6 py-3 rounded-full transition"
            >
              {t("startShopping")}
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
                      <p className="font-display font-bold text-[#1A1A1A]">{formatPrice(wholesaleUnitPrice(i, i.quantity), i.exchange_rate_ssp || exchangeRate, currency)}</p>
                      <p className="text-xs text-[#5C5C5C]">≈ {formatPriceAlt(wholesaleUnitPrice(i, i.quantity), i.exchange_rate_ssp || exchangeRate, currency)}<span className="ml-1">/ unit</span></p>
                    </div>
                  </div>
                  <div className="flex flex-col items-end justify-between">
                    <button onClick={() => removeItem(i.item_id)} data-testid={`remove-${i.item_id}`} className="p-2 hover:bg-[#F2EBE5] rounded-full">
                      <Trash2 className="w-4 h-4 text-[#C84B31]" />
                    </button>
                    <div className="flex flex-col items-end gap-1">
                    <div className="flex items-center gap-2 bg-[#F2EBE5] rounded-full px-2 py-1">
                      <button onClick={() => setQuantity(i.item_id, i.quantity - 1)} data-testid={`qty-minus-${i.item_id}`} className="p-1 hover:bg-white rounded-full disabled:opacity-40" disabled={i.quantity <= (i.is_wholesale ? Math.max(1, i.min_order_qty || 1) : 1)}>
                        <Minus className="w-3 h-3" />
                      </button>
                      <input
                        type="text"
                        inputMode="numeric"
                        value={i.quantity}
                        onChange={(e) => {
                          const raw = e.target.value.replace(/[^0-9]/g, "");
                          if (raw === "") return;
                          setQuantity(i.item_id, parseInt(raw, 10));
                        }}
                        data-testid={`qty-${i.item_id}`}
                        className="font-semibold text-sm w-10 text-center bg-transparent focus:outline-none"
                      />
                      <button onClick={() => setQuantity(i.item_id, i.quantity + 1)} data-testid={`qty-plus-${i.item_id}`} className="p-1 hover:bg-white rounded-full disabled:opacity-40" disabled={Number.isFinite(i.stock) && i.quantity >= i.stock}>
                        <Plus className="w-3 h-3" />
                      </button>
                    </div>
                    {Number.isFinite(i.stock) && i.quantity >= i.stock && (
                      <span className="text-[10px] text-[#C84B31] font-semibold" data-testid={`qty-max-${i.item_id}`}>Max {i.stock} in stock</span>
                    )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <aside className="bg-white border border-[#E2E2D9] rounded-3xl p-6 h-fit lg:sticky lg:top-24 space-y-4">
              <h2 className="font-display font-semibold text-xl text-[#1A1A1A]">{t("delivery")}</h2>

              <div>
                <label className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">{t("area")}</label>
                <AreaSelector value={area} onChange={setArea} testId="cart-area-selector" />
              </div>

              <div>
                <label className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">{t("address")}</label>
                <input
                  data-testid="cart-address-input"
                  value={address} onChange={(e) => setAddress(e.target.value)}
                  placeholder={t("addressPlaceholder")}
                  className="js-input"
                />
              </div>

              <div>
                <label className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">{t("phone")} <span className="text-[#D90429]">*</span></label>
                <input
                  required
                  data-testid="cart-phone-input"
                  value={phone} onChange={(e) => setPhone(e.target.value)}
                  placeholder="+211 ..."
                  className="js-input"
                />
              </div>

              <div>
                <label className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">{t("note")}</label>
                <textarea
                  data-testid="cart-note-input"
                  value={note} onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  className="js-input"
                />
              </div>

              <div className="border-t border-[#E2E2D9] pt-4 space-y-1.5">
                <div className="flex justify-between text-sm text-[#5C5C5C]">
                  <span>{t("subtotal")}</span>
                  <span data-testid="cart-subtotal">{fmtSubtotal}</span>
                </div>

                {/* Hide per-shop breakdown, show only total delivery */}
                <div className="flex justify-between text-sm text-[#5C5C5C]">
                  <span className="flex items-center gap-1">
                    <Truck className="w-3.5 h-3.5 text-[#2D6A4F]" /> {t("delivery")}
                  </span>
                  <span data-testid="cart-delivery-total" className="font-semibold">
                    {quote.delivery_fee_usd === 0 ? <span className="text-[#2D6A4F]">{t("free")}</span> : formatPrice(quote.delivery_fee_usd, exchangeRate, currency)}
                  </span>
                </div>

                <div className="flex justify-between font-bold text-lg pt-2 border-t border-[#E2E2D9]">
                  <span>{t("total")}</span>
                  <span className="font-display" data-testid="cart-total">{fmtTotal}</span>
                </div>
                <p className="text-[11px] text-[#5C5C5C] text-right">≈ {fmtTotalAlt}</p>
              </div>

              <button
                onClick={place}
                disabled={placing}
                data-testid="place-order-btn"
                className="w-full bg-[#C84B31] hover:bg-[#A83A23] disabled:bg-[#A3A39E] text-white font-semibold py-3.5 rounded-full transition"
              >
                {placing ? t("placing") : `${t("placeOrder")} · ${fmtTotal}`}
              </button>
              {!user && <p className="text-xs text-center text-[#5C5C5C]">{t("loginFirstHint")}</p>}
            </aside>
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
