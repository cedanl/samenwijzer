"""Dunne orchestrator: bouwt de chat-context uit gekozen OER-id's.

Laadt per OER de teksten (OER, KD, skills) via ``bron_catalogus`` en de documenten via
``documenten.selecteer_documenten``, bouwt daaruit een ``BronCatalogus`` en laat
``chat.bouw_prompt`` de systeemprompt en het webzoek-besluit maken. UI-vrij en testbaar.
"""

from __future__ import annotations

import os
import sqlite3
from functools import lru_cache

from validatie_samenwijzer import db
from validatie_samenwijzer.bron_catalogus import (
    BronCatalogus,
    OerInvoer,
    laad_kwalificatiedossier_tekst,
    laad_oer_tekst,
    laad_skills_tekst,
    resolve_oer_pad,
)
from validatie_samenwijzer.chat import bouw_prompt
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


def laad_context_met_melding(
    oer_ids: list[int], niveau: str = "publiek"
) -> tuple[str, list[str], list[str], bool, str]:
    """Geef (system-prompt, labels, web-zoek-domeinen, oer_onleesbaar, melding) voor de OER's.

    Per OER de volledige tekst + KD + skills; de bijbehorende documenten (instellingsbreed en
    opleidingsgebonden) komen uit ``documenten.selecteer_documenten`` binnen het budget, op basis
    van het ``niveau`` (publiek/student/mentor). De ``BronCatalogus`` laat OER's zonder enige
    bruikbare bron weg; een OER zonder leesbare tekst (gescande PDF) blijft staan als er een KD
    of document is (KD-fallback) en dan is ``oer_onleesbaar`` True. ``melding`` is niet leeg als
    documenten buiten het budget vielen. Lege string + False als geen enkele OER een bruikbare
    bron heeft.
    """
    conn = _conn()
    gevonden = [res for oid in oer_ids[:3] if (res := _oer_blok(oid)) is not None]
    selectie = selecteer_documenten(conn, [row for row, _ in gevonden], niveau)
    catalogus = BronCatalogus.bouw(
        OerInvoer(
            opleiding=row["opleiding"],
            instelling=row["display_naam"],
            oer_id=row["id"],
            instelling_sleutel=row["naam"],
            leerweg=row["leerweg"],
            cohort=row["cohort"],
            crebo=row["crebo"],
            oer_tekst=tekst,
            kd_tekst=laad_kwalificatiedossier_tekst(row["crebo"], row["cohort"]),
            skills_tekst=laad_skills_tekst(row["crebo"]),
            documenten=tuple(selectie.per_oer.get(row["id"], [])),
        )
        for row, tekst in gevonden
    )
    if catalogus.leeg:
        return "", [], [], False, ""

    prompt = bouw_prompt(catalogus)
    labels = [
        f"{o.invoer.instelling} · {nette_opleiding_naam(o.invoer.crebo, o.invoer.opleiding)} · "
        f"{o.invoer.leerweg} {o.invoer.cohort}"
        for o in catalogus.oers
    ]
    melding = (
        "Niet alle documenten pasten in dit gesprek; weggelaten: "
        + ", ".join(selectie.afgevallen)
        + "."
        if selectie.afgevallen
        else ""
    )
    return prompt.systeem, labels, prompt.web_domeinen, catalogus.oer_onleesbaar, melding


def laad_context(
    oer_ids: list[int], niveau: str = "publiek"
) -> tuple[str, list[str], list[str], bool]:
    """Als :func:`laad_context_met_melding` zonder de melding (vier-tuple, oud contract)."""
    return laad_context_met_melding(oer_ids, niveau)[:4]
