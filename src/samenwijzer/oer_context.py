"""OER-tekst ophalen als AI-context voor coach en tutor."""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

_MAX_TEKENS = 120_000
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DB_PAD = _PROJECT_ROOT / "data" / "02-prepared" / "oeren.db"


def laad_oer_tekst(bestandspad: str | Path) -> str:
    """Lees OER-markdownbestand; geeft lege string terug als bestand niet bestaat."""
    pad = Path(bestandspad)
    if not pad.is_absolute():
        pad = _PROJECT_ROOT / pad
    if not pad.exists():
        return ""
    return pad.read_text(encoding="utf-8", errors="replace")[:_MAX_TEKENS]


def haal_oer_context_op(student_row: dict) -> str:
    """Laad de OER-tekst voor de gegeven student.

    Zoekt de OER op via instelling/crebo/leerweg/cohort uit de catalog.
    Geeft lege string terug als de DB of het bestand niet beschikbaar is.
    """
    try:
        from samenwijzer import oer_store  # lazy import — DB hoeft niet aanwezig te zijn

        rij = oer_store.get_oer_voor_student(
            db_pad=_DB_PAD,
            instelling_naam=str(student_row.get("instelling", "") or ""),
            crebo=str(student_row.get("crebo", "") or ""),
            leerweg=str(student_row.get("leerweg", "") or ""),
            cohort=str(student_row.get("cohort", "") or ""),
        )
        if rij is None:
            return ""
        return laad_oer_tekst(rij["bestandspad"])
    except Exception:
        log.debug("OER-context niet beschikbaar", exc_info=True)
        return ""
