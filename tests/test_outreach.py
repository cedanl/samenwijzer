"""Tests voor samenwijzer.outreach (risicodetectie)."""

import pandas as pd
import pytest

from samenwijzer.outreach import at_risk_studenten


@pytest.fixture
def df_basis() -> pd.DataFrame:
    """Minimaal DataFrame met velden die at_risk_studenten gebruikt."""
    return pd.DataFrame(
        {
            "studentnummer": ["S001", "S002", "S003", "S004"],
            "naam": ["Anna", "Ben", "Cara", "Daan"],
            "opleiding": ["MBO"] * 4,
            "niveau": [3, 3, 4, 4],
            "voortgang": [0.20, 0.60, 0.45, 0.80],
            "bsa_behaald": [10, 30, 20, 40],
            "bsa_vereist": [40, 40, 40, 40],
            "risico": [False, False, False, False],
        }
    )


def test_selecteert_lage_voortgang(df_basis: pd.DataFrame) -> None:
    # S001: voortgang 20 % < 40 % drempel
    result = at_risk_studenten(df_basis)
    nummers = result["studentnummer"].tolist()
    assert "S001" in nummers


def test_selecteert_bsa_achterstand(df_basis: pd.DataFrame) -> None:
    # S003: bsa_behaald 20 < 0.75 * 40 = 30
    result = at_risk_studenten(df_basis)
    assert "S003" in result["studentnummer"].tolist()


def test_sluit_goede_studenten_uit(df_basis: pd.DataFrame) -> None:
    # S004: voortgang 80 %, bsa 40/40, geen risico-vlag
    result = at_risk_studenten(df_basis)
    assert "S004" not in result["studentnummer"].tolist()


def test_selecteert_op_risicovlag(df_basis: pd.DataFrame) -> None:
    df_basis.loc[df_basis["studentnummer"] == "S002", "risico"] = True
    result = at_risk_studenten(df_basis)
    assert "S002" in result["studentnummer"].tolist()


def test_gesorteerd_op_voortgang_oplopend(df_basis: pd.DataFrame) -> None:
    result = at_risk_studenten(df_basis)
    voortgangen = result["voortgang"].tolist()
    assert voortgangen == sorted(voortgangen)


def test_leeg_dataframe_geeft_leeg_resultaat() -> None:
    leeg = pd.DataFrame(
        columns=["studentnummer", "naam", "opleiding", "niveau", "voortgang",
                 "bsa_behaald", "bsa_vereist", "risico"]
    )
    result = at_risk_studenten(leeg)
    assert result.empty
