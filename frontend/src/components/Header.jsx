import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useCart } from "@/context/CartContext";
import { useSystem } from "@/context/SystemContext";
import {
  ShoppingCart, LogOut, Home as HomeIcon, LayoutGrid, Store, UtensilsCrossed,
  LayoutDashboard, Menu, X, User as UserIcon, ClipboardList,
} from "lucide-react";
import { useState } from "react";
import { Logo } from "@/components/Logo";
import NotificationBell from "@/components/NotificationBell";
import CategoriesNavMenu from "@/components/CategoriesNavMenu";

const Brand = () => (
  <Link to="/" className="flex items-center gap-2.5" data-testid="brand-logo">
    <Logo size={40} />
    <div className="flex flex-col leading-tight">
      <span className="font-display font-bold text-[17px] text-white">JubaSquare</span>
      <span className="text-[10px] uppercase tracking-[0.18em] text-white/60 -mt-0.5">by L.T.G Enterprise</span>
    </div>
  </Link>
);

function CurrencyToggle() {
  const { currency, toggleCurrency } = useCart();
  return (
    <button
      onClick={toggleCurrency}
      data-testid="currency-toggle"
      title={`Switch to ${currency === "SSP" ? "USD" : "SSP"}`}
      className="hidden sm:inline-flex items-center gap-1 bg-white/10 hover:bg-white/20 border border-white/20 rounded-full px-1 py-1 text-xs font-bold text-white transition"
    >
      <span
        className={`px-2.5 py-1 rounded-full transition ${
          currency === "SSP" ? "bg-[#E9C46A] text-[#1A1A1A]" : "text-white/70"
        }`}
        data-testid="currency-ssp"
      >SSP</span>
      <span
        className={`px-2.5 py-1 rounded-full transition ${
          currency === "USD" ? "bg-[#E9C46A] text-[#1A1A1A]" : "text-white/70"
        }`}
        data-testid="currency-usd"
      >USD</span>
    </button>
  );
}

export default function Header() {
  const { user, logout } = useAuth();
  const { count } = useCart();
  const { settings } = useSystem();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navLink = (to, label, Icon) => {
    const active = location.pathname === to || (to.includes("?") && location.pathname + location.search === to);
    return (
      <Link
        to={to}
        onClick={() => setMobileOpen(false)}
        data-testid={`nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
        className={`flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium transition-all ${
          active ? "bg-[#E9C46A] text-[#0E1A2B]" : "text-white/85 hover:bg-white/10 hover:text-white"
        }`}
      >
        <Icon className="w-4 h-4" />
        <span>{label}</span>
      </Link>
    );
  };

  const dashboardPath = user?.role === "admin" ? "/admin" : user?.role === "seller" ? "/seller" : null;
  const profilePath = user ? "/settings" : "/login";

  return (
    <header className="sticky top-0 z-50 bg-[#0E1A2B] border-b border-white/10 shadow-md">
      {settings.maintenance_mode && (
        <div className="bg-[#E9C46A] text-[#1A1A1A] text-center text-xs font-bold py-1.5" data-testid="maintenance-banner">
          ⚠ Maintenance mode is active — orders are paused.
        </div>
      )}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="h-16 flex items-center justify-between gap-4">
          <Brand />

          <nav className="hidden lg:flex items-center gap-1">
            {navLink("/", "Home", HomeIcon)}
            {settings.module_marketplace && (
              <CategoriesNavMenu
                active={location.pathname === "/marketplace"}
                onNavigate={() => setMobileOpen(false)}
              />
            )}
            {navLink("/shops", "Shops", Store)}
            {settings.module_restaurants && navLink("/restaurants", "Restaurants", UtensilsCrossed)}
            {user?.role === "customer" && navLink("/orders", "Orders", ClipboardList)}
            {dashboardPath && navLink(dashboardPath, "Dashboard", LayoutDashboard)}
          </nav>

          <div className="flex items-center gap-2">
            <CurrencyToggle />

            {user && <NotificationBell />}

            <Link to="/cart" data-testid="header-cart-button" className="relative p-2.5 rounded-full hover:bg-white/10 transition">
              <ShoppingCart className="w-5 h-5 text-white" />
              {count > 0 && (
                <span className="absolute -top-0.5 -right-0.5 bg-[#C84B31] text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center" data-testid="cart-count-badge">
                  {count}
                </span>
              )}
            </Link>

            {user ? (
              <div className="hidden sm:flex items-center gap-1">
                <Link
                  to={profilePath}
                  data-testid="nav-profile"
                  className={`flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium transition-all ${
                    location.pathname === profilePath ? "bg-[#E9C46A] text-[#0E1A2B]" : "text-white/85 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  <UserIcon className="w-4 h-4" />
                  <span>Profile</span>
                </Link>
                <button
                  onClick={async () => { await logout(); navigate("/login"); }}
                  data-testid="logout-button"
                  className="p-2 rounded-full hover:bg-white/10 transition"
                  title="Logout"
                >
                  <LogOut className="w-4 h-4 text-white" />
                </button>
              </div>
            ) : (
              <Link to="/login" data-testid="header-login-button" className="hidden sm:inline-flex items-center bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-semibold px-5 py-2 rounded-full transition">
                Sign In
              </Link>
            )}

            <button onClick={() => setMobileOpen(!mobileOpen)} className="lg:hidden p-2 rounded-full hover:bg-white/10 text-white" data-testid="mobile-menu-toggle">
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {mobileOpen && (
          <div className="lg:hidden pb-4 flex flex-col gap-1 fade-up">
            {navLink("/", "Home", HomeIcon)}
            {settings.module_marketplace && navLink("/marketplace", "Categories", LayoutGrid)}
            {navLink("/shops", "Shops", Store)}
            {settings.module_restaurants && navLink("/restaurants", "Restaurants", UtensilsCrossed)}
            {user?.role === "customer" && navLink("/orders", "Orders", ClipboardList)}
            {dashboardPath && navLink(dashboardPath, "Dashboard", LayoutDashboard)}
            {user && navLink(profilePath, "Profile", UserIcon)}
            {!user && (
              <Link to="/login" onClick={() => setMobileOpen(false)} className="bg-[#C84B31] text-white text-sm font-semibold px-4 py-2.5 rounded-full text-center" data-testid="mobile-login-link">
                Sign In
              </Link>
            )}
            {user && (
              <button onClick={async () => { await logout(); setMobileOpen(false); navigate("/login"); }} className="bg-white/10 text-white text-sm font-semibold px-4 py-2.5 rounded-full" data-testid="mobile-logout-button">
                Logout
              </button>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
