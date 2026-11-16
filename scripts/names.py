import json, time, urllib.parse, urllib.request
UA = "nosbazar-tracker (personal price history, github.com/SantaCF/nosbazar-tracket)"
Q = ["Carpa", "Pesce", "Ago", "Sgombro", "Balena"]
seen = {}
for q in Q:
    u = "https://nosbazar.com/api/items/name-search?" + urllib.parse.urlencode({"q": q, "lang": "IT"})
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30))
        ms = [(m["vnum"], m["name"]) for m in r.get("matches", [])]
        print(q, "=>", ms[:40], flush=True)
        for v, n in ms[:40]: seen[v] = n
    except Exception as e:
        print(q, "ERR", e, flush=True)
    time.sleep(1)
for v in list(seen):
    body = json.dumps({"server": 1, "filters": {"index": 0, "category": 0, "sub_category": 0, "level": 0, "rare": 0, "upgrade": 0, "order": 0, "vnum": [v]}, "lang": "IT", "name": ""}).encode()
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request("https://nosbazar.com/api/search", data=body, headers={"User-Agent": UA, "Content-Type": "application/json"}), timeout=30))
        it = [x for x in r.get("items", []) if x["item_vnum"] == v]
        p = sorted(x["bazar_price"] for x in it)
        print("LIST", v, seen.get(v, ""), "annunci", len(it), "pezzi", sum(x["amount"] for x in it), "prezzi", p[:8], flush=True)
    except Exception as e:
        print("LIST", v, "ERR", e, flush=True)
    time.sleep(1)
