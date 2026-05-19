"""Persistente opslag voor het groeidossier via SQLite."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "02-prepared" / "groei.db"

# Paden waarvoor init_db() al is uitgevoerd in deze sessie.
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
