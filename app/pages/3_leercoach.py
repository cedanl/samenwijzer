"""Pagina: AI Leerondersteuning — tutor, lesmateriaal, oefentoets en werkfeedback."""

import os

import streamlit as st
from dotenv import load_dotenv

from samenwijzer.analyze import get_student, leerpad_niveau, zwakste_kerntaak
from samenwijzer.auth import mentor_filter
from samenwijzer.coach import (
    controleer_antwoorden,
    geef_feedback_op_werk,
    genereer_lesmateriaal,
    genereer_oefentoets,
)
from samenwijzer.styles import CSS, render_footer, render_nav
from samenwijzer.tutor import StudentContext, TutorSessie, stuur_bericht

load_dotenv()

st.set_page_config(page_title="AI Leerondersteuning — Samenwijzer", page_icon="🎓", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
render_nav()
st.title("🎓 AI Leerondersteuning")

# ── Vereisten ──────────────────────────────────────────────────────────────────
if "df" not in st.session_state or "rol" not in st.session_state:
    st.warning("Ga eerst naar de startpagina om in te loggen.")
    st.stop()

if not os.environ.get("ANTHROPIC_API_KEY"):
    st.error(
        "Geen ANTHROPIC_API_KEY gevonden. "
        "Maak een `.env` bestand aan met `ANTHROPIC_API_KEY=sk-ant-...` en herstart de app."
    )
    st.stop()

df = st.session_state["df"]
rol = st.session_state["rol"]

# ── Studentselectie (rol-afhankelijk) ──────────────────────────────────────────
if rol == "student":
    # Student ziet altijd en alleen zijn eigen gegevens — geen selector tonen
    studentnummer = st.session_state["studentnummer"]
    student = get_student(df, studentnummer)
    leerpad = leerpad_niveau(student)
    opleiding = student["opleiding"]
    st.caption(f"**{opleiding}** · Leerpad: **{leerpad}**")
else:
    # Docent ziet alleen studenten uit eigen groep
    groep = mentor_filter(df)
    opties = (
        groep.sort_values("naam")[["naam", "studentnummer"]]
        .apply(lambda r: f"{r['naam']} ({r['studentnummer']})", axis=1)
        .tolist()
    )
    col_sel, col_info = st.columns([2, 1])
    with col_sel:
        keuze = st.selectbox("Selecteer een student", opties)
    studentnummer = keuze.split("(")[-1].rstrip(")")
    student = get_student(df, studentnummer)
    leerpad = leerpad_niveau(student)
    opleiding = student["opleiding"]
    with col_info:
        st.caption(f"**{opleiding}** · Leerpad: **{leerpad}**")

zkt = zwakste_kerntaak(df, studentnummer)
zwakste_kt_label = zkt[0] if zkt else ""

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_tutor, tab_les, tab_toets, tab_werk = st.tabs(
    ["🎓 Tutor", "📚 Lesmateriaal", "📝 Oefentoets", "✏️ Feedback op werk"]
)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: SOCRATISCHE TUTOR
# ─────────────────────────────────────────────────────────────────────────────
with tab_tutor:
    st.caption(
        "De tutor helpt je zelf antwoorden te vinden — hij geeft geen kant-en-klare "
        "oplossingen, maar stelt je de juiste vragen."
    )

    col_kt, col_btn = st.columns([3, 1])
    with col_kt:
        kt_opties = ["(geen specifiek)"] + [
            c.replace("_", " ").title()
            for c in df.columns
            if c.startswith("kt") and not c.endswith("_gemiddelde")
        ]
        kerntaak_focus = st.selectbox("Focus op kerntaak", kt_opties, key="kt_focus")
        focus_tekst = "" if kerntaak_focus == "(geen specifiek)" else kerntaak_focus
    with col_btn:
        st.markdown("<div style='padding-top:1.6rem'>", unsafe_allow_html=True)
        if st.button("NIEUW GESPREK", use_container_width=True):
            st.session_state.pop(f"tutor_sessie_{studentnummer}", None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    sessie_sleutel = f"tutor_sessie_{studentnummer}"
    if sessie_sleutel not in st.session_state:
        context = StudentContext(
            naam=student["naam"],
            opleiding=opleiding,
            niveau=int(student["niveau"]),
            voortgang=float(student["voortgang"]),
            kerntaak_focus=focus_tekst,
        )
        st.session_state[sessie_sleutel] = TutorSessie(student=context)

    sessie: TutorSessie = st.session_state[sessie_sleutel]
    sessie.student.kerntaak_focus = focus_tekst

    for bericht in sessie.geschiedenis:
        rol = "user" if bericht["role"] == "user" else "assistant"
        with st.chat_message(rol):
            st.write(bericht["content"])

    invoer = st.chat_input("Typ je vraag of gedachte hier…")
    if invoer:
        with st.chat_message("user"):
            st.write(invoer)
        with st.chat_message("assistant"):
            try:
                st.write_stream(stuur_bericht(sessie, invoer))
            except Exception as e:
                st.error(f"De tutor kon niet antwoorden: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: LESMATERIAAL
# ─────────────────────────────────────────────────────────────────────────────
with tab_les:
    st.subheader("Gepersonaliseerd lesmateriaal")
    st.caption(f"Afgestemd op **{leerpad}**-niveau voor **{opleiding}**.")

    with st.container(border=True):
        onderwerp = st.text_input(
            "Onderwerp",
            value=zwakste_kt_label,
            placeholder="bijv. wondverzorging, communicatie met cliënten …",
            key="les_onderwerp",
        )
        if st.button("GENEREER LESMATERIAAL", type="primary", key="btn_les"):
            if not onderwerp.strip():
                st.warning("Vul een onderwerp in.")
            else:
                st.session_state.pop("sw_lesmateriaal", None)
                tekst = st.write_stream(
                    genereer_lesmateriaal(onderwerp.strip(), opleiding, leerpad, zwakste_kt_label)
                )
                st.session_state["sw_lesmateriaal"] = tekst
        elif "sw_lesmateriaal" in st.session_state:
            st.markdown(st.session_state["sw_lesmateriaal"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: OEFENTOETS
# ─────────────────────────────────────────────────────────────────────────────
with tab_toets:
    st.subheader("AI-Oefentoets")
    st.caption("Genereer een toets en ontvang directe AI-feedback op je antwoorden.")

    with st.container(border=True):
        onderwerp_toets = st.text_input(
            "Onderwerp voor de toets",
            value=zwakste_kt_label,
            placeholder="bijv. wondverzorging, medicatieveiligheid …",
            key="toets_onderwerp",
        )
        if st.button("GENEREER OEFENTOETS", type="primary", key="btn_toets"):
            if not onderwerp_toets.strip():
                st.warning("Vul een onderwerp in.")
            else:
                for k in ("sw_toets_tekst", "sw_toets_feedback"):
                    st.session_state.pop(k, None)
                with st.spinner("Toets wordt gegenereerd…"):
                    st.session_state["sw_toets_tekst"] = genereer_oefentoets(
                        onderwerp_toets.strip(), opleiding, leerpad
                    )

    if "sw_toets_tekst" in st.session_state:
        toets_tekst = st.session_state["sw_toets_tekst"]
        vragen_deel = (
            toets_tekst.split("ANTWOORDEN:")[0] if "ANTWOORDEN:" in toets_tekst else toets_tekst
        )

        with st.container(border=True):
            st.markdown(vragen_deel)
            st.divider()
            st.markdown("**Vul jouw antwoorden in:**")

            opties = ["—", "A", "B", "C", "D"]
            antwoorden: dict[int, str] = {}
            cols = st.columns(5)
            for i, col in enumerate(cols, start=1):
                with col:
                    keuze_antw = st.selectbox(f"Vraag {i}", opties, key=f"sw_antw_{i}")
                    if keuze_antw != "—":
                        antwoorden[i] = keuze_antw

            if st.button("CONTROLEER ANTWOORDEN", type="primary", key="btn_controleer"):
                if len(antwoorden) < 5:
                    st.warning("Beantwoord eerst alle 5 vragen.")
                else:
                    st.session_state.pop("sw_toets_feedback", None)
                    feedback = st.write_stream(
                        controleer_antwoorden(toets_tekst, antwoorden, opleiding, leerpad)
                    )
                    st.session_state["sw_toets_feedback"] = feedback
            elif "sw_toets_feedback" in st.session_state:
                st.divider()
                st.markdown(st.session_state["sw_toets_feedback"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: FEEDBACK OP WERK
# ─────────────────────────────────────────────────────────────────────────────
with tab_werk:
    st.subheader("Feedback op jouw werk")
    st.caption(
        "Upload een tekstbestand of plak je werk hieronder. "
        "De AI geeft feedback afgestemd op jouw opleiding en niveau."
    )

    with st.container(border=True):
        uploaded = st.file_uploader(
            "Upload een .txt bestand (optioneel)",
            type=["txt"],
            key="sw_upload",
        )

        if uploaded is not None:
            werk_tekst = uploaded.read().decode("utf-8", errors="replace")
            st.text_area("Inhoud van het bestand", werk_tekst, height=150, disabled=True)
        else:
            werk_tekst = st.text_area(
                "Of plak je werk hier",
                height=200,
                placeholder="Plak hier je verslag, samenvatting of opdracht…",
                key="sw_werk_tekst",
            )

        if st.button("GEEF FEEDBACK", type="primary", key="btn_feedback"):
            if not werk_tekst.strip():
                st.warning("Upload een bestand of plak je werk in het tekstvak.")
            else:
                st.session_state.pop("sw_werk_feedback", None)
                fb = st.write_stream(geef_feedback_op_werk(werk_tekst.strip(), opleiding, leerpad))
                st.session_state["sw_werk_feedback"] = fb
        elif "sw_werk_feedback" in st.session_state:
            st.divider()
            st.markdown(st.session_state["sw_werk_feedback"])

render_footer()
