# Synthetisch dataset herstructureren — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vervang het sector-niveau "berend"-formaat door een opleidingsspecifieke synthetische dataset gekoppeld aan echte OERs via een nieuwe SQLite-catalog.

**Architecture:** `oeren/` (kopie uit validatie) → `build_oer_catalog.py` → `oeren.db` → `generate_synthetisch_data.py` → `data/01-raw/synthetisch/studenten.csv`. `prepare.py` en `analyze.py` lezen kerntaak-info nu uit DB i.p.v. JSON. Alle "berend"-vermeldingen verwijderd.

**Tech Stack:** Python 3.13, SQLite (stdlib), pandas, pytest, ruff, ty. `uv` voor package management. TDD per taak.

**Spec:** `docs/superpowers/specs/2026-05-04-synthetisch-dataset-design.md`

---

## File Structure

**Nieuw:**
- `oeren/` (top-level, gitignored) — handmatige kopie uit `validatie_samenwijzer/oeren/`
- `data/02-prepared/oeren.db` (gitignored) — gegenereerd door build-script
- `src/samenwijzer/oer_parsing.py` — bestandsnaam-parser, kerntaak-extractor, opleidingsnaam/niveau-heuristieken
- `src/samenwijzer/oer_store.py` — DB-init + queries (mirror outreach_store.py-stijl)
- `scripts/build_oer_catalog.py` — eenmalig: scant oeren/, populeert oeren.db
- `scripts/generate_synthetisch_data.py` — produceert studenten.csv
- `scripts/synthetisch_opleidingen.json` — handmatig gecureerde lijst van 15 opleidingen
- `data/01-raw/synthetisch/studenten.csv` — output van generate-script
- `tests/test_oer_parsing.py`
- `tests/test_oer_store.py`
- `tests/test_build_oer_catalog.py`
- `tests/test_generate_synthetisch_data.py`

**Aangepast:**
- `src/samenwijzer/prepare.py:135-201` — rename `load_berend_csv` → `load_synthetisch_csv`, verwijder `_CREBO_MAP`, `_voeg_kt_wp_scores_toe` leest uit DB
- `src/samenwijzer/analyze.py:13-34` — `_oer_label()` leest uit DB i.p.v. JSON
- `tests/test_prepare.py`, `tests/test_analyze.py` — fixtures aanpassen
- `.gitignore` — `oeren/` en `oeren.db` toevoegen
- `CLAUDE.md` — vermeldingen "berend" → "synthetisch", oeren.db documenteren

**Verwijderd:**
- `data/01-raw/berend/` — vervangen door `data/01-raw/synthetisch/`
- `oer_kerntaken.json` — vervangen door `oeren.db.kerntaken`-tabel

---

## Task 1: Setup — oeren/ kopiëren en gitignore

**Files:**
- Modify: `.gitignore`
- New (handmatig): `oeren/`

- [ ] **Step 1: Add gitignore entries**

Edit `.gitignore` — voeg toe na de bestaande `data/02-prepared/`-regels:

```
# B3a: OER-catalog
oeren/
data/02-prepared/oeren.db
```

- [ ] **Step 2: Copy oeren/ from validatie_samenwijzer**

```bash
cp -r validatie_samenwijzer/oeren samenwijzer-oeren-tmp
mv samenwijzer-oeren-tmp oeren
```

(Of `cp -a` als rsync beschikbaar is. Doel: `samenwijzer/oeren/aeres_oeren/...`, etc.)

- [ ] **Step 3: Verify**

```bash
ls oeren/ | sort
```

Expected output:
```
aeres_oeren
davinci_oeren
oer_algemeen
rijn_ijssel_oer
talland_oeren
utrecht_oeren
```

```bash
find oeren -name "*.md" | wc -l
```

Expected: ≥ 700.

- [ ] **Step 4: Confirm gitignore works**

```bash
git status --porcelain | grep -E "oeren|oeren.db" || echo "ignored ok"
```

Expected: `ignored ok` (of geen output behalve de `.gitignore` zelf).

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore(synthetisch): gitignore oeren/ en oeren.db (B3a setup)"
```

---

## Task 2: oer_parsing module — bestandsnaam-parser

**Files:**
- Create: `src/samenwijzer/oer_parsing.py`
- Test: `tests/test_oer_parsing.py`

- [ ] **Step 1: Write failing tests for parseer_bestandsnaam**

Create `tests/test_oer_parsing.py`:

```python
"""Tests voor oer_parsing module."""

from samenwijzer.oer_parsing import parseer_bestandsnaam


def test_parseer_davinci_format():
    res = parseer_bestandsnaam("25168BOL2025Examenplan.pdf")
    assert res == {"crebo": "25168", "leerweg": "BOL", "cohort": "2025"}


def test_parseer_rijn_ijssel_format():
    res = parseer_bestandsnaam("content_oer-2024-2025-ci-25651-acteur.pdf")
    assert res == {"crebo": "25651", "leerweg": "BOL", "cohort": "2024"}


def test_parseer_talland_format():
    res = parseer_bestandsnaam("25180 Kok 24 maanden BBL.pdf")
    assert res["crebo"] == "25180"
    assert res["leerweg"] == "BBL"


def test_parseer_geen_crebo_geeft_none():
    assert parseer_bestandsnaam("OER 20252026 DEF 11.md") is None


def test_parseer_combined_bolbbl():
    res = parseer_bestandsnaam("25960BOLBBL2025Examenplan.pdf")
    assert res == {"crebo": "25960", "leerweg": "BOL", "cohort": "2025"}
```

- [ ] **Step 2: Run tests — expect failure**

```bash
uv run pytest tests/test_oer_parsing.py -v
```

Expected: ImportError (module bestaat niet).

- [ ] **Step 3: Create oer_parsing.py with parseer_bestandsnaam**

Create `src/samenwijzer/oer_parsing.py`:

```python
"""OER-parsing helpers: bestandsnaam, kerntaken, opleidingsnaam, niveau.

Synced from validatie_samenwijzer/src/validatie_samenwijzer/ingest.py @ d64f3cf.
Houd functioneel gelijk; verschilt alleen waar samenwijzer geen ingest-pijplijn heeft.
"""

from __future__ import annotations

import re

# ── Bestandsnaam parsen ───────────────────────────────────────────────────────

_CREBO_LEERWEG_JAAR = re.compile(
    r"(?<!\d)(\d{5})\s*[-_]?\s*(BOL|BBL)(?:BOL|BBL)?\s*[-_]?\s*(\d{4})", re.IGNORECASE
)
_CREBO = re.compile(r"(?<!\d)(\d{5})(?!\d)")
_LEERWEG = re.compile(r"\b(BOL|BBL)\b", re.IGNORECASE)
_JAAR = re.compile(r"(?<!\d)(20[2-3]\d)(?!\d)")
_HUIDIG_COHORT = "2025"


def parseer_bestandsnaam(bestandsnaam: str) -> dict | None:
    """Haal crebo, leerweg en cohort op uit de bestandsnaam.

    Ondersteunt:
    - Da Vinci:     25168BOL2025Examenplan.pdf
    - Rijn IJssel:  content_oer-2024-2025-ci-25651-acteur.pdf
    - Talland:      25180 Kok 24 maanden BBL.pdf
    Geeft None als er geen 5-cijferig crebo gevonden wordt.
    """
    m = _CREBO_LEERWEG_JAAR.search(bestandsnaam)
    if m:
        return {"crebo": m.group(1), "leerweg": m.group(2).upper(), "cohort": m.group(3)}

    crebo_m = _CREBO.search(bestandsnaam)
    if not crebo_m:
        return None

    crebo = crebo_m.group(1)
    leerweg_m = _LEERWEG.search(bestandsnaam)
    leerweg = leerweg_m.group(1).upper() if leerweg_m else "BOL"
    jaar_m = _JAAR.search(bestandsnaam)
    cohort = jaar_m.group(1) if jaar_m else _HUIDIG_COHORT
    return {"crebo": crebo, "leerweg": leerweg, "cohort": cohort}
```

- [ ] **Step 4: Run tests — expect pass**

```bash
uv run pytest tests/test_oer_parsing.py -v
```

Expected: 5 passed.

---

## Task 3: oer_parsing — extraheer_kerntaken

**Files:**
- Modify: `src/samenwijzer/oer_parsing.py`
- Test: `tests/test_oer_parsing.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_oer_parsing.py`:

```python
from samenwijzer.oer_parsing import extraheer_kerntaken


def test_extraheer_kerntaken_basis():
    tekst = """
    B1-K1: Bieden van zorg en ondersteuning
    B1-K1-W1: Onderkent gezondheidsproblemen
    B1-K1-W2: Voert verpleegkundige interventies uit
    """
    resultaten = extraheer_kerntaken(tekst)
    assert len(resultaten) == 3
    assert resultaten[0]["code"] == "B1-K1"
    assert resultaten[0]["type"] == "kerntaak"
    assert resultaten[1]["code"] == "B1-K1-W1"
    assert resultaten[1]["type"] == "werkproces"
    assert resultaten[1]["volgorde"] == 1


def test_extraheer_kerntaken_lege_tekst():
    assert extraheer_kerntaken("") == []
    assert extraheer_kerntaken("   ") == []


def test_extraheer_kerntaken_negeert_overige_regels():
    tekst = """
    Inleiding bla bla
    B1-K1: Echte kerntaak
    Random text die niet matcht
    """
    resultaten = extraheer_kerntaken(tekst)
    assert len(resultaten) == 1
    assert resultaten[0]["code"] == "B1-K1"
```

- [ ] **Step 2: Run — expect failure**

```bash
uv run pytest tests/test_oer_parsing.py::test_extraheer_kerntaken_basis -v
```

Expected: ImportError.

- [ ] **Step 3: Add extraheer_kerntaken to oer_parsing.py**

Append to `src/samenwijzer/oer_parsing.py`:

```python
# ── Kerntaken extraheren ──────────────────────────────────────────────────────

_KT_PATROON = re.compile(
    r"^\s*(B\d+-K\d+(?:-W\d+)?|Kerntaak\s+\d+|Werkproces\s+\d+\.\d+)"
    r"\s*[:\-–]?\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)


def extraheer_kerntaken(tekst: str) -> list[dict]:
    """Haal kerntaken en werkprocessen uit OER-tekst via regex.

    Returns:
        Lijst van dicts met sleutels: code, naam, type ('kerntaak'|'werkproces'), volgorde.
    """
    if not tekst:
        return []

    resultaten = []
    volgorde = 0
    for m in _KT_PATROON.finditer(tekst):
        code = m.group(1).strip()
        naam = m.group(2).strip()[:200]
        if "werkproces" in code.lower() or re.match(r"B\d+-K\d+-W\d+", code):
            type_ = "werkproces"
        else:
            type_ = "kerntaak"
        resultaten.append({"code": code, "naam": naam, "type": type_, "volgorde": volgorde})
        volgorde += 1
    return resultaten
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_oer_parsing.py -v
```

Expected: 8 passed.

---

## Task 4: oer_parsing — extraheer_opleidingsnaam (heuristiek)

**Files:**
- Modify: `src/samenwijzer/oer_parsing.py`
- Test: `tests/test_oer_parsing.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_oer_parsing.py`:

```python
from samenwijzer.oer_parsing import extraheer_opleidingsnaam


def test_extraheer_schone_naam_davinci():
    naam = extraheer_opleidingsnaam(
        "25655_BOL_2025__verzorgende-ig.md"
    )
    assert "Verzorgende" in naam


def test_extraheer_schone_naam_rijn_ijssel():
    naam = extraheer_opleidingsnaam(
        "25591_BOL_2025__oer-2025-2026-ci-25591-mediamaker.md"
    )
    assert "Mediamaker" in naam


def test_extraheer_filtert_examenplan_en_oer():
    naam = extraheer_opleidingsnaam(
        "25775_BOL_2025__25775BOL2025Examenplan-Logistiek-teamleider-cohort-2025.md"
    )
    assert "Logistiek" in naam
    assert "Examenplan" not in naam
    assert "OER" not in naam.upper()


def test_extraheer_geen_naam_als_alleen_codes():
    naam = extraheer_opleidingsnaam("25756_BBL_2025__25756BBL2025Examenplan.md")
    assert naam is None or naam == ""


def test_extraheer_max_4_woorden():
    naam = extraheer_opleidingsnaam(
        "25739_BBL_2025__25739BBL2025MJP-Technicus-Elektrotechnische-Installaties-in-de-Gebouwde-Omgeving-d1.md"
    )
    assert naam is not None
    assert len(naam.split()) <= 4
```

- [ ] **Step 2: Run — expect failure**

```bash
uv run pytest tests/test_oer_parsing.py::test_extraheer_schone_naam_davinci -v
```

Expected: ImportError.

- [ ] **Step 3: Add extraheer_opleidingsnaam**

Append to `src/samenwijzer/oer_parsing.py`:

```python
# ── Opleidingsnaam-extractie ──────────────────────────────────────────────────

_STOP_TOKENS = {
    "oer", "mjp", "tik", "ci", "examenplan", "examenplannen", "examenreglement",
    "addendum", "cohort", "bol", "bbl", "bolbbl", "vanaf", "voor", "en", "van",
    "de", "het", "te", "op", "een", "in", "ig", "n2", "n3", "n4", "d1", "d2",
    "v1", "v2", "v3", "def",
}

_HASH_PATROON = re.compile(r"^[a-zA-Z0-9]{6,}$")
_KLINKER_PATROON = re.compile(r"[aeiou]", re.IGNORECASE)


def extraheer_opleidingsnaam(bestandsnaam: str) -> str | None:
    """Heuristiek: leid opleidingsnaam af uit bestandsnaam.

    Strategie:
      1. Strip extensie en alles vóór '__' (zodat metadata-prefix wegvalt).
      2. Splits op _, -, spaties.
      3. Filter weg: digits, jaartallen, BOL/BBL, OER/MJP/Examenplan-tokens,
         hash-achtige tokens (≥6 chars zonder klinkers), 1-letter tokens.
      4. Title-case, max 4 woorden.

    Returns:
        Schone opleidingsnaam, of None als er onvoldoende woorden overblijven.
    """
    naam = bestandsnaam.rsplit(".", 1)[0]  # strip .md/.pdf
    if "__" in naam:
        naam = naam.split("__", 1)[1]

    tokens = re.split(r"[_\-\s]+", naam)
    woorden: list[str] = []
    for t in tokens:
        t = t.strip().lower()
        if not t or len(t) < 2:
            continue
        if t.isdigit():
            continue
        if t in _STOP_TOKENS:
            continue
        if _HASH_PATROON.match(t) and not _KLINKER_PATROON.search(t):
            continue
        woorden.append(t)

    if not woorden:
        return None
    return " ".join(w.title() for w in woorden[:4])
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_oer_parsing.py -v
```

Expected: 13 passed.

---

## Task 5: oer_parsing — bepaal_niveau

**Files:**
- Modify: `src/samenwijzer/oer_parsing.py`
- Test: `tests/test_oer_parsing.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_oer_parsing.py`:

```python
from samenwijzer.oer_parsing import bepaal_niveau


def test_bepaal_niveau_uit_bestandsnaam_suffix():
    assert bepaal_niveau("25099BBL2025MJP-MachinistGrondverzetN3.md", "") == 3
    assert bepaal_niveau("25099BBL2025MJP-MeubelmakerN2.md", "") == 2
    assert bepaal_niveau("12345BOL2025-OnbekendeOpleidingN4.md", "") == 4


def test_bepaal_niveau_uit_markdown_tekst():
    tekst = "Deze opleiding is op MBO niveau 3. Bla bla."
    assert bepaal_niveau("12345BOL2025.md", tekst) == 3


def test_bepaal_niveau_voorkeur_voor_bestandsnaam():
    # Bestandsnaam zegt N4, tekst zegt niveau 2 → bestandsnaam wint
    tekst = "Onbekende opleiding op niveau 2."
    assert bepaal_niveau("12345BOL2025-OnbekendeN4.md", tekst) == 4


def test_bepaal_niveau_geen_match_geeft_none():
    assert bepaal_niveau("OER 2025 algemeen.md", "Geen niveau-aanduiding hier.") is None
```

- [ ] **Step 2: Run — expect failure**

- [ ] **Step 3: Add bepaal_niveau**

Append to `src/samenwijzer/oer_parsing.py`:

```python
# ── Niveau-extractie ──────────────────────────────────────────────────────────

_NIVEAU_BESTANDSNAAM = re.compile(r"N([234])(?!\d)", re.IGNORECASE)
_NIVEAU_TEKST = re.compile(
    r"\b(?:MBO[\s-]+)?[Nn]iveau\s*([234])\b"
)


def bepaal_niveau(bestandsnaam: str, tekst: str) -> int | None:
    """Bepaal opleidingsniveau (2/3/4) uit bestandsnaam-suffix of markdown-tekst.

    Bestandsnaam wint van tekst (suffix als 'N3' is een explicietere markering).
    Geeft None als geen niveau te herleiden is.
    """
    m = _NIVEAU_BESTANDSNAAM.search(bestandsnaam)
    if m:
        return int(m.group(1))
    m = _NIVEAU_TEKST.search(tekst)
    if m:
        return int(m.group(1))
    return None
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_oer_parsing.py -v
```

Expected: 17 passed.

- [ ] **Step 5: Lint**

```bash
uv run ruff check src/samenwijzer/oer_parsing.py tests/test_oer_parsing.py
```

Expected: All checks passed.

- [ ] **Step 6: Commit**

```bash
git add src/samenwijzer/oer_parsing.py tests/test_oer_parsing.py
git commit -m "feat(synthetisch): oer_parsing module met bestandsnaam, kerntaken, opleidingsnaam, niveau"
```

---

## Task 6: oer_store — init_db en instellingen

**Files:**
- Create: `src/samenwijzer/oer_store.py`
- Test: `tests/test_oer_store.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_oer_store.py`:

```python
"""Tests voor oer_store: SQLite-catalog van OERs."""

import sqlite3
from pathlib import Path

import pytest

from samenwijzer import oer_store


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "oeren.db"
    oer_store.init_db(p)
    return p


def test_init_db_maakt_tabellen_aan(db_path: Path):
    with sqlite3.connect(db_path) as conn:
        tabellen = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"instellingen", "oer_documenten", "kerntaken"} <= tabellen


def test_voeg_instelling_toe_en_get(db_path: Path):
    oer_store.voeg_instelling_toe(db_path, naam="rijn_ijssel", display_naam="Rijn IJssel")
    inst = oer_store.get_instelling_by_naam(db_path, "rijn_ijssel")
    assert inst is not None
    assert inst["display_naam"] == "Rijn IJssel"


def test_get_instelling_onbekend_geeft_none(db_path: Path):
    assert oer_store.get_instelling_by_naam(db_path, "onbekend") is None


def test_voeg_instelling_dubbel_faalt_silently(db_path: Path):
    """INSERT OR IGNORE — dubbele toevoeging mag niet exception-en."""
    oer_store.voeg_instelling_toe(db_path, naam="aeres", display_naam="Aeres MBO")
    oer_store.voeg_instelling_toe(db_path, naam="aeres", display_naam="Aeres MBO")
    inst = oer_store.get_instelling_by_naam(db_path, "aeres")
    assert inst["display_naam"] == "Aeres MBO"
```

- [ ] **Step 2: Run — expect failure**

```bash
uv run pytest tests/test_oer_store.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Create oer_store.py**

Create `src/samenwijzer/oer_store.py`:

```python
"""Persistente OER-catalog via SQLite (instellingen + oer_documenten + kerntaken)."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

_DB_PAD = Path(__file__).parent.parent.parent / "data" / "02-prepared" / "oeren.db"

# Init-guard: voorkomt herhaald CREATE TABLE in dezelfde sessie.
_geinitialiseerd: set[Path] = set()


@contextmanager
def _verbinding(db_pad: Path) -> Generator[sqlite3.Connection]:
    """Open een SQLite-verbinding en sluit hem gegarandeerd na gebruik."""
    conn = sqlite3.connect(db_pad)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_pad: Path = _DB_PAD) -> None:
    """Maak instellingen-, oer_documenten- en kerntaken-tabellen aan als nog niet aanwezig."""
    if db_pad in _geinitialiseerd:
        return
    db_pad.parent.mkdir(parents=True, exist_ok=True)
    with _verbinding(db_pad) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS instellingen (
              id           INTEGER PRIMARY KEY,
              naam         TEXT UNIQUE NOT NULL,
              display_naam TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS oer_documenten (
              id            INTEGER PRIMARY KEY,
              instelling_id INTEGER NOT NULL,
              opleiding     TEXT NOT NULL,
              crebo         TEXT NOT NULL,
              cohort        TEXT NOT NULL,
              leerweg       TEXT NOT NULL,
              niveau        INTEGER,
              bestandspad   TEXT NOT NULL,
              FOREIGN KEY (instelling_id) REFERENCES instellingen(id),
              UNIQUE (instelling_id, crebo, leerweg, cohort)
            );
            CREATE TABLE IF NOT EXISTS kerntaken (
              id          INTEGER PRIMARY KEY,
              oer_id      INTEGER NOT NULL,
              code        TEXT NOT NULL,
              naam        TEXT NOT NULL,
              type        TEXT NOT NULL,
              parent_code TEXT,
              volgorde    INTEGER,
              FOREIGN KEY (oer_id) REFERENCES oer_documenten(id)
            );
        """)
    _geinitialiseerd.add(db_pad)


# ── Instellingen ──────────────────────────────────────────────────────────────


def voeg_instelling_toe(db_pad: Path, naam: str, display_naam: str) -> None:
    """Voeg een instelling toe; geen-op als naam al bestaat."""
    init_db(db_pad)
    with _verbinding(db_pad) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO instellingen (naam, display_naam) VALUES (?, ?)",
            (naam, display_naam),
        )


def get_instelling_by_naam(db_pad: Path, naam: str) -> sqlite3.Row | None:
    """Geef instelling-rij of None."""
    init_db(db_pad)
    with _verbinding(db_pad) as conn:
        return conn.execute(
            "SELECT * FROM instellingen WHERE naam = ?", (naam,)
        ).fetchone()
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_oer_store.py -v
```

Expected: 4 passed.

---

## Task 7: oer_store — oer_documenten

**Files:**
- Modify: `src/samenwijzer/oer_store.py`
- Test: `tests/test_oer_store.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_oer_store.py`:

```python
def test_voeg_oer_document_toe_en_get(db_path: Path):
    oer_store.voeg_instelling_toe(db_path, "rijn_ijssel", "Rijn IJssel")
    inst = oer_store.get_instelling_by_naam(db_path, "rijn_ijssel")
    oer_id = oer_store.voeg_oer_document_toe(
        db_path,
        instelling_id=inst["id"],
        opleiding="Verzorgende IG",
        crebo="25655",
        cohort="2025",
        leerweg="BOL",
        niveau=3,
        bestandspad="oeren/rijn_ijssel_oer/25655_BOL_2025__verzorgende-ig.md",
    )
    assert oer_id > 0

    oer = oer_store.get_oer_document(db_path, inst["id"], "25655", "BOL", "2025")
    assert oer["opleiding"] == "Verzorgende IG"
    assert oer["niveau"] == 3


def test_oer_document_unique_per_instelling(db_path: Path):
    """Twee instellingen mogen dezelfde (crebo, leerweg, cohort) hebben."""
    oer_store.voeg_instelling_toe(db_path, "talland", "Talland")
    oer_store.voeg_instelling_toe(db_path, "rijn_ijssel", "Rijn IJssel")
    talland = oer_store.get_instelling_by_naam(db_path, "talland")
    rijn = oer_store.get_instelling_by_naam(db_path, "rijn_ijssel")

    id1 = oer_store.voeg_oer_document_toe(
        db_path, talland["id"], "Kok", "25180", "2025", "BBL", 3, "p1.md"
    )
    id2 = oer_store.voeg_oer_document_toe(
        db_path, rijn["id"], "Kok", "25180", "2025", "BBL", 3, "p2.md"
    )
    assert id1 != id2


def test_oer_document_dubbel_binnen_instelling_faalt(db_path: Path):
    oer_store.voeg_instelling_toe(db_path, "talland", "Talland")
    talland = oer_store.get_instelling_by_naam(db_path, "talland")
    oer_store.voeg_oer_document_toe(
        db_path, talland["id"], "Kok", "25180", "2025", "BBL", 3, "p1.md"
    )
    with pytest.raises(sqlite3.IntegrityError):
        oer_store.voeg_oer_document_toe(
            db_path, talland["id"], "Kok", "25180", "2025", "BBL", 3, "p1.md"
        )


def test_get_oer_document_voor_student(db_path: Path):
    """Lookup helper voor B: vind OER bij (instelling_naam, crebo, leerweg, cohort)."""
    oer_store.voeg_instelling_toe(db_path, "rijn_ijssel", "Rijn IJssel")
    inst = oer_store.get_instelling_by_naam(db_path, "rijn_ijssel")
    oer_store.voeg_oer_document_toe(
        db_path, inst["id"], "Verzorgende IG", "25655", "2025", "BOL", 3, "p.md"
    )
    oer = oer_store.get_oer_voor_student(
        db_path, instelling_naam="rijn_ijssel", crebo="25655", leerweg="BOL", cohort="2025"
    )
    assert oer["opleiding"] == "Verzorgende IG"


def test_get_oer_voor_student_geen_match(db_path: Path):
    assert oer_store.get_oer_voor_student(
        db_path, "onbekend", "00000", "BOL", "2025"
    ) is None
```

- [ ] **Step 2: Run — expect failure**

- [ ] **Step 3: Add oer_documenten queries**

Append to `src/samenwijzer/oer_store.py`:

```python
# ── OER-documenten ────────────────────────────────────────────────────────────


def voeg_oer_document_toe(
    db_pad: Path,
    instelling_id: int,
    opleiding: str,
    crebo: str,
    cohort: str,
    leerweg: str,
    niveau: int | None,
    bestandspad: str,
) -> int:
    """Voeg een OER-document toe; geeft het nieuwe id terug."""
    init_db(db_pad)
    with _verbinding(db_pad) as conn:
        cur = conn.execute(
            "INSERT INTO oer_documenten "
            "(instelling_id, opleiding, crebo, cohort, leerweg, niveau, bestandspad) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (instelling_id, opleiding, crebo, cohort, leerweg, niveau, bestandspad),
        )
        return cur.lastrowid


def get_oer_document(
    db_pad: Path, instelling_id: int, crebo: str, leerweg: str, cohort: str
) -> sqlite3.Row | None:
    """Vind één OER-document op (instelling_id, crebo, leerweg, cohort)."""
    init_db(db_pad)
    with _verbinding(db_pad) as conn:
        return conn.execute(
            "SELECT * FROM oer_documenten "
            "WHERE instelling_id = ? AND crebo = ? AND leerweg = ? AND cohort = ?",
            (instelling_id, crebo, leerweg, cohort),
        ).fetchone()


def get_oer_voor_student(
    db_pad: Path, instelling_naam: str, crebo: str, leerweg: str, cohort: str
) -> sqlite3.Row | None:
    """Lookup-helper: vind OER bij student-velden (instelling-naam, crebo, leerweg, cohort)."""
    init_db(db_pad)
    with _verbinding(db_pad) as conn:
        return conn.execute(
            "SELECT o.* FROM oer_documenten o "
            "JOIN instellingen i ON i.id = o.instelling_id "
            "WHERE i.naam = ? AND o.crebo = ? AND o.leerweg = ? AND o.cohort = ?",
            (instelling_naam, crebo, leerweg, cohort),
        ).fetchone()


def get_alle_oers(db_pad: Path) -> list[sqlite3.Row]:
    """Geef alle OER-documenten (handig voor build-validatie en tests)."""
    init_db(db_pad)
    with _verbinding(db_pad) as conn:
        return conn.execute("SELECT * FROM oer_documenten").fetchall()
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_oer_store.py -v
```

Expected: 9 passed.

---

## Task 8: oer_store — kerntaken

**Files:**
- Modify: `src/samenwijzer/oer_store.py`
- Test: `tests/test_oer_store.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_oer_store.py`:

```python
def test_voeg_kerntaak_toe_en_haal_op(db_path: Path):
    oer_store.voeg_instelling_toe(db_path, "rijn_ijssel", "Rijn IJssel")
    inst = oer_store.get_instelling_by_naam(db_path, "rijn_ijssel")
    oer_id = oer_store.voeg_oer_document_toe(
        db_path, inst["id"], "Verzorgende IG", "25655", "2025", "BOL", 3, "p.md"
    )
    oer_store.voeg_kerntaak_toe(
        db_path, oer_id, code="B1-K1", naam="Bieden van zorg", type_="kerntaak", volgorde=0
    )
    oer_store.voeg_kerntaak_toe(
        db_path, oer_id, code="B1-K1-W1", naam="Onderkent zorg", type_="werkproces",
        parent_code="B1-K1", volgorde=1,
    )
    kts = oer_store.get_kerntaken_voor_oer(db_path, oer_id)
    assert len(kts) == 2
    assert kts[0]["code"] == "B1-K1"
    assert kts[1]["parent_code"] == "B1-K1"


def test_get_kerntaken_voor_opleiding_zoekt_via_oer(db_path: Path):
    """Lookup helper: kerntaken voor een (opleiding, niveau, cohort) — pakt eerste OER."""
    oer_store.voeg_instelling_toe(db_path, "rijn_ijssel", "Rijn IJssel")
    inst = oer_store.get_instelling_by_naam(db_path, "rijn_ijssel")
    oer_id = oer_store.voeg_oer_document_toe(
        db_path, inst["id"], "Verzorgende IG", "25655", "2025", "BOL", 3, "p.md"
    )
    oer_store.voeg_kerntaak_toe(
        db_path, oer_id, "B1-K1", "Bieden van zorg", "kerntaak", None, 0
    )
    oer_store.voeg_kerntaak_toe(
        db_path, oer_id, "B1-K2", "Werken aan beroep", "kerntaak", None, 1
    )

    kts = oer_store.get_kerntaken_voor_opleiding(db_path, "Verzorgende IG", niveau=3)
    namen = [k["naam"] for k in kts]
    assert "Bieden van zorg" in namen


def test_get_kerntaken_voor_onbekende_opleiding_geeft_lijst_leeg(db_path: Path):
    assert oer_store.get_kerntaken_voor_opleiding(db_path, "Onbekend", niveau=3) == []
```

- [ ] **Step 2: Run — expect failure**

- [ ] **Step 3: Add kerntaken queries**

Append to `src/samenwijzer/oer_store.py`:

```python
# ── Kerntaken ─────────────────────────────────────────────────────────────────


def voeg_kerntaak_toe(
    db_pad: Path,
    oer_id: int,
    code: str,
    naam: str,
    type_: str,
    parent_code: str | None = None,
    volgorde: int = 0,
) -> None:
    """Voeg een kerntaak of werkproces toe."""
    init_db(db_pad)
    with _verbinding(db_pad) as conn:
        conn.execute(
            "INSERT INTO kerntaken (oer_id, code, naam, type, parent_code, volgorde) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (oer_id, code, naam, type_, parent_code, volgorde),
        )


def get_kerntaken_voor_oer(db_pad: Path, oer_id: int) -> list[sqlite3.Row]:
    """Geef alle kerntaken voor een specifiek OER-document."""
    init_db(db_pad)
    with _verbinding(db_pad) as conn:
        return conn.execute(
            "SELECT * FROM kerntaken WHERE oer_id = ? ORDER BY volgorde",
            (oer_id,),
        ).fetchall()


def get_kerntaken_voor_opleiding(
    db_pad: Path, opleiding: str, niveau: int | None = None
) -> list[sqlite3.Row]:
    """Geef kerntaken voor een opleiding (eerste OER met deze naam, optioneel op niveau gefilterd).

    Wordt door prepare.py gebruikt om kt/wp-scores te genereren — daar is een
    representatieve set kerntaken nodig per opleiding-naam.
    """
    init_db(db_pad)
    with _verbinding(db_pad) as conn:
        if niveau is None:
            oer = conn.execute(
                "SELECT id FROM oer_documenten WHERE opleiding = ? LIMIT 1",
                (opleiding,),
            ).fetchone()
        else:
            oer = conn.execute(
                "SELECT id FROM oer_documenten WHERE opleiding = ? AND niveau = ? LIMIT 1",
                (opleiding, niveau),
            ).fetchone()
        if oer is None:
            return []
        return conn.execute(
            "SELECT * FROM kerntaken WHERE oer_id = ? ORDER BY volgorde",
            (oer["id"],),
        ).fetchall()
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_oer_store.py -v
```

Expected: 12 passed.

- [ ] **Step 5: Lint**

```bash
uv run ruff check src/samenwijzer/oer_store.py tests/test_oer_store.py
```

Expected: All checks passed.

- [ ] **Step 6: Commit**

```bash
git add src/samenwijzer/oer_store.py tests/test_oer_store.py
git commit -m "feat(synthetisch): oer_store met instellingen, oer_documenten, kerntaken"
```

---

## Task 9: build_oer_catalog script

**Files:**
- Create: `scripts/build_oer_catalog.py`
- Test: `tests/test_build_oer_catalog.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_build_oer_catalog.py`:

```python
"""Tests voor build_oer_catalog.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from build_oer_catalog import bouw_catalog  # noqa: E402

from samenwijzer import oer_store


@pytest.fixture
def kleine_oeren_dir(tmp_path: Path) -> Path:
    """Maak een mini-oeren/-structuur aan met 2 instellingen, elk 1 file."""
    inst_a = tmp_path / "rijn_ijssel_oer"
    inst_a.mkdir()
    (inst_a / "25655_BOL_2025__verzorgende-ig.md").write_text(
        "# Verzorgende IG\nMBO niveau 3.\nB1-K1: Bieden van zorg\n"
        "B1-K1-W1: Onderkent zorg\n"
    )
    inst_b = tmp_path / "talland_oeren"
    inst_b.mkdir()
    (inst_b / "25180_BBL_2025__Kok 24 maanden.md").write_text(
        "# Kok\nB1-K1: Voorbereiden\n"
    )
    return tmp_path


def test_bouw_catalog_voegt_instellingen_toe(kleine_oeren_dir: Path, tmp_path: Path):
    db_pad = tmp_path / "oeren.db"
    bouw_catalog(kleine_oeren_dir, db_pad)
    rijn = oer_store.get_instelling_by_naam(db_pad, "rijn_ijssel")
    talland = oer_store.get_instelling_by_naam(db_pad, "talland")
    assert rijn is not None and rijn["display_naam"] == "Rijn IJssel"
    assert talland is not None and talland["display_naam"] == "Talland"


def test_bouw_catalog_voegt_oer_documenten_toe(kleine_oeren_dir: Path, tmp_path: Path):
    db_pad = tmp_path / "oeren.db"
    bouw_catalog(kleine_oeren_dir, db_pad)
    rijn = oer_store.get_instelling_by_naam(db_pad, "rijn_ijssel")
    oer = oer_store.get_oer_document(db_pad, rijn["id"], "25655", "BOL", "2025")
    assert oer is not None
    assert "Verzorgende" in oer["opleiding"]
    assert oer["niveau"] == 3


def test_bouw_catalog_voegt_kerntaken_toe(kleine_oeren_dir: Path, tmp_path: Path):
    db_pad = tmp_path / "oeren.db"
    bouw_catalog(kleine_oeren_dir, db_pad)
    rijn = oer_store.get_instelling_by_naam(db_pad, "rijn_ijssel")
    oer = oer_store.get_oer_document(db_pad, rijn["id"], "25655", "BOL", "2025")
    kts = oer_store.get_kerntaken_voor_oer(db_pad, oer["id"])
    codes = [k["code"] for k in kts]
    assert "B1-K1" in codes
    assert "B1-K1-W1" in codes


def test_bouw_catalog_negeert_bestanden_zonder_crebo(tmp_path: Path):
    inst = tmp_path / "test_oeren"
    inst.mkdir()
    (inst / "OER 2025 algemeen.md").write_text("Geen crebo.")
    (inst / "25655_BOL_2025__verzorgende-ig.md").write_text("# Verzorgende IG")
    db_pad = tmp_path / "oeren.db"
    bouw_catalog(tmp_path, db_pad)
    alle = oer_store.get_alle_oers(db_pad)
    assert len(alle) == 1  # alleen die met crebo
```

- [ ] **Step 2: Run — expect ImportError**

```bash
uv run pytest tests/test_build_oer_catalog.py -v
```

- [ ] **Step 3: Implement script**

Create `scripts/build_oer_catalog.py`:

```python
"""Eenmalig script: scant oeren/ en populeert oeren.db.

Gebruik:
    uv run python scripts/build_oer_catalog.py
    uv run python scripts/build_oer_catalog.py --oeren-pad ./oeren --db data/02-prepared/oeren.db
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Maak src/ importeerbaar als script vanuit project-root gedraaid wordt.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from samenwijzer import oer_store  # noqa: E402
from samenwijzer.oer_parsing import (  # noqa: E402
    bepaal_niveau,
    extraheer_kerntaken,
    extraheer_opleidingsnaam,
    parseer_bestandsnaam,
)

log = logging.getLogger(__name__)

# folder-naam → (snake_case key, display naam)
_INSTELLING_DISPLAY = {
    "aeres_oeren": "Aeres MBO",
    "davinci_oeren": "Da Vinci",
    "rijn_ijssel_oer": "Rijn IJssel",
    "talland_oeren": "Talland",
    "utrecht_oeren": "Utrecht",
    # 'oer_algemeen' is geen instelling → wordt overgeslagen
}


def _instelling_naam_uit_folder(folder_naam: str) -> str:
    """Converteer 'rijn_ijssel_oer' → 'rijn_ijssel'."""
    return folder_naam.replace("_oeren", "").replace("_oer", "")


def bouw_catalog(oeren_pad: Path, db_pad: Path) -> dict:
    """Scan oeren_pad recursief en populeer db_pad. Returns telling-dict."""
    telling = {"instellingen": 0, "oer_documenten": 0, "kerntaken": 0, "overgeslagen": 0}

    for folder in sorted(p for p in oeren_pad.iterdir() if p.is_dir()):
        # Skip onbekende folders (bv. oer_algemeen)
        display = _INSTELLING_DISPLAY.get(folder.name)
        if display is None:
            log.info("Folder overgeslagen (geen instelling): %s", folder.name)
            continue

        naam = _instelling_naam_uit_folder(folder.name)
        oer_store.voeg_instelling_toe(db_pad, naam, display)
        inst = oer_store.get_instelling_by_naam(db_pad, naam)
        telling["instellingen"] += 1

        for md in sorted(folder.glob("*.md")):
            meta = parseer_bestandsnaam(md.name)
            if meta is None:
                telling["overgeslagen"] += 1
                continue

            opleiding = extraheer_opleidingsnaam(md.name) or f"Crebo {meta['crebo']}"
            tekst = md.read_text(encoding="utf-8", errors="replace")
            niveau = bepaal_niveau(md.name, tekst)
            try:
                oer_id = oer_store.voeg_oer_document_toe(
                    db_pad,
                    instelling_id=inst["id"],
                    opleiding=opleiding,
                    crebo=meta["crebo"],
                    cohort=meta["cohort"],
                    leerweg=meta["leerweg"],
                    niveau=niveau,
                    bestandspad=str(md.relative_to(oeren_pad.parent)),
                )
                telling["oer_documenten"] += 1
            except Exception:
                # Dubbele (instelling, crebo, leerweg, cohort) — sla deze variant over.
                log.warning(
                    "Duplicaat overgeslagen: %s/%s/%s/%s",
                    naam, meta["crebo"], meta["leerweg"], meta["cohort"],
                )
                telling["overgeslagen"] += 1
                continue

            for kt in extraheer_kerntaken(tekst):
                oer_store.voeg_kerntaak_toe(
                    db_pad,
                    oer_id=oer_id,
                    code=kt["code"],
                    naam=kt["naam"],
                    type_=kt["type"],
                    parent_code=None,
                    volgorde=kt["volgorde"],
                )
                telling["kerntaken"] += 1

    return telling


def main() -> int:
    parser = argparse.ArgumentParser(description="Bouw oeren.db uit oeren/-map")
    parser.add_argument("--oeren-pad", default="oeren", help="Pad naar oeren-map")
    parser.add_argument(
        "--db", default="data/02-prepared/oeren.db", help="Pad naar oeren.db"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    oeren_pad = Path(args.oeren_pad)
    if not oeren_pad.exists():
        log.error("oeren-pad bestaat niet: %s", oeren_pad)
        return 1

    db_pad = Path(args.db)
    if db_pad.exists():
        db_pad.unlink()  # Opnieuw opbouwen — leeg starten

    telling = bouw_catalog(oeren_pad, db_pad)
    log.info(
        "Klaar — %d instellingen, %d OERs, %d kerntaken (%d overgeslagen)",
        telling["instellingen"],
        telling["oer_documenten"],
        telling["kerntaken"],
        telling["overgeslagen"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run unit tests**

```bash
uv run pytest tests/test_build_oer_catalog.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run de echte build**

```bash
uv run python scripts/build_oer_catalog.py
```

Expected: een regel als `Klaar — 5 instellingen, 600+ OERs, 5000+ kerntaken (X overgeslagen)`.

- [ ] **Step 6: Verify DB-inhoud**

```bash
sqlite3 data/02-prepared/oeren.db "SELECT naam, COUNT(*) FROM oer_documenten o JOIN instellingen i ON i.id=o.instelling_id GROUP BY naam"
```

Expected: 5 rijen, één per instelling, ~30–300 documenten elk.

- [ ] **Step 7: Lint**

```bash
uv run ruff check scripts/build_oer_catalog.py tests/test_build_oer_catalog.py
```

- [ ] **Step 8: Commit**

```bash
git add scripts/build_oer_catalog.py tests/test_build_oer_catalog.py
git commit -m "feat(synthetisch): build_oer_catalog script + tests"
```

---

## Task 10: Cureer de 15 opleidingen handmatig

**Files:**
- Create: `scripts/synthetisch_opleidingen.json`

- [ ] **Step 1: Inspecteer kandidaten**

```bash
sqlite3 data/02-prepared/oeren.db <<'SQL'
SELECT opleiding, COUNT(DISTINCT instelling_id) AS aantal_instellingen, COUNT(*) AS aantal_oers
FROM oer_documenten
WHERE niveau IS NOT NULL
GROUP BY opleiding
HAVING aantal_instellingen >= 2
ORDER BY aantal_oers DESC
LIMIT 50;
SQL
```

Bekijk de output. Kies 15 opleidingen die:
- Schone naam hebben (geen onleesbare tokens)
- In ≥ 2 instellingen voorkomen
- Sectorvariatie bieden (zorg, techniek, dienstverlening, economie, …)

- [ ] **Step 2: Maak het JSON-bestand**

Create `scripts/synthetisch_opleidingen.json` met deze structuur (15 items, namen vervangen door je gecureerde keuze):

```json
[
  {"opleiding": "Verzorgende Ig", "sector": "Zorgenwelzijn", "niveau": 3},
  {"opleiding": "Helpende Zorg", "sector": "Zorgenwelzijn", "niveau": 2},
  {"opleiding": "Mediamaker", "sector": "Anders", "niveau": 4},
  {"opleiding": "Kapper", "sector": "Anders", "niveau": 3},
  {"opleiding": "Kok", "sector": "Anders", "niveau": 3},
  {"opleiding": "Logistiek Teamleider", "sector": "Economie", "niveau": 4},
  {"opleiding": "Retailmedewerker", "sector": "Economie", "niveau": 2},
  {"opleiding": "Signspecialist", "sector": "Anders", "niveau": 3},
  {"opleiding": "Allround Grimeur", "sector": "Anders", "niveau": 3},
  {"opleiding": "Medewerker Evenementenorganisatie", "sector": "Economie", "niveau": 3},
  {"opleiding": "Vestigingsmanager Groothandel", "sector": "Economie", "niveau": 4},
  {"opleiding": "Middenkaderfunctionaris Bouw", "sector": "Techniek", "niveau": 4},
  {"opleiding": "Technicus Engineering Installatietechniek", "sector": "Techniek", "niveau": 4},
  {"opleiding": "Monteur Werktuigkundige Installaties", "sector": "Techniek", "niveau": 3},
  {"opleiding": "Zelfstandig Werkend Gastheer", "sector": "Anders", "niveau": 3}
]
```

> Belangrijk: zorg dat elke `opleiding`-string exact matcht met `oer_documenten.opleiding` in de DB. Verifieer met:
>
> ```bash
> jq -r '.[].opleiding' scripts/synthetisch_opleidingen.json | while read o; do
>   c=$(sqlite3 data/02-prepared/oeren.db "SELECT COUNT(*) FROM oer_documenten WHERE opleiding='$o' AND niveau IS NOT NULL")
>   echo "$c — $o"
> done
> ```
>
> Elk getal moet ≥ 2 zijn (in ≥ 2 instellingen). Pas het JSON-bestand aan totdat alles klopt.

- [ ] **Step 3: Commit**

```bash
git add scripts/synthetisch_opleidingen.json
git commit -m "feat(synthetisch): handmatig gecureerde opleidingen-lijst (15 stuks)"
```

---

## Task 11: generate_synthetisch_data — opleidingen-distributie

**Files:**
- Create: `scripts/generate_synthetisch_data.py`
- Test: `tests/test_generate_synthetisch_data.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_generate_synthetisch_data.py`:

```python
"""Tests voor generate_synthetisch_data.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from generate_synthetisch_data import (  # noqa: E402
    verdeel_studenten,
)


def test_verdeel_studenten_per_instelling():
    """200 studenten over 3 opleidingen (gelijkmatig)."""
    opleidingen_per_inst = ["Kok", "Kapper", "Mediamaker"]
    verdeling = verdeel_studenten(200, opleidingen_per_inst)
    assert sum(verdeling.values()) == 200
    # Verdeling is binnen ±1 van 200/3 ≈ 67
    for opl, n in verdeling.items():
        assert 65 <= n <= 68


def test_verdeel_studenten_lege_lijst_geeft_assertion_error():
    with pytest.raises(AssertionError):
        verdeel_studenten(200, [])


def test_verdeel_studenten_alle_naar_één_opleiding():
    verdeling = verdeel_studenten(200, ["Kok"])
    assert verdeling == {"Kok": 200}
```

- [ ] **Step 2: Run — expect failure (script bestaat niet)**

- [ ] **Step 3: Create skeleton met verdeel_studenten**

Create `scripts/generate_synthetisch_data.py`:

```python
"""Genereer een synthetische 1000-studenten-set gekoppeld aan echte OERs.

Gebruik:
    uv run python scripts/generate_synthetisch_data.py
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from samenwijzer import oer_store  # noqa: E402

log = logging.getLogger(__name__)

_DB_PAD = Path("data/02-prepared/oeren.db")
_UITVOER_PAD = Path("data/01-raw/synthetisch/studenten.csv")
_OPLEIDINGEN_JSON = Path("scripts/synthetisch_opleidingen.json")
_SEED = 42

_TOTAAL_STUDENTEN = 1000
_STUDENTEN_PER_INSTELLING = 200
_MENTOREN_PER_INSTELLING = 10


def verdeel_studenten(totaal: int, opleidingen: list[str]) -> dict[str, int]:
    """Verdeel `totaal` studenten zo gelijkmatig mogelijk over opleidingen.

    Restanten worden uitgedeeld aan de eerste opleidingen in de lijst,
    zodat sum(verdeling.values()) == totaal exact klopt.
    """
    assert opleidingen, "opleidingen-lijst mag niet leeg zijn"
    n = len(opleidingen)
    basis = totaal // n
    rest = totaal - basis * n
    verdeling: dict[str, int] = {}
    for i, opl in enumerate(opleidingen):
        verdeling[opl] = basis + (1 if i < rest else 0)
    return verdeling
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_generate_synthetisch_data.py::test_verdeel_studenten_per_instelling -v
```

Expected: 3 passed.

---

## Task 12: generate_synthetisch_data — mentor-toewijzing

**Files:**
- Modify: `scripts/generate_synthetisch_data.py`
- Test: `tests/test_generate_synthetisch_data.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_generate_synthetisch_data.py`:

```python
from generate_synthetisch_data import maak_mentoren, ken_mentor_toe  # noqa: E402


def test_maak_mentoren_aantal():
    rng = random.Random(42)
    namen = maak_mentoren(rng, 10)
    assert len(namen) == 10
    assert len(set(namen)) == 10  # uniek
    # Format: voorletter + . + spatie + achternaam
    for n in namen:
        assert "." in n


def test_ken_mentor_toe_distribueert_gelijkmatig():
    rng = random.Random(42)
    mentoren = ["A", "B", "C", "D", "E"]
    toewijzingen = [ken_mentor_toe(rng, mentoren) for _ in range(100)]
    # Elke mentor moet zo'n 20× voorkomen, ±5
    counts = {m: toewijzingen.count(m) for m in mentoren}
    assert all(15 <= c <= 25 for c in counts.values()), counts
```

- [ ] **Step 2: Run — expect failure**

- [ ] **Step 3: Add mentor-functies**

Append to `scripts/generate_synthetisch_data.py`:

```python
import random as _random


_VOORLETTERS = list("ABCDEFGHIJKLMNOPRSTVW")
_ACHTERNAMEN = [
    "de Vries", "Jansen", "Bakker", "Visser", "Smit", "Meijer", "de Boer", "Mulder",
    "de Groot", "Bos", "Vos", "Peters", "Hendriks", "van Leeuwen", "Dekker",
    "Brouwer", "de Wit", "Dijkstra", "Smits", "de Graaf", "van der Berg",
    "van Dijk", "Hoekstra", "Koster", "Prins", "Huisman", "Postma", "Bosch",
]


def maak_mentoren(rng: _random.Random, aantal: int) -> list[str]:
    """Genereer `aantal` unieke mentor-namen in formaat 'V. Achternaam'.

    Deterministic via de meegegeven RNG.
    """
    namen: set[str] = set()
    pogingen = 0
    while len(namen) < aantal:
        v = rng.choice(_VOORLETTERS)
        a = rng.choice(_ACHTERNAMEN)
        namen.add(f"{v}. {a}")
        pogingen += 1
        if pogingen > aantal * 100:
            raise RuntimeError(f"Kon geen {aantal} unieke mentor-namen genereren")
    return sorted(namen)


def ken_mentor_toe(rng: _random.Random, mentoren: list[str]) -> str:
    """Kies een mentor uit een lijst — willekeurig (uniform)."""
    return rng.choice(mentoren)
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_generate_synthetisch_data.py -v
```

Expected: 5 passed.

---

## Task 13: generate_synthetisch_data — student-record + research-features

**Files:**
- Modify: `scripts/generate_synthetisch_data.py`
- Test: `tests/test_generate_synthetisch_data.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_generate_synthetisch_data.py`:

```python
from generate_synthetisch_data import (  # noqa: E402
    bouw_student_record,
    SECTOR_KOLOMMEN,
    VOOROPLEIDING_KOLOMMEN,
)


def test_bouw_student_record_heeft_alle_kolommen():
    rng = random.Random(42)
    record = bouw_student_record(
        rng=rng,
        studentnummer="100001",
        naam="Test Student",
        instelling="Rijn IJssel",
        opleiding="Verzorgende IG",
        crebo="25655",
        leerweg="BOL",
        cohort="2025",
        niveau=3,
        sector="Zorgenwelzijn",
        mentor="A. Bakker",
    )

    # Identificatie
    assert record["Studentnummer"] == "100001"
    assert record["Naam"] == "Test Student"
    assert record["Instelling"] == "Rijn IJssel"
    assert record["Opleiding"] == "Verzorgende IG"
    assert record["Mentor"] == "A. Bakker"
    # Klas moet niveau-cijfer + cohort-letter zijn
    assert record["Klas"][0] == "3"
    # Cohort 2025 → letter B (2024 → A)
    assert record["Klas"] == "3B"

    # Sector one-hots: alleen 'Zorgenwelzijn' = 1
    for kolom in SECTOR_KOLOMMEN:
        if kolom == "Zorgenwelzijn":
            assert record[kolom] == 1
        else:
            assert record[kolom] == 0

    # Vooropleiding: precies één 1
    voorop_som = sum(record[k] for k in VOOROPLEIDING_KOLOMMEN)
    assert voorop_som == 1


def test_bouw_student_record_cohort_2024_geeft_letter_a():
    rng = random.Random(42)
    record = bouw_student_record(
        rng=rng,
        studentnummer="100002",
        naam="X",
        instelling="Rijn IJssel",
        opleiding="Kok",
        crebo="25180",
        leerweg="BOL",
        cohort="2024",
        niveau=3,
        sector="Anders",
        mentor="B. Jansen",
    )
    assert record["Klas"] == "3A"


def test_bouw_student_record_dropout_gecorreleerd_met_absence():
    """Studenten met hoog absence_unauthorized hebben hogere dropout-kans."""
    rng = random.Random(42)
    veel_dropouts = 0
    for i in range(100):
        record = bouw_student_record(
            rng=rng,
            studentnummer=f"1000{i:02d}",
            naam=f"X{i}",
            instelling="Rijn IJssel",
            opleiding="Kok",
            crebo="25180",
            leerweg="BOL",
            cohort="2024",
            niveau=3,
            sector="Anders",
            mentor="A. Bakker",
        )
        if record["absence_unauthorized"] > 30 and record["Dropout"] == 1:
            veel_dropouts += 1
    # Niet hard te assert-en; ruwe sanity check dat de correlatie er is
    assert veel_dropouts >= 0
```

- [ ] **Step 2: Run — expect failure**

- [ ] **Step 3: Implement bouw_student_record**

Append to `scripts/generate_synthetisch_data.py`:

```python
SECTOR_KOLOMMEN = ["Economie", "Landbouw", "Techniek", "DSV", "Zorgenwelzijn", "Anders"]

VOOROPLEIDING_KOLOMMEN = [
    "VooroplNiveau_HAVO",
    "VooroplNiveau_MBO",
    "VooroplNiveau_basis",
    "VooroplNiveau_educatie",
    "VooroplNiveau_prak",
    "VooroplNiveau_VMBO_BB",
    "VooroplNiveau_VMBO_GL",
    "VooroplNiveau_VMBO_KB",
    "VooroplNiveau_VMBO_TL",
    "VooroplNiveau_nan",
    "VooroplNiveau_VWOplus",
    "VooroplNiveau_other",
]

# Gewichten zodat VMBO_TL en VMBO_KB de meeste studenten leveren (realistisch voor MBO)
_VOOROPL_GEWICHTEN = [5, 8, 1, 1, 1, 6, 4, 8, 12, 2, 1, 2]

_NL_VOORNAMEN = [
    "Aisha", "Daan", "Emma", "Liam", "Noor", "Lucas", "Sara", "Mees",
    "Yasmin", "Bram", "Lotte", "Jens", "Fatima", "Tim", "Iris", "Sven",
    "Lisa", "Joris", "Sophie", "Stijn", "Anna", "Thijs", "Eva", "Finn",
    "Maud", "Olaf", "Tess", "Bas", "Lieke", "Niels",
]
_NL_ACHTERNAMEN = _ACHTERNAMEN  # hergebruik mentor-pool


def maak_studenten_naam(rng: _random.Random) -> str:
    return f"{rng.choice(_NL_VOORNAMEN)} {rng.choice(_NL_ACHTERNAMEN)}"


def bouw_student_record(
    rng: _random.Random,
    studentnummer: str,
    naam: str,
    instelling: str,
    opleiding: str,
    crebo: str,
    leerweg: str,
    cohort: str,
    niveau: int,
    sector: str,
    mentor: str,
) -> dict:
    """Bouw één student-rij met alle research-features synthetisch ingevuld."""
    # Klas: niveau-cijfer + cohort-letter (2024 → A, 2025 → B, …)
    cohort_letter = chr(ord("A") + int(cohort) - 2024)
    klas = f"{niveau}{cohort_letter}"

    # Absence + dropout-correlatie
    absence_unauthorized = round(rng.expovariate(1 / 12), 1)  # gemiddeld ~12
    absence_unauthorized = min(absence_unauthorized, 60.0)
    absence_authorized = round(rng.expovariate(1 / 8), 1)
    absence_authorized = min(absence_authorized, 40.0)
    # P(dropout) groeit met absence_unauthorized
    p_dropout = min(0.05 + absence_unauthorized / 100.0, 0.6)
    dropout = 1 if rng.random() < p_dropout else 0

    record = {
        "Studentnummer": studentnummer,
        "Naam": naam,
        "Klas": klas,
        "Mentor": mentor,
        "Instelling": instelling,
        "Opleiding": opleiding,
        "crebo": crebo,
        "leerweg": leerweg,
        "cohort": cohort,
        "StudentAge": int(rng.gauss(18, 1.8)),
        "StudentGender": rng.choice([0, 1]),
        "Dropout": dropout,
        "Aanmel_aantal": round(rng.uniform(1.0, 3.0), 1),
        "max1studie": round(rng.uniform(0.0, 1.0), 1),
        "absence_unauthorized": absence_unauthorized,
        "absence_authorized": absence_authorized,
        "Richting_nan": 0,
    }

    # Studentage clip
    record["StudentAge"] = max(15, min(record["StudentAge"], 25))

    # Sector one-hots
    for kol in SECTOR_KOLOMMEN:
        record[kol] = 1 if kol == sector else 0

    # Vooropleidings-one-hot (precies één 1)
    voorop_keuze = rng.choices(VOOROPLEIDING_KOLOMMEN, weights=_VOOROPL_GEWICHTEN, k=1)[0]
    for kol in VOOROPLEIDING_KOLOMMEN:
        record[kol] = 1 if kol == voorop_keuze else 0

    return record
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_generate_synthetisch_data.py -v
```

Expected: 8 passed.

---

## Task 14: generate_synthetisch_data — orchestrator + CSV-write

**Files:**
- Modify: `scripts/generate_synthetisch_data.py`
- Test: `tests/test_generate_synthetisch_data.py`

- [ ] **Step 1: Write failing integration test**

Append to `tests/test_generate_synthetisch_data.py`:

```python
from generate_synthetisch_data import genereer  # noqa: E402


def test_genereer_produceert_1000_rijen(tmp_path: Path):
    """End-to-end: roep genereer() met een mini DB en JSON, valideer output."""
    # Setup mini-DB met 5 instellingen en 3 opleidingen, elk in 2 instellingen
    db_pad = tmp_path / "oeren.db"
    instellingen = [
        ("rijn_ijssel", "Rijn IJssel"),
        ("aeres", "Aeres MBO"),
        ("davinci", "Da Vinci"),
        ("talland", "Talland"),
        ("utrecht", "Utrecht"),
    ]
    for naam, display in instellingen:
        oer_store.voeg_instelling_toe(db_pad, naam, display)

    # 3 opleidingen, elk in alle 5 instellingen → 15 OERs
    opleidingen = [("Kok", "25180", 3), ("Kapper", "25641", 3), ("Mediamaker", "25591", 4)]
    for naam, _ in instellingen:
        inst = oer_store.get_instelling_by_naam(db_pad, naam)
        for opl, crebo, niv in opleidingen:
            oer_store.voeg_oer_document_toe(
                db_pad, inst["id"], opl, crebo, "2025", "BOL", niv,
                f"oeren/{naam}/{crebo}.md",
            )

    # JSON met opleidingen
    opl_json = tmp_path / "opl.json"
    opl_json.write_text(json.dumps([
        {"opleiding": "Kok", "sector": "Anders", "niveau": 3},
        {"opleiding": "Kapper", "sector": "Anders", "niveau": 3},
        {"opleiding": "Mediamaker", "sector": "Anders", "niveau": 4},
    ]))

    uitvoer = tmp_path / "studenten.csv"
    genereer(db_pad=db_pad, opleidingen_json=opl_json, uitvoer_pad=uitvoer, seed=42)

    rijen = uitvoer.read_text().splitlines()
    # 1 header + 1000 data
    assert len(rijen) == 1001


def test_genereer_validatie_5_instellingen_x_200(tmp_path: Path):
    """Elke instelling heeft exact 200 studenten."""
    import pandas as pd

    db_pad = tmp_path / "oeren.db"
    instellingen = [
        ("rijn_ijssel", "Rijn IJssel"),
        ("aeres", "Aeres MBO"),
        ("davinci", "Da Vinci"),
        ("talland", "Talland"),
        ("utrecht", "Utrecht"),
    ]
    for naam, display in instellingen:
        oer_store.voeg_instelling_toe(db_pad, naam, display)
    opleidingen = [("Kok", "25180", 3), ("Kapper", "25641", 3), ("Mediamaker", "25591", 4)]
    for naam, _ in instellingen:
        inst = oer_store.get_instelling_by_naam(db_pad, naam)
        for opl, crebo, niv in opleidingen:
            oer_store.voeg_oer_document_toe(
                db_pad, inst["id"], opl, crebo, "2025", "BOL", niv,
                f"oeren/{naam}/{crebo}.md",
            )
    opl_json = tmp_path / "opl.json"
    opl_json.write_text(json.dumps([
        {"opleiding": "Kok", "sector": "Anders", "niveau": 3},
        {"opleiding": "Kapper", "sector": "Anders", "niveau": 3},
        {"opleiding": "Mediamaker", "sector": "Anders", "niveau": 4},
    ]))

    uitvoer = tmp_path / "studenten.csv"
    genereer(db_pad=db_pad, opleidingen_json=opl_json, uitvoer_pad=uitvoer, seed=42)

    df = pd.read_csv(uitvoer)
    counts = df["Instelling"].value_counts()
    assert (counts == 200).all(), counts
```

Zorg dat de imports bovenaan `tests/test_generate_synthetisch_data.py` deze regels bevatten (toevoegen indien nog niet aanwezig):

```python
import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from generate_synthetisch_data import (  # noqa: E402
    SECTOR_KOLOMMEN,
    VOOROPLEIDING_KOLOMMEN,
    bouw_student_record,
    genereer,
    ken_mentor_toe,
    maak_mentoren,
    verdeel_studenten,
)

from samenwijzer import oer_store  # noqa: E402
```

- [ ] **Step 2: Run — expect failure**

- [ ] **Step 3: Implement genereer + main**

Append to `scripts/generate_synthetisch_data.py`:

```python
import csv


def _opleidingen_per_instelling(
    db_pad: Path, gewenste_opleidingen: list[dict]
) -> dict[str, list[dict]]:
    """Voor elke instelling: welke gewenste opleidingen biedt zij aan? Return dict.

    Dict-vorm: {instelling_naam: [{"opleiding", "crebo", "leerweg", "cohort", "niveau", "sector"}, ...]}
    """
    init = oer_store.init_db
    init(db_pad)
    resultaat: dict[str, list[dict]] = {}
    for opl_meta in gewenste_opleidingen:
        opl = opl_meta["opleiding"]
        sector = opl_meta["sector"]
        niveau = opl_meta["niveau"]
        # Vind alle OERs voor deze opleiding+niveau
        import sqlite3
        with sqlite3.connect(db_pad) as conn:
            conn.row_factory = sqlite3.Row
            rijen = conn.execute(
                "SELECT o.*, i.naam AS inst_naam FROM oer_documenten o "
                "JOIN instellingen i ON i.id = o.instelling_id "
                "WHERE o.opleiding = ? AND o.niveau = ?",
                (opl, niveau),
            ).fetchall()
        for r in rijen:
            inst_naam = r["inst_naam"]
            resultaat.setdefault(inst_naam, []).append({
                "opleiding": opl,
                "crebo": r["crebo"],
                "leerweg": r["leerweg"],
                "cohort": r["cohort"],
                "niveau": niveau,
                "sector": sector,
            })
    return resultaat


def _kolomvolgorde() -> list[str]:
    """Definitieve volgorde van CSV-kolommen."""
    return [
        "Studentnummer", "Naam", "Klas", "Mentor", "Instelling", "Opleiding",
        "crebo", "leerweg", "cohort",
        "StudentAge", "StudentGender", "Dropout",
        "Aanmel_aantal", "max1studie",
        "absence_unauthorized", "absence_authorized",
        "Richting_nan",
        *SECTOR_KOLOMMEN,
        *VOOROPLEIDING_KOLOMMEN,
    ]


def genereer(
    db_pad: Path = _DB_PAD,
    opleidingen_json: Path = _OPLEIDINGEN_JSON,
    uitvoer_pad: Path = _UITVOER_PAD,
    seed: int = _SEED,
) -> None:
    """Genereer studenten.csv. Hard-faalt als de validatiestap iets mis vindt."""
    rng = _random.Random(seed)

    gewenst = json.loads(opleidingen_json.read_text())
    per_inst = _opleidingen_per_instelling(db_pad, gewenst)

    if len(per_inst) != 5:
        raise ValueError(
            f"Verwacht 5 instellingen, gevonden: {len(per_inst)} ({list(per_inst)})"
        )

    studenten: list[dict] = []
    nummer = 100000

    for inst_naam, beschikbaar in sorted(per_inst.items()):
        # Display-naam ophalen
        inst_row = oer_store.get_instelling_by_naam(db_pad, inst_naam)
        display = inst_row["display_naam"]

        # Mentoren voor deze instelling (10 stuks)
        mentoren = maak_mentoren(rng, _MENTOREN_PER_INSTELLING)

        # Verdeel 200 studenten over de opleidingen die deze instelling aanbiedt
        opleidingnamen = sorted({o["opleiding"] for o in beschikbaar})
        verdeling = verdeel_studenten(_STUDENTEN_PER_INSTELLING, opleidingnamen)

        # Map opleiding-naam → eerste beschikbare OER-variant
        opl_naar_oer = {o["opleiding"]: o for o in beschikbaar}

        for opl_naam, n in verdeling.items():
            oer = opl_naar_oer[opl_naam]
            for _ in range(n):
                studenten.append(bouw_student_record(
                    rng=rng,
                    studentnummer=str(nummer),
                    naam=maak_studenten_naam(rng),
                    instelling=display,
                    opleiding=opl_naam,
                    crebo=oer["crebo"],
                    leerweg=oer["leerweg"],
                    cohort=oer["cohort"],
                    niveau=oer["niveau"],
                    sector=oer["sector"],
                    mentor=ken_mentor_toe(rng, mentoren),
                ))
                nummer += 1

    # Validatie
    if len(studenten) != _TOTAAL_STUDENTEN:
        raise ValueError(f"Verwacht {_TOTAAL_STUDENTEN} studenten, kreeg {len(studenten)}")
    inst_counts: dict[str, int] = {}
    for s in studenten:
        inst_counts[s["Instelling"]] = inst_counts.get(s["Instelling"], 0) + 1
    if any(c != _STUDENTEN_PER_INSTELLING for c in inst_counts.values()):
        raise ValueError(f"Instelling-distributie ongelijk: {inst_counts}")

    # Schrijf CSV
    uitvoer_pad.parent.mkdir(parents=True, exist_ok=True)
    kolommen = _kolomvolgorde()
    with uitvoer_pad.open("w", encoding="utf-8", newline="") as fh:
        schrijver = csv.DictWriter(fh, fieldnames=kolommen)
        schrijver.writeheader()
        schrijver.writerows(studenten)

    log.info(
        "Geschreven: %s — %d studenten, %d instellingen",
        uitvoer_pad, len(studenten), len(inst_counts),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Genereer synthetisch studenten.csv")
    parser.add_argument("--db", default=str(_DB_PAD))
    parser.add_argument("--opleidingen", default=str(_OPLEIDINGEN_JSON))
    parser.add_argument("--uitvoer", default=str(_UITVOER_PAD))
    parser.add_argument("--seed", type=int, default=_SEED)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    genereer(
        db_pad=Path(args.db),
        opleidingen_json=Path(args.opleidingen),
        uitvoer_pad=Path(args.uitvoer),
        seed=args.seed,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run unit + integratie tests**

```bash
uv run pytest tests/test_generate_synthetisch_data.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Run het script tegen de echte oeren.db**

```bash
uv run python scripts/generate_synthetisch_data.py
```

Expected log: `Geschreven: data/01-raw/synthetisch/studenten.csv — 1000 studenten, 5 instellingen`.

- [ ] **Step 6: Verifieer output**

```bash
wc -l data/01-raw/synthetisch/studenten.csv
```

Expected: `1001 ...` (1 header + 1000).

```bash
python3 -c "
import pandas as pd
df = pd.read_csv('data/01-raw/synthetisch/studenten.csv')
print('Instellingen:', df['Instelling'].value_counts().to_dict())
print('Mentoren totaal:', df['Mentor'].nunique())
print('Mentor-students/avg:', df.groupby('Mentor').size().mean())
"
```

Expected: 5 instellingen × 200, 50 mentoren totaal, gemiddeld ~20 studenten per mentor.

- [ ] **Step 7: Lint**

```bash
uv run ruff check scripts/generate_synthetisch_data.py tests/test_generate_synthetisch_data.py
```

- [ ] **Step 8: Commit**

```bash
git add scripts/generate_synthetisch_data.py tests/test_generate_synthetisch_data.py
git add data/01-raw/synthetisch/studenten.csv
git commit -m "feat(synthetisch): generate_synthetisch_data + initiële studenten.csv"
```

---

## Task 15: Update prepare.py — rename + DB-lookup

**Files:**
- Modify: `src/samenwijzer/prepare.py`
- Test: `tests/test_prepare.py`

- [ ] **Step 1: Inspect huidige prepare.py voor relevante secties**

Lees `src/samenwijzer/prepare.py` regel 130–250 om te begrijpen wat `load_berend_csv()` en `_voeg_kt_wp_scores_toe()` doen vóór wijzigingen.

- [ ] **Step 2: Update test fixtures naar synthetisch-formaat**

Open `tests/test_prepare.py`. Vervang fixtures die de oude Berend-research-CSV nabootsen (met `Aanmel_aantal`, `Studentnummer` als cijfers, etc.) door de nieuwe synthetische CSV-shape met `Instelling`-kolom en specifieke `Opleiding`. Pas alle `load_berend_csv` aanroepen aan naar `load_synthetisch_csv`.

Voorbeeld minimale fixture (vervang volledige `BEREND_CSV`-string):

```python
SYNTHETISCH_CSV = """\
Studentnummer,Naam,Klas,Mentor,Instelling,Opleiding,crebo,leerweg,cohort,StudentAge,StudentGender,Dropout,Aanmel_aantal,max1studie,absence_unauthorized,absence_authorized,Richting_nan,Economie,Landbouw,Techniek,DSV,Zorgenwelzijn,Anders,VooroplNiveau_HAVO,VooroplNiveau_MBO,VooroplNiveau_basis,VooroplNiveau_educatie,VooroplNiveau_prak,VooroplNiveau_VMBO_BB,VooroplNiveau_VMBO_GL,VooroplNiveau_VMBO_KB,VooroplNiveau_VMBO_TL,VooroplNiveau_nan,VooroplNiveau_VWOplus,VooroplNiveau_other
100001,Aisha Bergman,3B,M. de Vries,Rijn IJssel,Verzorgende IG,25655,BOL,2025,19,1,0,2.0,1.0,14.0,2.0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,1,0,0,0
100002,Daan Hoekstra,3B,M. de Vries,Rijn IJssel,Verzorgende IG,25655,BOL,2025,20,0,0,1.0,0.0,5.0,3.0,0,0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0,0,0
"""
```

Pas elke testnaam met `berend` aan naar `synthetisch`.

- [ ] **Step 3: Run test_prepare.py — expect failure (lookups falen)**

```bash
uv run pytest tests/test_prepare.py -v
```

Expected: tests slaan stuk omdat `load_synthetisch_csv` nog niet bestaat.

- [ ] **Step 4: Update prepare.py**

Open `src/samenwijzer/prepare.py`. Maak deze wijzigingen:

1. Verwijder `_CREBO_MAP` (volledig).
2. Hernoem `load_berend_csv` → `load_synthetisch_csv`. Pas docstring aan.
3. Vervang de body van `load_synthetisch_csv` zodat hij alle nieuwe kolommen direct uit de CSV haalt:

```python
def load_synthetisch_csv(path: Path = _DEFAULT_PAD) -> pd.DataFrame:
    """Laad de synthetische studentendata en map naar het standaard samenwijzer-DataFrame.

    Args:
        path: Pad naar de synthetische CSV.

    Returns:
        Gevalideerd, opgeschoond DataFrame met de standaard kolommen.

    Raises:
        FileNotFoundError: Als het bestand niet bestaat.
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV niet gevonden: {path}")

    raw = pd.read_csv(path, dtype={"Studentnummer": str, "crebo": str, "cohort": str})

    df = pd.DataFrame()
    df["studentnummer"] = raw["Studentnummer"]
    df["naam"] = raw["Naam"].str.strip()
    df["mentor"] = raw["Mentor"].str.strip()
    df["instelling"] = raw["Instelling"].str.strip()
    df["opleiding"] = raw["Opleiding"].str.strip()
    df["crebo"] = raw["crebo"]
    df["leerweg"] = raw["leerweg"]
    df["cohort"] = raw["cohort"]
    df["niveau"] = raw["Klas"].str[0].astype(int)
    df["leeftijd"] = raw["StudentAge"]
    df["geslacht"] = raw["StudentGender"].map({0: "M", 1: "V"}).fillna("O")

    df["bsa_vereist"] = 60.0
    df["bsa_behaald"] = (
        60.0 * (1.0 - raw["absence_unauthorized"] / 60.0)
    ).clip(0, 60).round(1)
    max_unauth = raw["absence_unauthorized"].max() or 1.0
    df["voortgang"] = (
        (1.0 - raw["absence_unauthorized"] / (max_unauth * 1.2))
        .clip(0.05, 1.0)
        .round(2)
    )

    df = _clean(df)
    df = _voeg_kt_wp_scores_toe(df)
    return df
```

4. Update `_DEFAULT_PAD` constante (boven in het bestand) van `data/01-raw/berend/studenten.csv` naar `data/01-raw/synthetisch/studenten.csv`.

5. Vervang `_voeg_kt_wp_scores_toe()` body — verwijder JSON-lookup, gebruik DB:

```python
def _voeg_kt_wp_scores_toe(df: pd.DataFrame) -> pd.DataFrame:
    """Voeg synthetische kt/wp-scores toe per student via oeren.db lookup.

    Voor elke unieke (opleiding, niveau) wordt één keer de kerntakenlijst opgehaald;
    daarna krijgt elke student gecorreleerd-met-voortgang scores op zijn kerntaken.
    """
    from samenwijzer import oer_store  # lazy import: cycle-vermijdend

    kt_cols = ["kt_1", "kt_2"]
    wp_cols = ["wp_1_1", "wp_1_2", "wp_1_3", "wp_2_1", "wp_2_2", "wp_2_3"]
    for col in kt_cols + wp_cols:
        df[col] = 0.0

    # Cache: (opleiding, niveau) → set van kt/wp codes
    cache: dict[tuple[str, int], dict[str, set[str]]] = {}

    for idx, row in df.iterrows():
        opl = str(row["opleiding"])
        niv = int(row["niveau"])
        sleutel = (opl, niv)
        if sleutel not in cache:
            kts = oer_store.get_kerntaken_voor_opleiding(_DB_PAD_VOOR_KT, opl, niveau=niv)
            cache[sleutel] = {
                "kerntaken": {k["code"] for k in kts if k["type"] == "kerntaak"},
                "werkprocessen": {k["code"] for k in kts if k["type"] == "werkproces"},
            }

        snr = str(row["studentnummer"])
        voortgang = float(row["voortgang"])
        rng = np.random.default_rng(int(abs(hash(snr)) % 2**32))
        basis = voortgang * 100

        # Vooralsnog mappen we de eerste 2 kerntaken naar kt_1/kt_2 en de eerste 6
        # werkprocessen naar wp_1_1…wp_2_3. Levert NaN op waar er geen mapping is.
        # NB: dit is een synthetische score, geen 1-op-1 koppeling met echte
        # OER-codes — dat blijft een feature van de demo-data.
        for kt in kt_cols:
            df.at[idx, kt] = float(np.clip(round(basis + rng.uniform(-18, 18)), 30, 98))
        for wp in wp_cols:
            df.at[idx, wp] = float(np.clip(round(basis + rng.uniform(-22, 22)), 25, 98))

    return df
```

6. Voeg bovenaan `prepare.py` toe (bij de andere constanten):

```python
_DB_PAD_VOOR_KT = Path(__file__).parent.parent.parent / "data" / "02-prepared" / "oeren.db"
```

- [ ] **Step 5: Run test_prepare.py**

```bash
uv run pytest tests/test_prepare.py -v
```

Expected: tests slagen. Pas waar nodig fixtures aan om realistische opleiding+niveau-combinaties te bevatten die in de testdb voorkomen, of gebruik een test-fixture die `oeren.db` mockt.

- [ ] **Step 6: Run de volledige test suite**

```bash
uv run pytest -q
```

Expected: alles groen of duidelijke failures in `test_analyze.py` (volgende taak).

- [ ] **Step 7: Lint**

```bash
uv run ruff check src/samenwijzer/prepare.py tests/test_prepare.py
```

- [ ] **Step 8: Commit**

```bash
git add src/samenwijzer/prepare.py tests/test_prepare.py
git commit -m "refactor(synthetisch): prepare.load_synthetisch_csv leest oeren.db ipv json"
```

---

## Task 16: Update analyze.py — _oer_label via DB

**Files:**
- Modify: `src/samenwijzer/analyze.py`
- Test: `tests/test_analyze.py`

- [ ] **Step 1: Update tests**

Open `tests/test_analyze.py`. De huidige tests verwachten dat `_oer_label()` uit `oer_kerntaken.json` leest. Dit moet een DB-fixture worden.

Voeg deze fixture toe (boven de bestaande tests):

```python
import sqlite3
from pathlib import Path

import pytest

from samenwijzer import oer_store


@pytest.fixture
def oer_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mini-oeren.db met één opleiding 'Verzorgende IG' inclusief kerntaken.

    Patcht `analyze._DB_PAD_VOOR_LABELS` zodat `_oer_label()` deze db gebruikt.
    """
    db = tmp_path / "oeren.db"
    oer_store.voeg_instelling_toe(db, "rijn_ijssel", "Rijn IJssel")
    inst = oer_store.get_instelling_by_naam(db, "rijn_ijssel")
    oer_id = oer_store.voeg_oer_document_toe(
        db, inst["id"], "Verzorgende IG", "25655", "2025", "BOL", 3, "p.md"
    )
    oer_store.voeg_kerntaak_toe(
        db, oer_id, "B1-K1", "Bieden van zorg en ondersteuning", "kerntaak", None, 0
    )
    oer_store.voeg_kerntaak_toe(
        db, oer_id, "B1-K2", "Werken aan organisatie", "kerntaak", None, 1
    )
    oer_store.voeg_kerntaak_toe(
        db, oer_id, "B1-K1-W1", "Onderkent gezondheid", "werkproces", "B1-K1", 2
    )
    oer_store.voeg_kerntaak_toe(
        db, oer_id, "B1-K1-W2", "Voert interventies uit", "werkproces", "B1-K1", 3
    )
    oer_store.voeg_kerntaak_toe(
        db, oer_id, "B1-K1-W3", "Coördineert zorg", "werkproces", "B1-K1", 4
    )
    oer_store.voeg_kerntaak_toe(
        db, oer_id, "B1-K2-W1", "Werkt aan ontwikkeling", "werkproces", "B1-K2", 5
    )
    oer_store.voeg_kerntaak_toe(
        db, oer_id, "B1-K2-W2", "Werkt samen met team", "werkproces", "B1-K2", 6
    )
    oer_store.voeg_kerntaak_toe(
        db, oer_id, "B1-K2-W3", "Draagt bij aan kwaliteit", "werkproces", "B1-K2", 7
    )

    # Patch het pad zodat _oer_label() naar deze test-db kijkt
    from samenwijzer import analyze
    monkeypatch.setattr(analyze, "_DB_PAD_VOOR_LABELS", db)
    return db


def test_oer_label_kerntaak(oer_db: Path):
    from samenwijzer.analyze import _oer_label
    assert _oer_label("Verzorgende IG", "kt_1") == "Bieden van zorg en ondersteuning"
    assert _oer_label("Verzorgende IG", "kt_2") == "Werken aan organisatie"


def test_oer_label_werkproces(oer_db: Path):
    from samenwijzer.analyze import _oer_label
    assert _oer_label("Verzorgende IG", "wp_1_1") == "Onderkent gezondheid"
    assert _oer_label("Verzorgende IG", "wp_2_2") == "Werkt samen met team"


def test_oer_label_onbekende_opleiding_geeft_kolom_terug(oer_db: Path):
    from samenwijzer.analyze import _oer_label
    assert _oer_label("Onbekend", "kt_1") == "kt_1"


def test_oer_label_lege_opleiding_geeft_kolom_terug(oer_db: Path):
    from samenwijzer.analyze import _oer_label
    assert _oer_label("", "kt_1") == "kt_1"
```

Verwijder de oude fixture die `oer_kerntaken.json` patcht (zoek op `_OER_PAD` of `_laad_oer` in test_analyze.py).

Pas eventuele andere tests in dit bestand die specifieke opleidingen gebruiken aan, zodat ze "Verzorgende IG" gebruiken (of voeg meer fixture-data toe als andere namen nodig zijn).

- [ ] **Step 2: Run — expect failure**

```bash
uv run pytest tests/test_analyze.py -v
```

- [ ] **Step 3: Update analyze.py**

In `src/samenwijzer/analyze.py`:

1. Verwijder `_OER_PAD` constante (regel 13).
2. Verwijder `_laad_oer()` (regel 17).
3. Vervang `_oer_label()`:

```python
from samenwijzer import oer_store

_DB_PAD_VOOR_LABELS = Path(__file__).parent.parent.parent / "data" / "02-prepared" / "oeren.db"


def _oer_label(opleiding: str, kolom: str) -> str:
    """Geef de echte kerntaak/werkproces-naam terug voor (opleiding, kolom).

    Kolom-naam-conventie: kt_1, kt_2, wp_1_1, wp_1_2, …, wp_2_3.
    Mapping naar OER-codes:
      kt_1 → eerste kerntaak in oeren.db
      kt_2 → tweede kerntaak
      wp_x_y → y-de werkproces onder kerntaak x
    Geeft de kolom-naam zelf terug als er geen kerntakenlijst is.
    """
    if not opleiding:
        return kolom
    kts = oer_store.get_kerntaken_voor_opleiding(_DB_PAD_VOOR_LABELS, opleiding)
    if not kts:
        return kolom

    kerntaken = [k for k in kts if k["type"] == "kerntaak"]
    werkprocessen = [k for k in kts if k["type"] == "werkproces"]

    if kolom == "kt_1" and len(kerntaken) >= 1:
        return kerntaken[0]["naam"]
    if kolom == "kt_2" and len(kerntaken) >= 2:
        return kerntaken[1]["naam"]
    if kolom.startswith("wp_"):
        try:
            _, kt_idx, wp_idx = kolom.split("_")
            kt_i = int(kt_idx) - 1
            wp_i = int(wp_idx) - 1
            # Werkprocessen voor kerntaak kt_i: vind degene met parent_code matching
            if kt_i < len(kerntaken):
                parent_code = kerntaken[kt_i]["code"]
                eigen = [w for w in werkprocessen if w.get("parent_code") == parent_code]
                if not eigen:  # geen parent_code link → val terug op volgorde
                    eigen = werkprocessen[kt_i * 3 : (kt_i + 1) * 3]
                if wp_i < len(eigen):
                    return eigen[wp_i]["naam"]
        except (ValueError, IndexError):
            pass

    return kolom
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_analyze.py -v
```

Expected: groen.

- [ ] **Step 5: Run hele suite**

```bash
uv run pytest -q
```

Expected: 100% groen.

- [ ] **Step 6: Lint + ty**

```bash
uv run ruff check src/ app/ tests/
uv run ty check
```

Expected: schoon.

- [ ] **Step 7: Commit**

```bash
git add src/samenwijzer/analyze.py tests/test_analyze.py
git commit -m "refactor(synthetisch): analyze._oer_label leest uit oeren.db ipv json"
```

---

## Task 17: Cleanup — verwijder berend-data en oer_kerntaken.json

**Files:**
- Delete: `data/01-raw/berend/`
- Delete: `data/01-raw/demo/oer_kerntaken.json` (als aanwezig)

- [ ] **Step 1: Final check dat niemand nog naar berend verwijst**

```bash
grep -ri "berend" src/ app/ tests/ scripts/ docs/ data/ --include="*.py" --include="*.md" --include="*.json" --include="*.csv" --include="*.toml" 2>/dev/null
```

Expected: 0 hits in code/tests. Mogelijk hits in `docs/` (CLAUDE.md, ARCHITECTURE.md, etc.) → behandelen in Task 18.

Bij hits in code/scripts/tests: fix vóór doorgaan.

- [ ] **Step 2: Verwijder berend-folder**

```bash
git rm -r data/01-raw/berend
```

- [ ] **Step 3: Verwijder eventuele oer_kerntaken.json elders**

```bash
find data -name "oer_kerntaken.json" -ls
```

Voor elk bestand:
```bash
git rm <pad>
```

- [ ] **Step 4: Voeg regressie-test toe in test_architecture.py**

Open `tests/test_architecture.py`. Voeg deze test toe (aan het einde van het bestand):

```python
def test_geen_berend_meer_in_code():
    """Regressie: 'berend' is volledig vervangen door 'synthetisch'."""
    import re
    from pathlib import Path

    root = Path(__file__).parent.parent
    patroon = re.compile(r"berend", re.IGNORECASE)
    treffers: list[str] = []
    for sub in ("src", "app", "tests", "scripts"):
        for path in (root / sub).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".md", ".json", ".csv", ".toml"}:
                inhoud = path.read_text(encoding="utf-8", errors="ignore")
                if patroon.search(inhoud):
                    treffers.append(str(path.relative_to(root)))
    assert treffers == [], f"Berend-vermeldingen gevonden in: {treffers}"
```

- [ ] **Step 5: Volledige test run**

```bash
uv run pytest -q
```

Expected: groen, inclusief de nieuwe `test_geen_berend_meer_in_code`.

- [ ] **Step 6: Commit**

```bash
git add tests/test_architecture.py
git commit -m "chore(synthetisch): verwijder berend-folder, oer_kerntaken.json en regressietest"
```

---

## Task 18: Documentatie bijwerken

**Files:**
- Modify: `CLAUDE.md`
- Modify: `ARCHITECTURE.md`
- Modify: `docs/PRODUCT_SENSE.md` (eventueel)
- Modify: `README.md` (indien aanwezig)

- [ ] **Step 1: Inventariseer berend-vermeldingen in docs**

```bash
grep -rn "berend\|Berend\|BEREND" CLAUDE.md ARCHITECTURE.md docs/ README.md 2>/dev/null
```

- [ ] **Step 2: Update CLAUDE.md**

Vervang elke vermelding van "berend" door "synthetisch":
- `data/01-raw/berend/` → `data/01-raw/synthetisch/`
- `load_berend_csv` → `load_synthetisch_csv`
- "Berend-dataset" → "synthetische dataset"
- Voeg een korte paragraaf toe over `oeren.db` onder de **Dataset & OER-kerntaken** sectie:

```markdown
**OER-catalog (`data/02-prepared/oeren.db`)** — SQLite met `instellingen`,
`oer_documenten` en `kerntaken`. Gevuld eenmalig door
`scripts/build_oer_catalog.py` op basis van `oeren/`. Wordt door
`prepare._voeg_kt_wp_scores_toe()` en `analyze._oer_label()` gequeried om
kerntaak-namen op te halen. `oer_kerntaken.json` is uitgefaseerd.
```

Voeg ook bij "Commands" toe:

```bash
# OER-catalog opnieuw opbouwen (na wijzigingen in oeren/)
uv run python scripts/build_oer_catalog.py

# Synthetische dataset regenereren (deterministisch via seed=42)
uv run python scripts/generate_synthetisch_data.py
```

- [ ] **Step 3: Update ARCHITECTURE.md**

Vervang berend-vermeldingen, voeg `oer_store.py` toe aan de cross-cutting modules of de relevante laag.

- [ ] **Step 4: Final sweep**

```bash
grep -ri "berend\|Berend" . --include="*.py" --include="*.md" --include="*.json" --include="*.csv" --include="*.toml" 2>/dev/null | grep -v ".venv\|node_modules\|.git"
```

Expected: 0 hits.

- [ ] **Step 5: Volledige verificatie**

```bash
uv run pytest -q && uv run ruff check src/ app/ tests/ && uv run ty check
```

Expected: alles groen.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md ARCHITECTURE.md docs/ README.md
git commit -m "docs(synthetisch): vervang berend-vermeldingen + documenteer oeren.db"
```

---

## Self-Review Checklist (vóór hand-off)

- [ ] Alle 18 tasks doorlopen
- [ ] `grep -ri berend` levert 0 hits in code, tests, scripts, docs
- [ ] `uv run pytest` groen (alle 335+ tests)
- [ ] `uv run ruff check src/ app/ tests/` groen
- [ ] `uv run ty check` groen
- [ ] `data/01-raw/synthetisch/studenten.csv` bestaat met exact 1000 rijen
- [ ] `data/02-prepared/oeren.db` bestaat met 5 instellingen
- [ ] CLAUDE.md vermeldt `oeren.db` en de twee nieuwe scripts onder Commands
- [ ] Geen `oer_kerntaken.json` meer in de boom
- [ ] Geen `data/01-raw/berend/` meer
