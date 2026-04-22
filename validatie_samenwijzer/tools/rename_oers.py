"""Extraheer metadata (crebo, leerweg, cohort) uit titelpagina's en hernoem PDF-bestanden.

Gebruik:
    uv run python tools/rename_oers.py --dry-run        # voorbeeld zonder hernoemen
    uv run python tools/rename_oers.py                  # hernoem bestanden
    uv run python tools/rename_oers.py --map talland_oeren
"""

import argparse
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Regex voor inhoudsextractie ───────────────────────────────────────────────

# Crebo met context (bijv. "CREBO 25655" of "Kwalificatiecode: 25655")
_CREBO_MET_CONTEXT = re.compile(
    r"(?:crebo|kwalificatiecode|kwalificatie(?:dossier)?|code)[\s:–-]*(\d{5})",
    re.IGNORECASE,
)
# Crebo zonder context: eerste 5-cijferig getal dat er uitziet als een crebo
_CREBO_PUUR = re.compile(r"(?<!\d)(\d{5})(?!\d)")
_LEERWEG = re.compile(r"\b(BOL|BBL)\b", re.IGNORECASE)
_JAAR = re.compile(r"(?<!\d)(20[2-3]\d)(?!\d)")

# ── Bestandsnaam al parseerbaar? ──────────────────────────────────────────────

_NAAM_PARSEERBAAR = re.compile(
    r"(?<!\d)(\d{5})(?!\d)",  # crebo in naam is voldoende voor ingest
)


def _naam_heeft_crebo(bestandsnaam: str) -> bool:
    return bool(_NAAM_PARSEERBAAR.search(bestandsnaam))


# ── Metadata uit tekst ────────────────────────────────────────────────────────

def _extraheer_uit_tekst(tekst: str) -> dict:
    crebo_m = _CREBO_MET_CONTEXT.search(tekst) or _CREBO_PUUR.search(tekst)
    leerweg_m = _LEERWEG.search(tekst)
    jaar_m = _JAAR.search(tekst)
    return {
        "crebo": crebo_m.group(1) if crebo_m else None,
        "leerweg": leerweg_m.group(1).upper() if leerweg_m else None,
        "cohort": jaar_m.group(1) if jaar_m else None,
    }


# ── Tekst uit eerste pagina's ─────────────────────────────────────────────────

def _lees_eerste_paginas(pad: Path, n: int = 2) -> str:
    import pdfplumber

    tekst_delen = []
    with pdfplumber.open(str(pad)) as pdf:
        for pagina in pdf.pages[:n]:
            t = pagina.extract_text()
            if t:
                tekst_delen.append(t)
    tekst = "\n\n".join(tekst_delen)

    if len(tekst.strip()) < 50:
        logger.debug("pdfplumber leverde te weinig tekst voor '%s', gebruik OCR.", pad.name)
        try:
            import pytesseract
            from pdf2image import convert_from_path

            paginas = convert_from_path(str(pad), dpi=200, first_page=1, last_page=n)
            tekst = "\n\n".join(
                t for p in paginas if (t := pytesseract.image_to_string(p, lang="nld").strip())
            )
        except Exception as e:
            logger.warning("OCR mislukt voor '%s': %s", pad.name, e)

    return tekst


# ── Nieuwe bestandsnaam ───────────────────────────────────────────────────────

def _nieuwe_naam(pad: Path, meta: dict) -> Path | None:
    """Geeft nieuw pad terug, of None als er onvoldoende metadata is."""
    crebo = meta.get("crebo")
    if not crebo:
        return None

    leerweg = meta.get("leerweg") or "BOL"
    cohort = meta.get("cohort") or "2025"
    prefix = f"{crebo}_{leerweg}_{cohort}__"

    nieuwe_naam = prefix + pad.name
    return pad.parent / nieuwe_naam


# ── Verwerk één bestand ───────────────────────────────────────────────────────

def _verwerk(pad: Path, dry_run: bool) -> str:
    """Retourneert 'hernoemd', 'overgeslagen' of 'geen_metadata'."""
    if _naam_heeft_crebo(pad.name):
        return "overgeslagen"

    try:
        tekst = _lees_eerste_paginas(pad)
    except Exception as e:
        logger.error("Kan '%s' niet lezen: %s", pad.name, e)
        return "fout"

    meta = _extraheer_uit_tekst(tekst)
    nieuw_pad = _nieuwe_naam(pad, meta)

    if nieuw_pad is None:
        logger.warning("Geen crebo gevonden in '%s'", pad.name)
        return "geen_metadata"

    if nieuw_pad == pad:
        return "overgeslagen"

    leerweg_info = meta.get("leerweg") or "(geen leerweg gevonden, BOL aangenomen)"
    cohort_info = meta.get("cohort") or "(geen cohort gevonden, 2025 aangenomen)"
    logger.info(
        "%s → %s  [crebo=%s leerweg=%s cohort=%s]",
        pad.name, nieuw_pad.name, meta["crebo"], leerweg_info, cohort_info,
    )

    if not dry_run:
        pad.rename(nieuw_pad)

    return "hernoemd"


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Hernoem OER-PDFs met metadata-prefix")
    parser.add_argument("--oeren-pad", default="oeren", help="Map met OER-mappen")
    parser.add_argument("--map", help="Verwerk alleen deze submap (bijv. talland_oeren)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Toon wat hernoemd zou worden zonder daadwerkelijk te hernoemen",
    )
    args = parser.parse_args()

    oeren_root = Path(args.oeren_pad)
    if not oeren_root.exists():
        logger.error("Map '%s' bestaat niet.", oeren_root)
        sys.exit(1)

    if args.dry_run:
        logger.info("DRY-RUN — bestanden worden niet hernoemd.")

    mappen = [oeren_root / args.map] if args.map else sorted(oeren_root.iterdir())

    tellers = {"hernoemd": 0, "overgeslagen": 0, "geen_metadata": 0, "fout": 0}

    for map_pad in mappen:
        if not map_pad.is_dir():
            continue
        pdfs = sorted(p for p in map_pad.iterdir() if p.suffix.lower() == ".pdf")
        logger.info("── %s (%d bestanden) ──", map_pad.name, len(pdfs))
        for pdf in pdfs:
            uitkomst = _verwerk(pdf, dry_run=args.dry_run)
            tellers[uitkomst] += 1

    print()
    print(f"{'DRY-RUN ' if args.dry_run else ''}Resultaat:")
    print(f"  Hernoemd:       {tellers['hernoemd']}")
    print(f"  Overgeslagen:   {tellers['overgeslagen']}  (naam had al crebo)")
    print(f"  Geen metadata:  {tellers['geen_metadata']}  (crebo niet gevonden)")
    print(f"  Fouten:         {tellers['fout']}")


if __name__ == "__main__":
    main()
