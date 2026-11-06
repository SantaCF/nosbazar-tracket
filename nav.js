// Barra in alto e menu comune a tutte le pagine: <div id="nav"></div> + <script src="nav.js"></script> subito dopo.
// Sul telefono il menu sta in basso; le Impostazioni sono l'ingranaggio in alto a destra.
(() => {
  const ic = d => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const I = {
    oggi: ic('<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>'),
    prezzi: ic('<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>'),
    metodi: ic('<path d="M9 3h6"/><path d="M10 3v6L5 19a1.5 1.5 0 0 0 1.3 2h11.4a1.5 1.5 0 0 0 1.3-2L14 9V3"/><path d="M7.5 15h9"/>'),
    flip: ic('<path d="M17 3l4 4-4 4"/><path d="M3 7h18"/><path d="M7 21l-4-4 4-4"/><path d="M21 17H3"/>'),
    bil: ic('<rect x="3" y="6" width="18" height="14" rx="2"/><path d="M3 10h18"/><path d="M16 15h2"/><path d="M7 6V4h10v2"/>'),
    set: ic('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>'),
  };
  const pages = [["./", "Oggi", I.oggi], ["prezzi.html", "Prezzi", I.prezzi], ["metodi.html", "Metodi", I.metodi],
    ["flipping.html", "Flipping", I.flip], ["bilancio.html", "Bilancio", I.bil], ["impostazioni.html", "Impostazioni", I.set, "set"]];
  let here = location.pathname.split("/").pop() || "./"; if (here === "index.html") here = "./";
  const tabs = pages.map(([href, name, svg, c]) => `<a href="${href}" class="${[c, href === here ? "on" : ""].join(" ").trim()}"${href === here ? ' aria-current="page"' : ""}>${svg}<span>${name}</span></a>`).join("");
  const head = document.createElement("header");
  head.className = "top";
  head.innerHTML = `<div class="top-in"><a class="brand" href="./"><i>N</i>NosBazar <small>Dragonveil</small></a>` +
    `<nav class="tabs" aria-label="Pagine">${tabs}</nav>` +
    `<a class="gear${here === "impostazioni.html" ? " on" : ""}" href="impostazioni.html" aria-label="Impostazioni">${I.set}</a></div>`;
  document.body.prepend(head);
  document.getElementById("nav")?.remove();
})();
