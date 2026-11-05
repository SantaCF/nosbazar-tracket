"""Estimate units sold between two consecutive bazaar snapshots.

A listing is identified by item, seller, unit price, package flag and expiry time
(snapshot time + minutes_left, stable within a couple of minutes). Units that vanish
before the listing's expiry were sold or withdrawn by the seller: the two cannot be told
apart, so these are an upper bound of real sales ("spariti"). Units the same seller
relists in the same run are subtracted (withdraw + relist to change price).

    python3 scripts/sales.py          # add the snapshot pairs newer than the last saved row
    python3 scripts/sales.py --all    # rebuild data/sales.csv from every snapshot

Output data/sales.csv: ts, prev_ts, minutes, vnum, name, units_gone, listings_gone,
value_gone, wavg_price, max_price.
"""
import collections, csv, glob, gzip, json, os, sys
from datetime import datetime, timedelta

MAX_GAP_MIN = 40       # larger gaps: too much can happen in between, skip
TOL_MIN = 3            # expiry-time tolerance when matching a listing
OUT = "data/sales.csv"
HEADER = ["ts", "prev_ts", "minutes", "vnum", "name", "units_gone", "listings_gone", "value_gone", "wavg_price", "max_price"]


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
    (pts, p), (cts, c) = prev, cur
    minutes = (cts - pts).total_seconds() / 60
    if minutes <= 0 or minutes > MAX_GAP_MIN:
        return []
    now = cts.timestamp() / 60
    seen = {k[0] for k in c}               # items searched successfully in the current run
    # Per seller: units that vanished before expiry, and units newly listed in this run.
    # A seller who withdraws and relists (e.g. to change price) shows both: only the excess
    # of vanished over newly listed units counts as sold.
    vanished = collections.defaultdict(list)   # (vnum, owner) -> [(price, units, whole_listing)]
    added = collections.Counter()               # (vnum, owner) -> units newly listed
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
            if amt - left > 0:
                vanished[(vnum, owner)].append((price, amt - left, left == 0))
    for key, lst in c.items():
        old = [x[0] for x in p.get(key, [])]
        for exp, amt in lst:
            if not any(abs(exp - e) <= TOL_MIN for e in old):
                added[(key[0], key[1])] += amt
    gone = collections.defaultdict(lambda: [0, 0, 0, 0])   # vnum -> units, listings, value, max price
    for (vnum, owner), lst in vanished.items():
        relisted = added[(vnum, owner)]
        for price, units, whole in sorted(lst):           # relisting offsets the cheapest first
            take = min(units, relisted); relisted -= take; units -= take
            if units > 0:
                g = gone[vnum]; g[0] += units; g[1] += 1 if whole else 0; g[2] += units * price; g[3] = max(g[3], price)
    out = []
    for vnum, (u, l, v, mx) in sorted(gone.items()):
        out.append([cts.isoformat(), pts.isoformat(), round(minutes), vnum, names.get(vnum, ""), u, l, v, round(v / u) if u else "", mx])
    return out


def main():
    files = sorted(glob.glob("data/listings/*/*.csv.gz"))
    names = {}
    if os.path.exists("data/latest.csv"):
        for r in csv.DictReader(open("data/latest.csv", encoding="utf-8")):
            names[int(r["vnum"])] = r["name"]
    rebuild = "--all" in sys.argv or not os.path.exists(OUT)
    pairs = list(zip(files, files[1:]))
    if not rebuild:   # only pairs newer than the last row already saved
        last = ""
        with open(OUT, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                last = max(last, r["ts"])
        stamp = lambda path: path.split("/")[-2] + "T" + path.split("/")[-1][:2] + ":" + path.split("/")[-1][2:4]
        pairs = [(a, b) for a, b in pairs if stamp(b) > last[:16]][-200:]
    rows, cache = [], {}
    for a, b in pairs:
        pa = cache.pop(a, None) or load(a)
        pb = load(b); cache[b] = pb
        rows += compare(pa, pb, names)
    mode = "w" if rebuild else "a"
    with open(OUT, mode, newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if rebuild:
            w.writerow(HEADER)
        w.writerows(rows)
    print(f"sales: {len(rows)} righe da {len(pairs)} coppie di giri")


if __name__ == "__main__":
    main()
