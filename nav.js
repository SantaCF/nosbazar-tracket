// Menu comune a tutte le pagine: <div id="nav"></div> + <script src="nav.js"></script> subito dopo.
(() => {
  const pages = [["./", "Oggi"], ["prezzi.html", "Prezzi"], ["metodi.html", "Metodi"], ["flipping.html", "Flipping"], ["bilancio.html", "Bilancio"], ["impostazioni.html", "⚙ Impostazioni"]];
  const here = location.pathname.split("/").pop() || "./";
  const el = document.getElementById("nav"); if (!el) return;
  el.className = "nav"; el.style.cssText = "margin:4px 0 12px;font-size:14px;line-height:1.9";
  el.innerHTML = pages.map(([href, name]) => (href === here || (here === "index.html" && href === "./")) ? `<b>${name}</b>` : `<a href="${href}" style="color:var(--link,#1f6feb)">${name}</a>`).join(" · ");
})();
