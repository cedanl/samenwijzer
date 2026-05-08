"""Bulk-seed: synthetische studenten + mentoren bovenop een geïngestreerde DB.

Vereist een gevulde validatie.db waarin OERs al geïndexeerd zijn (`geindexeerd=1`).
Draai eerst:

    uv run python -m validatie_samenwijzer.ingest --alles

De seed kiest per instelling de top OERs (meeste kerntaken eerst, dan recentste cohort)
en hangt daar mentoren + studenten aan. Geen hardcoded crebos of bestandspaden — alle
koppelingen lopen via de OER-records die ingest heeft aangemaakt, zodat hernoemen of
verplaatsen van bron-PDFs niet meer tot wees-koppelingen leidt.
"""

import os
import random
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

from validatie_samenwijzer.auth import hash_wachtwoord
from validatie_samenwijzer.db import (
    get_connection,
    init_db,
    koppel_mentor_oer,
    voeg_instelling_toe,
    voeg_mentor_toe,
    voeg_student_kerntaak_score_toe,
    voeg_student_toe,
)

load_dotenv()

OERS_PER_INSTELLING = 2
MENTOREN_PER_OER = 5
STUDENTEN_PER_OER = 100
WW_HASH = hash_wachtwoord("Welkom123")
RNG = random.Random(2026)

# Instelling-namen moeten matchen met validatie_samenwijzer.ingest._INSTELLINGEN —
# anders ontstaan er dubbele instellingen-records (bv. 'roc_utrecht' naast 'utrecht').
INSTELLINGEN: list[dict] = [
    {"naam": "talland", "display_naam": "Talland", "klas_prefix": "TA"},
    {"naam": "davinci", "display_naam": "Da Vinci College", "klas_prefix": "DV"},
    {"naam": "rijn_ijssel", "display_naam": "Rijn IJssel", "klas_prefix": "RI"},
    {"naam": "aeres", "display_naam": "Aeres MBO", "klas_prefix": "AE"},
    {"naam": "utrecht", "display_naam": "ROC Utrecht", "klas_prefix": "UT"},
]

VOORNAMEN_V = [
    "Emma",
    "Sophie",
    "Julia",
    "Lisa",
    "Anna",
    "Sara",
    "Laura",
    "Amy",
    "Nora",
    "Lena",
    "Fatima",
    "Aisha",
    "Yasmin",
    "Lina",
    "Mia",
    "Fenna",
    "Roos",
    "Nathalie",
    "Isabel",
    "Mariam",
    "Zoë",
    "Eline",
    "Hanna",
    "Vera",
    "Manon",
    "Fleur",
    "Sanne",
    "Anouk",
    "Iris",
    "Sofie",
]
VOORNAMEN_M = [
    "Daan",
    "Luca",
    "Noah",
    "Sem",
    "Thomas",
    "Lars",
    "Tim",
    "Jesse",
    "Bram",
    "Finn",
    "Joris",
    "Sander",
    "Kevin",
    "Rick",
    "Milan",
    "Justin",
    "Ryan",
    "Niels",
    "Pieter",
    "Mark",
    "Thijs",
    "Stijn",
    "Ruben",
    "Joren",
    "Mohammed",
    "Adam",
    "Omar",
    "Hamza",
    "Rayan",
    "Bilal",
]
ACHTERNAMEN = [
    "de Jong",
    "Janssen",
    "de Vries",
    "van den Berg",
    "van Dijk",
    "Bakker",
    "Visser",
    "Smit",
    "Meijer",
    "de Boer",
    "Mulder",
    "van Leeuwen",
    "de Groot",
    "Bos",
    "Vos",
    "Peters",
    "Hendriks",
    "van der Berg",
    "Kuijpers",
    "Dijkstra",
    "Peeters",
    "Jacobs",
    "van den Broek",
    "Vermeer",
    "Willemsen",
    "Lammers",
    "Maas",
    "Postma",
    "Dekker",
    "Hoekstra",
    "Al-Hassan",
    "El Amrani",
    "Yilmaz",
    "Kowalski",
    "Nguyen",
    "Ozturk",
    "Bouzid",
    "Kaur",
    "Singh",
    "Ferreira",
]
VOOROPLEIDINGEN = ["VMBO_BB", "VMBO_KB", "VMBO_TL", "VMBO_GT", "HAVO", "MBO_2", "MBO_3"]

MENTOR_ACHTERNAMEN = [
    "Bakker",
    "de Boer",
    "Visser",
    "Smit",
    "Hendriks",
    "Mulder",
    "Peters",
    "Dekker",
    "Hoekstra",
    "Dijkstra",
]
MENTOR_VOORLETTERS = ["A.", "B.", "C.", "D.", "E.", "F.", "G.", "H.", "I.", "J."]


def _willekeurige_naam(rng: random.Random) -> tuple[str, str]:
    geslacht = rng.choice(["M", "V"])
    voornamen = VOORNAMEN_M if geslacht == "M" else VOORNAMEN_V
    naam = f"{rng.choice(voornamen)} {rng.choice(ACHTERNAMEN)}"
    return naam, geslacht


def _willekeurige_scores(rng: random.Random) -> dict:
    voortgang = round(rng.betavariate(2, 2), 2)
    bsa_vereist = rng.choice([40.0, 50.0, 60.0])
    bsa_behaald = round(voortgang * bsa_vereist * rng.uniform(0.7, 1.2), 1)
    bsa_behaald = min(bsa_behaald, bsa_vereist)
    return {
        "voortgang": voortgang,
        "bsa_behaald": bsa_behaald,
        "bsa_vereist": bsa_vereist,
        "absence_unauthorized": round(rng.expovariate(0.3), 1),
        "absence_authorized": round(rng.expovariate(0.5), 1),
        "leeftijd": rng.randint(16, 30),
        "dropout": voortgang < 0.2 and rng.random() < 0.3,
    }


def _check_db_klaar(conn: sqlite3.Connection) -> None:
    n = conn.execute("SELECT COUNT(*) FROM oer_documenten WHERE geindexeerd = 1").fetchone()[0]
    if n == 0:
        sys.exit(
            "Geen geïndexeerde OERs in database. Draai eerst:\n"
            "    uv run python -m validatie_samenwijzer.ingest --alles\n"
        )


def _reset_database(conn: sqlite3.Connection) -> None:
    """Wis seed-data + wees-OER-records; behoud geïndexeerde OERs en hun kerntaken."""
    conn.executescript("""
        DELETE FROM student_kerntaak_scores;
        DELETE FROM studenten;
        DELETE FROM mentor_oer;
        DELETE FROM mentoren;
    """)
    # Verwijder OER-records die nooit geïndexeerd raakten en waarvan het bronbestand
    # ook niet meer bestaat — typisch overblijfsels van eerdere bulk_seed-runs.
    weeskinderen = conn.execute(
        "SELECT id, bestandspad FROM oer_documenten WHERE geindexeerd = 0"
    ).fetchall()
    voor_verwijdering = [r["id"] for r in weeskinderen if not Path(r["bestandspad"]).exists()]
    for oer_id in voor_verwijdering:
        conn.execute("DELETE FROM kerntaken WHERE oer_id = ?", (oer_id,))
        conn.execute("DELETE FROM oer_documenten WHERE id = ?", (oer_id,))
    # Verwijder zombie-instellingen zonder OER-verwijzingen (zoals het oude
    # 'roc_utrecht'-record naast het 'utrecht'-record dat ingest aanmaakt).
    conn.execute(
        "DELETE FROM instellingen WHERE id NOT IN (SELECT instelling_id FROM oer_documenten)"
    )
    conn.commit()


def _kies_oers(conn: sqlite3.Connection, instelling_id: int, n: int) -> list[sqlite3.Row]:
    """Kies tot n geïndexeerde OERs voor deze instelling, gefilterd op kerntaken aanwezig."""
    return conn.execute(
        """
        SELECT o.*, (SELECT COUNT(*) FROM kerntaken WHERE oer_id = o.id) AS n_kt
        FROM oer_documenten o
        WHERE o.instelling_id = ?
          AND o.geindexeerd = 1
          AND (SELECT COUNT(*) FROM kerntaken WHERE oer_id = o.id) >= 1
        ORDER BY n_kt DESC, o.cohort DESC, o.id
        LIMIT ?
        """,
        (instelling_id, n),
    ).fetchall()


def bulk_seed(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    init_db(conn)
    _check_db_klaar(conn)
    _reset_database(conn)

    volgnummer = 100001
    totaal_studenten = 0
    overgeslagen: list[tuple[str, str]] = []

    for inst_idx, inst_def in enumerate(INSTELLINGEN):
        inst_id = voeg_instelling_toe(conn, inst_def["naam"], inst_def["display_naam"])
        oers = _kies_oers(conn, inst_id, OERS_PER_INSTELLING)
        if not oers:
            overgeslagen.append((inst_def["display_naam"], "geen geïndexeerde OERs met kerntaken"))
            continue
        if len(oers) < OERS_PER_INSTELLING:
            overgeslagen.append(
                (
                    inst_def["display_naam"],
                    f"slechts {len(oers)}/{OERS_PER_INSTELLING} OERs gebruikt",
                )
            )

        for oer in oers:
            kt_ids = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM kerntaken WHERE oer_id = ? ORDER BY volgorde",
                    (oer["id"],),
                ).fetchall()
            ]

            mentor_ids = []
            for i in range(MENTOREN_PER_OER):
                voorletter = MENTOR_VOORLETTERS[i % len(MENTOR_VOORLETTERS)]
                achternaam = MENTOR_ACHTERNAMEN[
                    (inst_idx * MENTOREN_PER_OER + i) % len(MENTOR_ACHTERNAMEN)
                ]
                mentor_naam = f"{voorletter} {achternaam} ({oer['crebo']})"
                mentor_id = voeg_mentor_toe(conn, mentor_naam, WW_HASH, inst_id)
                koppel_mentor_oer(conn, mentor_id, oer["id"])
                mentor_ids.append(mentor_id)

            for i in range(STUDENTEN_PER_OER):
                naam, geslacht = _willekeurige_naam(RNG)
                scores = _willekeurige_scores(RNG)
                mentor_id = mentor_ids[i % MENTOREN_PER_OER]
                klas = f"{inst_def['klas_prefix']}-{oer['crebo'][-3:]}-{RNG.randint(1, 3)}"

                st_id = voeg_student_toe(
                    conn,
                    studentnummer=str(volgnummer),
                    naam=naam,
                    wachtwoord_hash=WW_HASH,
                    instelling_id=inst_id,
                    oer_id=oer["id"],
                    mentor_id=mentor_id,
                    leeftijd=scores["leeftijd"],
                    geslacht=geslacht,
                    klas=klas,
                    voortgang=scores["voortgang"],
                    bsa_behaald=scores["bsa_behaald"],
                    bsa_vereist=scores["bsa_vereist"],
                    absence_unauthorized=scores["absence_unauthorized"],
                    absence_authorized=scores["absence_authorized"],
                    vooropleiding=RNG.choice(VOOROPLEIDINGEN),
                    sector=inst_def["display_naam"],
                    dropout=scores["dropout"],
                )
                for kt_id in kt_ids:
                    basis = scores["voortgang"] * 100
                    score = max(0.0, min(100.0, basis + RNG.gauss(0, 15)))
                    voeg_student_kerntaak_score_toe(conn, st_id, kt_id, round(score, 1))

                volgnummer += 1
                totaal_studenten += 1

    per_inst = conn.execute(
        """
        SELECT i.display_naam,
               COUNT(DISTINCT mo.oer_id) AS oers,
               COUNT(DISTINCT m.id) AS mentoren,
               COUNT(DISTINCT s.id) AS studenten
        FROM instellingen i
        LEFT JOIN mentoren m ON m.instelling_id = i.id
        LEFT JOIN mentor_oer mo ON mo.mentor_id = m.id
        LEFT JOIN studenten s ON s.instelling_id = i.id
        GROUP BY i.id
        HAVING studenten > 0
        ORDER BY i.display_naam
        """
    ).fetchall()

    print(f"Bulk-seed voltooid: {totaal_studenten} studenten aangemaakt.")
    print()
    print(f"{'Instelling':<25} {'OERs':>5} {'Mentoren':>9} {'Studenten':>10}")
    print("-" * 53)
    for r in per_inst:
        print(f"{r['display_naam']:<25} {r['oers']:>5} {r['mentoren']:>9} {r['studenten']:>10}")

    if overgeslagen:
        print()
        print("Aandachtspunten:")
        for naam, reden in overgeslagen:
            print(f"  - {naam}: {reden}")

    print()
    print("Wachtwoord voor allen: Welkom123")
    print(f"Studentnummers: 100001 t/m {volgnummer - 1}")
    conn.close()


if __name__ == "__main__":
    db_pad = Path(os.environ.get("DB_PATH", "data/validatie.db"))
    bulk_seed(db_pad)
