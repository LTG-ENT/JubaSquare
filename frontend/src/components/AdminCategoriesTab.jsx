import { useEffect, useMemo, useState } from "react";
import api, { formatDetail } from "@/lib/api";
import ImageUpload from "@/components/ImageUpload";
import { toast } from "sonner";
import {
  Plus,
  Pencil,
  Trash2,
  Eye,
  EyeOff,
  ArrowUp,
  ArrowDown,
  ChevronRight,
  ChevronDown,
  X,
  Save,
  FolderTree,
  Tag,
  Loader2,
  GripVertical,
  AlertTriangle,
} from "lucide-react";

const GROUPS = [
  { id: "retail", label: "Retail" },
  { id: "wholesale", label: "Wholesale" },
  { id: "restaurant", label: "Restaurants" },
];

// Iter 33 — drag-and-drop: which zone of a row the cursor is over.
const zoneFromEvent = (e) => {
  const r = e.currentTarget.getBoundingClientRect();
  const y = e.clientY - r.top;
  if (y < r.height * 0.3) return "before";
  if (y > r.height * 0.7) return "after";
  return "into";
};

export default function AdminCategoriesTab() {
  const [group, setGroup] = useState("retail");
  const [tree, setTree] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState({}); // {parentId: true}
  const [editor, setEditor] = useState(null); // {mode:'add-top'|'add-sub'|'edit', parent_id?, category?}
  const [dragId, setDragId] = useState(null); // Iter 33 — DnD source category id
  const [dragOver, setDragOver] = useState(null); // {id, zone: 'before'|'after'|'into'}

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/admin/categories?group=${group}`);
      // Backend returns dict per group when no group passed; with group param returns the group's tree directly.
      setTree(Array.isArray(data) ? data : data[group] || []);
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line
  }, [group]);

  const totalCounts = useMemo(() => {
    let parents = tree.length;
    let subs = tree.reduce((s, t) => s + (t.children?.length || 0), 0);
    return { parents, subs };
  }, [tree]);

  const toggleExpanded = (id) => setExpanded((e) => ({ ...e, [id]: !e[id] }));

  // Iter 33 — depth linter: warn when any subtree exceeds 3 levels (depth ≥ 3).
  const maxDepth = useMemo(() => {
    let max = 0;
    const walk = (nodes, d) => (nodes || []).forEach((n) => {
      if (d > max) max = d;
      if (n.children?.length) walk(n.children, d + 1);
    });
    walk(tree, 0);
    return max;
  }, [tree]);

  // Iter 33 — drop onto a row. zone 'into' = become child; 'before'/'after' =
  // reorder among (and move to) the target's siblings.
  const handleDropOnNode = async (targetNode, targetParentId, targetSiblings, zone) => {
    const src = dragId;
    setDragId(null);
    setDragOver(null);
    if (!src || src === targetNode.id) return;
    try {
      if (zone === "into") {
        await api.post(`/admin/categories/${src}/move`, { parent_id: targetNode.id });
        toast.success(`Moved under "${targetNode.name}"`);
      } else {
        const sameParent = targetSiblings.some((s) => s.id === src);
        if (!sameParent) {
          await api.post(`/admin/categories/${src}/move`, { parent_id: targetParentId });
        }
        const ids = targetSiblings.map((s) => s.id).filter((id) => id !== src);
        const idx = ids.indexOf(targetNode.id);
        ids.splice(zone === "before" ? idx : idx + 1, 0, src);
        await api.post("/admin/categories/reorder", { group, parent_id: targetParentId, ids });
        toast.success(sameParent ? "Reordered" : "Category moved");
      }
      await load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
      await load();
    }
  };

  const handleDropToRoot = async () => {
    const src = dragId;
    setDragId(null);
    setDragOver(null);
    if (!src) return;
    try {
      await api.post(`/admin/categories/${src}/move`, { parent_id: null });
      toast.success("Moved to top level");
      await load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    }
  };

  const dnd = { dragId, dragOver, setDragId, setDragOver, handleDropOnNode };

  const moveCategory = async (parentId, list, fromIdx, dir) => {
    const toIdx = fromIdx + dir;
    if (toIdx < 0 || toIdx >= list.length) return;
    const next = [...list];
    [next[fromIdx], next[toIdx]] = [next[toIdx], next[fromIdx]];
    try {
      await api.post("/admin/categories/reorder", {
        group,
        parent_id: parentId,
        ids: next.map((c) => c.id),
      });
      await load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    }
  };

  const toggleActive = async (cat) => {
    try {
      await api.put(`/admin/categories/${cat.id}`, { is_active: !cat.is_active });
      toast.success(cat.is_active ? "Category hidden" : "Category activated");
      await load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    }
  };

  const deleteCategory = async (cat) => {
    const hasChildren = (cat.children?.length || 0) > 0;
    const msg = hasChildren
      ? `Delete "${cat.name}" AND its ${cat.children.length} sub-categor${cat.children.length === 1 ? "y" : "ies"}? This cannot be undone.`
      : `Delete "${cat.name}"? This cannot be undone.`;
    if (!window.confirm(msg)) return;
    try {
      await api.delete(`/admin/categories/${cat.id}${hasChildren ? "?force=true" : ""}`);
      toast.success("Category deleted");
      await load();
    } catch (err) {
      toast.error(formatDetail(err.response?.data?.detail || err.message));
    }
  };

  return (
    <div className="space-y-6" data-testid="admin-categories-tab">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h2 className="font-display font-bold text-2xl text-[var(--js-text)] flex items-center gap-2">
            <FolderTree className="w-6 h-6" /> Categories
          </h2>
          <p className="text-sm text-[var(--js-text-secondary)] mt-1">
            Manage shop & product categories. Up to 5 levels of nesting are
            supported (3 recommended). Use product attributes/filters for
            variations like size, color, or brand.
          </p>
        </div>
        <button
          onClick={() => setEditor({ mode: "add-top" })}
          data-testid="cat-add-top"
          className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#B23E27] text-white text-sm font-semibold px-4 py-2.5 rounded-xl shadow-sm"
        >
          <Plus className="w-4 h-4" /> New top-level category
        </button>
      </div>

      {/* Group tabs */}
      <div className="flex flex-wrap gap-2">
        {GROUPS.map((g) => (
          <button
            key={g.id}
            onClick={() => setGroup(g.id)}
            data-testid={`cat-group-${g.id}`}
            className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-semibold transition ${
              group === g.id
                ? "bg-[#1A1A1A] text-white"
                : "bg-white border border-[var(--js-border)] text-[var(--js-text)] hover:border-[#1A1A1A]"
            }`}
          >
            {g.label}
          </button>
        ))}
        <span className="ml-auto text-xs text-[var(--js-text-secondary)] self-center">
          {totalCounts.parents} top-level · {totalCounts.subs} sub-categories
        </span>
      </div>

      {/* Iter 33 — depth linter banner */}
      {maxDepth >= 3 && (
        <div
          className="flex items-start gap-3 bg-amber-50 border border-amber-300 text-amber-900 rounded-2xl px-4 py-3"
          data-testid="cat-depth-warning"
        >
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-bold">This category structure is deeper than recommended (more than 3 levels).</p>
            <p className="text-xs mt-0.5">
              Categories should describe <em>what a product is</em>. For characteristics like
              Brand, Size, Storage or Material, use <strong>Attributes</strong> (Admin → Attributes tab)
              — they automatically become customer filters.
            </p>
          </div>
        </div>
      )}

      <p className="text-[11px] text-[var(--js-text-secondary)]">
        Tip: drag any row to reorder it, or drop it onto another category to nest it inside.
      </p>

      {/* Tree */}
      <div className="bg-white border border-[var(--js-border)] rounded-2xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-[var(--js-text-secondary)]">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
        ) : tree.length === 0 ? (
          <div className="text-center py-16 text-[var(--js-text-secondary)]" data-testid="cat-empty">
            No categories yet. Add your first one with the button above.
          </div>
        ) : (
          <ul className="divide-y divide-[var(--js-border)]">
            {tree.map((root, idx) => (
              <CategoryNode
                key={root.id}
                node={root}
                depth={0}
                siblings={tree}
                index={idx}
                expanded={expanded}
                toggleExpanded={toggleExpanded}
                setEditor={setEditor}
                toggleActive={toggleActive}
                deleteCategory={deleteCategory}
                moveCategory={moveCategory}
                parentId={null}
              />
            ))}
          </ul>
        )}
      </div>

      {/* Editor modal */}
      {editor && (
        <CategoryEditor
          group={group}
          editor={editor}
          onClose={() => setEditor(null)}
          onSaved={async () => {
            setEditor(null);
            await load();
          }}
        />
      )}
    </div>
  );
}

/**
 * Recursive category node — renders itself, then recurses into
 * `node.children`. Supports arbitrary depth (Iter 32). Level 0 = root; the
 * "Add sub-category" action shows on every level except the deepest allowed.
 */
const MAX_UI_DEPTH = 4; // matches backend MAX_CATEGORY_DEPTH - 1

function CategoryNode(props) { return CategoryNodeInner(props); }
function CategoryNodeInner({
  node,
  depth,
  siblings,
  index,
  parentId,
  expanded,
  toggleExpanded,
  setEditor,
  toggleActive,
  deleteCategory,
  moveCategory,
  dnd,
}) {
  const isRoot = depth === 0;
  const hasChildren = !!node.children?.length;
  const canAddSub = depth < MAX_UI_DEPTH;
  return (
    <CategoryRow
      cat={node}
      isParent={isRoot}
      isFirst={index === 0}
      isLast={index === siblings.length - 1}
      expanded={!!expanded[node.id]}
      onToggleExpanded={hasChildren ? () => toggleExpanded(node.id) : undefined}
      onMoveUp={() => moveCategory(parentId, siblings, index, -1)}
      onMoveDown={() => moveCategory(parentId, siblings, index, +1)}
      onEdit={() => setEditor({ mode: "edit", category: node })}
      onAddSub={canAddSub ? () => setEditor({ mode: "add-sub", parent_id: node.id, parentName: node.name }) : undefined}
      onToggleActive={() => toggleActive(node)}
      onDelete={() => deleteCategory(node)}
      depth={depth}
      dnd={dnd}
      parentId={parentId}
      siblings={siblings}
    >
      {hasChildren && expanded[node.id] && (
        <ul className="bg-[var(--js-bg)] border-t border-[var(--js-border)] divide-y divide-[var(--js-border)]">
          {node.children.map((child, cidx) => (
            <CategoryNode
              key={child.id}
              node={child}
              depth={depth + 1}
              siblings={node.children}
              index={cidx}
              parentId={node.id}
              expanded={expanded}
              toggleExpanded={toggleExpanded}
              setEditor={setEditor}
              toggleActive={toggleActive}
              deleteCategory={deleteCategory}
              moveCategory={moveCategory}
              dnd={dnd}
            />
          ))}
        </ul>
      )}
    </CategoryRow>
  );
}

function CategoryRow({
  cat,
  isParent = false,
  isFirst,
  isLast,
  expanded,
  onToggleExpanded,
  onMoveUp,
  onMoveDown,
  onEdit,
  onAddSub,
  onToggleActive,
  onDelete,
  children,
  depth = 0,
  dnd,
  parentId,
  siblings,
}) {
  const childCount = cat.children?.length || 0;
  const canExpand = childCount > 0;
  const over = dnd?.dragOver?.id === cat.id ? dnd.dragOver.zone : null;
  return (
    <li>
      <div
        className={`flex items-center gap-3 px-4 sm:px-5 py-3 ${cat.is_active ? "" : "opacity-60"} ${
          dnd?.dragId === cat.id ? "opacity-40" : ""
        } ${over === "into" ? "ring-2 ring-inset ring-[#C84B31] bg-[#C84B31]/5" : ""} ${
          over === "before" ? "shadow-[inset_0_3px_0_#C84B31]" : ""
        } ${over === "after" ? "shadow-[inset_0_-3px_0_#C84B31]" : ""}`}
        style={{ paddingLeft: `${16 + depth * 20}px` }}
        data-testid={`cat-row-${cat.id}`}
        draggable
        onDragStart={(e) => {
          e.stopPropagation();
          e.dataTransfer.effectAllowed = "move";
          e.dataTransfer.setData("text/plain", cat.id);
          dnd?.setDragId(cat.id);
        }}
        onDragEnd={() => {
          dnd?.setDragId(null);
          dnd?.setDragOver(null);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
          if (!dnd?.dragId || dnd.dragId === cat.id) return;
          const zone = zoneFromEvent(e);
          if (dnd.dragOver?.id !== cat.id || dnd.dragOver?.zone !== zone) {
            dnd.setDragOver({ id: cat.id, zone });
          }
        }}
        onDrop={(e) => {
          e.preventDefault();
          e.stopPropagation();
          dnd?.handleDropOnNode(cat, parentId, siblings, zoneFromEvent(e));
        }}
      >
        {/* Drag handle */}
        <span
          className="w-5 shrink-0 flex items-center justify-center text-[var(--js-text-secondary)] cursor-grab active:cursor-grabbing"
          data-testid={`cat-drag-${cat.id}`}
          title="Drag to move / reorder"
        >
          <GripVertical className="w-4 h-4" />
        </span>
        {/* Expand toggle — shown at every depth when the node has children */}
        {canExpand ? (
          <button
            onClick={onToggleExpanded}
            className="w-7 h-7 rounded-lg border border-[var(--js-border)] flex items-center justify-center hover:bg-[var(--js-bg)] shrink-0"
            data-testid={`cat-expand-${cat.id}`}
            aria-label="Toggle children"
          >
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        ) : (
          <span className="w-7 shrink-0" />
        )}

        {/* Image */}
        <div className="w-10 h-10 rounded-lg overflow-hidden bg-[var(--js-bg)] border border-[var(--js-border)] shrink-0 flex items-center justify-center">
          {cat.image_url ? (
            <img
              src={cat.image_url}
              alt=""
              className="w-full h-full object-cover"
              onError={(e) => {
                e.target.style.display = "none";
              }}
            />
          ) : (
            <Tag className="w-4 h-4 text-[var(--js-text-secondary)]" />
          )}
        </div>

        {/* Name + meta */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-[var(--js-text)] truncate">{cat.name}</span>
            {!cat.is_active && (
              <span className="text-[10px] uppercase tracking-wider font-bold bg-amber-100 text-amber-700 px-2 py-0.5 rounded">
                Hidden
              </span>
            )}
            {isParent && childCount > 0 && (
              <span className="text-[10px] text-[var(--js-text-secondary)]">
                {childCount} sub-categor{childCount === 1 ? "y" : "ies"}
              </span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={onMoveUp}
            disabled={isFirst}
            data-testid={`cat-up-${cat.id}`}
            className="w-8 h-8 rounded-lg hover:bg-[var(--js-bg)] disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center"
            title="Move up"
          >
            <ArrowUp className="w-4 h-4" />
          </button>
          <button
            onClick={onMoveDown}
            disabled={isLast}
            data-testid={`cat-down-${cat.id}`}
            className="w-8 h-8 rounded-lg hover:bg-[var(--js-bg)] disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center"
            title="Move down"
          >
            <ArrowDown className="w-4 h-4" />
          </button>
          {onAddSub && (
            <button
              onClick={onAddSub}
              data-testid={`cat-add-sub-${cat.id}`}
              className="w-8 h-8 rounded-lg hover:bg-[var(--js-bg)] flex items-center justify-center text-[#C84B31]"
              title="Add sub-category"
            >
              <Plus className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={onToggleActive}
            data-testid={`cat-toggle-${cat.id}`}
            className="w-8 h-8 rounded-lg hover:bg-[var(--js-bg)] flex items-center justify-center"
            title={cat.is_active ? "Hide" : "Show"}
          >
            {cat.is_active ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
          </button>
          <button
            onClick={onEdit}
            data-testid={`cat-edit-${cat.id}`}
            className="w-8 h-8 rounded-lg hover:bg-[var(--js-bg)] flex items-center justify-center"
            title="Edit"
          >
            <Pencil className="w-4 h-4" />
          </button>
          <button
            onClick={onDelete}
            data-testid={`cat-delete-${cat.id}`}
            className="w-8 h-8 rounded-lg hover:bg-red-50 text-red-600 flex items-center justify-center"
            title="Delete"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
      {children}
    </li>
  );
}

function CategoryEditor({ group, editor, onClose, onSaved }) {
  const isEdit = editor.mode === "edit";
  const isSub = editor.mode === "add-sub";
  const [name, setName] = useState(editor.category?.name || "");
  const [imageUrl, setImageUrl] = useState(editor.category?.image_url || "");
  const [isActive, setIsActive] = useState(
    editor.category?.is_active === undefined ? true : !!editor.category.is_active
  );
  const [busy, setBusy] = useState(false);

  const titleSuffix = isEdit
    ? "Edit category"
    : isSub
    ? `New sub-category of "${editor.parentName}"`
    : `New top-level category in ${group}`;

  const submit = async () => {
    if (!name.trim()) {
      toast.error("Name is required");
      return;
    }
    setBusy(true);
    try {
      if (isEdit) {
        await api.put(`/admin/categories/${editor.category.id}`, {
          name: name.trim(),
          image_url: imageUrl.trim(),
          is_active: isActive,
        });
        toast.success("Category updated");
      } else {
        await api.post(`/admin/categories`, {
          name: name.trim(),
          group,
          parent_id: isSub ? editor.parent_id : null,
          image_url: imageUrl.trim(),
          is_active: isActive,
        });
        toast.success("Category created");
      }
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
      data-testid="cat-editor"
    >
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--js-border)]">
          <h3 className="font-display font-bold text-lg">{titleSuffix}</h3>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg hover:bg-[var(--js-bg)] flex items-center justify-center"
            data-testid="cat-editor-close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div>
            <label className="text-xs font-semibold text-[var(--js-text-secondary)] uppercase tracking-wider">
              Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              data-testid="cat-editor-name"
              autoFocus
              className="mt-1.5 w-full bg-white border border-[var(--js-border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#C84B31]"
              placeholder="e.g. Groceries"
            />
          </div>

          <ImageUpload
            value={imageUrl}
            onChange={setImageUrl}
            label="Icon / image (optional)"
            testId="cat-editor-image"
          />

          <label className="flex items-center gap-2 text-sm font-medium select-none cursor-pointer">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              data-testid="cat-editor-active"
              className="w-4 h-4"
            />
            <span>Active (visible to shoppers)</span>
          </label>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-[var(--js-border)] bg-[var(--js-bg)]">
          <button
            onClick={onClose}
            data-testid="cat-editor-cancel"
            className="px-4 py-2 rounded-xl text-sm font-semibold text-[var(--js-text-secondary)] hover:text-[var(--js-text)]"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={busy}
            data-testid="cat-editor-save"
            className="inline-flex items-center gap-2 bg-[#C84B31] hover:bg-[#B23E27] text-white text-sm font-semibold px-5 py-2 rounded-xl shadow-sm disabled:opacity-60"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {isEdit ? "Save changes" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
