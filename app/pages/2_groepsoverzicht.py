"""Pagina: Groepsoverzicht — docentweergave."""

from pathlib import Path

import streamlit as st

from samenwijzer.analyze import cohort_gemiddelden, groepsoverzicht, peer_profielen, signaleringen
from samenwijzer.auth import mentor_filter, vereist_docent
from samenwijzer.prepare import load_welzijn_csv
from samenwijzer.styles import CSS, render_footer, render_nav
from samenwijzer.visualize import groep_voortgang_grafiek
from samenwijzer.wellbeing import (
    antwoord_label,
    filter_signaleringen_voor_mentor,
    laad_notities,
    sla_notitie_op,
)

_ROOT = Path(__file__).parent.parent.parent
_DEMO_WELZIJN = _ROOT / "data" / "01-raw" / "demo" / "welzijn.csv"
_NOTITIES_PAD = _ROOT / "data" / "02-prepared" / "notities.csv"

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

# ── Overzichtsmetrics (eerst getoond, filters daarna) ─────────────────────────
totaal_alle = len(df)
risico_alle = int(df["risico"].sum())
gem_voortgang_alle = f"{df['voortgang'].mean() * 100:.0f}%" if totaal_alle else "—"

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(
        f"<div class='stat-card'><p class='stat-card__label'>Studenten</p>"
        f"<p class='stat-card__value'>{totaal_alle}</p></div>",
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        f"<div class='stat-card'><p class='stat-card__label'>Op schema</p>"
        f"<p class='stat-card__value'>{totaal_alle - risico_alle}</p></div>",
        unsafe_allow_html=True,
    )
with m3:
    risico_delta_klasse = "stat-card__delta--neg" if risico_alle > 0 else "stat-card__delta--pos"
    risico_pct_alle = f"{risico_alle / totaal_alle * 100:.0f}%" if totaal_alle else "—"
    st.markdown(
        f"<div class='stat-card'><p class='stat-card__label'>Aandacht nodig</p>"
        f"<p class='stat-card__value'>{risico_alle}</p>"
        f"<p class='{risico_delta_klasse}'>{risico_pct_alle} van de groep</p></div>",
        unsafe_allow_html=True,
    )
with m4:
    st.markdown(
        f"<div class='stat-card'><p class='stat-card__label'>Gem. voortgang</p>"
        f"<p class='stat-card__value'>{gem_voortgang_alle}</p></div>",
        unsafe_allow_html=True,
    )

st.divider()

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

totaal = len(gefilterd)
risico_aantal = int(gefilterd["risico"].sum())

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_voortgang, tab_signaleringen = st.tabs(["📊 Voortgang", "⚠️ Signaleringen"])

# ── Tab: Voortgang ────────────────────────────────────────────────────────────
with tab_voortgang:
    st.subheader("Voortgang vs. BSA per student")
    if not gefilterd.empty:
        overzicht = groepsoverzicht(gefilterd)
        st.altair_chart(groep_voortgang_grafiek(overzicht), use_container_width=True)

    st.divider()

    risico_df = gefilterd[gefilterd["risico"]].sort_values("voortgang")
    if not risico_df.empty:
        st.subheader(f"⚠️ Studenten die aandacht nodig hebben ({len(risico_df)})")
        st.dataframe(
            risico_df[
                ["naam", "opleiding", "mentor", "voortgang",
                 "bsa_behaald", "bsa_vereist", "bsa_percentage"]
            ]
            .rename(columns={
                "naam": "Naam", "opleiding": "Opleiding", "mentor": "Mentor",
                "voortgang": "Voortgang", "bsa_behaald": "BSA behaald",
                "bsa_vereist": "BSA vereist", "bsa_percentage": "BSA %",
            })
            .style.format({"Voortgang": "{:.0%}", "BSA %": "{:.0%}"}),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    st.subheader("Alle studenten")
    st.dataframe(
        groepsoverzicht(gefilterd)
        .rename(columns={
            "studentnummer": "Nr.", "naam": "Naam", "opleiding": "Opleiding",
            "cohort": "Cohort", "leerweg": "Leerweg", "mentor": "Mentor",
            "voortgang": "Voortgang", "bsa_behaald": "BSA behaald",
            "bsa_vereist": "BSA vereist", "bsa_percentage": "BSA %",
            "risico": "Risico", "kt_gemiddelde": "KT gem.",
        })
        .style.format({"Voortgang": "{:.0%}", "BSA %": "{:.0%}", "KT gem.": "{:.0f}"})
        .map(lambda v: "background-color: #fdecea" if v is True else "", subset=["Risico"]),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

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
                pp_df.rename(columns={
                    "naam": "Student", "sterkste_kt": "Sterk in",
                    "sterkste_score": "Score", "zwakste_kt": "Aandacht voor",
                    "zwakste_score": "Score ",
                }).style.format({"Score": "{:.0f}", "Score ": "{:.0f}"}),
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    st.subheader("Gemiddelden per cohort")
    cohort_df = cohort_gemiddelden(gefilterd)
    if not cohort_df.empty:
        st.dataframe(
            cohort_df.rename(columns={
                "opleiding": "Opleiding", "cohort": "Cohort", "aantal": "Aantal",
                "gem_voortgang": "Gem. voortgang", "gem_bsa_percentage": "Gem. BSA %",
                "studenten_met_risico": "# Risico",
            }).style.format({"Gem. voortgang": "{:.0%}", "Gem. BSA %": "{:.0%}"}),
            use_container_width=True,
            hide_index=True,
        )

# ── Tab: Signaleringen ────────────────────────────────────────────────────────
with tab_signaleringen:
    df_welzijn = load_welzijn_csv(_DEMO_WELZIJN)
    df_signalen = signaleringen(gefilterd, df_welzijn)
    df_signalen = filter_signaleringen_voor_mentor(df_signalen, mentor_naam)

    if df_signalen.empty:
        st.success(f"Geen actieve signaleringen voor mentor **{mentor_naam}**.")
    else:
        st.caption(
            f"Studenten met een recente welzijnsscore van **Matig** of **Zwaar**. "
            f"{len(df_signalen)} signalering(en) — meest zorgelijk bovenaan."
        )

        notities_df = laad_notities(_NOTITIES_PAD)

        for _, rij in df_signalen.iterrows():
            snr = rij["studentnummer"]
            waarde = float(rij["welzijnswaarde"])
            kleur = "🔴" if waarde == 0.0 else "🟡"

            with st.container(border=True):
                col_info, col_form = st.columns([2, 1])

                with col_info:
                    st.markdown(
                        f"{kleur} **{rij['naam']}** &nbsp;·&nbsp; "
                        f"Laatste check: {rij['datum']} &nbsp;·&nbsp; "
                        f"Score: **{antwoord_label(int(rij['antwoord']))}**"
                    )
                    if rij["toelichting"]:
                        st.caption(f'Toelichting student: "{rij["toelichting"]}"')

                    student_notities = notities_df[
                        notities_df["studentnummer"] == snr
                    ].sort_values("timestamp", ascending=False)

                    if not student_notities.empty:
                        st.caption("Eerdere notities:")
                        for _, n in student_notities.iterrows():
                            st.caption(f"— {n['timestamp'][:10]}: {n['notitie']}")

                with col_form:
                    with st.form(key=f"notitie_{snr}"):
                        tekst = st.text_input(
                            "Notitie toevoegen",
                            placeholder="Bijv. 'Heb contact opgenomen'",
                            label_visibility="collapsed",
                        )
                        if st.form_submit_button("Opslaan", use_container_width=True):
                            try:
                                sla_notitie_op(_NOTITIES_PAD, snr, mentor_naam, tekst)
                                st.success("Opgeslagen.")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))

render_footer()
