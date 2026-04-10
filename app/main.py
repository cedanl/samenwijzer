"""Samenwijzer — welkomspagina en gecentraliseerde sessie-initialisatie.

Laadt studiedata eenmalig in st.session_state. Studenten en docenten loggen
beiden in met wachtwoord Welkom123. Rol en mentornaam worden bewaard in
session_state en bepalen welke pagina's zichtbaar zijn.
"""

import hashlib
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from samenwijzer.prepare import load_berend_csv
from samenwijzer.styles import CSS, render_footer, render_nav
from samenwijzer.transform import transform_student_data

load_dotenv()

_BEREND_CSV = Path(__file__).parent.parent / "data" / "01-raw" / "berend" / "studenten.csv"

# SHA-256 van "Welkom123"
_WACHTWOORD_HASH = hashlib.sha256(b"Welkom123").hexdigest()

st.set_page_config(page_title="Samenwijzer", page_icon="📚", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data
def _laad_data(path: Path) -> object:
    df = load_berend_csv(path)
    return transform_student_data(df)


if "df" not in st.session_state:
    st.session_state["df"] = _laad_data(_BEREND_CSV)

df = st.session_state["df"]

# ── Loginscherm ───────────────────────────────────────────────────────────────
if "rol" not in st.session_state:
    st.title("📚 Welkom bij Samenwijzer")
    st.write(
        "Samenwijzer helpt studenten grip te krijgen op hun leerproces "
        "en geeft docenten inzicht in de groep."
    )
    st.divider()

    col_student, col_docent = st.columns(2)

    with col_student:
        with st.container(border=True):
            st.markdown("**🎓 Ik ben student**")
            st.caption("Bekijk je eigen voortgang en gebruik de AI-leercoach.")
            namen = (
                df.sort_values("naam")[["naam", "studentnummer"]]
                .apply(lambda r: f"{r['naam']} ({r['studentnummer']})", axis=1)
                .tolist()
            )
            keuze = st.selectbox("Selecteer je naam", namen, key="login_naam")
            ww_student = st.text_input(
                "Wachtwoord",
                type="password",
                key="login_ww_student",
                label_visibility="collapsed",
                placeholder="Wachtwoord",
            )
            if st.button("INLOGGEN", key="btn_student", type="primary", use_container_width=True):
                if hashlib.sha256(ww_student.encode()).hexdigest() == _WACHTWOORD_HASH:
                    snr = keuze.split("(")[-1].rstrip(")")
                    st.session_state["studentnummer"] = snr
                    st.session_state["rol"] = "student"
                    st.rerun()
                else:
                    st.error("Onbekend wachtwoord.")

    with col_docent:
        with st.container(border=True):
            st.markdown("**👩‍🏫 Ik ben docent**")
            st.caption("Toegang tot groepsoverzichten, outreach en alle studentdata.")
            mentoren = sorted(df["mentor"].unique().tolist())
            mentor_keuze = st.selectbox("Selecteer je naam", mentoren, key="login_mentor")
            ww_docent = st.text_input(
                "Wachtwoord",
                type="password",
                key="login_ww_docent",
                label_visibility="collapsed",
                placeholder="Wachtwoord",
            )
            if st.button("INLOGGEN", key="btn_docent", type="primary", use_container_width=True):
                if hashlib.sha256(ww_docent.encode()).hexdigest() == _WACHTWOORD_HASH:
                    st.session_state["rol"] = "docent"
                    st.session_state["mentor_naam"] = mentor_keuze
                    st.rerun()
                else:
                    st.error("Onbekend wachtwoord.")

    render_footer()
    st.stop()

# ── Na inloggen ───────────────────────────────────────────────────────────────
rol = st.session_state["rol"]
render_nav()
st.title("📚 Samenwijzer")

if rol == "student":
    student = df[df["studentnummer"] == st.session_state["studentnummer"]].iloc[0]
    st.success(
        f"Welkom, **{student['naam']}** · {student['opleiding']} "
        f"· Niveau {student['niveau']} · {student['leerweg']}"
    )
else:
    mentor_naam = st.session_state.get("mentor_naam", "")
    eigen_studenten = len(df[df["mentor"] == mentor_naam])
    st.success(f"Ingelogd als **{mentor_naam}** · {eigen_studenten} studenten in jouw groep.")

st.divider()
st.subheader("Wat wil je doen?")

if rol == "student":
    _, col1, col2, col3, _ = st.columns([0.5, 3, 3, 3, 0.5])

    with col1:
        with st.container(border=True):
            st.markdown("**📊 Mijn voortgang**")
            st.caption("Bekijk je studievoortgang, BSA en competentiescores.")
            if st.button("OPEN", key="btn_voortgang", use_container_width=True, type="primary"):
                st.switch_page("pages/1_mijn_voortgang.py")

    with col2:
        with st.container(border=True):
            st.markdown("**🎓 AI Leerondersteuning**")
            st.caption("Tutor, lesmateriaal, oefentoets en feedback op werk.")
            if st.button("OPEN", key="btn_coach", use_container_width=True, type="primary"):
                st.switch_page("pages/3_leercoach.py")

    with col3:
        with st.container(border=True):
            st.markdown("**💚 Welzijn**")
            st.caption("Deel hoe het met je gaat en ontvang gerichte ondersteuning.")
            if st.button("OPEN", key="btn_welzijn", use_container_width=True, type="primary"):
                st.switch_page("pages/5_welzijn.py")

else:  # docent
    _, col1, col2, col3, col4, _ = st.columns([0.5, 3, 3, 3, 3, 0.5])

    with col1:
        with st.container(border=True):
            st.markdown("**📊 Studentvoortgang**")
            st.caption("Bekijk de voortgang van een individuele student.")
            if st.button("OPEN", key="btn_voortgang", use_container_width=True, type="primary"):
                st.switch_page("pages/1_mijn_voortgang.py")

    with col2:
        with st.container(border=True):
            st.markdown("**👥 Groepsoverzicht**")
            st.caption("Overzicht van al jouw studenten in de groep.")
            if st.button("OPEN", key="btn_groep", use_container_width=True, type="primary"):
                st.switch_page("pages/2_groepsoverzicht.py")

    with col3:
        with st.container(border=True):
            st.markdown("**🎓 AI Leerondersteuning**")
            st.caption("Tutor, lesmateriaal, oefentoets en feedback op werk.")
            if st.button("OPEN", key="btn_coach", use_container_width=True, type="primary"):
                st.switch_page("pages/3_leercoach.py")

    with col4:
        with st.container(border=True):
            st.markdown("**📬 Outreach**")
            st.caption("Signaleer risico's en neem contact op met jouw studenten.")
            if st.button("OPEN", key="btn_outreach", use_container_width=True, type="primary"):
                st.switch_page("pages/4_outreach.py")

render_footer()
