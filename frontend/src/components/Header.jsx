import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useCart } from "@/context/CartContext";
import { ShoppingCart, LogOut, Store, UtensilsCrossed, LayoutDashboard, Menu, X } from "lucide-react";
import { useState } from "react";

const Logo = () => (
  <Link to="/" className="flex items-center gap-2.5" data-testid="brand-logo">
    <div className="relative">
      <div className="w-9 h-9 rounded-xl bg-[#C84B31] flex items-center justify-center text-white font-display font-bold text-lg rotate-3">
        J
      </div>
      <div className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full bg-[#E9C46A]" />
    </div>
    <div className="flex flex-col leading-tight">
      <span className="font-display font-bold text-[17px] text-[#1A1A1A]">JubaSquare</span>
      <span className="text-[10px] uppercase tracking-[0.18em] text-[#5C5C5C] -mt-0.5">by L.T.G Enterprise</span>
    </div>
  </Link>
);

export default function Header() {
  const { user, logout } = useAuth();
  const { count } = useCart();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navLink = (to, label, Icon) => {
    const active = location.pathname === to;
    return (
      <Link
        to={to}
        onClick={() => setMobileOpen(false)}
        data-testid={`nav-${label.toLowerCase()}`}
        className={`flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium transition-all ${
          active
            ? "bg-[#1A1A1A] text-white"
            : "text-[#1A1A1A] hover:bg-[#F2EBE5]"
        }`}
      >
        <Icon className="w-4 h-4" />
        <span>{label}</span>
      </Link>
    );
  };

  const dashboardPath = user?.role === "admin" ? "/admin" : user?.role === "seller" ? "/seller" : null;

  return (
    <header className="sticky top-0 z-50 bg-[#F9F9F6]/80 backdrop-blur-xl border-b border-[#E2E2D9]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="h-16 flex items-center justify-between gap-4">
          <Logo />

          <nav className="hidden lg:flex items-center gap-1">
            {navLink("/marketplace", "Marketplace", Store)}
            {navLink("/restaurants", "Restaurants", UtensilsCrossed)}
            {dashboardPath && navLink(dashboardPath, "Dashboard", LayoutDashboard)}
          </nav>

          <div className="flex items-center gap-2">
            <Link
              to="/cart"
              data-testid="header-cart-button"
              className="relative p-2.5 rounded-full hover:bg-[#F2EBE5] transition"
            >
              <ShoppingCart className="w-5 h-5 text-[#1A1A1A]" />
              {count > 0 && (
                <span className="absolute -top-0.5 -right-0.5 bg-[#C84B31] text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center" data-testid="cart-count-badge">
                  {count}
                </span>
              )}
            </Link>

            {user ? (
              <div className="hidden sm:flex items-center gap-2">
                <span className="text-sm font-medium text-[#1A1A1A] hidden md:inline" data-testid="user-name">
                  {user.name}
                </span>
                <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#F2EBE5] text-[#5C5C5C] font-bold">
                  {user.role}
                </span>
                <button
                  onClick={async () => { await logout(); navigate("/login"); }}
                  data-testid="logout-button"
                  className="p-2 rounded-full hover:bg-[#F2EBE5] transition"
                  title="Logout"
                >
                  <LogOut className="w-4 h-4 text-[#1A1A1A]" />
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                data-testid="header-login-button"
                className="hidden sm:inline-flex items-center bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-semibold px-5 py-2 rounded-full transition"
              >
                Sign In
              </Link>
            )}

            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="lg:hidden p-2 rounded-full hover:bg-[#F2EBE5]"
              data-testid="mobile-menu-toggle"
            >
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {mobileOpen && (
          <div className="lg:hidden pb-4 flex flex-col gap-1 fade-up">
            {navLink("/marketplace", "Marketplace", Store)}
            {navLink("/restaurants", "Restaurants", UtensilsCrossed)}
            {dashboardPath && navLink(dashboardPath, "Dashboard", LayoutDashboard)}
            {!user && (
              <Link
                to="/login"
                onClick={() => setMobileOpen(false)}
                className="bg-[#C84B31] text-white text-sm font-semibold px-4 py-2.5 rounded-full text-center"
                data-testid="mobile-login-link"
              >
                Sign In
              </Link>
            )}
            {user && (
              <button
                onClick={async () => { await logout(); setMobileOpen(false); navigate("/login"); }}
                className="bg-[#F2EBE5] text-[#1A1A1A] text-sm font-semibold px-4 py-2.5 rounded-full"
                data-testid="mobile-logout-button"
              >
                Logout
              </button>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
