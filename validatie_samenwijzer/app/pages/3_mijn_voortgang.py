"""Student: kerntaakscores, BSA en aanwezigheid."""

from typing import Any

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Mijn voortgang", page_icon="📊", layout="wide")

from validatie_samenwijzer._db import get_conn  # noqa: E402
from validatie_samenwijzer.auth import vereist_student  # noqa: E402
from validatie_samenwijzer.db import (  # noqa: E402
    get_kerntaak_scores_by_student_id,
    get_student_by_studentnummer,
)
from validatie_samenwijzer.styles import (  # noqa: E402
    CSS,
    bepaal_kleur,
    render_footer,
    render_nav,
    render_progress_bar,
    render_student_info,
)

st.markdown(CSS, unsafe_allow_html=True)
vereist_student()
render_nav()
render_student_info()


studentnummer = st.session_state.get("studentnummer")
student = get_student_by_studentnummer(get_conn(), studentnummer)

st.subheader("Mijn voortgang")

if not student:
    st.error("Studentprofiel niet gevonden.")
    st.stop()

vg = student["voortgang"] or 0.0
bsa_b = student["bsa_behaald"] or 0.0
bsa_v = student["bsa_vereist"] or 60.0
bsa_pct = min(bsa_b / bsa_v, 1.0) if bsa_v else 0.0
afwn = student["absence_unauthorized"] or 0.0

col1, col2, col3 = st.columns(3)
with col1:
    kleur = bepaal_kleur(vg, schaal="0-1")
    st.metric("Voortgang", f"{vg * 100:.0f}%")
    st.markdown(render_progress_bar(vg, kleur, schaal="0-1"), unsafe_allow_html=True)
with col2:
    st.metric("BSA behaald", f"{bsa_b:.0f} / {bsa_v:.0f} uur", f"{bsa_pct * 100:.0f}%")
with col3:
    st.metric("Ongeoorl. afwezigheid", f"{afwn:.0f} uur")

st.markdown("---")
st.subheader("Kerntaken en werkprocessen")

scores = get_kerntaak_scores_by_student_id(get_conn(), student["id"])


def _dedup_op_naam(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Veiligheidsnet tegen duplicate kerntaak-namen — UNIQUE-constraint op DB
    voorkomt het structureel, maar deze guard blijft expliciet."""
    gezien: set[str] = set()
    uniek: list = []
    for s in items:
        if s["naam"] in gezien:
            continue
        gezien.add(s["naam"])
        uniek.append(s)
    return uniek


def _render_kerntaak(kt: dict[str, Any]) -> None:
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.markdown(f"**{kt['naam']}**")
        st.markdown(
            render_progress_bar(kt["score"], bepaal_kleur(kt["score"])),
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown(f"**{kt['score']:.0f}**")


def _render_werkproces(wp: dict[str, Any]) -> None:
    col_a, col_b = st.columns([3, 1])
    with col_a:
        bar = render_progress_bar(wp["score"], bepaal_kleur(wp["score"]))
        st.markdown(
            f'<div class="werkproces-row">'
            f'<span class="werkproces-label">↳ {wp["naam"]}</span>'
            f"{bar}"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_b:
        st.caption(f"{wp['score']:.0f}")


if not scores:
    st.info("Nog geen scores beschikbaar.")
else:
    kerntaken = _dedup_op_naam([s for s in scores if s["type"] == "kerntaak"])
    werkprocessen = _dedup_op_naam([s for s in scores if s["type"] == "werkproces"])

    overige_wp = list(werkprocessen)
    for kt in kerntaken:
        _render_kerntaak(kt)
        kt_code = kt["code"]
        kinderen = [wp for wp in overige_wp if wp["code"].startswith(f"{kt_code}-")]
        for wp in kinderen:
            _render_werkproces(wp)
            overige_wp.remove(wp)
        st.markdown("")

    if overige_wp:
        st.markdown("**Overige werkprocessen**")
        for wp in overige_wp:
            _render_werkproces(wp)

render_footer()
