"""Pagina: AI Leerondersteuning — tutor, lesmateriaal, oefentoets en werkfeedback."""

import os

import streamlit as st
from dotenv import load_dotenv

from samenwijzer.analyze import get_student, leerpad_niveau, zwakste_kerntaak
from samenwijzer.auth import mentor_filter
from samenwijzer.coach import (
    SCENARIO_OPTIES,
    RollenspelSessie,
    controleer_antwoorden,
    geef_feedback_op_werk,
    genereer_lesmateriaal,
    genereer_oefentoets,
    genereer_rollenspel_feedback,
    stuur_rollenspel_bericht,
)
from samenwijzer.styles import CSS, render_footer, render_nav
from samenwijzer.tutor import StudentContext, TutorSessie, stuur_bericht
from samenwijzer.whatsapp import laad_whatsapp_gesprek

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
    leerpad_klasse = leerpad.lower()
    st.markdown(
        f"<span class='badge badge--{leerpad_klasse}'>{leerpad}</span> "
        f"<span style='color:#888; font-size:0.85rem; margin-left:8px'>{opleiding}</span>",
        unsafe_allow_html=True,
    )
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
        leerpad_klasse = leerpad.lower()
        st.markdown(
            f"<span class='badge badge--{leerpad_klasse}'>{leerpad}</span> "
            f"<span style='color:#888; font-size:0.85rem; margin-left:8px'>{opleiding}</span>",
            unsafe_allow_html=True,
        )

zkt = zwakste_kerntaak(df, studentnummer)
zwakste_kt_label = zkt[0] if zkt else ""

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_tutor, tab_les, tab_toets, tab_werk, tab_rol = st.tabs(
    ["🎓 Tutor", "📚 Lesmateriaal", "📝 Oefentoets", "✏️ Feedback op werk", "🎭 Rollenspel"]
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
        if st.button("↺ Nieuw gesprek", use_container_width=True):
            st.session_state.pop(f"tutor_sessie_{studentnummer}", None)
            st.rerun()

    sessie_sleutel = f"tutor_sessie_{studentnummer}"
    if sessie_sleutel not in st.session_state:
        context = StudentContext(
            naam=student["naam"],
            opleiding=opleiding,
            niveau=int(student["niveau"]),
            voortgang=float(student["voortgang"]),
            kerntaak_focus=focus_tekst,
        )
        nieuwe_sessie = TutorSessie(student=context)

        # Laad WhatsApp-gesprekcontext als die beschikbaar is
        wa_data = laad_whatsapp_gesprek(studentnummer)
        if wa_data:
            for bericht in wa_data.get("gesprek", []):
                rol_map = {"student": "user", "coach": "assistant"}
                rol = rol_map.get(bericht.get("rol", ""), "user")
                nieuwe_sessie.voeg_toe(rol, bericht.get("tekst", ""))
            st.session_state[f"wa_context_geladen_{studentnummer}"] = wa_data["datum"]

        st.session_state[sessie_sleutel] = nieuwe_sessie

    sessie: TutorSessie = st.session_state[sessie_sleutel]
    sessie.student.kerntaak_focus = focus_tekst

    wa_datum = st.session_state.get(f"wa_context_geladen_{studentnummer}")
    if wa_datum and sessie.geschiedenis:
        st.info(
            f"📱 WhatsApp-gesprek van {wa_datum} is geladen als startcontext. "
            "De tutor is op de hoogte van dit gesprek.",
            icon="💬",
        )

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
        if st.button("📚 Genereer lesmateriaal", type="primary", key="btn_les"):
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
        if st.button("📝 Genereer oefentoets", type="primary", key="btn_toets"):
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

            if st.button("✓ Controleer antwoorden", type="primary", key="btn_controleer"):
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

        if st.button("✏️ Geef feedback", type="primary", key="btn_feedback"):
            if not werk_tekst.strip():
                st.warning("Upload een bestand of plak je werk in het tekstvak.")
            else:
                st.session_state.pop("sw_werk_feedback", None)
                fb = st.write_stream(geef_feedback_op_werk(werk_tekst.strip(), opleiding, leerpad))
                st.session_state["sw_werk_feedback"] = fb
        elif "sw_werk_feedback" in st.session_state:
            st.divider()
            st.markdown(st.session_state["sw_werk_feedback"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 5: ROLLENSPEL
# ─────────────────────────────────────────────────────────────────────────────
with tab_rol:
    st.subheader("🎭 Rollenspel")
    st.caption(
        "Oefen een gesprek met een AI-tegenpartij. "
        "Na afloop geeft de AI coaching op hoe het gesprek verliep."
    )

    rp_sleutel = f"rp_sessie_{studentnummer}"
    rp_feedback_sleutel = f"rp_feedback_{studentnummer}"

    # ── Scenario-instelling (alleen zichtbaar als er nog geen sessie is) ──────
    if rp_sleutel not in st.session_state:
        with st.container(border=True):
            scenario_labels = list(SCENARIO_OPTIES.values())
            scenario_codes = list(SCENARIO_OPTIES.keys())
            keuze_idx = st.selectbox(
                "Kies een scenario",
                range(len(scenario_labels)),
                format_func=lambda i: scenario_labels[i],
                key="rp_scenario_keuze",
            )
            if st.button("🎭 Start rollenspel", type="primary", key="btn_rp_start"):
                st.session_state[rp_sleutel] = RollenspelSessie(
                    scenario=scenario_codes[keuze_idx],
                    opleiding=opleiding,
                    leerpad=leerpad,
                    naam=student["naam"],
                )
                st.session_state.pop(rp_feedback_sleutel, None)
                st.rerun()
    else:
        rp_sessie: RollenspelSessie = st.session_state[rp_sleutel]

        col_info, col_nieuw = st.columns([3, 1])
        with col_info:
            st.caption(
                f"Scenario: **{SCENARIO_OPTIES[rp_sessie.scenario]}** · "
                f"Tegenpartij: **{rp_sessie.tegenpartij()}**"
            )
        with col_nieuw:
            if st.button("↺ Nieuw gesprek", use_container_width=True, key="btn_rp_reset"):
                st.session_state.pop(rp_sleutel, None)
                st.session_state.pop(rp_feedback_sleutel, None)
                st.rerun()

        # ── Gespreksgeschiedenis ──────────────────────────────────────────────
        for bericht in rp_sessie.geschiedenis:
            spreker = "user" if bericht["role"] == "user" else "assistant"
            with st.chat_message(spreker):
                st.write(bericht["content"])

        # ── Invoer (uitgeschakeld als feedback al gegeven is) ─────────────────
        if rp_feedback_sleutel not in st.session_state:
            invoer = st.chat_input(
                f"Typ wat jij zegt tegen de {rp_sessie.tegenpartij()}…",
                key="rp_invoer",
            )
            if invoer:
                with st.chat_message("user"):
                    st.write(invoer)
                with st.chat_message("assistant"):
                    try:
                        st.write_stream(stuur_rollenspel_bericht(rp_sessie, invoer))
                    except Exception as e:
                        st.error(f"De tegenpartij kon niet antwoorden: {e}")

            st.divider()
            if rp_sessie.geschiedenis and st.button(
                "✅ Afronden & feedback",
                type="primary",
                key="btn_rp_feedback",
            ):
                with st.spinner("Nabespreking wordt opgesteld…"):
                    try:
                        feedback = st.write_stream(genereer_rollenspel_feedback(rp_sessie))
                        st.session_state[rp_feedback_sleutel] = feedback
                    except Exception as e:
                        st.error(f"Feedback kon niet worden opgesteld: {e}")
        else:
            # ── Eerder gegenereerde feedback tonen ────────────────────────────
            st.divider()
            st.subheader("Nabespreking")
            st.markdown(st.session_state[rp_feedback_sleutel])

render_footer()
