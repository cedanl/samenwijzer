"""Tests voor samenwijzer.welzijn."""

from unittest.mock import MagicMock, patch

import pytest

from samenwijzer.welzijn import (
    CATEGORIEËN,
    categorie_label,
    genereer_welzijnsreactie,
    urgentie_label,
)


# ── Labels ────────────────────────────────────────────────────────────────────


def test_categorie_label_bekende_codes() -> None:
    assert categorie_label("studieplanning") == "Studieplanning & opdrachten"
    assert categorie_label("welzijn") == "Persoonlijk welzijn"
    assert categorie_label("financiën") == "Financiën"
    assert categorie_label("werkplekleren") == "Stage & werkplekleren"
    assert categorie_label("overig") == "Iets anders"


def test_categorie_label_onbekende_code_geeft_code_terug() -> None:
    assert categorie_label("onbekend") == "onbekend"


def test_alle_categorieën_hebben_label() -> None:
    for cat in CATEGORIEËN:
        label = categorie_label(cat)
        assert label != cat or cat == "overig"  # elke bekende code heeft een ander label


def test_urgentie_label_alle_niveaus() -> None:
    assert urgentie_label(1) == "Kan wachten"
    assert urgentie_label(2) == "Liefst snel"
    assert urgentie_label(3) == "Dringend"


def test_urgentie_label_onbekend_geeft_string_van_int() -> None:
    assert urgentie_label(99) == "99"


# ── genereer_welzijnsreactie ──────────────────────────────────────────────────


def _mock_stream(tekst: str) -> MagicMock:
    """Bouw een mock-stream die de gegeven tekst als één fragment yieldt."""
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    mock.text_stream = iter([tekst])
    return mock


@patch("samenwijzer.welzijn.anthropic.Anthropic")
def test_genereer_welzijnsreactie_yield_tekst(mock_cls: MagicMock) -> None:
    reactie = "Goed dat je dit aangeeft, Ama."
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _mock_stream(reactie)
    mock_cls.return_value = mock_client

    fragmenten = list(
        genereer_welzijnsreactie(
            voornaam="Ama",
            categorie="welzijn",
            toelichting="Ik voel me overweldigd",
            urgentie=2,
            api_key="test-key",
        )
    )

    assert "".join(fragmenten) == reactie


@patch("samenwijzer.welzijn.anthropic.Anthropic")
def test_genereer_welzijnsreactie_prompt_bevat_voornaam(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _mock_stream("OK")
    mock_cls.return_value = mock_client

    list(
        genereer_welzijnsreactie(
            voornaam="Karim",
            categorie="financiën",
            toelichting="",
            urgentie=1,
            api_key="test-key",
        )
    )

    call_kwargs = mock_client.messages.stream.call_args.kwargs
    prompt = call_kwargs["messages"][0]["content"]
    assert "Karim" in prompt


@patch("samenwijzer.welzijn.anthropic.Anthropic")
def test_genereer_welzijnsreactie_prompt_bevat_categorie_label(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _mock_stream("OK")
    mock_cls.return_value = mock_client

    list(
        genereer_welzijnsreactie(
            voornaam="X",
            categorie="werkplekleren",
            toelichting="",
            urgentie=1,
            api_key="test-key",
        )
    )

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "Stage & werkplekleren" in prompt


@patch("samenwijzer.welzijn.anthropic.Anthropic")
def test_genereer_welzijnsreactie_toelichting_opgenomen_als_aanwezig(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _mock_stream("OK")
    mock_cls.return_value = mock_client

    list(
        genereer_welzijnsreactie(
            voornaam="X",
            categorie="overig",
            toelichting="Ik heb problemen thuis",
            urgentie=3,
            api_key="test-key",
        )
    )

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "Ik heb problemen thuis" in prompt


@patch("samenwijzer.welzijn.anthropic.Anthropic")
def test_genereer_welzijnsreactie_lege_toelichting_niet_in_prompt(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _mock_stream("OK")
    mock_cls.return_value = mock_client

    list(
        genereer_welzijnsreactie(
            voornaam="X",
            categorie="overig",
            toelichting="   ",
            urgentie=1,
            api_key="test-key",
        )
    )

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "De student schrijft" not in prompt
