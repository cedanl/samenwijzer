"""Vergelijk chatmodellen op citaattrouw, snelheid en geschatte kosten.

Draait dezelfde productie-aanroep (`chat.genereer_antwoord`, effort low, 1h-cache) met de
publieke context (`app_fastapi.context.laad_context`) voor een kleine, vaste set OER's en
vragen. Per antwoord controleert het script of elk woordelijk citaat (tekst tussen
aanhalingstekens, ≥ 25 tekens) letterlijk in de systeemprompt voorkomt — de juridische
citatieplicht. Het meet geen inhoudelijke juistheid; lees de antwoorden (--uit) steekproefsgewijs.

Kosten: ~$0,3 per OER voor Sonnet 5.5 (cache-write), ~$0,02 voor Haiku 5.5. Standaard 4 OER's
× 4 vragen.

Gebruik (vanuit validatie_samenwijzer/):
    uv run python scripts/vergelijk_modellen.py
    uv run python scripts/vergelijk_modellen.py --modellen claude-haiku-5-5 --oers 2
    uv run python scripts/vergelijk_modellen.py --uit /tmp/antwoorden.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from app_fastapi import context  # noqa: E402
from app_fastapi.deps import ValidatieDb  # noqa: E402
from validatie_samenwijzer._ai import _client  # noqa: E402
from validatie_samenwijzer.chat import genereer_antwoord  # noqa: E402

STANDAARD_MODELLEN = ("claude-sonnet-5-5", "claude-haiku-5-5")
INSTELLINGEN = ("curio", "kwic", "landstede", "rijn_ijssel")
VRAGEN = (
    "Hoeveel studiepunten moet ik halen om geen negatief bindend studieadvies te krijgen?",
    "Hoe vaak mag ik een examen herkansen?",
    "Wat moet ik doen als ik ziek ben op de dag van een examen?",
    "Welke kerntaken horen bij mijn opleiding?",
)
MIN_CITAAT_TEKENS = 25
_DB = ValidatieDb(os.environ.get("DB_PATH", "data/validatie.db"))
_OER_BLOKKEN = context.OerBlokken()  # kies_oers en main laden dezelfde OER's

# Prijs per miljoen tokens (platform.claude.com/docs/en/about-claude/pricing, okt 2026):
# (invoer, 1h-cache-write, cache-read, uitvoer); Haiku 5.5 heeft een tarief tot en met
# 100K prompttokens en een hoger tarief erboven.
PRIJZEN = {
    "claude-sonnet-5-5": ((2.0, 4.0, 0.10, 10.0),),
    "claude-haiku-5-5": ((0.10, 0.20, 0.01, 0.50), (0.50, 1.0, 0.05, 2.50)),
}
HAIKU_DREMPEL = 100_000

# Alleen citaten die als eigen regel/alinea staan ("..." of > "..."), zoals de prompt eist;
# losse aanhalingstekens midden in een zin leveren te veel valse alarmen op (verkeerd gepaard).
_CITAAT = re.compile(
    rf"^[ \t>*_-]*[\"“„]([^\"”“„\n]{{{MIN_CITAAT_TEKENS},}})[\"”“][ \t*_.]*$", re.MULTILINE
)
# Weglatingstekens en opsommingen (`;`) in een citaat: elk deel moet los in de bron staan.
_SCHEIDING = re.compile(r"\.{3}|…|\[\s*\.{3}\s*\]|\[…\]|;")


def _normaliseer(tekst: str) -> str:
    tekst = re.sub(r"(?m)^\s*[-•●▪◦]\s+", " ", tekst)  # opsommingstekens zijn opmaak
    tekst = re.sub(r"[*_#|>`]", " ", tekst)
    tekst = tekst.replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", tekst).strip().lower()


def citaten_in(antwoord: str) -> list[str]:
    return [m.group(1) for m in _CITAAT.finditer(antwoord)]


def ongegrond(antwoord: str, bron: str) -> list[str]:
    """Citaten (of citaatdelen tussen weglatingstekens) die niet letterlijk in de bron staan."""
    bron_n = _normaliseer(bron)
    fout = []
    for citaat in citaten_in(antwoord):
        for deel in _SCHEIDING.split(citaat):
            deel_n = _normaliseer(deel).strip(" .,;:")
            if len(deel_n) >= MIN_CITAAT_TEKENS and deel_n not in bron_n:
                fout.append(deel.strip())
    return fout


def kies_oers(aantal: int) -> list[tuple[int, str, str]]:
    """Eerste geïndexeerde OER met de grootste context per gekozen instelling."""
    gekozen = []
    with _DB.verbinding() as conn:
        for naam in INSTELLINGEN[:aantal]:
            rijen = conn.execute(
                "SELECT o.id, o.opleiding FROM oer_documenten o JOIN instellingen i "
                "ON i.id = o.instelling_id WHERE i.naam = ? AND o.geindexeerd = 1",
                (naam,),
            ).fetchall()
            kandidaten = []
            for r in rijen:
                systeem = laad_systeem(conn, r["id"])
                if systeem:
                    kandidaten.append((len(systeem), r["id"], r["opleiding"]))
            if kandidaten:
                kandidaten.sort()
                _, oer_id, opleiding = kandidaten[len(kandidaten) // 2]  # mediaan i.p.v. extreem
                gekozen.append((oer_id, naam, opleiding))
    return gekozen


def laad_systeem(conn, oer_id: int) -> str:
    return context.laad_context(conn, [oer_id], oer_blokken=_OER_BLOKKEN).systeem


def schat_kosten(model: str, prompt_tokens: int, uitvoer_tokens: int, eerste: bool) -> float:
    tarieven = PRIJZEN[model]
    inv, write, read, uit = tarieven[
        1 if len(tarieven) > 1 and prompt_tokens > HAIKU_DREMPEL else 0
    ]
    return (prompt_tokens * (write if eerste else read) + uitvoer_tokens * uit) / 1_000_000


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--modellen", nargs="+", default=list(STANDAARD_MODELLEN))
    ap.add_argument("--oers", type=int, default=len(INSTELLINGEN), help="aantal instellingen")
    ap.add_argument("--uit", help="schrijf alle antwoorden naar dit JSON-bestand")
    args = ap.parse_args()

    client = _client()
    oers = kies_oers(args.oers)
    print(f"{len(oers)} OER's × {len(VRAGEN)} vragen × {len(args.modellen)} modellen\n")

    samenvatting: dict[str, dict] = {
        m: dict(n=0, citaten=0, fout=0, ttft=[], totaal=[], kosten=0.0, leeg=0)
        for m in args.modellen
    }
    log: list[dict] = []
    for oer_id, inst, opleiding in oers:
        with _DB.verbinding() as conn:
            systeem = laad_systeem(conn, oer_id)
        for model in args.modellen:
            prompt_tokens = client.messages.count_tokens(
                model=model, system=systeem, messages=[{"role": "user", "content": VRAGEN[0]}]
            ).input_tokens
            for i, vraag in enumerate(VRAGEN):
                start = time.perf_counter()
                eerste_chunk = None
                delen = []
                for chunk in genereer_antwoord(
                    client, systeem, [{"role": "user", "content": vraag}], model=model
                ):
                    if eerste_chunk is None:
                        eerste_chunk = time.perf_counter() - start
                    if isinstance(chunk, str):
                        delen.append(chunk)
                totaal = time.perf_counter() - start
                antwoord = "".join(delen)
                fouten = ongegrond(antwoord, systeem)
                s = samenvatting[model]
                s["n"] += 1
                s["leeg"] += not antwoord.strip()
                s["citaten"] += len(citaten_in(antwoord))
                s["fout"] += len(fouten)
                s["ttft"].append(eerste_chunk or totaal)
                s["totaal"].append(totaal)
                s["kosten"] += schat_kosten(model, prompt_tokens, len(antwoord) // 3, i == 0)
                log.append(
                    dict(
                        model=model,
                        instelling=inst,
                        opleiding=opleiding,
                        vraag=vraag,
                        antwoord=antwoord,
                        ongegronde_citaten=fouten,
                        prompt_tokens=prompt_tokens,
                    )
                )
                print(
                    f"  {model:18} {inst:12} v{i + 1}: {len(citaten_in(antwoord))} citaten, "
                    f"{len(fouten)} ongegrond, {totaal:5.1f}s"
                )

    print(
        "\n| model | antwoorden | leeg | citaten | ongegrond | trouw | TTFT gem. | totaal gem. "
        "| ~kosten |"
    )
    print("|---|---|---|---|---|---|---|---|---|")
    for model, s in samenvatting.items():
        trouw = 1 - s["fout"] / s["citaten"] if s["citaten"] else float("nan")
        print(
            f"| {model} | {s['n']} | {s['leeg']} | {s['citaten']} | {s['fout']} | {trouw:.0%} | "
            f"{sum(s['ttft']) / len(s['ttft']):.1f}s | "
            f"{sum(s['totaal']) / len(s['totaal']):.1f}s | "
            f"${s['kosten']:.2f} |"
        )
    if args.uit:
        Path(args.uit).write_text(json.dumps(log, ensure_ascii=False, indent=2))
        print(f"\nAntwoorden: {args.uit}")


if __name__ == "__main__":
    main()
