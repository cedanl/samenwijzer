"""Eén bron voor instelling-metataal.

Verving zes gesynchroniseerde hardgecodeerde lijsten die per instelling dezelfde
kennis apart bewaarden:

1. ``ingest._INSTELLINGEN``       (naam → display_naam)
2. ``ingest._MAP_NAAM``           (naam → oeren-submap)
3. ``scripts/seed_bulk.py:INSTELLINGEN`` (naam + display_naam + klas_prefix)
4. ``app_fastapi/main.py:_INSTELLING_KEYS`` (beheer-scope-validatie)
5. ``chat._INSTELLING_DOMEINEN``  (naam → schoolsite-domein voor webzoek-fallback)
6. ``bron_updates._OER_CRAWLBAAR``/``_OER_NIET_CRAWLBAAR`` + ``oer_catalogus._DIFF_SLEUTEL_VELDEN``

De consumenten leiden hun eigen mapping af van :data:`INSTELLINGEN`; de guard-test
``tests/test_instelling_lijsten_sync.py`` controleert dat die afgeleide mappings
compleet zijn (en vangt zo een terugval naar handmatige literals).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instelling:
    """Alle per-instelling-kennis op één plek.

    ``diff_velden``: tuple-diff-sleutel voor de bronactualiteit-cataloguscheck.
    Instellingen zonder betrouwbare leerweg in de catalogus (aeres, rijn_ijssel,
    utrecht) vergelijken op een subset — anders matcht hun tuple nooit de DB
    (die wél BOL/BBL heeft) en lijkt elke OER 'nieuw'.
    """

    naam: str
    display_naam: str
    map_naam: str
    web_domein: str
    klas_prefix: str
    crawlbaar: bool
    diff_velden: tuple[str, ...] = ("crebo", "leerweg", "cohort")


# VOLGORDE = seed-volgorde: seed_bulk.py deelt één Random(2026) in lijst-volgorde,
# dus append nieuwe instellingen ALLÉEN aan het eind — anders verandert de
# RNG-verdeling van de bestaande instellingen (bulk-seed ~1700 studenten).
# Crawlbaarheid: juni 2026 in kaart gebracht (zie reference-memory + scripts/fetch_deltion.py);
# bepaalt of de OER-/instellingscatalogus-check geautomatiseerd kan worden (Fase 3)
# of handmatig blijft.
INSTELLINGEN: tuple[Instelling, ...] = (
    Instelling("talland", "Talland", "talland_oeren", "talland.nl", "TA", True),
    Instelling("davinci", "Da Vinci College", "davinci_oeren", "davinci.nl", "DV", False),
    Instelling(
        "rijn_ijssel",
        "Rijn IJssel",
        "rijn_ijssel_oer",
        "rijnijssel.nl",
        "RI",
        True,
        ("crebo", "cohort"),
    ),
    Instelling("aeres", "Aeres MBO", "aeres_oeren", "aeres.nl", "AE", True, ("crebo", "cohort")),
    Instelling(
        "utrecht", "ROC Utrecht", "utrecht_oeren", "mboutrecht.nl", "UT", True, ("crebo", "cohort")
    ),
    Instelling("kwic", "Koning Willem I College", "kwic_oeren", "kw1c.nl", "KW", False),
    Instelling("curio", "Curio", "curio_oeren", "curio.nl", "CU", True),
    Instelling("deltion", "Deltion College", "deltion_oeren", "deltion.nl", "DE", True),
    Instelling(
        "graafschap", "Graafschap College", "graafschap_oeren", "graafschapcollege.nl", "GR", False
    ),
    Instelling("landstede", "Landstede MBO", "landstede_oeren", "landstedembo.nl", "LA", True),
    Instelling("nijmegen", "ROC Nijmegen", "nijmegen_oeren", "roc-nijmegen.nl", "NIJ", True),
)

_INDEX = {i.naam: i for i in INSTELLINGEN}


def alle() -> tuple[Instelling, ...]:
    return INSTELLINGEN


def namen() -> list[str]:
    return [i.naam for i in INSTELLINGEN]


def get(naam: str) -> Instelling | None:
    return _INDEX.get(naam)


def crawlbaar() -> list[str]:
    return [i.naam for i in INSTELLINGEN if i.crawlbaar]


def niet_crawlbaar() -> list[str]:
    return [i.naam for i in INSTELLINGEN if not i.crawlbaar]
