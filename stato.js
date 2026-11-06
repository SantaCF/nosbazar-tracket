// Avviso in cima alla pagina se la raccolta dei prezzi è ferma (ultimo giro più vecchio di 45 minuti).
(async () => {
  try {
    const t = await (await fetch("data/latest.csv?" + Date.now())).text();
    const ts = t.split(/\r?\n/)[1]?.split(",")[0]; if (!ts) return;
    const min = (Date.now() - new Date(ts)) / 6e4; if (min < 45) return;
    const when = new Date(ts).toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
    const age = min < 120 ? Math.round(min) + " minuti" : Math.round(min / 60) + " ore";
    const d = document.createElement("div");
    d.style.cssText = "background:#b42318;color:#fff;padding:10px 12px;border-radius:10px;margin:0 0 10px;font-size:14px";
    d.innerHTML = `<b>Raccolta ferma</b>: l'ultimo giro è delle ${when} (${age} fa), i dati non sono aggiornati. ` +
      `<a style="color:#fff" href="https://github.com/SantaCF/nosbazar-tracket/actions/workflows/collect.yml">Controlla i giri</a>`;
    (document.querySelector("main") || document.body).prepend(d);
  } catch (e) {}
})();
