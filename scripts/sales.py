"""Estimate units sold between two consecutive bazaar snapshots.

A listing is identified by item, seller, unit price, package flag and expiry time
(snapshot time + minutes_left, stable within a couple of minutes). Units that vanish
before the listing's expiry were sold or withdrawn by the seller. A whole listing that
vanishes while the same seller lists the same quantity at a lower price in the same run is a
price cut and is not counted; the same quantity at the same or a higher price is new stock
(someone who produces and relists continuously) and the vanished one counts as sold. Partial
decreases of a listing are always sales.

    python3 scripts/sales.py          # add the snapshot pairs newer than the last saved row
    python3 scripts/sales.py --all    # rebuild data/sales.csv from every snapshot

Output data/sales.csv: ts, prev_ts, minutes, vnum, name, units_gone, listings_gone,
value_gone, wavg_price, max_price, units_raw (every unit that vanished, price changes included),
units_under (units newly listed at or below the previous minimum +1%: they go ahead of the existing queue).
Output data/owners/YYYY-MM-DD.csv: ts, vnum, owner, units, value (sales per seller, used by the
Bilancio page for your own sales and for competition).
Adds sold_day (clean) and sold_day_raw (every vanished unit) to data/latest.csv.
"""
import collections, csv, glob, gzip, json, os, sys
from datetime import datetime, timedelta

MAX_GAP_MIN = 40       # larger gaps: too much can happen in between, skip
TOL_MIN = 3            # expiry-time tolerance when matching a listing
OUT = "data/sales.csv"
HEADER = ["ts", "prev_ts", "minutes", "vnum", "name", "units_gone", "listings_gone", "value_gone", "wavg_price", "max_price", "units_raw", "units_under"]
OWN_DIR = "data/owners"
OWN_HEADER = ["ts", "vnum", "owner", "units", "value"]


def load(path):
    rows = collections.defaultdict(list)   # (vnum, owner, price, pkg) -> [(expiry_min, amount), ...]
    ts = None
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ts = ts or datetime.fromisoformat(r["ts"])
            t0 = datetime.fromisoformat(r["ts"])
            exp = t0.timestamp() / 60 + int(r["minutes_left"] or 0)
            key = (int(r["vnum"]), r["owner"], int(r["price"]), r["is_package"])
            for _ in range(int(r["count"] or 1)):
                rows[key].append([exp, int(r["amount"] or 0)])
    return ts, rows


def compare(prev, cur, names):
    """Return (rows for sales.csv, rows for data/owners/DAY.csv) for one pair of runs."""
    (pts, p), (cts, c) = prev, cur
    minutes = (cts - pts).total_seconds() / 60
    if minutes <= 0 or minutes > MAX_GAP_MIN:
        return [], []
    now = cts.timestamp() / 60
    seen = {k[0] for k in c}               # items searched successfully in the current run
    # Listings that appeared in this run, per seller and size: (vnum, owner, amount) -> [prices].
    new = collections.defaultdict(list)
    # Units listed in this run at or below the previous run's minimum (+1%): they jump the queue ahead of
    # everyone already listed, so they eat the demand left for those listings ("units_under").
    pmin = {}
    for key in p:
        if key[0] in seen:
            pmin[key[0]] = min(pmin.get(key[0], key[2]), key[2])
    under = collections.Counter()
    for key, lst in c.items():
        old = [x[0] for x in p.get(key, [])]
        for exp, amt in lst:
            if not any(abs(exp - e) <= TOL_MIN for e in old):
                new[(key[0], key[1], amt)].append(key[2])
                if key[0] in pmin and key[2] <= pmin[key[0]] * 1.01:
                    under[key[0]] += amt
    gone = collections.defaultdict(lambda: [0, 0, 0, 0, 0])   # vnum -> units, listings, value, max price, raw units
    owners = collections.defaultdict(lambda: [0, 0])           # (vnum, owner) -> units, value
    for key, lst in p.items():
        vnum, owner, price = key[0], key[1], key[2]
        if vnum not in seen:
            continue
        pool = [x[:] for x in c.get(key, [])]
        # Largest listings first, each matched to the unchanged copy if there is one,
        # otherwise to the biggest remainder (partial sale): avoids pairing the wrong copies.
        for exp, amt in sorted(lst, key=lambda x: -x[1]):
            if exp <= now + 1:              # expired naturally
                continue
            cands = [x for x in pool if abs(x[0] - exp) <= TOL_MIN and x[1] <= amt]
            match = max(cands, key=lambda x: (x[1] == amt, x[1]), default=None)
            left = 0
            if match:
                left = match[1]; pool.remove(match)
            units = amt - left
            if units <= 0:
                continue
            g = gone[vnum]; g[4] += units
            # A whole listing that vanished while the same seller put up the same quantity at a
            # LOWER price in the same run is a price cut to sell faster, not a sale. The same
            # quantity at the same or a higher price is new stock (a producer relisting, maybe
            # following the market up), so the vanished one still counts as sold.
            if left == 0:
                prices = new.get((vnum, owner, amt), [])
                other = next((q for q in prices if q < price), None)
                if other is not None:
                    prices.remove(other)
                    continue
            g[0] += units; g[1] += 1 if left == 0 else 0; g[2] += units * price; g[3] = max(g[3], price)
            o = owners[(vnum, owner)]; o[0] += units; o[1] += units * price
    out = []
    for vnum in under:
        gone[vnum]   # rows also for items with new cheap listings and no sales
    for vnum, (u, l, v, mx, raw) in sorted(gone.items()):
        out.append([cts.isoformat(), pts.isoformat(), round(minutes), vnum, names.get(vnum, ""), u, l, v, round(v / u) if u else "", mx or "", raw, under[vnum]])
    own = [[cts.isoformat(), vnum, owner, u, v] for (vnum, owner), (u, v) in sorted(owners.items())]
    return out, own


def owners_write(rows, rebuild):
    """Per-seller sales, one file per day (UTC): data/owners/YYYY-MM-DD.csv."""
    if rebuild:
        for f in glob.glob(OWN_DIR + "/*.csv"):
            os.remove(f)
    days = collections.defaultdict(list)
    for r in rows:
        days[r[0][:10]].append(r)
    os.makedirs(OWN_DIR, exist_ok=True)
    for day, rs in sorted(days.items()):
        path = f"{OWN_DIR}/{day}.csv"
        fresh = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if fresh:
                w.writerow(OWN_HEADER)
            w.writerows(rs)


def main():
    files = sorted(glob.glob("data/listings/*/*.csv.gz"))
    names = {}
    if os.path.exists("data/latest.csv"):
        for r in csv.DictReader(open("data/latest.csv", encoding="utf-8")):
            names[int(r["vnum"])] = r["name"]
    rebuild = "--all" in sys.argv or not os.path.exists(OUT)
    if not rebuild:
        with open(OUT, encoding="utf-8") as f:
            rebuild = f.readline().strip().split(",") != HEADER   # old format: rebuild everything
    pairs = list(zip(files, files[1:]))
    if not rebuild:   # only pairs newer than the last row already saved
        last = ""
        with open(OUT, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                last = max(last, r["ts"])
        stamp = lambda path: path.split("/")[-2] + "T" + path.split("/")[-1][:2] + ":" + path.split("/")[-1][2:4]
        pairs = [(a, b) for a, b in pairs if stamp(b) > last[:16]][-200:]
    rows, own, cache = [], [], {}
    for a, b in pairs:
        pa = cache.pop(a, None) or load(a)
        pb = load(b); cache[b] = pb
        r, o = compare(pa, pb, names)
        rows += r; own += o
    mode = "w" if rebuild else "a"
    with open(OUT, mode, newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if rebuild:
            w.writerow(HEADER)
        w.writerows(rows)
    owners_write(own, rebuild)
    print(f"sales: {len(rows)} righe ({len(own)} per venditore) da {len(pairs)} coppie di giri" + (" (ricostruito)" if rebuild else ""))
    add_daily_to_latest(files)


def add_daily_to_latest(files):
    """Add sold_day (units gone in the last 24h, scaled to a day) to data/latest.csv."""
    if not os.path.exists("data/latest.csv") or not files:
        return
    stamp = lambda path: datetime.fromisoformat(path.split("/")[-2] + "T" + path.split("/")[-1][:2] + ":" + path.split("/")[-1][2:4] + "+00:00")
    times = [stamp(f) for f in files]
    since = times[-1] - timedelta(hours=24)
    covered = sum((b - a).total_seconds() / 60 for a, b in zip(times, times[1:]) if a >= since and (b - a).total_seconds() / 60 <= MAX_GAP_MIN)
    units, raw = collections.Counter(), collections.Counter()
    with open(OUT, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if datetime.fromisoformat(r["ts"]) >= since:
                units[r["vnum"]] += int(r["units_gone"] or 0)
                raw[r["vnum"]] += int(r.get("units_raw") or r["units_gone"] or 0)
    with open("data/latest.csv", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    for col in ("sold_day", "sold_day_raw"):
        if col in rows[0]:
            k = rows[0].index(col); rows = [r[:k] + r[k + 1:] for r in rows]
    # sold_day right after lot_price (column M of the Google Sheet), sold_day_raw at the end.
    k = rows[0].index("lot_price") + 1 if "lot_price" in rows[0] else len(rows[0])
    day = lambda c, v: round(c[v] * 1440 / covered) if covered >= 120 else ""
    out = [rows[0][:k] + ["sold_day"] + rows[0][k:] + ["sold_day_raw"]]
    for r in rows[1:]:
        out.append(r[:k] + [day(units, r[1])] + r[k:] + [day(raw, r[1])])
    with open("data/latest.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(out)


if __name__ == "__main__":
    main()
