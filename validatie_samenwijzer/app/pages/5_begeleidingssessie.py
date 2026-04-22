"""Mentor: studentprofiel + OER-assistent naast elkaar."""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Begeleidingssessie", page_icon="🎓", layout="wide")

from validatie_samenwijzer._ai import _client as ai_client  # noqa: E402
from validatie_samenwijzer._openai import _client as openai_client  # noqa: E402
from validatie_samenwijzer.auth import vereist_mentor  # noqa: E402
from validatie_samenwijzer.chat import (  # noqa: E402
    LAGE_RELEVANTIE_BERICHT,
    bouw_berichten,
    embed_vraag,
    genereer_antwoord,
)
from validatie_samenwijzer.db import (  # noqa: E402
    get_connection,
    get_kerntaak_scores_by_student_id,
    init_db,
)
from validatie_samenwijzer.styles import (  # noqa: E402
    CSS,
    GROEN,
    ORANJE,
    ROOD,
    render_footer,
    render_nav,
)
from validatie_samenwijzer.vector_store import (  # noqa: E402
    get_client,
    get_collection,
    zoek_chunks,
)

st.markdown(CSS, unsafe_allow_html=True)
vereist_mentor()
render_nav()

DB_PATH = Path(os.environ.get("DB_PATH", "data/validatie.db"))
CHROMA_PATH = Path(os.environ.get("CHROMA_PATH", "data/chroma"))


@st.cache_resource
def _conn():
    conn = get_connection(DB_PATH)
    init_db(conn)
    return conn


@st.cache_resource
def _collection():
    return get_collection(get_client(CHROMA_PATH))


student = st.session_state.get("actieve_student")
if not student:
    st.warning("Geen student geselecteerd. Ga terug naar 'Mijn studenten'.")
    st.page_link("pages/4_mijn_studenten.py", label="← Mijn studenten")
    st.stop()

oer = (
    _conn()
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

# ── Linkerpaneel: studentprofiel ──────────────────────────────────────────────
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

    scores = get_kerntaak_scores_by_student_id(_conn(), student["id"])
    if scores:
        with st.container(border=True):
            st.markdown("**Kerntaken**")
            for s in scores:
                if s["type"] == "kerntaak":
                    kleur = GROEN if s["score"] >= 70 else (ORANJE if s["score"] >= 50 else ROOD)
                    st.markdown(f"<small>{s['naam']}</small>", unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="progress-bar-bg"><div class="progress-bar-fill" '
                        f'style="width:{s["score"]:.0f}%;background:{kleur}"></div></div>',
                        unsafe_allow_html=True,
                    )

    # Bespreekpuntsuggesties
    punten = []
    if vg < 0.5:
        punten.append("⚠️ Lage voortgang — doorvragen naar oorzaak")
    if bsa_pct < 0.7:
        punten.append("⚠️ BSA-risico — aanwezigheid bespreken")
    if afwn > 8:
        punten.append("⚠️ Hoge ongeoorloofde afwezigheid")
    lage_kt = [s for s in scores if s["type"] == "kerntaak" and s["score"] < 50]
    for kt in lage_kt:
        punten.append(f"📉 Lage score: {kt['naam']}")

    if punten:
        with st.container(border=True):
            st.markdown("**💡 Bespreekpunten**")
            for punt in punten:
                st.caption(punt)

# ── Rechterpaneel: OER-chat ───────────────────────────────────────────────────
with col_chat:
    st.markdown(f"**💬 OER-assistent** — {opleiding}")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "chat_bronnen" not in st.session_state:
        st.session_state.chat_bronnen = []

    for i, bericht in enumerate(st.session_state.chat_history):
        if bericht["role"] == "user":
            vraag_tekst = (
                bericht["content"].split("Vraag:")[-1].strip()
                if "Vraag:" in bericht["content"]
                else bericht["content"]
            )
            st.markdown(
                f'<div class="chat-vraag">💬 {vraag_tekst}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="chat-antwoord">{bericht["content"]}</div>',
                unsafe_allow_html=True,
            )
            bron_idx = i // 2
            if bron_idx < len(st.session_state.chat_bronnen):
                bronnen = st.session_state.chat_bronnen[bron_idx]
                for bron in bronnen:
                    pagina = bron["metadata"].get("pagina", "?")
                    st.markdown(
                        f'<div class="bron-kaartje">📄 p.{pagina} — '
                        f"<em>{bron['tekst'][:150]}…</em></div>",
                        unsafe_allow_html=True,
                    )

    vraag = st.chat_input(f"Stel een vraag over {student['naam']}'s OER…")
    if vraag and oer:
        embedding = embed_vraag(openai_client(), vraag)
        chunks = zoek_chunks(_collection(), embedding, oer_ids=[student["oer_id"]])

        berichten = bouw_berichten(
            chat_history=st.session_state.chat_history,
            chunks=chunks,
            vraag=vraag,
            opleiding=opleiding,
            instelling=instelling,
        )

        st.markdown(
            f'<div class="chat-vraag">💬 {vraag}</div>',
            unsafe_allow_html=True,
        )

        if not chunks:
            antwoord = LAGE_RELEVANTIE_BERICHT
            st.info(antwoord)
        else:
            with st.spinner("Zoeken in OER…"):
                antwoord = st.write_stream(genereer_antwoord(ai_client(), berichten))

            for bron in chunks:
                pagina = bron["metadata"].get("pagina", "?")
                st.markdown(
                    f'<div class="bron-kaartje">📄 p.{pagina} — '
                    f"<em>{bron['tekst'][:150]}…</em></div>",
                    unsafe_allow_html=True,
                )

        st.session_state.chat_history.extend(
            [
                {"role": "user", "content": vraag},
                {"role": "assistant", "content": antwoord},
            ]
        )
        st.session_state.chat_bronnen.append(chunks)

render_footer()
