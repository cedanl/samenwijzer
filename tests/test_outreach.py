"""Tests voor samenwijzer.outreach (risicodetectie, verwijzing, berichtgeneratie)."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from samenwijzer.outreach import at_risk_studenten, genereer_outreach_bericht, suggereer_verwijzing
from tests.helpers import mock_stream


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
        columns=[
            "studentnummer",
            "naam",
            "opleiding",
            "niveau",
            "voortgang",
            "bsa_behaald",
            "bsa_vereist",
            "risico",
        ]
    )
    result = at_risk_studenten(leeg)
    assert result.empty


# ── suggereer_verwijzing ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "categorie, verwachte_rol",
    [
        ("studieplanning", "Studieloopbaanbegeleider (SLB-er)"),
        ("welzijn", "Studentendecaan / vertrouwenspersoon"),
        ("financiën", "Financieel spreekuur"),
        ("werkplekleren", "Praktijkbegeleider"),
        ("overig", "Mentor / SLB-er"),
    ],
)
def test_suggereer_verwijzing_alle_categorieën(categorie: str, verwachte_rol: str) -> None:
    resultaat = suggereer_verwijzing(categorie)
    assert resultaat["rol"] == verwachte_rol


def test_suggereer_verwijzing_bevat_toelichting() -> None:
    for cat in ["studieplanning", "welzijn", "financiën", "werkplekleren", "overig"]:
        resultaat = suggereer_verwijzing(cat)
        assert "toelichting" in resultaat
        assert len(resultaat["toelichting"]) > 0


def test_suggereer_verwijzing_onbekende_categorie_valt_terug_op_overig() -> None:
    resultaat = suggereer_verwijzing("onbekend_xyz")
    overig = suggereer_verwijzing("overig")
    assert resultaat == overig


def test_suggereer_verwijzing_geeft_dict_terug() -> None:
    resultaat = suggereer_verwijzing("welzijn")
    assert isinstance(resultaat, dict)
    assert set(resultaat.keys()) == {"rol", "toelichting"}


# ── genereer_outreach_bericht ─────────────────────────────────────────────────


@pytest.fixture
def student_serie() -> pd.Series:
    return pd.Series(
        {
            "naam": "Jan de Vries",
            "opleiding": "ICT",
            "niveau": 3,
            "voortgang": 0.25,
            "bsa_behaald": 10,
            "bsa_vereist": 40,
        }
    )


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_outreach_bericht_streamt_tekst(
    mock_cls: MagicMock, student_serie: pd.Series
) -> None:
    bericht = "Beste Jan, ik zie dat je achterloopt."
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream(bericht)
    mock_cls.return_value = mock_client

    fragmenten = list(
        genereer_outreach_bericht(student_serie, mentor_naam="M. de Vries", api_key="test-key")
    )

    assert "".join(fragmenten) == bericht


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_outreach_bericht_prompt_bevat_studentnaam(
    mock_cls: MagicMock, student_serie: pd.Series
) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
    mock_cls.return_value = mock_client

    list(genereer_outreach_bericht(student_serie, mentor_naam="M. de Vries", api_key="test-key"))

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "Jan de Vries" in prompt


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_outreach_bericht_prompt_bevat_mentor(
    mock_cls: MagicMock, student_serie: pd.Series
) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
    mock_cls.return_value = mock_client

    list(genereer_outreach_bericht(student_serie, mentor_naam="K. Bakker", api_key="test-key"))

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "K. Bakker" in prompt


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_outreach_bericht_prompt_bevat_voortgang(
    mock_cls: MagicMock, student_serie: pd.Series
) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
    mock_cls.return_value = mock_client

    list(genereer_outreach_bericht(student_serie, mentor_naam="M. de Vries", api_key="test-key"))

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "25%" in prompt  # 0.25 * 100 = 25


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_outreach_bericht_met_verwijzing_in_prompt(
    mock_cls: MagicMock, student_serie: pd.Series
) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
    mock_cls.return_value = mock_client

    verwijzing = {"rol": "Financieel spreekuur", "toelichting": "Advies over studiefinanciering"}
    list(
        genereer_outreach_bericht(
            student_serie, mentor_naam="M. de Vries", verwijzing=verwijzing, api_key="test-key"
        )
    )

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "Financieel spreekuur" in prompt


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_outreach_bericht_bsa_op_schema(
    mock_cls: MagicMock,
) -> None:
    """Wanneer bsa_behaald >= bsa_vereist staat de tekst 'op schema' in de prompt."""
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
    mock_cls.return_value = mock_client

    student = pd.Series(
        {
            "naam": "Emma Smit",
            "opleiding": "Zorg",
            "niveau": 2,
            "voortgang": 0.30,
            "bsa_behaald": 40,
            "bsa_vereist": 40,
        }
    )
    list(genereer_outreach_bericht(student, mentor_naam="X", api_key="test-key"))

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "op schema" in prompt
