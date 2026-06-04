"""Login + sessie-initialisatie voor validatie-samenwijzer."""

import hmac
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="OER-assistent · Login", page_icon="📚", layout="centered")

from validatie_samenwijzer._db import get_conn  # noqa: E402
from validatie_samenwijzer.auth import login_mentor, login_student  # noqa: E402
from validatie_samenwijzer.db import (  # noqa: E402
    INSTELLING_SOORTEN,
    get_oer_ids_by_mentor_id,
    haal_instelling_document_op,
)
from validatie_samenwijzer.styles import CSS, render_footer  # noqa: E402

# Welke instellingsbrede regelingen elke rol meekrijgt in de chat. Begeleidingsbeleid
# is mentor-only (privacy/begeleiding); de rest is student-relevant.
_STUDENT_SOORTEN = [
    "examenreglement",
    "studentenstatuut",
    "bindend_studieadvies",
    "klachtenregeling",
    "algemene_informatie",
]
_MENTOR_SOORTEN = [
    "examenreglement",
    "begeleidingsbeleid",
    "studentenstatuut",
    "bindend_studieadvies",
    "klachtenregeling",
    "algemene_informatie",
]


def _instelling_bron_paden(instelling_id: int | None, soorten: list[str]) -> list[tuple[str, str]]:
    """[(label, bestandspad)] voor de geïndexeerde instellingsbrede regelingen van een instelling.

    Label komt uit INSTELLING_SOORTEN (één bron van waarheid voor opslag, blok-kop en citatie).
    """
    if not instelling_id:
        return []
    paden = []
    for soort in soorten:
        doc = haal_instelling_document_op(get_conn(), instelling_id, soort)
        if doc and doc["geindexeerd"]:
            paden.append((INSTELLING_SOORTEN[soort], doc["bestandspad"]))
    return paden


st.markdown(CSS, unsafe_allow_html=True)


def _sla_student_op(student) -> None:
    oer = (
        get_conn()
        .execute(
            "SELECT oer_documenten.*, instellingen.display_naam "
            "FROM oer_documenten JOIN instellingen ON instellingen.id = oer_documenten.instelling_id "
            "WHERE oer_documenten.id = ?",
            (student["oer_id"],),
        )
        .fetchone()
    )
    st.session_state.update(
        {
            "rol": "student",
            "gebruiker_id": student["id"],
            "gebruiker_naam": student["naam"],
            "studentnummer": student["studentnummer"],
            "oer_id": student["oer_id"],
            "opleiding": oer["opleiding"] if oer else "",
            "instelling": oer["display_naam"] if oer else "",
            "crebo": oer["crebo"] if oer else "",
            "leerweg": oer["leerweg"] if oer else "",
            "bestandspad": oer["bestandspad"] if oer else "",
            "instelling_bron_paden": _instelling_bron_paden(
                oer["instelling_id"] if oer else None, _STUDENT_SOORTEN
            ),
            "chat_history": [],
        }
    )


def _sla_mentor_op(mentor) -> None:
    oer_ids = get_oer_ids_by_mentor_id(get_conn(), mentor["id"])
    instelling = (
        get_conn()
        .execute(
            "SELECT display_naam FROM instellingen WHERE id = ?",
            (mentor["instelling_id"],),
        )
        .fetchone()
    )
    st.session_state.update(
        {
            "rol": "mentor",
            "gebruiker_id": mentor["id"],
            "gebruiker_naam": mentor["naam"],
            "oer_ids": oer_ids,
            "instelling": instelling["display_naam"] if instelling else "",
            "opleiding": "Mentor",
            "instelling_bron_paden": _instelling_bron_paden(
                mentor["instelling_id"], _MENTOR_SOORTEN
            ),
            "actieve_student": None,
            "chat_history": [],
        }
    )


if st.session_state.get("rol") == "student":
    st.switch_page("pages/1_oer_assistent.py")
elif st.session_state.get("rol") == "mentor":
    st.switch_page("pages/4_mijn_studenten.py")
elif st.session_state.get("rol") == "gast":
    st.switch_page("pages/0_oer_vraag.py")

st.title("📚 OER-assistent")
st.caption("Samenwijzer · CEDA 2026")

st.divider()

tab_student, tab_mentor, tab_algemeen = st.tabs(["Student", "Mentor", "Direct een OER-vraag"])

with tab_student:
    with st.form("login_student"):
        studentnummer = st.text_input("Studentnummer")
        ww = st.text_input("Wachtwoord", type="password")
        if st.form_submit_button("Inloggen als student", use_container_width=True):
            student = login_student(get_conn(), studentnummer.strip(), ww)
            if student:
                _sla_student_op(student)
                st.switch_page("pages/1_oer_assistent.py")
            else:
                st.error("Onbekend studentnummer of onjuist wachtwoord.")

with tab_mentor:
    with st.form("login_mentor"):
        naam = st.text_input("Naam")
        ww2 = st.text_input("Wachtwoord", type="password")
        if st.form_submit_button("Inloggen als mentor", use_container_width=True):
            mentor = login_mentor(get_conn(), naam.strip(), ww2)
            if mentor:
                _sla_mentor_op(mentor)
                st.switch_page("pages/4_mijn_studenten.py")
            else:
                st.error("Onbekende naam of onjuist wachtwoord.")

with tab_algemeen:
    st.caption(
        "Stel direct OER-vragen met een algemeen account — geen persoonlijke gegevens nodig."
    )
    with st.form("login_algemeen"):
        ww_algemeen = st.text_input("Wachtwoord", type="password")
        if st.form_submit_button("Inloggen voor OER-vraag", use_container_width=True):
            # Fail-closed: vereist ALGEMEEN_WACHTWOORD (geen hardcoded default; de
            # repo is publiek). Constant-time vergelijking tegen timing-lekken.
            algemeen_pw = os.environ.get("ALGEMEEN_WACHTWOORD")
            if not algemeen_pw:
                st.error("Het algemene account is niet geconfigureerd.")
            elif ww_algemeen and hmac.compare_digest(ww_algemeen, algemeen_pw):
                st.session_state["rol"] = "gast"
                st.switch_page("pages/0_oer_vraag.py")
            else:
                st.error("Onjuist wachtwoord.")

render_footer()
