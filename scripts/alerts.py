"""Phone notifications (ntfy) about your own bazaar listings.

Each run looks for the listings of your characters in the latest snapshot and sends a notification when:
  - you sold most of an item (SOLD_SHARE, default 80%) and when it is all gone;
  - selling would take too long at your price (more than ALERT_HOURS, default 6): the units cheaper
    than yours plus yours exceed what the bazaar is expected to sell in the next ALERT_HOURS, estimated
    from the same hours of the previous days (scripts/flow.py, 70% confidence; with fewer than 3 days of
    data the 24h average sold_day). It suggests the price that sells everything within ALERT_HOURS.

Configuration comes from repository settings (Settings > Secrets and variables > Actions), not from this public repo:
  NOS_SELLERS   variable (or secret): character names, comma separated, not case sensitive
  NTFY_TOPIC    the ntfy topic subscribed in the phone app
  ALERT_HOURS   variable, optional: hours you are willing to wait, 1 to 24 (default 6)
Smart alerts (same run):
  - someone undercut you: you were the cheapest and now someone sells below you;
  - you can raise: the cheapest of the others is clearly above your price (e.g. after a bulk buyer swept the queue);
  - a method's margin per piece crossed ALERT_MARGIN (variable, %, default 10) at the current prices;
  - an ingredient or product of the methods is below its usual floor (10th percentile of the last 7 days).
  ALERT_MARGIN   variable, optional: method margin threshold in % (default 10)
State (what was already notified) lives in .alerts/state.json, kept between runs by the Actions cache.
Units that vanish before expiry count as sold: if you withdraw a listing yourself it counts as sold too.
"""
import csv, glob, gzip, json, os, sys, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow   # venduti attesi per fascia oraria (stessa logica delle pagine)

SELLERS = {s.strip().lower() for s in os.environ.get("NOS_SELLERS", "").split(",") if s.strip()}
TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
try:
    HOURS = min(24.0, max(1.0, float(os.environ.get("ALERT_HOURS") or 6)))   # 1-24 ore, default 6
except ValueError:
    HOURS = 6.0
try:
    MARGIN = float(os.environ.get("ALERT_MARGIN") or 10) / 100
except ValueError:
    MARGIN = 0.10
SOLD_SHARE = 0.8
RAISE_SHARE = 0.03   # "puoi alzare" when the cheapest of the others is at least 3% above you
SMART_REPEAT = 2 * 60
STATE = ".alerts/state.json"
REPEAT_MIN = 6 * 60   # a "slow" warning for the same item is repeated at most every 6 hours


def notify(title, body, tags="moneybag"):
    req = urllib.request.Request("https://ntfy.sh/" + TOPIC, data=body.encode("utf-8"), method="POST",
                                 headers={"Title": title.encode("utf-8").decode("latin-1", "ignore"), "Tags": tags,
                                          "Click": "https://santacf.github.io/nosbazar-tracket/flipping.html"})
    try:
        urllib.request.urlopen(req, timeout=20).read()
        print("notifica inviata:", title)
    except Exception as e:
        print("notifica non inviata:", e)


CONF = 0.7


def hours_to_sell(fl, v, start, qty, d):
    """First hour at which the expected net flow from start reaches qty (max 7 days); 24h average without data."""
    for h in range(1, 169):
        e, _ = flow.expected(fl, v, start, h, CONF)
        if e is None:
            e = d * h / 24 if d else None
        if e is None:
            return None
        if e >= qty:
            return h
    return None


def load_recipes():
    """RICETTE from ricette.js (pure JSON between "RICETTE =" and the final ";")."""
    try:
        t = open("ricette.js", encoding="utf-8").read()
        a = t.index("const RICETTE =") + len("const RICETTE =")
        return json.loads(t[a:t.index("};", a) + 1])
    except Exception as e:
        print("ricette non lette:", e)
        return None


def smart(state, mine, others, names, now):
    """Method margins over ALERT_MARGIN and ingredients/products under their usual floor."""
    rec = load_recipes()
    if not rec or not os.path.exists("data/latest.csv"):
        return
    last = {r["vnum"]: r for r in csv.DictReader(open("data/latest.csv", encoding="utf-8"))}
    num = lambda x: float(x) if x not in (None, "") else 0
    buy = lambda v: rec["npc"].get(str(v)) or num(last.get(str(v), {}).get("lot_price")) or num(last.get(str(v), {}).get("min"))
    sell = lambda v: num(last.get(str(v), {}).get("sell")) or num(last.get(str(v), {}).get("wp10"))
    ms = state.setdefault("_m", {})
    for m in rec["methods"]:
        if m.get("support"):
            continue
        cost = sum(q * buy(v) for v, q in m["ing"])
        gain = sum(q * sell(v) for v, q in m["out"])
        if not cost or not all(buy(v) for v, _ in m["ing"]) or not all(sell(v) for v, _ in m["out"]):
            continue
        mg, was = gain / cost - 1, ms.get(m["name"], False)
        if mg >= MARGIN and not was:
            ms[m["name"]] = True
            notify(f"Metodo in guadagno: {m['name']}", f"Margine {round(mg * 100)}% a pezzo con i prezzi di adesso (soglia {round(MARGIN * 100)}%). Apri Metodi per sapere quanti farne.", "chart_with_upwards_trend")
        elif mg < MARGIN - 0.02:
            ms[m["name"]] = False          # sotto la soglia (con 2 punti di margine): al prossimo superamento riavvisa
    # Occasioni: item delle ricette (ingredienti e prodotti) sotto il loro pavimento abituale.
    watch = {str(v) for m in rec["methods"] for v, _ in m["ing"] + m["out"]} - set(rec["npc"])
    hist = {}
    if os.path.exists("data/sell.csv"):
        since = datetime.fromtimestamp((now - 7 * 1440) * 60, timezone.utc).isoformat()
        for r in csv.DictReader(open("data/sell.csv", encoding="utf-8")):
            if r["vnum"] in watch and r["ts"] >= since and r["sell"]:
                hist.setdefault(r["vnum"], []).append(int(r["sell"]))
    os_ = state.setdefault("_o", {})
    for v, h in hist.items():
        if len(h) < 4 * 96:                 # almeno 4 giorni di giri
            continue
        cur, floor = h[-1], sorted(h[:-4])[len(h[:-4]) // 10]
        if cur < floor * 0.98 and now - os_.get(v, 0) >= 12 * 60:
            os_[v] = now
            notify(f"Occasione: {names.get(v, v)}", f"Si compra a {fmt(cur)}, sotto il pavimento degli ultimi 7 giorni ({fmt(floor)}, il prezzo più basso nel 10% dei giri). Guarda Prezzi prima di comprare.", "shopping_cart")


def fmt(n):
    return f"{round(n):,}".replace(",", ".")


def main():
    if not SELLERS or not TOPIC:
        print("notifiche non configurate (servono i secret NOS_SELLERS e NTFY_TOPIC)")
        return
    files = sorted(glob.glob("data/listings/*/*.csv.gz"))
    if not files:
        return
    names, day = {}, {}
    if os.path.exists("data/latest.csv"):
        for r in csv.DictReader(open("data/latest.csv", encoding="utf-8")):
            names[r["vnum"]] = r["name"]
            if r.get("sold_day"):
                day[r["vnum"]] = float(r["sold_day"])
    mine, others, ts = {}, {}, None
    with gzip.open(files[-1], "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ts = ts or r["ts"]
            n = int(r["count"] or 1)
            row = (int(r["price"]), int(r["amount"] or 0) * n)
            (mine if r["owner"].lower() in SELLERS else others).setdefault(r["vnum"], []).append(row)
    fl = flow.load()
    first = not os.path.exists(STATE)
    state = {} if first else json.load(open(STATE, encoding="utf-8"))
    d_, f_ = files[-1].split("/")[-2:]
    now = int(datetime.fromisoformat(f"{d_}T{f_[:2]}:{f_[2:4]}+00:00").timestamp() // 60)   # minutes since epoch
    if first:
        items = ", ".join(f"{names.get(v, v)} ({fmt(sum(a for _, a in l))})" for v, l in mine.items()) or "nessun annuncio trovato adesso"
        notify("Notifiche bazar attive", f"Ti avviso quando vendi l'{round(SOLD_SHARE * 100)}% e quando venderesti in più di {fmt(HOURS)} ore. Annunci tuoi: {items}", "white_check_mark")
    smart(state, mine, others, names, now)
    for v in (set(mine) | set(state)) - {k for k in state if k.startswith("_")}:
        units = sum(a for _, a in mine.get(v, []))
        st = state.get(v, {"peak": 0, "prev": 0, "sold80": False, "slow_at": 0, "slow_price": 0})
        if units > st["prev"]:
            st["peak"] += units - st["prev"]           # new listings: they join the stock to sell
        st["prev"] = units
        name = names.get(v, v)
        if units == 0:
            if st["peak"] > 0:
                notify(f"Venduto tutto: {name}", f"Sono spariti tutti i {fmt(st['peak'])} pezzi che avevi in vendita.", "tada")
            state.pop(v, None)
            continue
        sold = 1 - units / st["peak"]
        if sold >= SOLD_SHARE and not st["sold80"]:
            st["sold80"] = True
            notify(f"Venduto {round(sold * 100)}%: {name}", f"Restano {fmt(units)} pezzi su {fmt(st['peak'])}.", "moneybag")
        d = day.get(v)
        start = datetime.fromtimestamp(now * 60, timezone.utc)
        exp, _ = flow.expected(fl, v, start, HOURS, CONF)
        limit = exp if exp is not None else (d * HOURS / 24 if d else None)
        # Passato davanti / puoi alzare.
        if mine.get(v):
            low = min(p for p, _ in mine[v])
            book0 = sorted(others.get(v, []))
            under = [(p, a) for p, a in book0 if p < low]
            if under and st.get("first") and now - st.get("under_at", 0) >= SMART_REPEAT:
                st["under_at"] = now
                notify(f"Ti hanno passato davanti: {name}", f"Eri il più economico a {fmt(low)}, ora ci sono {fmt(sum(a for _, a in under))} pezzi sotto di te (il più basso a {fmt(under[0][0])}).", "arrow_down")
            st["first"] = not under
            if book0 and book0[0][0] >= low * (1 + RAISE_SHARE) and st.get("raise_price") != book0[0][0] and now - st.get("raise_at", 0) >= SMART_REPEAT:
                st["raise_at"], st["raise_price"] = now, book0[0][0]
                notify(f"Puoi alzare: {name}", f"Il più economico degli altri ora è a {fmt(book0[0][0])}, {round((book0[0][0] / low - 1) * 100)}% sopra il tuo {fmt(low)}: puoi rimettere a {fmt(book0[0][0] - 1)} e restare primo.", "arrow_up")
        if limit is not None and mine.get(v):
            top = max(p for p, _ in mine[v])
            book = sorted(others.get(v, []))
            ahead = sum(a for p, a in book if p < top)
            if ahead + units > limit:
                hours = hours_to_sell(fl, v, start, ahead + units, d)
                # Highest price that sells all your units within HOURS: units cheaper than you + yours <= demand.
                below, price = 0, None
                for i, (p, a) in enumerate(book):
                    if i == 0 or p != book[i - 1][0]:
                        if below + units <= limit:
                            price = p - 1
                        else:
                            break
                    below += a
                if price is None:
                    price = book[0][0] - 1 if book else top
                if price < top and (st["slow_price"] != price or now - st["slow_at"] >= REPEAT_MIN):
                    st["slow_at"], st["slow_price"] = now, price
                    cheaper = sum(a for p, a in book if p < min(p2 for p2, _ in mine[v]))
                    notify(f"Vendita lenta: {name}", f"Al tuo prezzo ({fmt(top)}) ci vorrebbero {'più di 7 giorni' if hours is None else f"circa {fmt(hours)} {'ora' if hours < 1.5 else 'ore'}"}: davanti a te ci sono {fmt(ahead)} pezzi più economici{f' ({fmt(cheaper)} sotto il tuo annuncio più basso)' if cheaper != ahead else ''}. Per vendere i tuoi {fmt(units)} pezzi entro {fmt(HOURS)} ore: {fmt(price)}.{' Attenzione: in queste ore gli altri mettono annunci al minimo quasi quanto se ne vendono, quindi anche al primo posto non è garantito.' if limit < units else ''}", "warning")
        state[v] = st
    os.makedirs(".alerts", exist_ok=True)
    json.dump(state, open(STATE, "w", encoding="utf-8"))


if __name__ == "__main__":
    main()
