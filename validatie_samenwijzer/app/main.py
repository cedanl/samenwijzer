"""Login + sessie-initialisatie voor validatie-samenwijzer."""

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="OER-assistent · Login", page_icon="📚", layout="centered")

from validatie_samenwijzer._db import get_conn  # noqa: E402
from validatie_samenwijzer.auth import login_mentor, login_student  # noqa: E402
from validatie_samenwijzer.db import get_oer_ids_by_mentor_id  # noqa: E402
from validatie_samenwijzer.styles import CSS, render_footer  # noqa: E402

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
            "actieve_student": None,
            "chat_history": [],
        }
    )


if st.session_state.get("rol") == "student":
    st.switch_page("pages/1_oer_assistent.py")
elif st.session_state.get("rol") == "mentor":
    st.switch_page("pages/4_mijn_studenten.py")

st.title("📚 OER-assistent")
st.caption("Samenwijzer · CEDA 2026")

tab_student, tab_mentor = st.tabs(["Student", "Mentor"])

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

st.divider()
st.page_link("pages/0_oer_vraag.py", label="📚 Stel direct een OER-vraag zonder in te loggen →")

render_footer()
