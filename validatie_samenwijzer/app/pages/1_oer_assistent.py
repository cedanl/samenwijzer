"""Student: vraag-en-antwoord met volledige documentcontext (de OER)."""

import html
import logging

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

st.set_page_config(page_title="Stel een vraag · De digitale gids", page_icon="💬", layout="wide")

from validatie_samenwijzer._ai import APITimeoutError  # noqa: E402
from validatie_samenwijzer._ai import _client as ai_client  # noqa: E402
from validatie_samenwijzer.auth import vereist_student  # noqa: E402
from validatie_samenwijzer.chat import (  # noqa: E402
    LAGE_RELEVANTIE_BERICHT,
    bouw_berichten,
    bouw_systeem,
    genereer_antwoord,
    laad_instelling_bron_tekst,
    laad_kwalificatiedossier_tekst,
    laad_oer_tekst,
    laad_skills_tekst,
    resolve_oer_pad,
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
crebo = st.session_state.get("crebo", "")

st.subheader("💬 Stel je vraag")
st.caption(
    "Antwoord uit je studiegids — mét bron, vindplaats en citaat "
    "(officieel heet die de OER, de onderwijs- en examenregeling)."
)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "oer_systeem" not in st.session_state:
    # Laad OER + instellingsregeling(en) + kwalificatiedossier eenmalig per sessie
    oer_tekst = laad_oer_tekst(resolve_oer_pad(bestandspad)) if bestandspad else ""
    dossier_tekst = laad_kwalificatiedossier_tekst(crebo)
    skills_tekst = laad_skills_tekst(crebo)
    instelling_bronnen = [
        (label, laad_instelling_bron_tekst(resolve_oer_pad(pad)))
        for label, pad in st.session_state.get("instelling_bron_paden", [])
    ]
    st.session_state.oer_systeem = (
        bouw_systeem(
            oer_tekst,
            opleiding,
            instelling,
            dossier_tekst=dossier_tekst,
            crebo=crebo,
            skills_tekst=skills_tekst,
            instelling_bronnen=instelling_bronnen,
        )
        if oer_tekst
        else ""
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

vraag = st.chat_input("Stel een vraag over je opleiding…")
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
                    f'<div class="chat-antwoord">\n\n{antwoord}\n\n</div>',
                    unsafe_allow_html=True,
                )
        except APITimeoutError:
            st.error("De AI-service reageert niet. Probeer het over een moment opnieuw.")
            antwoord = ""
        except Exception:
            log.exception("OER-antwoord (student) mislukt")
            st.error("Er ging iets mis. Probeer het later opnieuw.")
            antwoord = ""

    if antwoord:
        st.session_state.chat_history.extend(
            [
                {"role": "user", "content": vraag},
                {"role": "assistant", "content": antwoord},
            ]
        )
        if len(st.session_state.chat_history) > MAX_GESCHIEDENIS:
            st.session_state.chat_history = st.session_state.chat_history[-MAX_GESCHIEDENIS:]

render_footer()
