"""Dunne orchestrator: bouwt de chat-context uit gekozen OER-id's.

Hergebruikt de loaders en system-prompt-bouwers uit ``chat.py`` ongewijzigd; dit is
precies wat ``app/pages/0_oer_vraag.py`` nu inline doet, maar UI-vrij en testbaar.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from functools import lru_cache

from validatie_samenwijzer import db
from validatie_samenwijzer.chat import (
    bouw_gecombineerd_systeem,
    laad_kwalificatiedossier_tekst,
    laad_oer_tekst,
    laad_skills_tekst,
    resolve_oer_pad,
    vacature_domeinen,
    web_zoek_domeinen,
)
from validatie_samenwijzer.documenten import selecteer_documenten
from validatie_samenwijzer.opleiding import nette_opleiding_naam

_gemigreerd: set[str] = set()


def _conn() -> sqlite3.Connection:
    """DB-verbinding; migreert het schema één keer per proces (de ingebakken productie-DB kan
    van vóór de `documenten`-tabel zijn; `init_db` is idempotent)."""
    pad = os.environ.get("DB_PATH", "data/validatie.db")
    conn = db.get_connection(pad)
    if pad not in _gemigreerd:
        db.init_db(conn)
        _gemigreerd.add(pad)
    return conn


@lru_cache(maxsize=64)
def _oer_blok(oer_id: int):
    """Geef (db-rij, geladen OER-tekst) voor één OER, of None als niet leesbaar/onbekend."""
    row = db.get_oer_met_instelling(_conn(), oer_id)
    if row is None:
        return None
    tekst = laad_oer_tekst(resolve_oer_pad(row["bestandspad"]))
    return row, tekst  # tekst mag leeg zijn (gescande OER) — laad_context beslist op KD/bron


@dataclass(frozen=True)
class ChatContext:
    """De geladen chat-context voor één of meer OER's — één waarde, één eigenaar.

    ``systeem`` is leeg als geen enkele OER een bruikbare bron had; ``oer_ids`` blijft dan
    toch gevuld (max. 3, zoals gevraagd), zodat de chat 'lage relevantie' kan melden.
    """

    systeem: str = ""
    labels: list[str] = field(default_factory=list)
    domeinen: list[str] = field(default_factory=list)
    oer_onleesbaar: bool = False
    melding: str = ""
    oer_ids: list[int] = field(default_factory=list)


def laad_context(oer_ids: list[int], niveau: str = "publiek") -> ChatContext:
    """Geef de :class:`ChatContext` (system-prompt, labels, web-zoek-domeinen, onleesbaar-vlag,
    melding, OER-id's) voor de OER's.

    Per OER de volledige tekst + KD + skills; de bijbehorende documenten (instellingsbreed en
    opleidingsgebonden) komen uit ``documenten.selecteer_documenten`` binnen het budget, op basis
    van het ``niveau`` (publiek/student/mentor). Gecombineerd via ``bouw_gecombineerd_systeem``.
    Een OER zonder leesbare tekst (gescande PDF) wordt tóch opgenomen als er een KD of
    document is (KD-fallback); ``oer_onleesbaar`` is dan True. ``melding`` is niet leeg als
    documenten buiten het budget vielen. Lege string + False als geen enkele OER een bruikbare
    bron heeft.
    """
    conn = _conn()
    gevonden = [res for oid in oer_ids[:3] if (res := _oer_blok(oid)) is not None]
    selectie = selecteer_documenten(conn, [row for row, _ in gevonden], niveau)

    items: list[dict] = []
    labels: list[str] = []
    oer_onleesbaar = False
    for row, tekst in gevonden:
        crebo = row["crebo"]
        instelling_bronnen = [(d.kop, d.tekst) for d in selectie.per_oer.get(row["id"], [])]
        dossier_tekst = laad_kwalificatiedossier_tekst(crebo, row["cohort"])
        # Onleesbare OER (gescande PDF) tóch opnemen als er een KD of document is.
        if not tekst.strip() and not dossier_tekst and not instelling_bronnen:
            continue
        if not tekst.strip():
            oer_onleesbaar = True

        items.append(
            {
                "tekst": tekst,
                "opleiding": row["opleiding"],
                "display_naam": row["display_naam"],
                "naam": row["naam"],  # korte instelling-sleutel — voor web_zoek_domeinen
                "leerweg": row["leerweg"],
                "cohort": row["cohort"],
                "crebo": crebo,
                "dossier_tekst": dossier_tekst,
                "skills_tekst": laad_skills_tekst(crebo),
                "instelling_bronnen": instelling_bronnen,
            }
        )
        labels.append(
            f"{row['display_naam']} · {nette_opleiding_naam(crebo, row['opleiding'])} · "
            f"{row['leerweg']} {row['cohort']}"
        )

    if not items:
        return ChatContext(oer_ids=list(oer_ids[:3]))
    melding = (
        "Niet alle documenten pasten in dit gesprek; weggelaten: "
        + ", ".join(selectie.afgevallen)
        + "."
        if selectie.afgevallen
        else ""
    )
    school_domeinen = web_zoek_domeinen(items)
    # Vacaturezoek is altijd beschikbaar (beroep bekend via de OER/skills); het prompt-blok
    # gate't zelf op een expliciete vacaturevraag. Los van school_domeinen, zodat het ook
    # werkt bij een instelling zonder scrapebaar webdomein.
    systeem = bouw_gecombineerd_systeem(items, web_zoeken=bool(school_domeinen), vacatures=True)
    domeinen = sorted(set(school_domeinen) | set(vacature_domeinen()))
    return ChatContext(systeem, labels, domeinen, oer_onleesbaar, melding, list(oer_ids[:3]))
