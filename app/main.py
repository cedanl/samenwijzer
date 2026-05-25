"""Samenwijzer — welkomspagina, login en home (per rol)."""

import hashlib
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from samenwijzer.groei import overlay_self_scores
from samenwijzer.prepare import load_synthetisch_csv
from samenwijzer.styles import (
    action_tile,
    hero,
    inject_theme,
    render_footer,
    render_nav,
    section_label,
    stat_card,
)
from samenwijzer.transform import transform_student_data
from samenwijzer.whatsapp import stuur_verificatie
from samenwijzer.whatsapp_store import heeft_actieve_registratie, registreer_nummer

load_dotenv()

_STUDENTEN_CSV = Path(__file__).parent.parent / "data" / "01-raw" / "synthetisch" / "studenten.csv"

# SHA-256 van "Welkom123"
_WACHTWOORD_HASH = hashlib.sha256(b"Welkom123").hexdigest()

st.set_page_config(page_title="Samenwijzer", page_icon="📚", layout="wide")


@st.cache_data
def _laad_data(path: Path) -> object:
    df = load_synthetisch_csv(path)
    return transform_student_data(df)


if "df_basis" not in st.session_state:
    st.session_state["df_basis"] = _laad_data(_STUDENTEN_CSV)

st.session_state["df"] = overlay_self_scores(st.session_state["df_basis"])
df = st.session_state["df"]


# ── Loginscherm ───────────────────────────────────────────────────────────────
if "rol" not in st.session_state:
    inject_theme(None)

    st.markdown(
        """
<style>
.sw-login {
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 0; border-radius: 18px; overflow: hidden;
    box-shadow: 0 12px 48px rgba(31,29,24,0.12);
    margin: 0 0 var(--space-5);
    border: 1px solid var(--border);
}
.sw-login__side { padding: 36px 32px 24px; min-height: 360px; }
.sw-login__side--stu { background: #0F0F12; color: #FFFFFF; }
.sw-login__side--doc { background: #FAF5EC; color: #1F1D18; }
.sw-login__ey {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase;
    margin: 0;
}
.sw-login__side--stu .sw-login__ey { color: #A8FF60; }
.sw-login__side--doc .sw-login__ey { color: #6F8265; }
.sw-login__side--stu p.sw-login__ti {
    font-family: 'Cabinet Grotesk', sans-serif;
    font-weight: 800; font-size: 2.4rem; letter-spacing: -0.035em;
    line-height: 1; margin: 14px 0 8px; color: #FFFFFF;
}
.sw-login__side--doc p.sw-login__ti {
    font-family: 'Cabinet Grotesk', sans-serif;
    font-weight: 800; font-size: 2.4rem; letter-spacing: -0.035em;
    line-height: 1; margin: 14px 0 8px; color: #1F1D18;
}
.sw-login__side--stu p.sw-login__sb {
    font-family: 'Satoshi', sans-serif; font-weight: 500;
    font-size: 0.92rem; line-height: 1.5; margin: 0 0 24px;
    color: rgba(255,255,255,0.65);
}
.sw-login__side--doc p.sw-login__sb {
    font-family: 'Satoshi', sans-serif; font-weight: 500;
    font-size: 0.92rem; line-height: 1.5; margin: 0 0 24px;
    color: #6A6354;
}

@media (max-width: 768px) {
    .sw-login { grid-template-columns: 1fr; }
    .sw-login__side { min-height: 260px; }
}
</style>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="sw-login">
  <div class="sw-login__side sw-login__side--stu">
    <p class="sw-login__ey">— Student</p>
    <p class="sw-login__ti">Hoe sta<br>jij ervoor?</p>
    <p class="sw-login__sb">Bekijk je voortgang, krijg een persoonlijk weekplan en deel hoe het met je gaat.</p>
  </div>
  <div class="sw-login__side sw-login__side--doc">
    <p class="sw-login__ey">— Docent</p>
    <p class="sw-login__ti">Mentor­overzicht</p>
    <p class="sw-login__sb">Vroege signalen, gerichte outreach en alle studentdata op één plek.</p>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    col_student, col_docent = st.columns(2, gap="medium")

    with col_student:
        with st.container(border=True):
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
            if st.button(
                "INLOGGEN ALS STUDENT",
                key="btn_student",
                type="primary",
                use_container_width=True,
            ):
                if hashlib.sha256(ww_student.encode()).hexdigest() == _WACHTWOORD_HASH:
                    snr = keuze.split("(")[-1].rstrip(")")
                    st.session_state["studentnummer"] = snr
                    st.session_state["rol"] = "student"
                    st.rerun()
                else:
                    st.error("Onbekend wachtwoord.")

    with col_docent:
        with st.container(border=True):
            mentoren = sorted(df["mentor"].unique().tolist())
            mentor_keuze = st.selectbox("Selecteer je naam", mentoren, key="login_mentor")
            ww_docent = st.text_input(
                "Wachtwoord",
                type="password",
                key="login_ww_docent",
                label_visibility="collapsed",
                placeholder="Wachtwoord",
            )
            if st.button(
                "INLOGGEN ALS DOCENT",
                key="btn_docent",
                type="primary",
                use_container_width=True,
            ):
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
inject_theme(rol)
render_nav()

if rol == "student":
    student = df[df["studentnummer"] == st.session_state["studentnummer"]].iloc[0]
    snr = str(student["studentnummer"])
    voornaam = str(student["naam"]).split()[0]

    hero(
        f"Hey, {voornaam}",
        f"{student['opleiding']} · Niveau {student['niveau']} · {student['leerweg']} · Cohort {student['cohort']}",
        badges=[("accent", "Welkom terug")],
        accent_naam=False,
    )

    voortgang_pct = int(student["voortgang"] * 100)
    behaald = int(student["bsa_behaald"])
    vereist = int(student["bsa_vereist"])
    bsa_progress = behaald / vereist if vereist else 0.0

    col_v, col_b = st.columns(2)
    with col_v:
        stat_card(
            "Studievoortgang",
            f"{voortgang_pct}%",
            progress=student["voortgang"],
        )
    with col_b:
        stat_card(
            "Studiepunten BSA",
            str(behaald),
            value_sub=f" / {vereist}",
            progress=bsa_progress,
            alert_ring=bsa_progress < 0.7,
        )

    section_label("Wat wil je doen?")
    col1, col2, col3 = st.columns(3)
    with col1:
        action_tile(
            "— voortgang",
            "Mijn voortgang",
            "Bekijk je studievoortgang, BSA en competentiescores.",
            "pages/1_mijn_voortgang.py",
            key="btn_voortgang",
        )
    with col2:
        action_tile(
            "— ai leercoach",
            "Leercoach",
            "Tutor, oefentoets en feedback op werk.",
            "pages/3_leercoach.py",
            key="btn_coach",
        )
    with col3:
        action_tile(
            "— welzijn",
            "Welzijnscheck",
            "Deel hoe het met je gaat en krijg ondersteuning.",
            "pages/5_welzijn.py",
            key="btn_welzijn",
        )

    # ── WhatsApp opt-in (eenmalig als nog niet geregistreerd) ───────────
    if not heeft_actieve_registratie(snr):
        with st.expander("Ontvang wekelijkse check-ins via WhatsApp"):
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

else:  # docent
    mentor_naam = st.session_state.get("mentor_naam", "")
    eigen = df[df["mentor"] == mentor_naam]
    totaal = len(eigen)
    risico = int(eigen["risico"].sum())
    op_schema = totaal - risico
    gem_voortgang = int(eigen["voortgang"].mean() * 100) if totaal else 0

    voornaam = mentor_naam.split()[0] if mentor_naam else "mentor"
    hero(
        f"Goedemorgen, {voornaam}",
        f"{totaal} studenten in jouw groep · {risico} vragen aandacht",
    )

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        stat_card("Op schema", str(op_schema))
    with col_b:
        stat_card(
            "Aandacht nodig",
            str(risico),
            sub=f"{risico / totaal * 100:.0f}% van groep" if totaal else None,
            delta_negative=True,
        )
    with col_c:
        stat_card("Gem. voortgang", f"{gem_voortgang}%", progress=gem_voortgang / 100)
    with col_d:
        stat_card("Studenten totaal", str(totaal))

    section_label("Wat wil je doen?")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        action_tile(
            "— per student",
            "Voortgang",
            "Individueel dashboard met scores en weekplan.",
            "pages/1_mijn_voortgang.py",
            key="btn_voortgang",
        )
    with col2:
        action_tile(
            "— groep",
            "Groepsoverzicht",
            "Alle studenten, filteren op risico, niveau, cohort.",
            "pages/2_groepsoverzicht.py",
            key="btn_groep",
        )
    with col3:
        action_tile(
            "— actie",
            "Outreach",
            "Signaleer risico's en neem contact op.",
            "pages/4_outreach.py",
            key="btn_outreach",
        )
    with col4:
        action_tile(
            "— ai",
            "Leercoach",
            "Tutor, oefentoets, feedback op werk.",
            "pages/3_leercoach.py",
            key="btn_coach",
        )

render_footer()
