"""OER-chat: full-document context + Claude streaming."""

from __future__ import annotations

import logging
import re
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
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        max_tokens=max_tokens,
        output_config={"effort": "medium"},
        messages=berichten,
    ) as stream:
        yield from stream.text_stream


# ── Multi-OER ──────────────────────────────────────────────────────────────────

_MULTI_SYSTEEM_TEMPLATE = """\
Je bent een OER-assistent voor MBO-opleidingen.
Hieronder staan {n} Onderwijs- en Examenregelingen (OERs).
Beantwoord vragen uitsluitend op basis van deze OERs — nooit vanuit eigen kennis.
Geef volledige, goed gestructureerde antwoorden.
Verwijs bij elke claim naar de betreffende OER (gebruik de aanduiding uit de koppen hieronder).
Als de informatie niet in de OERs staat, zeg dat dan expliciet.
Antwoord in het Nederlands.

{oer_blokken}"""


def bouw_gecombineerd_systeem(oer_items: list[dict]) -> str:
    """Bouw een systeemprompt voor één of meerdere OERs.

    Args:
        oer_items: lijst van dict met sleutels 'tekst', 'opleiding',
                   'display_naam', 'leerweg', 'cohort'.
    """
    if len(oer_items) == 1:
        item = oer_items[0]
        return bouw_systeem(item["tekst"], item["opleiding"], item["display_naam"])

    blokken = []
    for i, item in enumerate(oer_items, 1):
        label = (
            f"{item['display_naam']} · {item['opleiding']} "
            f"· {item['leerweg']} {item['cohort']}"
        )
        blokken.append(f"=== OER {i}: {label} ===\n\n{item['tekst']}")
    return _MULTI_SYSTEEM_TEMPLATE.format(
        n=len(oer_items),
        oer_blokken="\n\n---\n\n".join(blokken),
    )


# ── Conversationele OER-identificatie ─────────────────────────────────────────

_INTAKE_SYSTEEM = """\
Je bent een assistent die helpt bij vragen over MBO Onderwijs- en Examenregelingen (OERs).
Je hebt nog geen OER geselecteerd. Om de juiste OER te kunnen raadplegen, heb je nodig:
- Instelling (bijv. Da Vinci, Rijn IJssel, Talland, Aeres, Utrecht)
- Opleiding (naam of crebo-nummer, bijv. Verzorgende IG of 25170)
- Leerweg: BOL of BBL
- Cohort: het startjaar (bijv. 2025)

Vraag vriendelijk naar de ontbrekende informatie. Reageer beknopt. Antwoord in het Nederlands."""


def identificeer_oer_kandidaten(oers: list, tekst: str, min_score: int = 0) -> list[dict]:
    """Geeft OER-kandidaten gesorteerd op match-score (hoogste eerst).

    Scoort op: crebo-nummer (+3), leerweg (+2), cohortjaar (+2),
    opleidingswoorden (+1 elk, max 2), instellingsnaam (+1).
    CamelCase-namen (Da Vinci-stijl) worden gesplitst vóór matching.
    Numerieke tokens worden uitgesloten zodat jaarcijfers niet dubbel tellen.
    """
    tekst_lower = tekst.lower()
    kandidaten = []
    _generiek = {"college", "school", "mbo", "roc"}

    for oer in oers:
        d = dict(oer)
        score = 0

        if d["crebo"] in tekst:
            score += 3

        if d["leerweg"].lower() in tekst_lower:
            score += 2

        if d["cohort"] in tekst:
            score += 2

        # CamelCase split (VerzorgendeIG → Verzorgende IG) + underscore als separator
        opl_gesplit = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", d["opleiding"])
        woorden = [
            w
            for w in re.sub(r"[_\W]+", " ", opl_gesplit).lower().split()
            if len(w) > 3 and not w.isdigit()
        ]
        score += min(sum(1 for w in woorden if w in tekst_lower), 2)

        for deel in d["display_naam"].lower().split():
            if len(deel) >= 4 and deel not in _generiek and deel in tekst_lower:
                score += 1
                break

        if score >= min_score:
            kandidaten.append({**d, "_score": score})

    return sorted(kandidaten, key=lambda x: x["_score"], reverse=True)


def genereer_intake_antwoord(
    client: anthropic.Anthropic,
    berichten: list[dict],
    beschikbare_instellingen: list[str] | None = None,
) -> Generator[str]:
    """Stream een intake-antwoord als nog geen OER is geselecteerd."""
    systeem = _INTAKE_SYSTEEM
    if beschikbare_instellingen:
        systeem += "\n\nBeschikbare instellingen: " + ", ".join(beschikbare_instellingen)
    with client.messages.stream(
        model="claude-sonnet-4-6",
        system=[{"type": "text", "text": systeem, "cache_control": {"type": "ephemeral"}}],
        max_tokens=512,
        messages=berichten,
    ) as stream:
        yield from stream.text_stream
