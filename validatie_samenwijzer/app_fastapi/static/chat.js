"use strict";
/* Gedeelde chat-engine: ESCAPENDE markdown-renderer + SSE-streaming + studiegids-viewer.
   Gebruikt door de publieke overlay (app.js) én de ingelogde pagina's. Eén plek voor de
   security-gevoelige rendering. */

function esc(s) {
  // Escape óók quotes: inline() plaatst ge-escapte tekst in attribuut-context (img alt),
  // dus een " of ' mag niet uit het attribuut breken.
  return s
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function inline(s) {
  s = esc(s);
  s = s.replace(/!\[([^\]]*)\]\((https?:\/\/[^)\s"'<>]+)\)/g,
    (_m, a, u) => `<img src="${u}" alt="${a}" loading="lazy">`);
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s"'<>]+)\)/g,
    (_m, t, u) => `<a href="${u}" target="_blank" rel="noopener noreferrer">${t}</a>`);
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  return s;
}
/* Het model begint de waarschuwings-blockquote soms middenin een regel
   ("...ik zoek dit op voor je...> \u26a0\ufe0f Let op:"). Zonder eigen regel rendert die als
   platte tekst. Alleen deze vorm normaliseren \u2014 een kale "> " kan ook gewoon
   een groter-dan-teken in de lopende tekst zijn. */
function normaliseerBlockquotes(md) {
  return md.replace(/([^\n])(> \u26a0)/g, "$1\n\n$2");
}
function renderMarkdown(md) {
  // Vangnet: de bronnenmarker hoort server-side gestript te zijn; nooit tonen als hij toch doorkomt.
  const lines = normaliseerBlockquotes(md).replace(/\r/g, "").split("\n")
    .filter((l) => !l.trimStart().startsWith("<!-- bronnen:"));
  let html = "", i = 0;
  const para = [];
  const flush = () => { if (para.length) { html += `<p>${inline(para.join(" "))}</p>`; para.length = 0; } };
  while (i < lines.length) {
    const line = lines[i];
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?[-:\s|]+\|?\s*$/.test(lines[i + 1])) {
      flush();
      const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const head = cells(line); i += 2; let rows = "";
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
        rows += "<tr>" + cells(lines[i]).map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>"; i++;
      }
      html += `<table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table>`;
      continue;
    }
    if (/^\s*([-*_])\1{2,}\s*$/.test(line)) { flush(); html += "<hr>"; i++; continue; }
    let m;
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { flush(); html += `<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`; i++; continue; }
    if (/^\s*>\s?/.test(line)) {
      flush(); const q = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) { q.push(lines[i].replace(/^\s*>\s?/, "")); i++; }
      html += `<blockquote>${inline(q.join(" "))}</blockquote>`; continue;
    }
    if (/^\s*[-*+]\s+/.test(line)) {
      flush(); let items = "";
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) { items += `<li>${inline(lines[i].replace(/^\s*[-*+]\s+/, ""))}</li>`; i++; }
      html += `<ul>${items}</ul>`; continue;
    }
    if (/^\s*\d+\.\s+/.test(line)) {
      flush(); let items = "";
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) { items += `<li>${inline(lines[i].replace(/^\s*\d+\.\s+/, ""))}</li>`; i++; }
      html += `<ol>${items}</ol>`; continue;
    }
    if (line.trim() === "") { flush(); i++; continue; }
    para.push(line.trim()); i++;
  }
  flush();
  return html;
}

function addVraag(thread, text) {
  _verwijderVervolgvragen(thread);
  const d = document.createElement("div");
  d.className = "bubble-q"; d.textContent = text;
  thread.appendChild(d); _scroll(thread);
}
function _verwijderVervolgvragen(thread) {
  thread.querySelectorAll(".vervolg").forEach((el) => el.remove());
}
function _scroll(thread) {
  const sc = thread.closest("[data-scroll]") || thread.parentElement;
  if (sc) sc.scrollTop = sc.scrollHeight;
}
function addAntwoord(thread, md) {
  const d = document.createElement("div");
  d.className = "bubble-a"; d.innerHTML = renderMarkdown(md);
  thread.appendChild(d); _scroll(thread);
}
const FOUT_TEKSTEN = {
  timeout: "De AI-service reageert niet. Probeer het zo opnieuw.",
  auth: "De AI-service weigert de toegang: de API-sleutel van deze omgeving is ongeldig. Meld dit bij de beheerder.",
};
function foutTekst(code) {
  return FOUT_TEKSTEN[code] || "Er ging iets mis. Probeer het later opnieuw.";
}

const STATUS_TEKSTEN = {
  lezen: "Studiegids en officiële documenten lezen…",
  intake: "Opleiding zoeken…",
  web: "Niet in de documenten gevonden — website van de school raadplegen…",
  schooldoc: "Niet in de studiegids — officieel schooldocument van de school gebruikt",
  webinfo: "Niet in de documenten — informatie van de schoolwebsite gebruikt",
};
const BRON_TYPE_LABELS = {
  studiegids: "Studiegids",
  kwalificatiedossier: "Kwalificatiedossier",
  schooldocument: "Schooldocument",
  skills: "Skills",
  website: "Website",
};

function maakStatusRegel() {
  const el = document.createElement("div");
  el.className = "status-regel";
  const tekst = document.createElement("span");
  tekst.className = "status-tekst"; tekst.textContent = "Even geduld";
  el.appendChild(tekst);
  for (let i = 0; i < 3; i++) {
    const punt = document.createElement("span");
    punt.className = "wacht-punt";
    el.appendChild(punt);
  }
  return el;
}
function zetStatus(el, code) {
  const tekst = STATUS_TEKSTEN[code];
  if (!tekst) return;
  const t = el.querySelector(".status-tekst");
  if (t) t.textContent = tekst;
}

/* Bronnenrij onder een antwoord. Titel/url komen uit modeloutput: alleen via
   textContent/createElement, en een link alleen bij een http(s)-url. */
function addBronnen(thread, bronnen) {
  if (!Array.isArray(bronnen) || !bronnen.length) return;
  const chips = [];
  for (const b of bronnen) {
    if (!b || !Object.prototype.hasOwnProperty.call(BRON_TYPE_LABELS, b.type)) continue;
    const link = b.type === "website" && typeof b.url === "string" && /^https?:\/\//.test(b.url);
    const chip = document.createElement(link ? "a" : "span");
    chip.className = "bron-chip";
    if (link) {
      chip.href = b.url; chip.target = "_blank"; chip.rel = "noopener noreferrer";
    }
    const type = document.createElement("span");
    type.className = "bron-type"; type.textContent = BRON_TYPE_LABELS[b.type];
    chip.appendChild(type);
    chip.appendChild(document.createTextNode(" · " + String(b.titel ?? "")));
    chips.push(chip);
  }
  if (!chips.length) return;
  const wrap = document.createElement("div");
  wrap.className = "bronnen";
  const label = document.createElement("span");
  label.className = "bronnen-label"; label.textContent = "Bronnen";
  wrap.appendChild(label);
  chips.forEach((c) => wrap.appendChild(c));
  thread.appendChild(wrap); _scroll(thread);
}

async function rehydrateer(thread) {
  const r = await (await fetch("/api/geschiedenis")).json();
  for (const b of r.beurten || []) {
    if (b.role === "user") addVraag(thread, b.content);
    else { addAntwoord(thread, b.content); addBronnen(thread, b.bronnen || []); }
  }
}

async function streamAntwoord(thread, vraag) {
  const status = maakStatusRegel();
  thread.appendChild(status);
  const node = document.createElement("div");
  node.className = "bubble-a"; node.setAttribute("aria-busy", "true");
  thread.appendChild(node); _scroll(thread);
  let acc = "";
  let fout = false;
  let bronnen = [];
  try {
    const resp = await fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vraag }),
    });
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n\n"); buf = parts.pop();
      for (const p of parts) {
        const line = p.replace(/^data: /, "").trim();
        if (!line) continue;
        const ev = JSON.parse(line);
        if (ev.status) zetStatus(status, ev.status);
        else if (ev.chunk) { acc += ev.chunk; node.removeAttribute("aria-busy"); node.innerHTML = renderMarkdown(acc); _scroll(thread); }
        else if (ev.bronnen) bronnen = ev.bronnen;
        else if (ev.error) {
          fout = true;
          node.removeAttribute("aria-busy");
          node.innerHTML = `<em>${foutTekst(ev.error)}</em>`;
        }
      }
    }
    status.remove();
    node.removeAttribute("aria-busy");
    if (!acc) node.innerHTML = "<em>Geen antwoord ontvangen. Probeer het opnieuw.</em>";
    else if (!fout) { addBronnen(thread, bronnen); await toonVervolgvragen(thread); }
  } catch (e) {
    status.remove();
    node.removeAttribute("aria-busy");
    node.innerHTML = "<em>Verbinding verbroken. Probeer het opnieuw.</em>";
  }
}

/* Vervolgvragen: 2-4 klikbare chips onder het laatste antwoord, opgehaald na een
   succesvolle stream. Skeleton-pills tijdens het laden; lege lijst/fout → niets tonen. */
async function toonVervolgvragen(thread) {
  const bubbels = thread.querySelectorAll(".bubble-a");
  const laatste = bubbels[bubbels.length - 1];
  if (!laatste) return;

  const wrap = document.createElement("div");
  wrap.className = "vervolg";
  const label = document.createElement("div");
  label.className = "vervolg-label"; label.textContent = "Verder vragen";
  const lijst = document.createElement("div");
  lijst.className = "vervolg-lijst";
  for (let i = 0; i < 3; i++) {
    const sk = document.createElement("span");
    sk.className = "vervolg-skelet";
    lijst.appendChild(sk);
  }
  wrap.appendChild(label); wrap.appendChild(lijst);
  laatste.insertAdjacentElement("afterend", wrap);
  _scroll(thread);

  let vragen = [];
  try {
    const resp = await fetch("/api/vervolgvragen", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    if (resp.ok) {
      const data = await resp.json();
      if (Array.isArray(data.vragen)) vragen = data.vragen;
    }
  } catch (e) {
    vragen = [];
  }

  if (!wrap.isConnected) return; // ondertussen weggehaald (nieuwe vraag gesteld)
  if (!vragen.length) { wrap.remove(); return; }

  lijst.innerHTML = "";
  vragen.forEach((vraagTekst, idx) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "vervolg-chip";
    btn.style.setProperty("--vi", idx);
    btn.textContent = vraagTekst; // NOOIT innerHTML: modelgegenereerde tekst
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      lijst.querySelectorAll(".vervolg-chip").forEach((c) => { c.disabled = true; });
      addVraag(thread, vraagTekst); // verwijdert zelf ook alle .vervolg-blokken
      streamAntwoord(thread, vraagTekst);
    });
    lijst.appendChild(btn);
  });
  _scroll(thread);
}

/* Studiegids-viewer: PDF → PDF.js-canvas (mobiel-proof) met download/open-fallback;
   markdown (bv. Deltion) → gerenderd. PDF.js lazy via CDN (geen build-stap). */
const _PDFJS_VERSIE = "4.7.76";
const _PDFJS_CDN = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${_PDFJS_VERSIE}/pdf.min.mjs`;
const _PDFJS_WORKER = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${_PDFJS_VERSIE}/pdf.worker.min.mjs`;

function _pdfActies(oerId) {
  const url = `/api/oer/${oerId}/bestand`;
  return `<div class="pdf-acties">`
    + `<a class="linkbtn" href="${url}?download=1" download>⬇️ Download</a>`
    + `<a class="linkbtn" href="${url}" target="_blank" rel="noopener">↗ Open in nieuw tabblad</a>`
    + `</div>`;
}

async function mountStudiegids(oerId, frameEl) {
  let resp;
  try {
    resp = await fetch(`/api/oer/${oerId}/bestand`);
  } catch (e) {
    resp = null;
  }
  if (!resp || !resp.ok) {
    frameEl.innerHTML = `<div class="wrap"><p class="studiegids-fout">Studiegids kon niet geladen worden.</p></div>`;
    return;
  }
  const ct = resp.headers.get("content-type") || "";
  if (!ct.includes("pdf")) {
    const tekst = await resp.text();
    frameEl.innerHTML = `<div class="wrap"><div class="studiegids-doc">${renderMarkdown(tekst)}</div></div>`;
    return;
  }
  // PDF: knoppen eerst (altijd zichtbare fallback), dan de canvas-render.
  frameEl.innerHTML = _pdfActies(oerId);
  try {
    const data = await resp.arrayBuffer();
    const pdfjs = await import(_PDFJS_CDN);
    pdfjs.GlobalWorkerOptions.workerSrc = _PDFJS_WORKER;
    const pdf = await pdfjs.getDocument({ data }).promise;
    const dpr = window.devicePixelRatio || 1;
    for (let n = 1; n <= pdf.numPages; n++) {
      const page = await pdf.getPage(n);
      const vp = page.getViewport({ scale: 1.4 * dpr });
      const canvas = document.createElement("canvas");
      canvas.width = vp.width; canvas.height = vp.height;
      frameEl.appendChild(canvas);
      await page.render({ canvasContext: canvas.getContext("2d"), viewport: vp }).promise;
    }
  } catch (e) {
    // PDF.js faalde (CDN-uitval/render-fout) → de download/open-knoppen blijven staan.
  }
}

/* Bedraad een inline chat: een form + een thread-element, met optionele "nieuw gesprek". */
function mountInlineChat({ form, thread, resetBtn }) {
  rehydrateer(thread);  // herstel de zichtbare gespreksgeschiedenis bij page-load
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const inp = form.querySelector("input, textarea");
    const v = inp.value.trim();
    if (!v) return;
    inp.value = "";
    addVraag(thread, v);
    streamAntwoord(thread, v);
  });
  if (resetBtn) {
    resetBtn.addEventListener("click", async () => {
      await fetch("/api/reset", { method: "POST" });
      thread.innerHTML = "";
    });
  }
}
