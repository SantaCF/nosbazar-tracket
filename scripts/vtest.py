"""Prova: la ricerca con filtro vnum dà gli stessi annunci della ricerca per nome, con meno pagine?"""
import json, time, urllib.request

API = "https://nosbazar.com/api"
UA = "nosbazar-tracker (personal price history, github.com/SantaCF/nosbazar-tracket)"
resolved = json.load(open("data/items_resolved.json", encoding="utf-8"))
items = {}
for ms in resolved.values():
    for m in ms:
        items[m["vnum"]] = m["name"]


def call(body):
    req = urllib.request.Request(API + "/search", data=json.dumps(body).encode(),
                                 headers={"User-Agent": UA, "Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r), time.time() - t


def run(name, vnum, vf):
    out, pages, lat = [], 0, 0.0
    for page in range(100):
        body = {"server": 1, "filters": {"index": page, "category": 0, "sub_category": 0, "level": 0, "rare": 0,
                "upgrade": 0, "order": 0, "vnum": vf}, "lang": "IT", "name": name}
        res, dt = call(body)
        it = res.get("items", [])
        pages += 1; lat += dt
        out += [i for i in it if i.get("item_vnum") == vnum]
        time.sleep(1)
        if len(it) < 30:
            break
    key = sorted((i.get("owner_name"), i.get("amount"), i.get("bazar_price")) for i in out)
    return pages, lat, len(out), key


tot = {"name": [0, 0.0], "vnum": [0, 0.0]}
for vnum, name in items.items():
    a = run(name, vnum, [])
    b = run(name, vnum, [vnum])
    c = run("", vnum, [vnum])
    tot["name"][0] += a[0]; tot["name"][1] += a[1]
    tot["vnum"][0] += c[0]; tot["vnum"][1] += c[1]
    print(f"{vnum} {name}: nome {a[0]}p {a[2]} ann | nome+vnum {b[0]}p {b[2]} uguale={a[3] == b[3]} | "
          f"solo vnum {c[0]}p {c[2]} uguale={a[3] == c[3]} | lat media {a[1] / a[0]:.2f}s", flush=True)
print("TOTALE", tot, flush=True)
