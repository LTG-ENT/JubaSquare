import { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import ProductCard from "@/components/ProductCard";
import WholesaleCard from "@/components/WholesaleCard";
import AreaSelector from "@/components/AreaSelector";
import { useCart } from "@/context/CartContext";
import { Search, X, Package, ChevronRight, ChevronDown } from "lucide-react";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "retail", label: "Retail only" },
  { id: "wholesale", label: "Wholesale only" },
];

export default function Marketplace() {
  const [products, setProducts] = useState([]);
  const [shops, setShops] = useState([]);
  const [categoryTree, setCategoryTree] = useState([]); // [{id,name,children:[...]}]
  const [expandedCats, setExpandedCats] = useState({});
  const [search, setSearch] = useState("");
  const [searchParams, setSearchParams] = useSearchParams();
  const [typeFilter, setTypeFilter] = useState(searchParams.get("view") || "all");
  const [sortBy, setSortBy] = useState("recommended");
  const { area, setArea } = useCart();

  // PRIMARY: Use category_id (UUID) for filtering
  // LEGACY: Also support category (name) for backward compatibility
  const selectedCategoryId = searchParams.get("category_id") || "";
  const selectedCategoryLegacy = searchParams.get("category") || "";
  const selectedShop = searchParams.get("shop") || "";

  useEffect(() => {
    api.get("/shops?limit=200")
      .then((r) => setShops(Array.isArray(r.data) ? r.data : []))
      .catch(() => setShops([]));
    // Pull retail tree (with sub-categories) for the sidebar.
    api
      .get("/categories/tree?group=retail")
      .then((r) => setCategoryTree(Array.isArray(r.data) ? r.data : []))
      .catch(() => setCategoryTree([]));
  }, []);

  useEffect(() => {
    const params = {};
    // PRIMARY: Use category_id for filtering
    if (selectedCategoryId) {
      params.category_id = selectedCategoryId;
    } 
    // LEGACY: Fall back to category name if category_id not present
    else if (selectedCategoryLegacy) {
      params.category = selectedCategoryLegacy;
    }
    if (selectedShop) params.shop_id = selectedShop;
    if (typeFilter === "retail") params.is_wholesale = false;
    if (typeFilter === "wholesale") params.is_wholesale = true;
    api.get("/products", { params: { ...params, limit: 200 } })
      .then((r) => setProducts(Array.isArray(r.data) ? r.data : []))
      .catch(() => setProducts([]));
  }, [selectedCategoryId, selectedCategoryLegacy, selectedShop, typeFilter]);

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

  const filtered = products.filter((p) => {
    if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false;
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
    setSearchParams(next);
  };

  const changeFilter = (f) => {
    setTypeFilter(f);
    const next = new URLSearchParams(searchParams);
    if (f === "all") next.delete("view"); else next.set("view", f);
    setSearchParams(next);
  };

  return (
    <div className="min-h-screen flex flex-col">
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

        <div className="flex flex-wrap gap-2 mb-8 items-center">
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

        <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-8">
          {/* Sidebar */}
          <aside className="space-y-6 lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
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
              <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--js-text-secondary)] font-bold mb-3">Categories</p>
              <div className="flex flex-col gap-1">
                <button
                  onClick={() => setCategory("")}
                  data-testid="category-all"
                  className={`text-left px-3 py-2 rounded-xl text-sm font-medium transition ${
                    !selectedCategoryId && !selectedCategoryLegacy ? "bg-[#1A1A1A] text-white" : "text-[var(--js-text)] hover:bg-[var(--js-subtle)]"
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
                            return (
                              <button
                                key={sub.id}
                                onClick={() => setCategory(sub.id)}
                                data-testid={`subcategory-filter-${subSlug}`}
                                className={`text-left px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                                  subSelected
                                    ? "bg-[#C84B31] text-white"
                                    : "text-[var(--js-text-secondary)] hover:bg-[var(--js-subtle)] hover:text-[var(--js-text)]"
                                }`}
                              >{sub.name}</button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {((selectedCategoryId || selectedCategoryLegacy) || selectedShop || search) && (
              <button
                onClick={() => { setSearchParams({}); setSearch(""); }}
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
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {sorted.map((p) =>
                  p.is_wholesale
                    ? <WholesaleCard key={p.id} product={p} shop={shopForProduct(p)} />
                    : <ProductCard key={p.id} product={p} shop={shopForProduct(p)} />
                )}
              </div>
            )}
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
