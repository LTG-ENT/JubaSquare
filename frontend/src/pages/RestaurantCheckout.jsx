import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useCart } from "@/context/CartContext";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import AreaSelectField from "@/components/AreaSelectField";
import { Star, Truck, MapPin, Phone, User, CreditCard, Clock, ArrowLeft, Trash2, Minus, Plus } from "lucide-react";
import api, { formatPrice } from "@/lib/api";
import { toast } from "sonner";

export default function RestaurantCheckout() {
  const { items, restaurantId, restaurantName, subtotalUSD, clear, currency, exchangeRate, removeItem, setQuantity } = useCart();
  const { user } = useAuth();
  const navigate = useNavigate();
  
  const [restaurant, setRestaurant] = useState(null);
  const [loading, setLoading] = useState(true);
  const [placing, setPlacing] = useState(false);
  
  // Form fields
  const [deliveryType, setDeliveryType] = useState("delivery");
  const [customerName, setCustomerName] = useState(user?.name || "");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerAddress, setCustomerAddress] = useState("");
  const [deliveryArea, setDeliveryArea] = useState("Munuki");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [note, setNote] = useState("");
  
  // Calculated values
  const [deliveryFee, setDeliveryFee] = useState(0);
  
  useEffect(() => {
    if (!user) {
      navigate("/login");
      return;
    }
    
    if (!restaurantId || items.length === 0) {
      toast.error("Your cart is empty");
      navigate("/restaurants");
      return;
    }
    
    // Fetch restaurant details
    api.get(`/restaurants/${restaurantId}`)
      .then((r) => {
        setRestaurant(r.data);
        setLoading(false);
      })
      .catch(() => {
        toast.error("Restaurant not found");
        navigate("/restaurants");
      });
  }, [restaurantId, user, navigate, items.length]);
  
  // Calculate delivery fee using backend API (admin pricing rules)
  useEffect(() => {
    const calculateFee = async () => {
      if (!restaurant || deliveryType === "pickup" || !deliveryArea) {
        setDeliveryFee(0);
        return;
      }
      
      try {
        // Use COD delivery fee calculation endpoint
        const { data } = await api.post("/restaurant-orders/quote", {
          restaurant_id: restaurantId,
          items: items.map(item => ({
            item_type: item.item_type || "menu_item",
            item_id: item.item_id,
            name: item.name,
            price_usd: item.price_usd,
            quantity: item.quantity,
            sides: item.sides || [],
          })),
          delivery_type: deliveryType,
          customer_area: deliveryArea,
        });
        setDeliveryFee(data.delivery_fee_usd || 0);
      } catch (err) {
        console.error("Failed to calculate delivery fee:", err);
        setDeliveryFee(0);
      }
    };
    
    calculateFee();
  }, [restaurant, deliveryType, deliveryArea, restaurantId, items]);
  
  const total = subtotalUSD + deliveryFee;
  
  const placeOrder = async () => {
    // Validation
    if (!customerName.trim()) {
      toast.error("Please enter your name");
      return;
    }
    if (!customerPhone.trim()) {
      toast.error("Please enter your phone number");
      return;
    }
    if (deliveryType === "delivery" && !customerAddress.trim()) {
      toast.error("Please enter your delivery address");
      return;
    }
    
    setPlacing(true);
    
    try {
      const orderData = {
        restaurant_id: restaurantId,
        items: items.map((item) => ({
          item_type: item.item_type || "menu_item",
          item_id: item.item_id,
          name: item.name,
          price_usd: item.price_usd,
          quantity: item.quantity,
          image_url: item.image_url || "",
          sides: item.sides || [],
        })),
        delivery_type: deliveryType,
        customer_name: customerName,
        customer_phone: customerPhone,
        customer_address: deliveryType === "delivery" ? customerAddress : "",
        customer_area: deliveryArea,  // NEW: Pass customer area for delivery fee calculation
        payment_method: paymentMethod,
        note: note,
      };
      
      const response = await api.post("/restaurant-orders", orderData);
      
      toast.success("Order placed successfully!");
      clear();
      
      // Navigate to orders page
      navigate("/orders");
    } catch (err) {
      console.error("Order placement error:", err);
      toast.error(err.response?.data?.detail || "Failed to place order. Please try again.");
    } finally {
      setPlacing(false);
    }
  };
  
  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--js-background)]">
        <Header />
        <div className="max-w-4xl mx-auto px-4 py-20 text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-gray-200 border-t-[#C84B31]"></div>
          <p className="mt-4 text-[var(--js-text-secondary)]">Loading checkout...</p>
        </div>
        <Footer />
      </div>
    );
  }
  
  if (!restaurant) {
    return null;
  }
  
  return (
    <div className="min-h-screen bg-[var(--js-background)]">
      <Header />
      
      <div className="max-w-4xl mx-auto px-4 py-8">
        <button
          onClick={() => navigate(-1)}
          data-testid="restaurant-checkout-back-btn"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-[var(--js-text-secondary)] hover:text-[var(--js-text)] mb-4"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        {/* Restaurant Header */}
        <div className="bg-white dark:bg-[#1A1A1A] rounded-2xl p-6 mb-6 shadow-sm border border-[var(--js-border)]">
          <div className="flex items-start gap-4">
            {restaurant.image_url && (
              <img
                src={restaurant.image_url}
                alt={restaurant.name}
                className="w-20 h-20 rounded-xl object-cover"
              />
            )}
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-[var(--js-text)]">{restaurant.name}</h1>
              <div className="flex items-center gap-4 mt-2 text-sm text-[var(--js-text-secondary)]">
                {restaurant.average_rating && (
                  <div className="flex items-center gap-1">
                    <Star className="w-4 h-4 fill-[#E9C46A] text-[#E9C46A]" />
                    <span className="font-semibold">{restaurant.average_rating}</span>
                    <span>({restaurant.review_count || 0} reviews)</span>
                  </div>
                )}
                <div className="flex items-center gap-1">
                  <Clock className="w-4 h-4" />
                  <span>30-45 min</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left: Form */}
          <div className="lg:col-span-2 space-y-6">
            {/* Delivery Options - Delivery Only */}
            <div className="bg-white dark:bg-[#1A1A1A] rounded-2xl p-6 shadow-sm border border-[var(--js-border)]">
              <h2 className="text-lg font-bold text-[var(--js-text)] mb-4 flex items-center gap-2">
                <Truck className="w-5 h-5" />
                Delivery Options
              </h2>
              <div className="p-4 rounded-xl border-2 border-[#C84B31] bg-[#C84B31]/5">
                <Truck className="w-6 h-6 mx-auto mb-2 text-[var(--js-text)]" />
                <div className="text-sm font-semibold text-[var(--js-text)] text-center">Delivery</div>
              </div>
            </div>
            
            {/* Customer Info */}
            <div className="bg-white dark:bg-[#1A1A1A] rounded-2xl p-6 shadow-sm border border-[var(--js-border)]">
              <h2 className="text-lg font-bold text-[var(--js-text)] mb-4 flex items-center gap-2">
                <User className="w-5 h-5" />
                Customer Information
              </h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-[var(--js-text)] mb-2">Name</label>
                  <input
                    type="text"
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                    placeholder="Your name"
                    className="w-full px-4 py-3 rounded-xl border border-[var(--js-border)] bg-[var(--js-background)] text-[var(--js-text)] focus:outline-none focus:ring-2 focus:ring-[#C84B31]"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-[var(--js-text)] mb-2">Phone Number</label>
                  <input
                    type="tel"
                    value={customerPhone}
                    onChange={(e) => setCustomerPhone(e.target.value)}
                    placeholder="+211 XXX XXX XXX"
                    className="w-full px-4 py-3 rounded-xl border border-[var(--js-border)] bg-[var(--js-background)] text-[var(--js-text)] focus:outline-none focus:ring-2 focus:ring-[#C84B31]"
                  />
                </div>
                {deliveryType === "delivery" && (
                  <>
                    <div>
                      <label className="block text-sm font-semibold text-[var(--js-text)] mb-2">Delivery Area</label>
                      <AreaSelectField 
                        value={deliveryArea} 
                        onChange={setDeliveryArea}
                        testId="checkout-delivery-area"
                      />
                      {restaurant?.delivery_pricing?.type === "per_area" && (
                        <p className="text-xs text-[var(--js-text-secondary)] mt-1">
                          Delivery fee varies by area
                        </p>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-[var(--js-text)] mb-2">Delivery Address</label>
                      <textarea
                        value={customerAddress}
                        onChange={(e) => setCustomerAddress(e.target.value)}
                        placeholder="Enter your full delivery address (street, building, etc.)"
                        rows={3}
                        className="w-full px-4 py-3 rounded-xl border border-[var(--js-border)] bg-[var(--js-background)] text-[var(--js-text)] focus:outline-none focus:ring-2 focus:ring-[#C84B31] resize-none"
                      />
                    </div>
                  </>
                )}
                <div>
                  <label className="block text-sm font-semibold text-[var(--js-text)] mb-2">Note (Optional)</label>
                  <textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Any special instructions..."
                    rows={2}
                    className="w-full px-4 py-3 rounded-xl border border-[var(--js-border)] bg-[var(--js-background)] text-[var(--js-text)] focus:outline-none focus:ring-2 focus:ring-[#C84B31] resize-none"
                  />
                </div>
              </div>
            </div>
            
            {/* Payment Method */}
            <div className="bg-white dark:bg-[#1A1A1A] rounded-2xl p-6 shadow-sm border border-[var(--js-border)]">
              <h2 className="text-lg font-bold text-[var(--js-text)] mb-4 flex items-center gap-2">
                <CreditCard className="w-5 h-5" />
                Payment Method
              </h2>
              <div className="p-4 rounded-xl border-2 border-[#C84B31] bg-[#C84B31]/5">
                <div className="font-semibold text-[var(--js-text)]">Cash on Delivery</div>
                <div className="text-sm text-[var(--js-text-secondary)] mt-1">Pay when your order arrives</div>
              </div>
            </div>
          </div>
          
          {/* Right: Order Summary */}
          <div className="lg:col-span-1">
            <div className="bg-white dark:bg-[#1A1A1A] rounded-2xl p-6 shadow-sm border border-[var(--js-border)] sticky top-24">
              <h2 className="text-lg font-bold text-[var(--js-text)] mb-4">Order Summary</h2>
              
              {/* Items */}
              <div className="space-y-3 mb-4 max-h-72 overflow-y-auto">
                {items.map((item) => (
                  <div key={item.item_id} data-testid={`rest-cart-row-${item.item_id}`} className="flex justify-between gap-2 text-sm">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-[var(--js-text)] truncate">{item.name}</div>
                      <div className="flex items-center gap-2 mt-1">
                        <div className="flex items-center bg-[var(--js-subtle)] rounded-full">
                          <button
                            type="button"
                            onClick={() => setQuantity(item.item_id, item.quantity - 1)}
                            data-testid={`rest-cart-minus-${item.item_id}`}
                            className="p-1 hover:bg-white rounded-full"
                            aria-label="Decrease quantity"
                          >
                            <Minus className="w-3 h-3" />
                          </button>
                          <span data-testid={`rest-cart-qty-${item.item_id}`} className="font-semibold text-xs w-6 text-center">{item.quantity}</span>
                          <button
                            type="button"
                            onClick={() => setQuantity(item.item_id, item.quantity + 1)}
                            data-testid={`rest-cart-plus-${item.item_id}`}
                            className="p-1 hover:bg-white rounded-full"
                            aria-label="Increase quantity"
                          >
                            <Plus className="w-3 h-3" />
                          </button>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeItem(item.item_id)}
                          data-testid={`rest-cart-remove-${item.item_id}`}
                          className="p-1 hover:bg-red-50 rounded-full"
                          title="Remove item"
                          aria-label={`Remove ${item.name}`}
                        >
                          <Trash2 className="w-3.5 h-3.5 text-[#C84B31]" />
                        </button>
                      </div>
                      {item.sides && item.sides.length > 0 && (
                        <div className="text-xs text-[var(--js-text-secondary)] mt-1">
                          + {item.sides.map(s => s.name).join(", ")}
                        </div>
                      )}
                    </div>
                    <div className="font-semibold text-[var(--js-text)] whitespace-nowrap">
                      {formatPrice(item.price_usd * item.quantity, currency, exchangeRate)}
                    </div>
                  </div>
                ))}
              </div>
              
              <div className="border-t border-[var(--js-border)] pt-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-[var(--js-text-secondary)]">Subtotal</span>
                  <span className="font-semibold text-[var(--js-text)]">
                    {formatPrice(subtotalUSD, currency, exchangeRate)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[var(--js-text-secondary)]">Delivery Fee</span>
                  <span className="font-semibold text-[var(--js-text)]">
                    {deliveryFee === 0 ? "FREE" : formatPrice(deliveryFee, currency, exchangeRate)}
                  </span>
                </div>
                <div className="flex justify-between text-lg font-bold pt-2 border-t border-[var(--js-border)]">
                  <span className="text-[var(--js-text)]">Total</span>
                  <span className="text-[#C84B31]">
                    {formatPrice(total, currency, exchangeRate)}
                  </span>
                </div>
              </div>
              
              <button
                onClick={placeOrder}
                disabled={placing}
                className="w-full mt-6 bg-[#C84B31] hover:bg-[#C84B31]/90 text-white font-bold py-4 rounded-xl transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {placing ? "Placing Order..." : "Place Order"}
              </button>
            </div>
          </div>
        </div>
      </div>
      
      <Footer />
    </div>
  );
}
