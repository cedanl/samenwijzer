# FastAPI-migratie — Implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. (Implementer-subagents zijn in dit project gesandboxed zonder Bash → inline uitvoeren; subagents alleen voor read-only review.)

**Goal:** FastAPI (`app_fastapi/`) productie-klaar maken en uiteindelijk de enige frontend van De digitale gids; dit plan dekt **Fase 1 (productie-blockers)** volledig en schetst Fase 2–3.

**Architecture:** UI-schil wisselt; Python-kern blijft gedeeld. Fase 1 vervangt de in-memory sessiestore door een SQLite-backed write-through store, hardt de cookies, en zet Fly op 1 machine. Fase 2 port de feature/kwaliteits-pariteit; Fase 3 doet de cutover + Streamlit-retire.

**Tech Stack:** FastAPI, Starlette `SessionMiddleware`, SQLite (stdlib `sqlite3`), pytest + `fastapi.testclient`. Commando's vanuit `validatie_samenwijzer/`.

**Spec:** `docs/plans/2026-06-10-fastapi-migratie-en-streamlit-retire.md`

---

## File Structure (Fase 1)

- `app_fastapi/sessie.py` — `Sessie`-dataclass (ongewijzigd) + **nieuwe** SQLite-store
  (`laad`/`bewaar`/serialisatie/TTL) en write-through `get_sessie`/`bewaar_sessie`.
- `app_fastapi/main.py` — `SESSION_SECRET` fail-closed + `https_only`; write-through-save in de
  `_toegangspoort`-middleware; expliciete save in de `api_chat`-stream.
- `fly.toml` — `min_machines_running = 1` (single-machine voor consistente SQLite-sessies).
- `tests/test_fastapi_poc.py` — store-tests (persist/herstel/TTL), fail-closed-secret-test.
- `data/sessies.db` — runtime, **al gitignored** via `data/*` (geen `.gitignore`-wijziging nodig).

---

## Task 1: SQLite-sessiestore met serialisatie + TTL

**Files:**
- Modify: `app_fastapi/sessie.py` (vervang in-memory `_STORE` + `get_sessie`, regels 67-77; behoud `Sessie` 20-64)
- Test: `tests/test_fastapi_poc.py`

- [ ] **Step 1: Schrijf de falende tests**

Voeg toe aan `tests/test_fastapi_poc.py` (bij de sessie-tests, na `test_sessie_reset_leegt_alles`):

```python
def test_sessiestore_bewaart_en_laadt(tmp_path, monkeypatch):
    from app_fastapi import sessie as sessie_mod

    monkeypatch.setattr(sessie_mod, "_DB_PAD", str(tmp_path / "sessies.db"))
    sessie_mod._reset_store_voor_test()
    s = sessie_mod.Sessie()
    s.oer_systeem = "PROMPT"
    s.oer_ids = [1, 2]
    s.voeg_beurt_toe("vraag", "antwoord")
    sessie_mod.bewaar("sid-1", s)

    geladen = sessie_mod.laad("sid-1")
    assert geladen is not None
    assert geladen.oer_systeem == "PROMPT"
    assert geladen.oer_ids == [1, 2]
    assert geladen.chat_history == [
        {"role": "user", "content": "vraag"},
        {"role": "assistant", "content": "antwoord"},
    ]


def test_sessiestore_laad_onbekende_sid_is_none(tmp_path, monkeypatch):
    from app_fastapi import sessie as sessie_mod

    monkeypatch.setattr(sessie_mod, "_DB_PAD", str(tmp_path / "sessies.db"))
    sessie_mod._reset_store_voor_test()
    assert sessie_mod.laad("bestaat-niet") is None


def test_sessiestore_ttl_verwijdert_verouderd(tmp_path, monkeypatch):
    from app_fastapi import sessie as sessie_mod

    monkeypatch.setattr(sessie_mod, "_DB_PAD", str(tmp_path / "sessies.db"))
    monkeypatch.setattr(sessie_mod, "_TTL_SECONDEN", 100)
    sessie_mod._reset_store_voor_test()
    # bewaar met een kunstmatig oude timestamp
    klok = [1_000_000.0]
    monkeypatch.setattr(sessie_mod.time, "time", lambda: klok[0])
    sessie_mod.bewaar("oud", sessie_mod.Sessie())
    klok[0] += 200  # voorbij de TTL
    sessie_mod.bewaar("nieuw", sessie_mod.Sessie())  # triggert lazy opruiming
    assert sessie_mod.laad("oud") is None
    assert sessie_mod.laad("nieuw") is not None
```

- [ ] **Step 2: Run de tests, verifieer dat ze falen**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -k "sessiestore" -v`
Expected: FAIL (`bewaar`/`laad`/`_DB_PAD`/`_reset_store_voor_test`/`_TTL_SECONDEN`/`time` bestaan nog niet).

- [ ] **Step 3: Vervang de in-memory store door een SQLite-store**

Vervang in `app_fastapi/sessie.py` de imports bovenaan:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
```
door:
```python
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
```

Vervang vervolgens het hele blok vanaf `_STORE: dict[str, Sessie] = {}` (regel 67) tot het einde van het bestand door:

```python
# ── SQLite-backed store (productie: 1 machine, overleeft app-restarts + TTL) ──────
_DB_PAD = os.environ.get("SESSIE_DB_PATH", "data/sessies.db")
_TTL_SECONDEN = 6 * 3600  # inactieve sessies vervallen na 6 uur
_conn: sqlite3.Connection | None = None


def _store() -> sqlite3.Connection:
    """Lazy SQLite-verbinding (WAL) met het sessies-schema."""
    global _conn
    if _conn is None:
        Path(_DB_PAD).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(_DB_PAD, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS sessies ("
            "sid TEXT PRIMARY KEY, data TEXT NOT NULL, laatst_gebruikt REAL NOT NULL)"
        )
        _conn.commit()
    return _conn


def _reset_store_voor_test() -> None:
    """Sluit de cache-verbinding zodat een test een vers `_DB_PAD` kan gebruiken."""
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = None


def _verwijder_verouderd(nu: float) -> None:
    _store().execute("DELETE FROM sessies WHERE laatst_gebruikt < ?", (nu - _TTL_SECONDEN,))
    _store().commit()


def bewaar(sid: str, sessie: Sessie) -> None:
    """Serialiseer en persisteer de sessie; ruim en passant verouderde sessies op."""
    nu = time.time()
    _verwijder_verouderd(nu)
    _store().execute(
        "INSERT INTO sessies (sid, data, laatst_gebruikt) VALUES (?, ?, ?) "
        "ON CONFLICT(sid) DO UPDATE SET data=excluded.data, laatst_gebruikt=excluded.laatst_gebruikt",
        (sid, json.dumps(asdict(sessie)), nu),
    )
    _store().commit()


def laad(sid: str) -> Sessie | None:
    """Lees een sessie uit de store, of None als die niet (meer) bestaat."""
    row = _store().execute("SELECT data FROM sessies WHERE sid = ?", (sid,)).fetchone()
    if row is None:
        return None
    return Sessie(**json.loads(row[0]))


def get_sessie(request) -> Sessie:
    """Haal (of maak) de sessie voor deze request; cachet op ``request.state``.

    Write-through: muteer het teruggegeven object vrij; persisteren gebeurt via
    ``bewaar_sessie`` (in de middleware na de request, en expliciet in de chat-stream).
    """
    if getattr(request.state, "sessie", None) is not None:
        return request.state.sessie
    sid = request.session.get("sid")
    sessie = laad(sid) if sid else None
    if sessie is None:
        sid = uuid.uuid4().hex
        request.session["sid"] = sid
        sessie = Sessie()
    request.state.sid = sid
    request.state.sessie = sessie
    return sessie


def bewaar_sessie(request) -> None:
    """Persisteer de op deze request gecachete sessie (no-op als er geen is)."""
    sessie = getattr(request.state, "sessie", None)
    sid = getattr(request.state, "sid", None)
    if sessie is not None and sid:
        bewaar(sid, sessie)
```

Voeg `os` en `Path` toe aan de imports (ze worden nu gebruikt):
```python
import json
import os
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
```

- [ ] **Step 4: Run de store-tests**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -k "sessiestore" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app_fastapi/sessie.py tests/test_fastapi_poc.py
git commit -m "feat(validatie): SQLite-backed sessiestore voor FastAPI (write-through + TTL)"
```

---

## Task 2: Write-through persistentie bedraden in main.py

**Files:**
- Modify: `app_fastapi/main.py` (`_toegangspoort`-middleware 49-60; `api_chat`-stream 157-176; import 30)
- Test: `tests/test_fastapi_poc.py`

- [ ] **Step 1: Schrijf de falende test**

Voeg toe aan `tests/test_fastapi_poc.py`. (Bekijk eerst hoe de bestaande TestClient-tests de
client + toegang opzetten — bv. `test_api_reset_ok`/`test_login_student_en_paginas` — en hergebruik
dat patroon: `SESSION_SECRET` env zetten, `TestClient(app)`, eerst `/toegang` POSTen.)

```python
def test_sessie_overleeft_nieuwe_client_via_store(tmp_path, monkeypatch):
    """Een tweede client met dezelfde sid-cookie krijgt de bewaarde sessie terug."""
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("ALGEMEEN_WACHTWOORD", "pw")
    monkeypatch.setattr("app_fastapi.sessie._DB_PAD", str(tmp_path / "s.db"))
    import app_fastapi.sessie as sessie_mod

    sessie_mod._reset_store_voor_test()
    from fastapi.testclient import TestClient

    from app_fastapi.main import app

    client = TestClient(app)
    client.post("/toegang", data={"wachtwoord": "pw"}, follow_redirects=False)
    # toegang is na de request bewaard in de store; lees 'm terug uit de DB
    cookie_sid_aanwezig = any("session" in c for c in client.cookies)
    assert cookie_sid_aanwezig
    rijen = sessie_mod._store().execute("SELECT COUNT(*) FROM sessies").fetchone()[0]
    assert rijen >= 1
```

- [ ] **Step 2: Run de test, verifieer dat hij faalt**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -k "overleeft_nieuwe_client" -v`
Expected: FAIL (de store wordt nog nergens geschreven → 0 rijen).

- [ ] **Step 3: Bedraad de write-through in de middleware**

In `app_fastapi/main.py`, pas de import aan (regel 30):
```python
from app_fastapi.sessie import bewaar_sessie, get_sessie
```

Vervang de `_toegangspoort`-middleware (regels 49-60) door:
```python
@app.middleware("http")
async def _toegangspoort(request: Request, call_next):
    """De hele app zit achter het algemene wachtwoord — sommige instellingen zetten
    hun OER achter een wachtwoord, dus niets is publiek vindbaar zonder de poort.
    Persisteert ná afloop de (mogelijk gemuteerde) sessie naar de store."""
    pad = request.url.path
    if pad.startswith("/static") or pad == "/toegang":
        response = await call_next(request)
        bewaar_sessie(request)
        return response
    if not get_sessie(request).toegang:
        bewaar_sessie(request)
        if pad.startswith("/api/"):
            return JSONResponse({"error": "geen toegang"}, status_code=401)
        return RedirectResponse("/toegang", status_code=303)
    response = await call_next(request)
    bewaar_sessie(request)
    return response
```

- [ ] **Step 4: Expliciete save in de chat-stream**

De `api_chat`-stream muteert ná afloop van de handler (`voeg_beurt_toe`), dus de middleware-save
mist dat. Vervang in `api_chat` (regel 168) de regel:
```python
            s.voeg_beurt_toe(vraag, antwoord)
```
door:
```python
            s.voeg_beurt_toe(vraag, antwoord)
            bewaar_sessie(request)
```
(De `request` is in scope via de closure; `bewaar_sessie` staat al geïmporteerd.)

- [ ] **Step 5: Run de test + alle bestaande FastAPI-tests**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -v`
Expected: PASS — de nieuwe test én alle bestaande (`test_api_reset_ok`, `test_login_student_en_paginas`, `test_mentor_idor_guard`, …) blijven groen.

- [ ] **Step 6: Commit**

```bash
git add app_fastapi/main.py tests/test_fastapi_poc.py
git commit -m "feat(validatie): write-through sessie-persistentie in middleware + chat-stream"
```

---

## Task 3: Cookie-hardening (SESSION_SECRET fail-closed + https_only)

**Files:**
- Modify: `app_fastapi/main.py` (regel 63-65, `SessionMiddleware`-registratie)
- Test: `tests/test_fastapi_poc.py`

- [ ] **Step 1: Schrijf de falende test**

```python
def test_session_secret_verplicht(monkeypatch):
    """Zonder SESSION_SECRET moet het opzetten van de app falen (fail-closed)."""
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    import importlib

    import app_fastapi.main as main_mod

    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        importlib.reload(main_mod)
```

- [ ] **Step 2: Run de test, verifieer dat hij faalt**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -k "session_secret_verplicht" -v`
Expected: FAIL (de huidige code valt terug op `"dev-poc-secret"`, geen RuntimeError).

- [ ] **Step 3: Maak het secret fail-closed + hard de cookie**

Vervang in `app_fastapi/main.py` regel 63-65:
```python
# SessionMiddleware ná de poort geregistreerd → draait als buitenste laag, zodat
# request.session (en dus get_sessie) in de poort beschikbaar is.
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET", "dev-poc-secret"))
```
door:
```python
# SessionMiddleware ná de poort geregistreerd → draait als buitenste laag, zodat
# request.session (en dus get_sessie) in de poort beschikbaar is.
_SESSION_SECRET = os.environ.get("SESSION_SECRET")
if not _SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET is verplicht (geen default) — zet 'm in .env / Fly-secrets.")
app.add_middleware(
    SessionMiddleware,
    secret_key=_SESSION_SECRET,
    https_only=True,
    same_site="lax",
)
```

- [ ] **Step 4: Zorg dat de testomgeving het secret zet**

De andere TestClient-tests importeren `app_fastapi.main` → dat eist nu `SESSION_SECRET`. Zet 'm
één keer centraal: voeg bovenaan `tests/test_fastapi_poc.py` (ná de bestaande imports, vóór de
eerste test) toe:
```python
os.environ.setdefault("SESSION_SECRET", "test-secret")
```
Controleer of `conftest.py` of bestaande tests al een secret zetten; zo ja, hergebruik dat i.p.v.
dupliceren.

- [ ] **Step 5: Run de volledige FastAPI-suite**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -v`
Expected: PASS (incl. de fail-closed-test; de reload-test herstelt het secret daarna niet —
draai 'm daarom als laatste of zet het secret in de test terug. Als de reload-test andere tests
beïnvloedt: zet aan het eind van de test `monkeypatch.setenv("SESSION_SECRET", "test-secret")` +
`importlib.reload(main_mod)`).

- [ ] **Step 6: Commit**

```bash
git add app_fastapi/main.py tests/test_fastapi_poc.py
git commit -m "feat(validatie): SESSION_SECRET fail-closed + https_only cookie-hardening"
```

---

## Task 4: Fly single-machine config

**Files:**
- Modify: `fly.toml` (`[http_service]`-blok)

- [ ] **Step 1: Zet min_machines_running op 1**

In `fly.toml`, in het `[http_service]`-blok, wijzig:
```toml
  min_machines_running = 0
```
naar:
```toml
  min_machines_running = 1
```
Laat `auto_stop_machines`/`auto_start_machines` staan; met één machine + `min_machines_running = 1`
blijft de SQLite-sessiestore consistent (geen tweede machine met eigen store).

- [ ] **Step 2: Documenteer de schaal-eis**

Voeg in `fly.toml` boven het `[http_service]`-blok een comment toe:
```toml
# SQLite-sessiestore vereist één machine: draai `flyctl scale count 1 -a digitale-gids`
# vóór/na deploy en houd min_machines_running = 1. Zie de FastAPI-migratie-spec.
```

- [ ] **Step 3: Verifieer (geen deploy in deze fase)**

Run: `grep -n "min_machines_running" fly.toml`
Expected: `min_machines_running = 1`.
> Effectief wordt dit pas bij de Fase 3-cutover-deploy. De feitelijke `flyctl scale count 1` is een
> handmatige ops-stap bij de cutover, niet hier.

- [ ] **Step 4: Commit**

```bash
git add fly.toml
git commit -m "chore(validatie): Fly single-machine voor SQLite-sessiestore (FastAPI)"
```

---

## Fase 1 — afronding

- [ ] Volledige suite groen: `uv run python -m pytest`
- [ ] Lint: `uv run ruff check app_fastapi/ tests/ && uv run ruff format --check app_fastapi/ tests/`
- [ ] Lokale rooktest: `SESSION_SECRET=x ALGEMEEN_WACHTWOORD=y uv run uvicorn app_fastapi.main:app --port 8504`
  → `/toegang` → chat → herstart proces → sessie (toegang/gesprek) overleeft via `data/sessies.db`.
- [ ] PR 1: `feat(validatie): FastAPI productie-blockers — SQLite-sessies + cookie-hardening`. Refs #177.

---

## Fase 2 — Feature/kwaliteits-pariteit (outline — apart plannen na Fase 1)

> Detailplan schrijven zodra Fase 1 gemerged is (de store-API uit Fase 1 bepaalt de leesgekant).

1. **chat-KD-fallback porten** — `app_fastapi/context.py`: includeer een OER met onleesbare
   fulltext tóch als er een KD/instellingsbron is (mirror van de Streamlit-fix PR #182); geef een
   `oer_onleesbaar`-signaal terug naar de routes. Templates (`index.html`, `student_assistent.html`,
   `mentor_sessie.html`): toon de banner. Verifieer dat `chat.bouw_*` (onleesbaar-modus, al
   aanwezig) de juiste prompt geeft. TDD: context-test (gate + signaal) + route-test (banner-veld).
2. **beheer porten** — nieuwe routes `/beheer` (+ subprocess-streaming) achter `BEHEER_ENABLED`,
   template `beheer.html`; mirror van `app/pages/9_beheer.py`. TDD: route geblokkeerd zonder flag.
3. **Kwaliteits-pariteit** — concreet gemaakt via de parallelle audit (2026-06-10):
   - **PDF mobiel-proof** (grootste gat): de viewer gebruikt al een server-URL-iframe (géén
     data-URI-valkuil), maar mist een **PDF.js-renderer** (st.pdf-equivalent) én **een
     download-/open-knop** als mobiele fallback — die ontbreekt in alle drie aanroepers
     (`studiegids.html`, `mentor_sessie.html`-tab, `index.html`-overlay). Backend `api_oer_bestand`
     (`main.py:179-197`) kan een `?download=1` → `FileResponse(filename=…, Content-Disposition:
     attachment` krijgen. Plus foutafhandeling in `mountStudiegids` (`chat.js:115`, check `resp.ok`).
   - **Chat-rendering**: definieer de ontbrekende `--marker-was` CSS-var (`app.css:160`); voeg
     **chat-historie-rehydratie** toe bij page-load (server houdt `chat_history`, maar de thread
     start leeg → divergeert van Streamlit `session_state`); spiegel een `LAGE_RELEVANTIE`-melding
     in de stream/`context.py` bij lege OER-context. (Escaping is al veilig — geen XSS-werk nodig.)
   - **Nav/styling**: mentor-nav mist de "Begeleidingssessie"-link (`base.html:22-24` vs
     `styles.py:_NAV_MENTOR`); groen-tint inconsistent (`app.css:13,190-191` vs `styles.py` `#27ae60`).
   - **GEEN dual-theme-werk**: het lime/sage student-vs-docent-thema zit in de *parent*-app, niet in
     dit subproject — hier is één editorial-thema dat al correct geport is. (Spec-aanname gecorrigeerd.)
   - UI-smoke-test per rol; PDF op **echt** mobiel verifiëren (iOS Safari + Android Chrome), niet
     alleen DevTools-emulatie.
4. PR 2: `feat(validatie): FastAPI feature/kwaliteits-pariteit (KD-fallback, beheer, PDF, chat-UX)`.

## Fase 3 — Cutover + retire (outline — apart plannen na Fase 2)

1. `Dockerfile.fastapi` finaliseren (`CMD uvicorn app_fastapi.main:app --port 8080` + env incl.
   `SESSION_SECRET`); `fly.toml` `[build] dockerfile = "Dockerfile.fastapi"`.
2. Fly-secret zetten: `flyctl secrets set SESSION_SECRET=… -a digitale-gids`; `flyctl scale count 1`.
3. Deploy + **volledige productie-UI-smoke-test** (publiek/student/mentor, incl. onleesbare OER).
4. Streamlit retiren: verwijder `app/`, repo-root `Dockerfile`, Streamlit-deps uit `pyproject.toml`
   (`streamlit`, `streamlit-pdf`, evt. alleen-Streamlit-deps — controleer `styles.py`-gebruik door
   niet-UI-code), update `CLAUDE.md`/`README`/docs. Verwijder de WhatsApp/Streamlit-only verwijzingen.
5. Rollback-vangnet: `flyctl releases rollback` naar de laatste Streamlit-release bij problemen.
6. PR 3: `feat(validatie): cutover naar FastAPI + retire Streamlit`.

---

## Self-Review (uitgevoerd bij het schrijven)

- **Spec-dekking Fase 1:** sessiestore (Task 1+2), cookie-hardening (Task 3), Fly 1 machine
  (Task 4) — alle drie blockers gedekt. Fase 2/3-spec-onderdelen staan als outline (bewust
  just-in-time). ✓
- **Placeholders:** geen TBD/TODO; alle code-stappen tonen echte code. De outlines voor Fase 2/3
  zijn expliciet als "apart plannen" gemarkeerd, geen verkapte placeholders in Fase 1. ✓
- **Naam/type-consistentie:** `_DB_PAD`, `_TTL_SECONDEN`, `_store()`, `_reset_store_voor_test()`,
  `_verwijder_verouderd()`, `bewaar()`, `laad()`, `get_sessie()`, `bewaar_sessie()`, `request.state.sid`
  /`request.state.sessie` consistent tussen Task 1 (definitie) en Task 2 (gebruik). ✓
- **Contract:** `Sessie`-dataclass + methoden blijven ongewijzigd → bestaande sessie-tests
  (`test_sessie_voeg_beurt_kapt_op_max`, `test_sessie_reset_leegt_alles`) blijven groen. ✓
