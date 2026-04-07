"""Samenwijzer — startpagina en sessie-initialisatie.

Laadt studiedata eenmalig in st.session_state zodat alle pagina's
dezelfde DataFrame delen zonder opnieuw te laden.
"""

from pathlib import Path

import streamlit as st

from samenwijzer.prepare import load_student_csv
from samenwijzer.transform import transform_student_data

_DEMO_CSV = Path(__file__).parent.parent / "data" / "01-raw" / "demo" / "studenten.csv"

st.set_page_config(
    page_title="Samenwijzer",
    page_icon="📚",
    layout="wide",
)


@st.cache_data
def _laad_data(path: Path):
    df = load_student_csv(path)
    return transform_student_data(df)


if "df" not in st.session_state:
    st.session_state["df"] = _laad_data(_DEMO_CSV)

st.title("📚 Samenwijzer")
st.write(
    "Welkom bij Samenwijzer — jouw persoonlijke leerondersteuning. "
    "Kies hiernaast een pagina om te beginnen."
)

col1, col2 = st.columns(2)
with col1:
    st.info("**Mijn voortgang** — Bekijk je eigen studievoortgang, BSA en competentiescores.")
with col2:
    st.info("**Groepsoverzicht** — Voor docenten: overzicht van alle studenten in de groep.")
