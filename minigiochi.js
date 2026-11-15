// Minigiochi del Miniland, livelli 4 e 5 (i più bassi non conviene prenderli, Alessio 15/11).
// Ogni livello: [vnum, pezzi, probabilità %] come nelle tabelle del gioco. Le probabilità non sempre sommano a 100
// (es. Stagno liv. 5 = 88%): le tratto come pesi, cioè una ricompensa a partita, scelta in proporzione.
// Ogni partita dà il premio a due pg (chi gioca + l'host) e costa uguale in tutti i minigiochi (Alessio 15/11):
// 100 punti produzione (80 con la fata −20%; 2.000 al giorno per pg), 30 di durabilità del minigioco dell'host (1 = 100 oro, max 12.000).
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

const MG_COST = { rewards: 2, pp: 100, ppFairy: 80, dur: 30, durGold: 100, durMax: 12000, ppCoupon: 500, durCoupon: 300 };
const MG_COUPON = { prod: 1271, dur: 1269, reward: 1270 };

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
      rows.push({ game, lv: +lv, ev, parts, missing, game2: ev * MG_COST.rewards });
    }
  return rows.sort((a, b) => b.ev - a.ev);
}

// Coupon: costo a partita ai prezzi di adesso e se conviene.
function minigiochiCoupons(items, rows) {
  const pr = v => { const it = items[v]; return it ? (it.sell > 0 ? it.sell : it.wp10 > 0 ? it.wp10 : null) : null; };
  const C = MG_COST, prod = pr(MG_COUPON.prod), dur = pr(MG_COUPON.dur), rew = pr(MG_COUPON.reward);
  const durGame = C.dur * C.durGold;
  const ppGame = prod == null ? null : prod * C.pp / C.ppCoupon, ppGameF = prod == null ? null : prod * C.ppFairy / C.ppCoupon;
  const durCouponPer = dur == null ? null : dur / C.durCoupon;
  // Il premio più grosso che può uscire (pezzi × prezzo), per capire quando raddoppiarlo conviene.
  // I premi che valgono più del coupon: solo su questi raddoppiare conviene.
  const big = {};
  if (rew != null) rows.forEach(r => r.parts.forEach(x => { const v = x.q * x.price; if (v > rew) big[x.v] = { val: v, name: x.name, q: x.q, noData: x.noData, day: x.day }; }));
  return { prod, dur, rew, durGame, ppGame, ppGameF, durCouponPer, big: Object.values(big).sort((a, b) => b.val - a.val),
    net: r => r.game2 - durGame - (ppGame || 0) };
}
