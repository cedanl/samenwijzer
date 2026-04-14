"""FastAPI webhook-endpoint voor inkomende WhatsApp-berichten via Twilio.

Start apart van Streamlit:
    uv run uvicorn app.webhook:app --host 0.0.0.0 --port 8502

Twilio stuurt inkomende berichten als HTTP POST naar /webhook/whatsapp.
De handler verwerkt het bericht, slaat een eventuele WelzijnsCheck op in
data/02-prepared/welzijn.csv, en stuurt het antwoord terug via TwiML.
"""

import csv
import logging
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import Response
from twilio.request_validator import RequestValidator

# Voeg src/ toe aan het zoekpad zodat samenwijzer-modules beschikbaar zijn
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
load_dotenv(Path(__file__).parent.parent / ".env")

from samenwijzer.whatsapp import verwerk_inkomend_bericht  # noqa: E402
from samenwijzer.wellbeing import WelzijnsCheck             # noqa: E402

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Samenwijzer WhatsApp Webhook")

_WELZIJN_CSV = Path(__file__).parent.parent / "data" / "02-prepared" / "welzijn.csv"
_WELZIJN_CSV.parent.mkdir(parents=True, exist_ok=True)

_KOLOMMEN = ["studentnummer", "datum", "antwoord", "toelichting"]


# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def _valideer_twilio_handtekening(request: Request, auth_token: str) -> bool:
    """Valideer de Twilio-handtekening om spoofing te voorkomen."""
    validator = RequestValidator(auth_token)
    url = str(request.url)
    signature = request.headers.get("X-Twilio-Signature", "")
    # Form-parameters zijn al door FastAPI geparsed — geef een lege dict mee
    # omdat Twilio de signature berekent over de URL bij JSON-payload
    return validator.validate(url, {}, signature)


def _sla_welzijnscheck_op(check: WelzijnsCheck) -> None:
    """Voeg een WelzijnsCheck toe aan de welzijn.csv."""
    bestaat = _WELZIJN_CSV.exists()
    with _WELZIJN_CSV.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_KOLOMMEN)
        if not bestaat:
            writer.writeheader()
        writer.writerow({
            "studentnummer": check.studentnummer,
            "datum": check.datum.isoformat(),
            "antwoord": check.antwoord,
            "toelichting": "",
        })
    log.info(
        "WelzijnsCheck opgeslagen: student=%s datum=%s antwoord=%s",
        check.studentnummer, check.datum, check.antwoord,
    )


def _twiml_antwoord(tekst: str) -> Response:
    """Geef een TwiML-antwoord terug dat Twilio verstuurt naar de student."""
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Message>{tekst}</Message>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


def _twiml_leeg() -> Response:
    """Geef een leeg TwiML-antwoord (niets versturen)."""
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response/>',
        media_type="application/xml",
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
) -> Response:
    """Ontvang en verwerk een inkomend WhatsApp-bericht van Twilio.

    Twilio stuurt:
    - From: 'whatsapp:+31612345678'
    - Body: berichttekst van de student
    """
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if auth_token and not _valideer_twilio_handtekening(request, auth_token):
        log.warning("Ongeldige Twilio-handtekening van %s", From)
        raise HTTPException(status_code=403, detail="Ongeldige handtekening")

    # Strip 'whatsapp:'-prefix voor interne verwerking
    from_number = From.removeprefix("whatsapp:")

    log.info("Inkomend bericht van %s: %r", from_number, Body[:50])

    resultaat = verwerk_inkomend_bericht(
        from_number=from_number,
        body=Body,
        ontvangen_op=date.today(),
    )

    if resultaat.welzijns_check:
        _sla_welzijnscheck_op(resultaat.welzijns_check)

    if resultaat.antwoord_tekst:
        return _twiml_antwoord(resultaat.antwoord_tekst)
    return _twiml_leeg()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
