import { useEffect, useMemo, useState } from "react";
import api, { formatDetail } from "@/lib/api";
import { toast } from "sonner";
import {
  Plus, Pencil, Trash2, Eye, EyeOff, ArrowUp, ArrowDown, X, Save,
  SlidersHorizontal, Layers, Loader2, Search as SearchIcon, Filter,
} from "lucide-react";

const BUSINESS_TYPES = [
  { id: "retail", label: "Retail" },
  { id: "wholesale", label: "Wholesale" },
  { id: "restaurant", label: "Restaurants" },
];

const ATTRIBUTE_TYPES = [
  { id: "text", label: "Text" },
  { id: "number", label: "Number" },
  { id: "decimal", label: "Decimal" },
  { id: "dropdown", label: "Dropdown" },
  { id: "multi_select", label: "Multi-select" },
  { id: "boolean", label: "Yes / No" },
  { id: "color", label: "Color" },
  { id: "date", label: "Date" },
  { id: "measurement", label: "Measurement" },
  { id: "dimensions", label: "Dimensions" },
  { id: "weight", label: "Weight" },
];

const OPTION_TYPES = ["dropdown", "multi_select", "color"];
const UNIT_TYPES = ["measurement", "dimensions", "weight", "number", "decimal"];

export default function AdminAttributesTab() {
  const [bt, setBt] = useState("retail");
  const [attrs, setAttrs] = useState([]);
  const [groups, setGroups] = useState([]);
  const [catTree, setCatTree] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editor, setEditor] = useState(null); // {attr?} null=closed, {}=new
  // Iter 33.7 — Groups act as a top-level filter tab strip. When null → show
  // every attribute grouped by their group (legacy layout). Otherwise show
  // ONLY attributes belonging to that group (or ungrouped if selectedGroup === "__other").
  const [selectedGroup, setSelectedGroup] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [{ data }, treeRes] = await Promise.all([
        api.get(`/admin/attributes?business_type=${bt}`),
        api.get(`/admin/categories?group=${bt}`),
      ]);
      setAttrs(data.attributes || []);
      setGroups(data.groups || []);
      setCatTree(Array.isArray(treeRes.data) ? treeRes.data : treeRes.data?.[bt] || []);
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [bt]);
  // Reset the group tab whenever the business type changes so we don't
  // reference a group that lives in a different business_type.
  useEffect(() => { setSelectedGroup(null); }, [bt]);

  const groupName = useMemo(() => {
    const m = {};
    groups.forEach((g) => { m[g.id] = g.name; });
    return m;
  }, [groups]);

  const buckets = useMemo(() => {
    const map = new Map();
    groups.forEach((g) => map.set(g.id, []));
    map.set("__other", []);
    attrs.forEach((a) => {
      const gid = a.group_id && groupName[a.group_id] ? a.group_id : "__other";
      map.get(gid).push(a);
    });
    return map;
  }, [attrs, groups, groupName]);

  const toggleActive = async (a) => {
    try {
      await api.put(`/admin/attributes/${a.id}`, { is_active: !a.is_active });
      toast.success(a.is_active ? "Attribute disabled" : "Attribute enabled");
      await load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    }
  };

  const removeAttr = async (a) => {
    if (!window.confirm(`Delete attribute "${a.name}"? Existing product values stay stored but will no longer display.`)) return;
    try {
      await api.delete(`/admin/attributes/${a.id}`);
      toast.success("Attribute deleted");
      await load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    }
  };

  const reorder = async (list, idx, dir) => {
    const other = list[idx + dir];
    if (!other) return;
    const a = list[idx];
    try {
      if (a.order === other.order) {
        // Normalize sequential orders for the whole bucket, then swap
        await Promise.all(list.map((x, i) => api.put(`/admin/attributes/${x.id}`, { order: i + 1 })));
        await Promise.all([
          api.put(`/admin/attributes/${a.id}`, { order: idx + dir + 1 }),
          api.put(`/admin/attributes/${other.id}`, { order: idx + 1 }),
        ]);
      } else {
        await Promise.all([
          api.put(`/admin/attributes/${a.id}`, { order: other.order }),
          api.put(`/admin/attributes/${other.id}`, { order: a.order }),
        ]);
      }
      await load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    }
  };

  return (
    <div className="space-y-6" data-testid="admin-attributes-tab">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h2 className="font-display font-bold text-2xl text-[var(--js-text)] flex items-center gap-2">
            <SlidersHorizontal className="w-6 h-6" /> Attributes
          </h2>
          <p className="text-sm text-[var(--js-text-secondary)] mt-1">
            Attributes describe product characteristics (Brand, RAM, Size, Spice Level...).
            Assign them to categories — children inherit them automatically — and they
            become customer filters when &ldquo;Filterable&rdquo; is on.
          </p>
        </div>
        <button
          onClick={() => setEditor({})}
          data-testid="attr-add-btn"
          className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#B23E27] text-white text-sm font-semibold px-4 py-2.5 rounded-xl shadow-sm"
        >
          <Plus className="w-4 h-4" /> New attribute
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {BUSINESS_TYPES.map((g) => (
          <button
            key={g.id}
            onClick={() => setBt(g.id)}
            data-testid={`attr-bt-${g.id}`}
            className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-semibold transition ${
              bt === g.id
                ? "bg-[#1A1A1A] text-white"
                : "bg-white border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#1A1A1A]"
            }`}
          >
            {g.label}
          </button>
        ))}
        <span className="ml-auto text-xs text-[var(--js-text-secondary)] self-center">
          {attrs.length} attribute{attrs.length === 1 ? "" : "s"} · {groups.length} group{groups.length === 1 ? "" : "s"}
        </span>
      </div>

      <GroupManager
        bt={bt}
        groups={groups}
        onChanged={load}
        selectedGroup={selectedGroup}
        onSelect={setSelectedGroup}
        ungroupedCount={(buckets.get("__other") || []).length}
      />

      <div className="bg-white border border-[var(--js-border)] rounded-2xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-[var(--js-text-secondary)]">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
        ) : attrs.length === 0 ? (
          <div className="text-center py-16 text-[var(--js-text-secondary)]" data-testid="attr-empty">
            No attributes yet for {bt}. Create your first one with the button above.
          </div>
        ) : (
          [...buckets.entries()]
            .filter(([gid, list]) => {
              if (list.length === 0) return false;
              if (selectedGroup === null) return true; // "All groups"
              return gid === selectedGroup;
            })
            .map(([gid, list]) =>
            list.length === 0 ? null : (
              <div key={gid}>
                <div className="px-5 py-2 bg-[var(--js-bg)] border-b border-[var(--js-border)] flex items-center gap-2">
                  <Layers className="w-3.5 h-3.5 text-[var(--js-text-secondary)]" />
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--js-text-secondary)]">
                    {gid === "__other" ? "Ungrouped" : groupName[gid]}
                  </span>
                </div>
                <ul className="divide-y divide-[var(--js-border)]">
                  {list.map((a, idx) => (
                    <li
                      key={a.id}
                      className={`flex items-center gap-3 px-5 py-3 ${a.is_active ? "" : "opacity-60"}`}
                      data-testid={`attr-row-${a.key}`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-semibold text-[var(--js-text)]">{a.name}</span>
                          <span className="text-[10px] uppercase tracking-wider font-bold bg-[var(--js-subtle)] text-[var(--js-text-secondary)] px-2 py-0.5 rounded">
                            {ATTRIBUTE_TYPES.find((t) => t.id === a.type)?.label || a.type}
                          </span>
                          {a.required && <Pill color="bg-red-100 text-red-700">Required</Pill>}
                          {a.filterable && <Pill color="bg-emerald-100 text-emerald-700"><Filter className="w-2.5 h-2.5 inline" /> Filter</Pill>}
                          {a.show_on_all && <Pill color="bg-indigo-100 text-indigo-700">Show on “All”</Pill>}
                          {a.searchable && <Pill color="bg-blue-100 text-blue-700"><SearchIcon className="w-2.5 h-2.5 inline" /> Search</Pill>}
                          {a.category_ids.length === 0 && <Pill color="bg-amber-100 text-amber-700">No categories</Pill>}
                          {!a.is_active && <Pill color="bg-amber-100 text-amber-700">Disabled</Pill>}
                        </div>
                        <p className="text-[11px] text-[var(--js-text-secondary)] mt-0.5 truncate">
                          {a.category_ids.length === 0
                            ? `All ${bt} categories`
                            : `Categories: ${(a.category_names || a.category_ids).join(", ")}`}
                          {a.options?.length ? ` · Options: ${a.options.slice(0, 5).join(", ")}${a.options.length > 5 ? "…" : ""}` : ""}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <IconBtn title="Move up" disabled={idx === 0} testId={`attr-up-${a.key}`} onClick={() => reorder(list, idx, -1)}><ArrowUp className="w-4 h-4" /></IconBtn>
                        <IconBtn title="Move down" disabled={idx === list.length - 1} testId={`attr-down-${a.key}`} onClick={() => reorder(list, idx, +1)}><ArrowDown className="w-4 h-4" /></IconBtn>
                        <IconBtn title={a.is_active ? "Disable" : "Enable"} testId={`attr-toggle-${a.key}`} onClick={() => toggleActive(a)}>
                          {a.is_active ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                        </IconBtn>
                        <IconBtn title="Edit" testId={`attr-edit-${a.key}`} onClick={() => setEditor({ attr: a })}><Pencil className="w-4 h-4" /></IconBtn>
                        <IconBtn title="Delete" testId={`attr-delete-${a.key}`} danger onClick={() => removeAttr(a)}><Trash2 className="w-4 h-4" /></IconBtn>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )
          )
        )}
      </div>

      {editor && (
        <AttributeEditor
          bt={bt}
          groups={groups}
          catTree={catTree}
          attr={editor.attr}
          onClose={() => setEditor(null)}
          onSaved={async () => { setEditor(null); await load(); }}
        />
      )}
    </div>
  );
}

const Pill = ({ color, children }) => (
  <span className={`text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded ${color}`}>{children}</span>
);

const IconBtn = ({ title, onClick, disabled, danger, testId, children }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    data-testid={testId}
    title={title}
    className={`w-8 h-8 rounded-lg flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed ${
      danger ? "hover:bg-red-50 text-red-600" : "hover:bg-[var(--js-bg)]"
    }`}
  >
    {children}
  </button>
);

function GroupManager({ bt, groups, onChanged, selectedGroup, onSelect, ungroupedCount }) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");

  const create = async () => {
    if (!name.trim()) return;
    try {
      await api.post("/admin/attribute-groups", { name: name.trim(), business_type: bt });
      toast.success("Group created");
      setName(""); setAdding(false);
      await onChanged();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    }
  };

  const rename = async (g) => {
    const next = window.prompt("Rename group", g.name);
    if (!next || next.trim() === g.name) return;
    try {
      await api.put(`/admin/attribute-groups/${g.id}`, { name: next.trim() });
      await onChanged();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    }
  };

  const remove = async (g) => {
    if (!window.confirm(`Delete group "${g.name}"? Its attributes become ungrouped.`)) return;
    try {
      await api.delete(`/admin/attribute-groups/${g.id}`);
      // If we were viewing the deleted group, drop back to "All".
      if (selectedGroup === g.id) onSelect?.(null);
      await onChanged();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    }
  };

  // Iter 33.7 — Groups render as a tab strip. Clicking a tab filters the
  // attribute list to that group. "All groups" is the default. Each group
  // tab shows a small rename/delete cluster on hover.
  return (
    <div className="space-y-2" data-testid="attr-group-manager">
      <div className="flex items-center gap-2">
        <span className="text-xs font-bold uppercase tracking-wider text-[var(--js-text-secondary)]">Groups</span>
        <div className="flex-1" />
        {adding ? (
          <span className="inline-flex items-center gap-1">
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && create()}
              placeholder="Group name"
              data-testid="attr-group-name-input"
              className="border border-[var(--js-border)] rounded-full px-3 py-1 text-xs focus:outline-none focus:border-[#C84B31]"
            />
            <button onClick={create} data-testid="attr-group-save" className="text-xs font-bold text-[#C84B31]">Add</button>
            <button onClick={() => setAdding(false)} className="text-xs text-[var(--js-text-secondary)]">Cancel</button>
          </span>
        ) : (
          <button
            onClick={() => setAdding(true)}
            data-testid="attr-group-add"
            className="inline-flex items-center gap-1 text-xs font-bold text-[#C84B31] hover:underline"
          >
            <Plus className="w-3 h-3" /> New group
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-2" role="tablist" data-testid="attr-groups-tabs">
        <button
          onClick={() => onSelect?.(null)}
          data-testid="attr-group-tab-all"
          role="tab"
          aria-selected={selectedGroup === null}
          className={`px-4 py-2 rounded-full text-xs font-semibold transition ${
            selectedGroup === null
              ? "bg-[#1A1A1A] text-white"
              : "bg-white border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#1A1A1A]"
          }`}
        >
          All groups
        </button>
        {groups.map((g) => {
          const active = selectedGroup === g.id;
          return (
            <div
              key={g.id}
              className={`inline-flex items-center gap-1 rounded-full pl-3 pr-1.5 py-1 text-xs font-semibold transition border ${
                active
                  ? "bg-[#C84B31] border-[#C84B31] text-white"
                  : "bg-white border-[var(--js-border)] text-[var(--js-text)] hover:border-[#1A1A1A]"
              }`}
              data-testid={`attr-group-tab-${g.id}`}
            >
              <button
                onClick={() => onSelect?.(g.id)}
                role="tab"
                aria-selected={active}
                data-testid={`attr-group-select-${g.id}`}
                className="cursor-pointer"
              >
                {g.name}
              </button>
              <button
                onClick={() => rename(g)}
                className={`w-5 h-5 rounded-full flex items-center justify-center ${
                  active ? "hover:bg-white/20" : "hover:bg-[var(--js-bg)]"
                }`}
                title="Rename"
                data-testid={`attr-group-rename-${g.id}`}
              >
                <Pencil className="w-3 h-3" />
              </button>
              <button
                onClick={() => remove(g)}
                className={`w-5 h-5 rounded-full flex items-center justify-center ${
                  active ? "hover:bg-white/20" : "hover:bg-red-50 text-red-600"
                }`}
                title="Delete"
                data-testid={`attr-group-delete-${g.id}`}
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          );
        })}
        {ungroupedCount > 0 && (
          <button
            onClick={() => onSelect?.("__other")}
            data-testid="attr-group-tab-ungrouped"
            role="tab"
            aria-selected={selectedGroup === "__other"}
            className={`px-4 py-2 rounded-full text-xs font-semibold transition ${
              selectedGroup === "__other"
                ? "bg-[#1A1A1A] text-white"
                : "bg-white border border-dashed border-[var(--js-border)] text-[var(--js-text-secondary)] hover:border-[#1A1A1A]"
            }`}
          >
            Ungrouped · {ungroupedCount}
          </button>
        )}
      </div>
    </div>
  );
}

function flattenCatNodes(nodes, depth = 0, out = []) {
  for (const n of nodes || []) {
    out.push({ id: n.id, name: n.name, depth });
    if (n.children && n.children.length) flattenCatNodes(n.children, depth + 1, out);
  }
  return out;
}

function CategoryCheckTree({ nodes, selected, onToggle }) {
  // Iter 33.9 — Render only top-level categories by default; each row has a
  // chevron that expands its children. Rows with `selected` descendants
  // auto-open so admins can see current picks.

  // Compute which top-level ids should be auto-expanded because they contain
  // a selected descendant.
  const initialOpen = new Set();
  const collectHasSelected = (n) => {
    if (selected.includes(n.id)) return true;
    let anyChild = false;
    (n.children || []).forEach((c) => { if (collectHasSelected(c)) anyChild = true; });
    if (anyChild) initialOpen.add(n.id);
    return anyChild || selected.includes(n.id);
  };
  (nodes || []).forEach(collectHasSelected);

  const [openIds, setOpenIds] = useState(initialOpen);
  const toggleOpen = (id) => setOpenIds((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const renderNode = (n, depth = 0) => {
    const isOpen = openIds.has(n.id);
    const hasChildren = (n.children || []).length > 0;
    const checked = selected.includes(n.id);
    return (
      <div key={n.id}>
        <div
          className="flex items-center gap-1 py-1 text-sm rounded-lg hover:bg-[var(--js-subtle)] px-1"
          style={{ marginLeft: depth * 16 }}
        >
          {hasChildren ? (
            <button
              type="button"
              onClick={() => toggleOpen(n.id)}
              data-testid={`attr-cat-toggle-${n.id}`}
              aria-label={isOpen ? "Collapse" : "Expand"}
              className="w-5 h-5 flex items-center justify-center rounded hover:bg-[var(--js-bg)] flex-shrink-0"
            >
              <span className={`inline-block transition-transform ${isOpen ? "rotate-90" : ""}`}>▶</span>
            </button>
          ) : (
            <span className="w-5 h-5 flex-shrink-0" />
          )}
          <label className="flex items-center gap-2 flex-1 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={checked}
              onChange={() => onToggle(n.id)}
              data-testid={`attr-cat-check-${n.id}`}
              className="w-3.5 h-3.5 accent-[#C84B31]"
            />
            <span className={depth === 0 ? "font-semibold" : "text-[var(--js-text-secondary)]"}>{n.name}</span>
            {hasChildren && !isOpen && (
              <span className="ml-1 text-[10px] text-[var(--js-text-secondary)]">({(n.children || []).length})</span>
            )}
          </label>
        </div>
        {isOpen && hasChildren && (
          <div>
            {(n.children || []).map((c) => renderNode(c, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-0.5">
      {(nodes || []).map((n) => renderNode(n, 0))}
    </div>
  );
}

function AttributeEditor({ bt, groups, catTree, attr, onClose, onSaved }) {
  const isEdit = !!attr;
  const [f, setF] = useState({
    name: attr?.name || "",
    description: attr?.description || "",
    type: attr?.type || "text",
    business_type: attr?.business_type || bt,
    category_ids: attr?.category_ids || [],
    group_id: attr?.group_id || "",
    options: (attr?.options || []).join("\n"),
    unit: attr?.unit || "",
    // Iter 33.11 — Measurement-only fields
    measurement_mode: attr?.measurement_mode || "single",
    unit_options: (attr?.unit_options || []).join(", "),
    required: !!attr?.required,
    filterable: attr ? !!attr.filterable : true,
    searchable: !!attr?.searchable,
    show_on_all: !!attr?.show_on_all,
    is_active: attr ? !!attr.is_active : true,
  });
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const toggleCat = (id) =>
    set("category_ids", f.category_ids.includes(id) ? f.category_ids.filter((c) => c !== id) : [...f.category_ids, id]);

  const submit = async () => {
    if (!f.name.trim()) { toast.error("Name is required"); return; }
    setBusy(true);
    const payload = {
      name: f.name.trim(),
      description: f.description.trim(),
      type: f.type,
      business_type: f.business_type,
      category_ids: f.business_type === bt ? f.category_ids : [],
      group_id: f.group_id || (isEdit ? "" : null),
      options: OPTION_TYPES.includes(f.type) ? f.options.split("\n").map((o) => o.trim()).filter(Boolean) : [],
      unit: UNIT_TYPES.includes(f.type) ? f.unit.trim() : "",
      // Iter 33.11
      measurement_mode: f.type === "measurement" ? f.measurement_mode : "single",
      unit_options: (f.type === "measurement" || UNIT_TYPES.includes(f.type))
        ? f.unit_options.split(",").map((u) => u.trim()).filter(Boolean)
        : [],
      required: f.required,
      filterable: f.filterable,
      searchable: f.searchable,
      show_on_all: f.show_on_all,
      is_active: f.is_active,
    };
    try {
      if (isEdit) await api.put(`/admin/attributes/${attr.id}`, payload);
      else await api.post("/admin/attributes", payload);
      toast.success(isEdit ? "Attribute updated" : "Attribute created");
      await onSaved();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
      data-testid="attr-editor"
    >
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--js-border)] sticky top-0 bg-white z-10">
          <h3 className="font-display font-bold text-lg">{isEdit ? `Edit "${attr.name}"` : `New ${bt} attribute`}</h3>
          <button onClick={onClose} className="w-8 h-8 rounded-lg hover:bg-[var(--js-bg)] flex items-center justify-center" data-testid="attr-editor-close">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Display name">
              <input value={f.name} onChange={(e) => set("name", e.target.value)} autoFocus data-testid="attr-editor-name"
                className="w-full bg-white border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#C84B31]" placeholder="e.g. Brand" />
              {isEdit && <p className="text-[10px] text-[var(--js-text-secondary)] mt-1">Key stays <code>{attr.key}</code> — product values are safe.</p>}
            </Field>
            <Field label="Type">
              <select value={f.type} onChange={(e) => set("type", e.target.value)} data-testid="attr-editor-type"
                className="w-full bg-white border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#C84B31]">
                {ATTRIBUTE_TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
            </Field>
          </div>

          <Field label="Description (optional)">
            <input value={f.description} onChange={(e) => set("description", e.target.value)} data-testid="attr-editor-desc"
              className="w-full bg-white border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#C84B31]" placeholder="Shown to sellers as a hint" />
          </Field>

          {OPTION_TYPES.includes(f.type) && (
            <Field label="Options (one per line)">
              <textarea rows={4} value={f.options} onChange={(e) => set("options", e.target.value)} data-testid="attr-editor-options"
                className="w-full bg-white border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#C84B31]" placeholder={"Samsung\nApple\nTecno"} />
            </Field>
          )}

          {UNIT_TYPES.includes(f.type) && (
            <Field label="Unit (optional)">
              <input value={f.unit} onChange={(e) => set("unit", e.target.value)} data-testid="attr-editor-unit"
                className="w-full bg-white border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#C84B31]" placeholder="e.g. kg, cm, inches" />
            </Field>
          )}

          {/* Iter 33.11 — Measurement type gets two extras */}
          {f.type === "measurement" && (
            <>
              <Field label="Measurement mode">
                <div className="flex gap-2" data-testid="attr-editor-measurement-mode">
                  {[
                    { id: "single", label: "Single value (value + unit)" },
                    { id: "dimensions", label: "Dimensions (L × W × H)" },
                  ].map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => set("measurement_mode", opt.id)}
                      data-testid={`attr-editor-mm-${opt.id}`}
                      className={`flex-1 px-3 py-2 rounded-xl text-xs font-semibold border transition ${
                        f.measurement_mode === opt.id
                          ? "bg-[#C84B31] text-white border-[#C84B31]"
                          : "bg-white text-[var(--js-text)] border-[var(--js-border)] hover:border-[#1A1A1A]"
                      }`}
                    >{opt.label}</button>
                  ))}
                </div>
              </Field>
              <Field label="Allowed units (comma-separated)" hint="e.g. cm, m, in — sellers pick one per value">
                <input
                  value={f.unit_options}
                  onChange={(e) => set("unit_options", e.target.value)}
                  data-testid="attr-editor-unit-options"
                  className="w-full bg-white border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#C84B31]"
                  placeholder="cm, m, in"
                />
              </Field>
            </>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Group">
              <select value={f.group_id} onChange={(e) => set("group_id", e.target.value)} data-testid="attr-editor-group"
                className="w-full bg-white border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#C84B31]">
                <option value="">Ungrouped</option>
                {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
              </select>
            </Field>
            <Field label="Business type">
              <select value={f.business_type} onChange={(e) => set("business_type", e.target.value)} data-testid="attr-editor-bt"
                className="w-full bg-white border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#C84B31]">
                {BUSINESS_TYPES.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
              </select>
              {f.business_type !== bt && (
                <p className="text-[10px] text-amber-700 mt-1">Moving to {f.business_type} clears category assignments (values on existing items stay stored).</p>
              )}
            </Field>
          </div>

          <div className="flex flex-wrap gap-4">
            {[
              ["required", "Required"],
              ["filterable", "Filterable (customer filters)"],
              ["searchable", "Searchable"],
              ["show_on_all", "Show in Marketplace when no category is selected"],
              ["is_active", "Active"],
            ].map(([k, lbl]) => (
              <label key={k} className="flex items-center gap-2 text-sm font-medium select-none cursor-pointer">
                <input type="checkbox" checked={f[k]} onChange={(e) => set(k, e.target.checked)} data-testid={`attr-editor-${k}`} className="w-4 h-4 accent-[#C84B31]" />
                {lbl}
              </label>
            ))}
          </div>

          {f.business_type === bt && (
            <Field label={`Assigned categories (${f.category_ids.length === 0 ? `all ${bt} categories` : `${f.category_ids.length} selected — children inherit`})`}>
              <div className="border border-[var(--js-border)] rounded-xl p-3 max-h-56 overflow-y-auto" data-testid="attr-editor-cat-tree">
                {catTree.length === 0 ? (
                  <p className="text-xs text-[var(--js-text-secondary)] italic">No categories in this business type yet.</p>
                ) : (
                  <CategoryCheckTree nodes={catTree} selected={f.category_ids} onToggle={toggleCat} />
                )}
              </div>
            </Field>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-[var(--js-border)] bg-[var(--js-bg)] sticky bottom-0">
          <button onClick={onClose} data-testid="attr-editor-cancel" className="px-4 py-2 rounded-xl text-sm font-semibold text-[var(--js-text-secondary)] hover:text-[var(--js-text)]">Cancel</button>
          <button onClick={submit} disabled={busy} data-testid="attr-editor-save"
            className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#B23E27] text-white text-sm font-semibold px-5 py-2 rounded-xl shadow-sm disabled:opacity-60">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {isEdit ? "Save changes" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

const Field = ({ label, hint, children }) => (
  <div>
    <label className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">{label}</label>
    <div className="mt-1.5">{children}</div>
    {hint && <p className="text-[11px] text-[var(--js-text-secondary)] mt-1">{hint}</p>}
  </div>
);
