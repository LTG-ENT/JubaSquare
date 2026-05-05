import { createContext, useContext, useEffect, useState } from "react";

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

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify({ items, area, exchangeRate }));
  }, [items, area, exchangeRate]);

  const addItem = (item) => {
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
  };

  const removeItem = (item_id) =>
    setItems((prev) => prev.filter((i) => i.item_id !== item_id));

  const setQuantity = (item_id, qty) =>
    setItems((prev) =>
      prev.map((i) => (i.item_id === item_id ? { ...i, quantity: Math.max(1, qty) } : i)),
    );

  const clear = () => setItems([]);

  const subtotalUSD = items.reduce((s, i) => s + i.price_usd * i.quantity, 0);
  const count = items.reduce((s, i) => s + i.quantity, 0);

  return (
    <CartContext.Provider
      value={{
        items, area, exchangeRate, count, subtotalUSD,
        addItem, removeItem, setQuantity, clear, setArea, setExchangeRate,
      }}
    >
      {children}
    </CartContext.Provider>
  );
};

export const useCart = () => useContext(CartContext);
