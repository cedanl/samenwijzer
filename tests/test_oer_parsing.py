"""Tests voor oer_parsing module."""

from samenwijzer.oer_parsing import (
    bepaal_niveau,
    extraheer_kerntaken,
    extraheer_opleidingsnaam,
    parseer_bestandsnaam,
)


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


def test_extraheer_schone_naam_davinci():
    naam = extraheer_opleidingsnaam(
        "25655_BOL_2025__verzorgende-ig.md"
    )
    assert "Verzorgende" in naam


def test_extraheer_schone_naam_rijn_ijssel():
    naam = extraheer_opleidingsnaam(
        "25591_BOL_2025__oer-2025-2026-ci-25591-mediamaker.md"
    )
    assert "Mediamaker" in naam


def test_extraheer_filtert_examenplan_en_oer():
    naam = extraheer_opleidingsnaam(
        "25775_BOL_2025__25775BOL2025Examenplan-Logistiek-teamleider-cohort-2025.md"
    )
    assert "Logistiek" in naam
    assert "Examenplan" not in naam
    assert "OER" not in naam.upper()


def test_extraheer_geen_naam_als_alleen_codes():
    naam = extraheer_opleidingsnaam("25756_BBL_2025__25756BBL2025Examenplan.md")
    assert naam is None or naam == ""


def test_extraheer_max_4_woorden():
    naam = extraheer_opleidingsnaam(
        "25739_BBL_2025__25739BBL2025MJP-Technicus-Elektrotechnische-Installaties-in-de-Gebouwde-Omgeving-d1.md"
    )
    assert naam is not None
    assert len(naam.split()) <= 4


def test_bepaal_niveau_uit_bestandsnaam_suffix():
    assert bepaal_niveau("25099BBL2025MJP-MachinistGrondverzetN3.md", "") == 3
    assert bepaal_niveau("25099BBL2025MJP-MeubelmakerN2.md", "") == 2
    assert bepaal_niveau("12345BOL2025-OnbekendeOpleidingN4.md", "") == 4


def test_bepaal_niveau_uit_markdown_tekst():
    tekst = "Deze opleiding is op MBO niveau 3. Bla bla."
    assert bepaal_niveau("12345BOL2025.md", tekst) == 3


def test_bepaal_niveau_voorkeur_voor_bestandsnaam():
    # Bestandsnaam zegt N4, tekst zegt niveau 2 → bestandsnaam wint
    tekst = "Onbekende opleiding op niveau 2."
    assert bepaal_niveau("12345BOL2025-OnbekendeN4.md", tekst) == 4


def test_bepaal_niveau_geen_match_geeft_none():
    assert bepaal_niveau("OER 2025 algemeen.md", "Geen niveau-aanduiding hier.") is None
