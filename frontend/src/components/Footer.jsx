import { Link } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { Facebook, Instagram, Twitter, Mail, Phone } from "lucide-react";

export default function Footer() {
  return (
    <footer className="border-t border-[var(--js-border)] bg-[#0E1A2B] text-white mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid md:grid-cols-4 gap-10">
          {/* Brand */}
          <div className="md:col-span-1">
            <Link to="/" className="flex items-center gap-3">
              <Logo size={44} />
              <div className="leading-tight">
                <p className="font-display font-bold text-lg text-white">JubaSquare</p>
                <p className="text-[10px] uppercase tracking-[0.2em] text-white/60">by L.T.G Enterprise</p>
              </div>
            </Link>
            <p className="text-sm text-white/70 mt-4 leading-relaxed">
              Juba's marketplace for retail, wholesale and food delivery — built for South Sudan.
            </p>
            <div className="flex items-center gap-3 mt-5">
              <a href="https://facebook.com/" target="_blank" rel="noreferrer" aria-label="Facebook"
                 className="w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition">
                <Facebook className="w-4 h-4" />
              </a>
              <a href="https://instagram.com/" target="_blank" rel="noreferrer" aria-label="Instagram"
                 className="w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition">
                <Instagram className="w-4 h-4" />
              </a>
              <a href="https://twitter.com/" target="_blank" rel="noreferrer" aria-label="Twitter"
                 className="w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition">
                <Twitter className="w-4 h-4" />
              </a>
            </div>
          </div>

          {/* Shop */}
          <div>
            <p className="font-display font-bold text-sm uppercase tracking-wider mb-4">Shop</p>
            <ul className="space-y-2 text-sm text-white/70">
              <li><Link to="/marketplace" className="hover:text-[#E9C46A]">Marketplace</Link></li>
              <li><Link to="/shops" className="hover:text-[#E9C46A]">All Shops</Link></li>
              <li><Link to="/marketplace?view=wholesale" className="hover:text-[#E9C46A]">Wholesale</Link></li>
              <li><Link to="/restaurants" className="hover:text-[#E9C46A]">Food & Restaurants</Link></li>
            </ul>
          </div>

          {/* Company */}
          <div>
            <p className="font-display font-bold text-sm uppercase tracking-wider mb-4">Company</p>
            <ul className="space-y-2 text-sm text-white/70">
              <li><Link to="/about" className="hover:text-[#E9C46A]">About</Link></li>
              <li><Link to="/contact" className="hover:text-[#E9C46A]">Contact</Link></li>
              <li><Link to="/signup" className="hover:text-[#E9C46A]">Become a seller</Link></li>
            </ul>
            <p className="font-display font-bold text-sm uppercase tracking-wider mt-6 mb-4">Legal</p>
            <ul className="space-y-2 text-sm text-white/70">
              <li><Link to="/terms" className="hover:text-[#E9C46A]">Terms of Service</Link></li>
              <li><Link to="/privacy" className="hover:text-[#E9C46A]">Privacy Policy</Link></li>
              <li><Link to="/returns" className="hover:text-[#E9C46A]">Return Policy</Link></li>
            </ul>
          </div>

          {/* Contact */}
          <div>
            <p className="font-display font-bold text-sm uppercase tracking-wider mb-4">Get in touch</p>
            <ul className="space-y-3 text-sm text-white/70">
              <li className="flex items-start gap-2">
                <Mail className="w-4 h-4 text-[#E9C46A] shrink-0 mt-0.5" />
                <a href="mailto:ltg-general-trading@hotmail.com" className="hover:text-[#E9C46A] break-all">ltg-general-trading@hotmail.com</a>
              </li>
              <li className="flex items-start gap-2">
                <Phone className="w-4 h-4 text-[#E9C46A] shrink-0 mt-0.5" />
                <span>+211 9XX XXX XXX</span>
              </li>
              <li className="text-xs text-white/60 mt-1">Juba, South Sudan 🇸🇸</li>
            </ul>
          </div>
        </div>

        <div className="border-t border-white/10 mt-10 pt-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-white/50">© {new Date().getFullYear()} L.T.G General Trading. All rights reserved.</p>
          <p className="text-xs text-white/50">Built with ❤ for Juba — Cash on Delivery supported.</p>
        </div>
      </div>
    </footer>
  );
}
