import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import "@/App.css";

import { AuthProvider } from "@/context/AuthContext";
import { CartProvider } from "@/context/CartContext";
import { SystemProvider } from "@/context/SystemContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import ErrorBoundary from "@/components/ErrorBoundary";
import RouteLoader from "@/components/RouteLoader";
import DarkModeIconButton from "@/components/DarkModeIconButton";
import FloatingChat from "@/components/FloatingChat";

// ---------------------------------------------------------------------------
// Eagerly bundled (small + commonly first-paint on a cold visit)
// ---------------------------------------------------------------------------
import Home from "@/pages/Home";
import Login from "@/pages/Login";
import NotFound from "@/pages/NotFound";

// ---------------------------------------------------------------------------
// Lazy-loaded routes — each becomes a separate JS chunk fetched on demand.
// This drops the initial bundle by ~60-70%, which is the biggest single win
// on low-RAM hosts.
// ---------------------------------------------------------------------------
const Signup = lazy(() => import("@/pages/Signup"));
const VerifyEmail = lazy(() => import("@/pages/VerifyEmail"));
const ForgotPassword = lazy(() => import("@/pages/ForgotPassword"));
const ResetPassword = lazy(() => import("@/pages/ResetPassword"));
const Marketplace = lazy(() => import("@/pages/Marketplace"));
const Shops = lazy(() => import("@/pages/Shops"));
const ShopPage = lazy(() => import("@/pages/ShopPage"));
const ProductDetail = lazy(() => import("@/pages/ProductDetail"));
const Restaurants = lazy(() => import("@/pages/Restaurants"));
const RestaurantCheckout = lazy(() => import("@/pages/RestaurantCheckout"));
const KitchenDashboard = lazy(() => import("@/pages/KitchenDashboard"));
const Cart = lazy(() => import("@/pages/Cart"));
const Orders = lazy(() => import("@/pages/Orders"));
const Favorites = lazy(() => import("@/pages/Favorites"));
const Settings = lazy(() => import("@/pages/Settings"));
const SellerDashboard = lazy(() => import("@/pages/SellerDashboard"));
const SellerShopEdit = lazy(() => import("@/pages/SellerShopEdit"));
const AdminDashboard = lazy(() => import("@/pages/AdminDashboard"));
const About = lazy(() => import("@/pages/legal/About"));
const Contact = lazy(() => import("@/pages/legal/Contact"));
const Terms = lazy(() => import("@/pages/legal/Terms"));
const Privacy = lazy(() => import("@/pages/legal/Privacy"));
const Returns = lazy(() => import("@/pages/legal/Returns"));

// Honor user's saved dark-mode preference before first paint to avoid a flash.
if (typeof document !== "undefined") {
  try {
    const saved = localStorage.getItem("darkMode");
    const prefersDark =
      saved !== null
        ? saved === "true"
        : window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.setAttribute("data-theme", prefersDark ? "dark" : "light");
    if (prefersDark) document.documentElement.classList.add("dark");
  } catch {
    document.documentElement.setAttribute("data-theme", "light");
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <SystemProvider>
          <CartProvider>
            <BrowserRouter>
              <Suspense fallback={<RouteLoader />}>
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/signup" element={<Signup />} />
                  <Route path="/verify-email" element={<VerifyEmail />} />
                  <Route path="/forgot-password" element={<ForgotPassword />} />
                  <Route path="/reset-password" element={<ResetPassword />} />
                  <Route path="/marketplace" element={<Marketplace />} />
                  <Route path="/shops" element={<Shops />} />
                  <Route path="/shop/:shop_id" element={<ShopPage />} />
                  <Route path="/product/:id" element={<ProductDetail />} />
                  <Route path="/wholesale" element={<Navigate to="/marketplace?view=wholesale" replace />} />
                  <Route path="/restaurants" element={<Restaurants />} />
                  <Route path="/restaurant-checkout" element={<ProtectedRoute><RestaurantCheckout /></ProtectedRoute>} />
                  <Route path="/kitchen/:restaurantId" element={<ProtectedRoute><KitchenDashboard /></ProtectedRoute>} />
                  <Route path="/cart" element={<Cart />} />
                  <Route path="/orders" element={<ProtectedRoute><Orders /></ProtectedRoute>} />
                  <Route path="/favorites" element={<ProtectedRoute><Favorites /></ProtectedRoute>} />
                  <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
                  <Route path="/seller" element={<ProtectedRoute role="seller"><SellerDashboard /></ProtectedRoute>} />
                  <Route path="/seller/shop/:shop_id/edit" element={<ProtectedRoute role="seller"><SellerShopEdit /></ProtectedRoute>} />
                  <Route path="/admin" element={<ProtectedRoute role="admin"><AdminDashboard /></ProtectedRoute>} />
                  <Route path="/about" element={<About />} />
                  <Route path="/contact" element={<Contact />} />
                  <Route path="/terms" element={<Terms />} />
                  <Route path="/privacy" element={<Privacy />} />
                  <Route path="/returns" element={<Returns />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
              <FloatingChat />
            </BrowserRouter>
            <DarkModeIconButton />
            <Toaster
              position="top-right"
              toastOptions={{
                style: { background: "var(--js-paper)", border: "1px solid var(--js-border)", color: "var(--js-text)", fontFamily: "Manrope, sans-serif" },
              }}
            />
          </CartProvider>
        </SystemProvider>
      </AuthProvider>
    </ErrorBoundary>
  );
}
