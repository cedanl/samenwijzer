"""Tests voor samenwijzer.analyze."""

import pandas as pd
import pytest

from samenwijzer.analyze import (
    cohort_gemiddelden,
    get_student,
    groepsoverzicht,
    kerntaak_scores,
    werkproces_scores,
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
