"""Pagella delle previsioni: quanto spesso il sito indovina il tempo di vendita.

Every 2 hours (first run of an even UTC hour) and for every item that sells, a "test listing" is placed on paper:
QTY pieces (2% of the units on sale, like the reference lot) at the realistic selling price of that run
(data/sell.csv). The site's model (flow.py, same as flow.js) predicts in how many hours the net demand eats the
queue in front of it plus the test pieces, at 70% and 50% confidence. Later the real net flow of the following
hours says how long it actually took.

The starting price is part of the test: a price above the usual has a longer queue in front (and buyers who wait),
so the page can show how good the model is when prices are high, normal or low, by time of day and by weekday.

    python3 scripts/pagella.py          # add new test listings and fill in the outcome of pending ones
    python3 scripts/pagella.py --all    # rebuild from every snapshot (uses only data older than each test)

Output data/pagella.csv:
  ts, vnum, price, ahead, qty, pred70, pred50, premium, hour_it, weekday, real, cover
  pred70/pred50: predicted hours (empty = more than MAX_H or not enough data)
  premium: price vs the median selling price of the previous 7 days (0.05 = 5% above)
  hour_it / weekday: Italian time (weekday 0 = Monday)
  real: hours it really took (empty = still pending, MAX_H + 1 = not sold within MAX_H)
  cover: share of the waited hours covered by runs (low = collection was down, the outcome is less reliable)
"""
import bisect, collections, csv, glob, gzip, math, os, statistics, sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
import flow  # noqa: E402

OUT = "data/pagella.csv"
HEADER = ["ts", "vnum", "price", "ahead", "qty", "pred70", "pred50", "premium", "hour_it", "weekday", "real", "cover"]
EVERY_H = 2
MAX_H = 48
LOT_SHARE = 0.02
ROME = ZoneInfo("Europe/Rome")


def stamp(path):
    d, f = path.split("/")[-2:]
    return datetime.fromisoformat(f"{d}T{f[:2]}:{f[2:4]}+00:00")


def net_series(units, vnum):
    sold, under = units.get(int(vnum), {}), units.get(-int(vnum), {})
    return {h: sold.get(h, 0) - under.get(h, 0) for h in set(sold) | set(under)}


def predict(cover, u, h0, need, conf):
    """First number of hours n (1..MAX_H) whose expected net demand (flow.expected logic) reaches need."""
    # Same days of the previous weeks: cumulative sums per past day k, scaled by covered share.
    per_n = [[] for _ in range(MAX_H + 1)]
    for k in range(1, flow.DAYS + 1):
        s = c = 0.0
        for n in range(1, MAX_H + 1):
            h = h0 - 24 * k + n - 1
            s += u.get(h, 0); c += cover.get(h, 0)
            cov = c / (60 * n)
            if cov >= flow.MIN_COVER:
                per_n[n].append((s / cov, flow.DECAY ** (k - 1)))
    for n in range(1, MAX_H + 1):
        if len(per_n[n]) >= flow.MIN_DAYS:
            if max(0, flow.quantile(per_n[n], 1 - conf)) >= need:
                return n
        else:
            # Few comparable days: windows of the same length at any hour of the last 72 hours.
            roll = []
            for k in range(1, 72 - n + 2):
                hs = range(h0 - k - n + 1, h0 - k + 1)
                cov = sum(cover.get(h, 0) for h in hs) / (60 * n)
                if cov >= flow.MIN_COVER:
                    roll.append(sum(u.get(h, 0) for h in hs) / cov)
            if len(roll) >= 6:
                roll.sort()
                if max(0, roll[min(len(roll) - 1, int((1 - conf) * len(roll)))]) >= need:
                    return n
    return None


def outcome(cover, u, h0, need, now_h):
    """-> (real hours or None if still pending, cover share). MAX_H + 1 = not sold within MAX_H hours."""
    s = c = 0.0
    for n in range(1, MAX_H + 1):
        h = h0 + n - 1
        if h >= now_h:
            return None, c / (60 * (n - 1)) if n > 1 else 0
        s += u.get(h, 0); c += cover.get(h, 0)
        if s >= need:
            return n, c / (60 * n)
    return MAX_H + 1, c / (60 * MAX_H)


def load_sell():
    """-> {vnum: ([epoch], [price])} sorted by time."""
    out = collections.defaultdict(lambda: ([], []))
    if os.path.exists("data/sell.csv"):
        for r in csv.DictReader(open("data/sell.csv", encoding="utf-8")):
            if r["sell"]:
                t, p = out[r["vnum"]]
                t.append(datetime.fromisoformat(r["ts"]).timestamp()); p.append(int(r["sell"]))
    return out


def tests_at(path, sells, cover, units):
    """Test listings for one snapshot."""
    ts = stamp(path)
    t0, h0 = ts.timestamp(), int(ts.timestamp() // 3600)
    book = collections.defaultdict(list)
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            book[r["vnum"]] += [(int(r["price"]), int(r["amount"] or 0))] * int(r["count"] or 1)
    loc = ts.astimezone(ROME)
    rows = []
    for vnum, rows_b in book.items():
        u = net_series(units, vnum)
        if not any(u.get(h, 0) > 0 for h in range(h0 - 72, h0)):
            continue                                   # item that does not sell: nothing to test
        t, p = sells.get(vnum, ([], []))
        i = bisect.bisect_right(t, t0 + 60) - 1
        if i < 0 or t0 - t[i] > 1800:
            continue
        price = p[i]
        j = bisect.bisect_left(t, t0 - 7 * 86400)
        usual = statistics.median(p[j:i]) if i - j >= 12 else None
        total = sum(a for _, a in rows_b)
        ahead = sum(a for pr, a in rows_b if pr < price)
        qty = max(1, round(total * LOT_SHARE))
        need = ahead + qty
        p70, p50 = predict(cover, u, h0, need, 0.7), predict(cover, u, h0, need, 0.5)
        rows.append({"ts": ts.isoformat(), "vnum": vnum, "price": price, "ahead": ahead, "qty": qty,
                     "pred70": p70 or "", "pred50": p50 or "",
                     "premium": f"{price / usual - 1:.4f}" if usual else "",
                     "hour_it": loc.hour, "weekday": loc.weekday(), "real": "", "cover": ""})
    return rows


def main():
    rebuild = "--all" in sys.argv or not os.path.exists(OUT)
    cover, units = flow.load()
    if not cover:
        print("pagella: manca data/flow.csv"); return
    snaps = sorted(glob.glob("data/listings/*/*.csv.gz"))
    old = [] if rebuild else list(csv.DictReader(open(OUT, encoding="utf-8")))
    done_hours = {r["ts"][:13] for r in old}
    # Only flow hours that the 28-day flow.csv still covers can be tested.
    first_h = min(cover) if cover else 0
    picked, seen = [], set(done_hours)
    for s in snaps:
        ts = stamp(s)
        key = ts.isoformat()[:13]
        if ts.hour % EVERY_H or key in seen or ts.timestamp() // 3600 < first_h + 24:
            continue
        seen.add(key); picked.append(s)
    sells = load_sell() if picked else {}
    new = [r for s in picked for r in tests_at(s, sells, cover, units)]
    rows = old + new
    now_h = max(cover) + 1 if cover else 0       # hours up to the last covered one are known
    for r in rows:
        if r["real"]:
            continue
        h0 = int(datetime.fromisoformat(r["ts"]).timestamp() // 3600)
        real, cov = outcome(cover, net_series(units, r["vnum"]), h0, int(r["ahead"]) + int(r["qty"]), now_h)
        if real is not None:
            r["real"], r["cover"] = real, f"{cov:.2f}"
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    print(f"pagella: {len(new)} prove nuove, {sum(1 for r in rows if r['real'])} valutate su {len(rows)}")


if __name__ == "__main__":
    main()
