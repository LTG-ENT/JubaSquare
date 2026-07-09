import { useEffect, useState } from "react";
import api from "@/lib/api";

/**
 * Iter 33 — Seller-facing dynamic attribute inputs. Fetches the effective
 * attributes (inherited included) for the given category and renders the
 * right input per attribute type. Values live in the parent form's
 * `attributes` object keyed by attribute `key`.
 */
export const AttributeFieldsEditor = ({ categoryId, values = {}, onChange }) => {
  const [defs, setDefs] = useState([]);
  const [groups, setGroups] = useState([]);

  useEffect(() => {
    if (!categoryId) { setDefs([]); return; }
    api.get(`/categories/${categoryId}/attributes`)
      .then((r) => {
        setDefs(r.data?.attributes || []);
        setGroups(r.data?.groups || []);
      })
      .catch(() => { setDefs([]); setGroups([]); });
  }, [categoryId]);

  if (!defs.length) return null;

  const setVal = (key, v) => {
    const next = { ...values };
    if (v === "" || v == null || (Array.isArray(v) && !v.length)) delete next[key];
    else next[key] = v;
    onChange(next);
  };

  const groupName = {};
  groups.forEach((g) => { groupName[g.id] = g.name; });
  const buckets = new Map();
  defs.forEach((d) => {
    const gid = d.group_id && groupName[d.group_id] ? d.group_id : "__other";
    if (!buckets.has(gid)) buckets.set(gid, []);
    buckets.get(gid).push(d);
  });

  return (
    <div className="bg-[var(--js-subtle)] rounded-2xl p-4 space-y-4" data-testid="attribute-fields-editor">
      <p className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">
        Product details & attributes
      </p>
      {[...buckets.entries()].map(([gid, list]) => (
        <div key={gid} className="space-y-3">
          {buckets.size > 1 && (
            <p className="text-[11px] font-bold text-[var(--js-text)]">
              {gid === "__other" ? "Other details" : groupName[gid]}
            </p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {list.map((d) => (
              <AttrInput key={d.key} def={d} value={values[d.key]} setVal={setVal} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

function AttrInput({ def: d, value, setVal }) {
  const label = (
    <span className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">
      {d.name}{d.unit ? ` (${d.unit})` : ""}{d.required && <span className="text-red-500"> *</span>}
    </span>
  );
  const tid = `attr-field-${d.key}`;

  if (d.type === "boolean") {
    return (
      <label className="flex items-center gap-2 text-sm font-medium cursor-pointer select-none pt-5">
        <input
          type="checkbox"
          checked={!!value}
          onChange={(e) => setVal(d.key, e.target.checked ? true : "")}
          data-testid={tid}
          className="w-4 h-4"
        />
        {d.name}
      </label>
    );
  }
  if ((d.type === "dropdown" || d.type === "color") && (d.options || []).length) {
    return (
      <div>
        {label}
        <select
          value={value || ""}
          onChange={(e) => setVal(d.key, e.target.value)}
          className="js-input w-full"
          data-testid={tid}
          required={d.required}
        >
          <option value="">— select —</option>
          {d.options.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>
    );
  }
  if (d.type === "multi_select") {
    const selected = Array.isArray(value) ? value : [];
    const toggle = (opt) =>
      setVal(d.key, selected.includes(opt) ? selected.filter((x) => x !== opt) : [...selected, opt]);
    return (
      <div className="sm:col-span-2">
        {label}
        <div className="flex flex-wrap gap-1.5" data-testid={tid}>
          {(d.options || []).map((o) => (
            <button
              key={o}
              type="button"
              onClick={() => toggle(o)}
              data-testid={`${tid}-${o.replace(/\s+/g, "-").toLowerCase()}`}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition ${
                selected.includes(o)
                  ? "bg-[#1A1A1A] text-white border-[#1A1A1A]"
                  : "bg-white text-[var(--js-text)] border-[var(--js-border)] hover:border-[#1A1A1A]"
              }`}
            >
              {o}
            </button>
          ))}
        </div>
      </div>
    );
  }
  const inputType =
    d.type === "date" ? "date" :
    ["number", "decimal", "weight", "measurement"].includes(d.type) ? "number" : "text";
  return (
    <div>
      {label}
      <input
        type={inputType}
        step={["decimal", "weight", "measurement"].includes(d.type) ? "any" : undefined}
        value={value ?? ""}
        onChange={(e) => setVal(d.key, e.target.value)}
        placeholder={d.description || ""}
        className="js-input w-full"
        data-testid={tid}
        required={d.required}
      />
    </div>
  );
}

export default AttributeFieldsEditor;
