"""Pagina: Voortgang — student- en docentweergave."""

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
from samenwijzer.auth import mentor_filter
from samenwijzer.coach import genereer_weekplan
from samenwijzer.styles import CSS, render_footer, render_nav
from samenwijzer.visualize import (
    bsa_staaf,
    kerntaak_grafiek,
    voortgang_gauge,
    werkproces_grafiek,
)

st.set_page_config(page_title="Voortgang — Samenwijzer", page_icon="📊", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
render_nav()

if "df" not in st.session_state or "rol" not in st.session_state:
    st.warning("Ga eerst naar de [startpagina](/) om in te loggen.")
    st.stop()

df = st.session_state["df"]
rol = st.session_state["rol"]

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

niveau_klasse = niveau.lower()
risico_badge = (
    "<span class='badge badge--niet-gecontacteerd'>⚠️ Aandacht nodig</span>"
    if student["risico"]
    else "<span class='badge badge--opgelost'>✅ Op schema</span>"
)

# ── Hero-kaart ─────────────────────────────────────────────────────────────────
st.markdown(
    f"""<div class="hero-card">
  <p class="hero-card__naam">{student["naam"]}</p>
  <p class="hero-card__meta">{student["opleiding"]} &nbsp;·&nbsp; Niveau {student["niveau"]} &nbsp;·&nbsp; {student["leerweg"]} &nbsp;·&nbsp; Cohort {student["cohort"]}</p>
  <p class="hero-card__mentor">Mentor: {student["mentor"]}</p>
  <span class="badge badge--{niveau_klasse}">{niveau}</span>
  &nbsp;
  {risico_badge}
  &nbsp;
  <span style="font-size:1.1rem;font-weight:700;">{badge(student)}</span>
</div>""",
    unsafe_allow_html=True,
)

# ── Drie statistieken ─────────────────────────────────────────────────────────
positie_info = cohort_positie(df, studentnummer)
pos = positie_info["positie"]
totaal_cohort = positie_info["totaal"]
cohort = positie_info["cohort"]
voortgang_pct = int(student["voortgang"] * 100)
gem_pct = int(df[df["cohort"] == cohort]["voortgang"].mean() * 100)
delta = voortgang_pct - gem_pct
delta_kleur = "#27ae60" if delta >= 0 else "#c0392b"
delta_teken = "+" if delta >= 0 else ""

col_v, col_b, col_c = st.columns(3)

with col_v:
    st.markdown(
        f"<div class='stat-card'>"
        f"<p class='stat-card__label'>Studievoortgang</p>"
        f"<p class='stat-card__value'>{voortgang_pct}%</p>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.altair_chart(voortgang_gauge(student["voortgang"]), use_container_width=True)

with col_b:
    behaald = int(student["bsa_behaald"])
    vereist = int(student["bsa_vereist"])
    st.markdown(
        f"<div class='stat-card'>"
        f"<p class='stat-card__label'>Studiepunten (BSA)</p>"
        f"<p class='stat-card__value'>{behaald}<span class='stat-card__sub'> / {vereist}</span></p>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.altair_chart(
        bsa_staaf(student["bsa_behaald"], student["bsa_vereist"]),
        use_container_width=True,
    )

delta_klasse = "stat-card__delta--pos" if delta >= 0 else "stat-card__delta--neg"
with col_c:
    st.markdown(
        f"<div class='stat-card'>"
        f"<p class='stat-card__label'>Positie in cohort</p>"
        f"<p class='stat-card__value'>{pos}<span class='stat-card__sub'> / {totaal_cohort}</span></p>"
        f"<p class='{delta_klasse}'>{delta_teken}{delta}% t.o.v. gemiddelde</p>"
        f"<p class='stat-card__sub'>Cohort {cohort}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )

# ── Tabs: scores, aandachtspunten, weekplan ───────────────────────────────────
zkt = zwakste_kerntaak(df, studentnummer)
zwp = zwakste_werkproces(df, studentnummer)
zkt_label = zkt[0] if zkt else ""
zwp_label = zwp[0] if zwp else ""

tab_scores, tab_aandacht, tab_weekplan = st.tabs(["📊 Scores", "⚠️ Aandachtspunten", "📅 Weekplan"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: SCORES
# ─────────────────────────────────────────────────────────────────────────────
with tab_scores:
    kt_df = kerntaak_scores(df, studentnummer)
    wp_df = werkproces_scores(df, studentnummer)

    col_kt, col_wp = st.columns(2)

    with col_kt:
        with st.container(border=True):
            st.markdown("<p class='section-label'>Kerntaken</p>", unsafe_allow_html=True)
            if not kt_df.empty:
                st.altair_chart(kerntaak_grafiek(kt_df), use_container_width=True)
            else:
                st.info("Geen kerntaakscores beschikbaar.")

    with col_wp:
        with st.container(border=True):
            st.markdown("<p class='section-label'>Werkprocessen</p>", unsafe_allow_html=True)
            if not wp_df.empty:
                st.altair_chart(werkproces_grafiek(wp_df), use_container_width=True)
            else:
                st.info("Geen werkprocesscores beschikbaar.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: AANDACHTSPUNTEN
# ─────────────────────────────────────────────────────────────────────────────
with tab_aandacht:
    if zkt or zwp:
        col_zkt, col_zwp = st.columns(2)

        with col_zkt:
            if zkt:
                label, score = zkt
                with st.container(border=True):
                    st.markdown(
                        "<p class='section-label section-label--warning'>⚠️ Zwakste kerntaak</p>"
                        f"<p style='font-size:1.05rem; font-weight:700; margin:6px 0 2px; "
                        f"color:#1a1a1a'>{label}</p>"
                        f"<p style='color:#aaa; font-size:0.82rem; margin:0'>"
                        f"{score:.0f} punten</p>",
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        "Bespreek dit met je mentor of gebruik de AI Leercoach voor gerichte "
                        "oefening."
                    )

        with col_zwp:
            if zwp:
                label, score = zwp
                with st.container(border=True):
                    st.markdown(
                        "<p class='section-label section-label--warning'>⚠️ Zwakste werkproces</p>"
                        f"<p style='font-size:1.05rem; font-weight:700; margin:6px 0 2px; "
                        f"color:#1a1a1a'>{label}</p>"
                        f"<p style='color:#aaa; font-size:0.82rem; margin:0'>"
                        f"{score:.0f} punten</p>",
                        unsafe_allow_html=True,
                    )
                    st.caption("Focus extra op dit werkproces bij je volgende stage of opdracht.")
    else:
        st.info("Geen specifieke aandachtspunten gevonden — goed bezig!")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: WEEKPLAN
# ─────────────────────────────────────────────────────────────────────────────
with tab_weekplan:
    st.caption(
        "Een persoonlijk studieplan voor deze week, afgestemd op jouw voortgang, "
        "BSA-status en aandachtspunten."
    )

    weekplan_sleutel = f"sw_weekplan_{studentnummer}"

    col_gen, col_reset = st.columns([4, 1])
    with col_gen:
        genereer_btn = st.button(
            "📅 Genereer weekplan", type="primary", key="btn_weekplan", use_container_width=True
        )
    with col_reset:
        if st.button("↺", key="btn_weekplan_reset", use_container_width=True):
            st.session_state.pop(weekplan_sleutel, None)
            st.rerun()

    if genereer_btn:
        st.session_state.pop(weekplan_sleutel, None)
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
    elif weekplan_sleutel in st.session_state:
        st.markdown(st.session_state[weekplan_sleutel])
    else:
        st.info("Klik op **GENEREER WEEKPLAN** om je persoonlijke studieplan te maken.")

render_footer()
