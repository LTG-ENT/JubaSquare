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
  
  // NEW: Track cart mode and restaurant for single-restaurant rule
  const [cartMode, setCartMode] = useState(() => readStorage()?.cartMode || "marketplace"); // "marketplace" | "restaurant"
  const [restaurantId, setRestaurantId] = useState(() => readStorage()?.restaurantId || null);
  const [restaurantName, setRestaurantName] = useState(() => readStorage()?.restaurantName || null);

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify({ 
      items, area, exchangeRate, currency, cartMode, restaurantId, restaurantName 
    }));
  }, [items, area, exchangeRate, currency, cartMode, restaurantId, restaurantName]);

  const addItem = (item, options = {}) => {
    const { restaurant_id, restaurant_name, force = false } = options;
    
    // RESTAURANT MODE: Enforce single restaurant rule
    if (restaurant_id) {
      if (restaurantId && restaurantId !== restaurant_id && !force) {
        // Different restaurant - show warning
        toast.error(
          `Cart contains items from ${restaurantName}. Please clear cart before adding from a different restaurant.`,
          { duration: 4000 }
        );
        return false;
      }
      
      // Set restaurant mode
      if (!restaurantId) {
        setCartMode("restaurant");
        setRestaurantId(restaurant_id);
        setRestaurantName(restaurant_name);
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
    setCartMode("marketplace");
    setRestaurantId(null);
    setRestaurantName(null);
  };

  const subtotalUSD = items.reduce((s, i) => s + i.price_usd * i.quantity, 0);
  const count = items.reduce((s, i) => s + i.quantity, 0);

  const toggleCurrency = () => setCurrency((c) => (c === "USD" ? "SSP" : "USD"));

  return (
    <CartContext.Provider
      value={{
        items, area, exchangeRate, count, subtotalUSD, currency,
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
