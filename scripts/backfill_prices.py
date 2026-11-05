"""Rebuild data/prices.csv from the saved listings (data/listings/*/*.csv.gz)."""
import csv, glob, gzip, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from collect import PRICE_HEADER, price_row

names = {}
for matches in json.load(open("data/items_resolved.json", encoding="utf-8")).values():
    for m in matches:
        names[m["vnum"]] = m["name"]
out = [PRICE_HEADER]
for path in sorted(glob.glob("data/listings/*/*.csv.gz")):
    groups = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            row = {"bazar_price": int(r["price"]), "amount": int(r["amount"])}
            groups.setdefault((r["ts"], int(r["vnum"])), []).extend([row] * int(r["count"]))
    for (ts, vnum), rows in groups.items():
        out.append(price_row(ts, vnum, names.get(vnum, str(vnum)), rows))
with open("data/prices.csv", "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(out)
print(len(out) - 1, "rows")
