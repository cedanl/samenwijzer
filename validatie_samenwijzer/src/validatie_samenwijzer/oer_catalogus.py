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
_DIFF_SLEUTEL_VELDEN: dict[str, tuple[str, ...]] = {"aeres": ("crebo", "cohort")}


class CatalogusOnbereikbaarError(Exception):
    """De catalogus van een instelling kon niet worden opgehaald (netwerk/API-fout)."""


@dataclass(frozen=True)
class CatalogusItem:
    crebo: str
    leerweg: str
    cohort: str
    naam: str
    instelling: str

    @property
    def sleutel(self) -> tuple[str, str, str]:
        return (self.crebo, self.leerweg, self.cohort)


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


def _items_naar_catalogus(
    raw_items: list[dict], instelling: str, parse: Callable[[dict], dict | None]
) -> list[CatalogusItem]:
    """Pure transform: ruwe API-items → CatalogusItem via de gegeven parse-functie."""
    uit: list[CatalogusItem] = []
    for raw in raw_items:
        rec = parse(raw)
        if rec:
            uit.append(
                CatalogusItem(rec["crebo"], rec["leerweg"], rec["cohort"], rec["naam"], instelling)
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


_CATALOGUS_BRONNEN: dict[str, Callable[[], list[CatalogusItem]]] = {
    "deltion": deltion_catalogus,
    "aeres": aeres_catalogus,
}


def open_conn():
    """Open een DB-connectie op het geconfigureerde pad (caller sluit 'm)."""
    return db.get_connection(Path(os.environ.get("DB_PATH", "data/validatie.db")))


def instelling_nieuwe_oers(instelling: str, conn=None) -> list[CatalogusItem]:
    """Haal de catalogus van een instelling en diff tegen de DB.

    Lege lijst als er (nog) geen adapter voor de instelling is. Geef een open
    ``conn`` mee om bij meerdere instellingen één connectie te delen; zonder
    ``conn`` opent (en sluit) de functie er zelf één. Bij een netwerk-/API-fout
    raise't hij ``CatalogusOnbereikbaarError`` zodat de aanroeper kan degraderen.
    """
    bron = _CATALOGUS_BRONNEN.get(instelling)
    if bron is None:
        return []
    try:
        catalogus = bron()
    except httpx.HTTPError as e:
        raise CatalogusOnbereikbaarError(f"{instelling}: {e}") from e
    velden = _DIFF_SLEUTEL_VELDEN.get(instelling, _STANDAARD_VELDEN)
    eigen = conn or open_conn()
    try:
        rows = db.get_alle_oers_met_instelling(eigen)
    finally:
        if conn is None:
            eigen.close()
    return nieuwe_oers(catalogus, _tupels_uit_rows(rows, instelling, velden), velden)
