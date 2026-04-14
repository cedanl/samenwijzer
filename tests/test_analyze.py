"""Tests voor samenwijzer.analyze."""

import pandas as pd
import pytest

from samenwijzer.analyze import (
    badge,
    cohort_gemiddelden,
    cohort_positie,
    detecteer_transitiemoment,
    get_student,
    groepsoverzicht,
    kerntaak_scores,
    leerpad_niveau,
    peer_profielen,
    transitiemoment_label,
    werkproces_scores,
    zwakste_kerntaak,
    zwakste_werkproces,
)
from samenwijzer.transform import transform_student_data


@pytest.fixture
def df() -> pd.DataFrame:
    raw = pd.DataFrame(
        {
            "studentnummer": ["S001", "S002"],
            "naam": ["Alice", "Bob"],
            "mentor": ["M. Bakker", "M. Bakker"],
            "opleiding": ["Verzorgende IG", "Verzorgende IG"],
            "crebo": ["25491", "25491"],
            "niveau": pd.array([3, 3], dtype="Int64"),
            "leerweg": ["BOL", "BBL"],
            "cohort": ["2024-2025", "2024-2025"],
            "leeftijd": pd.array([19, 21], dtype="Int64"),
            "geslacht": ["V", "M"],
            "bsa_behaald": [50.0, 20.0],
            "bsa_vereist": [60.0, 60.0],
            "voortgang": [0.83, 0.33],
            "kt1_begeleiden": [80.0, 40.0],
            "wp1_1_intake": [78.0, 38.0],
        }
    )
    return transform_student_data(raw)


def test_get_student_gevonden(df):
    student = get_student(df, "S001")
    assert student["naam"] == "Alice"


def test_get_student_niet_gevonden(df):
    with pytest.raises(ValueError, match="niet gevonden"):
        get_student(df, "X999")


def test_groepsoverzicht_kolommen(df):
    overzicht = groepsoverzicht(df)
    assert "naam" in overzicht.columns
    assert "risico" in overzicht.columns


def test_groepsoverzicht_gesorteerd(df):
    overzicht = groepsoverzicht(df)
    namen = overzicht["naam"].tolist()
    assert namen == sorted(namen)


def test_kerntaak_scores(df):
    kt = kerntaak_scores(df, "S001")
    assert len(kt) == 1
    assert kt.iloc[0]["score"] == 80.0


def test_werkproces_scores(df):
    wp = werkproces_scores(df, "S001")
    assert len(wp) == 1
    assert wp.iloc[0]["score"] == 78.0


def test_cohort_gemiddelden(df):
    cg = cohort_gemiddelden(df)
    assert len(cg) == 1
    assert cg.iloc[0]["aantal"] == 2


# ── leerpad_niveau ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("voortgang", "kt_gem", "verwacht"),
    [
        (0.90, 80.0, "Expert"),
        (0.80, 75.0, "Expert"),
        (0.70, 50.0, "Gevorderde"),
        (0.65, 45.0, "Gevorderde"),
        (0.50, 65.0, "Gevorderde"),
        (0.45, 40.0, "Onderweg"),
        (0.40, 30.0, "Onderweg"),
        (0.30, 40.0, "Starter"),
        (0.20, 20.0, "Starter"),
    ],
)
def test_leerpad_niveau(voortgang: float, kt_gem: float, verwacht: str) -> None:
    student = pd.Series({"voortgang": voortgang, "kt_gemiddelde": kt_gem})
    assert leerpad_niveau(student) == verwacht


def test_leerpad_niveau_zonder_kt_gemiddelde() -> None:
    # kt_gemiddelde ontbreekt → default 50
    student = pd.Series({"voortgang": 0.70})
    assert leerpad_niveau(student) == "Gevorderde"


# ── badge ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("voortgang", "verwacht_fragment"),
    [
        (0.90, "Expert"),
        (0.85, "Expert"),
        (0.80, "Gevorderde"),
        (0.75, "Gevorderde"),
        (0.70, "Onderweg"),
        (0.65, "Onderweg"),
        (0.50, "Starter"),
    ],
)
def test_badge(voortgang: float, verwacht_fragment: str) -> None:
    student = pd.Series({"voortgang": voortgang})
    assert verwacht_fragment in badge(student)


# ── zwakste_kerntaak / zwakste_werkproces ─────────────────────────────────────


def test_zwakste_kerntaak_geeft_tuple(df: pd.DataFrame) -> None:
    resultaat = zwakste_kerntaak(df, "S001")
    assert resultaat is not None
    label, score = resultaat
    assert isinstance(label, str)
    assert isinstance(score, float)


def test_zwakste_kerntaak_geeft_laagste_score(df: pd.DataFrame) -> None:
    # Bob heeft kt1_begeleiden=40, lager dan Alice (80)
    resultaat = zwakste_kerntaak(df, "S002")
    assert resultaat is not None
    _, score = resultaat
    assert score == 40.0


def test_zwakste_kerntaak_geen_kolommen() -> None:
    raw = pd.DataFrame(
        {
            "studentnummer": ["S001"],
            "naam": ["X"],
            "mentor": ["M"],
            "opleiding": ["O"],
            "crebo": ["0"],
            "niveau": pd.array([3], dtype="Int64"),
            "leerweg": ["BOL"],
            "cohort": ["2024"],
            "leeftijd": pd.array([20], dtype="Int64"),
            "geslacht": ["V"],
            "bsa_behaald": [40.0],
            "bsa_vereist": [60.0],
            "voortgang": [0.5],
        }
    )
    df_leeg = transform_student_data(raw)
    assert zwakste_kerntaak(df_leeg, "S001") is None


def test_zwakste_werkproces_geeft_tuple(df: pd.DataFrame) -> None:
    resultaat = zwakste_werkproces(df, "S001")
    assert resultaat is not None
    label, score = resultaat
    assert isinstance(label, str)
    assert score == 78.0


# ── cohort_positie ────────────────────────────────────────────────────────────


def test_cohort_positie_alice_eerste(df: pd.DataFrame) -> None:
    # Alice: voortgang 0.83 > Bob: 0.33 → positie 1 van 2
    pos = cohort_positie(df, "S001")
    assert pos["positie"] == 1
    assert pos["totaal"] == 2
    assert pos["cohort"] == "2024-2025"


def test_cohort_positie_bob_tweede(df: pd.DataFrame) -> None:
    pos = cohort_positie(df, "S002")
    assert pos["positie"] == 2


# ── peer_profielen ────────────────────────────────────────────────────────────


def test_peer_profielen_geeft_dataframe(df: pd.DataFrame) -> None:
    pp = peer_profielen(df)
    assert isinstance(pp, pd.DataFrame)
    assert "naam" in pp.columns
    assert "sterkste_kt" in pp.columns
    assert "zwakste_kt" in pp.columns


def test_peer_profielen_gesorteerd_op_naam(df: pd.DataFrame) -> None:
    pp = peer_profielen(df)
    namen = pp["naam"].tolist()
    assert namen == sorted(namen)


def test_peer_profielen_leeg_zonder_kt_kolommen() -> None:
    raw = pd.DataFrame(
        {
            "studentnummer": ["S001"],
            "naam": ["X"],
            "mentor": ["M"],
            "opleiding": ["O"],
            "crebo": ["0"],
            "niveau": pd.array([3], dtype="Int64"),
            "leerweg": ["BOL"],
            "cohort": ["2024"],
            "leeftijd": pd.array([20], dtype="Int64"),
            "geslacht": ["V"],
            "bsa_behaald": [40.0],
            "bsa_vereist": [60.0],
            "voortgang": [0.5],
        }
    )
    df_leeg = transform_student_data(raw)
    pp = peer_profielen(df_leeg)
    assert pp.empty


# ── detecteer_transitiemoment ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("bsa_pct", "voortgang", "verwacht"),
    [
        (0.50, 0.50, "bsa_risico"),
        (0.59, 0.90, "bsa_risico"),
        (0.80, 0.85, "bijna_klaar"),
        (0.80, 0.80, "bijna_klaar"),
        (0.70, 0.70, None),
        (0.60, 0.60, None),
    ],
)
def test_detecteer_transitiemoment(bsa_pct: float, voortgang: float, verwacht: str | None) -> None:
    student = pd.Series({"bsa_percentage": bsa_pct, "voortgang": voortgang})
    assert detecteer_transitiemoment(student) == verwacht


# ── transitiemoment_label ─────────────────────────────────────────────────────


def test_transitiemoment_label_bsa_risico() -> None:
    assert "BSA" in transitiemoment_label("bsa_risico")


def test_transitiemoment_label_bijna_klaar() -> None:
    assert "klaar" in transitiemoment_label("bijna_klaar").lower()


def test_transitiemoment_label_none() -> None:
    assert transitiemoment_label(None) == ""


def test_transitiemoment_label_onbekend() -> None:
    assert transitiemoment_label("onbekend") == ""
