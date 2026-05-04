"""Eenmalig script: scant oeren/ en populeert oeren.db.

Gebruik:
    uv run python scripts/build_oer_catalog.py
    uv run python scripts/build_oer_catalog.py --oeren-pad ./oeren --db data/02-prepared/oeren.db
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Maak src/ importeerbaar als script vanuit project-root gedraaid wordt.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from samenwijzer import oer_store  # noqa: E402
from samenwijzer.oer_parsing import (  # noqa: E402
    bepaal_niveau,
    extraheer_kerntaken,
    extraheer_opleidingsnaam,
    parseer_bestandsnaam,
)

log = logging.getLogger(__name__)

# folder-naam → (snake_case key, display naam)
_INSTELLING_DISPLAY = {
    "aeres_oeren": "Aeres MBO",
    "davinci_oeren": "Da Vinci",
    "rijn_ijssel_oer": "Rijn IJssel",
    "talland_oeren": "Talland",
    "utrecht_oeren": "Utrecht",
    # 'oer_algemeen' is geen instelling → wordt overgeslagen
}


def _instelling_naam_uit_folder(folder_naam: str) -> str:
    """Converteer 'rijn_ijssel_oer' → 'rijn_ijssel'."""
    return folder_naam.replace("_oeren", "").replace("_oer", "")


def bouw_catalog(oeren_pad: Path, db_pad: Path) -> dict:
    """Scan oeren_pad recursief en populeer db_pad. Returns telling-dict."""
    telling = {"instellingen": 0, "oer_documenten": 0, "kerntaken": 0, "overgeslagen": 0}

    for folder in sorted(p for p in oeren_pad.iterdir() if p.is_dir()):
        # Skip onbekende folders (bv. oer_algemeen)
        display = _INSTELLING_DISPLAY.get(folder.name)
        if display is None:
            log.info("Folder overgeslagen (geen instelling): %s", folder.name)
            continue

        naam = _instelling_naam_uit_folder(folder.name)
        oer_store.voeg_instelling_toe(db_pad, naam, display)
        inst = oer_store.get_instelling_by_naam(db_pad, naam)
        telling["instellingen"] += 1

        for md in sorted(folder.glob("*.md")):
            meta = parseer_bestandsnaam(md.name)
            if meta is None:
                telling["overgeslagen"] += 1
                continue

            opleiding = extraheer_opleidingsnaam(md.name) or f"Crebo {meta['crebo']}"
            tekst = md.read_text(encoding="utf-8", errors="replace")
            niveau = bepaal_niveau(md.name, tekst)
            try:
                oer_id = oer_store.voeg_oer_document_toe(
                    db_pad,
                    instelling_id=inst["id"],
                    opleiding=opleiding,
                    crebo=meta["crebo"],
                    cohort=meta["cohort"],
                    leerweg=meta["leerweg"],
                    niveau=niveau,
                    bestandspad=str(md.relative_to(oeren_pad.parent)),
                )
                telling["oer_documenten"] += 1
            except Exception:
                # Dubbele (instelling, crebo, leerweg, cohort) — sla deze variant over.
                log.warning(
                    "Duplicaat overgeslagen: %s/%s/%s/%s",
                    naam,
                    meta["crebo"],
                    meta["leerweg"],
                    meta["cohort"],
                )
                telling["overgeslagen"] += 1
                continue

            for kt in extraheer_kerntaken(tekst):
                oer_store.voeg_kerntaak_toe(
                    db_pad,
                    oer_id=oer_id,
                    code=kt["code"],
                    naam=kt["naam"],
                    type_=kt["type"],
                    parent_code=None,
                    volgorde=kt["volgorde"],
                )
                telling["kerntaken"] += 1

    return telling


def main() -> int:
    parser = argparse.ArgumentParser(description="Bouw oeren.db uit oeren/-map")
    parser.add_argument("--oeren-pad", default="oeren", help="Pad naar oeren-map")
    parser.add_argument(
        "--db", default="data/02-prepared/oeren.db", help="Pad naar oeren.db"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    oeren_pad = Path(args.oeren_pad)
    if not oeren_pad.exists():
        log.error("oeren-pad bestaat niet: %s", oeren_pad)
        return 1

    db_pad = Path(args.db)
    if db_pad.exists():
        db_pad.unlink()  # Opnieuw opbouwen — leeg starten

    telling = bouw_catalog(oeren_pad, db_pad)
    log.info(
        "Klaar — %d instellingen, %d OERs, %d kerntaken (%d overgeslagen)",
        telling["instellingen"],
        telling["oer_documenten"],
        telling["kerntaken"],
        telling["overgeslagen"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
