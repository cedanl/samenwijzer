"""Bulk-seed: 1000 synthetische studenten verspreid over alle geïndexeerde OERs."""

import os
import random
from pathlib import Path

from dotenv import load_dotenv

from validatie_samenwijzer.auth import hash_wachtwoord
from validatie_samenwijzer.db import (
    get_connection,
    init_db,
    koppel_mentor_oer,
    voeg_mentor_toe,
    voeg_student_kerntaak_score_toe,
    voeg_student_toe,
)

load_dotenv()

AANTAL_STUDENTEN = 1000
WW_HASH = hash_wachtwoord("Welkom123")
RNG = random.Random(2026)

# ── Namenlijsten ──────────────────────────────────────────────────────────────

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
SECTOREN = [
    "Zorgenwelzijn",
    "Techniek",
    "Economie",
    "Groen",
    "Horeca",
    "Dienstverlening",
    "ICT",
    "Media",
    "Sport",
]


def _willekeurige_naam(rng: random.Random) -> tuple[str, str]:
    geslacht = rng.choice(["M", "V"])
    voornamen = VOORNAMEN_M if geslacht == "M" else VOORNAMEN_V
    naam = f"{rng.choice(voornamen)} {rng.choice(ACHTERNAMEN)}"
    return naam, geslacht


def _willekeurige_scores(rng: random.Random) -> dict:
    voortgang = round(rng.betavariate(2, 2), 2)  # piek rond 0.5
    bsa_vereist = rng.choice([40.0, 50.0, 60.0])
    bsa_behaald = round(voortgang * bsa_vereist * rng.uniform(0.7, 1.2), 1)
    bsa_behaald = min(bsa_behaald, bsa_vereist)
    absence_unauthorized = round(rng.expovariate(0.3), 1)
    absence_authorized = round(rng.expovariate(0.5), 1)
    leeftijd = rng.randint(16, 30)
    dropout = 1 if (voortgang < 0.2 and rng.random() < 0.3) else 0
    return {
        "voortgang": voortgang,
        "bsa_behaald": bsa_behaald,
        "bsa_vereist": bsa_vereist,
        "absence_unauthorized": absence_unauthorized,
        "absence_authorized": absence_authorized,
        "leeftijd": leeftijd,
        "dropout": bool(dropout),
    }


def bulk_seed(db_path: Path, n: int = AANTAL_STUDENTEN) -> None:
    conn = get_connection(db_path)
    init_db(conn)

    # ── Laad geïndexeerde OERs ────────────────────────────────────────────────
    oers = conn.execute("""
        SELECT o.id, o.instelling_id, o.opleiding, o.crebo, o.leerweg, o.cohort,
               i.naam as inst_naam, i.display_naam
        FROM oer_documenten o
        JOIN instellingen i ON i.id = o.instelling_id
        WHERE o.geindexeerd = 1
    """).fetchall()

    if not oers:
        print("Geen geïndexeerde OERs gevonden. Voer eerst de ingest uit.")
        return

    # ── Kerntaken per OER ─────────────────────────────────────────────────────
    kt_per_oer: dict[int, list[int]] = {}
    for oer in oers:
        kt_rijen = conn.execute(
            "SELECT id FROM kerntaken WHERE oer_id=? ORDER BY volgorde", (oer["id"],)
        ).fetchall()
        kt_per_oer[oer["id"]] = [r["id"] for r in kt_rijen]

    # ── Mentoren aanmaken (1 per instelling) ──────────────────────────────────
    mentor_per_instelling: dict[int, int] = {}
    for oer in oers:
        inst_id = oer["instelling_id"]
        if inst_id in mentor_per_instelling:
            continue
        inst_naam = oer["inst_naam"]
        mentor_naam = f"Mentor_{inst_naam}"
        bestaand = conn.execute("SELECT id FROM mentoren WHERE naam=?", (mentor_naam,)).fetchone()
        if bestaand:
            mentor_id = bestaand["id"]
        else:
            mentor_id = voeg_mentor_toe(conn, mentor_naam, WW_HASH, inst_id)
        mentor_per_instelling[inst_id] = mentor_id

    # Koppel mentoren aan alle OERs van hun instelling
    for oer in oers:
        koppel_mentor_oer(conn, mentor_per_instelling[oer["instelling_id"]], oer["id"])

    # ── Controleer hoeveel studenten al bestaan ───────────────────────────────
    hoogste = (
        conn.execute("SELECT MAX(CAST(studentnummer AS INTEGER)) FROM studenten").fetchone()[0]
        or 200000
    )
    volgnummer = int(hoogste) + 1

    aangemaakt = 0
    overgeslagen = 0

    for _ in range(n):
        oer = RNG.choice(oers)
        naam, geslacht = _willekeurige_naam(RNG)
        scores = _willekeurige_scores(RNG)
        studentnummer = str(volgnummer)
        volgnummer += 1

        klas_code = oer["inst_naam"][:2].upper() + str(RNG.randint(1, 4))

        try:
            st_id = voeg_student_toe(
                conn,
                studentnummer=studentnummer,
                naam=naam,
                wachtwoord_hash=WW_HASH,
                instelling_id=oer["instelling_id"],
                oer_id=oer["id"],
                mentor_id=mentor_per_instelling[oer["instelling_id"]],
                leeftijd=scores["leeftijd"],
                geslacht=geslacht,
                klas=klas_code,
                voortgang=scores["voortgang"],
                bsa_behaald=scores["bsa_behaald"],
                bsa_vereist=scores["bsa_vereist"],
                absence_unauthorized=scores["absence_unauthorized"],
                absence_authorized=scores["absence_authorized"],
                vooropleiding=RNG.choice(VOOROPLEIDINGEN),
                sector=RNG.choice(SECTOREN),
                dropout=scores["dropout"],
            )
        except Exception:
            overgeslagen += 1
            continue

        for kt_id in kt_per_oer[oer["id"]]:
            basis = scores["voortgang"] * 100
            score = max(0.0, min(100.0, basis + RNG.gauss(0, 15)))
            voeg_student_kerntaak_score_toe(conn, st_id, kt_id, round(score, 1))

        aangemaakt += 1

    # ── Samenvatting ──────────────────────────────────────────────────────────
    totaal = conn.execute("SELECT COUNT(*) FROM studenten").fetchone()[0]
    per_inst = conn.execute("""
        SELECT i.display_naam, COUNT(*) as n
        FROM studenten s JOIN instellingen i ON i.id=s.instelling_id
        GROUP BY i.id ORDER BY n DESC
    """).fetchall()

    print(f"Bulk-seed voltooid: {aangemaakt} studenten aangemaakt, {overgeslagen} overgeslagen.")
    print(f"Totaal in database: {totaal} studenten")
    print()
    print("Verdeling per instelling:")
    for r in per_inst:
        print(f"  {r['display_naam']}: {r['n']}")


if __name__ == "__main__":
    db_pad = Path(os.environ.get("DB_PATH", "data/validatie.db"))
    bulk_seed(db_pad)
