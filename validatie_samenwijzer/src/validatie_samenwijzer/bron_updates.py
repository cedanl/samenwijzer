"""Bronactualiteit-rapport: is er voor onze bronnen iets nieuws bij de bron?

Out-of-band ops-tool (CLI/cron/Action) — nooit in het FastAPI-request-pad, en
muteert niets. Per bron een adapter die een ``BronStatus`` oplevert:

- skills: echte upstream-detectie via ``refresh_fallbacks(dry_run=True)``
  (welke ESCO-crebo's nu een CompetentNL-match hebben).
- kd: dekkingsgaten (geïndexeerde crebo's zonder KD-bestand). Bundel-versheid
  bij SBB is (nog) niet geautomatiseerd — zie het bronactualiteit-roadmapplan.
- oer/instellingsregelingen: niet geautomatiseerd; meldt de handmatige
  catalogus-crawlroute en welke instellingen crawlbaar zijn.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import sync_afgeleid

logger = logging.getLogger(__name__)

# Crawlbaarheid per instelling (juni 2026 in kaart gebracht; zie reference-memory
# + scripts/fetch_deltion.py). Bepaalt of een OER-/instellingscatalogus-check
# geautomatiseerd kan worden (Fase 3) of handmatig blijft.
_OER_CRAWLBAAR = ["aeres", "curio", "deltion", "rijn_ijssel", "talland", "utrecht"]
_OER_NIET_CRAWLBAAR = ["davinci", "graafschap", "kwic"]


@dataclass
class BronStatus:
    bron: str
    automatisch: bool
    signaal: str
    details: dict = field(default_factory=dict)


def _skills_dry_run() -> tuple[list[str], list[str]]:
    """Importeer het build-script (sibling in scripts/) en draai de dry-run.

    scripts/ is geen package; we voegen het pad toe zoals tests/sync_afgeleid dat
    ook doen. Gebeurt lui zodat een import van deze module goedkoop blijft.
    """
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import build_skills_taxonomie as bst

    return bst.refresh_fallbacks(dry_run=True)


def _skills_status() -> BronStatus:
    upgraded, _nog_fallback = _skills_dry_run()
    signaal = (
        f"{len(upgraded)} skills-upgrade(s) naar CompetentNL beschikbaar"
        if upgraded
        else "geen skills-upgrades beschikbaar"
    )
    return BronStatus("skills", automatisch=True, signaal=signaal, details={"upgrades": upgraded})


def _kd_status() -> BronStatus:
    crebos = sync_afgeleid.geindexeerde_crebos()
    aanwezig = {p.stem for p in sync_afgeleid._KD_DIR.glob("*.md")}
    ontbrekend = sorted(crebos - aanwezig)
    signaal = (
        f"{len(ontbrekend)} crebo('s) zonder KD-dekking; SBB-bundel-versheid niet geautomatiseerd"
        if ontbrekend
        else "KD-dekking compleet; SBB-bundel-versheid niet geautomatiseerd"
    )
    return BronStatus(
        "kd", automatisch=False, signaal=signaal, details={"ontbrekende_dekking": ontbrekend}
    )


def _oer_status() -> BronStatus:
    return BronStatus(
        "oer",
        automatisch=False,
        signaal="OER-/instellingscatalogus-check niet geautomatiseerd — handmatige crawl",
        details={"crawlbaar": _OER_CRAWLBAAR, "niet_crawlbaar": _OER_NIET_CRAWLBAAR},
    )


def verzamel_bron_status() -> list[BronStatus]:
    return [_skills_status(), _kd_status(), _oer_status()]


def rapporteer(statussen: list[BronStatus]) -> str:
    regels = ["Bronactualiteit-rapport", "=" * 24]
    for s in statussen:
        markering = "auto" if s.automatisch else "handmatig"
        regels.append(f"[{markering:9}] {s.bron:6} — {s.signaal}")
    return "\n".join(regels)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(rapporteer(verzamel_bron_status()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
