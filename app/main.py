"""Samenwijzer — welkomspagina en gecentraliseerde sessie-initialisatie.

Laadt studiedata eenmalig in st.session_state. De student kiest hier zijn naam
eenmalig; alle andere pagina's lezen studentnummer uit st.session_state.
"""

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from samenwijzer.prepare import load_student_csv
from samenwijzer.transform import transform_student_data

load_dotenv()

_DEMO_CSV = Path(__file__).parent.parent / "data" / "01-raw" / "demo" / "studenten.csv"

st.set_page_config(
    page_title="Samenwijzer",
    page_icon="📚",
    layout="wide",
)


@st.cache_data
def _laad_data(path: Path):
    df = load_student_csv(path)
    return transform_student_data(df)


if "df" not in st.session_state:
    st.session_state["df"] = _laad_data(_DEMO_CSV)

df = st.session_state["df"]

# ── Welkom ────────────────────────────────────────────────────────────────────
st.title("📚 Welkom bij Samenwijzer")
st.write(
    "Samenwijzer helpt je grip te krijgen op je eigen leerproces. "
    "Je ziet waar je staat, waar je naartoe werkt, "
    "en je kunt op elk moment in gesprek met je persoonlijke AI-tutor."
)

st.divider()

# ── Studentselectie ───────────────────────────────────────────────────────────
st.subheader("Wie ben jij?")
st.caption("Kies je naam om te beginnen. Je hoeft geen account aan te maken.")

namen = (
    df.sort_values("naam")[["naam", "studentnummer"]]
    .apply(lambda r: f"{r['naam']} ({r['studentnummer']})", axis=1)
    .tolist()
)

huidig = st.session_state.get("studentnummer")
huidig_index = 0
if huidig:
    overeenkomsten = [i for i, n in enumerate(namen) if n.endswith(f"({huidig})")]
    if overeenkomsten:
        huidig_index = overeenkomsten[0]

keuze = st.selectbox("Selecteer je naam", namen, index=huidig_index)
nieuw_studentnummer = keuze.split("(")[-1].rstrip(")")

if nieuw_studentnummer != huidig:
    st.session_state["studentnummer"] = nieuw_studentnummer
    # Wis tutorsessies bij wisselen van student
    for key in list(st.session_state.keys()):
        if key.startswith("tutor_sessie_"):
            del st.session_state[key]

student = df[df["studentnummer"] == nieuw_studentnummer].iloc[0]

st.success(
    f"Welkom, **{student['naam']}** · {student['opleiding']} "
    f"· Niveau {student['niveau']} · {student['leerweg']}"
)

st.divider()

# ── Navigatiekaarten ──────────────────────────────────────────────────────────
st.subheader("Wat wil je doen?")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📊 Mijn voortgang")
    st.write(
        "Bekijk je studievoortgang, behaalde studiepunten en scores op kerntaken en werkprocessen."
    )
    st.page_link("pages/1_mijn_voortgang.py", label="Ga naar Mijn voortgang →")

with col2:
    st.markdown("### 🎓 AI Tutor")
    st.write(
        "Chat met je persoonlijke tutor. Hij helpt je zelf "
        "antwoorden te vinden door de juiste vragen te stellen."
    )
    st.page_link("pages/3_tutor.py", label="Ga naar AI Tutor →")

with col3:
    st.markdown("### 👥 Groepsoverzicht")
    st.write(
        "Voor docenten en mentoren: bekijk de voortgang "
        "van de hele groep en zie wie aandacht nodig heeft."
    )
    st.page_link("pages/2_groepsoverzicht.py", label="Ga naar Groepsoverzicht →")
