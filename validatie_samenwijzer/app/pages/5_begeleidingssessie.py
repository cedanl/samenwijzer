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
from validatie_samenwijzer._openai import _client as openai_client  # noqa: E402
from validatie_samenwijzer.auth import vereist_mentor  # noqa: E402
from validatie_samenwijzer.chat import (  # noqa: E402
    LAGE_RELEVANTIE_BERICHT,
    bouw_berichten,
    embed_vraag,
    genereer_antwoord,
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
from validatie_samenwijzer.vector_store import (  # noqa: E402
    get_client,
    get_collection,
    zoek_chunks,
)

st.markdown(CSS, unsafe_allow_html=True)
vereist_mentor()
render_nav()

CHROMA_PATH = Path(os.environ.get("CHROMA_PATH", "data/chroma"))
MAX_GESCHIEDENIS = 20  # 10 uitwisselingen


@st.cache_resource
def _collection():
    """Gedeeld ChromaDB-collectie-object; gecached per sessie-lifecycle."""
    return get_collection(get_client(CHROMA_PATH))


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
                    st.markdown(f"<small>{s['naam']}</small>", unsafe_allow_html=True)
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
                    f'<div class="chat-antwoord">{html.escape(bericht["content"])}</div>',
                    unsafe_allow_html=True,
                )
                if assistant_idx < len(st.session_state.chat_bronnen):
                    bronnen = st.session_state.chat_bronnen[assistant_idx]
                    for bron in bronnen:
                        pagina = bron["metadata"].get("pagina", "?")
                        st.markdown(
                            f'<div class="bron-kaartje">📄 p.{pagina} — '
                            f"<em>{bron['tekst'][:150]}…</em></div>",
                            unsafe_allow_html=True,
                        )
                assistant_idx += 1

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
                f'<div class="chat-vraag">💬 {html.escape(vraag)}</div>',
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
            if len(st.session_state.chat_history) > MAX_GESCHIEDENIS:
                st.session_state.chat_history = st.session_state.chat_history[-MAX_GESCHIEDENIS:]
                st.session_state.chat_bronnen = st.session_state.chat_bronnen[
                    -(MAX_GESCHIEDENIS // 2) :
                ]

    with tab_oer:
        if not oer:
            st.warning("Geen OER gekoppeld aan deze student.")
        else:
            OEREN_PAD = Path(os.environ.get("OEREN_PAD", "oeren")).resolve()
            pad = Path(oer["bestandspad"])
            if not pad.is_absolute():
                pad = OEREN_PAD.parent / pad
            pad = pad.resolve()
            if not pad.is_relative_to(OEREN_PAD.parent):
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
            elif pad.suffix.lower() == ".txt":
                tekst = pad.read_text(encoding="utf-8", errors="replace")
                st.download_button(
                    label="⬇️ Download OER als tekstbestand",
                    data=tekst.encode("utf-8"),
                    file_name=pad.name,
                    mime="text/plain",
                )
                st.text_area("OER-inhoud", tekst, height=600)
            else:
                st.warning(f"Bestandstype '{pad.suffix}' wordt niet ondersteund.")

render_footer()
