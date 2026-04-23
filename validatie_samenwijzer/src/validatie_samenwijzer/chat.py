"""Hybride OER-chat: retrieval + prompt-opbouw + Claude streaming."""

from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path

import anthropic
import openai

logger = logging.getLogger(__name__)

MIN_RELEVANTE_CHUNKS = 2  # minimaal aantal chunks voor chunk-gebaseerd antwoord
_MAX_OER_TEKST_TEKENS = 100_000  # maximaal aantal tekens van volledige OER als context

LAGE_RELEVANTIE_BERICHT = (
    "Ik kon geen relevante informatie over deze vraag vinden in jouw OER. "
    "Controleer of de vraag betrekking heeft op jouw opleiding, of raadpleeg "
    "het volledige OER via 'Mijn OER'."
)

_SYSTEEM_TEMPLATE = (
    "Je bent een OER-assistent voor de opleiding {opleiding} bij {instelling}. "
    "Beantwoord vragen uitsluitend op basis van de aangeleverde OER-passages. "
    "Als de passages onvoldoende informatie bevatten, zeg dat dan expliciet. "
    "Antwoord in het Nederlands, beknopt en helder."
)

_VOLLEDIG_OER_SYSTEEM_TEMPLATE = (
    "Je bent een OER-assistent voor de opleiding {opleiding} bij {instelling}. "
    "Beantwoord vragen op basis van de volledige OER-tekst hieronder. "
    "Wees volledig en accuraat. Antwoord in het Nederlands."
)


def embed_vraag(openai_client: openai.OpenAI, vraag: str) -> list[float]:
    """Maak een embedding van de gebruikersvraag."""
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=vraag,
    )
    return response.data[0].embedding


def bouw_berichten(
    chat_history: list[dict],
    chunks: list[dict],
    vraag: str,
    opleiding: str,
    instelling: str,
) -> list[dict]:
    """Bouw de berichtenlijst op voor de Claude API."""
    systeem = _SYSTEEM_TEMPLATE.format(opleiding=opleiding, instelling=instelling)

    if chunks:
        passages = "\n\n".join(
            f"[Pagina {c['metadata'].get('pagina', '?')}]\n{c['tekst']}" for c in chunks
        )
        context = f"{systeem}\n\nRelevante OER-passages:\n{passages}"
    else:
        context = systeem

    berichten = list(chat_history)

    if not berichten:
        eerste_vraag = f"{context}\n\nVraag: {vraag}"
        berichten.append({"role": "user", "content": eerste_vraag})
    else:
        berichten.append({"role": "user", "content": vraag})

    return berichten


def laad_oer_tekst(bestandspad: Path) -> str:
    """Laad de volledige OER-tekst uit het bestand. Geeft lege string bij fout."""
    if not bestandspad.exists():
        return ""
    suffix = bestandspad.suffix.lower()
    if suffix == ".txt":
        return bestandspad.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        try:
            import pdfplumber

            tekst_delen = []
            with pdfplumber.open(str(bestandspad)) as pdf:
                for pagina in pdf.pages:
                    t = pagina.extract_text()
                    if t:
                        tekst_delen.append(t)
            return "\n\n".join(tekst_delen)
        except Exception as e:
            logger.warning("PDF lezen mislukt voor '%s': %s", bestandspad, e)
            return ""
    return ""


def bouw_berichten_volledig(
    chat_history: list[dict],
    oer_tekst: str,
    vraag: str,
    opleiding: str,
    instelling: str,
) -> list[dict]:
    """Bouw berichtenlijst op met de volledige OER-tekst als context."""
    systeem = _VOLLEDIG_OER_SYSTEEM_TEMPLATE.format(opleiding=opleiding, instelling=instelling)
    tekst = oer_tekst[:_MAX_OER_TEKST_TEKENS]
    context = f"{systeem}\n\nVolledig OER:\n{tekst}"

    berichten = list(chat_history)
    if not berichten:
        berichten.append({"role": "user", "content": f"{context}\n\nVraag: {vraag}"})
    else:
        berichten.append({"role": "user", "content": vraag})
    return berichten


def genereer_antwoord(
    client: anthropic.Anthropic,
    berichten: list[dict],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1024,
) -> Generator[str]:
    """Stream Claude-antwoord als generator van tekst-fragmenten."""
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        messages=berichten,
    ) as stream:
        yield from stream.text_stream
