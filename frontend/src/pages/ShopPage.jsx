import { useEffect, useMemo, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import ProductCard from "@/components/ProductCard";
import ContactSellerModal from "@/components/ContactSellerModal";
import ReportButton from "@/components/ReportButton";
import { MapPin, Clock, MessageCircle, Store, ShieldCheck, Banknote, ArrowLeft, AlertCircle, Star } from "lucide-react";

export default function ShopPage() {
  const { shop_id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [shop, setShop] = useState(null);
  const [products, setProducts] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [contactOpen, setContactOpen] = useState(false);
  const [search, setSearch] = useState("");
  // Iter 31 — active section tab (id) or "all"
  const [activeSectionId, setActiveSectionId] = useState("all");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      api.get(`/shops/${shop_id}`),
      api.get(`/products?shop_id=${shop_id}&limit=200`),
    ])
      .then(([s, p]) => {
        if (cancelled) return;
        setShop(s.data);
        setProducts(p.data || []);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err?.response?.status === 404) setError("Shop not found");
        else setError("Could not load this shop");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [shop_id]);

  const isOwner = !!(user && shop && user.id === shop.seller_id);
  const isHidden = shop && shop.is_public === false;

  const filteredProducts = useMemo(() => {
    const q = search.trim().toLowerCase();
    let list = products;
    // Section filter first
    if (activeSectionId && activeSectionId !== "all") {
      const sectionMeta = (shop?.product_sections || []).find((s) => s.id === activeSectionId);
      const isPromo = !!sectionMeta?.is_promo_section;
      const nowIso = new Date().toISOString();
      const promoLive = (m) => {
        const p = m?.promo || {};
        if (!p.active) return false;
        if (p.starts_at && nowIso < p.starts_at) return false;
        if (p.ends_at && nowIso > p.ends_at) return false;
        return true;
      };
      list = list.filter((p) =>
        isPromo ? promoLive(p) : p.product_section_id === activeSectionId
      );
    }
    if (!q) return list;
    return list.filter((p) =>
      (p.name || "").toLowerCase().includes(q) ||
      (p.category || "").toLowerCase().includes(q)
    );
  }, [search, products, activeSectionId, shop]);

  // Iter 31 — only surface sections that actually have products (or an
  // active promo, for promo sections). Prevents empty tabs.
  const visibleSections = useMemo(() => {
    if (!shop?.product_sections?.length) return [];
    const nowIso = new Date().toISOString();
    const promoLive = (m) => {
      const p = m?.promo || {};
      if (!p.active) return false;
      if (p.starts_at && nowIso < p.starts_at) return false;
      if (p.ends_at && nowIso > p.ends_at) return false;
      return true;
    };
    return (shop.product_sections || [])
      .slice()
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
      .filter((sec) => {
        if (sec.is_promo_section) return products.some(promoLive);
        return products.some((p) => p.product_section_id === sec.id);
      });
  }, [shop, products]);

  if (loading) {
    return (
      <PageWrapper>
        <div className="max-w-6xl mx-auto px-4 py-20 text-center">
          <p className="text-[var(--js-text-secondary)]">Loading shop…</p>
        </div>
      </PageWrapper>
    );
  }
  if (error || !shop) {
    return (
      <PageWrapper>
        <div className="max-w-2xl mx-auto px-4 py-20 text-center">
          <AlertCircle className="w-12 h-12 mx-auto text-[#D90429] mb-4" />
          <h1 className="font-display font-bold text-2xl text-[var(--js-text)]">{error || "Shop unavailable"}</h1>
          <p className="text-sm text-[var(--js-text-secondary)] mt-2">The shop you&apos;re looking for may have been removed or is not yet verified.</p>
          <Link to="/shops" className="mt-6 inline-flex items-center gap-2 text-sm font-bold text-[#C84B31] hover:underline">
            <ArrowLeft className="w-4 h-4" /> Back to all shops
          </Link>
        </div>
      </PageWrapper>
    );
  }

  if (isHidden && !isOwner && user?.role !== "admin") {
    return (
      <PageWrapper>
        <div className="max-w-2xl mx-auto px-4 py-20 text-center">
          <AlertCircle className="w-12 h-12 mx-auto text-[#D90429] mb-4" />
          <h1 className="font-display font-bold text-2xl text-[var(--js-text)]">Shop unavailable</h1>
          <p className="text-sm text-[var(--js-text-secondary)] mt-2">This shop is not currently public. Please check back later.</p>
          <Link to="/shops" className="mt-6 inline-flex items-center gap-2 text-sm font-bold text-[#C84B31] hover:underline">
            <ArrowLeft className="w-4 h-4" /> Back to all shops
          </Link>
        </div>
      </PageWrapper>
    );
  }

  const banner = shop.banner_url || shop.image_url || "";
  const logo = shop.logo_url || shop.image_url || "";
  const isOpen = shop.is_open !== false;

  return (
    <PageWrapper>
      {/* Owner-only: verification status banner */}
      {(isOwner || user?.role === "admin") && shop.verification !== "Verified" && (
        <VerificationBanner status={shop.verification || "Pending"} rejectionReason={shop.verification_note} />
      )}
      {/* Banner */}
      <div className="relative w-full" data-testid="shop-banner">
        <div className="h-44 sm:h-60 lg:h-72 w-full bg-[#1A1A1A] overflow-hidden relative">
          {banner ? (
            <img src={banner} alt={shop.name} className="w-full h-full object-cover opacity-90" />
          ) : (
            <div className="w-full h-full bg-gradient-to-br from-[#0E1A2B] to-[#C84B31]" />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/10 to-transparent" />
        </div>

        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 -mt-12 sm:-mt-16 relative z-10">
          <div className="flex flex-col sm:flex-row items-start sm:items-end gap-4">
            {/* Logo */}
            <div className="w-24 h-24 sm:w-32 sm:h-32 rounded-3xl bg-white border-4 border-white shadow-xl overflow-hidden flex-shrink-0" data-testid="shop-logo">
              {logo ? (
                <img src={logo} alt={shop.name} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full bg-gradient-to-br from-[#E9C46A] to-[#C84B31] flex items-center justify-center">
                  <Store className="w-10 h-10 text-white" />
                </div>
              )}
            </div>

            {/* Identity */}
            <div className="flex-1 min-w-0 sm:pb-2">
              <div className="bg-white rounded-2xl p-4 sm:p-5 shadow-sm border border-[var(--js-border)]">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h1 className="font-display font-bold text-xl sm:text-2xl text-[var(--js-text)]" data-testid="shop-name">{shop.name}</h1>
                      {shop.is_verified && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#2D6A4F]/10 text-[#2D6A4F]">
                          <ShieldCheck className="w-3 h-3" /> VERIFIED
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-[var(--js-text-secondary)] mt-1.5 flex-wrap">
                      {shop.area && <span className="inline-flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {shop.area}</span>}
                      {shop.opening_hours && <span className="inline-flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> {shop.opening_hours}</span>}
                      {shop.average_rating ? (
                        <span className="inline-flex items-center gap-1" data-testid="shop-rating">
                          <Star className="w-3.5 h-3.5 fill-[#E9C46A] text-[#E9C46A]" />
                          <span className="font-semibold text-[#1A1A1A]">{shop.average_rating}</span>
                          <span>({shop.review_count || 0} reviews)</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 italic" data-testid="shop-no-reviews">
                          <Star className="w-3.5 h-3.5" />
                          <span>No reviews yet</span>
                        </span>
                      )}
                    </div>
                    {shop.description && (
                      <p className="text-sm text-[var(--js-text-secondary)] mt-2 leading-relaxed" data-testid="shop-description">{shop.description}</p>
                    )}
                  </div>
                  <div className="flex flex-col gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        if (!user) {
                          navigate(`/login?next=/shop/${shop_id}`);
                          return;
                        }
                        setContactOpen(true);
                      }}
                      data-testid="contact-seller-btn"
                      className="inline-flex items-center justify-center gap-1.5 bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-bold px-4 py-2.5 rounded-full"
                    >
                      <MessageCircle className="w-4 h-4" /> Contact Seller
                    </button>
                    {isOwner && (
                      <Link
                        to={`/seller/shop/${shop_id}/edit`}
                        data-testid="edit-shop-link"
                        className="inline-flex items-center justify-center gap-1.5 bg-white border border-[var(--js-border)] hover:border-[#1A1A1A] text-[var(--js-text)] text-xs font-bold px-3 py-2 rounded-full"
                      >
                        Edit Shop Page
                      </Link>
                    )}
                    {!isOwner && (
                      <ReportButton targetType="shop" targetId={shop_id} label="Report shop" />
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
        {/* COD strip */}
        <div className="flex items-center gap-3 p-3 sm:p-4 bg-[#FFF7E0] border border-[#E9C46A]/40 rounded-2xl text-xs sm:text-sm text-[#7A5C12] mb-6" data-testid="shop-cod-banner">
          <Banknote className="w-5 h-5 flex-shrink-0" />
          <p><strong>Cash on Delivery only.</strong> Pay when you receive your order from {shop.name}.</p>
        </div>

        {!isOpen && (
          <div className="flex items-center gap-3 p-3 sm:p-4 bg-[#5C5C5C]/10 border border-[#5C5C5C]/30 rounded-2xl text-sm text-[#5C5C5C] mb-6" data-testid="shop-closed-notice">
            <Clock className="w-5 h-5" />
            <p><strong>This shop is currently closed.</strong> You can still browse but new orders may not be processed until it reopens.</p>
          </div>
        )}

        {isHidden && (
          <div className="flex items-center gap-3 p-3 sm:p-4 bg-[#1A1A1A]/5 border border-[#1A1A1A]/30 rounded-2xl text-sm text-[#1A1A1A] mb-6" data-testid="shop-hidden-notice">
            <AlertCircle className="w-5 h-5" />
            <p><strong>This shop is hidden from the marketplace.</strong> Only you (and admins) can see this preview. Toggle visibility from your dashboard to publish.</p>
          </div>
        )}

        {/* Products */}
        <div className="flex items-end justify-between gap-3 flex-wrap mb-4">
          <div>
            <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Storefront</p>
            <h2 className="font-display font-bold text-xl text-[var(--js-text)] mt-1">Products{products.length > 0 ? ` (${products.length})` : ""}</h2>
          </div>
          {products.length > 6 && (
            <div className="relative w-full sm:w-72">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search this shop's products…"
                data-testid="shop-product-search"
                className="w-full bg-white border border-[var(--js-border)] rounded-full pl-10 pr-4 py-2 text-sm focus:outline-none focus:border-[#C84B31] shadow-sm"
              />
              <svg className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--js-text-secondary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
            </div>
          )}
        </div>

        {/* Iter 31 — Product Section tabs (only shown when shop uses sections) */}
        {visibleSections.length > 0 && (
          <div className="mb-5" data-testid="shop-section-tabs">
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setActiveSectionId("all")}
                data-testid="shop-section-all"
                className={`px-4 py-2 rounded-full text-sm font-semibold transition ${
                  activeSectionId === "all"
                    ? "bg-[#1A1A1A] text-white"
                    : "bg-white border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#1A1A1A]"
                }`}
              >
                All
              </button>
              {visibleSections.map((sec) => (
                <button
                  key={sec.id}
                  onClick={() => setActiveSectionId(sec.id)}
                  data-testid={`shop-section-${sec.id}`}
                  className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-semibold transition ${
                    activeSectionId === sec.id
                      ? "bg-[#C84B31] text-white"
                      : "bg-white border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#C84B31]"
                  }`}
                >
                  {sec.is_promo_section && <span aria-hidden>🔥</span>}
                  {sec.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {filteredProducts.length === 0 ? (
          <div className="bg-white border border-[var(--js-border)] rounded-2xl p-8 text-center text-[var(--js-text-secondary)] text-sm" data-testid="shop-no-products">
            {products.length === 0
              ? "This shop has not added any products yet."
              : `No products match "${search}".`}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 lg:gap-5" data-testid="shop-products-grid">
            {filteredProducts.map((p) => <ProductCard key={p.id} product={p} shop={shop} />)}
          </div>
        )}
      </div>

      {contactOpen && (
        <ContactSellerModal
          shop={shop}
          onClose={() => setContactOpen(false)}
        />
      )}
    </PageWrapper>
  );
}

function PageWrapper({ children }) {
  return (
    <div className="min-h-screen flex flex-col bg-[var(--js-bg)]">
      <Header />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}

function VerificationBanner({ status, rejectionReason }) {
  const isRejected = status === "Rejected";
  const cfg = isRejected
    ? {
        wrap: "bg-[#D90429]/10 border-[#D90429]/40",
        icon: "text-[#D90429]",
        title: "Your shop was rejected",
        body: rejectionReason || "An admin reviewed your submission and could not approve it. Please update your documents and resubmit for review.",
        cta: { label: "Update KYC & resubmit", to: "/seller" },
        badge: "REJECTED",
      }
    : {
        wrap: "bg-[#E9C46A]/15 border-[#E9C46A]",
        icon: "text-[#8A6C00]",
        title: "Awaiting verification",
        body: "Your shop is only visible to you right now. Customers won't see it until an admin verifies your documents. This usually takes a business day.",
        cta: { label: "Complete KYC", to: "/seller" },
        badge: "PENDING",
      };
  return (
    <div className={`border-b ${cfg.wrap}`} data-testid="verification-banner">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <AlertCircle className={`w-5 h-5 flex-shrink-0 mt-0.5 ${cfg.icon}`} />
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="font-display font-bold text-sm text-[var(--js-text)]">{cfg.title}</p>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${isRejected ? "bg-[#D90429] text-white" : "bg-[#E9C46A] text-[#1A1A1A]"}`}>
                {cfg.badge}
              </span>
            </div>
            <p className="text-xs text-[var(--js-text-secondary)] mt-0.5 leading-relaxed">{cfg.body}</p>
          </div>
        </div>
        <Link
          to={cfg.cta.to}
          data-testid="verification-cta"
          className="inline-flex items-center justify-center gap-1.5 bg-[#1A1A1A] hover:bg-[#C84B31] text-white text-xs font-bold px-4 py-2 rounded-full flex-shrink-0"
        >
          {cfg.cta.label}
        </Link>
      </div>
    </div>
  );
}
