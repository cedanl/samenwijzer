"""Genereer een synthetische 1000-studenten-set gekoppeld aan echte OERs.

Gebruik:
    uv run python scripts/generate_synthetisch_data.py
"""

from __future__ import annotations

import argparse  # noqa: F401  — gebruikt door orchestrator (Task 14)
import json  # noqa: F401  — gebruikt door orchestrator (Task 14)
import logging
import random  # noqa: F401  — gebruikt door student-record (Task 13)
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
