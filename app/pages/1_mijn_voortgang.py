"""Pagina: Mijn voortgang — studentweergave."""

import streamlit as st

from samenwijzer.analyze import (
    badge,
    cohort_positie,
    get_student,
    kerntaak_scores,
    leerpad_niveau,
    werkproces_scores,
    zwakste_kerntaak,
    zwakste_werkproces,
)
from samenwijzer.styles import CSS, render_footer
from samenwijzer.visualize import (
    bsa_staaf,
    kerntaak_grafiek,
    voortgang_gauge,
    werkproces_grafiek,
)

st.set_page_config(page_title="Mijn voortgang — Samenwijzer", page_icon="📊", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
st.title("📊 Mijn voortgang")

if "df" not in st.session_state or "studentnummer" not in st.session_state:
    st.warning("Ga eerst naar de [startpagina](/) om je naam te kiezen.")
    st.stop()

df = st.session_state["df"]
studentnummer = st.session_state["studentnummer"]
student = get_student(df, studentnummer)

# ── Header ────────────────────────────────────────────────────────────────────
col_info, col_meta = st.columns([2, 1])
with col_info:
    st.subheader(student["naam"])
    st.caption(
        f"{student['opleiding']} · Niveau {student['niveau']} · "
        f"{student['leerweg']} · Cohort {student['cohort']}"
    )
    st.caption(f"Mentor: {student['mentor']}")
    niveau = leerpad_niveau(student)
    niveau_kleuren = {
        "Starter": "orange",
        "Onderweg": "blue",
        "Gevorderde": "green",
        "Expert": "violet",
    }
    kleur = niveau_kleuren[niveau]
    st.markdown(f"**Leerpad:** :{kleur}[**{niveau}**]")

with col_meta:
    st.markdown(f"#### {badge(student)}")
    if student["risico"]:
        st.error("⚠️ Aandacht nodig — neem contact op met je mentor.")
    else:
        st.success("✅ Je bent op schema.")

st.divider()

# ── Voortgang en BSA ──────────────────────────────────────────────────────────
col_v, col_b = st.columns(2)

with col_v:
    st.subheader("Studievoortgang")
    pct = int(student["voortgang"] * 100)
    st.metric("Voortgang", f"{pct}%")
    st.altair_chart(voortgang_gauge(student["voortgang"]), use_container_width=True)

with col_b:
    st.subheader("Studiepunten (BSA)")
    st.metric(
        "Behaald",
        f"{int(student['bsa_behaald'])} / {int(student['bsa_vereist'])}",
        delta=f"{int(student['bsa_behaald'] - student['bsa_vereist'])} t.o.v. norm"
        if student["bsa_behaald"] < student["bsa_vereist"]
        else "Op norm",
    )
    st.altair_chart(
        bsa_staaf(student["bsa_behaald"], student["bsa_vereist"]),
        use_container_width=True,
    )

st.divider()

# ── Kerntaken ─────────────────────────────────────────────────────────────────
st.subheader("Kerntaken")
kt_df = kerntaak_scores(df, studentnummer)
if not kt_df.empty:
    st.altair_chart(kerntaak_grafiek(kt_df), use_container_width=True)
else:
    st.info("Geen kerntaakscores beschikbaar.")

# ── Werkprocessen ─────────────────────────────────────────────────────────────
st.subheader("Werkprocessen")
wp_df = werkproces_scores(df, studentnummer)
if not wp_df.empty:
    st.altair_chart(werkproces_grafiek(wp_df), use_container_width=True)
else:
    st.info("Geen werkprocesscores beschikbaar.")

st.divider()

# ── Aandachtspunten ───────────────────────────────────────────────────────────
st.subheader("Aandachtspunten")
zkt = zwakste_kerntaak(df, studentnummer)
zwp = zwakste_werkproces(df, studentnummer)

col_zkt, col_zwp = st.columns(2)
with col_zkt:
    if zkt:
        label, score = zkt
        st.warning(f"**Zwakste kerntaak: {label}** ({score:.0f} punten)")
        st.caption(
            "Dit is het onderdeel waar je de meeste winst kunt behalen. "
            "Bespreek dit met je mentor of gebruik de AI Leercoach."
        )
with col_zwp:
    if zwp:
        label, score = zwp
        st.warning(f"**Zwakste werkproces: {label}** ({score:.0f} punten)")
        st.caption("Focus extra op dit werkproces bij je volgende stage of opdracht.")

st.divider()

# ── Positie in cohort (anoniem) ───────────────────────────────────────────────
st.subheader("Jouw positie in het cohort")
positie_info = cohort_positie(df, studentnummer)
pos = positie_info["positie"]
totaal = positie_info["totaal"]
cohort = positie_info["cohort"]

col_pos, col_bar = st.columns([1, 2])
with col_pos:
    st.metric(
        "Rangpositie", f"{pos} van {totaal}", help=f"Cohort {cohort}, gesorteerd op voortgang"
    )
with col_bar:
    voortgang_pct = int(student["voortgang"] * 100)
    gem_voortgang_pct = int(df[df["cohort"] == cohort]["voortgang"].mean() * 100)
    delta = f"{voortgang_pct - gem_voortgang_pct}% t.o.v. cohortgemiddelde"
    st.metric("Jouw voortgang", f"{voortgang_pct}%", delta=delta)

render_footer()
