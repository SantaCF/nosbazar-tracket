"""Fetch every bazaar listing for the tracked items on one NosTale server and save them.

Writes:
  data/listings/YYYY-MM-DD/HHMM.csv.gz  every listing seen in the run, identical listings
                                       grouped with a count (for sale/vanish analysis)
  data/summary.csv              one row per item per run (count, quantity, min/p20/median/p80/max)
  data/prices.csv              one row per item per run with quantity-weighted reference prices
  data/latest.csv               only the last run's rows of prices.csv (read by the Google Sheet calculator)
  data/items_resolved.json      which items each search line matched
"""
import collections, concurrent.futures, csv, gzip, json, os, statistics, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

API = "https://nosbazar.com/api"
SERVER = int(os.environ.get("NOS_SERVER", "1"))  # 1 = EU-Dragonveil
UA = "nosbazar-tracker (personal price history, github.com/SantaCF/nosbazar-tracket)"
PAGE = 30
MAX_PAGES = 100
MAX_MATCHES = 5
# Item cercati in parallelo. Ogni pagina di nosbazar risponde in ~1,7 s (di sera anche di più): uno per volta il giro
# arrivava a 20 minuti e veniva interrotto (09/11). Ogni ricerca resta di una pagina al secondo, come prima.
WORKERS = int(os.environ.get("NOS_WORKERS", "4"))


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


LOT_SHARE = 0.02  # default lot = 2% of all units on sale, so the lot scales with how mass-produced an item is


def read_config(path="config/items.txt"):
    """Return [(query, lot_override_or_None)]. A line may end with "| <units>" to fix the lot size."""
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        query, _, lot = line.partition("|")
        lot = lot.strip().replace(".", "")
        out.append((query.strip(), int(lot) if lot.isdigit() else None))
    return out


def lot_overrides(config, resolved):
    """Map vnum -> fixed lot size, using the search results saved for each config line."""
    out = {}
    for query, lot in config:
        if lot:
            for m in resolved.get(query, []):
                out[m["vnum"]] = lot
    return out


def lot_size(rows, override=None):
    total = sum(r.get("amount", 0) for r in rows)
    return override or max(1, round(total * LOT_SHARE))


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


def lot_cost(rows, lot):
    """Average unit price paid to buy the cheapest `lot` units on sale."""
    left, spent = lot, 0
    for r in sorted(rows, key=lambda r: r["bazar_price"]):
        take = min(left, r.get("amount", 0))
        spent += take * r["bazar_price"]
        left -= take
        if not left:
            return round(spent / lot)
    return round(spent / (lot - left)) if lot > left else ""


def price_row(ts, vnum, name, rows, override=None):
    prices = [r["bazar_price"] for r in rows]
    lot = lot_size(rows, override)
    return [ts, vnum, name, len(rows), sum(r.get("amount", 0) for r in rows), min(prices) if prices else "",
            wpct(rows, .05), wpct(rows, .10), wpct(rows, .25), wpct(rows, .50), lot, lot_cost(rows, lot) if rows else ""]


PRICE_HEADER = ["ts", "vnum", "name", "listings", "quantity", "min", "wp05", "wp10", "wp25", "wmedian", "lot_size", "lot_price"]


def main():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    ts = now.isoformat()
    config = read_config()
    queries = [q for q, _ in config]
    os.makedirs("data/listings", exist_ok=True)

    # Nomi -> vnum: riuso quelli del giro precedente (data/items_resolved.json) e cerco solo le righe nuove o
    # rimaste vuote. Una volta al giorno (giro tra le 03:00 e le 03:14 UTC) li ricerco tutti. Risparmia ~2-3 minuti a giro.
    try:
        cache = json.load(open("data/items_resolved.json", encoding="utf-8"))
    except Exception:
        cache = {}
    refresh = now.hour == 3 and now.minute < 15
    resolved, items = {}, {}
    for q in queries:
        if not refresh and cache.get(q):
            resolved[q] = cache[q]
        else:
            try:
                resolved[q] = resolve(q)
            except Exception as e:
                print(f"name-search failed for {q!r}: {e}", file=sys.stderr)
                resolved[q] = cache.get(q, [])
            time.sleep(1)
        for m in resolved[q]:
            items[m["vnum"]] = m["name"]
    json.dump(resolved, open("data/items_resolved.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    # L'ora del giro la prendo adesso, dopo la ricerca dei nomi: con minutes_left fa la scadenza di ogni annuncio, e se la
    # ricerca dei nomi è lunga (refresh delle 03:00, righe nuove in items.txt) le scadenze slitterebbero di qualche minuto
    # rispetto agli altri giri e sales.py conterebbe come vendute migliaia di annunci rimasti al loro posto (07/11 03:01).
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    overrides = lot_overrides(config, resolved)

    os.makedirs(f"data/listings/{now:%Y-%m-%d}", exist_ok=True)
    lpath = f"data/listings/{now:%Y-%m-%d}/{now:%H%M}.csv.gz"
    spath = "data/summary.csv"
    new_s = not os.path.exists(spath)
    ppath = "data/prices.csv"
    new_p = not os.path.exists(ppath)
    latest = []
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS)
    found = {vnum: pool.submit(search, name, vnum) for vnum, name in items.items()}
    pool.shutdown(wait=True)
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
                rows = found[vnum].result()
            except Exception as e:
                print(f"search failed for {name}: {e}", file=sys.stderr)
                continue
            groups = collections.Counter((r.get("owner_name"), r.get("amount"), r.get("bazar_price"),
                                          r.get("minutes_left"), int(bool(r.get("is_package")))) for r in rows)
            for key, n in sorted(groups.items(), key=lambda kv: kv[0][2]):
                lw.writerow([ts, vnum, *key, n])
            prow = price_row(ts, vnum, name, rows, overrides.get(vnum))
            pw.writerow(prow)
            latest.append(prow)
            prices = sorted(r["bazar_price"] for r in rows)
            qty = sum(r.get("amount", 0) for r in rows)
            sw.writerow([ts, vnum, name, len(rows), qty, prices[0] if prices else "", pct(prices, .2),
                         pct(prices, .5), pct(prices, .8), prices[-1] if prices else ""])
            print(f"{name} ({vnum}): {len(rows)} annunci, {qty} pezzi, min {prices[0] if prices else '-'}")
    if latest:
        with open("data/latest.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(PRICE_HEADER)
            w.writerows(latest)


if __name__ == "__main__":
    main()
