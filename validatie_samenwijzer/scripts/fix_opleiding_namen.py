"""Heal: vul ontbrekende opleidingsnamen aan in oer_documenten.

Sommige OER-records hebben een bestandsnaam zonder leesbare opleidingsnaam
(bv. Da Vinci '25882_BOL_2025__25882BOL2025Examenplan.pdf') en renderen daardoor
als 'Opleiding <crebo>'. Dit script vult de echte naam aan uit twee bronnen:

1. **Eigen bestand** — een sibling-bestandsnaam mét opleidingsnaam (bv. een
   MJP-bestand naast een kale Examenplan) óf de PDF-titelpagina van een same-crebo
   bestand; de kwalitatief beste wint (zie ``_kwaliteit``).
2. **Crebo-leen**: de beste naam die een ander OER-record met dezelfde crebo
   (de landelijke opleidingscode) al heeft — voor cover-pagina's zonder naam
   ('EXAMENPLAN' / 'Opleidingsplanning').

Twee passes: eerst de eigen bestanden (pass 1), dan crebo-leen voor wat overblijft
(pass 2, ziet de pass-1-fixes). Idempotent — records die al een schone naam hebben
worden overgeslagen.

    uv run python scripts/fix_opleiding_namen.py --dry-run
    uv run python scripts/fix_opleiding_namen.py --instelling davinci
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from validatie_samenwijzer.db import get_connection, update_oer_opleiding
from validatie_samenwijzer.ingest import (
    _MAP_NAAM,
    _extraheer_opleiding_uit_pdf,
    _stem_heeft_opleidingsnaam,
)
from validatie_samenwijzer.opleiding import schoon_opleiding_naam

log = logging.getLogger("fix_opleiding_namen")


def _is_naamloos(opleiding: str, crebo: str) -> bool:
    """True als het record als 'Opleiding <crebo>' zou renderen."""
    return schoon_opleiding_naam(opleiding, crebo).startswith("Opleiding")


def _kwaliteit(schoon: str) -> tuple[int, int]:
    """Sorteersleutel: meer natuurlijke woorden = beter, daarna minder ruis.

    Een 'natuurlijk' woord is ≥3 letters en niet volledig hoofdletters — zo wint
    'Eerste monteur service en onderhoud werktuigbouw' van de afkorting 'EMSO WTB',
    maar wint de strakke 'Monteur Werktuigkundige Installaties' van de variant met
    een 'BOL/BBL'-staart (gelijk aantal natuurlijke woorden, minder tokens).
    """
    toks = schoon.split()
    natuurlijk = sum(1 for t in toks if len(t) >= 3 and not t.isupper())
    return (natuurlijk, -len(toks))


def _eigen_naam(crebo: str, inst: str, oeren_root: Path) -> tuple[str | None, str | None]:
    """Beste naam uit de eigen bestanden van de instelling voor deze crebo.

    Verzamelt kandidaten uit zowel sibling-bestandsnamen (bv. een MJP-bestand naast
    een kale Examenplan) als de PDF-titelpagina's van same-crebo bestanden, en kiest
    de kwalitatief beste (zie ``_kwaliteit``). Geeft (ruwe_naam, bron) of (None, None).
    """
    map_naam = _MAP_NAAM.get(inst)
    if not map_naam:
        return None, None
    inst_dir = oeren_root / map_naam
    if not inst_dir.is_dir():
        return None, None
    files = sorted(
        p
        for p in inst_dir.glob(f"*{crebo}*")
        if p.suffix.lower() in {".pdf", ".md", ".html", ".htm"}
    )
    kandidaten: list[tuple[str, str]] = []  # (ruwe_naam, bron)
    for f in files:
        stem = f.stem[:100]
        if _stem_heeft_opleidingsnaam(stem) and not _is_naamloos(stem, crebo):
            kandidaten.append((stem, "bestandsnaam"))
    for f in files:
        if f.suffix.lower() == ".pdf":
            naam = _extraheer_opleiding_uit_pdf(f)
            if naam and not _is_naamloos(naam, crebo):
                kandidaten.append((naam, "titelpagina"))
    if not kandidaten:
        return None, None
    return max(kandidaten, key=lambda k: _kwaliteit(schoon_opleiding_naam(k[0], crebo)))


def _leen_van_crebo(conn, crebo: str, *, prefer_instelling: str | None = None) -> str | None:
    """Geef de beste naam die een ander record met dezelfde crebo al heeft.

    Crebo is de landelijke opleidingscode, dus de naam is gedeeld. Keuze:
    1. zelfde instelling (bv. een andere leerweg die al gevuld is);
    2. anders de meest voorkomende schone naam over alle instellingen (consensus),
       tie-break op het minste aantal woorden (vermijdt kerntaak-prefixen zoals
       Deltion's 'Meubels … maken Ondernemend meubelmaker …').
    """
    from collections import Counter

    rows = conn.execute(
        """SELECT i.naam, o.opleiding FROM oer_documenten o
           JOIN instellingen i ON o.instelling_id = i.id WHERE o.crebo = ?""",
        (crebo,),
    ).fetchall()
    schoon_kand = [(inst, opl, schoon_opleiding_naam(opl, crebo)) for inst, opl in rows]
    schoon_kand = [k for k in schoon_kand if not k[2].startswith("Opleiding")]
    if not schoon_kand:
        return None
    eigen = [k for k in schoon_kand if k[0] == prefer_instelling]
    if eigen:
        return eigen[0][1]
    freq = Counter(k[2] for k in schoon_kand)
    beste = max(schoon_kand, key=lambda k: (freq[k[2]], -len(k[2].split())))
    return beste[1]


def _naamloze_records(conn, instelling: str | None) -> list[tuple]:
    q = """SELECT o.id, o.opleiding, o.crebo, o.bestandspad, i.naam
           FROM oer_documenten o JOIN instellingen i ON o.instelling_id = i.id"""
    params: tuple = ()
    if instelling:
        q += " WHERE i.naam = ?"
        params = (instelling,)
    rows = conn.execute(q, params).fetchall()
    return [r for r in rows if _is_naamloos(r[1], r[2])]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instelling", help="beperk tot deze instelling-naam (bv. davinci)")
    ap.add_argument("--dry-run", action="store_true", help="toon wijzigingen, schrijf niets")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    conn = get_connection(Path(os.environ.get("DB_PATH", "data/validatie.db")))
    oeren_root = Path(os.environ.get("OEREN_PAD", "oeren")).resolve()
    start = _naamloze_records(conn, args.instelling)
    log.info("Naamloze records: %d", len(start))

    n_eigen = 0
    gefixt: set[int] = set()
    # Pass 1 — eigen bestanden (sibling-bestandsnaam of titelpagina)
    for oer_id, _opl, crebo, _pad, inst in start:
        naam, bron = _eigen_naam(crebo, inst, oeren_root)
        if naam:
            log.info(
                "[%s] %s/%s: 'Opleiding %s' → '%s'",
                bron,
                inst,
                crebo,
                crebo,
                schoon_opleiding_naam(naam, crebo),
            )
            if not args.dry_run:
                update_oer_opleiding(conn, oer_id, naam)
            gefixt.add(oer_id)
            n_eigen += 1

    # Pass 2 — crebo-leen voor wat pass 1 niet kon vullen
    n_leen = 0
    resterend: list[tuple] = []
    for oer_id, opl, crebo, _pad, inst in start:
        if oer_id in gefixt:
            continue
        naam = _leen_van_crebo(conn, crebo, prefer_instelling=inst)
        if naam:
            log.info(
                "[crebo-leen] %s/%s: 'Opleiding %s' → '%s'",
                inst,
                crebo,
                crebo,
                schoon_opleiding_naam(naam, crebo),
            )
            if not args.dry_run:
                update_oer_opleiding(conn, oer_id, naam)
            n_leen += 1
        else:
            resterend.append((inst, crebo, opl))

    log.info(
        "%sGefixt: %d (eigen bestand=%d, crebo-leen=%d) — resterend naamloos: %d",
        "[DRY-RUN] " if args.dry_run else "",
        n_eigen + n_leen,
        n_eigen,
        n_leen,
        len(resterend),
    )
    for inst, crebo, opl in resterend:
        log.info("  RESTEREND %s/%s: %r", inst, crebo, opl)


if __name__ == "__main__":
    main()
