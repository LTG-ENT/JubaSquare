import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useCart } from "@/context/CartContext";
import { useSystem } from "@/context/SystemContext";
import { ShoppingCart, LogOut, Store, UtensilsCrossed, LayoutDashboard, Menu, X, Package, Settings as SettingsIcon, Heart } from "lucide-react";
import { useState } from "react";
import { Logo } from "@/components/Logo";

const Brand = () => (
  <Link to="/" className="flex items-center gap-2.5" data-testid="brand-logo">
    <Logo size={40} />
    <div className="flex flex-col leading-tight">
      <span className="font-display font-bold text-[17px] text-[var(--js-text)]">JubaSquare</span>
      <span className="text-[10px] uppercase tracking-[0.18em] text-[var(--js-text-secondary)] -mt-0.5">by L.T.G Enterprise</span>
    </div>
  </Link>
);

export default function Header() {
  const { user, logout } = useAuth();
  const { count } = useCart();
  const { settings } = useSystem();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navLink = (to, label, Icon) => {
    const active = location.pathname === to;
    return (
      <Link
        to={to}
        onClick={() => setMobileOpen(false)}
        data-testid={`nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
        className={`flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium transition-all ${
          active ? "bg-[#1A1A1A] text-white" : "text-[var(--js-text)] hover:bg-[var(--js-subtle)]"
        }`}
      >
        <Icon className="w-4 h-4" />
        <span>{label}</span>
      </Link>
    );
  };

  const dashboardPath = user?.role === "admin" ? "/admin" : user?.role === "seller" ? "/seller" : null;

  return (
    <header className="sticky top-0 z-50 bg-[var(--js-bg)]/80 backdrop-blur-xl border-b border-[var(--js-border)]">
      {settings.maintenance_mode && (
        <div className="bg-[#E9C46A] text-[#1A1A1A] text-center text-xs font-bold py-1.5" data-testid="maintenance-banner">
          ⚠ Maintenance mode is active — orders are paused.
        </div>
      )}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="h-16 flex items-center justify-between gap-4">
          <Brand />

          <nav className="hidden lg:flex items-center gap-1">
            {settings.module_marketplace && navLink("/marketplace", "Marketplace", Store)}
            {settings.module_wholesale && navLink("/wholesale", "Wholesale", Package)}
            {settings.module_restaurants && navLink("/restaurants", "Restaurants", UtensilsCrossed)}
            {user?.role === "customer" && navLink("/favorites", "Favorites", Heart)}
            {dashboardPath && navLink(dashboardPath, "Dashboard", LayoutDashboard)}
            {user && navLink("/settings", "Settings", SettingsIcon)}
          </nav>

          <div className="flex items-center gap-2">
            <Link to="/cart" data-testid="header-cart-button" className="relative p-2.5 rounded-full hover:bg-[var(--js-subtle)] transition">
              <ShoppingCart className="w-5 h-5 text-[var(--js-text)]" />
              {count > 0 && (
                <span className="absolute -top-0.5 -right-0.5 bg-[#C84B31] text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center" data-testid="cart-count-badge">
                  {count}
                </span>
              )}
            </Link>

            {user ? (
              <div className="hidden sm:flex items-center gap-2">
                <span className="text-sm font-medium text-[var(--js-text)] hidden md:inline" data-testid="user-name">{user.name}</span>
                <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[var(--js-subtle)] text-[var(--js-text-secondary)] font-bold">{user.role}</span>
                <button onClick={async () => { await logout(); navigate("/login"); }} data-testid="logout-button" className="p-2 rounded-full hover:bg-[var(--js-subtle)] transition" title="Logout">
                  <LogOut className="w-4 h-4 text-[var(--js-text)]" />
                </button>
              </div>
            ) : (
              <Link to="/login" data-testid="header-login-button" className="hidden sm:inline-flex items-center bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-semibold px-5 py-2 rounded-full transition">
                Sign In
              </Link>
            )}

            <button onClick={() => setMobileOpen(!mobileOpen)} className="lg:hidden p-2 rounded-full hover:bg-[var(--js-subtle)]" data-testid="mobile-menu-toggle">
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {mobileOpen && (
          <div className="lg:hidden pb-4 flex flex-col gap-1 fade-up">
            {settings.module_marketplace && navLink("/marketplace", "Marketplace", Store)}
            {settings.module_wholesale && navLink("/wholesale", "Wholesale", Package)}
            {settings.module_restaurants && navLink("/restaurants", "Restaurants", UtensilsCrossed)}
            {user?.role === "customer" && navLink("/favorites", "Favorites", Heart)}
            {dashboardPath && navLink(dashboardPath, "Dashboard", LayoutDashboard)}
            {user && navLink("/settings", "Settings", SettingsIcon)}
            {!user && (
              <Link to="/login" onClick={() => setMobileOpen(false)} className="bg-[#C84B31] text-white text-sm font-semibold px-4 py-2.5 rounded-full text-center" data-testid="mobile-login-link">
                Sign In
              </Link>
            )}
            {user && (
              <button onClick={async () => { await logout(); setMobileOpen(false); navigate("/login"); }} className="bg-[var(--js-subtle)] text-[var(--js-text)] text-sm font-semibold px-4 py-2.5 rounded-full" data-testid="mobile-logout-button">
                Logout
              </button>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
