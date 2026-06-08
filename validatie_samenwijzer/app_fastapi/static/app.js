"use strict";

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

/* ── kleine, ESCAPENDE markdown-renderer (geen externe lib → geen XSS/CDN-risico) ──
   Dekt wat OER-antwoorden gebruiken: koppen, **vet**, *cursief*, lijsten,
   > blockquote (citaat), | tabellen |, [tekst](url), alinea's. Alle tekst wordt
   eerst ge-escaped; opmaak wordt daarna als veilige tags toegevoegd. */
function esc(s) {
  // Escape óók quotes: inline() plaatst ge-escapte tekst in attribuut-context
  // (img alt), dus een " of ' moet niet uit het attribuut kunnen breken.
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function inline(s) {
  s = esc(s);
  // Afbeeldingen ![alt](url) vóór links; URL-klasse sluit quotes/<>/spaties uit.
  s = s.replace(/!\[([^\]]*)\]\((https?:\/\/[^)\s"'<>]+)\)/g,
    (_m, a, u) => `<img src="${u}" alt="${a}" loading="lazy">`);
  // URL-tekenklasse sluit quotes/<>/spaties uit → geen attribuut-breakout in href.
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s"'<>]+)\)/g,
    (_m, t, u) => `<a href="${u}" target="_blank" rel="noopener noreferrer">${t}</a>`);
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  return s;
}
function renderMarkdown(md) {
  const lines = md.replace(/\r/g, "").split("\n");
  let html = "", i = 0;
  const flushParaBuf = (buf) => { if (buf.length) { html += `<p>${inline(buf.join(" "))}</p>`; buf.length = 0; } };
  const para = [];
  while (i < lines.length) {
    const line = lines[i];
    // tabel (pipe-rijen, met scheidingsregel)
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?[-:\s|]+\|?\s*$/.test(lines[i + 1])) {
      flushParaBuf(para);
      const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const head = cells(line);
      i += 2;
      let rows = "";
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
        rows += "<tr>" + cells(lines[i]).map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>";
        i++;
      }
      html += `<table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table>`;
      continue;
    }
    let m;
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { flushParaBuf(para); html += `<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`; i++; continue; }
    if (/^\s*>\s?/.test(line)) {
      flushParaBuf(para);
      const q = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) { q.push(lines[i].replace(/^\s*>\s?/, "")); i++; }
      html += `<blockquote>${inline(q.join(" "))}</blockquote>`;
      continue;
    }
    if (/^\s*[-*+]\s+/.test(line)) {
      flushParaBuf(para);
      let items = "";
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) { items += `<li>${inline(lines[i].replace(/^\s*[-*+]\s+/, ""))}</li>`; i++; }
      html += `<ul>${items}</ul>`;
      continue;
    }
    if (/^\s*\d+\.\s+/.test(line)) {
      flushParaBuf(para);
      let items = "";
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) { items += `<li>${inline(lines[i].replace(/^\s*\d+\.\s+/, ""))}</li>`; i++; }
      html += `<ol>${items}</ol>`;
      continue;
    }
    if (line.trim() === "") { flushParaBuf(para); i++; continue; }
    para.push(line.trim());
    i++;
  }
  flushParaBuf(para);
  return html;
}

/* ── chat-overlay-state ───────────────────────────────────────────────────── */
const overlay = document.getElementById("overlay");
const thread = document.getElementById("thread");
const picker = document.getElementById("picker");
const ovLabels = document.getElementById("ovLabels");
const ovAsk = document.getElementById("ovAsk");
const ovReset = document.getElementById("ovReset");
const ovPdfBtn = document.getElementById("ovPdfBtn");
const pdfFrame = document.getElementById("pdfFrame");
let oerIds = [];

function openOverlay() { overlay.classList.add("open"); document.body.style.overflow = "hidden"; }
function addQ(text) { const d = document.createElement("div"); d.className = "bubble-q"; d.textContent = text; thread.appendChild(d); scrollDown(); }
function addThinking() { const d = document.createElement("div"); d.className = "thinking"; d.textContent = "De gids zoekt het op"; thread.appendChild(d); scrollDown(); return d; }
function scrollDown() { const b = overlay.querySelector(".ov-body"); b.scrollTop = b.scrollHeight; }
function setLabels(labels) {
  ovLabels.innerHTML = (labels || []).map((l) => `<span class="ov-label">${esc(l)}</span>`).join("");
  ovPdfBtn.style.display = oerIds.length ? "" : "none";
}

async function streamAntwoord(vraag) {
  const node = addThinking();
  let acc = "";
  try {
    const resp = await fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vraag }),
    });
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    node.className = "bubble-a";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop();
      for (const p of parts) {
        const line = p.replace(/^data: /, "").trim();
        if (!line) continue;
        const ev = JSON.parse(line);
        if (ev.chunk) { acc += ev.chunk; node.innerHTML = renderMarkdown(acc); scrollDown(); }
        else if (ev.error) { node.innerHTML = `<em>${ev.error === "timeout" ? "De AI-service reageert niet. Probeer het zo opnieuw." : "Er ging iets mis. Probeer het later opnieuw."}</em>`; }
      }
    }
  } catch (e) {
    node.className = "bubble-a";
    node.innerHTML = "<em>Verbinding verbroken. Probeer het opnieuw.</em>";
  }
}

async function start(vraag) {
  openOverlay();
  addQ(vraag);
  const r = await (await fetch("/api/vraag", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vraag }),
  })).json();

  if (r.modus === "kies") { renderPicker(r.opties); return; }
  if (r.modus === "chat") { oerIds = r.oer_ids || oerIds; setLabels(r.labels); }
  // chat én intake: stream het antwoord op de gestelde vraag
  await streamAntwoord(vraag);
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
    if (checked.length > 3) { checked[checked.length - 1].checked = false; }
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
    picker.innerHTML = "";
    if (r.wachtende_vraag) await streamAntwoord(r.wachtende_vraag);
  });
}

/* Studiegids-viewer: PDF → iframe; markdown (bv. Deltion) → gerenderd, niet ruw. */
async function toonStudiegids(oerId) {
  const resp = await fetch(`/api/oer/${oerId}/bestand`);
  const ct = resp.headers.get("content-type") || "";
  if (ct.includes("pdf")) {
    pdfFrame.innerHTML = `<iframe src="/api/oer/${oerId}/bestand" title="Studiegids"></iframe>`;
  } else {
    const tekst = await resp.text();
    pdfFrame.innerHTML = `<div class="wrap"><div class="studiegids-doc">${renderMarkdown(tekst)}</div></div>`;
  }
  pdfFrame.style.display = "block";
}
ovPdfBtn.addEventListener("click", () => {
  if (!oerIds.length) return;
  if (pdfFrame.style.display === "block") { pdfFrame.style.display = "none"; pdfFrame.innerHTML = ""; }
  else { toonStudiegids(oerIds[0]); }
});

ovReset.addEventListener("click", async () => {
  await fetch("/api/reset", { method: "POST" });
  overlay.classList.remove("open"); document.body.style.overflow = "";
  thread.innerHTML = ""; picker.innerHTML = ""; ovLabels.innerHTML = "";
  pdfFrame.style.display = "none"; pdfFrame.innerHTML = ""; oerIds = [];
});

ovAsk.addEventListener("submit", (e) => {
  e.preventDefault();
  const inp = ovAsk.querySelector("input");
  const v = inp.value.trim();
  if (!v) return;
  inp.value = "";
  addQ(v);
  streamAntwoord(v);
});

/* landing ask-boxes (hero + closing) + chips */
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
