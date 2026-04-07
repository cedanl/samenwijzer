"""Tests voor samenwijzer.transform."""

import pandas as pd
import pytest

from samenwijzer.transform import (
    get_kerntaak_columns,
    get_werkproces_columns,
    melt_kerntaken,
    melt_werkprocessen,
    transform_student_data,
)


@pytest.fixture
def basis_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "studentnummer": ["S001", "S002", "S003"],
            "naam": ["Alice", "Bob", "Carol"],
            "niveau": pd.array([3, 3, 2], dtype="Int64"),
            "bsa_behaald": [50.0, 20.0, 38.0],
            "bsa_vereist": [60.0, 60.0, 40.0],
            "voortgang": [0.83, 0.33, 0.95],
            "kt1_taken": [80.0, 40.0, 75.0],
            "kt2_processen": [70.0, 35.0, 80.0],
            "wp1_1_sub": [78.0, 38.0, 72.0],
        }
    )


def test_bsa_percentage(basis_df):
    df = transform_student_data(basis_df)
    assert df.loc[df["studentnummer"] == "S001", "bsa_percentage"].iloc[0] == pytest.approx(50 / 60)


def test_bsa_percentage_capped_at_1(basis_df):
    basis_df.loc[0, "bsa_behaald"] = 70.0  # meer dan vereist
    df = transform_student_data(basis_df)
    assert df.loc[0, "bsa_percentage"] <= 1.0


def test_bsa_achterstand(basis_df):
    df = transform_student_data(basis_df)
    assert df.loc[df["studentnummer"] == "S002", "bsa_achterstand"].iloc[0] == 40.0


def test_bsa_op_schema(basis_df):
    basis_df.loc[0, "bsa_behaald"] = 60.0
    df = transform_student_data(basis_df)
    assert bool(df.loc[0, "bsa_op_schema"]) is True


def test_kt_gemiddelde(basis_df):
    df = transform_student_data(basis_df)
    verwacht = (80 + 70) / 2
    assert df.loc[0, "kt_gemiddelde"] == pytest.approx(verwacht)


def test_risico_laag_bsa(basis_df):
    df = transform_student_data(basis_df)
    # S002: bsa_percentage = 20/60 ≈ 0.33 < 0.50 → risico
    assert bool(df.loc[df["studentnummer"] == "S002", "risico"].iloc[0]) is True


def test_geen_risico(basis_df):
    df = transform_student_data(basis_df)
    # S001: bsa 50/60 ≈ 0.83, voortgang 0.83 → geen risico
    assert bool(df.loc[df["studentnummer"] == "S001", "risico"].iloc[0]) is False


def test_risico_lage_voortgang(basis_df):
    basis_df.loc[0, "voortgang"] = 0.30
    df = transform_student_data(basis_df)
    assert bool(df.loc[0, "risico"]) is True


def test_get_kerntaak_columns(basis_df):
    cols = get_kerntaak_columns(basis_df)
    assert cols == ["kt1_taken", "kt2_processen"]


def test_get_werkproces_columns(basis_df):
    cols = get_werkproces_columns(basis_df)
    assert cols == ["wp1_1_sub"]


def test_melt_kerntaken_shape(basis_df):
    df = transform_student_data(basis_df)
    melted = melt_kerntaken(df)
    assert set(melted.columns) >= {"studentnummer", "naam", "kerntaak", "score"}
    assert len(melted) == 3 * 2  # 3 studenten × 2 kerntaken


def test_melt_werkprocessen_shape(basis_df):
    df = transform_student_data(basis_df)
    melted = melt_werkprocessen(df)
    assert len(melted) == 3 * 1  # 3 studenten × 1 werkproces
