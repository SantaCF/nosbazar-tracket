// Ricette dei metodi: unica fonte per le pagine Metodi e Oggi.
// Modifica solo qui. Tra "RICETTE =" e il ";" finale c'è JSON puro, così lo può leggere anche uno script Python.
// Per ogni metodo: ing = ingredienti per un craft (o una run), [vnum, quantità]; out = prodotti venduti [vnum, pezzi]
// (il primo è il prodotto principale); per_h = craft (o run) all'ora; crafts = prodotti intermedi che craftai dentro il metodo
// (es. le 5 mezze lune per run della PTS, già contate negli ingredienti: servono solo per la lista di cosa craftare);
// support = conversione che da sola non conviene ma nel piano trasforma i tuoi prodotti in materiali che ti servono. npc = prezzi fissi degli ingredienti comprati da NPC.
const RICETTE = {
  "npc": { "1072": 5000, "2029": 500, "2097": 100 },
  "npc_names": { "1072": "Attrezzi di produzione per gemme (NPC)", "2029": "Bottiglia vuota (NPC)", "2097": "Pozione magica (NPC)" },
  "methods": [
    { "name": "PTS 50-60 (mezze lune craftate)", "unit": "run", "per_h": 12, "color": "#2e90fa",
      "note": "3 account, ciclo 5 minuti, mezze lune prodotte da te",
      "ing": [[1012, 34], [1092, 1], [1014, 100], [1028, 25], [1072, 5]], "crafts": [[1029, 5]],
      "out": [[1013, 90], [1016, 12], [1027, 210]] },
    { "name": "PTS 50-60 (mezze lune comprate)", "unit": "run", "per_h": 12, "color": "#155eef",
      "note": "3 account, ciclo 5 minuti, mezze lune comprate al bazar",
      "ing": [[1012, 34], [1092, 1], [1029, 5]],
      "out": [[1013, 90], [1016, 12], [1027, 210]] },
    { "name": "Polvere da Gillion", "unit": "craft", "per_h": 2400, "color": "#98a2b3", "support": true,
      "note": "Malcolm Mix: 140 Pietre Gillion = 999 Polvere del sottosuolo (nosapki craft_profit/1014/2). Utile per usare le Gillion della PTS invece di venderle e ricomprare la polvere",
      "ing": [[1013, 140]], "out": [[1014, 999]] },
    { "name": "Mezze lune", "unit": "craft", "per_h": 2400, "color": "#7a5af8",
      "ing": [[1014, 20], [1028, 5], [1072, 1]], "out": [[1029, 1]] },
    { "name": "Luna piena", "unit": "craft", "per_h": 2400, "color": "#f79009",
      "ing": [[1014, 50], [1029, 5], [1072, 1]], "out": [[1030, 1]] },
    { "name": "Pozione HP divina", "unit": "craft", "per_h": 2400, "color": "#12b76a",
      "ing": [[1011, 30], [2029, 20], [2097, 20], [2196, 3]], "out": [[1242, 10]] },
    { "name": "Pozione dell'esperienza", "unit": "craft", "per_h": 2400, "color": "#ee46bc",
      "ing": [[1241, 1], [2029, 5], [2097, 5], [2196, 7], [2206, 7], [2214, 1]], "out": [[1249, 1]] },
    { "name": "Pozione SP base", "unit": "craft", "per_h": 2400, "color": "#0ba5ec",
      "ing": [[1241, 1], [2029, 5], [2097, 5], [2196, 5], [2208, 5], [2215, 1]], "out": [[1245, 1]] },
    { "name": "Sigillo Lord Draco", "unit": "craft", "per_h": 2400, "color": "#f04438",
      "note": "Grande mago Kan: 20 Semi della potenza + 20 Sabbia + 20 Pietre Gillion (nosapki craft_profit/5500/1). Usa i prodotti della PTS",
      "ing": [[1012, 20], [1027, 20], [1013, 20]], "out": [[5500, 1]] },
    { "name": "Sigillo Glacerus", "unit": "craft", "per_h": 2400, "color": "#53b1fd",
      "note": "Felix Frost: 20 Semi + 20 Cubetti di ghiaccio + 20 Fiori di ghiaccio (nosapki craft_profit/5512/1). Serve tanto oro per pezzo",
      "ing": [[1012, 20], [2307, 20], [5911, 20]], "out": [[5512, 1]] },
    { "name": "Sigillo Ragno nero", "unit": "craft", "per_h": 2400, "color": "#344054",
      "note": "8 Semi + 4 Mezze lune + 1 Pezzo spazio-temporale raid + 30 Tele di ragno + 3 Occhi del Re ragno (nosapki craft_profit/1130/2)",
      "ing": [[1012, 8], [1029, 4], [1094, 1], [2091, 30], [2092, 3]], "out": [[1130, 1]] },
    { "name": "Sigillo Slade", "unit": "craft", "per_h": 2400, "color": "#7f56d9",
      "note": "10 Semi + 5 Mezze lune + 1 Pezzo spazio-temporale raid + 40 Perle delle tenebre + 30 Artigli di Slade (nosapki craft_profit/1131/2)",
      "ing": [[1012, 10], [1029, 5], [1094, 1], [2094, 40], [2172, 30]], "out": [[1131, 1]] }
  ]
};
// Metodi pronti per i calcoli. tax() = commissione corrente (0 con la medaglia).
// cost(p) = oro speso per un'unità con i prezzi p(vnum); gain(p) = ricavo netto; need = item del bazar che servono;
// prod/out = prodotto principale e pezzi per unità (per contare gli annunci e la commissione minima).
const NPC = Object.fromEntries(Object.entries(RICETTE.npc).map(([k, v]) => [+k, v]));
const NPC_NAME = Object.fromEntries(Object.entries(RICETTE.npc_names).map(([k, v]) => [+k, v]));
function buildMethods(tax) {
  return RICETTE.methods.map(r => ({
    name: r.name, unit: r.unit, perH: r.per_h, color: r.color, note: r.note || "", ing: r.ing, outs: r.out, crafts: r.crafts || [], support: !!r.support,
    need: [...r.ing.map(x => x[0]).filter(v => !NPC[v]), ...r.out.map(x => x[0])],
    prod: r.out[0][0], out: r.out[0][1],
    cost: p => r.ing.reduce((t, [v, q]) => t + q * (NPC[v] ?? p(v)), 0),
    gain: p => r.out.reduce((t, [v, q]) => t + q * p(v), 0) * (1 - tax()),
  }));
}
