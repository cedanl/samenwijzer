"""Tests voor samenwijzer.auth — mentorfiltering en rolcontrole."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


@pytest.fixture
def df_studenten() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "studentnummer": ["100001", "100002", "100003"],
            "naam": ["Anna Bakker", "Ben Smit", "Cara Lund"],
            "mentor": ["M. de Vries", "J. Janssen", "M. de Vries"],
        }
    )


# ── mentor_filter ─────────────────────────────────────────────────────────────


def test_mentor_filter_geeft_alleen_eigen_studenten(df_studenten) -> None:
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {"mentor_naam": "M. de Vries"}
        from samenwijzer.auth import mentor_filter

        resultaat = mentor_filter(df_studenten)

    assert len(resultaat) == 2
    assert set(resultaat["studentnummer"]) == {"100001", "100003"}


def test_mentor_filter_sluit_andere_mentor_uit(df_studenten) -> None:
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {"mentor_naam": "J. Janssen"}
        from samenwijzer.auth import mentor_filter

        resultaat = mentor_filter(df_studenten)

    assert len(resultaat) == 1
    assert resultaat.iloc[0]["studentnummer"] == "100002"


def test_mentor_filter_zonder_mentor_geeft_volledig_df(df_studenten) -> None:
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {}
        from samenwijzer.auth import mentor_filter

        resultaat = mentor_filter(df_studenten)

    assert len(resultaat) == 3


def test_mentor_filter_met_none_geeft_volledig_df(df_studenten) -> None:
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {"mentor_naam": None}
        from samenwijzer.auth import mentor_filter

        resultaat = mentor_filter(df_studenten)

    assert len(resultaat) == 3


def test_mentor_filter_onbekende_mentor_geeft_leeg_df(df_studenten) -> None:
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {"mentor_naam": "Onbekende Mentor"}
        from samenwijzer.auth import mentor_filter

        resultaat = mentor_filter(df_studenten)

    assert resultaat.empty


def test_mentor_filter_reset_index(df_studenten) -> None:
    """Index van gefilterd resultaat begint bij 0."""
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {"mentor_naam": "M. de Vries"}
        from samenwijzer.auth import mentor_filter

        resultaat = mentor_filter(df_studenten)

    assert list(resultaat.index) == [0, 1]


def test_mentor_filter_leeg_dataframe() -> None:
    leeg = pd.DataFrame(columns=["studentnummer", "naam", "mentor"])
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {"mentor_naam": "M. de Vries"}
        from samenwijzer.auth import mentor_filter

        resultaat = mentor_filter(leeg)

    assert resultaat.empty


# ── bezit_student / vereist_eigen_student ─────────────────────────────────────


def test_bezit_student_true_voor_eigen_student(df_studenten) -> None:
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {"mentor_naam": "M. de Vries"}
        from samenwijzer.auth import bezit_student

        assert bezit_student(df_studenten, "100001") is True


def test_bezit_student_false_voor_andere_mentor(df_studenten) -> None:
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {"mentor_naam": "M. de Vries"}
        from samenwijzer.auth import bezit_student

        assert bezit_student(df_studenten, "100002") is False  # hoort bij J. Janssen


def test_bezit_student_onbekend_studentnummer_is_false(df_studenten) -> None:
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {"mentor_naam": "M. de Vries"}
        from samenwijzer.auth import bezit_student

        assert bezit_student(df_studenten, "999999") is False


def test_bezit_student_zonder_mentor_ziet_iedereen(df_studenten) -> None:
    """Admin-rol zonder mentor_naam: mentor_filter geeft alles → bezit alles."""
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {}
        from samenwijzer.auth import bezit_student

        assert bezit_student(df_studenten, "100002") is True


def test_vereist_eigen_student_stopt_niet_bij_eigen_student(df_studenten) -> None:
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {"mentor_naam": "M. de Vries"}
        mock_st.stop = MagicMock()
        from samenwijzer.auth import vereist_eigen_student

        vereist_eigen_student(df_studenten, "100001")

    mock_st.stop.assert_not_called()


def test_vereist_eigen_student_stopt_bij_vreemde_student(df_studenten) -> None:
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {"mentor_naam": "M. de Vries"}
        mock_st.stop = MagicMock()
        mock_st.error = MagicMock()
        from samenwijzer.auth import vereist_eigen_student

        vereist_eigen_student(df_studenten, "100002")

    mock_st.stop.assert_called_once()
    mock_st.error.assert_called_once()


# ── vereist_docent ────────────────────────────────────────────────────────────


def test_vereist_docent_stopt_niet_bij_docent_rol() -> None:
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {"rol": "docent"}
        mock_st.stop = MagicMock()
        from samenwijzer.auth import vereist_docent

        vereist_docent()

    mock_st.stop.assert_not_called()


def test_vereist_docent_roept_stop_aan_bij_student_rol() -> None:
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {"rol": "student"}
        mock_st.stop = MagicMock()
        mock_st.error = MagicMock()
        mock_st.page_link = MagicMock()
        from samenwijzer.auth import vereist_docent

        vereist_docent()

    mock_st.stop.assert_called_once()


def test_vereist_docent_roept_stop_aan_zonder_rol() -> None:
    with patch("samenwijzer.auth.st") as mock_st:
        mock_st.session_state = {}
        mock_st.stop = MagicMock()
        mock_st.error = MagicMock()
        mock_st.page_link = MagicMock()
        from samenwijzer.auth import vereist_docent

        vereist_docent()

    mock_st.stop.assert_called_once()
