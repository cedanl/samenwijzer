"""Login-helpers voor de FastAPI-POC — hergebruikt de PBKDF2-loginfuncties uit
``validatie_samenwijzer.auth`` (die nemen een conn + credentials en zijn UI-vrij)."""

from __future__ import annotations

import os
import sqlite3

from validatie_samenwijzer import db
from validatie_samenwijzer.auth import login_mentor, login_student


def _conn() -> sqlite3.Connection:
    return db.get_connection(os.environ.get("DB_PATH", "data/validatie.db"))


def auth_student(studentnummer: str, wachtwoord: str) -> sqlite3.Row | None:
    return login_student(_conn(), studentnummer.strip(), wachtwoord)


def auth_mentor(naam: str, wachtwoord: str) -> sqlite3.Row | None:
    return login_mentor(_conn(), naam.strip(), wachtwoord)
