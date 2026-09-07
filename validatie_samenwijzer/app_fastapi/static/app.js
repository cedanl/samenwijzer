"use strict";
/* Publieke landing + chat-overlay. Rendering/streaming/viewer komen uit chat.js. */

/* ── mock-up: staggered reveal + marker sweep ─────────────────────────────── */
const io = new IntersectionObserver((entries) => {
  entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
}, { threshold: 0.15 });
document.querySelectorAll(".rise").forEach((el) => io.observe(el));
window.addEventListener("load", () => {
  document.querySelectorAll("header .rise").forEach((el) => el.classList.add("in"));
});
const mDoc = document.getElementById("m-doc");
if (mDoc) {
  const mIo = new IntersectionObserver((es) => es.forEach((e) => {
    if (e.isIntersecting) { setTimeout(() => mDoc.classList.add("lit"), 600); mIo.unobserve(e.target); }
  }), { threshold: 0.6 });
  mIo.observe(mDoc);
}

/* ── chat-overlay ─────────────────────────────────────────────────────────── */
const overlay = document.getElementById("overlay");
const thread = document.getElementById("thread");
const picker = document.getElementById("picker");
const ovLabels = document.getElementById("ovLabels");
const ovAsk = document.getElementById("ovAsk");
const ovReset = document.getElementById("ovReset");
const ovClose = document.getElementById("ovClose");
const ovPdfBtn = document.getElementById("ovPdfBtn");
const pdfFrame = document.getElementById("pdfFrame");
let oerIds = [];

/* ── opleidingskiezer-cascade (gedeeld: startpagina + picker) ──────────────── */
let _oplBoom = null;
async function laadOplBoom() {
  if (!_oplBoom) _oplBoom = await (await fetch("/api/opleidingen")).json();
  return _oplBoom;
}

function _vulOpties(sel, labels, placeholder) {
  sel.innerHTML = `<option value="">${esc(placeholder)}</option>` +
    labels.map((t, i) => `<option value="${i}">${esc(t)}</option>`).join("");
}

/* Max. aantal OER-id's dat /api/kies accepteert; de kiezer bewaakt dezelfde grens. */
const MAX_GIDSEN = 3;

/* Bouwt 4 afhankelijke selects + een lijstje gekozen studiegidsen in `container`.
   Je kunt meerdere opleidingen, leerwegen of scholen naast elkaar zetten (tot MAX_GIDSEN
   OER's, de grens die /api/kies hanteert). Roept onKies(oerIds[]) aan bij openen. */
function bouwCascade(container, boom, onKies) {
  container.innerHTML = `
    <div class="cascade">
      <select class="cas-inst" aria-label="School"></select>
      <select class="cas-lw" aria-label="Leerweg" disabled></select>
      <select class="cas-opl" aria-label="Opleiding" disabled></select>
      <select class="cas-coh" aria-label="Cohort" disabled hidden></select>
      <div class="cas-acties">
        <button type="button" class="cas-add" disabled>+ Nog een erbij</button>
        <button type="button" class="iconbtn cas-start" disabled>Open mijn studiegids →</button>
      </div>
    </div>
    <div class="cas-gekozen" hidden></div>`;
  const selI = container.querySelector(".cas-inst");
  const selL = container.querySelector(".cas-lw");
  const selO = container.querySelector(".cas-opl");
  const selC = container.querySelector(".cas-coh");
  const addBtn = container.querySelector(".cas-add");
  const btn = container.querySelector(".cas-start");
  const lijst = container.querySelector(".cas-gekozen");
  let inst = null, lw = null, opl = null;
  const gekozen = [];

  const resetSel = (sel, ph) => { sel.innerHTML = `<option value="">${esc(ph)}</option>`; sel.disabled = true; };

  /* De volledig ingevulde selectie, of null zolang er nog een keuze ontbreekt. */
  const huidige = () => {
    if (!opl) return null;
    if (opl.cohorten.length > 1 && selC.value === "") return null;
    const coh = opl.cohorten.length === 1 ? opl.cohorten[0] : opl.cohorten[Number(selC.value)];
    return { label: `${inst.instelling} · ${opl.naam} · ${lw.leerweg} ${coh.cohort}`, ids: coh.oer_ids };
  };
  const gekozenIds = () => gekozen.reduce((acc, g) => acc.concat(g.ids), []);

  const teken = () => {
    lijst.hidden = gekozen.length === 0;
    lijst.innerHTML = gekozen.map((g, i) =>
      `<span class="cas-chip">${esc(g.label)}<button type="button" data-i="${i}" aria-label="Verwijder ${esc(g.label)}">×</button></span>`
    ).join("");
    const h = huidige();
    const ruimte = MAX_GIDSEN - gekozenIds().length;
    addBtn.disabled = !h || h.ids.length > ruimte;
    addBtn.hidden = gekozen.length > 0 && ruimte <= 0;
    btn.disabled = !h && gekozen.length === 0;
    const n = gekozen.length + (h ? 1 : 0);
    btn.textContent = n > 1 ? `Vergelijk ${n} studiegidsen →` : "Open mijn studiegids →";
  };

  /* Zet de selects terug op schoolniveau zodat je meteen een volgende kunt kiezen. */
  const leegSelectie = () => {
    inst = null; lw = null; opl = null;
    selI.value = "";
    resetSel(selL, "Leerweg…"); resetSel(selO, "Opleiding…"); resetSel(selC, "Cohort…"); selC.hidden = true;
  };

  _vulOpties(selI, boom.map((b) => b.instelling), "Kies je school…");
  resetSel(selL, "Leerweg…"); resetSel(selO, "Opleiding…"); resetSel(selC, "Cohort…");

  selI.addEventListener("change", () => {
    inst = selI.value === "" ? null : boom[Number(selI.value)];
    lw = null; opl = null;
    resetSel(selL, "Leerweg…"); resetSel(selO, "Opleiding…"); resetSel(selC, "Cohort…"); selC.hidden = true;
    if (inst) { _vulOpties(selL, inst.leerwegen.map((x) => x.leerweg), "Leerweg…"); selL.disabled = false; }
    teken();
  });
  selL.addEventListener("change", () => {
    lw = selL.value === "" ? null : inst.leerwegen[Number(selL.value)];
    opl = null;
    resetSel(selO, "Opleiding…"); resetSel(selC, "Cohort…"); selC.hidden = true;
    if (lw) { _vulOpties(selO, lw.opleidingen.map((x) => x.naam), "Opleiding…"); selO.disabled = false; }
    teken();
  });
  selO.addEventListener("change", () => {
    opl = selO.value === "" ? null : lw.opleidingen[Number(selO.value)];
    resetSel(selC, "Cohort…"); selC.hidden = true;
    if (opl && opl.cohorten.length > 1) {
      _vulOpties(selC, opl.cohorten.map((c) => c.cohort), "Cohort…");
      selC.disabled = false; selC.hidden = false;
    }
    teken();
  });
  selC.addEventListener("change", teken);

  addBtn.addEventListener("click", () => {
    const h = huidige();
    if (!h) return;
    gekozen.push(h);
    leegSelectie();
    teken();
  });
  lijst.addEventListener("click", (e) => {
    const i = e.target.dataset && e.target.dataset.i;
    if (i === undefined) return;
    gekozen.splice(Number(i), 1);
    teken();
  });
  btn.addEventListener("click", () => {
    const h = huidige();
    const ids = gekozenIds().concat(h ? h.ids : []).slice(0, MAX_GIDSEN);
    if (ids.length) onKies(ids);
  });

  teken();
}

/* Laadt de gekozen studiegids in de sessie en opent de chat (gedeeld door beide paden). */
async function laadStudiegidsEnOpen(ids) {
  openOverlay();
  if (!_gehydrateerd) { _gehydrateerd = true; await rehydrateer(thread); }
  const r = await (await fetch("/api/kies", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ oer_ids: ids }),
  })).json();
  oerIds = r.oer_ids || ids;
  setLabels(r.labels);
  setBanner(r.oer_onleesbaar);
  if (r.wachtende_vraag) { await streamAntwoord(thread, r.wachtende_vraag); }
  else { ovAsk.querySelector("input").focus(); }
}

let _gehydrateerd = false;
function openOverlay() { overlay.classList.add("open"); document.body.style.overflow = "hidden"; }
function setLabels(labels) {
  ovLabels.innerHTML = (labels || []).map((l) => `<span class="ov-label">${esc(l)}</span>`).join("");
  ovPdfBtn.style.display = oerIds.length ? "" : "none";
}
function setBanner(onleesbaar) {
  const b = document.getElementById("ovBanner");
  if (!b) return;
  b.hidden = !onleesbaar;
  if (onleesbaar) b.textContent =
    "De OER van deze opleiding is niet machine-leesbaar; antwoorden komen uit het landelijke kwalificatiedossier en de instellingsregelingen.";
}

/* POST /api/vraag + modus-routering (gedeeld door start() en de ovAsk-handler). */
async function routeerVraag(vraag) {
  const r = await (await fetch("/api/vraag", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vraag }),
  })).json();
  if (r.modus === "kies") { renderPicker(); return; }
  // Chat/intake: een eventuele nog-zichtbare picker uit een eerder kies-ronde moet weg —
  // anders kan een klik erop later de net-geladen (of nog te laden) bron overschrijven.
  picker.innerHTML = "";
  if (r.modus === "chat") { oerIds = r.oer_ids || oerIds; setLabels(r.labels); setBanner(r.oer_onleesbaar); }
  await streamAntwoord(thread, vraag);
}

async function start(vraag) {
  openOverlay();
  // Eerst de bestaande historie herstellen (awaited), dán de nieuwe vraag — anders
  // landt de async-opgehaalde historie ónder de nieuwe beurt.
  if (!_gehydrateerd) { _gehydrateerd = true; await rehydrateer(thread); }
  addVraag(thread, vraag);
  await routeerVraag(vraag);
}

async function renderPicker() {
  const boom = await laadOplBoom();
  picker.innerHTML = `
    <div class="picker">
      <h3>Welke studiegids is van jou?</h3>
      <div class="hint">Kies je school, leerweg en opleiding.</div>
      <div id="pickerCascade" class="cascade-host"></div>
    </div>`;
  bouwCascade(picker.querySelector("#pickerCascade"), boom, async (ids) => {
    const r = await (await fetch("/api/kies", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ oer_ids: ids }),
    })).json();
    oerIds = r.oer_ids || ids;
    setLabels(r.labels);
    setBanner(r.oer_onleesbaar);
    picker.innerHTML = "";
    if (r.wachtende_vraag) await streamAntwoord(thread, r.wachtende_vraag);
  });
}

ovPdfBtn.addEventListener("click", () => {
  if (!oerIds.length) return;
  if (pdfFrame.style.display === "block") { pdfFrame.style.display = "none"; pdfFrame.innerHTML = ""; }
  else { mountStudiegids(oerIds[0], pdfFrame); pdfFrame.style.display = "block"; }
});

// Niet-destructief sluiten: verbergt de overlay, behoudt gesprek/gekozen studiegids
// (in tegenstelling tot ovReset hierboven, die /api/reset aanroept en alles wist).
ovClose.addEventListener("click", () => {
  overlay.classList.remove("open"); document.body.style.overflow = "";
});

ovReset.addEventListener("click", async () => {
  await fetch("/api/reset", { method: "POST" });
  overlay.classList.remove("open"); document.body.style.overflow = "";
  thread.innerHTML = ""; picker.innerHTML = ""; ovLabels.innerHTML = "";
  setBanner(false); _gehydrateerd = false;
  pdfFrame.style.display = "none"; pdfFrame.innerHTML = ""; oerIds = [];
});

ovAsk.addEventListener("submit", (e) => {
  e.preventDefault();
  const inp = ovAsk.querySelector("input");
  const v = inp.value.trim();
  if (!v) return;
  inp.value = "";
  addVraag(thread, v);
  // Nog geen studiegids geladen (intake-vervolgbeurt): route via dezelfde modus-flow als start().
  if (oerIds.length === 0) { routeerVraag(v); }
  else { streamAntwoord(thread, v); }
});

document.querySelectorAll("form.ask[data-ask]").forEach((form) => {
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const v = form.querySelector("input").value.trim();
    if (v) start(v);
  });
});
document.querySelectorAll(".chip").forEach((c) => {
  c.addEventListener("click", () => start(c.textContent.trim()));
});

/* startpagina-cascade vullen */
const oplCascadeEl = document.getElementById("oplCascade");
if (oplCascadeEl) {
  laadOplBoom().then((boom) => bouwCascade(oplCascadeEl, boom, laadStudiegidsEnOpen));
}
