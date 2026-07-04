import { useEffect, useMemo, useState } from "react";
import api, { formatPrice } from "@/lib/api";
import { useCart } from "@/context/CartContext";
import { TrendingUp, ShoppingBag, Package, AlertTriangle, DollarSign, Printer, Store, ChefHat } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Area, AreaChart } from "recharts";

const CHANNELS = [
  { id: "combined", label: "All", icon: TrendingUp },
  { id: "marketplace", label: "Shops", icon: Store },
  { id: "restaurant", label: "Restaurants", icon: ChefHat },
];

function StatCard({ icon: Icon, label, value, sub, accent = "#C84B31" }) {
  return (
    <div className="bg-white dark:bg-[var(--js-panel)] rounded-2xl border border-[var(--js-border)] p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-widest font-bold text-[var(--js-text-secondary)]">{label}</p>
          <p className="mt-1 font-display font-bold text-2xl text-[var(--js-text)]">{value}</p>
          {sub && <p className="mt-1 text-xs text-[var(--js-text-secondary)]">{sub}</p>}
        </div>
        <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${accent}22`, color: accent }}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </div>
  );
}

export default function SellerAnalyticsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState(30); // 7 or 30
  const [channel, setChannel] = useState("combined");
  const { currency = "USD", exchangeRate = 1 } = useCart() || {};

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api.get("/seller/analytics")
      .then((r) => { if (alive) setData(r.data); })
      .catch(() => {/* silent */})
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  const fmt = (usd) => formatPrice(usd, exchangeRate, currency);

  const scoped = useMemo(() => {
    if (!data) return null;
    const byCh = data.by_channel || {};
    const c = byCh[channel] || { totals: data.totals || {}, revenue_series: data.revenue_series || [] };
    return {
      totals: c.totals || {},
      series: (c.revenue_series || []).slice(-range),
    };
  }, [data, channel, range]);

  const printAnalytics = () => {
    if (!data) return;
    const byCh = data.by_channel || {};
    const w = window.open("", "_blank");
    if (!w) return;
    const channelBlock = (id, name) => {
      const src = byCh[id] || { totals: {}, revenue_series: [] };
      const t = src.totals || {};
      const s = (src.revenue_series || []).slice(-range);
      const totalRev = s.reduce((a, b) => a + (b.revenue || 0), 0);
      const totalOrd = s.reduce((a, b) => a + (b.orders || 0), 0);
      return `
        <section>
          <h2>${name}</h2>
          <table>
            <tr><th>Today</th><td>${fmt(t.today?.revenue || 0)}</td><td>${t.today?.orders || 0} orders</td></tr>
            <tr><th>Last 7 days</th><td>${fmt(t.week?.revenue || 0)}</td><td>${t.week?.orders || 0} orders</td></tr>
            <tr><th>Last 30 days</th><td>${fmt(t.month?.revenue || 0)}</td><td>${t.month?.orders || 0} orders</td></tr>
            <tr><th>All time</th><td>${fmt(t.all_time?.revenue || 0)}</td><td>${t.all_time?.orders || 0} orders</td></tr>
            <tr class="tot"><th>Range subtotal</th><td>${fmt(totalRev)}</td><td>${totalOrd} orders</td></tr>
          </table>
        </section>
      `;
    };
    const topProducts = (data.top_products || []).map((p) =>
      `<tr><td>${p.name}</td><td>${p.quantity}</td><td>${fmt(p.revenue)}</td></tr>`
    ).join("");
    const lowStock = (data.low_stock || []).map((p) =>
      `<tr><td>${p.name}</td><td>${p.stock}</td></tr>`
    ).join("");
    w.document.write(`
<!doctype html><html><head><title>Sales Analytics</title>
<style>
  body { font-family: Helvetica, Arial, sans-serif; max-width: 720px; margin: 30px auto; color: #111; padding: 0 20px; }
  h1 { text-transform: uppercase; letter-spacing: 3px; text-align: center; border-bottom: 2px solid #111; padding-bottom: 8px; }
  h2 { margin-top: 22px; letter-spacing: 2px; text-transform: uppercase; color: #C84B31; font-size: 13px; }
  section { border: 1px dashed #999; border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; }
  table { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 12px; }
  th { text-align: left; padding: 6px 8px; background: #f4f4f0; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; }
  td { padding: 6px 8px; border-bottom: 1px dashed #ddd; }
  tr.tot th, tr.tot td { background: #111; color: #fff; }
  .meta { text-align: center; color: #666; font-size: 11px; margin-bottom: 12px; }
  @media print { body { margin: 0; } }
</style></head><body>
  <h1>Sales Analytics</h1>
  <p class="meta">Generated ${new Date().toLocaleString()} · Currency: ${currency}${currency === "SSP" ? ` · Rate: 1 USD = SSP ${exchangeRate.toLocaleString()}` : ""}</p>
  ${channelBlock("combined", "Overall (all channels)")}
  ${channelBlock("marketplace", "Shops (marketplace)")}
  ${channelBlock("restaurant", "Restaurants")}
  <section>
    <h2>Top 5 products</h2>
    <table><tr><th>Product</th><th>Qty sold</th><th>Revenue</th></tr>${topProducts || `<tr><td colspan="3">No sales yet.</td></tr>`}</table>
  </section>
  ${lowStock ? `<section><h2>Low stock (${data.low_stock.length})</h2><table><tr><th>Product</th><th>Left</th></tr>${lowStock}</table></section>` : ""}
</body></html>`);
    w.document.close();
    setTimeout(() => { try { w.focus(); w.print(); } catch (_) { /* popup blocked */ } }, 400);
  };

  if (loading) return <div className="p-6 text-[var(--js-text-secondary)]">Loading analytics…</div>;
  if (!data) return <div className="p-6 text-[var(--js-text-secondary)]">Could not load analytics.</div>;

  const totals = scoped.totals;
  const series = scoped.series;

  return (
    <div className="space-y-6" data-testid="seller-analytics-tab">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="font-display font-bold text-xl text-[var(--js-text)] flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-[#C84B31]" /> Sales Analytics
          </h2>
          <p className="text-sm text-[var(--js-text-secondary)] mt-1">
            Revenue reflects your <strong>earnings</strong> (after commission, incl. delivery you kept). Toggle to see shops or restaurants only.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={printAnalytics}
            data-testid="analytics-print"
            className="inline-flex items-center gap-1 bg-[#1A1A1A] hover:bg-black text-white text-xs font-semibold px-3 py-1.5 rounded-full"
          >
            <Printer className="w-3.5 h-3.5" /> Print
          </button>
          <div className="inline-flex bg-[var(--js-subtle)] rounded-full p-1">
            {[7, 30].map((n) => (
              <button
                key={n}
                onClick={() => setRange(n)}
                className={`px-3 py-1 rounded-full text-xs font-semibold ${range === n ? "bg-[#0E1A2B] text-white" : "text-[var(--js-text-secondary)]"}`}
                data-testid={`range-${n}d`}
              >{n}d</button>
            ))}
          </div>
        </div>
      </div>

      {/* Channel selector */}
      <div className="inline-flex bg-[var(--js-subtle)] rounded-full p-1 flex-wrap">
        {CHANNELS.map((ch) => {
          const Icon = ch.icon;
          const active = channel === ch.id;
          return (
            <button
              key={ch.id}
              onClick={() => setChannel(ch.id)}
              data-testid={`analytics-channel-${ch.id}`}
              className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold transition ${
                active ? "bg-[#C84B31] text-white shadow" : "text-[var(--js-text-secondary)] hover:text-[var(--js-text)]"
              }`}
            >
              <Icon className="w-3.5 h-3.5" /> {ch.label}
            </button>
          );
        })}
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard icon={DollarSign} label="Today" value={fmt(totals.today?.revenue)} sub={`${totals.today?.orders || 0} orders`} accent="#C84B31" />
        <StatCard icon={DollarSign} label="Last 7 days" value={fmt(totals.week?.revenue)} sub={`${totals.week?.orders || 0} orders`} accent="#E9C46A" />
        <StatCard icon={DollarSign} label="Last 30 days" value={fmt(totals.month?.revenue)} sub={`${totals.month?.orders || 0} orders`} accent="#2A9D8F" />
        <StatCard icon={ShoppingBag} label="All time" value={fmt(totals.all_time?.revenue)} sub={`${totals.all_time?.orders || 0} orders`} accent="#0E1A2B" />
      </div>

      {/* Revenue chart */}
      <div className="bg-white dark:bg-[var(--js-panel)] rounded-2xl border border-[var(--js-border)] p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold text-[var(--js-text)]">Revenue ({currency})</h3>
          <p className="text-xs text-[var(--js-text-secondary)]">Last {range} days · {CHANNELS.find((c) => c.id === channel).label}</p>
        </div>
        <div style={{ width: "100%", height: 260 }}>
          <ResponsiveContainer>
            <AreaChart data={series} margin={{ top: 5, right: 10, left: -8, bottom: 0 }}>
              <defs>
                <linearGradient id="rev-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#C84B31" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#C84B31" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
              <XAxis
                dataKey="date"
                tickFormatter={(d) => (d ? d.slice(5) : "")}
                fontSize={11}
              />
              <YAxis
                fontSize={11}
                tickFormatter={(v) =>
                  currency === "USD"
                    ? "$" + v.toFixed(0)
                    : (v * exchangeRate).toLocaleString("en-US", { maximumFractionDigits: 0 })
                }
                width={currency === "SSP" ? 60 : 40}
              />
              <Tooltip
                formatter={(v, name) => (name === "revenue" ? [fmt(v), "Revenue"] : [v, "Orders"])}
                labelFormatter={(l) => `Date: ${l}`}
              />
              <Area type="monotone" dataKey="revenue" stroke="#C84B31" strokeWidth={2} fill="url(#rev-grad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Two-column: Top products + Low performers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white dark:bg-[var(--js-panel)] rounded-2xl border border-[var(--js-border)] p-4 shadow-sm">
          <h3 className="font-bold text-[var(--js-text)] flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-[#2A9D8F]" /> Top 5 products (revenue)
          </h3>
          {data.top_products?.length ? (
            <ul className="space-y-2">
              {data.top_products.map((p) => (
                <li key={p.id} className="flex items-center gap-3 p-2 rounded-lg bg-[var(--js-bg)]">
                  {p.image_url ? (
                    <img src={p.image_url} alt="" className="w-10 h-10 rounded-lg object-cover" />
                  ) : (
                    <div className="w-10 h-10 rounded-lg bg-[var(--js-subtle)] flex items-center justify-center">
                      <Package className="w-4 h-4 text-[var(--js-text-secondary)]" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[var(--js-text)] truncate">{p.name}</p>
                    <p className="text-xs text-[var(--js-text-secondary)]">{p.quantity} sold</p>
                  </div>
                  <p className="font-bold text-sm text-[#C84B31] whitespace-nowrap">{fmt(p.revenue)}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[var(--js-text-secondary)] italic py-4">No sales yet.</p>
          )}
        </div>

        <div className="bg-white dark:bg-[var(--js-panel)] rounded-2xl border border-[var(--js-border)] p-4 shadow-sm">
          <h3 className="font-bold text-[var(--js-text)] flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-[#E9C46A]" /> Low performers (last 30 days)
          </h3>
          {data.low_performers?.length ? (
            <ul className="space-y-2">
              {data.low_performers.map((p) => (
                <li key={p.id} className="flex items-center gap-3 p-2 rounded-lg bg-[var(--js-bg)]">
                  {p.image_url ? (
                    <img src={p.image_url} alt="" className="w-10 h-10 rounded-lg object-cover" />
                  ) : (
                    <div className="w-10 h-10 rounded-lg bg-[var(--js-subtle)] flex items-center justify-center">
                      <Package className="w-4 h-4 text-[var(--js-text-secondary)]" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[var(--js-text)] truncate">{p.name}</p>
                    <p className="text-xs text-[var(--js-text-secondary)]">{p.quantity} sold in 30d — consider a promo</p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[var(--js-text-secondary)] italic py-4">Every product is doing well.</p>
          )}
        </div>
      </div>

      {/* Low stock */}
      {data.low_stock?.length > 0 && (
        <div className="bg-white dark:bg-[var(--js-panel)] rounded-2xl border border-[#C84B31] p-4 shadow-sm">
          <h3 className="font-bold text-[#C84B31] flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4" /> Low stock ({data.low_stock.length})
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {data.low_stock.map((p) => (
              <div key={p.id} className="flex items-center justify-between p-2 rounded-lg bg-[var(--js-bg)]">
                <p className="text-sm text-[var(--js-text)] truncate">{p.name}</p>
                <span className="text-xs font-bold text-[#C84B31]">{p.stock} left</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
