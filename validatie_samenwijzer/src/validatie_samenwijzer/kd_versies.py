"""KD-versies per cohort.

Het nieuwste kwalificatiedossier staat als ``<crebo>.md`` in de KD-map; oudere versies staan in
``versies/`` met een manifest ``versies/versies.json`` (expliciet, niet afgeleid uit datums)::

    {"25122": [{"versie": "2016", "bestand": "25122@2016.md", "cohorten": [2016, 2025]}]}

``kies_kd_pad`` geeft de versie waarvan het cohortbereik het cohort van de OER bevat; geen match
betekent: de nieuwste (``<crebo>.md``) geldt. Het landelijke KD wordt nooit overschreven; een
oude versie komt ernaast. Zie docs/plans/2026-10-27-flexibele-documentlaag.md (§4).
"""

import json
import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def kd_map() -> Path:
    """Map met de KD-markdownbestanden. Default ``<repo-root>/kwalificatiedossiers/pdfs``;
    override via ``KWALDOSSIERS_PAD``."""
    base = os.environ.get("KWALDOSSIERS_PAD")
    if base:
        return Path(base).resolve()
    # kd_versies.py → parents[3] = repo-root → kwalificatiedossiers/pdfs
    return Path(__file__).resolve().parents[3] / "kwalificatiedossiers" / "pdfs"


def _lees_manifest(directory: Path) -> dict[str, list[dict]]:
    """Het manifest, of een lege dict als het ontbreekt of kapot is (geen crash in de chat)."""
    pad = directory / "versies" / "versies.json"
    if not pad.exists():
        return {}
    try:
        manifest = json.loads(pad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("KD-versiemanifest onleesbaar (%s): %s", pad, e)
        return {}
    return manifest if isinstance(manifest, dict) else {}


def _cohortjaar(cohort: str | int | None) -> int | None:
    try:
        return int(cohort)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def kies_kd_pad(crebo: str, cohort: str | int | None) -> Path | None:
    """Pad naar de KD-versie die voor dit cohort geldt, of None (dan geldt de nieuwste)."""
    jaar = _cohortjaar(cohort)
    if jaar is None:
        return None
    directory = kd_map()
    for versie in _lees_manifest(directory).get(str(crebo), []):
        van, tot = versie["cohorten"]
        pad = directory / "versies" / versie["bestand"]
        if van <= jaar <= tot and pad.exists():
            return pad
    return None


def controleer_kd_versies(conn: sqlite3.Connection) -> list[str]:
    """Meldingen voor KD-versies in het manifest zonder OER van een cohort in dat bereik.

    Een oudere KD is alleen nuttig als er een OER van dat cohort voor die opleiding bestaat.
    """
    meldingen = []
    for crebo, versies in _lees_manifest(kd_map()).items():
        cohorten = {
            _cohortjaar(r["cohort"])
            for r in conn.execute("SELECT cohort FROM oer_documenten WHERE crebo = ?", (crebo,))
        }
        for v in versies:
            van, tot = v["cohorten"]
            if not any(c is not None and van <= c <= tot for c in cohorten):
                meldingen.append(
                    f"KD {crebo} versie {v['versie']}: geen OER met cohort {van}–{tot}; "
                    "deze KD-versie wordt niet gebruikt."
                )
    return meldingen
