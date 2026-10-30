"""Dunne orchestrator: bouwt de chat-context uit gekozen OER-id's.

Laadt per OER de teksten (OER, KD, skills) via ``bron_catalogus`` en de documenten via
``documenten.selecteer_documenten``, bouwt daaruit een ``BronCatalogus`` en laat
``chat.bouw_prompt`` de systeemprompt en het webzoek-besluit maken. UI-vrij en testbaar: de
DB-verbinding en de OER-cache komen als parameter binnen (de app geeft ze uit ``AppDeps``).
"""

from __future__ import annotations

import sqlite3
import threading
from collections import OrderedDict
from dataclasses import dataclass, field

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


def _laad_oer_blok(conn: sqlite3.Connection, oer_id: int):
    """Geef (db-rij, geladen OER-tekst) voor één OER, of None als niet leesbaar/onbekend."""
    row = db.get_oer_met_instelling(conn, oer_id)
    if row is None:
        return None
    tekst = laad_oer_tekst(resolve_oer_pad(row["bestandspad"]))
    return row, tekst  # tekst mag leeg zijn (gescande OER) — laad_context beslist op KD/bron


class OerBlokken:
    """LRU-cache van (db-rij, OER-tekst) per ``oer_id`` — één per app-instantie.

    Hangt aan ``AppDeps.oer_blokken``: een nieuwe app (herstart, re-ingest + redeploy, of een
    test) begint leeg, en twee app-instanties delen niets. Bewust begrensd (OER-tekst tot 500K
    tekens per stuk). Ook ``None`` (onbekende id) wordt gecachet, zoals de oude ``lru_cache``.
    """

    def __init__(self, maxsize: int = 64) -> None:
        self.maxsize = maxsize
        self._items: OrderedDict[int, tuple | None] = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._items)

    def haal(self, conn: sqlite3.Connection, oer_id: int):
        """Geef het gecachete blok, of laad en cache het (zie :func:`_laad_oer_blok`)."""
        with self._lock:
            if oer_id in self._items:
                self._items.move_to_end(oer_id)
                return self._items[oer_id]
        blok = _laad_oer_blok(conn, oer_id)  # buiten de lock: bestands-I/O
        with self._lock:
            self._items[oer_id] = blok
            self._items.move_to_end(oer_id)
            while len(self._items) > self.maxsize:
                self._items.popitem(last=False)
        return blok

    def leeg(self) -> None:
        with self._lock:
            self._items.clear()


@dataclass(frozen=True)
class ChatContext:
    """De geladen chat-context voor één of meer OER's — één waarde, één eigenaar.

    ``systeem`` is leeg als geen enkele OER een bruikbare bron had; ``oer_ids`` blijft dan
    toch gevuld (max. 3, zoals gevraagd), zodat de chat 'lage relevantie' kan melden.
    ``bron_register`` (``BronCatalogus.register(prompt.web_domeinen)``) is JSON-serialiseerbaar
    en hoort in de server-side sessie; ``chat.splits_bronnen(antwoord, register)`` herleidt
    daarmee de titels in de bronnenregel naar bekende bronnen (met ``oer_id``/``doc_id``/
    ``crebo``) en wijst verzonnen titels af.
    """

    systeem: str = ""
    labels: list[str] = field(default_factory=list)
    domeinen: list[str] = field(default_factory=list)
    oer_onleesbaar: bool = False
    melding: str = ""
    oer_ids: list[int] = field(default_factory=list)
    bron_register: list[dict] = field(default_factory=list)


def laad_context(
    conn: sqlite3.Connection,
    oer_ids: list[int],
    niveau: str = "publiek",
    *,
    oer_blokken: OerBlokken | None = None,
) -> ChatContext:
    """Geef de :class:`ChatContext` voor de OER's (gelezen via ``conn``).

    Per OER de volledige tekst + KD + skills; de bijbehorende documenten (instellingsbreed en
    opleidingsgebonden) komen uit ``documenten.selecteer_documenten`` binnen het budget, op basis
    van het ``niveau`` (publiek/student/mentor). De ``BronCatalogus`` laat OER's zonder enige
    bruikbare bron weg; een OER zonder leesbare tekst (gescande PDF) blijft staan als er een KD
    of document is (KD-fallback) en dan is ``oer_onleesbaar`` True. ``melding`` is niet leeg als
    documenten buiten het budget vielen. Lege ``systeem`` + leeg register als geen enkele OER
    een bruikbare bron heeft. ``oer_blokken`` (de cache van de app) is optioneel; zonder laadt
    elke aanroep de OER-teksten opnieuw (scripts).
    """
    haal = oer_blokken.haal if oer_blokken is not None else _laad_oer_blok
    gevonden = [res for oid in oer_ids[:3] if (res := haal(conn, oid)) is not None]
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
        return ChatContext(oer_ids=list(oer_ids[:3]))

    prompt = bouw_prompt(catalogus)
    labels = [
        f"{o.invoer.instelling} · "
        f"{nette_opleiding_naam(o.invoer.crebo or '', o.invoer.opleiding)} · "
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
    return ChatContext(
        systeem=prompt.systeem,
        labels=labels,
        domeinen=prompt.web_domeinen,
        oer_onleesbaar=catalogus.oer_onleesbaar,
        melding=melding,
        oer_ids=list(oer_ids[:3]),
        bron_register=catalogus.register(prompt.web_domeinen),
    )
