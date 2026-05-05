export default function Footer() {
  return (
    <footer className="border-t border-[#E2E2D9] bg-[#F2EBE5]/40 mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-[#C84B31] flex items-center justify-center text-white font-display font-bold rotate-3">
            J
          </div>
          <div className="leading-tight">
            <p className="font-display font-bold text-[#1A1A1A]">JubaSquare</p>
            <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C]">by L.T.G Enterprise</p>
          </div>
        </div>
        <p className="text-xs text-[#5C5C5C]">© {new Date().getFullYear()} JubaSquare — Demo Showcase. Built for Juba 🇸🇸</p>
      </div>
    </footer>
  );
}
