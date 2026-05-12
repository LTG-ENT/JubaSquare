import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { Facebook, Mail, Phone } from "lucide-react";
import api from "@/lib/api";

const DEFAULT_FOOTER = {
  tagline: "Juba's marketplace for retail, wholesale and food delivery — built for South Sudan.",
  social_facebook: "https://facebook.com/",
  social_instagram: "https://instagram.com/",
  social_twitter: "https://twitter.com/",
  shop_title: "Shop",
  shop_links: [
    { label: "Marketplace", url: "/marketplace" },
    { label: "All Shops", url: "/shops" },
    { label: "Wholesale", url: "/marketplace?view=wholesale" },
    { label: "Food & Restaurants", url: "/restaurants" },
  ],
  company_title: "Company",
  company_links: [
    { label: "About", url: "/about" },
    { label: "Contact", url: "/contact" },
    { label: "Become a seller", url: "/signup" },
  ],
  legal_title: "Legal",
  legal_links: [
    { label: "Terms of Service", url: "/terms" },
    { label: "Privacy Policy", url: "/privacy" },
    { label: "Return Policy", url: "/returns" },
  ],
  contact_title: "Get in touch",
  contact_email: "ltg-general-trading@hotmail.com",
  contact_phone: "+211 9XX XXX XXX",
  contact_location: "Juba, South Sudan 🇸🇸",
  copyright_text: "© {year} L.T.G General Trading. All rights reserved.",
  tagline_bottom: "Built with ❤ for Juba — Cash on Delivery supported.",
};

// Distinguish internal app routes from external URLs (mailto:, https://, etc.)
function FooterLink({ link, className }) {
  const url = link?.url || "#";
  const isInternal = url.startsWith("/") && !url.startsWith("//");
  if (isInternal) {
    return <Link to={url} className={className}>{link.label}</Link>;
  }
  return (
    <a href={url} target="_blank" rel="noreferrer" className={className}>{link.label}</a>
  );
}

export default function Footer() {
  const [cfg, setCfg] = useState(DEFAULT_FOOTER);

  useEffect(() => {
    let cancelled = false;
    api.get("/site-config/footer")
      .then((r) => { if (!cancelled && r.data) setCfg({ ...DEFAULT_FOOTER, ...r.data }); })
      .catch(() => { /* keep defaults */ });
    return () => { cancelled = true; };
  }, []);

  const year = new Date().getFullYear();
  const copyright = (cfg.copyright_text || DEFAULT_FOOTER.copyright_text).replace("{year}", String(year));
  const linkClass = "hover:text-[#E9C46A]";

  return (
    <footer className="border-t border-[var(--js-border)] bg-[#0E1A2B] text-white mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid md:grid-cols-4 gap-10">
          {/* Brand */}
          <div className="md:col-span-1">
            <Link to="/" className="flex items-center gap-3">
              <Logo size={56} className="sm:w-16 sm:h-16 md:w-20 md:h-20 lg:w-[72px] lg:h-[72px]" />
              <div className="leading-tight">
                <p className="font-display font-bold text-lg text-white">JubaSquare</p>
                <p className="text-[10px] uppercase tracking-[0.2em] text-white/60">by L.T.G Enterprise</p>
              </div>
            </Link>
            <p className="text-sm text-white/70 mt-4 leading-relaxed" data-testid="footer-tagline">
              {cfg.tagline}
            </p>
            <div className="flex items-center gap-3 mt-5">
              {cfg.social_facebook && (
                <a href={cfg.social_facebook} target="_blank" rel="noreferrer" aria-label="Facebook"
                   className="w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition">
                  <Facebook className="w-4 h-4" />
                </a>
              )}
            </div>
          </div>

          {/* Shop column */}
          <div>
            <p className="font-display font-bold text-sm uppercase tracking-wider mb-4">{cfg.shop_title}</p>
            <ul className="space-y-2 text-sm text-white/70" data-testid="footer-shop-links">
              {(cfg.shop_links || []).map((l, i) => (
                <li key={`shop-${i}`}><FooterLink link={l} className={linkClass} /></li>
              ))}
            </ul>
          </div>

          {/* Company + Legal column */}
          <div>
            <p className="font-display font-bold text-sm uppercase tracking-wider mb-4">{cfg.company_title}</p>
            <ul className="space-y-2 text-sm text-white/70" data-testid="footer-company-links">
              {(cfg.company_links || []).map((l, i) => (
                <li key={`company-${i}`}><FooterLink link={l} className={linkClass} /></li>
              ))}
            </ul>
            <p className="font-display font-bold text-sm uppercase tracking-wider mt-6 mb-4">{cfg.legal_title}</p>
            <ul className="space-y-2 text-sm text-white/70" data-testid="footer-legal-links">
              {(cfg.legal_links || []).map((l, i) => (
                <li key={`legal-${i}`}><FooterLink link={l} className={linkClass} /></li>
              ))}
            </ul>
          </div>

          {/* Contact column */}
          <div>
            <p className="font-display font-bold text-sm uppercase tracking-wider mb-4">{cfg.contact_title}</p>
            <ul className="space-y-3 text-sm text-white/70">
              {cfg.contact_email && (
                <li className="flex items-start gap-2">
                  <Mail className="w-4 h-4 text-[#E9C46A] shrink-0 mt-0.5" />
                  <a href={`mailto:${cfg.contact_email}`} className="hover:text-[#E9C46A] break-all">{cfg.contact_email}</a>
                </li>
              )}
              {cfg.contact_phone && (
                <li className="flex items-start gap-2">
                  <Phone className="w-4 h-4 text-[#E9C46A] shrink-0 mt-0.5" />
                  <span>{cfg.contact_phone}</span>
                </li>
              )}
              {cfg.contact_location && (
                <li className="text-xs text-white/60 mt-1">{cfg.contact_location}</li>
              )}
            </ul>
          </div>
        </div>

        <div className="border-t border-white/10 mt-10 pt-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-white/50" data-testid="footer-copyright">{copyright}</p>
          <p className="text-xs text-white/50" data-testid="footer-tagline-bottom">{cfg.tagline_bottom}</p>
        </div>
      </div>
    </footer>
  );
}
