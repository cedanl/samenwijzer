"""Tests voor oer_parsing module."""

from samenwijzer.oer_parsing import extraheer_kerntaken, parseer_bestandsnaam


def test_parseer_davinci_format():
    res = parseer_bestandsnaam("25168BOL2025Examenplan.pdf")
    assert res == {"crebo": "25168", "leerweg": "BOL", "cohort": "2025"}


def test_parseer_rijn_ijssel_format():
    res = parseer_bestandsnaam("content_oer-2024-2025-ci-25651-acteur.pdf")
    assert res == {"crebo": "25651", "leerweg": "BOL", "cohort": "2024"}


def test_parseer_talland_format():
    res = parseer_bestandsnaam("25180 Kok 24 maanden BBL.pdf")
    assert res["crebo"] == "25180"
    assert res["leerweg"] == "BBL"


def test_parseer_geen_crebo_geeft_none():
    assert parseer_bestandsnaam("OER 20252026 DEF 11.md") is None


def test_parseer_combined_bolbbl():
    res = parseer_bestandsnaam("25960BOLBBL2025Examenplan.pdf")
    assert res == {"crebo": "25960", "leerweg": "BOL", "cohort": "2025"}


def test_extraheer_kerntaken_basis():
    tekst = """
    B1-K1: Bieden van zorg en ondersteuning
    B1-K1-W1: Onderkent gezondheidsproblemen
    B1-K1-W2: Voert verpleegkundige interventies uit
    """
    resultaten = extraheer_kerntaken(tekst)
    assert len(resultaten) == 3
    assert resultaten[0]["code"] == "B1-K1"
    assert resultaten[0]["type"] == "kerntaak"
    assert resultaten[1]["code"] == "B1-K1-W1"
    assert resultaten[1]["type"] == "werkproces"
    assert resultaten[1]["volgorde"] == 1


def test_extraheer_kerntaken_lege_tekst():
    assert extraheer_kerntaken("") == []
    assert extraheer_kerntaken("   ") == []


def test_extraheer_kerntaken_negeert_overige_regels():
    tekst = """
    Inleiding bla bla
    B1-K1: Echte kerntaak
    Random text die niet matcht
    """
    resultaten = extraheer_kerntaken(tekst)
    assert len(resultaten) == 1
    assert resultaten[0]["code"] == "B1-K1"
