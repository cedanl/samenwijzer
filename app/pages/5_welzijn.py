"""Pagina: Welzijnscheck — student self-assessment."""

import logging
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from samenwijzer._ai import APITimeoutError, vriendelijke_fout
from samenwijzer.outreach_store import (
    WelzijnsCheck,
    get_welzijnschecks_student,
    sla_welzijnscheck_op,
)
from samenwijzer.styles import (
    hero,
    inject_theme,
    render_footer,
    render_nav,
    section_label,
)
from samenwijzer.welzijn import (
    CATEGORIEËN,
    categorie_label,
    genereer_welzijnsreactie,
    stuur_welzijn_notificatie,
    urgentie_label,
)

load_dotenv()

log = logging.getLogger(__name__)

st.set_page_config(page_title="Welzijnscheck — Samenwijzer", page_icon="💚", layout="wide")

# ── Toegangscheck ─────────────────────────────────────────────────────────────
if "rol" not in st.session_state or st.session_state["rol"] != "student":
    inject_theme(None)
    st.warning("Deze pagina is alleen beschikbaar voor studenten.")
    st.stop()

if "studentnummer" not in st.session_state:
    inject_theme(None)
    st.warning("Ga eerst naar de [startpagina](/) om in te loggen.")
    st.stop()

inject_theme("student")
render_nav()

studentnummer = st.session_state["studentnummer"]
df = st.session_state.get("df")
voornaam = studentnummer
student_naam = studentnummer
mentor_naam = ""
if df is not None:
    rij = df[df["studentnummer"] == studentnummer]
    if not rij.empty:
        voornaam = rij.iloc[0]["naam"].split()[0]
        student_naam = rij.iloc[0]["naam"]
        mentor_naam = rij.iloc[0]["mentor"]

# ── Hero — zacht ingangsmoment ───────────────────────────────────────────────
hero(
    f"Hoe gaat het, {voornaam}?",
    "Veilig · alleen jij en je mentor zien de details",
)

st.caption("Je mentor krijgt een signaal en kan je helpen. Alles is veilig en vertrouwelijk.")

# ── Check-formulier ───────────────────────────────────────────────────────────
section_label("Wat speelt er?")

with st.container(border=True):
    with st.form("welzijnscheck"):
        categorie = st.selectbox(
            "Waar heb je moeite mee?",
            CATEGORIEËN,
            format_func=categorie_label,
        )
        toelichting = st.text_area(
            "Vertel er iets meer over (optioneel)",
            placeholder="Beschrijf kort wat er speelt…",
            height=120,
        )
        urgentie = st.radio(
            "Hoe dringend is het?",
            [1, 2, 3],
            format_func=urgentie_label,
            horizontal=True,
        )
        verzend = st.form_submit_button("Verstuur check", type="primary", use_container_width=True)

if verzend:
    check = WelzijnsCheck(
        studentnummer=studentnummer,
        timestamp=datetime.now().isoformat(),
        categorie=categorie,
        toelichting=toelichting.strip(),
        urgentie=urgentie,
    )
    sla_welzijnscheck_op(check)

    verstuurd = stuur_welzijn_notificatie(
        student_naam=student_naam,
        mentor_naam=mentor_naam,
        categorie=categorie,
        urgentie=urgentie,
        toelichting=toelichting.strip(),
        timestamp=check.timestamp,
    )

    if verstuurd:
        st.success("Je check is verstuurd. Je mentor heeft een e-mailmelding ontvangen.")
    else:
        st.success("Je check is verstuurd. Je mentor wordt op de hoogte gesteld.")

    with st.container(border=True):
        section_label("Reactie van Samenwijzer")
        try:
            with st.spinner("Reactie genereren…"):
                st.write_stream(
                    genereer_welzijnsreactie(voornaam, categorie, toelichting.strip(), urgentie)
                )
        except APITimeoutError:
            st.error("De AI-service reageert niet. Probeer het over een moment opnieuw.")
        except Exception as e:
            log.exception("Welzijnsreactie kon niet worden gegenereerd")
            st.error(vriendelijke_fout(e))

# ── Eerdere checks ────────────────────────────────────────────────────────────
eerdere = get_welzijnschecks_student(studentnummer)
if eerdere:
    with st.expander(f"Eerdere checks ({len(eerdere)})"):
        for c in eerdere[:5]:
            note = (
                f"<br><span style='color:var(--text-faint);font-size:12px;'>{c.toelichting[:120]}</span>"
                if c.toelichting
                else ""
            )
            st.markdown(
                f"<div style='padding:10px 0;border-bottom:1px solid var(--border);"
                f"font-family:var(--font-mono);font-size:11px;color:var(--text-faint);"
                f"letter-spacing:0.06em;text-transform:uppercase;'>"
                f"{c.timestamp[:10]} · "
                f"<span style='color:var(--text);'>{categorie_label(c.categorie)} · "
                f"{urgentie_label(c.urgentie)}</span>{note}</div>",
                unsafe_allow_html=True,
            )

render_footer()
