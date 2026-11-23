import json, urllib.parse, urllib.request
UA = "nosbazar-tracker (personal price history, github.com/SantaCF/nosbazar-tracket)"
for q in ["ricostituente divina", "Pozione ricostituente"]:
    u = "https://nosbazar.com/api/items/name-search?" + urllib.parse.urlencode({"q": q, "lang": "IT"})
    r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=60))
    print("TROVATO", q, "=>", [(m["vnum"], m["name"]) for m in r.get("matches", [])], flush=True)
