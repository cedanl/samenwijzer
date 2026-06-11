"""Dunne orchestrator: bouwt de chat-context uit gekozen OER-id's.

Hergebruikt de loaders en system-prompt-bouwers uit ``chat.py`` ongewijzigd; dit is
precies wat ``app/pages/0_oer_vraag.py`` nu inline doet, maar UI-vrij en testbaar.
"""

from __future__ import annotations

import os
import sqlite3
from functools import lru_cache

from validatie_samenwijzer import db
from validatie_samenwijzer.chat import (
    bouw_gecombineerd_systeem,
    laad_instelling_bron_tekst,
    laad_kwalificatiedossier_tekst,
    laad_oer_tekst,
    laad_skills_tekst,
    resolve_oer_pad,
    vacature_domeinen,
    web_zoek_domeinen,
)
from validatie_samenwijzer.opleiding import schoon_opleiding_naam

# Welke instellingsbrede documenten als bron meegaan, per context — mirror van
# app/main.py (_STUDENT_SOORTEN/_MENTOR_SOORTEN) en 0_oer_vraag.py (publiek = enkel
# examenreglement). Labels komen uit db.INSTELLING_SOORTEN (bron van waarheid).
PUBLIEK_SOORTEN = ("examenreglement",)
STUDENT_SOORTEN = (
    "examenreglement",
    "studentenstatuut",
    "bindend_studieadvies",
    "klachtenregeling",
    "gedragscode",
    "algemene_informatie",
)
MENTOR_SOORTEN = (
    "examenreglement",
    "begeleidingsbeleid",
    "studentenstatuut",
    "bindend_studieadvies",
    "klachtenregeling",
    "gedragscode",
    "algemene_informatie",
)


def _conn() -> sqlite3.Connection:
    return db.get_connection(os.environ.get("DB_PATH", "data/validatie.db"))


@lru_cache(maxsize=64)
def _oer_blok(oer_id: int):
    """Geef (db-rij, geladen OER-tekst) voor één OER, of None als niet leesbaar/onbekend."""
    row = (
        _conn()
        .execute(
            """SELECT o.*, i.display_naam, i.naam
           FROM oer_documenten o JOIN instellingen i ON i.id = o.instelling_id
           WHERE o.id = ?""",
            (oer_id,),
        )
        .fetchone()
    )
    if row is None:
        return None
    tekst = laad_oer_tekst(resolve_oer_pad(row["bestandspad"]))
    return row, tekst  # tekst mag leeg zijn (gescande OER) — laad_context beslist op KD/bron


def laad_context(
    oer_ids: list[int], soorten: tuple[str, ...] = PUBLIEK_SOORTEN
) -> tuple[str, list[str], list[str], bool]:
    """Geef (system-prompt, labels, web-zoek-domeinen, oer_onleesbaar) voor de gekozen OER's.

    Spiegelt 0_oer_vraag.py: per OER de volledige tekst + KD + skills + examenreglement
    (instellingsbrede bron), gecombineerd via ``bouw_gecombineerd_systeem``. Een OER zonder
    leesbare tekst (gescande PDF) wordt tóch opgenomen als er een KD of instellingsbron is
    (KD-fallback, mirror van PR #182); ``oer_onleesbaar`` is dan True (→ banner in de UI).
    Lege string + False als geen enkele OER een bruikbare bron heeft.
    """
    items: list[dict] = []
    labels: list[str] = []
    oer_onleesbaar = False
    conn = _conn()
    for oid in oer_ids[:3]:
        res = _oer_blok(oid)
        if res is None:
            continue
        row, tekst = res
        crebo = row["crebo"]

        instelling_bronnen: list[tuple[str, str]] = []
        for soort in soorten:
            doc = db.haal_instelling_document_op(conn, row["instelling_id"], soort)
            if doc is None or not doc["geindexeerd"]:
                continue
            doc_tekst = laad_instelling_bron_tekst(resolve_oer_pad(doc["bestandspad"]))
            if doc_tekst:
                instelling_bronnen.append((db.INSTELLING_SOORTEN[soort], doc_tekst))

        dossier_tekst = laad_kwalificatiedossier_tekst(crebo)
        # Onleesbare OER (gescande PDF) tóch opnemen als er een KD of instellingsbron is.
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
            f"{row['display_naam']} · {schoon_opleiding_naam(row['opleiding'], crebo)} · "
            f"{row['leerweg']} {row['cohort']}"
        )

    if not items:
        return "", [], [], False
    school_domeinen = web_zoek_domeinen(items)
    # Vacaturezoek is altijd beschikbaar (beroep bekend via de OER/skills); het prompt-blok
    # gate't zelf op een expliciete vacaturevraag. Los van school_domeinen, zodat het ook
    # werkt bij een instelling zonder scrapebaar webdomein.
    systeem = bouw_gecombineerd_systeem(items, web_zoeken=bool(school_domeinen), vacatures=True)
    domeinen = sorted(set(school_domeinen) | set(vacature_domeinen()))
    return systeem, labels, domeinen, oer_onleesbaar
