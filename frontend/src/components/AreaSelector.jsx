import { ChevronDown } from "lucide-react";
import { useEffect, useState } from "react";
import api from "@/lib/api";

export default function AreaSelector({ value, onChange, testId = "area-selector" }) {
  const [areas, setAreas] = useState([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.get("/meta/areas").then((r) => setAreas(r.data)).catch(() => setAreas([]));
  }, []);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        data-testid={testId}
        className="flex items-center gap-2 bg-white border border-[#E2E2D9] rounded-full px-4 py-2.5 hover:border-[#C84B31] transition text-sm font-medium text-[#1A1A1A]"
      >
        <span className="text-[#5C5C5C] text-xs">Area:</span>
        <span data-testid="selected-area">{value}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute mt-2 left-0 z-50 bg-white border border-[#E2E2D9] rounded-2xl shadow-[0_12px_32px_rgba(0,0,0,0.12)] p-2 min-w-[180px]">
            {areas.map((a) => (
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
            ))}
          </div>
        </>
      )}
    </div>
  );
}
