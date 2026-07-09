import { useEffect, useState } from "react";
import api from "@/lib/api";
import { X } from "lucide-react";

/**
 * Iter 33 — Storefront faceted attribute filters. Fetches live value counts
 * for the selected category (or business type) and renders checkbox facets.
 * `selected` = { attrKey: [values] }, controlled by the parent page.
 */
export const AttributeFilterPanel = ({ categoryId, businessType, selected = {}, onChange }) => {
  const [facets, setFacets] = useState([]);

  useEffect(() => {
    const params = {};
    if (categoryId) params.category_id = categoryId;
    else if (businessType) params.business_type = businessType;
    else { setFacets([]); return; }
    api.get("/attributes/facets", { params })
      .then((r) => setFacets(r.data?.facets || []))
      .catch(() => setFacets([]));
  }, [categoryId, businessType]);

  if (!facets.length) return null;

  const toggle = (key, value) => {
    const cur = selected[key] || [];
    const next = cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value];
    const out = { ...selected };
    if (next.length) out[key] = next; else delete out[key];
    onChange(out);
  };

  const activeCount = Object.values(selected).reduce((s, v) => s + v.length, 0);

  return (
    <div data-testid="attribute-filter-panel">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--js-text-secondary)] font-bold">
          Filters
        </p>
        {activeCount > 0 && (
          <button
            onClick={() => onChange({})}
            data-testid="attr-filters-clear"
            className="text-[10px] text-[#C84B31] font-bold inline-flex items-center gap-0.5 hover:underline"
          >
            <X className="w-3 h-3" /> Clear ({activeCount})
          </button>
        )}
      </div>
      <div className="space-y-4">
        {facets.map((f) => (
          <div key={f.key} data-testid={`attr-facet-${f.key}`}>
            <p className="text-xs font-bold text-[var(--js-text)] mb-1.5">
              {f.name}{f.unit ? ` (${f.unit})` : ""}
            </p>
            <div className="flex flex-col gap-1">
              {f.values.map((v) => {
                const checked = (selected[f.key] || []).includes(v.value);
                const displayVal = f.type === "boolean" ? (v.value === "true" ? "Yes" : "No") : v.value;
                return (
                  <label
                    key={v.value}
                    className="flex items-center gap-2 px-2 py-1 rounded-lg text-xs cursor-pointer hover:bg-[var(--js-subtle)] select-none"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(f.key, v.value)}
                      data-testid={`attr-filter-${f.key}-${String(v.value).replace(/\s+/g, "-").toLowerCase()}`}
                      className="w-3.5 h-3.5 accent-[#C84B31]"
                    />
                    <span className={`flex-1 ${checked ? "font-bold text-[var(--js-text)]" : "text-[var(--js-text-secondary)]"}`}>
                      {displayVal}
                    </span>
                    <span className="text-[10px] text-[var(--js-text-secondary)]">{v.count}</span>
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AttributeFilterPanel;
