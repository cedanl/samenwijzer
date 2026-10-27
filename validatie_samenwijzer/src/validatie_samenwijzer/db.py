"""SQLite schema-initialisatie en queries voor validatie-samenwijzer."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class SoortInfo:
    """Eigenschappen van een documentsoort (zie docs/plans/2026-10-27-flexibele-documentlaag.md).

    bereik: "instelling" (geldt voor alle opleidingen) of "opleiding" (per crebo/leerweg/cohort).
    juridisch: volledige tekst + harde citatieplicht (anders informatief; eerste die afvalt
        bij budgetdruk). zichtbaarheid: standaard voor nieuwe documenten van deze soort.
    """

    label: str
    bereik: Literal["instelling", "opleiding"]
    juridisch: bool
    zichtbaarheid: Literal["publiek", "ingelogd", "intern"] = "publiek"


# Documentsoorten → eigenschappen. Eén bron van waarheid voor opslag, ingestie, de chat-blokkop
# en de beheer-status. Een nieuwe soort toevoegen = hier één regel; geen schema-migratie nodig
# (soort-validatie staat in voeg_document_toe, niet in een DB-CHECK).
SOORTEN: dict[str, SoortInfo] = {
    "examenreglement": SoortInfo("Examenreglement", "instelling", True),
    "begeleidingsbeleid": SoortInfo(
        "Begeleidings- en welzijnsbeleid", "instelling", False, "ingelogd"
    ),
    # Deze bestaande soorten waren nooit publiek en zijn niet op persoonsgegevens gecontroleerd:
    # `ingelogd` (nu: niet in de publieke chat) tot ze na review op `publiek` worden gezet.
    "studentenstatuut": SoortInfo("Studentenstatuut", "instelling", True, "ingelogd"),
    "bindend_studieadvies": SoortInfo(
        "Regeling bindend studieadvies", "instelling", True, "ingelogd"
    ),
    "klachtenregeling": SoortInfo("Klachtenregeling", "instelling", True, "ingelogd"),
    "gedragscode": SoortInfo("Gedragscode", "instelling", True, "ingelogd"),
    "algemene_informatie": SoortInfo("Algemene informatie", "instelling", False, "ingelogd"),
    "privacyreglement": SoortInfo("Privacyreglement", "instelling", True),
    "pestprotocol": SoortInfo("Pestprotocol", "instelling", False),
    "meldcode": SoortInfo("Meldcode huiselijk geweld en kindermishandeling", "instelling", True),
    "ict_reglement": SoortInfo("Reglement gebruik ICT-voorzieningen", "instelling", False),
    "gedragsregeling": SoortInfo("Regeling houding en gedrag", "instelling", True),
    "praktijkovereenkomst": SoortInfo("Praktijkovereenkomst", "instelling", True),
    "schoolkosten": SoortInfo("Schoolkosten", "instelling", False),
    "veiligheidsplan": SoortInfo("Schoolveiligheidsplan", "instelling", False),
    "protocol": SoortInfo("Protocol", "instelling", False),
    "studiekeuzegids": SoortInfo("Studiekeuzegids", "instelling", False),
    "overig": SoortInfo("Overig document", "instelling", False),
    "examenplan": SoortInfo("Examenplan", "opleiding", False),
    "nominale_lijn": SoortInfo("Nominale lijn", "opleiding", False),
    "studiegids": SoortInfo("Studiegids", "opleiding", False),
    "onderwijsplan": SoortInfo("Onderwijsplan", "opleiding", False),
    "keuzedelen": SoortInfo("Keuzedelen", "opleiding", False),
}

# Instellingsbrede soorten → label (compat voor bestaande consumenten, o.a. de beheer-status).
INSTELLING_SOORTEN = {k: v.label for k, v in SOORTEN.items() if v.bereik == "instelling"}


def _kolom_bestaat(conn: sqlite3.Connection, tabel: str, kolom: str) -> bool:
    """True als `kolom` in `tabel` bestaat. Gebruikt positie 1 (de naam) zodat de check
    onafhankelijk is van de row_factory. Tabelnamen zijn hardgecodeerde literals."""
    return any(r[1] == kolom for r in conn.execute(f"PRAGMA table_info({tabel})"))


def init_db(conn: sqlite3.Connection) -> None:
    """Maak alle tabellen aan als ze nog niet bestaan en activeer foreign keys."""
    # Migratie: instelling_documenten had eerst een CHECK-constraint op `soort`
    # (examenreglement/begeleidingsbeleid). Soort-validatie is naar de code verplaatst
    # zodat nieuwe soorten geen schema-migratie vergen. Recreate de tabel als de oude
    # CHECK er nog in staat — de rijen zijn regenereerbaar via ingest van de _instelling/-bestanden.
    rij = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='instelling_documenten'"
    ).fetchone()
    if rij and "CHECK" in (rij[0] or ""):
        conn.execute("DROP TABLE instelling_documenten")
        conn.commit()

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
            volgorde INTEGER NOT NULL DEFAULT 0,
            UNIQUE (oer_id, type, naam)
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

        CREATE TABLE IF NOT EXISTS ingest_runs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tijdstip      TEXT NOT NULL DEFAULT (datetime('now')),
            scope         TEXT NOT NULL,
            n_oers        INTEGER NOT NULL DEFAULT 0,
            n_kerntaken   INTEGER NOT NULL DEFAULT 0,
            duur_seconden REAL
        );

        CREATE TABLE IF NOT EXISTS documenten (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            instelling_id  INTEGER NOT NULL REFERENCES instellingen(id),
            soort          TEXT NOT NULL,
            bereik         TEXT NOT NULL CHECK (bereik IN ('instelling', 'opleiding')),
            crebo          TEXT NOT NULL DEFAULT '',
            leerweg        TEXT NOT NULL DEFAULT '',
            cohort         TEXT NOT NULL DEFAULT '',
            titel          TEXT NOT NULL,
            bestandspad    TEXT NOT NULL,
            versie_label   TEXT NOT NULL DEFAULT '',
            zichtbaarheid  TEXT NOT NULL DEFAULT 'publiek'
                CHECK (zichtbaarheid IN ('publiek', 'ingelogd', 'intern')),
            gevoeligheid   TEXT NOT NULL DEFAULT 'normaal'
                CHECK (gevoeligheid IN ('normaal', 'geredigeerd', 'uitgesloten')),
            gereviewd      INTEGER NOT NULL DEFAULT 0,
            samenvatting   TEXT NOT NULL DEFAULT '',
            tekens         INTEGER NOT NULL DEFAULT 0,
            geindexeerd    INTEGER NOT NULL DEFAULT 0,
            content_hash   TEXT,
            toegevoegd_op  TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (instelling_id, soort, bereik, crebo, leerweg, cohort, bestandspad)
        );

        CREATE TABLE IF NOT EXISTS instelling_documenten (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            instelling_id INTEGER NOT NULL REFERENCES instellingen(id),
            soort         TEXT NOT NULL,
            titel         TEXT NOT NULL,
            bestandspad   TEXT NOT NULL,
            geindexeerd   INTEGER NOT NULL DEFAULT 0,
            toegevoegd_op TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (instelling_id, soort)
        );
    """)
    conn.commit()

    # Additieve migratie (Fase 3b): content_hash per document voor upstream-
    # wijzigingsdetectie. ADD COLUMN i.p.v. DROP — deze tabellen bevatten echte OER's.
    for tabel in ("oer_documenten", "instelling_documenten"):
        if not _kolom_bestaat(conn, tabel, "content_hash"):
            conn.execute(f"ALTER TABLE {tabel} ADD COLUMN content_hash TEXT")
    conn.commit()
    _migreer_instelling_documenten(conn)


def get_connection(db_path: Path, timeout: float = 30.0) -> sqlite3.Connection:
    """Open een SQLite-verbinding met WAL-modus en Row-factory."""
    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def voeg_instelling_toe(conn: sqlite3.Connection, naam: str, display_naam: str) -> int:
    """Voeg een instelling toe (INSERT OR IGNORE). Geeft het id terug."""
    # Niet vertrouwen op cur.lastrowid: bij OR IGNORE die niet inserteert geeft SQLite de
    # rowid van de vorige succesvolle insert op deze verbinding terug — die kan tot een
    # heel andere tabel behoren. Altijd via SELECT op de UNIQUE-kolom resolven.
    conn.execute(
        "INSERT OR IGNORE INTO instellingen (naam, display_naam) VALUES (?, ?)",
        (naam, display_naam),
    )
    conn.commit()
    return conn.execute("SELECT id FROM instellingen WHERE naam = ?", (naam,)).fetchone()["id"]


def get_instelling_by_naam(conn: sqlite3.Connection, naam: str) -> sqlite3.Row | None:
    """Zoek een instelling op korte naam. Geeft None als niet gevonden."""
    return conn.execute("SELECT * FROM instellingen WHERE naam = ?", (naam,)).fetchone()


def get_instelling_display_namen(conn: sqlite3.Connection) -> list[str]:
    """Geef alle unieke display-namen van instellingen, alfabetisch gesorteerd."""
    rijen = conn.execute("SELECT DISTINCT display_naam FROM instellingen ORDER BY 1").fetchall()
    return [r["display_naam"] for r in rijen]


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


def set_oer_content_hash(conn: sqlite3.Connection, oer_id: int, content_hash: str) -> None:
    """Sla de content-hash van een OER-document op (voor upstream-wijzigingsdetectie)."""
    conn.execute("UPDATE oer_documenten SET content_hash = ? WHERE id = ?", (content_hash, oer_id))
    conn.commit()


def get_alle_oers_met_instelling(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Geeft alle OER-documenten met naam en display_naam van de instelling."""
    return conn.execute(
        "SELECT o.*, i.naam, i.display_naam "
        "FROM oer_documenten o "
        "JOIN instellingen i ON i.id = o.instelling_id "
        "ORDER BY i.display_naam, o.opleiding, o.leerweg, o.cohort"
    ).fetchall()


def get_oer_met_instelling(conn: sqlite3.Connection, oer_id: int) -> sqlite3.Row | None:
    """Geef één OER-document met naam en display_naam van de instelling. None als niet gevonden."""
    return conn.execute(
        "SELECT o.*, i.naam, i.display_naam "
        "FROM oer_documenten o "
        "JOIN instellingen i ON i.id = o.instelling_id "
        "WHERE o.id = ?",
        (oer_id,),
    ).fetchone()


def get_oer_status_per_instelling(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Geef per instelling het aantal OERs (totaal) en hoeveel daarvan geïndexeerd (geindexeerd)."""
    return conn.execute(
        """
        SELECT i.display_naam,
               COUNT(*)                                AS totaal,
               SUM(CASE WHEN o.geindexeerd=1 THEN 1 ELSE 0 END) AS geindexeerd
          FROM oer_documenten o
          JOIN instellingen i ON i.id = o.instelling_id
         GROUP BY i.display_naam
         ORDER BY i.display_naam
        """
    ).fetchall()


def update_oer_bestandspad(conn: sqlite3.Connection, oer_id: int, bestandspad: str) -> None:
    """Overschrijf het bestandspad van een OER-document (bijv. upgrade van TXT naar PDF)."""
    conn.execute("UPDATE oer_documenten SET bestandspad = ? WHERE id = ?", (bestandspad, oer_id))
    conn.commit()


_BEREIKEN = ("instelling", "opleiding")
# niveau → zichtbaarheden die in die context meegaan. `intern` komt nergens in de chat.
_NIVEAU_ZICHTBAARHEID = {
    "publiek": ("publiek",),
    "student": ("publiek", "ingelogd"),
    "mentor": ("publiek", "ingelogd"),
}


def zichtbaarheden_voor_niveau(niveau: str) -> tuple[str, ...]:
    """Zichtbaarheidswaarden die bij een chat-niveau (publiek/student/mentor) horen.

    Raises:
        ValueError: bij een onbekend niveau (geen stille terugval naar een ruimere set).
    """
    if niveau not in _NIVEAU_ZICHTBAARHEID:
        raise ValueError(
            f"Onbekend niveau: {niveau!r}. Bekend: {', '.join(sorted(_NIVEAU_ZICHTBAARHEID))}."
        )
    return _NIVEAU_ZICHTBAARHEID[niveau]


def _migreer_instelling_documenten(conn: sqlite3.Connection) -> None:
    """Neem rijen uit de oude `instelling_documenten` over in `documenten` (idempotent).

    Bestaande documenten waren al ingelezen door de beheerder: instellingsbreed, `gereviewd`,
    zichtbaarheid volgens het register. De oude tabel blijft ongemoeid (legacy).
    """
    for r in conn.execute("SELECT * FROM instelling_documenten").fetchall():
        info = SOORTEN.get(r["soort"])
        conn.execute(
            """INSERT OR IGNORE INTO documenten
               (instelling_id, soort, bereik, titel, bestandspad, zichtbaarheid, gereviewd,
                geindexeerd, content_hash, toegevoegd_op)
               VALUES (?, ?, 'instelling', ?, ?, ?, 1, ?, ?, ?)""",
            (
                r["instelling_id"],
                r["soort"],
                r["titel"],
                r["bestandspad"],
                info.zichtbaarheid if info else "intern",
                r["geindexeerd"],
                r["content_hash"],
                r["toegevoegd_op"],
            ),
        )
    conn.commit()


def voeg_document_toe(
    conn: sqlite3.Connection,
    instelling_id: int,
    soort: str,
    titel: str,
    bestandspad: str,
    *,
    bereik: str | None = None,
    crebo: str = "",
    leerweg: str = "",
    cohort: str = "",
    zichtbaarheid: str | None = None,
    gevoeligheid: str = "normaal",
    gereviewd: bool = False,
    versie_label: str = "",
    samenvatting: str = "",
) -> int:
    """Voeg een document toe of werk het bij (upsert op de volledige sleutel).

    Sleutel: (instelling, soort, bereik, crebo, leerweg, cohort, bestandspad); `''` betekent
    "alle". Meerdere documenten per soort zijn dus mogelijk. `bereik` en `zichtbaarheid`
    vallen terug op het register. Een nieuw document is standaard niet gereviewd en dus nog
    niet zichtbaar in de chat. Geeft het id terug.

    Raises:
        ValueError: bij een onbekende soort of een ongeldig bereik.
    """
    info = SOORTEN.get(soort)
    if info is None:
        raise ValueError(
            f"Onbekende documentsoort: {soort!r}. Bekend: {', '.join(sorted(SOORTEN))}."
        )
    bereik = bereik or info.bereik
    if bereik not in _BEREIKEN:
        raise ValueError(f"Ongeldig bereik: {bereik!r}. Bekend: {', '.join(_BEREIKEN)}.")
    conn.execute(
        """INSERT INTO documenten
           (instelling_id, soort, bereik, crebo, leerweg, cohort, titel, bestandspad,
            versie_label, zichtbaarheid, gevoeligheid, gereviewd, samenvatting)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (instelling_id, soort, bereik, crebo, leerweg, cohort, bestandspad)
           DO UPDATE SET
               titel = excluded.titel,
               versie_label = excluded.versie_label,
               zichtbaarheid = excluded.zichtbaarheid,
               gevoeligheid = excluded.gevoeligheid,
               gereviewd = excluded.gereviewd,
               samenvatting = excluded.samenvatting,
               toegevoegd_op = datetime('now')""",
        (
            instelling_id, soort, bereik, crebo, leerweg, cohort, titel, bestandspad,
            versie_label, zichtbaarheid or info.zichtbaarheid, gevoeligheid, int(gereviewd),
            samenvatting,
        ),
    )  # fmt: skip
    conn.commit()
    # Niet op lastrowid vertrouwen bij ON CONFLICT; resolve via de UNIQUE-sleutel.
    return conn.execute(
        """SELECT id FROM documenten WHERE instelling_id = ? AND soort = ? AND bereik = ?
           AND crebo = ? AND leerweg = ? AND cohort = ? AND bestandspad = ?""",
        (instelling_id, soort, bereik, crebo, leerweg, cohort, bestandspad),
    ).fetchone()["id"]


def get_documenten_voor_context(
    conn: sqlite3.Connection,
    instelling_id: int,
    crebo: str,
    leerweg: str,
    cohort: str,
    niveau: str,
) -> list[sqlite3.Row]:
    """Documenten die in de chat-context van een OER horen.

    Instellingsbrede documenten van de instelling plus opleidingsgebonden documenten die op
    crebo/leerweg/cohort matchen (`''` = alle). Alleen geïndexeerde, gereviewde, niet-uitgesloten
    documenten waarvan de zichtbaarheid bij het niveau past.

    Raises:
        ValueError: bij een onbekend niveau.
    """
    zichtbaar = zichtbaarheden_voor_niveau(niveau)
    plaats = ", ".join("?" for _ in zichtbaar)
    return conn.execute(
        f"""SELECT * FROM documenten
            WHERE instelling_id = ? AND geindexeerd = 1 AND gereviewd = 1
              AND gevoeligheid <> 'uitgesloten' AND zichtbaarheid IN ({plaats})
              AND (bereik = 'instelling'
                   OR ((crebo = '' OR crebo = ?) AND (leerweg = '' OR leerweg = ?)
                       AND (cohort = '' OR cohort = ?)))
            ORDER BY soort, titel, id""",  # noqa: S608 — alleen vaste '?'-plaatshouders
        (instelling_id, *zichtbaar, crebo, leerweg, cohort),
    ).fetchall()


def markeer_document_geindexeerd(conn: sqlite3.Connection, doc_id: int) -> None:
    """Zet geindexeerd=1 voor het document met het gegeven id."""
    conn.execute("UPDATE documenten SET geindexeerd = 1 WHERE id = ?", (doc_id,))
    conn.commit()


def set_document_content_hash(conn: sqlite3.Connection, doc_id: int, content_hash: str) -> None:
    """Sla de content-hash van een document op."""
    conn.execute("UPDATE documenten SET content_hash = ? WHERE id = ?", (content_hash, doc_id))
    conn.commit()


def voeg_ingest_run_toe(
    conn: sqlite3.Connection,
    *,
    scope: str,
    n_oers: int,
    n_kerntaken: int,
    duur_seconden: float,
) -> None:
    """Log een afgeronde ingest-run voor de beheerpagina."""
    conn.execute(
        "INSERT INTO ingest_runs (scope, n_oers, n_kerntaken, duur_seconden) VALUES (?, ?, ?, ?)",
        (scope, n_oers, n_kerntaken, duur_seconden),
    )
    conn.commit()


def laatste_ingest_run(conn: sqlite3.Connection) -> sqlite3.Row | None:
    """Geef de meest recente ingest-run terug (of None als de tabel leeg is)."""
    return conn.execute("SELECT * FROM ingest_runs ORDER BY id DESC LIMIT 1").fetchone()


def update_oer_opleiding(conn: sqlite3.Connection, oer_id: int, opleiding: str) -> None:
    """Overschrijf de opleidingsnaam van een OER-document.

    Gebruikt door de ingest wanneer een betere naam (bv. uit de PDF-titelpagina)
    is afgeleid dan wat oorspronkelijk uit de bestandsnaam kwam.
    """
    conn.execute("UPDATE oer_documenten SET opleiding = ? WHERE id = ?", (opleiding, oer_id))
    conn.commit()


def voeg_kerntaak_toe(
    conn: sqlite3.Connection, oer_id: int, code: str, naam: str, type: str, volgorde: int
) -> int:
    """Voeg een kerntaak of werkproces toe (upsert).

    Geeft altijd het id terug — van de nieuw aangemaakte rij of van de bestaande
    rij die de UNIQUE(oer_id, type, naam)-constraint matcht. Idempotent, zodat
    callers hun return value veilig kunnen gebruiken om scores te koppelen.
    """
    cur = conn.execute(
        "INSERT OR IGNORE INTO kerntaken (oer_id, code, naam, type, volgorde) "
        "VALUES (?, ?, ?, ?, ?)",
        (oer_id, code, naam, type, volgorde),
    )
    conn.commit()
    if cur.rowcount > 0:
        return cur.lastrowid
    return conn.execute(
        "SELECT id FROM kerntaken WHERE oer_id = ? AND type = ? AND naam = ?",
        (oer_id, type, naam),
    ).fetchone()["id"]


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


def get_student_by_id(conn: sqlite3.Connection, student_id: int) -> sqlite3.Row | None:
    """Zoek een student op id. Geeft None als niet gevonden."""
    return conn.execute("SELECT * FROM studenten WHERE id = ?", (student_id,)).fetchone()


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
