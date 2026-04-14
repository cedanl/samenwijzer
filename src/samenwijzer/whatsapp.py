"""WhatsApp berichtuitwisseling via Twilio API.

Verantwoordelijkheden:
- Versturen van check-ins, verificaties en foutberichten via Twilio.
- Parsen en routeren van inkomende berichten (score / tekst / stop / ja).
- Beheren van AI-gesprekssessies (max. MAX_EXCHANGES uitwisselingen).
- Opslaan van WelzijnsCheck-resultaten na ontvangst van een score.

AI-isolatie: alle Anthropic-calls lopen via _ai._client().
"""

import logging
import os
from dataclasses import dataclass
from datetime import date
from typing import Literal

from twilio.rest import Client as TwilioClient

from samenwijzer._ai import _client as ai_client
from samenwijzer.wellbeing import WelzijnsCheck
from samenwijzer.whatsapp_store import (
    WhatsappSessie,
    activeer_nummer,
    deactiveer_nummer_via_telefoon,
    get_sessie,
    get_studentnummer_voor_telefoon,
    sla_sessie_op,
    verwijder_sessie,
)

log = logging.getLogger(__name__)

_TWILIO_FROM = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
MAX_EXCHANGES = 3

_CHECKIN_TEKST = (
    "Hoi {naam} 👋 Hoe was jouw week?\n"
    "Antwoord met een cijfer:\n"
    "1 – Goed, ik zit lekker in het ritme\n"
    "2 – Matig, het valt me wat zwaarder\n"
    "3 – Zwaar, ik kan wel wat hulp gebruiken"
)
_VERIFICATIE_TEKST = (
    "Hoi! Je hebt je aangemeld voor de wekelijkse welzijnscheck van Samenwijzer. "
    "Antwoord met JA om te bevestigen, of negeer dit bericht."
)
_FOUTBERICHT_TEKST = (
    "Ik begreep je antwoord niet. Stuur 1, 2 of 3:\n"
    "1 – Goed  |  2 – Matig  |  3 – Zwaar"
)
_DOORVERWIJZING_TEKST = (
    "Bedankt voor het delen 🙏 Je mentor heeft een seintje gekregen. "
    "Voor een uitgebreider gesprek kun je terecht in de Samenwijzer-app."
)
_STOP_BEVESTIGING = "Je bent afgemeld voor de welzijnscheck. Stuur JA als je je opnieuw wilt aanmelden."
_OPT_IN_BEVESTIGING = "Gelukt! Je ontvangt voortaan elke maandag een korte check-in van ons. ✅"
_OPT_IN_GEWEIGERD = "Geen probleem. Je ontvangt geen berichten meer."

_STOP_WOORDEN = {"stop", "stoppen", "afmelden", "unsubscribe"}
_JA_WOORDEN = {"ja", "yes", "j", "ok", "oke", "akkoord", "bevestig"}

_AI_SYSTEEM = (
    "Je bent een empathische studiecoach van Samenwijzer. "
    "Reageer begripvol, in het Nederlands, maximaal 2 zinnen. "
    "Stel één open vraag die de student helpt te reflecteren. "
    "Houd het geschikt voor mobiel (kort en concreet)."
)


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class AntwoordResultaat:
    soort: Literal["score", "tekst", "stop", "ja", "onbekend"]
    score: int | None = None
    tekst: str = ""


@dataclass
class VerwerkResultaat:
    """Resultaat van verwerk_inkomend_bericht."""
    antwoord_tekst: str | None
    welzijns_check: WelzijnsCheck | None


# ── Twilio client ─────────────────────────────────────────────────────────────

def _twilio() -> TwilioClient:
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        raise EnvironmentError(
            "TWILIO_ACCOUNT_SID en TWILIO_AUTH_TOKEN zijn vereist in .env."
        )
    return TwilioClient(sid, token)


def _stuur(to: str, tekst: str) -> None:
    """Verstuur een WhatsApp-bericht. Normaliseert het 'whatsapp:'-prefix."""
    if not to.startswith("whatsapp:"):
        to = f"whatsapp:{to}"
    _twilio().messages.create(body=tekst, from_=_TWILIO_FROM, to=to)
    log.info("WhatsApp verstuurd naar %s (%d tekens)", to, len(tekst))


# ── Publieke verstuurders ─────────────────────────────────────────────────────

def stuur_checkin(naam: str, telefoonnummer: str) -> None:
    """Verstuur de wekelijkse welzijnscheck naar een student."""
    _stuur(telefoonnummer, _CHECKIN_TEKST.format(naam=naam))


def stuur_verificatie(telefoonnummer: str) -> None:
    """Verstuur een opt-in verificatiebericht en registreer een verificatiesessie."""
    sessie = WhatsappSessie(
        from_number=telefoonnummer,
        stap="verificatie",
        uitgewisseld=0,
        context_json="[]",
        gestart_op=date.today().isoformat(),
    )
    sla_sessie_op(sessie)
    _stuur(telefoonnummer, _VERIFICATIE_TEKST)


def stuur_foutbericht(telefoonnummer: str) -> None:
    _stuur(telefoonnummer, _FOUTBERICHT_TEKST)


# ── Berichtparsing ────────────────────────────────────────────────────────────

def parseer_antwoord(body: str) -> AntwoordResultaat:
    """Parseer een inkomend WhatsApp-bericht naar een getypeerd resultaat."""
    tekst = body.strip()
    lower = tekst.lower()

    if lower in _STOP_WOORDEN:
        return AntwoordResultaat(soort="stop")
    if lower in _JA_WOORDEN:
        return AntwoordResultaat(soort="ja")
    if tekst in ("1", "2", "3"):
        return AntwoordResultaat(soort="score", score=int(tekst))
    if len(tekst) > 3:
        return AntwoordResultaat(soort="tekst", tekst=tekst)
    return AntwoordResultaat(soort="onbekend")


# ── Gespreksverwerking ────────────────────────────────────────────────────────

def verwerk_inkomend_bericht(
    from_number: str,
    body: str,
    ontvangen_op: date,
) -> VerwerkResultaat:
    """Verwerk een inkomend WhatsApp-bericht en geef antwoord + eventuele WelzijnsCheck.

    Routing:
    1. STOP-bericht → opt-out verwerken.
    2. Verificatiesessie actief → opt-in bevestigen of weigeren.
    3. Score 1/2/3 → WelzijnsCheck aanmaken; bij 2/3 AI-gesprek starten.
    4. AI-gesprekssessie actief → volgende uitwisseling of doorverwijzen.
    5. Onbekend bericht → foutbericht sturen.

    Args:
        from_number: Telefoonnummer van de afzender (zonder 'whatsapp:'-prefix).
        body: Berichttekst.
        ontvangen_op: Datum van ontvangst.

    Returns:
        VerwerkResultaat met antwoord_tekst (None = niets sturen) en welzijns_check.
    """
    antwoord = parseer_antwoord(body)

    # 1. Opt-out: altijd verwerken, ongeacht sessiestatus
    if antwoord.soort == "stop":
        deactiveer_nummer_via_telefoon(from_number)
        verwijder_sessie(from_number)
        log.info("Opt-out verwerkt voor %s", from_number)
        return VerwerkResultaat(_STOP_BEVESTIGING, None)

    sessie = get_sessie(from_number)

    # 2. Opt-in verificatie
    if sessie and sessie.stap == "verificatie":
        snr = get_studentnummer_voor_telefoon(from_number)
        verwijder_sessie(from_number)
        if antwoord.soort == "ja" and snr:
            activeer_nummer(snr)
            log.info("Opt-in geactiveerd voor student %s", snr)
            return VerwerkResultaat(_OPT_IN_BEVESTIGING, None)
        return VerwerkResultaat(_OPT_IN_GEWEIGERD, None)

    # 3. Check-in score
    if antwoord.soort == "score":
        assert antwoord.score is not None
        snr = get_studentnummer_voor_telefoon(from_number) or from_number
        check = WelzijnsCheck(
            studentnummer=snr,
            datum=ontvangen_op,
            antwoord=antwoord.score,
        )
        if antwoord.score == 1:
            verwijder_sessie(from_number)
            return VerwerkResultaat("Fijn om te horen! Veel succes deze week. 💪", check)

        # Score 2 of 3 → AI-gesprek starten
        nieuwe_sessie = WhatsappSessie(
            from_number=from_number,
            stap="ai_gesprek",
            uitgewisseld=0,
            context_json="[]",
            gestart_op=ontvangen_op.isoformat(),
        )
        sla_sessie_op(nieuwe_sessie)
        return VerwerkResultaat(
            "Dank je voor je eerlijkheid. Wil je even kwijt wat er speelt?",
            check,
        )

    # 4. AI-gesprek lopend
    if sessie and sessie.stap == "ai_gesprek":
        if sessie.uitgewisseld >= MAX_EXCHANGES:
            verwijder_sessie(from_number)
            return VerwerkResultaat(_DOORVERWIJZING_TEKST, None)

        sessie.voeg_bericht_toe("student", body)
        sla_sessie_op(sessie)

        reactie = _genereer_ai_reactie(sessie.context())
        sessie.voeg_bericht_toe("coach", reactie)
        sla_sessie_op(sessie)

        if sessie.uitgewisseld >= MAX_EXCHANGES:
            verwijder_sessie(from_number)
            return VerwerkResultaat(reactie + "\n\n" + _DOORVERWIJZING_TEKST, None)

        return VerwerkResultaat(reactie, None)

    # 5. Onbekend bericht buiten sessiecontext
    if antwoord.soort == "onbekend":
        stuur_foutbericht(from_number)
    return VerwerkResultaat(None, None)


# ── AI ────────────────────────────────────────────────────────────────────────

def _genereer_ai_reactie(context: list[dict]) -> str:
    """Genereer een korte empathische reactie voor WhatsApp (max. 2 zinnen)."""
    berichten = [
        {
            "role": "user" if m["rol"] == "student" else "assistant",
            "content": m["tekst"],
        }
        for m in context
        if m["rol"] in ("student", "coach")
    ]
    reactie = ai_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        system=_AI_SYSTEEM,
        messages=berichten,
    )
    return reactie.content[0].text
