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
let kiezer = null;   // startpagina-kiezer (zie onderaan), zodat "Nieuw gesprek" hem kan terugzetten
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
const KZ_STAPPEN = ["Instelling", "Opleiding", "Leerweg", "Cohort"];

/* De boom van /api/opleidingen loopt instelling → leerweg → opleiding → cohort; de kiezer vraagt
   instelling → opleiding → leerweg → cohort. Per gekozen school wordt hij hier opnieuw gegroepeerd. */
function _opleidingenVan(inst) {
  const perNaam = new Map();
  inst.leerwegen.forEach((lw) => lw.opleidingen.forEach((o) => {
    if (!perNaam.has(o.naam)) perNaam.set(o.naam, {});
    perNaam.get(o.naam)[lw.leerweg] = o.cohorten;
  }));
  return [...perNaam.entries()]
    .sort((x, y) => x[0].localeCompare(y[0], "nl", { sensitivity: "base" }))
    .map(([naam, leerwegen]) => ({ naam, leerwegen }));
}
const _lwVolgorde = (lw) => (lw === "BOL" ? 0 : lw === "BBL" ? 1 : 2);

/* Vier keuzekaarten (instelling → opleiding → leerweg → cohort) + lijstje gekozen studiegidsen.
   Je kunt meerdere studiegidsen naast elkaar zetten (tot MAX_GIDSEN OER's, de grens die /api/kies
   hanteert). opts.onChange({ ids, aantal, stappen, klaar }) meldt elke wijziging; opts.knop is het
   label van de openknop (weggelaten = geen knop, de aanroeper opent zelf, bv. via het vraagveld). */
function bouwCascade(container, boom, onKies, opts = {}) {
  const { onChange = null, knop = null } = opts;
  const leeg = () => ({ inst: null, opl: null, lw: null, coh: null, auto: {} });
  let s = leeg(), open = null, zoek = "";
  let gekozen = [];

  const opls = () => (s.inst ? _opleidingenVan(s.inst) : []);
  const lwOpties = () => (s.opl ? Object.keys(s.opl.leerwegen).sort((x, y) => _lwVolgorde(x) - _lwVolgorde(y)) : []);
  const cohOpties = () => (s.opl && s.lw ? s.opl.leerwegen[s.lw] : []);
  const autoCoh = () => {
    if (s.lw && cohOpties().length === 1) { s.coh = cohOpties()[0]; s.auto.coh = true; }
  };
  const aantalStappen = () => [s.inst, s.opl, s.lw, s.coh].filter((v) => v !== null).length;
  const huidige = () => (aantalStappen() < 4 ? null : {
    label: `${s.inst.instelling} · ${s.opl.naam} · ${s.lw} ${s.coh.cohort}`, ids: s.coh.oer_ids,
  });
  const gekozenIds = () => gekozen.reduce((acc, g) => acc.concat(g.ids), []);

  const kiesInst = (i) => { s = leeg(); s.inst = boom[i]; };
  const kiesOpl = (i) => {
    Object.assign(s, { opl: opls()[i], lw: null, coh: null, auto: {} });
    const l = lwOpties();
    if (l.length === 1) { s.lw = l[0]; s.auto.lw = true; autoCoh(); }
  };
  const kiesLw = (lw) => { s.lw = lw; s.coh = null; delete s.auto.coh; autoCoh(); };

  const veld = (i, inhoud) => {
    const waarden = [s.inst, s.opl, s.lw, s.coh];
    const klaar = waarden[i] !== null, nu = aantalStappen() === i;
    return `<div class="kz-veld${klaar ? " klaar" : ""}${nu ? " nu" : ""}${!klaar && !nu ? " uit" : ""}" data-v="${i}">
      <div class="kz-lab mono"><span class="kz-num">${klaar ? "✓" : i + 1}</span>${KZ_STAPPEN[i]}</div>${inhoud}</div>`;
  };
  const selKnop = (i, tekst, placeholder, aan) =>
    `<button type="button" class="kz-sel${tekst === null ? " leeg" : ""}" data-open="${i}" ${aan ? "" : "disabled"}
      aria-haspopup="listbox" aria-expanded="${open === i}"><span>${esc(tekst === null ? placeholder : tekst)}</span><span aria-hidden="true">▾</span></button>`;
  const autoNoot = (k) => (s.auto[k] ? `<div class="kz-auto">✓ automatisch gekozen</div>` : "");

  const tekenMenu = () => {
    const host = container.querySelector(`.kz-veld[data-v="${open}"]`);
    if (!host) return;
    const lijst = open === 0
      ? boom.map((b, i) => ({ i, t: b.instelling, x: "" }))
      : opls().map((o, i) => ({ i, t: o.naam, x: Object.keys(o.leerwegen).sort((p, q) => _lwVolgorde(p) - _lwVolgorde(q)).join(" · ") }));
    const items = (q) => lijst.filter((r) => r.t.toLowerCase().includes(q.toLowerCase()))
      .map((r) => `<li><button type="button" data-pick="${r.i}">${esc(r.t)}<small>${esc(r.x)}</small></button></li>`).join("")
      || `<li class="kz-niets">Niets gevonden</li>`;
    host.insertAdjacentHTML("beforeend", `<div class="kz-menu" role="listbox">
      <input type="text" placeholder="Zoeken…" value="${esc(zoek)}" aria-label="Zoeken"><ul>${items(zoek)}</ul></div>`);
    const inp = host.querySelector(".kz-menu input");
    inp.focus(); inp.setSelectionRange(zoek.length, zoek.length);
    inp.addEventListener("input", () => { zoek = inp.value; host.querySelector(".kz-menu ul").innerHTML = items(zoek); });
  };

  const teken = () => {
    const n = aantalStappen(), h = huidige();
    const ruimte = MAX_GIDSEN - gekozenIds().length;
    const kanErbij = !!h && h.ids.length <= ruimte && gekozenIds().length + h.ids.length < MAX_GIDSEN;
    const alleIds = gekozenIds().concat(h ? h.ids : []).slice(0, MAX_GIDSEN);
    const aantal = gekozen.length + (h ? 1 : 0);
    const lws = lwOpties();
    container.innerHTML = `
      <div class="kz-prog" aria-hidden="true">${[0, 1, 2, 3].map((i) => `<i${i < n ? ' class="on"' : ""}></i>`).join("")}</div>
      <div class="kz-velden">
        ${veld(0, selKnop(0, s.inst && s.inst.instelling, "Kies je school", true))}
        ${veld(1, selKnop(1, s.opl && s.opl.naam, "Kies je opleiding", !!s.inst))}
        ${veld(2, `<div class="kz-seg" role="group" aria-label="Leerweg">${(lws.length ? lws : ["BOL", "BBL"]).map((l) =>
          `<button type="button" data-lw="${esc(l)}" aria-pressed="${s.lw === l}" ${lws.length ? "" : "disabled"}>${esc(l)}<small>${l === "BOL" ? "op school" : l === "BBL" ? "werkend" : ""}</small></button>`).join("")}</div>${autoNoot("lw")}`)}
        ${veld(3, s.lw
          ? `<div class="kz-coh" role="group" aria-label="Cohort">${cohOpties().map((c, i) =>
              `<button type="button" data-coh="${i}" aria-pressed="${s.coh === c}">${esc(c.cohort)}</button>`).join("")}</div>${autoNoot("coh")}`
          : `<div class="kz-hint">Kies eerst een leerweg</div>`)}
      </div>
      <div class="kz-samen">
        ${gekozen.map((g, i) => `<span class="kz-chip">${esc(g.label)}<button type="button" data-x="${i}" aria-label="Verwijder ${esc(g.label)}">×</button></span>`).join("")}
        ${h ? `<span class="kz-chip nieuw">${esc(h.label)}</span>` : ""}
        ${kanErbij ? `<button type="button" class="kz-erbij">+ vergelijk met een andere</button>` : ""}
        ${h && !kanErbij && gekozenIds().length + h.ids.length >= MAX_GIDSEN ? `<span class="kz-hint">Maximaal ${MAX_GIDSEN} studiegidsen tegelijk</span>` : ""}
      </div>
      ${knop ? `<button type="button" class="iconbtn kz-open" ${aantal ? "" : "disabled"}>${aantal > 1 ? `Vergelijk ${aantal} studiegidsen →` : esc(knop)}</button>` : ""}`;
    if (open !== null) tekenMenu();
    if (onChange) onChange({ ids: alleIds, aantal, stappen: n, klaar: aantal > 0 });
  };
  const sluit = () => { open = null; zoek = ""; };

  container.addEventListener("click", (e) => {
    const t = e.target;
    if (open !== null && !t.closest(".kz-menu") && !t.closest("[data-open]")) { sluit(); teken(); }
    const pick = t.closest("[data-pick]"), o = t.closest("[data-open]"), lw = t.closest("[data-lw]"), coh = t.closest("[data-coh]");
    if (pick) {
      if (open === 0) { kiesInst(Number(pick.dataset.pick)); open = 1; } else { kiesOpl(Number(pick.dataset.pick)); open = null; }
      zoek = ""; teken(); return;
    }
    if (o && !o.disabled) { const i = Number(o.dataset.open); open = open === i ? null : i; zoek = ""; teken(); return; }
    if (lw && !lw.disabled) { kiesLw(lw.dataset.lw); teken(); return; }
    if (coh) { s.coh = cohOpties()[Number(coh.dataset.coh)]; delete s.auto.coh; teken(); return; }
    const x = t.dataset && t.dataset.x;
    if (x !== undefined && x !== "") { gekozen.splice(Number(x), 1); teken(); return; }
    if (t.closest(".kz-erbij")) { const h = huidige(); if (h) { gekozen.push(h); s = leeg(); teken(); } return; }
    if (t.closest(".kz-open") && onKies) {
      const h = huidige();
      const ids = gekozenIds().concat(h ? h.ids : []).slice(0, MAX_GIDSEN);
      if (ids.length) onKies(ids);
    }
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && open !== null) { sluit(); teken(); } });

  teken();
  return { reset() { s = leeg(); gekozen = []; sluit(); teken(); } };
}

/* Laadt de gekozen studiegids in de sessie en opent de chat (gedeeld door beide paden);
   met `vraag` wordt die meteen gesteld. */
async function laadStudiegidsEnOpen(ids, vraag = null) {
  openOverlay();
  if (!_gehydrateerd) { _gehydrateerd = true; await rehydrateer(thread); }
  const r = await (await fetch("/api/kies", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ oer_ids: ids }),
  })).json();
  oerIds = r.oer_ids || ids;
  setLabels(r.labels);
  setBanner(r.oer_onleesbaar, r.melding);
  if (vraag) { addVraag(thread, vraag); await streamAntwoord(thread, vraag); }
  else if (r.wachtende_vraag) { await streamAntwoord(thread, r.wachtende_vraag); }
  else { ovAsk.querySelector("input").focus(); }
}

let _gehydrateerd = false;
function openOverlay() { overlay.classList.add("open"); document.body.style.overflow = "hidden"; }
function setLabels(labels) {
  ovLabels.innerHTML = (labels || []).map((l) => `<span class="ov-label">${esc(l)}</span>`).join("");
  ovPdfBtn.style.display = oerIds.length ? "" : "none";
}
function setBanner(onleesbaar, melding = "") {
  const b = document.getElementById("ovBanner");
  if (!b) return;
  const tekst = [
    onleesbaar ? "De OER van deze opleiding is niet machine-leesbaar; antwoorden komen uit het landelijke kwalificatiedossier en de instellingsregelingen." : "",
    melding || "",
  ].filter(Boolean).join(" ");
  b.hidden = !tekst;
  b.textContent = tekst;
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
  if (r.modus === "chat") { oerIds = r.oer_ids || oerIds; setLabels(r.labels); setBanner(r.oer_onleesbaar, r.melding); }
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
    setBanner(r.oer_onleesbaar, r.melding);
    picker.innerHTML = "";
    if (r.wachtende_vraag) await streamAntwoord(thread, r.wachtende_vraag);
  }, { knop: "Open mijn studiegids →" });
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
  if (kiezer) kiezer.reset();
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

/* startpagina: kiezer + vraagveld dat pas opengaat als er een studiegids gekozen is */
const oplCascadeEl = document.getElementById("oplCascade");
const vraagveld = document.getElementById("vraagveld");
if (oplCascadeEl && vraagveld) {
  const vraagForm = document.getElementById("vraagForm");
  const vraagInput = vraagForm.querySelector("input");
  const vraagKnop = vraagForm.querySelector("button");
  const vraagChips = vraagveld.querySelectorAll(".chip");
  let gekozenIds = [];

  const werkVraagveldBij = ({ ids, aantal, stappen, klaar }) => {
    gekozenIds = ids;
    const rest = 4 - stappen;
    vraagveld.classList.toggle("locked", !klaar);
    vraagveld.classList.toggle("open", klaar);
    document.getElementById("vraagStatus").textContent = klaar
      ? (aantal > 1 ? `✓ aan ${aantal} studiegidsen` : "✓ klaar om te vragen")
      : `🔒 kies eerst je opleiding · nog ${rest} stap${rest === 1 ? "" : "pen"}`;
    vraagInput.disabled = vraagKnop.disabled = !klaar;
    vraagChips.forEach((c) => { c.disabled = !klaar; });
    vraagInput.placeholder = klaar ? "Stel je vraag over je opleiding…" : "Beschikbaar zodra je opleiding gekozen is";
  };
  werkVraagveldBij({ ids: [], aantal: 0, stappen: 0, klaar: false });

  const stelVraag = (v) => { if (v && gekozenIds.length) laadStudiegidsEnOpen(gekozenIds, v); };
  vraagForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const v = vraagInput.value.trim();
    if (v) { vraagInput.value = ""; stelVraag(v); }
  });
  vraagChips.forEach((c) => c.addEventListener("click", () => stelVraag(c.textContent.trim())));

  laadOplBoom().then((boom) => { kiezer = bouwCascade(oplCascadeEl, boom, null, { onChange: werkVraagveldBij }); });
}
