"""Genereer een synthetische 1000-studenten-set gekoppeld aan echte OERs.

Gebruik:
    uv run python scripts/generate_synthetisch_data.py
"""

from __future__ import annotations

import argparse  # noqa: F401  — gebruikt door orchestrator (Task 14)
import json  # noqa: F401  — gebruikt door orchestrator (Task 14)
import logging
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from samenwijzer import oer_store  # noqa: F401  — gebruikt door orchestrator (Task 14)

log = logging.getLogger(__name__)

_DB_PAD = Path("data/02-prepared/oeren.db")
_UITVOER_PAD = Path("data/01-raw/synthetisch/studenten.csv")
_OPLEIDINGEN_JSON = Path("scripts/synthetisch_opleidingen.json")
_SEED = 42

_TOTAAL_STUDENTEN = 1000
_STUDENTEN_PER_INSTELLING = 200
_MENTOREN_PER_INSTELLING = 10


def verdeel_studenten(totaal: int, opleidingen: list[str]) -> dict[str, int]:
    """Verdeel `totaal` studenten zo gelijkmatig mogelijk over opleidingen.

    Restanten worden uitgedeeld aan de eerste opleidingen in de lijst,
    zodat sum(verdeling.values()) == totaal exact klopt.
    """
    assert opleidingen, "opleidingen-lijst mag niet leeg zijn"
    n = len(opleidingen)
    basis = totaal // n
    rest = totaal - basis * n
    verdeling: dict[str, int] = {}
    for i, opl in enumerate(opleidingen):
        verdeling[opl] = basis + (1 if i < rest else 0)
    return verdeling


_VOORLETTERS = list("ABCDEFGHIJKLMNOPRSTVW")
_ACHTERNAMEN = [
    "de Vries", "Jansen", "Bakker", "Visser", "Smit", "Meijer", "de Boer", "Mulder",
    "de Groot", "Bos", "Vos", "Peters", "Hendriks", "van Leeuwen", "Dekker",
    "Brouwer", "de Wit", "Dijkstra", "Smits", "de Graaf", "van der Berg",
    "van Dijk", "Hoekstra", "Koster", "Prins", "Huisman", "Postma", "Bosch",
]


def maak_mentoren(rng: random.Random, aantal: int) -> list[str]:
    """Genereer `aantal` unieke mentor-namen in formaat 'V. Achternaam'.

    Deterministic via de meegegeven RNG.
    """
    namen: set[str] = set()
    pogingen = 0
    while len(namen) < aantal:
        v = rng.choice(_VOORLETTERS)
        a = rng.choice(_ACHTERNAMEN)
        namen.add(f"{v}. {a}")
        pogingen += 1
        if pogingen > aantal * 100:
            raise RuntimeError(f"Kon geen {aantal} unieke mentor-namen genereren")
    return sorted(namen)


def ken_mentor_toe(rng: random.Random, mentoren: list[str]) -> str:
    """Kies een mentor uit een lijst — willekeurig (uniform)."""
    return rng.choice(mentoren)


SECTOR_KOLOMMEN = ["Economie", "Landbouw", "Techniek", "DSV", "Zorgenwelzijn", "Anders"]

VOOROPLEIDING_KOLOMMEN = [
    "VooroplNiveau_HAVO",
    "VooroplNiveau_MBO",
    "VooroplNiveau_basis",
    "VooroplNiveau_educatie",
    "VooroplNiveau_prak",
    "VooroplNiveau_VMBO_BB",
    "VooroplNiveau_VMBO_GL",
    "VooroplNiveau_VMBO_KB",
    "VooroplNiveau_VMBO_TL",
    "VooroplNiveau_nan",
    "VooroplNiveau_VWOplus",
    "VooroplNiveau_other",
]

# Gewichten zodat VMBO_TL en VMBO_KB de meeste studenten leveren (realistisch voor MBO)
_VOOROPL_GEWICHTEN = [5, 8, 1, 1, 1, 6, 4, 8, 12, 2, 1, 2]

_NL_VOORNAMEN = [
    "Aisha", "Daan", "Emma", "Liam", "Noor", "Lucas", "Sara", "Mees",
    "Yasmin", "Bram", "Lotte", "Jens", "Fatima", "Tim", "Iris", "Sven",
    "Lisa", "Joris", "Sophie", "Stijn", "Anna", "Thijs", "Eva", "Finn",
    "Maud", "Olaf", "Tess", "Bas", "Lieke", "Niels",
]
_NL_ACHTERNAMEN = _ACHTERNAMEN  # hergebruik mentor-pool


def maak_studenten_naam(rng: random.Random) -> str:
    return f"{rng.choice(_NL_VOORNAMEN)} {rng.choice(_NL_ACHTERNAMEN)}"


def bouw_student_record(
    rng: random.Random,
    studentnummer: str,
    naam: str,
    instelling: str,
    opleiding: str,
    crebo: str,
    leerweg: str,
    cohort: str,
    niveau: int,
    sector: str,
    mentor: str,
) -> dict:
    """Bouw één student-rij met alle research-features synthetisch ingevuld."""
    # Klas: niveau-cijfer + cohort-letter (2024 → A, 2025 → B, …)
    cohort_letter = chr(ord("A") + int(cohort) - 2024)
    klas = f"{niveau}{cohort_letter}"

    # Absence + dropout-correlatie
    absence_unauthorized = round(rng.expovariate(1 / 12), 1)  # gemiddeld ~12
    absence_unauthorized = min(absence_unauthorized, 60.0)
    absence_authorized = round(rng.expovariate(1 / 8), 1)
    absence_authorized = min(absence_authorized, 40.0)
    # P(dropout) groeit met absence_unauthorized
    p_dropout = min(0.05 + absence_unauthorized / 100.0, 0.6)
    dropout = 1 if rng.random() < p_dropout else 0

    record = {
        "Studentnummer": studentnummer,
        "Naam": naam,
        "Klas": klas,
        "Mentor": mentor,
        "Instelling": instelling,
        "Opleiding": opleiding,
        "crebo": crebo,
        "leerweg": leerweg,
        "cohort": cohort,
        "StudentAge": int(rng.gauss(18, 1.8)),
        "StudentGender": rng.choice([0, 1]),
        "Dropout": dropout,
        "Aanmel_aantal": round(rng.uniform(1.0, 3.0), 1),
        "max1studie": round(rng.uniform(0.0, 1.0), 1),
        "absence_unauthorized": absence_unauthorized,
        "absence_authorized": absence_authorized,
        "Richting_nan": 0,
    }

    # Studentage clip
    record["StudentAge"] = max(15, min(record["StudentAge"], 25))

    # Sector one-hots
    for kol in SECTOR_KOLOMMEN:
        record[kol] = 1 if kol == sector else 0

    # Vooropleidings-one-hot (precies één 1)
    voorop_keuze = rng.choices(VOOROPLEIDING_KOLOMMEN, weights=_VOOROPL_GEWICHTEN, k=1)[0]
    for kol in VOOROPLEIDING_KOLOMMEN:
        record[kol] = 1 if kol == voorop_keuze else 0

    return record
