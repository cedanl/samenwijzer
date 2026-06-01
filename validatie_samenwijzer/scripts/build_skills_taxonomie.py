"""Bouw de skills-taxonomie: koppel elke OER-opleiding aan beroep + skills (ESCO).

Per unieke crebo in ``oer_documenten`` wordt het beroep bepaald (OER-opleidingsnaam
primair, KD-domein als zwakke fallback) en worden de ESCO-skills opgehaald. Het
resultaat komt als ``data/skills/<crebo>.json`` (uniform, bron-agnostisch artefact;
zie ``skills_bron``) plus een reviewbare ``data/skills/_match_overzicht.csv``.

Idempotent: bestaande crebo-bestanden worden overgeslagen (de match is
niet-deterministisch — LLM-keuze — dus we pinnen hem). Forceer herbouw met
``--reset``.

    uv run python scripts/build_skills_taxonomie.py            # alle ontbrekende
    uv run python scripts/build_skills_taxonomie.py --reset    # alles opnieuw
    uv run python scripts/build_skills_taxonomie.py --crebo 25180
    uv run python scripts/build_skills_taxonomie.py --limit 10 # eerste 10 (test)
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path

from validatie_samenwijzer import db, skills_bron

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("build_skills")

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILLS_DIR = _REPO_ROOT / "data" / "skills"
_MAPPING = _REPO_ROOT.parent / "kwalificatiedossiers" / "mapping.json"


def _kd_domein_per_crebo() -> dict[str, str]:
    """Laad crebo → KD-dossiernaam (domein) uit de kwalificatiedossier-mapping."""
    if not _MAPPING.exists():
        logger.warning("mapping.json niet gevonden (%s) — KD-domein-fallback uit", _MAPPING)
        return {}
    data = json.loads(_MAPPING.read_text(encoding="utf-8"))
    return data.get("crebo_naar_dossier", {})


def _beste_opleiding_per_crebo() -> dict[str, str]:
    """Kies per crebo de OER-opleidingsnaam met het meeste matchsignaal.

    Meerdere OERs delen een crebo; we nemen de naam waarvan de geschoonde vorm het
    langst is (meest beschrijvend voor het beroep).
    """
    db_path = Path(os.environ.get("DB_PATH", "data/validatie.db"))
    conn = db.get_connection(db_path)
    keuze: dict[str, str] = {}
    for crebo, opleiding in conn.execute(
        "SELECT crebo, opleiding FROM oer_documenten WHERE crebo IS NOT NULL AND crebo != ''"
    ):
        schoon = skills_bron.schoon_opleidingsnaam(opleiding)
        if crebo not in keuze or len(schoon) > len(skills_bron.schoon_opleidingsnaam(keuze[crebo])):
            keuze[crebo] = opleiding
    return keuze


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crebo", help="Bouw alleen deze crebo")
    parser.add_argument("--limit", type=int, help="Beperk tot de eerste N crebo's (test)")
    parser.add_argument("--reset", action="store_true", help="Herbouw ook bestaande bestanden")
    args = parser.parse_args()

    _SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    opleidingen = _beste_opleiding_per_crebo()
    kd_domeinen = _kd_domein_per_crebo()

    crebos = sorted(opleidingen)
    if args.crebo:
        crebos = [args.crebo] if args.crebo in opleidingen else []
        if not crebos:
            logger.error("Crebo %s niet gevonden in oer_documenten", args.crebo)
            return 1
    if args.limit:
        crebos = crebos[: args.limit]

    overzicht: list[dict] = []
    gematcht = ongematcht = overgeslagen = 0

    for i, crebo in enumerate(crebos, 1):
        bestand = _SKILLS_DIR / f"{crebo}.json"
        if bestand.exists() and not args.reset:
            overgeslagen += 1
            continue

        opleiding = opleidingen[crebo]
        record = skills_bron.bouw_skills_record(crebo, opleiding, kd_domeinen.get(crebo, ""))
        bestand.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

        ess = sum(1 for s in record.skills if s.categorie == "essentieel")
        opt = sum(1 for s in record.skills if s.categorie == "optioneel")
        beroep = record.beroep.label if record.beroep else "—"
        if record.beroep:
            gematcht += 1
        else:
            ongematcht += 1
            logger.warning("GEEN MATCH  %s  %r  (%s)", crebo, opleiding, record.match_methode)

        overzicht.append(
            {
                "crebo": crebo,
                "opleiding": opleiding,
                "beroep": beroep,
                "methode": record.match_methode,
                "essentieel": ess,
                "optioneel": opt,
                "kandidaten": " | ".join(record.kandidaten),
            }
        )
        logger.info("[%d/%d] %s → %r (%dess/%dopt)", i, len(crebos), crebo, beroep, ess, opt)

    # Review-CSV (her)schrijven met alles wat nu op schijf staat, zodat de tabel
    # compleet is ook na incrementele runs.
    _schrijf_overzicht()

    logger.info(
        "Klaar: %d gematcht, %d zonder match, %d overgeslagen. Artefacten in %s",
        gematcht,
        ongematcht,
        overgeslagen,
        _SKILLS_DIR,
    )
    return 0


def _schrijf_overzicht() -> None:
    """Bouw het match-overzicht opnieuw uit alle JSON-bestanden op schijf."""
    rijen: list[dict] = []
    for pad in sorted(_SKILLS_DIR.glob("*.json")):
        d = json.loads(pad.read_text(encoding="utf-8"))
        skills = d.get("skills", [])
        rijen.append(
            {
                "crebo": d["crebo"],
                "opleiding": d["opleiding"],
                "beroep": (d["beroep"] or {}).get("label", "—") if d["beroep"] else "—",
                "methode": d.get("match_methode", ""),
                "essentieel": sum(1 for s in skills if s["categorie"] == "essentieel"),
                "optioneel": sum(1 for s in skills if s["categorie"] == "optioneel"),
                "kandidaten": " | ".join(d.get("kandidaten", [])),
            }
        )
    overzicht_pad = _SKILLS_DIR / "_match_overzicht.csv"
    with overzicht_pad.open("w", encoding="utf-8", newline="") as f:
        schrijver = csv.DictWriter(
            f,
            fieldnames=[
                "crebo",
                "opleiding",
                "beroep",
                "methode",
                "essentieel",
                "optioneel",
                "kandidaten",
            ],
        )
        schrijver.writeheader()
        schrijver.writerows(rijen)
    logger.info("Review-overzicht: %s (%d rijen)", overzicht_pad, len(rijen))


if __name__ == "__main__":
    sys.exit(main())
