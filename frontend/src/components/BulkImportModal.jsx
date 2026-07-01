import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { X, Upload, Download, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

/**
 * Bulk product import modal.
 * Props:
 *   shops: [{id, name, kind}]
 *   onClose(): void
 *   onSuccess(createdCount): void
 */
export default function BulkImportModal({ shops = [], onClose, onSuccess }) {
  const [shopId, setShopId] = useState("");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);

  const retailShops = shops.filter((s) => s.kind !== "restaurant");

  const downloadTemplate = async () => {
    try {
      const res = await api.get("/products/bulk-template", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "products_template.csv");
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      toast.error("Could not download template");
    }
  };

  const handleUpload = async () => {
    if (!shopId) {
      toast.error("Please select a shop");
      return;
    }
    if (!file) {
      toast.error("Please choose a CSV file");
      return;
    }
    setUploading(true);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await api.post(`/products/bulk-import?shop_id=${encodeURIComponent(shopId)}`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(res.data);
      if (res.data.created > 0) {
        toast.success(`${res.data.created} product(s) imported`);
        onSuccess?.(res.data.created);
      } else {
        toast.error("No products imported");
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Import failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" data-testid="bulk-import-modal">
      <div className="bg-white dark:bg-[var(--js-panel)] rounded-2xl w-full max-w-2xl shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[var(--js-border)]">
          <h2 className="font-display font-bold text-xl text-[var(--js-text)]">Bulk Import Products</h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-[var(--js-subtle)]" data-testid="close-bulk-import">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-5 overflow-y-auto flex-1">
          {/* Step 1: Template */}
          <div className="rounded-xl border border-[var(--js-border)] p-4 bg-[var(--js-bg)]">
            <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
              <div>
                <p className="font-bold text-sm text-[var(--js-text)]">Step 1 — Download the CSV template</p>
                <p className="text-xs text-[var(--js-text-secondary)] mt-0.5">
                  Fill in one row per product. Required columns: name, category_name (or category_id), price_usd.
                </p>
              </div>
              <button
                onClick={downloadTemplate}
                className="inline-flex items-center gap-2 bg-[#0E1A2B] hover:bg-[#1E3A5F] text-white text-xs font-semibold px-3 py-1.5 rounded-full"
                data-testid="download-template-btn"
              >
                <Download className="w-3.5 h-3.5" /> Download Template
              </button>
            </div>
          </div>

          {/* Step 2: Shop */}
          <div>
            <label className="text-xs uppercase tracking-wide font-bold text-[var(--js-text-secondary)]">Step 2 — Choose target shop</label>
            <select
              value={shopId}
              onChange={(e) => setShopId(e.target.value)}
              className="mt-1 w-full px-3 py-2 rounded-lg border border-[var(--js-border)] bg-white dark:bg-[var(--js-bg)] text-[var(--js-text)]"
              data-testid="bulk-import-shop-select"
            >
              <option value="">— Select a shop —</option>
              {retailShops.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            {retailShops.length === 0 && (
              <p className="text-xs text-[#C84B31] mt-2">You need to create a shop first.</p>
            )}
          </div>

          {/* Step 3: File */}
          <div>
            <label className="text-xs uppercase tracking-wide font-bold text-[var(--js-text-secondary)]">Step 3 — Upload CSV</label>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="mt-1 w-full text-sm text-[var(--js-text)] file:mr-3 file:px-3 file:py-1.5 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-[#C84B31] file:text-white hover:file:bg-[#A83A23]"
              data-testid="bulk-import-file-input"
            />
            {file && (
              <p className="text-xs text-[var(--js-text-secondary)] mt-1">
                Selected: <span className="font-semibold text-[var(--js-text)]">{file.name}</span> ({Math.round(file.size / 1024)} KB)
              </p>
            )}
          </div>

          {/* Results */}
          {result && (
            <div className="rounded-xl border border-[var(--js-border)] p-4 bg-[var(--js-bg)]" data-testid="bulk-import-results">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle2 className="w-5 h-5 text-green-600" />
                <p className="font-bold text-sm text-[var(--js-text)]">
                  {result.created} of {result.total} imported successfully
                </p>
              </div>
              {result.errors?.length > 0 && (
                <div>
                  <p className="text-xs font-bold text-[#C84B31] mb-2 flex items-center gap-1">
                    <AlertCircle className="w-3.5 h-3.5" /> {result.errors.length} row(s) failed:
                  </p>
                  <div className="max-h-48 overflow-y-auto text-xs">
                    <table className="w-full">
                      <thead>
                        <tr className="text-left">
                          <th className="p-1 text-[var(--js-text-secondary)]">Row</th>
                          <th className="p-1 text-[var(--js-text-secondary)]">Name</th>
                          <th className="p-1 text-[var(--js-text-secondary)]">Error</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.errors.map((e, i) => (
                          <tr key={i} className="border-t border-[var(--js-border)]">
                            <td className="p-1">{e.row}</td>
                            <td className="p-1 truncate max-w-[120px]">{e.name || "-"}</td>
                            <td className="p-1 text-[#C84B31]">{e.error}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 p-4 border-t border-[var(--js-border)]">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-full text-sm font-semibold text-[var(--js-text)] hover:bg-[var(--js-subtle)]"
            data-testid="bulk-import-cancel"
          >
            Close
          </button>
          <button
            onClick={handleUpload}
            disabled={uploading || !file || !shopId}
            className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#A83A23] disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold px-5 py-2 rounded-full"
            data-testid="bulk-import-submit"
          >
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            {uploading ? "Importing…" : "Import"}
          </button>
        </div>
      </div>
    </div>
  );
}
