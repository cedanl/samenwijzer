"""Pagina: Groepsoverzicht — docentweergave."""

import streamlit as st

from samenwijzer.analyze import cohort_gemiddelden, groepsoverzicht, peer_profielen
from samenwijzer.auth import mentor_filter, vereist_docent
from samenwijzer.outreach_store import get_alle_welzijnschecks
from samenwijzer.styles import CSS, render_footer, render_nav
from samenwijzer.visualize import groep_voortgang_grafiek
from samenwijzer.welzijn import categorie_label, urgentie_label

st.set_page_config(page_title="Groepsoverzicht — Samenwijzer", page_icon="👥", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
render_nav()
vereist_docent()
st.title("👥 Groepsoverzicht")

if "df" not in st.session_state:
    st.warning("Ga eerst naar de startpagina om de data te laden.")
    st.stop()

df = mentor_filter(st.session_state["df"])
mentor_naam = st.session_state.get("mentor_naam", "")
st.caption(f"Mentor: **{mentor_naam}** · {len(df)} studenten")

# ── Filters ───────────────────────────────────────────────────────────────────
with st.expander("Filters", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        opleidingen = ["Alle"] + sorted(df["opleiding"].unique().tolist())
        opleiding = st.selectbox("Opleiding", opleidingen)
    with col2:
        cohorten = ["Alle"] + sorted(df["cohort"].unique().tolist(), reverse=True)
        cohort = st.selectbox("Cohort", cohorten)

gefilterd = df.copy()
if opleiding != "Alle":
    gefilterd = gefilterd[gefilterd["opleiding"] == opleiding]
if cohort != "Alle":
    gefilterd = gefilterd[gefilterd["cohort"] == cohort]

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

# ── Welzijnschecks ────────────────────────────────────────────────────────────
alle_checks = get_alle_welzijnschecks()
studentnummers_groep = set(gefilterd["studentnummer"].tolist())
checks_groep = [c for c in alle_checks if c.studentnummer in studentnummers_groep]

if checks_groep:
    _urgentie_icoon = {1: "🟢", 2: "🟡", 3: "🔴"}
    st.subheader(f"💚 Recente welzijnschecks ({len(checks_groep)})")
    st.caption("Studenten die zelf aangeven hulp nodig te hebben.")
    for check in checks_groep[:10]:
        naam_rij = gefilterd[gefilterd["studentnummer"] == check.studentnummer]
        naam = naam_rij.iloc[0]["naam"] if not naam_rij.empty else check.studentnummer
        icoon = _urgentie_icoon.get(check.urgentie, "⚪")
        st.markdown(
            f"{icoon} **{naam}** · {check.timestamp[:10]} · "
            f"{categorie_label(check.categorie)} · {urgentie_label(check.urgentie)}"
            + (f"  \n> {check.toelichting[:120]}" if check.toelichting else "")
        )
    if len(checks_groep) > 10:
        st.caption(f"… en nog {len(checks_groep) - 10} eerdere checks.")

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
    .map(lambda v: "background-color: #fdecea" if v is True else "", subset=["Risico"]),
    use_container_width=True,
    hide_index=True,
)

# ── Peer Learning ─────────────────────────────────────────────────────────────
with st.expander("👥 Peer Learning — koppeladvies op basis van kerntaken"):
    pp_df = peer_profielen(gefilterd)
    if pp_df.empty:
        st.info("Geen kerntaakdata beschikbaar voor peer matching.")
    else:
        st.caption(
            "Overzicht van de sterkste en zwakste kerntaak per student. "
            "Koppel studenten die elkaars sterke punten kunnen benutten."
        )
        st.dataframe(
            pp_df.rename(
                columns={
                    "naam": "Student",
                    "sterkste_kt": "Sterk in",
                    "sterkste_score": "Score",
                    "zwakste_kt": "Aandacht voor",
                    "zwakste_score": "Score ",
                }
            ).style.format({"Score": "{:.0f}", "Score ": "{:.0f}"}),
            use_container_width=True,
            hide_index=True,
        )

st.divider()

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

render_footer()
