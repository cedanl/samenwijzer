// Outreach: tab-navigatie, verwijzing-keuze en AI-conceptbericht (SSE).

(function () {
  const dataEl = document.getElementById("outreach-data");
  const pagina = dataEl ? JSON.parse(dataEl.textContent) : { tab: "werklijst", verwijzingen: {} };

  // ── Tabs ──────────────────────────────────────────────────────────────────
  const tabs = document.querySelectorAll(".sw-tab");
  const panelen = document.querySelectorAll(".sw-tabpanel");
  function toonTab(naam) {
    tabs.forEach((t) => t.classList.toggle("sw-tab--actief", t.dataset.tab === naam));
    panelen.forEach((p) => (p.hidden = p.dataset.panel !== naam));
    const url = new URL(window.location);
    url.searchParams.set("tab", naam);
    history.replaceState(null, "", url);
  }
  tabs.forEach((t) => t.addEventListener("click", () => toonTab(t.dataset.tab)));
  toonTab(pagina.tab || "werklijst");

  // ── Per studentkaart: verwijzing + genereer-knop ──────────────────────────
  document.querySelectorAll(".outreach-card").forEach((kaart) => {
    const snr = kaart.dataset.snr;
    const check = kaart.querySelector(".verwijzing-check");
    const catSelect = kaart.querySelector(".verwijzing-cat");
    const info = kaart.querySelector(".verwijzing-info");
    const knop = kaart.querySelector(".genereer-btn");
    const spinner = kaart.querySelector(".sw-spinner");
    const fout = kaart.querySelector(".genereer-fout");
    const tekstveld = kaart.querySelector("textarea[name=bericht]");

    function toonVerwijzing() {
      const actief = check.checked;
      catSelect.hidden = !actief;
      const v = actief ? pagina.verwijzingen[catSelect.value] : null;
      info.hidden = !v;
      if (v) info.textContent = `${v.rol} — ${v.toelichting}`;
    }
    check.addEventListener("change", toonVerwijzing);
    catSelect.addEventListener("change", toonVerwijzing);

    knop.addEventListener("click", () => {
      const toon = kaart.querySelector("input[name=toon-kies]:checked")?.value || "vriendelijk";
      const body = {
        studentnummer: snr,
        toon: toon,
        verwijzing_categorie: check.checked ? catSelect.value : null,
      };
      tekstveld.value = "";
      fout.hidden = true;
      knop.disabled = true;
      spinner.hidden = false;
      swStream("/outreach/api/bericht", body, {
        onChunk(chunk) {
          tekstveld.value += chunk;
        },
        onDone() {
          knop.disabled = false;
          spinner.hidden = true;
        },
        onError(melding) {
          knop.disabled = false;
          spinner.hidden = true;
          fout.textContent = `Bericht genereren mislukt: ${melding}`;
          fout.hidden = false;
        },
      });
    });
  });
})();
