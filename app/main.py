"""Samenwijzer — startpagina en sessie-initialisatie.

Laadt studiedata eenmalig in st.session_state zodat alle pagina's
dezelfde DataFrame delen zonder opnieuw te laden.
"""

from pathlib import Path

import streamlit as st

from samenwijzer.prepare import load_student_csv
from samenwijzer.styles import CSS, render_footer
from samenwijzer.transform import transform_student_data

_DEMO_CSV = Path(__file__).parent.parent / "data" / "01-raw" / "demo" / "studenten.csv"

st.set_page_config(
    page_title="Samenwijzer",
    page_icon="📚",
    layout="wide",
)
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data
def _laad_data(path: Path):
    df = load_student_csv(path)
    return transform_student_data(df)


if "df" not in st.session_state:
    st.session_state["df"] = _laad_data(_DEMO_CSV)

st.title("📚 Samenwijzer")
st.write(
    "Welkom bij Samenwijzer — jouw persoonlijke leerondersteuning. "
    "Kies hieronder een pagina om te beginnen."
)

_, col1, col2, col3, _ = st.columns([0.5, 3, 3, 3, 0.5])
with col1:
    with st.container(border=True):
        st.markdown("**📊 Mijn voortgang**")
        st.caption("Bekijk je eigen studievoortgang, BSA en competentiescores.")
        if st.button("OPEN", key="btn_voortgang", use_container_width=True, type="primary"):
            st.switch_page("pages/1_mijn_voortgang.py")
with col2:
    with st.container(border=True):
        st.markdown("**👥 Groepsoverzicht**")
        st.caption("Voor docenten: overzicht van alle studenten in de groep.")
        if st.button("OPEN", key="btn_groep", use_container_width=True, type="primary"):
            st.switch_page("pages/2_groepsoverzicht.py")
with col3:
    with st.container(border=True):
        st.markdown("**🎓 AI Leerondersteuning**")
        st.caption("Tutor, lesmateriaal, oefentoets en feedback op werk.")
        if st.button("OPEN", key="btn_coach", use_container_width=True, type="primary"):
            st.switch_page("pages/3_leercoach.py")

render_footer()
