# Bronactualiteit Fase 3c — beheer-paneel + tuple-manifest + wekelijkse Action Implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Maak de bronactualiteit-check zichtbaar én operationeel: (1) een **paneel achter `/beheer`** dat het rapport on-demand draait, en (2) een **wekelijkse GitHub Action** die `check-bron-updates --oer` draait en bij een niet-leeg signaal een issue opent/actualiseert. Omdat `validatie.db` én een deel van `oeren/` gitignored zijn, diff't de Action niet tegen de DB maar tegen een **gecommit tuple-manifest** (`data/oer_corpus_manifest.json`) dat bij ingest wordt geregenereerd.

**Architecture:** Het paneel voegt géén logica toe aan een route: het hergebruikt de bestaande `/api/beheer/run`-allowlist (`_BEHEER_TAKEN`) die `check-bron-updates` als **subprocess** streamt — out-of-band, geen netwerk in het request-pad, geen import van `bron_updates` in `app_fastapi`. De manifest-laag voegt een deterministische, gecommitte snapshot van `(crebo, leerweg, cohort)` per instelling toe (gegenereerd uit de volledige lokale DB), plus een `--manifest`-modus in de catalogus-diff zodat de Action zonder DB kan draaien. De Action draait in de subproject-directory met een eigen `uv sync` en gebruikt `--alleen-oer` zodat de OER-check niet aan skills/kd-CI-gereedheid hangt.

**Tech Stack:** Python 3.13, FastAPI/Jinja2 (bestaand), `json` (stdlib), `uv`, GitHub Actions, `gh` CLI (`GITHUB_TOKEN`). Hergebruikt `oer_catalogus`, `bron_updates`, `db.get_alle_oers_met_instelling`, de `/api/beheer/run`-route en `beheer.html`.

## Global Constraints

- **Geen netwerk/logica in het request-pad** — het paneel draait `check-bron-updates` als subprocess via de bestaande `_BEHEER_TAKEN`-allowlist (lijst-vorm Popen, `cwd=_PROJECT_ROOT`). De route importeert `bron_updates` **niet** en roept `verzamel_bron_status` **niet** inline aan (zou het request blokkeren op multi-instelling netwerk-I/O).
- **Action diff't tegen de manifest, niet tegen de DB** — `validatie.db` is gitignored én `oeren/{deltion,davinci,kwic,graafschap}_oeren/` zijn gitignored, dus een verse runner kan de DB niet volledig herbouwen. De gecommitte manifest (gegenereerd uit de volledige lokale DB, inclusief Deltion) is de bron van waarheid voor "wat we al hebben".
- **Manifest = afgeleid, klein, gecommit** — volgt exact het precedent van `data/opleidingsnamen.json`: `data/*` is gitignored met een expliciete `!data/oer_corpus_manifest.json`-exceptie. Geregenereerd bij elke ingest met scope; nooit handmatig bewerkt.
- **Action is OER-only** — `check-bron-updates --oer --manifest --alleen-oer`. De skills-check (`refresh_fallbacks`) en kd-check (gitignorede `kwalificatiedossiers/`) zijn niet CI-gereed; `--alleen-oer` ontkoppelt de OER-check daarvan.
- **Issue-dedup** — vaste label `bronactualiteit`: bij een open issue → comment toevoegen; anders nieuw issue. Alleen bij een niet-leeg signaal. Voorkomt wekelijkse spam.
- **Workflow leeft in de parent-repo** — `validatie_samenwijzer` is geen eigen git-repo; de workflow staat in `/.github/workflows/` (repo-root) met `working-directory: validatie_samenwijzer` + eigen `uv sync`.
- **Reconciliatie met Fase 3b** — als het 3b-plan al gemerged is, heeft `verzamel_bron_status`/`main` al een `inhoud`-parameter/`--oer-inhoud`-flag. Voeg de hier toegevoegde `manifest`/`alleen_oer`-parameters en `--manifest`/`--alleen-oer`-flags daar náást toe (niet vervangen).
- Lint: line-length 100, selectie `E,F,I,N,W,UP`. `app_fastapi/*.py` wordt volledig gelint; HTML in `templates/` valt buiten ruff. Draai `ruff` + `pytest` lokaal.

## File Structure

- Modify: `src/validatie_samenwijzer/oer_catalogus.py` — `manifest_pad`, `genereer_corpus_manifest`, `_tupels_uit_manifest`, `manifest`-param op `instelling_nieuwe_oers`.
- Modify: `src/validatie_samenwijzer/ingest.py:669-680` — manifest regenereren na een ingest-run.
- Modify: `.gitignore` — `!data/oer_corpus_manifest.json`-exceptie.
- Modify: `src/validatie_samenwijzer/bron_updates.py` — `manifest`/`alleen_oer` door `_oer_status`/`verzamel_bron_status`/`main`.
- Modify: `app_fastapi/main.py:111-118` (`_BEHEER_TAKEN`) — twee bron_updates-taken.
- Modify: `app_fastapi/templates/beheer.html` — twee knoppen.
- Create: `/.github/workflows/bronactualiteit.yml` (parent-repo-root).
- Test: `tests/test_oer_catalogus.py`, `tests/test_bron_updates.py`, `tests/test_beheer.py` (nieuw, klein).

---

### Task 1: corpus-manifest genereren bij ingest

**Files:**
- Modify: `src/validatie_samenwijzer/oer_catalogus.py` (imports + `manifest_pad` + `genereer_corpus_manifest`)
- Modify: `src/validatie_samenwijzer/ingest.py:669-680`
- Modify: `.gitignore`
- Test: `tests/test_oer_catalogus.py`

**Interfaces:**
- Produces:
  - `manifest_pad() -> Path` (default `data/oer_corpus_manifest.json`, naast `DB_PATH`).
  - `genereer_corpus_manifest(conn, pad: Path) -> None` — schrijft `{instelling: [[crebo, leerweg, cohort], …]}` (gesorteerd, ontdubbeld) uit de volledige DB.
- Consumes: `db.get_alle_oers_met_instelling`.

- [ ] **Step 1: Schrijf de falende test**

Voeg toe aan `tests/test_oer_catalogus.py`:

```python
def test_genereer_corpus_manifest_schrijft_gesorteerde_tupels(tmp_path):
    import json
    import sqlite3

    from validatie_samenwijzer import oer_catalogus
    from validatie_samenwijzer.db import init_db, voeg_instelling_toe, voeg_oer_document_toe

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    inst = voeg_instelling_toe(conn, "deltion", "Deltion")
    voeg_oer_document_toe(conn, inst, "Kok", "25180", "2026", "BOL", "b.md")
    voeg_oer_document_toe(conn, inst, "Kok", "25180", "2025", "BOL", "a.md")

    pad = tmp_path / "oer_corpus_manifest.json"
    oer_catalogus.genereer_corpus_manifest(conn, pad)

    data = json.loads(pad.read_text(encoding="utf-8"))
    assert data["deltion"] == [["25180", "BOL", "2025"], ["25180", "BOL", "2026"]]
    conn.close()
```

- [ ] **Step 2: Draai de test, verifieer dat hij faalt**

Run: `uv run python -m pytest tests/test_oer_catalogus.py -q -k manifest`
Expected: FAIL — `genereer_corpus_manifest` niet gedefinieerd.

- [ ] **Step 3: Implementeer `manifest_pad` + `genereer_corpus_manifest`**

In `src/validatie_samenwijzer/oer_catalogus.py`, voeg `import json` toe bij de imports (`:15`), en voeg na `open_conn` (`:300`) toe:

```python
def manifest_pad() -> Path:
    """Pad van de gecommitte corpus-manifest (naast de DB; gitignored-met-exceptie)."""
    return Path(os.environ.get("DB_PATH", "data/validatie.db")).parent / "oer_corpus_manifest.json"


def genereer_corpus_manifest(conn, pad: Path) -> None:
    """Schrijf een deterministische snapshot van (crebo, leerweg, cohort) per instelling.

    De Action diff't hiertegen i.p.v. tegen de DB (validatie.db + een deel van oeren/ zijn
    gitignored). Gegenereerd uit de VOLLEDIGE lokale DB, dus inclusief Deltion. Gesorteerd
    + ontdubbeld zodat de diff klein en de git-diff stabiel blijft.
    """
    manifest: dict[str, list[tuple[str, str, str]]] = {}
    for r in db.get_alle_oers_met_instelling(conn):
        manifest.setdefault(r["naam"], []).append((r["crebo"], r["leerweg"], r["cohort"]))
    uit = {inst: [list(t) for t in sorted(set(tupels))] for inst, tupels in sorted(manifest.items())}
    pad.write_text(
        json.dumps(uit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
```

- [ ] **Step 4: Draai de test, verifieer dat hij slaagt**

Run: `uv run python -m pytest tests/test_oer_catalogus.py -q -k manifest`
Expected: PASS.

- [ ] **Step 5: Regenereer de manifest na elke ingest-run**

In `src/validatie_samenwijzer/ingest.py`, breid het `if scope is not None:`-blok (`:669-680`) uit zodat na het registreren van de run de manifest wordt herschreven uit de volledige DB:

```python
    if scope is not None:
        n_oers = conn.execute(
            "SELECT COUNT(*) FROM oer_documenten WHERE geindexeerd = 1"
        ).fetchone()[0]
        n_kerntaken = conn.execute("SELECT COUNT(*) FROM kerntaken").fetchone()[0]
        voeg_ingest_run_toe(
            conn,
            scope=scope,
            n_oers=n_oers,
            n_kerntaken=n_kerntaken,
            duur_seconden=time.monotonic() - start,
        )
        from validatie_samenwijzer.oer_catalogus import genereer_corpus_manifest, manifest_pad

        pad = manifest_pad()
        pad.parent.mkdir(parents=True, exist_ok=True)
        genereer_corpus_manifest(conn, pad)
        log.info("Corpus-manifest bijgewerkt: %s", pad)
```

- [ ] **Step 6: Voeg de `.gitignore`-exceptie toe**

In `validatie_samenwijzer/.gitignore`, ná de regel `!data/opleidingsnamen.json`, voeg toe:

```
# corpus-manifest (crebo/leerweg/cohort per instelling) → tracken zodat de wekelijkse
# bronactualiteit-Action zonder DB kan diffen (validatie.db is gitignored).
!data/oer_corpus_manifest.json
```

- [ ] **Step 7: Genereer + commit de eerste manifest**

```bash
uv run python -m validatie_samenwijzer.ingest --alles    # regenereert de manifest uit de volledige lokale DB
git check-ignore data/oer_corpus_manifest.json && echo "FOUT: nog genegeerd" || echo "OK trackbaar"
uv run ruff check src/validatie_samenwijzer/oer_catalogus.py src/validatie_samenwijzer/ingest.py tests/test_oer_catalogus.py
git add .gitignore data/oer_corpus_manifest.json src/validatie_samenwijzer/oer_catalogus.py src/validatie_samenwijzer/ingest.py tests/test_oer_catalogus.py
git commit -m "feat(validatie): corpus-manifest (gecommit) regenereren bij ingest"
```

Expected: `git check-ignore` print `OK trackbaar`; de manifest verschijnt in `git status` als toe te voegen bestand.

---

### Task 2: `--manifest`-diff-modus + `--alleen-oer`-filter

**Files:**
- Modify: `src/validatie_samenwijzer/oer_catalogus.py` (`_tupels_uit_manifest`, `manifest`-param op `instelling_nieuwe_oers`)
- Modify: `src/validatie_samenwijzer/bron_updates.py:102-181`
- Test: `tests/test_oer_catalogus.py`, `tests/test_bron_updates.py`

**Interfaces:**
- Produces:
  - `_tupels_uit_manifest(instelling: str, velden: tuple[str, ...], pad: Path) -> set[tuple[str, ...]]`
  - `instelling_nieuwe_oers(instelling, conn=None, *, manifest: bool = False) -> list[CatalogusItem]` (manifest=True → diff tegen de gecommitte manifest i.p.v. de DB).
  - `verzamel_bron_status(online=False, manifest=False, alleen_oer=False) -> list[BronStatus]`; `--manifest` + `--alleen-oer` in `main`.
- Consumes: `manifest_pad`, `genereer_corpus_manifest`-output (Task 1).

- [ ] **Step 1: Schrijf de falende tests**

Voeg toe aan `tests/test_oer_catalogus.py`:

```python
def test_instelling_nieuwe_oers_manifest_modus(tmp_path, monkeypatch):
    import json

    from validatie_samenwijzer import oer_catalogus
    from validatie_samenwijzer.oer_catalogus import CatalogusItem

    pad = tmp_path / "oer_corpus_manifest.json"
    pad.write_text(json.dumps({"deltion": [["25180", "BOL", "2025"]]}), encoding="utf-8")
    monkeypatch.setattr(oer_catalogus, "manifest_pad", lambda: pad)
    monkeypatch.setitem(
        oer_catalogus._CATALOGUS_BRONNEN,
        "deltion",
        lambda: [
            CatalogusItem("25180", "BOL", "2025", "Kok", "deltion"),     # in manifest → niet nieuw
            CatalogusItem("25180", "BOL", "2026", "Kok", "deltion"),     # nieuw cohort
        ],
    )
    nieuw = oer_catalogus.instelling_nieuwe_oers("deltion", manifest=True)
    assert [i.sleutel for i in nieuw] == [("25180", "BOL", "2026")]
```

Voeg toe aan `tests/test_bron_updates.py`:

```python
def test_verzamel_bron_status_alleen_oer(monkeypatch, gemockte_bronnen):
    monkeypatch.setattr(
        bron_updates.oer_catalogus, "_CATALOGUS_BRONNEN", {"deltion": lambda: []}
    )
    monkeypatch.setattr(
        bron_updates.oer_catalogus,
        "instelling_nieuwe_oers",
        lambda inst, conn=None, manifest=False: [],
    )
    statussen = bron_updates.verzamel_bron_status(online=True, manifest=True, alleen_oer=True)
    assert [s.bron for s in statussen] == ["oer"]  # geen skills/kd
```

- [ ] **Step 2: Draai de tests, verifieer dat ze falen**

Run: `uv run python -m pytest tests/test_oer_catalogus.py tests/test_bron_updates.py -q -k "manifest or alleen_oer"`
Expected: FAIL — `manifest`-param / `_tupels_uit_manifest` / `alleen_oer` ontbreken.

- [ ] **Step 3: Implementeer `_tupels_uit_manifest` + de `manifest`-tak**

In `src/validatie_samenwijzer/oer_catalogus.py`, na `_tupels_uit_rows` (`:99`):

```python
def _tupels_uit_manifest(
    instelling: str, velden: tuple[str, ...], pad: Path
) -> set[tuple[str, ...]]:
    """De op `velden` geprojecteerde set uit de gecommitte corpus-manifest."""
    data = json.loads(Path(pad).read_text(encoding="utf-8"))
    return {_projecteer(crebo, leerweg, cohort, velden) for crebo, leerweg, cohort in data.get(instelling, [])}
```

Vervang `instelling_nieuwe_oers` (`:303-325`) zodat de tupel-bron schakelbaar is:

```python
def instelling_nieuwe_oers(instelling: str, conn=None, *, manifest: bool = False) -> list[CatalogusItem]:
    """Haal de catalogus van een instelling en diff tegen wat we al hebben.

    Lege lijst als er (nog) geen adapter voor de instelling is. Standaard diff't hij tegen
    de DB; met ``manifest=True`` tegen de gecommitte ``oer_corpus_manifest.json`` — die modus
    heeft geen DB nodig en is bedoeld voor de wekelijkse Action (validatie.db is gitignored).
    Geef een open ``conn`` mee om bij meerdere instellingen één connectie te delen. Bij een
    netwerk-/API-fout raise't hij ``CatalogusOnbereikbaarError`` zodat de aanroeper kan degraderen.
    """
    bron = _CATALOGUS_BRONNEN.get(instelling)
    if bron is None:
        return []
    try:
        catalogus = bron()
    except httpx.HTTPError as e:
        raise CatalogusOnbereikbaarError(f"{instelling}: {e}") from e
    velden = _DIFF_SLEUTEL_VELDEN.get(instelling, _STANDAARD_VELDEN)
    if manifest:
        db_tupels = _tupels_uit_manifest(instelling, velden, manifest_pad())
    else:
        eigen = conn or open_conn()
        try:
            rows = db.get_alle_oers_met_instelling(eigen)
        finally:
            if conn is None:
                eigen.close()
        db_tupels = _tupels_uit_rows(rows, instelling, velden)
    return nieuwe_oers(catalogus, db_tupels, velden)
```

- [ ] **Step 4: Plumb `manifest` + `alleen_oer` door `bron_updates`**

In `src/validatie_samenwijzer/bron_updates.py`, vervang de signature + DB-opening van `_oer_status` (`:102-124`) zodat de manifest-modus geen DB opent:

```python
def _oer_status(online: bool = False, manifest: bool = False) -> BronStatus:
    if not online:
        return BronStatus(
            "oer",
            automatisch=False,
            signaal="OER-catalogus-check niet gedraaid — gebruik `check-bron-updates --oer`",
            details={"crawlbaar": _OER_CRAWLBAAR, "niet_crawlbaar": _OER_NIET_CRAWLBAAR},
        )
    nieuw: dict[str, list] = {}
    onbereikbaar: list[str] = []
    conn = None if manifest else oer_catalogus.open_conn()
    try:
        for inst in sorted(oer_catalogus._CATALOGUS_BRONNEN):
            try:
                items = oer_catalogus.instelling_nieuwe_oers(inst, conn=conn, manifest=manifest)
            except oer_catalogus.CatalogusOnbereikbaarError as e:
                logger.warning("OER-catalogus overgeslagen (%s)", e)
                onbereikbaar.append(inst)
                continue
            if items:
                nieuw[inst] = items
    finally:
        if conn is not None:
            conn.close()
```

> Laat de rest van `_oer_status` (`:125-147`, de `n_totaal`/`delen`/`return BronStatus`-opbouw) ongewijzigd.

Vervang `verzamel_bron_status` (`:150-151`):

```python
def verzamel_bron_status(
    online: bool = False, manifest: bool = False, alleen_oer: bool = False
) -> list[BronStatus]:
    if alleen_oer:
        return [_oer_status(online=online, manifest=manifest)]
    return [_skills_status(), _kd_status(), _oer_status(online=online, manifest=manifest)]
```

In `main` (`:165-172`), voeg de flags toe en geef ze door:

```python
    parser.add_argument(
        "--oer", action="store_true", help="Draai ook de online OER-catalogus-check (netwerk)"
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Diff tegen de gecommitte corpus-manifest i.p.v. de DB (voor de Action)",
    )
    parser.add_argument(
        "--alleen-oer", action="store_true", help="Rapporteer alleen de OER-bron (sla skills/kd over)"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        statussen = verzamel_bron_status(
            online=args.oer, manifest=args.manifest, alleen_oer=args.alleen_oer
        )
```

- [ ] **Step 5: Draai de tests, verifieer dat ze slagen**

Run: `uv run python -m pytest tests/test_oer_catalogus.py tests/test_bron_updates.py -q`
Expected: PASS.

- [ ] **Step 6: Live verificatie van de manifest-modus**

Run: `uv run check-bron-updates --oer --manifest --alleen-oer`
Expected: alleen de `oer`-regel; het signaal is identiek aan `--oer` zonder `--manifest` zolang de manifest in sync is met de DB (beide leveren dezelfde tupel-set). Een verschil duidt op een verouderde manifest → her-ingest.

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check src/validatie_samenwijzer/oer_catalogus.py src/validatie_samenwijzer/bron_updates.py tests/
git add src/validatie_samenwijzer/oer_catalogus.py src/validatie_samenwijzer/bron_updates.py tests/test_oer_catalogus.py tests/test_bron_updates.py
git commit -m "feat(validatie): --manifest-diff + --alleen-oer voor de wekelijkse check"
```

---

### Task 3: bronactualiteit-paneel achter `/beheer`

**Files:**
- Modify: `app_fastapi/main.py:111-118` (`_BEHEER_TAKEN`)
- Modify: `app_fastapi/templates/beheer.html:30-36` (knoppenrij)
- Test: `tests/test_beheer.py` (nieuw)

**Interfaces:**
- Consumes: de bestaande `/api/beheer/run`-route (`app_fastapi/main.py:472-505`) die een allowlist-taak als SSE-subprocess streamt; geen route-wijziging nodig.
- Produces: twee nieuwe allowlist-taken `bron_updates` + `bron_updates_oer`; twee knoppen in `beheer.html`.

- [ ] **Step 1: Schrijf de falende test**

Maak `tests/test_beheer.py`:

```python
"""De bronactualiteit-taken in de beheer-allowlist zijn lijst-vorm (geen shell) en
draaien de bron_updates-module zoals de bestaande ingest-taak."""

from app_fastapi.main import _BEHEER_TAKEN


def test_bron_updates_taken_in_allowlist():
    assert _BEHEER_TAKEN["bron_updates"] == [
        "uv", "run", "python", "-m", "validatie_samenwijzer.bron_updates"
    ]
    assert _BEHEER_TAKEN["bron_updates_oer"] == [
        "uv", "run", "python", "-m", "validatie_samenwijzer.bron_updates", "--oer"
    ]


def test_bron_updates_taken_zijn_lijst_vorm():
    # Geen shell-string (injectie-veilig), spiegelt het ingest_alles-patroon.
    for taak in ("bron_updates", "bron_updates_oer"):
        cmd = _BEHEER_TAKEN[taak]
        assert isinstance(cmd, list) and all(isinstance(x, str) for x in cmd)
```

- [ ] **Step 2: Draai de test, verifieer dat hij faalt**

Run: `uv run python -m pytest tests/test_beheer.py -q`
Expected: FAIL — `KeyError: 'bron_updates'`.

> Mocht de import van `app_fastapi.main` falen door ontbrekende env (`ALGEMEEN_WACHTWOORD`/`SESSION_SECRET` zijn fail-closed), zet ze in de test bovenaan via `os.environ.setdefault(...)` vóór de import, of gebruik de bestaande conftest-fixture als die de app-env al zet (controleer `tests/conftest.py`).

- [ ] **Step 3: Voeg de taken toe aan de allowlist**

In `app_fastapi/main.py`, vervang `_BEHEER_TAKEN` (`:111-118`):

```python
_BEHEER_TAKEN: dict[str, list[str]] = {
    "sync_oeren": ["bash", "scripts/sync_oeren.sh"],
    "ingest_alles": ["uv", "run", "python", "-m", "validatie_samenwijzer.ingest", "--alles"],
    "ingest": ["uv", "run", "python", "-m", "validatie_samenwijzer.ingest"],  # vereist --instelling
    "seed_bulk": ["uv", "run", "python", "scripts/seed_bulk.py"],
    "seed_minimal": ["uv", "run", "python", "scripts/seed.py"],
    "kd_sync": ["bash", "scripts/sync_kwalificatiedossiers.sh"],
    "bron_updates": ["uv", "run", "python", "-m", "validatie_samenwijzer.bron_updates"],
    "bron_updates_oer": ["uv", "run", "python", "-m", "validatie_samenwijzer.bron_updates", "--oer"],
}
```

- [ ] **Step 4: Voeg de knoppen toe aan `beheer.html`**

In `app_fastapi/templates/beheer.html`, breid de knoppenrij (`:30-36`) uit met twee knoppen (de bestaande JS wire't elke `data-taak` automatisch — `:65-67`):

```html
  <div class="beheer-knoppen">
    <button class="iconbtn" data-taak="sync_oeren">Sync oeren</button>
    <button class="iconbtn" data-taak="ingest_alles">Re-ingest (alles)</button>
    <button class="iconbtn" data-taak="kd_sync">Sync KD's</button>
    <button class="iconbtn" data-taak="seed_bulk">Seed (bulk)</button>
    <button class="iconbtn" data-taak="seed_minimal">Seed (minimal)</button>
    <button class="iconbtn" data-taak="bron_updates">Bronactualiteit (offline)</button>
    <button class="iconbtn" data-taak="bron_updates_oer">Bronactualiteit (online&nbsp;--oer)</button>
  </div>
```

- [ ] **Step 5: Draai de test, verifieer dat hij slaagt**

Run: `uv run python -m pytest tests/test_beheer.py -q`
Expected: PASS.

- [ ] **Step 6: UI-smoke-test (verplicht — pytest groen ≠ feature werkt)**

Start de app met `BEHEER_ENABLED=true` in `.env` en draai de smoke-test via een browser:

```bash
uv run uvicorn app_fastapi.main:app --port 8504 --reload
```

Stappen (via `chrome-devtools-mcp`, met `dangerouslyDisableSandbox` voor de background-server zodat localhost bereikbaar is — zie de geheugen-notitie over sandboxed localservers):
1. Open `http://localhost:8504/` en passeer de algemene poort met `ALGEMEEN_WACHTWOORD`.
2. Ga naar `/beheer`. Verwacht: de twee nieuwe knoppen "Bronactualiteit (offline)" en "Bronactualiteit (online --oer)".
3. Klik "Bronactualiteit (offline)". Verwacht: in `#output` streamt het rapport (`Bronactualiteit-rapport` + de skills/kd/oer-regels), eindigend met `[exit 0]`.
4. (Optioneel, netwerk) Klik "Bronactualiteit (online --oer)" en verifieer dat de oer-regel een echt signaal toont.

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check app_fastapi/main.py tests/test_beheer.py
git add app_fastapi/main.py app_fastapi/templates/beheer.html tests/test_beheer.py
git commit -m "feat(validatie): bronactualiteit-knoppen op het beheer-paneel (subprocess)"
```

---

### Task 4: wekelijkse GitHub Action met issue-opener

**Files:**
- Create: `/.github/workflows/bronactualiteit.yml` (parent-repo-root, NIET in het subproject)
- Test: geen (CI-config; geverifieerd via `workflow_dispatch`)

**Interfaces:**
- Consumes: `check-bron-updates --oer --manifest --alleen-oer` (Task 2), de gecommitte `data/oer_corpus_manifest.json` (Task 1), `gh` + `GITHUB_TOKEN`.
- Produces: een wekelijkse run die bij een niet-leeg OER-signaal een issue met label `bronactualiteit` opent of becommentarieert.

- [ ] **Step 1: Maak de workflow**

Maak `/.github/workflows/bronactualiteit.yml` (in de **parent-repo-root** `/home/eddef/projects/samenwijzer/.github/workflows/`, want het subproject is geen eigen git-repo):

```yaml
name: Bronactualiteit-check (wekelijks)

on:
  schedule:
    # Maandag 07:00 UTC — vóór de WhatsApp-checkin (08:00) zodat ze elkaar niet raken.
    - cron: "0 7 * * 1"
  workflow_dispatch:

permissions:
  contents: read
  issues: write

jobs:
  check:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: validatie_samenwijzer
    steps:
      - uses: actions/checkout@v4

      - name: Installeer uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Installeer dependencies (subproject)
        run: uv sync --extra dev

      - name: Draai de OER-bronactualiteit-check (manifest-modus, geen DB)
        run: uv run check-bron-updates --oer --manifest --alleen-oer | tee rapport.txt

      - name: Open of actualiseer een issue bij een signaal
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          if ! grep -qF "OER('s) beschikbaar" rapport.txt; then
            echo "Geen nieuwe OER's — geen issue."
            exit 0
          fi
          gh label create bronactualiteit --color FBCA04 --description "Wekelijkse OER-bronactualiteit-check" --force
          NUM=$(gh issue list --label bronactualiteit --state open --json number --jq '.[0].number // empty')
          BODY=$'Wekelijkse OER-bronactualiteit-check vond nieuwe OER('"'"'s) upstream.\n\n```\n'"$(cat rapport.txt)"$'\n```\n\nActie: ingest de nieuwe OER('"'"'s) lokaal en commit de bijgewerkte `data/oer_corpus_manifest.json`.'
          if [ -n "$NUM" ]; then
            gh issue comment "$NUM" --body "$BODY"
          else
            gh issue create --label bronactualiteit \
              --title "Bronactualiteit: nieuwe OER('s) beschikbaar" --body "$BODY"
          fi
```

> **Waarom deze keuzes:** `working-directory: validatie_samenwijzer` + eigen `uv sync` omdat het subproject geen workspace-member is (de root-`uv` bereikt het niet). `--alleen-oer` ontkoppelt van skills/kd die in CI niet gereed zijn (gitignorede `kwalificatiedossiers/`, mogelijke API-afhankelijkheid van `refresh_fallbacks`). `--manifest` omdat `validatie.db` gitignored is. De `grep -qF "OER('s) beschikbaar"` matcht alleen de positieve rapporttak (de lege tak meldt "geen nieuwe OER's via API"). `gh label create … --force` is idempotent zodat `gh issue create --label` niet faalt op een ontbrekend label.

- [ ] **Step 2: Verifieer de YAML-syntax lokaal**

```bash
python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('/home/eddef/projects/samenwijzer/.github/workflows/bronactualiteit.yml').read_text()); print('YAML OK')"
```

Expected: `YAML OK`.

- [ ] **Step 3: Commit**

```bash
git -C /home/eddef/projects/samenwijzer add .github/workflows/bronactualiteit.yml
git -C /home/eddef/projects/samenwijzer commit -m "ci(validatie): wekelijkse bronactualiteit-check opent issue bij nieuwe OER's"
```

- [ ] **Step 4: Live-verificatie via `workflow_dispatch` (na merge naar `main`)**

GitHub Actions draait alleen workflows die op de default-branch staan. Na merge:

```bash
gh workflow run "Bronactualiteit-check (wekelijks)" --repo <org>/samenwijzer
gh run watch --repo <org>/samenwijzer
```

Expected: groene run. Bij een echt signaal verschijnt/actualiseert een issue met label `bronactualiteit`; bij geen signaal logt de issue-stap "Geen nieuwe OER's — geen issue." en eindigt groen.

> **Let op:** de Action heeft schrijfrechten op issues (`permissions: issues: write` + de ingebouwde `GITHUB_TOKEN`). Geen extra secret nodig. Verifieer dat de repo-instelling "Workflow permissions" issues-write toestaat.

---

## Self-Review

**Spec-dekking.** Design-sectie "3c — `/beheer`-pagina + scheduling" uit het Fase 3-plan:
- "Bronactualiteit-paneel achter `/beheer` (`BEHEER_ENABLED`) dat `verzamel_bron_status(online=…)` toont — geen logica in de route, hergebruik de module" → Task 3. De advisor-verfijning (subprocess i.p.v. inline `verzamel_bron_status`, want de docstring verbiedt netwerk in het request-pad) is verwerkt: hergebruik via `_BEHEER_TAKEN`, geen `bron_updates`-import in de route.
- "GitHub Action (wekelijks) draait `check-bron-updates --oer`; bij een niet-leeg signaal opent/actualiseert hij een issue; sluit aan op het `checkin.yml`-patroon" → Task 4 (cron `0 7 * * 1`, `astral-sh/setup-uv`, `workflow_dispatch`, issue-dedup op label).
- Door Ed gekozen corpus-strategie (committed tuple-manifest) → Task 1 (generatie + `.gitignore`-exceptie) + Task 2 (`--manifest`-diff). Lost de advisor-blocker op (verse runner zonder DB zou élke gitignorede-Deltion-OER als nieuw melden).

**Placeholder-scan.** Alle code- en YAML-stappen zijn volledig. `<org>/samenwijzer` in Task 4, Step 4 is een bewuste placeholder voor de echte org (`cedanl` of de fork-owner) — die vult de uitvoerder in op basis van de remote (`git remote -v`); geen weggelaten logica. Twee "Let op"/"Mocht"-blokken zijn lees-instructies naar bestaande fixtures/instellingen, geen ontbrekende code.

**Type-consistentie.** `instelling_nieuwe_oers(instelling, conn=None, *, manifest=False)` matcht de aanroep in `_oer_status` én de mock in `test_verzamel_bron_status_alleen_oer`. `verzamel_bron_status(online, manifest, alleen_oer)` matcht `main` + de tests. `genereer_corpus_manifest(conn, pad)` en `manifest_pad()` matchen de ingest-hook (Task 1) en de monkeypatch in `test_instelling_nieuwe_oers_manifest_modus`. De manifest-vorm `{instelling: [[crebo, leerweg, cohort], …]}` is consistent tussen `genereer_corpus_manifest` (schrijft) en `_tupels_uit_manifest` (leest). `_BEHEER_TAKEN`-entries matchen `tests/test_beheer.py` exact.
```

