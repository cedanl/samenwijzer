"""Herbouw studenten en mentoren.

Wist bestaande studenten en mentoren, en vult de database opnieuw met:
- 1000 studenten, proportioneel verdeeld over alle 5 instellingen
- Binnen elke instelling gelijkmatig verdeeld over alle geïndexeerde OERs
- ~20 studenten per mentor; mentoren worden round-robin toegewezen

Gebruik:
    uv run python seed/rebuild_students.py
"""

import math
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

TOTAAL_STUDENTEN = 1000
STUDENTEN_PER_MENTOR = 20
WW_HASH = hash_wachtwoord("Welkom123")
RNG = random.Random(2026)

# ── Namenlijsten studenten ────────────────────────────────────────────────────

VOORNAMEN_V = [
    "Emma", "Sophie", "Julia", "Lisa", "Anna", "Sara", "Laura", "Nora", "Lena",
    "Fatima", "Aisha", "Yasmin", "Lina", "Mia", "Fenna", "Roos", "Mariam",
    "Zoë", "Hanna", "Vera", "Manon", "Fleur", "Sanne", "Anouk", "Iris", "Sofie",
    "Eline", "Nathalie", "Isabel", "Amy",
]
VOORNAMEN_M = [
    "Daan", "Luca", "Noah", "Sem", "Thomas", "Lars", "Tim", "Jesse", "Bram",
    "Finn", "Joris", "Sander", "Kevin", "Rick", "Milan", "Justin", "Ryan",
    "Niels", "Pieter", "Mark", "Thijs", "Stijn", "Ruben", "Joren",
    "Mohammed", "Adam", "Omar", "Hamza", "Rayan", "Bilal",
]
ACHTERNAMEN = [
    "de Jong", "Janssen", "de Vries", "van den Berg", "van Dijk", "Bakker",
    "Visser", "Smit", "Meijer", "de Boer", "Mulder", "van Leeuwen", "de Groot",
    "Bos", "Vos", "Peters", "Hendriks", "Kuijpers", "Dijkstra", "Peeters",
    "Jacobs", "Vermeer", "Willemsen", "Lammers", "Maas", "Postma", "Dekker",
    "Hoekstra", "Al-Hassan", "El Amrani", "Yilmaz", "Kowalski", "Nguyen",
    "Ozturk", "Bouzid", "Singh", "Ferreira", "van der Berg",
]

# ── Namenlijsten mentoren ─────────────────────────────────────────────────────

MENTOR_VOORNAMEN = [
    "Anke", "Bart", "Carmen", "Dirk", "Ellen", "Frank", "Greta", "Hans",
    "Iris", "Joost", "Karen", "Leon", "Maria", "Niek", "Olga", "Piet",
    "Quirine", "Rob", "Sandra", "Tom", "Ursula", "Victor", "Wendy",
    "Xander", "Yvonne", "Annelies", "Bernd", "Corine", "Dennis", "Eva",
    "Gerard", "Hanneke", "Inge", "Jan", "Karin", "Lennart", "Miriam",
    "Nathan", "Patricia", "Rik", "Simone", "Theo", "Veerle", "Wouter",
]
MENTOR_ACHTERNAMEN = [
    "Aalbers", "Brouwer", "Claassen", "Dijkman", "Engelen", "Faber",
    "Gerritsen", "Hoeven", "Imhoff", "Joosten", "Klooster", "Linden",
    "Martens", "Noteboom", "Oosterbeek", "Pieters", "Rooijmans", "Stam",
    "Timmermans", "Verhoeven", "Wouters", "Zwart", "Alblas", "Bosma",
    "Cramer", "Daalman", "Everts", "Fortuin", "Groen", "Hamaker",
]

VOOROPLEIDINGEN = ["VMBO_BB", "VMBO_KB", "VMBO_TL", "VMBO_GT", "HAVO", "MBO_2", "MBO_3"]
SECTOREN = [
    "Zorgenwelzijn", "Techniek", "Economie", "Groen", "Horeca",
    "Dienstverlening", "ICT", "Media", "Sport",
]


# ── Hulpfuncties ──────────────────────────────────────────────────────────────


def _willekeurige_naam(rng: random.Random) -> tuple[str, str]:
    geslacht = rng.choice(["M", "V"])
    voornamen = VOORNAMEN_M if geslacht == "M" else VOORNAMEN_V
    return f"{rng.choice(voornamen)} {rng.choice(ACHTERNAMEN)}", geslacht


def _willekeurige_scores(rng: random.Random) -> dict:
    voortgang = round(rng.betavariate(2, 2), 2)
    bsa_vereist = rng.choice([40.0, 50.0, 60.0])
    bsa_behaald = round(min(voortgang * bsa_vereist * rng.uniform(0.7, 1.2), bsa_vereist), 1)
    return {
        "voortgang": voortgang,
        "bsa_behaald": bsa_behaald,
        "bsa_vereist": bsa_vereist,
        "absence_unauthorized": round(rng.expovariate(0.3), 1),
        "absence_authorized": round(rng.expovariate(0.5), 1),
        "leeftijd": rng.randint(16, 30),
        "dropout": bool(voortgang < 0.2 and rng.random() < 0.3),
    }


def _unieke_mentor_naam(rng: random.Random, gebruikt: set[str]) -> str:
    for _ in range(200):
        naam = f"{rng.choice(MENTOR_VOORNAMEN)} {rng.choice(MENTOR_ACHTERNAMEN)}"
        if naam not in gebruikt:
            gebruikt.add(naam)
            return naam
    raise RuntimeError("Namenpool mentor uitgeput — voeg meer namen toe.")


def _oer_verdeling(oers: list, n_studenten: int) -> list:
    """Verdeel n_studenten zo gelijkmatig mogelijk over oers (elke OER ≥1)."""
    n = len(oers)
    base, extra = divmod(n_studenten, n)
    verdeling = []
    for i, oer in enumerate(oers):
        verdeling.extend([oer] * (base + (1 if i < extra else 0)))
    RNG.shuffle(verdeling)
    return verdeling


# ── Hoofdfunctie ──────────────────────────────────────────────────────────────


def rebuild(db_path: Path) -> None:
    conn = get_connection(db_path)
    init_db(conn)

    # ── Wis bestaande studenten en mentoren ───────────────────────────────────
    print("Wis bestaande studenten en mentoren…")
    conn.execute("DELETE FROM student_kerntaak_scores")
    conn.execute("DELETE FROM studenten")
    conn.execute("DELETE FROM mentor_oer")
    conn.execute("DELETE FROM mentoren")
    conn.commit()

    # ── Laad geïndexeerde OERs per instelling ─────────────────────────────────
    alle_oers = conn.execute("""
        SELECT o.id, o.instelling_id, o.opleiding, i.naam as inst_naam, i.display_naam
        FROM oer_documenten o
        JOIN instellingen i ON i.id = o.instelling_id
        WHERE o.geindexeerd = 1
        ORDER BY i.id, o.id
    """).fetchall()

    oers_per_inst: dict[int, list] = {}
    for oer in alle_oers:
        oers_per_inst.setdefault(oer["instelling_id"], []).append(oer)

    totaal_oers = len(alle_oers)
    instellingen = sorted(oers_per_inst.keys())

    # ── Bereken studentaantallen per instelling (proportioneel) ───────────────
    studenten_per_inst: dict[int, int] = {}
    resterend = TOTAAL_STUDENTEN
    for inst_id in instellingen[:-1]:
        n = round(TOTAAL_STUDENTEN * len(oers_per_inst[inst_id]) / totaal_oers)
        studenten_per_inst[inst_id] = n
        resterend -= n
    studenten_per_inst[instellingen[-1]] = resterend  # rest aan de laatste

    # ── Kerntaken per OER vooraf ophalen ──────────────────────────────────────
    kt_per_oer: dict[int, list[int]] = {}
    for oer in alle_oers:
        rijen = conn.execute(
            "SELECT id FROM kerntaken WHERE oer_id=? ORDER BY volgorde", (oer["id"],)
        ).fetchall()
        kt_per_oer[oer["id"]] = [r["id"] for r in rijen]

    # ── Maak mentoren en studenten per instelling ─────────────────────────────
    gebruikte_mentor_namen: set[str] = set()
    volgnummer = 100001
    samenvatting = []

    for inst_id in instellingen:
        oers = oers_per_inst[inst_id]
        n_studenten = studenten_per_inst[inst_id]
        n_mentoren = max(1, math.ceil(n_studenten / STUDENTEN_PER_MENTOR))
        display_naam = oers[0]["display_naam"]
        inst_naam = oers[0]["inst_naam"]

        # Mentoren aanmaken
        mentor_ids = []
        mentor_namen_inst = []
        for _ in range(n_mentoren):
            naam = _unieke_mentor_naam(RNG, gebruikte_mentor_namen)
            mentor_id = voeg_mentor_toe(conn, naam, WW_HASH, inst_id)
            mentor_ids.append(mentor_id)
            mentor_namen_inst.append(naam)

        # Studenten gelijkmatig over OERs verdelen
        oer_verdeling = _oer_verdeling(oers, n_studenten)

        # Bijhouden welke OERs elke mentor begeleidt
        mentor_oer_ids: dict[int, set[int]] = {m: set() for m in mentor_ids}

        for i, oer in enumerate(oer_verdeling):
            mentor_id = mentor_ids[i % n_mentoren]
            naam, geslacht = _willekeurige_naam(RNG)
            scores = _willekeurige_scores(RNG)
            klas = inst_naam[:2].upper() + str(RNG.randint(1, 4))

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
                sector=RNG.choice(SECTOREN),
                dropout=scores["dropout"],
            )
            volgnummer += 1
            mentor_oer_ids[mentor_id].add(oer["id"])

            for kt_id in kt_per_oer[oer["id"]]:
                basis = scores["voortgang"] * 100
                score = max(0.0, min(100.0, basis + RNG.gauss(0, 15)))
                voeg_student_kerntaak_score_toe(conn, st_id, kt_id, round(score, 1))

        # Koppel elke mentor aan zijn/haar OERs
        for mentor_id, oer_ids in mentor_oer_ids.items():
            for oer_id in oer_ids:
                koppel_mentor_oer(conn, mentor_id, oer_id)

        samenvatting.append((display_naam, n_studenten, n_mentoren, mentor_namen_inst))

    # ── Samenvatting ──────────────────────────────────────────────────────────
    print()
    print(f"{'Instelling':<22} {'OERs':>5} {'Studenten':>10} {'Mentoren':>9}")
    print("-" * 52)
    for display_naam, n_st, n_m, _ in samenvatting:
        inst_id = next(
            i for i in instellingen if oers_per_inst[i][0]["display_naam"] == display_naam
        )
        n_oers = len(oers_per_inst[inst_id])
        print(f"{display_naam:<22} {n_oers:>5} {n_st:>10} {n_m:>9}")
    print("-" * 52)
    totaal_st = conn.execute("SELECT COUNT(*) FROM studenten").fetchone()[0]
    totaal_m = conn.execute("SELECT COUNT(*) FROM mentoren").fetchone()[0]
    print(f"{'Totaal':<22} {totaal_oers:>5} {totaal_st:>10} {totaal_m:>9}")

    print()
    print("Voorbeeldlogins per instelling (wachtwoord: Welkom123):")
    for display_naam, _, _, mentor_namen in samenvatting:
        eerste_mentor = mentor_namen[0]
        eerste_student = conn.execute("""
            SELECT s.studentnummer, s.naam
            FROM studenten s
            JOIN instellingen i ON i.id = s.instelling_id
            WHERE i.display_naam = ?
            LIMIT 1
        """, (display_naam,)).fetchone()
        print(f"  {display_naam}:")
        print(f"    student : {eerste_student['studentnummer']} ({eerste_student['naam']})")
        print(f"    mentor  : {eerste_mentor}")


if __name__ == "__main__":
    db_pad = Path(os.environ.get("DB_PATH", "data/validatie.db"))
    rebuild(db_pad)
