"""One-off: page through the whole bazaar (no name filter) and rank items by number of listings."""
import collections, json, statistics, sys, time, urllib.request
API, UA = "https://nosbazar.com/api", "nosbazar-tracker (personal price history, github.com/SantaCF/nosbazar-tracket)"
def call(path, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None, headers={"User-Agent": UA, "Content-Type": "application/json"})
    for a in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
        except Exception as e:
            if a == 2: print("ERR", path, e); return {}
            time.sleep(5)
by = collections.defaultdict(list)
cat_of = {}
for cat in range(0, 13) if "--cats" in sys.argv else [0]:
    n = 0
    for page in range(4000):
        res = call("/search", {"server": 1, "filters": {"index": page, "category": cat, "sub_category": 0, "level": 0, "rare": 0, "upgrade": 0, "order": 0, "vnum": []}, "lang": "IT", "name": ""})
        items = res.get("items", [])
        if page == 0: print("cat", cat, "keys", sorted(res.keys()), items[0] if items else None, flush=True)
        for i in items:
            if cat == 0: by[i["item_vnum"]].append((i["bazar_price"], i["amount"]))
            else: cat_of.setdefault(i["item_vnum"], cat)
        n += len(items)
        time.sleep(0.4)
        if len(items) < 30: break
    print("cat", cat, "pages", page + 1, "listings", n, flush=True)
rows = []
for v, l in by.items():
    med = statistics.median(p for p, _ in l)
    rows.append((len(l), sum(a for _, a in l), med, v))
rows.sort(reverse=True)
print("items", len(rows))
for cnt, units, med, v in rows[:250]:
    st = call(f"/items/static/{v}"); time.sleep(0.3)
    if v == rows[0][3]: print("static keys", json.dumps(st)[:600])
    nm = (st.get("name") or {}).get("IT") or (st.get("name") or {}).get("UK")
    print(f"{v}\t{nm}\t{cnt}\t{units}\t{round(med)}\t{round(med*units/1e6,1)}M\tcat={cat_of.get(v,'')}", flush=True)
