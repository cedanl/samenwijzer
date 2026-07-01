"""Download ROC Nijmegen-OER's uit het publieke ``/downloads``-documentsysteem.

ROC Nijmegen (Joomla, component ``com_rocnijmegen``) publiceert **geen** OER-links op de
opleidingspagina's zelf — noch in de statische HTML, noch via de template-JS. De OER-grade
documenten leven uitsluitend in de download-boom onder
``/downloads/bpv/bpv-werkveld/<opleiding>/.../examinering*/`` en zijn bereikbaar als
publieke PDF's op ``/downloads/<categoriepad>/<id>-<slug>/file``. Alleen de cluster
Zorg & Welzijn publiceert deze; de overige ~225 opleidingen hebben geen publieke OER.

De crawl loopt in drie stappen:

1. **Boom in kaart** — recursief ``/downloads`` aflopen (server-gerenderde HTML): elke
   categoriepagina bevat subcategorie-links (``/downloads/a/b``) en bestand-links
   (``/downloads/a/b/<id>-<slug>/file``).
2. **OER-grade filteren** — bestand-slugs die ``oer-``/``examenplan``/``leerplan``/
   ``studiegids`` bevatten (dit weert losse werkproces-examenfragmenten zoals
   ``b1-k3-w1-mei2021`` die wél een kerntaakcode dragen maar geen OER zijn).
3. **Ophalen + valideren** — elke PDF downloaden, tekst met ``pdfplumber`` extraheren,
   kerntaakcodes normaliseren en met ``ingest.extraheer_kerntaken`` controleren.

**Kerntaak-normalisatie** (analoog aan ``fetch_landstede._normaliseer_kerntaken``):
Nijmegen prefixt kerntaakcodes op drie manieren die de ``^``-verankerde ingest-regex
breken — het woord ``Kerntaak``/``Werkproces`` (``Kerntaak B1-K1: …``), een 5-cijferige
crebo (``25656-B1-K1-W1 …``) of een 2-4-letter-opleidingsafkorting (``MZ-``/``VP-B1-K1-W1``).
``_normaliseer_kerntaken`` tilt de code naar regelstart zodat de ingest-/parser-regex
(ongemoeid) de codes herkent.

**Crebo = uitstroomcode**, uitsluitend uit het document zelf afgeleid (nooit extern
geraden): (1) de code-prefix in de werkprocescode (``25656-B1-K1-W1``), (2) een crebo-context
in de tekst/bestandsnaam, anders (3) **overslaan + waarschuwen** (zoals fetch_landstede:
"uitstroomcode niet eenduidig → niet gokken"). Zonder crebo koppelt de seed stil de
verkeerde KD-/skills-bundel.

Naast de opleidings-OER's haalt het script de **instellingsbrede regelingen** op uit
``/downloads/rechten-en-plichten/`` en schrijft ze als ``_instelling/<soort>.pdf`` volgens
``db.INSTELLING_SOORTEN``.

Opslag als ``.pdf`` (bron) + genormaliseerde ``.md`` (pdfplumber-tekst) onder
``oeren/nijmegen_oeren/`` (zoals de overige PDF-instellingen aeres/curio). ``OEREN_PAD``
overschrijft de oeren-tree.

Gebruik (vanuit ``validatie_samenwijzer/``):

    uv run python scripts/fetch_nijmegen.py                    # download + schrijf
    uv run python scripts/fetch_nijmegen.py --preview          # droge run, schrijf niets
    uv run python scripts/fetch_nijmegen.py --preview --limit 5
    OEREN_PAD=../oeren uv run python scripts/fetch_nijmegen.py
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote

import httpx
import pdfplumber

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]

BASE = "https://www.roc-nijmegen.nl"
DOWNLOADS = "/downloads"

_HEADERS = {
    "accept": "text/html,application/xhtml+xml",
    "user-agent": "Mozilla/5.0 (samenwijzer OER-ingestie)",
}
_WORKERS = 4  # bewust bescheiden — beleefd crawlen
_TIMEOUT = 60.0
_RETRIES = 4
_MAX_CRAWL_DEPTH = 7

# ── Link-patronen op de category-HTML ────────────────────────────────────────
_FILE_RE = re.compile(r'href="(/downloads/[a-z0-9/-]+/\d+-[a-z0-9-]+/file)"')
_SUBCAT_RE = re.compile(r'href="(/downloads/[a-z0-9/-]+)"')
# OER-grade slug-keywords (weert losse examen-werkprocesfragmenten).
_OER_SLUG_RE = re.compile(r"/\d+-[a-z0-9-]*(oer-|examenplan|leerplan|studiegids)", re.I)

# ── Inhoud-patronen ──────────────────────────────────────────────────────────
# Til Kerntaak-/Werkproces-codes naar regelstart (zie module-docstring).
_KT_PREFIX_RE = re.compile(
    r"^\s*(?:Kerntaak|Werkproces|(?:[A-Z]{2,4}|\d{5})-)\s*(B\d+-K\d+(?:-W\d+)?\b.*)$"
)
# Crebo primair uit de werkprocescode (25656-B1-K1-W1), autoritatief.
_CREBO_CODE_RE = re.compile(r"(?<!\d)(\d{5})-B\d+-K\d+")
# Crebo-context in tekst of bestandsnaam (bv. "crebo 254780").
_CREBO_CTX_RE = re.compile(r"(?:crebo(?:code)?|kwalificatie(?:code|dossier)?)\W{0,15}(\d{5})", re.I)
_LEERWEG_RE = re.compile(r"(?<![a-z])(bol|bbl)(?![a-z])", re.I)
# Cohortjaar uit bestandsnaam/slug (2023-2024, cohort-2022, 2023-2026 → startjaar).
_COHORT_RE = re.compile(r"(20[2-3]\d)")

# ── Instellingsbrede regelingen (→ db.INSTELLING_SOORTEN) ─────────────────────
_REG = "/downloads/rechten-en-plichten"
_INSTELLING_REGELINGEN = {
    "studentenstatuut": f"{_REG}/973-studentenstatuut-vanaf-1-augustus-2025/file",
    "examenreglement": f"{_REG}/7-examenreglement-roc-nijmegen/file",
    "klachtenregeling": f"{_REG}/439-reglement-klachten-en-geschillen-voor-studenten/file",
    "bindend_studieadvies": f"{_REG}/440-bindend-studieadvies/file",
    "gedragscode": f"{_REG}/8-gedragscode/file",
}


def _nijmegen_dir() -> Path:
    """Doelmap ``<oeren>/nijmegen_oeren``; ``OEREN_PAD`` overschrijft de oeren-tree."""
    base = os.environ.get("OEREN_PAD")
    oeren = Path(base).resolve() if base else ROOT / "oeren"
    return oeren / "nijmegen_oeren"


def _slug(naam: str) -> str:
    """Leesbare ascii-stem uit de (echte) bestandsnaam; extensie + crebo's weren."""
    naam = re.sub(r"\.(pdf|md|txt|docx?)$", "", naam, flags=re.I)
    naam = unicodedata.normalize("NFKD", naam).encode("ascii", "ignore").decode()
    naam = re.sub(r"\d{5,6}", "", naam)  # losse crebo's (5-6 cijfers) uit de naam weren
    naam = re.sub(r"[^A-Za-z0-9]+", "_", naam).strip("_")
    return naam[:80] or "OER"


def _normaliseer_kerntaken(tekst: str) -> str:
    """Til kerntaak-/werkproces-codes naar regelstart zodat ``extraheer_kerntaken``
    ze herkent (Nijmegen prefixt met ``Kerntaak``/``Werkproces``, een crebo of een
    opleidingsafkorting — zie module-docstring)."""
    return "\n".join(
        (m.group(1) if (m := _KT_PREFIX_RE.match(regel)) else regel) for regel in tekst.splitlines()
    )


def _get(client: httpx.Client, url: str) -> str:
    """GET (tekst) met retry/backoff."""
    for poging in range(_RETRIES):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as exc:
            log.debug("GET %s mislukt (poging %d/%d): %s", url, poging + 1, _RETRIES, exc)
            if poging < _RETRIES - 1:
                time.sleep(1.5 * (poging + 1))
    log.warning("GET definitief mislukt na %d pogingen: %s", _RETRIES, url)
    return ""


def _get_response(client: httpx.Client, url: str) -> httpx.Response | None:
    """GET (bytes+headers) met retry/backoff — voor de PDF-download."""
    for poging in range(_RETRIES):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp
        except httpx.HTTPError as exc:
            log.debug("GET %s mislukt (poging %d/%d): %s", url, poging + 1, _RETRIES, exc)
            if poging < _RETRIES - 1:
                time.sleep(1.5 * (poging + 1))
    log.warning("GET definitief mislukt na %d pogingen: %s", _RETRIES, url)
    return None


def verzamel_bestand_urls(client: httpx.Client) -> list[str]:
    """Loop de ``/downloads``-boom recursief af; verzamel alle bestand-URL's (``/file``)."""
    seen: set[str] = set()
    files: set[str] = set()
    frontier = [DOWNLOADS]
    while frontier:

        def _crawl(pad: str) -> list[str]:
            if pad in seen or pad.count("/") - 1 > _MAX_CRAWL_DEPTH:
                return []
            seen.add(pad)
            html = _get(client, BASE + pad)
            if not html:
                return []
            files.update(_FILE_RE.findall(html))
            # Subcategorieën: alle /downloads-links behalve bestand-links (``…/file``) —
            # _SUBCAT_RE matcht die anders óók en dan zou de crawl elke PDF ophalen.
            subs = {
                p
                for p in _SUBCAT_RE.findall(html)
                if p.startswith("/downloads")
                and not p.endswith("/file")
                and p != pad
                and p not in seen
            }
            return list(subs)

        with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
            resultaten = list(pool.map(_crawl, frontier))
        nieuw: set[str] = set()
        for lijst in resultaten:
            nieuw.update(lijst)
        frontier = [p for p in nieuw if p not in seen]
        log.info("Crawl: %d categorieën bezocht, %d bestanden gevonden.", len(seen), len(files))
    return sorted(files)


def _bepaal_bestandsnaam(resp: httpx.Response, fallback: str) -> str:
    """Echte bestandsnaam uit de Content-Disposition (RFC 5987 ``filename*``)."""
    disp = resp.headers.get("content-disposition", "")
    m = re.search(r"filename\*=UTF-8''([^;]+)", disp) or re.search(r'filename="?([^";]+)', disp)
    if m:
        return unquote(m.group(1)).strip()
    return fallback


def _bepaal_crebo(tekst: str, bestandsnaam: str, slug: str) -> str | None:
    """Uitstroom-crebo uit het document zelf; None → overslaan (niet gokken)."""
    m = _CREBO_CODE_RE.search(tekst)
    if m:
        return m.group(1)
    for bron in (tekst, bestandsnaam, slug):
        m = _CREBO_CTX_RE.search(bron)
        if m:
            return m.group(1)
    return None


def _bepaal_leerweg(bestandsnaam: str, url: str) -> str:
    """Leerweg uit de bestandsnaam (BOL/BBL-token) of het download-pad; default BOL."""
    for bron in (bestandsnaam, url):
        m = _LEERWEG_RE.search(bron)
        if m:
            return m.group(1).upper()
    return "BOL"


def _bepaal_cohort(bestandsnaam: str, slug: str) -> str:
    """Startjaar (cohort) uit de bestandsnaam/slug; default 2025."""
    m = _COHORT_RE.search(bestandsnaam) or _COHORT_RE.search(slug)
    return m.group(1) if m else "2025"


def _verwerk_bestand(client: httpx.Client, url: str, extraheer_kerntaken) -> dict | None:
    """Download + parse één OER-kandidaat naar een record (of None bij falen)."""
    resp = _get_response(client, BASE + url)
    if resp is None:
        return None
    slug = url.rsplit("/", 2)[-2]  # <id>-<slug>
    naam = _bepaal_bestandsnaam(resp, slug)
    try:
        with pdfplumber.open(BytesIO(resp.content)) as pdf:
            ruw = "\n".join((pagina.extract_text() or "") for pagina in pdf.pages)
    except Exception as exc:  # pragma: no cover - defensief tegen corrupte PDF's
        log.warning("pdfplumber faalde voor %s: %s", naam, exc)
        return None
    tekst = _normaliseer_kerntaken(ruw)
    kerntaken = len(extraheer_kerntaken(tekst))
    # Crebo uit de RUWE tekst: de code-prefix (25656-B1-K1-W1) staat vaak op regelstart
    # en wordt dán door _normaliseer_kerntaken weggehaald — dus vóór normalisatie zoeken.
    crebo = _bepaal_crebo(ruw, naam, slug)
    return {
        "url": url,
        "naam": naam,
        "pdf": resp.content,
        "tekst": tekst,
        "crebo": crebo,
        "leerweg": _bepaal_leerweg(naam, url),
        "cohort": _bepaal_cohort(naam, slug),
        "kerntaken": kerntaken,
    }


def _download_regelingen(client: httpx.Client, doelmap: Path, preview: bool) -> int:
    """Haal de instellingsbrede regelingen op naar ``_instelling/<soort>.pdf`` + ``.md``."""
    inst = doelmap / "_instelling"
    geschreven = 0
    for soort, pad in _INSTELLING_REGELINGEN.items():
        resp = _get_response(client, BASE + pad)
        if resp is None:
            continue
        try:
            with pdfplumber.open(BytesIO(resp.content)) as pdf:
                tekst = "\n".join((p.extract_text() or "") for p in pdf.pages)
        except Exception as exc:  # pragma: no cover
            log.warning("pdfplumber faalde voor regeling %s: %s", soort, exc)
            continue
        log.info("  regeling %s (%d bytes, %d tekens tekst)", soort, len(resp.content), len(tekst))
        if preview:
            continue
        inst.mkdir(parents=True, exist_ok=True)
        (inst / f"{soort}.pdf").write_bytes(resp.content)
        (inst / f"{soort}.md").write_text(tekst, encoding="utf-8")
        geschreven += 1
    return geschreven


def main() -> None:
    parser = argparse.ArgumentParser(description="Download ROC Nijmegen-OER's uit /downloads")
    parser.add_argument("--preview", action="store_true", help="Droge run; schrijf geen bestanden")
    parser.add_argument("--limit", type=int, help="Verwerk max N OER-kandidaten (test)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # per-request GET-ruis dempen

    # extraheer_kerntaken stuurt de make-or-break-controle én de dedup-score; dezelfde
    # regex die ingest later op de .md draait.
    from validatie_samenwijzer.ingest import extraheer_kerntaken

    limits = httpx.Limits(max_connections=_WORKERS, max_keepalive_connections=_WORKERS)
    with httpx.Client(
        headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True, limits=limits
    ) as client:
        alle_files = verzamel_bestand_urls(client)
        kandidaten = [u for u in alle_files if _OER_SLUG_RE.search(u)]
        if args.limit:
            kandidaten = kandidaten[: args.limit]
        log.info(
            "%d bestanden in /downloads; %d OER-grade kandidaten (oer/examenplan/leerplan)",
            len(alle_files),
            len(kandidaten),
        )

        with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
            records = [
                r
                for r in pool.map(
                    lambda u: _verwerk_bestand(client, u, extraheer_kerntaken), kandidaten
                )
                if r is not None
            ]

        # Instellingsbrede regelingen.
        log.info("Instellingsbrede regelingen:")
        doelmap = _nijmegen_dir()
        n_reg = _download_regelingen(client, doelmap, args.preview)

    # Filter: make-or-break (kerntaken>0) én bepaalbare crebo (anders stil verkeerde bundel).
    zonder_kerntaken = [r for r in records if r["kerntaken"] == 0]
    zonder_crebo = [r for r in records if r["kerntaken"] > 0 and not r["crebo"]]
    bruikbaar = [r for r in records if r["kerntaken"] > 0 and r["crebo"]]
    for r in zonder_kerntaken:
        log.warning("Overgeslagen (geen kerntaken): %s", r["naam"])
    for r in zonder_crebo:
        log.warning("Overgeslagen (crebo onbepaalbaar, niet geraden): %s", r["naam"])

    # Dedup op (crebo, leerweg): make-or-break, dan nieuwste cohort, dan langste tekst.
    def _score(r: dict) -> tuple[bool, int, int]:
        return (r["kerntaken"] > 0, int(r["cohort"]), len(r["tekst"]))

    beste: dict[tuple[str, str], dict] = {}
    for r in bruikbaar:
        sleutel = (r["crebo"], r["leerweg"])
        if sleutel not in beste or _score(r) > _score(beste[sleutel]):
            beste[sleutel] = r

    crebos = {r["crebo"] for r in beste.values()}
    log.info(
        "%d OER-bestanden over %d unieke crebo's na dedup "
        "(%d zonder kerntaken, %d zonder crebo overgeslagen).",
        len(beste),
        len(crebos),
        len(zonder_kerntaken),
        len(zonder_crebo),
    )

    for (crebo, leerweg), r in sorted(beste.items()):
        stem = f"{crebo}_{leerweg}_{r['cohort']}__{_slug(r['naam'])}"
        log.info(
            "  %s.pdf/.md — %s (%d tekens, %d kerntaken)",
            stem,
            r["naam"],
            len(r["tekst"]),
            r["kerntaken"],
        )

    if args.preview:
        log.info(
            "Preview — %d OER-bestanden + %d regelingen niet weggeschreven.",
            len(beste),
            len(_INSTELLING_REGELINGEN),
        )
        return

    doelmap.mkdir(parents=True, exist_ok=True)
    for (crebo, leerweg), r in beste.items():
        stem = f"{crebo}_{leerweg}_{r['cohort']}__{_slug(r['naam'])}"
        (doelmap / f"{stem}.pdf").write_bytes(r["pdf"])
        (doelmap / f"{stem}.md").write_text(r["tekst"], encoding="utf-8")
    log.info(
        "%d OER-bestanden + %d instellingsregelingen geschreven naar %s.",
        len(beste),
        n_reg,
        doelmap,
    )


if __name__ == "__main__":
    main()
