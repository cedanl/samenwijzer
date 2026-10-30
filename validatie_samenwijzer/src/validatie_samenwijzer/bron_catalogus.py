"""Chat-bronnen: laden van bronbestanden en de bron-catalogus van een chat-sessie.

Eén plek die weet hoe een chat-bron (OER, kwalificatiedossier, skills-taxonomie,
instellingsbreed document) van schijf komt en met welke cap.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from validatie_samenwijzer.kd_versies import kd_map, kies_kd_pad

logger = logging.getLogger(__name__)

_MAX_OER_TEKST_TEKENS = 500_000  # ruim voldoende voor elke OER binnen Sonnet 4.6 (1M context)
_MAX_DOSSIER_TEKST_TEKENS = 300_000
_MAX_SKILLS_TEKST_TEKENS = 50_000  # skills-blok is klein; cap als veiligheid
# Cap voor instellingsbrede documenten (examenreglement/begeleidingsbeleid). Ruime veiligheidsrem:
# een echt examenreglement meet ~37K tekens (~12,5K tokens), dus de cap bindt in de praktijk niet.
# Onderbouwing: docs/plans/2026-06-02-instellingsbrede-bron.md §4 (kostenmeting 2026-06-02).
_MAX_INSTELLING_TEKST_TEKENS = 300_000


# ── Bronladers ────────────────────────────────────────────────────────────────


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


def laad_oer_tekst(bestandspad: Path, cap: int = _MAX_OER_TEKST_TEKENS) -> str:
    """Laad de tekst van een OER of instellingsbreed document voor gebruik als chatcontext.

    Prioriteit: .md-broertje (markitdown-kwaliteit) → .md zelf → PDF via pdfplumber.

    Args:
        bestandspad: Pad naar het bestand (PDF of Markdown).
        cap: maximum aantal tekens; instellingsbrede documenten geven
            ``_MAX_INSTELLING_TEKST_TEKENS`` mee.

    Returns:
        De tekst (gecapt), of lege string als niets beschikbaar is.
    """
    if not bestandspad.exists():
        # Probeer het .md-broertje ook als het bronbestand zelf ontbreekt
        md_pad = bestandspad.with_suffix(".md")
        if md_pad.exists():
            md_tekst = md_pad.read_text(encoding="utf-8", errors="replace")
            if md_tekst.strip():
                return md_tekst[:cap]
        return ""

    suffix = bestandspad.suffix.lower()

    if suffix == ".md":
        return bestandspad.read_text(encoding="utf-8", errors="replace")[:cap]

    if suffix == ".pdf":
        # Voorkeur: naastliggend .md-bestand van markitdown-conversie — maar alleen als
        # het écht inhoud heeft. Een leeg .md (bv. mislukte conversie van een gescande
        # PDF) mag de pdfplumber-fallback niet blokkeren.
        md_pad = bestandspad.with_suffix(".md")
        if md_pad.exists():
            md_tekst = md_pad.read_text(encoding="utf-8", errors="replace")
            if md_tekst.strip():
                return md_tekst[:cap]
        # Fallback: pdfplumber
        try:
            import pdfplumber

            tekst_delen = []
            with pdfplumber.open(str(bestandspad)) as pdf:
                for pagina in pdf.pages:
                    t = pagina.extract_text()
                    if t:
                        tekst_delen.append(t)
            return "\n\n".join(tekst_delen)[:cap]
        except Exception as e:
            logger.warning("PDF lezen mislukt voor '%s': %s", bestandspad, e)
            return ""

    return ""


def laad_kwalificatiedossier_tekst(crebo: str | None, cohort: str | int | None = None) -> str:
    """Laad de markdown-tekst van een kwalificatiedossier op crebo, of lege string.

    Met ``cohort`` wordt de KD-versie gekozen die voor dat cohort geldt (zie ``kd_versies``);
    zonder cohort of zonder match geldt het nieuwste (``<crebo>.md`` in ``kd_versies.kd_map()``).
    """
    if not crebo:
        return ""
    md_pad = kies_kd_pad(str(crebo), cohort) or kd_map() / f"{crebo}.md"
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
        # bron_catalogus.py → parents[2] = subproject-root → data/skills
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
