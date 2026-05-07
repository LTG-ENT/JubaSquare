import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Search, Check } from "lucide-react";
import api from "@/lib/api";

/**
 * Custom area dropdown — replaces the native <select>.
 * Renders the trigger with the same `js-input` styling so it sits flush in forms.
 * The popup is always scrollable (max-h-72) and respects dark-mode tokens.
 *
 * Props:
 *  - value: current selected area (string)
 *  - onChange: (area: string) => void
 *  - options: optional explicit list; otherwise fetches GET /meta/areas
 *  - placeholder: shown when value is empty
 *  - testId: data-testid for the trigger
 *  - className: extra classes for trigger
 *  - disabled: bool
 */
export default function AreaSelectField({
  value,
  onChange,
  options,
  placeholder = "Select area",
  testId = "area-select",
  className = "",
  disabled = false,
}) {
  const [areas, setAreas] = useState(options || []);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const wrapRef = useRef(null);
  const searchRef = useRef(null);

  useEffect(() => {
    if (options && options.length) {
      setAreas(options);
      return;
    }
    let cancelled = false;
    api
      .get("/meta/areas")
      .then((r) => {
        if (cancelled) return;
        setAreas(Array.isArray(r.data) ? r.data : []);
      })
      .catch(() => {
        if (!cancelled) setAreas([]);
      });
    return () => {
      cancelled = true;
    };
  }, [options]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    const t = setTimeout(() => searchRef.current?.focus(), 30);
    return () => clearTimeout(t);
  }, [open]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const onDocClick = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return areas;
    return areas.filter((a) => a.toLowerCase().includes(q));
  }, [areas, query]);

  return (
    <div ref={wrapRef} className={`relative ${className}`}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setOpen((v) => !v)}
        data-testid={testId}
        className="js-input flex items-center justify-between w-full text-left"
      >
        <span className={`truncate ${value ? "" : "text-[var(--js-text-disabled)]"}`}>
          {value || placeholder}
        </span>
        <ChevronDown className={`w-4 h-4 shrink-0 ml-2 text-[var(--js-text-secondary)] transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div
          className="absolute z-50 mt-1.5 left-0 right-0 bg-[var(--js-paper)] border border-[var(--js-border)] rounded-2xl shadow-[0_18px_42px_rgba(0,0,0,0.18)] overflow-hidden"
          data-testid={`${testId}-popup`}
        >
          <div className="p-2 border-b border-[var(--js-border)] bg-[var(--js-paper)]">
            <div className="flex items-center gap-2 bg-[var(--js-subtle)] rounded-lg px-3 py-2">
              <Search className="w-4 h-4 text-[var(--js-text-secondary)]" />
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search area…"
                data-testid={`${testId}-search`}
                className="flex-1 bg-transparent text-sm outline-none text-[var(--js-text)] placeholder-[var(--js-text-disabled)]"
              />
            </div>
          </div>
          <div className="max-h-72 overflow-y-auto overscroll-contain p-1.5">
            {filtered.length === 0 ? (
              <p className="text-xs text-[var(--js-text-secondary)] text-center py-4">
                No areas match "{query}"
              </p>
            ) : (
              filtered.map((a) => {
                const selected = a === value;
                return (
                  <button
                    type="button"
                    key={a}
                    onClick={() => {
                      onChange(a);
                      setOpen(false);
                    }}
                    data-testid={`${testId}-option-${a.replace(/\s+/g, "-").toLowerCase()}`}
                    className={`w-full flex items-center justify-between gap-2 text-left px-3 py-2 rounded-lg text-sm font-medium transition ${
                      selected
                        ? "bg-[#C84B31] text-white"
                        : "text-[var(--js-text)] hover:bg-[var(--js-subtle)]"
                    }`}
                  >
                    <span className="truncate">{a}</span>
                    {selected && <Check className="w-4 h-4 shrink-0" />}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
