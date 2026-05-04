"""OER-parsing helpers: bestandsnaam, kerntaken, opleidingsnaam, niveau.

Synced from validatie_samenwijzer/src/validatie_samenwijzer/ingest.py @ d64f3cf.
Houd functioneel gelijk; verschilt alleen waar samenwijzer geen ingest-pijplijn heeft.
"""

from __future__ import annotations

import re

# ── Bestandsnaam parsen ───────────────────────────────────────────────────────

_CREBO_LEERWEG_JAAR = re.compile(
    r"(?<!\d)(\d{5})\s*[-_]?\s*(BOL|BBL)(?:BOL|BBL)?\s*[-_]?\s*(\d{4})", re.IGNORECASE
)
_CREBO = re.compile(r"(?<!\d)(\d{5})(?!\d)")
_LEERWEG = re.compile(r"\b(BOL|BBL)\b", re.IGNORECASE)
_JAAR = re.compile(r"(?<!\d)(20[2-3]\d)(?!\d)")
_HUIDIG_COHORT = "2025"


def parseer_bestandsnaam(bestandsnaam: str) -> dict | None:
    """Haal crebo, leerweg en cohort op uit de bestandsnaam.

    Ondersteunt:
    - Da Vinci:     25168BOL2025Examenplan.pdf
    - Rijn IJssel:  content_oer-2024-2025-ci-25651-acteur.pdf
    - Talland:      25180 Kok 24 maanden BBL.pdf
    Geeft None als er geen 5-cijferig crebo gevonden wordt.
    """
    m = _CREBO_LEERWEG_JAAR.search(bestandsnaam)
    if m:
        return {"crebo": m.group(1), "leerweg": m.group(2).upper(), "cohort": m.group(3)}

    crebo_m = _CREBO.search(bestandsnaam)
    if not crebo_m:
        return None

    crebo = crebo_m.group(1)
    leerweg_m = _LEERWEG.search(bestandsnaam)
    leerweg = leerweg_m.group(1).upper() if leerweg_m else "BOL"
    jaar_m = _JAAR.search(bestandsnaam)
    cohort = jaar_m.group(1) if jaar_m else _HUIDIG_COHORT
    return {"crebo": crebo, "leerweg": leerweg, "cohort": cohort}
