"""OER-ingestie pipeline: parse → extraheer → chunk → embed → sla op."""

import re
from pathlib import Path

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


# ── Tekst chunken ─────────────────────────────────────────────────────────────

def chunk_tekst(tekst: str, chunk_grootte: int = 500, overlap: int = 50) -> list[str]:
    """Splits tekst in chunks van ~chunk_grootte woorden met overlap."""
    woorden = tekst.split()
    if len(woorden) <= chunk_grootte:
        return [tekst]

    chunks = []
    start = 0
    while start < len(woorden):
        einde = min(start + chunk_grootte, len(woorden))
        chunk = " ".join(woorden[start:einde])
        chunks.append(chunk)
        if einde >= len(woorden):
            break
        start += chunk_grootte - overlap
    return chunks


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
    import logging

    import pdfplumber

    logger = logging.getLogger(__name__)
    tekst_delen = []
    with pdfplumber.open(str(pad)) as pdf:
        for pagina in pdf.pages:
            t = pagina.extract_text()
            if t:
                tekst_delen.append(t)
    tekst = "\n\n".join(tekst_delen)

    if len(tekst.strip()) < _OCR_DREMPEL:
        logger.info("pdfplumber leverde te weinig tekst voor '%s', val terug op OCR.", pad.name)
        tekst = _extraheer_tekst_ocr(pad)

    return tekst


def extraheer_tekst_html(pad: Path) -> str:
    from bs4 import BeautifulSoup
    html = pad.read_text(encoding="utf-8", errors="replace")
    soep = BeautifulSoup(html, "html.parser")
    for tag in soep(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soep.get_text(separator="\n", strip=True)


def extraheer_tekst_md(pad: Path) -> str:
    return pad.read_text(encoding="utf-8", errors="replace")


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

def _verwerk_bestand(pad: Path, instelling_naam: str, conn, collection,
                     openai_client, *, reset: bool = False) -> None:
    """Verwerk één OER-bestand: parse → extraheer → chunk → embed → sla op."""
    import logging
    logger = logging.getLogger(__name__)

    meta = parseer_bestandsnaam(pad.name)
    if meta is None:
        logger.warning("Kan crebo/leerweg/cohort niet parsen uit '%s' — overgeslagen.", pad.name)
        return

    from validatie_samenwijzer.db import (
        get_instelling_by_naam,
        get_oer_document,
        markeer_geindexeerd,
        voeg_kerntaak_toe,
        voeg_oer_document_toe,
    )
    from validatie_samenwijzer.vector_store import voeg_chunks_toe

    inst = get_instelling_by_naam(conn, instelling_naam)
    if inst is None:
        logger.error("Instelling '%s' niet gevonden in database.", instelling_naam)
        return

    oer = get_oer_document(conn, meta["crebo"], meta["cohort"], meta["leerweg"])
    if oer is None:
        oer_id = voeg_oer_document_toe(
            conn, instelling_id=inst["id"],
            opleiding=pad.stem[:100],
            crebo=meta["crebo"], cohort=meta["cohort"], leerweg=meta["leerweg"],
            bestandspad=str(pad),
        )
    else:
        oer_id = oer["id"]
        if oer["geindexeerd"] and not reset:
            logger.info("'%s' al geïndexeerd — overgeslagen.", pad.name)
            return

    logger.info("Verwerk '%s' (oer_id=%d)...", pad.name, oer_id)

    try:
        tekst = extraheer_tekst(pad)
    except Exception as e:
        logger.error("Extractie mislukt voor '%s': %s", pad.name, e)
        return

    kerntaken = extraheer_kerntaken(tekst)
    for kt in kerntaken:
        voeg_kerntaak_toe(conn, oer_id=oer_id, code=kt["code"], naam=kt["naam"],
                          type=kt["type"], volgorde=kt["volgorde"])

    chunks_tekst = [c for c in chunk_tekst(tekst) if c.strip()]
    if not chunks_tekst:
        logger.warning("'%s' bevat geen extraheerbare tekst — overgeslagen.", pad.name)
        return

    embeddings = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=chunks_tekst,
    )

    chunks = [
        {
            "id": f"oer{oer_id}_chunk{i}",
            "tekst": chunk_t,
            "embedding": emb.embedding,
            "metadata": {
                "oer_id": oer_id,
                "instelling": instelling_naam,
                "crebo": meta["crebo"],
                "cohort": meta["cohort"],
                "leerweg": meta["leerweg"],
                "pagina": 0,
            },
        }
        for i, (chunk_t, emb) in enumerate(zip(chunks_tekst, embeddings.data))
    ]
    voeg_chunks_toe(collection, chunks)
    markeer_geindexeerd(conn, oer_id)
    logger.info("'%s' geïndexeerd: %d chunks, %d kerntaken.", pad.name, len(chunks), len(kerntaken))


def main() -> None:
    import argparse
    import logging
    import os

    from dotenv import load_dotenv

    from validatie_samenwijzer._openai import _client as openai_client_factory
    from validatie_samenwijzer.db import get_connection, init_db, voeg_instelling_toe
    from validatie_samenwijzer.vector_store import get_client as chroma_client
    from validatie_samenwijzer.vector_store import get_collection

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
    chroma_path = Path(os.environ.get("CHROMA_PATH", "data/chroma"))
    oeren_pad = Path(os.environ.get("OEREN_PAD", "oeren"))

    db_path.parent.mkdir(parents=True, exist_ok=True)
    chroma_path.mkdir(parents=True, exist_ok=True)

    conn = get_connection(db_path)
    init_db(conn)

    chroma = get_collection(chroma_client(chroma_path))
    oc = openai_client_factory()

    instellingen_map = {
        "aeres": "Aeres MBO",
        "davinci": "Da Vinci College",
        "rijn_ijssel": "Rijn IJssel",
        "talland": "Talland",
        "utrecht": "ROC Utrecht",
    }

    for naam, display in instellingen_map.items():
        voeg_instelling_toe(conn, naam, display)

    def verwerk_instelling(naam: str) -> None:
        map_naam = {
            "aeres": "aeres_oeren", "davinci": "davinci_oeren",
            "rijn_ijssel": "rijn_ijssel_oer", "talland": "talland_oeren",
            "utrecht": "utrecht_oeren",
        }.get(naam, naam)
        pad = oeren_pad / map_naam
        if not pad.exists():
            logging.warning("Map '%s' niet gevonden.", pad)
            return
        for bestand in pad.iterdir():
            if bestand.suffix.lower() in {".pdf", ".html", ".htm", ".md"}:
                _verwerk_bestand(bestand, naam, conn, chroma, oc, reset=args.reset)

    if args.bestand:
        pad = Path(args.bestand)
        inst = pad.parent.name.replace("_oeren", "").replace("_oer", "")
        _verwerk_bestand(pad, inst, conn, chroma, oc, reset=args.reset)
    elif args.instelling:
        verwerk_instelling(args.instelling)
    elif args.alles:
        for naam in instellingen_map:
            verwerk_instelling(naam)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
