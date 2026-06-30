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
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import kd_bundel, oer_catalogus, sync_afgeleid

logger = logging.getLogger(__name__)

# Crawlbaarheid per instelling (juni 2026 in kaart gebracht; zie reference-memory
# + scripts/fetch_deltion.py). Bepaalt of een OER-/instellingscatalogus-check
# geautomatiseerd kan worden (Fase 3) of handmatig blijft.
_OER_CRAWLBAAR = ["aeres", "curio", "deltion", "landstede", "rijn_ijssel", "talland", "utrecht"]
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
    kd_dir = sync_afgeleid.kd_dir()
    # Onderscheid "geen gaten" (map bestaat, alles gedekt) van "onbekend" (map mist):
    # zonder dat onderscheid zou "0 zonder dekking" volle dekking suggereren terwijl
    # we het niet weten.
    dekking_onbekend = not kd_dir.exists()
    ontbrekend = [] if dekking_onbekend else sorted(crebos - {p.stem for p in kd_dir.glob("*.md")})

    bundel = kd_bundel.bundel_status()
    toestand = bundel["toestand"]
    jaar = bundel["crebolijst_jaar"]
    if toestand == "gewijzigd":
        signaal = (
            f"SBB-bundel gewijzigd sinds laatste ingest "
            f"({len(bundel['gewijzigde_zips'])} zip(s)) — re-ingest nodig"
        )
    elif toestand == "geen_manifest":
        signaal = "geen bundelmanifest — draai `python -m validatie_samenwijzer.kd_bundel`"
    elif dekking_onbekend:
        signaal = f"bundel in sync (crebolijst {jaar}); KD-dekking onbekend (map niet gevonden)"
    else:
        signaal = f"bundel in sync (crebolijst {jaar}); {len(ontbrekend)} crebo('s) zonder dekking"
    return BronStatus(
        "kd",
        automatisch=True,
        signaal=signaal,
        details={
            "toestand": toestand,
            "crebolijst_jaar": jaar,
            "gewijzigde_zips": bundel["gewijzigde_zips"],
            "ontbrekende_dekking": ontbrekend,
            "dekking_onbekend": dekking_onbekend,
        },
    )


def _oer_status(online: bool = False, manifest: bool = False) -> BronStatus:
    if not online:
        return BronStatus(
            "oer",
            automatisch=False,
            signaal="OER-catalogus-check niet gedraaid — gebruik `check-bron-updates --oer`",
            details={"crawlbaar": _OER_CRAWLBAAR, "niet_crawlbaar": _OER_NIET_CRAWLBAAR},
        )
    nieuw: dict[str, list] = {}
    onbereikbaar: list[str] = []
    conn = None if manifest else oer_catalogus.open_conn()
    try:
        for inst in sorted(oer_catalogus._CATALOGUS_BRONNEN):
            try:
                items = oer_catalogus.instelling_nieuwe_oers(inst, conn=conn, manifest=manifest)
            except oer_catalogus.CatalogusOnbereikbaarError as e:
                logger.warning("OER-catalogus overgeslagen (%s)", e)
                onbereikbaar.append(inst)
                continue
            if items:
                nieuw[inst] = items
    finally:
        if conn is not None:
            conn.close()
    n_totaal = sum(len(v) for v in nieuw.values())
    rest = sorted(set(_OER_CRAWLBAAR) - set(oer_catalogus._CATALOGUS_BRONNEN))
    delen = [
        f"{n_totaal} nieuwe OER('s) beschikbaar ("
        + ", ".join(f"{i}: {len(v)}" for i, v in sorted(nieuw.items()))
        + ")"
        if n_totaal
        else "geen nieuwe OER's via API"
    ]
    if onbereikbaar:
        delen.append(f"{len(onbereikbaar)} instelling(en) onbereikbaar")
    delen.append(f"{len(rest)} instelling(en) handmatig")
    return BronStatus(
        "oer",
        automatisch=True,
        signaal="; ".join(delen),
        details={
            "nieuw_per_instelling": {i: [it.sleutel for it in v] for i, v in nieuw.items()},
            "onbereikbaar": onbereikbaar,
            "handmatig": rest,
            "niet_crawlbaar": _OER_NIET_CRAWLBAAR,
        },
    )


def _oer_inhoud_status() -> BronStatus:
    """Content-wijzigingscheck: bestaande OER's die upstream zijn herzien (Deltion-only).

    Duur (één refetch per gematcht document) → eigen flag (--oer-inhoud). Instellingen
    zonder per-OER content-endpoint leveren ([], 0) en worden als 'niet gecheckt'
    gerapporteerd, niet als 'ongewijzigd'.
    """
    gewijzigd: dict[str, list] = {}
    onbereikbaar: list[str] = []
    zonder_baseline = 0
    conn = oer_catalogus.open_conn()
    try:
        for inst in sorted(oer_catalogus._CATALOGUS_BRONNEN):
            try:
                items, nb = oer_catalogus.gewijzigde_oers(inst, conn=conn)
            except oer_catalogus.CatalogusOnbereikbaarError as e:
                logger.warning("OER-inhoudcheck overgeslagen (%s)", e)
                onbereikbaar.append(inst)
                continue
            zonder_baseline += nb
            if items:
                gewijzigd[inst] = items
    finally:
        conn.close()
    n_totaal = sum(len(v) for v in gewijzigd.values())
    gecheckt = sorted(set(oer_catalogus._CATALOGUS_BRONNEN) - set(onbereikbaar))
    niet_gecheckt = sorted(set(_OER_CRAWLBAAR) - {"deltion"})
    if n_totaal:
        per = ", ".join(f"{i}: {len(v)}" for i, v in sorted(gewijzigd.items()))
        kop = f"{n_totaal} herziene OER('s) ({per})"
    else:
        kop = "geen herziene OER's via content-check"
    delen = [kop]
    if zonder_baseline:
        delen.append(f"{zonder_baseline} zonder baseline (her-ingest legt 'm vast)")
    delen.append(f"{len(niet_gecheckt)} instelling(en) niet gecheckt (geen content-endpoint)")
    return BronStatus(
        "oer-inhoud",
        automatisch=True,
        signaal="; ".join(delen),
        details={
            "gewijzigd_per_instelling": {i: [it.sleutel for it in v] for i, v in gewijzigd.items()},
            "zonder_baseline": zonder_baseline,
            "onbereikbaar": onbereikbaar,
            "gecheckt": gecheckt,
            "niet_gecheckt": niet_gecheckt,
        },
    )


def verzamel_bron_status(
    online: bool = False, manifest: bool = False, alleen_oer: bool = False, inhoud: bool = False
) -> list[BronStatus]:
    statussen = [] if alleen_oer else [_skills_status(), _kd_status()]
    statussen.append(_oer_status(online=online, manifest=manifest))
    if inhoud:
        statussen.append(_oer_inhoud_status())
    return statussen


def rapporteer(statussen: list[BronStatus]) -> str:
    regels = ["Bronactualiteit-rapport", "=" * 24]
    for s in statussen:
        markering = "auto" if s.automatisch else "handmatig"
        regels.append(f"[{markering:9}] {s.bron:6} — {s.signaal}")
    return "\n".join(regels)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Bronactualiteit-rapport")
    parser.add_argument(
        "--oer", action="store_true", help="Draai ook de online OER-catalogus-check (netwerk)"
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Diff tegen de gecommitte corpus-manifest i.p.v. de DB (voor de Action)",
    )
    parser.add_argument(
        "--alleen-oer",
        action="store_true",
        help="Rapporteer alleen de OER-bron (sla skills/kd over)",
    )
    parser.add_argument(
        "--oer-inhoud",
        action="store_true",
        help="Draai ook de content-wijzigingscheck (duur: refetch per Deltion-OER)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        statussen = verzamel_bron_status(
            online=args.oer,
            manifest=args.manifest,
            alleen_oer=args.alleen_oer,
            inhoud=args.oer_inhoud,
        )
    except sqlite3.OperationalError as e:
        logger.error("Kan de database niet lezen (%s) — is DB_PATH correct?", e)
        return 1
    print(rapporteer(statussen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
