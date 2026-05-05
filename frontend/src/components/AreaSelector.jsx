import { ChevronDown, Search, MapPin } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import api from "@/lib/api";

export default function AreaSelector({ value, onChange, testId = "area-selector" }) {
  const [areas, setAreas] = useState([]);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const inputRef = useRef(null);

  useEffect(() => {
    api.get("/meta/areas").then((r) => setAreas(r.data)).catch(() => setAreas([]));
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return areas;
    return areas.filter((a) => a.toLowerCase().includes(q));
  }, [areas, query]);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        data-testid={testId}
        className="flex items-center gap-2 bg-white border border-[#E2E2D9] rounded-full px-4 py-2.5 hover:border-[#C84B31] transition text-sm font-medium text-[#1A1A1A]"
      >
        <MapPin className="w-4 h-4 text-[#C84B31]" />
        <span className="text-[#5C5C5C] text-xs">Area:</span>
        <span data-testid="selected-area" className="truncate max-w-[140px]">{value}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute mt-2 left-0 z-50 bg-white border border-[#E2E2D9] rounded-2xl shadow-[0_12px_32px_rgba(0,0,0,0.12)] w-[260px] overflow-hidden">
            <div className="p-2 border-b border-[#E2E2D9] sticky top-0 bg-white">
              <div className="flex items-center gap-2 bg-[#F8F5F0] rounded-lg px-3 py-2">
                <Search className="w-4 h-4 text-[#5C5C5C]" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search area..."
                  data-testid="area-search-input"
                  className="flex-1 bg-transparent text-sm outline-none text-[#1A1A1A] placeholder-[#A3A39E]"
                />
              </div>
            </div>
            <div className="max-h-[260px] overflow-y-auto p-2">
              {filtered.length === 0 ? (
                <p className="text-xs text-[#5C5C5C] text-center py-4">No areas match "{query}"</p>
              ) : (
                filtered.map((a) => (
                  <button
                    key={a}
                    onClick={() => { onChange(a); setOpen(false); }}
                    data-testid={`area-option-${a.replace(/\s+/g, "-").toLowerCase()}`}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition ${
                      value === a ? "bg-[#C84B31] text-white" : "text-[#1A1A1A] hover:bg-[#F2EBE5]"
                    }`}
                  >
                    {a}
                  </button>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
