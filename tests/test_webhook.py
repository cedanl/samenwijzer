"""Tests voor app/webhook.py — TwiML-helpers, CSV-schrijven, handtekeningvalidatie en endpoint."""

import csv
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Zorg dat app/ en src/ op het zoekpad staan
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def csv_pad(tmp_path, monkeypatch):
    """Laat _sla_welzijnscheck_op schrijven naar een tijdelijk bestand."""
    pad = tmp_path / "welzijn.csv"
    import app.webhook as wh

    monkeypatch.setattr(wh, "_WELZIJN_CSV", pad)
    return pad


@pytest.fixture
def client():
    """FastAPI TestClient met nep-token en gemockte handtekeningvalidatie."""
    from app.webhook import app

    with patch.dict("os.environ", {"TWILIO_AUTH_TOKEN": "test_token"}):
        with patch("app.webhook._valideer_twilio_handtekening", return_value=True):
            yield TestClient(app)


# ── _twiml_antwoord ───────────────────────────────────────────────────────────


def test_twiml_antwoord_bevat_bericht() -> None:
    from app.webhook import _twiml_antwoord

    resp = _twiml_antwoord("Hallo student!")
    assert resp.media_type == "application/xml"
    assert b"Hallo student!" in resp.body
    assert b"<Message>" in resp.body
    assert b"<Response>" in resp.body


def test_twiml_antwoord_is_valid_xml() -> None:
    import xml.etree.ElementTree as ET

    from app.webhook import _twiml_antwoord

    resp = _twiml_antwoord("Testbericht")
    root = ET.fromstring(resp.body)
    assert root.tag == "Response"
    assert root.find("Message").text == "Testbericht"


# ── _twiml_leeg ───────────────────────────────────────────────────────────────


def test_twiml_leeg_geeft_lege_response() -> None:
    import xml.etree.ElementTree as ET

    from app.webhook import _twiml_leeg

    resp = _twiml_leeg()
    assert resp.media_type == "application/xml"
    root = ET.fromstring(resp.body)
    assert root.tag == "Response"
    assert len(list(root)) == 0  # geen child-elementen


# ── _sla_welzijnscheck_op ─────────────────────────────────────────────────────


def test_sla_welzijnscheck_op_schrijft_header_bij_nieuw_bestand(csv_pad) -> None:
    from app.webhook import _sla_welzijnscheck_op
    from samenwijzer.wellbeing import WelzijnsCheck

    check = WelzijnsCheck(studentnummer="100001", datum=date(2026, 4, 14), antwoord=2)
    _sla_welzijnscheck_op(check)

    assert csv_pad.exists()
    with csv_pad.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rijen = list(reader)

    assert len(rijen) == 1
    assert rijen[0]["studentnummer"] == "100001"
    assert rijen[0]["datum"] == "2026-04-14"
    assert rijen[0]["antwoord"] == "2"


def test_sla_welzijnscheck_op_voegt_toe_zonder_extra_header(csv_pad) -> None:
    from app.webhook import _sla_welzijnscheck_op
    from samenwijzer.wellbeing import WelzijnsCheck

    _sla_welzijnscheck_op(
        WelzijnsCheck(studentnummer="100001", datum=date(2026, 4, 14), antwoord=1)
    )
    _sla_welzijnscheck_op(
        WelzijnsCheck(studentnummer="100002", datum=date(2026, 4, 15), antwoord=3)
    )

    with csv_pad.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rijen = list(reader)

    assert len(rijen) == 2
    assert rijen[1]["studentnummer"] == "100002"


def test_sla_welzijnscheck_op_toelichting_is_leeg(csv_pad) -> None:
    from app.webhook import _sla_welzijnscheck_op
    from samenwijzer.wellbeing import WelzijnsCheck

    _sla_welzijnscheck_op(
        WelzijnsCheck(studentnummer="100001", datum=date(2026, 4, 14), antwoord=2)
    )

    with csv_pad.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rij = next(reader)
    assert rij["toelichting"] == ""


# ── _valideer_twilio_handtekening ─────────────────────────────────────────────


def test_valideer_handtekening_geldig() -> None:
    import base64
    import hashlib
    import hmac

    from app.webhook import _valideer_twilio_handtekening

    auth_token = "test_token_abc"
    url = "https://example.com/webhook/whatsapp"

    # Bereken de verwachte handtekening zoals Twilio dat doet (over URL zonder params)
    mac = hmac.new(auth_token.encode(), url.encode(), hashlib.sha1)
    handtekening = base64.b64encode(mac.digest()).decode()

    request = MagicMock()
    request.url = url
    request.headers = {"X-Twilio-Signature": handtekening}

    assert _valideer_twilio_handtekening(request, auth_token, {}) is True


def test_valideer_handtekening_ongeldig() -> None:

    from app.webhook import _valideer_twilio_handtekening

    request = MagicMock()
    request.url = "https://example.com/webhook/whatsapp"
    request.headers = {"X-Twilio-Signature": "verkeerde_handtekening"}

    assert _valideer_twilio_handtekening(request, "echte_token", {}) is False


def test_valideer_handtekening_ontbrekende_header() -> None:

    from app.webhook import _valideer_twilio_handtekening

    request = MagicMock()
    request.url = "https://example.com/webhook/whatsapp"
    request.headers = {}  # geen X-Twilio-Signature header

    assert _valideer_twilio_handtekening(request, "token", {}) is False


# ── Endpoint /webhook/whatsapp ────────────────────────────────────────────────


def _maak_verwerk_resultaat(antwoord_tekst=None, welzijns_check=None):
    from samenwijzer.whatsapp import VerwerkResultaat

    return VerwerkResultaat(antwoord_tekst=antwoord_tekst, welzijns_check=welzijns_check)


def test_endpoint_geeft_200_zonder_auth(client) -> None:
    with patch("app.webhook.verwerk_inkomend_bericht") as mock_verwerk:
        mock_verwerk.return_value = _maak_verwerk_resultaat("Hallo!")
        resp = client.post(
            "/webhook/whatsapp",
            data={"From": "whatsapp:+31612345678", "Body": "1"},
        )
    assert resp.status_code == 200


def test_endpoint_geeft_twiml_met_antwoord(client) -> None:
    with patch("app.webhook.verwerk_inkomend_bericht") as mock_verwerk:
        mock_verwerk.return_value = _maak_verwerk_resultaat("Dankjewel voor je bericht!")
        resp = client.post(
            "/webhook/whatsapp",
            data={"From": "whatsapp:+31612345678", "Body": "2"},
        )
    assert b"Dankjewel voor je bericht!" in resp.content
    assert b"<Message>" in resp.content


def test_endpoint_geeft_leeg_twiml_zonder_antwoord(client) -> None:
    with patch("app.webhook.verwerk_inkomend_bericht") as mock_verwerk:
        mock_verwerk.return_value = _maak_verwerk_resultaat(antwoord_tekst=None)
        resp = client.post(
            "/webhook/whatsapp",
            data={"From": "whatsapp:+31612345678", "Body": "xyz"},
        )
    assert resp.status_code == 200
    assert b"<Message>" not in resp.content


def test_endpoint_slaat_welzijnscheck_op(client, csv_pad) -> None:
    from samenwijzer.wellbeing import WelzijnsCheck

    check = WelzijnsCheck(studentnummer="100001", datum=date(2026, 4, 14), antwoord=2)
    with patch("app.webhook.verwerk_inkomend_bericht") as mock_verwerk:
        mock_verwerk.return_value = _maak_verwerk_resultaat("OK", check)
        with patch("app.webhook._sla_welzijnscheck_op") as mock_sla:
            client.post(
                "/webhook/whatsapp",
                data={"From": "whatsapp:+31612345678", "Body": "2"},
            )
    mock_sla.assert_called_once_with(check)


def test_endpoint_slaat_geen_welzijnscheck_op_zonder_check(client) -> None:
    with patch("app.webhook.verwerk_inkomend_bericht") as mock_verwerk:
        mock_verwerk.return_value = _maak_verwerk_resultaat("Stop bevestiging", welzijns_check=None)
        with patch("app.webhook._sla_welzijnscheck_op") as mock_sla:
            client.post(
                "/webhook/whatsapp",
                data={"From": "whatsapp:+31612345678", "Body": "stop"},
            )
    mock_sla.assert_not_called()


def test_endpoint_403_bij_ongeldige_handtekening() -> None:
    from app.webhook import app

    with patch.dict("os.environ", {"TWILIO_AUTH_TOKEN": "echte_token"}):
        with patch("app.webhook._valideer_twilio_handtekening", return_value=False):
            with TestClient(app) as client:
                resp = client.post(
                    "/webhook/whatsapp",
                    data={"From": "whatsapp:+31612345678", "Body": "1"},
                    headers={"X-Twilio-Signature": "fout"},
                )
    assert resp.status_code == 403


def test_endpoint_strip_whatsapp_prefix(client) -> None:
    with patch("app.webhook.verwerk_inkomend_bericht") as mock_verwerk:
        mock_verwerk.return_value = _maak_verwerk_resultaat("OK")
        client.post(
            "/webhook/whatsapp",
            data={"From": "whatsapp:+31612345678", "Body": "1"},
        )
    assert mock_verwerk.call_args.kwargs["from_number"] == "+31612345678"


# ── Security findings ────────────────────────────────────────────────────────


def test_endpoint_403_zonder_auth_token() -> None:
    """Finding 1: ontbrekend token moet 403 geven, niet stiekem doorlaten."""
    from app.webhook import app

    with patch.dict("os.environ", {"TWILIO_AUTH_TOKEN": ""}):
        with TestClient(app) as c:
            resp = c.post(
                "/webhook/whatsapp",
                data={"From": "whatsapp:+31612345678", "Body": "1"},
            )
    assert resp.status_code == 403


def test_valideer_handtekening_gebruikt_form_params() -> None:
    """Finding 2: validator moet form-params meekrijgen, niet een lege dict."""
    import base64
    import hashlib
    import hmac as hmaclib

    from app.webhook import _valideer_twilio_handtekening

    auth_token = "test_token"
    url = "https://example.com/webhook/whatsapp"
    params = {"Body": "1", "From": "whatsapp:+31612345678"}

    # Handtekening berekend zónder params (de kapotte methode)
    mac_leeg = hmaclib.new(auth_token.encode(), url.encode(), hashlib.sha1)
    sig_leeg = base64.b64encode(mac_leeg.digest()).decode()

    request = MagicMock()
    request.url = url
    request.headers = {"X-Twilio-Signature": sig_leeg}

    # Signature over lege dict moet False geven als params wél aanwezig zijn
    assert _valideer_twilio_handtekening(request, auth_token, params) is False


def test_twiml_antwoord_escapet_xml_speciale_tekens() -> None:
    """Finding 3: AI-output met XML-tekens mag TwiML niet corrumperen."""
    import xml.etree.ElementTree as ET

    from app.webhook import _twiml_antwoord

    gevaarlijke_tekst = 'Hoi! <Redirect>http://evil.com</Redirect> &amp; "quoted"'
    resp = _twiml_antwoord(gevaarlijke_tekst)
    root = ET.fromstring(resp.body)
    # Na escaping moet de tekst letterlijk in <Message> staan
    assert root.find("Message").text == gevaarlijke_tekst


# ── Endpoint /health ──────────────────────────────────────────────────────────


def test_health_endpoint(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
