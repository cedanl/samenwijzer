"""Server-side sessiestate voor de publieke OER-chat.

De gecombineerde system-prompt is tot ~500K tekens × 3 → past nooit in een cookie.
Daarom houdt een ondertekende cookie (via Starlette ``SessionMiddleware``) enkel een
``sid``; de echte state leeft in een in-memory store. Spiegelt het ``pub_*``-
session_state-contract van ``app/pages/0_oer_vraag.py``.

POC-grens: in-memory store werkt op één machine. Multi-machine vereist sticky sessions
of een gedeelde store (Redis/sqlite) — zie het plan-doc.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

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


_STORE: dict[str, Sessie] = {}


def get_sessie(request) -> Sessie:
    """Haal (of maak) de server-side ``Sessie`` voor deze request via de ``sid``-cookie."""
    sid = request.session.get("sid")
    if not sid or sid not in _STORE:
        sid = uuid.uuid4().hex
        request.session["sid"] = sid
        _STORE[sid] = Sessie()
    return _STORE[sid]
