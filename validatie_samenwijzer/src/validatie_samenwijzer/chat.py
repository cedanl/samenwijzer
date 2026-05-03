"""OER-chat: full-document context + Claude streaming."""

from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

_MAX_OER_TEKST_TEKENS = 500_000  # ruim voldoende voor elke OER binnen Sonnet 4.6 (1M context)

LAGE_RELEVANTIE_BERICHT = (
    "Ik kon geen OER-tekst laden voor deze student. "
    "Controleer of het OER-bestand beschikbaar is, of raadpleeg het via 'Mijn OER'."
)

_SYSTEEM_TEMPLATE = """\
Je bent een OER-assistent voor de opleiding {opleiding} bij {instelling}.
Hieronder staat de volledige Onderwijs- en Examenregeling (OER).
Beantwoord vragen uitsluitend op basis van deze OER — nooit vanuit eigen kennis.
Geef volledige, goed gestructureerde antwoorden met kopjes of opsommingen waar dat helpt.
Verwijs bij elke claim naar de sectie of het paginanummer uit de OER
(bijv. "Volgens sectie 3.2…" of "Op pagina 12 staat…").
Als de informatie niet in de OER staat, zeg dat dan expliciet.
Antwoord in het Nederlands.

OER:
{oer_tekst}"""


def laad_oer_tekst(bestandspad: Path) -> str:
    """Laad de OER-tekst voor gebruik als chatcontext.

    Prioriteit: .md-broertje (markitdown-kwaliteit) → .md zelf → PDF via pdfplumber.

    Args:
        bestandspad: Pad naar het OER-bestand (PDF of Markdown).

    Returns:
        Volledige OER-tekst als string, of lege string als niets beschikbaar is.
    """
    if not bestandspad.exists() and bestandspad.suffix.lower() != ".md":
        # Probeer het .md-broertje ook als het bronbestand zelf ontbreekt
        md_pad = bestandspad.with_suffix(".md")
        if md_pad.exists():
            return md_pad.read_text(encoding="utf-8", errors="replace")[:_MAX_OER_TEKST_TEKENS]
        return ""

    suffix = bestandspad.suffix.lower()

    if suffix == ".md":
        return bestandspad.read_text(encoding="utf-8", errors="replace")[:_MAX_OER_TEKST_TEKENS]

    if suffix == ".pdf":
        # Voorkeur: naastliggend .md-bestand van markitdown-conversie
        md_pad = bestandspad.with_suffix(".md")
        if md_pad.exists():
            return md_pad.read_text(encoding="utf-8", errors="replace")[:_MAX_OER_TEKST_TEKENS]
        # Fallback: pdfplumber
        try:
            import pdfplumber

            tekst_delen = []
            with pdfplumber.open(str(bestandspad)) as pdf:
                for pagina in pdf.pages:
                    t = pagina.extract_text()
                    if t:
                        tekst_delen.append(t)
            return "\n\n".join(tekst_delen)[:_MAX_OER_TEKST_TEKENS]
        except Exception as e:
            logger.warning("PDF lezen mislukt voor '%s': %s", bestandspad, e)
            return ""

    return ""


def bouw_systeem(oer_tekst: str, opleiding: str, instelling: str) -> str:
    """Stel de systeemprompt samen met de volledige OER als context."""
    return _SYSTEEM_TEMPLATE.format(
        opleiding=opleiding,
        instelling=instelling,
        oer_tekst=oer_tekst,
    )


def bouw_berichten(chat_history: list[dict], vraag: str) -> list[dict]:
    """Voeg de nieuwe vraag toe aan de gesprekshistorie."""
    berichten = list(chat_history)
    berichten.append({"role": "user", "content": vraag})
    return berichten


def genereer_antwoord(
    client: anthropic.Anthropic,
    system: str,
    berichten: list[dict],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 2048,
) -> Generator[str]:
    """Stream Claude-antwoord als generator van tekst-fragmenten.

    Args:
        client: Geïnitialiseerde Anthropic-client.
        system: Systeemprompt met OER-context.
        berichten: Gesprekshistorie als lijst van rol/content-dicts.
        model: Claude-model ID.
        max_tokens: Maximum aantal tokens in het antwoord.

    Yields:
        Tekst-fragmenten van het gestreamde antwoord.
    """
    with client.messages.stream(
        model=model,
        system=system,
        max_tokens=max_tokens,
        output_config={"effort": "medium"},
        messages=berichten,
    ) as stream:
        yield from stream.text_stream
