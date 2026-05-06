import { Link } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { Home as HomeIcon } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12 grain-bg text-center">
      <Link to="/"><Logo size={72} className="shadow-xl" /></Link>
      <p className="mt-6 text-[72px] sm:text-[96px] font-display font-bold text-[#C84B31] leading-none">404</p>
      <h1 className="font-display font-bold text-2xl text-[var(--js-text)] mt-2">Page not found</h1>
      <p className="text-sm text-[var(--js-text-secondary)] mt-3 max-w-sm">
        The page you're looking for doesn't exist or may have moved.
      </p>
      <Link
        to="/"
        className="mt-8 inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-6 py-3 rounded-xl text-sm"
        data-testid="not-found-home"
      >
        <HomeIcon className="w-4 h-4" /> Back to Home
      </Link>
    </div>
  );
}
