"""OER-chat: full-document context + Claude streaming."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Generator
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

_MAX_OER_TEKST_TEKENS = 500_000  # ruim voldoende voor elke OER binnen Sonnet 4.6 (1M context)
_MAX_DOSSIER_TEKST_TEKENS = 300_000

LAGE_RELEVANTIE_BERICHT = (
    "Ik kon geen OER-tekst laden voor deze student. "
    "Controleer of het OER-bestand beschikbaar is, of raadpleeg het via 'Mijn OER'."
)

_SYSTEEM_TEMPLATE = """\
Je bent een onderwijs-assistent voor de opleiding {opleiding} bij {instelling}.

PRIMAIRE BRON — de Onderwijs- en Examenregeling (OER) van deze opleiding.
Dit is het leidende, schoolspecifieke document. Beantwoord vragen primair op
basis van de OER.

AANVULLENDE BRON — het landelijke kwalificatiedossier (KD). Raadpleeg het KD
alléén als de OER het onderwerp niet of onvoldoende behandelt. Geef niet
onnodig een tweede antwoord uit het KD als de OER de vraag al beantwoordt —
de OER is leidend.

CITATIEPLICHT (de OER is een juridisch document).
Bij ELKE claim die je doet, MOET je:
1. de bron noemen ("Volgens de OER" of "Volgens het kwalificatiedossier"),
2. de exacte vindplaats noemen — sectie-nummer, kopje, artikel of paginanummer,
3. de relevante passage WOORDELIJK citeren tussen dubbele aanhalingstekens.

Voorbeeld OER: Volgens de OER, sectie 3.2 "Bindend studieadvies": "De student
ontvangt uiterlijk in juli van het eerste studiejaar een bindend studieadvies."

Voorbeeld KD: De OER beschrijft dit niet. Volgens het kwalificatiedossier,
kerntaak B1-K1 "Bieden van zorg en ondersteuning": "...".

Een claim zonder bron + vindplaats + woordelijk citaat is niet toegestaan.
Parafraseren mag alleen ter inleiding van een citaat, niet ter vervanging ervan.
Als een passage te lang is, citeer dan een representatief fragment en geef de
vindplaats van de rest. Beantwoord vragen uitsluitend op basis van deze bronnen
— nooit vanuit eigen kennis. Als de informatie in geen van beide bronnen staat,
zeg dat dan expliciet. Antwoord in het Nederlands.

=== ONDERWIJS- EN EXAMENREGELING (OER) ===
{oer_tekst}{dossier_blok}"""

_DOSSIER_BLOK_TEMPLATE = "\n\n=== KWALIFICATIEDOSSIER (Crebo {crebo}) ===\n{dossier_tekst}"


def resolve_oer_pad(bestandspad: str) -> Path:
    """Maak een DB-`bestandspad` (relatief, bv. `oeren/talland_oeren/x.pdf`) absoluut.

    De DB bewaart paden onder de oeren/-tree. OEREN_PAD wijst naar die tree
    (default `oeren`, na de root-dedupe `../oeren` vanuit validatie_samenwijzer/).
    De parent van OEREN_PAD is de bovenliggende projectroot — daarmee wordt
    `oeren/...` correct geresolved naar het echte bestand.
    """
    pad = Path(bestandspad)
    if pad.is_absolute():
        return pad
    return Path(os.environ.get("OEREN_PAD", "oeren")).resolve().parent / pad


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


def pad_kwalificatiedossier(crebo: str) -> Path:
    """Pad naar het markdown-bestand van het kwalificatiedossier voor een crebo.

    Default: ``<repo-root>/kwalificatiedossiers/pdfs/<crebo>.md``. Override via
    ``KWALDOSSIERS_PAD`` (absolute of relatief; valt terug op default als de
    env-var ontbreekt).
    """
    base = os.environ.get("KWALDOSSIERS_PAD")
    if base:
        directory = Path(base).resolve()
    else:
        # chat.py → parents[3] = repo-root → kwalificatiedossiers/pdfs
        directory = (
            Path(__file__).resolve().parents[3] / "kwalificatiedossiers" / "pdfs"
        )
    return directory / f"{crebo}.md"


def laad_kwalificatiedossier_tekst(crebo: str | None) -> str:
    """Laad de markdown-tekst van een kwalificatiedossier op crebo, of lege string."""
    if not crebo:
        return ""
    md_pad = pad_kwalificatiedossier(str(crebo))
    if not md_pad.exists():
        return ""
    return md_pad.read_text(encoding="utf-8", errors="replace")[:_MAX_DOSSIER_TEKST_TEKENS]


def bouw_systeem(
    oer_tekst: str,
    opleiding: str,
    instelling: str,
    dossier_tekst: str = "",
    crebo: str | None = None,
) -> str:
    """Stel de systeemprompt samen met OER en optioneel kwalificatiedossier als context."""
    dossier_blok = ""
    if dossier_tekst:
        dossier_blok = _DOSSIER_BLOK_TEMPLATE.format(
            crebo=crebo or "onbekend",
            dossier_tekst=dossier_tekst,
        )
    return _SYSTEEM_TEMPLATE.format(
        opleiding=opleiding,
        instelling=instelling,
        oer_tekst=oer_tekst,
        dossier_blok=dossier_blok,
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
Je bent een onderwijs-assistent voor MBO-opleidingen.
Hieronder staan {n} Onderwijs- en Examenregelingen (OERs), elk waar beschikbaar
gevolgd door het bijbehorende kwalificatiedossier (KD).

PRIMAIRE BRON — de OERs (schoolspecifieke afspraken). Dit is leidend.
AANVULLENDE BRON — de KDs (landelijke eisen, kerntaken, werkprocessen).
Raadpleeg een KD alléén als de bijbehorende OER het onderwerp niet of
onvoldoende behandelt. Geef niet onnodig een tweede antwoord uit het KD als
de OER de vraag al beantwoordt — de OER is leidend.

CITATIEPLICHT (de OER is een juridisch document).
Bij ELKE claim MOET je:
1. de bron noemen ("OER N" of "Kwalificatiedossier N", zie de koppen hieronder),
2. de exacte vindplaats noemen — sectie-nummer, kopje, artikel of paginanummer,
3. de relevante passage WOORDELIJK citeren tussen dubbele aanhalingstekens.

Voorbeeld: OER 1, sectie 3.2 "Bindend studieadvies": "De student ontvangt
uiterlijk in juli...". Voor het KD: De OER beschrijft dit niet. Volgens
Kwalificatiedossier 1, kerntaak B1-K1: "...".

Een claim zonder bron + vindplaats + woordelijk citaat is niet toegestaan.
Parafraseren mag alleen ter inleiding van een citaat, niet ter vervanging ervan.
Beantwoord uitsluitend op basis van deze bronnen — nooit vanuit eigen kennis.
Als de informatie in geen van de bronnen staat, zeg dat dan expliciet.
Antwoord in het Nederlands.

{oer_blokken}"""


def bouw_gecombineerd_systeem(oer_items: list[dict]) -> str:
    """Bouw een systeemprompt voor één of meerdere OERs.

    Args:
        oer_items: lijst van dict met sleutels 'tekst', 'opleiding',
                   'display_naam', 'leerweg', 'cohort'. Optioneel:
                   'dossier_tekst' en 'crebo' om het landelijke
                   kwalificatiedossier mee in te bedden.
    """
    if len(oer_items) == 1:
        item = oer_items[0]
        return bouw_systeem(
            item["tekst"],
            item["opleiding"],
            item["display_naam"],
            dossier_tekst=item.get("dossier_tekst", ""),
            crebo=item.get("crebo"),
        )

    blokken = []
    for i, item in enumerate(oer_items, 1):
        label = f"{item['display_naam']} · {item['opleiding']} · {item['leerweg']} {item['cohort']}"
        oer_blok = f"=== OER {i}: {label} ===\n\n{item['tekst']}"
        dossier_tekst = item.get("dossier_tekst", "")
        if dossier_tekst:
            crebo_label = item.get("crebo", "onbekend")
            oer_blok += (
                f"\n\n=== KWALIFICATIEDOSSIER {i} (Crebo {crebo_label}) ===\n\n{dossier_tekst}"
            )
        blokken.append(oer_blok)
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
    tekst_woorden = set(re.findall(r"\w+", tekst_lower))
    kandidaten = []
    _generiek = {"college", "school", "mbo", "roc"}

    for oer in oers:
        d = dict(oer)
        score = 0

        if d["crebo"] in tekst_woorden:
            score += 3

        if d["leerweg"].lower() in tekst_woorden:
            score += 2

        if d["cohort"] in tekst_woorden:
            score += 2

        # CamelCase split (VerzorgendeIG → Verzorgende IG) + underscore als separator.
        # Dedupliceren met set: filename-prefixen herhalen vaak BOL/BBL/jaar, anders
        # zou een opleiding "Kok BOL" via een prefix "_BOL_" dubbel scoren.
        # Sluit BOL/BBL uit; die worden al via `leerweg` gescoord.
        opl_gesplit = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", d["opleiding"])
        woorden = {
            w
            for w in re.sub(r"[_\W]+", " ", opl_gesplit).lower().split()
            if len(w) >= 3 and not w.isdigit() and w not in {"bol", "bbl"}
        }
        score += min(sum(1 for w in woorden if w in tekst_woorden), 2)

        for deel in d["display_naam"].lower().split():
            if len(deel) >= 4 and deel not in _generiek and deel in tekst_woorden:
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
