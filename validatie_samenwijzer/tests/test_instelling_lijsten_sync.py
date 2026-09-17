"""Guard: de afgeleide instelling-mappings dekken de volledige registry.

Sinds de instelling-registry (``validatie_samenwijzer.instellingen``) is de bron
één lijst: :data:`instellingen.INSTELLINGEN`. De consumenten (ingest, seed_bulk,
beheer, chat, bron_updates, oer_catalogus) leiden hun mapping daarvan af. Deze
test vangt een terugval naar handmatige literals: elke afgeleide mapping moet
exact de registry-namen hebben.

Ontbreekt een instelling in ``seed_bulk.INSTELLINGEN`` dan krijgt ze stil
0 studenten (zie CLAUDE.md); ontbreekt ze in ``chat._INSTELLING_DOMEINEN`` dan
krijgt die instelling stil geen webzoek-fallback; ontbreekt ze in
``bron_updates`` dan stil geen catalogus-check.
"""

import sys
from pathlib import Path

from validatie_samenwijzer import instellingen

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

import seed_bulk  # noqa: E402  (scripts/ is geen package)


def _ingest_mapping():
    from validatie_samenwijzer import ingest

    return set(ingest._INSTELLINGEN), set(ingest._MAP_NAAM)


def _chat_domeinen():
    from validatie_samenwijzer import chat

    return set(chat._INSTELLING_DOMEINEN)


def _beheer_keys():
    from app_fastapi import main as beheer_main

    return set(beheer_main._INSTELLING_KEYS)


def _bronupdates_lijsten():
    from validatie_samenwijzer import bron_updates

    return set(bron_updates._OER_CRAWLBAAR), set(bron_updates._OER_NIET_CRAWLBAAR)


def test_ingest_mappings_dekken_registry():
    inst, mappen = _ingest_mapping()
    assert inst == set(instellingen.namen())
    assert mappen == set(instellingen.namen())


def test_seed_bulk_dekt_registry():
    assert {d["naam"] for d in seed_bulk.INSTELLINGEN} == set(instellingen.namen())
    assert [d["naam"] for d in seed_bulk.INSTELLINGEN] == instellingen.namen()  # seed-volgorde


def test_beheer_keys_dekken_registry():
    assert _beheer_keys() == set(instellingen.namen())


def test_chat_domeinen_dekken_registry():
    assert _chat_domeinen() == set(instellingen.namen())


def test_bronupdates_lijsten_dekken_registry():
    crawlbaar, niet_crawlbaar = _bronupdates_lijsten()
    assert crawlbaar == set(instellingen.crawlbaar())
    assert niet_crawlbaar == set(instellingen.niet_crawlbaar())
    assert not crawlbaar & niet_crawlbaar


def test_diff_velden_uitzonderingen_gebruiken_geen_leerweg():
    """De catalogus-uitzonderingen vergelijken op ('crebo', 'cohort') — de catalogus
    levert voor deze instellingen geen betrouwbare leerweg, dus diff op leerweg zou
    elke OER als 'nieuw' markeren. Overige instellingen diffen op de standaard-tuple."""

    uitzonderingen = ("aeres", "rijn_ijssel", "utrecht")
    standaard = ("crebo", "leerweg", "cohort")
    for i in instellingen.alle():
        verwacht = ("crebo", "cohort") if i.naam in uitzonderingen else standaard
        assert i.diff_velden == verwacht


# Frozen snapshot: de registry-volgorde is de seed-volgorde (één gedeelde Random(2026)).
# Insert nieuwe instellingen alléén aan het EIND — een insert middenin schuift de
# studenten-verdeling van álle latere instellingen op. Dit snapshot maakt dat bewijsbaar.
_SEEDVOLGORDE_SNAPSHOT = [
    "talland",
    "davinci",
    "rijn_ijssel",
    "aeres",
    "utrecht",
    "kwic",
    "curio",
    "deltion",
    "graafschap",
    "landstede",
    "nijmegen",
]


def test_registry_volgorde_is_append_only_seedvolgorde():
    assert instellingen.namen() == _SEEDVOLGORDE_SNAPSHOT, (
        "De registry-volgorde is de seed-volgorde (Random(2026) deelt in lijst-volgorde). "
        "Append nieuwe instellingen alléén aan het eind en update dit snapshot bewust."
    )
