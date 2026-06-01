"""CompetentNL-bron voor de skills-taxonomie: crebo → skills, zonder beroep-matching.

Anders dan ESCO (`skills_bron.py`, dat OER → beroep → skills via tekstmatching doet) is
CompetentNL **crebo-direct**: een `cnlo:EducationalNorm` met `ksmo:opleidingscode = <crebo>`
verwijst rechtstreeks via `prescribesHATEssential` / `prescribesHATImportant` naar de skills
(`humancapability` + `knowledgearea`). Dat is de gecureerde Nederlandse skills-set áchter het
UWV-skills-dashboard — robuuster en exacter dan ESCO, maar met lagere crebo-dekking (~58% van
onze crebo's). Daarom: CompetentNL eerst, ESCO als fallback (zie `build_skills_taxonomie.py`).

Vereist `COMPETENTNL_API_KEY` in de omgeving (SPARQL-endpoint, header `apikey`). Zonder key
geeft `haal_skills_record()` `None` terug en valt de build terug op ESCO.

`prescribesHATImportant` kan ook naar `LanguageProficiency`-nodes wijzen (taalvereisten zonder
`skos:prefLabel`); die worden overgeslagen — alleen skills met een Nederlandstalig prefLabel
tellen mee.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

from .skills_bron import Beroep, Skill, SkillsRecord

logger = logging.getLogger(__name__)

SPARQL_ENDPOINT = "https://sparql.competentnl.nl/v1"
_TIMEOUT = 40

_QUERY_TEMPLATE = """\
prefix cnlo: <https://linkeddata.competentnl.nl/def/competentnl#>
prefix ksmo: <https://data.s-bb.nl/ksm/ont/ksmo#>
prefix skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?label ?def ?rel ?skill ?skillLabel WHERE {{
  ?en a cnlo:EducationalNorm ; ksmo:opleidingscode "{crebo}" .
  OPTIONAL {{ ?en skos:prefLabel ?label }}
  OPTIONAL {{ ?en skos:definition ?def }}
  OPTIONAL {{
    VALUES ?rel {{ cnlo:prescribesHATEssential cnlo:prescribesHATImportant }}
    ?en ?rel ?skill .
    ?skill skos:prefLabel ?skillLabel .
    FILTER(LANG(?skillLabel) = "nl")
  }}
}}"""

_CATEGORIE = {
    "prescribesHATEssential": "essentieel",
    "prescribesHATImportant": "belangrijk",
}


def _sparql(query: str) -> dict | None:
    """Voer een SPARQL-query uit op CompetentNL; None bij ontbrekende key of fout."""
    api_key = os.environ.get("COMPETENTNL_API_KEY")
    if not api_key:
        return None
    url = f"{SPARQL_ENDPOINT}?{urllib.parse.urlencode({'query': query})}"
    req = urllib.request.Request(
        url, headers={"Accept": "application/sparql-results+json", "apikey": api_key}
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 (vaste host)
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        logger.warning("CompetentNL-query mislukt: %s", e)
        return None


def haal_skills_record(crebo: str, opleiding: str) -> SkillsRecord | None:
    """Bouw een SkillsRecord uit CompetentNL voor een crebo, of None.

    Geeft None als er geen API-key is, de query faalt, of de crebo niet als
    EducationalNorm in CompetentNL voorkomt — de build valt dan terug op ESCO.
    """
    data = _sparql(_QUERY_TEMPLATE.format(crebo=crebo))
    if data is None:
        return None
    bindings = data.get("results", {}).get("bindings", [])
    if not bindings:
        return None  # crebo niet in CompetentNL

    label = ""
    definitie = ""
    skills: list[Skill] = []
    gezien: set[str] = set()
    for r in bindings:
        if not label and "label" in r:
            label = r["label"]["value"]
        if not definitie and "def" in r:
            definitie = r["def"]["value"]
        if "skill" in r and "rel" in r:
            uri = r["skill"]["value"]
            if uri in gezien:
                continue
            gezien.add(uri)
            rel = r["rel"]["value"].split("#")[-1]
            skills.append(
                Skill(
                    label=r["skillLabel"]["value"],
                    uri=uri,
                    categorie=_CATEGORIE.get(rel, "overig"),
                )
            )

    if not label:
        return None  # geen bruikbare EducationalNorm

    return SkillsRecord(
        crebo=crebo,
        opleiding=opleiding,
        bron="CompetentNL",
        beroep=Beroep(label=label, uri="", definitie=definitie),
        skills=skills,
        match_methode="crebo-direct",
        kandidaten=[],
    )
