"""Authenticatie: wachtwoord-hashing, login en Streamlit rolcontrole."""

import hashlib
import hmac
import os
import sqlite3

import streamlit as st

_ITERATIONS = 600_000
_SALT_BYTES = 32


def hash_wachtwoord(wachtwoord: str) -> str:
    """Return een PBKDF2-HMAC-SHA256 hash als 'salt_hex:hash_hex'."""
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", wachtwoord.encode(), salt, _ITERATIONS)
    return f"{salt.hex()}:{dk.hex()}"


def verifieer_wachtwoord(wachtwoord: str, opgeslagen_hash: str) -> bool:
    """Verificeer wachtwoord tegen opgeslagen PBKDF2-hash of oude SHA-256-hash."""
    if ":" in opgeslagen_hash:
        salt_hex, dk_hex = opgeslagen_hash.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", wachtwoord.encode(), salt, _ITERATIONS)
        return hmac.compare_digest(dk.hex(), dk_hex)
    # Legacy: bare SHA-256 (migrate on next login)
    return hmac.compare_digest(hashlib.sha256(wachtwoord.encode()).hexdigest(), opgeslagen_hash)


def _login(
    conn: sqlite3.Connection, tabel: str, veld: str, waarde: str, wachtwoord: str
) -> sqlite3.Row | None:
    row = conn.execute(
        f"SELECT * FROM {tabel} WHERE {veld} = ?",  # noqa: S608
        (waarde,),
    ).fetchone()
    if row and verifieer_wachtwoord(wachtwoord, row["wachtwoord_hash"]):
        return row
    return None


def login_student(
    conn: sqlite3.Connection, studentnummer: str, wachtwoord: str
) -> sqlite3.Row | None:
    return _login(conn, "studenten", "studentnummer", studentnummer, wachtwoord)


def login_mentor(conn: sqlite3.Connection, naam: str, wachtwoord: str) -> sqlite3.Row | None:
    return _login(conn, "mentoren", "naam", naam, wachtwoord)


def vereist_rol(vereiste_rol: str) -> None:
    if st.session_state.get("rol") != vereiste_rol:
        label = "studenten" if vereiste_rol == "student" else "mentoren"
        st.error(f"🔒 Deze pagina is alleen toegankelijk voor {label}.")
        st.page_link("main.py", label="Terug naar de startpagina", icon="🏠")
        st.stop()


def vereist_student() -> None:
    vereist_rol("student")


def vereist_mentor() -> None:
    vereist_rol("mentor")
