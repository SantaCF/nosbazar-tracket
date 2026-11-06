"""Sales flow by hour, for "how much sells in the next X hours" (instead of a flat 24h average).

Players are not online evenly: evenings and weekends sell more. data/flow.csv keeps, for the last DAYS days,
the units sold per item in every hour (UTC, epoch hour) and how many minutes of that hour were covered by
consecutive runs (vnum 0 rows). Pages (flow.js) and alerts.py estimate the next X hours from the same window
of the previous days, recent days weighing more.

    python3 scripts/flow.py     # rebuild data/flow.csv from data/sales.csv and the snapshot list

Output data/flow.csv: hour, vnum, units   (vnum 0: units = covered minutes of that hour)
"""
import collections, csv, glob, math, os
from datetime import datetime, timedelta, timezone

DAYS = 28
MAX_GAP_MIN = 40
OUT = "data/flow.csv"
DECAY = 0.85          # weight of a day = DECAY ** (days ago - 1)
MIN_DAYS = 3          # fewer comparable days than this: fall back to the 24h average
MIN_COVER = 0.6       # a past window counts only if runs covered at least 60% of it


def stamp(path):
    d, f = path.split("/")[-2:]
    return datetime.fromisoformat(f"{d}T{f[:2]}:{f[2:4]}+00:00")


def spread(acc, key, a, b, amount):
    """Split amount over the epoch hours touched by the interval [a, b] (epoch seconds), by overlap."""
    total = b - a
    if total <= 0:
        return
    h = int(a // 3600)
    while h * 3600 < b:
        lo, hi = max(a, h * 3600), min(b, (h + 1) * 3600)
        if hi > lo:
            acc[(h, key)] += amount * (hi - lo) / total
        h += 1


def build():
    times = [stamp(f) for f in sorted(glob.glob("data/listings/*/*.csv.gz"))]
    if not times:
        return
    since = times[-1] - timedelta(days=DAYS)
    acc = collections.defaultdict(float)
    for a, b in zip(times, times[1:]):
        gap = (b - a).total_seconds() / 60
        if a >= since and 0 < gap <= MAX_GAP_MIN:
            spread(acc, 0, a.timestamp(), b.timestamp(), gap)        # covered minutes
    if os.path.exists("data/sales.csv"):
        for r in csv.DictReader(open("data/sales.csv", encoding="utf-8")):
            t, p = datetime.fromisoformat(r["ts"]), datetime.fromisoformat(r["prev_ts"])
            if p >= since and r["units_gone"]:
                spread(acc, int(r["vnum"]), p.timestamp(), t.timestamp(), int(r["units_gone"]))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["hour", "vnum", "units"])
        for (h, v), u in sorted(acc.items()):
            if u >= 0.5 or v == 0:
                w.writerow([h, v, round(u, 1)])
    print(f"flow: {len(acc)} righe")


def load(path=OUT):
    """-> (cover {hour: minutes}, units {vnum: {hour: units}})"""
    cover, units = {}, collections.defaultdict(dict)
    if not os.path.exists(path):
        return cover, units
    for r in csv.DictReader(open(path, encoding="utf-8")):
        h, v, u = int(r["hour"]), int(r["vnum"]), float(r["units"])
        if v == 0:
            cover[h] = u
        else:
            units[v][h] = u
    return cover, units


def expected(flow, vnum, start, hours, conf=0.5):
    """Units of vnum expected to sell in [start, start + hours), from the same window on previous days.
    conf = probability of selling at least that much (0.5 = median, 0.8 = beaten on 4 days out of 5).
    Returns (units, days used) or (None, days) when there are fewer than MIN_DAYS comparable days."""
    cover, units = flow
    u = units.get(int(vnum), {})
    h0, n = int(start.timestamp() // 3600), max(1, math.ceil(hours))
    pts = []
    for k in range(1, DAYS + 1):
        hs = range(h0 - 24 * k, h0 - 24 * k + n)
        cov = sum(cover.get(h, 0) for h in hs) / (60 * n)
        if cov >= MIN_COVER:
            pts.append((sum(u.get(h, 0) for h in hs) / cov * hours / n, DECAY ** (k - 1)))
    if len(pts) < MIN_DAYS:
        return None, len(pts)
    return quantile(pts, 1 - conf), len(pts)


def quantile(pts, q):
    """Weighted quantile of [(value, weight)]."""
    pts = sorted(pts)
    tot, run = sum(w for _, w in pts), 0
    for v, w in pts:
        run += w
        if run >= q * tot:
            return v
    return pts[-1][0]


if __name__ == "__main__":
    build()
