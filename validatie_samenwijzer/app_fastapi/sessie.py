"""Server-side sessiestate voor de publieke OER-chat.

De gecombineerde system-prompt is tot ~500K tekens × 3 → past nooit in een cookie.
Daarom houdt een ondertekende cookie (via Starlette ``SessionMiddleware``) enkel een
``sid``; de echte state leeft in een in-memory store. Spiegelt het ``pub_*``-
session_state-contract van ``app/pages/0_oer_vraag.py``.

POC-grens: in-memory store werkt op één machine. Multi-machine vereist sticky sessions
of een gedeelde store (Redis/sqlite) — zie het plan-doc.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

MAX_GESCHIEDENIS = 20  # 10 vraag/antwoord-paren, zoals 0_oer_vraag.py


@dataclass
class Sessie:
    # Chat-/OER-context (publiek én ingelogd)
    chat_history: list[dict] = field(default_factory=list)
    oer_systeem: str | None = None
    oer_labels: list[str] = field(default_factory=list)
    oer_ids: list[int] = field(default_factory=list)
    domeinen: list[str] = field(default_factory=list)
    kandidaten: list[dict] = field(default_factory=list)
    wachtende_vraag: str | None = None
    # Algemene toegang (gedeeld wachtwoord — sommige instellingen zetten hun OER
    # achter een wachtwoord, dus de hele app zit achter deze poort).
    toegang: bool = False
    # Ingelogde gebruiker (None = publiek)
    rol: str | None = None  # "student" | "mentor"
    gebruiker: dict | None = None  # {id, naam, studentnummer?}
    actieve_student: dict | None = None  # mentor: geselecteerde student

    def voeg_beurt_toe(self, vraag: str, antwoord: str) -> None:
        """Voeg een vraag/antwoord-paar toe en kap de historie op MAX_GESCHIEDENIS."""
        self.chat_history.append({"role": "user", "content": vraag})
        self.chat_history.append({"role": "assistant", "content": antwoord})
        if len(self.chat_history) > MAX_GESCHIEDENIS:
            self.chat_history = self.chat_history[-MAX_GESCHIEDENIS:]

    def nieuw_gesprek(self) -> None:
        """Wis alleen de gesprekshistorie (OER-context blijft — ingelogde pagina's)."""
        self.chat_history = []

    def reset(self) -> None:
        """Wis alle chat-/OER-state (publiek 'nieuw gesprek' of na uitloggen)."""
        self.chat_history = []
        self.oer_systeem = None
        self.oer_labels = []
        self.oer_ids = []
        self.domeinen = []
        self.kandidaten = []
        self.wachtende_vraag = None
        self.actieve_student = None

    def uitloggen(self) -> None:
        """Wis alles inclusief login."""
        self.reset()
        self.rol = None
        self.gebruiker = None


# ── SQLite-backed store (productie: 1 machine, overleeft app-restarts + TTL) ──────
_DB_PAD = os.environ.get("SESSIE_DB_PATH", "data/sessies.db")
_TTL_SECONDEN = 6 * 3600  # inactieve sessies vervallen na 6 uur
_conn: sqlite3.Connection | None = None


def _store() -> sqlite3.Connection:
    """Lazy SQLite-verbinding (WAL) met het sessies-schema."""
    global _conn
    if _conn is None:
        Path(_DB_PAD).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(_DB_PAD, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS sessies ("
            "sid TEXT PRIMARY KEY, data TEXT NOT NULL, laatst_gebruikt REAL NOT NULL)"
        )
        _conn.commit()
    return _conn


def _reset_store_voor_test() -> None:
    """Sluit de cache-verbinding zodat een test een vers ``_DB_PAD`` kan gebruiken."""
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = None


def _verwijder_verouderd(nu: float) -> None:
    _store().execute("DELETE FROM sessies WHERE laatst_gebruikt < ?", (nu - _TTL_SECONDEN,))
    _store().commit()


def bewaar(sid: str, sessie: Sessie) -> None:
    """Serialiseer en persisteer de sessie; ruim en passant verouderde sessies op."""
    nu = time.time()
    _verwijder_verouderd(nu)
    _store().execute(
        "INSERT INTO sessies (sid, data, laatst_gebruikt) VALUES (?, ?, ?) "
        "ON CONFLICT(sid) DO UPDATE SET "
        "data=excluded.data, laatst_gebruikt=excluded.laatst_gebruikt",
        (sid, json.dumps(asdict(sessie)), nu),
    )
    _store().commit()


def laad(sid: str) -> Sessie | None:
    """Lees een sessie uit de store, of None als die niet (meer) bestaat."""
    row = _store().execute("SELECT data FROM sessies WHERE sid = ?", (sid,)).fetchone()
    if row is None:
        return None
    return Sessie(**json.loads(row[0]))


def get_sessie(request) -> Sessie:
    """Haal (of maak) de sessie voor deze request; cachet op ``request.state``.

    Write-through: muteer het teruggegeven object vrij; persisteren gebeurt via
    ``bewaar_sessie`` (in de middleware na de request, en expliciet in de chat-stream).
    """
    if getattr(request.state, "sessie", None) is not None:
        return request.state.sessie
    sid = request.session.get("sid")
    sessie = laad(sid) if sid else None
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
        bewaar(sid, sessie)
