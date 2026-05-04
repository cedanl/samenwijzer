"""Tests voor oer_parsing module."""

from samenwijzer.oer_parsing import parseer_bestandsnaam


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
