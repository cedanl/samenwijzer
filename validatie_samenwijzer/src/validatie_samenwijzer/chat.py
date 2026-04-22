"""Hybride OER-chat: retrieval + prompt-opbouw + Claude streaming."""

from collections.abc import Generator

import anthropic

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


def embed_vraag(openai_client, vraag: str) -> list[float]:
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
            f"[Pagina {c['metadata'].get('pagina', '?')}]\n{c['tekst']}"
            for c in chunks
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
