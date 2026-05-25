"""Pagina: Voortgang — student- en docentweergave."""

import logging

import streamlit as st

from samenwijzer._ai import APITimeoutError, vriendelijke_fout
from samenwijzer.analyze import (
    cohort_positie,
    get_student,
    kerntaak_scores,
    leerpad_niveau,
    werkproces_scores,
    zwakste_kerntaak,
    zwakste_werkproces,
)
from samenwijzer.auth import mentor_filter
from samenwijzer.coach import genereer_weekplan
from samenwijzer.groei import heeft_self_rating
from samenwijzer.styles import (
    badge,
    hero,
    inject_theme,
    render_footer,
    render_nav,
    section_label,
    stat_card,
)
from samenwijzer.visualize import werkproces_grafiek

log = logging.getLogger(__name__)

st.set_page_config(page_title="Voortgang — Samenwijzer", page_icon="📊", layout="wide")

if "df" not in st.session_state or "rol" not in st.session_state:
    inject_theme(None)
    st.warning("Ga eerst naar de [startpagina](/) om in te loggen.")
    st.stop()

df = st.session_state["df"]
rol = st.session_state["rol"]
inject_theme(rol)
render_nav()

# ── Studentselectie ────────────────────────────────────────────────────────────
if rol == "student":
    studentnummer = st.session_state["studentnummer"]
else:
    groep = mentor_filter(df)
    opties = (
        groep.sort_values("naam")[["naam", "studentnummer"]]
        .apply(lambda r: f"{r['naam']} ({r['studentnummer']})", axis=1)
        .tolist()
    )
    studentnummer = (
        st.selectbox("Selecteer een student uit jouw groep", opties).split("(")[-1].rstrip(")")
    )

student = get_student(df, studentnummer)
niveau = leerpad_niveau(student)
niveau_kind = niveau.lower()

# ── Hero ─────────────────────────────────────────────────────────────────────
status_kind = "urgent" if student["risico"] else "onschema"
status_label = "Aandacht nodig" if student["risico"] else "Op schema"
meta_text = (
    f"{student['opleiding']} · Niveau {student['niveau']} · {student['leerweg']}"
    f" · Cohort {student['cohort']} · Mentor {student['mentor']}"
)
hero(
    str(student["naam"]),
    meta_text,
    badges=[(niveau_kind, niveau), (status_kind, status_label)],
)

# ── Bron-badge: zelf beoordeeld of synthetische schatting? ──
heeft_rating, laatst = heeft_self_rating(studentnummer)
if heeft_rating:
    st.caption(f"Zelf beoordeeld op {(laatst or '')[:10]}")
else:
    st.caption("Schatting op basis van OER — vul je groeidossier in voor je eigen scores")

# ── Drie stat-cards met inline ring ─────────────────────────────────────────
positie_info = cohort_positie(df, studentnummer)
pos = positie_info["positie"]
totaal_cohort = positie_info["totaal"]
cohort = positie_info["cohort"]
voortgang_pct = int(student["voortgang"] * 100)
gem_pct = int(positie_info["gemiddelde_voortgang"] * 100)
delta = voortgang_pct - gem_pct

behaald = int(student["bsa_behaald"])
vereist = int(student["bsa_vereist"])
bsa_progress = behaald / vereist if vereist else 0.0

# Positie: lager nummer = beter; visualiseer als percentile (1 = top)
positie_progress = (totaal_cohort - pos + 1) / totaal_cohort if totaal_cohort else 0.0

col_v, col_b, col_c = st.columns(3)
with col_v:
    stat_card(
        "Studievoortgang",
        f"{voortgang_pct}%",
        progress=student["voortgang"],
    )
with col_b:
    stat_card(
        "Studiepunten BSA",
        str(behaald),
        value_sub=f" / {vereist}",
        progress=bsa_progress,
        alert_ring=bsa_progress < 0.7,
    )
with col_c:
    stat_card(
        "Positie in cohort",
        str(pos),
        value_sub=f" / {totaal_cohort}",
        delta=f"{'+' if delta >= 0 else ''}{delta}% vs. gemiddelde",
        delta_negative=delta < 0,
        sub=f"Cohort {cohort}",
        progress=positie_progress,
    )

# ── Tabs: scores, aandachtspunten, weekplan ───────────────────────────────────
zkt = zwakste_kerntaak(df, studentnummer)
zwp = zwakste_werkproces(df, studentnummer)
zkt_label = zkt[0] if zkt else ""
zwp_label = zwp[0] if zwp else ""

tab_scores, tab_aandacht, tab_weekplan = st.tabs(["Scores", "Aandachtspunten", "Weekplan"])

# ── TAB 1: SCORES ────────────────────────────────────────────────────────────
with tab_scores:
    kt_df = kerntaak_scores(df, studentnummer)
    wp_df = werkproces_scores(df, studentnummer)

    if kt_df.empty:
        st.info("Geen kerntaakscores beschikbaar.")
    else:
        for _, kt in kt_df.iterrows():
            kt_idx = str(kt["kerntaak"]).removeprefix("kt_")
            wps = wp_df[wp_df["werkproces"].str.startswith(f"wp_{kt_idx}_")]

            with st.container(border=True):
                st.markdown(
                    f'<p class="sw-label">Kerntaak {kt_idx} · {kt["label"]}</p>'
                    f'<p class="sw-stat__value">{kt["score"]:.0f}'
                    f'<span class="sw-stat__value-sub"> / 100</span></p>',
                    unsafe_allow_html=True,
                )
                if not wps.empty:
                    section_label("Werkprocessen")
                    st.altair_chart(werkproces_grafiek(wps), use_container_width=True)

# ── TAB 2: AANDACHTSPUNTEN ───────────────────────────────────────────────────
with tab_aandacht:
    if zkt or zwp:
        col_zkt, col_zwp = st.columns(2)
        with col_zkt:
            if zkt:
                label, score = zkt
                with st.container(border=True):
                    section_label("Zwakste kerntaak", warning=True)
                    st.markdown(
                        f'<p class="sw-tile__title">{label}</p>'
                        f'<p class="sw-stat__sub">{score:.0f} punten</p>',
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        "Bespreek dit met je mentor of gebruik de AI Leercoach voor gerichte oefening."
                    )
        with col_zwp:
            if zwp:
                label, score = zwp
                with st.container(border=True):
                    section_label("Zwakste werkproces", warning=True)
                    st.markdown(
                        f'<p class="sw-tile__title">{label}</p>'
                        f'<p class="sw-stat__sub">{score:.0f} punten</p>',
                        unsafe_allow_html=True,
                    )
                    st.caption("Focus extra op dit werkproces bij je volgende stage of opdracht.")
    else:
        st.markdown(
            '<div class="sw-alert sw-alert--info">Geen specifieke aandachtspunten gevonden '
            "— goed bezig.</div>",
            unsafe_allow_html=True,
        )

# ── TAB 3: WEEKPLAN ──────────────────────────────────────────────────────────
with tab_weekplan:
    st.caption(
        "Een persoonlijk studieplan voor deze week, afgestemd op jouw voortgang, "
        "BSA-status en aandachtspunten."
    )

    weekplan_sleutel = f"sw_weekplan_{studentnummer}"

    col_gen, col_reset = st.columns([4, 1])
    with col_gen:
        genereer_btn = st.button(
            "Genereer weekplan",
            type="primary",
            key="btn_weekplan",
            use_container_width=True,
        )
    with col_reset:
        if st.button("Reset", key="btn_weekplan_reset", use_container_width=True):
            st.session_state.pop(weekplan_sleutel, None)
            st.rerun()

    if genereer_btn:
        st.session_state.pop(weekplan_sleutel, None)
        try:
            with st.spinner("Weekplan wordt opgesteld…"):
                tekst = st.write_stream(
                    genereer_weekplan(
                        naam=str(student["naam"]),
                        opleiding=str(student["opleiding"]),
                        leerpad=niveau,
                        voortgang=float(student["voortgang"]),
                        bsa_behaald=float(student["bsa_behaald"]),
                        bsa_vereist=float(student["bsa_vereist"]),
                        zwakste_kerntaak=zkt_label,
                        zwakste_werkproces=zwp_label,
                    )
                )
            st.session_state[weekplan_sleutel] = tekst
        except APITimeoutError:
            st.error("De AI-service reageert niet. Probeer het over een moment opnieuw.")
        except Exception as e:
            log.exception("Weekplan-generatie mislukt")
            st.error(vriendelijke_fout(e))
    elif weekplan_sleutel in st.session_state:
        st.markdown(st.session_state[weekplan_sleutel])
    else:
        st.markdown(
            '<div class="sw-alert sw-alert--info">'
            f"Klik op {badge('accent', 'Genereer weekplan')} om je persoonlijke studieplan te maken."
            "</div>",
            unsafe_allow_html=True,
        )

render_footer()
