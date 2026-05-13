import { useState, useEffect } from "react";
import api, { formatUSD, formatDetail } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Edit2, Trash2, Search, MapPin, DollarSign, X, Check, AlertCircle } from "lucide-react";

export default function AdminDeliveryPricingTab() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [defaultFee, setDefaultFee] = useState(2.0);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingRule, setEditingRule] = useState(null);

  const loadRules = async () => {
    setLoading(true);
    try {
      const [rulesRes, defaultRes] = await Promise.all([
        api.get("/admin/delivery-pricing-rules"),
        api.get("/admin/delivery-pricing-rules/default-fee"),
      ]);
      setRules(rulesRes.data || []);
      setDefaultFee(defaultRes.data?.default_delivery_fee_usd || 2.0);
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Failed to load pricing rules");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRules();
  }, []);

  const handleSaveDefaultFee = async () => {
    try {
      await api.post("/admin/delivery-pricing-rules/default-fee", { default_delivery_fee_usd: defaultFee });
      toast.success("Default delivery fee updated");
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Failed to update default fee");
    }
  };

  const handleDeleteRule = async (ruleId) => {
    if (!confirm("Delete this delivery pricing rule?")) return;
    try {
      await api.delete(`/admin/delivery-pricing-rules/${ruleId}`);
      toast.success("Rule deleted");
      loadRules();
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Failed to delete rule");
    }
  };

  const filteredRules = rules.filter(
    (r) =>
      r.pickup_area?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.delivery_area?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.shop_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.restaurant_id?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-bold text-2xl text-[var(--js-text)]">Delivery Pricing Rules</h2>
          <p className="text-sm text-[var(--js-text-secondary)] mt-1">
            Control delivery fees based on pickup and delivery areas
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="bg-[#C84B31] hover:bg-[#A63C26] text-white font-semibold px-4 py-2 rounded-lg flex items-center gap-2 transition"
        >
          <Plus className="w-4 h-4" /> Add Rule
        </button>
      </div>

      {/* Default Fee */}
      <div className="bg-[#E9C46A]/10 border-2 border-[#E9C46A] rounded-xl p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-[#E9C46A] rounded-full p-2">
              <DollarSign className="w-5 h-5 text-[#1A1A1A]" />
            </div>
            <div>
              <p className="font-bold text-[var(--js-text)]">Default Delivery Fee</p>
              <p className="text-xs text-[var(--js-text-secondary)]">
                Used when no specific rule matches
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="number"
              step="0.01"
              min="0"
              value={defaultFee}
              onChange={(e) => setDefaultFee(parseFloat(e.target.value) || 0)}
              className="w-24 px-3 py-2 border border-[var(--js-border)] rounded-lg text-right"
            />
            <button
              onClick={handleSaveDefaultFee}
              className="bg-[#2A9D8F] hover:bg-[#238276] text-white px-4 py-2 rounded-lg transition"
            >
              Save
            </button>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--js-text-secondary)]" />
        <input
          type="text"
          placeholder="Search by pickup area, delivery area, or shop/restaurant..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-[var(--js-border)] rounded-lg"
        />
      </div>

      {/* Rules Table */}
      {loading ? (
        <p className="text-center py-12 text-[var(--js-text-secondary)]">Loading...</p>
      ) : filteredRules.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-[var(--js-border)] rounded-2xl">
          <MapPin className="w-12 h-12 mx-auto text-[var(--js-text-secondary)] mb-3" />
          <p className="text-[var(--js-text-secondary)]">
            {searchTerm ? "No rules match your search" : "No delivery pricing rules yet. Add your first rule above."}
          </p>
        </div>
      ) : (
        <div className="bg-white border border-[var(--js-border)] rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-[var(--js-bg)] border-b border-[var(--js-border)]">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-bold text-[var(--js-text)] uppercase">Pickup Area</th>
                  <th className="px-4 py-3 text-left text-xs font-bold text-[var(--js-text)] uppercase">Delivery Area</th>
                  <th className="px-4 py-3 text-left text-xs font-bold text-[var(--js-text)] uppercase">Order Type</th>
                  <th className="px-4 py-3 text-left text-xs font-bold text-[var(--js-text)] uppercase">Specific To</th>
                  <th className="px-4 py-3 text-right text-xs font-bold text-[var(--js-text)] uppercase">Fee (USD)</th>
                  <th className="px-4 py-3 text-center text-xs font-bold text-[var(--js-text)] uppercase">Status</th>
                  <th className="px-4 py-3 text-right text-xs font-bold text-[var(--js-text)] uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--js-border)]">
                {filteredRules.map((rule) => (
                  <tr key={rule.id} className="hover:bg-[var(--js-bg)] transition">
                    <td className="px-4 py-3 text-sm text-[var(--js-text)]">{rule.pickup_area}</td>
                    <td className="px-4 py-3 text-sm text-[var(--js-text)]">{rule.delivery_area}</td>
                    <td className="px-4 py-3">
                      <span className="inline-block px-2 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800">
                        {rule.order_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--js-text-secondary)]">
                      {rule.shop_id ? `Shop: ${rule.shop_id.slice(0, 8)}` : rule.restaurant_id ? `Restaurant: ${rule.restaurant_id.slice(0, 8)}` : "—"}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm text-[var(--js-text)]">
                      {formatUSD(rule.delivery_fee_usd)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {rule.active ? (
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#2A9D8F]">
                          <Check className="w-3 h-3" /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500">
                          <X className="w-3 h-3" /> Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => setEditingRule(rule)}
                          className="text-[#2A9D8F] hover:text-[#238276] transition"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteRule(rule.id)}
                          className="text-[#D90429] hover:text-[#A8031F] transition"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Add/Edit Modal */}
      {(showAddModal || editingRule) && (
        <RuleModal
          rule={editingRule}
          onClose={() => {
            setShowAddModal(false);
            setEditingRule(null);
          }}
          onSave={() => {
            setShowAddModal(false);
            setEditingRule(null);
            loadRules();
          }}
        />
      )}
    </div>
  );
}

function RuleModal({ rule, onClose, onSave }) {
  const [formData, setFormData] = useState({
    pickup_area: rule?.pickup_area || "",
    delivery_area: rule?.delivery_area || "",
    order_type: rule?.order_type || "all",
    shop_id: rule?.shop_id || "",
    restaurant_id: rule?.restaurant_id || "",
    delivery_fee_usd: rule?.delivery_fee_usd || 2.0,
    active: rule?.active ?? true,
  });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);

    // Validation
    if (!formData.pickup_area.trim() || !formData.delivery_area.trim()) {
      toast.error("Pickup and delivery areas are required");
      setSaving(false);
      return;
    }

    if (formData.delivery_fee_usd < 0) {
      toast.error("Delivery fee cannot be negative");
      setSaving(false);
      return;
    }

    try {
      const payload = {
        ...formData,
        pickup_area: formData.pickup_area.trim(),
        delivery_area: formData.delivery_area.trim(),
        shop_id: formData.shop_id.trim() || null,
        restaurant_id: formData.restaurant_id.trim() || null,
      };

      if (rule) {
        await api.put(`/admin/delivery-pricing-rules/${rule.id}`, payload);
        toast.success("Rule updated");
      } else {
        await api.post("/admin/delivery-pricing-rules", payload);
        toast.success("Rule created");
      }
      onSave();
    } catch (e) {
      toast.error(formatDetail(e.response?.data?.detail) || "Failed to save rule");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-[var(--js-border)] px-6 py-4 flex items-center justify-between">
          <h3 className="font-bold text-xl text-[var(--js-text)]">
            {rule ? "Edit Pricing Rule" : "Add Pricing Rule"}
          </h3>
          <button onClick={onClose} className="text-[var(--js-text-secondary)] hover:text-[var(--js-text)]">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Pickup Area */}
          <div>
            <label className="block text-sm font-semibold text-[var(--js-text)] mb-1">
              Pickup Area <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.pickup_area}
              onChange={(e) => setFormData({ ...formData, pickup_area: e.target.value })}
              placeholder="e.g., Gudele"
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-lg"
              required
            />
          </div>

          {/* Delivery Area */}
          <div>
            <label className="block text-sm font-semibold text-[var(--js-text)] mb-1">
              Delivery Area <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.delivery_area}
              onChange={(e) => setFormData({ ...formData, delivery_area: e.target.value })}
              placeholder="e.g., Munuki"
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-lg"
              required
            />
          </div>

          {/* Order Type */}
          <div>
            <label className="block text-sm font-semibold text-[var(--js-text)] mb-1">
              Order Type
            </label>
            <select
              value={formData.order_type}
              onChange={(e) => setFormData({ ...formData, order_type: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-lg"
            >
              <option value="all">All Orders</option>
              <option value="marketplace">Marketplace Only</option>
              <option value="restaurant">Restaurant Only</option>
            </select>
          </div>

          {/* Shop ID (optional) */}
          <div>
            <label className="block text-sm font-semibold text-[var(--js-text)] mb-1">
              Specific Shop ID (Optional)
            </label>
            <input
              type="text"
              value={formData.shop_id}
              onChange={(e) => setFormData({ ...formData, shop_id: e.target.value })}
              placeholder="Leave empty for all shops"
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-lg"
            />
            <p className="text-xs text-[var(--js-text-secondary)] mt-1">
              If specified, this rule only applies to orders from this shop
            </p>
          </div>

          {/* Restaurant ID (optional) */}
          <div>
            <label className="block text-sm font-semibold text-[var(--js-text)] mb-1">
              Specific Restaurant ID (Optional)
            </label>
            <input
              type="text"
              value={formData.restaurant_id}
              onChange={(e) => setFormData({ ...formData, restaurant_id: e.target.value })}
              placeholder="Leave empty for all restaurants"
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-lg"
            />
            <p className="text-xs text-[var(--js-text-secondary)] mt-1">
              If specified, this rule only applies to orders from this restaurant
            </p>
          </div>

          {/* Delivery Fee */}
          <div>
            <label className="block text-sm font-semibold text-[var(--js-text)] mb-1">
              Delivery Fee (USD) <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={formData.delivery_fee_usd}
              onChange={(e) => setFormData({ ...formData, delivery_fee_usd: parseFloat(e.target.value) || 0 })}
              className="w-full px-3 py-2 border border-[var(--js-border)] rounded-lg"
              required
            />
          </div>

          {/* Active */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="active"
              checked={formData.active}
              onChange={(e) => setFormData({ ...formData, active: e.target.checked })}
              className="w-4 h-4"
            />
            <label htmlFor="active" className="text-sm font-semibold text-[var(--js-text)]">
              Active (rule is currently in use)
            </label>
          </div>

          {/* Info Box */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex gap-3">
            <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-900">
              <p className="font-semibold mb-1">Priority Order:</p>
              <ol className="list-decimal list-inside space-y-0.5 text-xs">
                <li>Shop/Restaurant-specific rules (highest priority)</li>
                <li>Order type + area rules</li>
                <li>Generic area rules (order_type = "all")</li>
                <li>Default delivery fee (fallback)</li>
              </ol>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-[var(--js-border)] rounded-lg font-semibold text-[var(--js-text)] hover:bg-[var(--js-bg)] transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 px-4 py-2 bg-[#C84B31] hover:bg-[#A63C26] disabled:bg-gray-300 text-white font-semibold rounded-lg transition"
            >
              {saving ? "Saving..." : rule ? "Update Rule" : "Create Rule"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
