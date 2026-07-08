import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Printer, ArrowLeft, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";

/**
 * SellerLowStockReport (Iter 31)
 * -------------------------------
 * Printable report of every out-of-stock or low-stock product across the
 * seller's shops. Autoprints if `?autoprint=1` is on the URL.
 */
export default function SellerLowStockReport() {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/seller/low-stock-report");
      setReport(data);
    } catch (err) {
      toast.error("Failed to load low-stock report");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    if (window.location.search.includes("autoprint=1")) {
      setTimeout(() => window.print(), 700);
    }
  }, []);

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-[#5C5C5C]">Loading…</div>;
  }
  if (!report) return null;

  const { out_of_stock, low_stock, seller_name, generated_at, total_products, out_of_stock_count, low_stock_count, default_threshold } = report;

  return (
    <div className="min-h-screen bg-white text-[#1A1A1A]" data-testid="seller-low-stock-report">
      {/* Toolbar — hidden on print */}
      <div className="print:hidden max-w-5xl mx-auto px-4 py-4 flex items-center justify-between border-b border-[#E8E8E4]">
        <Link to="/seller" className="inline-flex items-center gap-2 text-sm text-[#5C5C5C] hover:text-[#1A1A1A]" data-testid="back-to-seller">
          <ArrowLeft className="w-4 h-4" /> Back to dashboard
        </Link>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[#F4F1EA] hover:bg-[#E8E8E4] rounded-lg"
            data-testid="refresh-btn"
          >
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 text-sm bg-[#1A1A1A] hover:bg-[#2A2A2A] text-white font-bold rounded-lg"
            data-testid="print-btn"
          >
            <Printer className="w-4 h-4" /> Print
          </button>
        </div>
      </div>

      <main className="max-w-5xl mx-auto px-6 py-8 print:py-2">
        {/* Header */}
        <header className="mb-6 pb-4 border-b-2 border-[#1A1A1A]">
          <div className="flex items-baseline justify-between flex-wrap gap-2">
            <div>
              <p className="text-xs uppercase tracking-[0.25em] text-[#5C5C5C]">JubaSquare · Seller Report</p>
              <h1 className="text-3xl font-bold mt-1">Low-Stock & Out-of-Stock Report</h1>
              <p className="text-sm text-[#5C5C5C] mt-1">
                {seller_name} · generated {new Date(generated_at).toLocaleString()}
              </p>
            </div>
            <div className="text-right text-xs text-[#5C5C5C]">
              <p>Total products: <strong className="text-[#1A1A1A]">{total_products}</strong></p>
              <p>Low-stock threshold: <strong className="text-[#1A1A1A]">≤ {default_threshold}</strong></p>
            </div>
          </div>
          <div className="mt-4 flex gap-3">
            <div className="flex-1 border border-[#D90429] bg-[#D90429]/5 rounded-lg p-3">
              <p className="text-xs uppercase tracking-wider text-[#D90429] font-bold">Out of stock</p>
              <p className="text-2xl font-bold text-[#D90429]">{out_of_stock_count}</p>
            </div>
            <div className="flex-1 border border-[#E9C46A] bg-[#E9C46A]/10 rounded-lg p-3">
              <p className="text-xs uppercase tracking-wider text-[#8B6B00] font-bold">Low stock</p>
              <p className="text-2xl font-bold text-[#8B6B00]">{low_stock_count}</p>
            </div>
            <div className="flex-1 border border-[#2D6A4F] bg-[#2D6A4F]/5 rounded-lg p-3">
              <p className="text-xs uppercase tracking-wider text-[#2D6A4F] font-bold">Healthy</p>
              <p className="text-2xl font-bold text-[#2D6A4F]">{total_products - out_of_stock_count - low_stock_count}</p>
            </div>
          </div>
        </header>

        {/* Out of stock */}
        {out_of_stock.length > 0 && (
          <section className="mb-8" data-testid="section-out-of-stock">
            <h2 className="text-lg font-bold mb-3 flex items-center gap-2">
              <span className="inline-block w-3 h-3 rounded-full bg-[#D90429]" /> Out of stock ({out_of_stock_count})
            </h2>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b-2 border-[#1A1A1A] text-left">
                  <th className="py-2 pr-2 font-bold">#</th>
                  <th className="py-2 pr-2 font-bold">Product</th>
                  <th className="py-2 pr-2 font-bold">SKU</th>
                  <th className="py-2 pr-2 font-bold">Shop</th>
                  <th className="py-2 pr-2 font-bold text-right">Price</th>
                  <th className="py-2 pl-2 font-bold text-right">Stock</th>
                </tr>
              </thead>
              <tbody>
                {out_of_stock.map((p, i) => (
                  <tr key={p.id} className="border-b border-[#E8E8E4]">
                    <td className="py-2 pr-2">{i + 1}</td>
                    <td className="py-2 pr-2">
                      {p.name}
                      {p.is_wholesale ? <span className="ml-2 text-[10px] font-bold text-[#3D5A80]">📦</span> : null}
                    </td>
                    <td className="py-2 pr-2 text-[#5C5C5C]">{p.sku || "—"}</td>
                    <td className="py-2 pr-2 text-[#5C5C5C]">{p._shop_name}</td>
                    <td className="py-2 pr-2 text-right">${(p.price_usd || 0).toFixed(2)}</td>
                    <td className="py-2 pl-2 text-right font-bold text-[#D90429]">{p.stock || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {/* Low stock */}
        {low_stock.length > 0 && (
          <section className="mb-8" data-testid="section-low-stock">
            <h2 className="text-lg font-bold mb-3 flex items-center gap-2">
              <span className="inline-block w-3 h-3 rounded-full bg-[#E9C46A]" /> Low stock ({low_stock_count})
            </h2>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b-2 border-[#1A1A1A] text-left">
                  <th className="py-2 pr-2 font-bold">#</th>
                  <th className="py-2 pr-2 font-bold">Product</th>
                  <th className="py-2 pr-2 font-bold">SKU</th>
                  <th className="py-2 pr-2 font-bold">Shop</th>
                  <th className="py-2 pr-2 font-bold text-right">Price</th>
                  <th className="py-2 pr-2 font-bold text-right">Threshold</th>
                  <th className="py-2 pl-2 font-bold text-right">Stock</th>
                </tr>
              </thead>
              <tbody>
                {low_stock.map((p, i) => (
                  <tr key={p.id} className="border-b border-[#E8E8E4]">
                    <td className="py-2 pr-2">{i + 1}</td>
                    <td className="py-2 pr-2">
                      {p.name}
                      {p.is_wholesale ? <span className="ml-2 text-[10px] font-bold text-[#3D5A80]">📦</span> : null}
                    </td>
                    <td className="py-2 pr-2 text-[#5C5C5C]">{p.sku || "—"}</td>
                    <td className="py-2 pr-2 text-[#5C5C5C]">{p._shop_name}</td>
                    <td className="py-2 pr-2 text-right">${(p.price_usd || 0).toFixed(2)}</td>
                    <td className="py-2 pr-2 text-right text-[#5C5C5C]">≤ {p._threshold}</td>
                    <td className="py-2 pl-2 text-right font-bold text-[#8B6B00]">{p.stock || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {out_of_stock.length === 0 && low_stock.length === 0 && (
          <div className="text-center py-16 text-[#5C5C5C]" data-testid="empty-state">
            <p className="text-3xl mb-2">✅</p>
            <p className="font-semibold">All good — no products are low or out of stock.</p>
          </div>
        )}

        <footer className="mt-12 pt-4 border-t border-[#E8E8E4] text-xs text-[#5C5C5C] flex justify-between">
          <span>Generated by JubaSquare · Seller Portal</span>
          <span>Restock the highlighted products to keep your listings live.</span>
        </footer>
      </main>

      {/* Print CSS */}
      <style>{`
        @media print {
          body { margin: 0; }
          .print\\:hidden { display: none !important; }
          .print\\:py-2 { padding-top: 0.5rem !important; padding-bottom: 0.5rem !important; }
          @page { margin: 12mm; }
        }
      `}</style>
    </div>
  );
}
