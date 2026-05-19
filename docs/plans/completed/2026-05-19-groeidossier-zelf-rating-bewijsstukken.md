# Groeidossier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Voeg een groeidossier-pagina toe aan samenwijzer waarin studenten per werkproces zelf een score (0–100) en verantwoording invullen, bewijsstukken uploaden, en hun groei over tijd zien — met mentor-feedback per kerntaak en een AI-knop die de verantwoording aanscherpt.

**Architecture:** Nieuwe laag `groei` (groei.py + groei_store.py + bewijsstuk_store.py) naast `welzijn`/`outreach`. SQLite-DB `data/02-prepared/groei.db` met tabellen `groei_actueel`, `groei_historie`, `mentor_feedback`, `bewijsstuk`. Bestandsuploads onder `data/bewijsstukken/<studentnummer>/<uuid>.<ext>`. Zelf-scores overlayen via `prepare.load_synthetisch_csv()` zodat alle bestaande dashboards automatisch meeprofiteren. Streamlit-pagina `app/pages/6_groeidossier.py` is rol-gestuurd.

**Tech Stack:** Python 3.13 · Streamlit · pandas · SQLite (stdlib) · Altair · Anthropic SDK · pytest · ruff · ty · uv.

**Spec:** `docs/specs/2026-05-19-groeidossier-zelf-rating-bewijsstukken-design.md`

---

## File Structure

**Nieuw:**
- `src/samenwijzer/groei.py` — business-logic (aggregatie kt-score, overlay, delta).
- `src/samenwijzer/groei_store.py` — SQLite-CRUD voor groei.db.
- `src/samenwijzer/bewijsstuk_store.py` — filesystem-IO voor bewijsstukken.
- `app/pages/6_groeidossier.py` — Streamlit-UI (student- en docent-view).
- `tests/test_groei.py`
- `tests/test_groei_store.py`
- `tests/test_bewijsstuk_store.py`

**Gewijzigd:**
- `src/samenwijzer/prepare.py` — `load_synthetisch_csv()` past `groei.overlay_self_scores(df)` toe na laden.
- `src/samenwijzer/tutor.py` — nieuwe functie `aanscherp_verantwoording()`.
- `src/samenwijzer/styles.py` — nav uitbreiden met "Groeidossier"-link in student- én docent-nav.
- `app/pages/1_mijn_voortgang.py` — bron-badge ("Zelf beoordeeld op …" / "Schatting op basis van OER").
- `tests/test_architecture.py` — `groei` + `groei_store` + `bewijsstuk_store` toevoegen aan laag-checks.
- `.gitignore` — `data/02-prepared/groei.db*` en `data/bewijsstukken/`.

---

### Task 1: Gitignore + directory-scaffolding

**Files:**
- Modify: `.gitignore`
- Create: `data/bewijsstukken/.gitkeep`

- [ ] **Step 1: Open .gitignore en controleer of de groei-paden ontbreken**

Run: `grep -E 'groei.db|bewijsstukken' .gitignore || echo "ontbreekt"`
Expected: `ontbreekt`

- [ ] **Step 2: Voeg de patronen toe**

Edit `.gitignore` — voeg onder de bestaande `data/02-prepared/*.db`-regels (of waar `outreach.db` staat) toe:

```
# Groeidossier
data/02-prepared/groei.db
data/02-prepared/groei.db-journal
data/bewijsstukken/*
!data/bewijsstukken/.gitkeep
```

Als er al een `data/02-prepared/*.db` glob staat, alleen de `data/bewijsstukken/`-blok toevoegen.

- [ ] **Step 3: Maak de bewijsstukken-folder en .gitkeep**

Run: `mkdir -p data/bewijsstukken && touch data/bewijsstukken/.gitkeep`
Expected: geen output

- [ ] **Step 4: Verifieer dat gitignore werkt**

Run: `touch data/bewijsstukken/test.pdf && git check-ignore data/bewijsstukken/test.pdf && rm data/bewijsstukken/test.pdf`
Expected: `data/bewijsstukken/test.pdf` (gevolgd door successful exit)

- [ ] **Step 5: Commit**

```bash
git add .gitignore data/bewijsstukken/.gitkeep
git commit -m "chore(groei): gitignore + bewijsstukken-folder voor groeidossier"
```

---

### Task 2: groei_store — schema + dataclasses + init_db

**Files:**
- Create: `src/samenwijzer/groei_store.py`
- Create: `tests/test_groei_store.py`

- [ ] **Step 1: Schrijf de failing test voor init_db**

Maak `tests/test_groei_store.py`:

```python
"""Tests voor samenwijzer.groei_store."""

import sqlite3
from pathlib import Path

import pytest

from samenwijzer.groei_store import (
    BewijsstukMeta,
    GroeiActueel,
    GroeiHistorieRij,
    MentorFeedback,
    init_db,
)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    pad = tmp_path / "test_groei.db"
    init_db(pad)
    return pad


def test_init_db_maakt_alle_tabellen(db: Path) -> None:
    with sqlite3.connect(db) as conn:
        tabellen = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "groei_actueel" in tabellen
    assert "groei_historie" in tabellen
    assert "mentor_feedback" in tabellen
    assert "bewijsstuk" in tabellen


def test_init_db_idempotent(db: Path) -> None:
    init_db(db)  # mag geen fout opleveren bij tweede call
    with sqlite3.connect(db) as conn:
        n = conn.execute("SELECT COUNT(*) FROM groei_actueel").fetchone()[0]
    assert n == 0
```

- [ ] **Step 2: Run de test — verifieer dat hij faalt**

Run: `uv run pytest tests/test_groei_store.py -v`
Expected: `ImportError: cannot import name 'init_db' from 'samenwijzer.groei_store'`

- [ ] **Step 3: Schrijf groei_store.py — schema + dataclasses + helpers**

Maak `src/samenwijzer/groei_store.py`:

```python
"""Persistente opslag voor het groeidossier via SQLite."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "02-prepared" / "groei.db"

_geinitialiseerd: set[Path] = set()


@contextmanager
def _verbinding(db_path: Path) -> Generator[sqlite3.Connection]:
    """Open een SQLite-verbinding en sluit hem gegarandeerd na gebruik."""
    conn = sqlite3.connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@dataclass
class GroeiActueel:
    studentnummer: str
    wp_kolom: str
    score: int
    verantwoording: str
    laatst_gewijzigd: str


@dataclass
class GroeiHistorieRij:
    studentnummer: str
    wp_kolom: str
    score: int
    verantwoording: str
    opgeslagen_op: str
    id: int | None = None


@dataclass
class MentorFeedback:
    studentnummer: str
    kt_kolom: str
    mentor_naam: str
    tekst: str
    geschreven_op: str


@dataclass
class BewijsstukMeta:
    studentnummer: str
    bestandsnaam: str
    bestandspad: str
    mime_type: str
    grootte_bytes: int
    geupload_op: str
    wp_kolom: str | None = None
    kt_kolom: str | None = None
    toelichting: str = ""
    id: int | None = None


def init_db(db_path: Path = _DB_PATH) -> None:
    """Maak groei.db en alle tabellen aan als ze nog niet bestaan."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _verbinding(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS groei_actueel (
                studentnummer    TEXT NOT NULL,
                wp_kolom         TEXT NOT NULL,
                score            INTEGER NOT NULL,
                verantwoording   TEXT NOT NULL DEFAULT '',
                laatst_gewijzigd TEXT NOT NULL,
                PRIMARY KEY (studentnummer, wp_kolom)
            );
            CREATE TABLE IF NOT EXISTS groei_historie (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                studentnummer    TEXT NOT NULL,
                wp_kolom         TEXT NOT NULL,
                score            INTEGER NOT NULL,
                verantwoording   TEXT NOT NULL,
                opgeslagen_op    TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_historie_student
                ON groei_historie(studentnummer, opgeslagen_op);
            CREATE TABLE IF NOT EXISTS mentor_feedback (
                studentnummer  TEXT NOT NULL,
                kt_kolom       TEXT NOT NULL,
                mentor_naam    TEXT NOT NULL,
                tekst          TEXT NOT NULL,
                geschreven_op  TEXT NOT NULL,
                PRIMARY KEY (studentnummer, kt_kolom)
            );
            CREATE TABLE IF NOT EXISTS bewijsstuk (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                studentnummer   TEXT NOT NULL,
                wp_kolom        TEXT,
                kt_kolom        TEXT,
                bestandsnaam    TEXT NOT NULL,
                bestandspad     TEXT NOT NULL,
                mime_type       TEXT NOT NULL,
                grootte_bytes   INTEGER NOT NULL,
                toelichting     TEXT NOT NULL DEFAULT '',
                geupload_op     TEXT NOT NULL,
                CHECK (wp_kolom IS NOT NULL OR kt_kolom IS NOT NULL)
            );
            CREATE INDEX IF NOT EXISTS idx_bewijs_student
                ON bewijsstuk(studentnummer);
        """)
    _geinitialiseerd.add(db_path)


def _zorg_voor_db(db_path: Path) -> None:
    """Initialiseer de database eenmalig per pad per proces."""
    if db_path not in _geinitialiseerd:
        init_db(db_path)
```

- [ ] **Step 4: Run de test — verifieer dat hij slaagt**

Run: `uv run pytest tests/test_groei_store.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/samenwijzer/groei_store.py tests/test_groei_store.py
git commit -m "feat(groei): SQLite-schema + dataclasses voor groei.db"
```

---

### Task 3: groei_store — CRUD voor groei_actueel + groei_historie

**Files:**
- Modify: `src/samenwijzer/groei_store.py`
- Modify: `tests/test_groei_store.py`

- [ ] **Step 1: Voeg failing tests toe voor atomic save + read**

Append aan `tests/test_groei_store.py`:

```python
def test_sla_groei_op_schrijft_actueel_en_historie(db: Path) -> None:
    from samenwijzer.groei_store import get_actueel, get_historie, sla_groei_op

    rijen = [
        GroeiActueel("S001", "wp_1_1", 60, "ik kan dit", "2026-05-19T10:00:00"),
        GroeiActueel("S001", "wp_1_2", 75, "soms", "2026-05-19T10:00:00"),
    ]
    sla_groei_op("S001", rijen, db)

    actueel = get_actueel("S001", db)
    assert {r.wp_kolom for r in actueel} == {"wp_1_1", "wp_1_2"}
    assert next(r for r in actueel if r.wp_kolom == "wp_1_1").score == 60

    historie = get_historie("S001", db)
    assert len(historie) == 2


def test_sla_groei_op_upserts_en_voegt_historie_toe(db: Path) -> None:
    from samenwijzer.groei_store import get_actueel, get_historie, sla_groei_op

    sla_groei_op(
        "S001",
        [GroeiActueel("S001", "wp_1_1", 40, "v1", "2026-05-19T10:00:00")],
        db,
    )
    sla_groei_op(
        "S001",
        [GroeiActueel("S001", "wp_1_1", 70, "v2", "2026-05-19T11:00:00")],
        db,
    )

    actueel = get_actueel("S001", db)
    assert len(actueel) == 1
    assert actueel[0].score == 70
    assert actueel[0].verantwoording == "v2"

    historie = get_historie("S001", db)
    assert len(historie) == 2
    assert {h.score for h in historie} == {40, 70}


def test_sla_groei_op_is_atomic_bij_fout(db: Path) -> None:
    """Als een rij in de batch ongeldig is, mag geen enkele wijziging blijven hangen."""
    from samenwijzer.groei_store import get_actueel, sla_groei_op

    rijen = [
        GroeiActueel("S001", "wp_1_1", 50, "ok", "2026-05-19T10:00:00"),
        GroeiActueel("S001", "wp_1_1", None, "fout", "2026-05-19T10:00:00"),  # type: ignore[arg-type]
    ]
    with pytest.raises(sqlite3.IntegrityError):
        sla_groei_op("S001", rijen, db)

    actueel = get_actueel("S001", db)
    assert actueel == []


def test_get_actueel_voor_onbekende_student(db: Path) -> None:
    from samenwijzer.groei_store import get_actueel

    assert get_actueel("S999", db) == []
```

- [ ] **Step 2: Run de tests — verifieer dat ze falen**

Run: `uv run pytest tests/test_groei_store.py -v`
Expected: ImportError op `sla_groei_op`.

- [ ] **Step 3: Voeg sla_groei_op + getters toe aan groei_store.py**

Append aan `src/samenwijzer/groei_store.py`:

```python
def sla_groei_op(
    studentnummer: str,
    rijen: list[GroeiActueel],
    db_path: Path = _DB_PATH,
) -> None:
    """Sla een batch wp-scores in één transactie op (upsert actueel + insert historie).

    Bij elke wp wordt een snapshot in groei_historie geschreven, zodat de
    voortgang over tijd te volgen is.
    """
    _zorg_voor_db(db_path)
    with _verbinding(db_path) as conn:
        for rij in rijen:
            conn.execute(
                """
                INSERT INTO groei_actueel
                    (studentnummer, wp_kolom, score, verantwoording, laatst_gewijzigd)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(studentnummer, wp_kolom) DO UPDATE SET
                    score = excluded.score,
                    verantwoording = excluded.verantwoording,
                    laatst_gewijzigd = excluded.laatst_gewijzigd
                """,
                (
                    studentnummer,
                    rij.wp_kolom,
                    rij.score,
                    rij.verantwoording,
                    rij.laatst_gewijzigd,
                ),
            )
            conn.execute(
                """
                INSERT INTO groei_historie
                    (studentnummer, wp_kolom, score, verantwoording, opgeslagen_op)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    studentnummer,
                    rij.wp_kolom,
                    rij.score,
                    rij.verantwoording,
                    rij.laatst_gewijzigd,
                ),
            )


def get_actueel(studentnummer: str, db_path: Path = _DB_PATH) -> list[GroeiActueel]:
    """Geef de huidige wp-scores van een student als lijst (leeg = nog niets opgeslagen)."""
    _zorg_voor_db(db_path)
    with _verbinding(db_path) as conn:
        rows = conn.execute(
            """
            SELECT studentnummer, wp_kolom, score, verantwoording, laatst_gewijzigd
            FROM groei_actueel
            WHERE studentnummer = ?
            ORDER BY wp_kolom
            """,
            (studentnummer,),
        ).fetchall()
    return [GroeiActueel(*r) for r in rows]


def get_alle_actueel(db_path: Path = _DB_PATH) -> dict[str, list[GroeiActueel]]:
    """Geef alle actuele scores als dict (studentnummer → lijst). Voor overlay op df."""
    _zorg_voor_db(db_path)
    with _verbinding(db_path) as conn:
        rows = conn.execute(
            "SELECT studentnummer, wp_kolom, score, verantwoording, laatst_gewijzigd "
            "FROM groei_actueel"
        ).fetchall()
    resultaat: dict[str, list[GroeiActueel]] = {}
    for r in rows:
        resultaat.setdefault(r[0], []).append(GroeiActueel(*r))
    return resultaat


def get_historie(studentnummer: str, db_path: Path = _DB_PATH) -> list[GroeiHistorieRij]:
    """Geef de volledige historie van een student, oudste eerst."""
    _zorg_voor_db(db_path)
    with _verbinding(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, studentnummer, wp_kolom, score, verantwoording, opgeslagen_op
            FROM groei_historie
            WHERE studentnummer = ?
            ORDER BY opgeslagen_op ASC, id ASC
            """,
            (studentnummer,),
        ).fetchall()
    return [
        GroeiHistorieRij(
            id=r[0],
            studentnummer=r[1],
            wp_kolom=r[2],
            score=r[3],
            verantwoording=r[4],
            opgeslagen_op=r[5],
        )
        for r in rows
    ]
```

- [ ] **Step 4: Run de tests — verifieer dat ze slagen**

Run: `uv run pytest tests/test_groei_store.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/samenwijzer/groei_store.py tests/test_groei_store.py
git commit -m "feat(groei): atomic sla_groei_op + getters voor actueel/historie"
```

---

### Task 4: groei_store — mentor_feedback + bewijsstuk-metadata CRUD

**Files:**
- Modify: `src/samenwijzer/groei_store.py`
- Modify: `tests/test_groei_store.py`

- [ ] **Step 1: Schrijf failing tests voor mentor_feedback + bewijsstuk-metadata**

Append aan `tests/test_groei_store.py`:

```python
def test_upsert_mentor_feedback_en_lezen(db: Path) -> None:
    from samenwijzer.groei_store import get_mentor_feedback, upsert_mentor_feedback

    upsert_mentor_feedback(
        MentorFeedback("S001", "kt_1", "Jan Jansen", "Mooie groei!", "2026-05-19T10:00:00"),
        db,
    )
    fb = get_mentor_feedback("S001", db)
    assert fb["kt_1"].tekst == "Mooie groei!"

    upsert_mentor_feedback(
        MentorFeedback("S001", "kt_1", "Jan Jansen", "Update", "2026-05-19T11:00:00"),
        db,
    )
    fb = get_mentor_feedback("S001", db)
    assert fb["kt_1"].tekst == "Update"


def test_bewijsstuk_insert_en_lijst(db: Path) -> None:
    from samenwijzer.groei_store import (
        get_bewijsstukken,
        insert_bewijsstuk,
        verwijder_bewijsstuk,
    )

    meta = BewijsstukMeta(
        studentnummer="S001",
        wp_kolom="wp_1_1",
        bestandsnaam="stage.pdf",
        bestandspad="S001/abc.pdf",
        mime_type="application/pdf",
        grootte_bytes=12345,
        toelichting="stageverslag",
        geupload_op="2026-05-19T10:00:00",
    )
    bewijsstuk_id = insert_bewijsstuk(meta, db)
    assert bewijsstuk_id > 0

    lijst = get_bewijsstukken("S001", db)
    assert len(lijst) == 1
    assert lijst[0].bestandsnaam == "stage.pdf"
    assert lijst[0].id == bewijsstuk_id

    verwijder_bewijsstuk(bewijsstuk_id, db)
    assert get_bewijsstukken("S001", db) == []


def test_bewijsstuk_zonder_wp_of_kt_geweigerd(db: Path) -> None:
    from samenwijzer.groei_store import insert_bewijsstuk

    meta = BewijsstukMeta(
        studentnummer="S001",
        bestandsnaam="losse.pdf",
        bestandspad="S001/zzz.pdf",
        mime_type="application/pdf",
        grootte_bytes=1,
        geupload_op="2026-05-19T10:00:00",
    )
    with pytest.raises(sqlite3.IntegrityError):
        insert_bewijsstuk(meta, db)
```

- [ ] **Step 2: Run tests — verifieer falen**

Run: `uv run pytest tests/test_groei_store.py -v`
Expected: ImportError op `upsert_mentor_feedback`.

- [ ] **Step 3: Voeg de functies toe aan groei_store.py**

Append aan `src/samenwijzer/groei_store.py`:

```python
def upsert_mentor_feedback(feedback: MentorFeedback, db_path: Path = _DB_PATH) -> None:
    """Schrijf of update de mentor-feedback voor één kerntaak."""
    _zorg_voor_db(db_path)
    with _verbinding(db_path) as conn:
        conn.execute(
            """
            INSERT INTO mentor_feedback
                (studentnummer, kt_kolom, mentor_naam, tekst, geschreven_op)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(studentnummer, kt_kolom) DO UPDATE SET
                mentor_naam = excluded.mentor_naam,
                tekst = excluded.tekst,
                geschreven_op = excluded.geschreven_op
            """,
            (
                feedback.studentnummer,
                feedback.kt_kolom,
                feedback.mentor_naam,
                feedback.tekst,
                feedback.geschreven_op,
            ),
        )


def get_mentor_feedback(
    studentnummer: str,
    db_path: Path = _DB_PATH,
) -> dict[str, MentorFeedback]:
    """Geef alle mentor-feedback van een student als dict (kt_kolom → MentorFeedback)."""
    _zorg_voor_db(db_path)
    with _verbinding(db_path) as conn:
        rows = conn.execute(
            """
            SELECT studentnummer, kt_kolom, mentor_naam, tekst, geschreven_op
            FROM mentor_feedback WHERE studentnummer = ?
            """,
            (studentnummer,),
        ).fetchall()
    return {r[1]: MentorFeedback(*r) for r in rows}


def insert_bewijsstuk(meta: BewijsstukMeta, db_path: Path = _DB_PATH) -> int:
    """Sla bewijsstuk-metadata op en geef het AUTOINCREMENT-id terug."""
    _zorg_voor_db(db_path)
    with _verbinding(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO bewijsstuk
                (studentnummer, wp_kolom, kt_kolom, bestandsnaam, bestandspad,
                 mime_type, grootte_bytes, toelichting, geupload_op)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                meta.studentnummer,
                meta.wp_kolom,
                meta.kt_kolom,
                meta.bestandsnaam,
                meta.bestandspad,
                meta.mime_type,
                meta.grootte_bytes,
                meta.toelichting,
                meta.geupload_op,
            ),
        )
        new_id = cur.lastrowid
    assert new_id is not None
    return new_id


def get_bewijsstukken(
    studentnummer: str,
    db_path: Path = _DB_PATH,
) -> list[BewijsstukMeta]:
    """Geef alle bewijsstukken van een student, nieuwste eerst."""
    _zorg_voor_db(db_path)
    with _verbinding(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, studentnummer, wp_kolom, kt_kolom, bestandsnaam, bestandspad,
                   mime_type, grootte_bytes, toelichting, geupload_op
            FROM bewijsstuk WHERE studentnummer = ?
            ORDER BY geupload_op DESC, id DESC
            """,
            (studentnummer,),
        ).fetchall()
    return [
        BewijsstukMeta(
            id=r[0],
            studentnummer=r[1],
            wp_kolom=r[2],
            kt_kolom=r[3],
            bestandsnaam=r[4],
            bestandspad=r[5],
            mime_type=r[6],
            grootte_bytes=r[7],
            toelichting=r[8],
            geupload_op=r[9],
        )
        for r in rows
    ]


def verwijder_bewijsstuk(bewijsstuk_id: int, db_path: Path = _DB_PATH) -> None:
    """Verwijder bewijsstuk-metadata (filesystem-cleanup gebeurt in bewijsstuk_store)."""
    _zorg_voor_db(db_path)
    with _verbinding(db_path) as conn:
        conn.execute("DELETE FROM bewijsstuk WHERE id = ?", (bewijsstuk_id,))


def get_bewijsstuk(bewijsstuk_id: int, db_path: Path = _DB_PATH) -> BewijsstukMeta | None:
    """Haal één bewijsstuk op via id (None als niet gevonden)."""
    _zorg_voor_db(db_path)
    with _verbinding(db_path) as conn:
        r = conn.execute(
            """
            SELECT id, studentnummer, wp_kolom, kt_kolom, bestandsnaam, bestandspad,
                   mime_type, grootte_bytes, toelichting, geupload_op
            FROM bewijsstuk WHERE id = ?
            """,
            (bewijsstuk_id,),
        ).fetchone()
    if r is None:
        return None
    return BewijsstukMeta(
        id=r[0],
        studentnummer=r[1],
        wp_kolom=r[2],
        kt_kolom=r[3],
        bestandsnaam=r[4],
        bestandspad=r[5],
        mime_type=r[6],
        grootte_bytes=r[7],
        toelichting=r[8],
        geupload_op=r[9],
    )
```

- [ ] **Step 4: Run tests — verifieer dat ze slagen**

Run: `uv run pytest tests/test_groei_store.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/samenwijzer/groei_store.py tests/test_groei_store.py
git commit -m "feat(groei): mentor-feedback + bewijsstuk-metadata CRUD"
```

---

### Task 5: bewijsstuk_store — filesystem-IO met path-traversal-bescherming

**Files:**
- Create: `src/samenwijzer/bewijsstuk_store.py`
- Create: `tests/test_bewijsstuk_store.py`

- [ ] **Step 1: Schrijf failing tests**

Maak `tests/test_bewijsstuk_store.py`:

```python
"""Tests voor samenwijzer.bewijsstuk_store."""

from pathlib import Path

import pytest

from samenwijzer.bewijsstuk_store import (
    MAX_GROOTTE_BYTES,
    TOEGESTANE_EXTENSIES,
    BewijsstukFout,
    open_bestand,
    opslaan,
    verwijderen,
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "bewijsstukken"


def test_opslaan_legt_bestand_in_studentmap(root: Path) -> None:
    pad = opslaan(
        studentnummer="S001",
        bestandsnaam="stage.pdf",
        inhoud=b"%PDF-1.4 dummy",
        root=root,
    )
    abs_pad = root / pad
    assert abs_pad.exists()
    assert abs_pad.read_bytes() == b"%PDF-1.4 dummy"
    assert pad.startswith("S001/")
    assert pad.endswith(".pdf")


def test_opslaan_genereert_uuid_naam_dus_geen_collisions(root: Path) -> None:
    pad_a = opslaan("S001", "zelfde.pdf", b"a", root=root)
    pad_b = opslaan("S001", "zelfde.pdf", b"b", root=root)
    assert pad_a != pad_b


def test_opslaan_weigert_ongeldige_extensie(root: Path) -> None:
    with pytest.raises(BewijsstukFout, match="extensie"):
        opslaan("S001", "virus.exe", b"x", root=root)


def test_opslaan_weigert_grootte_boven_limiet(root: Path) -> None:
    inhoud = b"x" * (MAX_GROOTTE_BYTES + 1)
    with pytest.raises(BewijsstukFout, match="grootte"):
        opslaan("S001", "groot.pdf", inhoud, root=root)


def test_opslaan_weigert_ongeldig_studentnummer(root: Path) -> None:
    with pytest.raises(BewijsstukFout, match="studentnummer"):
        opslaan("../etc", "x.pdf", b"x", root=root)


def test_open_bestand_buiten_root_geweigerd(root: Path, tmp_path: Path) -> None:
    buiten = tmp_path / "buiten.pdf"
    buiten.write_bytes(b"geheim")
    with pytest.raises(BewijsstukFout, match="buiten"):
        open_bestand("../buiten.pdf", root=root)


def test_verwijderen_verwijdert_bestand(root: Path) -> None:
    pad = opslaan("S001", "weg.pdf", b"x", root=root)
    verwijderen(pad, root=root)
    assert not (root / pad).exists()


def test_verwijderen_van_pad_buiten_root_geweigerd(root: Path) -> None:
    with pytest.raises(BewijsstukFout, match="buiten"):
        verwijderen("../buiten.pdf", root=root)


def test_toegestane_extensies_zijn_pdf_jpg_png_docx_xlsx() -> None:
    assert TOEGESTANE_EXTENSIES == frozenset({".pdf", ".jpg", ".jpeg", ".png", ".docx", ".xlsx"})
```

- [ ] **Step 2: Run de tests — verifieer dat ze falen**

Run: `uv run pytest tests/test_bewijsstuk_store.py -v`
Expected: ImportError op `samenwijzer.bewijsstuk_store`.

- [ ] **Step 3: Schrijf bewijsstuk_store.py**

Maak `src/samenwijzer/bewijsstuk_store.py`:

```python
"""Filesystem-IO voor bewijsstukken — opslag onder data/bewijsstukken/<studentnummer>/."""

import re
import uuid
from pathlib import Path

_DEFAULT_ROOT = Path(__file__).parent.parent.parent / "data" / "bewijsstukken"

MAX_GROOTTE_BYTES = 10 * 1024 * 1024  # 10 MB
TOEGESTANE_EXTENSIES: frozenset[str] = frozenset(
    {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".xlsx"}
)

_STUDENTNUMMER_PATROON = re.compile(r"^[A-Za-z0-9]{1,20}$")


class BewijsstukFout(ValueError):
    """Validatiefout bij opslaan/openen van bewijsstuk."""


def _valideer_studentnummer(studentnummer: str) -> None:
    if not _STUDENTNUMMER_PATROON.match(studentnummer):
        raise BewijsstukFout(f"Ongeldig studentnummer: {studentnummer!r}")


def _resolve_in_root(relatief_pad: str, root: Path) -> Path:
    """Resolve relatief pad onder root; raise BewijsstukFout bij traversal."""
    root = root.resolve()
    abs_pad = (root / relatief_pad).resolve()
    if not abs_pad.is_relative_to(root):
        raise BewijsstukFout(f"Pad {relatief_pad!r} valt buiten bewijsstukken-root")
    return abs_pad


def opslaan(
    studentnummer: str,
    bestandsnaam: str,
    inhoud: bytes,
    root: Path = _DEFAULT_ROOT,
) -> str:
    """Sla een bewijsstuk op onder <root>/<studentnummer>/<uuid>.<ext>.

    Returns:
        Relatief pad t.o.v. root (bv. 'S001/abc-123.pdf') — sla dit op in groei.db.

    Raises:
        BewijsstukFout: Bij ongeldige studentnummer, extensie of grootte.
    """
    _valideer_studentnummer(studentnummer)

    extensie = Path(bestandsnaam).suffix.lower()
    if extensie not in TOEGESTANE_EXTENSIES:
        raise BewijsstukFout(
            f"Bestandsextensie {extensie!r} niet toegestaan. "
            f"Toegestaan: {sorted(TOEGESTANE_EXTENSIES)}"
        )

    if len(inhoud) > MAX_GROOTTE_BYTES:
        raise BewijsstukFout(
            f"Bestand is {len(inhoud)} bytes; maximale grootte is {MAX_GROOTTE_BYTES}."
        )

    student_dir = root / studentnummer
    student_dir.mkdir(parents=True, exist_ok=True)

    nieuwe_naam = f"{uuid.uuid4().hex}{extensie}"
    abs_pad = student_dir / nieuwe_naam
    abs_pad.write_bytes(inhoud)

    return f"{studentnummer}/{nieuwe_naam}"


def open_bestand(relatief_pad: str, root: Path = _DEFAULT_ROOT) -> bytes:
    """Lees een opgeslagen bewijsstuk via zijn relatieve pad.

    Raises:
        BewijsstukFout: Als het pad buiten root valt.
        FileNotFoundError: Als het bestand niet (meer) bestaat.
    """
    abs_pad = _resolve_in_root(relatief_pad, root)
    return abs_pad.read_bytes()


def verwijderen(relatief_pad: str, root: Path = _DEFAULT_ROOT) -> None:
    """Verwijder een bewijsstuk; idempotent als het bestand al weg is.

    Raises:
        BewijsstukFout: Als het pad buiten root valt.
    """
    abs_pad = _resolve_in_root(relatief_pad, root)
    abs_pad.unlink(missing_ok=True)
```

- [ ] **Step 4: Run tests — verifieer dat ze slagen**

Run: `uv run pytest tests/test_bewijsstuk_store.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/samenwijzer/bewijsstuk_store.py tests/test_bewijsstuk_store.py
git commit -m "feat(groei): bewijsstuk_store met path-traversal-bescherming"
```

---

### Task 6: groei — business-logic (overlay + kt-aggregatie + delta)

**Files:**
- Create: `src/samenwijzer/groei.py`
- Create: `tests/test_groei.py`

- [ ] **Step 1: Schrijf failing tests**

Maak `tests/test_groei.py`:

```python
"""Tests voor samenwijzer.groei."""

from pathlib import Path

import pandas as pd
import pytest

from samenwijzer.groei import (
    bereken_kt_uit_wp,
    delta_t_o_v_vorige,
    overlay_self_scores,
)
from samenwijzer.groei_store import GroeiActueel, init_db, sla_groei_op


@pytest.fixture
def db(tmp_path: Path) -> Path:
    pad = tmp_path / "test_groei.db"
    init_db(pad)
    return pad


def _basisrij(studentnummer: str, **kwargs: object) -> dict[str, object]:
    rij: dict[str, object] = {
        "studentnummer": studentnummer,
        "kt_1": 30.0,
        "kt_2": 40.0,
        "wp_1_1": 30.0,
        "wp_1_2": 30.0,
        "wp_1_3": 30.0,
        "wp_2_1": 40.0,
        "wp_2_2": 40.0,
        "wp_2_3": 40.0,
    }
    rij.update(kwargs)
    return rij


def test_bereken_kt_uit_wp_neemt_gemiddelde() -> None:
    rij = pd.Series(_basisrij("S001", wp_1_1=60.0, wp_1_2=80.0, wp_1_3=70.0))
    assert bereken_kt_uit_wp(rij, kt_index=1) == pytest.approx(70.0)


def test_bereken_kt_uit_wp_negeert_nan() -> None:
    rij = pd.Series(_basisrij("S001", wp_1_1=60.0, wp_1_2=float("nan"), wp_1_3=80.0))
    assert bereken_kt_uit_wp(rij, kt_index=1) == pytest.approx(70.0)


def test_overlay_self_scores_overschrijft_synthetisch(db: Path) -> None:
    df = pd.DataFrame([_basisrij("S001"), _basisrij("S002")])
    sla_groei_op(
        "S001",
        [
            GroeiActueel("S001", "wp_1_1", 90, "ik kan dit", "2026-05-19T10:00:00"),
            GroeiActueel("S001", "wp_1_2", 80, "soms", "2026-05-19T10:00:00"),
            GroeiActueel("S001", "wp_1_3", 70, "vaak", "2026-05-19T10:00:00"),
        ],
        db,
    )

    overlaid = overlay_self_scores(df, db_path=db)

    s001 = overlaid[overlaid["studentnummer"] == "S001"].iloc[0]
    assert s001["wp_1_1"] == 90
    assert s001["wp_1_2"] == 80
    assert s001["wp_1_3"] == 70
    assert s001["kt_1"] == pytest.approx(80.0)  # gemiddelde van 90/80/70

    s002 = overlaid[overlaid["studentnummer"] == "S002"].iloc[0]
    assert s002["wp_1_1"] == 30.0  # synthetisch blijft staan


def test_overlay_negeert_wp_die_NaN_zijn_in_df(db: Path) -> None:
    """Als de student geen wp_x_y heeft in zijn opleiding (NaN), niet overschrijven."""
    df = pd.DataFrame([_basisrij("S001", wp_1_2=float("nan"))])
    sla_groei_op(
        "S001",
        [GroeiActueel("S001", "wp_1_2", 80, "", "2026-05-19T10:00:00")],
        db,
    )

    overlaid = overlay_self_scores(df, db_path=db)
    s001 = overlaid.iloc[0]
    assert pd.isna(s001["wp_1_2"])  # blijft NaN want opleiding heeft deze wp niet


def test_delta_t_o_v_vorige_geeft_verschil_per_kerntaak(db: Path) -> None:
    sla_groei_op(
        "S001",
        [GroeiActueel("S001", "wp_1_1", 40, "", "2026-05-19T10:00:00")],
        db,
    )
    sla_groei_op(
        "S001",
        [GroeiActueel("S001", "wp_1_1", 70, "", "2026-05-19T11:00:00")],
        db,
    )

    delta = delta_t_o_v_vorige("S001", "wp_1_1", db_path=db)
    assert delta == 30


def test_delta_zonder_historie_is_none(db: Path) -> None:
    assert delta_t_o_v_vorige("S999", "wp_1_1", db_path=db) is None
```

- [ ] **Step 2: Run de tests — verifieer falen**

Run: `uv run pytest tests/test_groei.py -v`
Expected: ImportError op `samenwijzer.groei`.

- [ ] **Step 3: Schrijf groei.py**

Maak `src/samenwijzer/groei.py`:

```python
"""Business-logic voor het groeidossier: overlay van zelf-scores en kt-aggregatie."""

from pathlib import Path

import pandas as pd

from samenwijzer.groei_store import (
    _DB_PATH,
    get_alle_actueel,
    get_historie,
)

_KT_PREFIX = "kt_"
_WP_PREFIX = "wp_"


def bereken_kt_uit_wp(rij: pd.Series, kt_index: int) -> float:
    """Bereken het gemiddelde van de werkprocessen onder kerntaak `kt_index`.

    NaN-werkprocessen (= niet aanwezig in deze opleiding) worden genegeerd.
    Returns NaN als geen enkel werkproces een score heeft.
    """
    wp_kolommen = [k for k in rij.index if k.startswith(f"{_WP_PREFIX}{kt_index}_")]
    scores = pd.to_numeric(rij[wp_kolommen], errors="coerce").dropna()
    if scores.empty:
        return float("nan")
    return float(scores.mean())


def overlay_self_scores(df: pd.DataFrame, db_path: Path = _DB_PATH) -> pd.DataFrame:
    """Overschrijf wp-scores met self-ratings uit groei.db en herbereken kt-scores.

    - wp-kolommen die NaN zijn in df (= niet in opleiding) blijven NaN.
    - kt-kolommen worden hercalculeerd als gemiddelde van hun wp's.
    - Studenten zonder self-rating houden hun synthetische scores.

    Returns:
        Nieuwe DataFrame (origineel blijft ongewijzigd).
    """
    alle_actueel = get_alle_actueel(db_path)
    if not alle_actueel:
        return df.copy()

    overlaid = df.copy()
    studentnummer_kolom = "studentnummer"

    for studentnummer, rijen in alle_actueel.items():
        mask = overlaid[studentnummer_kolom] == studentnummer
        if not mask.any():
            continue
        idx = overlaid.index[mask][0]
        for rij in rijen:
            if rij.wp_kolom not in overlaid.columns:
                continue
            if pd.isna(overlaid.at[idx, rij.wp_kolom]):
                # NaN betekent: opleiding heeft deze wp niet — niet overschrijven.
                continue
            overlaid.at[idx, rij.wp_kolom] = float(rij.score)

        # Herbereken alle kt's voor deze student
        for kt_col in [c for c in overlaid.columns if c.startswith(_KT_PREFIX)]:
            kt_index = int(kt_col.removeprefix(_KT_PREFIX))
            nieuwe_kt = bereken_kt_uit_wp(overlaid.loc[idx], kt_index=kt_index)
            if not pd.isna(nieuwe_kt):
                overlaid.at[idx, kt_col] = nieuwe_kt

    return overlaid


def delta_t_o_v_vorige(
    studentnummer: str,
    wp_kolom: str,
    db_path: Path = _DB_PATH,
) -> int | None:
    """Geef verschil (nieuwste − op één na nieuwste) voor één werkproces.

    Returns None als er minder dan twee metingen zijn.
    """
    historie = [r for r in get_historie(studentnummer, db_path) if r.wp_kolom == wp_kolom]
    if len(historie) < 2:
        return None
    return historie[-1].score - historie[-2].score


def heeft_self_rating(studentnummer: str, db_path: Path = _DB_PATH) -> tuple[bool, str | None]:
    """Returns (heeft_rating, laatst_gewijzigd_iso). Voor de bron-badge op voortgang-pagina."""
    alle = get_alle_actueel(db_path)
    rijen = alle.get(studentnummer)
    if not rijen:
        return False, None
    laatste = max(r.laatst_gewijzigd for r in rijen)
    return True, laatste
```

- [ ] **Step 4: Run de tests — verifieer dat ze slagen**

Run: `uv run pytest tests/test_groei.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/samenwijzer/groei.py tests/test_groei.py
git commit -m "feat(groei): overlay-logica + kt-aggregatie + delta"
```

---

### Task 7: Architectuurtests uitbreiden

**Files:**
- Modify: `tests/test_architecture.py`

- [ ] **Step 1: Voeg een failing test toe voor de nieuwe modules**

In `tests/test_architecture.py`, voeg onderaan toe (vóór `def test_geen_b_erend_meer_in_code`):

```python
# ── 7. groei-modules respecteren de laagvolgorde ─────────────────────────────

_VERBODEN_VOOR_GROEI = {
    "coach",
    "tutor",
    "welzijn",
    "outreach",
    "outreach_store",
}


def test_groei_importeert_geen_ai_modules_of_app() -> None:
    """groei.py mag alleen leunen op groei_store en stdlib/pandas."""
    imports = _importnamen(SRC / "groei.py")
    schendingen = [i for i in imports if i in _VERBODEN_VOOR_GROEI or i == "streamlit"]
    assert not schendingen, f"groei.py importeert verboden: {schendingen}"


def test_groei_store_importeert_geen_hogere_laag() -> None:
    imports = _samenwijzer_imports(SRC / "groei_store.py")
    schendingen = [
        i
        for i in imports
        if i in {"groei", "tutor", "coach", "welzijn", "outreach", "app"}
    ]
    assert not schendingen, f"groei_store.py importeert hogere laag: {schendingen}"


def test_bewijsstuk_store_importeert_alleen_stdlib() -> None:
    imports = _samenwijzer_imports(SRC / "bewijsstuk_store.py")
    assert imports == [], f"bewijsstuk_store.py moet stdlib-only zijn, vond: {imports}"
```

- [ ] **Step 2: Run de tests — verifieer dat ze al slagen (omdat we al netjes geschreven hebben)**

Run: `uv run pytest tests/test_architecture.py -v`
Expected: all green inclusief 3 nieuwe tests.

- [ ] **Step 3: Commit**

```bash
git add tests/test_architecture.py
git commit -m "test(groei): laag-regels voor groei/groei_store/bewijsstuk_store"
```

---

### Task 8: prepare-integratie — overlay self-scores na laden CSV

**Files:**
- Modify: `src/samenwijzer/prepare.py`
- Modify: `tests/test_prepare.py`

- [ ] **Step 1: Schrijf een failing integratietest**

Append aan `tests/test_prepare.py`:

```python
def test_load_synthetisch_csv_past_self_scores_overlay_toe(
    tmp_path: pytest.MonkeyPatch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Na het laden moeten self-scores uit groei.db de synthetische scores overschrijven."""
    from samenwijzer.groei_store import GroeiActueel, init_db, sla_groei_op
    from samenwijzer.prepare import load_synthetisch_csv

    # Wijs naar tijdelijke DB
    test_db = tmp_path / "groei.db"
    init_db(test_db)
    monkeypatch.setattr("samenwijzer.groei._DB_PATH", test_db, raising=True)

    df = load_synthetisch_csv()
    assert not df.empty
    eerste_student = df.iloc[0]["studentnummer"]
    synthetisch_was = float(df.iloc[0]["wp_1_1"])

    # Schrijf een afwijkende self-rating
    sla_groei_op(
        eerste_student,
        [GroeiActueel(eerste_student, "wp_1_1", 99, "", "2026-05-19T10:00:00")],
        test_db,
    )

    df2 = load_synthetisch_csv()
    rij = df2[df2["studentnummer"] == eerste_student].iloc[0]
    assert rij["wp_1_1"] == 99
    assert rij["wp_1_1"] != synthetisch_was
```

Voeg bovenaan `tests/test_prepare.py` toe als de import nog niet bestaat:
```python
import pytest
```

- [ ] **Step 2: Run de test — verifieer dat hij faalt**

Run: `uv run pytest tests/test_prepare.py::test_load_synthetisch_csv_past_self_scores_overlay_toe -v`
Expected: de self-rating wordt niet toegepast, dus de assert `rij["wp_1_1"] == 99` faalt.

- [ ] **Step 3: Wijzig prepare.load_synthetisch_csv om overlay toe te passen**

Open `src/samenwijzer/prepare.py`. Aan het einde van `load_synthetisch_csv` (na `df = _voeg_kt_wp_scores_toe(df)` en de validatie, vlak voor `return df`):

Verander de laatste regels naar:
```python
    df = _voeg_kt_wp_scores_toe(df)
    _validate(df)

    # Overlay zelf-beoordelingen uit groei.db over de synthetische scores
    from samenwijzer.groei import overlay_self_scores

    return overlay_self_scores(df)
```

Belangrijk: de import staat *binnen* de functie om de laagregel te respecteren — `prepare` mag geen module-niveau import doen van een hogere laag-module. Run een snelle controle:

```bash
grep -n "from samenwijzer.groei" src/samenwijzer/prepare.py
```
Expected: één regel binnen `load_synthetisch_csv`.

- [ ] **Step 4: Pas de architectuurtest aan zodat de lazy-import niet als overtreding wordt geflagged**

Open `tests/test_architecture.py` en bekijk `test_prepare_importeert_geen_hogere_laag` (rond regel 86). De huidige `_samenwijzer_imports` walkt door `ast.walk` heen — dat vindt *óók* function-level imports. We willen die lazy-import expliciet toestaan voor `groei`. Verander de testfunctie:

```python
def test_prepare_importeert_geen_hogere_laag() -> None:
    imports = _samenwijzer_imports(SRC / "prepare.py")
    # `groei` is een toegestane lazy-import binnen load_synthetisch_csv om
    # zelf-beoordelingen over de synthetische scores te leggen.
    schendingen = [i for i in imports if i in _HOGER_DAN_PREPARE and i != "groei"]
    assert not schendingen, f"prepare.py importeert uit hogere laag: {schendingen}"
```

- [ ] **Step 5: Run alle tests**

Run: `uv run pytest tests/test_prepare.py tests/test_architecture.py -v`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/samenwijzer/prepare.py tests/test_prepare.py tests/test_architecture.py
git commit -m "feat(groei): overlay self-scores in load_synthetisch_csv"
```

---

### Task 9: AI-aanscherp-functie in tutor.py

**Files:**
- Modify: `src/samenwijzer/tutor.py`
- Modify: `tests/test_tutor.py`

- [ ] **Step 1: Schrijf een failing test (mock op _ai._client)**

Append aan `tests/test_tutor.py`:

```python
def test_aanscherp_verantwoording_streamt_en_geeft_tekst_terug(monkeypatch) -> None:
    """De aanscherpfunctie moet streamen via _ai._client en de tekstfragmenten yielden."""
    from samenwijzer.tutor import aanscherp_verantwoording

    fragmenten = ["Ik ", "kan ", "klanten ", "te woord ", "staan."]

    class _DummyStream:
        def __init__(self) -> None:
            self.text_stream = iter(fragmenten)

        def __enter__(self) -> "_DummyStream":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    class _DummyMessages:
        def stream(self, **kwargs: object) -> _DummyStream:
            return _DummyStream()

    class _DummyClient:
        messages = _DummyMessages()

    monkeypatch.setattr("samenwijzer.tutor._client", lambda api_key=None: _DummyClient())

    result = "".join(
        aanscherp_verantwoording(
            werkproces_label="Treedt op als aanspreekpunt",
            kerntaak_label="Voert taken uit binnen zakelijke dienstverlening",
            opleiding="Medewerker Secretarieel",
            huidige_tekst="ik kan dit wel",
            score=65,
        )
    )
    assert result == "Ik kan klanten te woord staan."
```

- [ ] **Step 2: Run de test — verifieer falen**

Run: `uv run pytest tests/test_tutor.py::test_aanscherp_verantwoording_streamt_en_geeft_tekst_terug -v`
Expected: ImportError op `aanscherp_verantwoording`.

- [ ] **Step 3: Voeg de functie toe aan tutor.py**

Append aan `src/samenwijzer/tutor.py` (na de bestaande functies):

```python
def aanscherp_verantwoording(
    werkproces_label: str,
    kerntaak_label: str,
    opleiding: str,
    huidige_tekst: str,
    score: int,
    *,
    api_key: str | None = None,
) -> Generator[str]:
    """Laat de tutor een aangescherpte verantwoording suggereren.

    Args:
        werkproces_label: OER-label van het werkproces.
        kerntaak_label: OER-label van de bovenliggende kerntaak.
        opleiding: Opleidingsnaam van de student.
        huidige_tekst: De huidige verantwoording die de student heeft getypt.
        score: De zelf-gegeven score 0..100 voor dit werkproces.
        api_key: Optionele override; gebruikt ANTHROPIC_API_KEY als None.

    Yields:
        Tekstfragmenten van de aangescherpte versie (streaming).
    """
    client = _client(api_key)

    systeem = (
        "Je bent een leercoach voor een MBO-student. Help de student z'n eigen "
        "verantwoording aanscherpen. Schrijf in de ik-vorm van de student, in "
        "2 tot 4 zinnen, met concreet voorbeeldgedrag dat past bij de OER-formulering. "
        "Voeg geen kop, geen bullets, geen tussenkopjes toe — alleen lopende tekst."
    )
    gebruikersbericht = (
        f"Werkproces: {werkproces_label}\n"
        f"Kerntaak: {kerntaak_label}\n"
        f"Opleiding: {opleiding}\n"
        f"Zelf-gegeven score: {score}/100\n"
        f"Huidige verantwoording: {huidige_tekst or '(nog leeg)'}\n\n"
        "Geef een aangescherpte versie."
    )

    with client.messages.stream(
        model=_MODEL,
        max_tokens=400,
        system=[{"type": "text", "text": systeem}],
        messages=[{"role": "user", "content": gebruikersbericht}],
    ) as stream:
        for fragment in stream.text_stream:
            yield fragment
```

- [ ] **Step 4: Run de test — verifieer dat hij slaagt**

Run: `uv run pytest tests/test_tutor.py -v`
Expected: all green inclusief de nieuwe test.

- [ ] **Step 5: Commit**

```bash
git add src/samenwijzer/tutor.py tests/test_tutor.py
git commit -m "feat(tutor): aanscherp_verantwoording voor groeidossier"
```

---

### Task 10: Navigatie + bron-badge op voortgang-pagina

**Files:**
- Modify: `src/samenwijzer/styles.py`
- Modify: `app/pages/1_mijn_voortgang.py`

- [ ] **Step 1: Voeg de nav-link toe in styles.py**

Open `src/samenwijzer/styles.py` (rond regel 38-50). Vervang `_NAV_STUDENT` en `_NAV_DOCENT`:

```python
_NAV_STUDENT = [
    ("📚 Home", "main.py"),
    ("📊 Mijn voortgang", "pages/1_mijn_voortgang.py"),
    ("🌱 Groeidossier", "pages/6_groeidossier.py"),
    ("🎓 Leercoach", "pages/3_leercoach.py"),
    ("💚 Welzijn", "pages/5_welzijn.py"),
]

_NAV_DOCENT = [
    ("📚 Home", "main.py"),
    ("👥 Groepsoverzicht", "pages/2_groepsoverzicht.py"),
    ("🌱 Groeidossier", "pages/6_groeidossier.py"),
    ("📬 Outreach", "pages/4_outreach.py"),
    ("🎓 Leercoach", "pages/3_leercoach.py"),
]
```

- [ ] **Step 2: Voeg de bron-badge toe op de voortgang-pagina**

Open `app/pages/1_mijn_voortgang.py`. Na de hero-kaart (rond regel 77, vlak na de `st.markdown(f"""<div class="hero-card">...""")`-block), voeg toe:

```python
# ── Bron-badge: zelf beoordeeld of synthetische schatting? ──
from samenwijzer.groei import heeft_self_rating

heeft_rating, laatst = heeft_self_rating(studentnummer)
if heeft_rating:
    datum_kort = (laatst or "")[:10]
    st.caption(f"📝 Zelf beoordeeld op {datum_kort}")
else:
    st.caption("🤖 Schatting op basis van OER — vul je groeidossier in voor je eigen scores")
```

- [ ] **Step 3: Verifieer dat de bestaande tests nog slagen**

Run: `uv run pytest tests/ -v -x`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add src/samenwijzer/styles.py app/pages/1_mijn_voortgang.py
git commit -m "feat(groei): nav-link Groeidossier + bron-badge op voortgang-pagina"
```

---

### Task 11: Groeidossier-pagina — student-view (sliders + verantwoording + opslaan)

**Files:**
- Create: `app/pages/6_groeidossier.py`

- [ ] **Step 1: Maak het skelet van de pagina**

Maak `app/pages/6_groeidossier.py`:

```python
"""Pagina: Groeidossier — student-zelfbeoordeling en mentor-feedback."""

import logging
from datetime import datetime

import pandas as pd
import streamlit as st

from samenwijzer._ai import APITimeoutError, vriendelijke_fout
from samenwijzer.analyze import _oer_label, get_student
from samenwijzer.auth import mentor_filter
from samenwijzer.groei import delta_t_o_v_vorige
from samenwijzer.groei_store import (
    GroeiActueel,
    MentorFeedback,
    get_actueel,
    get_historie,
    get_mentor_feedback,
    sla_groei_op,
    upsert_mentor_feedback,
)
from samenwijzer.styles import CSS, render_footer, render_nav
from samenwijzer.transform import get_kerntaak_columns, get_werkproces_columns
from samenwijzer.tutor import aanscherp_verantwoording

log = logging.getLogger(__name__)

st.set_page_config(page_title="Groeidossier — Samenwijzer", page_icon="🌱", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
render_nav()

if "df" not in st.session_state or "rol" not in st.session_state:
    st.warning("Ga eerst naar de [startpagina](/) om in te loggen.")
    st.stop()

df = st.session_state["df"]
rol = st.session_state["rol"]

# ── Studentselectie ──────────────────────────────────────────────────────────
if rol == "student":
    studentnummer = st.session_state["studentnummer"]
    is_eigenaar = True
else:
    groep = mentor_filter(df)
    opties = (
        groep.sort_values("naam")[["naam", "studentnummer"]]
        .apply(lambda r: f"{r['naam']} ({r['studentnummer']})", axis=1)
        .tolist()
    )
    if not opties:
        st.info("Je hebt geen studenten in je groep.")
        render_footer()
        st.stop()
    keuze = st.selectbox("Selecteer een student uit jouw groep", opties)
    studentnummer = keuze.split("(")[-1].rstrip(")")
    is_eigenaar = False

student = get_student(df, studentnummer)
opleiding = str(student["opleiding"])
crebo = str(student.get("crebo", ""))

st.markdown(f"## 🌱 Groeidossier — {student['naam']}")
st.caption(f"{opleiding} · Niveau {student['niveau']} · Cohort {student['cohort']}")

# ── Huidige data ─────────────────────────────────────────────────────────────
actueel_lijst = get_actueel(studentnummer)
actueel = {r.wp_kolom: r for r in actueel_lijst}
feedback = get_mentor_feedback(studentnummer)

kt_cols = get_kerntaak_columns(df)
wp_cols = get_werkproces_columns(df)

_NIVEAU_LABELS = "Starter  ·  Op weg  ·  Gevorderd  ·  Beroepsbekwaam"


def _wp_van_kt(kt_col: str) -> list[str]:
    idx = kt_col.removeprefix("kt_")
    return [w for w in wp_cols if w.startswith(f"wp_{idx}_")]


def _huidige_score(wp_col: str) -> int:
    if wp_col in actueel:
        return actueel[wp_col].score
    df_waarde = student.get(wp_col)
    try:
        return int(float(df_waarde)) if df_waarde is not None else 50
    except (TypeError, ValueError):
        return 50


def _huidige_verantwoording(wp_col: str) -> str:
    return actueel[wp_col].verantwoording if wp_col in actueel else ""


# ── Render per kerntaak ──────────────────────────────────────────────────────
tab_scores, tab_history = st.tabs(["📊 Mijn beoordeling", "📈 Groei over tijd"])

with tab_scores:
    nieuwe_waarden: dict[str, tuple[int, str]] = {}

    for kt_col in kt_cols:
        kt_label = _oer_label(opleiding, kt_col, crebo)
        kt_eigen_wp = _wp_van_kt(kt_col)
        if not kt_eigen_wp:
            continue
        # Skip kerntaken waarvan álle wp's NaN zijn (opleiding heeft ze niet)
        if all(pd.isna(student.get(w, float("nan"))) for w in kt_eigen_wp):
            continue

        with st.container(border=True):
            st.markdown(f"### {kt_label}")

            # Mentor-feedback (indien aanwezig)
            if kt_col in feedback:
                st.markdown(
                    f"<div style='background:#f4f4f4;padding:12px;border-radius:6px;"
                    f"margin-bottom:12px;'>"
                    f"<b>📣 Feedback van {feedback[kt_col].mentor_naam}</b><br>"
                    f"{feedback[kt_col].tekst}</div>",
                    unsafe_allow_html=True,
                )

            for wp_col in kt_eigen_wp:
                wp_label = _oer_label(opleiding, wp_col, crebo)
                huidige = _huidige_score(wp_col)
                huidige_v = _huidige_verantwoording(wp_col)

                st.markdown(f"**{wp_label}**")
                st.caption(_NIVEAU_LABELS)

                score = st.slider(
                    "Score",
                    min_value=0,
                    max_value=100,
                    value=huidige,
                    key=f"slider_{studentnummer}_{wp_col}",
                    label_visibility="collapsed",
                    disabled=not is_eigenaar,
                )
                verant = st.text_area(
                    "Waarom vind je dit?",
                    value=huidige_v,
                    max_chars=1000,
                    key=f"verant_{studentnummer}_{wp_col}",
                    disabled=not is_eigenaar,
                )

                # AI-aanscherp-knop
                if is_eigenaar:
                    aanscherp_sleutel = f"sw_aanscherp_{studentnummer}_{wp_col}"
                    cols_ai = st.columns([1, 4])
                    with cols_ai[0]:
                        klik_aanscherp = st.button(
                            "✨ Aanscherpen",
                            key=f"btn_aanscherp_{wp_col}",
                            help="Vraag de tutor om je verantwoording aan te scherpen",
                        )
                    with cols_ai[1]:
                        if aanscherp_sleutel in st.session_state:
                            st.markdown(
                                f"<div style='background:#fffbe6;padding:8px;border-radius:6px;'>"
                                f"<b>💡 Suggestie:</b><br>{st.session_state[aanscherp_sleutel]}"
                                f"</div>",
                                unsafe_allow_html=True,
                            )

                    if klik_aanscherp:
                        st.session_state.pop(aanscherp_sleutel, None)
                        try:
                            with st.spinner("Tutor denkt mee…"):
                                tekst = st.write_stream(
                                    aanscherp_verantwoording(
                                        werkproces_label=wp_label,
                                        kerntaak_label=kt_label,
                                        opleiding=opleiding,
                                        huidige_tekst=verant,
                                        score=score,
                                    )
                                )
                            st.session_state[aanscherp_sleutel] = tekst
                            st.rerun()
                        except APITimeoutError:
                            st.error("De AI-service reageert niet. Probeer het later opnieuw.")
                        except Exception as e:
                            log.exception("Aanscherpen mislukt")
                            st.error(vriendelijke_fout(e))

                nieuwe_waarden[wp_col] = (score, verant)
                st.markdown("---")

    if is_eigenaar:
        if st.button("💾 Opslaan", type="primary", use_container_width=True):
            nu = datetime.now().isoformat(timespec="seconds")
            rijen = [
                GroeiActueel(studentnummer, wp, score, verant, nu)
                for wp, (score, verant) in nieuwe_waarden.items()
                if (wp not in actueel)
                or actueel[wp].score != score
                or actueel[wp].verantwoording != verant
            ]
            if not rijen:
                st.info("Niets gewijzigd om op te slaan.")
            else:
                sla_groei_op(studentnummer, rijen)
                st.success(f"{len(rijen)} wijziging(en) opgeslagen.")
                st.rerun()
    else:
        # Docent-only: feedback per kerntaak
        st.markdown("### Mentor-feedback per kerntaak")
        for kt_col in kt_cols:
            kt_label = _oer_label(opleiding, kt_col, crebo)
            huidige_fb = feedback.get(kt_col).tekst if kt_col in feedback else ""
            tekst = st.text_area(
                f"Feedback op {kt_label}",
                value=huidige_fb,
                key=f"fb_{studentnummer}_{kt_col}",
                max_chars=1000,
            )
            if st.button(f"💬 Feedback opslaan ({kt_col})", key=f"btn_fb_{kt_col}"):
                upsert_mentor_feedback(
                    MentorFeedback(
                        studentnummer=studentnummer,
                        kt_kolom=kt_col,
                        mentor_naam=st.session_state.get("mentor_naam", "onbekend"),
                        tekst=tekst,
                        geschreven_op=datetime.now().isoformat(timespec="seconds"),
                    )
                )
                st.success("Feedback opgeslagen.")
                st.rerun()


with tab_history:
    historie = get_historie(studentnummer)
    if not historie:
        st.info("Nog geen groeihistorie — sla je beoordeling op om je eerste meetpunt vast te leggen.")
    else:
        import pandas as pd

        hist_df = pd.DataFrame(
            [
                {
                    "datum": h.opgeslagen_op[:10],
                    "werkproces": _oer_label(opleiding, h.wp_kolom, crebo),
                    "score": h.score,
                }
                for h in historie
            ]
        )
        st.line_chart(hist_df, x="datum", y="score", color="werkproces")

        st.markdown("#### Delta t.o.v. vorige meting")
        cols = st.columns(min(len(wp_cols), 3))
        for i, wp_col in enumerate(wp_cols):
            d = delta_t_o_v_vorige(studentnummer, wp_col)
            if d is None:
                continue
            with cols[i % 3]:
                pijl = "▲" if d > 0 else ("▼" if d < 0 else "■")
                kleur = "#27ae60" if d > 0 else ("#c0392b" if d < 0 else "#999")
                st.markdown(
                    f"<div style='border:1px solid #eee;padding:10px;border-radius:6px;'>"
                    f"<small>{_oer_label(opleiding, wp_col, crebo)}</small><br>"
                    f"<span style='color:{kleur};font-size:1.4rem;font-weight:700;'>"
                    f"{pijl} {abs(d)}</span></div>",
                    unsafe_allow_html=True,
                )

render_footer()
```

- [ ] **Step 2: Run ruff en ty**

Run: `uv run ruff check --fix app/pages/6_groeidossier.py && uv run ruff format app/pages/6_groeidossier.py`
Expected: geen overgebleven errors.

Run: `uv run ty check`
Expected: clean.

- [ ] **Step 3: Run de hele testsuite om regressies op te sporen**

Run: `uv run pytest -x`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add app/pages/6_groeidossier.py
git commit -m "feat(groei): student-view groeidossier met sliders, verantwoording, AI-aanscherp"
```

---

### Task 12: Bewijsstukken-uploadwidget in de pagina

**Files:**
- Modify: `app/pages/6_groeidossier.py`

- [ ] **Step 1: Breid imports uit in app/pages/6_groeidossier.py**

Vervang de bestaande `from samenwijzer.groei_store import (...)`-block door:

```python
from samenwijzer.bewijsstuk_store import (
    MAX_GROOTTE_BYTES,
    TOEGESTANE_EXTENSIES,
    BewijsstukFout,
    open_bestand,
)
from samenwijzer.bewijsstuk_store import opslaan as bewijsstuk_opslaan
from samenwijzer.bewijsstuk_store import verwijderen as bewijsstuk_verwijderen
from samenwijzer.groei_store import (
    BewijsstukMeta,
    GroeiActueel,
    MentorFeedback,
    get_actueel,
    get_bewijsstukken,
    get_historie,
    get_mentor_feedback,
    insert_bewijsstuk,
    sla_groei_op,
    upsert_mentor_feedback,
)
from samenwijzer.groei_store import verwijder_bewijsstuk as verwijder_bewijsstuk_meta
```

- [ ] **Step 2: Bouw een helper-functie voor de upload-expander**

Voeg toe vlak boven `# ── Render per kerntaak ──`-comment:

```python
def _render_bewijsstuk_expander(wp_col: str, wp_label: str) -> None:
    """Toon bewijsstukken voor één werkproces + upload + verwijder."""
    stukken = [b for b in get_bewijsstukken(studentnummer) if b.wp_kolom == wp_col]
    with st.expander(f"📎 Bewijsstukken ({len(stukken)})"):
        for stuk in stukken:
            cols = st.columns([5, 2, 1])
            with cols[0]:
                grootte_kb = stuk.grootte_bytes // 1024
                st.markdown(f"**{stuk.bestandsnaam}** _{grootte_kb} kB_")
                if stuk.toelichting:
                    st.caption(stuk.toelichting)
            with cols[1]:
                try:
                    inhoud = open_bestand(stuk.bestandspad)
                    st.download_button(
                        "⬇️ Download",
                        data=inhoud,
                        file_name=stuk.bestandsnaam,
                        mime=stuk.mime_type,
                        key=f"dl_{stuk.id}",
                    )
                except FileNotFoundError:
                    st.warning("Bestand ontbreekt op disk.")
                except BewijsstukFout as e:
                    log.warning("Bewijsstuk %s onbereikbaar: %s", stuk.id, e)
            with cols[2]:
                if is_eigenaar and st.button("🗑️", key=f"del_{stuk.id}"):
                    try:
                        bewijsstuk_verwijderen(stuk.bestandspad)
                    except BewijsstukFout as e:
                        log.warning("FS-verwijdering mislukt: %s", e)
                    assert stuk.id is not None
                    verwijder_bewijsstuk_meta(stuk.id)
                    st.rerun()

        if is_eigenaar:
            st.markdown("---")
            upload = st.file_uploader(
                f"Voeg bewijsstuk toe voor {wp_label}",
                type=[e.lstrip(".") for e in TOEGESTANE_EXTENSIES],
                key=f"upl_{wp_col}",
                accept_multiple_files=False,
            )
            toelichting = st.text_input(
                "Toelichting (optioneel)",
                key=f"upl_toel_{wp_col}",
                max_chars=200,
            )
            if upload is not None and st.button(
                "📤 Uploaden", key=f"btn_upl_{wp_col}"
            ):
                inhoud = upload.getvalue()
                if len(inhoud) > MAX_GROOTTE_BYTES:
                    st.error(
                        f"Bestand is te groot ({len(inhoud) // 1024} kB); "
                        f"max {MAX_GROOTTE_BYTES // 1024 // 1024} MB."
                    )
                else:
                    try:
                        rel_pad = bewijsstuk_opslaan(
                            studentnummer=studentnummer,
                            bestandsnaam=upload.name,
                            inhoud=inhoud,
                        )
                        insert_bewijsstuk(
                            BewijsstukMeta(
                                studentnummer=studentnummer,
                                wp_kolom=wp_col,
                                bestandsnaam=upload.name,
                                bestandspad=rel_pad,
                                mime_type=upload.type or "application/octet-stream",
                                grootte_bytes=len(inhoud),
                                toelichting=toelichting,
                                geupload_op=datetime.now().isoformat(timespec="seconds"),
                            )
                        )
                        st.success(f"Bewijsstuk '{upload.name}' geüpload.")
                        st.rerun()
                    except BewijsstukFout as e:
                        st.error(str(e))
```

- [ ] **Step 3: Roep de helper aan per werkproces**

In de `for wp_col in kt_eigen_wp:`-lus, vlak na de AI-aanscherp-block en vóór `nieuwe_waarden[wp_col] = ...`, voeg toe:

```python
                _render_bewijsstuk_expander(wp_col, wp_label)
```

- [ ] **Step 4: AVG-check toevoegen — voorkom dat een mentor van een andere instelling bewijsstukken kan zien**

In het docent-pad (na `studentnummer = keuze.split(...)`), is de student al gefilterd via `mentor_filter`. Daarmee zijn bewijsstukken impliciet beperkt. Voeg ter zekerheid een redundante check toe direct na `studentnummer = ...`:

```python
    if studentnummer not in groep["studentnummer"].values:
        st.error("Geen toegang tot deze student.")
        st.stop()
```

- [ ] **Step 5: Run ruff + tests**

Run: `uv run ruff check --fix app/pages/6_groeidossier.py && uv run ruff format app/pages/6_groeidossier.py`
Run: `uv run pytest -x`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add app/pages/6_groeidossier.py
git commit -m "feat(groei): bewijsstuk-upload + download + verwijder per werkproces"
```

---

### Task 13: UI-smoketest via chrome-devtools-mcp

**Files:**
- Geen — handmatige verificatie via browser.

- [ ] **Step 1: Start beide services lokaal**

Open twee terminals (parallel):

```bash
uv run streamlit run app/main.py
```

(De WhatsApp-webhook is hier niet nodig.)

Wacht tot Streamlit zegt: `You can now view your Streamlit app in your browser. Local URL: http://localhost:8501`.

- [ ] **Step 2: Login als test-student uit gebruikers.txt**

Open `gebruikers.txt` voor een actief studentnummer en wachtwoord. Genoteerd nodig: `studentnummer`, `wachtwoord` (Welkom123), en de toegewezen `mentor`.

Via chrome-devtools-mcp:
- Navigeer naar `http://localhost:8501`.
- Login als student.
- Verifieer dat de nav-link "🌱 Groeidossier" zichtbaar is.

- [ ] **Step 3: Test de student-flow**

1. Klik "🌱 Groeidossier".
2. Verschuif minstens twee sliders.
3. Type een verantwoording bij elk.
4. Klik op "✨ Aanscherpen" voor één werkproces — verifieer dat een suggestie verschijnt (geen exception in logs).
5. Klik "💾 Opslaan" — verwacht "X wijzigingen opgeslagen."
6. Refresh de pagina — verwacht dat sliders en verantwoordingen op de opgeslagen waarden staan.
7. Upload een PDF (klein testbestand) bij één werkproces.
8. Verifieer dat het bestand verschijnt in de expander; download het en check inhoud-roundtrip.
9. Open de tab "📈 Groei over tijd" — verwacht een lijngrafiek (één punt).
10. Sla nog één keer op met een gewijzigde slider. Refresh, ga naar history-tab — verwacht twee punten en een delta-pijl.
11. Ga naar "📊 Mijn voortgang" — verwacht de bron-badge "📝 Zelf beoordeeld op {datum}".

- [ ] **Step 4: Test de docent-flow**

1. Uitloggen (via `/uitloggen` of de uitlog-pagina).
2. Login als de mentor die in `gebruikers.txt` aan deze student gekoppeld is.
3. Open "🌱 Groeidossier".
4. Selecteer de zojuist beoordeelde student.
5. Verifieer dat sliders en verantwoordingen read-only zijn (gedisabled).
6. Verifieer dat bewijsstukken downloadable zijn maar geen uploadwidget zichtbaar is.
7. Schrijf feedback bij `kt_1`, klik opslaan.
8. Uitloggen → opnieuw inloggen als de student → verifieer dat de feedback in een grijze kaart bovenaan `kt_1` te zien is.

- [ ] **Step 5: Test cross-instelling-isolatie (AVG)**

1. Uitloggen.
2. Login als een mentor van een andere instelling uit `gebruikers.txt`.
3. Open "🌱 Groeidossier".
4. Verifieer dat de student-selectbox alléén de eigen groep toont, niet de student uit step 3.

- [ ] **Step 6: Cleanup-bevestiging**

Run: `git status`
Expected: clean (geen onverwachte gewijzigde files).

Run: `ls data/02-prepared/groei.db && ls data/bewijsstukken/`
Expected: `groei.db` bestaat met data; in `data/bewijsstukken/` staat de student-folder met het geüploade PDF — beide gitignored.

- [ ] **Step 7: Commit-marker dat smoketest geslaagd is**

```bash
git commit --allow-empty -m "test(groei): UI-smoketest student- en docent-flow geslaagd"
```

---

### Task 14: Plan-completion + plan-archivering

**Files:**
- Move: `docs/plans/active/2026-05-19-groeidossier-zelf-rating-bewijsstukken.md` → `docs/plans/completed/`

- [ ] **Step 1: Volledige testsuite + linting**

Run: `uv run pytest`
Expected: all green met coverage.

Run: `uv run ruff check src/ app/ && uv run ruff format --check src/ app/`
Expected: clean.

Run: `uv run ty check`
Expected: clean.

- [ ] **Step 2: Verplaats het plan naar completed**

```bash
git mv docs/plans/active/2026-05-19-groeidossier-zelf-rating-bewijsstukken.md \
       docs/plans/completed/2026-05-19-groeidossier-zelf-rating-bewijsstukken.md
git commit -m "docs(plans): groeidossier-plan voltooid en gearchiveerd"
```

- [ ] **Step 3: Maak een PR (geen direct push naar main — zie AGENTS.md regel 5)**

```bash
git push -u origin HEAD
gh pr create --title "feat(groei): groeidossier met zelf-rating, bewijsstukken en AI-aanscherp" --body "$(cat <<'EOF'
## Summary
- Studenten kunnen per werkproces hun eigen score (0–100) en verantwoording invullen
- Bewijsstukken uploaden (PDF/JPG/PNG/DOCX/XLSX, max 10 MB)
- Groei over tijd zichtbaar als lijngrafiek + delta t.o.v. vorige meting
- Mentor schrijft feedback per kerntaak; student ziet die bovenin
- AI-aanscherp-knop hergebruikt `tutor._client()` voor een streaming suggestie
- Self-scores overlayen automatisch de synthetische dataset, zodat alle bestaande dashboards meeprofiteren

## Test plan
- [ ] `uv run pytest` groen
- [ ] `uv run ruff check src/ app/` clean
- [ ] `uv run ty check` clean
- [ ] UI-smoketest als student: slider → verantwoording → AI-aanscherp → opslaan → upload PDF → history
- [ ] UI-smoketest als mentor: feedback schrijven, bewijsstukken downloaden, geen edit-rechten op sliders
- [ ] AVG-check: mentor van andere instelling ziet de student niet
EOF
)"
```

---

## Spec-coverage check

| Spec-sectie | Implementerende task(s) |
|---|---|
| § Architectuur — module-lagen | 2, 5, 6, 7 |
| § Data-model | 2, 3, 4 |
| § UI-flow — student-view | 11, 12 |
| § UI-flow — docent-view | 11, 12 |
| § AI-aanscherpknop | 9, 11 |
| § Integratie met dashboards | 8, 10 |
| § Validatie en error-handling | 5 (boundary), 11 (try/except), 12 (size-check) |
| § Tests | 2, 3, 4, 5, 6, 7, 8, 9, 13 |
| § Migratie | n.v.t. — `groei.db` start leeg |

Geen gaten.
