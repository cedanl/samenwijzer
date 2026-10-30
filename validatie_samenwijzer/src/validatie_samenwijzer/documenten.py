"""Selectie en budgetbewaking van documenten voor de chat-context.

Per sessie (niet per vraag) wordt bepaald welke documenten bij de gekozen OER's horen:
instellingsbrede documenten plus opleidingsgebonden documenten die op crebo/leerweg/cohort
matchen. Past alles niet binnen het totaalbudget, dan geldt de prioriteit juridisch →
opleidingsgebonden → informatief, binnen een groep het kleinste document eerst. Wat afvalt wordt
teruggegeven (en gelogd) zodat de student erover geïnformeerd kan worden.

Zie docs/plans/2026-10-27-flexibele-documentlaag.md (§3).
"""

import logging
import os
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from validatie_samenwijzer.bron_catalogus import (
    _MAX_INSTELLING_TEKST_TEKENS,
    laad_oer_tekst,
    resolve_oer_pad,
)
from validatie_samenwijzer.db import (
    SOORTEN,
    get_documenten_voor_context,
    zichtbaarheden_voor_niveau,
)

logger = logging.getLogger(__name__)

_STANDAARD_BUDGET_TEKENS = 700_000


@dataclass(frozen=True)
class GekozenDocument:
    doc_id: int
    kop: str
    tekst: str
    juridisch: bool
    bereik: str


@dataclass(frozen=True)
class Selectie:
    per_oer: dict[int, list[GekozenDocument]]
    afgevallen: list[str]


def budget_tekens() -> int:
    """Totaalbudget voor documenten (tekens); override via env `DOC_BUDGET_TEKENS`."""
    return int(os.environ.get("DOC_BUDGET_TEKENS", _STANDAARD_BUDGET_TEKENS))


def _kop(soort: str, titel: str, instelling: str = "") -> str:
    """Blokkop in de prompt. Een achtervoegsel met de instellingsnaam (oude titels als
    "Examenreglement Curio") wordt weggelaten. Niet-juridische documenten krijgen
    `[INFORMATIEF]`: daarbij volstaat een bronvermelding en is een woordelijk citaat niet nodig.
    """
    info = SOORTEN[soort]
    naam = titel.removesuffix(f" {instelling}") if instelling else titel
    if naam == info.label:
        kop = info.label
    elif naam.startswith(f"{info.label} "):
        kop = f"{info.label} — {naam[len(info.label) + 1 :]}"
    else:
        kop = f"{info.label} — {naam}"
    return kop if info.juridisch else f"{kop} [INFORMATIEF]"


def _prioriteit(doc: GekozenDocument) -> int:
    """0 = juridisch, 1 = opleidingsgebonden, 2 = informatief instellingsbreed."""
    if doc.juridisch:
        return 0
    return 1 if doc.bereik == "opleiding" else 2


def selecteer_documenten(
    conn: sqlite3.Connection,
    oers: Sequence[sqlite3.Row],
    niveau: str,
    budget: int | None = None,
) -> Selectie:
    """Kies de documenten voor de gegeven OER's binnen het budget.

    Elke OER-rij heeft `id`, `instelling_id`, `crebo`, `leerweg` en `cohort`. Een document dat
    voor meerdere OER's geldt (bv. instellingsbreed) komt één keer voor, bij de eerste OER.

    Raises:
        ValueError: bij een onbekend niveau.
    """
    zichtbaarheden_voor_niveau(niveau)  # valideert ook zonder OER's
    budget = budget_tekens() if budget is None else budget

    kandidaten: list[tuple[int, GekozenDocument, str]] = []
    gezien: set[int] = set()
    for oer in oers:
        rijen = get_documenten_voor_context(
            conn, oer["instelling_id"], oer["crebo"], oer["leerweg"], oer["cohort"], niveau
        )
        for r in rijen:
            if r["id"] in gezien:
                continue
            gezien.add(r["id"])
            tekst = laad_oer_tekst(
                resolve_oer_pad(r["bestandspad"]), cap=_MAX_INSTELLING_TEKST_TEKENS
            )
            if not tekst.strip():
                logger.warning("Document zonder leesbare tekst overgeslagen: id=%s", r["id"])
                continue
            instelling = oer["display_naam"] if "display_naam" in oer.keys() else ""  # noqa: SIM118
            doc = GekozenDocument(
                r["id"], _kop(r["soort"], r["titel"], instelling), tekst,
                SOORTEN[r["soort"]].juridisch, r["bereik"],
            )  # fmt: skip
            kandidaten.append((oer["id"], doc, r["titel"]))

    kandidaten.sort(key=lambda k: (_prioriteit(k[1]), len(k[1].tekst), k[1].doc_id))
    per_oer: dict[int, list[GekozenDocument]] = {}
    afgevallen: list[str] = []
    gebruikt = 0
    for oer_id, doc, titel in kandidaten:
        if gebruikt + len(doc.tekst) > budget:
            afgevallen.append(titel)
            continue
        gebruikt += len(doc.tekst)
        per_oer.setdefault(oer_id, []).append(doc)
    if afgevallen:
        logger.warning("Documenten buiten budget (%s tekens) weggelaten: %s", budget, afgevallen)
    return Selectie(per_oer, afgevallen)
