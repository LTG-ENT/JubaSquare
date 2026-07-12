"""
Dynamic Attribute System for JubaSquare (Iter 33).

Categories describe WHAT a product is; attributes describe its
CHARACTERISTICS (Brand, RAM, Size, Spice Level ...). Attributes are
business-type scoped (retail | wholesale | restaurant), can be assigned to
specific categories (empty assignment = whole business type) and are
inherited down the category tree via the category `path` field.
"""
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional, Any, Dict

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

BUSINESS_TYPES = {"retail", "wholesale", "restaurant"}
ATTRIBUTE_TYPES = {
    "text", "number", "decimal", "dropdown", "multi_select", "boolean",
    "color", "date", "measurement", "dimensions", "weight",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")
    return s[:64] or "attr"


def _attr_doc(a: dict) -> dict:
    return {
        "id": a.get("id"),
        "key": a.get("key"),
        "name": a.get("name", ""),
        "description": a.get("description") or "",
        "type": a.get("type", "text"),
        "business_type": a.get("business_type", "retail"),
        "category_ids": a.get("category_ids") or [],
        "group_id": a.get("group_id"),
        "options": a.get("options") or [],
        "unit": a.get("unit") or "",
        "measurement_mode": a.get("measurement_mode") or "single",
        "unit_options": a.get("unit_options") or [],
        "required": bool(a.get("required")),
        "filterable": bool(a.get("filterable", True)),
        "searchable": bool(a.get("searchable")),
        "show_on_all": bool(a.get("show_on_all")),
        "order": int(a.get("order") or 0),
        "is_active": bool(a.get("is_active", True)),
        "created_at": a.get("created_at"),
        "updated_at": a.get("updated_at"),
    }


async def get_effective_attributes(db, category_id: str):
    """Return (category, [effective attribute docs]) for a category, resolving
    inheritance through `path` and per-category exclusions."""
    cat = await db.categories.find_one({"id": category_id}, {"_id": 0})
    if not cat:
        return None, []
    ancestors = list(cat.get("path") or [])
    scope = set(ancestors + [category_id])
    excluded = set(cat.get("excluded_attribute_ids") or [])
    if ancestors:
        anc_docs = await db.categories.find(
            {"id": {"$in": ancestors}}, {"_id": 0, "excluded_attribute_ids": 1}
        ).to_list(50)
        for a in anc_docs:
            excluded |= set(a.get("excluded_attribute_ids") or [])
    attrs = await db.attributes.find(
        {"business_type": cat.get("group", "retail"), "is_active": {"$ne": False}},
        {"_id": 0},
    ).sort([("order", 1), ("name", 1)]).to_list(500)
    out = []
    for a in attrs:
        if a.get("id") in excluded:
            continue
        cids = a.get("category_ids") or []
        if cids and not (set(cids) & scope):
            continue
        doc = _attr_doc(a)
        doc["inherited"] = bool(cids) and category_id not in cids
        doc["global"] = not cids
        out.append(doc)
    return cat, out


async def validate_attribute_values(db, category_id: str, values: Any, enforce_required: bool = True) -> dict:
    """Sanitize + validate a product/menu-item `attributes` dict against the
    effective attribute definitions of its category. Unknown keys are dropped,
    typed values coerced, dropdown options enforced, required enforced."""
    if not isinstance(values, dict):
        values = {}
    _, defs = await get_effective_attributes(db, category_id)
    by_key = {d["key"]: d for d in defs}
    clean: dict = {}
    for k, v in values.items():
        d = by_key.get(k)
        if not d:
            continue
        if v is None or v == "" or v == []:
            continue
        t = d.get("type")
        if t == "boolean":
            clean[k] = v if isinstance(v, bool) else str(v).strip().lower() in ("true", "1", "yes")
        elif t == "measurement":
            # Iter 33.11 — Measurement values follow the attribute's mode:
            #   * single     → {"value": <number>, "unit": "<unit>"} (unit optional
            #                   when the attribute has no declared unit_options).
            #   * dimensions → {"length": {"value": N, "unit": "u"},
            #                    "width":  {...},
            #                    "height": {...}}
            # We also accept raw numbers for backward-compat single-mode usage.
            mode = d.get("measurement_mode") or "single"
            allowed_units = list(d.get("unit_options") or [])
            if d.get("unit") and d["unit"] not in allowed_units:
                allowed_units.append(d["unit"])

            def _num(x, label):
                try:
                    return float(x)
                except (TypeError, ValueError):
                    raise HTTPException(400, f"{label} must be a number for attribute '{d['name']}'")

            def _validate_unit(u, label):
                if u is None or u == "":
                    return ""
                u = str(u).strip()
                if allowed_units and u not in allowed_units:
                    raise HTTPException(400, f"{label} unit '{u}' is not allowed for attribute '{d['name']}'. Allowed: {allowed_units}")
                return u

            if mode == "dimensions":
                if not isinstance(v, dict):
                    raise HTTPException(400, f"Attribute '{d['name']}' expects a Length/Width/Height object")
                out = {}
                for dim in ("length", "width", "height"):
                    if dim not in v:
                        continue
                    piece = v[dim]
                    if isinstance(piece, dict):
                        val = _num(piece.get("value"), f"{dim}")
                        unit = _validate_unit(piece.get("unit"), f"{dim}")
                    else:
                        val = _num(piece, f"{dim}")
                        unit = ""
                    out[dim] = {"value": val, "unit": unit}
                if out:
                    clean[k] = out
            else:
                # Single-value measurement. Accept a raw number OR an object.
                if isinstance(v, dict):
                    val = _num(v.get("value"), "Value")
                    unit = _validate_unit(v.get("unit"), "Value")
                    clean[k] = {"value": val, "unit": unit}
                else:
                    clean[k] = {"value": _num(v, "Value"), "unit": ""}
        elif t in ("number", "decimal", "weight"):
            try:
                clean[k] = float(v)
            except (TypeError, ValueError):
                raise HTTPException(400, f"Attribute '{d['name']}' must be a number")
        elif t == "multi_select":
            vals = v if isinstance(v, list) else [v]
            vals = [str(x).strip() for x in vals if str(x).strip()][:25]
            opts = d.get("options") or []
            if opts:
                bad = [x for x in vals if x not in opts]
                if bad:
                    raise HTTPException(400, f"Invalid value(s) {bad} for attribute '{d['name']}'")
            if vals:
                clean[k] = vals
        elif t in ("dropdown", "color"):
            sv = str(v).strip()
            opts = d.get("options") or []
            if opts and sv not in opts:
                raise HTTPException(400, f"Invalid value '{sv}' for attribute '{d['name']}'")
            clean[k] = sv
        else:  # text, date, dimensions
            clean[k] = str(v).strip()[:500]
    for d in defs:
        if enforce_required and d.get("required") and d["key"] not in clean:
            raise HTTPException(400, f"Attribute '{d['name']}' is required for this category")
    return clean


class AttributeIn(BaseModel):
    name: str
    description: Optional[str] = ""
    type: str = "text"
    business_type: str
    category_ids: List[str] = Field(default_factory=list)
    group_id: Optional[str] = None
    options: List[str] = Field(default_factory=list)
    unit: Optional[str] = ""
    # Iter 33.11 — Measurement attributes support two modes:
    #   * "single"     — one numeric value + one unit picked from unit_options
    #   * "dimensions" — three numeric values (Length × Width × Height),
    #                    each with its own unit picked from unit_options.
    # `unit_options` also applies to weight/dimensions types so sellers can
    # switch between kg/g/lb, cm/m/in, etc.
    measurement_mode: Optional[str] = "single"
    unit_options: List[str] = Field(default_factory=list)
    required: bool = False
    filterable: bool = True
    searchable: bool = False
    show_on_all: bool = False
    order: Optional[int] = None
    is_active: bool = True


class AttributeUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    business_type: Optional[str] = None
    category_ids: Optional[List[str]] = None
    group_id: Optional[str] = None
    options: Optional[List[str]] = None
    unit: Optional[str] = None
    measurement_mode: Optional[str] = None
    unit_options: Optional[List[str]] = None
    required: Optional[bool] = None
    filterable: Optional[bool] = None
    searchable: Optional[bool] = None
    show_on_all: Optional[bool] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None


class AttributeGroupIn(BaseModel):
    name: str
    business_type: str
    order: Optional[int] = None


class AttributeGroupUpdateIn(BaseModel):
    name: Optional[str] = None
    order: Optional[int] = None


def create_attribute_routes(db, require_role):
    router = APIRouter(prefix="/api", tags=["attributes"])

    async def _validate_category_ids(category_ids: List[str], business_type: str) -> List[str]:
        ids = [c for c in (category_ids or []) if c]
        if not ids:
            return []
        cats = await db.categories.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "group": 1}).to_list(500)
        found = {c["id"]: c for c in cats}
        for cid in ids:
            c = found.get(cid)
            if not c:
                raise HTTPException(400, f"Category not found: {cid}")
            if c.get("group") != business_type:
                raise HTTPException(400, f"Category {cid} belongs to '{c.get('group')}', not '{business_type}'")
        return ids

    # ---------------- Public ----------------
    @router.get("/categories/{cat_id}/attributes")
    async def category_attributes(cat_id: str):
        cat, effective = await get_effective_attributes(db, cat_id)
        if not cat:
            raise HTTPException(404, "Category not found")
        groups = await db.attribute_groups.find(
            {"business_type": cat.get("group", "retail")}, {"_id": 0}
        ).sort([("order", 1), ("name", 1)]).to_list(100)
        return {
            "category_id": cat_id,
            "business_type": cat.get("group", "retail"),
            "attributes": effective,
            "groups": groups,
        }

    @router.get("/attributes/facets")
    async def attribute_facets(category_id: Optional[str] = None, business_type: Optional[str] = None):
        """Faceted filter values for the storefront. Counts distinct attribute
        values across products (or menu items) in the category subtree."""
        if not category_id and not business_type:
            raise HTTPException(400, "category_id or business_type required")
        match: dict = {}
        if category_id:
            cat, effective = await get_effective_attributes(db, category_id)
            if not cat:
                raise HTTPException(404, "Category not found")
            bt = cat.get("group", "retail")
            desc = await db.categories.find({"path": category_id}, {"_id": 0, "id": 1}).to_list(2000)
            match["category_id"] = {"$in": [category_id] + [d["id"] for d in desc]}
            defs = [d for d in effective if d.get("filterable")]
        else:
            bt = business_type
            if bt not in BUSINESS_TYPES:
                raise HTTPException(400, f"Unknown business_type. Must be one of: {sorted(BUSINESS_TYPES)}")
            # Iter 33.7 → refined in 33.10 — Return ALL filterable attributes
            # for this business_type when a business_type is explicitly
            # provided. The Marketplace uses this branch when the customer
            # narrows to "Retail only" or "Wholesale only". The `show_on_all`
            # gate is now enforced by the SPA (which simply skips rendering
            # this panel on the un-narrowed "All" view) so wholesale sellers
            # keep their category-agnostic filters.
            raw = await db.attributes.find(
                {
                    "business_type": bt,
                    "is_active": {"$ne": False},
                    "filterable": True,
                },
                {"_id": 0},
            ).sort([("order", 1), ("name", 1)]).to_list(500)
            defs = [_attr_doc(a) for a in raw]
            if not defs:
                return {"business_type": bt, "category_id": None, "facets": []}
            if bt == "wholesale":
                match["is_wholesale"] = True
            elif bt == "retail":
                match["is_wholesale"] = {"$ne": True}
        coll = db.menu_items if bt == "restaurant" else db.products
        match["attributes"] = {"$exists": True, "$nin": [None, {}]}
        docs = await coll.find(match, {"_id": 0, "attributes": 1}).to_list(3000)
        counts: Dict[str, Dict[str, int]] = {}
        for doc in docs:
            for k, v in (doc.get("attributes") or {}).items():
                vals = v if isinstance(v, list) else [v]
                for val in vals:
                    if isinstance(val, bool):
                        sval = "true" if val else "false"
                    elif isinstance(val, float) and val.is_integer():
                        sval = str(int(val))
                    else:
                        sval = str(val)
                    counts.setdefault(k, {})
                    counts[k][sval] = counts[k].get(sval, 0) + 1
        facets = []
        for d in defs:
            vals = counts.get(d["key"], {})
            if not vals:
                continue
            options = [str(o) for o in (d.get("options") or [])]
            value_list = [{"value": o, "count": vals[o]} for o in options if o in vals]
            seen = set(v["value"] for v in value_list)
            for v_, c_ in sorted(vals.items(), key=lambda kv: -kv[1]):
                if v_ not in seen:
                    value_list.append({"value": v_, "count": c_})
            facets.append({
                "key": d["key"], "name": d.get("name"), "type": d.get("type"),
                "unit": d.get("unit") or "", "values": value_list[:30],
            })
        return {"business_type": bt, "category_id": category_id, "facets": facets}

    # ---------------- Admin: attributes ----------------
    @router.get("/admin/attributes")
    async def admin_list_attributes(business_type: Optional[str] = None,
                                    user: dict = Depends(require_role("admin"))):
        q: dict = {}
        if business_type:
            if business_type not in BUSINESS_TYPES:
                raise HTTPException(400, "Unknown business_type")
            q["business_type"] = business_type
        raw = await db.attributes.find(q, {"_id": 0}).sort([("order", 1), ("name", 1)]).to_list(1000)
        attrs = [_attr_doc(a) for a in raw]
        all_cids = sorted({c for a in attrs for c in a["category_ids"]})
        name_by_id = {}
        if all_cids:
            cats = await db.categories.find({"id": {"$in": all_cids}}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
            name_by_id = {c["id"]: c.get("name", "") for c in cats}
        for a in attrs:
            a["category_names"] = [name_by_id.get(c, c) for c in a["category_ids"]]
        gq = {"business_type": business_type} if business_type else {}
        groups = await db.attribute_groups.find(gq, {"_id": 0}).sort([("order", 1), ("name", 1)]).to_list(200)
        return {"attributes": attrs, "groups": groups}

    @router.post("/admin/attributes")
    async def admin_create_attribute(body: AttributeIn, user: dict = Depends(require_role("admin"))):
        name = (body.name or "").strip()
        if not name:
            raise HTTPException(400, "Name is required")
        if body.business_type not in BUSINESS_TYPES:
            raise HTTPException(400, f"Unknown business_type. Must be one of: {sorted(BUSINESS_TYPES)}")
        if body.type not in ATTRIBUTE_TYPES:
            raise HTTPException(400, f"Unknown attribute type. Must be one of: {sorted(ATTRIBUTE_TYPES)}")
        key = _slug(name)
        # Iter 33.8 — Allow the same attribute NAME in different groups. The
        # storage key must still be unique per business_type so product
        # attribute values don't collide, so we auto-suffix the key with the
        # target group's slug when we detect a clash. Same name in the SAME
        # group is still rejected as an obvious duplicate.
        if body.group_id:
            g = await db.attribute_groups.find_one({"id": body.group_id})
            if not g:
                raise HTTPException(404, "Attribute group not found")
        else:
            g = None
        clash = await db.attributes.find_one({"business_type": body.business_type, "key": key})
        if clash:
            if clash.get("group_id") == body.group_id:
                # Same group + same name → true duplicate.
                raise HTTPException(400, f"An attribute named '{name}' already exists in this group.")
            # Different group → append group slug to keep the key unique.
            suffix = _slug((g or {}).get("name", "")) if g else "ungrouped"
            candidate = f"{key}_{suffix}" if suffix else key
            # Guard against a second-level collision (rare: two groups with
            # identical slug or an existing suffixed key).
            n = 2
            while await db.attributes.find_one({"business_type": body.business_type, "key": candidate}):
                candidate = f"{key}_{suffix}_{n}"
                n += 1
            key = candidate
        category_ids = await _validate_category_ids(body.category_ids, body.business_type)
        order_val = body.order
        if order_val is None:
            last = await db.attributes.find_one({"business_type": body.business_type}, sort=[("order", -1)])
            order_val = (last.get("order", 0) + 1) if last else 1
        doc = {
            "id": str(uuid.uuid4()),
            "key": key,
            "name": name,
            "description": (body.description or "").strip(),
            "type": body.type,
            "business_type": body.business_type,
            "category_ids": category_ids,
            "group_id": body.group_id,
            "options": [str(o).strip() for o in (body.options or []) if str(o).strip()][:100],
            "unit": (body.unit or "").strip(),
            "measurement_mode": (body.measurement_mode or "single") if body.type == "measurement" else "single",
            "unit_options": [str(u).strip() for u in (body.unit_options or []) if str(u).strip()][:20],
            "required": bool(body.required),
            "filterable": bool(body.filterable),
            "searchable": bool(body.searchable),
            "show_on_all": bool(body.show_on_all),
            "order": int(order_val),
            "is_active": bool(body.is_active),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        await db.attributes.insert_one(doc)
        return _attr_doc(doc)

    @router.put("/admin/attributes/{attr_id}")
    async def admin_update_attribute(attr_id: str, body: AttributeUpdateIn,
                                     user: dict = Depends(require_role("admin"))):
        existing = await db.attributes.find_one({"id": attr_id})
        if not existing:
            raise HTTPException(404, "Attribute not found")
        updates: dict = {}
        target_bt = existing.get("business_type", "retail")
        if body.business_type is not None and body.business_type != target_bt:
            if body.business_type not in BUSINESS_TYPES:
                raise HTTPException(400, "Unknown business_type")
            dup = await db.attributes.find_one({
                "business_type": body.business_type, "key": existing.get("key"), "id": {"$ne": attr_id}
            })
            if dup:
                raise HTTPException(400, f"An attribute with key '{existing.get('key')}' already exists in {body.business_type}")
            target_bt = body.business_type
            updates["business_type"] = target_bt
            # Moving business types: drop category assignments that belong to the old type
            if body.category_ids is None:
                updates["category_ids"] = []
        if body.name is not None:
            nm = body.name.strip()
            if not nm:
                raise HTTPException(400, "Name cannot be empty")
            updates["name"] = nm  # `key` stays stable so product values stay safe
        if body.type is not None:
            if body.type not in ATTRIBUTE_TYPES:
                raise HTTPException(400, "Unknown attribute type")
            updates["type"] = body.type
        if body.category_ids is not None:
            updates["category_ids"] = await _validate_category_ids(body.category_ids, target_bt)
        if body.group_id is not None:
            if body.group_id == "":
                updates["group_id"] = None
            else:
                g = await db.attribute_groups.find_one({"id": body.group_id})
                if not g:
                    raise HTTPException(404, "Attribute group not found")
                updates["group_id"] = body.group_id
        if body.description is not None:
            updates["description"] = body.description.strip()
        if body.options is not None:
            updates["options"] = [str(o).strip() for o in body.options if str(o).strip()][:100]
        if body.unit is not None:
            updates["unit"] = body.unit.strip()
        if body.measurement_mode is not None:
            mm = (body.measurement_mode or "single").strip()
            if mm not in ("single", "dimensions"):
                raise HTTPException(400, "measurement_mode must be 'single' or 'dimensions'")
            updates["measurement_mode"] = mm
        if body.unit_options is not None:
            updates["unit_options"] = [str(u).strip() for u in body.unit_options if str(u).strip()][:20]
        for f in ("required", "filterable", "searchable", "show_on_all", "is_active"):
            v = getattr(body, f)
            if v is not None:
                updates[f] = bool(v)
        if body.order is not None:
            updates["order"] = int(body.order)
        if updates:
            updates["updated_at"] = _now_iso()
            await db.attributes.update_one({"id": attr_id}, {"$set": updates})
        saved = await db.attributes.find_one({"id": attr_id}, {"_id": 0})
        return _attr_doc(saved)

    @router.delete("/admin/attributes/{attr_id}")
    async def admin_delete_attribute(attr_id: str, user: dict = Depends(require_role("admin"))):
        existing = await db.attributes.find_one({"id": attr_id})
        if not existing:
            raise HTTPException(404, "Attribute not found")
        # Definition removed; existing product values remain stored (harmless, hidden)
        await db.attributes.delete_one({"id": attr_id})
        await db.categories.update_many(
            {"excluded_attribute_ids": attr_id},
            {"$pull": {"excluded_attribute_ids": attr_id}},
        )
        return {"ok": True}

    # ---------------- Admin: attribute groups ----------------
    @router.get("/admin/attribute-groups")
    async def admin_list_groups(business_type: Optional[str] = None,
                                user: dict = Depends(require_role("admin"))):
        q = {"business_type": business_type} if business_type else {}
        return await db.attribute_groups.find(q, {"_id": 0}).sort([("order", 1), ("name", 1)]).to_list(200)

    @router.post("/admin/attribute-groups")
    async def admin_create_group(body: AttributeGroupIn, user: dict = Depends(require_role("admin"))):
        name = (body.name or "").strip()
        if not name:
            raise HTTPException(400, "Name is required")
        if body.business_type not in BUSINESS_TYPES:
            raise HTTPException(400, "Unknown business_type")
        if await db.attribute_groups.find_one({"business_type": body.business_type, "name": name}):
            raise HTTPException(400, "A group with this name already exists")
        order_val = body.order
        if order_val is None:
            last = await db.attribute_groups.find_one({"business_type": body.business_type}, sort=[("order", -1)])
            order_val = (last.get("order", 0) + 1) if last else 1
        doc = {
            "id": str(uuid.uuid4()), "name": name, "business_type": body.business_type,
            "order": int(order_val), "created_at": _now_iso(),
        }
        await db.attribute_groups.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/admin/attribute-groups/{group_id}")
    async def admin_update_group(group_id: str, body: AttributeGroupUpdateIn,
                                 user: dict = Depends(require_role("admin"))):
        g = await db.attribute_groups.find_one({"id": group_id})
        if not g:
            raise HTTPException(404, "Group not found")
        updates = {}
        if body.name is not None and body.name.strip():
            updates["name"] = body.name.strip()
        if body.order is not None:
            updates["order"] = int(body.order)
        if updates:
            await db.attribute_groups.update_one({"id": group_id}, {"$set": updates})
        return await db.attribute_groups.find_one({"id": group_id}, {"_id": 0})

    @router.delete("/admin/attribute-groups/{group_id}")
    async def admin_delete_group(group_id: str, user: dict = Depends(require_role("admin"))):
        g = await db.attribute_groups.find_one({"id": group_id})
        if not g:
            raise HTTPException(404, "Group not found")
        await db.attribute_groups.delete_one({"id": group_id})
        await db.attributes.update_many({"group_id": group_id}, {"$set": {"group_id": None}})
        return {"ok": True}

    # ---------------- Admin: inheritance exclusions ----------------
    @router.post("/admin/categories/{cat_id}/excluded-attributes/{attr_id}")
    async def admin_exclude_attribute(cat_id: str, attr_id: str,
                                      user: dict = Depends(require_role("admin"))):
        cat = await db.categories.find_one({"id": cat_id})
        if not cat:
            raise HTTPException(404, "Category not found")
        if not await db.attributes.find_one({"id": attr_id}):
            raise HTTPException(404, "Attribute not found")
        await db.categories.update_one({"id": cat_id}, {"$addToSet": {"excluded_attribute_ids": attr_id}})
        return {"ok": True, "excluded": True}

    @router.delete("/admin/categories/{cat_id}/excluded-attributes/{attr_id}")
    async def admin_include_attribute(cat_id: str, attr_id: str,
                                      user: dict = Depends(require_role("admin"))):
        cat = await db.categories.find_one({"id": cat_id})
        if not cat:
            raise HTTPException(404, "Category not found")
        await db.categories.update_one({"id": cat_id}, {"$pull": {"excluded_attribute_ids": attr_id}})
        return {"ok": True, "excluded": False}

    return router


async def seed_example_attributes(db):
    """Idempotent one-time seed — only runs when the attributes collection is empty."""
    if await db.attributes.count_documents({}) > 0:
        return
    log.info("Seeding example attributes + groups (empty collection)")

    async def mk_group(name, bt, order):
        doc = {"id": str(uuid.uuid4()), "name": name, "business_type": bt,
               "order": order, "created_at": _now_iso()}
        await db.attribute_groups.insert_one(doc)
        return doc["id"]

    g_tech = await mk_group("Technical Specifications", "retail", 1)
    g_phys = await mk_group("Physical Details", "retail", 2)
    g_ws = await mk_group("Product Specifications", "wholesale", 1)
    g_food = await mk_group("Food Details", "restaurant", 1)

    electronics = await db.categories.find_one(
        {"group": "retail", "name": {"$regex": "^electronics", "$options": "i"}}, {"_id": 0, "id": 1})
    elec_ids = [electronics["id"]] if electronics else []

    def mk(name, bt, typ, group_id, order, options=None, category_ids=None,
           unit="", searchable=False, filterable=True):
        return {
            "id": str(uuid.uuid4()), "key": _slug(name), "name": name, "description": "",
            "type": typ, "business_type": bt, "category_ids": category_ids or [],
            "group_id": group_id, "options": options or [], "unit": unit,
            "required": False, "filterable": filterable, "searchable": searchable,
            "order": order, "is_active": True,
            "created_at": _now_iso(), "updated_at": _now_iso(),
        }

    docs = [
        mk("Brand", "retail", "dropdown", g_tech, 1,
           ["Samsung", "Apple", "Tecno", "Infinix", "Huawei", "Itel", "Nokia", "Other"],
           elec_ids, searchable=True),
        mk("Model", "retail", "text", g_tech, 2, None, elec_ids, searchable=True, filterable=False),
        mk("Storage", "retail", "dropdown", g_tech, 3,
           ["32GB", "64GB", "128GB", "256GB", "512GB", "1TB"], elec_ids),
        mk("RAM", "retail", "dropdown", g_tech, 4,
           ["2GB", "4GB", "6GB", "8GB", "12GB", "16GB"], elec_ids),
        mk("Color", "retail", "color", g_phys, 5,
           ["Black", "White", "Blue", "Red", "Green", "Gold", "Silver", "Other"]),
        mk("Condition", "retail", "dropdown", g_phys, 6, ["New", "Used", "Refurbished"]),
        mk("Material", "wholesale", "dropdown", g_ws, 1,
           ["Cement", "Steel", "Wood", "Plastic", "Aluminium", "Other"]),
        mk("Unit of Measure", "wholesale", "dropdown", g_ws, 2,
           ["Bag", "Ton", "Piece", "Box", "Carton", "Roll"]),
        mk("Spice Level", "restaurant", "dropdown", g_food, 1,
           ["Mild", "Medium", "Hot", "Extra Hot"]),
        mk("Dietary Type", "restaurant", "multi_select", g_food, 2,
           ["Vegetarian", "Vegan", "Halal", "Gluten-Free", "Contains Nuts"]),
        mk("Portion Size", "restaurant", "dropdown", g_food, 3,
           ["Small", "Regular", "Large", "Family"]),
    ]
    await db.attributes.insert_many(docs)
    log.info("✅ Seeded %d example attributes across 4 groups", len(docs))
