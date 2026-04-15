"""Tests voor samenwijzer.welzijn."""

import smtplib
from unittest.mock import MagicMock, patch

from samenwijzer.welzijn import (
    CATEGORIEËN,
    categorie_label,
    genereer_welzijnsreactie,
    stuur_welzijn_notificatie,
    urgentie_label,
)
from tests.helpers import mock_stream

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


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_welzijnsreactie_yield_tekst(mock_cls: MagicMock) -> None:
    reactie = "Goed dat je dit aangeeft, Ama."
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream(reactie)
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


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_welzijnsreactie_prompt_bevat_voornaam(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
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


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_welzijnsreactie_prompt_bevat_categorie_label(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
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


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_welzijnsreactie_toelichting_opgenomen_als_aanwezig(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
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


@patch("samenwijzer._ai.anthropic.Anthropic")
def test_genereer_welzijnsreactie_lege_toelichting_niet_in_prompt(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream("OK")
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


# ── stuur_welzijn_notificatie ─────────────────────────────────────────────────

_SMTP_CONFIG = {
    "smtp_host": "smtp.test.nl",
    "smtp_port": "587",
    "smtp_user": "noreply@test.nl",
    "smtp_password": "secret",
    "afzender_email": "noreply@test.nl",
    "welzijn_notificatie_email": "mentor@test.nl",
}


@patch("samenwijzer.welzijn.verstuur_email")
@patch("samenwijzer.welzijn.email_config_uit_env")
def test_stuur_notificatie_verstuurt_email(mock_config: MagicMock, mock_mail: MagicMock) -> None:
    mock_config.return_value = _SMTP_CONFIG
    resultaat = stuur_welzijn_notificatie(
        student_naam="Ali Hassan",
        mentor_naam="Piet Jansen",
        categorie="welzijn",
        urgentie=2,
        toelichting="Ik voel me overweldigd",
        timestamp="2026-04-12T10:00:00",
    )
    assert resultaat is True
    mock_mail.assert_called_once()


@patch("samenwijzer.welzijn.verstuur_email")
@patch("samenwijzer.welzijn.email_config_uit_env")
def test_stuur_notificatie_onderwerp_bevat_naam(
    mock_config: MagicMock, mock_mail: MagicMock
) -> None:  # noqa: E501
    mock_config.return_value = _SMTP_CONFIG
    stuur_welzijn_notificatie(
        student_naam="Yasmin Bakr",
        mentor_naam="Piet",
        categorie="financiën",
        urgentie=1,
        toelichting="",
        timestamp="2026-04-12T10:00:00",
    )
    onderwerp = mock_mail.call_args.kwargs["onderwerp"]
    assert "Yasmin Bakr" in onderwerp


@patch("samenwijzer.welzijn.verstuur_email")
@patch("samenwijzer.welzijn.email_config_uit_env")
def test_stuur_notificatie_urgentie_3_dringend(
    mock_config: MagicMock, mock_mail: MagicMock
) -> None:  # noqa: E501
    mock_config.return_value = _SMTP_CONFIG
    stuur_welzijn_notificatie(
        student_naam="Ravi",
        mentor_naam="Mentor",
        categorie="overig",
        urgentie=3,
        toelichting="",
        timestamp="2026-04-12T10:00:00",
    )
    onderwerp = mock_mail.call_args.kwargs["onderwerp"]
    assert "DRINGEND" in onderwerp


@patch("samenwijzer.welzijn.verstuur_email")
@patch("samenwijzer.welzijn.email_config_uit_env")
def test_stuur_notificatie_toelichting_in_bericht(
    mock_config: MagicMock, mock_mail: MagicMock
) -> None:  # noqa: E501
    mock_config.return_value = _SMTP_CONFIG
    stuur_welzijn_notificatie(
        student_naam="X",
        mentor_naam="Y",
        categorie="welzijn",
        urgentie=1,
        toelichting="Ik heb problemen thuis",
        timestamp="2026-04-12T10:00:00",
    )
    bericht = mock_mail.call_args.kwargs["bericht"]
    assert "Ik heb problemen thuis" in bericht


@patch("samenwijzer.welzijn.email_config_uit_env")
def test_stuur_notificatie_geen_smtp_geeft_false(mock_config: MagicMock) -> None:
    mock_config.return_value = {**_SMTP_CONFIG, "smtp_host": "", "smtp_user": ""}
    resultaat = stuur_welzijn_notificatie(
        student_naam="X",
        mentor_naam="Y",
        categorie="welzijn",
        urgentie=1,
        toelichting="",
        timestamp="2026-04-12T10:00:00",
    )
    assert resultaat is False


@patch("samenwijzer.welzijn.email_config_uit_env")
def test_stuur_notificatie_geen_notificatie_email_geeft_false(mock_config: MagicMock) -> None:
    mock_config.return_value = {**_SMTP_CONFIG, "welzijn_notificatie_email": ""}
    resultaat = stuur_welzijn_notificatie(
        student_naam="X",
        mentor_naam="Y",
        categorie="welzijn",
        urgentie=1,
        toelichting="",
        timestamp="2026-04-12T10:00:00",
    )
    assert resultaat is False


@patch("samenwijzer.welzijn.verstuur_email")
@patch("samenwijzer.welzijn.email_config_uit_env")
def test_stuur_notificatie_smtp_fout_geeft_false(
    mock_config: MagicMock, mock_mail: MagicMock
) -> None:  # noqa: E501
    mock_config.return_value = _SMTP_CONFIG
    mock_mail.side_effect = smtplib.SMTPException("verbinding mislukt")
    resultaat = stuur_welzijn_notificatie(
        student_naam="X",
        mentor_naam="Y",
        categorie="welzijn",
        urgentie=2,
        toelichting="",
        timestamp="2026-04-12T10:00:00",
    )
    assert resultaat is False
