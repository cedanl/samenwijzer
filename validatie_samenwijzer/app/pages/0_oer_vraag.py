"""Publieke OER-vraag — conversationeel, zonder inlogvereiste."""

import base64
import html
import logging
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

st.set_page_config(page_title="OER-vraag — Samenwijzer", page_icon="📚", layout="wide")

from validatie_samenwijzer._ai import APITimeoutError  # noqa: E402
from validatie_samenwijzer._ai import _client as ai_client  # noqa: E402
from validatie_samenwijzer._db import get_conn  # noqa: E402
from validatie_samenwijzer.chat import (  # noqa: E402
    LAGE_RELEVANTIE_BERICHT,
    bouw_berichten,
    bouw_gecombineerd_systeem,
    genereer_antwoord,
    genereer_intake_antwoord,
    identificeer_oer_kandidaten,
    laad_oer_tekst,
)
from validatie_samenwijzer.db import get_alle_oers_met_instelling  # noqa: E402
from validatie_samenwijzer.ingest import extraheer_tekst_html  # noqa: E402
from validatie_samenwijzer.styles import CSS, render_footer  # noqa: E402

st.markdown(CSS, unsafe_allow_html=True)

MAX_GESCHIEDENIS = 20
MAX_OER_SELECTIE = 3  # max aantal OERs tegelijk
MAX_KANDIDATEN = 10  # boven dit aantal → intake in plaats van dropdown

# ── Session state ──────────────────────────────────────────────────────────────
_DEFAULTS: dict = {
    "pub_chat_history": [],
    "pub_oer_systeem": None,
    "pub_oer_labels": [],
    "pub_oer_paden": [],
    "pub_kandidaten": [],
    "pub_wachtende_vraag": None,
}
for _sleutel, _waarde in _DEFAULTS.items():
    if _sleutel not in st.session_state:
        st.session_state[_sleutel] = _waarde


def _reset() -> None:
    for sleutel, waarde in _DEFAULTS.items():
        st.session_state[sleutel] = waarde if not isinstance(waarde, list) else []


def _render_oer_bestand(pad: Path) -> None:
    """Render een OER-bestand inline (PDF iframe + download, of tekst-fallback)."""
    if not pad.exists():
        st.warning(f"OER-bestand niet gevonden op: {pad}")
        return

    suffix = pad.suffix.lower()
    if suffix == ".pdf":
        pdf_bytes = pad.read_bytes()
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
    elif suffix in {".html", ".htm"}:
        st.text_area("OER-inhoud", extraheer_tekst_html(pad), height=800)
    elif suffix == ".md":
        st.markdown(pad.read_text(encoding="utf-8"))
    else:
        st.warning(f"Bestandstype '{suffix}' wordt niet ondersteund.")


# ── Codex-header ───────────────────────────────────────────────────────────────
hdr_l, hdr_r = st.columns([1, 7])
with hdr_l:
    st.markdown('<div class="oer-mark">§</div>', unsafe_allow_html=True)
with hdr_r:
    st.markdown(
        '<div class="oer-overtitel">Onderwijs- en Examenregeling</div>'
        '<h1 style="margin:0">OER-vraag</h1>'
        '<div class="oer-ondertitel">een juridisch document, helder uitgelegd</div>',
        unsafe_allow_html=True,
    )

st.markdown('<div class="oer-ornament">⁂</div>', unsafe_allow_html=True)

if st.session_state.pub_oer_labels:
    labels_str = " · ".join(st.session_state.pub_oer_labels)
    col1, col2 = st.columns([8, 2])
    with col1:
        st.markdown(
            '<div class="oer-overtitel">geraadpleegd</div>'
            f'<div class="oer-meta">{labels_str}</div>',
            unsafe_allow_html=True,
        )
    with col2:
        if st.button("Nieuw gesprek"):
            _reset()
            st.rerun()
else:
    st.markdown(
        '<div class="oer-intro" style="margin-bottom:1.2rem">'
        "Stel je vraag. Vermeld instelling, opleiding, leerweg (BOL/BBL) en cohortjaar — "
        "of laat de assistent ernaar vragen. Je kunt meerdere OERs tegelijk bevragen."
        "</div>",
        unsafe_allow_html=True,
    )

# ── PDF-bekijkknoppen per geladen OER ──────────────────────────────────────────
if st.session_state.pub_oer_paden:
    knop_cols = st.columns(len(st.session_state.pub_oer_paden))
    for i, col in enumerate(knop_cols):
        with col:
            if st.button(f"📄 Bekijk OER {i + 1}", key=f"toon_oer_{i}",
                         use_container_width=True):
                st.session_state[f"pub_toon_oer_{i}"] = (
                    not st.session_state.get(f"pub_toon_oer_{i}", False)
                )
    for i, pad in enumerate(st.session_state.pub_oer_paden):
        if st.session_state.get(f"pub_toon_oer_{i}"):
            with st.expander(
                f"📄 {st.session_state.pub_oer_labels[i]}", expanded=True
            ):
                _render_oer_bestand(pad)

# ── Chatgeschiedenis ───────────────────────────────────────────────────────────
for bericht in st.session_state.pub_chat_history:
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

# ── Keuzelijst bij meerdere kandidaten ────────────────────────────────────────
if st.session_state.pub_kandidaten:
    kandidaten = st.session_state.pub_kandidaten

    def _label(k: dict) -> str:
        opl = k["opleiding"][:40]
        return f"{k['display_naam']} · {opl} · {k['leerweg']} {k['cohort']}"

    opties = {_label(k): k for k in kandidaten}
    geselecteerd = st.multiselect(
        f"Meerdere OERs gevonden — kies er één of meer (max {MAX_OER_SELECTIE}):",
        list(opties.keys()),
        max_selections=MAX_OER_SELECTIE,
    )

    if st.button("✅ Bevestig keuze", type="primary", disabled=not geselecteerd):
        oer_items = []
        labels = []
        paden = []
        for lbl in geselecteerd:
            k = opties[lbl]
            pad = Path(k["bestandspad"])
            tekst = laad_oer_tekst(pad)
            if tekst:
                oer_items.append(
                    {
                        "tekst": tekst,
                        "opleiding": k["opleiding"],
                        "display_naam": k["display_naam"],
                        "leerweg": k["leerweg"],
                        "cohort": k["cohort"],
                    }
                )
                labels.append(_label(k))
                paden.append(pad)

        if not oer_items:
            st.error("Geen van de geselecteerde OER-bestanden kon worden geladen.")
        else:
            st.session_state.pub_oer_systeem = bouw_gecombineerd_systeem(oer_items)
            st.session_state.pub_oer_labels = labels
            st.session_state.pub_oer_paden = paden
            st.session_state.pub_kandidaten = []

            if st.session_state.pub_wachtende_vraag:
                st.session_state.pub_wachtende_vraag = None
                berichten = list(st.session_state.pub_chat_history)
                placeholder = st.empty()
                antwoord = ""
                try:
                    for fragment in genereer_antwoord(
                        ai_client(), st.session_state.pub_oer_systeem, berichten
                    ):
                        antwoord += fragment
                        placeholder.markdown(
                            f'<div class="chat-antwoord">\n\n{antwoord}\n\n</div>',
                            unsafe_allow_html=True,
                        )
                except APITimeoutError:
                    st.error("De AI-service reageert niet. Probeer het over een moment opnieuw.")
                    antwoord = ""
                except Exception as e:
                    log.exception("OER-antwoord (publiek, na keuze) mislukt")
                    st.error(f"Er ging iets mis: {e}")
                    antwoord = ""
                st.session_state.pub_chat_history.append({"role": "assistant", "content": antwoord})
            st.rerun()

    render_footer()
    st.stop()

# ── Chat input ─────────────────────────────────────────────────────────────────
vraag = st.chat_input("Stel een vraag over een OER…")

if not vraag:
    render_footer()
    st.stop()

vraag = vraag.strip()
st.markdown(
    f'<div class="chat-vraag">💬 {html.escape(vraag)}</div>',
    unsafe_allow_html=True,
)


def _stream_antwoord(systeem: str, berichten: list[dict]) -> str:
    placeholder = st.empty()
    antwoord = ""
    try:
        for fragment in genereer_antwoord(ai_client(), systeem, berichten):
            antwoord += fragment
            placeholder.markdown(
                f'<div class="chat-antwoord">\n\n{antwoord}\n\n</div>',
                unsafe_allow_html=True,
            )
    except APITimeoutError:
        st.error("De AI-service reageert niet. Probeer het over een moment opnieuw.")
    except Exception as e:
        log.exception("OER-antwoord (publiek, stream) mislukt")
        st.error(f"Er ging iets mis: {e}")
    return antwoord


# ── OER al geladen: antwoord direct ───────────────────────────────────────────
if st.session_state.pub_oer_systeem:
    berichten = bouw_berichten(st.session_state.pub_chat_history, vraag)
    antwoord = _stream_antwoord(st.session_state.pub_oer_systeem, berichten)
    st.session_state.pub_chat_history.extend(
        [
            {"role": "user", "content": vraag},
            {"role": "assistant", "content": antwoord},
        ]
    )
    if len(st.session_state.pub_chat_history) > MAX_GESCHIEDENIS:
        st.session_state.pub_chat_history = st.session_state.pub_chat_history[-MAX_GESCHIEDENIS:]
    render_footer()
    st.stop()

# ── Probeer OER te identificeren ───────────────────────────────────────────────
alle_oers = get_alle_oers_met_instelling(get_conn())
instellingen = sorted({oer["display_naam"] for oer in alle_oers})

gebruiker_tekst = (
    " ".join(b["content"] for b in st.session_state.pub_chat_history if b["role"] == "user")
    + " "
    + vraag
)
kandidaten = identificeer_oer_kandidaten(list(alle_oers), gebruiker_tekst, min_score=5)

if len(kandidaten) == 1:
    k = kandidaten[0]
    pad = Path(k["bestandspad"])
    tekst = laad_oer_tekst(pad)
    if tekst:
        st.session_state.pub_oer_systeem = bouw_gecombineerd_systeem(
            [
                {
                    "tekst": tekst,
                    "opleiding": k["opleiding"],
                    "display_naam": k["display_naam"],
                    "leerweg": k["leerweg"],
                    "cohort": k["cohort"],
                }
            ]
        )
        st.session_state.pub_oer_labels = [
            f"{k['display_naam']} · {k['opleiding'][:40]} · {k['leerweg']} {k['cohort']}"
        ]
        st.session_state.pub_oer_paden = [pad]
        berichten = bouw_berichten(st.session_state.pub_chat_history, vraag)
        antwoord = _stream_antwoord(st.session_state.pub_oer_systeem, berichten)
    else:
        antwoord = LAGE_RELEVANTIE_BERICHT
        st.info(antwoord)

elif 1 < len(kandidaten) <= MAX_KANDIDATEN:
    st.session_state.pub_kandidaten = kandidaten
    st.session_state.pub_wachtende_vraag = vraag
    st.session_state.pub_chat_history.append({"role": "user", "content": vraag})
    st.rerun()

elif len(kandidaten) > MAX_KANDIDATEN:
    # Verfijn naar de hoogst scorende OERs; alleen als dat ≤ MAX_KANDIDATEN zijn → dropdown
    top_score = kandidaten[0]["_score"]
    top_tier = [k for k in kandidaten if k["_score"] >= top_score]
    if len(top_tier) <= MAX_KANDIDATEN:
        st.session_state.pub_kandidaten = top_tier
        st.session_state.pub_wachtende_vraag = vraag
        st.session_state.pub_chat_history.append({"role": "user", "content": vraag})
        st.rerun()
    else:
        # Zelfs in top tier te vaag: vraag om opleidingsnaam zonder Claude-call
        antwoord = (
            f"Er zijn {len(top_tier)} OERs gevonden met de hoogste relevantie. "
            "Geef de **opleidingsnaam** of het **crebo-nummer** om preciezer te zoeken. "
            f"Beschikbare instellingen: {', '.join(instellingen)}."
        )
        st.markdown(
            f'<div class="chat-antwoord">\n\n{antwoord}\n\n</div>',
            unsafe_allow_html=True,
        )

else:
    # Geen matches: conversationele intake via Claude
    berichten = bouw_berichten(st.session_state.pub_chat_history, vraag)
    placeholder = st.empty()
    antwoord = ""
    try:
        for fragment in genereer_intake_antwoord(ai_client(), berichten, instellingen):
            antwoord += fragment
            placeholder.markdown(
                f'<div class="chat-antwoord">\n\n{antwoord}\n\n</div>',
                unsafe_allow_html=True,
            )
    except APITimeoutError:
        st.error("De AI-service reageert niet. Probeer het over een moment opnieuw.")
        antwoord = ""
    except Exception as e:
        log.exception("OER-intake-antwoord mislukt")
        st.error(f"Er ging iets mis: {e}")
        antwoord = ""

st.session_state.pub_chat_history.extend(
    [
        {"role": "user", "content": vraag},
        {"role": "assistant", "content": antwoord},
    ]
)
if len(st.session_state.pub_chat_history) > MAX_GESCHIEDENIS:
    st.session_state.pub_chat_history = st.session_state.pub_chat_history[-MAX_GESCHIEDENIS:]

render_footer()
