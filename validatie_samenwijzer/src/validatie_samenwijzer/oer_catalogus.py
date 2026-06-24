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
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import db

logger = logging.getLogger(__name__)


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


def nieuwe_oers(
    catalogus: list[CatalogusItem], db_tupels: set[tuple[str, str, str]]
) -> list[CatalogusItem]:
    """Catalogus-items waarvan de (crebo, leerweg, cohort) niet in de DB staat."""
    return [item for item in catalogus if item.sleutel not in db_tupels]


def _tupels_uit_rows(rows, instelling: str) -> set[tuple[str, str, str]]:
    """De (crebo, leerweg, cohort)-set die we al hebben voor één instelling.

    `rows` = `db.get_alle_oers_met_instelling()` (sqlite3.Row of dict met de
    sleutels crebo/leerweg/cohort/naam; `naam` = instelling-key).
    """
    return {(r["crebo"], r["leerweg"], r["cohort"]) for r in rows if r["naam"] == instelling}


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
    import httpx

    fd = _fetch_deltion()
    with httpx.Client(headers=fd._HEADERS, timeout=30) as client:
        raw = fd.haal_items_op(client, None)  # None = alle cohorten
    return _items_naar_catalogus(raw, "deltion", fd._record)


_CATALOGUS_BRONNEN: dict[str, Callable[[], list[CatalogusItem]]] = {
    "deltion": deltion_catalogus,
}


def instelling_nieuwe_oers(instelling: str, conn=None) -> list[CatalogusItem]:
    """Haal de catalogus van een instelling en diff tegen de DB.

    Lege lijst als er (nog) geen adapter voor de instelling is.
    """
    bron = _CATALOGUS_BRONNEN.get(instelling)
    if bron is None:
        return []
    catalogus = bron()
    eigen = conn or db.get_connection(Path(os.environ.get("DB_PATH", "data/validatie.db")))
    rows = db.get_alle_oers_met_instelling(eigen)
    return nieuwe_oers(catalogus, _tupels_uit_rows(rows, instelling))
