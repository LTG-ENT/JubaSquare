import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useCart } from "@/context/CartContext";
import { useSystem } from "@/context/SystemContext";
import {
  ShoppingCart, LogOut, Home as HomeIcon, LayoutGrid, Store, UtensilsCrossed,
  LayoutDashboard, Menu, X, User as UserIcon, Settings as SettingsIcon, Package,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Logo } from "@/components/Logo";
import NotificationBell from "@/components/NotificationBell";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import CategoriesNavMenu from "@/components/CategoriesNavMenu";
import SearchButton from "@/components/SearchButton";
import GlobalSearch from "@/components/GlobalSearch";

const Brand = ({ to = "/" }) => (
  <Link to={to} className="flex items-center gap-1.5 sm:gap-2 md:gap-3 shrink-0 min-w-0 max-w-full" data-testid="brand-logo">
    {/* Logo - Show on all screens but smaller on mobile */}
    <Logo size={48} className="w-8 h-8 sm:w-10 sm:h-10 md:w-12 md:h-12 lg:w-14 lg:h-14 xl:w-16 xl:h-16 shrink-0" />
    {/* Text - Hide on mobile, show from sm up */}
    <div className="hidden sm:flex flex-col leading-tight min-w-0 overflow-hidden">
      <span className="font-display font-bold text-base sm:text-lg md:text-xl lg:text-2xl text-white truncate">JubaSquare</span>
      <span className="hidden md:inline text-[9px] sm:text-[10px] uppercase tracking-[0.18em] text-white/60 -mt-0.5 truncate">by L.T.G Enterprise</span>
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

// Role-based quick menu opened from the Profile icon.
// Renders a small overlay panel anchored under the trigger button.
function ProfileQuickMenu({ user }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const navigate = useNavigate();
  const { t } = useTranslation();

  // Close on outside click + ESC.
  useEffect(() => {
    if (!open) return;
    const onDown = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Build options per role. Order matters.
  const role = user?.role;
  const items = [];
  if (role === "customer") {
    items.push({ key: "orders", label: t("orders"), to: "/orders", Icon: Package });
    items.push({ key: "settings", label: t("settings"), to: "/settings", Icon: SettingsIcon });
  } else if (role === "seller") {
    items.push({ key: "dashboard", label: t("dashboard"), to: "/seller", Icon: LayoutDashboard });
    items.push({ key: "settings", label: t("settings"), to: "/settings", Icon: SettingsIcon });
  } else if (role === "admin") {
    items.push({ key: "dashboard", label: t("dashboard"), to: "/admin", Icon: LayoutDashboard });
    items.push({ key: "settings", label: t("settings"), to: "/settings", Icon: SettingsIcon });
  } else if (role === "driver") {
    items.push({ key: "driver", label: t("driver"), to: "/driver", Icon: LayoutDashboard });
    items.push({ key: "settings", label: t("settings"), to: "/settings", Icon: SettingsIcon });
  }

  const go = (to) => {
    setOpen(false);
    navigate(to);
  };

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="true"
        aria-expanded={open}
        data-testid="nav-profile"
        className={`flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium transition-all ${
          open ? "bg-[#E9C46A] text-[#0E1A2B]" : "text-white/85 hover:bg-white/10 hover:text-white"
        }`}
      >
        <UserIcon className="w-4 h-4" />
        <span>{t("profile")}</span>
      </button>

      {open && (
        <div
          role="menu"
          data-testid="profile-quick-menu"
          className="absolute right-0 mt-2 w-56 bg-white border border-[#E2E2D9] rounded-2xl shadow-xl py-2 z-50 fade-up"
        >
          <div className="px-4 pt-1 pb-2 border-b border-[#E2E2D9] mb-1">
            <p className="text-[10px] uppercase tracking-[0.18em] text-[#5C5C5C] font-bold">{t("signedInAs")}</p>
            <p className="text-sm font-semibold text-[#1A1A1A] truncate">{user?.name || user?.email || "Guest"}</p>
            <p className="text-[11px] text-[#5C5C5C] capitalize">{role}</p>
          </div>
          {items.map(({ key, label, to, Icon }) => (
            <button
              key={key}
              onClick={() => go(to)}
              data-testid={`profile-quick-${key}`}
              role="menuitem"
              className="w-full flex items-center gap-3 px-4 py-2.5 text-sm font-medium text-[#1A1A1A] hover:bg-[#F2EBE5] transition text-left"
            >
              <Icon className="w-4 h-4 text-[#C84B31]" />
              <span>{label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Header() {
  const { user, logout } = useAuth();
  const { count } = useCart();
  const { settings } = useSystem();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navLink = (to, label, Icon) => {
    const active = location.pathname === to || (to.includes("?") && location.pathname + location.search === to);
    return (
      <Link
        to={to}
        onClick={() => setMobileOpen(false)}
        data-testid={`nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
        className={`flex items-center gap-1 px-2 lg:px-2.5 xl:px-3 py-2 rounded-full text-sm font-medium transition-all whitespace-nowrap ${
          active ? "bg-[#E9C46A] text-[#0E1A2B]" : "text-white/85 hover:bg-white/10 hover:text-white"
        }`}
      >
        <Icon className="w-4 h-4 shrink-0" />
        <span className="text-xs lg:text-sm">{label}</span>
      </Link>
    );
  };

  const dashboardPath = user?.role === "admin" ? "/admin" : user?.role === "seller" ? "/seller" : user?.role === "driver" ? "/driver" : null;

  // Drivers are restricted to their own dashboard — hide marketplace nav,
  // shopping cart, search, currency toggle. They keep notifications, profile, logout.
  const isDriver = user?.role === "driver";

  return (
    <header className="sticky top-0 z-50 bg-[#0E1A2B] border-b border-white/10 shadow-md">
      {settings.maintenance_mode && (
        <div className="bg-[#E9C46A] text-[#1A1A1A] text-center text-xs font-bold py-1.5" data-testid="maintenance-banner">
          ⚠ Maintenance mode is active — orders are paused.
        </div>
      )}
      <div className="max-w-7xl mx-auto px-3 sm:px-4 md:px-6 lg:px-8">
        <div className="h-16 sm:h-20 lg:h-24 flex items-center gap-2 sm:gap-4" dir="ltr">
          {/* Left cluster: mobile menu + language switcher */}
          <div className="flex items-center gap-1 shrink-0">
            {!isDriver && (
              <button
                onClick={() => setMobileOpen((v) => !v)}
                data-testid="mobile-menu-button"
                className="lg:hidden p-1.5 sm:p-2 rounded-full hover:bg-white/10 transition"
                aria-label="Menu"
              >
                {mobileOpen ? <X className="w-5 h-5 sm:w-6 sm:h-6 text-white" /> : <Menu className="w-5 h-5 sm:w-6 sm:h-6 text-white" />}
              </button>
            )}
            <LanguageSwitcher />
          </div>

          {/* Brand - Icon only on mobile, full branding on larger screens */}
          <div className="flex justify-start items-center min-w-0 sm:flex-1 sm:justify-center lg:justify-start lg:flex-none overflow-hidden">
            <Brand to={isDriver ? "/driver" : "/"} />
          </div>

          {/* Desktop Navigation - hidden on mobile + completely hidden for drivers */}
          {!isDriver && (
            <nav className="hidden lg:flex items-center gap-0.5 flex-1 lg:ml-4 xl:ml-6">
              {navLink("/", t("home"), HomeIcon)}
              {settings.module_marketplace && (
                <CategoriesNavMenu
                  active={location.pathname === "/marketplace"}
                  onNavigate={() => setMobileOpen(false)}
                  trigger={navLink("/marketplace", t("marketplace"), LayoutGrid)}
                />
              )}
              {navLink("/shops", t("shops"), Store)}
              {settings.module_restaurants && navLink("/restaurants", t("restaurants"), UtensilsCrossed)}
            </nav>
          )}

          {/* Right side actions */}
          <div className="flex items-center gap-1 shrink-0">
            {!isDriver && <SearchButton />}
            {!isDriver && <CurrencyToggle />}

            {user && <NotificationBell />}

            {!isDriver && (
              <Link to="/cart" data-testid="header-cart-button" className="relative p-2 rounded-full hover:bg-white/10 transition">
                <ShoppingCart className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                {count > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 bg-[#C84B31] text-white text-[10px] font-bold rounded-full w-4 h-4 sm:w-5 sm:h-5 flex items-center justify-center" data-testid="cart-count-badge">
                    {count}
                  </span>
                )}
              </Link>
            )}

            {user ? (
              <div className="flex items-center gap-0.5">
                <ProfileQuickMenu user={user} />
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
              <Link to="/login" data-testid="header-login-button" className="inline-flex items-center bg-[#C84B31] hover:bg-[#A83A23] text-white text-xs sm:text-sm font-semibold px-3 sm:px-4 py-1.5 sm:py-2 rounded-full transition whitespace-nowrap">
                {t("signIn")}
              </Link>
            )}
          </div>
        </div>

        {mobileOpen && !isDriver && (
          <div className="lg:hidden pb-4 flex flex-col gap-1 fade-up">
            <div className="md:hidden mb-2">
              <GlobalSearch />
            </div>
            {navLink("/", t("home"), HomeIcon)}
            {settings.module_marketplace && navLink("/marketplace", t("categories"), LayoutGrid)}
            {navLink("/shops", t("shops"), Store)}
            {settings.module_restaurants && navLink("/restaurants", t("restaurants"), UtensilsCrossed)}
            {user && (
              <div className="mt-1 pt-2 border-t border-white/10 flex flex-col gap-1" data-testid="mobile-profile-menu">
                <p className="text-[10px] uppercase tracking-[0.18em] text-white/50 font-bold px-3 pt-1">{t("profile")}</p>
                {user.role === "customer" && navLink("/orders", t("orders"), Package)}
                {(user.role === "seller" || user.role === "admin" || user.role === "driver") && dashboardPath && navLink(dashboardPath, t("dashboard"), LayoutDashboard)}
                {navLink("/settings", t("settings"), SettingsIcon)}
              </div>
            )}
            {!user && (
              <Link to="/login" onClick={() => setMobileOpen(false)} className="bg-[#C84B31] text-white text-sm font-semibold px-4 py-2.5 rounded-full text-center" data-testid="mobile-login-link">
                {t("signIn")}
              </Link>
            )}
            {user && (
              <button onClick={async () => { await logout(); setMobileOpen(false); navigate("/login"); }} className="bg-white/10 text-white text-sm font-semibold px-4 py-2.5 rounded-full" data-testid="mobile-logout-button">
                {t("logout")}
              </button>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
