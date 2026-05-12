import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import api from "@/lib/api";
import { LayoutGrid, ChevronDown } from "lucide-react";

const GROUPS = [
  { id: "retail", label: "Retail" },
  { id: "wholesale", label: "Wholesale" },
  { id: "restaurant", label: "Restaurants" },
];

/**
 * Build a deep-link for a category click in the mega-menu.
 *  - ALL groups now use category_id (single source of truth: DB).
 */
function buildHref(groupId, cat) {
  if (groupId === "restaurant") {
    return `/restaurants?category_id=${encodeURIComponent(cat.id)}`;
  }
  if (groupId === "wholesale") {
    return `/marketplace?view=wholesale&category_id=${encodeURIComponent(cat.id)}`;
  }
  // retail
  return `/marketplace?category_id=${encodeURIComponent(cat.id)}`;
}

/**
 * Categories nav button with a hover-triggered mega-menu dropdown.
 * Shows all 4 groups (Retail / Wholesale / Restaurants / Food) in tabs,
 * each tab listing top-level categories with their sub-categories.
 *
 * Props:
 *   - active: bool — applies active styling to the default "Categories" trigger
 *   - onNavigate: () => void — called when a link in the menu is clicked
 *   - trigger: ReactNode (optional) — custom trigger element. When omitted, a
 *     default "Categories" pill button (links to /marketplace) is rendered.
 */
export default function CategoriesNavMenu({ active, onNavigate, trigger }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState({ retail: [], wholesale: [], restaurant: [] });
  const [activeGroup, setActiveGroup] = useState("retail");
  const closeTimer = useRef(null);
  const location = useLocation();

  useEffect(() => {
    api
      .get("/categories/tree")
      .then((r) => {
        // /categories/tree without a group returns a dict keyed by group
        if (r.data && !Array.isArray(r.data)) setData(r.data);
      })
      .catch(() => {});
  }, []);

  // Close menu when route changes
  useEffect(() => {
    setOpen(false);
  }, [location.pathname, location.search]);

  const cancelClose = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };
  const scheduleClose = () => {
    cancelClose();
    closeTimer.current = setTimeout(() => setOpen(false), 150);
  };
  const openNow = () => {
    cancelClose();
    setOpen(true);
  };

  const buildHrefFor = (groupId, cat) => buildHref(groupId, cat);

  const groupHasItems = (gid) => (data[gid] || []).length > 0;
  const totalCount = Object.values(data).reduce(
    (sum, arr) => sum + (arr || []).length + (arr || []).reduce((s, p) => s + (p.children?.length || 0), 0),
    0,
  );

  const currentList = data[activeGroup] || [];

  return (
    <div
      className="relative"
      onMouseEnter={openNow}
      onMouseLeave={scheduleClose}
      data-testid="nav-categories-wrap"
    >
      {trigger ? (
        <span onFocus={openNow} className="contents">
          {trigger}
        </span>
      ) : (
        <Link
          to="/marketplace"
          onFocus={openNow}
          onClick={() => {
            setOpen(false);
            onNavigate?.();
          }}
          data-testid="nav-categories"
          className={`flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium transition-all ${
            active ? "bg-[#E9C46A] text-[#0E1A2B]" : "text-white/85 hover:bg-white/10 hover:text-white"
          }`}
          aria-haspopup="true"
          aria-expanded={open}
        >
          <LayoutGrid className="w-4 h-4" />
          <span>Categories</span>
          <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
        </Link>
      )}

      {/* Mega-menu panel — fixed and centered to viewport so it appears in the
          middle of the page just below the header (which is h-20 = 80px). */}
      {open && totalCount > 0 && (
        <div
          className="fixed left-1/2 -translate-x-1/2 top-20 pt-3 z-50"
          onMouseEnter={openNow}
          onMouseLeave={scheduleClose}
          data-testid="nav-categories-menu"
        >
          <div className="bg-white rounded-2xl shadow-2xl border border-[var(--js-border)] w-[min(92vw,880px)] overflow-hidden">
            {/* Tabs */}
            <div className="flex items-center gap-1 px-3 pt-3 border-b border-[var(--js-border)]">
              {GROUPS.filter((g) => groupHasItems(g.id)).map((g) => (
                <button
                  key={g.id}
                  onMouseEnter={() => setActiveGroup(g.id)}
                  onClick={() => setActiveGroup(g.id)}
                  data-testid={`nav-cat-tab-${g.id}`}
                  className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition ${
                    activeGroup === g.id
                      ? "border-[#C84B31] text-[#C84B31]"
                      : "border-transparent text-[var(--js-text-secondary)] hover:text-[var(--js-text)]"
                  }`}
                >
                  {g.label}
                </button>
              ))}
            </div>

            {/* Grid */}
            <div className="p-5 max-h-[70vh] overflow-y-auto">
              {currentList.length === 0 ? (
                <div className="py-10 text-center text-sm text-[var(--js-text-secondary)]">
                  No categories yet in {activeGroup}.
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-5">
                  {currentList.map((parent) => {
                    const slug = parent.name.replace(/\s+/g, "-").toLowerCase();
                    return (
                      <div key={parent.id} className="min-w-0">
                        <Link
                          to={buildHrefFor(activeGroup, parent)}
                          onClick={() => {
                            setOpen(false);
                            onNavigate?.();
                          }}
                          data-testid={`nav-cat-${slug}`}
                          className="flex items-center gap-2.5 mb-2 group"
                        >
                          {parent.image_url ? (
                            <img
                              src={parent.image_url}
                              alt=""
                              className="w-9 h-9 rounded-lg object-cover bg-[var(--js-bg)] shrink-0"
                              onError={(e) => {
                                e.target.style.display = "none";
                              }}
                            />
                          ) : (
                            <div className="w-9 h-9 rounded-lg bg-[var(--js-bg)] border border-[var(--js-border)] shrink-0 flex items-center justify-center text-xs font-bold text-[var(--js-text-secondary)]">
                              {parent.name.charAt(0)}
                            </div>
                          )}
                          <span className="font-display font-semibold text-sm text-[var(--js-text)] group-hover:text-[#C84B31] truncate">
                            {parent.name}
                          </span>
                        </Link>
                        {(parent.children || []).length > 0 && (
                          <ul className="ml-11 flex flex-col gap-1.5">
                            {parent.children.map((sub) => {
                              const subSlug = sub.name.replace(/\s+/g, "-").toLowerCase();
                              return (
                                <li key={sub.id}>
                                  <Link
                                    to={buildHrefFor(activeGroup, sub)}
                                    onClick={() => {
                                      setOpen(false);
                                      onNavigate?.();
                                    }}
                                    data-testid={`nav-subcat-${subSlug}`}
                                    className="text-xs text-[var(--js-text-secondary)] hover:text-[#C84B31] hover:underline truncate block"
                                  >
                                    {sub.name}
                                  </Link>
                                </li>
                              );
                            })}
                          </ul>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-[var(--js-border)] bg-[var(--js-bg)] flex items-center justify-between">
              <span className="text-xs text-[var(--js-text-secondary)]">
                Hover a tab to switch group · click any category to browse
              </span>
              <Link
                to="/marketplace"
                onClick={() => {
                  setOpen(false);
                  onNavigate?.();
                }}
                data-testid="nav-cat-see-all"
                className="text-xs font-semibold text-[#C84B31] hover:underline"
              >
                See all products →
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
