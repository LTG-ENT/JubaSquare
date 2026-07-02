import { useRef, useState } from "react";
import api, { formatDetail } from "@/lib/api";
import { Upload, Loader2, X } from "lucide-react";
import { toast } from "sonner";

/**
 * Image upload field. Controlled: parent passes value (URL) and onChange.
 * Shows preview, upload button, and a remove-x.
 */
export default function ImageUpload({ value, onChange, label = "Image", testId = "image-upload" }) {
  const fileRef = useRef(null);
  const [busy, setBusy] = useState(false);

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Image is too large (max 5 MB)");
      return;
    }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      onChange(data.url);
      toast.success("Image uploaded");
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div>
      {label && (
        <label className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">{label}</label>
      )}
      <div className="mt-1.5 flex items-start gap-3">
        {value ? (
          <div className="relative w-24 h-24 rounded-xl overflow-hidden border border-[var(--js-border)] shrink-0">
            <img src={value} alt="" className="w-full h-full object-cover" onError={(e) => { e.target.style.display = "none"; }} />
            <button type="button" onClick={() => onChange("")} data-testid={`${testId}-remove`}
              className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/70 text-white flex items-center justify-center hover:bg-black">
              <X className="w-3 h-3" />
            </button>
          </div>
        ) : (
          <div className="w-24 h-24 rounded-xl border-2 border-dashed border-[var(--js-border)] bg-[var(--js-bg)] flex items-center justify-center shrink-0">
            <Upload className="w-6 h-6 text-[var(--js-text-secondary)]" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <input type="file" ref={fileRef} accept="image/*" className="hidden" onChange={handleFile} data-testid={`${testId}-input`} />
          <button type="button" onClick={() => fileRef.current?.click()} disabled={busy} data-testid={`${testId}-button`}
            className="inline-flex items-center gap-2 bg-white border border-[var(--js-border)] hover:border-[#1A1A1A] text-[var(--js-text)] text-sm font-semibold px-4 py-2 rounded-xl disabled:opacity-60">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            {value ? "Replace image" : "Upload image"}
          </button>
          <p className="text-[11px] text-[var(--js-text-secondary)] mt-2 leading-relaxed">
            JPG, PNG, WEBP or GIF · max 5 MB.{value && " Or paste a URL below."}
          </p>
          {/* NOTE: use type="text" (NOT type="url") — the uploaded image
              URL is intentionally RELATIVE (/api/uploads/xxx.png) so the
              browser resolves it against whatever origin the app is served
              from (jubasquare.com, www.jubasquare.com, preview, etc.).
              type="url" would trigger native validation and reject
              relative paths with "Please enter a URL". */}
          <input type="text" value={value || ""} placeholder="https://... or /api/uploads/..." onChange={(e) => onChange(e.target.value)} data-testid={`${testId}-url`}
            className="mt-2 w-full bg-[var(--js-bg)] border border-[var(--js-border)] rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-[#1A1A1A]" />
        </div>
      </div>
    </div>
  );
}
