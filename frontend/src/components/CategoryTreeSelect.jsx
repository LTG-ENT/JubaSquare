import { useEffect, useMemo, useState } from "react";
import { cachedGet } from "@/lib/cachedGet";

const LEVEL_LABELS = ["Category", "Sub-category", "Sub-sub-category"];

function findChain(nodes, targetId, trail = []) {
  for (const n of nodes || []) {
    const next = [...trail, n];
    if (n.id === targetId) return next;
    const deeper = findChain(n.children, targetId, next);
    if (deeper) return deeper;
  }
  return null;
}

/**
 * Hierarchical category selector (Iter 33). Renders one <select> per level
 * of the tree. Selecting a node with children reveals the next level with an
 * optional "(use this category)" escape so sellers can stop at any depth.
 */
export const CategoryTreeSelect = ({ group, value, onChange, testIdPrefix = "cat-tree" }) => {
  const [tree, setTree] = useState([]);
  useEffect(() => {
    cachedGet(`/categories/tree?group=${group}`)
      .then((d) => setTree(Array.isArray(d) ? d : []))
      .catch(() => setTree([]));
  }, [group]);

  const chain = useMemo(() => findChain(tree, value) || [], [tree, value]);

  if (!tree.length) {
    return (
      <div>
        <span className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">Category</span>
        <div className="js-input text-[#A3A39E] italic">No categories available yet.</div>
      </div>
    );
  }

  const levels = [];
  let opts = tree;
  for (let i = 0; opts && opts.length; i++) {
    const selected = chain[i];
    levels.push({ options: opts, selectedId: selected?.id || "" });
    opts = selected?.children?.length ? selected.children : null;
    if (levels.length >= 6) break;
  }

  const pick = (levelIdx, id) => {
    if (!id) {
      // "(use this category)" — fall back to the parent level's selection
      const parent = chain[levelIdx - 1];
      if (parent) onChange(parent.id, chain.slice(0, levelIdx).map((n) => n.name).join(" > "));
      return;
    }
    const node = levels[levelIdx].options.find((o) => o.id === id);
    if (!node) return;
    const names = [...chain.slice(0, levelIdx).map((n) => n.name), node.name];
    onChange(node.id, names.join(" > "));
  };

  return (
    <div className="space-y-3">
      {levels.map((lvl, i) => (
        <div key={i}>
          <span className="text-xs text-[#5C5C5C] font-semibold block mb-1.5">
            {LEVEL_LABELS[i] || `Level ${i + 1}`}
          </span>
          <select
            value={lvl.selectedId}
            onChange={(e) => pick(i, e.target.value)}
            className="js-input w-full"
            data-testid={`${testIdPrefix}-level-${i}`}
            required={i === 0}
          >
            {i > 0 && <option value="">— use "{chain[i - 1]?.name}" (no deeper) —</option>}
            {lvl.options.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}{o.children?.length ? " ›" : ""}
              </option>
            ))}
          </select>
        </div>
      ))}
      {chain.length > 1 && (
        <p className="text-[11px] text-[var(--js-text-secondary)]" data-testid={`${testIdPrefix}-path`}>
          Path: {chain.map((n) => n.name).join(" > ")}
        </p>
      )}
    </div>
  );
};

export default CategoryTreeSelect;
