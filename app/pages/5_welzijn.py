"""Pagina: Welzijnscheck — student self-assessment."""

from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from samenwijzer.outreach_store import (
    WelzijnsCheck,
    get_welzijnschecks_student,
    sla_welzijnscheck_op,
)
from samenwijzer.styles import CSS, render_footer, render_nav
from samenwijzer.welzijn import (
    CATEGORIEËN,
    categorie_label,
    genereer_welzijnsreactie,
    urgentie_label,
)

load_dotenv()

st.set_page_config(page_title="Welzijnscheck — Samenwijzer", page_icon="💚", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
render_nav()

# ── Toegangscheck ─────────────────────────────────────────────────────────────
if "rol" not in st.session_state or st.session_state["rol"] != "student":
    st.warning("Deze pagina is alleen beschikbaar voor studenten.")
    st.stop()

if "studentnummer" not in st.session_state:
    st.warning("Ga eerst naar de [startpagina](/) om in te loggen.")
    st.stop()

studentnummer = st.session_state["studentnummer"]
df = st.session_state.get("df")
voornaam = studentnummer  # fallback
if df is not None:
    rij = df[df["studentnummer"] == studentnummer]
    if not rij.empty:
        voornaam = rij.iloc[0]["naam"].split()[0]

st.title("💚 Welzijnscheck")
st.markdown(
    "Hoe gaat het met je? Geef aan waar je tegenaan loopt — "
    "je mentor krijgt een signaal en kan je helpen."
)

# ── Check-formulier ───────────────────────────────────────────────────────────
with st.form("welzijnscheck"):
    categorie = st.selectbox(
        "Waar heb je moeite mee?",
        CATEGORIEËN,
        format_func=categorie_label,
    )
    toelichting = st.text_area(
        "Vertel er iets meer over (optioneel)",
        placeholder="Beschrijf kort wat er speelt…",
        height=100,
    )
    urgentie = st.radio(
        "Hoe dringend is het?",
        [1, 2, 3],
        format_func=urgentie_label,
        horizontal=True,
    )
    verzend = st.form_submit_button("💚 Verstuur check", type="primary", use_container_width=True)

if verzend:
    check = WelzijnsCheck(
        studentnummer=studentnummer,
        timestamp=datetime.now().isoformat(),
        categorie=categorie,
        toelichting=toelichting.strip(),
        urgentie=urgentie,
    )
    sla_welzijnscheck_op(check)
    st.success("Je check is verstuurd. Je mentor wordt op de hoogte gesteld.")

    with st.spinner("Reactie genereren…"):
        reactie = st.write_stream(
            genereer_welzijnsreactie(voornaam, categorie, toelichting.strip(), urgentie)
        )

# ── Eerdere checks ────────────────────────────────────────────────────────────
eerdere = get_welzijnschecks_student(studentnummer)
if eerdere:
    with st.expander(f"Eerdere checks ({len(eerdere)})"):
        for c in eerdere[:5]:
            st.caption(
                f"**{c.timestamp[:10]}** · {categorie_label(c.categorie)} · "
                f"{urgentie_label(c.urgentie)}"
                + (f" — {c.toelichting[:80]}" if c.toelichting else "")
            )

render_footer()
