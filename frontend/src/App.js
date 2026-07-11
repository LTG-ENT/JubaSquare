import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { HelmetProvider } from "react-helmet-async";
import "@/App.css";

import { AuthProvider, useAuth } from "@/context/AuthContext";
import { CartProvider } from "@/context/CartContext";
import { SystemProvider, useSystem } from "@/context/SystemContext";
import { SeoProvider } from "@/context/SeoContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import ErrorBoundary from "@/components/ErrorBoundary";
import RouteLoader from "@/components/RouteLoader";
import DarkModeIconButton from "@/components/DarkModeIconButton";
import FloatingChat from "@/components/FloatingChat";
import InstallAppBanner from "@/components/InstallAppBanner";
import MaintenancePage from "@/pages/MaintenancePage";
import { useLocation, Navigate as RRNavigate } from "react-router-dom";

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
const SellerRestaurantEdit = lazy(() => import("@/pages/SellerRestaurantEdit"));
const SellerGuide = lazy(() => import("@/pages/SellerGuide"));
const SellerLowStockReport = lazy(() => import("@/pages/SellerLowStockReport"));
const AdminDashboard = lazy(() => import("@/pages/AdminDashboard"));
const DriverDashboard = lazy(() => import("@/pages/DriverDashboard"));
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

// Drivers are locked to their dashboard — any other route redirects them to /driver.
const DRIVER_ALLOWED_PATHS = new Set(["/driver", "/login", "/logout", "/settings", "/verify-email"]);
function DriverGate({ children }) {
  const { user } = useAuth();
  const location = useLocation();
  if (user?.role === "driver" && !DRIVER_ALLOWED_PATHS.has(location.pathname)) {
    return <RRNavigate to="/driver" replace />;
  }
  return children;
}

/**
 * MaintenanceGate — when the existing platform setting `maintenance_mode` is ON,
 * we render the branded MaintenancePage to normal visitors. Admins and a small
 * allowlist of paths (login/signup/admin) keep working so an admin can flip the
 * switch back off. This uses the SAME settings.maintenance_mode from
 * Admin → Platform Settings — no new toggle, no new setting.
 */
const MAINTENANCE_ALLOWED_PATHS = [
  "/login",
  "/signup",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/admin",              // AdminDashboard root
];
function MaintenanceGate({ children }) {
  const { settings } = useSystem();
  const { user } = useAuth();
  const location = useLocation();

  const isMaintenance = !!settings?.maintenance_mode;
  if (!isMaintenance) return children;

  // Admins bypass the maintenance page entirely so they can turn it off.
  if (user?.role === "admin") return children;

  // Allow the auth flows and admin routes so admins can log in.
  const path = location.pathname || "/";
  const isAllowed = MAINTENANCE_ALLOWED_PATHS.some((p) => path === p || path.startsWith(p + "/"));
  if (isAllowed) return children;

  return <MaintenancePage />;
}


export default function App() {
  return (
    <HelmetProvider>
    <ErrorBoundary>
      <AuthProvider>
        <SystemProvider>
          <SeoProvider>
          <CartProvider>
            <BrowserRouter>
              <Suspense fallback={<RouteLoader />}>
                <DriverGate>
                <MaintenanceGate>
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
                  <Route path="/seller/guide" element={<ProtectedRoute role="seller"><SellerGuide /></ProtectedRoute>} />
                  <Route path="/seller/low-stock" element={<ProtectedRoute role="seller"><SellerLowStockReport /></ProtectedRoute>} />
                  <Route path="/seller/shop/:shop_id/edit" element={<ProtectedRoute role="seller"><SellerShopEdit /></ProtectedRoute>} />
                  <Route path="/seller/restaurant/:restaurant_id/edit" element={<ProtectedRoute role="seller"><SellerRestaurantEdit /></ProtectedRoute>} />
                  <Route path="/admin" element={<ProtectedRoute role="admin"><AdminDashboard /></ProtectedRoute>} />
                  <Route path="/driver" element={<ProtectedRoute role="driver"><DriverDashboard /></ProtectedRoute>} />
                  <Route path="/about" element={<About />} />
                  <Route path="/contact" element={<Contact />} />
                  <Route path="/terms" element={<Terms />} />
                  <Route path="/privacy" element={<Privacy />} />
                  <Route path="/returns" element={<Returns />} />
                  <Route path="*" element={<NotFound />} />
                  </Routes>
                </MaintenanceGate>
                </DriverGate>
              </Suspense>
              <FloatingChat />
              <InstallAppBanner />
            </BrowserRouter>
            <DarkModeIconButton />
            <Toaster
              position="top-right"
              toastOptions={{
                style: { background: "var(--js-paper)", border: "1px solid var(--js-border)", color: "var(--js-text)", fontFamily: "Manrope, sans-serif" },
              }}
            />
          </CartProvider>
          </SeoProvider>
        </SystemProvider>
      </AuthProvider>
    </ErrorBoundary>
    </HelmetProvider>
  );
}
