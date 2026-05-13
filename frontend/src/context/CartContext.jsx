import { createContext, useContext, useEffect, useState } from "react";
import { toast } from "sonner";

const CartContext = createContext(null);
const KEY = "js_cart_v1";

const readStorage = () => {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

export const CartProvider = ({ children }) => {
  const [items, setItems] = useState(() => readStorage()?.items || []);
  const [area, setArea] = useState(() => readStorage()?.area || "Munuki");
  const [exchangeRate, setExchangeRate] = useState(() => readStorage()?.exchangeRate || 600);
  const [currency, setCurrency] = useState(() => readStorage()?.currency || "SSP");

  // Cart-isolation tracking: marketplace vs restaurant
  const [cartMode, setCartMode] = useState(() => readStorage()?.cartMode || null); // null | "marketplace" | "restaurant"
  const [restaurantId, setRestaurantId] = useState(() => readStorage()?.restaurantId || null);
  const [restaurantName, setRestaurantName] = useState(() => readStorage()?.restaurantName || null);

  // Load global exchange rate from backend on mount
  useEffect(() => {
    const loadExchangeRate = async () => {
      try {
        const response = await fetch('/api/admin/settings');
        const data = await response.json();
        const rate = Number(data.global_rate ?? 600);
        if (rate !== exchangeRate) {
          setExchangeRate(rate);
        }
      } catch (err) {
        console.error('Failed to load exchange rate:', err);
      }
    };
    loadExchangeRate();
  }, []); // Only run on mount

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify({
      items, area, exchangeRate, currency, cartMode, restaurantId, restaurantName,
    }));
  }, [items, area, exchangeRate, currency, cartMode, restaurantId, restaurantName]);

  // Self-heal: if cart is empty, reset mode so the next add can start fresh
  useEffect(() => {
    if (items.length === 0 && (cartMode !== null || restaurantId !== null)) {
      setCartMode(null);
      setRestaurantId(null);
      setRestaurantName(null);
    }
  }, [items.length, cartMode, restaurantId]);

  /**
   * Add an item to cart with strict marketplace ⇄ restaurant isolation.
   * Returns `true` on success, `false` if blocked (so callers can skip success toasts).
   *
   * Pass `options.restaurant_id` (+ `restaurant_name`) when adding a menu item.
   * Omit it for marketplace/wholesale products.
   */
  const addItem = (item, options = {}) => {
    const { restaurant_id, restaurant_name } = options;
    const isRestaurantItem = !!restaurant_id;
    const activeMode = items.length === 0 ? null : cartMode;

    // Block: trying to add a marketplace item while cart already holds restaurant items
    if (!isRestaurantItem && activeMode === "restaurant") {
      toast.error(
        "You have items from another order type. Please clear cart to continue.",
        { duration: 4000, id: "cart-isolation" }
      );
      return false;
    }

    // Block: trying to add a restaurant item while cart already holds marketplace items
    if (isRestaurantItem && activeMode === "marketplace") {
      toast.error(
        "You have items from another order type. Please clear cart to continue.",
        { duration: 4000, id: "cart-isolation" }
      );
      return false;
    }

    // Block: trying to add a menu item from a different restaurant
    if (isRestaurantItem && restaurantId && restaurantId !== restaurant_id) {
      toast.error(
        `Cart contains items from ${restaurantName}. Please clear cart before adding from a different restaurant.`,
        { duration: 4000, id: "cart-isolation" }
      );
      return false;
    }

    // First item — lock the cart mode accordingly
    if (items.length === 0) {
      if (isRestaurantItem) {
        setCartMode("restaurant");
        setRestaurantId(restaurant_id);
        setRestaurantName(restaurant_name);
      } else {
        setCartMode("marketplace");
        setRestaurantId(null);
        setRestaurantName(null);
      }
    }

    setItems((prev) => {
      const idx = prev.findIndex(
        (i) => i.item_id === item.item_id && i.item_type === item.item_type,
      );
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = { ...copy[idx], quantity: copy[idx].quantity + (item.quantity || 1) };
        return copy;
      }
      return [...prev, { ...item, quantity: item.quantity || 1 }];
    });

    return true;
  };

  const removeItem = (item_id) =>
    setItems((prev) => prev.filter((i) => i.item_id !== item_id));

  const setQuantity = (item_id, qty) =>
    setItems((prev) =>
      prev.map((i) => (i.item_id === item_id ? { ...i, quantity: Math.max(1, qty) } : i)),
    );

  const clear = () => {
    setItems([]);
    setCartMode(null);
    setRestaurantId(null);
    setRestaurantName(null);
  };

  const subtotalUSD = items.reduce((s, i) => s + i.price_usd * i.quantity, 0);
  // Per-line SSP using each line's own seller rate (falls back to global rate)
  const subtotalSSP = items.reduce(
    (s, i) => s + i.price_usd * i.quantity * (i.exchange_rate_ssp || exchangeRate || 600),
    0,
  );
  const count = items.reduce((s, i) => s + i.quantity, 0);

  const toggleCurrency = () => setCurrency((c) => (c === "USD" ? "SSP" : "USD"));

  return (
    <CartContext.Provider
      value={{
        items, area, exchangeRate, count, subtotalUSD, subtotalSSP, currency,
        cartMode, restaurantId, restaurantName,
        addItem, removeItem, setQuantity, clear, setArea, setExchangeRate,
        setCurrency, toggleCurrency,
      }}
    >
      {children}
    </CartContext.Provider>
  );
};

export const useCart = () => useContext(CartContext);
