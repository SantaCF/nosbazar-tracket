// Minigiochi del Miniland, livelli 4 e 5 (i più bassi non conviene prenderli, Alessio 15/11).
// Ogni livello: [vnum, pezzi, probabilità %] come nelle tabelle del gioco. Le probabilità non sempre sommano a 100
// (es. Stagno liv. 5 = 88%): le tratto come pesi, cioè una ricompensa a partita, scelta in proporzione.
// Ogni partita costa 50 punti produzione, uguale per tutti: il confronto è quindi per partita.
const MINIGIOCHI = {
  "Stagno magnifico": {
    4: [[2037, 4, 2], [2041, 4, 1], [2045, 4, 20], [2049, 4, 2], [2196, 2, 20], [2200, 2, 10], [1028, 2, 25], [1029, 2, 25]],
    5: [[2213, 1, 1], [2214, 1, 1], [2215, 1, 2], [2216, 1, 1], [2196, 2, 40], [2204, 1, 5], [2261, 2, 2], [1030, 2, 35], [9356, 1, 1]] },
  "Campo da tiro magnifico": {
    4: [[2037, 4, 2], [2041, 4, 1], [2045, 4, 2], [2049, 4, 20], [2195, 2, 20], [2199, 2, 10], [1028, 2, 25], [1029, 2, 20]],
    5: [[2213, 1, 1], [2214, 1, 1], [2215, 1, 1], [2216, 1, 2], [2195, 2, 40], [2203, 1, 20], [1030, 2, 35], [9356, 1, 1]] },
  "Segheria eccellente": {
    4: [[2037, 4, 2], [2041, 4, 15], [2045, 4, 1], [2049, 4, 2], [2194, 2, 15], [2198, 2, 10], [2231, 2, 15], [1028, 2, 25], [1029, 2, 15]],
    5: [[2213, 1, 2], [2214, 1, 3], [2215, 1, 2], [2216, 1, 2], [2194, 2, 40], [2202, 1, 6], [1030, 2, 40], [9356, 1, 1]] },
  "Cava magnifica": {
    4: [[2037, 4, 20], [2041, 4, 2], [2045, 4, 1], [2049, 4, 2], [2193, 2, 20], [2197, 2, 10], [2226, 2, 15], [1028, 2, 25], [1029, 2, 20]],
    5: [[2213, 1, 2], [2214, 1, 1], [2215, 1, 1], [2216, 1, 1], [2193, 2, 40], [2201, 1, 5], [1030, 2, 35], [9356, 1, 1]] },
};

// Loot aggiunti alla raccolta il 15/11: per qualche giorno le vendite al giorno non sono ancora misurate.
const MG_NEW = { since: "2026-11-15", days: 3, vnums: [2037, 2041, 2045, 2049, 2213, 2216, 9356, 2200, 2261, 2195, 2199, 2194, 2198, 2231, 2193, 2197, 2226] };
const mgNoData = v => MG_NEW.vnums.includes(+v) && Date.now() - new Date(MG_NEW.since) < MG_NEW.days * 864e5;

// Valore atteso a partita per ogni minigioco e livello, ai prezzi di vendita realistici dell'ultimo giro.
// items: { vnum: { name, sell, wp10, day } } da data/latest.csv.
function minigiochiRows(items, tax) {
  const price = v => { const it = items[v]; if (!it) return null; return it.sell > 0 ? it.sell : it.wp10 > 0 ? it.wp10 : null; };
  const rows = [];
  for (const [game, levels] of Object.entries(MINIGIOCHI))
    for (const [lv, loot] of Object.entries(levels)) {
      const w = loot.reduce((t, x) => t + x[2], 0);
      let ev = 0; const parts = [], missing = [];
      for (const [v, q, p] of loot) {
        const pr = price(v), share = p / w;
        if (pr == null) { missing.push(v); continue; }
        const val = share * q * pr * (1 - tax);
        ev += val; parts.push({ v, q, p: share, price: pr, val, day: items[v]?.day || 0, name: items[v]?.name || v, noData: mgNoData(v) });
      }
      parts.sort((a, b) => b.val - a.val);
      rows.push({ game, lv: +lv, ev, parts, missing });
    }
  return rows.sort((a, b) => b.ev - a.ev);
}
