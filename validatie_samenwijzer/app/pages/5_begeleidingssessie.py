"""Mentor: studentprofiel + OER-assistent naast elkaar."""

import base64
import html
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Begeleidingssessie", page_icon="🎓", layout="wide")

from validatie_samenwijzer._ai import _client as ai_client  # noqa: E402
from validatie_samenwijzer._db import get_conn  # noqa: E402
from validatie_samenwijzer.auth import vereist_mentor  # noqa: E402
from validatie_samenwijzer.chat import (  # noqa: E402
    LAGE_RELEVANTIE_BERICHT,
    bouw_berichten,
    bouw_systeem,
    genereer_antwoord,
    laad_oer_tekst,
)
from validatie_samenwijzer.db import get_kerntaak_scores_by_student_id  # noqa: E402
from validatie_samenwijzer.ingest import extraheer_tekst_html  # noqa: E402
from validatie_samenwijzer.styles import (  # noqa: E402
    CSS,
    GROEN,
    ORANJE,
    ROOD,
    render_footer,
    render_nav,
)

st.markdown(CSS, unsafe_allow_html=True)
vereist_mentor()
render_nav()

MAX_GESCHIEDENIS = 20  # 10 uitwisselingen

student = st.session_state.get("actieve_student")
if not student:
    st.warning("Geen student geselecteerd. Ga terug naar 'Mijn studenten'.")
    st.page_link("pages/4_mijn_studenten.py", label="← Mijn studenten")
    st.stop()

oer = (
    get_conn()
    .execute(
        """SELECT oer_documenten.*, instellingen.display_naam
       FROM oer_documenten JOIN instellingen ON instellingen.id =
       oer_documenten.instelling_id WHERE oer_documenten.id = ?""",
        (student["oer_id"],),
    )
    .fetchone()
)

opleiding = oer["opleiding"] if oer else ""
instelling = oer["display_naam"] if oer else ""

st.subheader(f"🎓 Begeleidingssessie — {student['naam']}")
st.caption(f"{opleiding} · {instelling}")

col_profiel, col_chat = st.columns([1.3, 2])

with col_profiel:
    vg = student.get("voortgang") or 0.0
    bsa_b = student.get("bsa_behaald") or 0.0
    bsa_v = student.get("bsa_vereist") or 60.0
    bsa_pct = min(bsa_b / bsa_v, 1.0) if bsa_v else 0.0
    afwn = student.get("absence_unauthorized") or 0.0

    kleur_vg = GROEN if vg >= 0.7 else (ORANJE if vg >= 0.5 else ROOD)

    with st.container(border=True):
        st.markdown("**Voortgang**")
        st.markdown(
            f"<span style='font-size:1.4rem;font-weight:700;color:{kleur_vg}'>"
            f"{vg * 100:.0f}%</span>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="progress-bar-bg"><div class="progress-bar-fill" '
            f'style="width:{vg * 100:.0f}%;background:{kleur_vg}"></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(f"BSA: **{bsa_b:.0f}/{bsa_v:.0f} uur** ({bsa_pct * 100:.0f}%)")
        kleur_afw = ROOD if afwn > 10 else (ORANJE if afwn > 5 else GROEN)
        st.markdown(
            f"Ongeoorl. afwez.: <span style='color:{kleur_afw}'><b>{afwn:.0f} uur</b></span>",
            unsafe_allow_html=True,
        )

    scores = get_kerntaak_scores_by_student_id(get_conn(), student["id"])
    lage_kt: list = []
    if scores:
        with st.container(border=True):
            st.markdown("**Kerntaken**")
            for s in scores:
                if s["type"] == "kerntaak":
                    kleur = GROEN if s["score"] >= 70 else (ORANJE if s["score"] >= 50 else ROOD)
                    st.markdown(f"<small>{html.escape(s['naam'])}</small>", unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="progress-bar-bg"><div class="progress-bar-fill" '
                        f'style="width:{s["score"]:.0f}%;background:{kleur}"></div></div>',
                        unsafe_allow_html=True,
                    )
                    if s["score"] < 50:
                        lage_kt.append(s)

    punten = []
    if vg < 0.5:
        punten.append("⚠️ Lage voortgang — doorvragen naar oorzaak")
    if bsa_pct < 0.7:
        punten.append("⚠️ BSA-risico — aanwezigheid bespreken")
    if afwn > 8:
        punten.append("⚠️ Hoge ongeoorloofde afwezigheid")
    for kt in lage_kt:
        punten.append(f"📉 Lage score: {kt['naam']}")

    if punten:
        with st.container(border=True):
            st.markdown("**💡 Bespreekpunten**")
            for punt in punten:
                st.caption(punt)

with col_chat:
    tab_chat, tab_oer = st.tabs(["💬 OER-assistent", "📄 Volledig OER"])

    with tab_chat:
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        if "oer_systeem" not in st.session_state:
            # Laad OER eenmalig per sessie
            oer_tekst = ""
            if oer:
                pad = Path(oer["bestandspad"])
                if not pad.is_absolute():
                    OEREN_PAD = Path(os.environ.get("OEREN_PAD", "oeren")).resolve()
                    pad = OEREN_PAD.parent / pad
                oer_tekst = laad_oer_tekst(pad)
            st.session_state.oer_systeem = (
                bouw_systeem(oer_tekst, opleiding, instelling) if oer_tekst else ""
            )

        for bericht in st.session_state.chat_history:
            if bericht["role"] == "user":
                st.markdown(
                    f'<div class="chat-vraag">💬 {html.escape(bericht["content"])}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="chat-antwoord">\n\n{bericht["content"]}\n\n</div>',
                    unsafe_allow_html=True,
                )

        vraag = st.chat_input(f"Stel een vraag over {student['naam']}'s OER…")
        if vraag:
            st.markdown(
                f'<div class="chat-vraag">💬 {html.escape(vraag)}</div>',
                unsafe_allow_html=True,
            )

            if not st.session_state.oer_systeem:
                st.info(LAGE_RELEVANTIE_BERICHT)
                antwoord = LAGE_RELEVANTIE_BERICHT
            else:
                berichten = bouw_berichten(st.session_state.chat_history, vraag)
                antwoord = LAGE_RELEVANTIE_BERICHT
                try:
                    placeholder = st.empty()
                    antwoord = ""
                    for fragment in genereer_antwoord(
                        ai_client(), st.session_state.oer_systeem, berichten
                    ):
                        antwoord += fragment
                        placeholder.markdown(
                            f'<div class="chat-antwoord">\n\n{antwoord}\n\n</div>',
                            unsafe_allow_html=True,
                        )
                except Exception as e:
                    st.error(f"Er ging iets mis bij het ophalen van een antwoord: {e}")

            st.session_state.chat_history.extend(
                [
                    {"role": "user", "content": vraag},
                    {"role": "assistant", "content": antwoord},
                ]
            )
            if len(st.session_state.chat_history) > MAX_GESCHIEDENIS:
                st.session_state.chat_history = st.session_state.chat_history[-MAX_GESCHIEDENIS:]

    with tab_oer:
        if not oer:
            st.warning("Geen OER gekoppeld aan deze student.")
        else:
            OEREN_PAD = Path(os.environ.get("OEREN_PAD", "oeren")).resolve()
            pad = Path(oer["bestandspad"])
            if not pad.is_absolute():
                pad = OEREN_PAD.parent / pad
            pad = pad.resolve()
            if not pad.is_relative_to(OEREN_PAD):
                st.error("Ongeldig OER-bestandspad.")
                st.stop()

            st.caption(f"Crebo {oer['crebo']} · {oer['leerweg']} · Cohort {oer['cohort']}")

            if not pad.exists():
                st.warning(f"OER-bestand niet gevonden op: {pad}")
            elif pad.suffix.lower() == ".pdf":
                with open(pad, "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(
                    label="⬇️ Download OER als PDF",
                    data=pdf_bytes,
                    file_name=pad.name,
                    mime="application/pdf",
                )
                b64 = base64.b64encode(pdf_bytes).decode()
                st.markdown(
                    f'<iframe src="data:application/pdf;base64,{b64}" '
                    f'width="100%" height="800px"></iframe>',
                    unsafe_allow_html=True,
                )
            elif pad.suffix.lower() in {".html", ".htm"}:
                st.text_area("OER-inhoud", extraheer_tekst_html(pad), height=600)
            elif pad.suffix.lower() == ".md":
                st.markdown(pad.read_text(encoding="utf-8"))
            else:
                st.warning(f"Bestandstype '{pad.suffix}' wordt niet ondersteund.")

render_footer()
