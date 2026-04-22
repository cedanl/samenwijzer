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


def get_connection(db_path: Path, timeout: float = 30.0) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
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
