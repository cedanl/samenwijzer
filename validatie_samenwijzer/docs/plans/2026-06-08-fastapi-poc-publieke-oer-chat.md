# FastAPI-POC: publieke OER-chat — Implementatieplan

> **Voor agentic workers:** gebruik `superpowers:executing-plans` of `subagent-driven-development`
> om dit taak-voor-taak uit te voeren. Stappen gebruiken checkbox-syntax (`- [ ]`).
> Let op: implementer-subagents in deze repo zijn gesandboxed (geen `uvicorn`/`pytest`/`git`);
> de bouw- en verificatiestappen worden **inline** gedaan, subagents alleen voor review.

**Doel:** Bewijs dat we de publieke OER-chat (`app/pages/0_oer_vraag.py`) kunnen herbouwen in
FastAPI met de mock-up als frontend (volledige CSS/JS-vrijheid), terwijl we de hele Python-
"brein"-laag (`chat.py`, `db.py`, `_ai.py`) **ongewijzigd** hergebruiken.

**Architectuur:** Dunne FastAPI-laag (ASGI/uvicorn) serveert de statische mock-up-frontend +
een handvol JSON/SSE-endpoints die rechtstreeks `chat.py` aanroepen. Streaming-antwoorden lopen
via Server-Sent Events (de `genereer_antwoord`-generator mapt 1-op-1 op `text/event-stream`).
Sessiestate (chat-historie, gekozen OER's) leeft server-side, gesleuteld op een ondertekende
cookie. Draait standalone op een eigen poort, **náást** de bestaande Streamlit-app — nul risico.

**Tech stack:** FastAPI + uvicorn (ASGI), Starlette `SessionMiddleware` (ondertekende cookie) +
in-memory sessiestore, Jinja2 voor één template, vanilla JS/CSS frontend (geen build-step —
spiegelt de mock-up). Hergebruikt: `chat.py`, `db.py`, `_ai.py`, `oer_store`-queries.

---

## 1. Context & beslissing

De Streamlit-UI kan de mock-up-kwaliteit structureel niet halen (geen DOM-bezit, geen page-JS,
rerun-model, iframe-sandbox voor components). De business-logica is echter al volledig UI-vrij:
`chat.py`, `db.py`, `ingest.py`, `_ai.py` en de bron-modules importeren **geen streamlit**. Alleen
`_db.py`, `auth.py` en `styles.py` zijn Streamlit-gekoppeld. Daarom kunnen we de UI-schil
vervangen zonder het brein te herschrijven.

We doen dit **gefaseerd**, beginnend bij de publieke pagina (`0_oer_vraag.py`) — de etalage waar
de mock-up over gaat, geen login nodig, en de meest waardevolle "wow"-oppervlakte. Bevalt het,
dan migreren we student/mentor later; zo niet, dan is er weinig verbrand.

**Wat we hergebruiken (ongewijzigd):** alle publieke `chat.py`-functies — `identificeer_oer_kandidaten`,
`genereer_intake_antwoord`, `bouw_gecombineerd_systeem`, `bouw_berichten`, `genereer_antwoord`,
`web_zoek_domeinen`, en de loaders (`laad_oer_tekst`, `laad_kwalificatiedossier_tekst`,
`laad_skills_tekst`, `laad_instelling_bron_tekst`). Bevestigd streaming-contract: `genereer_antwoord`
en `genereer_intake_antwoord` zijn **generators die tekst-chunks yielden** (`stream.text_stream`),
gooien `anthropic.APITimeoutError` bij een vastgelopen stream, en zetten zelf `cache_control`
(1u-TTL op system + laatste user-turn). De FastAPI-laag geeft `berichten` ongewijzigd door en
hergebruikt dezelfde `_ai._client()` zodat prompt-caching blijft werken.

## 2. Scope

**In scope (POC):**
- Publieke landing = de mock-up, met werkende ask-box + suggestie-chips.
- Intake/identificatie: vraag → kandidaat-OER's (`identificeer_oer_kandidaten`).
- Drie flows uit `0_oer_vraag.py`: exact-1-match → direct chatten; ties → OER-kiezer (max 3);
  geen match → intake-chat tot genoeg info.
- Chat met **SSE-streaming**, bubbels in mock-up-stijl, markdown-rendering, citaat-pull-quotes.
- "Bekijk studiegids"-PDF-weergave per geladen OER.
- Sessiecontinuïteit (chat-historie max 20 beurten, "nieuw gesprek"-reset).
- Eigen `Dockerfile.fastapi` + lokaal draaien naast Streamlit.

**Buiten scope (POC):** login/student/mentor-pagina's, voortgang-grafieken, beheerpagina,
multi-machine sessie-persistentie (zie Risico's), Fly-deploy van de POC (pas na akkoord).

## 3. Architectuur

### 3.1 Backend-routes (`app_fastapi/main.py`)

| Route | Methode | Doel |
|---|---|---|
| `/` | GET | Serveer de landing (Jinja2-template = mock-up). |
| `/static/*` | GET | CSS/JS/fonts (StaticFiles). |
| `/api/vraag` | POST | `{vraag}` → identificeer kandidaten. Antwoord: `{"modus": "chat"\|"kies"\|"intake", ...}`. |
| `/api/kies` | POST | `{oer_ids:[...]}` → laad context server-side, zet in sessie, antwoord `{labels, oer_ids}`. |
| `/api/chat` | POST (SSE) | `{vraag}` → `text/event-stream` met antwoord-chunks (chat of intake, afhankelijk van sessie). |
| `/api/oer/{oer_id}/bestand` | GET | Serveer de OER-PDF (inline) voor de viewer. |
| `/api/reset` | POST | Wis sessie ("nieuw gesprek"). |

### 3.2 Sessiemodel

`SessionMiddleware` (ondertekende cookie) bewaart enkel een `sid`. Een server-side
`dict[sid, Sessie]` houdt de echte state (de system-prompt is tot ~500K tekens × 3 → past nooit
in een cookie):

```python
@dataclass
class Sessie:
    chat_history: list[dict]      # [{"role","content"}], max 20
    oer_systeem: str | None       # gecombineerde system-prompt (None = intake-modus)
    oer_labels: list[str]
    oer_ids: list[int]            # voor de PDF-viewer + rebuild
    domeinen: list[str]           # web-zoek-fallback
    kandidaten: list[dict]        # bij ties
    wachtende_vraag: str | None
```

Dit spiegelt exact het `pub_*`-session_state-contract uit `0_oer_vraag.py`.

### 3.3 Frontend (`app_fastapi/static/` + `templates/index.html`)

Vertrekpunt: `docs/mockups/oer-vraag-landing.html` (al geldige HTML/CSS/JS). Toevoegingen:
- ask-box `submit` → `fetch('/api/vraag')` → toont chat-paneel / OER-kiezer / intake.
- chat-paneel hergebruikt de `demo-band` bubble-stijl (`.bubble-q` / `.bubble-a` / `.cite`).
- SSE-consumptie via `EventSource`-achtige `fetch`+`ReadableStream` (POST → stream lezen).
- citaat-pull-quotes: markdown-blockquotes → `.cite`-styling (zelfde marker-sweep als mock-up).
- "Bekijk studiegids N" → `<iframe>`/`st.pdf`-equivalent op `/api/oer/{id}/bestand`.

### 3.4 Deploy-delta (later, na akkoord)

`fly.toml` blijft identiek (`internal_port = 8080`). Nieuw `Dockerfile.fastapi` met
`CMD ["uv","run","uvicorn","app_fastapi.main:app","--host","0.0.0.0","--port","8080"]`.
Voor multi-machine sessie: of `min_machines_running=1` + sticky, of later een gedeelde store.

## 4. Bestandsstructuur

```
validatie_samenwijzer/
├── app_fastapi/
│   ├── __init__.py
│   ├── main.py            # FastAPI-app, routes, SSE
│   ├── sessie.py          # Sessie-dataclass + in-memory store + cookie-helper
│   ├── context.py         # laad_context(oer_ids) → (systeem, labels, domeinen) — hergebruikt chat.py-loaders, @lru_cache
│   ├── templates/
│   │   └── index.html     # mock-up als Jinja2-template
│   └── static/
│       ├── app.js         # ask-box, SSE-consumptie, bubble-rendering, OER-kiezer
│       └── app.css        # = mock-up-CSS (1-op-1) + chat-paneel-aanvullingen
├── tests/
│   └── test_fastapi_poc.py
└── Dockerfile.fastapi     # (alleen voorbereid; deploy later)
```

`context.py` is de enige nieuwe businesslogica — een dunne orchestrator die de `chat.py`-loaders
bundelt (wat `0_oer_vraag.py:230-260` en `:337-360` nu inline doen). Wordt zo ook testbaar.

## 5. Implementatieplan

### Taak 1: Projectskelet + dependencies

**Files:** Create `app_fastapi/__init__.py`, modify `pyproject.toml`.

- [ ] **Stap 1:** Voeg deps toe aan `pyproject.toml` `dependencies`: `"fastapi>=0.115"`, `"uvicorn[standard]>=0.30"`, `"jinja2>=3.1"`, `"itsdangerous>=2.2"` (voor SessionMiddleware).
- [ ] **Stap 2:** `uv sync` — verifieer install.
  Run: `uv sync && uv run python -c "import fastapi, uvicorn, jinja2; print('ok')"`
  Verwacht: `ok`
- [ ] **Stap 3:** Maak lege `app_fastapi/__init__.py`.
- [ ] **Stap 4:** Commit. `git add app_fastapi pyproject.toml uv.lock && git commit -m "feat(poc): FastAPI-skelet + deps"`

### Taak 2: Context-orchestrator (`context.py`) — TDD

**Files:** Create `app_fastapi/context.py`, Test `tests/test_fastapi_poc.py`.

- [ ] **Stap 1: Failing test.** Test dat `laad_context([oer_id])` voor een geïndexeerde OER een
  niet-lege systeem-prompt + 1 label + oer_ids teruggeeft, en dat onbekende id's leeg systeem geven.

```python
# tests/test_fastapi_poc.py
import os
from validatie_samenwijzer import db
from app_fastapi.context import laad_context

def _een_geindexeerde_oer_id():
    conn = db.get_connection(os.environ.get("DB_PATH", "data/validatie.db"))
    row = conn.execute("SELECT id FROM oer_documenten WHERE geindexeerd=1 LIMIT 1").fetchone()
    return row[0]

def test_laad_context_geeft_systeem_en_label():
    oer_id = _een_geindexeerde_oer_id()
    systeem, labels, domeinen = laad_context([oer_id])
    assert systeem and len(systeem) > 500
    assert len(labels) == 1
    assert isinstance(domeinen, list)

def test_laad_context_lege_lijst():
    systeem, labels, domeinen = laad_context([])
    assert systeem == "" and labels == [] and domeinen == []
```

- [ ] **Stap 2:** Run → faalt (module bestaat niet).
  Run: `uv run pytest tests/test_fastapi_poc.py -q`  Verwacht: FAIL (ImportError).
- [ ] **Stap 3: Implementeer `context.py`.** Bundelt de loaders zoals `0_oer_vraag.py` dat doet.

```python
"""Dunne orchestrator: bouwt de chat-context uit gekozen OER-id's (hergebruikt chat.py)."""
from __future__ import annotations
import os
from functools import lru_cache
from validatie_samenwijzer import db
from validatie_samenwijzer.chat import (
    bouw_gecombineerd_systeem, laad_instelling_bron_tekst, laad_kwalificatiedossier_tekst,
    laad_oer_tekst, laad_skills_tekst, resolve_oer_pad, web_zoek_domeinen,
)
from validatie_samenwijzer.opleiding import schoon_opleiding_naam

def _conn():
    return db.get_connection(os.environ.get("DB_PATH", "data/validatie.db"))

@lru_cache(maxsize=64)
def _oer_blok(oer_id: int):
    """Geef (db-rij, geladen OER-tekst) voor één OER, of None als niet leesbaar/onbekend."""
    row = _conn().execute(
        """SELECT o.*, i.display_naam, i.naam AS inst_naam, i.id AS inst_id
           FROM oer_documenten o JOIN instellingen i ON i.id=o.instelling_id WHERE o.id=?""",
        (oer_id,),
    ).fetchone()
    if row is None:
        return None
    tekst = laad_oer_tekst(resolve_oer_pad(row["bestandspad"]))
    if not tekst.strip():
        return None
    return row, tekst

def laad_context(oer_ids: list[int]) -> tuple[str, list[str], list[str]]:
    """Geef (gecombineerde system-prompt, labels, web-zoek-domeinen) voor de gekozen OER's."""
    items, labels = [], []
    for oid in oer_ids[:3]:
        res = _oer_blok(oid)
        if res is None:
            continue
        row, tekst = res
        crebo = row["crebo"]
        # examenreglement (instellingsbrede bron), zoals 0_oer_vraag._examenreglement_bron
        regl = db.haal_instelling_document_op(_conn(), row["inst_id"], "examenreglement")
        bronnen = []
        if regl is not None:
            t = laad_instelling_bron_tekst(resolve_oer_pad(regl["bestandspad"]))
            if t:
                bronnen.append(("Examenreglement", t))
        items.append({
            "tekst": tekst, "opleiding": row["opleiding"], "display_naam": row["display_naam"],
            "leerweg": row["leerweg"], "cohort": row["cohort"], "crebo": crebo,
            "naam": row["display_naam"],
            "dossier_tekst": laad_kwalificatiedossier_tekst(crebo),
            "skills_tekst": laad_skills_tekst(crebo),
            "instelling_bronnen": bronnen,
        })
        labels.append(
            f"{row['display_naam']} · {schoon_opleiding_naam(row['opleiding'], crebo)} · "
            f"{row['leerweg']} {row['cohort']}"
        )
    if not items:
        return "", [], []
    domeinen = web_zoek_domeinen(items)
    systeem = bouw_gecombineerd_systeem(items, web_zoeken=bool(domeinen))
    return systeem, labels, domeinen
```

> **Let op tijdens bouw:** verifieer de exacte kolomnamen/aanroep-signaturen tegen `db.py` en
> `chat.bouw_gecombineerd_systeem` (de research-rapporten geven de vorm; de DB-rij-velden moeten
> kloppen). Pas `_oer_blok`-retour aan als `bouw_gecombineerd_systeem` andere keys verwacht.

- [ ] **Stap 4:** Run → slaagt.  Run: `uv run pytest tests/test_fastapi_poc.py -q`  Verwacht: 2 passed.
- [ ] **Stap 5:** Commit. `git add app_fastapi/context.py tests/test_fastapi_poc.py && git commit -m "feat(poc): context-orchestrator + test"`

### Taak 3: Sessie-laag (`sessie.py`)

**Files:** Create `app_fastapi/sessie.py`.

- [ ] **Stap 1:** Implementeer de `Sessie`-dataclass + in-memory store + `get_sessie(request)`-helper
  die een `sid`-cookie leest/zet via `request.session` (SessionMiddleware) en de server-side `Sessie`
  ophaalt/aanmaakt. `MAX_GESCHIEDENIS = 20`, window-shift in een `voeg_beurt_toe`-helper.
- [ ] **Stap 2:** Mini-test: `voeg_beurt_toe` kapt op 20 beurten; `reset` leegt alles.
  Run: `uv run pytest tests/test_fastapi_poc.py -q -k sessie`  Verwacht: passed.
- [ ] **Stap 3:** Commit. `git commit -am "feat(poc): server-side sessie + window-shift"`

### Taak 4: FastAPI-app + routes + SSE (`main.py`)

**Files:** Create `app_fastapi/main.py`.

- [ ] **Stap 1:** App-setup: `FastAPI()`, `SessionMiddleware(secret=...)`, `StaticFiles` op `/static`,
  Jinja2 `templates`. `GET /` rendert `index.html`.
- [ ] **Stap 2:** `POST /api/vraag`: lees `vraag`, haal alle OER's, `identificeer_oer_kandidaten`.
  Bepaal modus (`chat` bij 1 match → `laad_context` + sessie zetten; `kies` bij ties → kandidaten in
  sessie; `intake` bij 0). Antwoord JSON met de juiste payload (labels, of kandidatenlijst).
- [ ] **Stap 3:** `POST /api/kies`: `laad_context(oer_ids)` → sessie zetten → `{labels, oer_ids}`.
- [ ] **Stap 4:** `POST /api/chat` (SSE): bouw `berichten = bouw_berichten(sessie.chat_history, vraag)`;
  kies generator (`genereer_antwoord` als `sessie.oer_systeem` else `genereer_intake_antwoord`);
  stream als `text/event-stream`; vang `APITimeoutError`/`Exception` → `data: {"error":...}`; bij
  succes accumuleer + `voeg_beurt_toe`. Hergebruik `_ai._client()` (cache-continuïteit).

```python
from fastapi.responses import StreamingResponse
import anthropic, json
from validatie_samenwijzer._ai import _client as ai_client
from validatie_samenwijzer.chat import bouw_berichten, genereer_antwoord, genereer_intake_antwoord

@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()
    vraag = data["vraag"]
    s = get_sessie(request)
    berichten = bouw_berichten(s.chat_history, vraag)

    def stream():
        antwoord = ""
        try:
            if s.oer_systeem:
                gen = genereer_antwoord(ai_client(), s.oer_systeem, berichten,
                                        web_search_domeinen=s.domeinen or None)
            else:
                gen = genereer_intake_antwoord(ai_client(), berichten, _instellingen())
            for chunk in gen:
                antwoord += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            s.chat_history.append({"role": "user", "content": vraag})
            s.chat_history.append({"role": "assistant", "content": antwoord})
            _trim(s)
            yield "data: {\"done\": true}\n\n"
        except anthropic.APITimeoutError:
            yield f"data: {json.dumps({'error': 'timeout'})}\n\n"
        except Exception:
            log.exception("chat-stream mislukt")
            yield f"data: {json.dumps({'error': 'onbekend'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
```

- [ ] **Stap 5:** `GET /api/oer/{oer_id}/bestand`: lees `bestandspad` uit DB, `FileResponse`
  (PDF inline / `.md` als text). `POST /api/reset`: wis sessie.
- [ ] **Stap 6:** App-boot-test (TestClient): `GET /` → 200 + bevat "Stel je vraag";
  `POST /api/vraag` met onzin-instelling → modus `intake`.
  Run: `uv run pytest tests/test_fastapi_poc.py -q -k api`  Verwacht: passed.
- [ ] **Stap 7:** Commit. `git commit -am "feat(poc): FastAPI-routes + SSE-chat"`

### Taak 5: Frontend (template + JS/CSS uit de mock-up)

**Files:** Create `templates/index.html`, `static/app.css`, `static/app.js`.

- [ ] **Stap 1:** Kopieer de mock-up naar `index.html`; verplaats de `<style>` naar `app.css` en de
  `<script>` naar `app.js`; link ze. Verifieer dat de landing identiek rendert (`GET /`).
- [ ] **Stap 2:** Bedraad de ask-box: `submit` → `POST /api/vraag`. Toon op basis van `modus`:
  `chat` → open chat-paneel + stuur de oorspronkelijke vraag naar `/api/chat`; `kies` → render
  OER-kiezer (checkbox-lijst, max 3) → `POST /api/kies` → chat-paneel; `intake` → chat-paneel in
  intake-modus.
- [ ] **Stap 3:** Chat-paneel: render `.bubble-q`/`.bubble-a`; consumeer SSE via
  `fetch('/api/chat',{...})` + `response.body.getReader()`; stream chunks live; markdown→HTML
  (kleine renderer of `marked` via CDN); blockquote → `.cite`-pull-quote (marker-sweep).
- [ ] **Stap 4:** "Bekijk studiegids N"-knop per label → toggle `<iframe src="/api/oer/{id}/bestand">`.
  "Nieuw gesprek" → `POST /api/reset` → terug naar landing-state.
- [ ] **Stap 5:** Commit. `git commit -am "feat(poc): mock-up-frontend + chat-paneel + SSE-client"`

### Taak 6: Lokaal draaien + browser-smoke-test

- [ ] **Stap 1:** Start: `uv run uvicorn app_fastapi.main:app --port 8504 --reload` (poort 8504 zodat
  Streamlit op 8503 blijft draaien).
- [ ] **Stap 2:** Browser-smoke (chrome-devtools-mcp): open `localhost:8504`, stel een Deltion-vraag
  ("Bij hoeveel tekorten krijg ik een negatief BSA?"), doorloop intake/kies indien nodig, verifieer:
  streaming antwoord verschijnt, citaat-pull-quote rendert, "Bekijk studiegids" toont de PDF.
- [ ] **Stap 3:** Vergelijk visueel met de mock-up + met de Streamlit-versie. Screenshot vastleggen.
- [ ] **Stap 4:** `Dockerfile.fastapi` schrijven (niet deployen). Commit alles.

## 6. Risico's & bekende POC-grenzen

- **In-memory sessie ↔ 2 Fly-machines.** Werkt lokaal/1 machine; multi-machine vereist sticky
  sessions of een gedeelde store (Redis/sqlite). Voor de POC: lokaal + (indien deploy) `min_machines_running=1`.
- **Geen login.** Bewust — publieke pagina. Student/mentor komt in een latere fase.
- **DB-rij-velden in `context.py`** moeten tegen het echte `db.py`-schema gevalideerd worden tijdens
  de bouw (research gaf de vorm, niet elke kolomnaam). Eerste integratietest vangt mismatches.
- **Markdown-renderer client-side**: gebruik een bewezen mini-lib (bv. `marked`) i.p.v. zelf parsen,
  met escaping om XSS te vermijden (antwoorden kunnen `<` bevatten — zelfde les als de Streamlit-fix).
- **Prompt-cache**: alleen behouden als we `_ai._client()` hergebruiken en `berichten` ongewijzigd
  doorgeven (bevestigd in research). Niet per request een nieuwe client maken.

## 7. Succescriteria

1. `localhost:8504` toont de mock-up-landing pixel-gelijk aan `docs/mockups/oer-vraag-landing.html`.
2. Een echte OER-vraag levert een **streaming** antwoord met bron + vindplaats + citaat, citaat als
   pull-quote gerenderd — inhoudelijk gelijk aan de Streamlit-versie (zelfde `chat.py`).
3. Intake (geen match) en OER-kiezer (ties, max 3) werken.
4. "Bekijk studiegids" toont de PDF.
5. `chat.py`/`db.py`/`_ai.py` zijn **niet gewijzigd** (alleen `pyproject.toml` + nieuwe `app_fastapi/`).
6. Streamlit blijft ongemoeid en draait nog (8503).
7. Alle nieuwe tests groen; lint clean.

## 8. Uitvoerings-handoff

Na akkoord op dit doc bouw ik (b) **inline** (subagents zijn gesandboxed voor `uvicorn`/`pytest`),
taak voor taak met commits, en doe de browser-smoke-test zelf. Een review-subagent kijkt aan het
eind mee. Fly-deploy van de POC pas op jouw expliciete "ja".
