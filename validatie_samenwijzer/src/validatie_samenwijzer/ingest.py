"""OER-ingestie pipeline: parse → extraheer → sla op in SQLite."""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import time
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

# ── Opleidingsnaam afleiden ──────────────────────────────────────────────────

# Standaard prefix die rename_oers.py voor de stem zet (`<crebo>_<leerweg>_<cohort>__`)
_PREFIX_PATROON = re.compile(r"^\d{5}_(?:BOL|BBL)_\d{4}__", re.IGNORECASE)
# Examenplannen leggen de profielnaam expliciet vast op de titelpagina
_OPLEIDING_LIJN = re.compile(
    r"^\s*Kwalificatie\s*\(profiel\)\s*[:\-]?\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
# Generieke woorden die niet als opleidingsnaam tellen — alleen op deze
# overhouden geldt de stem als oninformatief.
_GENERIEKE_OPLEIDINGSWOORDEN = {
    "examenplan",
    "examenplannen",
    "oer",
    "addendum",
    "bol",
    "bbl",
    "mbo",
    "roc",
}


def _stem_heeft_opleidingsnaam(stem: str) -> bool:
    """True als de stem na de metadata-prefix ten minste één opleidingswoord bevat."""
    rest = _PREFIX_PATROON.sub("", stem).lower()
    tokens = [w for w in re.split(r"[_\W]+", rest) if w]
    return any(
        len(w) >= 3 and not w.isdigit() and w not in _GENERIEKE_OPLEIDINGSWOORDEN for w in tokens
    )


def _extraheer_opleiding_uit_pdf(pad: Path) -> str | None:
    """Lees de eerste pagina en haal de profiel-kwalificatienaam op.

    Werkt voor het ROC Utrecht 'Examenplan' formaat dat een vaste key/value-tabel
    op de eerste pagina heeft. Geeft None als de PDF niet leesbaar is of het
    patroon niet matcht.
    """
    if pad.suffix.lower() != ".pdf":
        return None
    try:
        import pdfplumber

        with pdfplumber.open(str(pad)) as pdf:
            tekst = pdf.pages[0].extract_text() or ""
    except Exception as e:
        log.debug("Kan eerste pagina niet lezen voor '%s': %s", pad.name, e)
        return None
    m = _OPLEIDING_LIJN.search(tekst)
    if m:
        return m.group(1).strip()[:100]
    return None


def _pad_relatief_aan_oeren_root(pad: Path) -> str:
    """Normaliseer naar `oeren/<map>/<bestand>` voor opslag in de DB.

    OEREN_PAD wijst vanuit dit subproject naar `../oeren`; zonder normalisatie
    krijgt de DB `../oeren/...`-paden, en `resolve_oer_pad()` rekent dan een
    map te ver naar boven (`samenwijzer/..` → `projects/`).
    """
    parts = pad.parts
    for i, part in enumerate(parts):
        if part == "oeren":
            return str(Path(*parts[i:]))
    return str(pad)


def _bepaal_opleiding(pad: Path) -> str:
    """Geef de beste opleidingsnaam voor een OER-bestand.

    Default is de bestandsnaam zonder extensie. Wanneer die geen
    opleidingswoord bevat (bv. `25698_BOL_2026__Examenplan - 25698`),
    valt het terug op de profielnaam uit de PDF-titelpagina.
    """
    stem = pad.stem[:100]
    if _stem_heeft_opleidingsnaam(stem):
        return stem
    pdf_naam = _extraheer_opleiding_uit_pdf(pad)
    return pdf_naam or stem


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
    """Haal kerntaken en werkprocessen uit OER-tekst via regex.

    Filtert garbled fragments (geen complete zin) en dedupliceert binnen
    één document — dezelfde kerntaak komt vaak meerdere keren in een OER
    voor (introductie + tabel + uitwerking).
    """
    if not tekst:
        return []

    seen: set[tuple[str, str, str]] = set()
    resultaten = []
    volgorde = 0

    for m in _KT_PATROON.finditer(tekst):
        code = m.group(1).strip()
        naam = m.group(2).strip()[:200]

        # Filter garbled fragments uit afgevlakte tabellen: een echte beschrijving
        # heeft minstens 12 letters en bevat lowercase tekst (niet alleen codes
        # of cijfers zoals "1", "W2", "TE").
        if sum(1 for c in naam if c.isalpha()) < 12:
            continue
        if not any(c.islower() for c in naam):
            continue

        type_ = (
            "werkproces"
            if "werkproces" in code.lower() or re.match(r"B\d+-K\d+-W\d+", code)
            else "kerntaak"
        )

        sleutel = (type_, code, naam)
        if sleutel in seen:
            continue
        seen.add(sleutel)

        resultaten.append({"code": code, "naam": naam, "type": type_, "volgorde": volgorde})
        volgorde += 1

    return resultaten


# Inhoudsopgaveregels in een KD dragen trailing dotted leaders + paginanummer,
# bv. "Voert preventieve werkzaamheden uit  ...........  6".
_KD_LEADER_PATROON = re.compile(r"\s*\.{2,}\s*\d*\s*$")


def _schoon_kd_naam(naam: str) -> str:
    """Verwijder trailing dotted leaders en paginanummer uit een KD-inhoudsopgaveregel."""
    return _KD_LEADER_PATROON.sub("", naam).strip()


def _kerntaken_uit_kd(tekst: str) -> list[dict]:
    """Kerntaken/werkprocessen uit een kwalificatiedossier-markdown.

    Hergebruikt de OER-extractor maar schoont KD-specifieke dotted leaders uit de
    namen en dedupt per (type, code) — de inhoudsopgave noemt elke code één keer
    schoon, de body herhaalt hem soms gewrapt of met trailing prose. Het eerste
    voorkomen wint: de inhoudsopgave staat vóór de body, dus dat is de schone vorm.
    """
    beste: dict[tuple[str, str], dict] = {}
    for kt in extraheer_kerntaken(tekst):
        sleutel = (kt["type"], kt["code"])
        if sleutel not in beste:
            beste[sleutel] = {**kt, "naam": _schoon_kd_naam(kt["naam"])}

    resultaat = sorted(beste.values(), key=lambda k: k["volgorde"])
    for i, kt in enumerate(resultaat):
        kt["volgorde"] = i
    return resultaat


def _pad_kwalificatiedossier(crebo: str | None) -> Path | None:
    """Pad naar <crebo>.md van het kwalificatiedossier, of None als de crebo leeg is
    of het bestand ontbreekt.

    Spiegelt ``chat.pad_kwalificatiedossier`` bewust zonder import: chat.py trekt
    ``anthropic`` binnen en hoort niet in de ingest-pijplijn. Default-pad
    ``<repo-root>/kwalificatiedossiers/pdfs``; override via ``KWALDOSSIERS_PAD``.
    """
    if not crebo:
        return None
    base = os.environ.get("KWALDOSSIERS_PAD")
    if base:
        directory = Path(base).resolve()
    else:
        directory = Path(__file__).resolve().parents[3] / "kwalificatiedossiers" / "pdfs"
    pad = directory / f"{crebo}.md"
    return pad if pad.exists() else None


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
    "curio": "Curio",
    "davinci": "Da Vinci College",
    "kwic": "Koning Willem I College",
    "rijn_ijssel": "Rijn IJssel",
    "talland": "Talland",
    "utrecht": "ROC Utrecht",
}

_MAP_NAAM = {
    "aeres": "aeres_oeren",
    "curio": "curio_oeren",
    "davinci": "davinci_oeren",
    "kwic": "kwic_oeren",
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
        update_oer_opleiding,
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

    opleiding = _bepaal_opleiding(pad)
    bestandspad_db = _pad_relatief_aan_oeren_root(pad)

    oer = get_oer_document(conn, inst["id"], meta["crebo"], meta["cohort"], meta["leerweg"])
    if oer is None:
        oer_id = voeg_oer_document_toe(
            conn,
            instelling_id=inst["id"],
            opleiding=opleiding,
            crebo=meta["crebo"],
            cohort=meta["cohort"],
            leerweg=meta["leerweg"],
            bestandspad=bestandspad_db,
        )
    else:
        oer_id = oer["id"]
        if bestandspad_db == oer["bestandspad"] and oer["geindexeerd"] and not reset:
            log.info("'%s' al geïndexeerd — overgeslagen.", pad.name)
            return None
        # PDF heeft prioriteit boven MD; update als pad afwijkt.
        stored_suffix = Path(oer["bestandspad"]).suffix.lower()
        incoming_suffix = pad.suffix.lower()
        if (incoming_suffix == ".pdf" or stored_suffix not in {".pdf"}) and (
            bestandspad_db != oer["bestandspad"]
        ):
            log.info("Bestandspad bijgewerkt naar '%s'.", pad.name)
            update_oer_bestandspad(conn, oer_id, bestandspad_db)
        # Werk de opleidingsnaam bij als de nieuwe variant informatiever is
        # dan wat eerder is opgeslagen (bv. PDF-titelpagina vs. generieke
        # filename als "Examenplan - 25698").
        if (
            opleiding != oer["opleiding"]
            and _stem_heeft_opleidingsnaam(opleiding)
            and not (_stem_heeft_opleidingsnaam(oer["opleiding"]))
        ):
            log.info("Opleiding bijgewerkt: '%s' → '%s'.", oer["opleiding"], opleiding)
            update_oer_opleiding(conn, oer_id, opleiding)

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
    oer_id, meta = result

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
    if not kerntaken:
        kd_pad = _pad_kwalificatiedossier(meta["crebo"])
        if kd_pad is not None:
            try:
                kd_tekst = kd_pad.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                log.warning("Kan KD niet lezen voor '%s': %s", pad.name, e)
                kd_tekst = ""
            kerntaken = _kerntaken_uit_kd(kd_tekst)
            if kerntaken:
                log.info(
                    "Geen kerntaken in OER '%s'; %d kerntaken uit KD %s gehaald.",
                    pad.name,
                    len(kerntaken),
                    meta["crebo"],
                )
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


# Instellingsbrede documenten (niet crebo-gebonden): één submap per instelling,
# bestandsnaam-stem == soort (zie db.INSTELLING_SOORTEN). Bewust een aparte submap zodat
# de platte iterdir in _verwerk_instelling deze bestanden niet als OER oppikt.
_INSTELLING_SUBMAP = "_instelling"


def _verwerk_instelling_documenten(
    naam: str,
    oeren_pad: Path,
    conn: sqlite3.Connection,
    *,
    reset: bool = False,
) -> None:
    """Indexeer instellingsbrede documenten (examenreglement, beleid, statuut, …).

    Verwacht ze in `<map>/_instelling/<soort>.<ext>` met de bestandsnaam-stem als soort
    (geldige soorten: db.INSTELLING_SOORTEN). Crebo-loos: alleen markdown-conversie +
    registratie in `instelling_documenten`, geen kerntaken-extractie. Onbekende stems
    worden overgeslagen.
    """
    from validatie_samenwijzer.db import (
        INSTELLING_SOORTEN,
        get_instelling_by_naam,
        markeer_instelling_document_geindexeerd,
        voeg_instelling_document_toe,
    )

    map_naam = _MAP_NAAM.get(naam, naam)
    pad = oeren_pad / map_naam / _INSTELLING_SUBMAP
    if not pad.exists():
        return
    inst = get_instelling_by_naam(conn, naam)
    if inst is None:
        log.error("Instelling '%s' niet gevonden in database.", naam)
        return
    for bestand in sorted(pad.iterdir()):
        soort = bestand.stem.lower()
        ondersteund = bestand.suffix.lower() in _ONDERSTEUNDE_EXTENSIES
        if soort not in INSTELLING_SOORTEN or not ondersteund:
            continue
        if reset and bestand.suffix.lower() == ".pdf":
            md_pad = bestand.with_suffix(".md")
            if md_pad.exists():
                md_pad.unlink()
        converteer_naar_markdown(bestand)
        titel = f"{INSTELLING_SOORTEN[soort]} {inst['display_naam']}"
        doc_id = voeg_instelling_document_toe(
            conn,
            instelling_id=inst["id"],
            soort=soort,
            titel=titel,
            bestandspad=_pad_relatief_aan_oeren_root(bestand),
        )
        markeer_instelling_document_geindexeerd(conn, doc_id)
        log.info("Instellingsbron '%s' geïndexeerd voor %s.", soort, inst["display_naam"])


def main() -> None:
    """CLI-entrypoint voor de OER-ingestie pipeline (--instelling, --bestand, --alles)."""
    import argparse

    from dotenv import load_dotenv

    from validatie_samenwijzer.db import (
        get_connection,
        init_db,
        voeg_ingest_run_toe,
        voeg_instelling_toe,
    )

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

    start = time.monotonic()
    scope: str | None = None
    if args.bestand:
        pad = Path(args.bestand)
        inst = pad.parent.name.replace("_oeren", "").replace("_oer", "")
        _verwerk_bestand(pad, inst, conn, reset=args.reset)
        scope = f"bestand:{pad.name}"
    elif args.instelling:
        _verwerk_instelling(args.instelling, oeren_pad, conn, reset=args.reset)
        _verwerk_instelling_documenten(args.instelling, oeren_pad, conn, reset=args.reset)
        scope = f"instelling:{args.instelling}"
    elif args.alles:
        for naam in _INSTELLINGEN:
            _verwerk_instelling(naam, oeren_pad, conn, reset=args.reset)
            _verwerk_instelling_documenten(naam, oeren_pad, conn, reset=args.reset)
        scope = "alles"
    else:
        parser.print_help()

    if scope is not None:
        n_oers = conn.execute(
            "SELECT COUNT(*) FROM oer_documenten WHERE geindexeerd = 1"
        ).fetchone()[0]
        n_kerntaken = conn.execute("SELECT COUNT(*) FROM kerntaken").fetchone()[0]
        voeg_ingest_run_toe(
            conn,
            scope=scope,
            n_oers=n_oers,
            n_kerntaken=n_kerntaken,
            duur_seconden=time.monotonic() - start,
        )


if __name__ == "__main__":
    main()
