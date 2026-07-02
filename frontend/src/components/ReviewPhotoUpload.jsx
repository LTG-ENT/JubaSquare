import { useRef, useState } from "react";
import api, { formatDetail } from "@/lib/api";
import { Camera, Loader2, X } from "lucide-react";
import { toast } from "sonner";

/**
 * Multi-photo upload for reviews. Compresses client-side before upload so we
 * don't ship 5 × 8 MB files to Object Storage. Controlled component — parent
 * owns the array of URLs.
 *
 * @param {string[]} value  Array of image URLs.
 * @param {(urls:string[])=>void} onChange
 * @param {number} max      Max total photos (default 5).
 */
export default function ReviewPhotoUpload({ value = [], onChange, max = 5, testId = "review-photos" }) {
  const fileRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const photos = value || [];
  const remaining = Math.max(0, max - photos.length);

  const compress = (file) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          const MAX = 1600;
          let { width, height } = img;
          if (width > MAX || height > MAX) {
            const s = MAX / Math.max(width, height);
            width = Math.round(width * s);
            height = Math.round(height * s);
          }
          const canvas = document.createElement("canvas");
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext("2d");
          ctx.drawImage(img, 0, 0, width, height);
          canvas.toBlob(
            (blob) => (blob ? resolve(new File([blob], file.name.replace(/\.[^.]+$/, ".jpg"), { type: "image/jpeg" })) : reject(new Error("compress failed"))),
            "image/jpeg",
            0.82
          );
        };
        img.onerror = reject;
        img.src = e.target?.result;
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });

  const handleFiles = async (e) => {
    const files = Array.from(e.target.files || []).slice(0, remaining);
    if (!files.length) return;
    setBusy(true);
    const added = [];
    try {
      for (const file of files) {
        if (file.size > 10 * 1024 * 1024) {
          toast.error(`${file.name} is too large (max 10 MB)`);
          continue;
        }
        const smaller = await compress(file).catch(() => file); // fall back to raw
        const fd = new FormData();
        fd.append("file", smaller);
        const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
        if (data?.url) added.push(data.url);
      }
      if (added.length) {
        onChange([...photos, ...added].slice(0, max));
        toast.success(`${added.length} photo${added.length > 1 ? "s" : ""} added`);
      }
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const remove = (idx) => {
    onChange(photos.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-2" data-testid={testId}>
      <div className="flex flex-wrap items-center gap-2">
        {photos.map((url, i) => (
          <div key={i} className="relative w-16 h-16 rounded-xl overflow-hidden border border-[var(--js-border)] shrink-0" data-testid={`${testId}-thumb-${i}`}>
            <img src={url} alt="" className="w-full h-full object-cover" />
            <button
              type="button"
              onClick={() => remove(i)}
              data-testid={`${testId}-remove-${i}`}
              className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/70 text-white flex items-center justify-center hover:bg-black"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}
        {remaining > 0 && (
          <>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={handleFiles}
              data-testid={`${testId}-input`}
            />
            <button
              type="button"
              disabled={busy}
              onClick={() => fileRef.current?.click()}
              data-testid={`${testId}-add`}
              className="w-16 h-16 rounded-xl border-2 border-dashed border-[var(--js-border)] hover:border-[#C84B31] text-[var(--js-text-secondary)] hover:text-[#C84B31] flex flex-col items-center justify-center gap-0.5 transition"
              title="Add photos"
            >
              {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Camera className="w-5 h-5" />}
              <span className="text-[9px] font-semibold uppercase tracking-wider">Add</span>
            </button>
          </>
        )}
      </div>
      <p className="text-[11px] text-[var(--js-text-secondary)]">
        {photos.length ? `${photos.length} / ${max} photos` : `Optional · up to ${max} photos · auto-compressed`}
      </p>
    </div>
  );
}
