"""Bulk-seed: 1000 synthetische studenten verspreid over 5 instellingen en 10 opleidingen.

Wist bestaande data en bouwt een schone dataset:
  - 5 instellingen × 2 opleidingen = 10 OERs
  - 5 mentoren per OER = 50 mentoren totaal
  - 100 studenten per OER = 1000 studenten totaal
  - 20 studenten per mentor (round-robin)
"""

import os
import random
from pathlib import Path

from dotenv import load_dotenv

from validatie_samenwijzer.auth import hash_wachtwoord
from validatie_samenwijzer.db import (
    get_connection,
    init_db,
    koppel_mentor_oer,
    voeg_instelling_toe,
    voeg_kerntaak_toe,
    voeg_mentor_toe,
    voeg_oer_document_toe,
    voeg_student_kerntaak_score_toe,
    voeg_student_toe,
)

load_dotenv()

STUDENTEN_PER_OER = 100
MENTOREN_PER_OER = 5
WW_HASH = hash_wachtwoord("Welkom123")
RNG = random.Random(2026)

# ── Instellingen en opleidingen ───────────────────────────────────────────────

INSTELLINGEN: list[dict] = [
    {
        "naam": "talland",
        "display_naam": "Talland",
        "opleidingen": [
            {
                "opleiding": "Mbo-Verpleegkundige",
                "crebo": "25655",
                "leerweg": "BBL",
                "cohort": "2025",
                "bestandspad": "oeren/talland_oeren/25655 Mbo-Verpleegkundige 24 maanden BBL.pdf",
                "sector": "Zorgenwelzijn",
                "kerntaken": [
                    ("B1-K1", "Verpleegkundige zorg verlenen", "kerntaak"),
                    ("B1-K1-W1", "Zorg plannen en organiseren", "werkproces"),
                    ("B1-K1-W2", "Zorg uitvoeren", "werkproces"),
                    ("B1-K2", "Begeleiding en ondersteuning bieden", "kerntaak"),
                    ("B1-K2-W1", "Begeleidingsgesprek voeren", "werkproces"),
                ],
            },
            {
                "opleiding": "Helpende Zorg en Welzijn",
                "crebo": "25480",
                "leerweg": "BBL",
                "cohort": "2025",
                "bestandspad": "oeren/talland_oeren/25480 Helpende ZW BBL.pdf",
                "sector": "Zorgenwelzijn",
                "kerntaken": [
                    ("B1-K1", "Ondersteunen bij activiteiten dagelijks leven", "kerntaak"),
                    ("B1-K1-W1", "Persoonlijke verzorging uitvoeren", "werkproces"),
                    ("B1-K1-W2", "Huishoudelijke ondersteuning bieden", "werkproces"),
                    ("B1-K2", "Signaleren en rapporteren", "kerntaak"),
                    ("B1-K2-W1", "Rapportage bijhouden", "werkproces"),
                ],
            },
        ],
    },
    {
        "naam": "davinci",
        "display_naam": "Da Vinci College",
        "opleidingen": [
            {
                "opleiding": "Kok",
                "crebo": "25180",
                "leerweg": "BBL",
                "cohort": "2025",
                "bestandspad": "oeren/davinci_oeren/25180BBL2025MJP-Kok.pdf",
                "sector": "Horeca",
                "kerntaken": [
                    ("B1-K1", "Bereiden van gerechten", "kerntaak"),
                    ("B1-K1-W1", "Mise en place uitvoeren", "werkproces"),
                    ("B1-K1-W2", "Warm bereiden", "werkproces"),
                    ("B1-K2", "Onderhouden van de werkplek", "kerntaak"),
                    ("B1-K2-W1", "Keuken schoonmaken en opruimen", "werkproces"),
                ],
            },
            {
                "opleiding": "Medewerker Bediening",
                "crebo": "25478",
                "leerweg": "BOL",
                "cohort": "2025",
                "bestandspad": "oeren/davinci_oeren/25478BOL2025Medewerker-Bediening.pdf",
                "sector": "Horeca",
                "kerntaken": [
                    ("B1-K1", "Gasten ontvangen en bedienen", "kerntaak"),
                    ("B1-K1-W1", "Tafelopstelling verzorgen", "werkproces"),
                    ("B1-K1-W2", "Bestelling opnemen en serveren", "werkproces"),
                    ("B1-K2", "Kas en betalingen beheren", "kerntaak"),
                    ("B1-K2-W1", "Kassawerkzaamheden uitvoeren", "werkproces"),
                ],
            },
        ],
    },
    {
        "naam": "rijn_ijssel",
        "display_naam": "Rijn IJssel",
        "opleidingen": [
            {
                "opleiding": "Applicatieontwikkelaar",
                "crebo": "25604",
                "leerweg": "BOL",
                "cohort": "2025",
                "bestandspad": "oeren/rijn_ijssel_oer/25604BOL2025Applicatieontwikkelaar.pdf",
                "sector": "ICT",
                "kerntaken": [
                    ("B1-K1", "Ontwerpen en bouwen van applicaties", "kerntaak"),
                    ("B1-K1-W1", "Requirements analyseren", "werkproces"),
                    ("B1-K1-W2", "Applicatie coderen en testen", "werkproces"),
                    ("B1-K2", "Beheren en optimaliseren", "kerntaak"),
                    ("B1-K2-W1", "Applicatie deployen en onderhouden", "werkproces"),
                ],
            },
            {
                "opleiding": "Medewerker ICT",
                "crebo": "25187",
                "leerweg": "BBL",
                "cohort": "2025",
                "bestandspad": "oeren/rijn_ijssel_oer/25187BBL2025Medewerker-ICT.pdf",
                "sector": "ICT",
                "kerntaken": [
                    ("B1-K1", "Installeren en configureren van systemen", "kerntaak"),
                    ("B1-K1-W1", "Hardware installeren", "werkproces"),
                    ("B1-K1-W2", "Software installeren en configureren", "werkproces"),
                    ("B1-K2", "Gebruikers ondersteunen", "kerntaak"),
                    ("B1-K2-W1", "Helpdesk-dienstverlening uitvoeren", "werkproces"),
                ],
            },
        ],
    },
    {
        "naam": "aeres",
        "display_naam": "Aeres",
        "opleidingen": [
            {
                "opleiding": "Dierverzorger 2",
                "crebo": "25390",
                "leerweg": "BBL",
                "cohort": "2025",
                "bestandspad": "oeren/aeres_oeren/25390BBL2025Dierverzorger2.pdf",
                "sector": "Groen",
                "kerntaken": [
                    ("B1-K1", "Verzorgen van dieren", "kerntaak"),
                    ("B1-K1-W1", "Dagelijkse zorg uitvoeren", "werkproces"),
                    ("B1-K1-W2", "Gezondheid bewaken en rapporteren", "werkproces"),
                    ("B1-K2", "Beheren van de dierenverblijven", "kerntaak"),
                    ("B1-K2-W1", "Verblijf reinigen en onderhouden", "werkproces"),
                ],
            },
            {
                "opleiding": "Medewerker Agrarisch Loonwerk",
                "crebo": "25402",
                "leerweg": "BBL",
                "cohort": "2025",
                "bestandspad": "oeren/aeres_oeren/25402BBL2025Agrarisch-Loonwerk.pdf",
                "sector": "Groen",
                "kerntaken": [
                    ("B1-K1", "Uitvoeren van loonwerkzaamheden", "kerntaak"),
                    ("B1-K1-W1", "Machines bedienen en onderhouden", "werkproces"),
                    ("B1-K1-W2", "Gewasbehandeling uitvoeren", "werkproces"),
                    ("B1-K2", "Plannen en administreren", "kerntaak"),
                    ("B1-K2-W1", "Werkopdracht voorbereiden en registreren", "werkproces"),
                ],
            },
        ],
    },
    {
        "naam": "roc_utrecht",
        "display_naam": "ROC Utrecht",
        "opleidingen": [
            {
                "opleiding": "Medewerker Commercie",
                "crebo": "25606",
                "leerweg": "BOL",
                "cohort": "2025",
                "bestandspad": "oeren/utrecht_oeren/25606BOL2025Medewerker-Commercie.pdf",
                "sector": "Economie",
                "kerntaken": [
                    ("B1-K1", "Verkopen en adviseren", "kerntaak"),
                    ("B1-K1-W1", "Klantgesprek voeren", "werkproces"),
                    ("B1-K1-W2", "Verkooptransactie afhandelen", "werkproces"),
                    ("B1-K2", "Inkoop en voorraadbeheer", "kerntaak"),
                    ("B1-K2-W1", "Voorraad controleren en bijbestellen", "werkproces"),
                ],
            },
            {
                "opleiding": "Logistiek Medewerker",
                "crebo": "25251",
                "leerweg": "BBL",
                "cohort": "2025",
                "bestandspad": "oeren/utrecht_oeren/25251BBL2025Logistiek-Medewerker.pdf",
                "sector": "Economie",
                "kerntaken": [
                    ("B1-K1", "Ontvangen en opslaan van goederen", "kerntaak"),
                    ("B1-K1-W1", "Goederen controleren en inboeken", "werkproces"),
                    ("B1-K1-W2", "Goederen opslaan en picken", "werkproces"),
                    ("B1-K2", "Verzenden en distribueren", "kerntaak"),
                    ("B1-K2-W1", "Vrachtbrief opmaken en verladen", "werkproces"),
                ],
            },
        ],
    },
]

# ── Namenlijsten ──────────────────────────────────────────────────────────────

VOORNAMEN_V = [
    "Emma", "Sophie", "Julia", "Lisa", "Anna", "Sara", "Laura", "Amy", "Nora", "Lena",
    "Fatima", "Aisha", "Yasmin", "Lina", "Mia", "Fenna", "Roos", "Nathalie", "Isabel",
    "Mariam", "Zoë", "Eline", "Hanna", "Vera", "Manon", "Fleur", "Sanne", "Anouk",
    "Iris", "Sofie",
]
VOORNAMEN_M = [
    "Daan", "Luca", "Noah", "Sem", "Thomas", "Lars", "Tim", "Jesse", "Bram", "Finn",
    "Joris", "Sander", "Kevin", "Rick", "Milan", "Justin", "Ryan", "Niels", "Pieter",
    "Mark", "Thijs", "Stijn", "Ruben", "Joren", "Mohammed", "Adam", "Omar", "Hamza",
    "Rayan", "Bilal",
]
ACHTERNAMEN = [
    "de Jong", "Janssen", "de Vries", "van den Berg", "van Dijk", "Bakker", "Visser",
    "Smit", "Meijer", "de Boer", "Mulder", "van Leeuwen", "de Groot", "Bos", "Vos",
    "Peters", "Hendriks", "van der Berg", "Kuijpers", "Dijkstra", "Peeters", "Jacobs",
    "van den Broek", "Vermeer", "Willemsen", "Lammers", "Maas", "Postma", "Dekker",
    "Hoekstra", "Al-Hassan", "El Amrani", "Yilmaz", "Kowalski", "Nguyen", "Ozturk",
    "Bouzid", "Kaur", "Singh", "Ferreira",
]
VOOROPLEIDINGEN = ["VMBO_BB", "VMBO_KB", "VMBO_TL", "VMBO_GT", "HAVO", "MBO_2", "MBO_3"]

MENTOR_ACHTERNAMEN = [
    "Bakker", "de Boer", "Visser", "Smit", "Hendriks", "Mulder", "Peters", "Dekker",
    "Hoekstra", "Dijkstra",
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


def _reset_database(conn) -> None:
    conn.executescript("""
        DELETE FROM student_kerntaak_scores;
        DELETE FROM studenten;
        DELETE FROM mentor_oer;
        DELETE FROM mentoren;
        DELETE FROM kerntaken;
        DELETE FROM oer_documenten;
        DELETE FROM instellingen;
    """)
    conn.commit()


def bulk_seed(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    init_db(conn)
    _reset_database(conn)

    volgnummer = 100001
    totaal_studenten = 0

    for instelling_def in INSTELLINGEN:
        inst_id = voeg_instelling_toe(conn, instelling_def["naam"], instelling_def["display_naam"])

        for opl in instelling_def["opleidingen"]:
            # OER aanmaken
            oer_id = voeg_oer_document_toe(
                conn,
                inst_id,
                opl["opleiding"],
                opl["crebo"],
                opl["cohort"],
                opl["leerweg"],
                opl["bestandspad"],
            )

            # Kerntaken aanmaken
            kt_ids = []
            for volgorde, (code, naam, type_) in enumerate(opl["kerntaken"]):
                kt_id = voeg_kerntaak_toe(conn, oer_id, code, naam, type_, volgorde)
                kt_ids.append(kt_id)

            # Mentoren aanmaken (MENTOREN_PER_OER per opleiding)
            mentor_ids = []
            for i in range(MENTOREN_PER_OER):
                voorletter = MENTOR_VOORLETTERS[i % len(MENTOR_VOORLETTERS)]
                achternaam = MENTOR_ACHTERNAMEN[
                    (INSTELLINGEN.index(instelling_def) * MENTOREN_PER_OER + i)
                    % len(MENTOR_ACHTERNAMEN)
                ]
                mentor_naam = f"{voorletter} {achternaam} ({opl['crebo']})"
                mentor_id = voeg_mentor_toe(conn, mentor_naam, WW_HASH, inst_id)
                koppel_mentor_oer(conn, mentor_id, oer_id)
                mentor_ids.append(mentor_id)

            # Studenten aanmaken (STUDENTEN_PER_OER per opleiding, round-robin over mentoren)
            klas_prefix = instelling_def["naam"][:2].upper()
            for i in range(STUDENTEN_PER_OER):
                naam, geslacht = _willekeurige_naam(RNG)
                scores = _willekeurige_scores(RNG)
                mentor_id = mentor_ids[i % MENTOREN_PER_OER]
                klas = f"{klas_prefix}-{opl['crebo'][-3:]}-{RNG.randint(1, 3)}"

                st_id = voeg_student_toe(
                    conn,
                    studentnummer=str(volgnummer),
                    naam=naam,
                    wachtwoord_hash=WW_HASH,
                    instelling_id=inst_id,
                    oer_id=oer_id,
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
                    sector=opl["sector"],
                    dropout=scores["dropout"],
                )
                for kt_id in kt_ids:
                    basis = scores["voortgang"] * 100
                    score = max(0.0, min(100.0, basis + RNG.gauss(0, 15)))
                    voeg_student_kerntaak_score_toe(conn, st_id, kt_id, round(score, 1))

                volgnummer += 1
                totaal_studenten += 1

    # ── Samenvatting ──────────────────────────────────────────────────────────
    per_inst = conn.execute("""
        SELECT i.display_naam, COUNT(DISTINCT o.id) as oers, COUNT(DISTINCT m.id) as mentoren,
               COUNT(DISTINCT s.id) as studenten
        FROM instellingen i
        LEFT JOIN oer_documenten o ON o.instelling_id = i.id
        LEFT JOIN mentoren m ON m.instelling_id = i.id
        LEFT JOIN studenten s ON s.instelling_id = i.id
        GROUP BY i.id ORDER BY i.display_naam
    """).fetchall()

    print(f"Bulk-seed voltooid: {totaal_studenten} studenten aangemaakt.")
    print()
    print(f"{'Instelling':<20} {'OERs':>5} {'Mentoren':>9} {'Studenten':>10}")
    print("-" * 48)
    for r in per_inst:
        print(
            f"{r['display_naam']:<20} {r['oers']:>5} {r['mentoren']:>9} {r['studenten']:>10}"
        )
    print()
    print("Wachtwoord voor allen: Welkom123")
    print(f"Studentnummers: 100001 t/m {volgnummer - 1}")
    conn.close()


if __name__ == "__main__":
    db_pad = Path(os.environ.get("DB_PATH", "data/validatie.db"))
    bulk_seed(db_pad)
