"""Genereer synthetische welzijn-data voor de 1000 synthetische studenten.

Wekelijkse welzijnschecks (antwoord 1=goed / 2=matig / 3=zwaar) over een periode
van ~10 weken. Niet elke student vult elke week in; antwoord-kansen zijn licht
gecorreleerd met `voortgang` zodat studenten met lagere voortgang vaker een
matig/zwaar-antwoord krijgen — daardoor is de signaleringen-tab betekenisvol.

Reproduceerbaar via `_SEED = 42`.

Vereist: `data/01-raw/synthetisch/studenten.csv` moet bestaan
(genereer met `scripts/generate_synthetisch_data.py`).

Gebruik:
    uv run python scripts/generate_synthetisch_welzijn.py
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from samenwijzer.prepare import load_synthetisch_csv  # noqa: E402

log = logging.getLogger(__name__)

_INVOER_PAD = Path("data/01-raw/synthetisch/studenten.csv")
_UITVOER_PAD = Path("data/01-raw/synthetisch/welzijn.csv")
_SEED = 42

# Periode: 10 wekelijkse checks tot eind april 2026 (laatste check = afgelopen maandag).
_LAATSTE_CHECK = date(2026, 5, 4)
_AANTAL_WEKEN = 10
_KANS_DEELNAME_PER_WEEK = 0.45
_KANS_TOELICHTING = 0.30

_TOELICHTINGEN_GOED = [
    "Beetje beter",
    "Het loopt",
    "Lekker bezig deze week",
    "Goed weekend gehad",
    "Stage gaat lekker",
    "Tentamens zijn goed gegaan",
]
_TOELICHTINGEN_MATIG = [
    "Veel huiswerk deze week",
    "Druk met stage",
    "Slechte nachtrust",
    "Beetje stress",
    "Niet helemaal lekker",
    "Toetsen stapelen op",
    "Moeite met plannen",
    "Privé dingen spelen",
]
_TOELICHTINGEN_ZWAAR = [
    "Stage loopt niet lekker",
    "Ik weet niet meer of ik dit wil",
    "Veel privé gedoe",
    "Ik snap de leerstof niet",
    "Nog steeds moeilijk",
    "Echt te veel allemaal",
    "Geen zin meer in school",
    "Conflict met stagebegeleider",
]


def _antwoord_kansen(voortgang: float) -> tuple[float, float, float]:
    """Geef kansverdeling (P(1), P(2), P(3)) gebaseerd op voortgang.

    Hoge voortgang → vaker antwoord 1; lage voortgang → vaker 2 of 3.
    """
    if voortgang >= 0.7:
        return (0.75, 0.20, 0.05)
    if voortgang >= 0.4:
        return (0.50, 0.35, 0.15)
    return (0.25, 0.35, 0.40)


def _kies_toelichting(rng: random.Random, antwoord: int) -> str:
    """Kies een toelichting (of laat leeg op basis van _KANS_TOELICHTING)."""
    if rng.random() >= _KANS_TOELICHTING:
        return ""
    pool = {
        1: _TOELICHTINGEN_GOED,
        2: _TOELICHTINGEN_MATIG,
        3: _TOELICHTINGEN_ZWAAR,
    }[antwoord]
    return rng.choice(pool)


def genereer_rijen(
    studenten: list[dict],
    seed: int = _SEED,
    aantal_weken: int = _AANTAL_WEKEN,
    kans_deelname: float = _KANS_DEELNAME_PER_WEEK,
    laatste_check: date = _LAATSTE_CHECK,
) -> list[dict]:
    """Genereer welzijn-rijen voor de gegeven studenten.

    Args:
        studenten: Iterable van student-dicts met 'studentnummer' en 'voortgang'.
        seed: RNG-seed voor reproduceerbaarheid.
        aantal_weken: Aantal wekelijkse check-momenten.
        kans_deelname: Kans dat een student in een gegeven week reageert.
        laatste_check: Datum van de meest recente check.

    Returns:
        Lijst van dicts met keys: studentnummer, datum, antwoord, toelichting.
        Gesorteerd op (studentnummer, datum).
    """
    rng = random.Random(seed)
    rijen: list[dict] = []

    for student in studenten:
        snr = str(student["studentnummer"])
        voortgang = float(student["voortgang"])
        kansen = _antwoord_kansen(voortgang)

        for week in range(aantal_weken):
            if rng.random() > kans_deelname:
                continue
            check_datum = laatste_check - timedelta(weeks=week)
            antwoord = rng.choices([1, 2, 3], weights=kansen)[0]
            toelichting = _kies_toelichting(rng, antwoord)
            rijen.append(
                {
                    "studentnummer": snr,
                    "datum": check_datum.isoformat(),
                    "antwoord": antwoord,
                    "toelichting": toelichting,
                }
            )

    rijen.sort(key=lambda r: (r["studentnummer"], r["datum"]))
    return rijen


def schrijf_csv(rijen: list[dict], pad: Path) -> None:
    """Schrijf welzijn-rijen naar een CSV-bestand met `;` als separator."""
    pad.parent.mkdir(parents=True, exist_ok=True)
    with pad.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["studentnummer", "datum", "antwoord", "toelichting"],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(rijen)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--invoer", type=Path, default=_INVOER_PAD)
    parser.add_argument("--uitvoer", type=Path, default=_UITVOER_PAD)
    parser.add_argument("--seed", type=int, default=_SEED)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    df = load_synthetisch_csv(args.invoer)
    studenten = df[["studentnummer", "voortgang"]].to_dict(orient="records")
    rijen = genereer_rijen(studenten, seed=args.seed)
    schrijf_csv(rijen, args.uitvoer)

    n_studenten_gedekt = len({r["studentnummer"] for r in rijen})
    log.info(
        "Welzijn-CSV: %d rijen, %d unieke studenten → %s",
        len(rijen),
        n_studenten_gedekt,
        args.uitvoer,
    )


if __name__ == "__main__":
    main()
