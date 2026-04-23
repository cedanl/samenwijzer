import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from rename_oers import (
    _extraheer_uit_bestandsnaam,
    _extraheer_uit_tekst,
    _naam_heeft_prefix,
)


# ── _naam_heeft_prefix ────────────────────────────────────────────────────────


def test_prefix_aanwezig():
    assert _naam_heeft_prefix("25726_BOL_2025__bestand.txt") is True


def test_prefix_afwezig_davinci_stijl():
    assert _naam_heeft_prefix("25726BOL2025Examenplan.txt") is False


def test_prefix_afwezig_geen_crebo():
    assert _naam_heeft_prefix("Addendum OER vanaf cohort 2024-2025.txt") is False


# ── _extraheer_uit_bestandsnaam ───────────────────────────────────────────────


def test_davinci_bol():
    r = _extraheer_uit_bestandsnaam("25726BOL2025Examenplan.txt")
    assert r == {"crebo": "25726", "leerweg": "BOL", "cohort": "2025"}


def test_davinci_bbl():
    r = _extraheer_uit_bestandsnaam("25099BBL2025MJP-MachinistGrondverzetN3.txt")
    assert r == {"crebo": "25099", "leerweg": "BBL", "cohort": "2025"}


def test_davinci_leerweg_voor_examenplan():
    # leerweg staat direct na crebo maar jaar komt later: 25182BBLExamenplan2025
    r = _extraheer_uit_bestandsnaam("25182BBLExamenplan2025-Zelfstandig-werkend-kok.txt")
    assert r == {"crebo": "25182", "leerweg": "BBL", "cohort": "2025"}


def test_davinci_bol_voor_examenplan():
    r = _extraheer_uit_bestandsnaam("25182BOLExamenplan2025-Zelfstandig-werkend-kok.txt")
    assert r == {"crebo": "25182", "leerweg": "BOL", "cohort": "2025"}


def test_naam_zonder_crebo():
    r = _extraheer_uit_bestandsnaam("Addendum OER vanaf cohort 2024-2025.txt")
    assert r["crebo"] is None


def test_rijn_ijssel_stijl():
    r = _extraheer_uit_bestandsnaam("content_oer-2024-2025-ci-25651-acteur.txt")
    assert r["crebo"] == "25651"
    assert r["cohort"] == "2024"


def test_talland_stijl():
    r = _extraheer_uit_bestandsnaam("25180 Kok 24 maanden BBL.txt")
    assert r["crebo"] == "25180"
    assert r["leerweg"] == "BBL"


# ── _extraheer_uit_tekst ──────────────────────────────────────────────────────


def test_tekst_met_crebo_label():
    tekst = "CREBO: 25655\nLeerweg: BBL\nCohort 2024-2025"
    r = _extraheer_uit_tekst(tekst)
    assert r["crebo"] == "25655"
    assert r["leerweg"] == "BBL"
    assert r["cohort"] == "2024"


def test_tekst_zonder_metadata():
    r = _extraheer_uit_tekst("Inhoudsopgave en algemene informatie")
    assert r["crebo"] is None
    assert r["leerweg"] is None
    assert r["cohort"] is None
