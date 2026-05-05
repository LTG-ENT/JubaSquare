import { Logo } from "@/components/Logo";

export default function Footer() {
  return (
    <footer className="border-t border-[var(--js-border)] bg-[var(--js-subtle)]/40 mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <Logo size={36} />
          <div className="leading-tight">
            <p className="font-display font-bold text-[var(--js-text)]">JubaSquare</p>
            <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--js-text-secondary)]">by L.T.G Enterprise</p>
          </div>
        </div>
        <p className="text-xs text-[var(--js-text-secondary)]">© {new Date().getFullYear()} JubaSquare — Demo Showcase. Built for Juba 🇸🇸</p>
      </div>
    </footer>
  );
}
