import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { useEffect } from "react";
import "@/App.css";

import { AuthProvider, useAuth } from "@/context/AuthContext";
import { CartProvider } from "@/context/CartContext";
import { SystemProvider } from "@/context/SystemContext";
import ProtectedRoute from "@/components/ProtectedRoute";

import Home from "@/pages/Home";
import Login from "@/pages/Login";
import Marketplace from "@/pages/Marketplace";
import Shops from "@/pages/Shops";
import ProductDetail from "@/pages/ProductDetail";
import Restaurants from "@/pages/Restaurants";
import Cart from "@/pages/Cart";
import Orders from "@/pages/Orders";
import Favorites from "@/pages/Favorites";
import Settings from "@/pages/Settings";
import SellerDashboard from "@/pages/SellerDashboard";
import AdminDashboard from "@/pages/AdminDashboard";

function ThemeApplier() {
  const { user } = useAuth();
  useEffect(() => {
    const dark = !!user?.settings?.dark_mode;
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  }, [user]);
  return null;
}

export default function App() {
  return (
    <AuthProvider>
      <SystemProvider>
        <CartProvider>
          <ThemeApplier />
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/login" element={<Login />} />
              <Route path="/marketplace" element={<Marketplace />} />
              <Route path="/shops" element={<Shops />} />
              <Route path="/product/:id" element={<ProductDetail />} />
              <Route path="/wholesale" element={<Navigate to="/marketplace?view=wholesale" replace />} />
              <Route path="/restaurants" element={<Restaurants />} />
              <Route path="/cart" element={<Cart />} />
              <Route path="/orders" element={<ProtectedRoute><Orders /></ProtectedRoute>} />
              <Route path="/favorites" element={<ProtectedRoute><Favorites /></ProtectedRoute>} />
              <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
              <Route path="/seller" element={<ProtectedRoute role="seller"><SellerDashboard /></ProtectedRoute>} />
              <Route path="/admin" element={<ProtectedRoute role="admin"><AdminDashboard /></ProtectedRoute>} />
            </Routes>
          </BrowserRouter>
          <Toaster
            position="top-right"
            toastOptions={{
              style: { background: "var(--js-paper)", border: "1px solid var(--js-border)", color: "var(--js-text)", fontFamily: "Manrope, sans-serif" },
            }}
          />
        </CartProvider>
      </SystemProvider>
    </AuthProvider>
  );
}
