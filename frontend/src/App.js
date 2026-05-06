import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import "@/App.css";

import { AuthProvider } from "@/context/AuthContext";
import { CartProvider } from "@/context/CartContext";
import { SystemProvider } from "@/context/SystemContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import ErrorBoundary from "@/components/ErrorBoundary";

import Home from "@/pages/Home";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import VerifyEmail from "@/pages/VerifyEmail";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
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
import NotFound from "@/pages/NotFound";
import About from "@/pages/legal/About";
import Contact from "@/pages/legal/Contact";
import Terms from "@/pages/legal/Terms";
import Privacy from "@/pages/legal/Privacy";
import Returns from "@/pages/legal/Returns";

// Dark mode removed — light theme is enforced.
if (typeof document !== "undefined") {
  document.documentElement.setAttribute("data-theme", "light");
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <SystemProvider>
          <CartProvider>
            <BrowserRouter>
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/login" element={<Login />} />
                <Route path="/signup" element={<Signup />} />
                <Route path="/verify-email" element={<VerifyEmail />} />
                <Route path="/forgot-password" element={<ForgotPassword />} />
                <Route path="/reset-password" element={<ResetPassword />} />
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
                <Route path="/about" element={<About />} />
                <Route path="/contact" element={<Contact />} />
                <Route path="/terms" element={<Terms />} />
                <Route path="/privacy" element={<Privacy />} />
                <Route path="/returns" element={<Returns />} />
                <Route path="*" element={<NotFound />} />
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
    </ErrorBoundary>
  );
}
