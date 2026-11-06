// Venduti attesi nelle prossime X ore, dalla stessa fascia oraria dei giorni precedenti (data/flow.csv, vedi
// scripts/flow.py: stessa logica, stessi parametri). I giorni recenti pesano di più. Con meno di 3 giorni
// confrontabili usa la media delle ultime 24 ore (sold_day), e lo dice (est: "media24").
const FLOW = { cover: {}, units: {}, ready: false, DAYS: 28, DECAY: 0.85, MIN_DAYS: 3, MIN_COVER: 0.6 };
async function loadFlow() {
  if (FLOW.ready) return FLOW;
  try {
    const r = await fetch("data/flow.csv?" + Date.now()); if (!r.ok) throw 0; const t = await r.text();
    t.trim().split(/\r?\n/).slice(1).forEach(l => { const [h, v, u] = l.split(","); if (v === "0") FLOW.cover[h] = +u; else (FLOW.units[v] ??= {})[h] = +u; });
  } catch (e) {}
  FLOW.ready = true; return FLOW;
}
function flowConf() { try { return Math.min(0.95, Math.max(0.5, +(localStorage.getItem("conf") || 0.7))); } catch (e) { return 0.7; } }
// -> { units, days, est }: est = "fascia" (dai giorni passati) o "media24" (media 24h, pochi dati) o null (niente dati).
function expectedSold(vnum, start, hours, perDay, conf = flowConf()) {
  const u = FLOW.units[vnum] || {}, h0 = Math.floor(+new Date(start) / 3600e3), n = Math.max(1, Math.ceil(hours)), pts = [];
  for (let k = 1; k <= FLOW.DAYS; k++) {
    let cov = 0, s = 0;
    for (let h = h0 - 24 * k; h < h0 - 24 * k + n; h++) { cov += FLOW.cover[h] || 0; s += u[h] || 0; }
    cov /= 60 * n;
    if (cov >= FLOW.MIN_COVER) pts.push([s / cov * hours / n, Math.pow(FLOW.DECAY, k - 1)]);
  }
  if (pts.length >= FLOW.MIN_DAYS) {
    pts.sort((a, b) => a[0] - b[0]);
    const tot = pts.reduce((t, p) => t + p[1], 0); let run = 0, q = pts[pts.length - 1][0];
    for (const [v, w] of pts) { run += w; if (run >= (1 - conf) * tot) { q = v; break; } }
    return { units: q, days: pts.length, est: "fascia", all: pts.map(p => p[0]) };
  }
  return perDay > 0 ? { units: perDay * hours / 24, days: pts.length, est: "media24" } : { units: 0, days: pts.length, est: null };
}
// Ore che servono per vendere qty pezzi a partire da start (prima ora in cui i venduti attesi arrivano a qty), max 7 giorni.
function hoursToSell(vnum, start, qty, perDay, conf = flowConf()) {
  if (!(qty > 0)) return 0;
  const first = expectedSold(vnum, start, 24, perDay, conf);
  if (first.est !== "fascia") return perDay > 0 ? qty / perDay * 24 : null;
  for (let h = 1; h <= 168; h++) if (expectedSold(vnum, start, h, perDay, conf).units >= qty) return h;
  return null;
}
