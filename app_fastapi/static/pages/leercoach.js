// Leercoach — tabs, tutor-/rollenspelchat en AI-generatie via SSE (swStream in app.js).
(function () {
  const root = document.getElementById("lc-root");
  if (!root) return;
  const student = root.dataset.student;

  const TIMEOUT_TEKST = "De AI-service reageert niet. Probeer het over een moment opnieuw.";
  const foutTekst = (err) => (err === "timeout" ? TIMEOUT_TEKST : err);

  // Minimale markdown-weergave: escapen + vet/koppen (output is pre-wrap).
  function mdLite(tekst) {
    const veilig = tekst
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return veilig
      .replace(/^#{1,4} (.*)$/gm, "<h4>$1</h4>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  }

  function toonFout(el, boodschap) {
    if (!el) return;
    el.textContent = boodschap;
    el.hidden = !boodschap;
  }

  // Stream een SSE-antwoord naar `el`; rauwe tekst tijdens het streamen,
  // mdLite-rendering zodra het klaar is.
  function streamNaar(el, foutEl, url, body, naAfloop) {
    let tekst = "";
    el.hidden = false;
    el.textContent = "…";
    toonFout(foutEl, "");
    swStream(url, Object.assign({ student }, body), {
      onChunk(chunk) {
        tekst += chunk;
        el.textContent = tekst;
      },
      onDone() {
        el.innerHTML = mdLite(tekst);
        naAfloop?.(tekst);
      },
      onError(err) {
        if (!tekst) el.hidden = true;
        toonFout(foutEl, foutTekst(err));
        naAfloop?.(tekst, err);
      },
    });
  }

  async function postJson(url, body) {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ student }, body)),
    });
    return { ok: resp.ok, data: await resp.json().catch(() => ({})) };
  }

  // ── Tabs ────────────────────────────────────────────────────────────────
  const tabs = document.querySelectorAll(".lc-tab");
  tabs.forEach((tab) =>
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.toggle("is-active", t === tab));
      document.querySelectorAll(".lc-panel").forEach((p) =>
        p.classList.toggle("is-active", p.dataset.panel === tab.dataset.tab)
      );
    })
  );

  // ── Docent: studentwissel ───────────────────────────────────────────────
  document.getElementById("lc-student-select")?.addEventListener("change", (e) => {
    location.href = "/leercoach?student=" + encodeURIComponent(e.target.value);
  });

  // ── Chat-helper (tutor + rollenspel) ────────────────────────────────────
  function chatVerstuur({ chatEl, foutEl, invoerEl, url, extra, naAfloop }) {
    const bericht = invoerEl.value.trim();
    if (!bericht) return;
    invoerEl.value = "";
    invoerEl.disabled = true;
    chatEl.appendChild(swEl("div", "sw-chat__msg sw-chat__msg--user", bericht));
    const aiEl = swEl("div", "sw-chat__msg sw-chat__msg--ai", "…");
    chatEl.appendChild(aiEl);
    aiEl.scrollIntoView({ block: "end" });
    let tekst = "";
    toonFout(foutEl, "");
    swStream(url, Object.assign({ student, bericht, vraag: bericht }, extra?.() || {}), {
      onChunk(chunk) {
        tekst += chunk;
        aiEl.textContent = tekst;
      },
      onDone() {
        aiEl.innerHTML = mdLite(tekst);
        invoerEl.disabled = false;
        invoerEl.focus();
        naAfloop?.();
      },
      onError(err) {
        if (!tekst) aiEl.remove();
        toonFout(foutEl, foutTekst(err));
        invoerEl.disabled = false;
      },
    });
  }

  // ── Tab 1: Tutor ────────────────────────────────────────────────────────
  const tutorForm = document.getElementById("lc-tutor-form");
  tutorForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    chatVerstuur({
      chatEl: document.getElementById("lc-tutor-chat"),
      foutEl: document.getElementById("lc-tutor-fout"),
      invoerEl: document.getElementById("lc-tutor-invoer"),
      url: "/leercoach/api/tutor",
      extra: () => ({ focus: document.getElementById("lc-focus").value }),
    });
  });
  document.getElementById("lc-tutor-reset")?.addEventListener("click", async () => {
    await postJson("/leercoach/api/tutor/reset", {});
    location.reload();
  });

  // ── Tab 2: Lesmateriaal ─────────────────────────────────────────────────
  document.getElementById("lc-les-btn")?.addEventListener("click", () => {
    const onderwerp = document.getElementById("lc-les-onderwerp").value.trim();
    const foutEl = document.getElementById("lc-les-fout");
    if (!onderwerp) return toonFout(foutEl, "Vul een onderwerp in.");
    streamNaar(document.getElementById("lc-les-uit"), foutEl,
      "/leercoach/api/les", { onderwerp });
  });

  // ── Tab 3: Oefentoets ───────────────────────────────────────────────────
  const toetsBtn = document.getElementById("lc-toets-btn");
  toetsBtn?.addEventListener("click", async () => {
    const onderwerp = document.getElementById("lc-toets-onderwerp").value.trim();
    const foutEl = document.getElementById("lc-toets-fout");
    if (!onderwerp) return toonFout(foutEl, "Vul een onderwerp in.");
    const spinner = document.getElementById("lc-toets-spinner");
    toonFout(foutEl, "");
    toetsBtn.disabled = true;
    spinner.hidden = false;
    const { ok, data } = await postJson("/leercoach/api/toets", { onderwerp });
    toetsBtn.disabled = false;
    spinner.hidden = true;
    if (!ok) return toonFout(foutEl, foutTekst(data.error || "Er ging iets mis."));
    document.getElementById("lc-toets-vragen").innerHTML = mdLite(data.vragen);
    document.getElementById("lc-toets-blok").hidden = false;
    const feedbackEl = document.getElementById("lc-toets-feedback");
    feedbackEl.hidden = true;
    feedbackEl.textContent = "";
    document.querySelectorAll("#lc-toets-blok select").forEach((s) => (s.value = ""));
  });

  document.getElementById("lc-controleer-btn")?.addEventListener("click", () => {
    const foutEl = document.getElementById("lc-toets-fout");
    const antwoorden = {};
    document.querySelectorAll("#lc-toets-blok select").forEach((s) => {
      if (s.value) antwoorden[s.dataset.vraag] = s.value;
    });
    if (Object.keys(antwoorden).length < 5) {
      return toonFout(foutEl, "Beantwoord eerst alle 5 vragen.");
    }
    streamNaar(document.getElementById("lc-toets-feedback"), foutEl,
      "/leercoach/api/toets/controleer",
      { antwoorden, vragen: document.getElementById("lc-toets-vragen").textContent });
  });

  // ── Tab 4: Feedback op werk ─────────────────────────────────────────────
  document.getElementById("lc-werk-bestand")?.addEventListener("change", (e) => {
    const bestand = e.target.files[0];
    if (!bestand) return;
    const lezer = new FileReader();
    lezer.onload = () => (document.getElementById("lc-werk-tekst").value = lezer.result);
    lezer.readAsText(bestand);
  });
  document.getElementById("lc-werk-btn")?.addEventListener("click", () => {
    const tekst = document.getElementById("lc-werk-tekst").value.trim();
    const foutEl = document.getElementById("lc-werk-fout");
    if (!tekst) return toonFout(foutEl, "Upload een bestand of plak je werk in het tekstvak.");
    streamNaar(document.getElementById("lc-werk-uit"), foutEl,
      "/leercoach/api/werk", { tekst });
  });

  // ── Tab 5: Rollenspel ───────────────────────────────────────────────────
  document.getElementById("lc-rp-start")?.addEventListener("click", async () => {
    const scenario = document.getElementById("lc-rp-scenario").value;
    const { ok } = await postJson("/leercoach/api/rollenspel/start", { scenario });
    if (ok) location.reload();
  });
  document.getElementById("lc-rp-reset")?.addEventListener("click", async () => {
    await postJson("/leercoach/api/rollenspel/reset", {});
    location.reload();
  });
  document.getElementById("lc-rp-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    chatVerstuur({
      chatEl: document.getElementById("lc-rp-chat"),
      foutEl: document.getElementById("lc-rp-fout"),
      invoerEl: document.getElementById("lc-rp-invoer"),
      url: "/leercoach/api/rollenspel/bericht",
      naAfloop: () => (document.getElementById("lc-rp-afronden").disabled = false),
    });
  });
  document.getElementById("lc-rp-afronden")?.addEventListener("click", () => {
    const knop = document.getElementById("lc-rp-afronden");
    const spinner = document.getElementById("lc-rp-spinner");
    knop.disabled = true;
    spinner.hidden = false;
    document.getElementById("lc-rp-feedback-blok").hidden = false;
    streamNaar(
      document.getElementById("lc-rp-feedback"),
      document.getElementById("lc-rp-fout"),
      "/leercoach/api/rollenspel/feedback", {},
      (_tekst, err) => {
        spinner.hidden = true;
        if (err) {
          knop.disabled = false;
          document.getElementById("lc-rp-feedback-blok").hidden = true;
        } else {
          document.getElementById("lc-rp-form")?.remove();
          knop.closest(".lc-toolbar")?.remove();
        }
      }
    );
  });
})();
