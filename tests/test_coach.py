"""Tests voor samenwijzer.coach."""

from unittest.mock import MagicMock, patch

import pytest

from samenwijzer.coach import (
    controleer_antwoorden,
    genereer_lesmateriaal,
    genereer_oefentoets,
    geef_feedback_op_werk,
)


# ── Mock helpers ──────────────────────────────────────────────────────────────


def _mock_stream(tekst: str) -> MagicMock:
    """Bouw een mock-stream die tekst als één fragment yieldt."""
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    mock.text_stream = iter([tekst])
    return mock


def _mock_response(tekst: str) -> MagicMock:
    """Bouw een mock messages.create-response."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=tekst)]
    return mock_msg


# ── genereer_lesmateriaal ─────────────────────────────────────────────────────


@patch("samenwijzer.coach.anthropic.Anthropic")
def test_genereer_lesmateriaal_yield_fragmenten(mock_cls: MagicMock) -> None:
    verwacht = "Hier is het lesmateriaal over zorgverlening."
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _mock_stream(verwacht)
    mock_cls.return_value = mock_client

    resultaat = "".join(
        genereer_lesmateriaal("zorgverlening", "Verzorgende IG", "Gevorderde", api_key="test")
    )

    assert resultaat == verwacht


@patch("samenwijzer.coach.anthropic.Anthropic")
def test_genereer_lesmateriaal_prompt_bevat_onderwerp(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _mock_stream("OK")
    mock_cls.return_value = mock_client

    list(genereer_lesmateriaal("hygiëne", "Horeca", "Starter", api_key="test"))

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "hygiëne" in prompt
    assert "Horeca" in prompt
    assert "Starter" in prompt


@patch("samenwijzer.coach.anthropic.Anthropic")
def test_genereer_lesmateriaal_zwakste_kt_opgenomen(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _mock_stream("OK")
    mock_cls.return_value = mock_client

    list(
        genereer_lesmateriaal(
            "elektra", "Elektrotechniek", "Expert", zwakste_kt="KT2 Installaties", api_key="test"
        )
    )

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "KT2 Installaties" in prompt


# ── genereer_oefentoets ───────────────────────────────────────────────────────


@patch("samenwijzer.coach.anthropic.Anthropic")
def test_genereer_oefentoets_geeft_tekst_terug(mock_cls: MagicMock) -> None:
    toets_tekst = "**Vraag 1:** ...\nANTWOORDEN: 1=A, 2=B, 3=C, 4=D, 5=A"
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response(toets_tekst)
    mock_cls.return_value = mock_client

    resultaat = genereer_oefentoets("wondverzorging", "Verzorgende IG", "Onderweg", api_key="test")

    assert resultaat == toets_tekst


@patch("samenwijzer.coach.anthropic.Anthropic")
def test_genereer_oefentoets_prompt_bevat_onderwerp_en_opleiding(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response("toets")
    mock_cls.return_value = mock_client

    genereer_oefentoets("metaalbewerking", "Metaalbewerker", "Gevorderde", api_key="test")

    prompt = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "metaalbewerking" in prompt
    assert "Metaalbewerker" in prompt


# ── controleer_antwoorden ─────────────────────────────────────────────────────


@patch("samenwijzer.coach.anthropic.Anthropic")
def test_controleer_antwoorden_yield_feedback(mock_cls: MagicMock) -> None:
    feedback = "Vraag 1: goed! Vraag 2: fout."
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _mock_stream(feedback)
    mock_cls.return_value = mock_client

    resultaat = "".join(
        controleer_antwoorden(
            toets_tekst="ANTWOORDEN: 1=A",
            antwoorden={1: "A", 2: "B"},
            opleiding="Verpleging",
            leerpad="Starter",
            api_key="test",
        )
    )

    assert resultaat == feedback


@patch("samenwijzer.coach.anthropic.Anthropic")
def test_controleer_antwoorden_prompt_bevat_antwoorden(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _mock_stream("OK")
    mock_cls.return_value = mock_client

    list(
        controleer_antwoorden(
            toets_tekst="toekst",
            antwoorden={1: "C", 2: "D"},
            opleiding="X",
            leerpad="Y",
            api_key="test",
        )
    )

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "Vraag 1: C" in prompt
    assert "Vraag 2: D" in prompt


# ── geef_feedback_op_werk ─────────────────────────────────────────────────────


@patch("samenwijzer.coach.anthropic.Anthropic")
def test_geef_feedback_op_werk_yield_feedback(mock_cls: MagicMock) -> None:
    feedback = "Goed werk, verbeter de structuur."
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _mock_stream(feedback)
    mock_cls.return_value = mock_client

    resultaat = "".join(
        geef_feedback_op_werk(
            werk="Dit is mijn verslag over stage.",
            opleiding="Zorg en Welzijn",
            leerpad="Onderweg",
            api_key="test",
        )
    )

    assert resultaat == feedback


@patch("samenwijzer.coach.anthropic.Anthropic")
def test_geef_feedback_op_werk_prompt_bevat_werk(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _mock_stream("OK")
    mock_cls.return_value = mock_client

    list(
        geef_feedback_op_werk(
            werk="Mijn stageverslag gaat over...",
            opleiding="Horeca",
            leerpad="Gevorderde",
            api_key="test",
        )
    )

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "Mijn stageverslag gaat over..." in prompt
    assert "Horeca" in prompt
