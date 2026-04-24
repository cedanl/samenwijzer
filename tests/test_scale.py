"""Schaaltests: correctheid van analyze- en transform-functies met 1000 studenten."""

import pandas as pd
import pytest

from samenwijzer.analyze import (
    cohort_gemiddelden,
    cohort_positie,
    groepsoverzicht,
    leerpad_niveau,
    peer_profielen,
    zwakste_kerntaak,
    zwakste_werkproces,
)
from samenwijzer.outreach import at_risk_studenten
from samenwijzer.transform import (
    get_kerntaak_columns,
    get_werkproces_columns,
    melt_kerntaken,
    melt_werkprocessen,
    transform_student_data,
)
from tests.helpers import maak_grote_df


@pytest.fixture(scope="module")
def df_groot() -> pd.DataFrame:
    return maak_grote_df(1000)


# ── transform ─────────────────────────────────────────────────────────────────


def test_transform_geen_null_verplichte_kolommen(df_groot: pd.DataFrame) -> None:
    verplicht = ["bsa_percentage", "bsa_achterstand", "bsa_op_schema", "risico"]
    for kolom in verplicht:
        assert df_groot[kolom].notna().all(), f"Kolom '{kolom}' bevat NaN-waarden"


def test_transform_bsa_percentage_bereik(df_groot: pd.DataFrame) -> None:
    assert (df_groot["bsa_percentage"] >= 0).all()


def test_transform_risico_is_bool(df_groot: pd.DataFrame) -> None:
    assert df_groot["risico"].dtype == bool


def test_get_kerntaak_columns_retourneert_lijst(df_groot: pd.DataFrame) -> None:
    kt_cols = get_kerntaak_columns(df_groot)
    assert isinstance(kt_cols, list)
    assert all(col in df_groot.columns for col in kt_cols)


def test_get_werkproces_columns_retourneert_lijst(df_groot: pd.DataFrame) -> None:
    wp_cols = get_werkproces_columns(df_groot)
    assert isinstance(wp_cols, list)
    assert all(col in df_groot.columns for col in wp_cols)


def test_melt_kerntaken_bevat_alle_studenten(df_groot: pd.DataFrame) -> None:
    kt_cols = get_kerntaak_columns(df_groot)
    if not kt_cols:
        pytest.skip("Geen kerntaakkolommen in dataset")
    gesmolten = melt_kerntaken(df_groot)
    assert len(gesmolten) == len(df_groot) * len(kt_cols)


def test_melt_werkprocessen_bevat_alle_studenten(df_groot: pd.DataFrame) -> None:
    wp_cols = get_werkproces_columns(df_groot)
    if not wp_cols:
        pytest.skip("Geen werkproceskolommen in dataset")
    gesmolten = melt_werkprocessen(df_groot)
    assert len(gesmolten) == len(df_groot) * len(wp_cols)


# ── analyze ───────────────────────────────────────────────────────────────────


def test_groepsoverzicht_bevat_alle_studenten(df_groot: pd.DataFrame) -> None:
    overzicht = groepsoverzicht(df_groot)
    assert len(overzicht) == 1000


def test_groepsoverzicht_gesorteerd_op_naam(df_groot: pd.DataFrame) -> None:
    overzicht = groepsoverzicht(df_groot)
    namen = overzicht["naam"].tolist()
    assert namen == sorted(namen)


def test_leerpad_niveau_nooit_none(df_groot: pd.DataFrame) -> None:
    for _, student in df_groot.iterrows():
        assert leerpad_niveau(student) is not None


def test_cohort_positie_geeft_dict(df_groot: pd.DataFrame) -> None:
    snr = df_groot.iloc[0]["studentnummer"]
    resultaat = cohort_positie(df_groot, snr)
    assert isinstance(resultaat, dict)
    assert "positie" in resultaat
    assert "totaal" in resultaat
    assert 1 <= resultaat["positie"] <= resultaat["totaal"]


def test_cohort_positie_beste_student(df_groot: pd.DataFrame) -> None:
    """Student met hoogste voortgang in het cohort heeft positie 1."""
    beste_snr = df_groot.loc[df_groot["voortgang"].idxmax(), "studentnummer"]
    resultaat = cohort_positie(df_groot, beste_snr)
    assert resultaat["positie"] == 1


def test_cohort_gemiddelden_geeft_dataframe(df_groot: pd.DataFrame) -> None:
    gem = cohort_gemiddelden(df_groot)
    assert isinstance(gem, pd.DataFrame)
    assert "gem_voortgang" in gem.columns
    assert (gem["gem_voortgang"] >= 0).all()
    assert (gem["gem_voortgang"] <= 1).all()


def test_peer_profielen_bevat_alle_studenten(df_groot: pd.DataFrame) -> None:
    """peer_profielen geeft één rij per student terug."""
    profielen = peer_profielen(df_groot)
    if profielen.empty:
        pytest.skip("Geen kerntaakkolommen in dataset")
    assert len(profielen) == len(df_groot)


def test_peer_profielen_heeft_vereiste_kolommen(df_groot: pd.DataFrame) -> None:
    profielen = peer_profielen(df_groot)
    if profielen.empty:
        pytest.skip("Geen kerntaakkolommen in dataset")
    for kolom in ("naam", "sterkste_kt", "zwakste_kt"):
        assert kolom in profielen.columns


def test_zwakste_kerntaak_geeft_naam_of_none(df_groot: pd.DataFrame) -> None:
    snr = df_groot.iloc[0]["studentnummer"]
    resultaat = zwakste_kerntaak(df_groot, snr)
    assert resultaat is None or isinstance(resultaat[0], str)


def test_zwakste_werkproces_geeft_naam_of_none(df_groot: pd.DataFrame) -> None:
    snr = df_groot.iloc[0]["studentnummer"]
    resultaat = zwakste_werkproces(df_groot, snr)
    assert resultaat is None or isinstance(resultaat[0], str)


# ── outreach ──────────────────────────────────────────────────────────────────


def test_at_risk_studenten_retourneert_subset(df_groot: pd.DataFrame) -> None:
    result = at_risk_studenten(df_groot)
    assert len(result) <= len(df_groot)
    assert len(result) > 0  # met 1000 studenten zijn er altijd risicogevallen


def test_at_risk_studenten_gesorteerd_oplopend(df_groot: pd.DataFrame) -> None:
    result = at_risk_studenten(df_groot)
    voortgangen = result["voortgang"].tolist()
    assert voortgangen == sorted(voortgangen)


def test_at_risk_studenten_geen_goede_studenten(df_groot: pd.DataFrame) -> None:
    """Studenten met voortgang ≥ 0.40, bsa op schema en geen risicovlag zijn uitgesloten."""
    result = at_risk_studenten(df_groot)
    goede = df_groot[
        (~df_groot["risico"])
        & (df_groot["voortgang"] >= 0.40)
        & (df_groot["bsa_behaald"] >= 0.75 * df_groot["bsa_vereist"])
    ]
    overlap = set(result["studentnummer"]) & set(goede["studentnummer"])
    assert len(overlap) == 0


# ── Randgeval: alle voortgangen gelijk ───────────────────────────────────────


def test_cohort_positie_bij_gelijke_voortgangen() -> None:
    """Geen crash als alle studenten in het cohort dezelfde voortgang hebben."""
    raw = pd.DataFrame(
        {
            "studentnummer": [f"S{i:03d}" for i in range(50)],
            "naam": [f"Student {i}" for i in range(50)],
            "mentor": ["M. X"] * 50,
            "opleiding": ["TestOpl"] * 50,
            "crebo": ["99999"] * 50,
            "niveau": pd.array([3] * 50, dtype="Int64"),
            "leerweg": ["BOL"] * 50,
            "cohort": ["2024-2025"] * 50,
            "leeftijd": pd.array([20] * 50, dtype="Int64"),
            "geslacht": ["V"] * 50,
            "bsa_behaald": [30.0] * 50,
            "bsa_vereist": [60.0] * 50,
            "voortgang": [0.50] * 50,
        }
    )
    df = transform_student_data(raw)
    snr = df.iloc[0]["studentnummer"]
    resultaat = cohort_positie(df, snr)
    assert isinstance(resultaat["positie"], int)
    assert resultaat["totaal"] == 50
