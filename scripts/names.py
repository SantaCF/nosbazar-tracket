import json, time, urllib.request
UA = "nosbazar-tracker (personal price history, github.com/SantaCF/nosbazar-tracket)"
def call(body):
    return json.load(urllib.request.urlopen(urllib.request.Request("https://nosbazar.com/api/search", data=json.dumps(body).encode(), headers={"User-Agent": UA, "Content-Type": "application/json"}), timeout=30))
def run(name, vnum, by_vnum):
    out, pages = [], 0
    for page in range(100):
        b = {"server": 1, "filters": {"index": page, "category": 0, "sub_category": 0, "level": 0, "rare": 0, "upgrade": 0, "order": 0, "vnum": [vnum] if by_vnum else []}, "lang": "IT", "name": "" if by_vnum else name}
        it = call(b).get("items", []); pages += 1
        out += [i for i in it if i.get("item_vnum") == vnum]
        time.sleep(1)
        if len(it) < 30: break
    return pages, len(out), sum(i["amount"] for i in out)
for name, v in [("Ago", 2200), ("Gillion", 1013), ("Cristallo di luna piena", 1030), ("Giocherellone", 9356), ("Pozione del recupero degli SpP base", 1245), ("Mela", 2206)]:
    for bv in (False, True):
        t = time.time()
        print(name, v, "vnum" if bv else "nome", run(name, v, bv), round(time.time() - t), "s", flush=True)
