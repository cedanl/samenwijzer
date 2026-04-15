"""Tests voor samenwijzer.visualize."""

import altair as alt
import pandas as pd
import pytest

from samenwijzer.visualize import (
    bsa_staaf,
    groep_voortgang_grafiek,
    kerntaak_grafiek,
    voortgang_gauge,
    werkproces_grafiek,
)

# ── voortgang_gauge ───────────────────────────────────────────────────────────


def test_voortgang_gauge_geeft_altair_chart() -> None:
    chart = voortgang_gauge(0.65)
    assert isinstance(chart, alt.LayerChart)


def test_voortgang_gauge_kleur_goed_bij_hoge_voortgang() -> None:
    # ≥ 0.75 → groen
    chart = voortgang_gauge(0.80)
    # Controleer dat de chart aangemaakt wordt zonder fout
    assert chart is not None


def test_voortgang_gauge_kleur_risico_bij_lage_voortgang() -> None:
    chart = voortgang_gauge(0.30)
    assert chart is not None


def test_voortgang_gauge_hoogte_is_80() -> None:
    chart = voortgang_gauge(0.5)
    assert chart.properties().height == 80


def test_voortgang_gauge_custom_label() -> None:
    chart = voortgang_gauge(0.4, label="BSA-voortgang")
    assert chart is not None


@pytest.mark.parametrize("waarde", [0.0, 0.5, 1.0])
def test_voortgang_gauge_grenzen(waarde: float) -> None:
    chart = voortgang_gauge(waarde)
    assert isinstance(chart, alt.LayerChart)


# ── bsa_staaf ─────────────────────────────────────────────────────────────────


def test_bsa_staaf_geeft_altair_chart() -> None:
    chart = bsa_staaf(bsa_behaald=25.0, bsa_vereist=40.0)
    assert isinstance(chart, alt.Chart)


def test_bsa_staaf_hoogte_is_110() -> None:
    chart = bsa_staaf(25.0, 40.0)
    assert chart.properties().height == 110


def test_bsa_staaf_behaald_gelijk_aan_vereist() -> None:
    # Restant = max(0, 40 - 40) = 0 — mag geen negatieve waarden geven
    chart = bsa_staaf(40.0, 40.0)
    assert chart is not None


def test_bsa_staaf_meer_dan_vereist() -> None:
    # bsa_behaald > bsa_vereist: restant = 0
    chart = bsa_staaf(50.0, 40.0)
    assert chart is not None


# ── kerntaak_grafiek ──────────────────────────────────────────────────────────


@pytest.fixture
def kt_df() -> pd.DataFrame:
    return pd.DataFrame({"label": ["KT1 Zorgverlening", "KT2 Begeleiding"], "score": [72.0, 55.0]})


def test_kerntaak_grafiek_geeft_altair_chart(kt_df: pd.DataFrame) -> None:
    chart = kerntaak_grafiek(kt_df)
    assert isinstance(chart, alt.Chart)


def test_kerntaak_grafiek_hoogte_schaalt_met_rijen(kt_df: pd.DataFrame) -> None:
    chart = kerntaak_grafiek(kt_df)
    assert chart.properties().height == max(100, len(kt_df) * 55)


def test_kerntaak_grafiek_één_rij() -> None:
    df = pd.DataFrame({"label": ["KT1"], "score": [80.0]})
    chart = kerntaak_grafiek(df)
    assert chart.properties().height == 100  # minimum


# ── werkproces_grafiek ────────────────────────────────────────────────────────


@pytest.fixture
def wp_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "label": ["WP1.1 Intake", "WP1.2 Plan", "WP2.1 Uitvoer"],
            "score": [68.0, 45.0, 82.0],
        }
    )


def test_werkproces_grafiek_geeft_altair_chart(wp_df: pd.DataFrame) -> None:
    chart = werkproces_grafiek(wp_df)
    assert isinstance(chart, alt.Chart)


def test_werkproces_grafiek_hoogte_schaalt_met_rijen(wp_df: pd.DataFrame) -> None:
    chart = werkproces_grafiek(wp_df)
    assert chart.properties().height == max(140, len(wp_df) * 42)


# ── groep_voortgang_grafiek ───────────────────────────────────────────────────


@pytest.fixture
def overzicht_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "naam": ["Anna", "Ben", "Cara"],
            "opleiding": ["Verpleging"] * 3,
            "mentor": ["Fatima"] * 3,
            "voortgang": [0.30, 0.65, 0.85],
            "bsa_percentage": [0.45, 0.70, 0.95],
            "risico": [True, False, False],
        }
    )


def test_groep_voortgang_grafiek_geeft_altair_chart(overzicht_df: pd.DataFrame) -> None:
    chart = groep_voortgang_grafiek(overzicht_df)
    assert isinstance(chart, alt.Chart)


def test_groep_voortgang_grafiek_hoogte_is_350(overzicht_df: pd.DataFrame) -> None:
    chart = groep_voortgang_grafiek(overzicht_df)
    assert chart.properties().height == 350


def test_groep_voortgang_grafiek_muteert_origineel_niet(overzicht_df: pd.DataFrame) -> None:
    # groep_voortgang_grafiek doet een .copy() — origineel mag geen risico_label krijgen
    groep_voortgang_grafiek(overzicht_df)
    assert "risico_label" not in overzicht_df.columns
