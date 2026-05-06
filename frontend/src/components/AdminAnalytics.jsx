import { useEffect, useState } from "react";
import api, { formatUSD } from "@/lib/api";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, LineChart, Line, CartesianGrid } from "recharts";
import { ShoppingBag, DollarSign, Users, Store, TrendingUp, Clock } from "lucide-react";

const Stat = ({ icon: Icon, label, value, color = "#C84B31" }) => (
  <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5">
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: color + "1A", color }}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--js-text-secondary)]">{label}</p>
        <p className="font-display font-bold text-xl text-[var(--js-text)]">{value}</p>
      </div>
    </div>
  </div>
);

export default function AdminAnalytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/admin/analytics");
        setData(data);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return <div className="py-12 text-center text-sm text-[var(--js-text-secondary)]">Loading analytics…</div>;
  }
  if (!data) {
    return <div className="py-12 text-center text-sm text-[var(--js-text-secondary)]">Could not load analytics.</div>;
  }

  const t = data.totals || {};
  const shortDay = (s) => (s ? s.slice(5) : ""); // MM-DD
  const ordersSeries = (data.orders_per_day || []).map((d) => ({ ...d, day: shortDay(d.day) }));
  const usersSeries = (data.users_per_day || []).map((d) => ({ ...d, day: shortDay(d.day) }));

  return (
    <div className="space-y-8" data-testid="admin-analytics">
      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat icon={ShoppingBag} label="Total Orders" value={t.orders ?? 0} color="#C84B31" />
        <Stat icon={DollarSign} label="Total Revenue" value={formatUSD(t.revenue_usd ?? 0)} color="#2D6A4F" />
        <Stat icon={Clock} label="Pending Orders" value={t.pending_orders ?? 0} color="#E9C46A" />
        <Stat icon={TrendingUp} label="Delivered Orders" value={t.delivered_orders ?? 0} color="#0E1A2B" />
        <Stat icon={Users} label="Customers" value={t.customers ?? 0} color="#4E598C" />
        <Stat icon={Store} label="Sellers" value={t.sellers ?? 0} color="#8B5CF6" />
        <Stat icon={Store} label="Active Shops" value={t.shops ?? 0} color="#C84B31" />
        <Stat icon={ShoppingBag} label="Products" value={t.products ?? 0} color="#0E1A2B" />
      </div>

      {/* Charts row */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5">
          <p className="font-display font-bold text-[var(--js-text)] mb-4">Orders — last 30 days</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={ordersSeries}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E0D6" />
                <XAxis dataKey="day" stroke="#808080" fontSize={11} />
                <YAxis stroke="#808080" fontSize={11} allowDecimals={false} />
                <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="orders" fill="#C84B31" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5">
          <p className="font-display font-bold text-[var(--js-text)] mb-4">New users — last 30 days</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={usersSeries}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E0D6" />
                <XAxis dataKey="day" stroke="#808080" fontSize={11} />
                <YAxis stroke="#808080" fontSize={11} allowDecimals={false} />
                <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                <Line type="monotone" dataKey="users" stroke="#2D6A4F" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Top sellers */}
      <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5">
        <p className="font-display font-bold text-[var(--js-text)] mb-4">Top sellers by revenue</p>
        {(data.top_sellers || []).length === 0 ? (
          <p className="text-sm text-[var(--js-text-secondary)]">No sales yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] uppercase tracking-wider text-[var(--js-text-secondary)] border-b border-[var(--js-border)]">
                  <th className="py-2 pr-2 font-semibold">#</th>
                  <th className="py-2 pr-2 font-semibold">Seller</th>
                  <th className="py-2 pr-2 font-semibold text-right">Revenue</th>
                </tr>
              </thead>
              <tbody>
                {data.top_sellers.map((s, i) => (
                  <tr key={s.seller_id} className="border-b border-[var(--js-border)] last:border-0">
                    <td className="py-3 pr-2 font-bold text-[var(--js-text-secondary)]">{i + 1}</td>
                    <td className="py-3 pr-2 font-semibold text-[var(--js-text)]">{s.name}</td>
                    <td className="py-3 pr-2 text-right font-bold">{formatUSD(s.revenue_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
