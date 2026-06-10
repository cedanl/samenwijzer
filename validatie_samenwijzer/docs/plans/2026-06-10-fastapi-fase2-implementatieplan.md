# FastAPI-migratie Fase 2 — Implementatieplan (opgeknipt in deelplannen)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. Inline uitvoeren (implementer-subagents zijn gesandboxed zonder Bash).

**Goal:** Feature- en kwaliteits-pariteit van de FastAPI-frontend met de Streamlit-app, opgesplitst in drie onafhankelijke deel-PR's.

**Architecture:** UI-schil-only wijzigingen op `app_fastapi/`; de Python-kern (`chat.py` etc.) blijft ongewijzigd. Elke deel-PR levert werkende, testbare software en kan los gemerged worden.

**Tech Stack:** FastAPI, Jinja2, vanilla JS (`static/chat.js`, `static/app.js`), SQLite, pytest + `fastapi.testclient`. Commando's vanuit `validatie_samenwijzer/`.

**Spec:** `docs/plans/2026-06-10-fastapi-migratie-en-streamlit-retire.md` · **Audit:** sessielog 2026-06-10.

---

## De drie deelplannen

| Deel | Scope | Onafhankelijk? |
|---|---|---|
| **2a — chat-UX-pariteit** | KD-fallback (gate + banner), chat-historie-rehydratie, `LAGE_RELEVANTIE`-melding, `--marker-was` CSS-var | Ja — raakt `context.py`, `sessie.py`, chat-routes, templates, `chat.js` |
| **2b — PDF mobiel-proof** | PDF.js-viewer (st.pdf-equivalent) + download-/open-knop + foutafhandeling in `mountStudiegids` + `?download=1` backend | Ja — raakt PDF-viewer-pad (`chat.js`, `main.py` bestand-route, templates, `app.css`) |
| **2c — beheer + styling-pariteit** | beheer-pagina porten (routes + template + SSE subprocess-streaming achter `BEHEER_ENABLED`) + mentor-nav-link + groen-tint | Ja — nieuwe route/template + `base.html`/`app.css` |

**Volgorde-advies:** 2a eerst (rondt de feature-pariteit van de chat af, sluit aan op PR #182), dan 2b (grootste UX-risico op mobiel), dan 2c (dev-tool + cosmetisch). Geen harde afhankelijkheden tussen de drie.

> **Status van dit document:** alle drie de deelplannen (2a, 2b, 2c) zijn uitgewerkt op basis van
> drie parallelle read-only research-audits (chat-UX, PDF, beheer+styling). Eén **open
> productbeslissing** staat nog: de mentor-nav-link in 2c Task 4 (FastAPI heeft geen losse
> begeleidingssessie-route — met Ed te bevestigen vóór uitvoering).

---

# Deelplan 2a — chat-UX-pariteit

**Doel:** de FastAPI-chat valt terug op KD/instellingsbronnen bij een onleesbare OER (met zichtbare banner), herstelt de zichtbare gespreksgeschiedenis bij page-load, en heeft de citaat-CSS-var gedicht.

## File Structure (2a)

- `app_fastapi/context.py` — `_oer_blok` niet meer droppen bij lege tekst; `laad_context` includeert OER-loze-maar-KD/bron-items en geeft een `oer_onleesbaar`-vlag terug.
- `app_fastapi/sessie.py` — `Sessie.oer_onleesbaar: bool` veld.
- `app_fastapi/main.py` — callers van `laad_context` de 4e returnwaarde laten opslaan; `oer_onleesbaar` aan template-context doorgeven; nieuw `GET /api/geschiedenis`.
- `app_fastapi/templates/{index,student_assistent,mentor_sessie}.html` — banner + rehydratie-haak.
- `app_fastapi/static/chat.js` + `static/app.js` — rehydratie bij load; (frontend-details volgen uit research).
- `app_fastapi/static/app.css` — `--marker-was`-var definiëren.
- `tests/test_fastapi_poc.py` — context-gate + 4-tuple + onleesbaar-vlag + geschiedenis-endpoint.

## Task 1: `laad_context` includeert onleesbare OER's via KD + geeft `oer_onleesbaar` terug

**Files:**
- Modify: `app_fastapi/context.py` (`_oer_blok` 50-68, `laad_context` 71-122)
- Test: `tests/test_fastapi_poc.py`

- [ ] **Step 1: Schrijf de falende tests**

Voeg toe aan `tests/test_fastapi_poc.py` (bij de `laad_context`-tests, na `test_laad_context_student_soorten_minstens_zo_breed`):

```python
def test_laad_context_viertuple_leeg():
    # Nieuw contract: 4-tuple (systeem, labels, domeinen, oer_onleesbaar).
    assert laad_context([]) == ("", [], [], False)


def test_laad_context_onleesbare_oer_via_kd(monkeypatch):
    """Een OER zonder leesbare tekst maar mét KD levert tóch context + oer_onleesbaar=True."""
    import app_fastapi.context as ctx

    # Forceer: bekende OER-rij, lege OER-tekst, wél een KD-tekst.
    fake_row = {
        "id": 1, "crebo": "25168", "opleiding": "Gastheer", "display_naam": "Da Vinci",
        "naam": "davinci", "leerweg": "BBL", "cohort": "2025", "instelling_id": 2,
        "bestandspad": "x.pdf",
    }
    ctx._oer_blok.cache_clear()
    monkeypatch.setattr(ctx, "_oer_blok", lambda oid: (fake_row, ""))
    monkeypatch.setattr(ctx, "laad_kwalificatiedossier_tekst", lambda c: "KD-INHOUD")
    monkeypatch.setattr(ctx, "laad_skills_tekst", lambda c: "")
    monkeypatch.setattr(ctx.db, "haal_instelling_document_op", lambda *a, **k: None)
    monkeypatch.setattr(ctx, "web_zoek_domeinen", lambda items: [])

    systeem, labels, domeinen, onleesbaar = laad_context([1])
    assert "KD-INHOUD" in systeem
    assert onleesbaar is True
    assert len(labels) == 1


def test_laad_context_leesbare_oer_niet_onleesbaar(monkeypatch):
    import app_fastapi.context as ctx

    fake_row = {
        "id": 1, "crebo": "25168", "opleiding": "Gastheer", "display_naam": "Da Vinci",
        "naam": "davinci", "leerweg": "BBL", "cohort": "2025", "instelling_id": 2,
        "bestandspad": "x.pdf",
    }
    ctx._oer_blok.cache_clear()
    monkeypatch.setattr(ctx, "_oer_blok", lambda oid: (fake_row, "ECHTE OER-TEKST"))
    monkeypatch.setattr(ctx, "laad_kwalificatiedossier_tekst", lambda c: "")
    monkeypatch.setattr(ctx, "laad_skills_tekst", lambda c: "")
    monkeypatch.setattr(ctx.db, "haal_instelling_document_op", lambda *a, **k: None)
    monkeypatch.setattr(ctx, "web_zoek_domeinen", lambda items: [])

    systeem, labels, domeinen, onleesbaar = laad_context([1])
    assert "ECHTE OER-TEKST" in systeem
    assert onleesbaar is False
```

- [ ] **Step 2: Run de tests, verifieer dat ze falen**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -k "laad_context_viertuple or onleesbare_oer_via_kd or leesbare_oer_niet" -v`
Expected: FAIL (`laad_context` geeft nu een 3-tuple terug; `_oer_blok` dropt lege tekst).

- [ ] **Step 3: Pas `_oer_blok` aan — drop niet op lege tekst**

In `app_fastapi/context.py`, vervang het einde van `_oer_blok` (regels 63-68):
```python
    if row is None:
        return None
    tekst = laad_oer_tekst(resolve_oer_pad(row["bestandspad"]))
    if not tekst.strip():
        return None
    return row, tekst
```
door:
```python
    if row is None:
        return None
    tekst = laad_oer_tekst(resolve_oer_pad(row["bestandspad"]))
    return row, tekst  # tekst mag leeg zijn (gescande OER) — laad_context beslist op KD/bron
```

- [ ] **Step 4: Pas `laad_context` aan — includeer op bron + geef `oer_onleesbaar` terug**

Vervang de loop-body + return in `laad_context`. De nieuwe versie (regels 80-122):
```python
    items: list[dict] = []
    labels: list[str] = []
    oer_onleesbaar = False
    conn = _conn()
    for oid in oer_ids[:3]:
        res = _oer_blok(oid)
        if res is None:
            continue
        row, tekst = res
        crebo = row["crebo"]

        instelling_bronnen: list[tuple[str, str]] = []
        for soort in soorten:
            doc = db.haal_instelling_document_op(conn, row["instelling_id"], soort)
            if doc is None or not doc["geindexeerd"]:
                continue
            doc_tekst = laad_instelling_bron_tekst(resolve_oer_pad(doc["bestandspad"]))
            if doc_tekst:
                instelling_bronnen.append((db.INSTELLING_SOORTEN[soort], doc_tekst))

        dossier_tekst = laad_kwalificatiedossier_tekst(crebo)
        # Onleesbare OER (gescande PDF) tóch opnemen als er een KD of instellingsbron is.
        if not tekst.strip() and not dossier_tekst and not instelling_bronnen:
            continue
        if not tekst.strip():
            oer_onleesbaar = True

        items.append(
            {
                "tekst": tekst,
                "opleiding": row["opleiding"],
                "display_naam": row["display_naam"],
                "naam": row["naam"],
                "leerweg": row["leerweg"],
                "cohort": row["cohort"],
                "crebo": crebo,
                "dossier_tekst": dossier_tekst,
                "skills_tekst": laad_skills_tekst(crebo),
                "instelling_bronnen": instelling_bronnen,
            }
        )
        labels.append(
            f"{row['display_naam']} · {schoon_opleiding_naam(row['opleiding'], crebo)} · "
            f"{row['leerweg']} {row['cohort']}"
        )

    if not items:
        return "", [], [], False
    domeinen = web_zoek_domeinen(items)
    systeem = bouw_gecombineerd_systeem(items, web_zoeken=bool(domeinen))
    return systeem, labels, domeinen, oer_onleesbaar
```
Werk ook de docstring-returnregel bij naar het 4-tuple, en de type-hint:
`) -> tuple[str, list[str], list[str], bool]:`.

- [ ] **Step 5: Run de context-tests**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -k "laad_context" -v`
Expected: PASS (incl. de bestaande `test_laad_context_geeft_systeem_en_label` en `..._student_soorten_minstens_zo_breed` — die unpacken 3 waarden en MOETEN aangepast worden; zie Step 6).

- [ ] **Step 6: Repareer de bestaande 3-tuple-unpacks in de tests**

In `tests/test_fastapi_poc.py` unpacken twee bestaande tests een 3-tuple:
- `test_laad_context_geeft_systeem_en_label`: `systeem, labels, domeinen = laad_context([oer_id])`
- `test_laad_context_student_soorten_minstens_zo_breed`: `publiek, _, _ = ...` en `student, _, _ = ...`
- `test_laad_context_onbekende_id`: `assert laad_context([99_999_999]) == ("", [], [])`

Wijzig deze naar het 4-tuple:
```python
    systeem, labels, domeinen, _ = laad_context([oer_id])
```
```python
    publiek, _, _, _ = laad_context([oer_id])
    student, _, _, _ = laad_context([oer_id], STUDENT_SOORTEN)
```
```python
    assert laad_context([99_999_999]) == ("", [], [], False)
```

- [ ] **Step 7: Run de volledige FastAPI-suite**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -v`
Expected: alle context-tests groen. (De callers in `main.py` zijn nog 3-tuple → Task 2.)

- [ ] **Step 8: Commit**

```bash
git add app_fastapi/context.py tests/test_fastapi_poc.py
git commit -m "feat(validatie): laad_context includeert onleesbare OER via KD + oer_onleesbaar-vlag"
```

## Task 2: `Sessie.oer_onleesbaar` + callers in main.py

**Files:**
- Modify: `app_fastapi/sessie.py` (`Sessie`-dataclass), `app_fastapi/main.py` (`laad_context`-callers: `api_vraag` ~116, `api_kies` ~140, `login_post` ~234, `mentor_sessie` ~325; template-context van `/student`, `/mentor/student/{id}`, en de publieke flow)
- Test: `tests/test_fastapi_poc.py`

- [ ] **Step 1: Voeg het veld toe aan `Sessie`**

In `app_fastapi/sessie.py`, in de `Sessie`-dataclass (na `oer_ids`):
```python
    oer_onleesbaar: bool = False
```
En in `Sessie.reset()` toevoegen: `self.oer_onleesbaar = False`.

- [ ] **Step 2: Werk de vier `laad_context`-callers bij (4-tuple)**

In `app_fastapi/main.py`, elke `s.oer_systeem, s.oer_labels, s.domeinen = laad_context(...)`
wordt `s.oer_systeem, s.oer_labels, s.domeinen, s.oer_onleesbaar = laad_context(...)`:
- `api_vraag` (~regel 116): `s.oer_systeem, s.oer_labels, s.domeinen, s.oer_onleesbaar = laad_context([oer_id])`
- `api_kies` (~regel 140): idem met `[int(i) for i in oer_ids]`
- `login_post` student-tak (~regel 234): idem met `[student["oer_id"]], STUDENT_SOORTEN`
- `mentor_sessie` (~regel 325): idem met `[prof["oer_id"]], MENTOR_SOORTEN`

- [ ] **Step 3: Geef `oer_onleesbaar` door aan de templates**

In `/student` (`student_home`), `/mentor/student/{id}` (`mentor_sessie`) en de publieke index-render:
voeg `"oer_onleesbaar": s.oer_onleesbaar` toe aan de `TemplateResponse`-context-dict.
(Voor de publieke landing: `index` rendert zonder sessie-context; daar komt de vlag via de
`/api/kies`- en `/api/vraag`-JSON-respons — voeg `"oer_onleesbaar": s.oer_onleesbaar` toe aan
die `JSONResponse`-payloads zodat `app.js` de banner kan tonen.)

- [ ] **Step 4: Test — login-student met onleesbare OER zet de vlag**

Voeg een test toe die met een gemockte `laad_context` (4-tuple, onleesbaar=True) controleert dat
na `/login` de sessie `oer_onleesbaar=True` heeft en de `/student`-respons het veld bevat. Gebruik
het bestaande TestClient + monkeypatch-patroon (zie `test_login_student_en_paginas`).

```python
def test_student_onleesbare_oer_zet_vlag(monkeypatch):
    import app_fastapi.main as main_mod

    monkeypatch.setattr(main_mod, "laad_context", lambda ids, soorten=None: ("SYS", ["L"], [], True))
    monkeypatch.setattr(main_mod, "auth_student", lambda i, w: {"id": 1, "naam": "T", "studentnummer": "100", "oer_id": 1})
    c = _client()
    r = c.post("/login", data={"rol": "student", "identifier": "100", "wachtwoord": "x"}, follow_redirects=False)
    assert r.status_code == 303
    # /student rendert nu met de banner-vlag
    pagina = c.get("/student")
    assert pagina.status_code == 200
```
(Verifieer de exacte mock-signatuur van `laad_context` met/zonder `soorten`-kwarg tegen de echte aanroep.)

- [ ] **Step 5: Run + commit**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -v` → PASS.
```bash
git add app_fastapi/sessie.py app_fastapi/main.py tests/test_fastapi_poc.py
git commit -m "feat(validatie): oer_onleesbaar door sessie + chat-routes naar templates"
```

## Task 3: Banner "OER niet machine-leesbaar" in de templates

**Files:** `app_fastapi/templates/{student_assistent,mentor_sessie,index}.html`, `app_fastapi/static/app.js`, `app_fastapi/static/app.css`

> Geen gedeelde include → drie insertiepunten. Classes uit de chat-render zijn `bubble-q`/`bubble-a`.

- [ ] **Step 1: CSS — `.banner-warn`-klasse**

Voeg in `app_fastapi/static/app.css` een definitie toe (hergebruik bestaande tokens):
```css
.banner-warn {
  margin: 0 0 12px; padding: 10px 14px; border-radius: 8px;
  background: var(--marker-was); border: 1px solid var(--marker);
  font: 500 0.92rem/1.4 var(--body); color: var(--ink);
}
```

- [ ] **Step 2: Student- en mentor-template**

In `app_fastapi/templates/student_assistent.html`, direct vóór `<div class="thread" id="thread" ...>` (regel 12):
```html
{% if oer_onleesbaar %}<div class="banner-warn">De OER van jouw opleiding is niet machine-leesbaar; antwoorden komen uit het landelijke kwalificatiedossier en de instellingsregelingen.</div>{% endif %}
```
In `app_fastapi/templates/mentor_sessie.html`, binnen `#tab-chat`, direct vóór `<div class="thread" id="thread" ...>` (regel 55):
```html
{% if oer_onleesbaar %}<div class="banner-warn">De OER van deze student is niet machine-leesbaar; antwoorden komen uit het landelijke kwalificatiedossier en de instellingsregelingen.</div>{% endif %}
```

- [ ] **Step 3: Publieke overlay (`index.html` + `app.js`)**

In `app_fastapi/templates/index.html`, vóór `<div class="thread" id="thread">` (regel 164):
```html
<div class="banner-warn" id="ovBanner" hidden></div>
```
In `app_fastapi/static/app.js`, voeg een helper toe en roep 'm aan waar de labels gezet worden (`setLabels`, ~regel 32-35) met de `oer_onleesbaar`-waarde uit de `/api/vraag`/`/api/kies`-JSON (Task 2 Step 3 levert dat veld):
```js
function setBanner(onleesbaar) {
  const b = document.getElementById("ovBanner");
  if (!b) return;
  b.hidden = !onleesbaar;
  if (onleesbaar) b.textContent =
    "De OER van deze opleiding is niet machine-leesbaar; antwoorden komen uit het landelijke kwalificatiedossier en de instellingsregelingen.";
}
```
Roep `setBanner(data.oer_onleesbaar)` aan in de `/api/vraag`- en `/api/kies`-responsverwerking, en `setBanner(false)` in de reset-handler (`ovReset`).

- [ ] **Step 4: UI-rooktest + commit**

Start de app (`SESSION_SECRET=x ALGEMEEN_WACHTWOORD=y COOKIE_HTTPS_ONLY=0 uv run uvicorn app_fastapi.main:app --port 8504`). Test publiek (crebo 25168 → banner), student (gekoppeld aan 25168 → banner), leesbare OER (géén banner).
```bash
git add app_fastapi/templates/ app_fastapi/static/app.js app_fastapi/static/app.css
git commit -m "feat(validatie): banner 'OER niet machine-leesbaar' in FastAPI-chat"
```

## Task 4: Chat-historie-rehydratie

**Files:** `app_fastapi/main.py` (nieuw `GET /api/geschiedenis`), `app_fastapi/static/chat.js`, `app_fastapi/static/app.js`, `tests/test_fastapi_poc.py`

- [ ] **Step 1: Falende test voor het endpoint**

```python
def test_api_geschiedenis_geeft_beurten(monkeypatch, tmp_path):
    monkeypatch.setattr("app_fastapi.sessie._DB_PAD", str(tmp_path / "s.db"))
    import app_fastapi.sessie as sessie_mod
    sessie_mod._reset_store_voor_test()
    c = _client()
    # geen historie → lege lijst
    r = c.get("/api/geschiedenis")
    assert r.status_code == 200 and r.json() == {"beurten": []}
```

- [ ] **Step 2: Run → faalt** (`404`, route bestaat niet).
Run: `uv run python -m pytest tests/test_fastapi_poc.py -k "geschiedenis" -v`

- [ ] **Step 3: Voeg de route toe** in `app_fastapi/main.py`, direct ná `api_reset` (~regel 207):
```python
@app.get("/api/geschiedenis")
def api_geschiedenis(request: Request):
    return JSONResponse({"beurten": get_sessie(request).chat_history})
```
(Read-only GET → de middleware bewaart 'm niet; geen lost-update-risico.)

- [ ] **Step 4: `addAntwoord` + `rehydrateer` in `chat.js`**

Voeg ná `addVraag` (~regel 70) toe:
```js
function addAntwoord(thread, md) {
  const d = document.createElement("div");
  d.className = "bubble-a";
  d.innerHTML = renderMarkdown(md);
  thread.appendChild(d);
  _scroll(thread);
}
async function rehydrateer(thread) {
  const r = await (await fetch("/api/geschiedenis")).json();
  for (const b of r.beurten || []) {
    if (b.role === "user") addVraag(thread, b.content);
    else addAntwoord(thread, b.content);
  }
}
```
In `mountInlineChat` (~regel 127), aan het begin: `rehydrateer(thread);`. Dit dekt student + mentor.

- [ ] **Step 5: Lazy rehydratie in de publieke overlay (`app.js`)**

In `openOverlay` (~regel 31), met een one-shot guard:
```js
let _gehydrateerd = false;
// in openOverlay(), ná het openen:
if (!_gehydrateerd) { _gehydrateerd = true; rehydrateer(thread); }
```
In `ovReset` (~regel 85-90): zet `_gehydrateerd = false;` (na reset is de historie leeg). Maak `rehydrateer`/`addAntwoord` bereikbaar voor `app.js` (zelfde global scope als de bestaande `mount*`-functies).

- [ ] **Step 6: Run + commit**
Run: `uv run python -m pytest tests/test_fastapi_poc.py -v` → PASS.
```bash
git add app_fastapi/main.py app_fastapi/static/chat.js app_fastapi/static/app.js tests/test_fastapi_poc.py
git commit -m "feat(validatie): chat-historie-rehydratie bij page-load (FastAPI)"
```

## Task 5: `--marker-was` CSS-var dichten

**Files:** `app_fastapi/static/app.css`

- [ ] **Step 1:** In `:root`, direct ná `--marker: #FFD84D;` (~regel 12):
```css
  --marker-was: rgba(255, 216, 77, 0.16);
```
- [ ] **Step 2:** Verifieer dat `.thread .bubble-a blockquote` (~regel 160) nu de var gebruikt i.p.v. de fallback; commit (kan met Task 3 mee).

---

# Deelplan 2b — PDF mobiel-proof

**Doel:** vervang de kale `<iframe>`-PDF-viewer (blank op iOS/Android) door een PDF.js-canvas-render
(st.pdf-equivalent) met een **download-/open-knop** als fallback, en dicht de ontbrekende
foutafhandeling. De viewer zit op **één plek** (`chat.js:mountStudiegids`, ~115-124) → de fix raakt
automatisch alle drie aanroepers (`studiegids.html`, `mentor_sessie.html`-tab, publieke overlay).

**Besloten:** PDF.js via **CDN** (lazy ESM-import, pinned versie, `GlobalWorkerOptions.workerSrc` naar
de matching CDN-worker). Geen CSP aanwezig → werkt direct; consistent met de bestaande Google-Fonts-CDN.
**Open punt voor productie:** zodra er een CSP komt, PDF.js vendoren in `static/` (zwaarder maar geen
externe origin). Noteren bij de PR.

## Task 1: Download-fallback in de backend
**Files:** `app_fastapi/main.py` (`api_oer_bestand` ~179-197), `tests/test_fastapi_poc.py`
- [ ] Test: `GET /api/oer/{id}/bestand?download=1` op een gekoppelde PDF geeft een
  `Content-Disposition: attachment`-header (mock/skip als geen DB).
- [ ] Breid de signatuur uit: `def api_oer_bestand(request, oer_id: int, download: int = 0)`. Bij
  `download` → `return FileResponse(pad, media_type=media, filename=pad.name)` (zet automatisch
  `Content-Disposition: attachment`). De inline-tak (PDF.js-fetch) blijft ongewijzigd. IDOR-guard +
  bestand-checks blijven voor beide takken gelden.
- [ ] Run + commit (`feat(validatie): ?download=1 attachment-fallback voor OER-bestand`).

## Task 2: PDF.js-canvas-viewer + foutafhandeling in `mountStudiegids`
**Files:** `app_fastapi/static/chat.js` (~115-124), `app_fastapi/static/app.css` (~173-184)
- [ ] Herschrijf `mountStudiegids(oerId, frameEl)`:
  1. `fetch` → **check `resp.ok`** eerst; bij niet-ok (403/404) toon nette melding in `frameEl`
     ("Studiegids kon niet geladen worden") i.p.v. de huidige else-tak die JSON-fout als markdown rendert.
  2. PDF-tak: een knoppenbalk (`.pdf-acties`) met **⬇️ Download** (`/api/oer/${oerId}/bestand?download=1`,
     `download`-attr) en **↗ Open in nieuw tabblad** (`/api/oer/${oerId}/bestand`, `target="_blank"`) —
     de open-knop is de cruciale mobiele fallback. Dan lazy `import()` van PDF.js (CDN), `getDocument`,
     loop pages → render elk naar een `<canvas>` op `devicePixelRatio`-schaal, append in `frameEl`.
  3. `try/catch` rond de PDF.js-render → bij fout alleen de download/open-knoppen tonen.
  4. markdown-tak (Deltion) ongewijzigd.
- [ ] CSS (`app.css`): `.pdf-frame canvas { width:100%; height:auto; display:block; margin:0 auto 12px;
  box-shadow:var(--shadow); }` + `.pdf-acties`-knoppenbalk (hergebruik `.iconbtn`/`.linkbtn`). De oude
  `.pdf-frame iframe`-regel mag weg.
- [ ] Geen template-wijziging nodig (de `.pdf-frame`-containers blijven mount-target). De publieke
  overlay-toggle (`app.js` ~79-83) doet al `pdfFrame.innerHTML = ""` bij dichtklappen → canvas wordt
  opgeruimd.
- [ ] Commit (`feat(validatie): PDF.js-canvas-viewer + download/open-fallback (mobiel-proof)`).

## Task 3: Verificatie op echt mobiel (verplicht)
- [ ] iOS Safari + iOS Chrome + Android Chrome: alle pagina's scherp (devicePixelRatio), scrollt in
  `.pdf-frame`, geen blank. Download-knop saved echt; open-knop opent native viewer. Foutpaden (403/404,
  Deltion-markdown) tonen nette melding. Alle drie aanroepers. CDN-uitval (devtools-block) → knoppen
  blijven zichtbaar (catch-fallback). Test via `chrome-devtools-mcp` én indien mogelijk een echt toestel
  (de iframe-valkuil reproduceert niet altijd in desktop-emulatie).
- [ ] PR 2b: `feat(validatie): FastAPI PDF mobiel-proof (PDF.js + download-fallback)`.

# Deelplan 2c — beheer + styling-pariteit

**Doel:** de dev-only beheer-pagina (`app/pages/9_beheer.py`) porten naar FastAPI met live
subprocess-output via SSE, achter `BEHEER_ENABLED`; plus twee kleine styling-pariteit-fixes.

> **cwd-kritisch:** beheer-commando's draaien met `cwd = repo-root` (`Path(__file__).resolve().parents[2]`),
> want `scripts/*.sh` en `uv run` verwachten dat. **Verse** `db.get_connection(...)` na een run
> (anders is de subprocess-commit onzichtbaar) — `main._conn()` maakt al telkens een nieuwe verbinding.

## Task 1: `BEHEER_ENABLED`-gate + commando-allowlist
**Files:** `app_fastapi/main.py`
- [ ] Module-constante naast `_ALGEMEEN_WACHTWOORD` (~regel 43): `_BEHEER_ENABLED = os.environ.get("BEHEER_ENABLED", "").lower() == "true"`.
- [ ] Allowlist-dict `_BEHEER_TAKEN: dict[str, list[str]]` met de **vaste** commando's (lijst-vorm, geen shell):
  `sync_oeren` → `["bash","scripts/sync_oeren.sh"]`, `ingest_alles` → `["uv","run","python","-m","validatie_samenwijzer.ingest","--alles"]`,
  `seed_bulk` → `["uv","run","python","scripts/seed_bulk.py"]`, `seed_minimal` → `[...,"scripts/seed.py"]`,
  `kd_sync` → `["bash","scripts/sync_kwalificatiedossiers.sh"]`, `kd_convert` → `["uv","run","python","scripts/convert_kwalificatiedossiers_md.py"]`
  (overige uit de tabel hieronder). De browser stuurt alleen een `taak`-**key**, nooit een commando-string.

Bron-commando's (uit `9_beheer.py`): Status (geen subprocess), Bootstrap (`bash scripts/bootstrap.sh` + vlaggen),
Sync oeren, Re-ingest (`--alles`|`--instelling <scope>` + opt `--reset`; scopes = `_INSTELLING_KEYS`:
`alles,aeres,curio,davinci,deltion,kwic,rijn_ijssel,talland,utrecht`), Kwalificatiedossiers (sync/convert/download/upload),
Seed (bulk/minimal).

## Task 2: SSE-run-route
**Files:** `app_fastapi/main.py`, `tests/test_fastapi_poc.py`
- [ ] Test: `/api/beheer/run?taak=onbekend` → 400; route → 404 als `_BEHEER_ENABLED` False (monkeypatch); mock `subprocess.Popen` om de stream te verifiëren zonder echt te draaien.
- [ ] **GET** `/api/beheer/run` (GET → de middleware bewaart 'm niet tijdens de lange run):
```python
@app.get("/api/beheer/run")
def beheer_run(request: Request, taak: str, reset: int = 0, instelling: str = ""):
    if not _BEHEER_ENABLED:
        return JSONResponse({"error": "uit"}, status_code=404)
    cmd = list(_BEHEER_TAKEN.get(taak, []))
    if not cmd:
        return JSONResponse({"error": "onbekende taak"}, status_code=400)
    if taak == "ingest" and instelling in _INSTELLING_KEYS:
        cmd = ["uv", "run", "python", "-m", "validatie_samenwijzer.ingest", "--instelling", instelling]
    if reset:
        cmd.append("--reset")

    def stream():
        proc = subprocess.Popen(cmd, cwd=str(_PROJECT_ROOT), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        for regel in iter(proc.stdout.readline, ""):
            yield f"data: {json.dumps({'regel': regel.rstrip()})}\n\n"
        proc.wait()
        yield f"data: {json.dumps({'done': True, 'exit': proc.returncode})}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")
```
  met `_PROJECT_ROOT = Path(__file__).resolve().parents[2]` en `_INSTELLING_KEYS` (set, gespiegeld uit `9_beheer.py`). **Veiligheid:** dubbele gate (`_BEHEER_ENABLED` + algemene poort), lijst-vorm `Popen` (geen `shell=True`), `instelling`/`reset` gevalideerd, `cwd` hard. Bevestig-vereisende taken (bootstrap/KD-download) achter een extra `bevestig=1`-param.

## Task 3: `/beheer`-pagina + status
**Files:** `app_fastapi/main.py`, `app_fastapi/templates/beheer.html`, evt. `app_fastapi/data.py`
- [ ] `GET /beheer` (achter gate) → render `beheer.html` met status-data (OERs per instelling totaal+geïndexeerd, `laatste_ingest_run`, bestanden op schijf, KD-coverage, instellingsregelingen — herbruik de queries uit `9_beheer.py:127-241` in een helper). Verse `db.get_connection`.
- [ ] `beheer.html` (stramien `mentor_studenten.html`): statusblok + per taak een knop met `data-taak` + een `<pre class="mono">` output-target; `{% block scripts %}` opent `EventSource('/api/beheer/run?taak=...')`, `onmessage` appendt `data.regel` (auto-scroll), sluit op `{"done":true}`.
- [ ] Optioneel: conditionele nav-link achter een `beheer_enabled`-template-var (anders direct via `/beheer`).
- [ ] Commit (`feat(validatie): beheer-pagina geport naar FastAPI (SSE subprocess-stream)`).

## Task 4: Styling-pariteit-fixes
**Files:** `app_fastapi/static/app.css`, `app_fastapi/templates/base.html`
- [ ] **Groen-tint** (`app.css`): de drie groenen (`--green:#2E4636` r.13, `.groen` r.190, `.fill.groen:#2e7d4f` r.191) consolideren naar de Streamlit-status-groen `#27ae60` (`styles.GROEN`). Verifieer met `grep` dat `--green` alleen in deze regels gebruikt wordt; zo ja: `--green: #27ae60` + beide `.groen`-regels via `var(--green)`.
- [ ] **Mentor-nav-link** — **besloten: optie (a)**. Voeg in `base.html` (binnen het `{% elif rol == 'mentor' %}`-blok, ~r.22-24) een tweede mentor-link toe met `href="/mentor"` en label "🎓 Begeleidingssessie", die `actief` wordt op een `/mentor/student/`-pad (FastAPI heeft geen losse sessie-route; de sessie start per student vanaf `/mentor`). Gebruik `{% if request.url.path.startswith('/mentor/student/') %}actief{% endif %}` voor de actief-staat.
- [ ] Commit (`fix(validatie): groen-tint pariteit + (evt.) mentor-nav-link`).

## Afronding 2c
- [ ] Tests groen + lint; lokale rooktest van `/beheer` met `BEHEER_ENABLED=true` (één veilige taak, bv. status + een droge run). PR 2c: `feat(validatie): FastAPI beheer-pagina + styling-pariteit`.

---

## Self-Review (2a, uitgevoerd bij het schrijven)

- **Spec-dekking:** KD-fallback gate (Task 1) + vlag-doorgifte (Task 2) + banner (Task 3); historie-rehydratie (Task 4); `--marker-was` (Task 5). 2b/2c gescoped. ✓
- **Type-consistentie:** `laad_context` → 4-tuple overal (Task 1 def + Task 1 Step 6 bestaande tests + Task 2 callers); `Sessie.oer_onleesbaar: bool` (Task 2) consistent met de template-context-key `oer_onleesbaar`. ✓
- **Placeholders:** 2a Tasks 1-2 zijn volledige code; Tasks 3-5 zijn bewust gemarkeerd als "aanvullen uit research" (frontend-insertiepunten vereisen de lopende file-reads) — geen verkapte placeholders in de backend-kern. 2b/2c expliciet scoped, niet uitgewerkt. ✓
