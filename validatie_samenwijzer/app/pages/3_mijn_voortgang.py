"""Student: kerntaakscores, BSA en aanwezigheid."""

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
    GROEN,
    ORANJE,
    ROOD,
    render_footer,
    render_nav,
    render_student_info,
)

st.markdown(CSS, unsafe_allow_html=True)
vereist_student()
render_nav()
render_student_info()


studentnummer = st.session_state.get("studentnummer")
student = get_student_by_studentnummer(get_conn(), studentnummer)

st.subheader("📊 Mijn voortgang")

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
    kleur = GROEN if vg >= 0.7 else (ORANJE if vg >= 0.5 else ROOD)
    st.metric("Voortgang", f"{vg * 100:.0f}%")
    st.markdown(
        f'<div class="progress-bar-bg"><div class="progress-bar-fill" '
        f'style="width:{vg * 100:.0f}%;background:{kleur}"></div></div>',
        unsafe_allow_html=True,
    )
with col2:
    st.metric("BSA behaald", f"{bsa_b:.0f} / {bsa_v:.0f} uur", f"{bsa_pct * 100:.0f}%")
with col3:
    st.metric("Ongeoorl. afwezigheid", f"{afwn:.0f} uur")

st.markdown("---")
st.subheader("Kerntaken en werkprocessen")

scores = get_kerntaak_scores_by_student_id(get_conn(), student["id"])
if not scores:
    st.info("Nog geen scores beschikbaar.")
else:
    kerntaken = [s for s in scores if s["type"] == "kerntaak"]
    werkprocessen = [s for s in scores if s["type"] == "werkproces"]

    if kerntaken:
        st.markdown("**Kerntaken**")
        for kt in kerntaken:
            pct = kt["score"] / 100
            kleur = GROEN if pct >= 0.7 else (ORANJE if pct >= 0.5 else ROOD)
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"_{kt['naam']}_")
                st.markdown(
                    f'<div class="progress-bar-bg"><div class="progress-bar-fill" '
                    f'style="width:{kt["score"]:.0f}%;background:{kleur}"></div></div>',
                    unsafe_allow_html=True,
                )
            with col_b:
                st.markdown(f"**{kt['score']:.0f}**")

    if werkprocessen:
        with st.expander("Werkprocessen"):
            for wp in werkprocessen:
                pct = wp["score"] / 100
                kleur = GROEN if pct >= 0.7 else (ORANJE if pct >= 0.5 else ROOD)
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.caption(wp["naam"])
                    st.markdown(
                        f'<div class="progress-bar-bg"><div class="progress-bar-fill" '
                        f'style="width:{wp["score"]:.0f}%;background:{kleur}"></div></div>',
                        unsafe_allow_html=True,
                    )
                with col_b:
                    st.caption(f"{wp['score']:.0f}")

render_footer()
