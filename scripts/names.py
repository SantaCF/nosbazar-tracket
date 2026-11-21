import json, time, urllib.request
UA = "nosbazar-tracker (personal price history, github.com/SantaCF/nosbazar-tracket)"
def go(path, body=None):
    t = time.time()
    try:
        req = urllib.request.Request("https://nosbazar.com/api" + path, data=json.dumps(body).encode() if body else None, headers={"User-Agent": UA, "Content-Type": "application/json"})
        r = urllib.request.urlopen(req, timeout=30); txt = r.read().decode()[:300]
        print(path, r.status, round(time.time() - t, 1), "s", txt[:200], flush=True)
    except Exception as e:
        print(path, "ERR", round(time.time() - t, 1), "s", e, getattr(e, "read", lambda: b"")()[:300], flush=True)
go("/servers")
for v in (1013, 1029, 2200):
    go("/search", {"server": 1, "filters": {"index": 0, "category": 0, "sub_category": 0, "level": 0, "rare": 0, "upgrade": 0, "order": 0, "vnum": [v]}, "lang": "IT", "name": ""})
go("/items/static/1013")
