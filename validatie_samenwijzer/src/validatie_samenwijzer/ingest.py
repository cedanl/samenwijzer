"""OER-ingestie pipeline: parse → extraheer → sla op in SQLite."""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# ── Bestandsnaam parsen ───────────────────────────────────────────────────────

# Patroon 1 (Da Vinci): crebo direct gevolgd door BOL/BBL (evt. gecombineerd) en jaar
_CREBO_LEERWEG_JAAR = re.compile(
    r"(?<!\d)(\d{5})\s*[-_]?\s*(BOL|BBL)(?:BOL|BBL)?\s*[-_]?\s*(\d{4})", re.IGNORECASE
)
# Losse patronen voor fallback — (?<!\d) en (?!\d) i.p.v. \b om underscores te doorbreken
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
    # Patroon 1: crebo + leerweg + jaar aaneengesloten (Da Vinci)
    m = _CREBO_LEERWEG_JAAR.search(bestandsnaam)
    if m:
        return {"crebo": m.group(1), "leerweg": m.group(2).upper(), "cohort": m.group(3)}

    # Patroon 2: losse elementen — crebo verplicht, leerweg en jaar optioneel
    crebo_m = _CREBO.search(bestandsnaam)
    if not crebo_m:
        return None

    crebo = crebo_m.group(1)
    leerweg_m = _LEERWEG.search(bestandsnaam)
    leerweg = leerweg_m.group(1).upper() if leerweg_m else "BOL"
    jaar_m = _JAAR.search(bestandsnaam)
    cohort = jaar_m.group(1) if jaar_m else _HUIDIG_COHORT

    return {"crebo": crebo, "leerweg": leerweg, "cohort": cohort}


# ── Kerntaken extraheren ──────────────────────────────────────────────────────

_KT_PATROON = re.compile(
    r"^\s*(B\d+-K\d+(?:-W\d+)?|Kerntaak\s+\d+|Werkproces\s+\d+\.\d+)"
    r"\s*[:\-–]?\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)


def extraheer_kerntaken(tekst: str) -> list[dict]:
    """Haal kerntaken en werkprocessen uit OER-tekst via regex."""
    if not tekst:
        return []

    resultaten = []
    volgorde = 0
    for m in _KT_PATROON.finditer(tekst):
        code = m.group(1).strip()
        naam = m.group(2).strip()[:200]
        code_lower = code.lower()

        if "werkproces" in code_lower or re.match(r"B\d+-K\d+-W\d+", code):
            type_ = "werkproces"
        else:
            type_ = "kerntaak"

        resultaten.append({"code": code, "naam": naam, "type": type_, "volgorde": volgorde})
        volgorde += 1

    return resultaten


# ── Tekstextractie per bestandstype ──────────────────────────────────────────

_OCR_DREMPEL = 100  # minimaal aantal tekens voor acceptabele tekst


def _extraheer_tekst_ocr(pad: Path) -> str:
    """Tesseract OCR fallback voor gescande of afbeelding-gebaseerde PDFs."""
    import pytesseract
    from pdf2image import convert_from_path

    paginas = convert_from_path(str(pad), dpi=200)
    return "\n\n".join(
        t for p in paginas if (t := pytesseract.image_to_string(p, lang="nld").strip())
    )


def extraheer_tekst_pdf(pad: Path) -> str:
    """Extraheer tekst uit een PDF via pdfplumber; valt terug op Tesseract OCR bij < 100 tekens."""
    import pdfplumber

    tekst_delen = []
    with pdfplumber.open(str(pad)) as pdf:
        for pagina in pdf.pages:
            t = pagina.extract_text()
            if t:
                tekst_delen.append(t)
    tekst = "\n\n".join(tekst_delen)

    if len(tekst.strip()) < _OCR_DREMPEL:
        log.info("pdfplumber leverde te weinig tekst voor '%s', val terug op OCR.", pad.name)
        tekst = _extraheer_tekst_ocr(pad)

    return tekst


def extraheer_tekst_html(pad: Path) -> str:
    """Extraheer zichtbare tekst uit een HTML-bestand; verwijdert scripts, stijlen en nav."""
    from bs4 import BeautifulSoup

    html = pad.read_text(encoding="utf-8", errors="replace")
    soep = BeautifulSoup(html, "html.parser")
    for tag in soep(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soep.get_text(separator="\n", strip=True)


def extraheer_tekst_md(pad: Path) -> str:
    """Lees een Markdown-bestand."""
    return pad.read_text(encoding="utf-8", errors="replace")


def converteer_naar_markdown(pad: Path) -> Path:
    """Converteer een PDF naar Markdown via markitdown.

    Slaat het resultaat op als <stem>.md naast het bronbestand.

    Args:
        pad: Pad naar het PDF-bestand.

    Returns:
        Pad naar het gegenereerde .md-bestand, of het originele pad bij mislukking
        of als het geen PDF is.
    """
    if pad.suffix.lower() != ".pdf":
        return pad
    md_pad = pad.with_suffix(".md")
    if md_pad.exists():
        return md_pad
    try:
        from markitdown import MarkItDown

        md = MarkItDown()
        resultaat = md.convert(str(pad))
        md_pad.write_text(resultaat.text_content, encoding="utf-8")
        log.info("PDF geconverteerd naar Markdown: '%s'", md_pad.name)
    except Exception as e:
        log.warning("Markitdown-conversie mislukt voor '%s': %s", pad.name, e)
        return pad
    return md_pad


def extraheer_tekst(pad: Path) -> str:
    """Extraheer tekst uit PDF, HTML of Markdown."""
    suffix = pad.suffix.lower()
    if suffix == ".pdf":
        return extraheer_tekst_pdf(pad)
    if suffix in {".html", ".htm"}:
        return extraheer_tekst_html(pad)
    if suffix == ".md":
        return extraheer_tekst_md(pad)
    raise ValueError(f"Niet-ondersteund bestandstype: {suffix}")


# ── CLI pipeline ──────────────────────────────────────────────────────────────

_INSTELLINGEN = {
    "aeres": "Aeres MBO",
    "davinci": "Da Vinci College",
    "rijn_ijssel": "Rijn IJssel",
    "talland": "Talland",
    "utrecht": "ROC Utrecht",
}

_MAP_NAAM = {
    "aeres": "aeres_oeren",
    "davinci": "davinci_oeren",
    "rijn_ijssel": "rijn_ijssel_oer",
    "talland": "talland_oeren",
    "utrecht": "utrecht_oeren",
}

_ONDERSTEUNDE_EXTENSIES = {".pdf", ".html", ".htm", ".md"}


def _resolveer_oer(
    pad: Path,
    instelling_naam: str,
    conn: sqlite3.Connection,
    *,
    reset: bool,
) -> tuple[int, dict] | None:
    """Zoek of maak een OER-record aan; geef (oer_id, meta) of None als overgeslagen.

    Meerdere bestanden met hetzelfde crebo/leerweg/cohort (bijv. OER + examenplan)
    worden allemaal geïndexeerd onder hetzelfde oer_id.
    """
    from validatie_samenwijzer.db import (
        get_instelling_by_naam,
        get_oer_document,
        update_oer_bestandspad,
        voeg_oer_document_toe,
    )

    meta = parseer_bestandsnaam(pad.name)
    if meta is None:
        log.warning("Kan crebo/leerweg/cohort niet parsen uit '%s' — overgeslagen.", pad.name)
        return None

    inst = get_instelling_by_naam(conn, instelling_naam)
    if inst is None:
        log.error("Instelling '%s' niet gevonden in database.", instelling_naam)
        return None

    oer = get_oer_document(conn, inst["id"], meta["crebo"], meta["cohort"], meta["leerweg"])
    if oer is None:
        oer_id = voeg_oer_document_toe(
            conn,
            instelling_id=inst["id"],
            opleiding=pad.stem[:100],
            crebo=meta["crebo"],
            cohort=meta["cohort"],
            leerweg=meta["leerweg"],
            bestandspad=str(pad),
        )
    else:
        oer_id = oer["id"]
        if str(pad) == oer["bestandspad"] and oer["geindexeerd"] and not reset:
            log.info("'%s' al geïndexeerd — overgeslagen.", pad.name)
            return None
        # PDF heeft prioriteit boven MD; update als pad afwijkt.
        stored_suffix = Path(oer["bestandspad"]).suffix.lower()
        incoming_suffix = pad.suffix.lower()
        if (incoming_suffix == ".pdf" or stored_suffix not in {".pdf"}) and str(
            pad
        ) != oer["bestandspad"]:
            log.info("Bestandspad bijgewerkt naar '%s'.", pad.name)
            update_oer_bestandspad(conn, oer_id, str(pad))

    return oer_id, meta


def _verwerk_bestand(
    pad: Path,
    instelling_naam: str,
    conn: sqlite3.Connection,
    *,
    reset: bool = False,
) -> None:
    """Verwerk één OER-bestand: parse → extraheer tekst en kerntaken → sla op in SQLite."""
    from validatie_samenwijzer.db import markeer_geindexeerd, voeg_kerntaak_toe

    result = _resolveer_oer(pad, instelling_naam, conn, reset=reset)
    if result is None:
        return
    oer_id, _meta = result

    log.info("Verwerk '%s' (oer_id=%d)...", pad.name, oer_id)

    if pad.suffix.lower() == ".pdf":
        md_pad = converteer_naar_markdown(pad)
        verwerk_pad = md_pad if md_pad.suffix.lower() == ".md" else pad
    else:
        verwerk_pad = pad

    try:
        tekst = extraheer_tekst(verwerk_pad)
    except Exception as e:
        log.error("Extractie mislukt voor '%s': %s", pad.name, e)
        return

    if not tekst.strip():
        log.warning("'%s' bevat geen extraheerbare tekst — overgeslagen.", pad.name)
        return

    kerntaken = extraheer_kerntaken(tekst)
    for kt in kerntaken:
        voeg_kerntaak_toe(
            conn,
            oer_id=oer_id,
            code=kt["code"],
            naam=kt["naam"],
            type=kt["type"],
            volgorde=kt["volgorde"],
        )

    markeer_geindexeerd(conn, oer_id)
    log.info("'%s' geïndexeerd: %d kerntaken.", pad.name, len(kerntaken))


def _verwerk_instelling(
    naam: str,
    oeren_pad: Path,
    conn: sqlite3.Connection,
    *,
    reset: bool = False,
) -> None:
    """Verwerk alle OER-bestanden in de map van de opgegeven instelling."""
    map_naam = _MAP_NAAM.get(naam, naam)
    pad = oeren_pad / map_naam
    if not pad.exists():
        log.warning("Map '%s' niet gevonden.", pad)
        return
    for bestand in pad.iterdir():
        if bestand.suffix.lower() in _ONDERSTEUNDE_EXTENSIES:
            _verwerk_bestand(bestand, naam, conn, reset=reset)


def main() -> None:
    """CLI-entrypoint voor de OER-ingestie pipeline (--instelling, --bestand, --alles)."""
    import argparse

    from dotenv import load_dotenv

    from validatie_samenwijzer.db import get_connection, init_db, voeg_instelling_toe

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="OER-ingestie pipeline")
    parser.add_argument("--instelling", help="Verwerk alle OER's van deze instelling")
    parser.add_argument("--bestand", help="Verwerk één specifiek bestand")
    parser.add_argument("--alles", action="store_true", help="Verwerk alle instellingen")
    parser.add_argument(
        "--reset", action="store_true", help="Herindexeer ook al-geïndexeerde OER's"
    )
    args = parser.parse_args()

    db_path = Path(os.environ.get("DB_PATH", "data/validatie.db"))
    oeren_pad = Path(os.environ.get("OEREN_PAD", "oeren"))

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(db_path)
    init_db(conn)

    for naam, display in _INSTELLINGEN.items():
        voeg_instelling_toe(conn, naam, display)

    if args.bestand:
        pad = Path(args.bestand)
        inst = pad.parent.name.replace("_oeren", "").replace("_oer", "")
        _verwerk_bestand(pad, inst, conn, reset=args.reset)
    elif args.instelling:
        _verwerk_instelling(args.instelling, oeren_pad, conn, reset=args.reset)
    elif args.alles:
        for naam in _INSTELLINGEN:
            _verwerk_instelling(naam, oeren_pad, conn, reset=args.reset)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
