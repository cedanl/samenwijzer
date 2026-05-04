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
