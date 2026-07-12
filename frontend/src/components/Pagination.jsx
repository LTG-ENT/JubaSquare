import { ChevronLeft, ChevronRight } from "lucide-react";

/**
 * Classic page-number pagination used across the seller dashboard.
 *
 * Props:
 *   page       — 1-indexed current page
 *   total      — total number of items (from server)
 *   pageSize   — items per page
 *   onChange   — (nextPage) => void
 *   testIdPrefix — prefix for data-testid on the buttons (e.g. "products-pagination")
 *
 * Renders nothing when there is only one page (or none).
 */
export function Pagination({ page, total, pageSize, onChange, testIdPrefix = "pagination" }) {
  const pageCount = Math.max(1, Math.ceil((total || 0) / (pageSize || 1)));
  if (pageCount <= 1) return null;

  const clamp = (p) => Math.min(pageCount, Math.max(1, p));

  // Build a compact page-number window: first, current ±2, last, with ellipses.
  const nums = [];
  const push = (n) => { if (!nums.includes(n)) nums.push(n); };
  push(1);
  for (let i = page - 2; i <= page + 2; i++) if (i >= 2 && i <= pageCount - 1) push(i);
  push(pageCount);
  nums.sort((a, b) => a - b);

  const withEllipses = [];
  nums.forEach((n, i) => {
    if (i > 0 && n - nums[i - 1] > 1) withEllipses.push("…");
    withEllipses.push(n);
  });

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div
      className="mt-4 flex flex-wrap items-center justify-between gap-3"
      data-testid={testIdPrefix}
    >
      <p className="text-xs text-[var(--js-text-secondary)]">
        Showing <span className="font-bold text-[var(--js-text)]">{start}</span>–
        <span className="font-bold text-[var(--js-text)]">{end}</span> of{" "}
        <span className="font-bold text-[var(--js-text)]">{total}</span>
      </p>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onChange(clamp(page - 1))}
          disabled={page <= 1}
          data-testid={`${testIdPrefix}-prev`}
          className="inline-flex items-center gap-1 text-xs font-bold px-3 py-1.5 rounded-full border border-[var(--js-border)] bg-white text-[var(--js-text)] disabled:opacity-40 disabled:cursor-not-allowed hover:border-[#1A1A1A] transition"
        >
          <ChevronLeft className="w-3.5 h-3.5" /> Prev
        </button>
        {withEllipses.map((n, i) =>
          n === "…" ? (
            <span key={`e-${i}`} className="px-2 text-xs text-[var(--js-text-secondary)]">…</span>
          ) : (
            <button
              key={n}
              type="button"
              onClick={() => onChange(n)}
              data-testid={`${testIdPrefix}-page-${n}`}
              className={`min-w-[32px] h-8 text-xs font-bold rounded-full border transition ${
                n === page
                  ? "bg-[#1A1A1A] text-white border-[#1A1A1A]"
                  : "bg-white text-[var(--js-text)] border-[var(--js-border)] hover:border-[#1A1A1A]"
              }`}
            >
              {n}
            </button>
          )
        )}
        <button
          type="button"
          onClick={() => onChange(clamp(page + 1))}
          disabled={page >= pageCount}
          data-testid={`${testIdPrefix}-next`}
          className="inline-flex items-center gap-1 text-xs font-bold px-3 py-1.5 rounded-full border border-[var(--js-border)] bg-white text-[var(--js-text)] disabled:opacity-40 disabled:cursor-not-allowed hover:border-[#1A1A1A] transition"
        >
          Next <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

export default Pagination;
