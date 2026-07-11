import { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import SeoMeta from "@/components/SeoMeta";
import ProductCard from "@/components/ProductCard";
import WholesaleCard from "@/components/WholesaleCard";
import AreaSelector from "@/components/AreaSelector";
import BadgeFilterBar from "@/components/BadgeFilterBar";
import CategoryBreadcrumb from "@/components/CategoryBreadcrumb";
import AttributeFilterPanel, { ActiveAttributeChips } from "@/components/AttributeFilterPanel";
import { cachedGet } from "@/lib/cachedGet";
import { useCart } from "@/context/CartContext";
import { Search, X, Package, ChevronRight, ChevronDown } from "lucide-react";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "retail", label: "Retail only" },
  { id: "wholesale", label: "Wholesale only" },
];

const PAGE_SIZE = 40; // Iter 33.5 — paginate 40 items per fetch

export default function Marketplace() {
  const [products, setProducts] = useState([]);
  const [productsSkip, setProductsSkip] = useState(0);
  const [hasMoreProducts, setHasMoreProducts] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [shops, setShops] = useState([]);
  const [categoryTree, setCategoryTree] = useState([]); // [{id,name,children:[...]}]
  const [expandedCats, setExpandedCats] = useState({});
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState(searchParams.get("q") || "");
  const [showMobileCats, setShowMobileCats] = useState(false); // Iter 31
  // Iter 33.1 — attribute filters live in the URL (?attrs=...) so filtered
  // pages are shareable/bookmarkable.
  const parseAttrsParam = (sp) => {
    try {
      const parsed = JSON.parse(sp.get("attrs") || "{}");
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch {
      return {};
    }
  };
  const [attrFilters, setAttrFilters] = useState(() => parseAttrsParam(searchParams)); // {attrKey: [values]}
  const [facetDefs, setFacetDefs] = useState([]); // Iter 33.1 — key→name lookup for chips
  const [catsOpen, setCatsOpen] = useState(false); // Sidebar Categories collapsed by default

  // If a category is preselected via URL, expand the sidebar Categories section
  // so users can see their current selection in context.
  useEffect(() => {
    if (searchParams.get("category_id") || searchParams.get("category")) {
      setCatsOpen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Iter 31 — sync ?q= URL param with local search state so the header
  // "See all results" jumps to /marketplace?q=<query> land pre-filtered.
  useEffect(() => {
    const q = searchParams.get("q") || "";
    if (q !== search) setSearch(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);
  const [typeFilter, setTypeFilter] = useState(searchParams.get("view") || "all");
  const [sortBy, setSortBy] = useState("recommended");
  const { area, setArea } = useCart();

  // PRIMARY: Use category_id (UUID) for filtering
  // LEGACY: Also support category (name) for backward compatibility
  const selectedCategoryId = searchParams.get("category_id") || "";
  const selectedCategoryLegacy = searchParams.get("category") || "";
  const selectedShop = searchParams.get("shop") || "";

  // Iter 33.1 — attribute filters live in the URL (?attrs=...) so filtered
  // pages are shareable/bookmarkable. Keep local state in sync both ways.
  // Keep local state in sync with URL changes (back/forward, category switch).
  useEffect(() => {
    const fromUrl = parseAttrsParam(searchParams);
    if (JSON.stringify(fromUrl) !== JSON.stringify(attrFilters)) setAttrFilters(fromUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const applyAttrFilters = (next) => {
    setAttrFilters(next);
    const p = new URLSearchParams(searchParams);
    if (next && Object.keys(next).length) p.set("attrs", JSON.stringify(next));
    else p.delete("attrs");
    setSearchParams(p, { replace: true });
  };

  useEffect(() => {
    api.get("/shops?limit=200")
      .then((r) => setShops(Array.isArray(r.data) ? r.data : []))
      .catch(() => setShops([]));
  }, []);

  // Iter 31 — refetch the category tree whenever the retail/wholesale
  // filter changes so the sidebar reflects the correct set. "All" pulls
  // both trees and merges them. Cached in localStorage for 5 min.
  useEffect(() => {
    const group = typeFilter === "wholesale" ? "wholesale" : typeFilter === "retail" ? "retail" : null;
    if (group) {
      cachedGet(`/categories/tree?group=${group}`)
        .then((data) => setCategoryTree(Array.isArray(data) ? data : []))
        .catch(() => setCategoryTree([]));
    } else {
      // All → merge retail + wholesale
      Promise.all([
        cachedGet("/categories/tree?group=retail").catch(() => []),
        cachedGet("/categories/tree?group=wholesale").catch(() => []),
      ]).then(([retail, whole]) => {
        const merged = [
          ...(Array.isArray(retail) ? retail : []),
          ...(Array.isArray(whole) ? whole : []),
        ];
        setCategoryTree(merged);
      });
    }
  }, [typeFilter]);

  useEffect(() => {
    const params = {};
    // PRIMARY: Use category_id for filtering. Iter 33 — parent categories
    // include products from their whole subtree.
    if (selectedCategoryId) {
      params.category_id = selectedCategoryId;
      params.include_descendants = "true";
    } 
    // LEGACY: Fall back to category name if category_id not present
    else if (selectedCategoryLegacy) {
      params.category = selectedCategoryLegacy;
    }
    if (selectedShop) params.shop_id = selectedShop;
    if (typeFilter === "retail") params.is_wholesale = false;
    if (typeFilter === "wholesale") params.is_wholesale = true;
    // Iter 30 Wave 2 — pass badge chip filters through to backend so the
    // server's ranked list already respects them.
    if (searchParams.get("ltg")) params.ltg = "true";
    if (searchParams.get("deals")) params.deals = "true";
    // ?wholesale=1 chip: only meaningful when typeFilter is not already
    // constraining is_wholesale.
    if (searchParams.get("wholesale") && typeFilter !== "retail") params.is_wholesale = "true";
    // Iter 33 — dynamic attribute filters
    if (Object.keys(attrFilters).length) params.attrs = JSON.stringify(attrFilters);
    // Iter 33.5 — paginate 40 at a time (was 200). Reset when filters change.
    setProductsSkip(0);
    setHasMoreProducts(true);
    setLoadingMore(false);
    api.get("/products", { params: { ...params, limit: PAGE_SIZE, skip: 0 } })
      .then((r) => {
        const arr = Array.isArray(r.data) ? r.data : [];
        setProducts(arr);
        setHasMoreProducts(arr.length === PAGE_SIZE);
      })
      .catch(() => setProducts([]));
  }, [selectedCategoryId, selectedCategoryLegacy, selectedShop, typeFilter, searchParams, attrFilters]);

  // Iter 33.5 — Load more (append next 40 products)
  const loadMoreProducts = () => {
    if (loadingMore || !hasMoreProducts) return;
    setLoadingMore(true);
    const nextSkip = productsSkip + PAGE_SIZE;
    const params = {};
    if (selectedCategoryId) { params.category_id = selectedCategoryId; params.include_descendants = "true"; }
    else if (selectedCategoryLegacy) params.category = selectedCategoryLegacy;
    if (selectedShop) params.shop_id = selectedShop;
    if (typeFilter === "retail") params.is_wholesale = false;
    if (typeFilter === "wholesale") params.is_wholesale = true;
    if (searchParams.get("ltg")) params.ltg = "true";
    if (searchParams.get("deals")) params.deals = "true";
    if (searchParams.get("wholesale") && typeFilter !== "retail") params.is_wholesale = "true";
    if (Object.keys(attrFilters).length) params.attrs = JSON.stringify(attrFilters);
    api.get("/products", { params: { ...params, limit: PAGE_SIZE, skip: nextSkip } })
      .then((r) => {
        const arr = Array.isArray(r.data) ? r.data : [];
        setProducts((prev) => [...prev, ...arr]);
        setProductsSkip(nextSkip);
        setHasMoreProducts(arr.length === PAGE_SIZE);
      })
      .catch(() => setHasMoreProducts(false))
      .finally(() => setLoadingMore(false));
  };

  const categories = useMemo(() => {
    try {
      return [...new Set(products.map((p) => p.category).filter(Boolean))];
    } catch (err) {
      console.error("Error processing categories:", err);
      return [];
    }
  }, [products]);

  // Merge categories from products with the admin-managed tree:
  //   - Use the tree as the primary source (so admin order + sub-categories are respected)
  //   - Also include any product categories that exist but aren't yet in the tree (legacy/unknown)
  const sidebarCats = useMemo(() => {
    try {
      const treeNames = new Set();
      categoryTree.forEach((c) => {
        treeNames.add(c.name);
        (c.children || []).forEach((s) => treeNames.add(s.name));
      });
      const orphans = categories.filter((c) => c && !treeNames.has(c));
      return [
        ...categoryTree.map((c) => ({ ...c, _kind: "tree" })),
        ...orphans.map((name) => ({ id: `orphan-${name}`, name, children: [], _kind: "orphan" })),
      ];
    } catch (err) {
      console.error("Error processing sidebar categories:", err);
      return categoryTree || [];
    }
  }, [categoryTree, categories]);

  const toggleCatExpanded = (id) =>
    setExpandedCats((e) => ({ ...e, [id]: !e[id] }));

  // Iter 28 — "Deals only" filter chip (?deals=1). Shows only products
  // whose promo is currently live.
  const dealsOnly = searchParams.get("deals") === "1";
  const nowIsoMkt = new Date().toISOString();
  const isPromoLive = (p) => {
    const pm = p.promo || {};
    if (!pm.active) return false;
    if (pm.starts_at && nowIsoMkt < pm.starts_at) return false;
    if (pm.ends_at && nowIsoMkt > pm.ends_at) return false;
    return true;
  };
  const filtered = products.filter((p) => {
    if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false;
    if (dealsOnly && !isPromoLive(p)) return false;
    return true;
  });

  // Backend already returns verified-first (recommended). Apply client sort options.
  const sorted = useMemo(() => {
    const arr = [...filtered];
    if (sortBy === "price_asc") arr.sort((a, b) => (a.price_usd || 0) - (b.price_usd || 0));
    else if (sortBy === "price_desc") arr.sort((a, b) => (b.price_usd || 0) - (a.price_usd || 0));
    else if (sortBy === "name_asc") arr.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    else if (sortBy === "newest") arr.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    return arr;
  }, [filtered, sortBy]);

  const shopForProduct = (p) => shops.find((s) => s.id === p.shop_id);
  const activeShop = selectedShop ? shops.find((s) => s.id === selectedShop) : null;

  // Iter 33.4 — find selected category's display name from the tree (any depth)
  const findCatName = (nodes, id) => {
    for (const n of nodes || []) {
      if (n.id === id) return n.name;
      const child = findCatName(n.children, id);
      if (child) return child;
    }
    return null;
  };
  const selectedCategoryName = selectedCategoryId
    ? findCatName(categoryTree, selectedCategoryId) || null
    : null;

  // Update to use category_id instead of category name
  const setCategory = (catId) => {
    const next = new URLSearchParams(searchParams);
    if (catId) {
      next.set("category_id", catId);
      next.delete("category"); // Remove legacy param
    } else {
      next.delete("category_id");
      next.delete("category");
    }
    next.delete("shop");
    next.delete("attrs"); // Iter 33.1 — attribute filters don't carry across categories
    // Iter 29 — "All categories" also clears the "Deals only" filter so
    // customers can escape the promo view with one click.
    next.delete("deals");
    setSearchParams(next);
    // Iter 33.7 — auto-close the Categories tree once a category is chosen
    // so the attribute filters become visible without scrolling.
    if (catId) setCatsOpen(false);
  };

  const changeFilter = (f) => {
    setTypeFilter(f);
    const next = new URLSearchParams(searchParams);
    if (f === "all") next.delete("view"); else next.set("view", f);
    setSearchParams(next);
  };

  return (
    <div className="min-h-screen flex flex-col">
      <SeoMeta pageKey="marketplace" title="Marketplace — JubaSquare" description="Browse thousands of products from trusted South Sudan sellers." />
      <Header />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--js-text-secondary)] font-bold mb-2">Marketplace</p>
            <h1 className="font-display font-bold text-3xl sm:text-4xl lg:text-5xl text-[var(--js-text)]">
              {activeShop ? activeShop.name : "All Products"}
            </h1>
            {activeShop && <p className="text-sm text-[var(--js-text-secondary)] mt-1">{activeShop.description}</p>}
          </div>
          <AreaSelector value={area} onChange={setArea} />
        </div>

        <div className="flex flex-wrap gap-2 mb-4 items-center">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => changeFilter(f.id)}
              data-testid={`market-filter-${f.id}`}
              className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-semibold transition ${
                typeFilter === f.id
                  ? "bg-[#1A1A1A] text-white"
                  : "bg-white border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#1A1A1A]"
              }`}
            >
              {f.id === "wholesale" && <Package className="w-3.5 h-3.5" />}
              {f.label}
            </button>
          ))}

          <div className="ml-auto flex items-center gap-2">
            <label className="text-xs font-semibold text-[var(--js-text-secondary)]">Sort by</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              data-testid="market-sort-by"
              className="bg-white border border-[var(--js-border)] rounded-full px-4 py-2 text-sm font-semibold focus:outline-none focus:border-[#C84B31] shadow-sm cursor-pointer"
            >
              <option value="recommended">Recommended (verified first)</option>
              <option value="newest">Newest first</option>
              <option value="price_asc">Price: low → high</option>
              <option value="price_desc">Price: high → low</option>
              <option value="name_asc">Name: A → Z</option>
            </select>
          </div>
        </div>

        {/* Iter 32 — Category breadcrumb (only shown when a category is
             selected). Sits above the badge filter row so customers see the
             path they're browsing at a glance. */}
        {selectedCategoryId && (
          <div className="mb-2">
            <CategoryBreadcrumb categoryId={selectedCategoryId} />
          </div>
        )}

        {/* Iter 33.1 + 33.4 — unified active filter chip row. Includes
             the selected category, "Deals only" and per-attribute chips.
             Each chip removes only its own filter with one tap. */}
        {(selectedCategoryName || selectedCategoryLegacy || dealsOnly || Object.keys(attrFilters).length > 0) && (
          <div className="mb-3 flex flex-wrap items-center gap-2" data-testid="active-filter-chips">
            {(selectedCategoryName || selectedCategoryLegacy) && (
              <button
                onClick={() => setCategory("")}
                data-testid="active-chip-category"
                title="Remove category filter"
                className="inline-flex items-center gap-1.5 pl-3 pr-2 py-1.5 rounded-full bg-[#1A1A1A] text-white text-xs font-semibold hover:bg-[#C84B31] transition-colors"
              >
                <span className="opacity-70">Category:</span> {selectedCategoryName || selectedCategoryLegacy}
                <X className="w-3 h-3" />
              </button>
            )}
            {dealsOnly && (
              <button
                onClick={() => {
                  const next = new URLSearchParams(searchParams);
                  next.delete("deals");
                  setSearchParams(next);
                }}
                data-testid="active-chip-deals"
                title="Remove deals filter"
                className="inline-flex items-center gap-1.5 pl-3 pr-2 py-1.5 rounded-full bg-[#C84B31] text-white text-xs font-semibold hover:bg-[#A83A23] transition-colors"
              >
                <span aria-hidden>🔥</span> Deals only
                <X className="w-3 h-3" />
              </button>
            )}
            {Object.keys(attrFilters).length > 0 && (
              <ActiveAttributeChips facets={facetDefs} selected={attrFilters} onChange={applyAttrFilters} />
            )}
            {/* Universal clear-all */}
            {((selectedCategoryName || selectedCategoryLegacy ? 1 : 0)
              + (dealsOnly ? 1 : 0)
              + Object.values(attrFilters).reduce((s, v) => s + (Array.isArray(v) ? v.length : 0), 0)) > 1 && (
              <button
                onClick={() => { setSearchParams({}); setAttrFilters({}); }}
                data-testid="active-chips-clear-all"
                className="text-xs font-bold text-[#C84B31] hover:underline"
              >
                Clear all
              </button>
            )}
          </div>
        )}

        {/* Iter 30 Wave 2 — Filter-by-badge chip row */}
        <div className="mb-4">
          <BadgeFilterBar showWholesale={typeFilter !== "retail"} />
        </div>

        {/* Iter 31 — Mobile/tablet launcher (desktop uses left rail).
             Opens a bottom-sheet with attribute filters + category tree. */}
        <div className="lg:hidden mb-4 flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setShowMobileCats(true)}
            data-testid="mobile-categories-btn"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#1A1A1A] text-white text-sm font-semibold shadow-sm"
          >
            <Package className="w-4 h-4" />
            Filters & categories
            {(selectedCategoryId || dealsOnly || Object.keys(attrFilters).length > 0) && (
              <span className="ml-1 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-[#C84B31] text-white text-[10px] font-bold" aria-hidden>
                {(selectedCategoryId || selectedCategoryLegacy ? 1 : 0)
                  + (dealsOnly ? 1 : 0)
                  + Object.values(attrFilters).reduce((s, v) => s + (Array.isArray(v) ? v.length : 0), 0)}
              </span>
            )}
          </button>
          {(selectedCategoryId || selectedCategoryLegacy || dealsOnly || Object.keys(attrFilters).length > 0) && (
            <button
              onClick={() => { setSearchParams({}); setAttrFilters({}); }}
              className="text-xs text-[#C84B31] font-bold underline"
              data-testid="mobile-clear-all"
            >
              Clear
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-8">
          {/* Sidebar — desktop only. Mobile uses the drawer below. */}
          <aside className="space-y-6 lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto hidden lg:block">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-[var(--js-text-secondary)]" />
              <input
                data-testid="marketplace-search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search products..."
                className="w-full bg-white border border-[var(--js-border)] rounded-full pl-11 pr-4 py-2.5 text-sm focus:outline-none focus:border-[#C84B31] shadow-sm"
              />
            </div>

            <div>
              <button
                type="button"
                onClick={() => setCatsOpen((v) => !v)}
                data-testid="sidebar-categories-toggle"
                className="w-full flex items-center justify-between mb-3 group"
                aria-expanded={catsOpen}
              >
                <span className="text-[10px] uppercase tracking-[0.2em] text-[var(--js-text-secondary)] font-bold group-hover:text-[var(--js-text)] transition">Categories</span>
                {catsOpen ? (
                  <ChevronDown className="w-4 h-4 text-[var(--js-text-secondary)]" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-[var(--js-text-secondary)]" />
                )}
              </button>
              {catsOpen && (
              <div className="flex flex-col gap-1">
                <button
                  onClick={() => {
                    const next = new URLSearchParams(searchParams);
                    // Iter 29 — toggle behaviour: clicking Deals a second
                    // time clears the filter.
                    if (dealsOnly) next.delete("deals");
                    else next.set("deals", "1");
                    setSearchParams(next);
                  }}
                  data-testid="category-deals-only"
                  className={`text-left px-3 py-2 rounded-xl text-sm font-bold transition inline-flex items-center gap-2 ${
                    dealsOnly
                      ? "bg-gradient-to-r from-[#E14B31] via-[#C84B31] to-[#B23A21] text-white shadow-md"
                      : "text-[#C84B31] border border-[#C84B31] hover:bg-[#C84B31]/10"
                  }`}
                >
                  <span aria-hidden>🔥</span> Deals only
                </button>
                <button
                  onClick={() => setCategory("")}
                  data-testid="category-all"
                  className={`text-left px-3 py-2 rounded-xl text-sm font-medium transition ${
                    !selectedCategoryId && !selectedCategoryLegacy && !dealsOnly ? "bg-[#1A1A1A] text-white" : "text-[var(--js-text)] hover:bg-[var(--js-subtle)]"
                  }`}
                >All categories</button>
                {sidebarCats.map((c) => {
                  const slug = c.name.replace(/\s+/g, "-").toLowerCase();
                  const hasKids = (c.children || []).length > 0;
                  const isOpen = !!expandedCats[c.id] || c.children?.some((k) => k.id === selectedCategoryId);
                  const isSelected = selectedCategoryId === c.id;
                  return (
                    <div key={c.id}>
                      <div className="flex items-center">
                        <button
                          onClick={() => setCategory(c.id)}
                          data-testid={`category-filter-${slug}`}
                          className={`flex-1 text-left px-3 py-2 rounded-xl text-sm font-medium transition ${
                            isSelected ? "bg-[#1A1A1A] text-white" : "text-[var(--js-text)] hover:bg-[var(--js-subtle)]"
                          }`}
                        >{c.name}</button>
                        {hasKids && (
                          <button
                            onClick={() => toggleCatExpanded(c.id)}
                            data-testid={`category-expand-${slug}`}
                            className="ml-1 w-7 h-7 rounded-lg hover:bg-[var(--js-subtle)] flex items-center justify-center text-[var(--js-text-secondary)]"
                            aria-label="Toggle sub-categories"
                          >
                            {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </button>
                        )}
                      </div>
                      {hasKids && isOpen && (
                        <div className="mt-1 ml-3 pl-3 border-l border-[var(--js-border)] flex flex-col gap-1">
                          {c.children.map((sub) => {
                            const subSlug = sub.name.replace(/\s+/g, "-").toLowerCase();
                            const subSelected = selectedCategoryId === sub.id;
                            const subKids = sub.children || [];
                            const subOpen = subSelected || subKids.some((k) => k.id === selectedCategoryId);
                            return (
                              <div key={sub.id}>
                                <button
                                  onClick={() => setCategory(sub.id)}
                                  data-testid={`subcategory-filter-${subSlug}`}
                                  className={`w-full text-left px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                                    subSelected
                                      ? "bg-[#C84B31] text-white"
                                      : "text-[var(--js-text-secondary)] hover:bg-[var(--js-subtle)] hover:text-[var(--js-text)]"
                                  }`}
                                >{sub.name}</button>
                                {/* Iter 33 — 3rd level (sub-sub-categories) */}
                                {subKids.length > 0 && subOpen && (
                                  <div className="mt-0.5 ml-3 pl-2 border-l border-[var(--js-border)] flex flex-col gap-0.5">
                                    {subKids.map((leaf) => (
                                      <button
                                        key={leaf.id}
                                        onClick={() => setCategory(leaf.id)}
                                        data-testid={`subsubcategory-filter-${leaf.name.replace(/\s+/g, "-").toLowerCase()}`}
                                        className={`text-left px-2.5 py-1 rounded-lg text-[11px] font-medium transition ${
                                          selectedCategoryId === leaf.id
                                            ? "bg-[#C84B31] text-white"
                                            : "text-[var(--js-text-secondary)] hover:bg-[var(--js-subtle)]"
                                        }`}
                                      >{leaf.name}</button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              )}
            </div>

            {/* Iter 33 — dynamic attribute filters. Category-specific when a
                 category is selected, otherwise business-type-wide facets. */}
            {selectedCategoryId ? (
              <AttributeFilterPanel
                categoryId={selectedCategoryId}
                selected={attrFilters}
                onChange={applyAttrFilters}
                onFacets={setFacetDefs}
              />
            ) : (
              <AttributeFilterPanel
                businessType={typeFilter === "wholesale" ? "wholesale" : "retail"}
                selected={attrFilters}
                onChange={applyAttrFilters}
                onFacets={setFacetDefs}
              />
            )}

            {((selectedCategoryId || selectedCategoryLegacy) || selectedShop || search) && (
              <button
                onClick={() => { setSearchParams({}); setSearch(""); setAttrFilters({}); }}
                data-testid="clear-filters"
                className="text-xs text-[#C84B31] font-bold flex items-center gap-1 hover:underline"
              >
                <X className="w-3 h-3" /> Clear filters
              </button>
            )}
          </aside>

          {/* Grid */}
          <div>
            {sorted.length === 0 ? (
              <div className="text-center py-20 text-[var(--js-text-secondary)]" data-testid="empty-products">
                No products found.
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                  {sorted.map((p) =>
                    p.is_wholesale
                      ? <WholesaleCard key={p.id} product={p} shop={shopForProduct(p)} />
                      : <ProductCard key={p.id} product={p} shop={shopForProduct(p)} />
                  )}
                </div>
                {hasMoreProducts && (
                  <div className="mt-8 flex justify-center">
                    <button
                      onClick={loadMoreProducts}
                      disabled={loadingMore}
                      data-testid="load-more-products"
                      className="px-6 py-3 rounded-full bg-[#1A1A1A] text-white text-sm font-bold hover:bg-black disabled:opacity-60 disabled:cursor-not-allowed shadow-md"
                    >
                      {loadingMore ? "Loading…" : `Load more (${PAGE_SIZE} at a time)`}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Iter 31 — Mobile categories bottom sheet */}
      {showMobileCats && (
        <div
          className="fixed inset-0 z-50 lg:hidden"
          onClick={() => setShowMobileCats(false)}
          data-testid="mobile-categories-drawer"
        >
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div
            onClick={(e) => e.stopPropagation()}
            className="absolute bottom-0 inset-x-0 max-h-[80vh] bg-white rounded-t-3xl shadow-2xl flex flex-col animate-in slide-in-from-bottom duration-200"
          >
            <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--js-border)] sticky top-0 bg-white rounded-t-3xl">
              <h3 className="font-display font-bold text-lg text-[var(--js-text)]">Filters & categories</h3>
              <button
                onClick={() => setShowMobileCats(false)}
                data-testid="mobile-categories-close"
                className="p-2 rounded-full hover:bg-[var(--js-subtle)]"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="overflow-y-auto flex-1 px-5 py-4 space-y-4">
              {/* Categories — top of the sheet, collapsed by default. */}
              <div>
                <button
                  type="button"
                  onClick={() => setCatsOpen((v) => !v)}
                  data-testid="mobile-categories-toggle"
                  aria-expanded={catsOpen}
                  className="w-full flex items-center justify-between mb-2"
                >
                  <span className="text-[10px] uppercase tracking-[0.2em] text-[var(--js-text-secondary)] font-bold">Categories</span>
                  {catsOpen ? (
                    <ChevronDown className="w-4 h-4 text-[var(--js-text-secondary)]" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-[var(--js-text-secondary)]" />
                  )}
                </button>
                {catsOpen && (
                  <div className="space-y-1">
                    <button
                      onClick={() => {
                        const next = new URLSearchParams(searchParams);
                        if (dealsOnly) next.delete("deals"); else next.set("deals", "1");
                        setSearchParams(next);
                        setShowMobileCats(false);
                      }}
                      className={`w-full text-left px-3 py-3 rounded-xl text-sm font-bold inline-flex items-center gap-2 ${
                        dealsOnly ? "bg-gradient-to-r from-[#E14B31] via-[#C84B31] to-[#B23A21] text-white" : "text-[#C84B31] border border-[#C84B31]"
                      }`}
                    >
                      <span aria-hidden>🔥</span> Deals only
                    </button>
                    <button
                      onClick={() => { setCategory(""); setShowMobileCats(false); }}
                      className={`w-full text-left px-3 py-3 rounded-xl text-sm font-medium ${
                        !selectedCategoryId && !selectedCategoryLegacy && !dealsOnly ? "bg-[#1A1A1A] text-white" : "text-[var(--js-text)] hover:bg-[var(--js-subtle)]"
                      }`}
                    >
                      All categories
                    </button>
                    {sidebarCats.map((c) => (
                      <div key={c.id}>
                        <button
                          onClick={() => { setCategory(c.id); setShowMobileCats(false); }}
                          className={`w-full text-left px-3 py-3 rounded-xl text-sm font-medium ${
                            selectedCategoryId === c.id ? "bg-[#1A1A1A] text-white" : "text-[var(--js-text)] hover:bg-[var(--js-subtle)]"
                          }`}
                          data-testid={`mobile-category-${c.name.replace(/\s+/g, "-").toLowerCase()}`}
                        >
                          {c.name}
                        </button>
                        {(c.children || []).map((sub) => (
                          <div key={sub.id}>
                            <button
                              onClick={() => { setCategory(sub.id); setShowMobileCats(false); }}
                              className={`w-full text-left px-6 py-2 rounded-xl text-xs font-medium ${
                                selectedCategoryId === sub.id ? "bg-[#C84B31] text-white" : "text-[var(--js-text-secondary)] hover:bg-[var(--js-subtle)]"
                              }`}
                            >
                              → {sub.name}
                            </button>
                            {(sub.children || []).map((leaf) => (
                              <button
                                key={leaf.id}
                                onClick={() => { setCategory(leaf.id); setShowMobileCats(false); }}
                                className={`w-full text-left px-9 py-1.5 rounded-xl text-[11px] font-medium ${
                                  selectedCategoryId === leaf.id ? "bg-[#C84B31] text-white" : "text-[var(--js-text-secondary)] hover:bg-[var(--js-subtle)]"
                                }`}
                              >
                                →→ {leaf.name}
                              </button>
                            ))}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Attribute filters — below categories */}
              <div data-testid="mobile-attribute-filters" className="pt-2 border-t border-[var(--js-border)]">
                {selectedCategoryId ? (
                  <AttributeFilterPanel
                    categoryId={selectedCategoryId}
                    selected={attrFilters}
                    onChange={applyAttrFilters}
                    onFacets={setFacetDefs}
                  />
                ) : (
                  <AttributeFilterPanel
                    businessType={typeFilter === "wholesale" ? "wholesale" : "retail"}
                    selected={attrFilters}
                    onChange={applyAttrFilters}
                    onFacets={setFacetDefs}
                  />
                )}
              </div>
            </div>

            {/* Sticky footer with Apply/Reset for a clear mobile CTA */}
            <div className="border-t border-[var(--js-border)] px-5 py-3 flex items-center gap-2 bg-white">
              <button
                onClick={() => { setAttrFilters({}); applyAttrFilters({}); }}
                className="flex-1 px-4 py-2.5 rounded-full text-sm font-semibold text-[var(--js-text)] border border-[var(--js-border)] hover:bg-[var(--js-subtle)]"
                data-testid="mobile-drawer-reset"
              >
                Reset filters
              </button>
              <button
                onClick={() => setShowMobileCats(false)}
                className="flex-1 px-4 py-2.5 rounded-full text-sm font-bold text-white bg-[#C84B31] hover:bg-[#A83A23]"
                data-testid="mobile-drawer-apply"
              >
                Show results
              </button>
            </div>
          </div>
        </div>
      )}

      <Footer />
    </div>
  );
}
