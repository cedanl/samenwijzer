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
const ovPdfBtn = document.getElementById("ovPdfBtn");
const pdfFrame = document.getElementById("pdfFrame");
let oerIds = [];

let _gehydrateerd = false;
function openOverlay() {
  overlay.classList.add("open"); document.body.style.overflow = "hidden";
  if (!_gehydrateerd) { _gehydrateerd = true; rehydrateer(thread); }
}
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

async function start(vraag) {
  openOverlay();
  addVraag(thread, vraag);
  const r = await (await fetch("/api/vraag", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vraag }),
  })).json();
  if (r.modus === "kies") { renderPicker(r.opties); return; }
  if (r.modus === "chat") { oerIds = r.oer_ids || oerIds; setLabels(r.labels); setBanner(r.oer_onleesbaar); }
  await streamAntwoord(thread, vraag);
}

function renderPicker(opties) {
  picker.innerHTML = `
    <div class="picker">
      <h3>Welke studiegids is van jou?</h3>
      <div class="hint">Kies er één — of meerdere om te vergelijken (max 3).</div>
      <div class="opts">${opties.map((o) =>
        `<label><input type="checkbox" value="${o.id}"> <span>${esc(o.label)}</span></label>`).join("")}</div>
      <button class="iconbtn" id="pickConfirm" disabled>Bevestig keuze</button>
    </div>`;
  const boxes = () => Array.from(picker.querySelectorAll("input[type=checkbox]"));
  const confirm = picker.querySelector("#pickConfirm");
  picker.addEventListener("change", () => {
    const checked = boxes().filter((b) => b.checked);
    if (checked.length > 3) checked[checked.length - 1].checked = false;
    confirm.disabled = boxes().filter((b) => b.checked).length === 0;
  });
  confirm.addEventListener("click", async () => {
    const ids = boxes().filter((b) => b.checked).map((b) => Number(b.value));
    confirm.disabled = true;
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
  streamAntwoord(thread, v);
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
