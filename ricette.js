// Ricette dei metodi: unica fonte per le pagine Metodi e Oggi.
// Modifica solo qui. Tra "RICETTE =" e il ";" finale c'è JSON puro, così lo può leggere anche uno script Python.
// Per ogni metodo: ing = ingredienti per un craft (o una run), [vnum, quantità]; out = prodotti venduti [vnum, pezzi]
// (il primo è il prodotto principale); per_h = craft (o run) all'ora. npc = prezzi fissi degli ingredienti comprati da NPC.
const RICETTE = {
  "npc": { "1072": 5000, "2029": 500, "2097": 100 },
  "npc_names": { "1072": "Attrezzi di produzione per gemme (NPC)", "2029": "Bottiglia vuota (NPC)", "2097": "Pozione magica (NPC)" },
  "methods": [
    { "name": "PTS 50-60", "unit": "run", "per_h": 12, "color": "#2e90fa",
      "note": "3 account, ciclo 5 minuti, mezze lune prodotte da te",
      "ing": [[1012, 34], [1092, 1], [1014, 100], [1028, 25], [1072, 5]],
      "out": [[1013, 90], [1016, 12], [1027, 210]] },
    { "name": "Mezze lune", "unit": "craft", "per_h": 2400, "color": "#7a5af8",
      "ing": [[1014, 20], [1028, 5], [1072, 1]], "out": [[1029, 1]] },
    { "name": "Luna piena", "unit": "craft", "per_h": 2400, "color": "#f79009",
      "ing": [[1014, 50], [1029, 5], [1072, 1]], "out": [[1030, 1]] },
    { "name": "Pozione HP divina", "unit": "craft", "per_h": 2400, "color": "#12b76a",
      "ing": [[1011, 30], [2029, 20], [2097, 20], [2196, 3]], "out": [[1242, 10]] },
    { "name": "Pozione dell'esperienza", "unit": "craft", "per_h": 2400, "color": "#ee46bc",
      "ing": [[1241, 1], [2029, 5], [2097, 5], [2196, 7], [2206, 7], [2214, 1]], "out": [[1249, 1]] },
    { "name": "Pozione SP base", "unit": "craft", "per_h": 2400, "color": "#0ba5ec",
      "ing": [[1241, 1], [2029, 5], [2097, 5], [2196, 5], [2208, 5], [2215, 1]], "out": [[1245, 1]] }
  ]
};
// Metodi pronti per i calcoli. tax() = commissione corrente (0 con la medaglia).
// cost(p) = oro speso per un'unità con i prezzi p(vnum); gain(p) = ricavo netto; need = item del bazar che servono;
// prod/out = prodotto principale e pezzi per unità (per contare gli annunci e la commissione minima).
const NPC = Object.fromEntries(Object.entries(RICETTE.npc).map(([k, v]) => [+k, v]));
const NPC_NAME = Object.fromEntries(Object.entries(RICETTE.npc_names).map(([k, v]) => [+k, v]));
function buildMethods(tax) {
  return RICETTE.methods.map(r => ({
    name: r.name, unit: r.unit, perH: r.per_h, color: r.color, note: r.note || "", ing: r.ing, outs: r.out,
    need: [...r.ing.map(x => x[0]).filter(v => !NPC[v]), ...r.out.map(x => x[0])],
    prod: r.out[0][0], out: r.out[0][1],
    cost: p => r.ing.reduce((t, [v, q]) => t + q * (NPC[v] ?? p(v)), 0),
    gain: p => r.out.reduce((t, [v, q]) => t + q * p(v), 0) * (1 - tax()),
  }));
}
