"""Student: hybride OER-chat met doorvraagmogelijkheid."""

import html
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="OER-assistent", page_icon="💬", layout="wide")

from validatie_samenwijzer._ai import _client as ai_client  # noqa: E402
from validatie_samenwijzer._openai import _client as openai_client  # noqa: E402
from validatie_samenwijzer.auth import vereist_student  # noqa: E402
from validatie_samenwijzer.chat import (  # noqa: E402
    LAGE_RELEVANTIE_BERICHT,
    MIN_RELEVANTE_CHUNKS,
    bouw_berichten,
    bouw_berichten_volledig,
    embed_vraag,
    genereer_antwoord,
    laad_oer_tekst,
)
from validatie_samenwijzer.styles import CSS, render_footer, render_nav  # noqa: E402
from validatie_samenwijzer.vector_store import get_client, get_collection, zoek_chunks  # noqa: E402

st.markdown(CSS, unsafe_allow_html=True)
vereist_student()
render_nav()

CHROMA_PATH = Path(os.environ.get("CHROMA_PATH", "data/chroma"))
MAX_GESCHIEDENIS = 20  # 10 uitwisselingen


@st.cache_resource
def _collection():
    client = get_client(CHROMA_PATH)
    return get_collection(client)


opleiding = st.session_state.get("opleiding", "")
instelling = st.session_state.get("instelling", "")
oer_id = st.session_state.get("oer_id")
bestandspad = st.session_state.get("bestandspad", "")

st.subheader(f"💬 OER-assistent — {opleiding}")
st.caption(f"{instelling} · Jouw vragen, beantwoord vanuit jouw OER")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "chat_bronnen" not in st.session_state:
    st.session_state.chat_bronnen = []

assistant_idx = 0
for bericht in st.session_state.chat_history:
    if bericht["role"] == "user":
        vraag_tekst = (
            bericht["content"].split("Vraag:")[-1].strip()
            if "Vraag:" in bericht["content"]
            else bericht["content"]
        )
        st.markdown(
            f'<div class="chat-vraag">💬 {html.escape(vraag_tekst)}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="chat-antwoord">{bericht["content"]}</div>',
            unsafe_allow_html=True,
        )
        if assistant_idx < len(st.session_state.chat_bronnen):
            bronnen = st.session_state.chat_bronnen[assistant_idx]
            if bronnen:
                cols = st.columns(min(len(bronnen), 2))
                for j, bron in enumerate(bronnen):
                    with cols[j % 2]:
                        pagina = bron["metadata"].get("pagina", "?")
                        st.markdown(
                            f'<div class="bron-kaartje">📄 <strong>Pagina {pagina}'
                            f"</strong><br>"
                            f"<em>{bron['tekst'][:200]}…</em></div>",
                            unsafe_allow_html=True,
                        )
        assistant_idx += 1

vraag = st.chat_input("Stel een vraag over jouw OER…")
if vraag and oer_id:
    embedding = embed_vraag(openai_client(), vraag)

    # Strikte zoektocht (drempelwaarde 0.7, 5 chunks)
    chunks = zoek_chunks(_collection(), embedding, oer_ids=[oer_id])

    # Bredere zoektocht als te weinig resultaten
    if len(chunks) < MIN_RELEVANTE_CHUNKS:
        chunks_breed = zoek_chunks(
            _collection(), embedding, oer_ids=[oer_id], n=15, drempelwaarde=0.85
        )
        if len(chunks_breed) >= MIN_RELEVANTE_CHUNKS:
            chunks = chunks_breed

    st.markdown(
        f'<div class="chat-vraag">💬 {html.escape(vraag)}</div>',
        unsafe_allow_html=True,
    )

    if len(chunks) >= MIN_RELEVANTE_CHUNKS:
        berichten = bouw_berichten(
            chat_history=st.session_state.chat_history,
            chunks=chunks,
            vraag=vraag,
            opleiding=opleiding,
            instelling=instelling,
        )
        with st.spinner("Even zoeken in jouw OER…"):
            antwoord = st.write_stream(genereer_antwoord(ai_client(), berichten))

        cols = st.columns(min(len(chunks), 2))
        for j, bron in enumerate(chunks):
            with cols[j % 2]:
                pagina = bron["metadata"].get("pagina", "?")
                st.markdown(
                    f'<div class="bron-kaartje">📄 <strong>Pagina {pagina}</strong><br>'
                    f"<em>{bron['tekst'][:200]}…</em></div>",
                    unsafe_allow_html=True,
                )
    else:
        oer_tekst = laad_oer_tekst(Path(bestandspad)) if bestandspad else ""
        if oer_tekst:
            st.caption("📖 Gezocht in de volledige OER")
            berichten = bouw_berichten_volledig(
                chat_history=st.session_state.chat_history,
                oer_tekst=oer_tekst,
                vraag=vraag,
                opleiding=opleiding,
                instelling=instelling,
            )
            with st.spinner("Even zoeken in jouw OER…"):
                antwoord = st.write_stream(
                    genereer_antwoord(ai_client(), berichten, max_tokens=4096)
                )
        else:
            antwoord = LAGE_RELEVANTIE_BERICHT
            st.info(antwoord)

    st.session_state.chat_history.extend(
        [
            {"role": "user", "content": vraag},
            {"role": "assistant", "content": antwoord},
        ]
    )
    st.session_state.chat_bronnen.append(chunks)
    if len(st.session_state.chat_history) > MAX_GESCHIEDENIS:
        st.session_state.chat_history = st.session_state.chat_history[-MAX_GESCHIEDENIS:]
        st.session_state.chat_bronnen = st.session_state.chat_bronnen[-(MAX_GESCHIEDENIS // 2) :]

render_footer()
