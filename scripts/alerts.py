"""Phone notifications (ntfy) about your own bazaar listings.

Each run looks for the listings of your characters in the latest snapshot and sends a notification when:
  - you sold most of an item (SOLD_SHARE, default 80%) and when it is all gone;
  - selling would take too long at your price (more than ALERT_HOURS, default 24): the units cheaper
    than yours plus yours exceed what the bazaar sells in that time (sold_day estimate). It suggests the
    price that sells everything within ALERT_HOURS.

Configuration comes from repository secrets, so names are never written in this public repo:
  NOS_SELLERS   character names, comma separated (not case sensitive)
  NTFY_TOPIC    the ntfy topic subscribed in the phone app
  ALERT_HOURS   optional, hours you are willing to wait (default 24)
State (what was already notified) lives in .alerts/state.json, kept between runs by the Actions cache.
Units that vanish before expiry count as sold: if you withdraw a listing yourself it counts as sold too.
"""
import csv, glob, gzip, json, os, urllib.request
from datetime import datetime, timezone

SELLERS = {s.strip().lower() for s in os.environ.get("NOS_SELLERS", "").split(",") if s.strip()}
TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
HOURS = float(os.environ.get("ALERT_HOURS") or 24)
SOLD_SHARE = 0.8
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
    first = not os.path.exists(STATE)
    state = {} if first else json.load(open(STATE, encoding="utf-8"))
    d_, f_ = files[-1].split("/")[-2:]
    now = int(datetime.fromisoformat(f"{d_}T{f_[:2]}:{f_[2:4]}+00:00").timestamp() // 60)   # minutes since epoch
    if first:
        items = ", ".join(f"{names.get(v, v)} ({fmt(sum(a for _, a in l))})" for v, l in mine.items()) or "nessun annuncio trovato adesso"
        notify("Notifiche bazar attive", f"Ti avviso quando vendi l'{round(SOLD_SHARE * 100)}% e quando venderesti in più di {fmt(HOURS)} ore. Annunci tuoi: {items}", "white_check_mark")
    for v in set(mine) | set(state):
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
        if d and d > 0:
            top = max(p for p, _ in mine[v])
            book = sorted(others.get(v, []))
            ahead = sum(a for p, a in book if p < top)
            hours = (ahead + units) / d * 24
            if hours > HOURS:
                # Highest price that sells all your units within HOURS: units cheaper than you + yours <= demand.
                limit, below, price = d * HOURS / 24, 0, None
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
                    notify(f"Vendita lenta: {name}", f"Al tuo prezzo ({fmt(top)}) ci vorrebbero circa {fmt(hours)} {'ora' if hours < 1.5 else 'ore'}: davanti a te ci sono {fmt(ahead)} pezzi più economici{f' ({fmt(cheaper)} sotto il tuo annuncio più basso)' if cheaper != ahead else ''}. Per vendere i tuoi {fmt(units)} pezzi entro {fmt(HOURS)} ore: {fmt(price)}.", "warning")
        state[v] = st
    os.makedirs(".alerts", exist_ok=True)
    json.dump(state, open(STATE, "w", encoding="utf-8"))


if __name__ == "__main__":
    main()
