import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, Home } from "lucide-react";
import api from "@/lib/api";

/**
 * CategoryBreadcrumb (Iter 32)
 * -----------------------------
 * Fetches /api/categories/{id}/breadcrumb and renders the ancestor chain
 * as a horizontally-scrollable breadcrumb. Links target /marketplace?category_id=<id>
 * so clicking any ancestor drills the customer into that level.
 *
 * Props:
 *   categoryId — string | null. When null the component renders nothing.
 *   basePath   — where clicking a crumb navigates (default "/marketplace")
 */
export default function CategoryBreadcrumb({ categoryId, basePath = "/marketplace" }) {
  const [crumbs, setCrumbs] = useState([]);
  useEffect(() => {
    if (!categoryId) {
      setCrumbs([]);
      return;
    }
    api
      .get(`/categories/${categoryId}/breadcrumb`)
      .then((r) => setCrumbs(r.data?.breadcrumb || []))
      .catch(() => setCrumbs([]));
  }, [categoryId]);

  if (!categoryId || crumbs.length === 0) return null;

  return (
    <nav
      aria-label="Category breadcrumb"
      data-testid="category-breadcrumb"
      className="flex items-center gap-1 text-xs sm:text-sm text-[var(--js-text-secondary)] overflow-x-auto whitespace-nowrap py-2"
    >
      <Link
        to={basePath}
        className="inline-flex items-center gap-1 hover:text-[var(--js-text)] font-medium"
        data-testid="breadcrumb-home"
      >
        <Home className="w-3.5 h-3.5" /> Home
      </Link>
      {crumbs.map((c, i) => {
        const isLast = i === crumbs.length - 1;
        return (
          <span key={c.id} className="flex items-center gap-1">
            <ChevronRight className="w-3 h-3 text-[var(--js-text-secondary)]/60" />
            {isLast ? (
              <span
                data-testid={`breadcrumb-current`}
                className="font-semibold text-[var(--js-text)]"
              >
                {c.name}
              </span>
            ) : (
              <Link
                to={`${basePath}?category_id=${c.id}`}
                className="hover:text-[var(--js-text)] font-medium"
                data-testid={`breadcrumb-link-${c.id}`}
              >
                {c.name}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
