"""OER-catalogus-check: zijn er nieuwe OER's/cohorten bij een instelling die wij
nog niet hebben? Tuple-diff (crebo, leerweg, cohort) tegen oer_documenten.

Netwerk-isolatie: de pure functies (`nieuwe_oers`, `_tupels_uit_rows`,
`_items_naar_catalogus`) zijn deterministisch en getest; alleen de instelling-
adapters (nu: Deltion) doen een HTTP-call. Gegate achter --oer in het rapport,
zodat het standaard `check-bron-updates` offline/instant blijft.

De Deltion-adapter vraagt met een leeg cohortfilter (alle cohorten), zodat een
gloednieuw cohort (bv. 2026-2027) als 'nieuwe OER' zichtbaar wordt.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from . import db

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (samenwijzer bronactualiteit-check)"

# Standaard-diff-sleutel; instellingen die geen betrouwbare leerweg leveren (bv. Aeres)
# vergelijken op een subset, anders matcht hun tuple nooit de DB (die wél BOL/BBL heeft)
# en lijkt elke OER 'nieuw'.
_STANDAARD_VELDEN = ("crebo", "leerweg", "cohort")
_DIFF_SLEUTEL_VELDEN: dict[str, tuple[str, ...]] = {
    "aeres": ("crebo", "cohort"),
    "rijn_ijssel": ("crebo", "cohort"),
    "utrecht": ("crebo", "cohort"),
}


class CatalogusOnbereikbaarError(Exception):
    """De catalogus van een instelling kon niet worden opgehaald (netwerk/API-fout)."""


@dataclass(frozen=True)
class CatalogusItem:
    crebo: str
    leerweg: str
    cohort: str
    naam: str
    instelling: str
    uuid: str | None = None  # alleen Deltion levert 'm; nodig voor de content-refetch

    @property
    def sleutel(self) -> tuple[str, str, str]:
        return (self.crebo, self.leerweg, self.cohort)


def bereken_content_hash(tekst: str) -> str:
    """Genormaliseerde SHA256-hex van documenttekst, voor upstream-wijzigingsdetectie.

    Whitespace wordt gecollapst (`" ".join(tekst.split())`) zodat onbelangrijke
    verschillen (regeleindes, dubbele spaties) geen valse 'gewijzigd' triggeren. DEZE
    helper is de enige bron van waarheid: ingest (producent) en `gewijzigde_oers`
    (consument) MOETEN beide hierlangs, anders matchen ongewijzigde documenten nooit.
    """
    return hashlib.sha256(" ".join(tekst.split()).encode("utf-8")).hexdigest()


def _projecteer(crebo: str, leerweg: str, cohort: str, velden: tuple[str, ...]) -> tuple[str, ...]:
    """Projecteer een OER op de gekozen diff-velden (subset van crebo/leerweg/cohort)."""
    waarden = {"crebo": crebo, "leerweg": leerweg, "cohort": cohort}
    return tuple(waarden[v] for v in velden)


def nieuwe_oers(
    catalogus: list[CatalogusItem],
    db_tupels: set[tuple[str, ...]],
    velden: tuple[str, ...] = _STANDAARD_VELDEN,
) -> list[CatalogusItem]:
    """Catalogus-items waarvan de sleutel (op `velden`) niet in de DB staat.

    Dedupliceert op dezelfde sleutel: de bron kan dezelfde combinatie onder
    meerdere items teruggeven, anders telt die dubbel mee. `db_tupels` moet met
    dezelfde `velden` geprojecteerd zijn (zie `_tupels_uit_rows`).
    """
    nieuw: list[CatalogusItem] = []
    gezien: set[tuple[str, ...]] = set()
    for item in catalogus:
        sleutel = _projecteer(item.crebo, item.leerweg, item.cohort, velden)
        if sleutel in db_tupels or sleutel in gezien:
            continue
        gezien.add(sleutel)
        nieuw.append(item)
    return nieuw


def _tupels_uit_rows(
    rows, instelling: str, velden: tuple[str, ...] = _STANDAARD_VELDEN
) -> set[tuple[str, ...]]:
    """De op `velden` geprojecteerde set die we al hebben voor één instelling.

    `rows` = `db.get_alle_oers_met_instelling()` (sqlite3.Row of dict met de
    sleutels crebo/leerweg/cohort/naam; `naam` = instelling-key).
    """
    return {
        _projecteer(r["crebo"], r["leerweg"], r["cohort"], velden)
        for r in rows
        if r["naam"] == instelling
    }


def _tupels_uit_manifest(
    instelling: str, velden: tuple[str, ...], pad: Path
) -> set[tuple[str, ...]]:
    """De op `velden` geprojecteerde set uit de gecommitte corpus-manifest."""
    data = json.loads(pad.read_text(encoding="utf-8"))
    return {
        _projecteer(crebo, leerweg, cohort, velden)
        for crebo, leerweg, cohort in data.get(instelling, [])
    }


def _items_naar_catalogus(
    raw_items: list[dict], instelling: str, parse: Callable[[dict], dict | None]
) -> list[CatalogusItem]:
    """Pure transform: ruwe API-items → CatalogusItem via de gegeven parse-functie."""
    uit: list[CatalogusItem] = []
    for raw in raw_items:
        rec = parse(raw)
        if rec:
            uit.append(
                CatalogusItem(
                    rec["crebo"],
                    rec["leerweg"],
                    rec["cohort"],
                    rec["naam"],
                    instelling,
                    rec.get("uuid"),
                )
            )
    return uit


def _fetch_deltion():
    """Importeer het Deltion-script (sibling in scripts/), zoals de tests dat doen."""
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import fetch_deltion

    return fetch_deltion


def deltion_catalogus() -> list[CatalogusItem]:
    """Haal de volledige Deltion-catalogus (alle cohorten) op via de SQill-API."""
    fd = _fetch_deltion()
    with httpx.Client(headers=fd._HEADERS, timeout=30) as client:
        raw = fd.haal_items_op(client, None)  # None = alle cohorten
    return _items_naar_catalogus(raw, "deltion", fd._record)


# Aeres: één statische pagina met per-crebo examenplan-links. Alleen het per-crebo
# cohort (2026-2027 e.v.); oudere cohorten zijn gebundeld-per-domein en worden door
# de regex overgeslagen. Leerweg staat niet in de bron → diff op (crebo, cohort).
_AERES_URL = "https://www.aeresmbo.nl/over-aeres-mbo/regelingen-en-statuten"
_AERES_HREF_RE = re.compile(
    r"/regelingen-en-statuten/(\d{4})-\d{4}/examenplannen/"
    r"examenplan-(\d{5})-([^\"'?]*?)-vastgesteld\.pdf",
    re.IGNORECASE,
)


def _parse_aeres(html: str) -> list[CatalogusItem]:
    """Pure parse: examenplan-hrefs → CatalogusItem (crebo + cohort uit de URL)."""
    items: list[CatalogusItem] = []
    for cohort, crebo, naam in _AERES_HREF_RE.findall(html):
        items.append(CatalogusItem(crebo, "onbekend", cohort, naam.replace("-", " "), "aeres"))
    return items


def aeres_catalogus() -> list[CatalogusItem]:
    """Haal de Aeres-examenplannen (per-crebo cohorten) van de regelingen-pagina."""
    with httpx.Client(headers={"user-agent": _UA}, timeout=30, follow_redirects=True) as client:
        resp = client.get(_AERES_URL)
        resp.raise_for_status()
    return _parse_aeres(resp.text)


# Rijn IJssel: sitemap → ~136 opleidingpagina's (server-side HTML) met
# `apicms.rijnijssel.nl/documents/<id>/<bestand>.pdf`-links. Crebo + cohort komen uit
# de bestandsnaam; ~45% van de bestanden mist een crebo in de naam → die slaan we
# bewust over (de goedkope subset). Diff op (crebo, cohort) — leerweg is inconsistent
# (soms "bolbbl") en niet betrouwbaar uit de naam te halen.
_RIJNIJSSEL_SITEMAP = "https://www.rijnijssel.nl/sitemap-0.xml"
_RIJNIJSSEL_OPLEIDING_RE = re.compile(
    r"<loc>(https://www\.rijnijssel\.nl/mbo-opleidingen/[^<]+)</loc>", re.IGNORECASE
)
_RIJNIJSSEL_DOC_RE = re.compile(
    r"https://apicms\.rijnijssel\.nl/documents/\d+/[^\s\"'<>]+\.pdf", re.IGNORECASE
)
_CREBO_RE = re.compile(r"\d{5}")
_COHORT_RE = re.compile(r"20\d{2}")


def _parse_rijnijssel(html: str) -> list[CatalogusItem]:
    """Pure parse: apicms-doc-links → CatalogusItem (primaire crebo + cohort uit naam).

    Alleen items waarvan zowel crebo als cohort in de bestandsnaam staan; de rest is
    niet goedkoop te bepalen (zou crebo uit de PDF-inhoud vereisen) en wordt overgeslagen.
    """
    items: list[CatalogusItem] = []
    for url in _RIJNIJSSEL_DOC_RE.findall(html):
        naam = url.rsplit("/", 1)[-1]
        crebo = _CREBO_RE.search(naam)
        cohort = _COHORT_RE.search(naam)
        if crebo and cohort:
            items.append(
                CatalogusItem(crebo.group(), "onbekend", cohort.group(), naam, "rijn_ijssel")
            )
    return items


def rijnijssel_catalogus() -> list[CatalogusItem]:
    """Crawl de Rijn IJssel-opleidingpagina's en verzamel de OER-doc-links."""
    items: list[CatalogusItem] = []
    with httpx.Client(headers={"user-agent": _UA}, timeout=30, follow_redirects=True) as client:
        sitemap = client.get(_RIJNIJSSEL_SITEMAP)
        sitemap.raise_for_status()
        for url in _RIJNIJSSEL_OPLEIDING_RE.findall(sitemap.text):
            try:
                resp = client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError:
                continue  # sla een kapotte/trage opleidingpagina over, niet de hele crawl
            items.extend(_parse_rijnijssel(resp.text))
    return items


# MBO Utrecht: practicalinformation-sitemap → academie-pagina's (server-side HTML) met
# WordPress-OER-PDF's `…/wp-content/uploads/<jaar>/<mm>/<jaar>_OER_<leerweg>_<naam>.pdf`.
# De crebo staat NIET in de bestandsnaam → per PDF de inhoud parsen (pagina 1-5). Cohort
# uit de bestandsnaam (het _OER_-jaar, niet de uploadmaand). Diff op (crebo, cohort).
# Hiaat in v1: cohort-2025-OER's op het externe sqill.it-portaal worden nog niet gedekt.
_MBOU_SITEMAP = "https://mboutrecht.nl/practicalinformation-sitemap.xml"
_MBOU_LOC_RE = re.compile(r"<loc>(https://[^<]*mboutrecht\.nl/[^<]+)</loc>", re.IGNORECASE)
_MBOU_PDF_RE = re.compile(
    r"https://(?:www\.)?mboutrecht\.nl/wp-content/uploads/[^\s\"'<>]*_OER_[^\s\"'<>]*\.pdf",
    re.IGNORECASE,
)
_MBOU_COHORT_RE = re.compile(r"/(\d{4})_OER_", re.IGNORECASE)
_MBOU_CREBO_RE = re.compile(r"crebo(?:nr)?[.:]?\s*(\d{5})", re.IGNORECASE)


def _mbou_crebo_uit_tekst(tekst: str) -> str | None:
    """Crebo uit PDF-tekst (`crebo 25655` / `Crebonr. 25998`)."""
    m = _MBOU_CREBO_RE.search(tekst)
    return m.group(1) if m else None


def _mbou_cohort_uit_url(url: str) -> str | None:
    """Cohort = het jaar vóór `_OER_` in de bestandsnaam (niet de uploadmaand)."""
    m = _MBOU_COHORT_RE.search(url)
    return m.group(1) if m else None


def _mbou_pdf_urls(html: str) -> list[str]:
    """De OER-PDF-URL's uit een academie-pagina (gesorteerd, ontdubbeld)."""
    return sorted(set(_MBOU_PDF_RE.findall(html)))


def _mbou_crebo_uit_pdf(pdf_bytes: bytes) -> str | None:
    """Open de PDF en zoek de crebo in de eerste 5 pagina's (best-effort)."""
    import io

    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:5]:
                crebo = _mbou_crebo_uit_tekst(page.extract_text() or "")
                if crebo:
                    return crebo
    except Exception as e:  # corrupte/onleesbare PDF → overslaan, niet de hele crawl breken
        logger.warning("MBO Utrecht: PDF onleesbaar (%s)", e)
    return None


def mboutrecht_catalogus() -> list[CatalogusItem]:
    """Crawl de MBO Utrecht-academiepagina's, download de OER-PDF's en parse de crebo."""
    items: list[CatalogusItem] = []
    with httpx.Client(headers={"user-agent": _UA}, timeout=60, follow_redirects=True) as client:
        sitemap = client.get(_MBOU_SITEMAP)
        sitemap.raise_for_status()
        pdf_urls: set[str] = set()
        for pagina_url in _MBOU_LOC_RE.findall(sitemap.text):
            try:
                resp = client.get(pagina_url)
                resp.raise_for_status()
            except httpx.HTTPError:
                continue
            pdf_urls.update(_mbou_pdf_urls(resp.text))
        for url in sorted(pdf_urls):
            cohort = _mbou_cohort_uit_url(url)
            if not cohort:
                continue
            try:
                pdf = client.get(url)
                pdf.raise_for_status()
            except httpx.HTTPError:
                continue
            crebo = _mbou_crebo_uit_pdf(pdf.content)
            if crebo:
                naam = url.rsplit("/", 1)[-1]
                items.append(CatalogusItem(crebo, "onbekend", cohort, naam, "utrecht"))
    return items


_CATALOGUS_BRONNEN: dict[str, Callable[[], list[CatalogusItem]]] = {
    "deltion": deltion_catalogus,
    "aeres": aeres_catalogus,
    "rijn_ijssel": rijnijssel_catalogus,
    "utrecht": mboutrecht_catalogus,
}


def open_conn():
    """Open een DB-connectie op het geconfigureerde pad (caller sluit 'm)."""
    return db.get_connection(Path(os.environ.get("DB_PATH", "data/validatie.db")))


def manifest_pad() -> Path:
    """Pad van de gecommitte corpus-manifest (naast de DB; gitignored-met-exceptie)."""
    return Path(os.environ.get("DB_PATH", "data/validatie.db")).parent / "oer_corpus_manifest.json"


def genereer_corpus_manifest(conn, pad: Path) -> None:
    """Schrijf een deterministische snapshot van (crebo, leerweg, cohort) per instelling.

    De Action diff't hiertegen i.p.v. tegen de DB (validatie.db + een deel van oeren/ zijn
    gitignored). Gegenereerd uit de VOLLEDIGE lokale DB, dus inclusief Deltion. Gesorteerd
    + ontdubbeld zodat de diff klein en de git-diff stabiel blijft.
    """
    manifest: dict[str, list[tuple[str, str, str]]] = {}
    for r in db.get_alle_oers_met_instelling(conn):
        manifest.setdefault(r["naam"], []).append((r["crebo"], r["leerweg"], r["cohort"]))
    uit = {
        inst: [list(t) for t in sorted(set(tupels))] for inst, tupels in sorted(manifest.items())
    }
    pad.write_text(json.dumps(uit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def instelling_nieuwe_oers(
    instelling: str, conn=None, *, manifest: bool = False
) -> list[CatalogusItem]:
    """Haal de catalogus van een instelling en diff tegen wat we al hebben.

    Lege lijst als er (nog) geen adapter voor de instelling is. Standaard diff't hij tegen
    de DB; met ``manifest=True`` tegen de gecommitte ``oer_corpus_manifest.json`` — die modus
    heeft geen DB nodig en is bedoeld voor de wekelijkse Action (validatie.db is gitignored).
    Geef een open ``conn`` mee om bij meerdere instellingen één connectie te delen. Bij een
    netwerk-/API-fout raise't hij ``CatalogusOnbereikbaarError`` zodat de aanroeper kan degraderen.
    """
    bron = _CATALOGUS_BRONNEN.get(instelling)
    if bron is None:
        return []
    try:
        catalogus = bron()
    except httpx.HTTPError as e:
        raise CatalogusOnbereikbaarError(f"{instelling}: {e}") from e
    velden = _DIFF_SLEUTEL_VELDEN.get(instelling, _STANDAARD_VELDEN)
    if manifest:
        db_tupels = _tupels_uit_manifest(instelling, velden, manifest_pad())
    else:
        eigen = conn or open_conn()
        try:
            rows = db.get_alle_oers_met_instelling(eigen)
        finally:
            if conn is None:
                eigen.close()
        db_tupels = _tupels_uit_rows(rows, instelling, velden)
    return nieuwe_oers(catalogus, db_tupels, velden)


def gewijzigde_oers(instelling: str, conn=None) -> tuple[list[CatalogusItem], int]:
    """OER's die wij hebben én die upstream inhoudelijk zijn gewijzigd (Deltion-only).

    Matcht elk catalogus-item op zijn diff-sleutel tegen onze DB-rijen. Voor een match
    met een opgeslagen `content_hash` wordt de upstream-content gerefetcht
    (`/reports/<uuid>/html`) en via `bereken_content_hash` vergeleken. Returnt
    ``(gewijzigde_items, aantal_zonder_baseline)``. Een rij met `content_hash IS NULL`
    telt als zonder-baseline (niet gefetcht). Niet-Deltion-instellingen → ``([], 0)``
    omdat ze geen per-OER content-endpoint hebben.

    Raises:
        CatalogusOnbereikbaarError: bij een netwerk-/API-fout op de catalogus-call.
    """
    if instelling != "deltion":
        return [], 0
    try:
        catalogus = deltion_catalogus()
    except httpx.HTTPError as e:
        raise CatalogusOnbereikbaarError(f"{instelling}: {e}") from e
    velden = _DIFF_SLEUTEL_VELDEN.get(instelling, _STANDAARD_VELDEN)
    eigen = conn or open_conn()
    try:
        rows = db.get_alle_oers_met_instelling(eigen)
    finally:
        if conn is None:
            eigen.close()
    hash_per_sleutel = {
        _projecteer(r["crebo"], r["leerweg"], r["cohort"], velden): r["content_hash"]
        for r in rows
        if r["naam"] == instelling
    }
    gewijzigd: list[CatalogusItem] = []
    zonder_baseline = 0
    fd = _fetch_deltion()
    with httpx.Client(headers=fd._HEADERS, timeout=30) as client:
        for item in catalogus:
            sleutel = _projecteer(item.crebo, item.leerweg, item.cohort, velden)
            if sleutel not in hash_per_sleutel:
                continue  # nieuwe OER → telt onder nieuwe_oers, niet hier
            opgeslagen = hash_per_sleutel[sleutel]
            if not opgeslagen:
                zonder_baseline += 1
                continue
            if not item.uuid:
                continue
            try:
                md = fd._haal_studiegids_md(client, item.uuid)
            except httpx.HTTPError:
                continue  # sla een kapotte refetch over, niet de hele check
            if bereken_content_hash(md) != opgeslagen:
                gewijzigd.append(item)
    return gewijzigd, zonder_baseline
