// Venduti attesi nelle prossime X ore, dalla stessa fascia oraria dei giorni precedenti (data/flow.csv, vedi
// scripts/flow.py: stessa logica, stessi parametri). I giorni recenti pesano di più. Con meno di 3 giorni
// confrontabili usa finestre della stessa durata a qualsiasi ora delle ultime 72 ore (est: "finestre"), e se non
// bastano nemmeno quelle la media delle ultime 24 ore (sold_day, est: "media24").
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
// Flusso NETTO: pezzi venduti meno pezzi nuovi messi al minimo o sotto (scavalcano chi è già in vendita).
function expectedSold(vnum, start, hours, perDay, conf = flowConf()) {
  const sold = FLOW.units[vnum] || {}, under = FLOW.units["-" + vnum] || {}, u = {};
  for (const h of new Set([...Object.keys(sold), ...Object.keys(under)])) u[h] = (sold[h] || 0) - (under[h] || 0);
  const h0 = Math.floor(+new Date(start) / 3600e3), n = Math.max(1, Math.ceil(hours)), pts = [];
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
    return { units: Math.max(0, q), days: pts.length, est: "fascia", all: pts.map(p => p[0]) };
  }
  // Pochi giorni per questa fascia: finestre della stessa durata a qualsiasi ora delle ultime 72 ore. Non vede la
  // differenza sera/notte, ma vede che le vendite arrivano a blocchi (molte finestre senza vendite).
  const roll = [];
  for (let k = 1; k <= 72 - n + 1; k++) {
    let cov = 0, s = 0;
    for (let h = h0 - k - n + 1; h <= h0 - k; h++) { cov += FLOW.cover[h] || 0; s += u[h] || 0; }
    cov /= 60 * n;
    if (cov >= FLOW.MIN_COVER) roll.push(s / cov * hours / n);
  }
  if (roll.length >= 6) { roll.sort((a, b) => a - b); return { units: Math.max(0, roll[Math.min(roll.length - 1, Math.floor((1 - conf) * roll.length))]), days: pts.length, est: "finestre", all: roll, windows: roll.length }; }
  return perDay > 0 ? { units: perDay * hours / 24, days: pts.length, est: "media24" } : { units: 0, days: pts.length, est: null };
}
// Ore che servono per vendere qty pezzi a partire da start (prima ora in cui i venduti attesi arrivano a qty), max 7 giorni.
function hoursToSell(vnum, start, qty, perDay, conf = flowConf()) {
  if (!(qty > 0)) return 0;
  for (let h = 1; h <= 168; h++) { const e = expectedSold(vnum, start, h, perDay, conf); if (!e.est) return null; if (e.units >= qty) return h; }
  return null;
}
