"""Simulazione di trading sullo storico: quanto avrebbe reso seguire le regole di Flipping.

Parte con GOLD0 di oro al primo giro con almeno 24 ore di storico e rifà tutto, giro per giro, usando a ogni giro
SOLO i dati di quel momento e di prima (niente sguardi al futuro):

1. Vendite: ogni posizione aperta (pezzi rimessi in vendita a un prezzo P) si vende solo se in quel giro qualcuno ha
   davvero venduto a P o più (data/owners: pezzi e incasso per venditore, prezzo medio >= P). I compratori passano dagli
   annunci più economici, quindi chi ha comprato a P o più avrebbe preso prima i nostri. Pezzi venduti = al massimo
   quelli venduti a P o più in quel giro. Dopo MAX_H ore la posizione si chiude al prezzo di vendita realistico di quel
   momento (data/sell.csv): "uscita forzata", di solito in perdita.
2. Acquisti: le stesse due regole della pagina Flipping, sul libro di annunci vero di quel giro:
   - "now" (compra e rivendi subito): compra sotto il tetto (25% dei pezzi e 75° percentile del prezzo di vendita delle
     ultime 24 ore) e rimette appena sotto il primo annuncio che resta, se i pezzi davanti + i tuoi stanno nella domanda;
   - "hold" (sotto il solito): compra sotto la mediana del prezzo di vendita (giri più vecchi di 2 ore) e rimette lì.
   Guadagno minimo: MIN_PCT del patrimonio (oro + merce al costo), e almeno l'1% della spesa.
3. Scelta tra le opportunità: rendimento orario atteso = (probabilità di vendere x guadagno % + resto x esito medio delle
   uscite forzate) / ore attese per vendere. Così vince chi gira più in fretta (turnover), a parità chi rende di più.
4. Apprendimento: ore attese e probabilità di vendere partono da una stima semplice (pezzi davanti + tuoi diviso i pezzi
   venduti all'ora nelle ultime 24 ore) e si correggono con le operazioni già chiuse dello stesso item e tipo: il
   rapporto ore vere / ore stimate e la quota vendute in tempo. Con poche operazioni conta di più la media di tutti gli
   item (PRIOR_N operazioni "finte" alla media generale).

Niente commissioni (Medaglia NosBazar). Una posizione aperta per item alla volta.

Output:
  data/sim.json       serie del patrimonio, operazioni, posizioni aperte, riepilogo (pagina simulazione.html)
  data/sim_learn.csv  quello che ha imparato per item e tipo (usato da Flipping)
"""
import bisect, collections, csv, glob, gzip, json, math, os, statistics
from datetime import datetime, timedelta

GOLD0 = 25_000_000
MIN_PCT = 0.01          # guadagno minimo: 1% del patrimonio
MAX_H = 48              # oltre, uscita forzata al prezzo di vendita realistico
DEMAND_H = 3            # i pezzi davanti + i tuoi devono vendersi in queste ore (come "Rivendere entro" in Flipping)
PRIOR_N = 3
MAX_SHARE = 0.3         # al massimo il 30% del patrimonio in una sola operazione
# Esclusi: il prezzo dipende da cosa c'è dentro o da upgrade e rarità, che la raccolta non vede (perle con un pet,
# una fata, un mezzo; scarpe e guanti con resistenze). Il "solito" lì non vuol dire niente.
SKIP = {"4194", "285", "286", "8581", "4106"} | {str(v) for v in range(376, 392)}
OUT, LEARN = "data/sim.json", "data/sim_learn.csv"


def ts_of(s):
    return datetime.fromisoformat(s)


def load():
    runs = []
    for f in sorted(glob.glob("data/listings/*/*.csv.gz")):
        book = collections.defaultdict(list)
        ts = None
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                ts = ts or r["ts"]
                book[r["vnum"]].append((int(r["price"]), int(r["amount"]) * int(r.get("count") or 1), r["owner"]))
        if ts:
            for a in book.values():
                a.sort()
            runs.append((ts_of(ts), book))
    prices = collections.defaultdict(dict)          # ts -> vnum -> (wp10, wp25)
    names = {}
    for r in csv.DictReader(open("data/prices.csv", encoding="utf-8")):
        prices[r["ts"]][r["vnum"]] = (float(r["wp10"] or 0), float(r["wp25"] or 0))
        names[r["vnum"]] = r["name"]
    sell = collections.defaultdict(list)            # vnum -> [(ts, price)]
    for r in csv.DictReader(open("data/sell.csv", encoding="utf-8")):
        if r["sell"]:
            sell[r["vnum"]].append((ts_of(r["ts"]), float(r["sell"])))
    sold = collections.defaultdict(lambda: collections.defaultdict(list))   # ts -> vnum -> [(avg price, units)]
    for f in sorted(glob.glob("data/owners/*.csv")):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            u = int(r["units"])
            if u > 0:
                sold[ts_of(r["ts"])][r["vnum"]].append((float(r["value"]) / u, u))
    return runs, prices, names, sell, sold


class Hist:
    """Pezzi venduti all'ora per item nelle 24 ore prima di un giro (da data/owners)."""

    def __init__(self, sold):
        self.t = sorted(sold)
        self.sold = sold

    def rate(self, v, now):
        i0 = bisect.bisect_left(self.t, now - timedelta(hours=24))
        i1 = bisect.bisect_right(self.t, now)
        if i1 - i0 < 10:
            return 0.0
        units = sum(u for t in self.t[i0:i1] for _, u in self.sold[t].get(v, ()))
        span = (self.t[i1 - 1] - self.t[i0]).total_seconds() / 3600 or 1
        return units / span


def sell_window(h, now, hours):
    i1 = bisect.bisect_right([t for t, _ in h], now)
    return [p for t, p in h[:i1] if t >= now - timedelta(hours=hours)], h[:i1]


def resell(rest, q, d, cap):
    """Come resell() di flipping.html: prezzo più alto con pezzi davanti + tuoi entro la domanda d, mai sopra cap."""
    if not rest or q > d:
        return None
    below, price, ahead = 0, min(rest[0][0] - 1, cap), 0
    for k, (pr, am) in enumerate(rest):
        if k > 0 and pr != rest[k - 1][0]:
            if below + q <= d and pr - 1 <= cap:
                price, ahead = pr - 1, below
            else:
                break
        below += am
    return price, ahead


def flip_now(book, wp, hsell, d, money):
    wp10, wp25 = wp
    recent, _ = sell_window(hsell, NOW[0], 24)
    if len(recent) < 4:
        return None
    hi = sorted(recent)[int(len(recent) * 0.75)]
    cap = min(wp25 or wp10, hi)
    q = cost = 0
    best = None
    for i, (p, am) in enumerate(book):
        if p >= cap:
            break
        take = am if cost + am * p <= money else int((money - cost) // p)
        if take <= 0:
            break
        q += take
        cost += take * p
        rest = ([(p, am - take)] if take < am else []) + book[i + 1:]
        s = resell(rest, q, d, cap)
        if s and s[0] > p:
            profit = q * s[0] - cost
            if not best or profit > best["profit"]:
                best = {"kind": "now", "q": q, "cost": cost, "price": s[0], "ahead": s[1], "profit": profit}
        if take < am:
            break
    return best


def flip_hold(book, hsell, d, day, money):
    _, upto = sell_window(hsell, NOW[0], 0)
    if len(upto) < 8 or (upto[-1][0] - upto[0][0]).total_seconds() < 6 * 3600:
        return None
    old = sorted(p for t, p in upto if t <= NOW[0] - timedelta(hours=2) and t >= NOW[0] - timedelta(days=7))
    if len(old) < 8:
        return None
    target = old[len(old) // 2] - 1
    under = sum(am for p, am in book if p < target)
    if under > d:
        return None
    max_q = min(day, d)
    q = cost = 0
    best = None
    for p, am in book:
        if p >= target * 0.98:
            break
        take = min(am, max_q - q)
        if cost + take * p > money:
            take = int((money - cost) // p)
        if take <= 0:
            break
        q += take
        cost += take * p
        profit = q * target - cost
        if not best or profit > best["profit"]:
            best = {"kind": "hold", "q": q, "cost": cost, "price": int(target), "ahead": under - q, "profit": profit}
        if take < am:
            break
    return best


NOW = [None]


def learned(closed, v, kind):
    """(fattore ore vere/stimate, quota vendute entro MAX_H, esito medio % delle uscite forzate) per item e tipo."""
    def stats(rows):
        ok = [r for r in rows if not r["forced"]]
        f = [r["hours"] / max(r["est_h"], 0.25) for r in ok]
        fail = [r["pct"] for r in rows if r["forced"]]
        return len(rows), (statistics.median(f) if f else None), (len(ok) / len(rows) if rows else None), (statistics.mean(fail) if fail else None)
    g_n, g_f, g_p, g_fail = stats([r for r in closed if r["kind"] == kind])
    g_f = g_f if g_f is not None else 1.0
    g_p = g_p if g_p is not None else 0.8
    g_fail = g_fail if g_fail is not None else -0.05
    n, f, p, fail = stats([r for r in closed if r["vnum"] == v and r["kind"] == kind])
    w = n / (n + PRIOR_N)
    return ((f if f is not None else g_f) * w + g_f * (1 - w),
            (p if p is not None else g_p) * w + g_p * (1 - w),
            (fail if fail is not None else g_fail) * w + g_fail * (1 - w), n)


def main():
    runs, prices, names, sell, sold = load()
    hist = Hist(sold)
    t0 = runs[0][0] + timedelta(hours=24)
    gold, open_pos, closed, series, taken, prev_keys = GOLD0, {}, [], [], {}, {}
    for now, book in runs:
        if now < t0:
            continue
        NOW[0] = now
        # Gli annunci "comprati" dalla simulazione nei dati veri restano lì: li tolgo dal libro finché ci sono.
        # taken[v] = {(venditore, prezzo): pezzi}; quando l'annuncio sparisce dai dati lo dimentico.
        vo = {}
        for v, b in book.items():
            if v in SKIP:
                continue
            left, a = dict(taken.get(v, {})), []
            for p, am, ow in b:
                cut = min(am, left.get((ow, p), 0))
                if cut:
                    left[(ow, p)] -= cut
                if am > cut:
                    a.append((p, am - cut, ow))
            if v in taken:
                seen = {(ow, p) for p, _, ow in b}
                taken[v] = {k: n for k, n in taken[v].items() if k in seen}
            vo[v] = a
        # 1. vendite delle posizioni aperte, con le vendite vere di questo giro
        for v, pos in list(open_pos.items()):
            hrs = (now - pos["t"]).total_seconds() / 3600
            fill = sum(u for avg, u in sold.get(now, {}).get(v, ()) if avg >= pos["price"])
            # I compratori passano dagli annunci più economici: se sotto il nostro prezzo resta un annuncio che c'era già
            # al giro prima, chi risulta aver venduto più in alto ha ritirato l'annuncio o ha scelto proprio quello
            # (compratori di stack): non conto che avrebbe preso il nostro.
            prev = prev_keys.get(v, set())
            if fill and any(p < pos["price"] and (ow, p) in prev for p, _, ow in vo.get(v, ())):
                fill = 0
            take = min(pos["left"], fill)
            if take:
                pos["left"] -= take
                pos["got"] += take * pos["price"]
                gold += take * pos["price"]
            forced = False
            if pos["left"] and hrs >= MAX_H:
                _, upto = sell_window(sell.get(v, []), now, 0)
                exit_p = upto[-1][1] if upto else pos["cost"] / pos["q"] * 0.9
                pos["got"] += pos["left"] * exit_p
                gold += pos["left"] * exit_p
                pos["left"] = 0
                forced = True
            if not pos["left"]:
                del open_pos[v]
                closed.append({"vnum": v, "name": names.get(v, v), "kind": pos["kind"], "t": pos["t"].isoformat(),
                               "end": now.isoformat(), "q": pos["q"], "cost": pos["cost"], "price": pos["price"],
                               "got": round(pos["got"]), "profit": round(pos["got"] - pos["cost"]),
                               "pct": (pos["got"] - pos["cost"]) / pos["cost"], "hours": round(hrs, 2),
                               "est_h": pos["est_h"], "forced": forced})
        # 2. opportunità sul libro di questo giro
        stock = sum(p["cost"] * p["left"] / p["q"] for p in open_pos.values())
        equity = gold + stock
        wps = prices.get(now.isoformat(), {})
        cands = []
        for v, bo in vo.items():
            if v in open_pos or v not in wps:
                continue
            b = [(p, am) for p, am, _ in bo]
            money = min(gold, MAX_SHARE * equity)
            rate = hist.rate(v, now)
            if rate <= 0:
                continue
            d = rate * DEMAND_H
            for o in (flip_now(b, wps[v], sell.get(v, []), d, money), flip_hold(b, sell.get(v, []), d, rate * 24, money)):
                if not o or o["profit"] < max(MIN_PCT * equity, o["cost"] * 0.01):
                    continue
                f, p_ok, fail, n = learned(closed, v, o["kind"])
                est = (o["ahead"] + o["q"]) / rate
                exp_h = max(est * f, 0.25)
                pct = o["profit"] / o["cost"]
                o.update(v=v, est_h=round(est, 2), exp_h=exp_h, score=(p_ok * pct + (1 - p_ok) * fail) / exp_h)
                if o["score"] > 0:
                    cands.append(o)
        # 3. le migliori per rendimento orario atteso, finché c'è oro (ricalcolate sull'oro rimasto)
        cands.sort(key=lambda o: -o["score"])
        for o in cands:
            if o["v"] in open_pos:
                continue
            if o["cost"] > gold:
                continue
            gold -= o["cost"]
            need, tk = o["q"], taken.setdefault(o["v"], {})
            for p, am, ow in vo[o["v"]]:
                if need <= 0:
                    break
                t = min(am, need)
                tk[(ow, p)] = tk.get((ow, p), 0) + t
                need -= t
            open_pos[o["v"]] = {"t": now, "kind": o["kind"], "q": o["q"], "left": o["q"], "cost": o["cost"],
                                "price": o["price"], "got": 0, "est_h": o["est_h"]}
        stock = sum(p["cost"] * p["left"] / p["q"] for p in open_pos.values())
        # posizioni in quel momento: [vnum, pezzi rimasti, oro fermo al costo, appena comprata 1/0]
        series.append([now.isoformat(), round(gold), round(stock),
                       [[v, p["left"], round(p["cost"] * p["left"] / p["q"]), int(p["t"] == now)] for v, p in open_pos.items()]])
        prev_keys = {v: {(ow, p) for p, _, ow in b} for v, b in book.items()}

    # riepilogo
    last = runs[-1][0]
    stock_val = 0
    opened = []
    for v, p in open_pos.items():
        _, upto = sell_window(sell.get(v, []), last, 0)
        cur = upto[-1][1] if upto else p["price"]
        stock_val += p["left"] * cur
        opened.append({"vnum": v, "name": names.get(v, v), "kind": p["kind"], "t": p["t"].isoformat(), "q": p["q"],
                       "left": p["left"], "cost": p["cost"], "price": p["price"], "got": round(p["got"]), "now": cur})
    learn_rows = []
    for v, kind in sorted({(r["vnum"], r["kind"]) for r in closed}):
        f, p_ok, fail, n = learned(closed, v, kind)
        rows = [r for r in closed if r["vnum"] == v and r["kind"] == kind]
        ok = [r for r in rows if not r["forced"]]
        learn_rows.append([v, names.get(v, v), kind, n, len(ok), round(statistics.median(r["hours"] for r in ok), 1) if ok else "",
                           round(f, 2), round(p_ok, 2), round(statistics.mean(r["pct"] for r in rows), 4),
                           round(sum(r["profit"] for r in rows))])
    with open(LEARN, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["vnum", "name", "kind", "trades", "sold", "med_hours", "time_factor", "p_sold", "avg_pct", "profit"])
        w.writerows(learn_rows)
    json.dump({"gold0": GOLD0, "min_pct": MIN_PCT, "max_h": MAX_H, "start": series[0][0] if series else None,
               "end": last.isoformat(), "names": {v: names.get(v, v) for v in {x[0] for s in series for x in s[3]}}, "gold": round(gold), "stock_cost": round(sum(p["cost"] * p["left"] / p["q"] for p in open_pos.values())),
               "stock_value": round(stock_val), "series": series, "closed": closed, "open": opened},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    eq = gold + stock_val
    print(f"simulazione {series[0][0] if series else '-'} → {last}: oro {gold:,.0f} + merce {stock_val:,.0f} = {eq:,.0f} "
          f"({(eq / GOLD0 - 1) * 100:+.1f}%), {len(closed)} operazioni chiuse, {len(open_pos)} aperte")


if __name__ == "__main__":
    main()
