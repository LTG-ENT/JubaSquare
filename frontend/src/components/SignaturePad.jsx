import { useRef, useEffect, useState } from "react";
import { Eraser } from "lucide-react";

/**
 * Lightweight HTML5 canvas signature pad.
 * Returns a base64 PNG via `onChange(dataUrl)` after each stroke ends.
 */
export default function SignaturePad({ onChange, height = 160 }) {
  const ref = useRef(null);
  const drawing = useRef(false);
  const [empty, setEmpty] = useState(true);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = c.getBoundingClientRect();
    c.width = rect.width * dpr;
    c.height = height * dpr;
    const ctx = c.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.strokeStyle = "#0E1A2B";
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  }, [height]);

  const pos = (e) => {
    const c = ref.current;
    const rect = c.getBoundingClientRect();
    if (e.touches?.[0]) {
      return { x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top };
    }
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const start = (e) => {
    e.preventDefault();
    const ctx = ref.current.getContext("2d");
    const { x, y } = pos(e);
    ctx.beginPath();
    ctx.moveTo(x, y);
    drawing.current = true;
  };
  const move = (e) => {
    if (!drawing.current) return;
    e.preventDefault();
    const ctx = ref.current.getContext("2d");
    const { x, y } = pos(e);
    ctx.lineTo(x, y);
    ctx.stroke();
  };
  const end = () => {
    if (!drawing.current) return;
    drawing.current = false;
    setEmpty(false);
    if (onChange) onChange(ref.current.toDataURL("image/png"));
  };
  const clear = () => {
    const c = ref.current;
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, c.width, c.height);
    setEmpty(true);
    if (onChange) onChange("");
  };

  return (
    <div className="space-y-2">
      <canvas
        ref={ref}
        onMouseDown={start} onMouseMove={move} onMouseUp={end} onMouseLeave={end}
        onTouchStart={start} onTouchMove={move} onTouchEnd={end}
        style={{ height, width: "100%", touchAction: "none" }}
        className="border-2 border-dashed border-[var(--js-border)] rounded-xl bg-white cursor-crosshair"
        data-testid="signature-canvas"
      />
      <div className="flex items-center justify-between text-xs text-[var(--js-text-secondary)]">
        <span>{empty ? "Customer signs here" : "Looks good — tap below to confirm."}</span>
        <button type="button" onClick={clear} className="inline-flex items-center gap-1 px-2 py-1 hover:bg-gray-100 rounded">
          <Eraser className="w-3 h-3" /> Clear
        </button>
      </div>
    </div>
  );
}
