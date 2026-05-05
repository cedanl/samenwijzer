"""Pagina: Welzijnscheck — student self-assessment."""

import logging
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from samenwijzer._ai import APITimeoutError
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
    stuur_welzijn_notificatie,
    urgentie_label,
)

load_dotenv()

log = logging.getLogger(__name__)

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
student_naam = studentnummer
mentor_naam = ""
if df is not None:
    rij = df[df["studentnummer"] == studentnummer]
    if not rij.empty:
        voornaam = rij.iloc[0]["naam"].split()[0]
        student_naam = rij.iloc[0]["naam"]
        mentor_naam = rij.iloc[0]["mentor"]

st.markdown(
    f"""<div class="welzijn-intro">
  <p class="welzijn-intro__title">💚 Hallo {voornaam}, hoe gaat het?</p>
  <p class="welzijn-intro__body">Geef aan waar je tegenaan loopt — je mentor krijgt een signaal en kan je helpen. Alles is veilig en vertrouwelijk.</p>
</div>""",
    unsafe_allow_html=True,
)

# ── Check-formulier ───────────────────────────────────────────────────────────
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
            height=100,
        )
        urgentie = st.radio(
            "Hoe dringend is het?",
            [1, 2, 3],
            format_func=urgentie_label,
            horizontal=True,
        )
        verzend = st.form_submit_button(
            "💚 Verstuur check", type="primary", use_container_width=True
        )

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
        st.markdown("<p class='section-label'>Reactie van Samenwijzer</p>", unsafe_allow_html=True)
        try:
            with st.spinner("Reactie genereren…"):
                reactie = st.write_stream(
                    genereer_welzijnsreactie(voornaam, categorie, toelichting.strip(), urgentie)
                )
        except APITimeoutError:
            st.error("De AI-service reageert niet. Probeer het over een moment opnieuw.")
            reactie = ""
        except Exception as e:
            log.exception("Welzijnsreactie kon niet worden gegenereerd")
            st.error(f"De reactie kon niet worden gegenereerd: {e}")
            reactie = ""

# ── Eerdere checks ────────────────────────────────────────────────────────────
eerdere = get_welzijnschecks_student(studentnummer)
if eerdere:
    with st.expander(f"Eerdere checks ({len(eerdere)})"):
        for c in eerdere[:5]:
            note = (
                f"<span class='check-item__note'>{c.toelichting[:80]}</span>"
                if c.toelichting
                else ""
            )
            st.markdown(
                f"""<div class="check-item">
  <span class="check-item__date">{c.timestamp[:10]}</span>
  <span class="check-item__label">{categorie_label(c.categorie)} · {urgentie_label(c.urgentie)}</span>
  {note}
</div>""",
                unsafe_allow_html=True,
            )

render_footer()
