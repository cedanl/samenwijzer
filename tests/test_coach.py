"""Tests voor samenwijzer.coach."""

from unittest.mock import MagicMock, patch

import pytest

from samenwijzer.coach import (
    SCENARIO_OPTIES,
    RollenspelSessie,
    controleer_antwoorden,
    geef_feedback_op_werk,
    genereer_lesmateriaal,
    genereer_oefentoets,
    genereer_rollenspel_feedback,
    genereer_weekplan,
    stuur_rollenspel_bericht,
)
from tests.helpers import mock_stream, mock_stream_fragmenten, mock_stream_met_fout

# ── Mock helpers ──────────────────────────────────────────────────────────────


def _mock_response(tekst: str) -> MagicMock:
    """Bouw een mock messages.create-response."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=tekst)]
    return mock_msg


# ── genereer_lesmateriaal ─────────────────────────────────────────────────────


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_lesmateriaal_yield_fragmenten(mock_cls: MagicMock) -> None:
    verwacht = "Hier is het lesmateriaal over zorgverlening."
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream(verwacht)
    mock_cls.return_value = mock_client

    resultaat = "".join(
        genereer_lesmateriaal("zorgverlening", "Verzorgende IG", "Gevorderde", api_key="test")
    )

    assert resultaat == verwacht


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_lesmateriaal_prompt_bevat_onderwerp(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
    mock_cls.return_value = mock_client

    list(genereer_lesmateriaal("hygiëne", "Horeca", "Starter", api_key="test"))

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "hygiëne" in prompt
    assert "Horeca" in prompt
    assert "Starter" in prompt


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_lesmateriaal_zwakste_kt_opgenomen(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
    mock_cls.return_value = mock_client

    list(
        genereer_lesmateriaal(
            "elektra", "Elektrotechniek", "Expert", zwakste_kt="KT2 Installaties", api_key="test"
        )
    )

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "KT2 Installaties" in prompt


# ── genereer_oefentoets ───────────────────────────────────────────────────────


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_oefentoets_geeft_tekst_terug(mock_cls: MagicMock) -> None:
    toets_tekst = "**Vraag 1:** ...\nANTWOORDEN: 1=A, 2=B, 3=C, 4=D, 5=A"
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response(toets_tekst)
    mock_cls.return_value = mock_client

    resultaat = genereer_oefentoets("wondverzorging", "Verzorgende IG", "Onderweg", api_key="test")

    assert resultaat == toets_tekst


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_oefentoets_prompt_bevat_onderwerp_en_opleiding(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response("toets")
    mock_cls.return_value = mock_client

    genereer_oefentoets("metaalbewerking", "Metaalbewerker", "Gevorderde", api_key="test")

    prompt = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "metaalbewerking" in prompt
    assert "Metaalbewerker" in prompt


# ── controleer_antwoorden ─────────────────────────────────────────────────────


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_controleer_antwoorden_yield_feedback(mock_cls: MagicMock) -> None:
    feedback = "Vraag 1: goed! Vraag 2: fout."
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream(feedback)
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


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_controleer_antwoorden_prompt_bevat_antwoorden(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
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


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_geef_feedback_op_werk_yield_feedback(mock_cls: MagicMock) -> None:
    feedback = "Goed werk, verbeter de structuur."
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream(feedback)
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


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_geef_feedback_op_werk_prompt_bevat_werk(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
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


# ── RollenspelSessie ──────────────────────────────────────────────────────────


def _maak_sessie(scenario: str = "sollicitatie") -> RollenspelSessie:
    return RollenspelSessie(
        scenario=scenario, opleiding="Verzorgende IG", leerpad="Gevorderde", naam="Anna"
    )


def test_rollenspel_sessie_tegenpartij_sollicitatie() -> None:
    assert _maak_sessie("sollicitatie").tegenpartij() == "werkgever"


def test_rollenspel_sessie_tegenpartij_stagegesprek() -> None:
    assert _maak_sessie("stagegesprek").tegenpartij() == "stagebegeleider"


def test_rollenspel_sessie_tegenpartij_beroepssituatie() -> None:
    assert _maak_sessie("beroepssituatie").tegenpartij() == "gesprekspartner"


def test_rollenspel_sessie_tegenpartij_onbekend_scenario() -> None:
    assert _maak_sessie("onbekend").tegenpartij() == "gesprekspartner"


def test_rollenspel_sessie_reset_wist_geschiedenis() -> None:
    sessie = _maak_sessie()
    sessie.geschiedenis = [{"role": "user", "content": "hallo"}]
    sessie.reset()
    assert sessie.geschiedenis == []


def test_scenario_opties_bevat_alle_sleutels() -> None:
    assert set(SCENARIO_OPTIES) == {"sollicitatie", "stagegesprek", "beroepssituatie"}


# ── stuur_rollenspel_bericht ──────────────────────────────────────────────────


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_stuur_rollenspel_bericht_yield_reactie(mock_cls: MagicMock) -> None:
    reactie = "Goedemorgen, vertel eens over jezelf."
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream(reactie)
    mock_cls.return_value = mock_client

    sessie = _maak_sessie()
    resultaat = "".join(stuur_rollenspel_bericht(sessie, "Hallo!", api_key="test"))

    assert resultaat == reactie


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_stuur_rollenspel_bericht_voegt_berichten_toe(mock_cls: MagicMock) -> None:
    reactie = "Interessant!"
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream(reactie)
    mock_cls.return_value = mock_client

    sessie = _maak_sessie()
    list(stuur_rollenspel_bericht(sessie, "Ik wil graag stage lopen.", api_key="test"))

    assert len(sessie.geschiedenis) == 2
    assert sessie.geschiedenis[0] == {"role": "user", "content": "Ik wil graag stage lopen."}
    assert sessie.geschiedenis[1] == {"role": "assistant", "content": reactie}


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_stuur_rollenspel_bericht_stuurt_systeem_prompt(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
    mock_cls.return_value = mock_client

    sessie = _maak_sessie("sollicitatie")
    list(stuur_rollenspel_bericht(sessie, "Goedemorgen.", api_key="test"))

    call_kwargs = mock_client.messages.stream.call_args.kwargs
    assert "system" in call_kwargs
    assert "werkgever" in call_kwargs["system"]


# ── genereer_rollenspel_feedback ──────────────────────────────────────────────


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_rollenspel_feedback_yield_nabespreking(mock_cls: MagicMock) -> None:
    nabespreking = "Je deed het goed! Verbeterpunt: meer doorvragen."
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream(nabespreking)
    mock_cls.return_value = mock_client

    sessie = _maak_sessie()
    sessie.geschiedenis = [
        {"role": "user", "content": "Hallo"},
        {"role": "assistant", "content": "Vertel over jezelf."},
    ]
    resultaat = "".join(genereer_rollenspel_feedback(sessie, api_key="test"))

    assert resultaat == nabespreking


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_rollenspel_feedback_prompt_bevat_gesprek(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
    mock_cls.return_value = mock_client

    sessie = _maak_sessie("stagegesprek")
    sessie.geschiedenis = [
        {"role": "user", "content": "Ik doe mijn best."},
        {"role": "assistant", "content": "Dat waardeer ik."},
    ]
    list(genereer_rollenspel_feedback(sessie, api_key="test"))

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "Ik doe mijn best." in prompt
    assert "Dat waardeer ik." in prompt
    assert "stagegesprek" in prompt.lower() or "Stagegesprek" in prompt


# ── genereer_weekplan ─────────────────────────────────────────────────────────


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_weekplan_yield_tekst(mock_cls: MagicMock) -> None:
    weekplan = "**Weekplan — Yasmin**\n| Maandag | Herhaal theorie | 30 min | Begrip |"
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream(weekplan)
    mock_cls.return_value = mock_client

    resultaat = "".join(
        genereer_weekplan(
            naam="Yasmin",
            opleiding="Verzorgende IG",
            leerpad="Onderweg",
            voortgang=0.55,
            bsa_behaald=33.0,
            bsa_vereist=60.0,
            api_key="test",
        )
    )

    assert resultaat == weekplan


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_weekplan_prompt_bevat_studentprofiel(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
    mock_cls.return_value = mock_client

    list(
        genereer_weekplan(
            naam="Ravi",
            opleiding="Elektrotechniek",
            leerpad="Gevorderde",
            voortgang=0.72,
            bsa_behaald=45.0,
            bsa_vereist=60.0,
            api_key="test",
        )
    )

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "Ravi" in prompt
    assert "Elektrotechniek" in prompt
    assert "Gevorderde" in prompt
    assert "72%" in prompt


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_weekplan_prompt_bevat_aandachtspunten(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
    mock_cls.return_value = mock_client

    list(
        genereer_weekplan(
            naam="Sara",
            opleiding="Horeca",
            leerpad="Starter",
            voortgang=0.30,
            bsa_behaald=15.0,
            bsa_vereist=60.0,
            zwakste_kerntaak="KT1 Gastvrijheid",
            zwakste_werkproces="WP1.2 Serviceverlening",
            api_key="test",
        )
    )

    prompt = mock_client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "KT1 Gastvrijheid" in prompt
    assert "WP1.2 Serviceverlening" in prompt


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_weekplan_zonder_aandachtspunten(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
    mock_cls.return_value = mock_client

    # Geen crash als zwakste_kerntaak en zwakste_werkproces leeg zijn
    resultaat = "".join(
        genereer_weekplan(
            naam="Tim",
            opleiding="Logistiek",
            leerpad="Expert",
            voortgang=0.90,
            bsa_behaald=58.0,
            bsa_vereist=60.0,
            api_key="test",
        )
    )

    assert resultaat == "OK"


# ── Stream-gedrag ─────────────────────────────────────────────────────────────


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_lesmateriaal_meerdere_fragmenten(mock_cls: MagicMock) -> None:
    """Meerdere stream-fragmenten worden correct samengevoegd."""
    fragmenten = ["Deel één. ", "Deel twee. ", "Deel drie."]
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream_fragmenten(fragmenten)
    mock_cls.return_value = mock_client

    resultaat = list(
        genereer_lesmateriaal("zorgverlening", "Verzorgende IG", "Starter", api_key="test")
    )

    assert resultaat == fragmenten
    assert "".join(resultaat) == "Deel één. Deel twee. Deel drie."


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_lesmateriaal_leeg_stream_geeft_niets(mock_cls: MagicMock) -> None:
    """Een lege stream levert geen fragmenten op."""
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream_fragmenten([])
    mock_cls.return_value = mock_client

    resultaat = list(
        genereer_lesmateriaal("zorgverlening", "Verzorgende IG", "Starter", api_key="test")
    )

    assert resultaat == []


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_lesmateriaal_fout_mid_stream_propagates(mock_cls: MagicMock) -> None:
    """Een uitzondering halverwege de stream propagates naar de aanroeper."""
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream_met_fout(
        ["begin van tekst"],
        ConnectionError("verbinding verbroken"),
    )
    mock_cls.return_value = mock_client

    gen = genereer_lesmateriaal("zorgverlening", "Verzorgende IG", "Starter", api_key="test")
    assert next(gen) == "begin van tekst"
    with pytest.raises(ConnectionError):
        next(gen)


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_oefentoets_geeft_volledige_tekst_terug(mock_cls: MagicMock) -> None:
    """genereer_oefentoets gebruikt messages.create en geeft de volledige tekst terug."""
    from samenwijzer.coach import genereer_oefentoets

    toets_tekst = "Vraag 1: ...\nANTWOORDEN: 1=A"
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=toets_tekst)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_cls.return_value = mock_client

    resultaat = genereer_oefentoets("zorgverlening", "Verzorgende IG", "Gevorderde", api_key="test")
    assert resultaat == toets_tekst
