# Opleidingskiezer op de publieke startpagina — Implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Voeg een cascade van keuzemenu's (Instelling → Leerweg → Opleiding → Cohort) toe aan de publieke startpagina én aan de picker, zodat een student z'n studiegids gericht kiest met schone opleidingsnamen i.p.v. een te lange kandidatenlijst.

**Architecture:** Een gecommit JSON-asset (`data/opleidingsnamen.json`, gebouwd uit de parent-bronnen) levert autoritatieve crebo→naam-labels; een runtime-resolver in `opleiding.py` valt terug op de bestaande string-opschoner. `data.py` bouwt hieruit een geneste opleidingsboom; een nieuwe `GET /api/opleidingen` serveert die. De frontend (`app.js`) rendert één herbruikbare cascade-component op de startpagina én in de picker; beide laden via het bestaande `POST /api/kies`.

**Tech Stack:** Python 3.13, FastAPI, sqlite3, openpyxl (build-time, al een dependency), vanilla JS, paper/licht-CSS-thema.

## Global Constraints

- Geen business logic in `app_fastapi/`; geen raw SQL in routes — alle DB-toegang via `db.py` (`get_connection()`) of de bestaande `_conn()`-helpers. (CLAUDE.md)
- AI-isolatie ongemoeid: deze feature raakt geen Anthropic-calls.
- Publiek thema is **paper/licht**: gebruik tokens `--paper`, `--paper-card`, `--ink`, `--ink-soft`, `--line`, `--vermilion`, `--shadow-sm` uit `app_fastapi/static/app.css`. Géén donker thema.
- Static-asset-cache: na elke edit aan `app.css`/`app.js` hard-refreshen bij UI-checks.
- Lint: line-length 100, selectie `E,F,I,N,W,UP`. Draai lint, format en pytest **lokaal** (geen CI-gate voor dit subproject).
- Resolutie-sleutel `(instelling, leerweg, crebo, cohort)` is uniek (geverifieerd); een opleidingsnaam die binnen het nieuwste cohort meerdere crebo's dekt (21 randgevallen) levert meerdere `oer_ids` op die samen geladen worden (≤3).
- Commit-/PR-attributie: eindig commits met enkel `Ed de Feber, in nauwe samenwerking met Claude` — géén Co-Authored-By-trailer.
- Lokaal draaien: `uv run uvicorn app_fastapi.main:app --port 8504 --reload` (vereist `SESSION_SECRET` + `ALGEMEEN_WACHTWOORD` in `.env`). Tests: `uv run python -m pytest`.

---

### Task 1: Crebo→naam-asset + runtime-resolver

**Files:**
- Create: `scripts/build_opleidingsnamen.py`
- Create: `data/opleidingsnamen.json` (gegenereerd door het script)
- Modify: `src/validatie_samenwijzer/opleiding.py` (voeg `laad_crebo_namen` + `nette_opleiding_naam` toe)
- Test: `tests/test_opleiding_namen.py`

**Interfaces:**
- Produces:
  - `validatie_samenwijzer.opleiding.laad_crebo_namen(pad: str | None = None) -> dict[str, str]` (lru_cache, `.cache_clear()` beschikbaar)
  - `validatie_samenwijzer.opleiding.nette_opleiding_naam(crebo: str, opleiding: str = "") -> str`
  - `scripts/build_opleidingsnamen.py:bouw() -> dict[str, str]`
- Consumes: bestaande `validatie_samenwijzer.opleiding.schoon_opleiding_naam(opleiding, crebo)`.

- [ ] **Step 1: Schrijf de falende test**

```python
# tests/test_opleiding_namen.py
"""nette_opleiding_naam: autoritatieve crebo-naam met string-fallback."""

import json

from validatie_samenwijzer import opleiding


def test_nette_naam_gebruikt_crebo_lookup(tmp_path, monkeypatch):
    asset = tmp_path / "opleidingsnamen.json"
    asset.write_text(json.dumps({"25180": "Kok"}), encoding="utf-8")
    monkeypatch.setenv("OPLEIDINGSNAMEN_PAD", str(asset))
    opleiding.laad_crebo_namen.cache_clear()

    assert opleiding.nette_opleiding_naam("25180", "25180BBL2025MJP-Kok-rommel") == "Kok"


def test_nette_naam_valt_terug_op_string_opschoner(tmp_path, monkeypatch):
    asset = tmp_path / "opleidingsnamen.json"
    asset.write_text(json.dumps({"25180": "Kok"}), encoding="utf-8")
    monkeypatch.setenv("OPLEIDINGSNAMEN_PAD", str(asset))
    opleiding.laad_crebo_namen.cache_clear()

    # crebo 99999 niet in de lookup → val terug op schoon_opleiding_naam
    verwacht = opleiding.schoon_opleiding_naam("23030_BOL_2025__Laboratoriumtechniek", "99999")
    assert opleiding.nette_opleiding_naam("99999", "23030_BOL_2025__Laboratoriumtechniek") == verwacht


def test_laad_crebo_namen_zonder_bestand_geeft_leeg(tmp_path, monkeypatch):
    monkeypatch.setenv("OPLEIDINGSNAMEN_PAD", str(tmp_path / "bestaat-niet.json"))
    opleiding.laad_crebo_namen.cache_clear()
    assert opleiding.laad_crebo_namen() == {}
```

- [ ] **Step 2: Draai de test om te zien dat hij faalt**

Run: `uv run python -m pytest tests/test_opleiding_namen.py -v`
Expected: FAIL — `AttributeError: module 'validatie_samenwijzer.opleiding' has no attribute 'nette_opleiding_naam'`.

- [ ] **Step 3: Voeg resolver toe aan `opleiding.py`**

Voeg bovenaan `src/validatie_samenwijzer/opleiding.py` toe aan de imports (onder `import re`):

```python
import json
import os
from functools import lru_cache
```

Voeg onderaan het bestand toe:

```python
@lru_cache(maxsize=1)
def laad_crebo_namen(pad: str | None = None) -> dict[str, str]:
    """Autoritatieve crebo → kwalificatie-naam-lookup (gecommit JSON-asset).

    Pad via ``OPLEIDINGSNAMEN_PAD`` (default ``data/opleidingsnamen.json``). Ontbreekt
    het bestand, dan een lege dict — de resolver valt dan terug op de string-opschoner.
    """
    pad = pad or os.environ.get("OPLEIDINGSNAMEN_PAD", "data/opleidingsnamen.json")
    try:
        with open(pad, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def nette_opleiding_naam(crebo: str, opleiding: str = "") -> str:
    """Autoritatieve kwalificatie-naam per crebo; valt terug op ``schoon_opleiding_naam``."""
    naam = laad_crebo_namen().get(str(crebo))
    return naam if naam else schoon_opleiding_naam(opleiding, crebo)
```

- [ ] **Step 4: Draai de test om te zien dat hij slaagt**

Run: `uv run python -m pytest tests/test_opleiding_namen.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Schrijf het build-script**

```python
# scripts/build_opleidingsnamen.py
"""Bouw data/opleidingsnamen.json: crebo → nette kwalificatie-naam.

Bronnen (prioriteit): crebolijst.xlsx kolom 'Kwalificatie' (specifiek per crebo) →
mapping.json crebo_naar_dossier (brede dossier-naam). Crebo's zonder treffer worden
weggelaten; de runtime-resolver valt dan terug op schoon_opleiding_naam(). De bronnen
leven in de parent-repo (build-context = repo-root).

Draai vanuit validatie_samenwijzer/:
    uv run python scripts/build_opleidingsnamen.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import openpyxl

KD_PAD = Path(os.environ.get("KD_PAD", "../kwalificatiedossiers"))
UIT = Path(os.environ.get("OPLEIDINGSNAMEN_PAD", "data/opleidingsnamen.json"))


def _crebolijst_namen(xlsx: Path) -> dict[str, str]:
    wb = openpyxl.load_workbook(xlsx, read_only=True)
    rijen = list(wb.active.iter_rows(values_only=True))
    kop = next(
        i for i, r in enumerate(rijen) if r and "Opleidingscode" in r and "Kwalificatie" in r
    )
    kol = {v: j for j, v in enumerate(rijen[kop]) if v}
    ci, ck = kol["Opleidingscode"], kol["Kwalificatie"]
    out: dict[str, str] = {}
    for r in rijen[kop + 1 :]:
        code = r[ci]
        if code is None:
            continue
        naam = (r[ck] or "").replace("\xa0", " ").strip()
        if naam:
            out[str(code).strip()] = naam
    return out


def _mapping_namen(pad: Path) -> dict[str, str]:
    data = json.loads(pad.read_text(encoding="utf-8"))
    return {
        str(k): str(v).replace("\xa0", " ").strip()
        for k, v in data.get("crebo_naar_dossier", {}).items()
        if v
    }


def bouw() -> dict[str, str]:
    """crebolijst (specifiek) wint van mapping.json (breed)."""
    namen = _mapping_namen(KD_PAD / "mapping.json")
    namen.update(_crebolijst_namen(KD_PAD / "crebolijst.xlsx"))
    return dict(sorted(namen.items()))


if __name__ == "__main__":
    namen = bouw()
    UIT.write_text(json.dumps(namen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(namen)} crebo-namen geschreven naar {UIT}")
```

- [ ] **Step 6: Draai het build-script en controleer de output**

Run: `uv run python scripts/build_opleidingsnamen.py`
Expected: print `NNN crebo-namen geschreven naar data/opleidingsnamen.json` (NNN ≈ 450+). Controleer:

Run: `uv run python -c "import json; d=json.load(open('data/opleidingsnamen.json')); print(len(d), d.get('25180'))"`
Expected: aantal > 400 en een niet-lege naam voor `25180` (bv. `Keuken`/`Kok`-achtig).

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check --fix src/ app_fastapi/ scripts/ && uv run ruff format src/ app_fastapi/ scripts/
git add scripts/build_opleidingsnamen.py data/opleidingsnamen.json src/validatie_samenwijzer/opleiding.py tests/test_opleiding_namen.py
git commit -m "feat(validatie): crebo→naam-asset + nette_opleiding_naam-resolver"
```

---

### Task 2: Opleidingsboom-builder in `data.py`

**Files:**
- Modify: `app_fastapi/data.py` (import + nieuwe functie `opleidingen_boom`)
- Test: `tests/test_opleidingen_boom.py`

**Interfaces:**
- Consumes: `validatie_samenwijzer.opleiding.nette_opleiding_naam`, `db.get_alle_oers_met_instelling(conn)`.
- Produces: `app_fastapi.data.opleidingen_boom() -> list[dict]` met vorm:
  ```json
  [{"instelling": "Rijn IJssel",
    "leerwegen": [{"leerweg": "BOL",
      "opleidingen": [{"naam": "Kok",
        "cohorten": [{"cohort": "2025", "oer_ids": [123]}]}]}]}]
  ```
  Instellingen + leerwegen + opleidingen alfabetisch (opleidingen case-insensitive); cohorten aflopend (nieuwste eerst). Alleen `geindexeerd=1`.

- [ ] **Step 1: Schrijf de falende test**

```python
# tests/test_opleidingen_boom.py
"""opleidingen_boom: geneste, gesorteerde structuur uit de OER-documenten."""

from app_fastapi import data


def test_boom_structuur_en_sortering():
    boom = data.opleidingen_boom()
    assert isinstance(boom, list) and boom, "boom mag niet leeg zijn"

    # instellingen alfabetisch
    namen = [b["instelling"] for b in boom]
    assert namen == sorted(namen)

    eerste = boom[0]
    assert set(eerste) == {"instelling", "leerwegen"}
    lw = eerste["leerwegen"][0]
    assert set(lw) == {"leerweg", "opleidingen"}
    assert lw["leerweg"] in {"BOL", "BBL"}

    opl = lw["opleidingen"][0]
    assert set(opl) == {"naam", "cohorten"}
    assert opl["naam"] and not opl["naam"][0].isdigit()  # schone naam, geen ruwe string

    # opleidingen case-insensitief gesorteerd
    opl_namen = [o["naam"] for o in lw["opleidingen"]]
    assert opl_namen == sorted(opl_namen, key=str.casefold)

    coh = opl["cohorten"][0]
    assert set(coh) == {"cohort", "oer_ids"}
    assert coh["oer_ids"] and all(isinstance(i, int) for i in coh["oer_ids"])

    # cohorten aflopend (nieuwste eerst)
    cohorten = [c["cohort"] for c in opl["cohorten"]]
    assert cohorten == sorted(cohorten, reverse=True)


def test_boom_alleen_geindexeerd():
    # Alle oer_ids in de boom moeten geindexeerd=1 zijn.
    import os
    import sqlite3

    boom = data.opleidingen_boom()
    ids = {i for b in boom for lw in b["leerwegen"] for o in lw["opleidingen"] for c in o["cohorten"] for i in c["oer_ids"]}
    conn = sqlite3.connect(os.environ.get("DB_PATH", "data/validatie.db"))
    rij = conn.execute(
        f"SELECT COUNT(*) FROM oer_documenten WHERE geindexeerd=0 AND id IN ({','.join('?' * len(ids))})",
        tuple(ids),
    ).fetchone()
    assert rij[0] == 0
```

- [ ] **Step 2: Draai de test om te zien dat hij faalt**

Run: `uv run python -m pytest tests/test_opleidingen_boom.py -v`
Expected: FAIL — `AttributeError: module 'app_fastapi.data' has no attribute 'opleidingen_boom'`.

- [ ] **Step 3: Implementeer `opleidingen_boom` in `data.py`**

Wijzig de import bovenaan `app_fastapi/data.py`:

```python
from validatie_samenwijzer.opleiding import nette_opleiding_naam, schoon_opleiding_naam
```

Voeg onderaan `app_fastapi/data.py` toe:

```python
def opleidingen_boom() -> list[dict]:
    """Geneste keuzeboom instelling → leerweg → opleiding → cohort voor de publieke kiezer.

    Alleen geïndexeerde OER's. Opleidingsnamen via de autoritatieve crebo-lookup; een naam
    die binnen één cohort meerdere crebo's dekt levert meerdere oer_ids op (samen te laden).
    """
    rows = db.get_alle_oers_met_instelling(_conn())
    boom: dict[str, dict[str, dict[str, dict[str, list[int]]]]] = {}
    for r in rows:
        if not r["geindexeerd"]:
            continue
        naam = nette_opleiding_naam(r["crebo"], r["opleiding"])
        inst = boom.setdefault(r["display_naam"], {})
        lw = inst.setdefault(r["leerweg"], {})
        opl = lw.setdefault(naam, {})
        opl.setdefault(r["cohort"], []).append(r["id"])

    result: list[dict] = []
    for inst_naam in sorted(boom):
        leerwegen = []
        for lw_naam in sorted(boom[inst_naam]):
            opleidingen = []
            for opl_naam in sorted(boom[inst_naam][lw_naam], key=str.casefold):
                cohorten = [
                    {"cohort": coh, "oer_ids": boom[inst_naam][lw_naam][opl_naam][coh]}
                    for coh in sorted(boom[inst_naam][lw_naam][opl_naam], reverse=True)
                ]
                opleidingen.append({"naam": opl_naam, "cohorten": cohorten})
            leerwegen.append({"leerweg": lw_naam, "opleidingen": opleidingen})
        result.append({"instelling": inst_naam, "leerwegen": leerwegen})
    return result
```

- [ ] **Step 4: Draai de test om te zien dat hij slaagt**

Run: `uv run python -m pytest tests/test_opleidingen_boom.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check --fix src/ app_fastapi/ scripts/ && uv run ruff format src/ app_fastapi/ scripts/
git add app_fastapi/data.py tests/test_opleidingen_boom.py
git commit -m "feat(validatie): opleidingen_boom-builder voor de keuzecascade"
```

---

### Task 3: `GET /api/opleidingen` + `/api/kies` zonder wachtende vraag

**Files:**
- Modify: `app_fastapi/main.py` (import `data`, nieuwe route)
- Test: `tests/test_fastapi_poc.py` (voeg twee tests toe)

**Interfaces:**
- Consumes: `app_fastapi.data.opleidingen_boom()`, bestaande `POST /api/kies`.
- Produces: `GET /api/opleidingen` → JSON-lijst (de boom uit Task 2).

- [ ] **Step 1: Schrijf de falende tests**

Bekijk eerst hoe `tests/test_fastapi_poc.py` de `TestClient` opzet (bestaande fixture/helper) en volg dat patroon. Voeg toe (pas de client-fixturenaam aan op het bestaande patroon in het bestand):

```python
def test_api_opleidingen_geeft_boom(client):
    r = client.get("/api/opleidingen")
    assert r.status_code == 200
    boom = r.json()
    assert isinstance(boom, list) and boom
    assert {"instelling", "leerwegen"} <= set(boom[0])


def test_api_kies_zonder_wachtende_vraag(client):
    # Verzin een geldig oer_id uit de boom en laad het zónder voorafgaande vraag.
    boom = client.get("/api/opleidingen").json()
    oer_id = boom[0]["leerwegen"][0]["opleidingen"][0]["cohorten"][0]["oer_ids"][0]
    r = client.post("/api/kies", json={"oer_ids": [oer_id]})
    assert r.status_code == 200
    body = r.json()
    assert body["oer_ids"] == [oer_id]
    assert body["wachtende_vraag"] is None  # geen vraag in de sessie
    assert "labels" in body
```

> Let op: als de testclient een gedeelde sessie hergebruikt, isoleer deze test (eigen client of reset) zodat een eerder geladen OER `s.oer_systeem` niet beïnvloedt. Volg het isolatiepatroon dat al in `test_fastapi_poc.py` staat.

- [ ] **Step 2: Draai de tests om te zien dat ze falen**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -k "opleidingen or wachtende" -v`
Expected: FAIL — `/api/opleidingen` geeft 404 (route bestaat nog niet).

- [ ] **Step 3: Voeg de route + import toe in `main.py`**

Voeg bij de imports toe (bij de andere `app_fastapi`-imports, rond regel 30):

```python
from app_fastapi import data
```

Voeg de route toe, direct ná `index()` (rond regel 162):

```python
@app.get("/api/opleidingen")
def api_opleidingen() -> JSONResponse:
    """Keuzeboom instelling → leerweg → opleiding → cohort voor de publieke kiezer."""
    return JSONResponse(data.opleidingen_boom())
```

> `/api/kies` heeft geen wijziging nodig: het leest `oer_ids` uit de body, laadt context en geeft `wachtende_vraag` terug (`None` als de sessie er geen heeft). Bevestig dit door de tests te draaien.

- [ ] **Step 4: Draai de tests om te zien dat ze slagen**

Run: `uv run python -m pytest tests/test_fastapi_poc.py -k "opleidingen or wachtende" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Volledige testsuite + lint + commit**

```bash
uv run python -m pytest
uv run ruff check --fix src/ app_fastapi/ scripts/ && uv run ruff format src/ app_fastapi/ scripts/
git add app_fastapi/main.py tests/test_fastapi_poc.py
git commit -m "feat(validatie): GET /api/opleidingen endpoint voor de keuzecascade"
```

---

### Task 4: Herbruikbare cascade-component + startpagina-blok

**Files:**
- Modify: `app_fastapi/templates/index.html` (inklap-blok onder het hero-vraagveld)
- Modify: `app_fastapi/static/app.js` (cascade-builder + boom-loader + start-handler)
- Modify: `app_fastapi/static/app.css` (paper-thema styling)

**Interfaces:**
- Consumes: `GET /api/opleidingen`, `POST /api/kies`, bestaande `openOverlay()`, `rehydrateer()`, `setLabels()`, `setBanner()`, `streamAntwoord()`, `esc()`.
- Produces (in `app.js`, gebruikt door Task 5): `laadOplBoom() -> Promise<Array>`, `bouwCascade(container, boom, onKies)` waarbij `onKies(oerIds: number[])`.

- [ ] **Step 1: Voeg het inklap-blok toe in `index.html`**

Vervang in `app_fastapi/templates/index.html` het bestaande hero-startblok (regels 39–49, het `<div class="rise" ... id="start">`-blok) zó dat ná de `.chips`-div en vóór het sluiten van `#start` het kiezer-blok komt:

```html
      <div class="rise" style="transition-delay:.24s" id="start">
        <form class="ask" data-ask>
          <input type="text" placeholder="Bijv. Hoeveel punten heb ik nodig voor mijn BSA?" autocomplete="off" />
          <button type="submit" aria-label="Vraag stellen">→</button>
        </form>
        <div class="chips">
          <button class="chip" type="button">Wanneer krijg ik een bindend studieadvies?</button>
          <button class="chip" type="button">Hoe vaak mag ik herkansen?</button>
          <button class="chip" type="button">Telt mijn stage mee voor mijn diploma?</button>
        </div>
        <details class="oplkiezer">
          <summary>Of kies direct je opleiding</summary>
          <div id="oplCascade" class="cascade-host"></div>
        </details>
      </div>
```

- [ ] **Step 2: Voeg de cascade-component + boom-loader toe in `app.js`**

Voeg in `app_fastapi/static/app.js`, ná de regel `let oerIds = [];` (rond regel 36), toe:

```javascript
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

/* Bouwt 4 afhankelijke selects + startknop in `container`. Roept onKies(oerIds[]) aan. */
function bouwCascade(container, boom, onKies) {
  container.innerHTML = `
    <div class="cascade">
      <select class="cas-inst" aria-label="School"></select>
      <select class="cas-lw" aria-label="Leerweg" disabled></select>
      <select class="cas-opl" aria-label="Opleiding" disabled></select>
      <select class="cas-coh" aria-label="Cohort" disabled hidden></select>
      <button type="button" class="iconbtn cas-start" disabled>Open mijn studiegids →</button>
    </div>`;
  const selI = container.querySelector(".cas-inst");
  const selL = container.querySelector(".cas-lw");
  const selO = container.querySelector(".cas-opl");
  const selC = container.querySelector(".cas-coh");
  const btn = container.querySelector(".cas-start");
  let inst = null, lw = null, opl = null;

  const resetSel = (sel, ph) => { sel.innerHTML = `<option value="">${esc(ph)}</option>`; sel.disabled = true; };
  const check = () => {
    btn.disabled = !(opl && (opl.cohorten.length === 1 || selC.value !== ""));
  };

  _vulOpties(selI, boom.map((b) => b.instelling), "Kies je school…");
  selL.innerHTML = `<option value="">Leerweg…</option>`;
  selO.innerHTML = `<option value="">Opleiding…</option>`;
  selC.innerHTML = `<option value="">Cohort…</option>`;

  selI.addEventListener("change", () => {
    inst = selI.value === "" ? null : boom[Number(selI.value)];
    lw = null; opl = null;
    resetSel(selL, "Leerweg…"); resetSel(selO, "Opleiding…"); resetSel(selC, "Cohort…"); selC.hidden = true;
    if (inst) { _vulOpties(selL, inst.leerwegen.map((x) => x.leerweg), "Leerweg…"); selL.disabled = false; }
    check();
  });
  selL.addEventListener("change", () => {
    lw = selL.value === "" ? null : inst.leerwegen[Number(selL.value)];
    opl = null;
    resetSel(selO, "Opleiding…"); resetSel(selC, "Cohort…"); selC.hidden = true;
    if (lw) { _vulOpties(selO, lw.opleidingen.map((x) => x.naam), "Opleiding…"); selO.disabled = false; }
    check();
  });
  selO.addEventListener("change", () => {
    opl = selO.value === "" ? null : lw.opleidingen[Number(selO.value)];
    resetSel(selC, "Cohort…"); selC.hidden = true;
    if (opl && opl.cohorten.length > 1) {
      _vulOpties(selC, opl.cohorten.map((c) => c.cohort), "Cohort…");
      selC.disabled = false; selC.hidden = false;
    }
    check();
  });
  selC.addEventListener("change", check);
  btn.addEventListener("click", () => {
    if (!opl) return;
    const coh = opl.cohorten.length === 1 ? opl.cohorten[0] : opl.cohorten[Number(selC.value)];
    onKies(coh.oer_ids);
  });
}

/* Laadt de gekozen studiegids in de sessie en opent de chat (gedeeld door beide paden). */
async function laadStudiegidsEnOpen(oerIds) {
  openOverlay();
  if (!_gehydrateerd) { _gehydrateerd = true; await rehydrateer(thread); }
  const r = await (await fetch("/api/kies", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ oer_ids: oerIds }),
  })).json();
  oerIds = r.oer_ids || oerIds;
  window.oerIdsHuidig = oerIds;
  setLabels(r.labels);
  setBanner(r.oer_onleesbaar);
  if (r.wachtende_vraag) { await streamAntwoord(thread, r.wachtende_vraag); }
  else { ovAsk.querySelector("input").focus(); }
}
```

> **Belangrijk over `oerIds`:** de bestaande code gebruikt een module-scope `let oerIds`. Binnen `laadStudiegidsEnOpen` schaduwt de parameter die naam. Vermijd verwarring: hernoem de **parameter** naar `ids` en zet de module-variabele expliciet. Gebruik exact:

```javascript
async function laadStudiegidsEnOpen(ids) {
  openOverlay();
  if (!_gehydrateerd) { _gehydrateerd = true; await rehydrateer(thread); }
  const r = await (await fetch("/api/kies", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ oer_ids: ids }),
  })).json();
  oerIds = r.oer_ids || ids;        // module-scope variabele bijwerken
  setLabels(r.labels);
  setBanner(r.oer_onleesbaar);
  if (r.wachtende_vraag) { await streamAntwoord(thread, r.wachtende_vraag); }
  else { ovAsk.querySelector("input").focus(); }
}
```

(Gebruik deze tweede versie; verwijder de eerste met `window.oerIdsHuidig`.)

- [ ] **Step 3: Bedraad het startpagina-blok**

Voeg onderaan `app_fastapi/static/app.js` toe (ná de bestaande `.chip`-listener-blok):

```javascript
/* startpagina-cascade vullen */
const oplCascadeEl = document.getElementById("oplCascade");
if (oplCascadeEl) {
  laadOplBoom().then((boom) => bouwCascade(oplCascadeEl, boom, laadStudiegidsEnOpen));
}
```

- [ ] **Step 4: Voeg paper-thema styling toe in `app.css`**

Voeg onderaan `app_fastapi/static/app.css` toe:

```css
/* ── opleidingskiezer ─────────────────────────────────────────────────────── */
.oplkiezer { margin-top: 1.1rem; }
.oplkiezer > summary {
  cursor: pointer; display: inline-flex; align-items: center; gap: .4rem;
  font-size: .9rem; color: var(--ink-soft); list-style: none; user-select: none;
}
.oplkiezer > summary::-webkit-details-marker { display: none; }
.oplkiezer > summary::before { content: "▸"; transition: transform .2s; }
.oplkiezer[open] > summary::before { transform: rotate(90deg); }
.oplkiezer > summary:hover { color: var(--ink); }
.cascade-host { margin-top: .9rem; }
.cascade { display: flex; flex-wrap: wrap; gap: .6rem; align-items: center; }
.cascade select {
  font-family: inherit; font-size: .95rem; color: var(--ink);
  background: var(--paper-card); border: 1px solid var(--line); border-radius: 10px;
  padding: .6rem .9rem; min-width: 0; flex: 1 1 180px; cursor: pointer;
}
.cascade select:disabled { opacity: .5; cursor: not-allowed; }
.cascade select:focus { outline: 2px solid var(--vermilion); outline-offset: 1px; }
.cascade .cas-start { flex: 1 1 200px; height: 48px; }
.cascade .cas-start:disabled { opacity: .45; cursor: not-allowed; }
```

- [ ] **Step 5: Handmatige UI-check (startpagina-pad)**

Start de app (zie Global Constraints) en log in via de landing met `ALGEMEEN_WACHTWOORD`. Open de startpagina, klap **"Of kies direct je opleiding"** open. Verifieer:
- School-dropdown gevuld, leerweg/opleiding/cohort disabled tot de vorige gekozen is.
- Cohort-select verschijnt **alleen** bij een opleiding met >1 cohort.
- "Open mijn studiegids" opent de chat-overlay met gevulde labels en cursor in het vraagveld.
- Hard-refresh na CSS/JS-edits.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check src/ app_fastapi/ scripts/   # JS/CSS/HTML vallen buiten ruff
git add app_fastapi/templates/index.html app_fastapi/static/app.js app_fastapi/static/app.css
git commit -m "feat(validatie): opleidingskiezer-cascade op de publieke startpagina"
```

---

### Task 5: Picker gebruikt dezelfde cascade

**Files:**
- Modify: `app_fastapi/static/app.js` (`renderPicker` herschrijven; aanroep in `start()` aanpassen)

**Interfaces:**
- Consumes: `laadOplBoom()`, `bouwCascade()` (Task 4), bestaande `picker`, `setLabels()`, `setBanner()`, `streamAntwoord()`.

- [ ] **Step 1: Herschrijf `renderPicker` naar de cascade**

Vervang in `app_fastapi/static/app.js` de volledige functie `renderPicker(opties)` (de huidige checkbox-variant) door:

```javascript
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
    if (r.wachtende_vraag) { await streamAntwoord(thread, r.wachtende_vraag); }
  });
}
```

- [ ] **Step 2: Pas de aanroep in `start()` aan**

In `app_fastapi/static/app.js`, in functie `start(vraag)`, vervang:

```javascript
  if (r.modus === "kies") { renderPicker(r.opties); return; }
```

door:

```javascript
  if (r.modus === "kies") { renderPicker(); return; }
```

> De backend blijft `opties` in de respons sturen; die wordt nu genegeerd (geen backend-wijziging nodig). De cascade in de picker toont de volledige boom en versmalt gegarandeerd naar één studiegids — dit lost het "te veel kandidaten"-aantalsprobleem op.

- [ ] **Step 3: Handmatige UI-check (bug-pad)**

Start/refresh de app. Typ in het hero-vraagveld een **brede** vraag die meerdere kandidaten oplevert (bv. *"Hoeveel uur stage moet ik lopen?"* zonder opleiding gekozen). Verifieer:
- De overlay toont nu de **cascade** (school → leerweg → opleiding), géén lange checkbox-lijst.
- Na het kiezen van één opleiding wordt de studiegids geladen en de **oorspronkelijke vraag** automatisch beantwoord met citaat.

- [ ] **Step 4: Lint + commit**

```bash
uv run ruff check src/ app_fastapi/ scripts/
git add app_fastapi/static/app.js
git commit -m "feat(validatie): picker gebruikt dezelfde keuzecascade (fix te-veel-kandidaten)"
```

---

### Task 6: UI-smoke-test beide paden + dode code opruimen

**Files:**
- Modify: `app_fastapi/main.py` (alleen als de `opties`-opbouw in `api_vraag` nu volledig dood is — zie stap)

**Interfaces:** geen nieuwe.

- [ ] **Step 1: Volledige geautomatiseerde suite**

Run: `uv run python -m pytest`
Expected: alles groen.

- [ ] **Step 2: UI-smoke — shortcut-pad**

Via `chrome-devtools-mcp` of browser, ingelogd via de landing (`ALGEMEEN_WACHTWOORD`):
1. Open startpagina → klap kiezer open → kies bv. **Rijn IJssel → BOL → (een opleiding)**.
2. Klik "Open mijn studiegids" → typ *"Hoe vaak mag ik herkansen?"*.
3. Verifieer: geciteerd antwoord met bron + vindplaats + woordelijk citaat.
4. Verifieer: cohort-stap verscheen alleen bij een opleiding met >1 cohort.

- [ ] **Step 3: UI-smoke — bug-pad (bewijst de gemelde pijn weg)**

1. Open startpagina → typ direct in het hero-veld een brede vraag (géén opleiding gekozen).
2. Verifieer: de overlay toont de **cascade**, niet een platte lijst van veel OER's.
3. Kies één opleiding → de oorspronkelijke vraag wordt beantwoord met citaat.

- [ ] **Step 4: Dode code controleren**

Controleer of de flat-list-picker-opbouw nog ergens gebruikt wordt. In `app_fastapi/main.py:api_vraag` wordt `opties` nog opgebouwd en meegestuurd; de frontend negeert het nu. **Laat dit staan** (de backend-respons blijft geldig; verwijderen is buiten scope tenzij je eigen wijziging het wees maakte). Noteer het hooguit als observatie. Geen wijziging vereist in deze stap.

- [ ] **Step 5: Eindcommit (indien wijzigingen) en afronding**

Als er in deze taak niets is gewijzigd, geen commit. Anders:

```bash
uv run ruff check --fix src/ app_fastapi/ scripts/ && uv run ruff format src/ app_fastapi/ scripts/
git add -A
git commit -m "test(validatie): UI-smoke beide paden opleidingskiezer geverifieerd"
```

---

## Self-Review (uitgevoerd)

- **Spec-dekking:** Data-laag (Task 1) ✓, backend-boom + endpoint (Task 2–3) ✓, startpagina-blok (Task 4) ✓, picker-cascade als harde eis (Task 5) ✓, beide UI-smoke-paden (Task 6) ✓, `/api/kies` zonder wachtende vraag (Task 3) ✓.
- **Afwijking t.o.v. spec, bewust:** de spec nam aan dat er nog géén schone-naam-laag bestond; `opleiding.schoon_opleiding_naam` bestaat al en wordt nu de **fallback** onder de autoritatieve crebo-lookup (DRY, geen tweede naamsysteem). Het publieke thema is **paper/licht**, niet donker (spec-tekst gecorrigeerd in dit plan).
- **Type-consistentie:** `nette_opleiding_naam(crebo, opleiding="")` identiek gebruikt in Task 1 (def), Task 2 (consume). `bouwCascade(container, boom, onKies)` en `laadOplBoom()` identiek in Task 4 (def) en Task 5 (consume). Boom-vorm identiek in Task 2/3/4.
- **Geen placeholders:** alle code-stappen bevatten volledige code.

## Open observaties (geen blocker)

- `api_vraag` bouwt nog steeds `opties` op voor `modus: "kies"`; dit is nu dode payload aan de frontend-kant. Bewust niet verwijderd (chirurgische scope). Kandidaat voor opruiming in een latere PR.
- De picker-cascade toont de **volledige** boom, niet alleen de kandidaten die de vrije-tekst-picker vond. Bewust: garandeert versmalling naar één studiegids; de wachtende vraag blijft server-side bewaard en wordt na de keuze beantwoord.
