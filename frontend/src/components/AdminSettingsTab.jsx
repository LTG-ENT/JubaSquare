import { useEffect, useState } from "react";
import api, { formatDetail } from "@/lib/api";
import { Percent, Save, RotateCcw, Info, Store, ArrowRight, Users, Search, Filter, MoreVertical, Edit, Key, Mail, Power, Trash2, Eye, X, CheckCircle, XCircle, ShoppingBag, DollarSign, Plus } from "lucide-react";
import { toast } from "sonner";

/**
 * AdminSettingsTab
 *
 * Central place for global platform settings including:
 * - Commission rates
 * - User management
 */
export default function AdminSettingsTab({ onGoToShop }) {
  const [globalRate, setGlobalRate] = useState(0.10);
  const [rateDraft, setRateDraft] = useState("10");
  const [shops, setShops] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [s, sh] = await Promise.all([
        api.get("/admin/settings"),
        api.get("/shops?limit=200"),
      ]);
      const g = Number(s.data.commission_rate ?? 0.10);
      setGlobalRate(g);
      setRateDraft((g * 100).toFixed(1).replace(/\.0$/, ""));
      setShops(sh.data || []);
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const parsedDraftRate = (() => {
    const pct = parseFloat(rateDraft);
    if (Number.isNaN(pct)) return null;
    if (pct < 0 || pct > 100) return null;
    return Math.round(pct * 10) / 1000;
  })();

  const dirty = parsedDraftRate !== null && Math.abs(parsedDraftRate - globalRate) > 1e-6;

  const saveGlobalRate = async () => {
    if (parsedDraftRate === null) {
      toast.error("Enter a valid percentage between 0 and 100");
      return;
    }
    const confirmMsg = `Set the global commission rate to ${(parsedDraftRate * 100).toFixed(1)}%?\n\nThis will be applied to all shops that do NOT have their own custom rate. Pending/unpaid invoices will be regenerated with the new rate.`;
    if (!window.confirm(confirmMsg)) return;
    setSaving(true);
    try {
      await api.put("/admin/settings", { commission_rate: parsedDraftRate });
      toast.success(`Global commission rate set to ${(parsedDraftRate * 100).toFixed(1)}%`);
      try {
        await api.post("/admin/invoices/generate");
      } catch { /* non-critical */ }
      await load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const resetShopCommission = async (shop) => {
    if (!window.confirm(`Remove the custom commission on ${shop.name}? It will fall back to the global rate (${(globalRate * 100).toFixed(1)}%).`)) return;
    try {
      await api.put(`/admin/shops/${shop.id}/commission`, { commission_rate: null });
      toast.success(`${shop.name} now uses the global rate`);
      await load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed");
    }
  };

  if (loading) {
    return <p className="text-sm text-[var(--js-text-secondary)]">Loading settings…</p>;
  }

  const overrides = shops.filter((s) => s.commission_rate != null);
  const noOverrides = shops.filter((s) => s.commission_rate == null);

  return (
    <div className="space-y-6">
      {/* Global commission card */}
      <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5 sm:p-6">
        <div className="flex items-start gap-4">
          <div className="w-11 h-11 rounded-xl bg-[#C84B31]/10 text-[#C84B31] flex items-center justify-center flex-shrink-0">
            <Percent className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Platform</p>
            <h2 className="font-display font-bold text-lg text-[var(--js-text)] mt-0.5">Global commission rate</h2>
            <p className="text-xs text-[var(--js-text-secondary)] mt-1 leading-relaxed">
              This percentage is charged on every sale as JubaSquare's commission. It applies to <strong>every shop</strong> unless that shop has a custom rate set (see below).
            </p>

            <div className="mt-4 flex items-stretch gap-2 flex-wrap">
              <div className="relative">
                <input
                  type="number"
                  value={rateDraft}
                  onChange={(e) => setRateDraft(e.target.value)}
                  min="0"
                  max="100"
                  step="0.1"
                  data-testid="settings-global-rate-input"
                  className="w-40 bg-[var(--js-bg)] border border-[var(--js-border)] rounded-xl pl-3 pr-8 py-2.5 text-lg font-bold focus:outline-none focus:border-[#C84B31]"
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--js-text-secondary)] font-bold">%</span>
              </div>
              <button
                type="button"
                onClick={saveGlobalRate}
                disabled={!dirty || saving}
                data-testid="settings-save-global-rate"
                className="inline-flex items-center gap-1.5 text-sm font-bold px-5 py-2.5 rounded-xl bg-[#C84B31] hover:bg-[#A83A23] text-white disabled:bg-[#A3A39E]"
              >
                <Save className="w-4 h-4" /> {saving ? "Saving…" : "Save rate"}
              </button>
              {dirty && (
                <button
                  type="button"
                  onClick={() => setRateDraft((globalRate * 100).toFixed(1).replace(/\.0$/, ""))}
                  data-testid="settings-reset-global-rate"
                  className="inline-flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-xl border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#1A1A1A]"
                >
                  <RotateCcw className="w-3.5 h-3.5" /> Discard
                </button>
              )}
            </div>

            <div className="mt-3 text-xs text-[var(--js-text-secondary)]">
              <span className="font-semibold text-[var(--js-text)]">Currently saved:</span>{" "}
              <span data-testid="settings-global-rate-current" className="font-bold text-[#C84B31]">{(globalRate * 100).toFixed(1)}%</span>
              {parsedDraftRate === null && rateDraft !== "" && (
                <span className="ml-3 text-[#D90429] font-semibold">⚠ Must be between 0 and 100</span>
              )}
            </div>

            <div className="mt-4 flex gap-2 items-start p-3 bg-[#FFF7E0] border border-[#E9C46A]/40 rounded-xl text-xs text-[#7A5C12]">
              <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <div>
                <strong>How commission is applied:</strong> when invoices are generated, each shop's effective rate is
                <code className="mx-1 px-1.5 py-0.5 bg-white rounded">shop.commission_rate ?? global_rate</code>.
                Changing the global rate triggers invoice regeneration so pending invoices pick up the new value.
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Per-shop overrides */}
      <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
          <div>
            <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Shop overrides</p>
            <h2 className="font-display font-bold text-lg text-[var(--js-text)] mt-0.5">Shops with a custom rate</h2>
            <p className="text-xs text-[var(--js-text-secondary)] mt-1">
              {overrides.length === 0
                ? `All ${shops.length} shop${shops.length === 1 ? "" : "s"} currently use the global rate.`
                : `${overrides.length} of ${shops.length} shops have a custom rate. The remaining ${noOverrides.length} use the global rate.`}
            </p>
          </div>
        </div>

        {overrides.length === 0 ? (
          <div className="p-6 bg-[var(--js-bg)] rounded-xl border border-[var(--js-border)] text-sm text-[var(--js-text-secondary)] text-center" data-testid="settings-no-overrides">
            No shop overrides yet. To set a custom rate for a shop, go to the <strong>Shops</strong> tab and open a shop.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="settings-overrides-table">
              <thead className="text-xs uppercase tracking-wider text-[var(--js-text-secondary)]">
                <tr>
                  <th className="text-left py-2 font-bold">Shop</th>
                  <th className="text-left py-2 font-bold">Custom rate</th>
                  <th className="text-left py-2 font-bold hidden sm:table-cell">Difference vs global</th>
                  <th className="text-right py-2 font-bold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {overrides.map((s) => {
                  const rate = Number(s.commission_rate);
                  const diff = rate - globalRate;
                  return (
                    <tr key={s.id} className="border-t border-[var(--js-border)]" data-testid={`settings-override-row-${s.id}`}>
                      <td className="py-3">
                        <div className="flex items-center gap-2">
                          <Store className="w-4 h-4 text-[var(--js-text-secondary)]" />
                          <span className="font-semibold text-[var(--js-text)]">{s.name}</span>
                        </div>
                      </td>
                      <td className="py-3">
                        <span className="font-bold text-[#C84B31]">{(rate * 100).toFixed(1)}%</span>
                      </td>
                      <td className="py-3 hidden sm:table-cell text-xs">
                        {diff === 0 ? (
                          <span className="text-[var(--js-text-secondary)]">= global</span>
                        ) : diff > 0 ? (
                          <span className="text-[#2D6A4F] font-semibold">+{(diff * 100).toFixed(1)}% higher</span>
                        ) : (
                          <span className="text-[#D90429] font-semibold">{(diff * 100).toFixed(1)}% lower</span>
                        )}
                      </td>
                      <td className="py-3 text-right">
                        <button
                          type="button"
                          onClick={() => resetShopCommission(s)}
                          data-testid={`settings-reset-shop-${s.id}`}
                          className="inline-flex items-center gap-1 text-[11px] font-bold px-3 py-1.5 rounded-full border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#C84B31] hover:text-[#C84B31]"
                        >
                          <RotateCcw className="w-3 h-3" /> Reset to global
                        </button>
                        {onGoToShop && (
                          <button
                            type="button"
                            onClick={() => onGoToShop(s.id)}
                            data-testid={`settings-edit-shop-${s.id}`}
                            className="ml-2 inline-flex items-center gap-1 text-[11px] font-bold px-3 py-1.5 rounded-full bg-[#1A1A1A] text-white hover:bg-[#C84B31]"
                          >
                            Edit <ArrowRight className="w-3 h-3" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <p className="text-[11px] text-[var(--js-text-secondary)] mt-3">
          To set a custom rate on a shop, open its detail panel from the <strong>Shops</strong> tab.
        </p>
      </div>

      {/* User Management Section */}
      <UserManagement />
    </div>
  );
}

/**
 * UserManagement Component
 * Comprehensive user management section with filters, search, and actions
 */
function UserManagement() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterRole, setFilterRole] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterVerified, setFilterVerified] = useState("");
  const [search, setSearch] = useState("");
  const [selectedUser, setSelectedUser] = useState(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedUserIds, setSelectedUserIds] = useState([]);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterRole) params.append("role", filterRole);
      if (filterStatus) params.append("is_active", filterStatus === "active" ? "true" : "false");
      if (filterVerified) params.append("email_verified", filterVerified === "verified" ? "true" : "false");
      if (search) params.append("search", search);
      params.append("limit", "200");
      
      const { data } = await api.get(`/admin/users?${params.toString()}`);
      setUsers(data || []);
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadUsers(); }, [filterRole, filterStatus, filterVerified]);

  const handleSearch = () => {
    loadUsers();
  };

  const toggleUserStatus = async (user) => {
    const newStatus = !user.is_active;
    const action = newStatus ? "enable" : "disable";
    if (!window.confirm(`${action.charAt(0).toUpperCase() + action.slice(1)} ${user.name}'s account?`)) return;
    
    try {
      await api.put(`/admin/users/${user.id}/status`, { is_active: newStatus });
      toast.success(`User ${action}d successfully`);
      loadUsers();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || `Failed to ${action} user`);
    }
  };

  const deleteUser = async (user) => {
    if (!window.confirm(`Delete ${user.name}'s account? This action cannot be undone.\n\nAll their data (shops, products, orders history) will be removed.`)) return;
    
    try {
      await api.delete(`/admin/users/${user.id}`);
      toast.success("User deleted successfully");
      loadUsers();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to delete user");
    }
  };


  const bulkDeleteUsers = async () => {
    if (selectedUserIds.length === 0) {
      toast.error("No users selected");
      return;
    }
    
    const confirmMsg = `Delete ${selectedUserIds.length} selected user(s)? This action cannot be undone.\n\nAll their data (shops, products, orders) will be removed.`;
    if (!window.confirm(confirmMsg)) return;
    
    try {
      const { data } = await api.post("/admin/users/bulk-delete", { user_ids: selectedUserIds });
      toast.success(data.message || `${selectedUserIds.length} user(s) deleted successfully`);
      setSelectedUserIds([]);
      loadUsers();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to delete users");
    }
  };

  const toggleSelectUser = (userId) => {
    setSelectedUserIds(prev => 
      prev.includes(userId) 
        ? prev.filter(id => id !== userId)
        : [...prev, userId]
    );
  };

  const toggleSelectAll = () => {
    if (selectedUserIds.length === users.length) {
      setSelectedUserIds([]);
    } else {
      setSelectedUserIds(users.map(u => u.id));
    }
  };


  const counts = {
    total: users.length,
    customers: users.filter(u => u.role === "customer").length,
    sellers: users.filter(u => u.role === "seller").length,
    active: users.filter(u => u.is_active !== false).length,
    disabled: users.filter(u => u.is_active === false).length,
  };

  return (
    <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5 sm:p-6">
      <div className="flex items-start gap-4 mb-6">
        <div className="w-11 h-11 rounded-xl bg-[#2D6A4F]/10 text-[#2D6A4F] flex items-center justify-center flex-shrink-0">
          <Users className="w-5 h-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Platform</p>
              <h2 className="font-display font-bold text-lg text-[var(--js-text)] mt-0.5">User Management</h2>
              <p className="text-xs text-[var(--js-text-secondary)] mt-1">
                View and manage all user accounts. {counts.total} total users ({counts.customers} customers, {counts.sellers} sellers)
              </p>
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#2D6A4F] hover:bg-[#1B4332] text-white text-sm font-bold rounded-xl transition flex-shrink-0"
            >
              <Plus className="w-4 h-4" /> Create User
            </button>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--js-text-secondary)]" />
          <input
            type="text"
            placeholder="Search by name or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="w-full pl-10 pr-3 py-2 text-sm border border-[var(--js-border)] rounded-xl focus:outline-none focus:border-[#C84B31]"
          />
        </div>
        
        <select
          value={filterRole}
          onChange={(e) => setFilterRole(e.target.value)}
          className="px-3 py-2 text-sm border border-[var(--js-border)] rounded-xl focus:outline-none focus:border-[#C84B31]"
        >
          <option value="">All roles</option>
          <option value="customer">Customers</option>
          <option value="seller">Sellers</option>
          <option value="admin">Admins</option>
        </select>

        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-3 py-2 text-sm border border-[var(--js-border)] rounded-xl focus:outline-none focus:border-[#C84B31]"
        >
          <option value="">All status</option>
          <option value="active">Active</option>
          <option value="disabled">Disabled</option>
        </select>

        <select
          value={filterVerified}
          onChange={(e) => setFilterVerified(e.target.value)}
          className="px-3 py-2 text-sm border border-[var(--js-border)] rounded-xl focus:outline-none focus:border-[#C84B31]"
        >
          <option value="">All verified</option>
          <option value="verified">Verified</option>
          <option value="unverified">Unverified</option>
        </select>

        <button
          onClick={handleSearch}
          className="px-4 py-2 text-sm font-bold bg-[#C84B31] text-white rounded-xl hover:bg-[#A83A23]"
        >
          Search
        </button>
      </div>

      {/* Bulk Actions Bar */}
      {selectedUserIds.length > 0 && (
        <div className="mb-4 flex items-center justify-between gap-3 p-3 bg-[#2D6A4F]/10 border border-[#2D6A4F]/30 rounded-xl">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={selectedUserIds.length === users.length}
              onChange={toggleSelectAll}
              className="w-4 h-4 rounded border-[var(--js-border)] text-[#2D6A4F] focus:ring-[#2D6A4F]"
            />
            <span className="text-sm font-semibold text-[var(--js-text)]">
              {selectedUserIds.length} user(s) selected
            </span>
          </div>
          <button
            onClick={bulkDeleteUsers}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#D90429] hover:bg-[#9B2C2C] text-white text-sm font-bold rounded-xl transition"
          >
            <Trash2 className="w-4 h-4" /> Delete Selected
          </button>
        </div>
      )}

      {/* Users Table */}
      {loading ? (
        <p className="text-sm text-[var(--js-text-secondary)] py-8 text-center">Loading users...</p>
      ) : users.length === 0 ? (
        <p className="text-sm text-[var(--js-text-secondary)] py-8 text-center">No users found</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wider text-[var(--js-text-secondary)] bg-[var(--js-bg)]">
              <tr>
                <th className="text-left p-3 font-bold w-10">
                  <input
                    type="checkbox"
                    checked={selectedUserIds.length === users.length && users.length > 0}
                    onChange={toggleSelectAll}
                    className="w-4 h-4 rounded border-[var(--js-border)] text-[#2D6A4F] focus:ring-[#2D6A4F]"
                  />
                </th>
                <th className="text-left p-3 font-bold">User</th>
                <th className="text-left p-3 font-bold hidden md:table-cell">Role</th>
                <th className="text-left p-3 font-bold hidden lg:table-cell">Status</th>
                <th className="text-left p-3 font-bold hidden xl:table-cell">Stats</th>
                <th className="text-left p-3 font-bold hidden sm:table-cell">Joined</th>
                <th className="text-right p-3 font-bold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <UserRow 
                  key={user.id} 
                  user={user}
                  selected={selectedUserIds.includes(user.id)}
                  onToggleSelect={() => toggleSelectUser(user.id)}
                  onToggleStatus={toggleUserStatus}
                  onDelete={deleteUser}
                  onEdit={() => { setSelectedUser(user); setShowEditModal(true); }}
                  onPassword={() => { setSelectedUser(user); setShowPasswordModal(true); }}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modals */}
      {showEditModal && selectedUser && (
        <EditUserModal
          user={selectedUser}
          onClose={() => { setShowEditModal(false); setSelectedUser(null); }}
          onSuccess={() => { setShowEditModal(false); setSelectedUser(null); loadUsers(); }}
        />
      )}

      {showPasswordModal && selectedUser && (
        <PasswordResetModal
          user={selectedUser}
          onClose={() => { setShowPasswordModal(false); setSelectedUser(null); }}
          onSuccess={() => { setShowPasswordModal(false); setSelectedUser(null); }}
        />
      )}

      {showCreateModal && (
        <CreateUserModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => { setShowCreateModal(false); loadUsers(); }}
        />
      )}
    </div>
  );
}

function UserRow({ user, selected, onToggleSelect, onToggleStatus, onDelete, onEdit, onPassword }) {
  const [showMenu, setShowMenu] = useState(false);
  const buttonRef = useState(null);
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 });
  
  const handleMenuToggle = (e) => {
    if (!showMenu) {
      const rect = e.currentTarget.getBoundingClientRect();
      setMenuPosition({
        top: rect.bottom + window.scrollY + 4,
        left: rect.right + window.scrollX - 192, // 192px = 12rem (menu width)
      });
    }
    setShowMenu(!showMenu);
  };
  
  const formatDate = (iso) => {
    if (!iso) return "Never";
    try {
      return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch {
      return "—";
    }
  };

  const getRoleBadge = (role) => {
    const styles = {
      admin: "bg-[#9B2C2C]/10 text-[#9B2C2C]",
      seller: "bg-[#2D6A4F]/10 text-[#2D6A4F]",
      customer: "bg-[#2B6CB0]/10 text-[#2B6CB0]",
    };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${styles[role] || ""}`}>
        {role}
      </span>
    );
  };

  return (
    <tr className="border-t border-[var(--js-border)] hover:bg-[var(--js-bg)]">
      <td className="p-3 w-10">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggleSelect}
          className="w-4 h-4 rounded border-[var(--js-border)] text-[#2D6A4F] focus:ring-[#2D6A4F]"
        />
      </td>
      <td className="p-3">
        <div>
          <p className="font-semibold text-[var(--js-text)]">{user.name}</p>
          <p className="text-xs text-[var(--js-text-secondary)]">{user.email}</p>
          <div className="flex items-center gap-2 mt-1">
            {user.email_verified ? (
              <CheckCircle className="w-3 h-3 text-[#2D6A4F]" title="Email verified" />
            ) : (
              <XCircle className="w-3 h-3 text-[#E9C46A]" title="Email not verified" />
            )}
            {user.is_active === false && (
              <span className="text-[10px] font-bold text-[#D90429]">DISABLED</span>
            )}
          </div>
        </div>
      </td>
      <td className="p-3 hidden md:table-cell">{getRoleBadge(user.role)}</td>
      <td className="p-3 hidden lg:table-cell">
        {user.is_active === false ? (
          <span className="text-xs text-[#D90429] font-semibold">Disabled</span>
        ) : (
          <span className="text-xs text-[#2D6A4F] font-semibold">Active</span>
        )}
        {user.last_login && (
          <p className="text-[10px] text-[var(--js-text-secondary)] mt-0.5">
            Last: {formatDate(user.last_login)}
          </p>
        )}
      </td>
      <td className="p-3 hidden xl:table-cell text-xs">
        {user.role === "customer" && user.total_orders !== undefined && (
          <div className="flex items-center gap-1 text-[var(--js-text-secondary)]">
            <ShoppingBag className="w-3 h-3" />
            <span>{user.total_orders} orders</span>
          </div>
        )}
        {user.role === "seller" && user.total_sales !== undefined && (
          <div className="flex items-center gap-1 text-[var(--js-text-secondary)]">
            <DollarSign className="w-3 h-3" />
            <span>${user.total_sales.toFixed(2)}</span>
          </div>
        )}
      </td>
      <td className="p-3 hidden sm:table-cell text-xs text-[var(--js-text-secondary)]">
        {formatDate(user.created_at)}
      </td>
      <td className="p-3 text-right relative">
        <button
          onClick={handleMenuToggle}
          className="p-1.5 rounded-lg hover:bg-[var(--js-bg)]"
        >
          <MoreVertical className="w-4 h-4" />
        </button>
        
        {showMenu && (
          <>
            <div className="fixed inset-0 z-[100]" onClick={() => setShowMenu(false)} />
            <div 
              className="fixed bg-white border border-[var(--js-border)] rounded-xl shadow-lg z-[101] py-1 w-48"
              style={{
                top: `${menuPosition.top}px`,
                left: `${menuPosition.left}px`,
              }}
            >
              <button onClick={() => { onEdit(); setShowMenu(false); }} className="w-full px-4 py-2 text-left text-sm hover:bg-[var(--js-bg)] flex items-center gap-2">
                <Edit className="w-4 h-4" /> Edit details
              </button>
              <button onClick={() => { onPassword(); setShowMenu(false); }} className="w-full px-4 py-2 text-left text-sm hover:bg-[var(--js-bg)] flex items-center gap-2">
                <Key className="w-4 h-4" /> Reset password
              </button>
              <button onClick={() => { onToggleStatus(user); setShowMenu(false); }} className="w-full px-4 py-2 text-left text-sm hover:bg-[var(--js-bg)] flex items-center gap-2">
                <Power className="w-4 h-4" /> {user.is_active === false ? "Enable" : "Disable"} account
              </button>
              <hr className="my-1 border-[var(--js-border)]" />
              <button onClick={() => { onDelete(user); setShowMenu(false); }} className="w-full px-4 py-2 text-left text-sm hover:bg-red-50 text-[#D90429] flex items-center gap-2">
                <Trash2 className="w-4 h-4" /> Delete user
              </button>
            </div>
          </>
        )}
      </td>
    </tr>
  );
}


function CreateUserModal({ onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    password: "",
    phone: "",
    role: "customer",
    email_verified: true,
  });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (formData.password.length < 6) {
      toast.error("Password must be at least 6 characters");
      return;
    }
    setSaving(true);
    try {
      await api.post("/admin/users", formData);
      toast.success("User created successfully");
      onSuccess();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to create user");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-bold text-xl">Create New User</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-[var(--js-bg)]">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-semibold mb-1">Name *</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-xl focus:outline-none focus:border-[#C84B31]"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-semibold mb-1">Email *</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-xl focus:outline-none focus:border-[#C84B31]"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-semibold mb-1">Password *</label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              placeholder="Minimum 6 characters"
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-xl focus:outline-none focus:border-[#C84B31]"
              required
            />
            <p className="text-xs text-[var(--js-text-secondary)] mt-1">User will be able to login with this password</p>
          </div>

          <div>
            <label className="block text-sm font-semibold mb-1">Phone</label>
            <input
              type="text"
              value={formData.phone}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-xl focus:outline-none focus:border-[#C84B31]"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold mb-1">Role *</label>
            <select
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-xl focus:outline-none focus:border-[#C84B31]"
            >
              <option value="customer">Customer</option>
              <option value="seller">Seller</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="email_verified"
              checked={formData.email_verified}
              onChange={(e) => setFormData({ ...formData, email_verified: e.target.checked })}
              className="w-4 h-4 rounded border-[var(--js-border)] text-[#C84B31] focus:ring-[#C84B31]"
            />
            <label htmlFor="email_verified" className="text-sm text-[var(--js-text)]">
              Email verified (user can login immediately)
            </label>
          </div>

          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-[var(--js-border)] rounded-xl font-semibold hover:bg-[var(--js-bg)]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 px-4 py-2 bg-[#2D6A4F] text-white rounded-xl font-semibold hover:bg-[#1B4332] disabled:bg-[#A3A39E]"
            >
              {saving ? "Creating..." : "Create User"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}


function EditUserModal({ user, onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    name: user.name || "",
    email: user.email || "",
    phone: user.phone || "",
    role: user.role || "customer",
  });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.put(`/admin/users/${user.id}`, formData);
      toast.success("User updated successfully");
      onSuccess();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to update user");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-bold text-xl">Edit User</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-[var(--js-bg)]">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-semibold mb-1">Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-xl focus:outline-none focus:border-[#C84B31]"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-semibold mb-1">Email</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-xl focus:outline-none focus:border-[#C84B31]"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-semibold mb-1">Phone</label>
            <input
              type="text"
              value={formData.phone}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-xl focus:outline-none focus:border-[#C84B31]"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold mb-1">Role</label>
            <select
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-xl focus:outline-none focus:border-[#C84B31]"
            >
              <option value="customer">Customer</option>
              <option value="seller">Seller</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-[var(--js-border)] rounded-xl font-semibold hover:bg-[var(--js-bg)]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 px-4 py-2 bg-[#C84B31] text-white rounded-xl font-semibold hover:bg-[#A83A23] disabled:bg-[#A3A39E]"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function PasswordResetModal({ user, onClose, onSuccess }) {
  const [mode, setMode] = useState("direct"); // direct, email, temp
  const [newPassword, setNewPassword] = useState("");
  const [tempPassword, setTempPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleDirectReset = async () => {
    if (!newPassword || newPassword.length < 6) {
      toast.error("Password must be at least 6 characters");
      return;
    }
    setLoading(true);
    try {
      await api.post(`/admin/users/${user.id}/reset-password`, { new_password: newPassword });
      toast.success("Password updated successfully");
      onSuccess();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to reset password");
    } finally {
      setLoading(false);
    }
  };

  const handleSendEmail = async () => {
    setLoading(true);
    try {
      const { data } = await api.post(`/admin/users/${user.id}/send-reset-email`);
      toast.success(data.message || "Password reset email sent");
      onSuccess();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to send email");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateTemp = async () => {
    setLoading(true);
    try {
      const { data } = await api.post(`/admin/users/${user.id}/generate-temp-password`);
      setTempPassword(data.temp_password || "");
      toast.success("Temporary password generated");
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail) || "Failed to generate password");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-bold text-xl">Reset Password</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-[var(--js-bg)]">
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-sm text-[var(--js-text-secondary)] mb-4">
          Reset password for <strong>{user.name}</strong> ({user.email})
        </p>

        {/* Tabs */}
        <div className="flex gap-2 mb-4 border-b border-[var(--js-border)]">
          <button
            onClick={() => setMode("direct")}
            className={`px-4 py-2 text-sm font-semibold border-b-2 transition ${mode === "direct" ? "border-[#C84B31] text-[#C84B31]" : "border-transparent text-[var(--js-text-secondary)]"}`}
          >
            Set Password
          </button>
          <button
            onClick={() => setMode("email")}
            className={`px-4 py-2 text-sm font-semibold border-b-2 transition ${mode === "email" ? "border-[#C84B31] text-[#C84B31]" : "border-transparent text-[var(--js-text-secondary)]"}`}
          >
            Send Email
          </button>
          <button
            onClick={() => setMode("temp")}
            className={`px-4 py-2 text-sm font-semibold border-b-2 transition ${mode === "temp" ? "border-[#C84B31] text-[#C84B31]" : "border-transparent text-[var(--js-text-secondary)]"}`}
          >
            Generate Temp
          </button>
        </div>

        {/* Content */}
        <div className="space-y-4">
          {mode === "direct" && (
            <>
              <div>
                <label className="block text-sm font-semibold mb-1">New Password</label>
                <input
                  type="text"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new password (min 6 characters)"
                  className="w-full px-3 py-2 border border-[var(--js-border)] rounded-xl focus:outline-none focus:border-[#C84B31]"
                />
              </div>
              <button
                onClick={handleDirectReset}
                disabled={loading}
                className="w-full px-4 py-2 bg-[#C84B31] text-white rounded-xl font-semibold hover:bg-[#A83A23] disabled:bg-[#A3A39E]"
              >
                {loading ? "Setting..." : "Set Password"}
              </button>
            </>
          )}

          {mode === "email" && (
            <>
              <p className="text-sm text-[var(--js-text-secondary)]">
                Send a password reset link to <strong>{user.email}</strong>. User will receive an email with a link to set their own password.
              </p>
              <button
                onClick={handleSendEmail}
                disabled={loading}
                className="w-full px-4 py-2 bg-[#C84B31] text-white rounded-xl font-semibold hover:bg-[#A83A23] disabled:bg-[#A3A39E]"
              >
                {loading ? "Sending..." : "Send Reset Email"}
              </button>
            </>
          )}

          {mode === "temp" && (
            <>
              <p className="text-sm text-[var(--js-text-secondary)]">
                Generate a random temporary password. User will need to change it on their first login.
              </p>
              {tempPassword ? (
                <div className="p-4 bg-[#FFF7E0] border border-[#E9C46A]/40 rounded-xl">
                  <p className="text-xs font-semibold mb-2">Temporary Password:</p>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 px-3 py-2 bg-white rounded text-sm font-mono">{tempPassword}</code>
                    <button
                      onClick={() => copyToClipboard(tempPassword)}
                      className="px-3 py-2 bg-[#C84B31] text-white rounded-lg text-xs font-semibold hover:bg-[#A83A23]"
                    >
                      Copy
                    </button>
                  </div>
                  <p className="text-xs text-[#7A5C12] mt-2">
                    Share this password with the user. They must change it on their next login.
                  </p>
                </div>
              ) : (
                <button
                  onClick={handleGenerateTemp}
                  disabled={loading}
                  className="w-full px-4 py-2 bg-[#C84B31] text-white rounded-xl font-semibold hover:bg-[#A83A23] disabled:bg-[#A3A39E]"
                >
                  {loading ? "Generating..." : "Generate Temporary Password"}
                </button>
              )}
            </>
          )}
        </div>

        <div className="mt-4 pt-4 border-t border-[var(--js-border)]">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 border border-[var(--js-border)] rounded-xl font-semibold hover:bg-[var(--js-bg)]"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
