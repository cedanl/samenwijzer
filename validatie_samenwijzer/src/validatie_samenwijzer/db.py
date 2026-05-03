"""SQLite schema-initialisatie en queries voor validatie-samenwijzer."""

import sqlite3
from pathlib import Path


def init_db(conn: sqlite3.Connection) -> None:
    """Maak alle tabellen aan als ze nog niet bestaan en activeer foreign keys."""
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


def get_connection(db_path: Path, timeout: float = 30.0) -> sqlite3.Connection:
    """Open een SQLite-verbinding met WAL-modus en Row-factory."""
    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def voeg_instelling_toe(conn: sqlite3.Connection, naam: str, display_naam: str) -> int:
    """Voeg een instelling toe (INSERT OR IGNORE). Geeft het id terug."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO instellingen (naam, display_naam) VALUES (?, ?)",
        (naam, display_naam),
    )
    conn.commit()
    if cur.lastrowid:
        return cur.lastrowid
    return conn.execute("SELECT id FROM instellingen WHERE naam = ?", (naam,)).fetchone()["id"]


def get_instelling_by_naam(conn: sqlite3.Connection, naam: str) -> sqlite3.Row | None:
    """Zoek een instelling op korte naam. Geeft None als niet gevonden."""
    return conn.execute("SELECT * FROM instellingen WHERE naam = ?", (naam,)).fetchone()


def voeg_oer_document_toe(
    conn: sqlite3.Connection,
    instelling_id: int,
    opleiding: str,
    crebo: str,
    cohort: str,
    leerweg: str,
    bestandspad: str,
) -> int:
    """Voeg een nieuw OER-document toe. Geeft het gegenereerde id terug."""
    cur = conn.execute(
        """INSERT INTO oer_documenten
           (instelling_id, opleiding, crebo, cohort, leerweg, bestandspad)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (instelling_id, opleiding, crebo, cohort, leerweg, bestandspad),
    )
    conn.commit()
    return cur.lastrowid


def get_oer_document(
    conn: sqlite3.Connection, instelling_id: int, crebo: str, cohort: str, leerweg: str
) -> sqlite3.Row | None:
    """Zoek een OER op instelling + crebo + cohort + leerweg. Geeft None als niet gevonden."""
    return conn.execute(
        "SELECT * FROM oer_documenten "
        "WHERE instelling_id = ? AND crebo = ? AND cohort = ? AND leerweg = ?",
        (instelling_id, crebo, cohort, leerweg),
    ).fetchone()


def get_oer_document_by_id(conn: sqlite3.Connection, oer_id: int) -> sqlite3.Row | None:
    """Zoek een OER op primaire sleutel. Geeft None als niet gevonden."""
    return conn.execute("SELECT * FROM oer_documenten WHERE id = ?", (oer_id,)).fetchone()


def markeer_geindexeerd(conn: sqlite3.Connection, oer_id: int) -> None:
    """Zet geindexeerd=1 voor het OER-document met het gegeven id."""
    conn.execute("UPDATE oer_documenten SET geindexeerd = 1 WHERE id = ?", (oer_id,))
    conn.commit()


def update_oer_bestandspad(conn: sqlite3.Connection, oer_id: int, bestandspad: str) -> None:
    """Overschrijf het bestandspad van een OER-document (bijv. upgrade van TXT naar PDF)."""
    conn.execute("UPDATE oer_documenten SET bestandspad = ? WHERE id = ?", (bestandspad, oer_id))
    conn.commit()


def voeg_kerntaak_toe(
    conn: sqlite3.Connection, oer_id: int, code: str, naam: str, type: str, volgorde: int
) -> int:
    """Voeg een kerntaak of werkproces toe aan een OER. Geeft het id terug."""
    cur = conn.execute(
        "INSERT INTO kerntaken (oer_id, code, naam, type, volgorde) VALUES (?, ?, ?, ?, ?)",
        (oer_id, code, naam, type, volgorde),
    )
    conn.commit()
    return cur.lastrowid


def get_kerntaken_by_oer_id(conn: sqlite3.Connection, oer_id: int) -> list[sqlite3.Row]:
    """Geef alle kerntaken en werkprocessen van een OER, gesorteerd op volgorde."""
    return conn.execute(
        "SELECT * FROM kerntaken WHERE oer_id = ? ORDER BY volgorde",
        (oer_id,),
    ).fetchall()


def voeg_mentor_toe(
    conn: sqlite3.Connection, naam: str, wachtwoord_hash: str, instelling_id: int
) -> int:
    """Maak een nieuwe mentor aan. Geeft het id terug."""
    cur = conn.execute(
        "INSERT INTO mentoren (naam, wachtwoord_hash, instelling_id) VALUES (?, ?, ?)",
        (naam, wachtwoord_hash, instelling_id),
    )
    conn.commit()
    return cur.lastrowid


def get_mentor_by_naam(conn: sqlite3.Connection, naam: str) -> sqlite3.Row | None:
    """Zoek een mentor op naam. Geeft None als niet gevonden."""
    return conn.execute("SELECT * FROM mentoren WHERE naam = ?", (naam,)).fetchone()


def koppel_mentor_oer(conn: sqlite3.Connection, mentor_id: int, oer_id: int) -> None:
    """Koppel een mentor aan een OER (INSERT OR IGNORE voor idempotentie)."""
    conn.execute(
        "INSERT OR IGNORE INTO mentor_oer (mentor_id, oer_id) VALUES (?, ?)",
        (mentor_id, oer_id),
    )
    conn.commit()


def get_oer_ids_by_mentor_id(conn: sqlite3.Connection, mentor_id: int) -> list[int]:
    """Geef alle unieke OER-ids van een mentor (via mentor_oer én studenten)."""
    rows = conn.execute(
        """SELECT DISTINCT oer_id FROM mentor_oer WHERE mentor_id = ?
           UNION
           SELECT DISTINCT oer_id FROM studenten WHERE mentor_id = ?""",
        (mentor_id, mentor_id),
    ).fetchall()
    return [r["oer_id"] for r in rows]


def voeg_student_toe(
    conn: sqlite3.Connection,
    studentnummer: str,
    naam: str,
    wachtwoord_hash: str,
    instelling_id: int,
    oer_id: int,
    mentor_id: int | None,
    leeftijd: int | None,
    geslacht: str | None,
    klas: str | None,
    voortgang: float | None,
    bsa_behaald: float | None,
    bsa_vereist: float | None,
    absence_unauthorized: float | None,
    absence_authorized: float | None,
    vooropleiding: str | None,
    sector: str | None,
    dropout: bool,
) -> int:
    """Maak een nieuwe student aan met alle profiel- en voortgangsgegevens. Geeft het id terug."""
    cur = conn.execute(
        """INSERT INTO studenten
           (studentnummer, naam, wachtwoord_hash, instelling_id, oer_id, mentor_id,
            leeftijd, geslacht, klas, voortgang, bsa_behaald, bsa_vereist,
            absence_unauthorized, absence_authorized, vooropleiding, sector, dropout)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            studentnummer,
            naam,
            wachtwoord_hash,
            instelling_id,
            oer_id,
            mentor_id,
            leeftijd,
            geslacht,
            klas,
            voortgang,
            bsa_behaald,
            bsa_vereist,
            absence_unauthorized,
            absence_authorized,
            vooropleiding,
            sector,
            int(dropout),
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_student_by_studentnummer(
    conn: sqlite3.Connection, studentnummer: str
) -> sqlite3.Row | None:
    """Zoek een student op studentnummer. Geeft None als niet gevonden."""
    return conn.execute(
        "SELECT * FROM studenten WHERE studentnummer = ?", (studentnummer,)
    ).fetchone()


def get_studenten_by_mentor_id(conn: sqlite3.Connection, mentor_id: int) -> list[sqlite3.Row]:
    """Geef alle studenten van een mentor, gesorteerd op naam."""
    return conn.execute(
        "SELECT * FROM studenten WHERE mentor_id = ? ORDER BY naam",
        (mentor_id,),
    ).fetchall()


def voeg_student_kerntaak_score_toe(
    conn: sqlite3.Connection, student_id: int, kerntaak_id: int, score: float
) -> None:
    """Sla een kerntaakscore op voor een student (INSERT OR REPLACE)."""
    conn.execute(
        """INSERT OR REPLACE INTO student_kerntaak_scores (student_id, kerntaak_id, score)
           VALUES (?, ?, ?)""",
        (student_id, kerntaak_id, score),
    )
    conn.commit()


def get_kerntaak_scores_by_student_id(
    conn: sqlite3.Connection, student_id: int
) -> list[sqlite3.Row]:
    """Geef alle kerntaakscores van een student met code, naam en type, gesorteerd op volgorde."""
    return conn.execute(
        """SELECT sks.score, k.code, k.naam, k.type, k.volgorde
           FROM student_kerntaak_scores sks
           JOIN kerntaken k ON k.id = sks.kerntaak_id
           WHERE sks.student_id = ?
           ORDER BY k.volgorde""",
        (student_id,),
    ).fetchall()
