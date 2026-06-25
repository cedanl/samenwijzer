# Bronactualiteit Fase 3b — content_hash-register + content-wijzigingsdetectie Implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detecteer dat een OER die we **al** hebben upstream is **herzien** (zelfde crebo/leerweg/cohort, andere inhoud) door per document een genormaliseerde SHA256-`content_hash` op te slaan bij ingest en die te vergelijken met de upstream-content. Eerste (en voorlopig enige) bron met een per-OER content-endpoint: Deltion (`/reports/<uuid>/html`).

**Architecture:** Drie lagen. (1) Een **register**: een nullable `content_hash`-kolom op `oer_documenten` + `instelling_documenten`, additief toegevoegd via een idempotente `ALTER TABLE … ADD COLUMN`-migratie (géén DROP — de tabellen bevatten echte OER's + kerntaken). (2) Een **producent**: `ingest` berekent de hash uit de geëxtraheerde tekst via één gedeelde `bereken_content_hash`-helper en slaat 'm op. (3) Een **consument**: `oer_catalogus.gewijzigde_oers` refetcht per bekende Deltion-OER de upstream-content, hasht 'm via dezelfde helper en vergelijkt. Gegate achter een eigen `--oer-inhoud`-flag (één fetch per document = duur).

**Tech Stack:** Python 3.13, `hashlib` (stdlib), `httpx` (bestaande dep), `sqlite3`, pytest, `uv`. Hergebruikt `scripts/fetch_deltion.py` (`_haal_studiegids_md`, `_record`, `_HEADERS`) en `db.get_alle_oers_met_instelling`.

## Global Constraints

- **Additieve migratie, nooit destructief** — `content_hash` toevoegen gebeurt met `ALTER TABLE … ADD COLUMN`, idempotent geguard met een `PRAGMA table_info`-check. De bestaande `init_db`-migratie die `instelling_documenten` DROPt is voor een *pre-data* CHECK-fix; die mag NIET als model dienen voor het toevoegen van een kolom aan een tabel met echte data.
- **Eén hash-definitie voor beide kanten** — ingest (producent) en de upstream-check (consument) hashen via exact dezelfde `bereken_content_hash(tekst)` (whitespace-genormaliseerd). Twee aparte normalisaties → elke week een valse "gewijzigd".
- **Baseline-eerlijkheid** — een rij zonder opgeslagen hash (`NULL`, want vóór deze fase geïndexeerd) is **niet** "ongewijzigd"; de check telt 'm als "baseline ontbreekt" en raakt 'm niet aan. Eerste re-ingest legt de baseline vast.
- **Content-change is Deltion-only** — alleen Deltion heeft een per-OER content-endpoint. Andere instellingen leveren `([], 0)` en worden expliciet als "niet gecheckt" gerapporteerd, niet als "ongewijzigd" — spiegelt de bestaande "handmatig"-eerlijkheid in `_oer_status`.
- **Netwerk alleen achter de flag** — de upstream-check zit achter `--oer-inhoud`; het standaard `check-bron-updates` blijft offline/instant.
- **Out-of-band, muteert niets** — de check leest catalogus + DB en vergelijkt; schrijft niets. (De hash-`write` gebeurt uitsluitend in `ingest`, niet in de check.)
- **Volgorde t.o.v. Fase 3c** — implementeer **3b vóór 3c**. Beide plannen herschrijven (`Vervang`) `verzamel_bron_status` én `main` in `bron_updates.py`. 3b voegt `inhoud`/`--oer-inhoud` toe; 3c voegt `manifest`/`alleen_oer` + `--manifest`/`--alleen-oer` toe. Is 3c onverhoopt eerst gemerged, voeg de hier toegevoegde parameters/flags er dan **náást** (niet vervangen) — anders sneuvelt de `--oer --manifest --alleen-oer`-aanroep waar de Action op leunt.
- **Instelling-doc-hash is voorbereidend** — Task 2 vult `content_hash` óók op `instelling_documenten`, maar `gewijzigde_oers` consumeert in 3b alléén de Deltion-OER-hashes. De instelling-doc-kolom is dus bewust nog write-only groundwork (spec-vereist, goedkoop, additief); een consument volgt zodra een instelling een per-document content-endpoint krijgt.
- Lint: line-length 100, selectie `E,F,I,N,W,UP`. Draai `ruff` + `pytest` lokaal (geen CI-gate voor dit subproject).

## File Structure

- Modify: `src/validatie_samenwijzer/db.py` — migratie in `init_db`, `_kolom_bestaat`-helper, `set_oer_content_hash`, `set_instelling_document_content_hash`.
- Modify: `src/validatie_samenwijzer/oer_catalogus.py` — `bereken_content_hash`, `uuid` op `CatalogusItem`, `uuid` doorgeven in `_items_naar_catalogus`, `gewijzigde_oers`.
- Modify: `src/validatie_samenwijzer/ingest.py` — hash berekenen + opslaan in `_verwerk_bestand` en `_verwerk_instelling_documenten`.
- Modify: `src/validatie_samenwijzer/bron_updates.py` — `_oer_inhoud_status`, `--oer-inhoud`-flag, rapportage.
- Test: `tests/test_db.py`, `tests/test_oer_catalogus.py`, `tests/test_ingest.py`, `tests/test_bron_updates.py`.

---

### Task 1: `content_hash`-kolommen + setters (idempotente migratie)

**Files:**
- Modify: `src/validatie_samenwijzer/db.py:21-125` (`init_db`) + nieuwe helpers na `markeer_geindexeerd` (`:194`) en `markeer_instelling_document_geindexeerd` (`:268`)
- Test: `tests/test_db.py`

**Interfaces:**
- Produces:
  - `_kolom_bestaat(conn: sqlite3.Connection, tabel: str, kolom: str) -> bool`
  - `set_oer_content_hash(conn, oer_id: int, content_hash: str) -> None`
  - `set_instelling_document_content_hash(conn, doc_id: int, content_hash: str) -> None`
  - `oer_documenten` + `instelling_documenten` krijgen een nullable kolom `content_hash TEXT`.
- Consumes: niets nieuw.

- [ ] **Step 1: Schrijf de falende tests**

Voeg toe aan `tests/test_db.py`:

```python
def test_init_db_voegt_content_hash_kolom_toe(conn):
    for tabel in ("oer_documenten", "instelling_documenten"):
        kolommen = {r[1] for r in conn.execute(f"PRAGMA table_info({tabel})")}
        assert "content_hash" in kolommen


def test_init_db_migratie_is_idempotent_en_behoudt_data():
    """ALTER TABLE ADD COLUMN op een bestaande tabel mét data mag niet DROPpen."""
    import sqlite3

    from validatie_samenwijzer.db import init_db

    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    # Oud schema: oer_documenten ZONDER content_hash, met één rij.
    c.executescript(
        """
        CREATE TABLE instellingen (id INTEGER PRIMARY KEY, naam TEXT, display_naam TEXT);
        CREATE TABLE oer_documenten (
            id INTEGER PRIMARY KEY AUTOINCREMENT, instelling_id INTEGER NOT NULL,
            opleiding TEXT NOT NULL, crebo TEXT NOT NULL, cohort TEXT NOT NULL,
            leerweg TEXT NOT NULL, bestandspad TEXT NOT NULL,
            geindexeerd INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO instellingen (id, naam, display_naam) VALUES (1, 'deltion', 'Deltion');
        INSERT INTO oer_documenten (instelling_id, opleiding, crebo, cohort, leerweg, bestandspad)
            VALUES (1, 'Kok', '25180', '2025', 'BOL', 'x.md');
        """
    )
    c.commit()
    init_db(c)  # eerste keer: voegt kolom toe
    init_db(c)  # tweede keer: idempotent, geen fout
    rij = c.execute("SELECT crebo, content_hash FROM oer_documenten").fetchone()
    assert rij["crebo"] == "25180"  # rij behouden, niet ge-DROPt
    assert rij["content_hash"] is None  # nieuwe kolom, nog leeg
    c.close()


def test_set_oer_content_hash(conn):
    from validatie_samenwijzer.db import (
        set_oer_content_hash,
        voeg_instelling_toe,
        voeg_oer_document_toe,
    )

    inst = voeg_instelling_toe(conn, "deltion", "Deltion")
    oer_id = voeg_oer_document_toe(conn, inst, "Kok", "25180", "2025", "BOL", "x.md")
    set_oer_content_hash(conn, oer_id, "abc123")
    assert conn.execute(
        "SELECT content_hash FROM oer_documenten WHERE id = ?", (oer_id,)
    ).fetchone()[0] == "abc123"
```

- [ ] **Step 2: Draai de tests, verifieer dat ze falen**

Run: `uv run python -m pytest tests/test_db.py -q -k "content_hash"`
Expected: FAIL — kolom `content_hash` bestaat niet / `set_oer_content_hash` niet gedefinieerd.

- [ ] **Step 3: Voeg de migratie + helper toe aan `init_db`**

In `src/validatie_samenwijzer/db.py`, vlak vóór `def init_db` (`:21`), voeg de helper toe:

```python
def _kolom_bestaat(conn: sqlite3.Connection, tabel: str, kolom: str) -> bool:
    """True als `kolom` in `tabel` bestaat. Gebruikt positie 1 (de naam) zodat de check
    onafhankelijk is van de row_factory. Tabelnamen zijn hardgecodeerde literals."""
    return any(r[1] == kolom for r in conn.execute(f"PRAGMA table_info({tabel})"))
```

In `init_db`, ná de bestaande `conn.commit()` (`:125`, einde van `executescript`), voeg de additieve migratie toe:

```python
    # Additieve migratie (Fase 3b): content_hash per document voor upstream-
    # wijzigingsdetectie. ADD COLUMN i.p.v. DROP — deze tabellen bevatten echte OER's.
    for tabel in ("oer_documenten", "instelling_documenten"):
        if not _kolom_bestaat(conn, tabel, "content_hash"):
            conn.execute(f"ALTER TABLE {tabel} ADD COLUMN content_hash TEXT")
    conn.commit()
```

- [ ] **Step 4: Voeg de setters toe**

Na `markeer_geindexeerd` (`:194`):

```python
def set_oer_content_hash(conn: sqlite3.Connection, oer_id: int, content_hash: str) -> None:
    """Sla de content-hash van een OER-document op (voor upstream-wijzigingsdetectie)."""
    conn.execute(
        "UPDATE oer_documenten SET content_hash = ? WHERE id = ?", (content_hash, oer_id)
    )
    conn.commit()
```

Na `markeer_instelling_document_geindexeerd` (`:268`):

```python
def set_instelling_document_content_hash(
    conn: sqlite3.Connection, doc_id: int, content_hash: str
) -> None:
    """Sla de content-hash van een instellingsbreed document op."""
    conn.execute(
        "UPDATE instelling_documenten SET content_hash = ? WHERE id = ?", (content_hash, doc_id)
    )
    conn.commit()
```

- [ ] **Step 5: Draai de tests, verifieer dat ze slagen**

Run: `uv run python -m pytest tests/test_db.py -q`
Expected: PASS — alle bestaande + nieuwe tests groen.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check src/validatie_samenwijzer/db.py tests/test_db.py
git add src/validatie_samenwijzer/db.py tests/test_db.py
git commit -m "feat(validatie): content_hash-kolom + setters (idempotente ADD COLUMN-migratie)"
```

---

### Task 2: `bereken_content_hash`-helper + opslaan bij ingest

**Files:**
- Modify: `src/validatie_samenwijzer/oer_catalogus.py` (nieuwe `bereken_content_hash`-functie + import `hashlib`)
- Modify: `src/validatie_samenwijzer/ingest.py:451-536` (`_verwerk_bestand`) + `:563-610` (`_verwerk_instelling_documenten`)
- Test: `tests/test_oer_catalogus.py`, `tests/test_ingest.py`

**Interfaces:**
- Produces: `bereken_content_hash(tekst: str) -> str` in `oer_catalogus.py` (genormaliseerde SHA256-hex). Na ingest hebben geïndexeerde OER's + instellingsdocumenten een gevulde `content_hash`.
- Consumes: `db.set_oer_content_hash`, `db.set_instelling_document_content_hash` (Task 1).

- [ ] **Step 1: Schrijf de falende test voor de helper**

Voeg toe aan `tests/test_oer_catalogus.py`:

```python
def test_bereken_content_hash_negeert_whitespace_verschillen():
    from validatie_samenwijzer.oer_catalogus import bereken_content_hash

    assert bereken_content_hash("hallo  wereld") == bereken_content_hash("hallo\n\nwereld\n")
    assert bereken_content_hash("hallo wereld") != bereken_content_hash("hallo werelt")
    # Deterministisch + hex SHA256 (64 tekens).
    h = bereken_content_hash("x")
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)
```

- [ ] **Step 2: Draai de test, verifieer dat hij faalt**

Run: `uv run python -m pytest tests/test_oer_catalogus.py -q -k content_hash`
Expected: FAIL — `bereken_content_hash` niet gedefinieerd.

- [ ] **Step 3: Implementeer `bereken_content_hash`**

In `src/validatie_samenwijzer/oer_catalogus.py`, voeg `import hashlib` toe bij de imports (`:15`, bij `import logging`), en voeg na `_projecteer` (`:62`) toe:

```python
def bereken_content_hash(tekst: str) -> str:
    """Genormaliseerde SHA256-hex van documenttekst, voor upstream-wijzigingsdetectie.

    Whitespace wordt gecollapst (`" ".join(tekst.split())`) zodat onbelangrijke
    verschillen (regeleindes, dubbele spaties) geen valse 'gewijzigd' triggeren. DEZE
    helper is de enige bron van waarheid: ingest (producent) en `gewijzigde_oers`
    (consument) MOETEN beide hierlangs, anders matchen ongewijzigde documenten nooit.
    """
    return hashlib.sha256(" ".join(tekst.split()).encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Schrijf de falende ingest-test**

Voeg toe aan `tests/test_ingest.py` (gebruikt de bestaande `conn`-fixture + `tmp_path`-patroon; kijk naar `test_verwerk_bestand_*` voor de exacte opzet van een instelling + OER-map):

```python
def test_verwerk_bestand_slaat_content_hash_op(conn, tmp_path, monkeypatch):
    """Na ingest heeft de OER-rij de hash van de geëxtraheerde tekst."""
    from validatie_samenwijzer import ingest
    from validatie_samenwijzer.db import voeg_instelling_toe
    from validatie_samenwijzer.oer_catalogus import bereken_content_hash

    voeg_instelling_toe(conn, "deltion", "Deltion")
    map_ = tmp_path / "deltion_oeren"
    map_.mkdir()
    tekst = "Kerntaak B1-K1 Bereidt gerechten voor. Crebo 25180."
    bestand = map_ / "25180_BOL_2025__studiegids.md"
    bestand.write_text(tekst, encoding="utf-8")
    monkeypatch.setenv("OEREN_PAD", str(tmp_path))

    ingest._verwerk_bestand(bestand, "deltion", conn)

    rij = conn.execute(
        "SELECT content_hash FROM oer_documenten WHERE crebo='25180'"
    ).fetchone()
    assert rij["content_hash"] == bereken_content_hash(tekst)
```

> **Let op:** de exacte bestandsnaam-conventie (`<crebo>_<leerweg>_<cohort>__…`) en of `_resolveer_oer` een instelling/map vereist, leid je af uit de bestaande `test_verwerk_bestand_*`-tests in `tests/test_ingest.py`. Pas de fixture-opzet daarop aan; de assertie op `content_hash` blijft gelijk.

- [ ] **Step 5: Draai de test, verifieer dat hij faalt**

Run: `uv run python -m pytest tests/test_ingest.py -q -k content_hash`
Expected: FAIL — `content_hash` is `None` (nog niet opgeslagen).

- [ ] **Step 6: Sla de hash op in `_verwerk_bestand`**

In `src/validatie_samenwijzer/ingest.py`, breid de lokale import in `_verwerk_bestand` (`:459-463`) uit:

```python
    from validatie_samenwijzer.db import (
        markeer_geindexeerd,
        set_oer_content_hash,
        update_oer_bestandspad,
        voeg_kerntaak_toe,
    )
    from validatie_samenwijzer.oer_catalogus import bereken_content_hash
```

Vervang het einde van de functie (`:535-536`):

```python
    set_oer_content_hash(conn, oer_id, bereken_content_hash(tekst))
    markeer_geindexeerd(conn, oer_id)
    log.info("'%s' geïndexeerd: %d kerntaken.", pad.name, len(kerntaken))
```

- [ ] **Step 7: Sla de hash op in `_verwerk_instelling_documenten`**

In `src/validatie_samenwijzer/ingest.py`, breid de lokale import (`:577-582`) uit met `set_instelling_document_content_hash`, en voeg `from validatie_samenwijzer.oer_catalogus import bereken_content_hash` toe. Vervang de lus-body (`:597-610`) zodat na conversie de tekst wordt geëxtraheerd, gehasht en opgeslagen:

```python
        if reset and bestand.suffix.lower() == ".pdf":
            md_pad = bestand.with_suffix(".md")
            if md_pad.exists():
                md_pad.unlink()
        converteer_naar_markdown(bestand)
        md_pad = bestand.with_suffix(".md")
        verwerk_pad = md_pad if md_pad.exists() else bestand
        try:
            tekst = extraheer_tekst(verwerk_pad)
        except Exception as e:
            log.error("Extractie mislukt voor '%s': %s", bestand.name, e)
            tekst = ""
        titel = f"{INSTELLING_SOORTEN[soort]} {inst['display_naam']}"
        doc_id = voeg_instelling_document_toe(
            conn,
            instelling_id=inst["id"],
            soort=soort,
            titel=titel,
            bestandspad=_pad_relatief_aan_oeren_root(bestand),
        )
        set_instelling_document_content_hash(conn, doc_id, bereken_content_hash(tekst))
        markeer_instelling_document_geindexeerd(conn, doc_id)
```

- [ ] **Step 8: Draai de tests, verifieer dat ze slagen**

Run: `uv run python -m pytest tests/test_ingest.py tests/test_oer_catalogus.py -q`
Expected: PASS.

- [ ] **Step 9: Lint + commit**

```bash
uv run ruff check src/validatie_samenwijzer/oer_catalogus.py src/validatie_samenwijzer/ingest.py tests/test_ingest.py tests/test_oer_catalogus.py
git add src/validatie_samenwijzer/oer_catalogus.py src/validatie_samenwijzer/ingest.py tests/test_ingest.py tests/test_oer_catalogus.py
git commit -m "feat(validatie): bereken_content_hash + opslaan bij OER- en instellingsdoc-ingest"
```

---

### Task 3: `uuid` op `CatalogusItem` + `gewijzigde_oers` (Deltion content-diff)

**Files:**
- Modify: `src/validatie_samenwijzer/oer_catalogus.py:46-56` (`CatalogusItem`), `:102-113` (`_items_naar_catalogus`), nieuwe `gewijzigde_oers` na `instelling_nieuwe_oers` (`:325`)
- Test: `tests/test_oer_catalogus.py`

**Interfaces:**
- Consumes: `bereken_content_hash` (Task 2), `db.get_alle_oers_met_instelling` (incl. nieuwe `content_hash`-kolom), `fetch_deltion._haal_studiegids_md`/`_record`/`_HEADERS`.
- Produces:
  - `CatalogusItem` krijgt optioneel veld `uuid: str | None = None` (laatste veld → bestaande 5-arg-constructies blijven werken).
  - `gewijzigde_oers(instelling: str, conn=None) -> tuple[list[CatalogusItem], int]` — (gewijzigde items, aantal-zonder-baseline). Niet-Deltion → `([], 0)`.

- [ ] **Step 1: Schrijf de falende tests**

Voeg toe aan `tests/test_oer_catalogus.py`:

```python
def test_catalogusitem_uuid_default_none():
    # Bestaande 5-arg-constructie (de niet-Deltion-parsers) blijft werken.
    item = CatalogusItem("25180", "BOL", "2025", "Kok", "deltion")
    assert item.uuid is None
    assert CatalogusItem("25180", "BOL", "2025", "Kok", "deltion", "u-1").uuid == "u-1"


def test_gewijzigde_oers_niet_deltion_is_leeg():
    items, zonder_baseline = oer_catalogus.gewijzigde_oers("aeres", conn=None)
    assert items == [] and zonder_baseline == 0


def test_gewijzigde_oers_detecteert_andere_upstream_hash(monkeypatch):
    """Een Deltion-OER die we hebben, met afwijkende upstream-content, telt als gewijzigd;
    een rij zonder baseline telt als zonder_baseline en wordt niet gefetcht."""
    import sqlite3

    from validatie_samenwijzer.db import (
        init_db,
        set_oer_content_hash,
        voeg_instelling_toe,
        voeg_oer_document_toe,
    )
    from validatie_samenwijzer.oer_catalogus import CatalogusItem, bereken_content_hash

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    inst = voeg_instelling_toe(conn, "deltion", "Deltion")
    # OER A: baseline = hash van "oud" → upstream "nieuw" → gewijzigd.
    a = voeg_oer_document_toe(conn, inst, "Kok", "25180", "2025", "BOL", "a.md")
    set_oer_content_hash(conn, a, bereken_content_hash("oud"))
    # OER B: geen baseline (NULL) → zonder_baseline, geen fetch.
    voeg_oer_document_toe(conn, inst, "Bakker", "25181", "2025", "BOL", "b.md")

    monkeypatch.setattr(
        oer_catalogus,
        "deltion_catalogus",
        lambda: [
            CatalogusItem("25180", "BOL", "2025", "Kok", "deltion", "uuid-a"),
            CatalogusItem("25181", "BOL", "2025", "Bakker", "deltion", "uuid-b"),
        ],
    )
    monkeypatch.setitem(oer_catalogus._CATALOGUS_BRONNEN, "deltion", oer_catalogus.deltion_catalogus)

    class _FakeFD:
        _HEADERS = {}

        def _haal_studiegids_md(self, client, uuid):
            return "nieuw"  # afwijkend van baseline "oud"

    monkeypatch.setattr(oer_catalogus, "_fetch_deltion", lambda: _FakeFD())
    monkeypatch.setattr(oer_catalogus.httpx, "Client", lambda **kw: _NullClient())

    items, zonder_baseline = oer_catalogus.gewijzigde_oers("deltion", conn=conn)
    assert [i.crebo for i in items] == ["25180"]
    assert zonder_baseline == 1
    conn.close()


class _NullClient:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False
```

> **Let op:** `_FakeFD._haal_studiegids_md(self, client, uuid)` negeert `client` (de `_NullClient`); de echte versie doet de HTTP-call. Het contract dat we testen is uitsluitend: gematcht-tuple + baseline aanwezig + afwijkende hash → gewijzigd; baseline `NULL` → zonder_baseline zonder fetch.

- [ ] **Step 2: Draai de tests, verifieer dat ze falen**

Run: `uv run python -m pytest tests/test_oer_catalogus.py -q -k "uuid or gewijzigde"`
Expected: FAIL — `CatalogusItem` heeft geen `uuid`; `gewijzigde_oers` niet gedefinieerd.

- [ ] **Step 3: Voeg `uuid` toe aan `CatalogusItem`**

In `src/validatie_samenwijzer/oer_catalogus.py`, vervang de dataclass (`:46-56`):

```python
@dataclass(frozen=True)
class CatalogusItem:
    crebo: str
    leerweg: str
    cohort: str
    naam: str
    instelling: str
    uuid: str | None = None  # alleen Deltion levert 'm; nodig voor de content-refetch

    @property
    def sleutel(self) -> tuple[str, str, str]:
        return (self.crebo, self.leerweg, self.cohort)
```

- [ ] **Step 4: Geef de uuid door in `_items_naar_catalogus`**

Vervang de append in `_items_naar_catalogus` (`:106-112`):

```python
    for raw in raw_items:
        rec = parse(raw)
        if rec:
            uit.append(
                CatalogusItem(
                    rec["crebo"],
                    rec["leerweg"],
                    rec["cohort"],
                    rec["naam"],
                    instelling,
                    rec.get("uuid"),
                )
            )
```

- [ ] **Step 5: Implementeer `gewijzigde_oers`**

Na `instelling_nieuwe_oers` (`:325`):

```python
def gewijzigde_oers(instelling: str, conn=None) -> tuple[list[CatalogusItem], int]:
    """OER's die wij hebben én die upstream inhoudelijk zijn gewijzigd (Deltion-only).

    Matcht elk catalogus-item op zijn diff-sleutel tegen onze DB-rijen. Voor een match
    met een opgeslagen `content_hash` wordt de upstream-content gerefetcht
    (`/reports/<uuid>/html`) en via `bereken_content_hash` vergeleken. Returnt
    ``(gewijzigde_items, aantal_zonder_baseline)``. Een rij met `content_hash IS NULL`
    telt als zonder-baseline (niet gefetcht). Niet-Deltion-instellingen → ``([], 0)``
    omdat ze geen per-OER content-endpoint hebben.

    Raises:
        CatalogusOnbereikbaarError: bij een netwerk-/API-fout op de catalogus-call.
    """
    if instelling != "deltion":
        return [], 0
    try:
        catalogus = deltion_catalogus()
    except httpx.HTTPError as e:
        raise CatalogusOnbereikbaarError(f"{instelling}: {e}") from e
    velden = _DIFF_SLEUTEL_VELDEN.get(instelling, _STANDAARD_VELDEN)
    eigen = conn or open_conn()
    try:
        rows = db.get_alle_oers_met_instelling(eigen)
    finally:
        if conn is None:
            eigen.close()
    hash_per_sleutel = {
        _projecteer(r["crebo"], r["leerweg"], r["cohort"], velden): r["content_hash"]
        for r in rows
        if r["naam"] == instelling
    }
    gewijzigd: list[CatalogusItem] = []
    zonder_baseline = 0
    fd = _fetch_deltion()
    with httpx.Client(headers=fd._HEADERS, timeout=30) as client:
        for item in catalogus:
            sleutel = _projecteer(item.crebo, item.leerweg, item.cohort, velden)
            if sleutel not in hash_per_sleutel:
                continue  # nieuwe OER → telt onder nieuwe_oers, niet hier
            opgeslagen = hash_per_sleutel[sleutel]
            if not opgeslagen:
                zonder_baseline += 1
                continue
            if not item.uuid:
                continue
            try:
                md = fd._haal_studiegids_md(client, item.uuid)
            except httpx.HTTPError:
                continue  # sla een kapotte refetch over, niet de hele check
            if bereken_content_hash(md) != opgeslagen:
                gewijzigd.append(item)
    return gewijzigd, zonder_baseline
```

- [ ] **Step 6: Draai de tests, verifieer dat ze slagen**

Run: `uv run python -m pytest tests/test_oer_catalogus.py -q`
Expected: PASS.

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check src/validatie_samenwijzer/oer_catalogus.py tests/test_oer_catalogus.py
git add src/validatie_samenwijzer/oer_catalogus.py tests/test_oer_catalogus.py
git commit -m "feat(validatie): gewijzigde_oers — Deltion content-hash-diff (uuid op CatalogusItem)"
```

---

### Task 4: `--oer-inhoud`-flag in `bron_updates` + live verificatie

**Files:**
- Modify: `src/validatie_samenwijzer/bron_updates.py:102-181` (`_oer_inhoud_status`, `verzamel_bron_status`, `main`)
- Test: `tests/test_bron_updates.py`

**Interfaces:**
- Consumes: `oer_catalogus.gewijzigde_oers`, `oer_catalogus._CATALOGUS_BRONNEN`, `oer_catalogus.open_conn`, `oer_catalogus.CatalogusOnbereikbaarError` (Task 3).
- Produces: `_oer_inhoud_status() -> BronStatus` (bron `"oer-inhoud"`); `verzamel_bron_status(online=False, inhoud=False)`; `--oer-inhoud`-flag in `main`.

- [ ] **Step 1: Schrijf de falende test**

Voeg toe aan `tests/test_bron_updates.py`:

```python
def test_oer_inhoud_status_aggregeert_gewijzigde_oers(monkeypatch):
    from validatie_samenwijzer.oer_catalogus import CatalogusItem

    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(bron_updates.oer_catalogus, "open_conn", lambda: _Conn())
    monkeypatch.setattr(
        bron_updates.oer_catalogus, "_CATALOGUS_BRONNEN", {"deltion": lambda: []}
    )

    def _fake_gewijzigd(inst, conn=None):
        return ([CatalogusItem("25180", "BOL", "2025", "Kok", "deltion", "u")], 2)

    monkeypatch.setattr(bron_updates.oer_catalogus, "gewijzigde_oers", _fake_gewijzigd)

    status = bron_updates._oer_inhoud_status()
    assert status.bron == "oer-inhoud"
    assert status.automatisch is True
    assert "1" in status.signaal and "deltion" in status.signaal
    assert status.details["gewijzigd_per_instelling"]["deltion"] == [("25180", "BOL", "2025")]
    assert status.details["zonder_baseline"] == 2


def test_verzamel_bron_status_voegt_inhoud_toe_met_flag(monkeypatch, gemockte_bronnen):
    bronnen = {s.bron for s in bron_updates.verzamel_bron_status(inhoud=False)}
    assert "oer-inhoud" not in bronnen  # standaard niet
    monkeypatch.setattr(
        bron_updates.oer_catalogus, "_CATALOGUS_BRONNEN", {"deltion": lambda: []}
    )
    monkeypatch.setattr(bron_updates.oer_catalogus, "open_conn", lambda: type("C", (), {"close": lambda s: None})())
    monkeypatch.setattr(bron_updates.oer_catalogus, "gewijzigde_oers", lambda i, conn=None: ([], 0))
    bronnen2 = {s.bron for s in bron_updates.verzamel_bron_status(inhoud=True)}
    assert "oer-inhoud" in bronnen2
```

> **Let op:** `gemockte_bronnen` is de bestaande fixture in `tests/test_bron_updates.py` die de skills/kd-bronnen mockt; hergebruik 'm. Verifieer de naam in dat bestand voor je begint.

- [ ] **Step 2: Draai de tests, verifieer dat ze falen**

Run: `uv run python -m pytest tests/test_bron_updates.py -q -k "inhoud"`
Expected: FAIL — `_oer_inhoud_status` bestaat niet; `verzamel_bron_status` mist `inhoud`.

- [ ] **Step 3: Implementeer `_oer_inhoud_status`**

In `src/validatie_samenwijzer/bron_updates.py`, na `_oer_status` (`:147`):

```python
def _oer_inhoud_status() -> BronStatus:
    """Content-wijzigingscheck: bestaande OER's die upstream zijn herzien (Deltion-only).

    Duur (één refetch per gematcht document) → eigen flag (--oer-inhoud). Instellingen
    zonder per-OER content-endpoint leveren ([], 0) en worden als 'niet gecheckt'
    gerapporteerd, niet als 'ongewijzigd'.
    """
    gewijzigd: dict[str, list] = {}
    onbereikbaar: list[str] = []
    zonder_baseline = 0
    conn = oer_catalogus.open_conn()
    try:
        for inst in sorted(oer_catalogus._CATALOGUS_BRONNEN):
            try:
                items, nb = oer_catalogus.gewijzigde_oers(inst, conn=conn)
            except oer_catalogus.CatalogusOnbereikbaarError as e:
                logger.warning("OER-inhoudcheck overgeslagen (%s)", e)
                onbereikbaar.append(inst)
                continue
            zonder_baseline += nb
            if items:
                gewijzigd[inst] = items
    finally:
        conn.close()
    n_totaal = sum(len(v) for v in gewijzigd.values())
    gecheckt = sorted(set(oer_catalogus._CATALOGUS_BRONNEN) - set(onbereikbaar))
    niet_gecheckt = sorted(set(_OER_CRAWLBAAR) - {"deltion"})
    if n_totaal:
        per = ", ".join(f"{i}: {len(v)}" for i, v in sorted(gewijzigd.items()))
        kop = f"{n_totaal} herziene OER('s) ({per})"
    else:
        kop = "geen herziene OER's via content-check"
    delen = [kop]
    if zonder_baseline:
        delen.append(f"{zonder_baseline} zonder baseline (her-ingest legt 'm vast)")
    delen.append(f"{len(niet_gecheckt)} instelling(en) niet gecheckt (geen content-endpoint)")
    return BronStatus(
        "oer-inhoud",
        automatisch=True,
        signaal="; ".join(delen),
        details={
            "gewijzigd_per_instelling": {i: [it.sleutel for it in v] for i, v in gewijzigd.items()},
            "zonder_baseline": zonder_baseline,
            "onbereikbaar": onbereikbaar,
            "gecheckt": gecheckt,
            "niet_gecheckt": niet_gecheckt,
        },
    )
```

- [ ] **Step 4: Plumb de flag door `verzamel_bron_status` + `main`**

Vervang `verzamel_bron_status` (`:150-151`):

```python
def verzamel_bron_status(online: bool = False, inhoud: bool = False) -> list[BronStatus]:
    statussen = [_skills_status(), _kd_status(), _oer_status(online=online)]
    if inhoud:
        statussen.append(_oer_inhoud_status())
    return statussen
```

In `main` (`:165-172`), voeg de flag toe en geef 'm door:

```python
    parser.add_argument(
        "--oer", action="store_true", help="Draai ook de online OER-catalogus-check (netwerk)"
    )
    parser.add_argument(
        "--oer-inhoud",
        action="store_true",
        help="Draai ook de content-wijzigingscheck (duur: refetch per Deltion-OER)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        statussen = verzamel_bron_status(online=args.oer, inhoud=args.oer_inhoud)
```

- [ ] **Step 5: Draai de tests, verifieer dat ze slagen**

Run: `uv run python -m pytest tests/test_bron_updates.py -q`
Expected: PASS.

- [ ] **Step 6: Live verificatie tegen de echte Deltion-API + DB**

Eerst een baseline leggen voor Deltion (anders is alles "zonder baseline"):

```bash
uv run python -m validatie_samenwijzer.ingest --instelling deltion --reset
uv run check-bron-updates --oer-inhoud
```

Expected: de regel `[auto     ] oer-inhoud — …` toont `geen herziene OER's via content-check` (direct na her-ingest, want baseline == upstream) of een aantal herziene OER's als upstream sinds de laatste ingest is gewijzigd; `zonder baseline` ≈ 0 voor Deltion na de `--reset`-ingest; `niet gecheckt` = de overige crawlbare instellingen. Zonder `--oer-inhoud` verschijnt de regel niet.

- [ ] **Step 7: Volledige suite + lint + commit**

```bash
uv run python -m pytest -q
uv run ruff check src/ scripts/ tests/
git add src/validatie_samenwijzer/bron_updates.py tests/test_bron_updates.py
git commit -m "feat(validatie): --oer-inhoud draait de content-wijzigingscheck (Deltion)"
```

---

## Self-Review

**Spec-dekking.** Design-sectie "3b — `content_hash`-register + content-wijzigingsdetectie" uit het Fase 3-plan:
- "`content_hash` toevoegen aan `oer_documenten` + `instelling_documenten`" → Task 1 (ADD COLUMN + setters).
- "Migratie idempotent, geguard met `pragma table_info`" → Task 1, Step 3 (`_kolom_bestaat`). De advisor-correctie (géén DROP) is expliciet in Global Constraints + getest in `test_init_db_migratie_is_idempotent_en_behoudt_data`.
- "ingest berekent SHA256 van de bronbytes" → Task 2 (één `bereken_content_hash`, beide ingest-paden).
- "content-wijzigingscheck fetcht per bekende OER de bron en vergelijkt de hash; duur → eigen flag" → Task 3 (`gewijzigde_oers`, Deltion-only) + Task 4 (`--oer-inhoud`).
- Advisor-eisen: identieke hash beide kanten (Task 2, gedeelde helper); uuid die `CatalogusItem` eerst weggooide (Task 3, Step 3-4); Deltion-only + "niet gecheckt" i.p.v. "ongewijzigd" (Task 4, `niet_gecheckt`); baseline-semantiek (Task 3/4, `zonder_baseline`).

**Placeholder-scan.** Alle code-stappen bevatten volledige code. Twee "Let op"-blokken verwijzen naar bestaande test-fixtures (`test_verwerk_bestand_*`, `gemockte_bronnen`) die de implementer in het testbestand moet verifiëren — dat is een bewuste lees-instructie, geen weggelaten code.

**Type-consistentie.** `bereken_content_hash(tekst: str) -> str` overal identiek aangeroepen (ingest ×2, `gewijzigde_oers`). `CatalogusItem(... , uuid=None)` als laatste veld houdt de 5-arg-constructies in de niet-Deltion-parsers geldig. `gewijzigde_oers(instelling, conn=None) -> tuple[list[CatalogusItem], int]` matcht de mock in `test_oer_inhoud_status_aggregeert_gewijzigde_oers` en de aanroep in `_oer_inhoud_status`. `set_oer_content_hash`/`set_instelling_document_content_hash` matchen hun aanroepen in `ingest`.
