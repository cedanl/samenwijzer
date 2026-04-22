"""Authenticatie: wachtwoord-hashing, login en Streamlit rolcontrole."""

import hashlib
import sqlite3

import streamlit as st


def hash_wachtwoord(wachtwoord: str) -> str:
    return hashlib.sha256(wachtwoord.encode()).hexdigest()


def login_student(conn: sqlite3.Connection, studentnummer: str,
                  wachtwoord: str) -> sqlite3.Row | None:
    wh = hash_wachtwoord(wachtwoord)
    return conn.execute(
        "SELECT * FROM studenten WHERE studentnummer = ? AND wachtwoord_hash = ?",
        (studentnummer, wh),
    ).fetchone()


def login_mentor(conn: sqlite3.Connection, naam: str,
                 wachtwoord: str) -> sqlite3.Row | None:
    wh = hash_wachtwoord(wachtwoord)
    return conn.execute(
        "SELECT * FROM mentoren WHERE naam = ? AND wachtwoord_hash = ?",
        (naam, wh),
    ).fetchone()


def vereist_student() -> None:
    if st.session_state.get("rol") != "student":
        st.error("🔒 Deze pagina is alleen toegankelijk voor studenten.")
        st.page_link("main.py", label="Terug naar de startpagina", icon="🏠")
        st.stop()


def vereist_mentor() -> None:
    if st.session_state.get("rol") != "mentor":
        st.error("🔒 Deze pagina is alleen toegankelijk voor mentoren.")
        st.page_link("main.py", label="Terug naar de startpagina", icon="🏠")
        st.stop()
