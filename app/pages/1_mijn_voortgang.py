"""Pagina: Mijn voortgang — studentweergave."""

import streamlit as st

from samenwijzer.analyze import get_student, kerntaak_scores, werkproces_scores
from samenwijzer.visualize import (
    bsa_staaf,
    kerntaak_grafiek,
    voortgang_gauge,
    werkproces_grafiek,
)

st.set_page_config(page_title="Mijn voortgang — Samenwijzer", page_icon="📊", layout="wide")
st.title("📊 Mijn voortgang")

if "df" not in st.session_state:
    st.warning("Ga eerst naar de startpagina om de data te laden.")
    st.stop()

df = st.session_state["df"]

namen = (
    df.sort_values("naam")[["naam", "studentnummer"]]
    .apply(lambda r: f"{r['naam']} ({r['studentnummer']})", axis=1)
    .tolist()
)
keuze = st.selectbox("Kies je naam", namen)
studentnummer = keuze.split("(")[-1].rstrip(")")

student = get_student(df, studentnummer)

st.divider()

# ── Header ────────────────────────────────────────────────────────────────────
col_info, col_meta = st.columns([2, 1])
with col_info:
    st.subheader(student["naam"])
    st.caption(
        f"{student['opleiding']} · Niveau {student['niveau']} · "
        f"{student['leerweg']} · Cohort {student['cohort']}"
    )
    st.caption(f"Mentor: {student['mentor']}")

with col_meta:
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
