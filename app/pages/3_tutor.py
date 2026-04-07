"""Pagina: AI Tutor — persoonlijke Socratische leerondersteuning."""

import os

import streamlit as st

from samenwijzer.analyze import get_student
from samenwijzer.tutor import StudentContext, TutorSessie, stuur_bericht

st.set_page_config(page_title="AI Tutor — Samenwijzer", page_icon="🎓", layout="wide")
st.title("🎓 AI Tutor")
st.caption(
    "De tutor helpt je zelf antwoorden te vinden — hij geeft geen kant-en-klare oplossingen, "
    "maar stelt je de juiste vragen."
)

# ── Vereisten ─────────────────────────────────────────────────────────────────
if "df" not in st.session_state:
    st.warning("Ga eerst naar de startpagina om de data te laden.")
    st.stop()

if not os.environ.get("ANTHROPIC_API_KEY"):
    st.error(
        "Geen ANTHROPIC_API_KEY gevonden. "
        "Maak een `.env` bestand aan met `ANTHROPIC_API_KEY=sk-ant-...` "
        "en herstart de app."
    )
    st.stop()

df = st.session_state["df"]

# ── Studentselectie ───────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Instellingen")

    namen = (
        df.sort_values("naam")[["naam", "studentnummer"]]
        .apply(lambda r: f"{r['naam']} ({r['studentnummer']})", axis=1)
        .tolist()
    )
    keuze = st.selectbox("Jij bent", namen)
    studentnummer = keuze.split("(")[-1].rstrip(")")
    student_row = get_student(df, studentnummer)

    kt_opties = ["(geen specifiek)"] + [
        c.replace("_", " ").title()
        for c in df.columns
        if c.startswith("kt") and not c.endswith("_gemiddelde")
    ]
    kerntaak_focus = st.selectbox("Focus op kerntaak", kt_opties)
    focus_tekst = "" if kerntaak_focus == "(geen specifiek)" else kerntaak_focus

    if st.button("Nieuw gesprek", use_container_width=True):
        st.session_state.pop("tutor_sessie", None)
        st.rerun()

# ── Sessie aanmaken of hergebruiken ───────────────────────────────────────────
sessie_sleutel = f"tutor_sessie_{studentnummer}"

if sessie_sleutel not in st.session_state:
    context = StudentContext(
        naam=student_row["naam"],
        opleiding=student_row["opleiding"],
        niveau=int(student_row["niveau"]),
        voortgang=float(student_row["voortgang"]),
        kerntaak_focus=focus_tekst,
    )
    st.session_state[sessie_sleutel] = TutorSessie(student=context)

sessie: TutorSessie = st.session_state[sessie_sleutel]

# Pas kerntaakfocus aan als de student die heeft gewijzigd
sessie.student.kerntaak_focus = focus_tekst

# ── Gespreksweergave ──────────────────────────────────────────────────────────
for bericht in sessie.geschiedenis:
    rol = "user" if bericht["role"] == "user" else "assistant"
    with st.chat_message(rol):
        st.write(bericht["content"])

# ── Chatinvoer ────────────────────────────────────────────────────────────────
invoer = st.chat_input("Typ je vraag of gedachte hier…")

if invoer:
    with st.chat_message("user"):
        st.write(invoer)

    with st.chat_message("assistant"):
        try:
            reactie = st.write_stream(stuur_bericht(sessie, invoer))
        except Exception as e:
            st.error(f"De tutor kon niet antwoorden: {e}")
