"""Pagina: Groepsoverzicht — docentweergave."""

import streamlit as st

from samenwijzer.analyze import cohort_gemiddelden, groepsoverzicht
from samenwijzer.visualize import groep_voortgang_grafiek

st.set_page_config(page_title="Groepsoverzicht — Samenwijzer", page_icon="👥", layout="wide")
st.title("👥 Groepsoverzicht")

if "df" not in st.session_state:
    st.warning("Ga eerst naar de startpagina om de data te laden.")
    st.stop()

df = st.session_state["df"]

# ── Filters ───────────────────────────────────────────────────────────────────
with st.expander("Filters", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        opleidingen = ["Alle"] + sorted(df["opleiding"].unique().tolist())
        opleiding = st.selectbox("Opleiding", opleidingen)
    with col2:
        cohorten = ["Alle"] + sorted(df["cohort"].unique().tolist(), reverse=True)
        cohort = st.selectbox("Cohort", cohorten)
    with col3:
        mentoren = ["Alle"] + sorted(df["mentor"].unique().tolist())
        mentor = st.selectbox("Mentor", mentoren)

gefilterd = df.copy()
if opleiding != "Alle":
    gefilterd = gefilterd[gefilterd["opleiding"] == opleiding]
if cohort != "Alle":
    gefilterd = gefilterd[gefilterd["cohort"] == cohort]
if mentor != "Alle":
    gefilterd = gefilterd[gefilterd["mentor"] == mentor]

st.divider()

# ── Overzichtsmetrics ─────────────────────────────────────────────────────────
totaal = len(gefilterd)
risico_aantal = int(gefilterd["risico"].sum())

m1, m2, m3, m4 = st.columns(4)
m1.metric("Studenten", totaal)
m2.metric("Op schema", totaal - risico_aantal)
risico_pct = f"{risico_aantal / totaal * 100:.0f}%" if totaal else "—"
m3.metric("Aandacht nodig", risico_aantal, delta=risico_pct, delta_color="inverse")
gem_voortgang = f"{gefilterd['voortgang'].mean() * 100:.0f}%" if totaal else "—"
m4.metric("Gem. voortgang", gem_voortgang)

st.divider()

# ── Spreidingsplot ────────────────────────────────────────────────────────────
st.subheader("Voortgang vs. BSA per student")
if not gefilterd.empty:
    overzicht = groepsoverzicht(gefilterd)
    st.altair_chart(groep_voortgang_grafiek(overzicht), use_container_width=True)

st.divider()

# ── Studenten met aandacht ────────────────────────────────────────────────────
risico_df = gefilterd[gefilterd["risico"]].sort_values("voortgang")
if not risico_df.empty:
    st.subheader(f"⚠️ Studenten die aandacht nodig hebben ({len(risico_df)})")
    st.dataframe(
        risico_df[
            [
                "naam",
                "opleiding",
                "mentor",
                "voortgang",
                "bsa_behaald",
                "bsa_vereist",
                "bsa_percentage",
            ]
        ]
        .rename(
            columns={
                "naam": "Naam",
                "opleiding": "Opleiding",
                "mentor": "Mentor",
                "voortgang": "Voortgang",
                "bsa_behaald": "BSA behaald",
                "bsa_vereist": "BSA vereist",
                "bsa_percentage": "BSA %",
            }
        )
        .style.format({"Voortgang": "{:.0%}", "BSA %": "{:.0%}"}),
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# ── Volledig overzicht ────────────────────────────────────────────────────────
st.subheader("Alle studenten")
overzicht_cols = groepsoverzicht(gefilterd)
st.dataframe(
    overzicht_cols.rename(
        columns={
            "studentnummer": "Nr.",
            "naam": "Naam",
            "opleiding": "Opleiding",
            "cohort": "Cohort",
            "leerweg": "Leerweg",
            "mentor": "Mentor",
            "voortgang": "Voortgang",
            "bsa_behaald": "BSA behaald",
            "bsa_vereist": "BSA vereist",
            "bsa_percentage": "BSA %",
            "risico": "Risico",
            "kt_gemiddelde": "KT gem.",
        }
    )
    .style.format({"Voortgang": "{:.0%}", "BSA %": "{:.0%}", "KT gem.": "{:.0f}"})
    .applymap(lambda v: "background-color: #fdecea" if v is True else "", subset=["Risico"]),
    use_container_width=True,
    hide_index=True,
)

# ── Cohortgemiddelden ─────────────────────────────────────────────────────────
st.subheader("Gemiddelden per cohort")
cohort_df = cohort_gemiddelden(gefilterd)
if not cohort_df.empty:
    st.dataframe(
        cohort_df.rename(
            columns={
                "opleiding": "Opleiding",
                "cohort": "Cohort",
                "aantal": "Aantal",
                "gem_voortgang": "Gem. voortgang",
                "gem_bsa_percentage": "Gem. BSA %",
                "studenten_met_risico": "# Risico",
            }
        ).style.format({"Gem. voortgang": "{:.0%}", "Gem. BSA %": "{:.0%}"}),
        use_container_width=True,
        hide_index=True,
    )
