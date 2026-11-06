"""Realistic selling price per item and run ("vendita").

To sell you have to undercut the cheapest real competition. Tiny or odd listings at the very
bottom (1 piece far below the rest) are skipped: the first SKIP_SHARE of units on sale are
ignored, and the selling price is the price of the next listing minus 1 gold.

    python3 scripts/sell.py          # add runs newer than the last row in data/sell.csv
    python3 scripts/sell.py --all    # rebuild data/sell.csv from every snapshot

Also adds the column "sell" to data/latest.csv (read by the Google Sheet calculator).
"""
import collections, csv, glob, gzip, os, sys

SKIP_SHARE = 0.005
OUT = "data/sell.csv"
HEADER = ["ts", "vnum", "sell"]


def sell_prices(path):
    book = collections.defaultdict(list)
    ts = None
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ts = ts or r["ts"]
            book[r["vnum"]] += [(int(r["price"]), int(r["amount"] or 0))] * int(r["count"] or 1)
    out = {}
    for vnum, rows in book.items():
        rows.sort()
        skip, seen = sum(a for _, a in rows) * SKIP_SHARE, 0
        price = rows[-1][0]
        for p, a in rows:
            if seen + a > skip:
                price = p
                break
            seen += a
        out[vnum] = max(rows[0][0], price - 1)
    return ts, out


def stamp(path):
    d, f = path.split("/")[-2:]
    return f"{d}T{f[:2]}:{f[2:4]}"


def main():
    files = sorted(glob.glob("data/listings/*/*.csv.gz"))
    rebuild = "--all" in sys.argv or not os.path.exists(OUT)
    todo = files
    if not rebuild:
        last = ""
        with open(OUT, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                last = max(last, r["ts"])
        todo = [p for p in files if stamp(p) > last[:16]][-200:]
    rows, latest = [], {}
    for path in todo:
        ts, prices = sell_prices(path)
        rows += [[ts, v, p] for v, p in sorted(prices.items(), key=lambda x: int(x[0]))]
    with open(OUT, "w" if rebuild else "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if rebuild:
            w.writerow(HEADER)
        w.writerows(rows)
    print(f"sell: {len(rows)} righe da {len(todo)} giri")
    if files and os.path.exists("data/latest.csv"):
        _, latest = sell_prices(files[-1])
        with open("data/latest.csv", encoding="utf-8") as f:
            t = list(csv.reader(f))
        if "sell" in t[0]:
            k = t[0].index("sell"); t = [r[:k] + r[k + 1:] for r in t]
        # Right after sold_day (column N of the Google Sheet), otherwise at the end.
        k = t[0].index("sold_day") + 1 if "sold_day" in t[0] else len(t[0])
        t = [r[:k] + ["sell"] + r[k:] for r in t[:1]] + [r[:k] + [latest.get(r[1], "")] + r[k:] for r in t[1:]]
        with open("data/latest.csv", "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(t)


if __name__ == "__main__":
    main()
