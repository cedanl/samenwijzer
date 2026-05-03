"""Student: OER-chat met volledige documentcontext."""

import html
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="OER-assistent", page_icon="💬", layout="wide")

from validatie_samenwijzer._ai import _client as ai_client  # noqa: E402
from validatie_samenwijzer.auth import vereist_student  # noqa: E402
from validatie_samenwijzer.chat import (  # noqa: E402
    LAGE_RELEVANTIE_BERICHT,
    bouw_berichten,
    bouw_systeem,
    genereer_antwoord,
    laad_oer_tekst,
)
from validatie_samenwijzer.styles import (  # noqa: E402
    CSS,
    render_footer,
    render_nav,
    render_student_info,
)

st.markdown(CSS, unsafe_allow_html=True)
vereist_student()
render_nav()
render_student_info()

MAX_GESCHIEDENIS = 20  # 10 uitwisselingen

opleiding = st.session_state.get("opleiding", "")
instelling = st.session_state.get("instelling", "")
bestandspad = st.session_state.get("bestandspad", "")

st.subheader(f"💬 OER-assistent — {opleiding}")
st.caption(f"{instelling} · Jouw vragen, beantwoord vanuit jouw OER")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "oer_systeem" not in st.session_state:
    # Laad OER eenmalig per sessie
    oer_tekst = laad_oer_tekst(Path(bestandspad)) if bestandspad else ""
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
            f'<div class="chat-antwoord">{bericht["content"]}</div>',
            unsafe_allow_html=True,
        )

vraag = st.chat_input("Stel een vraag over jouw OER…")
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
            for fragment in genereer_antwoord(ai_client(), st.session_state.oer_systeem, berichten):
                antwoord += fragment
                placeholder.markdown(
                    f'<div class="chat-antwoord">{html.escape(antwoord)}</div>',
                    unsafe_allow_html=True,
                )
        except Exception as e:
            st.error(f"Er ging iets mis: {e}")

    st.session_state.chat_history.extend(
        [
            {"role": "user", "content": vraag},
            {"role": "assistant", "content": antwoord},
        ]
    )
    if len(st.session_state.chat_history) > MAX_GESCHIEDENIS:
        st.session_state.chat_history = st.session_state.chat_history[-MAX_GESCHIEDENIS:]

render_footer()
