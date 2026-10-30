"""Login-helpers voor de FastAPI-POC — hergebruikt de PBKDF2-loginfuncties uit
``validatie_samenwijzer.auth`` (die nemen een conn + credentials en zijn UI-vrij)."""

from __future__ import annotations

import sqlite3

from validatie_samenwijzer.auth import login_mentor, login_student


def auth_student(
    conn: sqlite3.Connection, studentnummer: str, wachtwoord: str
) -> sqlite3.Row | None:
    return login_student(conn, studentnummer.strip(), wachtwoord)


def auth_mentor(conn: sqlite3.Connection, naam: str, wachtwoord: str) -> sqlite3.Row | None:
    return login_mentor(conn, naam.strip(), wachtwoord)
