"""Meet input/output tokens en kosten voor OER-only vs OER+KD chat.

Voor een handvol typische vragen vergelijken we twee setups: alleen OER als
context, en OER+KD samen. Per vraag rapporteren we input/output tokens en
cache-gedrag (Sonnet 4.6 standaard tarief).

Vereisten:
    - ANTHROPIC_API_KEY in .env
    - kwalificatiedossiers/pdfs/<crebo>.md aanwezig (zie download/convert-scripts)

Gebruik:
    uv run python scripts/meet_token_kosten.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from validatie_samenwijzer._ai import _client  # noqa: E402
from validatie_samenwijzer.chat import (  # noqa: E402
    bouw_systeem,
    laad_kwalificatiedossier_tekst,
    laad_oer_tekst,
    resolve_oer_pad,
)

# Sonnet 4.6 tarief (USD per 1M tokens; bron: anthropic.com/pricing 2026-05).
PRIJS_INPUT = 3.0 / 1_000_000
PRIJS_OUTPUT = 15.0 / 1_000_000
PRIJS_CACHE_WRITE = 3.75 / 1_000_000  # 25% premium
PRIJS_CACHE_READ = 0.30 / 1_000_000  # 90% korting


@dataclass
class Vraag:
    label: str
    tekst: str
    verwacht: str  # "oer" | "kd-fallback"


VRAGEN = [
    Vraag(
        label="kerntaken",
        tekst="Welke kerntaken horen bij mijn opleiding?",
        verwacht="oer",
    ),
    Vraag(
        label="bpv-uren",
        tekst="Hoeveel uren BPV moet ik in totaal lopen?",
        verwacht="oer",
    ),
    Vraag(
        label="complexiteit",
        tekst="Wat is de complexiteit en verantwoordelijkheid van mijn beroep?",
        verwacht="kd-fallback",
    ),
]


def kies_test_student() -> tuple[str, str, str, str]:
    """Geef (oer_bestandspad, crebo, opleiding, instelling) van een student met KD."""
    db = sqlite3.connect(ROOT / "data" / "validatie.db")
    row = db.execute(
        """SELECT o.bestandspad, o.crebo, o.opleiding, i.display_naam
             FROM oer_documenten o
             JOIN instellingen i ON i.id = o.instelling_id
            WHERE o.geindexeerd = 1 AND o.crebo IS NOT NULL
            LIMIT 1
              OFFSET (SELECT COUNT(*) FROM oer_documenten WHERE geindexeerd=1)/2"""
    ).fetchone()
    db.close()
    return row[0], row[1], row[2], row[3]


def meet_call(client, systeem: str, vraag: str) -> dict:
    """Doe één non-streaming call, return usage-dict."""
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=[{"type": "text", "text": systeem, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": vraag}],
    )
    u = resp.usage
    return {
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "cache_creation": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
        "antwoord_kort": resp.content[0].text[:120].replace("\n", " "),
    }


def usd(usage: dict) -> float:
    return (
        usage["input_tokens"] * PRIJS_INPUT
        + usage["cache_creation"] * PRIJS_CACHE_WRITE
        + usage["cache_read"] * PRIJS_CACHE_READ
        + usage["output_tokens"] * PRIJS_OUTPUT
    )


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY ontbreekt — kan geen calls doen.")
        return 1

    bestandspad, crebo, opleiding, instelling = kies_test_student()
    oer_pad = resolve_oer_pad(bestandspad)
    oer_tekst = laad_oer_tekst(oer_pad)
    kd_tekst = laad_kwalificatiedossier_tekst(crebo)
    if not oer_tekst:
        print(f"Geen OER-tekst voor {bestandspad}")
        return 1
    if not kd_tekst:
        print(f"Geen KD-tekst voor crebo {crebo} — meting beperkt tot OER-only")

    systeem_oer = bouw_systeem(oer_tekst, opleiding, instelling)
    systeem_beide = bouw_systeem(
        oer_tekst, opleiding, instelling, dossier_tekst=kd_tekst, crebo=crebo
    )
    print(
        f"Test-student: opleiding={opleiding!r}, crebo={crebo}, instelling={instelling!r}\n"
        f"OER-tekens={len(oer_tekst):,}  KD-tekens={len(kd_tekst):,}  "
        f"systeem_oer-tekens={len(systeem_oer):,}  systeem_beide-tekens={len(systeem_beide):,}\n"
    )

    client = _client()

    kolommen = ("vraag", "setup", "in", "cache_w", "cache_r", "out", "USD")
    print("{:<14}{:<12}{:>8}{:>10}{:>10}{:>8}{:>10}".format(*kolommen))
    print("-" * 72)

    totaal_oer = totaal_beide = 0.0
    for v in VRAGEN:
        u_oer = meet_call(client, systeem_oer, v.tekst)
        u_beide = meet_call(client, systeem_beide, v.tekst)
        totaal_oer += usd(u_oer)
        totaal_beide += usd(u_beide)
        for label, u in (("OER", u_oer), ("OER+KD", u_beide)):
            print(
                "{:<14}{:<12}{:>8}{:>10}{:>10}{:>8}{:>10.4f}".format(
                    v.label,
                    label,
                    u["input_tokens"],
                    u["cache_creation"],
                    u["cache_read"],
                    u["output_tokens"],
                    usd(u),
                )
            )
    print("-" * 72)
    print(
        f"Totaal OER-only:  ${totaal_oer:.4f}\n"
        f"Totaal OER+KD:    ${totaal_beide:.4f}\n"
        f"Verschil:         ${totaal_beide - totaal_oer:+.4f}  "
        f"({(totaal_beide / totaal_oer - 1) * 100:+.1f}%)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
