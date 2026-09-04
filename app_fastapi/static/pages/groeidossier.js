// Groeidossier — tabs, AI-aanscherpen (SSE) en Plotly-grafieken.

(function () {
  // ── Tabs ──────────────────────────────────────────────────────────────────
  const tabs = document.querySelectorAll(".gd-tab");
  const panelen = { };
  document.querySelectorAll(".gd-panel").forEach((p) => {
    panelen[p.id.replace("tab-", "")] = p;
  });

  let plotsGetekend = false;
  function toonTab(naam) {
    tabs.forEach((t) => t.classList.toggle("is-actief", t.dataset.tab === naam));
    Object.entries(panelen).forEach(([key, p]) => { p.hidden = key !== naam; });
    if (!plotsGetekend && (naam === "historie" || naam === "spinneweb")) {
      tekenGrafieken();
      plotsGetekend = true;
    }
  }
  tabs.forEach((t) => t.addEventListener("click", () => toonTab(t.dataset.tab)));

  const config = document.getElementById("gd-config");
  const startTab = config ? JSON.parse(config.textContent).tab : "scores";
  if (tabs.length) toonTab(startTab);

  // ── Plotly: historie-lijnchart + spinnewebben ─────────────────────────────
  function tekenGrafieken() {
    if (typeof Plotly === "undefined") return;

    const histEl = document.getElementById("gd-hist-data");
    const histDoel = document.getElementById("gd-hist-chart");
    if (histEl && histDoel) {
      const punten = JSON.parse(histEl.textContent || "[]");
      const perWp = {};
      punten.forEach((p) => {
        (perWp[p.werkproces] ??= { x: [], y: [] });
        perWp[p.werkproces].x.push(p.datum);
        perWp[p.werkproces].y.push(p.score);
      });
      const traces = Object.entries(perWp).map(([naam, d]) => ({
        x: d.x, y: d.y, name: naam, mode: "lines+markers", type: "scatter",
      }));
      if (traces.length) {
        Plotly.newPlot(histDoel, traces, {
          margin: { t: 20, r: 10, b: 40, l: 40 },
          yaxis: { range: [0, 105], title: "score" },
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          font: { color: getComputedStyle(document.body).getPropertyValue("--text") },
          legend: { orientation: "h" },
        }, { responsive: true, displayModeBar: false });
      }
    }

    document.querySelectorAll(".gd-spin-data").forEach((el) => {
      const doel = document.getElementById(el.dataset.doel);
      if (!doel) return;
      const fig = JSON.parse(el.textContent);
      Plotly.newPlot(doel, fig.data, fig.layout, { responsive: true, displayModeBar: false });
    });
  }

  // ── AI-aanscherpen via SSE ────────────────────────────────────────────────
  document.querySelectorAll(".gd-aanscherp__btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const wp = btn.dataset.wp;
      const slider = document.querySelector(`input[name="score__${wp}"]`);
      const tekstveld = document.querySelector(`textarea[name="verant__${wp}"]`);
      const uit = document.getElementById(`aanscherp-${wp}`);
      if (!uit) return;

      btn.disabled = true;
      uit.hidden = false;
      uit.innerHTML = "<b>Suggestie:</b><br>";
      const span = document.createElement("span");
      uit.appendChild(span);
      const spinner = swEl("span", "sw-spinner");
      uit.appendChild(spinner);

      swStream("/groeidossier/aanscherpen", {
        wp_kolom: wp,
        tekst: tekstveld ? tekstveld.value : "",
        score: slider ? Number(slider.value) : 50,
      }, {
        onChunk: (chunk) => { span.textContent += chunk; },
        onDone: () => { spinner.remove(); btn.disabled = false; },
        onError: (fout) => {
          spinner.remove();
          btn.disabled = false;
          span.textContent = fout === "timeout"
            ? "De AI-service reageert niet. Probeer het later opnieuw."
            : fout;
        },
      });
    });
  });
})();
