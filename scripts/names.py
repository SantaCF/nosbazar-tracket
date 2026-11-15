import json, time, urllib.parse, urllib.request
UA = "nosbazar-tracker (personal price history, github.com/SantaCF/nosbazar-tracket)"
Q = ["Metallo raro", "Legno raro", "Stoffa rara", "Pelle rara", "Metallo leggendario", "Pelle leggendaria",
     "Giocherellone", "Ago", "Gemma nera", "Verme", "Mithrill", "Foglia rara", "Ascia", "Punta di spada",
     "Oriharcon", "Martello", "Freccia contaminata"]
for q in Q:
    u = "https://nosbazar.com/api/items/name-search?" + urllib.parse.urlencode({"q": q, "lang": "IT"})
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30))
        print(q, "=>", [(m["vnum"], m["name"]) for m in r.get("matches", [])][:12], flush=True)
    except Exception as e:
        print(q, "ERR", e, flush=True)
    time.sleep(1)
