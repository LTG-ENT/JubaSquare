import Header from "@/components/Header";
import Footer from "@/components/Footer";

export default function LegalLayout({ title, subtitle, lastUpdated, children }) {
  return (
    <div className="min-h-screen flex flex-col bg-[var(--js-bg)]">
      <Header />
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 w-full flex-1">
        <p className="text-[10px] uppercase tracking-[0.25em] text-[var(--js-text-secondary)] font-bold">{subtitle || "JubaSquare"}</p>
        <h1 className="font-display font-bold text-3xl sm:text-4xl text-[var(--js-text)] mt-2 mb-2">{title}</h1>
        <p className="text-xs text-[var(--js-text-secondary)] mb-10" data-testid="legal-last-updated">
          Last updated: {lastUpdated || "July 2025"}
        </p>
        <div className="prose prose-sm sm:prose-base max-w-none bg-white border border-[var(--js-border)] rounded-3xl p-6 sm:p-10 space-y-4 text-[var(--js-text)]" style={{ lineHeight: 1.75 }}>
          {children}
        </div>
      </div>
      <Footer />
    </div>
  );
}
