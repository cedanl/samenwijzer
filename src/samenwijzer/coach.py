"""AI Leercoach: gepersonaliseerd lesmateriaal, oefentoets en werkfeedback."""

import os
from collections.abc import Generator

import anthropic

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 2048


def _client(api_key: str | None = None) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))


def genereer_lesmateriaal(
    onderwerp: str,
    opleiding: str,
    leerpad: str,
    zwakste_kt: str = "",
    *,
    api_key: str | None = None,
) -> Generator[str, None, None]:
    """Stream gepersonaliseerd lesmateriaal over een onderwerp.

    Args:
        onderwerp: Het onderwerp of de kerntaak om uitleg over te genereren.
        opleiding: De opleiding van de student.
        leerpad: Het leerpadniveau (Starter/Onderweg/Gevorderde/Expert).
        zwakste_kt: Optionele naam van de zwakste kerntaak voor extra context.

    Yields:
        Tekstfragmenten van het gegenereerde lesmateriaal.
    """
    context = f"opleiding {opleiding}, leerpadniveau {leerpad}"
    if zwakste_kt:
        context += f", met extra aandacht voor {zwakste_kt}"

    prompt = (
        f"Maak uitgebreid lesmateriaal over het onderwerp: **{onderwerp}**.\n"
        f"De student volgt {context}.\n"
        "Gebruik eenvoudige MBO-taal met concrete voorbeelden uit het vakgebied. "
        "Structureer de tekst met kopjes. "
        "Voeg aan het einde 2-3 reflectievragen toe om begrip te toetsen."
    )

    client = _client(api_key)
    with client.messages.stream(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        yield from stream.text_stream


def genereer_oefentoets(
    onderwerp: str,
    opleiding: str,
    leerpad: str,
    *,
    api_key: str | None = None,
) -> str:
    """Genereer 5 multiple-choice vragen over een onderwerp.

    Returns:
        Volledige toekst inclusief antwoordsleutel na het scheidingsteken ANTWOORDEN:.
    """
    prompt = (
        f"Maak een oefentoets van precies 5 multiple-choice vragen over: **{onderwerp}**.\n"
        f"De student volgt {opleiding} op {leerpad}-niveau.\n"
        "Elke vraag heeft 4 antwoordopties (A, B, C, D).\n"
        "Gebruik dit formaat voor elke vraag:\n\n"
        "**Vraag 1:** [vraagtekst]\n"
        "A. [optie A]\n"
        "B. [optie B]\n"
        "C. [optie C]\n"
        "D. [optie D]\n\n"
        "Geef NA alle 5 vragen op een aparte regel de antwoordsleutel in exact dit formaat:\n"
        "ANTWOORDEN: 1=A, 2=C, 3=B, 4=D, 5=A"
    )

    client = _client(api_key)
    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def controleer_antwoorden(
    toets_tekst: str,
    antwoorden: dict[int, str],
    opleiding: str,
    leerpad: str,
    *,
    api_key: str | None = None,
) -> Generator[str, None, None]:
    """Stream feedback op de ingevulde toetsantwoorden.

    Args:
        toets_tekst: De volledige toekst inclusief antwoordsleutel.
        antwoorden: Dict met vraagnummer (1-5) als sleutel en gekozen optie (A-D) als waarde.
        opleiding: De opleiding van de student.
        leerpad: Het leerpadniveau van de student.

    Yields:
        Tekstfragmenten van de feedback.
    """
    antwoorden_tekst = ", ".join(
        f"Vraag {k}: {v}" for k, v in sorted(antwoorden.items())
    )

    prompt = (
        f"Dit is de oefentoets:\n{toets_tekst}\n\n"
        f"De student ({opleiding}, {leerpad}-niveau) gaf deze antwoorden: {antwoorden_tekst}\n\n"
        "Geef per vraag aan of het antwoord goed of fout is en leg kort uit waarom. "
        "Sluit af met het totaalaantal goede antwoorden en een motiverende opmerking."
    )

    client = _client(api_key)
    with client.messages.stream(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        yield from stream.text_stream


def geef_feedback_op_werk(
    werk: str,
    opleiding: str,
    leerpad: str,
    *,
    api_key: str | None = None,
) -> Generator[str, None, None]:
    """Stream constructieve feedback op ingeleverd werk van een student.

    Args:
        werk: De tekst van het ingeleverde werk.
        opleiding: De opleiding van de student.
        leerpad: Het leerpadniveau van de student.

    Yields:
        Tekstfragmenten van de feedback.
    """
    prompt = (
        f"Geef constructieve feedback op het volgende werk van een MBO-student "
        f"({opleiding}, {leerpad}-niveau).\n\n"
        "Beoordeel achtereenvolgens: inhoud en vakkennis, structuur en opbouw, "
        "taalgebruik en leesbaarheid. "
        "Geef per onderdeel een concreet verbeterpunt. "
        "Sluit af met één positief punt dat de student kan vasthouden.\n\n"
        f"Werk van de student:\n{werk}"
    )

    client = _client(api_key)
    with client.messages.stream(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        yield from stream.text_stream
