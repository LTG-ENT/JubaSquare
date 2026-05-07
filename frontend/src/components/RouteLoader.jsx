import { Logo } from "@/components/Logo";

/**
 * Lightweight Suspense fallback shown while a lazy-loaded route chunk is
 * downloading. Kept tiny on purpose — no API calls, no heavy libraries — so
 * it appears instantly even on slow connections.
 */
export default function RouteLoader() {
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center gap-4 bg-[var(--js-bg)]"
      data-testid="route-loader"
      role="status"
      aria-label="Loading page"
    >
      <Logo size={64} className="animate-pulse" />
      <div className="flex items-center gap-2 text-sm text-[var(--js-text-secondary)]">
        <span className="w-2 h-2 rounded-full bg-[#C84B31] animate-bounce" style={{ animationDelay: "0ms" }} />
        <span className="w-2 h-2 rounded-full bg-[#C84B31] animate-bounce" style={{ animationDelay: "150ms" }} />
        <span className="w-2 h-2 rounded-full bg-[#C84B31] animate-bounce" style={{ animationDelay: "300ms" }} />
      </div>
    </div>
  );
}
