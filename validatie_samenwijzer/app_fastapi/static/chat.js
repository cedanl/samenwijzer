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
function renderMarkdown(md) {
  const lines = md.replace(/\r/g, "").split("\n");
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
  const d = document.createElement("div");
  d.className = "bubble-q"; d.textContent = text;
  thread.appendChild(d); _scroll(thread);
}
function _scroll(thread) {
  const sc = thread.closest("[data-scroll]") || thread.parentElement;
  if (sc) sc.scrollTop = sc.scrollHeight;
}

async function streamAntwoord(thread, vraag) {
  const node = document.createElement("div");
  node.className = "thinking"; node.textContent = "De gids zoekt het op";
  thread.appendChild(node); _scroll(thread);
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
      const parts = buf.split("\n\n"); buf = parts.pop();
      for (const p of parts) {
        const line = p.replace(/^data: /, "").trim();
        if (!line) continue;
        const ev = JSON.parse(line);
        if (ev.chunk) { acc += ev.chunk; node.innerHTML = renderMarkdown(acc); _scroll(thread); }
        else if (ev.error) {
          node.innerHTML = `<em>${ev.error === "timeout"
            ? "De AI-service reageert niet. Probeer het zo opnieuw."
            : "Er ging iets mis. Probeer het later opnieuw."}</em>`;
        }
      }
    }
    if (!acc) node.innerHTML = "<em>Geen antwoord ontvangen. Probeer het opnieuw.</em>";
  } catch (e) {
    node.className = "bubble-a";
    node.innerHTML = "<em>Verbinding verbroken. Probeer het opnieuw.</em>";
  }
}

/* Studiegids-viewer: PDF → iframe; markdown (bv. Deltion) → gerenderd. */
async function mountStudiegids(oerId, frameEl) {
  const resp = await fetch(`/api/oer/${oerId}/bestand`);
  const ct = resp.headers.get("content-type") || "";
  if (ct.includes("pdf")) {
    frameEl.innerHTML = `<iframe src="/api/oer/${oerId}/bestand" title="Studiegids"></iframe>`;
  } else {
    const tekst = await resp.text();
    frameEl.innerHTML = `<div class="wrap"><div class="studiegids-doc">${renderMarkdown(tekst)}</div></div>`;
  }
}

/* Bedraad een inline chat: een form + een thread-element, met optionele "nieuw gesprek". */
function mountInlineChat({ form, thread, resetBtn }) {
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
