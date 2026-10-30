"""Server-side sessiestate voor de OER-chat (publiek én ingelogd).

De gecombineerde system-prompt is tot ~500K tekens × 3 → past nooit in een cookie.
Daarom houdt een ondertekende cookie (via Starlette ``SessionMiddleware``) enkel een
``sid``; de echte state leeft in een **SQLite-store** (``SessieStore``, één per app via
``AppDeps.sessie_store``; standaard ``data/sessies.db``, write-through met TTL-opruiming).
Spiegelt het ``pub_*``-session_state-contract van ``app/pages/0_oer_vraag.py``.

Schaal-grens (bewust, Fase 1): één machine. De store overleeft proces-restarts, maar
niet een redeploy (nieuwe ephemerale container-fs). Multi-machine zou een gedeelde store
(Redis) of een Fly-volume vereisen — buiten scope. Zie de FastAPI-migratie-spec.
"""

from __future__ import annotations

import copy
import json
import sqlite3
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING

from validatie_samenwijzer.gesprek import MAX_GESCHIEDENIS, Gesprek  # noqa: F401 — her-export

if TYPE_CHECKING:
    from app_fastapi.context import ChatContext


@dataclass
class Sessie:
    # Chat-/OER-context (publiek én ingelogd)
    gesprek: Gesprek = field(default_factory=Gesprek)  # opslagsleutel in sessies.db: chat_history
    oer_systeem: str | None = None
    oer_labels: list[str] = field(default_factory=list)
    oer_ids: list[int] = field(default_factory=list)
    oer_onleesbaar: bool = False  # OER-fulltext onleesbaar (gescand) → banner + KD-fallback
    melding: str = ""  # documenten buiten budget weggelaten → banner
    domeinen: list[str] = field(default_factory=list)
    bron_register: list[dict] = field(default_factory=list)  # BronCatalogus.register()
    wachtende_vraag: str | None = None
    # Algemene toegang (gedeeld wachtwoord — sommige instellingen zetten hun OER
    # achter een wachtwoord, dus de hele app zit achter deze poort).
    toegang: bool = False
    # Ingelogde gebruiker (None = publiek)
    rol: str | None = None  # "student" | "mentor"
    gebruiker: dict | None = None  # {id, naam, studentnummer?}

    def laad_context(self, ctx: ChatContext) -> None:
        """Neem een geladen :class:`ChatContext` over — de enige plek die deze velden zet.

        Wist ook een wachtende kies-vraag en de melding van een eerdere context; de
        gesprek blijft (gebruik :meth:`nieuw_gesprek` om dat te wissen).
        """
        self.oer_systeem = ctx.systeem
        self.oer_labels = list(ctx.labels)
        self.domeinen = list(ctx.domeinen)
        self.oer_onleesbaar = ctx.oer_onleesbaar
        self.melding = ctx.melding
        self.oer_ids = list(ctx.oer_ids)
        self.bron_register = [dict(b) for b in ctx.bron_register]
        self.wachtende_vraag = None

    def nieuw_gesprek(self) -> None:
        """Wis alleen het gesprek (OER-context blijft — ingelogde pagina's)."""
        self.gesprek.reset()

    def reset(self) -> None:
        """Wis alle chat-/OER-state (publiek 'nieuw gesprek' of na uitloggen)."""
        self.gesprek.reset()
        self.oer_systeem = None
        self.oer_labels = []
        self.oer_ids = []
        self.oer_onleesbaar = False
        self.melding = ""
        self.domeinen = []
        self.bron_register = []
        self.wachtende_vraag = None

    def uitloggen(self) -> None:
        """Wis alles inclusief login."""
        self.reset()
        self.rol = None
        self.gebruiker = None

    def naar_dict(self) -> dict:
        """Opslagvorm voor ``sessies.db``; het gesprek staat onder de sleutel ``chat_history``."""
        data = {
            f.name: copy.deepcopy(getattr(self, f.name))
            for f in fields(self)
            if f.name != "gesprek"
        }
        data["chat_history"] = self.gesprek.naar_lijst()
        return data

    @classmethod
    def uit_dict(cls, data: dict) -> Sessie:
        """Inverse van :meth:`naar_dict`; onbekende sleutels worden genegeerd, ontbrekende
        krijgen hun default. Een oude rij (alleen ``chat_history``) laadt zo ongewijzigd."""
        bekend = {f.name for f in fields(cls)} - {"gesprek"}
        sessie = cls(**{k: v for k, v in data.items() if k in bekend})
        sessie.gesprek = Gesprek.van_lijst(data.get("chat_history"))
        return sessie


# ── SQLite-backed store (productie: 1 machine, overleeft app-restarts + TTL) ──────
_TTL_SECONDEN = 6 * 3600  # inactieve sessies vervallen na 6 uur


class SessieStore:
    """SQLite-store voor sessies (write-through, TTL-opruiming bij elke ``bewaar``).

    Eén instantie per app (``AppDeps.sessie_store``). De verbinding opent lazy bij het eerste
    gebruik en wordt gedeeld over threads (``check_same_thread=False``) — één machine, één
    proces. ``":memory:"`` geeft een lege store die alleen in deze instantie leeft (tests).
    """

    def __init__(
        self,
        pad: str | Path,
        *,
        ttl_seconden: float = _TTL_SECONDEN,
        klok: Callable[[], float] = time.time,
    ) -> None:
        self.pad = str(pad)
        self.ttl_seconden = ttl_seconden
        self._klok = klok
        self._conn: sqlite3.Connection | None = None

    def _store(self) -> sqlite3.Connection:
        """Lazy SQLite-verbinding (WAL) met het sessies-schema."""
        if self._conn is None:
            if self.pad != ":memory:":
                Path(self.pad).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.pad, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS sessies ("
                "sid TEXT PRIMARY KEY, data TEXT NOT NULL, laatst_gebruikt REAL NOT NULL)"
            )
            conn.commit()
            self._conn = conn
        return self._conn

    def sluit(self) -> None:
        """Sluit de verbinding (een volgend gebruik opent een nieuwe)."""
        if self._conn is not None:
            self._conn.close()
        self._conn = None

    def _verwijder_verouderd(self, nu: float) -> None:
        self._store().execute(
            "DELETE FROM sessies WHERE laatst_gebruikt < ?", (nu - self.ttl_seconden,)
        )
        self._store().commit()

    def bewaar(self, sid: str, sessie: Sessie) -> None:
        """Serialiseer en persisteer de sessie; ruim en passant verouderde sessies op."""
        nu = self._klok()
        self._verwijder_verouderd(nu)
        self._store().execute(
            "INSERT INTO sessies (sid, data, laatst_gebruikt) VALUES (?, ?, ?) "
            "ON CONFLICT(sid) DO UPDATE SET "
            "data=excluded.data, laatst_gebruikt=excluded.laatst_gebruikt",
            (sid, json.dumps(sessie.naar_dict()), nu),
        )
        self._store().commit()

    def laad(self, sid: str) -> Sessie | None:
        """Lees een sessie uit de store, of None als die niet (meer) bestaat.

        Onbekende velden (oude rij ná het verwijderen van een ``Sessie``-veld, bv.
        ``kandidaten``) worden genegeerd, ontbrekende velden krijgen hun default. Een
        onleesbare rij laat de sessie netjes vervallen i.p.v. een harde 500 te geven.
        """
        row = self._store().execute("SELECT data FROM sessies WHERE sid = ?", (sid,)).fetchone()
        if row is None:
            return None
        try:
            return Sessie.uit_dict(json.loads(row[0]))
        except (TypeError, ValueError, AttributeError):
            return None


def _store_van(request) -> SessieStore:
    """De sessie-store van de app die deze request afhandelt (``AppDeps.sessie_store``)."""
    return request.app.state.deps.sessie_store


def get_sessie(request) -> Sessie:
    """Haal (of maak) de sessie voor deze request; cachet op ``request.state``.

    Write-through: muteer het teruggegeven object vrij; persisteren gebeurt via
    ``bewaar_sessie`` (in de middleware na de request, en expliciet in de chat-stream).
    """
    if getattr(request.state, "sessie", None) is not None:
        return request.state.sessie
    sid = request.session.get("sid")
    sessie = _store_van(request).laad(sid) if sid else None
    if sessie is None:
        sid = uuid.uuid4().hex
        request.session["sid"] = sid
        sessie = Sessie()
    request.state.sid = sid
    request.state.sessie = sessie
    return sessie


def bewaar_sessie(request) -> None:
    """Persisteer de op deze request gecachete sessie (no-op als er geen is)."""
    sessie = getattr(request.state, "sessie", None)
    sid = getattr(request.state, "sid", None)
    if sessie is not None and sid:
        _store_van(request).bewaar(sid, sessie)
