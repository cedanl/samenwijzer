"""Reconciliatie: bouw ontbrekende afgeleide bronnen (KD + skills) per crebo.

Desired-state reconciliatie: vergelijk de geïndexeerde crebo's (`oer_documenten`) met de
bestaande artefacten (`kwalificatiedossiers/pdfs/<crebo>.md`, `data/skills/<crebo>.json`) en
bouw alleen wat ontbreekt. Idempotent — dezelfde run twee keer doet de tweede keer niets. Dit
dekt nieuwe OER's, nieuwe instellingen die honderden bestanden dumpen, en catch-up na downtime,
zónder event-boekhouding.

Werkt **working-tree only**: schrijft alleen lokaal en raakt git/Box niet aan. Daarom rapporteert
het expliciet wat het veranderde, zodat een mens de skills (PR) en KD (Box-sync) kan distribueren.

De asymmetrie tussen de bronnen:
- **Skills** zijn live per crebo (CompetentNL SPARQL → ESCO) en altijd bouwbaar.
- **KD** komt uit de lokale s-bb-bundle (zips + crebolijsten); een crebo zonder dossier in die
  bundle is een **gat** dat een bundle-refresh vereist — dat wordt gerapporteerd, niet gefaald.

Bekende kosten: het KD-batch-script kent geen skip-existing, dus `--alles` her-extraheert alle
~240 KD-PDFs uit de zips (de md's worden wél overgeslagen, dus de chat-inhoud en de
gerapporteerde diff blijven stabiel). De gewijzigde pdf-mtimes kunnen een daaropvolgende
`sync_kwalificatiedossiers.sh --upload` alles opnieuw naar Box laten pushen.

Gebruik:
    python -m validatie_samenwijzer.sync_afgeleid --alles
    python -m validatie_samenwijzer.sync_afgeleid --crebo 25180
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import db, ingest

logger = logging.getLogger(__name__)

_SUBPROJECT = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = _SUBPROJECT / "scripts"
_KD_DIR = _REPO_ROOT / "kwalificatiedossiers" / "pdfs"
_SKILLS_DIR = _SUBPROJECT / "data" / "skills"
_DOWNLOAD_SCRIPT = _SCRIPTS / "download_kwalificatiedossiers.py"
_SKILLS_SCRIPT = _SCRIPTS / "build_skills_taxonomie.py"


@dataclass
class Samenvatting:
    """Wat de reconciliatie veranderde — basis voor de change-rapportage."""

    nieuwe_kd: list[str] = field(default_factory=list)
    nieuwe_skills: list[str] = field(default_factory=list)
    kd_gaten: list[str] = field(default_factory=list)
    skills_gaten: list[str] = field(default_factory=list)

    @property
    def iets_veranderd(self) -> bool:
        return bool(self.nieuwe_kd or self.nieuwe_skills)


def geindexeerde_crebos() -> set[str]:
    """De crebo's waarvoor afgeleide bronnen zouden moeten bestaan (uit oer_documenten)."""
    db_path = Path(os.environ.get("DB_PATH", "data/validatie.db"))
    conn = db.get_connection(db_path)
    rijen = conn.execute(
        "SELECT DISTINCT crebo FROM oer_documenten WHERE crebo IS NOT NULL AND crebo != ''"
    )
    return {r[0] for r in rijen}


def _bestaande_kd() -> set[str]:
    return {p.stem for p in _KD_DIR.glob("*.md")} if _KD_DIR.exists() else set()


def _bestaande_skills() -> set[str]:
    return {p.stem for p in _SKILLS_DIR.glob("*.json")} if _SKILLS_DIR.exists() else set()


def _skills_zonder_match(crebos: set[str]) -> list[str]:
    """Crebo's met een skills-artefact maar zónder gematcht beroep (lege skills).

    Deze bestaan op schijf (de build schrijft ook voor 'geen-match' een JSON), dus de
    reconciliatie bouwt ze niet opnieuw — maar ze worden wél gerapporteerd, anders lijken
    ze stil 'compleet' terwijl een student er geen skills voor krijgt. Opnieuw matchen
    (bv. als CompetentNL de crebo later toevoegt) is Fase 3: `--refresh-fallbacks`.
    """
    gaten = []
    for crebo in crebos:
        pad = _SKILLS_DIR / f"{crebo}.json"
        if not pad.exists():
            continue
        try:
            if json.loads(pad.read_text(encoding="utf-8")).get("beroep") is None:
                gaten.append(crebo)
        except (json.JSONDecodeError, OSError):
            continue
    return sorted(gaten)


def _run(cmd: list[str]) -> int:
    """Draai een subprocess (erft de omgeving incl. API-keys); geeft de exit-code."""
    logger.info("→ %s", " ".join(Path(c).name if c.endswith(".py") else c for c in cmd))
    return subprocess.run(cmd, cwd=_SUBPROJECT).returncode


def _converteer_kd_md(crebo: str | None) -> None:
    """Maak <crebo>.md voor gedownloade pdf('s) zonder markdown.

    Voor één crebo alleen dat bestand; voor de batch (crebo=None) alle pdf's zonder md.
    """
    if crebo:
        pdfs = [_KD_DIR / f"{crebo}.pdf"]
    else:
        pdfs = sorted(_KD_DIR.glob("*.pdf"))
    for pdf in pdfs:
        if pdf.exists() and not pdf.with_suffix(".md").exists():
            ingest.converteer_naar_markdown(pdf)


def _bouw_kd(crebo: str | None) -> None:
    """Download ontbrekende KD-PDF('s) uit de s-bb-bundle en converteer naar markdown."""
    cmd = [sys.executable, str(_DOWNLOAD_SCRIPT)]
    if crebo:
        cmd += ["--crebo", crebo]
    rc = _run(cmd)
    if rc != 0:
        # Een gat geeft exit 0; non-zero = een echte fout (bv. ontbrekende dependency
        # of geen s-bb-bundle). Niet stil doorgaan — log zichtbaar.
        logger.error("KD-download mislukt (exit %d) — geen KD gebouwd deze run", rc)
        return
    _converteer_kd_md(crebo)


def _bouw_skills(crebo: str | None, force: bool) -> None:
    """Bouw ontbrekende skills-artefact(en) via de hybride build (CompetentNL → ESCO)."""
    cmd = [sys.executable, str(_SKILLS_SCRIPT)]
    if crebo:
        cmd += ["--crebo", crebo]
    if force:
        cmd += ["--reset"]
    _run(cmd)


def werk_afgeleide_bronnen_bij(
    crebo: str | None = None, *, alles: bool = False, force: bool = False
) -> Samenvatting:
    """Reconcilieer KD + skills voor één crebo of voor alle geïndexeerde crebo's.

    Args:
        crebo: één crebo bijwerken (genegeerd als ``alles=True``).
        alles: alle geïndexeerde crebo's reconciliëren.
        force: bestaande skills-artefacten herbouwen (``--reset``) i.p.v. overslaan.
    """
    kd_voor, skills_voor = _bestaande_kd(), _bestaande_skills()

    if alles:
        _bouw_kd(None)
        _bouw_skills(None, force)
    elif crebo:
        kd_md = _KD_DIR / f"{crebo}.md"
        if force or not kd_md.exists():
            _bouw_kd(crebo)
        _bouw_skills(crebo, force)
    else:
        raise ValueError("geef --crebo of --alles op")

    kd_na, skills_na = _bestaande_kd(), _bestaande_skills()
    doel = geindexeerde_crebos() if alles else {crebo} if crebo else set()
    samenvatting = Samenvatting(
        nieuwe_kd=sorted(kd_na - kd_voor),
        nieuwe_skills=sorted(skills_na - skills_voor),
        kd_gaten=sorted(doel - kd_na),
        skills_gaten=_skills_zonder_match(doel),
    )
    _rapporteer(samenvatting)
    return samenvatting


def _rapporteer(s: Samenvatting) -> None:
    """Log wat er veranderde + de vervolgacties (working-tree only: mens commit/synct)."""
    logger.info(
        "Reconciliatie klaar: +%d skills, +%d KD, %d KD-gaten, %d skills-gaten.",
        len(s.nieuwe_skills),
        len(s.nieuwe_kd),
        len(s.kd_gaten),
        len(s.skills_gaten),
    )
    if s.kd_gaten:
        logger.warning(
            "KD-gaten (geen dossier in de s-bb-bundle): %s%s",
            ", ".join(s.kd_gaten[:10]),
            " …" if len(s.kd_gaten) > 10 else "",
        )
    if s.skills_gaten:
        logger.warning(
            "Skills-gaten (geen passend beroep gevonden): %s%s",
            ", ".join(s.skills_gaten[:10]),
            " …" if len(s.skills_gaten) > 10 else "",
        )
    if s.nieuwe_skills:
        logger.info("→ commit de nieuwe skills: git add data/skills/ && open een PR")
    if s.nieuwe_kd:
        logger.info("→ sync de nieuwe KD naar Box: ./scripts/sync_kwalificatiedossiers.sh --upload")


def main() -> int:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    groep = parser.add_mutually_exclusive_group(required=True)
    groep.add_argument("--crebo", help="Reconcilieer één crebo")
    groep.add_argument(
        "--alles", action="store_true", help="Reconcilieer alle geïndexeerde crebo's"
    )
    parser.add_argument("--force", action="store_true", help="Herbouw bestaande skills (--reset)")
    args = parser.parse_args()

    werk_afgeleide_bronnen_bij(crebo=args.crebo, alles=args.alles, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
