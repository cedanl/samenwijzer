"""Tests voor samenwijzer.tutor."""

from unittest.mock import MagicMock, patch

import pytest

from samenwijzer.tutor import StudentContext, TutorSessie, stuur_bericht
from tests.helpers import mock_stream, mock_stream_fragmenten, mock_stream_met_fout


@pytest.fixture
def student() -> StudentContext:
    return StudentContext(
        naam="Testine Jansen",
        opleiding="Verzorgende IG",
        niveau=3,
        voortgang=0.70,
    )


@pytest.fixture
def sessie(student) -> TutorSessie:
    return TutorSessie(student=student)


# ── StudentContext ─────────────────────────────────────────────────────────────


def test_student_context_als_tekst(student):
    tekst = student.als_tekst()
    assert "Testine Jansen" in tekst
    assert "Verzorgende IG" in tekst
    assert "70%" in tekst
    assert "gevorderde" in tekst


def test_student_context_als_tekst_met_focus():
    ctx = StudentContext(naam="A", opleiding="B", niveau=2, voortgang=0.5, kerntaak_focus="KT1")
    assert "KT1" in ctx.als_tekst()


def test_student_context_niveau_labels():
    for niveau, label in [(1, "starter"), (2, "op weg"), (3, "gevorderde"), (4, "expert")]:
        ctx = StudentContext(naam="X", opleiding="Y", niveau=niveau, voortgang=0.5)
        assert label in ctx.als_tekst()


# ── TutorSessie ───────────────────────────────────────────────────────────────


def test_sessie_voeg_toe(sessie):
    sessie.voeg_toe("user", "Hallo")
    assert len(sessie.geschiedenis) == 1
    assert sessie.geschiedenis[0] == {"role": "user", "content": "Hallo"}


def test_sessie_voeg_toe_meerdere(sessie):
    sessie.voeg_toe("user", "Vraag")
    sessie.voeg_toe("assistant", "Antwoord")
    assert len(sessie.geschiedenis) == 2


def test_sessie_reset(sessie):
    sessie.voeg_toe("user", "iets")
    sessie.reset()
    assert sessie.geschiedenis == []
    assert sessie.student.naam == "Testine Jansen"  # context bewaard


# ── stuur_bericht ─────────────────────────────────────────────────────────────


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_stuur_bericht_yield_fragmenten(mock_anthropic_cls, sessie):
    reactie_tekst = "Wat denk jij zelf?"
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream(reactie_tekst)
    mock_anthropic_cls.return_value = mock_client

    fragmenten = list(stuur_bericht(sessie, "Ik snap het niet.", api_key="test-key"))

    assert len(fragmenten) > 0
    assert "".join(fragmenten) == reactie_tekst


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_stuur_bericht_update_geschiedenis(mock_anthropic_cls, sessie):
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("Goed zo!")
    mock_anthropic_cls.return_value = mock_client

    list(stuur_bericht(sessie, "Mijn vraag.", api_key="test-key"))

    assert len(sessie.geschiedenis) == 2
    assert sessie.geschiedenis[0] == {"role": "user", "content": "Mijn vraag."}
    assert sessie.geschiedenis[1]["role"] == "assistant"
    assert "Goed" in sessie.geschiedenis[1]["content"]


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_stuur_bericht_meerdere_beurten(mock_anthropic_cls, sessie):
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("Prima.")
    mock_anthropic_cls.return_value = mock_client

    list(stuur_bericht(sessie, "Eerste vraag.", api_key="test-key"))

    mock_client.messages.stream.return_value = mock_stream("Precies.")
    list(stuur_bericht(sessie, "Tweede vraag.", api_key="test-key"))

    assert len(sessie.geschiedenis) == 4
    rollen = [b["role"] for b in sessie.geschiedenis]
    assert rollen == ["user", "assistant", "user", "assistant"]


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_stuur_bericht_gebruikt_student_context(mock_anthropic_cls, sessie):
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
    mock_anthropic_cls.return_value = mock_client

    list(stuur_bericht(sessie, "Test.", api_key="test-key"))

    call_kwargs = mock_client.messages.stream.call_args.kwargs
    system_text = call_kwargs["system"][0]["text"]
    assert "Testine Jansen" in system_text
    assert "Verzorgende IG" in system_text


# ── Stream-gedrag ─────────────────────────────────────────────────────────────


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_stuur_bericht_meerdere_fragmenten(
    mock_anthropic_cls: MagicMock, student: StudentContext
) -> None:
    """Meerdere stream-fragmenten worden correct doorgegeven."""
    fragmenten = ["Goedemorgen! ", "Hier is ", "je antwoord."]
    sessie = TutorSessie(student=student)
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream_fragmenten(fragmenten)
    mock_anthropic_cls.return_value = mock_client

    resultaat = list(stuur_bericht(sessie, "Hoi", api_key="test-key"))

    assert resultaat == fragmenten


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_stuur_bericht_leeg_stream(mock_anthropic_cls: MagicMock, student: StudentContext) -> None:
    """Een lege stream levert een lege lijst op."""
    sessie = TutorSessie(student=student)
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream_fragmenten([])
    mock_anthropic_cls.return_value = mock_client

    resultaat = list(stuur_bericht(sessie, "Hoi", api_key="test-key"))

    assert resultaat == []


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_stuur_bericht_fout_mid_stream_propagates(
    mock_anthropic_cls: MagicMock, student: StudentContext
) -> None:
    """Een uitzondering halverwege de stream propagates naar de aanroeper."""
    sessie = TutorSessie(student=student)
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream_met_fout(
        ["begin..."], TimeoutError("timeout")
    )
    mock_anthropic_cls.return_value = mock_client

    gen = stuur_bericht(sessie, "Hoi", api_key="test-key")
    assert next(gen) == "begin..."
    with pytest.raises(TimeoutError):
        next(gen)
