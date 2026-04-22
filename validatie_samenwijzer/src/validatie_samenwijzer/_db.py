"""Gedeelde gecachede DB-verbinding voor Streamlit-pagina's."""

import os
from pathlib import Path

import streamlit as st

from validatie_samenwijzer.db import get_connection, init_db

_DB_PATH = Path(os.environ.get("DB_PATH", "data/validatie.db"))


@st.cache_resource
def get_conn():
    conn = get_connection(_DB_PATH)
    init_db(conn)
    return conn
