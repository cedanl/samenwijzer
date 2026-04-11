"""Persistente opslag voor outreach-interventies via SQLite."""

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "02-prepared" / "outreach.db"

_STATUSSEN = ("niet_gecontacteerd", "gecontacteerd", "gereageerd", "opgelost")

# Paden waarvoor init_db() al is uitgevoerd in deze sessie.
_geinitialiseerd: set[Path] = set()


@dataclass
class StudentStatus:
    studentnummer: str
    status: str
    laatste_contact: str | None = None
    laatste_mentor: str | None = None
    notitie: str | None = None


@dataclass
class Campagne:
    naam: str
    transitiemoment: str
    bericht_template: str
    aangemaakt_door: str
    aangemaakt_op: str
    doelgroep_filter: dict = field(default_factory=dict)
    status: str = "actief"
    id: int | None = None


@dataclass
class WelzijnsCheck:
    studentnummer: str
    timestamp: str
    categorie: str
    toelichting: str
    urgentie: int
    id: int | None = None


@dataclass
class Interventie:
    studentnummer: str
    timestamp: str
    mentor: str
    status_voor: str
    status_na: str
    bericht_samenvatting: str
    voortgang_op_moment: float
    bsa_percentage_op_moment: float
    id: int | None = None


def init_db(db_path: Path = _DB_PATH) -> None:
    """Maak de database en tabellen aan als ze nog niet bestaan."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS student_status (
                studentnummer TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'niet_gecontacteerd',
                laatste_contact TEXT,
                laatste_mentor TEXT,
                notitie TEXT
            );
            CREATE TABLE IF NOT EXISTS interventies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                studentnummer TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                mentor TEXT NOT NULL,
                status_voor TEXT NOT NULL,
                status_na TEXT NOT NULL,
                bericht_samenvatting TEXT,
                voortgang_op_moment REAL,
                bsa_percentage_op_moment REAL
            );
            CREATE TABLE IF NOT EXISTS campagnes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                naam TEXT NOT NULL,
                transitiemoment TEXT NOT NULL,
                bericht_template TEXT NOT NULL,
                aangemaakt_door TEXT NOT NULL,
                aangemaakt_op TEXT NOT NULL,
                doelgroep_filter TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'actief'
            );
            CREATE TABLE IF NOT EXISTS welzijnschecks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                studentnummer TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                categorie TEXT NOT NULL,
                toelichting TEXT NOT NULL DEFAULT '',
                urgentie INTEGER NOT NULL DEFAULT 1
            );
        """)
    _geinitialiseerd.add(db_path)


def _zorg_voor_db(db_path: Path) -> None:
    """Initialiseer de database eenmalig per pad per proces."""
    if db_path not in _geinitialiseerd:
        init_db(db_path)


def get_student_status(studentnummer: str, db_path: Path = _DB_PATH) -> StudentStatus:
    """Haal de status op voor één student. Retourneert standaard als nog niet aanwezig."""
    _zorg_voor_db(db_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, laatste_contact, laatste_mentor, notitie "
            "FROM student_status WHERE studentnummer = ?",
            (studentnummer,),
        ).fetchone()
    if row is None:
        return StudentStatus(studentnummer=studentnummer, status="niet_gecontacteerd")
    return StudentStatus(
        studentnummer=studentnummer,
        status=row[0],
        laatste_contact=row[1],
        laatste_mentor=row[2],
        notitie=row[3],
    )


def get_alle_statussen(db_path: Path = _DB_PATH) -> dict[str, StudentStatus]:
    """Haal alle opgeslagen statussen op als dict (studentnummer → StudentStatus)."""
    _zorg_voor_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT studentnummer, status, laatste_contact, laatste_mentor, notitie "
            "FROM student_status"
        ).fetchall()
    return {
        row[0]: StudentStatus(
            studentnummer=row[0],
            status=row[1],
            laatste_contact=row[2],
            laatste_mentor=row[3],
            notitie=row[4],
        )
        for row in rows
    }


def upsert_status(status: StudentStatus, db_path: Path = _DB_PATH) -> None:
    """Sla de status van een student op (insert of update)."""
    _zorg_voor_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO student_status
                (studentnummer, status, laatste_contact, laatste_mentor, notitie)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(studentnummer) DO UPDATE SET
                status = excluded.status,
                laatste_contact = excluded.laatste_contact,
                laatste_mentor = excluded.laatste_mentor,
                notitie = excluded.notitie
            """,
            (
                status.studentnummer,
                status.status,
                status.laatste_contact,
                status.laatste_mentor,
                status.notitie,
            ),
        )


def log_interventie(interventie: Interventie, db_path: Path = _DB_PATH) -> None:
    """Schrijf een interventie naar de auditlog."""
    _zorg_voor_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO interventies
                (studentnummer, timestamp, mentor, status_voor, status_na,
                 bericht_samenvatting, voortgang_op_moment, bsa_percentage_op_moment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                interventie.studentnummer,
                interventie.timestamp,
                interventie.mentor,
                interventie.status_voor,
                interventie.status_na,
                interventie.bericht_samenvatting,
                interventie.voortgang_op_moment,
                interventie.bsa_percentage_op_moment,
            ),
        )


def get_interventies_voor_student(
    studentnummer: str, db_path: Path = _DB_PATH
) -> list[Interventie]:
    """Haal alle interventies op voor één student, nieuwste eerst."""
    _zorg_voor_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, studentnummer, timestamp, mentor, status_voor, status_na, "
            "bericht_samenvatting, voortgang_op_moment, bsa_percentage_op_moment "
            "FROM interventies WHERE studentnummer = ? ORDER BY timestamp DESC",
            (studentnummer,),
        ).fetchall()
    return [_row_to_interventie(r) for r in rows]


def get_alle_interventies(db_path: Path = _DB_PATH) -> list[Interventie]:
    """Haal alle interventies op, nieuwste eerst."""
    _zorg_voor_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, studentnummer, timestamp, mentor, status_voor, status_na, "
            "bericht_samenvatting, voortgang_op_moment, bsa_percentage_op_moment "
            "FROM interventies ORDER BY timestamp DESC"
        ).fetchall()
    return [_row_to_interventie(r) for r in rows]


def maak_campagne(campagne: Campagne, db_path: Path = _DB_PATH) -> int:
    """Sla een nieuwe campagne op en geef het nieuwe id terug."""
    _zorg_voor_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO campagnes
                (naam, transitiemoment, bericht_template, aangemaakt_door,
                 aangemaakt_op, doelgroep_filter, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                campagne.naam,
                campagne.transitiemoment,
                campagne.bericht_template,
                campagne.aangemaakt_door,
                campagne.aangemaakt_op,
                json.dumps(campagne.doelgroep_filter),
                campagne.status,
            ),
        )
        return int(cur.lastrowid)


def get_alle_campagnes(db_path: Path = _DB_PATH) -> list[Campagne]:
    """Haal alle campagnes op, nieuwste eerst."""
    _zorg_voor_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, naam, transitiemoment, bericht_template, aangemaakt_door, "
            "aangemaakt_op, doelgroep_filter, status FROM campagnes ORDER BY aangemaakt_op DESC"
        ).fetchall()
    return [_row_to_campagne(r) for r in rows]


def sluit_campagne(campagne_id: int, db_path: Path = _DB_PATH) -> None:
    """Zet de status van een campagne op 'afgesloten'."""
    _zorg_voor_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE campagnes SET status = 'afgesloten' WHERE id = ?", (campagne_id,))


def _row_to_campagne(row: tuple) -> Campagne:
    """Converteer een SQLite-rij naar een Campagne-dataclass."""
    return Campagne(
        id=row[0],
        naam=row[1],
        transitiemoment=row[2],
        bericht_template=row[3],
        aangemaakt_door=row[4],
        aangemaakt_op=row[5],
        doelgroep_filter=json.loads(row[6]) if row[6] else {},
        status=row[7],
    )


def sla_welzijnscheck_op(check: WelzijnsCheck, db_path: Path = _DB_PATH) -> int:
    """Sla een welzijnscheck op en geef het nieuwe id terug."""
    _zorg_voor_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO welzijnschecks (studentnummer, timestamp, categorie, toelichting, urgentie)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                check.studentnummer,
                check.timestamp,
                check.categorie,
                check.toelichting,
                check.urgentie,
            ),
        )
        return int(cur.lastrowid)


def get_welzijnschecks_student(studentnummer: str, db_path: Path = _DB_PATH) -> list[WelzijnsCheck]:
    """Haal alle welzijnschecks op voor één student, nieuwste eerst."""
    _zorg_voor_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, studentnummer, timestamp, categorie, toelichting, urgentie "
            "FROM welzijnschecks WHERE studentnummer = ? ORDER BY timestamp DESC",
            (studentnummer,),
        ).fetchall()
    return [_row_to_welzijnscheck(r) for r in rows]


def get_alle_welzijnschecks(db_path: Path = _DB_PATH) -> list[WelzijnsCheck]:
    """Haal alle welzijnschecks op, nieuwste eerst."""
    _zorg_voor_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, studentnummer, timestamp, categorie, toelichting, urgentie "
            "FROM welzijnschecks ORDER BY timestamp DESC"
        ).fetchall()
    return [_row_to_welzijnscheck(r) for r in rows]


def _row_to_welzijnscheck(row: tuple) -> WelzijnsCheck:
    """Converteer een SQLite-rij naar een WelzijnsCheck-dataclass."""
    return WelzijnsCheck(
        id=row[0],
        studentnummer=row[1],
        timestamp=row[2],
        categorie=row[3],
        toelichting=row[4],
        urgentie=row[5],
    )


def _row_to_interventie(row: tuple) -> Interventie:
    """Converteer een SQLite-rij naar een Interventie-dataclass."""
    return Interventie(
        id=row[0],
        studentnummer=row[1],
        timestamp=row[2],
        mentor=row[3],
        status_voor=row[4],
        status_na=row[5],
        bericht_samenvatting=row[6],
        voortgang_op_moment=row[7],
        bsa_percentage_op_moment=row[8],
    )
