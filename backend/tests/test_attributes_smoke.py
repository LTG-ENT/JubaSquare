import os, sys, requests, json, uuid

API = None
for line in open("/app/frontend/.env"):
    if line.startswith("REACT_APP_BACKEND_URL="):
        API = line.strip().split("=", 1)[1] + "/api"
assert API

def check(name, cond, extra=""):
    print(("PASS" if cond else "FAIL"), name, extra)
    if not cond:
        sys.exit(1)

tok = requests.post(f"{API}/auth/login", json={"email": "admin@jubasquare.com", "password": "1234"}).json()["token"]
H = {"Authorization": f"Bearer {tok}"}

# find Electronics child category
tree = requests.get(f"{API}/categories/tree?group=retail").json()
elec = next(t for t in tree if t["name"].lower().startswith("electronics"))
child = elec["children"][0]

# create temp shop (admin acts as seller)
shop = requests.post(f"{API}/shops", json={"name": f"AttrTest Shop {uuid.uuid4().hex[:6]}", "area": "Munuki", "category": "Electronics"}, headers=H).json()
check("shop created", "id" in shop, str(shop)[:120])

# 1. create product with valid attributes
p = requests.post(f"{API}/products", json={
    "shop_id": shop["id"], "name": "Attr Phone X", "category_id": child["id"],
    "price_usd": 199.0, "stock": 5,
    "attributes": {"brand": "Samsung", "storage": "256GB", "ram": "8GB", "color": "Black", "model": "Galaxy S24", "bogus_key": "x"},
}, headers=H)
check("product create w/ attrs", p.status_code == 200, p.text[:200])
prod = p.json()
check("unknown key dropped", "bogus_key" not in prod["attributes"], str(prod["attributes"]))
check("values stored", prod["attributes"].get("brand") == "Samsung")

# 2. invalid dropdown value rejected
bad = requests.post(f"{API}/products", json={
    "shop_id": shop["id"], "name": "Bad Phone", "category_id": child["id"],
    "price_usd": 10, "attributes": {"storage": "999TB"}}, headers=H)
check("invalid option rejected 400", bad.status_code == 400, bad.text[:120])

# 3. restaurant category rejected for product
rest_tree = requests.get(f"{API}/categories/tree?group=restaurant").json()
bad2 = requests.post(f"{API}/products", json={
    "shop_id": shop["id"], "name": "Wrong BT", "category_id": rest_tree[0]["id"], "price_usd": 5}, headers=H)
check("restaurant category rejected for product", bad2.status_code == 400, bad2.text[:120])

# 4. facets for parent Electronics include child product values (subtree)
fac = requests.get(f"{API}/attributes/facets", params={"category_id": elec["id"]}).json()
brands = next((f for f in fac["facets"] if f["key"] == "brand"), None)
check("facets subtree includes child product", brands and any(v["value"] == "Samsung" for v in brands["values"]), json.dumps(fac)[:200])

# 5. /products attrs filter + include_descendants (shop_id targeting bypasses verification gate; test both)
r = requests.get(f"{API}/products", params={"shop_id": shop["id"], "attrs": json.dumps({"brand": ["Samsung"]})}).json()
check("attrs filter matches", any(x["id"] == prod["id"] for x in r), f"{len(r)} results")
r2 = requests.get(f"{API}/products", params={"shop_id": shop["id"], "attrs": json.dumps({"brand": ["Apple"]})}).json()
check("attrs filter excludes", not any(x["id"] == prod["id"] for x in r2))
r3 = requests.get(f"{API}/products", params={"shop_id": shop["id"], "category_id": elec["id"], "include_descendants": "true"}).json()
check("include_descendants finds child product", any(x["id"] == prod["id"] for x in r3))
r4 = requests.get(f"{API}/products", params={"shop_id": shop["id"], "category_id": elec["id"]}).json()
check("without include_descendants excludes", not any(x["id"] == prod["id"] for x in r4))

# 6. required attribute enforcement
attr = requests.post(f"{API}/admin/attributes", json={
    "name": f"Warranty {uuid.uuid4().hex[:4]}", "type": "dropdown", "business_type": "retail",
    "options": ["6 months", "1 year"], "category_ids": [child["id"]], "required": True}, headers=H)
check("required attr created", attr.status_code == 200, attr.text[:150])
attr = attr.json()
miss = requests.post(f"{API}/products", json={
    "shop_id": shop["id"], "name": "Missing Req", "category_id": child["id"], "price_usd": 9, "attributes": {}}, headers=H)
check("missing required rejected", miss.status_code == 400, miss.text[:120])

# 7. exclusion (remove inherited attribute on child)
ex = requests.post(f"{API}/admin/categories/{child['id']}/excluded-attributes/{attr['id']}", headers=H)
check("exclude ok", ex.status_code == 200)
eff = requests.get(f"{API}/categories/{child['id']}/attributes").json()
check("excluded attr gone", not any(a["id"] == attr["id"] for a in eff["attributes"]))
ok_now = requests.post(f"{API}/products", json={
    "shop_id": shop["id"], "name": "No Req After Exclude", "category_id": child["id"], "price_usd": 9}, headers=H)
check("create ok after exclusion", ok_now.status_code == 200, ok_now.text[:120])
requests.delete(f"{API}/admin/categories/{child['id']}/excluded-attributes/{attr['id']}", headers=H)

# 8. attribute move business type clears categories
mv = requests.put(f"{API}/admin/attributes/{attr['id']}", json={"business_type": "wholesale"}, headers=H).json()
check("moved to wholesale, cats cleared", mv["business_type"] == "wholesale" and mv["category_ids"] == [])

# 9. groups CRUD
g = requests.post(f"{API}/admin/attribute-groups", json={"name": f"TestGrp {uuid.uuid4().hex[:4]}", "business_type": "retail"}, headers=H).json()
check("group created", "id" in g)
ren = requests.put(f"{API}/admin/attribute-groups/{g['id']}", json={"name": g["name"] + " R"}, headers=H).json()
check("group renamed", ren["name"].endswith(" R"))
check("group deleted", requests.delete(f"{API}/admin/attribute-groups/{g['id']}", headers=H).status_code == 200)

# 10. menu-item attributes (restaurant business type)
rest = requests.post(f"{API}/restaurants", json={"name": f"AttrTest Rest {uuid.uuid4().hex[:6]}", "area": "Munuki"}, headers=H).json()
check("restaurant created", "id" in rest, str(rest)[:120])
mi = requests.post(f"{API}/menu-items", json={
    "restaurant_id": rest["id"], "name": "Spicy Wings", "price_usd": 7.5,
    "category_id": rest_tree[0]["id"],
    "attributes": {"spice_level": "Hot", "dietary_type": ["Halal"], "portion_size": "Large"}}, headers=H)
check("menu item w/ attrs", mi.status_code == 200 and mi.json()["attributes"]["spice_level"] == "Hot", mi.text[:200])

# 11. update product edit path preserves attrs validation
upd = requests.put(f"{API}/products/{prod['id']}", json={
    "shop_id": shop["id"], "name": prod["name"], "category_id": child["id"], "price_usd": 189.0,
    "attributes": {"brand": "Apple", "storage": "128GB"}}, headers=H)
check("product update attrs", upd.status_code == 200 and upd.json()["attributes"]["brand"] == "Apple", upd.text[:150])

# cleanup
requests.delete(f"{API}/admin/attributes/{attr['id']}", headers=H)
for x in requests.get(f"{API}/products", params={"shop_id": shop["id"], "limit": 50}).json():
    requests.delete(f"{API}/products/{x['id']}", headers=H)
requests.delete(f"{API}/menu-items/{mi.json()['id']}", headers=H)
requests.delete(f"{API}/shops/{shop['id']}", headers=H)
requests.delete(f"{API}/restaurants/{rest['id']}", headers=H)
print("ALL BACKEND ATTRIBUTE TESTS PASSED ✅")
