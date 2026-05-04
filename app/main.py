"""Samenwijzer — welkomspagina en gecentraliseerde sessie-initialisatie.

Laadt studiedata eenmalig in st.session_state. Studenten en docenten loggen
beiden in met wachtwoord Welkom123. Rol en mentornaam worden bewaard in
session_state en bepalen welke pagina's zichtbaar zijn.
"""

import hashlib
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from samenwijzer.prepare import load_student_csv
from samenwijzer.styles import CSS, render_footer, render_nav
from samenwijzer.transform import transform_student_data
from samenwijzer.whatsapp import stuur_verificatie
from samenwijzer.whatsapp_store import heeft_actieve_registratie, registreer_nummer

load_dotenv()

_STUDENTEN_CSV = Path(__file__).parent.parent / "data" / "01-raw" / "demo" / "studenten.csv"

# SHA-256 van "Welkom123"
_WACHTWOORD_HASH = hashlib.sha256(b"Welkom123").hexdigest()

st.set_page_config(page_title="Samenwijzer", page_icon="📚", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data
def _laad_data(path: Path) -> object:
    df = load_student_csv(path)
    return transform_student_data(df)


if "df" not in st.session_state:
    st.session_state["df"] = _laad_data(_STUDENTEN_CSV)

df = st.session_state["df"]

# ── Loginscherm ───────────────────────────────────────────────────────────────
if "rol" not in st.session_state:
    st.markdown(
        """<div style="background:linear-gradient(135deg,#fae8e8 0%,#f0d4d4 100%);
border-radius:20px; padding:32px 36px 28px; margin-bottom:24px;
border-left:5px solid #c8785a;">
  <h1 style="margin:0 0 8px; font-size:2.4rem; font-weight:700; color:#1a1a1a;">📚 Welkom bij Samenwijzer</h1>
  <p style="margin:0; color:#555; font-size:1rem; line-height:1.5;">
    Samenwijzer helpt studenten grip te krijgen op hun leerproces
    en geeft docenten inzicht in de groep.
  </p>
</div>""",
        unsafe_allow_html=True,
    )

    col_student, col_docent = st.columns(2)

    with col_student:
        with st.container(border=True):
            st.markdown(
                "<p style='font-size:1.05rem; font-weight:700; margin:0 0 2px; color:#1a1a1a'>🎓 Ik ben student</p>"
                "<p style='font-size:0.82rem; color:#888; margin:0 0 12px'>Bekijk je eigen voortgang en gebruik de AI-leercoach.</p>",
                unsafe_allow_html=True,
            )
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
            st.markdown(
                "<p style='font-size:1.05rem; font-weight:700; margin:0 0 2px; color:#1a1a1a'>👩‍🏫 Ik ben docent</p>"
                "<p style='font-size:0.82rem; color:#888; margin:0 0 12px'>Toegang tot groepsoverzichten, outreach en alle studentdata.</p>",
                unsafe_allow_html=True,
            )
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

if rol == "student":
    student = df[df["studentnummer"] == st.session_state["studentnummer"]].iloc[0]
    snr = str(student["studentnummer"])
    st.markdown(
        f"""<div style="background:#fae8e8; border-left:4px solid #c8785a; border-radius:12px;
padding:16px 20px; margin-bottom:20px;">
  <p style="margin:0 0 2px; font-size:1.05rem; font-weight:700; color:#1a1a1a">
    Welkom, {student["naam"]}
  </p>
  <p style="margin:0; font-size:0.85rem; color:#888">
    {student["opleiding"]} · Niveau {student["niveau"]} · {student["leerweg"]}
  </p>
</div>""",
        unsafe_allow_html=True,
    )

    # ── WhatsApp opt-in (eenmalig tonen als nog niet geregistreerd) ───────────
    if not heeft_actieve_registratie(snr):
        with st.expander("📱 Ontvang wekelijkse check-ins via WhatsApp", expanded=False):
            st.caption(
                "Samenwijzer kan je elke maandag een kort berichtje sturen: hoe gaat het? "
                "Zo hoef je de app niet te openen om in contact te blijven met je mentor."
            )
            with st.form("whatsapp_optin"):
                nummer = st.text_input(
                    "Jouw WhatsApp-nummer",
                    placeholder="+31612345678",
                    help="Internationaal formaat, bijv. +31612345678",
                )
                akkoord = st.checkbox(
                    "Ik geef toestemming om wekelijks een WhatsApp-bericht te ontvangen "
                    "en begrijp dat ik me altijd kan afmelden door STOP te sturen."
                )
                verzenden = st.form_submit_button("Aanmelden", type="primary")

            if verzenden:
                nummer = nummer.strip()
                if not nummer.startswith("+") or len(nummer) < 10:
                    st.error("Voer een geldig internationaal nummer in, bijv. +31612345678.")
                elif not akkoord:
                    st.error("Geef toestemming om je aan te melden.")
                else:
                    try:
                        registreer_nummer(snr, nummer)
                        stuur_verificatie(nummer)
                        st.success(
                            f"Verificatiebericht verstuurd naar {nummer}. "
                            "Antwoord JA in WhatsApp om te bevestigen."
                        )
                    except OSError:
                        st.warning(
                            "WhatsApp-koppeling is nog niet geconfigureerd "
                            "(geen Twilio-credentials). Je registratie is opgeslagen."
                        )
                        registreer_nummer(snr, nummer)
else:
    mentor_naam = st.session_state.get("mentor_naam", "")
    eigen_studenten = len(df[df["mentor"] == mentor_naam])
    st.markdown(
        f"""<div style="background:#fae8e8; border-left:4px solid #c8785a; border-radius:12px;
padding:16px 20px; margin-bottom:20px;">
  <p style="margin:0 0 2px; font-size:1.05rem; font-weight:700; color:#1a1a1a">
    Welkom, {mentor_naam}
  </p>
  <p style="margin:0; font-size:0.85rem; color:#888">
    {eigen_studenten} studenten in jouw groep
  </p>
</div>""",
        unsafe_allow_html=True,
    )

st.markdown("<p class='section-label'>Wat wil je doen?</p>", unsafe_allow_html=True)

if rol == "student":
    _, col1, col2, col3, _ = st.columns([0.5, 3, 3, 3, 0.5])

    with col1:
        with st.container(border=True):
            st.markdown(
                "<p class='section-label'>Voortgang</p>"
                "<p style='font-size:0.95rem; font-weight:700; margin:0 0 4px; color:#1a1a1a'>📊 Mijn voortgang</p>"
                "<p style='font-size:0.80rem; color:#888; margin:0 0 10px'>Bekijk je studievoortgang, BSA en competentiescores.</p>",
                unsafe_allow_html=True,
            )
            if st.button("OPEN", key="btn_voortgang", use_container_width=True, type="primary"):
                st.switch_page("pages/1_mijn_voortgang.py")

    with col2:
        with st.container(border=True):
            st.markdown(
                "<p class='section-label'>Leren</p>"
                "<p style='font-size:0.95rem; font-weight:700; margin:0 0 4px; color:#1a1a1a'>🎓 AI Leerondersteuning</p>"
                "<p style='font-size:0.80rem; color:#888; margin:0 0 10px'>Tutor, lesmateriaal, oefentoets en feedback op werk.</p>",
                unsafe_allow_html=True,
            )
            if st.button("OPEN", key="btn_coach", use_container_width=True, type="primary"):
                st.switch_page("pages/3_leercoach.py")

    with col3:
        with st.container(border=True):
            st.markdown(
                "<p class='section-label'>Welzijn</p>"
                "<p style='font-size:0.95rem; font-weight:700; margin:0 0 4px; color:#1a1a1a'>💚 Welzijn</p>"
                "<p style='font-size:0.80rem; color:#888; margin:0 0 10px'>Deel hoe het met je gaat en ontvang gerichte ondersteuning.</p>",
                unsafe_allow_html=True,
            )
            if st.button("OPEN", key="btn_welzijn", use_container_width=True, type="primary"):
                st.switch_page("pages/5_welzijn.py")

else:  # docent
    _, col1, col2, col3, col4, _ = st.columns([0.5, 3, 3, 3, 3, 0.5])

    with col1:
        with st.container(border=True):
            st.markdown(
                "<p class='section-label'>Voortgang</p>"
                "<p style='font-size:0.95rem; font-weight:700; margin:0 0 4px; color:#1a1a1a'>📊 Studentvoortgang</p>"
                "<p style='font-size:0.80rem; color:#888; margin:0 0 10px'>Bekijk de voortgang van een individuele student.</p>",
                unsafe_allow_html=True,
            )
            if st.button("OPEN", key="btn_voortgang", use_container_width=True, type="primary"):
                st.switch_page("pages/1_mijn_voortgang.py")

    with col2:
        with st.container(border=True):
            st.markdown(
                "<p class='section-label'>Groep</p>"
                "<p style='font-size:0.95rem; font-weight:700; margin:0 0 4px; color:#1a1a1a'>👥 Groepsoverzicht</p>"
                "<p style='font-size:0.80rem; color:#888; margin:0 0 10px'>Overzicht van al jouw studenten in de groep.</p>",
                unsafe_allow_html=True,
            )
            if st.button("OPEN", key="btn_groep", use_container_width=True, type="primary"):
                st.switch_page("pages/2_groepsoverzicht.py")

    with col3:
        with st.container(border=True):
            st.markdown(
                "<p class='section-label'>Leren</p>"
                "<p style='font-size:0.95rem; font-weight:700; margin:0 0 4px; color:#1a1a1a'>🎓 AI Leerondersteuning</p>"
                "<p style='font-size:0.80rem; color:#888; margin:0 0 10px'>Tutor, lesmateriaal, oefentoets en feedback op werk.</p>",
                unsafe_allow_html=True,
            )
            if st.button("OPEN", key="btn_coach", use_container_width=True, type="primary"):
                st.switch_page("pages/3_leercoach.py")

    with col4:
        with st.container(border=True):
            st.markdown(
                "<p class='section-label'>Outreach</p>"
                "<p style='font-size:0.95rem; font-weight:700; margin:0 0 4px; color:#1a1a1a'>📬 Outreach</p>"
                "<p style='font-size:0.80rem; color:#888; margin:0 0 10px'>Signaleer risico's en neem contact op met jouw studenten.</p>",
                unsafe_allow_html=True,
            )
            if st.button("OPEN", key="btn_outreach", use_container_width=True, type="primary"):
                st.switch_page("pages/4_outreach.py")

render_footer()
