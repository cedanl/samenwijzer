"""Mentor: studentenoverzicht met voortgangsbadges."""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Mijn studenten", page_icon="👥", layout="wide")

from validatie_samenwijzer.auth import vereist_mentor  # noqa: E402
from validatie_samenwijzer.db import (  # noqa: E402
    get_connection,
    get_studenten_by_mentor_id,
    init_db,
)
from validatie_samenwijzer.styles import (  # noqa: E402
    CSS,
    GROEN,
    ORANJE,
    ROOD,
    render_footer,
    render_nav,
)

st.markdown(CSS, unsafe_allow_html=True)
vereist_mentor()
render_nav()

DB_PATH = Path(os.environ.get("DB_PATH", "data/validatie.db"))


@st.cache_resource
def _conn():
    conn = get_connection(DB_PATH)
    init_db(conn)
    return conn


mentor_id = st.session_state.get("gebruiker_id")
st.subheader("👥 Mijn studenten")

studenten = get_studenten_by_mentor_id(_conn(), mentor_id)

if not studenten:
    st.info("Geen studenten gekoppeld aan jouw account.")
    st.stop()

st.caption(f"{len(studenten)} studenten · Klik op een student om een begeleidingssessie te starten")

for student in studenten:
    vg = student["voortgang"] or 0.0
    bsa_b = student["bsa_behaald"] or 0.0
    bsa_v = student["bsa_vereist"] or 60.0
    bsa_pct = min(bsa_b / bsa_v, 1.0) if bsa_v else 0.0
    afwn = student["absence_unauthorized"] or 0.0

    kleur_vg = GROEN if vg >= 0.7 else (ORANJE if vg >= 0.5 else ROOD)
    kleur_bsa = GROEN if bsa_pct >= 0.8 else (ORANJE if bsa_pct >= 0.6 else ROOD)
    kleur_afw = ROOD if afwn > 10 else (ORANJE if afwn > 5 else GROEN)

    with st.container(border=True):
        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
        with col1:
            st.markdown(f"**{student['naam']}**")
            oer = (
                _conn()
                .execute(
                    "SELECT opleiding, leerweg, cohort FROM oer_documenten WHERE id = ?",
                    (student["oer_id"],),
                )
                .fetchone()
            )
            if oer:
                st.caption(f"{oer['opleiding']} · {oer['leerweg']} · {oer['cohort']}")
        with col2:
            st.markdown(
                f"<span style='color:{kleur_vg}'>▸ Voortgang: **{vg * 100:.0f}%**</span>",
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                f"<span style='color:{kleur_bsa}'>▸ BSA: **{bsa_pct * 100:.0f}%**</span>",
                unsafe_allow_html=True,
            )
        with col4:
            st.markdown(
                f"<span style='color:{kleur_afw}'>▸ Afwez.: **{afwn:.0f} uur**</span>",
                unsafe_allow_html=True,
            )
        with col5:
            if st.button("🎓 Begeleiden", key=f"begeleid_{student['id']}"):
                st.session_state["actieve_student"] = dict(student)
                st.session_state["chat_history"] = []
                st.session_state["chat_bronnen"] = []
                st.switch_page("pages/5_begeleidingssessie.py")

render_footer()
