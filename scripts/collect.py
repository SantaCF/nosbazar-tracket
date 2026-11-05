"""Fetch every bazaar listing for the tracked items on one NosTale server and save them.

Writes:
  data/listings/YYYY-MM-DD/HHMM.csv.gz  every listing seen in the run, identical listings
                                       grouped with a count (for sale/vanish analysis)
  data/summary.csv              one row per item per run (count, quantity, min/p20/median/p80/max)
  data/prices.csv              one row per item per run with quantity-weighted reference prices
  data/items_resolved.json      which items each search line matched
"""
import collections, csv, gzip, json, os, statistics, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

API = "https://nosbazar.com/api"
SERVER = int(os.environ.get("NOS_SERVER", "1"))  # 1 = EU-Dragonveil
UA = "nosbazar-tracker (personal price history, github.com/SantaCF/nosbazar-tracket)"
PAGE = 30
MAX_PAGES = 100
MAX_MATCHES = 5


def call(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, headers={"User-Agent": UA, "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # network hiccup: retry with backoff
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    time.sleep(1)


def resolve(query):
    if query.isdigit():  # a vnum written directly in config/items.txt
        names = call(f"/items/static/{query}").get("name", {})
        return [{"vnum": int(query), "name": names.get("IT") or names.get("UK") or query}]
    res = call("/items/name-search?" + urllib.parse.urlencode({"q": query, "lang": "IT"}))
    return [{"vnum": m["vnum"], "name": m["name"]} for m in res.get("matches", [])][:MAX_MATCHES]


def search(name, vnum):
    out = []
    for page in range(MAX_PAGES):
        body = {"server": SERVER, "filters": {"index": page, "category": 0, "sub_category": 0, "level": 0,
                "rare": 0, "upgrade": 0, "order": 0, "vnum": []}, "lang": "IT", "name": name}
        items = call("/search", body).get("items", [])
        out += [i for i in items if i.get("item_vnum") == vnum]
        time.sleep(1)
        if len(items) < PAGE:
            break
    return out


def pct(sorted_vals, p):
    if not sorted_vals:
        return ""
    k = (len(sorted_vals) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo))


LOT = 1000  # units for the "cost to buy a lot" metric


def wpct(rows, p):
    """Quantity-weighted percentile: the price below which a share p of all listed units sit.
    A single cheap listing of 1 unit cannot move it, unlike the plain minimum."""
    rows = sorted(rows, key=lambda r: r["bazar_price"])
    total = sum(r.get("amount", 0) for r in rows)
    if not total:
        return ""
    target, seen = total * p, 0
    for r in rows:
        seen += r.get("amount", 0)
        if seen >= target:
            return r["bazar_price"]
    return rows[-1]["bazar_price"]


def lot_cost(rows, lot=LOT):
    """Average unit price paid to buy the cheapest `lot` units on sale."""
    left, spent = lot, 0
    for r in sorted(rows, key=lambda r: r["bazar_price"]):
        take = min(left, r.get("amount", 0))
        spent += take * r["bazar_price"]
        left -= take
        if not left:
            return round(spent / lot)
    return round(spent / (lot - left)) if lot > left else ""


def price_row(ts, vnum, name, rows):
    prices = [r["bazar_price"] for r in rows]
    return [ts, vnum, name, len(rows), sum(r.get("amount", 0) for r in rows), min(prices) if prices else "",
            wpct(rows, .05), wpct(rows, .10), wpct(rows, .25), wpct(rows, .50), lot_cost(rows)]


PRICE_HEADER = ["ts", "vnum", "name", "listings", "quantity", "min", "wp05", "wp10", "wp25", "wmedian", "lot1000"]


def main():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    ts = now.isoformat()
    queries = [l.strip() for l in open("config/items.txt", encoding="utf-8") if l.strip() and not l.startswith("#")]
    os.makedirs("data/listings", exist_ok=True)

    resolved, items = {}, {}
    for q in queries:
        try:
            resolved[q] = resolve(q)
        except Exception as e:
            print(f"name-search failed for {q!r}: {e}", file=sys.stderr)
            resolved[q] = []
        for m in resolved[q]:
            items[m["vnum"]] = m["name"]
        time.sleep(1)
    json.dump(resolved, open("data/items_resolved.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    os.makedirs(f"data/listings/{now:%Y-%m-%d}", exist_ok=True)
    lpath = f"data/listings/{now:%Y-%m-%d}/{now:%H%M}.csv.gz"
    spath = "data/summary.csv"
    new_s = not os.path.exists(spath)
    ppath = "data/prices.csv"
    new_p = not os.path.exists(ppath)
    with gzip.open(lpath, "wt", newline="", encoding="utf-8") as lf, open(spath, "a", newline="", encoding="utf-8") as sf, \
            open(ppath, "a", newline="", encoding="utf-8") as pf:
        lw, sw, pw = csv.writer(lf), csv.writer(sf), csv.writer(pf)
        if new_p:
            pw.writerow(PRICE_HEADER)
        lw.writerow(["ts", "vnum", "owner", "amount", "price", "minutes_left", "is_package", "count"])
        if new_s:
            sw.writerow(["ts", "vnum", "name", "listings", "quantity", "min", "p20", "median", "p80", "max"])
        for vnum, name in items.items():
            try:
                rows = search(name, vnum)
            except Exception as e:
                print(f"search failed for {name}: {e}", file=sys.stderr)
                continue
            groups = collections.Counter((r.get("owner_name"), r.get("amount"), r.get("bazar_price"),
                                          r.get("minutes_left"), int(bool(r.get("is_package")))) for r in rows)
            for key, n in sorted(groups.items(), key=lambda kv: kv[0][2]):
                lw.writerow([ts, vnum, *key, n])
            pw.writerow(price_row(ts, vnum, name, rows))
            prices = sorted(r["bazar_price"] for r in rows)
            qty = sum(r.get("amount", 0) for r in rows)
            sw.writerow([ts, vnum, name, len(rows), qty, prices[0] if prices else "", pct(prices, .2),
                         pct(prices, .5), pct(prices, .8), prices[-1] if prices else ""])
            print(f"{name} ({vnum}): {len(rows)} annunci, {qty} pezzi, min {prices[0] if prices else '-'}")


if __name__ == "__main__":
    main()
