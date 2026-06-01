"""Skills-taxonomie: koppel een opleiding aan het bijbehorende beroep en skills.

Een OER leidt op voor een beroep; van dat beroep willen we de benodigde skills
kunnen tonen ("welke skills heb ik nodig voor het beroep Kok?"). De koppeling
loopt **OER → beroep → skills**, want anders dan bij OER↔kwalificatiedossier is er
geen directe crebo-sleutel naar een skills-bron.

Bron-agnostisch ontwerp: het build-script (`scripts/build_skills_taxonomie.py`)
schrijft per crebo een uniform ``data/skills/<crebo>.json``. Dit artefact is het
contract; `chat.py` leest het zonder de bron te kennen. Deze module levert de
**ESCO**-implementatie (keyless REST-API, Nederlandstalige labels). CompetentNL
(SPARQL, vereist API-key) kan later als tweede bron worden toegevoegd zonder het
artefact-formaat te wijzigen.

Matching is het risicovolle deel: de OER-opleidingsnaam (vrije tekst, vaak uit de
bestandsnaam) draagt het beroep, de KD-dossiernaam hooguit het domein. ESCO is een
*beroepen*-taxonomie, dus het domein ("Keuken") matcht slecht en het beroep ("Kok")
goed. We voeden beide als zoekkandidaten maar laten Claude de beste kiezen, en
persisteren de keuze in het artefact zodat de batch eenmalig is en reviewbaar.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

import anthropic

from . import _ai

logger = logging.getLogger(__name__)

ESCO_API = "https://ec.europa.eu/esco/api"
_TIMEOUT = 25
_MATCH_MODEL = "claude-haiku-4-5-20251001"

# Tokens die in OER-bestandsnamen voorkomen maar geen deel van de beroepsnaam zijn.
_RUIS = re.compile(
    r"""
    \b\d{5}[A-Z]?\b          # crebo (evt. met letter-suffix)
    | \b(?:19|20)\d{2}\b     # jaartal
    | \bBOL\b | \bBBL\b | \bBOL/?BBL\b
    | \bOER\b | \bVG\b | \bWEI\b | \bSB\b | \bN4\b
    | \bExamenplan(?:nen)?\b
    | \(OUD\) | \(V\d+\) | \bV\d+(?:\.\d+)?\b | \bversie\b
    | \bvastgesteld\b
    | \b\d+\s*maanden\b
    | \bcohort\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass
class Skill:
    """Eén skill met zijn relevantie-categorie voor het beroep."""

    label: str
    uri: str
    categorie: str  # "essentieel" of "optioneel" (ESCO); generaliseerbaar voor andere bronnen


@dataclass
class Beroep:
    """Het beroep waar een opleiding voor opleidt, plus de matchverantwoording."""

    label: str
    uri: str
    definitie: str = ""


@dataclass
class SkillsRecord:
    """Uniform, bron-agnostisch artefact per crebo (zie module-docstring)."""

    crebo: str
    opleiding: str
    bron: str  # "ESCO" of later "CompetentNL"
    beroep: Beroep | None
    skills: list[Skill] = field(default_factory=list)
    match_methode: str = ""  # "llm-keuze" | "geen-match" | "geen-kandidaten" | "llm-fout"
    kandidaten: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "crebo": self.crebo,
            "opleiding": self.opleiding,
            "bron": self.bron,
            "beroep": (
                None
                if self.beroep is None
                else {
                    "label": self.beroep.label,
                    "uri": self.beroep.uri,
                    "definitie": self.beroep.definitie,
                }
            ),
            "match_methode": self.match_methode,
            "kandidaten": self.kandidaten,
            "skills": [
                {"label": s.label, "uri": s.uri, "categorie": s.categorie} for s in self.skills
            ],
        }


def schoon_opleidingsnaam(opleiding: str) -> str:
    """Strip crebo/jaar/leerweg/OER-ruis uit een rommelige OER-naam tot het beroep.

    Voorbeelden:
        "2021 - 25180 OER Kok (V1)"                        -> "Kok"
        "25168_BOL_2023__2023_OER_Gastheer-vrouw"          -> "Gastheer vrouw"
        "27015_BOL_2025__OER (OUD) - 27015O - ICT support" -> "ICT support"
    """
    tekst = opleiding.replace("_", " ").replace("-", " ")
    tekst = _RUIS.sub(" ", tekst)
    tekst = re.sub(r"[^\w\s/&]", " ", tekst, flags=re.UNICODE)
    tekst = re.sub(r"\s+", " ", tekst).strip()
    return tekst


def _esco_get(pad: str, params: dict) -> dict:
    """GET op de ESCO-API; geeft geparsete JSON of een lege dict bij falen."""
    url = f"{ESCO_API}/{pad}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 (vaste host)
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        logger.warning("ESCO-call mislukt (%s): %s", pad, e)
        return {}


def zoek_esco_beroepen(term: str, limit: int = 8) -> list[Beroep]:
    """Zoek Nederlandstalige ESCO-beroepen op een vrije-tekstterm."""
    if not term.strip():
        return []
    data = _esco_get(
        "search",
        {"language": "nl", "type": "occupation", "text": term, "limit": limit},
    )
    resultaten = data.get("_embedded", {}).get("results", [])
    return [
        Beroep(label=r.get("title", ""), uri=r.get("uri", "")) for r in resultaten if r.get("uri")
    ]


def haal_esco_beroep_details(beroep_uri: str) -> tuple[str, list[Skill]]:
    """Haal definitie + essentiële/optionele skills van een ESCO-beroep (NL) in één call."""
    data = _esco_get("resource/occupation", {"uri": beroep_uri, "language": "nl"})
    definitie = data.get("description", {}).get("nl", {}).get("literal", "")
    links = data.get("_links", {})
    skills: list[Skill] = []
    for cat, sleutel in (("essentieel", "hasEssentialSkill"), ("optioneel", "hasOptionalSkill")):
        for s in links.get(sleutel, []):
            if s.get("uri"):
                skills.append(Skill(label=s.get("title", ""), uri=s["uri"], categorie=cat))
    return definitie, skills


def _kies_met_llm(
    opleiding: str, kd_domein: str, kandidaten: list[Beroep], client: anthropic.Anthropic
) -> tuple[int | None, str]:
    """Laat Claude de beste beroepskandidaat kiezen; geeft (index|None, methode).

    De top-1 van ESCO-zoeken is niet betrouwbaar (bv. "chauffeur wegvervoer" →
    "chauffeur gevaarlijke stoffen"). Claude kiest uit de kandidaten het beroep dat
    het best past, met de opleidingsnaam én het kwalificatiedomein als context — dat
    domein is een slechte zoekterm maar een goed keuzesignaal. Brede instroom-
    opleidingen (zoals "Entree") krijgen bewust "GEEN" zodat ze niet aan een
    willekeurig beroep worden gekoppeld.
    """
    lijst = "\n".join(f"{i}. {b.label}" for i, b in enumerate(kandidaten))
    domein_regel = f'- Kwalificatiedomein: "{kd_domein}"\n' if kd_domein else ""
    prompt = (
        "Een MBO-opleiding heeft deze gegevens:\n"
        f'- Opleidingsnaam: "{opleiding}"\n'
        f"{domein_regel}"
        "\nHieronder staan ESCO-beroepen. Kies het beroep waarvoor deze opleiding "
        f"het meest waarschijnlijk opleidt.\n\n{lijst}\n\n"
        "Regels:\n"
        "- Antwoord met UITSLUITEND het nummer van het best passende beroep.\n"
        '- Is de opleiding een brede oriëntatie- of instroomopleiding (zoals "Entree") '
        'zonder specifiek beroep, of past geen enkel beroep echt, antwoord dan "GEEN".'
    )
    try:
        resp = client.messages.create(
            model=_MATCH_MODEL,
            max_tokens=8,
            messages=[{"role": "user", "content": prompt}],
        )
        antwoord = resp.content[0].text.strip()
    except (anthropic.APIError, IndexError, AttributeError) as e:
        logger.warning("LLM-match mislukt voor '%s': %s — geen match", opleiding, e)
        return None, "llm-fout"

    m = re.search(r"\d+", antwoord)
    if m and 0 <= int(m.group()) < len(kandidaten):
        return int(m.group()), "llm-keuze"
    return None, "geen-match"


def bouw_skills_record(
    crebo: str,
    opleiding: str,
    kd_domein: str = "",
    client: anthropic.Anthropic | None = None,
) -> SkillsRecord:
    """Resolve één opleiding naar beroep + skills via ESCO.

    Args:
        crebo: crebo-code (artefact-sleutel).
        opleiding: OER-opleidingsnaam (primair matchsignaal).
        kd_domein: kwalificatiedossier-domeinnaam (zwakke fallback-kandidaatbron).
        client: Anthropic-client voor de beroepskeuze; default via ``_ai._client()``.
    """
    client = client or _ai._client()
    schoon = schoon_opleidingsnaam(opleiding)

    # Kandidaten: primair uit de (geschoonde) opleidingsnaam, aangevuld met het
    # KD-domein. Dedup op URI; opleidingsnaam-treffers staan vooraan.
    kandidaten: list[Beroep] = []
    gezien: set[str] = set()
    for term in (schoon, kd_domein):
        for b in zoek_esco_beroepen(term):
            if b.uri not in gezien:
                gezien.add(b.uri)
                kandidaten.append(b)

    leeg = SkillsRecord(crebo=crebo, opleiding=opleiding, bron="ESCO", beroep=None, kandidaten=[])
    if not kandidaten:
        leeg.match_methode = "geen-kandidaten"
        return leeg

    namen = [b.label for b in kandidaten]
    # Altijd via de LLM kiezen — ook bij één kandidaat, zodat een zwakke losse
    # ESCO-treffer "GEEN" kan worden i.p.v. blind geaccepteerd.
    idx, methode = _kies_met_llm(schoon or opleiding, kd_domein, kandidaten, client)

    if idx is None:
        leeg.match_methode = methode
        leeg.kandidaten = namen
        return leeg

    beroep = kandidaten[idx]
    definitie, skills = haal_esco_beroep_details(beroep.uri)
    beroep.definitie = definitie
    return SkillsRecord(
        crebo=crebo,
        opleiding=opleiding,
        bron="ESCO",
        beroep=beroep,
        skills=skills,
        match_methode=methode,
        kandidaten=namen,
    )
