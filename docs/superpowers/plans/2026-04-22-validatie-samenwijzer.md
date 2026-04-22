# Validatie Samenwijzer — OER-assistent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standalone Streamlit-app in `validatie_samenwijzer/` waarmee MBO-studenten en mentoren hun OER kunnen bevragen via een hybride AI-chat (antwoord + bronpassages), aangevuld met voortgangsdata en een begeleidingsinterface.

**Architecture:** SQLite voor gebruikers/studentdata, ChromaDB voor OER-embeddings, OpenAI `text-embedding-3-small` voor embeddings, Anthropic Claude Sonnet voor chat. Ingestie loopt via een aparte CLI (`ingest.py`). Lagenregel: `db → auth/vector_store → chat → app`.

**Tech Stack:** Python 3.13, Streamlit, SQLite, ChromaDB, OpenAI SDK, Anthropic SDK, pdfplumber, BeautifulSoup4, uv, pytest, ruff.

---

## Bestandskaart

| Bestand | Verantwoordelijkheid |
|---|---|
| `pyproject.toml` | Dependencies, ruff config, pytest config |
| `src/validatie_samenwijzer/db.py` | SQLite schema-init + alle queries |
| `src/validatie_samenwijzer/auth.py` | Wachtwoord-hash, login, rolcontrole |
| `src/validatie_samenwijzer/_ai.py` | Anthropic client factory |
| `src/validatie_samenwijzer/_openai.py` | OpenAI client factory |
| `src/validatie_samenwijzer/vector_store.py` | ChromaDB wrapper (opslaan + zoeken) |
| `src/validatie_samenwijzer/ingest.py` | OER → chunks → embeddings → ChromaDB (CLI) |
| `src/validatie_samenwijzer/chat.py` | Retrieval + prompt + Claude streaming |
| `src/validatie_samenwijzer/styles.py` | CSS + render_nav() + render_footer() |
| `seed/seed.py` | Testgebruikers + synthetische scores aanmaken |
| `app/main.py` | Login + sessie-initialisatie |
| `app/pages/1_oer_assistent.py` | Student: hybride OER-chat |
| `app/pages/2_mijn_oer.py` | Student: volledig OER inzien/downloaden |
| `app/pages/3_mijn_voortgang.py` | Student: kerntaakscores, BSA, aanwezigheid |
| `app/pages/4_mijn_studenten.py` | Mentor: studentenoverzicht met voortgangsbadges |
| `app/pages/5_begeleidingssessie.py` | Mentor: studentprofiel + OER-chat naast elkaar |
| `app/pages/uitloggen.py` | Wist sessie, redirect naar login |
| `tests/test_db.py` | DB schema + query tests |
| `tests/test_auth.py` | Auth tests |
| `tests/test_ingest.py` | Filename parsing, chunking, kerntaken-detectie |
| `tests/test_vector_store.py` | ChromaDB wrapper tests |
| `tests/test_chat.py` | Prompt-opbouw + retrieval tests |

---

## Task 1: Project scaffolding

**Files:**
- Create: `validatie_samenwijzer/pyproject.toml`
- Create: `validatie_samenwijzer/.gitignore`
- Create: `validatie_samenwijzer/.streamlit/config.toml`
- Create: `validatie_samenwijzer/.env.example`
- Create: `validatie_samenwijzer/src/validatie_samenwijzer/__init__.py`
- Create: `validatie_samenwijzer/tests/__init__.py`

- [ ] **Stap 1: Maak directorystructuur aan**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
mkdir -p src/validatie_samenwijzer app/pages seed tests data/chroma .streamlit
touch src/validatie_samenwijzer/__init__.py tests/__init__.py seed/__init__.py
```

- [ ] **Stap 2: Schrijf pyproject.toml**

```toml
[project]
name = "validatie-samenwijzer"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "streamlit>=1.42.0",
    "anthropic>=0.45.0",
    "openai>=1.60.0",
    "chromadb>=0.6.0",
    "pdfplumber>=0.11.0",
    "beautifulsoup4>=4.12.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.9.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/validatie_samenwijzer"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
```

- [ ] **Stap 3: Schrijf .streamlit/config.toml**

```toml
[theme]
base = "light"
primaryColor = "#1a237e"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f5f5f5"
textColor = "#1a1a1a"

[client]
showSidebarNavigation = false

[server]
headless = true
port = 8503
```

- [ ] **Stap 4: Schrijf .gitignore**

```
.env
data/validatie.db
data/chroma/
data/*.db
__pycache__/
*.pyc
.venv/
.pytest_cache/
*.egg-info/
```

- [ ] **Stap 5: Schrijf .env.example**

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
DB_PATH=data/validatie.db
CHROMA_PATH=data/chroma
OEREN_PAD=oeren
```

- [ ] **Stap 6: Installeer dependencies**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
uv sync --extra dev
```

Verwacht: alle packages geïnstalleerd zonder fouten.

- [ ] **Stap 7: Commit**

```bash
git add validatie_samenwijzer/
git commit -m "feat(validatie): scaffolding — pyproject, dirs, streamlit config"
```

---

## Task 2: db.py — SQLite schema + queries

**Files:**
- Create: `validatie_samenwijzer/src/validatie_samenwijzer/db.py`
- Create: `validatie_samenwijzer/tests/test_db.py`

- [ ] **Stap 1: Schrijf de failing tests**

`tests/test_db.py`:
```python
import sqlite3
import pytest
from validatie_samenwijzer.db import init_db, voeg_instelling_toe, get_instelling_by_naam, \
    voeg_oer_document_toe, get_oer_document, voeg_mentor_toe, get_mentor_by_naam, \
    voeg_student_toe, get_student_by_studentnummer, get_studenten_by_mentor_id, \
    voeg_kerntaak_toe, get_kerntaken_by_oer_id, markeer_geindexeerd, \
    get_oer_ids_by_mentor_id, voeg_student_kerntaak_score_toe, \
    get_kerntaak_scores_by_student_id


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


def test_init_db_maakt_tabellen_aan(conn):
    tabellen = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"instellingen", "oer_documenten", "kerntaken", "mentoren", "mentor_oer",
            "studenten", "student_kerntaak_scores"} <= tabellen


def test_instelling_crud(conn):
    voeg_instelling_toe(conn, naam="aeres", display_naam="Aeres MBO")
    inst = get_instelling_by_naam(conn, "aeres")
    assert inst["display_naam"] == "Aeres MBO"
    assert get_instelling_by_naam(conn, "onbekend") is None


def test_oer_document_crud(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    inst = get_instelling_by_naam(conn, "rijn")
    oer_id = voeg_oer_document_toe(conn, instelling_id=inst["id"], opleiding="Verzorgende IG",
                                   crebo="25655", cohort="2025", leerweg="BOL",
                                   bestandspad="oeren/test.pdf")
    oer = get_oer_document(conn, crebo="25655", cohort="2025", leerweg="BOL")
    assert oer["id"] == oer_id
    assert oer["opleiding"] == "Verzorgende IG"
    assert oer["geindexeerd"] == 0
    markeer_geindexeerd(conn, oer_id)
    oer2 = get_oer_document(conn, "25655", "2025", "BOL")
    assert oer2["geindexeerd"] == 1


def test_kerntaken_crud(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    inst = get_instelling_by_naam(conn, "rijn")
    oer_id = voeg_oer_document_toe(conn, inst["id"], "Verzorgende IG", "25655", "2025", "BOL", "pad.pdf")
    kt_id = voeg_kerntaak_toe(conn, oer_id=oer_id, code="B1-K1", naam="Verpleegkundige zorg", type="kerntaak", volgorde=1)
    wp_id = voeg_kerntaak_toe(conn, oer_id=oer_id, code="B1-K1-W1", naam="Zorg plannen", type="werkproces", volgorde=2)
    kt_lijst = get_kerntaken_by_oer_id(conn, oer_id)
    assert len(kt_lijst) == 2
    assert kt_lijst[0]["code"] == "B1-K1"


def test_mentor_en_student_crud(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    inst = get_instelling_by_naam(conn, "rijn")
    oer_id = voeg_oer_document_toe(conn, inst["id"], "Verzorgende IG", "25655", "2025", "BOL", "pad.pdf")

    mentor_id = voeg_mentor_toe(conn, naam="Jansen", wachtwoord_hash="abc123", instelling_id=inst["id"])
    mentor = get_mentor_by_naam(conn, "Jansen")
    assert mentor["id"] == mentor_id

    voeg_student_toe(conn, studentnummer="100001", naam="Fatima", wachtwoord_hash="def456",
                     instelling_id=inst["id"], oer_id=oer_id, mentor_id=mentor_id,
                     leeftijd=19, geslacht="V", klas="VZ-1A", voortgang=0.54,
                     bsa_behaald=37.0, bsa_vereist=60.0, absence_unauthorized=8.0,
                     absence_authorized=2.0, vooropleiding="VMBO_TL", sector="Zorgenwelzijn",
                     dropout=False)
    student = get_student_by_studentnummer(conn, "100001")
    assert student["naam"] == "Fatima"
    assert student["voortgang"] == pytest.approx(0.54)

    studenten = get_studenten_by_mentor_id(conn, mentor_id)
    assert len(studenten) == 1
    assert studenten[0]["studentnummer"] == "100001"

    oer_ids = get_oer_ids_by_mentor_id(conn, mentor_id)
    assert oer_id in oer_ids


def test_student_kerntaak_score(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    inst = get_instelling_by_naam(conn, "rijn")
    oer_id = voeg_oer_document_toe(conn, inst["id"], "VZ", "25655", "2025", "BOL", "pad.pdf")
    mentor_id = voeg_mentor_toe(conn, "Mentor", "hash", inst["id"])
    voeg_student_toe(conn, "100001", "Fatima", "hash", inst["id"], oer_id, mentor_id,
                     19, "V", "klas", 0.5, 30.0, 60.0, 0.0, 0.0, "VMBO_TL", "Zorg", False)
    student = get_student_by_studentnummer(conn, "100001")
    kt_id = voeg_kerntaak_toe(conn, oer_id, "B1-K1", "Zorg", "kerntaak", 1)
    voeg_student_kerntaak_score_toe(conn, student_id=student["id"], kerntaak_id=kt_id, score=72.5)
    scores = get_kerntaak_scores_by_student_id(conn, student["id"])
    assert len(scores) == 1
    assert scores[0]["score"] == pytest.approx(72.5)
    assert scores[0]["naam"] == "Zorg"
```

- [ ] **Stap 2: Draai tests — verwacht FAIL**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
uv run pytest tests/test_db.py -v
```

Verwacht: `ModuleNotFoundError` of `ImportError`.

- [ ] **Stap 3: Schrijf db.py**

`src/validatie_samenwijzer/db.py`:
```python
"""SQLite schema-initialisatie en queries voor validatie-samenwijzer."""

import sqlite3
from pathlib import Path


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS instellingen (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            naam         TEXT NOT NULL UNIQUE,
            display_naam TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS oer_documenten (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            instelling_id INTEGER NOT NULL REFERENCES instellingen(id),
            opleiding     TEXT NOT NULL,
            crebo         TEXT NOT NULL,
            cohort        TEXT NOT NULL,
            leerweg       TEXT NOT NULL CHECK (leerweg IN ('BOL', 'BBL')),
            bestandspad   TEXT NOT NULL,
            geindexeerd   INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS kerntaken (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            oer_id   INTEGER NOT NULL REFERENCES oer_documenten(id),
            code     TEXT NOT NULL,
            naam     TEXT NOT NULL,
            type     TEXT NOT NULL CHECK (type IN ('kerntaak', 'werkproces')),
            volgorde INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS mentoren (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            naam            TEXT NOT NULL,
            wachtwoord_hash TEXT NOT NULL,
            instelling_id   INTEGER NOT NULL REFERENCES instellingen(id)
        );

        CREATE TABLE IF NOT EXISTS mentor_oer (
            mentor_id INTEGER NOT NULL REFERENCES mentoren(id),
            oer_id    INTEGER NOT NULL REFERENCES oer_documenten(id),
            PRIMARY KEY (mentor_id, oer_id)
        );

        CREATE TABLE IF NOT EXISTS studenten (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            studentnummer        TEXT NOT NULL UNIQUE,
            naam                 TEXT NOT NULL,
            wachtwoord_hash      TEXT NOT NULL,
            instelling_id        INTEGER NOT NULL REFERENCES instellingen(id),
            oer_id               INTEGER NOT NULL REFERENCES oer_documenten(id),
            mentor_id            INTEGER REFERENCES mentoren(id),
            leeftijd             INTEGER,
            geslacht             TEXT,
            klas                 TEXT,
            voortgang            REAL,
            bsa_behaald          REAL,
            bsa_vereist          REAL,
            absence_unauthorized REAL,
            absence_authorized   REAL,
            vooropleiding        TEXT,
            sector               TEXT,
            dropout              INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS student_kerntaak_scores (
            student_id  INTEGER NOT NULL REFERENCES studenten(id),
            kerntaak_id INTEGER NOT NULL REFERENCES kerntaken(id),
            score       REAL NOT NULL,
            PRIMARY KEY (student_id, kerntaak_id)
        );
    """)
    conn.commit()


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def voeg_instelling_toe(conn: sqlite3.Connection, naam: str, display_naam: str) -> int:
    cur = conn.execute(
        "INSERT OR IGNORE INTO instellingen (naam, display_naam) VALUES (?, ?)",
        (naam, display_naam),
    )
    conn.commit()
    if cur.lastrowid:
        return cur.lastrowid
    return conn.execute("SELECT id FROM instellingen WHERE naam = ?", (naam,)).fetchone()["id"]


def get_instelling_by_naam(conn: sqlite3.Connection, naam: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM instellingen WHERE naam = ?", (naam,)).fetchone()


def voeg_oer_document_toe(conn: sqlite3.Connection, instelling_id: int, opleiding: str,
                           crebo: str, cohort: str, leerweg: str, bestandspad: str) -> int:
    cur = conn.execute(
        """INSERT INTO oer_documenten
           (instelling_id, opleiding, crebo, cohort, leerweg, bestandspad)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (instelling_id, opleiding, crebo, cohort, leerweg, bestandspad),
    )
    conn.commit()
    return cur.lastrowid


def get_oer_document(conn: sqlite3.Connection, crebo: str, cohort: str,
                     leerweg: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM oer_documenten WHERE crebo = ? AND cohort = ? AND leerweg = ?",
        (crebo, cohort, leerweg),
    ).fetchone()


def markeer_geindexeerd(conn: sqlite3.Connection, oer_id: int) -> None:
    conn.execute("UPDATE oer_documenten SET geindexeerd = 1 WHERE id = ?", (oer_id,))
    conn.commit()


def voeg_kerntaak_toe(conn: sqlite3.Connection, oer_id: int, code: str, naam: str,
                      type: str, volgorde: int) -> int:
    cur = conn.execute(
        "INSERT INTO kerntaken (oer_id, code, naam, type, volgorde) VALUES (?, ?, ?, ?, ?)",
        (oer_id, code, naam, type, volgorde),
    )
    conn.commit()
    return cur.lastrowid


def get_kerntaken_by_oer_id(conn: sqlite3.Connection, oer_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM kerntaken WHERE oer_id = ? ORDER BY volgorde",
        (oer_id,),
    ).fetchall()


def voeg_mentor_toe(conn: sqlite3.Connection, naam: str, wachtwoord_hash: str,
                    instelling_id: int) -> int:
    cur = conn.execute(
        "INSERT INTO mentoren (naam, wachtwoord_hash, instelling_id) VALUES (?, ?, ?)",
        (naam, wachtwoord_hash, instelling_id),
    )
    conn.commit()
    return cur.lastrowid


def get_mentor_by_naam(conn: sqlite3.Connection, naam: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM mentoren WHERE naam = ?", (naam,)).fetchone()


def koppel_mentor_oer(conn: sqlite3.Connection, mentor_id: int, oer_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO mentor_oer (mentor_id, oer_id) VALUES (?, ?)",
        (mentor_id, oer_id),
    )
    conn.commit()


def get_oer_ids_by_mentor_id(conn: sqlite3.Connection, mentor_id: int) -> list[int]:
    rows = conn.execute(
        """SELECT DISTINCT oer_id FROM mentor_oer WHERE mentor_id = ?
           UNION
           SELECT DISTINCT oer_id FROM studenten WHERE mentor_id = ?""",
        (mentor_id, mentor_id),
    ).fetchall()
    return [r["oer_id"] for r in rows]


def voeg_student_toe(conn: sqlite3.Connection, studentnummer: str, naam: str,
                     wachtwoord_hash: str, instelling_id: int, oer_id: int,
                     mentor_id: int | None, leeftijd: int | None, geslacht: str | None,
                     klas: str | None, voortgang: float | None, bsa_behaald: float | None,
                     bsa_vereist: float | None, absence_unauthorized: float | None,
                     absence_authorized: float | None, vooropleiding: str | None,
                     sector: str | None, dropout: bool) -> int:
    cur = conn.execute(
        """INSERT INTO studenten
           (studentnummer, naam, wachtwoord_hash, instelling_id, oer_id, mentor_id,
            leeftijd, geslacht, klas, voortgang, bsa_behaald, bsa_vereist,
            absence_unauthorized, absence_authorized, vooropleiding, sector, dropout)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (studentnummer, naam, wachtwoord_hash, instelling_id, oer_id, mentor_id,
         leeftijd, geslacht, klas, voortgang, bsa_behaald, bsa_vereist,
         absence_unauthorized, absence_authorized, vooropleiding, sector, int(dropout)),
    )
    conn.commit()
    return cur.lastrowid


def get_student_by_studentnummer(conn: sqlite3.Connection,
                                 studentnummer: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM studenten WHERE studentnummer = ?", (studentnummer,)
    ).fetchone()


def get_studenten_by_mentor_id(conn: sqlite3.Connection, mentor_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM studenten WHERE mentor_id = ? ORDER BY naam",
        (mentor_id,),
    ).fetchall()


def voeg_student_kerntaak_score_toe(conn: sqlite3.Connection, student_id: int,
                                     kerntaak_id: int, score: float) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO student_kerntaak_scores (student_id, kerntaak_id, score)
           VALUES (?, ?, ?)""",
        (student_id, kerntaak_id, score),
    )
    conn.commit()


def get_kerntaak_scores_by_student_id(conn: sqlite3.Connection,
                                       student_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT sks.score, k.code, k.naam, k.type, k.volgorde
           FROM student_kerntaak_scores sks
           JOIN kerntaken k ON k.id = sks.kerntaak_id
           WHERE sks.student_id = ?
           ORDER BY k.volgorde""",
        (student_id,),
    ).fetchall()
```

- [ ] **Stap 4: Draai tests — verwacht PASS**

```bash
uv run pytest tests/test_db.py -v
```

Verwacht: alle 6 tests PASS.

- [ ] **Stap 5: Commit**

```bash
git add validatie_samenwijzer/src/validatie_samenwijzer/db.py validatie_samenwijzer/tests/test_db.py
git commit -m "feat(validatie): db.py — SQLite schema en queries"
```

---

## Task 3: auth.py — wachtwoord en rolcontrole

**Files:**
- Create: `validatie_samenwijzer/src/validatie_samenwijzer/auth.py`
- Create: `validatie_samenwijzer/tests/test_auth.py`

- [ ] **Stap 1: Schrijf de failing tests**

`tests/test_auth.py`:
```python
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from validatie_samenwijzer.db import init_db, voeg_instelling_toe, voeg_oer_document_toe, \
    voeg_mentor_toe, voeg_student_toe
from validatie_samenwijzer.auth import hash_wachtwoord, login_student, login_mentor


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    voeg_instelling_toe(c, "rijn", "Rijn IJssel")
    inst = c.execute("SELECT id FROM instellingen WHERE naam='rijn'").fetchone()
    oer_id = voeg_oer_document_toe(c, inst["id"], "VZ", "25655", "2025", "BOL", "pad.pdf")
    wh = hash_wachtwoord("Welkom123")
    mentor_id = voeg_mentor_toe(c, "Jansen", wh, inst["id"])
    voeg_student_toe(c, "100001", "Fatima", wh, inst["id"], oer_id, mentor_id,
                     19, "V", "VZ-1A", 0.54, 37.0, 60.0, 8.0, 2.0, "VMBO_TL", "Zorg", False)
    yield c
    c.close()


def test_hash_wachtwoord_is_deterministisch():
    assert hash_wachtwoord("test") == hash_wachtwoord("test")


def test_hash_wachtwoord_is_sha256():
    import hashlib
    assert hash_wachtwoord("abc") == hashlib.sha256("abc".encode()).hexdigest()


def test_login_student_geldig(conn):
    student = login_student(conn, "100001", "Welkom123")
    assert student is not None
    assert student["naam"] == "Fatima"


def test_login_student_fout_wachtwoord(conn):
    assert login_student(conn, "100001", "verkeerd") is None


def test_login_student_onbekend(conn):
    assert login_student(conn, "999999", "Welkom123") is None


def test_login_mentor_geldig(conn):
    mentor = login_mentor(conn, "Jansen", "Welkom123")
    assert mentor is not None
    assert mentor["naam"] == "Jansen"


def test_login_mentor_fout_wachtwoord(conn):
    assert login_mentor(conn, "Jansen", "verkeerd") is None
```

- [ ] **Stap 2: Draai tests — verwacht FAIL**

```bash
uv run pytest tests/test_auth.py -v
```

- [ ] **Stap 3: Schrijf auth.py**

`src/validatie_samenwijzer/auth.py`:
```python
"""Authenticatie: wachtwoord-hashing, login en Streamlit rolcontrole."""

import hashlib
import sqlite3

import streamlit as st


def hash_wachtwoord(wachtwoord: str) -> str:
    return hashlib.sha256(wachtwoord.encode()).hexdigest()


def login_student(conn: sqlite3.Connection, studentnummer: str,
                  wachtwoord: str) -> sqlite3.Row | None:
    wh = hash_wachtwoord(wachtwoord)
    return conn.execute(
        "SELECT * FROM studenten WHERE studentnummer = ? AND wachtwoord_hash = ?",
        (studentnummer, wh),
    ).fetchone()


def login_mentor(conn: sqlite3.Connection, naam: str,
                 wachtwoord: str) -> sqlite3.Row | None:
    wh = hash_wachtwoord(wachtwoord)
    return conn.execute(
        "SELECT * FROM mentoren WHERE naam = ? AND wachtwoord_hash = ?",
        (naam, wh),
    ).fetchone()


def vereist_student() -> None:
    if st.session_state.get("rol") != "student":
        st.error("🔒 Deze pagina is alleen toegankelijk voor studenten.")
        st.page_link("main.py", label="Terug naar de startpagina", icon="🏠")
        st.stop()


def vereist_mentor() -> None:
    if st.session_state.get("rol") != "mentor":
        st.error("🔒 Deze pagina is alleen toegankelijk voor mentoren.")
        st.page_link("main.py", label="Terug naar de startpagina", icon="🏠")
        st.stop()
```

- [ ] **Stap 4: Draai tests — verwacht PASS**

```bash
uv run pytest tests/test_auth.py -v
```

- [ ] **Stap 5: Commit**

```bash
git add validatie_samenwijzer/src/validatie_samenwijzer/auth.py validatie_samenwijzer/tests/test_auth.py
git commit -m "feat(validatie): auth.py — wachtwoord, login, rolcontrole"
```

---

## Task 4: _ai.py + _openai.py — client factories

**Files:**
- Create: `validatie_samenwijzer/src/validatie_samenwijzer/_ai.py`
- Create: `validatie_samenwijzer/src/validatie_samenwijzer/_openai.py`

Geen aparte tests — dit zijn dunne wrappers rond SDK-constructors die de API key uit de omgeving lezen. Gecoverd door integratie.

- [ ] **Stap 1: Schrijf _ai.py**

`src/validatie_samenwijzer/_ai.py`:
```python
"""Gedeelde Anthropic API-client helper."""

from os import environ

import anthropic


def _client(api_key: str | None = None) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key or environ.get("ANTHROPIC_API_KEY"))
```

- [ ] **Stap 2: Schrijf _openai.py**

`src/validatie_samenwijzer/_openai.py`:
```python
"""Gedeelde OpenAI client helper (embeddings)."""

from os import environ

from openai import OpenAI


def _client(api_key: str | None = None) -> OpenAI:
    return OpenAI(api_key=api_key or environ.get("OPENAI_API_KEY"))
```

- [ ] **Stap 3: Commit**

```bash
git add validatie_samenwijzer/src/validatie_samenwijzer/_ai.py validatie_samenwijzer/src/validatie_samenwijzer/_openai.py
git commit -m "feat(validatie): client factories voor Anthropic en OpenAI"
```

---

## Task 5: vector_store.py — ChromaDB wrapper

**Files:**
- Create: `validatie_samenwijzer/src/validatie_samenwijzer/vector_store.py`
- Create: `validatie_samenwijzer/tests/test_vector_store.py`

- [ ] **Stap 1: Schrijf de failing tests**

`tests/test_vector_store.py`:
```python
import pytest
import chromadb
from validatie_samenwijzer.vector_store import get_collection, voeg_chunks_toe, zoek_chunks


@pytest.fixture
def collection():
    client = chromadb.EphemeralClient()
    return get_collection(client)


def test_get_collection_geeft_collectie_terug(collection):
    assert collection.name == "oer_chunks"


def test_voeg_chunks_toe_en_zoek(collection):
    chunks = [
        {
            "id": "chunk_001",
            "tekst": "De student volgt minimaal 800 uur BPV per jaar.",
            "embedding": [0.1] * 1536,
            "metadata": {"oer_id": 1, "instelling": "rijn", "crebo": "25655",
                         "cohort": "2025", "leerweg": "BOL", "pagina": 14},
        },
        {
            "id": "chunk_002",
            "tekst": "Vrijstelling kan worden verleend bij EVC.",
            "embedding": [0.9] * 1536,
            "metadata": {"oer_id": 2, "instelling": "aeres", "crebo": "25100",
                         "cohort": "2025", "leerweg": "BOL", "pagina": 7},
        },
    ]
    voeg_chunks_toe(collection, chunks)
    assert collection.count() == 2


def test_zoek_filtert_op_oer_id(collection):
    chunks = [
        {"id": "c1", "tekst": "BPV uren verplicht.", "embedding": [0.1] * 1536,
         "metadata": {"oer_id": 1, "instelling": "rijn", "crebo": "25655",
                      "cohort": "2025", "leerweg": "BOL", "pagina": 5}},
        {"id": "c2", "tekst": "Examen afleggen.", "embedding": [0.2] * 1536,
         "metadata": {"oer_id": 2, "instelling": "aeres", "crebo": "25100",
                      "cohort": "2025", "leerweg": "BOL", "pagina": 8}},
    ]
    voeg_chunks_toe(collection, chunks)
    resultaten = zoek_chunks(collection, query_embedding=[0.1] * 1536, oer_ids=[1], n=5)
    assert all(r["metadata"]["oer_id"] == 1 for r in resultaten)


def test_zoek_geeft_lege_lijst_bij_geen_resultaten(collection):
    resultaten = zoek_chunks(collection, query_embedding=[0.5] * 1536, oer_ids=[99], n=5)
    assert resultaten == []
```

- [ ] **Stap 2: Draai tests — verwacht FAIL**

```bash
uv run pytest tests/test_vector_store.py -v
```

- [ ] **Stap 3: Schrijf vector_store.py**

`src/validatie_samenwijzer/vector_store.py`:
```python
"""ChromaDB wrapper: chunks opslaan en zoeken."""

from pathlib import Path

import chromadb


COLLECTIE_NAAM = "oer_chunks"
DREMPELWAARDE = 0.7  # cosine distance; > drempel = te weinig relevant


def get_client(chroma_path: Path) -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(chroma_path))


def get_collection(client: chromadb.ClientAPI) -> chromadb.Collection:
    return client.get_or_create_collection(
        COLLECTIE_NAAM,
        metadata={"hnsw:space": "cosine"},
    )


def voeg_chunks_toe(collection: chromadb.Collection, chunks: list[dict]) -> None:
    """Voeg chunks toe aan de collectie.

    Elk chunk dict heeft: id, tekst, embedding, metadata.
    """
    collection.add(
        ids=[c["id"] for c in chunks],
        documents=[c["tekst"] for c in chunks],
        embeddings=[c["embedding"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )


def zoek_chunks(collection: chromadb.Collection, query_embedding: list[float],
                oer_ids: list[int], n: int = 5) -> list[dict]:
    """Zoek relevante chunks gefilterd op oer_ids. Geeft lege lijst bij geen resultaten."""
    if not oer_ids:
        return []

    where = {"oer_id": {"$in": oer_ids}} if len(oer_ids) > 1 else {"oer_id": oer_ids[0]}

    try:
        resultaten = collection.query(
            query_embeddings=[query_embedding],
            n_results=n,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return []

    chunks = []
    for tekst, meta, dist in zip(
        resultaten["documents"][0],
        resultaten["metadatas"][0],
        resultaten["distances"][0],
    ):
        if dist <= DREMPELWAARDE:
            chunks.append({"tekst": tekst, "metadata": meta, "distance": dist})
    return chunks
```

- [ ] **Stap 4: Draai tests — verwacht PASS**

```bash
uv run pytest tests/test_vector_store.py -v
```

- [ ] **Stap 5: Commit**

```bash
git add validatie_samenwijzer/src/validatie_samenwijzer/vector_store.py validatie_samenwijzer/tests/test_vector_store.py
git commit -m "feat(validatie): vector_store.py — ChromaDB wrapper"
```

---

## Task 6: ingest.py — pure functies (parse, chunk, kerntaken)

**Files:**
- Create: `validatie_samenwijzer/src/validatie_samenwijzer/ingest.py` (pure functies)
- Create: `validatie_samenwijzer/tests/test_ingest.py`

- [ ] **Stap 1: Schrijf de failing tests**

`tests/test_ingest.py`:
```python
import pytest
from validatie_samenwijzer.ingest import (
    parseer_bestandsnaam,
    chunk_tekst,
    extraheer_kerntaken,
)


def test_parseer_bestandsnaam_davinci():
    r = parseer_bestandsnaam("25168BOL2025Examenplan-Gastheer-vrouw-cohort-2025.pdf")
    assert r == {"crebo": "25168", "leerweg": "BOL", "cohort": "2025"}


def test_parseer_bestandsnaam_met_spatie():
    r = parseer_bestandsnaam("25655 BBL 2024 OER Verzorgende.pdf")
    assert r == {"crebo": "25655", "leerweg": "BBL", "cohort": "2024"}


def test_parseer_bestandsnaam_geen_match():
    assert parseer_bestandsnaam("Examenplannen Biologisch Dynamische landbouw.pdf") is None


def test_chunk_tekst_verdeelt_in_stukken():
    tekst = " ".join([f"woord{i}" for i in range(600)])
    chunks = chunk_tekst(tekst, chunk_grootte=100, overlap=10)
    assert len(chunks) > 1
    assert all(len(c.split()) <= 110 for c in chunks)


def test_chunk_tekst_korte_tekst():
    tekst = "Dit is een korte tekst."
    chunks = chunk_tekst(tekst, chunk_grootte=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0] == tekst


def test_chunk_tekst_overlap():
    woorden = [f"w{i}" for i in range(25)]
    tekst = " ".join(woorden)
    chunks = chunk_tekst(tekst, chunk_grootte=20, overlap=5)
    assert len(chunks) >= 2
    # overlap: laatste woorden van chunk N zitten ook in chunk N+1
    eerste_einde = chunks[0].split()[-3:]
    tweede_begin = chunks[1].split()[:3]
    assert any(w in tweede_begin for w in eerste_einde)


def test_extraheer_kerntaken_herkent_codes():
    tekst = """
    B1-K1 Verpleegkundige zorg verlenen
    Hieronder valt: dagelijkse zorg voor cliënten.

    B1-K1-W1 Zorg plannen en organiseren
    De student plant de zorg zelfstandig.

    B1-K2 Begeleiding bieden
    Tweede kerntaak van de opleiding.
    """
    kt = extraheer_kerntaken(tekst)
    codes = [k["code"] for k in kt]
    assert "B1-K1" in codes
    assert "B1-K1-W1" in codes
    assert "B1-K2" in codes
    assert kt[0]["type"] == "kerntaak"
    assert kt[1]["type"] == "werkproces"


def test_extraheer_kerntaken_herkent_kerntaak_prefix():
    tekst = """
    Kerntaak 1: Werkzaamheden uitvoeren
    Werkproces 1.1: Plannen van werkzaamheden
    Werkproces 1.2: Uitvoeren van taken
    Kerntaak 2: Rapportage
    """
    kt = extraheer_kerntaken(tekst)
    typen = [k["type"] for k in kt]
    assert typen.count("kerntaak") >= 2
    assert typen.count("werkproces") >= 2


def test_extraheer_kerntaken_lege_tekst():
    assert extraheer_kerntaken("") == []
```

- [ ] **Stap 2: Draai tests — verwacht FAIL**

```bash
uv run pytest tests/test_ingest.py -v
```

- [ ] **Stap 3: Schrijf ingest.py (pure functies)**

`src/validatie_samenwijzer/ingest.py` (alleen de pure functies nu, CLI volgt in Task 7):
```python
"""OER-ingestie pipeline: parse → extraheer → chunk → embed → sla op."""

import re
from pathlib import Path


# ── Bestandsnaam parsen ───────────────────────────────────────────────────────

_CREBO_PATROON = re.compile(r"(\d{5})\s*[-_]?\s*(BOL|BBL)\s*[-_]?\s*(\d{4})", re.IGNORECASE)


def parseer_bestandsnaam(bestandsnaam: str) -> dict | None:
    """Haal crebo, leerweg en cohort op uit de bestandsnaam.

    Ondersteunt patronen zoals:
    - 25168BOL2025Examenplan.pdf
    - 25655 BBL 2024 OER.pdf
    Geeft None als er geen match is.
    """
    m = _CREBO_PATROON.search(bestandsnaam)
    if not m:
        return None
    return {
        "crebo": m.group(1),
        "leerweg": m.group(2).upper(),
        "cohort": m.group(3),
    }


# ── Tekst chunken ─────────────────────────────────────────────────────────────

def chunk_tekst(tekst: str, chunk_grootte: int = 500, overlap: int = 50) -> list[str]:
    """Splits tekst in chunks van ~chunk_grootte woorden met overlap.

    Respecteert lege regels als natuurlijke breekpunten waar mogelijk.
    """
    woorden = tekst.split()
    if len(woorden) <= chunk_grootte:
        return [tekst]

    chunks = []
    start = 0
    while start < len(woorden):
        einde = min(start + chunk_grootte, len(woorden))
        chunk = " ".join(woorden[start:einde])
        chunks.append(chunk)
        if einde >= len(woorden):
            break
        start += chunk_grootte - overlap
    return chunks


# ── Kerntaken extraheren ──────────────────────────────────────────────────────

_KT_PATROON = re.compile(
    r"^(B\d+-K\d+(?:-W\d+)?|Kerntaak\s+\d+|Werkproces\s+\d+\.\d+)"
    r"\s*[:\-–]?\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)


def extraheer_kerntaken(tekst: str) -> list[dict]:
    """Haal kerntaken en werkprocessen uit OER-tekst via regex.

    Herkent:
    - B1-K1, B1-K1-W1, B1-K2 (standaard MBO-notatie)
    - Kerntaak 1: ..., Werkproces 1.1: ...
    Geeft lijst van {code, naam, type, volgorde}.
    """
    if not tekst:
        return []

    resultaten = []
    volgorde = 0
    for m in _KT_PATROON.finditer(tekst):
        code = m.group(1).strip()
        naam = m.group(2).strip()[:200]
        code_lower = code.lower()

        if "werkproces" in code_lower or re.match(r"B\d+-K\d+-W\d+", code):
            type_ = "werkproces"
        else:
            type_ = "kerntaak"

        resultaten.append({"code": code, "naam": naam, "type": type_, "volgorde": volgorde})
        volgorde += 1

    return resultaten
```

- [ ] **Stap 4: Draai tests — verwacht PASS**

```bash
uv run pytest tests/test_ingest.py -v
```

- [ ] **Stap 5: Commit**

```bash
git add validatie_samenwijzer/src/validatie_samenwijzer/ingest.py validatie_samenwijzer/tests/test_ingest.py
git commit -m "feat(validatie): ingest.py — parse, chunk, kerntaken (pure functies)"
```

---

## Task 7: ingest.py — extractie + volledige CLI pipeline

**Files:**
- Modify: `validatie_samenwijzer/src/validatie_samenwijzer/ingest.py`

- [ ] **Stap 1: Voeg tekstextractie-functies toe aan ingest.py**

Voeg onderaan `ingest.py` toe (na de bestaande functies):
```python
# ── Tekstextractie per bestandstype ──────────────────────────────────────────

def extraheer_tekst_pdf(pad: Path) -> str:
    import pdfplumber
    tekst_delen = []
    with pdfplumber.open(str(pad)) as pdf:
        for pagina in pdf.pages:
            t = pagina.extract_text()
            if t:
                tekst_delen.append(t)
    return "\n\n".join(tekst_delen)


def extraheer_tekst_html(pad: Path) -> str:
    from bs4 import BeautifulSoup
    html = pad.read_text(encoding="utf-8", errors="replace")
    soep = BeautifulSoup(html, "html.parser")
    for tag in soep(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soep.get_text(separator="\n", strip=True)


def extraheer_tekst_md(pad: Path) -> str:
    return pad.read_text(encoding="utf-8", errors="replace")


def extraheer_tekst(pad: Path) -> str:
    """Extraheer tekst uit PDF, HTML of Markdown."""
    suffix = pad.suffix.lower()
    if suffix == ".pdf":
        return extraheer_tekst_pdf(pad)
    if suffix in {".html", ".htm"}:
        return extraheer_tekst_html(pad)
    if suffix == ".md":
        return extraheer_tekst_md(pad)
    raise ValueError(f"Niet-ondersteund bestandstype: {suffix}")
```

- [ ] **Stap 2: Voeg de CLI pipeline toe aan ingest.py**

Voeg onderaan toe:
```python
# ── CLI pipeline ──────────────────────────────────────────────────────────────

def _verwerk_bestand(pad: Path, instelling_naam: str, conn, collection,
                     openai_client, *, reset: bool = False) -> None:
    """Verwerk één OER-bestand: parse → extraheer → chunk → embed → sla op."""
    import logging
    logger = logging.getLogger(__name__)

    meta = parseer_bestandsnaam(pad.name)
    if meta is None:
        logger.warning("Kan crebo/leerweg/cohort niet parsen uit '%s' — overgeslagen.", pad.name)
        return

    from validatie_samenwijzer.db import (
        get_instelling_by_naam, voeg_oer_document_toe, get_oer_document,
        voeg_kerntaak_toe, markeer_geindexeerd,
    )
    from validatie_samenwijzer.vector_store import voeg_chunks_toe

    inst = get_instelling_by_naam(conn, instelling_naam)
    if inst is None:
        logger.error("Instelling '%s' niet gevonden in database.", instelling_naam)
        return

    oer = get_oer_document(conn, meta["crebo"], meta["cohort"], meta["leerweg"])
    if oer is None:
        oer_id = voeg_oer_document_toe(
            conn, instelling_id=inst["id"],
            opleiding=pad.stem[:100],
            crebo=meta["crebo"], cohort=meta["cohort"], leerweg=meta["leerweg"],
            bestandspad=str(pad),
        )
    else:
        oer_id = oer["id"]
        if oer["geindexeerd"] and not reset:
            logger.info("'%s' al geïndexeerd — overgeslagen.", pad.name)
            return

    logger.info("Verwerk '%s' (oer_id=%d)...", pad.name, oer_id)

    try:
        tekst = extraheer_tekst(pad)
    except Exception as e:
        logger.error("Extractie mislukt voor '%s': %s", pad.name, e)
        return

    kerntaken = extraheer_kerntaken(tekst)
    for kt in kerntaken:
        voeg_kerntaak_toe(conn, oer_id=oer_id, code=kt["code"], naam=kt["naam"],
                          type=kt["type"], volgorde=kt["volgorde"])

    chunks_tekst = chunk_tekst(tekst)
    if not chunks_tekst:
        return

    embeddings = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=chunks_tekst,
    )

    chunks = [
        {
            "id": f"oer{oer_id}_chunk{i}",
            "tekst": tekst,
            "embedding": emb.embedding,
            "metadata": {
                "oer_id": oer_id,
                "instelling": instelling_naam,
                "crebo": meta["crebo"],
                "cohort": meta["cohort"],
                "leerweg": meta["leerweg"],
                "pagina": 0,
            },
        }
        for i, (tekst, emb) in enumerate(zip(chunks_tekst, embeddings.data))
    ]
    voeg_chunks_toe(collection, chunks)
    markeer_geindexeerd(conn, oer_id)
    logger.info("'%s' geïndexeerd: %d chunks, %d kerntaken.", pad.name, len(chunks), len(kerntaken))


def main() -> None:
    import argparse
    import logging
    from pathlib import Path
    from dotenv import load_dotenv
    from validatie_samenwijzer.db import get_connection, init_db, voeg_instelling_toe
    from validatie_samenwijzer._openai import _client as openai_client
    from validatie_samenwijzer.vector_store import get_client as chroma_client, get_collection

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="OER-ingestie pipeline")
    parser.add_argument("--instelling", help="Verwerk alle OER's van deze instelling")
    parser.add_argument("--bestand", help="Verwerk één specifiek bestand")
    parser.add_argument("--alles", action="store_true", help="Verwerk alle instellingen")
    parser.add_argument("--reset", action="store_true", help="Herindexeer ook al-geïndexeerde OER's")
    args = parser.parse_args()

    import os
    db_path = Path(os.environ.get("DB_PATH", "data/validatie.db"))
    chroma_path = Path(os.environ.get("CHROMA_PATH", "data/chroma"))
    oeren_pad = Path(os.environ.get("OEREN_PAD", "oeren"))

    db_path.parent.mkdir(parents=True, exist_ok=True)
    chroma_path.mkdir(parents=True, exist_ok=True)

    conn = get_connection(db_path)
    init_db(conn)

    chroma = get_collection(chroma_client(chroma_path))
    oc = openai_client()

    instellingen_map = {
        "aeres": "Aeres MBO",
        "davinci": "Da Vinci College",
        "rijn_ijssel": "Rijn IJssel",
        "talland": "Talland",
        "utrecht": "ROC Utrecht",
    }

    for naam, display in instellingen_map.items():
        voeg_instelling_toe(conn, naam, display)

    def verwerk_instelling(naam: str) -> None:
        map_naam = {
            "aeres": "aeres_oeren", "davinci": "davinci_oeren",
            "rijn_ijssel": "rijn_ijssel_oer", "talland": "talland_oeren",
            "utrecht": "utrecht_oeren",
        }.get(naam, naam)
        pad = oeren_pad / map_naam
        if not pad.exists():
            logging.warning("Map '%s' niet gevonden.", pad)
            return
        for bestand in pad.iterdir():
            if bestand.suffix.lower() in {".pdf", ".html", ".htm", ".md"}:
                _verwerk_bestand(bestand, naam, conn, chroma, oc, reset=args.reset)

    if args.bestand:
        pad = Path(args.bestand)
        inst = pad.parent.name.replace("_oeren", "").replace("_oer", "")
        _verwerk_bestand(pad, inst, conn, chroma, oc, reset=args.reset)
    elif args.instelling:
        verwerk_instelling(args.instelling)
    elif args.alles:
        for naam in instellingen_map:
            verwerk_instelling(naam)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

- [ ] **Stap 3: Voeg module entry point toe aan pyproject.toml**

Voeg toe in `pyproject.toml` onder `[project]`:
```toml
[project.scripts]
ingest = "validatie_samenwijzer.ingest:main"
```

- [ ] **Stap 4: Draai bestaande tests — verwacht PASS (pure functies nog intact)**

```bash
uv run pytest tests/test_ingest.py -v
```

- [ ] **Stap 5: Commit**

```bash
git add validatie_samenwijzer/src/validatie_samenwijzer/ingest.py validatie_samenwijzer/pyproject.toml
git commit -m "feat(validatie): ingest.py — tekstextractie en CLI pipeline"
```

---

## Task 8: seed.py — testdata

**Files:**
- Create: `validatie_samenwijzer/seed/seed.py`

- [ ] **Stap 1: Schrijf seed.py**

`seed/seed.py`:
```python
"""Seed-script: testgebruikers en synthetische scores aanmaken."""

import random
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

from validatie_samenwijzer.auth import hash_wachtwoord
from validatie_samenwijzer.db import (
    get_connection, init_db,
    voeg_instelling_toe, get_instelling_by_naam,
    voeg_oer_document_toe, get_oer_document,
    voeg_mentor_toe, get_mentor_by_naam,
    voeg_student_toe, get_student_by_studentnummer,
    voeg_kerntaak_toe, get_kerntaken_by_oer_id,
    voeg_student_kerntaak_score_toe, koppel_mentor_oer,
)

load_dotenv()

WW_HASH = hash_wachtwoord("Welkom123")
RNG = random.Random(42)


def seed(db_path: Path) -> None:
    conn = get_connection(db_path)
    init_db(conn)

    # Instellingen
    voeg_instelling_toe(conn, "rijn_ijssel", "Rijn IJssel")
    voeg_instelling_toe(conn, "davinci", "Da Vinci College")
    inst_rijn = get_instelling_by_naam(conn, "rijn_ijssel")
    inst_dv = get_instelling_by_naam(conn, "davinci")

    # OER documenten (zonder echte bestanden — voor UI-test)
    oer_vz_bol = voeg_oer_document_toe(
        conn, inst_rijn["id"], "Verzorgende IG", "25655", "2025", "BOL",
        "oeren/rijn_ijssel_oer/OER_2025-2026_Verzorgende-IG_BOL.pdf",
    )
    oer_kok_bbl = voeg_oer_document_toe(
        conn, inst_dv["id"], "Kok", "25180", "2025", "BBL",
        "oeren/davinci_oeren/25180BBL2025MJP-Kok.pdf",
    )

    # Kerntaken voor VZ-BOL
    kt1 = voeg_kerntaak_toe(conn, oer_vz_bol, "B1-K1", "Verpleegkundige zorg verlenen", "kerntaak", 0)
    kt2 = voeg_kerntaak_toe(conn, oer_vz_bol, "B1-K1-W1", "Zorg plannen en organiseren", "werkproces", 1)
    kt3 = voeg_kerntaak_toe(conn, oer_vz_bol, "B1-K1-W2", "Zorg uitvoeren", "werkproces", 2)
    kt4 = voeg_kerntaak_toe(conn, oer_vz_bol, "B1-K2", "Begeleiding en ondersteuning bieden", "kerntaak", 3)
    kt5 = voeg_kerntaak_toe(conn, oer_vz_bol, "B1-K2-W1", "Begeleidingsgesprek voeren", "werkproces", 4)

    # Kerntaken voor Kok-BBL
    kk1 = voeg_kerntaak_toe(conn, oer_kok_bbl, "B1-K1", "Bereiden van gerechten", "kerntaak", 0)
    kk2 = voeg_kerntaak_toe(conn, oer_kok_bbl, "B1-K1-W1", "Mise en place uitvoeren", "werkproces", 1)
    kk3 = voeg_kerntaak_toe(conn, oer_kok_bbl, "B1-K1-W2", "Warm bereiden", "werkproces", 2)

    # Mentoren
    mentor1_id = voeg_mentor_toe(conn, "Jansen", WW_HASH, inst_rijn["id"])
    mentor2_id = voeg_mentor_toe(conn, "De Vries", WW_HASH, inst_dv["id"])
    koppel_mentor_oer(conn, mentor1_id, oer_vz_bol)
    koppel_mentor_oer(conn, mentor2_id, oer_kok_bbl)

    # Studenten
    studenten = [
        ("100001", "Fatima Al-Hassan", inst_rijn["id"], oer_vz_bol, mentor1_id,
         19, "V", "VZ-1A", 0.54, 37.0, 60.0, 8.0, 2.0, "VMBO_TL", "Zorgenwelzijn", False),
        ("100002", "Daan Vermeer", inst_rijn["id"], oer_vz_bol, mentor1_id,
         20, "M", "VZ-1A", 0.78, 52.0, 60.0, 1.0, 4.0, "VMBO_KB", "Zorgenwelzijn", False),
        ("100003", "Lina Kowalski", inst_dv["id"], oer_kok_bbl, mentor2_id,
         18, "V", "HO-1B", 0.38, 24.0, 60.0, 14.0, 0.0, "VMBO_BB", "Economie", False),
    ]

    kt_per_oer = {
        oer_vz_bol: [kt1, kt2, kt3, kt4, kt5],
        oer_kok_bbl: [kk1, kk2, kk3],
    }

    for nr, naam, inst_id, oer_id, mentor_id, lft, gsl, klas, vg, bsa_b, bsa_v, afwn, afwg, voopl, sect, drop in studenten:
        if get_student_by_studentnummer(conn, nr):
            continue
        st_id = voeg_student_toe(
            conn, nr, naam, WW_HASH, inst_id, oer_id, mentor_id,
            lft, gsl, klas, vg, bsa_b, bsa_v, afwn, afwg, voopl, sect, drop,
        )
        for kt_id in kt_per_oer[oer_id]:
            basis = vg * 100
            score = max(0.0, min(100.0, basis + RNG.gauss(0, 12)))
            voeg_student_kerntaak_score_toe(conn, st_id, kt_id, round(score, 1))

    print("Seed voltooid.")
    print(f"  Studenten: {len(studenten)}")
    print("  Mentoren: Jansen (rijn_ijssel), De Vries (davinci)")
    print("  Wachtwoord voor allen: Welkom123")
    conn.close()


if __name__ == "__main__":
    import os
    db_pad = Path(os.environ.get("DB_PATH", "data/validatie.db"))
    db_pad.parent.mkdir(parents=True, exist_ok=True)
    seed(db_pad)
```

- [ ] **Stap 2: Draai seed-script**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
uv run python seed/seed.py
```

Verwacht:
```
Seed voltooid.
  Studenten: 3
  Mentoren: Jansen (rijn_ijssel), De Vries (davinci)
  Wachtwoord voor allen: Welkom123
```

- [ ] **Stap 3: Commit**

```bash
git add validatie_samenwijzer/seed/seed.py
git commit -m "feat(validatie): seed.py — testgebruikers en synthetische scores"
```

---

## Task 9: chat.py — retrieval + prompt + streaming

**Files:**
- Create: `validatie_samenwijzer/src/validatie_samenwijzer/chat.py`
- Create: `validatie_samenwijzer/tests/test_chat.py`

- [ ] **Stap 1: Schrijf de failing tests**

`tests/test_chat.py`:
```python
from unittest.mock import MagicMock, patch
import pytest
from validatie_samenwijzer.chat import bouw_berichten, LAGE_RELEVANTIE_BERICHT


def test_bouw_berichten_zonder_chunks():
    history = []
    chunks = []
    berichten = bouw_berichten(
        chat_history=history,
        chunks=chunks,
        vraag="Hoeveel uren BPV?",
        opleiding="Verzorgende IG",
        instelling="Rijn IJssel",
    )
    # systeem + gebruiker
    assert berichten[0]["role"] == "user"
    assert "Hoeveel uren BPV?" in berichten[0]["content"]


def test_bouw_berichten_met_chunks():
    chunks = [
        {"tekst": "Minimaal 800 uur BPV.", "metadata": {"pagina": 14}, "distance": 0.2},
        {"tekst": "BPV wordt geregistreerd.", "metadata": {"pagina": 17}, "distance": 0.3},
    ]
    berichten = bouw_berichten(
        chat_history=[],
        chunks=chunks,
        vraag="Hoeveel uren?",
        opleiding="Verzorgende IG",
        instelling="Rijn IJssel",
    )
    content = berichten[0]["content"]
    assert "Minimaal 800 uur BPV." in content
    assert "BPV wordt geregistreerd." in content


def test_bouw_berichten_behoudt_history():
    history = [
        {"role": "user", "content": "Vraag 1"},
        {"role": "assistant", "content": "Antwoord 1"},
    ]
    berichten = bouw_berichten(
        chat_history=history,
        chunks=[],
        vraag="Vraag 2",
        opleiding="Kok",
        instelling="Da Vinci",
    )
    rollen = [b["role"] for b in berichten]
    assert rollen == ["user", "assistant", "user"]


def test_lage_relevantie_bericht_is_string():
    assert isinstance(LAGE_RELEVANTIE_BERICHT, str)
    assert len(LAGE_RELEVANTIE_BERICHT) > 10
```

- [ ] **Stap 2: Draai tests — verwacht FAIL**

```bash
uv run pytest tests/test_chat.py -v
```

- [ ] **Stap 3: Schrijf chat.py**

`src/validatie_samenwijzer/chat.py`:
```python
"""Hybride OER-chat: retrieval + prompt-opbouw + Claude streaming."""

from collections.abc import Generator

import anthropic

LAGE_RELEVANTIE_BERICHT = (
    "Ik kon geen relevante informatie over deze vraag vinden in jouw OER. "
    "Controleer of de vraag betrekking heeft op jouw opleiding, of raadpleeg "
    "het volledige OER via 'Mijn OER'."
)

_SYSTEEM_TEMPLATE = (
    "Je bent een OER-assistent voor de opleiding {opleiding} bij {instelling}. "
    "Beantwoord vragen uitsluitend op basis van de aangeleverde OER-passages. "
    "Als de passages onvoldoende informatie bevatten, zeg dat dan expliciet. "
    "Antwoord in het Nederlands, beknopt en helder."
)


def embed_vraag(openai_client, vraag: str) -> list[float]:
    """Maak een embedding van de gebruikersvraag."""
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=vraag,
    )
    return response.data[0].embedding


def bouw_berichten(
    chat_history: list[dict],
    chunks: list[dict],
    vraag: str,
    opleiding: str,
    instelling: str,
) -> list[dict]:
    """Bouw de berichtenlijst op voor de Claude API.

    Geeft een lijst van {role, content} dicts terug.
    Het systeem-bericht wordt inline meegestuurd als eerste user-bericht
    zodat de conversatiehistorie klopt bij doorvragen.
    """
    systeem = _SYSTEEM_TEMPLATE.format(opleiding=opleiding, instelling=instelling)

    if chunks:
        passages = "\n\n".join(
            f"[Pagina {c['metadata'].get('pagina', '?')}]\n{c['tekst']}" for c in chunks
        )
        context = f"{systeem}\n\nRelevante OER-passages:\n{passages}"
    else:
        context = systeem

    berichten = list(chat_history)

    if not berichten:
        eerste_vraag = f"{context}\n\nVraag: {vraag}"
        berichten.append({"role": "user", "content": eerste_vraag})
    else:
        berichten.append({"role": "user", "content": vraag})

    return berichten


def genereer_antwoord(
    client: anthropic.Anthropic,
    berichten: list[dict],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1024,
) -> Generator[str, None, None]:
    """Stream Claude-antwoord als generator van tekst-fragmenten."""
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        messages=berichten,
    ) as stream:
        yield from stream.text_stream
```

- [ ] **Stap 4: Draai tests — verwacht PASS**

```bash
uv run pytest tests/test_chat.py -v
```

- [ ] **Stap 5: Commit**

```bash
git add validatie_samenwijzer/src/validatie_samenwijzer/chat.py validatie_samenwijzer/tests/test_chat.py
git commit -m "feat(validatie): chat.py — retrieval, prompt-opbouw, Claude streaming"
```

---

## Task 10: styles.py — CSS + navigatie

**Files:**
- Create: `validatie_samenwijzer/src/validatie_samenwijzer/styles.py`

- [ ] **Stap 1: Schrijf styles.py**

`src/validatie_samenwijzer/styles.py`:
```python
"""EduPulse huisstijl CSS en navigatie voor validatie-samenwijzer."""

DONKERBLAUW = "#1a237e"
WIT = "#ffffff"
GRIJS_BG = "#f5f5f5"
GROEN = "#43a047"
ORANJE = "#fb8c00"
ROOD = "#c62828"
GEEL_BRON = "#fffde7"
GEEL_RAND = "#f0c040"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
    background-color: {WIT};
    color: #1a1a1a;
}}

/* Sidebar verbergen */
[data-testid="stSidebar"], [data-testid="collapsedControl"] {{
    display: none !important;
}}

/* Topbalk-ruimte */
.block-container {{
    padding-top: 5rem !important;
    padding-bottom: 4rem !important;
    max-width: 960px;
}}

/* Navigatiebalk */
.nav-bar {{
    position: fixed;
    top: 0; left: 0; right: 0;
    background: {DONKERBLAUW};
    color: {WIT};
    padding: 0.6rem 1.5rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    z-index: 1000;
    font-size: 0.85rem;
}}

.nav-bar a {{
    color: {WIT};
    text-decoration: none;
    padding: 0.3rem 0.7rem;
    border-radius: 4px;
    white-space: nowrap;
}}

.nav-bar a:hover {{ background: rgba(255,255,255,0.15); }}
.nav-bar .nav-user {{ margin-left: auto; opacity: 0.75; font-size: 0.78rem; }}

/* Voortgangsbalk */
.progress-bar-bg {{
    background: #e0e0e0; border-radius: 6px; height: 8px; margin: 4px 0;
}}
.progress-bar-fill {{
    border-radius: 6px; height: 8px;
    background: {GROEN};
}}

/* Bronkaartje */
.bron-kaartje {{
    background: {GEEL_BRON};
    border: 1px solid {GEEL_RAND};
    border-radius: 8px;
    padding: 0.7rem 1rem;
    font-size: 0.82rem;
    margin-bottom: 0.4rem;
}}

/* Chat-bubbles */
.chat-vraag {{
    background: #e8eaf6;
    border-radius: 12px 12px 12px 0;
    padding: 0.7rem 1rem;
    margin-bottom: 0.3rem;
    max-width: 80%;
    font-size: 0.88rem;
}}
.chat-antwoord {{
    background: #e8f5e9;
    border-radius: 12px 12px 0 12px;
    padding: 0.7rem 1rem;
    margin-bottom: 0.3rem;
    font-size: 0.88rem;
}}

/* Footer */
.footer {{
    position: fixed; bottom: 0; left: 0; right: 0;
    background: {WIT};
    border-top: 1px solid #e0e0e0;
    padding: 0.4rem 1.5rem;
    font-size: 0.68rem;
    color: #888;
    text-align: center;
    z-index: 999;
}}
</style>
"""

_NAV_STUDENT = [
    ("💬 OER-assistent", "pages/1_oer_assistent.py"),
    ("📄 Mijn OER", "pages/2_mijn_oer.py"),
    ("📊 Mijn voortgang", "pages/3_mijn_voortgang.py"),
]

_NAV_MENTOR = [
    ("👥 Mijn studenten", "pages/4_mijn_studenten.py"),
    ("🎓 Begeleidingssessie", "pages/5_begeleidingssessie.py"),
]


def render_nav() -> None:
    import streamlit as st

    rol = st.session_state.get("rol")
    if not rol:
        return

    nav_items = _NAV_STUDENT if rol == "student" else _NAV_MENTOR
    gebruiker = st.session_state.get("gebruiker_naam", "")
    opleiding = st.session_state.get("opleiding", "")

    cols = st.columns([2] * len(nav_items) + [4, 1])
    for i, (label, page) in enumerate(nav_items):
        with cols[i]:
            st.page_link(page, label=label)
    with cols[-2]:
        st.markdown(
            f'<span style="color:white;font-size:0.78rem">{gebruiker} · {opleiding}</span>',
            unsafe_allow_html=True,
        )
    with cols[-1]:
        st.page_link("pages/uitloggen.py", label="🚪")


def render_footer() -> None:
    import streamlit as st
    st.markdown(
        '<div class="footer">Samenwijzer OER-assistent · CEDA 2026 · Npuls</div>',
        unsafe_allow_html=True,
    )
```

- [ ] **Stap 2: Commit**

```bash
git add validatie_samenwijzer/src/validatie_samenwijzer/styles.py
git commit -m "feat(validatie): styles.py — CSS, navigatie, footer"
```

---

## Task 11: app/main.py — loginpagina

**Files:**
- Create: `validatie_samenwijzer/app/main.py`

- [ ] **Stap 1: Schrijf main.py**

`app/main.py`:
```python
"""Login + sessie-initialisatie voor validatie-samenwijzer."""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="OER-assistent · Login", page_icon="📚", layout="centered")

from validatie_samenwijzer.styles import CSS, render_footer  # noqa: E402
from validatie_samenwijzer.db import (  # noqa: E402
    get_connection, init_db, get_oer_document,
    get_oer_ids_by_mentor_id,
)
from validatie_samenwijzer.auth import login_student, login_mentor  # noqa: E402

st.markdown(CSS, unsafe_allow_html=True)

DB_PATH = Path(os.environ.get("DB_PATH", "data/validatie.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@st.cache_resource
def _conn():
    conn = get_connection(DB_PATH)
    init_db(conn)
    return conn


def _sla_student_op(student) -> None:
    oer = _conn().execute(
        "SELECT oer_documenten.*, instellingen.display_naam "
        "FROM oer_documenten JOIN instellingen ON instellingen.id = oer_documenten.instelling_id "
        "WHERE oer_documenten.id = ?",
        (student["oer_id"],),
    ).fetchone()
    st.session_state.update({
        "rol": "student",
        "gebruiker_id": student["id"],
        "gebruiker_naam": student["naam"],
        "studentnummer": student["studentnummer"],
        "oer_id": student["oer_id"],
        "opleiding": oer["opleiding"] if oer else "",
        "instelling": oer["display_naam"] if oer else "",
        "crebo": oer["crebo"] if oer else "",
        "chat_history": [],
    })


def _sla_mentor_op(mentor) -> None:
    oer_ids = get_oer_ids_by_mentor_id(_conn(), mentor["id"])
    instelling = _conn().execute(
        "SELECT display_naam FROM instellingen WHERE id = ?",
        (mentor["instelling_id"],),
    ).fetchone()
    st.session_state.update({
        "rol": "mentor",
        "gebruiker_id": mentor["id"],
        "gebruiker_naam": mentor["naam"],
        "oer_ids": oer_ids,
        "instelling": instelling["display_naam"] if instelling else "",
        "opleiding": "Mentor",
        "actieve_student": None,
        "chat_history": [],
    })


if st.session_state.get("rol") == "student":
    st.switch_page("pages/1_oer_assistent.py")
elif st.session_state.get("rol") == "mentor":
    st.switch_page("pages/4_mijn_studenten.py")

st.title("📚 OER-assistent")
st.caption("Samenwijzer · CEDA 2026")

tab_student, tab_mentor = st.tabs(["Student", "Mentor"])

with tab_student:
    with st.form("login_student"):
        studentnummer = st.text_input("Studentnummer")
        ww = st.text_input("Wachtwoord", type="password")
        if st.form_submit_button("Inloggen als student", use_container_width=True):
            student = login_student(_conn(), studentnummer.strip(), ww)
            if student:
                _sla_student_op(student)
                st.switch_page("pages/1_oer_assistent.py")
            else:
                st.error("Onbekend studentnummer of onjuist wachtwoord.")

with tab_mentor:
    with st.form("login_mentor"):
        naam = st.text_input("Naam")
        ww2 = st.text_input("Wachtwoord", type="password")
        if st.form_submit_button("Inloggen als mentor", use_container_width=True):
            mentor = login_mentor(_conn(), naam.strip(), ww2)
            if mentor:
                _sla_mentor_op(mentor)
                st.switch_page("pages/4_mijn_studenten.py")
            else:
                st.error("Onbekende naam of onjuist wachtwoord.")

render_footer()
```

- [ ] **Stap 2: Commit**

```bash
git add validatie_samenwijzer/app/main.py
git commit -m "feat(validatie): app/main.py — loginpagina"
```

---

## Task 12: Student-pagina's

**Files:**
- Create: `validatie_samenwijzer/app/pages/1_oer_assistent.py`
- Create: `validatie_samenwijzer/app/pages/2_mijn_oer.py`
- Create: `validatie_samenwijzer/app/pages/3_mijn_voortgang.py`

- [ ] **Stap 1: Schrijf 1_oer_assistent.py (student)**

`app/pages/1_oer_assistent.py`:
```python
"""Student: hybride OER-chat met doorvraagmogelijkheid."""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="OER-assistent", page_icon="💬", layout="wide")

from validatie_samenwijzer.styles import CSS, render_nav, render_footer
from validatie_samenwijzer.auth import vereist_student
from validatie_samenwijzer.db import get_connection, init_db
from validatie_samenwijzer.vector_store import get_client, get_collection, zoek_chunks
from validatie_samenwijzer.chat import embed_vraag, bouw_berichten, genereer_antwoord, LAGE_RELEVANTIE_BERICHT
from validatie_samenwijzer._ai import _client as ai_client
from validatie_samenwijzer._openai import _client as openai_client

st.markdown(CSS, unsafe_allow_html=True)
vereist_student()
render_nav()

DB_PATH = Path(os.environ.get("DB_PATH", "data/validatie.db"))
CHROMA_PATH = Path(os.environ.get("CHROMA_PATH", "data/chroma"))

@st.cache_resource
def _collection():
    client = get_client(CHROMA_PATH)
    return get_collection(client)

opleiding = st.session_state.get("opleiding", "")
instelling = st.session_state.get("instelling", "")
oer_id = st.session_state.get("oer_id")

st.subheader(f"💬 OER-assistent — {opleiding}")
st.caption(f"{instelling} · Jouw vragen, beantwoord vanuit jouw OER")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "chat_bronnen" not in st.session_state:
    st.session_state.chat_bronnen = []

# Toon gesprekshistorie
for i, bericht in enumerate(st.session_state.chat_history):
    if bericht["role"] == "user":
        vraag_tekst = bericht["content"].split("Vraag:")[-1].strip() if "Vraag:" in bericht["content"] else bericht["content"]
        st.markdown(f'<div class="chat-vraag">💬 {vraag_tekst}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-antwoord">{bericht["content"]}</div>', unsafe_allow_html=True)
        if i < len(st.session_state.chat_bronnen):
            bronnen = st.session_state.chat_bronnen[i // 2]
            if bronnen:
                cols = st.columns(min(len(bronnen), 2))
                for j, bron in enumerate(bronnen):
                    with cols[j % 2]:
                        pagina = bron["metadata"].get("pagina", "?")
                        st.markdown(
                            f'<div class="bron-kaartje">📄 <strong>Pagina {pagina}</strong><br>'
                            f'<em>{bron["tekst"][:200]}…</em></div>',
                            unsafe_allow_html=True,
                        )

# Invoerveld
vraag = st.chat_input("Stel een vraag over jouw OER…")
if vraag and oer_id:
    embedding = embed_vraag(openai_client(), vraag)
    chunks = zoek_chunks(_collection(), embedding, oer_ids=[oer_id])

    berichten = bouw_berichten(
        chat_history=st.session_state.chat_history,
        chunks=chunks,
        vraag=vraag,
        opleiding=opleiding,
        instelling=instelling,
    )

    st.markdown(f'<div class="chat-vraag">💬 {vraag}</div>', unsafe_allow_html=True)

    if not chunks:
        antwoord = LAGE_RELEVANTIE_BERICHT
        st.info(antwoord)
    else:
        with st.spinner("Even zoeken in jouw OER…"):
            antwoord = st.write_stream(genereer_antwoord(ai_client(), berichten))

        cols = st.columns(min(len(chunks), 2))
        for j, bron in enumerate(chunks):
            with cols[j % 2]:
                pagina = bron["metadata"].get("pagina", "?")
                st.markdown(
                    f'<div class="bron-kaartje">📄 <strong>Pagina {pagina}</strong><br>'
                    f'<em>{bron["tekst"][:200]}…</em></div>',
                    unsafe_allow_html=True,
                )

    st.session_state.chat_history.extend([
        {"role": "user", "content": vraag},
        {"role": "assistant", "content": antwoord},
    ])
    st.session_state.chat_bronnen.append(chunks)

render_footer()
```

- [ ] **Stap 2: Schrijf 2_mijn_oer.py**

`app/pages/2_mijn_oer.py`:
```python
"""Student: volledig OER inzien of downloaden."""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Mijn OER", page_icon="📄", layout="wide")

from validatie_samenwijzer.styles import CSS, render_nav, render_footer
from validatie_samenwijzer.auth import vereist_student
from validatie_samenwijzer.db import get_connection, init_db

st.markdown(CSS, unsafe_allow_html=True)
vereist_student()
render_nav()

DB_PATH = Path(os.environ.get("DB_PATH", "data/validatie.db"))
OEREN_PAD = Path(os.environ.get("OEREN_PAD", "oeren"))

@st.cache_resource
def _conn():
    conn = get_connection(DB_PATH)
    init_db(conn)
    return conn

oer_id = st.session_state.get("oer_id")
opleiding = st.session_state.get("opleiding", "")

st.subheader(f"📄 Mijn OER — {opleiding}")

oer = _conn().execute(
    "SELECT * FROM oer_documenten WHERE id = ?", (oer_id,)
).fetchone()

if not oer:
    st.warning("Geen OER gekoppeld aan jouw profiel.")
else:
    st.caption(f"Crebo {oer['crebo']} · {oer['leerweg']} · Cohort {oer['cohort']}")
    pad = Path(oer["bestandspad"])

    if not pad.is_absolute():
        pad = OEREN_PAD.parent / pad

    if pad.exists() and pad.suffix.lower() == ".pdf":
        with open(pad, "rb") as f:
            pdf_bytes = f.read()
        st.download_button(
            label="⬇️ Download OER als PDF",
            data=pdf_bytes,
            file_name=pad.name,
            mime="application/pdf",
        )
        st.markdown("---")
        st.components.v1.iframe(
            src=f"data:application/pdf;base64,",
            height=800,
        )
        # PDF inline tonen via base64
        import base64
        b64 = base64.b64encode(pdf_bytes).decode()
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="800px"></iframe>',
            unsafe_allow_html=True,
        )
    elif pad.exists() and pad.suffix.lower() in {".html", ".htm"}:
        from validatie_samenwijzer.ingest import extraheer_tekst_html
        tekst = extraheer_tekst_html(pad)
        st.text_area("OER-inhoud", tekst, height=600)
    elif pad.exists() and pad.suffix.lower() == ".md":
        st.markdown(pad.read_text(encoding="utf-8"))
    else:
        st.warning(f"OER-bestand niet gevonden op: {pad}")
        st.info("Vraag je mentor of beheerder om het bestand te uploaden.")

render_footer()
```

- [ ] **Stap 3: Schrijf 3_mijn_voortgang.py**

`app/pages/3_mijn_voortgang.py`:
```python
"""Student: kerntaakscores, BSA en aanwezigheid."""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Mijn voortgang", page_icon="📊", layout="wide")

from validatie_samenwijzer.styles import CSS, render_nav, render_footer, GROEN, ORANJE, ROOD
from validatie_samenwijzer.auth import vereist_student
from validatie_samenwijzer.db import (
    get_connection, init_db, get_student_by_studentnummer,
    get_kerntaak_scores_by_student_id,
)

st.markdown(CSS, unsafe_allow_html=True)
vereist_student()
render_nav()

DB_PATH = Path(os.environ.get("DB_PATH", "data/validatie.db"))

@st.cache_resource
def _conn():
    conn = get_connection(DB_PATH)
    init_db(conn)
    return conn

studentnummer = st.session_state.get("studentnummer")
student = get_student_by_studentnummer(_conn(), studentnummer)

st.subheader("📊 Mijn voortgang")

if not student:
    st.error("Studentprofiel niet gevonden.")
    st.stop()

vg = student["voortgang"] or 0.0
bsa_b = student["bsa_behaald"] or 0.0
bsa_v = student["bsa_vereist"] or 60.0
bsa_pct = min(bsa_b / bsa_v, 1.0) if bsa_v else 0.0
afwn = student["absence_unauthorized"] or 0.0

col1, col2, col3 = st.columns(3)
with col1:
    kleur = GROEN if vg >= 0.7 else (ORANJE if vg >= 0.5 else ROOD)
    st.metric("Voortgang", f"{vg*100:.0f}%")
    st.markdown(
        f'<div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{vg*100:.0f}%;background:{kleur}"></div></div>',
        unsafe_allow_html=True,
    )
with col2:
    kleur_bsa = GROEN if bsa_pct >= 0.8 else (ORANJE if bsa_pct >= 0.6 else ROOD)
    st.metric("BSA behaald", f"{bsa_b:.0f} / {bsa_v:.0f} uur", f"{bsa_pct*100:.0f}%")
with col3:
    kleur_afw = ROOD if afwn > 10 else (ORANJE if afwn > 5 else GROEN)
    st.metric("Ongeoorl. afwezigheid", f"{afwn:.0f} uur")

st.markdown("---")
st.subheader("Kerntaken en werkprocessen")

scores = get_kerntaak_scores_by_student_id(_conn(), student["id"])
if not scores:
    st.info("Nog geen scores beschikbaar.")
else:
    kerntaken = [s for s in scores if s["type"] == "kerntaak"]
    werkprocessen = [s for s in scores if s["type"] == "werkproces"]

    if kerntaken:
        st.markdown("**Kerntaken**")
        for kt in kerntaken:
            pct = kt["score"] / 100
            kleur = GROEN if pct >= 0.7 else (ORANJE if pct >= 0.5 else ROOD)
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"_{kt['naam']}_")
                st.markdown(
                    f'<div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{kt["score"]:.0f}%;background:{kleur}"></div></div>',
                    unsafe_allow_html=True,
                )
            with col_b:
                st.markdown(f"**{kt['score']:.0f}**")

    if werkprocessen:
        with st.expander("Werkprocessen"):
            for wp in werkprocessen:
                pct = wp["score"] / 100
                kleur = GROEN if pct >= 0.7 else (ORANJE if pct >= 0.5 else ROOD)
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.caption(wp["naam"])
                    st.markdown(
                        f'<div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{wp["score"]:.0f}%;background:{kleur}"></div></div>',
                        unsafe_allow_html=True,
                    )
                with col_b:
                    st.caption(f"{wp['score']:.0f}")

render_footer()
```

- [ ] **Stap 4: Commit**

```bash
git add validatie_samenwijzer/app/pages/1_oer_assistent.py validatie_samenwijzer/app/pages/2_mijn_oer.py validatie_samenwijzer/app/pages/3_mijn_voortgang.py
git commit -m "feat(validatie): student-pagina's — OER-assistent, Mijn OER, Mijn voortgang"
```

---

## Task 13: Mentor-pagina's + uitloggen

**Files:**
- Create: `validatie_samenwijzer/app/pages/4_mijn_studenten.py`
- Create: `validatie_samenwijzer/app/pages/5_begeleidingssessie.py`
- Create: `validatie_samenwijzer/app/pages/uitloggen.py`

- [ ] **Stap 1: Schrijf 4_mijn_studenten.py**

`app/pages/4_mijn_studenten.py`:
```python
"""Mentor: studentenoverzicht met voortgangsbadges."""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Mijn studenten", page_icon="👥", layout="wide")

from validatie_samenwijzer.styles import CSS, render_nav, render_footer, GROEN, ORANJE, ROOD
from validatie_samenwijzer.auth import vereist_mentor
from validatie_samenwijzer.db import get_connection, init_db, get_studenten_by_mentor_id

st.markdown(CSS, unsafe_allow_html=True)
vereist_mentor()
render_nav()

DB_PATH = Path(os.environ.get("DB_PATH", "data/validatie.db"))

@st.cache_resource
def _conn():
    conn = get_connection(DB_PATH)
    init_db(conn)
    return conn

mentor_id = st.session_state.get("gebruiker_id")
st.subheader("👥 Mijn studenten")

studenten = get_studenten_by_mentor_id(_conn(), mentor_id)

if not studenten:
    st.info("Geen studenten gekoppeld aan jouw account.")
    st.stop()

st.caption(f"{len(studenten)} studenten · Klik op een student om een begeleidingssessie te starten")

for student in studenten:
    vg = student["voortgang"] or 0.0
    bsa_b = student["bsa_behaald"] or 0.0
    bsa_v = student["bsa_vereist"] or 60.0
    bsa_pct = min(bsa_b / bsa_v, 1.0) if bsa_v else 0.0
    afwn = student["absence_unauthorized"] or 0.0

    kleur_vg = GROEN if vg >= 0.7 else (ORANJE if vg >= 0.5 else ROOD)
    kleur_bsa = GROEN if bsa_pct >= 0.8 else (ORANJE if bsa_pct >= 0.6 else ROOD)
    kleur_afw = ROOD if afwn > 10 else (ORANJE if afwn > 5 else GROEN)

    with st.container(border=True):
        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
        with col1:
            st.markdown(f"**{student['naam']}**")
            oer = _conn().execute(
                "SELECT opleiding, leerweg, cohort FROM oer_documenten WHERE id = ?",
                (student["oer_id"],),
            ).fetchone()
            if oer:
                st.caption(f"{oer['opleiding']} · {oer['leerweg']} · {oer['cohort']}")
        with col2:
            st.markdown(f"<span style='color:{kleur_vg}'>▸ Voortgang: **{vg*100:.0f}%**</span>",
                        unsafe_allow_html=True)
        with col3:
            st.markdown(f"<span style='color:{kleur_bsa}'>▸ BSA: **{bsa_pct*100:.0f}%**</span>",
                        unsafe_allow_html=True)
        with col4:
            st.markdown(f"<span style='color:{kleur_afw}'>▸ Afwez.: **{afwn:.0f} uur**</span>",
                        unsafe_allow_html=True)
        with col5:
            if st.button("🎓 Begeleiden", key=f"begeleid_{student['id']}"):
                st.session_state["actieve_student"] = dict(student)
                st.session_state["chat_history"] = []
                st.session_state["chat_bronnen"] = []
                st.switch_page("pages/5_begeleidingssessie.py")

render_footer()
```

- [ ] **Stap 2: Schrijf 5_begeleidingssessie.py**

`app/pages/5_begeleidingssessie.py`:
```python
"""Mentor: studentprofiel + OER-assistent naast elkaar."""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Begeleidingssessie", page_icon="🎓", layout="wide")

from validatie_samenwijzer.styles import CSS, render_nav, render_footer, GROEN, ORANJE, ROOD
from validatie_samenwijzer.auth import vereist_mentor
from validatie_samenwijzer.db import (
    get_connection, init_db,
    get_kerntaak_scores_by_student_id,
)
from validatie_samenwijzer.vector_store import get_client, get_collection, zoek_chunks
from validatie_samenwijzer.chat import embed_vraag, bouw_berichten, genereer_antwoord, LAGE_RELEVANTIE_BERICHT
from validatie_samenwijzer._ai import _client as ai_client
from validatie_samenwijzer._openai import _client as openai_client

st.markdown(CSS, unsafe_allow_html=True)
vereist_mentor()
render_nav()

DB_PATH = Path(os.environ.get("DB_PATH", "data/validatie.db"))
CHROMA_PATH = Path(os.environ.get("CHROMA_PATH", "data/chroma"))

@st.cache_resource
def _conn():
    conn = get_connection(DB_PATH)
    init_db(conn)
    return conn

@st.cache_resource
def _collection():
    return get_collection(get_client(CHROMA_PATH))

student = st.session_state.get("actieve_student")
if not student:
    st.warning("Geen student geselecteerd. Ga terug naar 'Mijn studenten'.")
    st.page_link("pages/4_mijn_studenten.py", label="← Mijn studenten")
    st.stop()

oer = _conn().execute(
    "SELECT oer_documenten.*, instellingen.display_naam "
    "FROM oer_documenten JOIN instellingen ON instellingen.id = oer_documenten.instelling_id "
    "WHERE oer_documenten.id = ?",
    (student["oer_id"],),
).fetchone()

opleiding = oer["opleiding"] if oer else ""
instelling = oer["display_naam"] if oer else ""

st.subheader(f"🎓 Begeleidingssessie — {student['naam']}")
st.caption(f"{opleiding} · {instelling}")

col_profiel, col_chat = st.columns([1.3, 2])

# ── Linkerpaneel: studentprofiel ──────────────────────────────────────────────
with col_profiel:
    vg = student.get("voortgang") or 0.0
    bsa_b = student.get("bsa_behaald") or 0.0
    bsa_v = student.get("bsa_vereist") or 60.0
    bsa_pct = min(bsa_b / bsa_v, 1.0) if bsa_v else 0.0
    afwn = student.get("absence_unauthorized") or 0.0

    kleur_vg = GROEN if vg >= 0.7 else (ORANJE if vg >= 0.5 else ROOD)

    with st.container(border=True):
        st.markdown("**Voortgang**")
        st.markdown(f"<span style='font-size:1.4rem;font-weight:700;color:{kleur_vg}'>{vg*100:.0f}%</span>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{vg*100:.0f}%;background:{kleur_vg}"></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(f"BSA: **{bsa_b:.0f}/{bsa_v:.0f} uur** ({bsa_pct*100:.0f}%)")
        kleur_afw = ROOD if afwn > 10 else (ORANJE if afwn > 5 else GROEN)
        st.markdown(f"Ongeoorl. afwez.: <span style='color:{kleur_afw}'><b>{afwn:.0f} uur</b></span>", unsafe_allow_html=True)

    scores = get_kerntaak_scores_by_student_id(_conn(), student["id"])
    if scores:
        with st.container(border=True):
            st.markdown("**Kerntaken**")
            for s in scores:
                if s["type"] == "kerntaak":
                    kleur = GROEN if s["score"] >= 70 else (ORANJE if s["score"] >= 50 else ROOD)
                    st.markdown(f"<small>{s['naam']}</small>", unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{s["score"]:.0f}%;background:{kleur}"></div></div>',
                        unsafe_allow_html=True,
                    )

    # Bespreekpuntsuggesties
    punten = []
    if vg < 0.5:
        punten.append("⚠️ Lage voortgang — doorvragen naar oorzaak")
    if bsa_pct < 0.7:
        punten.append("⚠️ BSA-risico — aanwezigheid bespreken")
    if afwn > 8:
        punten.append("⚠️ Hoge ongeoorloofde afwezigheid")
    lage_kt = [s for s in scores if s["type"] == "kerntaak" and s["score"] < 50]
    for kt in lage_kt:
        punten.append(f"📉 Lage score: {kt['naam']}")

    if punten:
        with st.container(border=True):
            st.markdown("**💡 Bespreekpunten**")
            for punt in punten:
                st.caption(punt)

# ── Rechterpaneel: OER-chat ───────────────────────────────────────────────────
with col_chat:
    st.markdown(f"**💬 OER-assistent** — {opleiding}")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "chat_bronnen" not in st.session_state:
        st.session_state.chat_bronnen = []

    for i, bericht in enumerate(st.session_state.chat_history):
        if bericht["role"] == "user":
            vraag_tekst = bericht["content"].split("Vraag:")[-1].strip() if "Vraag:" in bericht["content"] else bericht["content"]
            st.markdown(f'<div class="chat-vraag">💬 {vraag_tekst}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-antwoord">{bericht["content"]}</div>', unsafe_allow_html=True)
            bron_idx = i // 2
            if bron_idx < len(st.session_state.chat_bronnen):
                bronnen = st.session_state.chat_bronnen[bron_idx]
                for bron in bronnen:
                    pagina = bron["metadata"].get("pagina", "?")
                    st.markdown(
                        f'<div class="bron-kaartje">📄 p.{pagina} — <em>{bron["tekst"][:150]}…</em></div>',
                        unsafe_allow_html=True,
                    )

    vraag = st.chat_input(f"Stel een vraag over {student['naam']}'s OER…")
    if vraag and oer:
        embedding = embed_vraag(openai_client(), vraag)
        chunks = zoek_chunks(_collection(), embedding, oer_ids=[student["oer_id"]])

        berichten = bouw_berichten(
            chat_history=st.session_state.chat_history,
            chunks=chunks,
            vraag=vraag,
            opleiding=opleiding,
            instelling=instelling,
        )

        st.markdown(f'<div class="chat-vraag">💬 {vraag}</div>', unsafe_allow_html=True)

        if not chunks:
            antwoord = LAGE_RELEVANTIE_BERICHT
            st.info(antwoord)
        else:
            with st.spinner("Zoeken in OER…"):
                antwoord = st.write_stream(genereer_antwoord(ai_client(), berichten))

            for bron in chunks:
                pagina = bron["metadata"].get("pagina", "?")
                st.markdown(
                    f'<div class="bron-kaartje">📄 p.{pagina} — <em>{bron["tekst"][:150]}…</em></div>',
                    unsafe_allow_html=True,
                )

        st.session_state.chat_history.extend([
            {"role": "user", "content": vraag},
            {"role": "assistant", "content": antwoord},
        ])
        st.session_state.chat_bronnen.append(chunks)

render_footer()
```

- [ ] **Stap 3: Schrijf uitloggen.py**

`app/pages/uitloggen.py`:
```python
"""Wist sessie en stuurt terug naar de loginpagina."""

import streamlit as st

st.session_state.clear()
st.switch_page("main.py")
```

- [ ] **Stap 4: Commit**

```bash
git add validatie_samenwijzer/app/pages/
git commit -m "feat(validatie): mentor-pagina's — Mijn studenten, Begeleidingssessie, Uitloggen"
```

---

## Task 14: Smoke test — volledige app

- [ ] **Stap 1: Draai alle unit-tests**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
uv run pytest -v
```

Verwacht: alle tests PASS.

- [ ] **Stap 2: Controleer linting**

```bash
uv run ruff check src/ app/
```

Verwacht: geen fouten. Fix eventuele fouten met:
```bash
uv run ruff check --fix src/ app/
uv run ruff format src/ app/
```

- [ ] **Stap 3: Draai seed-script (als nog niet gedaan)**

```bash
uv run python seed/seed.py
```

- [ ] **Stap 4: Start de app**

```bash
uv run streamlit run app/main.py
```

Open http://localhost:8503 in de browser.

- [ ] **Stap 5: Test student-flow**

1. Log in als student: studentnummer `100001`, wachtwoord `Welkom123`
2. Navigeer naar "OER-assistent" — invoerveld zichtbaar
3. Navigeer naar "Mijn OER" — pagina laadt zonder crash (OER-bestand hoeft niet beschikbaar te zijn)
4. Navigeer naar "Mijn voortgang" — voortgangsbar, BSA-metrics en kerntaakscores zichtbaar
5. Log uit

- [ ] **Stap 6: Test mentor-flow**

1. Log in als mentor: naam `Jansen`, wachtwoord `Welkom123`
2. "Mijn studenten" toont Fatima en Daan met voortgangsbadges
3. Klik "🎓 Begeleiden" bij Fatima → begeleidingssessie opent
4. Profiel links zichtbaar (voortgang, BSA, kerntaken, bespreekpunten)
5. Stel een vraag in het chatvenster rechts (zonder geïndexeerde OER werkt de chat niet, maar de UI laadt foutloos)
6. Log uit

- [ ] **Stap 7: Test ingestie (optioneel — vereist API keys in .env)**

```bash
uv run python -m validatie_samenwijzer.ingest --instelling rijn_ijssel
```

Verwacht: logberichten per verwerkt bestand. Bestanden zonder crebo-patroon worden overgeslagen met een waarschuwing.

- [ ] **Stap 8: Final commit**

```bash
git add -A
git commit -m "feat(validatie): sprint 1 volledig — OER-assistent, begeleidingssessie, ingestie"
```

---

## Self-review

**Spec coverage check:**

| Spec-onderdeel | Gedekt in task |
|---|---|
| SQLite database-setup met volledig datamodel | Task 2 |
| Seed-script met testgebruikers | Task 8 |
| OER-ingestie CLI (PDF/HTML/MD) | Task 6 + 7 |
| Inlogscherm student / mentor | Task 11 |
| OER-assistent hybride chat + doorvragen | Task 9 + 12 |
| Volledig OER raadplegen | Task 12 (2_mijn_oer.py) |
| Studentvoortgang-pagina | Task 12 (3_mijn_voortgang.py) |
| Mentor: studentenoverzicht | Task 13 (4_mijn_studenten.py) |
| Mentor: begeleidingssessie | Task 13 (5_begeleidingssessie.py) |
| Crebo/cohort/leerweg uit bestandsnaam | Task 6 (parseer_bestandsnaam) |
| Kerntaken extraheren uit OER | Task 6 (extraheer_kerntaken) |
| ChromaDB filter op oer_id | Task 5 (zoek_chunks where-filter) |
| Lage relevantie melding | Task 9 (LAGE_RELEVANTIE_BERICHT) |
| Mobile-first CSS | Task 10 |
| Toegangscontrole per rol | Task 3 + 11/12/13 |
| instelling als veld in datamodel | Task 2 |

Geen gaps gevonden.

**Type consistency check:**
- `voeg_student_toe` in db.py gebruikt positional args; seed.py en main.py roepen identiek aan ✓
- `zoek_chunks` in vector_store.py geeft `list[dict]` met `tekst`, `metadata`, `distance` — chat.py gebruikt `c["tekst"]` en `c["metadata"]` ✓
- `bouw_berichten` geeft `list[dict]` met `role`/`content` — `genereer_antwoord` verwacht hetzelfde ✓
- `get_oer_ids_by_mentor_id` geeft `list[int]` — `zoek_chunks` verwacht `list[int]` ✓
