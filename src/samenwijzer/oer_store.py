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
