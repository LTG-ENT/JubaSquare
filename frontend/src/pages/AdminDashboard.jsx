import { useEffect, useState } from "react";
import api, { formatUSD, formatDetail } from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Store, Mail, ShoppingBag, CheckCircle2, XCircle, Clock, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

const TABS = [
  { id: "shops", label: "Shops", icon: Store },
  { id: "emails", label: "Blocked Emails", icon: Mail },
  { id: "orders", label: "All Orders", icon: ShoppingBag },
];

export default function AdminDashboard() {
  const [tab, setTab] = useState("shops");

  return (
    <div className="min-h-screen flex flex-col bg-[#F9F9F6]">
      <Header />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-1">
        <p className="text-[10px] uppercase tracking-[0.2em] text-[#5C5C5C] font-bold mb-2">Admin Dashboard</p>
        <h1 className="font-display font-bold text-3xl sm:text-4xl text-[#1A1A1A]">Platform control</h1>

        <div className="mt-8 flex flex-wrap gap-2 border-b border-[#E2E2D9]">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                data-testid={`admin-tab-${t.id}`}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 transition ${
                  tab === t.id
                    ? "border-[#C84B31] text-[#C84B31]"
                    : "border-transparent text-[#5C5C5C] hover:text-[#1A1A1A]"
                }`}
              >
                <Icon className="w-4 h-4" /> {t.label}
              </button>
            );
          })}
        </div>

        <div className="mt-8">
          {tab === "shops" && <AdminShopsTab />}
          {tab === "emails" && <AdminEmailsTab />}
          {tab === "orders" && <AdminOrdersTab />}
        </div>
      </div>
      <Footer />
    </div>
  );
}

function AdminShopsTab() {
  const [shops, setShops] = useState([]);
  const load = () => api.get("/shops").then((r) => setShops(r.data));
  useEffect(() => { load(); }, []);

  const verify = async (id) => { await api.put(`/admin/shops/${id}/verify`); toast.success("Verified"); load(); };
  const reject = async (id) => { await api.put(`/admin/shops/${id}/reject`); toast.success("Rejected"); load(); };

  const counts = {
    Verified: shops.filter((s) => s.verification === "Verified").length,
    Pending: shops.filter((s) => s.verification === "Pending").length,
    Rejected: shops.filter((s) => s.verification === "Rejected").length,
  };

  return (
    <div>
      <div className="grid grid-cols-3 gap-3 mb-6">
        <Stat label="Verified" value={counts.Verified} color="#2D6A4F" />
        <Stat label="Pending" value={counts.Pending} color="#E9C46A" />
        <Stat label="Rejected" value={counts.Rejected} color="#D90429" />
      </div>

      <div className="bg-white border border-[#E2E2D9] rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F9F9F6] text-[#5C5C5C] text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left p-4 font-bold">Shop</th>
                <th className="text-left p-4 font-bold hidden md:table-cell">Category</th>
                <th className="text-left p-4 font-bold hidden lg:table-cell">Area</th>
                <th className="text-left p-4 font-bold">Status</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {shops.map((s) => (
                <tr key={s.id} className="border-t border-[#E2E2D9]" data-testid={`admin-shop-row-${s.id}`}>
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <img src={s.image_url} alt="" className="w-10 h-10 rounded-lg object-cover" />
                      <p className="font-semibold text-[#1A1A1A]">{s.name}</p>
                    </div>
                  </td>
                  <td className="p-4 text-[#5C5C5C] hidden md:table-cell">{s.category}</td>
                  <td className="p-4 text-[#5C5C5C] hidden lg:table-cell">{s.area}</td>
                  <td className="p-4">
                    {s.verification === "Verified" && <span className="inline-flex items-center gap-1 bg-[#2D6A4F]/10 text-[#2D6A4F] text-xs font-bold px-2 py-1 rounded-full"><CheckCircle2 className="w-3 h-3" /> Verified</span>}
                    {s.verification === "Pending" && <span className="inline-flex items-center gap-1 bg-[#E9C46A]/30 text-[#1A1A1A] text-xs font-bold px-2 py-1 rounded-full"><Clock className="w-3 h-3" /> Pending</span>}
                    {s.verification === "Rejected" && <span className="inline-flex items-center gap-1 bg-[#D90429]/10 text-[#D90429] text-xs font-bold px-2 py-1 rounded-full"><XCircle className="w-3 h-3" /> Rejected</span>}
                  </td>
                  <td className="p-4 text-right">
                    <div className="inline-flex gap-2">
                      <button onClick={() => verify(s.id)} data-testid={`verify-shop-${s.id}`} className="text-xs font-semibold bg-[#2D6A4F] hover:bg-[#1B4332] text-white px-3 py-1.5 rounded-full">Verify</button>
                      <button onClick={() => reject(s.id)} data-testid={`reject-shop-${s.id}`} className="text-xs font-semibold bg-[#D90429]/10 text-[#D90429] hover:bg-[#D90429] hover:text-white px-3 py-1.5 rounded-full transition">Reject</button>
                    </div>
                  </td>
                </tr>
              ))}
              {shops.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-[#5C5C5C]">No shops.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function AdminEmailsTab() {
  const [list, setList] = useState([]);
  const [email, setEmail] = useState("");

  const load = () => api.get("/admin/blocked-emails").then((r) => setList(r.data));
  useEffect(() => { load(); }, []);

  const block = async (e) => {
    e.preventDefault();
    try {
      await api.post("/admin/block-email", { email });
      toast.success("Email blocked");
      setEmail("");
      load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail));
    }
  };

  const unblock = async (em) => {
    await api.delete(`/admin/block-email/${encodeURIComponent(em)}`);
    toast.success("Unblocked");
    load();
  };

  return (
    <div className="max-w-2xl">
      <form onSubmit={block} className="bg-white border border-[#E2E2D9] rounded-3xl p-6 mb-6 flex gap-3">
        <input
          type="email"
          required
          data-testid="block-email-input"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="user@example.com"
          className="js-input flex-1"
        />
        <button type="submit" data-testid="block-email-btn" className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-5 py-2.5 rounded-full">
          <Plus className="w-4 h-4" /> Block
        </button>
      </form>

      <div className="bg-white border border-[#E2E2D9] rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-[#E2E2D9] bg-[#F9F9F6]">
          <p className="text-xs uppercase tracking-wider text-[#5C5C5C] font-bold">Blocked emails ({list.length})</p>
        </div>
        {list.length === 0 ? (
          <p className="p-8 text-center text-[#5C5C5C]">No blocked emails.</p>
        ) : (
          <ul className="divide-y divide-[#E2E2D9]">
            {list.map((b) => (
              <li key={b.email} className="flex items-center justify-between p-4" data-testid={`blocked-${b.email}`}>
                <div>
                  <p className="font-semibold text-[#1A1A1A]">{b.email}</p>
                  <p className="text-xs text-[#5C5C5C]">Blocked {new Date(b.blocked_at).toLocaleDateString()}</p>
                </div>
                <button
                  onClick={() => unblock(b.email)}
                  data-testid={`unblock-${b.email}`}
                  className="text-xs font-semibold bg-[#F2EBE5] hover:bg-[#E2E2D9] text-[#1A1A1A] px-3 py-1.5 rounded-full inline-flex items-center gap-1"
                >
                  <Trash2 className="w-3 h-3" /> Unblock
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function AdminOrdersTab() {
  const [orders, setOrders] = useState([]);
  const load = () => api.get("/orders").then((r) => setOrders(r.data));
  useEffect(() => { load(); }, []);

  const updateStatus = async (id, status) => {
    await api.put(`/orders/${id}/status`, { status });
    toast.success("Status updated");
    load();
  };

  const total = orders.reduce((s, o) => s + (o.subtotal_usd || 0), 0);

  return (
    <div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Stat label="Total Orders" value={orders.length} color="#1A1A1A" />
        <Stat label="Pending" value={orders.filter((o) => o.status === "Pending").length} color="#E9C46A" />
        <Stat label="In Progress" value={orders.filter((o) => o.status === "In Progress").length} color="#2A9D8F" />
        <Stat label="Revenue" value={formatUSD(total)} color="#C84B31" />
      </div>

      <div className="bg-white border border-[#E2E2D9] rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F9F9F6] text-[#5C5C5C] text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left p-4 font-bold">Order</th>
                <th className="text-left p-4 font-bold hidden sm:table-cell">Customer</th>
                <th className="text-left p-4 font-bold hidden md:table-cell">Type</th>
                <th className="text-left p-4 font-bold">Total</th>
                <th className="text-left p-4 font-bold">Status</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id} className="border-t border-[#E2E2D9]" data-testid={`admin-order-${o.id}`}>
                  <td className="p-4">
                    <p className="font-semibold text-[#1A1A1A]">#{o.id.slice(0, 8).toUpperCase()}</p>
                    <p className="text-xs text-[#5C5C5C]">{new Date(o.created_at).toLocaleDateString()}</p>
                  </td>
                  <td className="p-4 hidden sm:table-cell">
                    <p className="font-semibold">{o.customer_name}</p>
                    <p className="text-xs text-[#5C5C5C]">{o.area}</p>
                  </td>
                  <td className="p-4 hidden md:table-cell text-[#5C5C5C] capitalize">{o.order_kind}</td>
                  <td className="p-4 font-bold">{formatUSD(o.subtotal_usd)}</td>
                  <td className="p-4">
                    <select
                      value={o.status}
                      onChange={(e) => updateStatus(o.id, e.target.value)}
                      data-testid={`admin-order-status-${o.id}`}
                      className="bg-white border border-[#E2E2D9] rounded-full px-3 py-1.5 text-xs font-semibold focus:border-[#C84B31] focus:outline-none"
                    >
                      <option>Pending</option>
                      <option>In Progress</option>
                      <option>Delivered</option>
                    </select>
                  </td>
                </tr>
              ))}
              {orders.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-[#5C5C5C]">No orders.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div className="bg-white border border-[#E2E2D9] rounded-2xl p-4">
      <p className="text-[10px] uppercase tracking-[0.18em] text-[#5C5C5C] font-bold">{label}</p>
      <p className="font-display font-bold text-2xl mt-1" style={{ color }}>{value}</p>
    </div>
  );
}
