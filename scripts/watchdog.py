"""Phone notifications (ntfy) when price collection stops or fails.

    python3 scripts/watchdog.py --gap      # in the collect run: the previous run was more than GAP_MIN ago
    python3 scripts/watchdog.py --failed   # in the collect run, only if a step failed
    python3 scripts/watchdog.py --stale    # in watchdog.yml (hourly): the last saved run is older than STALE_MIN

Times in the messages are Italian time. Needs the NTFY_TOPIC secret.
"""
import glob, os, sys, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

GAP_MIN = 60
STALE_MIN = 75
TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
RUNS = "https://github.com/SantaCF/nosbazar-tracket/actions/workflows/collect.yml"


def notify(title, body, tags="warning"):
    if not TOPIC:
        print("NTFY_TOPIC mancante:", title); return
    req = urllib.request.Request("https://ntfy.sh/" + TOPIC, data=body.encode("utf-8"), method="POST",
                                 headers={"Title": title.encode("utf-8").decode("latin-1", "ignore"), "Tags": tags, "Click": RUNS})
    try:
        urllib.request.urlopen(req, timeout=20).read(); print("notifica inviata:", title)
    except Exception as e:
        print("notifica non inviata:", e)


def runs():
    out = []
    for f in sorted(glob.glob("data/listings/*/*.csv.gz")):
        d, n = f.split("/")[-2:]
        out.append(datetime.fromisoformat(f"{d}T{n[:2]}:{n[2:4]}+00:00"))
    return out


def it(t):
    return t.astimezone(ZoneInfo("Europe/Rome")).strftime("%d/%m %H:%M")


def span(minutes):
    return f"{round(minutes)} minuti" if minutes < 120 else f"{minutes / 60:.0f} ore"


def main():
    t = runs()
    now = datetime.now(timezone.utc)
    if "--failed" in sys.argv:
        notify("Giro del bazar non riuscito", f"Il giro delle {it(now)} è fallito. Se succede di nuovo apri la pagina dei giri.", "x")
    elif "--gap" in sys.argv and len(t) >= 2:
        gap = (t[-1] - t[-2]).total_seconds() / 60
        if gap > GAP_MIN:
            notify("Raccolta ripartita", f"Nessun giro tra le {it(t[-2])} e le {it(t[-1])} ({span(gap)}). Ora funziona di nuovo.", "white_check_mark")
    elif "--stale" in sys.argv and t:
        age = (now - t[-1]).total_seconds() / 60
        if age > STALE_MIN:
            notify("Raccolta ferma", f"L'ultimo giro salvato è delle {it(t[-1])} ({span(age)} fa). Controlla cron-job.org o la pagina dei giri.")


if __name__ == "__main__":
    main()
