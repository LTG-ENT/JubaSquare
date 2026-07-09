"""Iter 32 backend tests — category hierarchy (path/depth, move, breadcrumb,
cascade delete) + section limit bump 10→20.

Covers items from iter32 review request. Test data prefixed with RUN_TAG for
easy cleanup.
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

RUN_TAG = f"TEST_iter32_{uuid.uuid4().hex[:8]}"


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    d = client[DB_NAME]
    yield d
    # Cleanup: any category whose name starts with RUN_TAG
    d.categories.delete_many({"name": {"$regex": f"^{RUN_TAG}"}})
    d.categories.delete_many({"id": {"$regex": f"^{RUN_TAG}"}})
    d.users.delete_many({"email": {"$regex": f"^{RUN_TAG.lower()}"}})
    d.shops.delete_many({"name": {"$regex": f"^{RUN_TAG}"}})
    d.restaurants.delete_many({"name": {"$regex": f"^{RUN_TAG}"}})
    client.close()


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    from requests.cookies import RequestsCookieJar

    class BlockingJar(RequestsCookieJar):
        def set_cookie(self, cookie, *a, **kw):
            return None
    s.cookies = BlockingJar()
    return s


@pytest.fixture(scope="module")
def admin_headers(api):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": "admin@jubasquare.com", "password": "1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}",
            "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def seller_ctx(api, admin_headers, db):
    seller_email = f"{RUN_TAG.lower()}_seller@example.com"
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/admin/users", headers=admin_headers, json={
        "email": seller_email, "name": f"{RUN_TAG} Seller", "role": "seller",
        "password": password, "phone": "+211900032001", "email_verified": True,
    })
    assert r.status_code == 200, r.text
    lr = api.post(f"{BASE_URL}/api/auth/login",
                  json={"email": seller_email, "password": password})
    assert lr.status_code == 200, lr.text
    tok = lr.json()["token"]
    return {"id": lr.json()["user"]["id"], "email": seller_email, "token": tok,
            "headers": {"Authorization": f"Bearer {tok}",
                        "Content-Type": "application/json"}}


@pytest.fixture(scope="module")
def customer_ctx(api, db):
    email = f"{RUN_TAG.lower()}_cust@example.com"
    password = "TestPass123!"
    r = api.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "name": f"{RUN_TAG} Cust",
        "password": password, "phone": "+211900032002",
    })
    assert r.status_code == 200, r.text
    db.users.update_one({"email": email}, {"$set": {"email_verified": True}})
    lg = api.post(f"{BASE_URL}/api/auth/login",
                  json={"email": email, "password": password})
    assert lg.status_code == 200, lg.text
    tok = lg.json()["token"]
    return {"id": lg.json()["user"]["id"], "token": tok,
            "headers": {"Authorization": f"Bearer {tok}",
                        "Content-Type": "application/json"}}


def _create_cat(api, headers, name, parent_id=None, group="retail"):
    r = api.post(f"{BASE_URL}/api/admin/categories", headers=headers,
                 json={"name": name, "group": group, "parent_id": parent_id})
    return r


# ---------------------------------------------------------------------------
# 1) Health
# ---------------------------------------------------------------------------
def test_health(api):
    r = api.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# 2) Backfill: existing categories have path (list) + depth (int)
# ---------------------------------------------------------------------------
def test_backfill_path_depth_populated(api, admin_headers):
    r = api.get(f"{BASE_URL}/api/admin/categories?group=retail",
                headers=admin_headers)
    assert r.status_code == 200, r.text
    tree = r.json()
    # tree is a list of root nodes (children[] recursive)
    assert isinstance(tree, list)

    def _walk(nodes):
        for n in nodes:
            assert "path" in n, f"missing path on {n.get('id')}"
            assert "depth" in n, f"missing depth on {n.get('id')}"
            assert isinstance(n["path"], list)
            assert isinstance(n["depth"], int)
            _walk(n.get("children") or [])

    _walk(tree)


# ---------------------------------------------------------------------------
# 3) Create nested level-3 category — validate depth + path
# ---------------------------------------------------------------------------
class TestCreateNested:
    def test_level3_create(self, api, admin_headers):
        r1 = _create_cat(api, admin_headers, f"{RUN_TAG}_L0", None)
        assert r1.status_code == 200, r1.text
        gp = r1.json()
        assert gp["depth"] == 0 and gp["path"] == []

        r2 = _create_cat(api, admin_headers, f"{RUN_TAG}_L1", gp["id"])
        assert r2.status_code == 200, r2.text
        p = r2.json()
        assert p["depth"] == 1 and p["path"] == [gp["id"]]

        r3 = _create_cat(api, admin_headers, f"{RUN_TAG}_L2", p["id"])
        assert r3.status_code == 200, r3.text
        c = r3.json()
        assert c["depth"] == 2
        assert c["path"] == [gp["id"], p["id"]]


# ---------------------------------------------------------------------------
# 4) Depth limit — creating beyond MAX_CATEGORY_DEPTH must 400
# ---------------------------------------------------------------------------
def test_max_depth_enforced(api, admin_headers):
    tag = f"{RUN_TAG}_depth"
    parent = None
    created = []
    # Create as many as backend allows; expect the failing insert to 400 with
    # "Maximum category depth is 5".
    for i in range(10):
        r = _create_cat(api, admin_headers, f"{tag}_{i}", parent)
        if r.status_code == 200:
            parent = r.json()["id"]
            created.append(r.json())
            continue
        # Expect first failure at depth exceeding MAX (currently 5)
        assert r.status_code == 400, r.text
        assert "Maximum category depth" in r.text or "depth" in r.text.lower()
        break
    else:
        pytest.fail("No depth cap was reached in 10 nested creates — MAX_CATEGORY_DEPTH not enforced")
    # We should have created at least 5 categories before hitting the cap.
    assert len(created) >= 5, f"only created {len(created)} before cap"


# ---------------------------------------------------------------------------
# 5) Move endpoint + descendant refresh
# ---------------------------------------------------------------------------
class TestMoveCategory:
    def test_move_refreshes_subtree(self, api, admin_headers):
        # Build: A -> B -> C, and D (root). Move B under D, then verify C's path.
        a = _create_cat(api, admin_headers, f"{RUN_TAG}_A").json()
        b = _create_cat(api, admin_headers, f"{RUN_TAG}_B", a["id"]).json()
        c = _create_cat(api, admin_headers, f"{RUN_TAG}_C", b["id"]).json()
        d = _create_cat(api, admin_headers, f"{RUN_TAG}_D").json()

        # Move B under D
        r = api.post(f"{BASE_URL}/api/admin/categories/{b['id']}/move",
                     headers=admin_headers, json={"parent_id": d["id"]})
        assert r.status_code == 200, r.text
        moved = r.json()
        assert moved["parent_id"] == d["id"]
        assert moved["depth"] == 1
        assert moved["path"] == [d["id"]]

        # Now fetch C and confirm its path was refreshed
        bc = api.get(f"{BASE_URL}/api/categories/{c['id']}/breadcrumb")
        assert bc.status_code == 200, bc.text
        breadcrumb = bc.json()["breadcrumb"]
        # Expect: [D, B, C]
        ids_in_bc = [x["id"] for x in breadcrumb]
        assert ids_in_bc == [d["id"], b["id"], c["id"]], ids_in_bc

    def test_cycle_prevention(self, api, admin_headers):
        gp = _create_cat(api, admin_headers, f"{RUN_TAG}_cyc_gp").json()
        ch = _create_cat(api, admin_headers, f"{RUN_TAG}_cyc_ch", gp["id"]).json()
        # Try move gp under its own descendant ch → must fail
        r = api.post(f"{BASE_URL}/api/admin/categories/{gp['id']}/move",
                     headers=admin_headers, json={"parent_id": ch["id"]})
        assert r.status_code == 400, r.text
        assert "itself or a descendant" in r.text or "cycle" in r.text.lower()

    def test_self_parent_prevented(self, api, admin_headers):
        c = _create_cat(api, admin_headers, f"{RUN_TAG}_selfparent").json()
        r = api.post(f"{BASE_URL}/api/admin/categories/{c['id']}/move",
                     headers=admin_headers, json={"parent_id": c["id"]})
        assert r.status_code == 400, r.text

    def test_move_to_root(self, api, admin_headers):
        p = _create_cat(api, admin_headers, f"{RUN_TAG}_root_p").json()
        c = _create_cat(api, admin_headers, f"{RUN_TAG}_root_c", p["id"]).json()
        r = api.post(f"{BASE_URL}/api/admin/categories/{c['id']}/move",
                     headers=admin_headers, json={"parent_id": None})
        assert r.status_code == 200, r.text
        node = r.json()
        assert node["parent_id"] is None
        assert node["depth"] == 0
        assert node["path"] == []


# ---------------------------------------------------------------------------
# 6) Breadcrumb endpoint
# ---------------------------------------------------------------------------
def test_breadcrumb_l3(api, admin_headers):
    a = _create_cat(api, admin_headers, f"{RUN_TAG}_bc_A").json()
    b = _create_cat(api, admin_headers, f"{RUN_TAG}_bc_B", a["id"]).json()
    c = _create_cat(api, admin_headers, f"{RUN_TAG}_bc_C", b["id"]).json()
    d = _create_cat(api, admin_headers, f"{RUN_TAG}_bc_D", c["id"]).json()

    r = api.get(f"{BASE_URL}/api/categories/{d['id']}/breadcrumb")
    assert r.status_code == 200, r.text
    ids = [x["id"] for x in r.json()["breadcrumb"]]
    assert ids == [a["id"], b["id"], c["id"], d["id"]], ids


# ---------------------------------------------------------------------------
# 7) Force-delete cascade removes entire subtree
# ---------------------------------------------------------------------------
def test_force_delete_cascade(api, admin_headers, db):
    root = _create_cat(api, admin_headers, f"{RUN_TAG}_del_root").json()
    ch1 = _create_cat(api, admin_headers, f"{RUN_TAG}_del_ch1", root["id"]).json()
    ch2 = _create_cat(api, admin_headers, f"{RUN_TAG}_del_ch2", root["id"]).json()
    gc = _create_cat(api, admin_headers, f"{RUN_TAG}_del_gc", ch1["id"]).json()

    # Sanity: without force, refuses
    r_bad = api.delete(f"{BASE_URL}/api/admin/categories/{root['id']}",
                       headers=admin_headers)
    assert r_bad.status_code == 400, r_bad.text

    # Force delete
    r = api.delete(f"{BASE_URL}/api/admin/categories/{root['id']}?force=true",
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    # deleted_children should count ALL 3 descendants (subtree), not just direct
    assert body.get("deleted_children") == 3, body

    # Verify all 4 gone
    for cid in [root["id"], ch1["id"], ch2["id"], gc["id"]]:
        assert db.categories.count_documents({"id": cid}) == 0


# ---------------------------------------------------------------------------
# 8) PUT accepts parent_id (re-parent via update); name-only doesn't move
# ---------------------------------------------------------------------------
class TestPutReparent:
    def test_put_with_parent_id_reparents(self, api, admin_headers):
        a = _create_cat(api, admin_headers, f"{RUN_TAG}_putA").json()
        b = _create_cat(api, admin_headers, f"{RUN_TAG}_putB").json()
        c = _create_cat(api, admin_headers, f"{RUN_TAG}_putC", a["id"]).json()
        gc = _create_cat(api, admin_headers, f"{RUN_TAG}_putGC", c["id"]).json()

        # Move C from A to B via PUT
        r = api.put(f"{BASE_URL}/api/admin/categories/{c['id']}",
                    headers=admin_headers, json={"parent_id": b["id"]})
        assert r.status_code == 200, r.text
        assert r.json()["parent_id"] == b["id"]

        # Verify descendant GC's path was refreshed to [b, c]
        gc_bc = api.get(f"{BASE_URL}/api/categories/{gc['id']}/breadcrumb").json()
        ids = [x["id"] for x in gc_bc["breadcrumb"]]
        assert ids == [b["id"], c["id"], gc["id"]], ids

    def test_put_name_only_doesnt_move(self, api, admin_headers):
        p = _create_cat(api, admin_headers, f"{RUN_TAG}_nameA").json()
        ch = _create_cat(api, admin_headers, f"{RUN_TAG}_nameB", p["id"]).json()
        r = api.put(f"{BASE_URL}/api/admin/categories/{ch['id']}",
                    headers=admin_headers, json={"name": f"{RUN_TAG}_nameB_renamed"})
        assert r.status_code == 200, r.text
        assert r.json()["parent_id"] == p["id"]
        assert r.json()["depth"] == 1


# ---------------------------------------------------------------------------
# 9) Products regression
# ---------------------------------------------------------------------------
def test_products_list_regression(api):
    r = api.get(f"{BASE_URL}/api/products")
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, (list, dict))


def test_categories_tree_regression(api):
    r = api.get(f"{BASE_URL}/api/categories/tree")
    assert r.status_code == 200, r.text
    data = r.json()
    # Tree structure: either list of nodes with children[] or dict keyed by group
    def _has_children_field(nodes):
        for n in nodes:
            if "children" in n:
                return True
        return False
    if isinstance(data, list):
        assert _has_children_field(data) or len(data) == 0
    elif isinstance(data, dict):
        for grp, nodes in data.items():
            if nodes:
                assert isinstance(nodes, list)


# ---------------------------------------------------------------------------
# 10) Non-admin rejected (403)
# ---------------------------------------------------------------------------
class TestAdminGuard:
    def test_non_admin_create_forbidden(self, api, customer_ctx):
        r = api.post(f"{BASE_URL}/api/admin/categories",
                     headers=customer_ctx["headers"],
                     json={"name": f"{RUN_TAG}_forbidden", "group": "retail"})
        assert r.status_code == 403, r.text

    def test_non_admin_move_forbidden(self, api, customer_ctx, admin_headers):
        c = _create_cat(api, admin_headers, f"{RUN_TAG}_guard_move").json()
        r = api.post(f"{BASE_URL}/api/admin/categories/{c['id']}/move",
                     headers=customer_ctx["headers"], json={"parent_id": None})
        assert r.status_code == 403, r.text

    def test_non_admin_delete_forbidden(self, api, customer_ctx, admin_headers):
        c = _create_cat(api, admin_headers, f"{RUN_TAG}_guard_del").json()
        r = api.delete(f"{BASE_URL}/api/admin/categories/{c['id']}",
                       headers=customer_ctx["headers"])
        assert r.status_code == 403, r.text

    def test_non_admin_put_forbidden(self, api, customer_ctx, admin_headers):
        c = _create_cat(api, admin_headers, f"{RUN_TAG}_guard_put").json()
        r = api.put(f"{BASE_URL}/api/admin/categories/{c['id']}",
                    headers=customer_ctx["headers"], json={"name": "hi"})
        assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# 11) Section limit bumped to 20 — shop.product_sections
# ---------------------------------------------------------------------------
class TestSectionLimit20:
    @pytest.fixture(scope="class")
    def shop_id(self, api, seller_ctx):
        payload = {
            "name": f"{RUN_TAG}_Shop", "area": "Juba", "category": "gen",
            "delivery_mode": "free", "delivery_fee_usd": 0.0,
        }
        r = api.post(f"{BASE_URL}/api/shops", headers=seller_ctx["headers"], json=payload)
        assert r.status_code in (200, 201), r.text
        return r.json()["id"]

    def _shop_put(self, sections):
        return {
            "name": f"{RUN_TAG}_Shop", "area": "Juba",
            "delivery_mode": "free", "delivery_fee_usd": 0.0,
            "product_sections": sections,
        }

    def test_20_sections_accepted(self, api, seller_ctx, shop_id):
        sections = [{"id": f"p{i}", "name": f"Sec{i}", "sort_order": i} for i in range(20)]
        r = api.put(f"{BASE_URL}/api/shops/{shop_id}", headers=seller_ctx["headers"],
                    json=self._shop_put(sections))
        assert r.status_code == 200, r.text
        assert len(r.json()["product_sections"]) == 20

    def test_21_sections_rejected(self, api, seller_ctx, shop_id):
        sections = [{"id": f"p{i}", "name": f"Sec{i}", "sort_order": i} for i in range(21)]
        r = api.put(f"{BASE_URL}/api/shops/{shop_id}", headers=seller_ctx["headers"],
                    json=self._shop_put(sections))
        assert r.status_code == 400, r.text
        assert "20" in r.text
        assert "section" in r.text.lower()


# ---------------------------------------------------------------------------
# 12) Section limit 20 — restaurant.menu_sections
# ---------------------------------------------------------------------------
class TestRestaurantSectionLimit20:
    @pytest.fixture(scope="class")
    def restaurant_id(self, db, seller_ctx):
        rid = f"{RUN_TAG}_rest_main"
        db.restaurants.insert_one({
            "id": rid, "seller_id": seller_ctx["id"],
            "name": f"{RUN_TAG}_Rest", "area": "Juba",
            "is_open": True, "is_deleted": False,
            "verification": "Verified",
            "delivery_managed_by": "seller",
            "delivery_mode": "free", "delivery_fee_usd": 0.0,
            "menu_sections": [],
            "created_at": _now(),
        })
        return rid

    def _rest_put(self, sections):
        return {
            "name": f"{RUN_TAG}_Rest", "area": "Juba",
            "is_open": True, "delivery_mode": "free", "delivery_fee_usd": 0.0,
            "menu_sections": sections,
        }

    def test_20_menu_sections_ok(self, api, seller_ctx, restaurant_id):
        sections = [{"id": f"m{i}", "name": f"MSec{i}", "sort_order": i} for i in range(20)]
        r = api.put(f"{BASE_URL}/api/restaurants/{restaurant_id}",
                    headers=seller_ctx["headers"], json=self._rest_put(sections))
        assert r.status_code == 200, r.text
        assert len(r.json()["menu_sections"]) == 20

    def test_21_menu_sections_rejected(self, api, seller_ctx, restaurant_id):
        sections = [{"id": f"m{i}", "name": f"MSec{i}", "sort_order": i} for i in range(21)]
        r = api.put(f"{BASE_URL}/api/restaurants/{restaurant_id}",
                    headers=seller_ctx["headers"], json=self._rest_put(sections))
        assert r.status_code == 400, r.text
        assert "20" in r.text
        assert "section" in r.text.lower()
