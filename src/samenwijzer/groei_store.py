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
