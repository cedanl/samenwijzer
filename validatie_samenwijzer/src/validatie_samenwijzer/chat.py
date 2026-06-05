"""OER-chat: full-document context + Claude streaming."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Generator, Sequence
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

_MAX_OER_TEKST_TEKENS = 500_000  # ruim voldoende voor elke OER binnen Sonnet 4.6 (1M context)
_MAX_DOSSIER_TEKST_TEKENS = 300_000
_MAX_SKILLS_TEKST_TEKENS = 50_000  # skills-blok is klein; cap als veiligheid
# Cap voor instellingsbrede documenten (examenreglement/begeleidingsbeleid). Ruime veiligheidsrem:
# een echt examenreglement meet ~37K tekens (~12,5K tokens), dus de cap bindt in de praktijk niet.
# Onderbouwing: docs/plans/2026-06-02-instellingsbrede-bron.md §4 (kostenmeting 2026-06-02).
_MAX_INSTELLING_TEKST_TEKENS = 300_000

LAGE_RELEVANTIE_BERICHT = (
    "Ik kon de studiegids voor deze opleiding niet laden. "
    "Controleer of het bestand beschikbaar is, of bekijk 'm via 'Mijn studiegids'."
)

_SYSTEEM_TEMPLATE = """\
Je bent een onderwijs-assistent voor de opleiding {opleiding} bij {instelling}.

PRIMAIRE BRON — de Onderwijs- en Examenregeling (OER) van deze opleiding.
Dit is het leidende, schoolspecifieke document. Beantwoord vragen primair op
basis van de OER.

AANVULLENDE BRON — instellingsbrede regelingen van de school (zie de koppen
hieronder, zoals het examenreglement en het begeleidings-/welzijnsbeleid). Dit
zijn APARTE documenten, NIET de OER. Ze gelden voor de hele instelling.
Raadpleeg ze voor vragen over examinering, herkansingen, fraude, bezwaar of
begeleiding; bij school-specifieke regels gaan ze vóór het landelijke KD.

AANVULLENDE BRON — het landelijke kwalificatiedossier (KD). Raadpleeg het KD
alléén als de OER het onderwerp niet of onvoldoende behandelt. Geef niet
onnodig een tweede antwoord uit het KD als de OER de vraag al beantwoordt —
de OER is leidend.

AANVULLENDE BRON — de skills-taxonomie (ESCO): de skills, vaardigheden en
competenties die horen bij het beroep waarvoor deze opleiding opleidt. Raadpleeg
deze alléén bij vragen over welke skills of vaardigheden het beroep vereist
(bijv. "welke skills heb ik nodig voor dit beroep?").

CITATIEPLICHT (de OER is een juridisch document).
Bij ELKE claim uit de OER, een instellingsbrede regeling of het KD, MOET je:
1. de bron noemen ("Volgens de OER", "Volgens het Examenreglement" of "Volgens
   het kwalificatiedossier"),
2. de exacte vindplaats noemen — sectie-nummer, kopje, artikel of paginanummer,
3. de relevante passage WOORDELIJK citeren tussen dubbele aanhalingstekens, op
   een APARTE regel als markdown-blockquote (de regel begint met "> "), zodat de
   verwijzing visueel als juridisch citaat opvalt. Zet bron + vindplaats op de
   regel ervoor.

Voorbeeld OER:
Volgens de OER, sectie 3.2 "Bindend studieadvies":
> "De student ontvangt uiterlijk in juli van het eerste studiejaar een bindend studieadvies."

Voorbeeld regeling:
Volgens het Examenreglement, artikel 6.3 "Herkansingen":
> "..."

Noem de regeling exact zoals in de kop hierboven (bv. "het Examenreglement" of
"het Begeleidingsbeleid") — citeer een regeling NOOIT als "de OER".

Voorbeeld KD: De OER beschrijft dit niet. Volgens het kwalificatiedossier,
kerntaak B1-K1 "Bieden van zorg en ondersteuning":
> "..."

Voor de skills-taxonomie geldt een AANGEPASTE citatie (een taxonomie heeft geen
secties of pagina's): noem de bron PRECIES zoals die in de kop van het
skills-blok staat (ESCO óf CompetentNL — verzin er geen), plus het beroep en de
categorie, en citeer de exacte skill-naam tussen dubbele aanhalingstekens.
Voorbeeld: Volgens CompetentNL hoort bij het beroep "kok" de essentiële skill
"samenwerken". Verzin nooit een sectie- of paginanummer bij skills.

Een claim zonder correcte bronvermelding is niet toegestaan. Parafraseren mag
alleen ter inleiding van een citaat, niet ter vervanging ervan. Beantwoord vragen
uitsluitend op basis van deze bronnen — nooit vanuit eigen kennis. Als de
informatie in geen van de bronnen staat, zeg dat dan expliciet. Antwoord in het
Nederlands.

=== ONDERWIJS- EN EXAMENREGELING (OER) ===
{oer_tekst}{instelling_blok}{dossier_blok}{skills_blok}"""

_DOSSIER_BLOK_TEMPLATE = "\n\n=== KWALIFICATIEDOSSIER (Crebo {crebo}) ===\n{dossier_tekst}"
_INSTELLING_BLOK_TEMPLATE = "\n\n=== {kop} ({instelling}) ===\n{tekst}"


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


def laad_instelling_bron_tekst(bestandspad: Path | str | None) -> str:
    """Laad de tekst van een instellingsbreed document (examenreglement/begeleidingsbeleid).

    Zelfde laadlogica als de OER (md-voorkeur → PDF-fallback), met een eigen cap. Geeft
    een lege string bij een ontbrekend pad of onleesbaar bestand, zodat de chat zonder de
    bron blijft werken.

    Args:
        bestandspad: DB-`bestandspad` van het document (al naar absoluut pad geresolved),
            of None als de instelling deze soort niet heeft.
    """
    if not bestandspad:
        return ""
    return laad_oer_tekst(Path(bestandspad))[:_MAX_INSTELLING_TEKST_TEKENS]


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
        directory = Path(__file__).resolve().parents[3] / "kwalificatiedossiers" / "pdfs"
    return directory / f"{crebo}.md"


def laad_kwalificatiedossier_tekst(crebo: str | None) -> str:
    """Laad de markdown-tekst van een kwalificatiedossier op crebo, of lege string."""
    if not crebo:
        return ""
    md_pad = pad_kwalificatiedossier(str(crebo))
    if not md_pad.exists():
        return ""
    return md_pad.read_text(encoding="utf-8", errors="replace")[:_MAX_DOSSIER_TEKST_TEKENS]


def pad_skills(crebo: str) -> Path:
    """Pad naar het skills-taxonomie-artefact voor een crebo.

    Default: ``<subproject-root>/data/skills/<crebo>.json`` (gebouwd door
    ``scripts/build_skills_taxonomie.py``). Override via env-var ``SKILLS_PAD``.
    """
    base = os.environ.get("SKILLS_PAD")
    if base:
        directory = Path(base).resolve()
    else:
        # chat.py → parents[2] = subproject-root → data/skills
        directory = Path(__file__).resolve().parents[2] / "data" / "skills"
    return directory / f"{crebo}.json"


def laad_skills_tekst(crebo: str | None) -> str:
    """Bouw het skills-tekstblok voor een crebo, of lege string als er geen artefact is.

    Leest het bron-agnostische JSON-artefact en formatteert het tot een leesbaar
    blok voor de systeemprompt. Lege string als het bestand ontbreekt of geen
    beroep gematcht is — de chat werkt dan zonder skills.
    """
    if not crebo:
        return ""
    json_pad = pad_skills(str(crebo))
    if not json_pad.exists():
        return ""
    try:
        data = json.loads(json_pad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Skills-artefact onleesbaar voor crebo %s: %s", crebo, e)
        return ""

    beroep = data.get("beroep")
    if not beroep:
        return ""

    regels = [f'Beroep "{beroep["label"]}"']
    if beroep.get("definitie"):
        regels.append(beroep["definitie"])
    for categorie, kop in (
        ("essentieel", "Essentiële skills"),
        ("belangrijk", "Belangrijke skills"),
        ("optioneel", "Optionele skills"),
    ):
        labels = [s["label"] for s in data.get("skills", []) if s["categorie"] == categorie]
        if labels:
            regels.append(f"\n{kop}:")
            regels.extend(f"- {label}" for label in labels)

    bron = data.get("bron", "ESCO")
    tekst = "\n".join(regels)[:_MAX_SKILLS_TEKST_TEKENS]
    return (
        f"\n\n=== SKILLS-TAXONOMIE ({bron}) — beroep: {beroep['label']} ===\n"
        f"De skills die horen bij het beroep waarvoor deze opleiding opleidt. "
        f"Citeer deze skills uitsluitend als afkomstig van: {bron}.\n"
        f"{tekst}"
    )


def _instelling_blok(instelling: str, instelling_bronnen: Sequence[tuple[str, str]]) -> str:
    """Render de instellingsbrede regelingen (label, tekst) als prompt-blokken.

    Lege of ontbrekende bronnen leveren geen blok op (geen lege koppen).
    """
    delen = [
        _INSTELLING_BLOK_TEMPLATE.format(kop=kop.upper(), instelling=instelling, tekst=tekst)
        for kop, tekst in instelling_bronnen
        if tekst
    ]
    return "".join(delen)


def bouw_systeem(
    oer_tekst: str,
    opleiding: str,
    instelling: str,
    dossier_tekst: str = "",
    crebo: str | None = None,
    skills_tekst: str = "",
    instelling_bronnen: Sequence[tuple[str, str]] = (),
) -> str:
    """Stel de systeemprompt samen met OER, optionele instellingsbrede regelingen, KD en skills.

    Args:
        instelling_bronnen: (label, tekst)-paren voor instellingsbrede regelingen
            (bv. ("Examenreglement", ...)). Het label wordt de blok-kop en de te
            citeren bronnaam. Volgorde bepaalt de blok-volgorde; lege tekst → geen blok.
    """
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
        instelling_blok=_instelling_blok(instelling, instelling_bronnen),
        dossier_blok=dossier_blok,
        skills_blok=skills_tekst,
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
AANVULLENDE BRON — instellingsbrede regelingen (zoals een examenreglement of
begeleidingsbeleid) waar bij een OER getoond. Dit zijn APARTE documenten, NIET
de OER; ze gelden voor de hele instelling en gaan bij school-specifieke regels
vóór het KD.
AANVULLENDE BRON — de KDs (landelijke eisen, kerntaken, werkprocessen).
Raadpleeg een KD alléén als de bijbehorende OER het onderwerp niet of
onvoldoende behandelt. Geef niet onnodig een tweede antwoord uit het KD als
de OER de vraag al beantwoordt — de OER is leidend.
AANVULLENDE BRON — de skills-taxonomie (ESCO) waar beschikbaar: de skills en
vaardigheden die horen bij het beroep van een opleiding. Raadpleeg deze alléén
bij vragen over welke skills of vaardigheden het beroep vereist.

CITATIEPLICHT (de OER is een juridisch document).
Bij ELKE claim uit een OER of KD MOET je:
1. de bron noemen ("OER N" of "Kwalificatiedossier N", zie de koppen hieronder),
2. de exacte vindplaats noemen — sectie-nummer, kopje, artikel of paginanummer,
3. de relevante passage WOORDELIJK citeren tussen dubbele aanhalingstekens, op
   een APARTE regel als markdown-blockquote (de regel begint met "> "), zodat de
   verwijzing visueel als juridisch citaat opvalt. Zet bron + vindplaats op de
   regel ervoor.

Voorbeeld:
OER 1, sectie 3.2 "Bindend studieadvies":
> "De student ontvangt uiterlijk in juli..."

Voor het KD: De OER beschrijft dit niet. Volgens Kwalificatiedossier 1,
kerntaak B1-K1:
> "..."

Voor een instellingsbrede regeling: noem de regeling exact zoals in de kop (bv.
"het Examenreglement"), met artikel/vindplaats en het woordelijk citaat als
blockquote — nooit als "de OER".

Voor de skills-taxonomie geldt een AANGEPASTE citatie (geen secties of pagina's):
noem de bron PRECIES zoals in de kop van het skills-blok (ESCO óf CompetentNL),
plus het beroep en de categorie, en citeer de exacte skill-naam, bijv. Volgens
CompetentNL hoort bij het beroep "kok" de essentiële skill "samenwerken".
Verzin nooit een sectie- of paginanummer bij skills.

Een claim zonder correcte bronvermelding is niet toegestaan.
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
                   kwalificatiedossier mee in te bedden, en 'skills_tekst'
                   voor de skills-taxonomie van het beroep.
    """
    if len(oer_items) == 1:
        item = oer_items[0]
        return bouw_systeem(
            item["tekst"],
            item["opleiding"],
            item["display_naam"],
            dossier_tekst=item.get("dossier_tekst", ""),
            crebo=item.get("crebo"),
            skills_tekst=item.get("skills_tekst", ""),
            instelling_bronnen=item.get("instelling_bronnen", ()),
        )

    blokken = []
    for i, item in enumerate(oer_items, 1):
        label = f"{item['display_naam']} · {item['opleiding']} · {item['leerweg']} {item['cohort']}"
        oer_blok = f"=== OER {i}: {label} ===\n\n{item['tekst']}"
        for kop, tekst in item.get("instelling_bronnen", ()):
            if tekst:
                oer_blok += f"\n\n=== {kop.upper()} {i} ({item['display_naam']}) ===\n\n{tekst}"
        dossier_tekst = item.get("dossier_tekst", "")
        if dossier_tekst:
            crebo_label = item.get("crebo", "onbekend")
            oer_blok += (
                f"\n\n=== KWALIFICATIEDOSSIER {i} (Crebo {crebo_label}) ===\n\n{dossier_tekst}"
            )
        oer_blok += item.get("skills_tekst", "")
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
    opleidingswoorden (+1 elk, max 2), instellingsnaam (+3).
    De instellingsnaam weegt bewust even zwaar als het crebo: een expliciet genoemde
    instelling moet de OER van een ándere instelling met dezelfde opleidingswoorden
    overstemmen (anders wint de instelling met de "schoonste" opleidingsnaam, bv.
    Talland boven kwic, waarvan de opleidingsnaam aaneengeplakt in de bestandsnaam zit).
    Bewust niet zwaarder dan crebo (+3): zo blijft het crebo het sterkste enkele
    signaal en degradeert een toevallige stad/naam-match ("Utrecht") tot een
    gelijkspel-dropdown i.p.v. een stille verkeerde keuze.
    CamelCase-namen (Da Vinci-stijl) worden gesplitst vóór matching.
    Numerieke tokens worden uitgesloten zodat jaarcijfers niet dubbel tellen.
    """
    tekst_lower = tekst.lower()
    tekst_woorden = set(re.findall(r"\w+", tekst_lower))
    kandidaten = []
    _generiek = {"college", "school", "mbo", "roc"}
    # Officiële afkortingen die niet uit de display-naam of sleutel af te leiden zijn
    # (kwic ≠ de merknaam "KW1C"). Per instelling-sleutel uitbreidbaar.
    _aliassen = {"kwic": {"kw1c"}}

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

        # Instellingsmatch op woorden uit de display-naam ("Koning", "Willem") én
        # de korte sleutel ("kwic"). Eén match volstaat voor de volle bonus.
        inst_woorden = {
            w for w in d["display_naam"].lower().split() if len(w) >= 4 and w not in _generiek
        }
        if d.get("naam"):
            inst_woorden.add(d["naam"].lower())
            inst_woorden |= _aliassen.get(d["naam"].lower(), set())
        if inst_woorden & tekst_woorden:
            score += 3

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
