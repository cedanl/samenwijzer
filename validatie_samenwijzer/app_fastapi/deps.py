"""Afhankelijkheden van de app — één bundel, één seam voor productie én tests.

``AppDeps`` draagt alles wat de routes van buiten nodig hebben: config (uit env), de
validatie.db-verbinding, de sessie-store, de AI-client en de OER-cache. ``AppDeps.uit_env()`` is
de productie-constructor (fail-closed op ``SESSION_SECRET``/``ALGEMEEN_WACHTWOORD``); tests
bouwen ``AppDeps(...)`` met ``":memory:"``-databases en een nep-``ai_client``. ``main.maak_app``
hangt de bundel aan ``app.state.deps``; routes lezen hem via :func:`deps_van` — geen
module-globals, geen env-reads bij import.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app_fastapi.context import OerBlokken
from app_fastapi.sessie import SessieStore
from validatie_samenwijzer import _ai, db


class ValidatieDb:
    """Bron van verbindingen met validatie.db.

    Migreert het schema één keer per instantie (de ingebakken productie-DB kan van vóór de
    `documenten`-tabel zijn; ``db.init_db`` is idempotent). Een bestandspad geeft per
    :meth:`verbinding` een eigen connectie die na gebruik sluit; ``":memory:"`` houdt één
    gedeelde connectie open (tests: schema + seed blijven over requests heen bestaan).
    """

    def __init__(self, pad: str | Path) -> None:
        self.pad = str(pad)
        self._gedeeld = db.get_connection(Path(self.pad)) if self.pad == ":memory:" else None
        self._gemigreerd = False
        self._lock = threading.Lock()

    def _migreer(self, conn: sqlite3.Connection) -> None:
        if self._gemigreerd:
            return
        with self._lock:
            if not self._gemigreerd:
                db.init_db(conn)
                self._gemigreerd = True

    def sluit(self) -> None:
        """Sluit de gedeelde ``":memory:"``-verbinding (no-op voor een bestandspad)."""
        if self._gedeeld is not None:
            self._gedeeld.close()

    @contextmanager
    def verbinding(self) -> Iterator[sqlite3.Connection]:
        """Geef een (gemigreerde) verbinding voor de duur van het ``with``-blok."""
        if self._gedeeld is not None:
            self._migreer(self._gedeeld)
            yield self._gedeeld
            return
        conn = db.get_connection(Path(self.pad))
        try:
            self._migreer(conn)
            yield conn
        finally:
            conn.close()


@dataclass(frozen=True)
class AppDeps:
    """Alle externe afhankelijkheden van één app-instantie (zie moduledocstring)."""

    session_secret: str
    algemeen_wachtwoord: str
    validatie_db: ValidatieDb
    sessie_store: SessieStore
    ai_client: Callable[[], Any] = _ai._client
    cookie_https_only: bool = True
    beheer_enabled: bool = False
    chat_heartbeat_seconden: float = 15.0
    chat_max_seconden: float = 90.0
    oer_blokken: OerBlokken = field(default_factory=OerBlokken)

    def __post_init__(self) -> None:
        # Fail-closed: zonder wachtwoord lockt de toegangspoort de hele app uit, zonder secret
        # is de sessie-cookie niet te ondertekenen — geef een duidelijk operator-signaal.
        if not self.algemeen_wachtwoord:
            raise RuntimeError(
                "ALGEMEEN_WACHTWOORD is verplicht (geen default) — zet 'm in .env / Fly-secrets."
            )
        if not self.session_secret:
            raise RuntimeError(
                "SESSION_SECRET is verplicht (geen default) — zet 'm in .env / Fly-secrets."
            )

    @classmethod
    def uit_env(cls, env: Mapping[str, str] | None = None) -> AppDeps:
        """Productie-constructor: lees de config uit ``env`` (default ``os.environ``)."""
        env = os.environ if env is None else env
        return cls(
            session_secret=env.get("SESSION_SECRET", ""),
            algemeen_wachtwoord=env.get("ALGEMEEN_WACHTWOORD", ""),
            validatie_db=ValidatieDb(env.get("DB_PATH", "data/validatie.db")),
            sessie_store=SessieStore(env.get("SESSIE_DB_PATH", "data/sessies.db")),
            cookie_https_only=env.get("COOKIE_HTTPS_ONLY", "1") != "0",
            beheer_enabled=env.get("BEHEER_ENABLED", "").lower() == "true",
            chat_max_seconden=float(env.get("CHAT_MAX_SECONDEN", "90")),
        )

    def verbinding(self):
        """Kortere schrijfwijze voor ``self.validatie_db.verbinding()`` (contextmanager)."""
        return self.validatie_db.verbinding()


def deps_van(request) -> AppDeps:
    """De ``AppDeps`` van de app die deze request afhandelt."""
    return request.app.state.deps
