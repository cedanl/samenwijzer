"""Genereer een synthetische 1000-studenten-set gekoppeld aan echte OERs.

Gebruik:
    uv run python scripts/generate_synthetisch_data.py
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from samenwijzer import oer_store

log = logging.getLogger(__name__)

_DB_PAD = Path("data/02-prepared/oeren.db")
_UITVOER_PAD = Path("data/01-raw/synthetisch/studenten.csv")
_OPLEIDINGEN_JSON = Path("scripts/synthetisch_opleidingen.json")
_SEED = 42

_AANTAL_INSTELLINGEN = 4   # Aeres uitgesloten
_TOTAAL_STUDENTEN = 1000
_STUDENTEN_PER_INSTELLING = _TOTAAL_STUDENTEN // _AANTAL_INSTELLINGEN  # 250
_OVER_TE_SLAAN_INSTELLINGEN = {"aeres"}  # geen overlap met de 14 opleidingen


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


# ── Orchestrator ──────────────────────────────────────────────────────────────


def _opleidingen_per_instelling(
    db_pad: Path, gewenste_opleidingen: list[dict]
) -> dict[str, list[dict]]:
    """Voor elke instelling: welke gewenste opleidingen biedt zij aan?

    Dict-vorm: {instelling_naam: [{"opleiding", "crebo", "leerweg", "cohort", "niveau",
    "sector"}, ...]}
    Instellingen in _OVER_TE_SLAAN_INSTELLINGEN worden uitgesloten.
    """
    oer_store.init_db(db_pad)
    resultaat: dict[str, list[dict]] = {}
    for opl_meta in gewenste_opleidingen:
        opl = opl_meta["opleiding"]
        sector = opl_meta["sector"]
        niveau = opl_meta["niveau"]
        conn = sqlite3.connect(db_pad)
        conn.row_factory = sqlite3.Row
        try:
            rijen = conn.execute(
                "SELECT o.*, i.naam AS inst_naam FROM oer_documenten o "
                "JOIN instellingen i ON i.id = o.instelling_id "
                "WHERE o.opleiding = ? AND o.niveau = ?",
                (opl, niveau),
            ).fetchall()
        finally:
            conn.close()
        for r in rijen:
            inst_naam = r["inst_naam"]
            if inst_naam in _OVER_TE_SLAAN_INSTELLINGEN:
                continue
            resultaat.setdefault(inst_naam, []).append({
                "opleiding": opl,
                "crebo": r["crebo"],
                "leerweg": r["leerweg"],
                "cohort": r["cohort"],
                "niveau": niveau,
                "sector": sector,
            })
    return resultaat


def _kolomvolgorde() -> list[str]:
    """Definitieve volgorde van CSV-kolommen."""
    return [
        "Studentnummer", "Naam", "Klas", "Mentor", "Instelling", "Opleiding",
        "crebo", "leerweg", "cohort",
        "StudentAge", "StudentGender", "Dropout",
        "Aanmel_aantal", "max1studie",
        "absence_unauthorized", "absence_authorized",
        "Richting_nan",
        *SECTOR_KOLOMMEN,
        *VOOROPLEIDING_KOLOMMEN,
    ]


def _mentoren_per_instelling(aantal_instellingen: int, totaal_mentoren: int = 50) -> list[int]:
    """Mentor-distributie: 50 totaal over N instellingen.

    Eerste (totaal_mentoren % aantal_instellingen) instellingen krijgen 1 extra.
    """
    basis = totaal_mentoren // aantal_instellingen
    rest = totaal_mentoren - basis * aantal_instellingen
    return [basis + (1 if i < rest else 0) for i in range(aantal_instellingen)]


def genereer(
    db_pad: Path = _DB_PAD,
    opleidingen_json: Path = _OPLEIDINGEN_JSON,
    uitvoer_pad: Path = _UITVOER_PAD,
    seed: int = _SEED,
) -> None:
    """Genereer studenten.csv. Hard-faalt als de validatiestap iets mis vindt."""
    rng = random.Random(seed)

    gewenst = json.loads(opleidingen_json.read_text())
    per_inst = _opleidingen_per_instelling(db_pad, gewenst)

    if len(per_inst) != _AANTAL_INSTELLINGEN:
        raise ValueError(
            f"Verwacht {_AANTAL_INSTELLINGEN} instellingen, gevonden: "
            f"{len(per_inst)} ({list(per_inst)})"
        )

    # Mentor-aantal per instelling (sortering = alfabetisch zodat reproduceerbaar)
    inst_namen_sorted = sorted(per_inst.keys())
    mentoren_aantallen = _mentoren_per_instelling(len(inst_namen_sorted))

    # Genereer alle mentoren in één batch → gegarandeerd globaal unieke namen
    totaal_mentoren = sum(mentoren_aantallen)
    alle_mentoren = maak_mentoren(rng, totaal_mentoren)
    mentor_partitie: list[list[str]] = []
    start = 0
    for n in mentoren_aantallen:
        mentor_partitie.append(alle_mentoren[start : start + n])
        start += n

    studenten: list[dict] = []
    nummer = 100000

    for idx, inst_naam in enumerate(inst_namen_sorted):
        beschikbaar = per_inst[inst_naam]
        # Display-naam ophalen
        inst_row = oer_store.get_instelling_by_naam(db_pad, inst_naam)
        display = inst_row["display_naam"]

        # Mentoren voor deze instelling (uit de globale partitie)
        mentoren = mentor_partitie[idx]

        # Verdeel _STUDENTEN_PER_INSTELLING over de opleidingen die deze instelling aanbiedt
        opleidingnamen = sorted({o["opleiding"] for o in beschikbaar})
        verdeling = verdeel_studenten(_STUDENTEN_PER_INSTELLING, opleidingnamen)

        # Map opleiding-naam → eerste beschikbare OER-variant (stabiel via dict-invoeging)
        opl_naar_oer: dict[str, dict] = {}
        for o in beschikbaar:
            opl_naar_oer.setdefault(o["opleiding"], o)

        for opl_naam, n in verdeling.items():
            oer = opl_naar_oer[opl_naam]
            for _ in range(n):
                studenten.append(bouw_student_record(
                    rng=rng,
                    studentnummer=str(nummer),
                    naam=maak_studenten_naam(rng),
                    instelling=display,
                    opleiding=opl_naam,
                    crebo=oer["crebo"],
                    leerweg=oer["leerweg"],
                    cohort=oer["cohort"],
                    niveau=oer["niveau"],
                    sector=oer["sector"],
                    mentor=ken_mentor_toe(rng, mentoren),
                ))
                nummer += 1

    # Validatie
    if len(studenten) != _TOTAAL_STUDENTEN:
        raise ValueError(f"Verwacht {_TOTAAL_STUDENTEN} studenten, kreeg {len(studenten)}")
    inst_counts: dict[str, int] = {}
    for s in studenten:
        inst_counts[s["Instelling"]] = inst_counts.get(s["Instelling"], 0) + 1
    if any(c != _STUDENTEN_PER_INSTELLING for c in inst_counts.values()):
        raise ValueError(f"Instelling-distributie ongelijk: {inst_counts}")

    # Schrijf CSV
    uitvoer_pad.parent.mkdir(parents=True, exist_ok=True)
    kolommen = _kolomvolgorde()
    with uitvoer_pad.open("w", encoding="utf-8", newline="") as fh:
        schrijver = csv.DictWriter(fh, fieldnames=kolommen)
        schrijver.writeheader()
        schrijver.writerows(studenten)

    log.info(
        "Geschreven: %s — %d studenten, %d instellingen",
        uitvoer_pad, len(studenten), len(inst_counts),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Genereer synthetisch studenten.csv")
    parser.add_argument("--db", default=str(_DB_PAD))
    parser.add_argument("--opleidingen", default=str(_OPLEIDINGEN_JSON))
    parser.add_argument("--uitvoer", default=str(_UITVOER_PAD))
    parser.add_argument("--seed", type=int, default=_SEED)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    genereer(
        db_pad=Path(args.db),
        opleidingen_json=Path(args.opleidingen),
        uitvoer_pad=Path(args.uitvoer),
        seed=args.seed,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
