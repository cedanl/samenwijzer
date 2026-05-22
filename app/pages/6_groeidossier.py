"""Pagina: Groeidossier — student-zelfbeoordeling en mentor-feedback."""

import html
import logging
from datetime import datetime

import pandas as pd
import streamlit as st

from samenwijzer._ai import APITimeoutError, vriendelijke_fout
from samenwijzer.analyze import get_student, oer_label
from samenwijzer.auth import mentor_filter
from samenwijzer.bewijsstuk_store import (
    MAX_GROOTTE_BYTES,
    TOEGESTANE_EXTENSIES,
    BewijsstukFout,
    open_bestand,
)
from samenwijzer.bewijsstuk_store import opslaan as bewijsstuk_opslaan
from samenwijzer.bewijsstuk_store import verwijderen as bewijsstuk_verwijderen
from samenwijzer.groei import (
    delta_t_o_v_vorige,
    klas_gemiddelden_per_wp,
    laatste_twee_metingen_per_wp,
    overlay_self_scores,
)
from samenwijzer.groei_store import (
    BewijsstukMeta,
    GroeiActueel,
    MentorFeedback,
    dien_in,
    geef_terug,
    get_actueel,
    get_bewijsstukken,
    get_historie,
    get_mentor_feedback,
    insert_bewijsstuk,
    keur_goed,
    sla_groei_op,
    upsert_mentor_feedback,
)
from samenwijzer.groei_store import verwijder_bewijsstuk as verwijder_bewijsstuk_meta
from samenwijzer.styles import CSS, render_footer, render_nav
from samenwijzer.transform import get_kerntaak_columns, get_werkproces_columns
from samenwijzer.tutor import aanscherp_verantwoording

log = logging.getLogger(__name__)

st.set_page_config(page_title="Groeidossier — Samenwijzer", page_icon="🌱", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
render_nav()

if "df" not in st.session_state or "rol" not in st.session_state:
    st.warning("Ga eerst naar de [startpagina](/) om in te loggen.")
    st.stop()

df = st.session_state["df"]
rol = st.session_state["rol"]

# ── Studentselectie ──────────────────────────────────────────────────────────
if rol == "student":
    studentnummer = st.session_state["studentnummer"]
    is_eigenaar = True
else:
    groep = mentor_filter(df)
    opties = (
        groep.sort_values("naam")[["naam", "studentnummer"]]
        .apply(lambda r: f"{r['naam']} ({r['studentnummer']})", axis=1)
        .tolist()
    )
    if not opties:
        st.info("Je hebt geen studenten in je groep.")
        render_footer()
        st.stop()
    keuze = st.selectbox("Selecteer een student uit jouw groep", opties)
    studentnummer = keuze.split("(")[-1].rstrip(")")
    if studentnummer not in groep["studentnummer"].values:
        st.error("Geen toegang tot deze student.")
        st.stop()
    is_eigenaar = False

student = get_student(df, studentnummer)
opleiding = str(student["opleiding"])
crebo = str(student.get("crebo", ""))

st.markdown(f"## 🌱 Groeidossier — {student['naam']}")
st.caption(f"{opleiding} · Niveau {student['niveau']} · Cohort {student['cohort']}")

# ── Huidige data ─────────────────────────────────────────────────────────────
actueel_lijst = get_actueel(studentnummer)
actueel = {r.wp_kolom: r for r in actueel_lijst}
feedback = get_mentor_feedback(studentnummer)

kt_cols = get_kerntaak_columns(df)
wp_cols = get_werkproces_columns(df)

_NIVEAU_LABELS = "Starter  ·  Op weg  ·  Gevorderd  ·  Beroepsbekwaam"


def _wp_van_kt(kt_col: str) -> list[str]:
    idx = kt_col.removeprefix("kt_")
    return [w for w in wp_cols if w.startswith(f"wp_{idx}_")]


def _huidige_score(wp_col: str) -> int:
    if wp_col in actueel:
        return actueel[wp_col].score
    df_waarde = student.get(wp_col)
    try:
        return int(float(df_waarde)) if df_waarde is not None else 50
    except (TypeError, ValueError):
        return 50


def _huidige_verantwoording(wp_col: str) -> str:
    return actueel[wp_col].verantwoording if wp_col in actueel else ""


def _render_bewijsstuk_expander(wp_col: str, wp_label: str) -> None:
    """Toon bewijsstukken voor één werkproces + upload + verwijder."""
    stukken = [b for b in get_bewijsstukken(studentnummer) if b.wp_kolom == wp_col]
    with st.expander(f"📎 Bewijsstukken ({len(stukken)})"):
        for stuk in stukken:
            cols = st.columns([5, 2, 1])
            with cols[0]:
                grootte_kb = stuk.grootte_bytes // 1024
                st.markdown(f"**{stuk.bestandsnaam}** _{grootte_kb} kB_")
                if stuk.toelichting:
                    st.caption(stuk.toelichting)
            with cols[1]:
                try:
                    inhoud = open_bestand(stuk.bestandspad)
                    st.download_button(
                        "⬇️ Download",
                        data=inhoud,
                        file_name=stuk.bestandsnaam,
                        mime=stuk.mime_type,
                        key=f"dl_{stuk.id}",
                    )
                except FileNotFoundError:
                    st.warning("Bestand ontbreekt op disk.")
                except BewijsstukFout as e:
                    log.warning("Bewijsstuk %s onbereikbaar: %s", stuk.id, e)
            with cols[2]:
                if is_eigenaar and st.button("🗑️", key=f"del_{stuk.id}"):
                    try:
                        bewijsstuk_verwijderen(stuk.bestandspad)
                    except BewijsstukFout as e:
                        log.warning("FS-verwijdering mislukt: %s", e)
                    assert stuk.id is not None
                    verwijder_bewijsstuk_meta(stuk.id)
                    st.rerun()

        if is_eigenaar:
            st.markdown("---")
            upload = st.file_uploader(
                f"Voeg bewijsstuk toe voor {wp_label}",
                type=[e.lstrip(".") for e in TOEGESTANE_EXTENSIES],
                key=f"upl_{studentnummer}_{wp_col}",
                accept_multiple_files=False,
            )
            toelichting = st.text_input(
                "Toelichting (optioneel)",
                key=f"upl_toel_{studentnummer}_{wp_col}",
                max_chars=200,
            )
            if upload is not None and st.button(
                "📤 Uploaden", key=f"btn_upl_{studentnummer}_{wp_col}"
            ):
                inhoud = upload.getvalue()
                if len(inhoud) > MAX_GROOTTE_BYTES:
                    st.error(
                        f"Bestand is te groot ({len(inhoud) // 1024} kB); "
                        f"max {MAX_GROOTTE_BYTES // 1024 // 1024} MB."
                    )
                else:
                    try:
                        rel_pad = bewijsstuk_opslaan(
                            studentnummer=studentnummer,
                            bestandsnaam=upload.name,
                            inhoud=inhoud,
                        )
                        insert_bewijsstuk(
                            BewijsstukMeta(
                                studentnummer=studentnummer,
                                wp_kolom=wp_col,
                                bestandsnaam=upload.name,
                                bestandspad=rel_pad,
                                mime_type=upload.type or "application/octet-stream",
                                grootte_bytes=len(inhoud),
                                toelichting=toelichting,
                                geupload_op=datetime.now().isoformat(timespec="seconds"),
                            )
                        )
                        st.success(f"Bewijsstuk '{upload.name}' geüpload.")
                        st.rerun()
                    except BewijsstukFout as e:
                        st.error(str(e))


tab_scores, tab_history, tab_spinneweb = st.tabs(
    ["📊 Mijn beoordeling", "📈 Groei over tijd", "🕸️ Spinneweb"]
)

with tab_scores:
    nieuwe_waarden: dict[str, tuple[int, str]] = {}

    for kt_col in kt_cols:
        kt_label = oer_label(opleiding, kt_col, crebo)
        kt_eigen_wp = _wp_van_kt(kt_col)
        if not kt_eigen_wp:
            continue
        # Skip kerntaken waarvan álle wp's NaN zijn (opleiding heeft ze niet)
        if all(pd.isna(student.get(w, float("nan"))) for w in kt_eigen_wp):
            continue

        with st.container(border=True):
            st.markdown(f"### {kt_label}")

            # Mentor-feedback (indien aanwezig)
            if kt_col in feedback:
                _naam = html.escape(feedback[kt_col].mentor_naam)
                _tekst = html.escape(feedback[kt_col].tekst).replace("\n", "<br>")
                st.markdown(
                    f"<div style='background:#f4f4f4;padding:12px;border-radius:6px;"
                    f"margin-bottom:12px;'>"
                    f"<b>📣 Feedback van {_naam}</b><br>{_tekst}</div>",
                    unsafe_allow_html=True,
                )

            for wp_col in kt_eigen_wp:
                wp_label = oer_label(opleiding, wp_col, crebo)
                huidige = _huidige_score(wp_col)
                huidige_v = _huidige_verantwoording(wp_col)

                st.markdown(f"**{wp_label}**")
                _status = actueel[wp_col].status if wp_col in actueel else None
                _badges = {
                    "concept": "🟡 Concept",
                    "ingediend": "📤 Ingediend — wacht op mentor",
                    "goedgekeurd": "✅ Goedgekeurd",
                    "teruggegeven": "↩️ Teruggegeven — pas aan en dien opnieuw in",
                }
                if _status in _badges:
                    st.caption(_badges[_status])
                if _status == "teruggegeven" and actueel[wp_col].mentor_opmerking:
                    st.warning(
                        f"**Verbeterpunt van je mentor:** {actueel[wp_col].mentor_opmerking}"
                    )
                st.caption(_NIVEAU_LABELS)

                score = st.slider(
                    "Score",
                    min_value=0,
                    max_value=100,
                    value=huidige,
                    key=f"slider_{studentnummer}_{wp_col}",
                    label_visibility="collapsed",
                    disabled=not is_eigenaar,
                )
                verant = st.text_area(
                    "Waarom vind je dit?",
                    value=huidige_v,
                    max_chars=1000,
                    key=f"verant_{studentnummer}_{wp_col}",
                    disabled=not is_eigenaar,
                )

                if is_eigenaar:
                    aanscherp_sleutel = f"sw_aanscherp_{studentnummer}_{wp_col}"
                    cols_ai = st.columns([1, 4])
                    with cols_ai[0]:
                        klik_aanscherp = st.button(
                            "✨ Aanscherpen",
                            key=f"btn_aanscherp_{studentnummer}_{wp_col}",
                            help="Vraag de tutor om je verantwoording aan te scherpen",
                        )
                    with cols_ai[1]:
                        if aanscherp_sleutel in st.session_state:
                            _sug = html.escape(st.session_state[aanscherp_sleutel]).replace(
                                "\n", "<br>"
                            )
                            st.markdown(
                                f"<div style='background:#fffbe6;padding:8px;border-radius:6px;'>"
                                f"<b>💡 Suggestie:</b><br>{_sug}</div>",
                                unsafe_allow_html=True,
                            )

                    if klik_aanscherp:
                        st.session_state.pop(aanscherp_sleutel, None)
                        try:
                            with st.spinner("Tutor denkt mee…"):
                                tekst = st.write_stream(
                                    aanscherp_verantwoording(
                                        werkproces_label=wp_label,
                                        kerntaak_label=kt_label,
                                        opleiding=opleiding,
                                        huidige_tekst=verant,
                                        score=score,
                                    )
                                )
                            st.session_state[aanscherp_sleutel] = tekst
                            st.rerun()
                        except APITimeoutError:
                            st.error("De AI-service reageert niet. Probeer het later opnieuw.")
                        except Exception as e:
                            log.exception("Aanscherpen mislukt")
                            st.error(vriendelijke_fout(e))

                _render_bewijsstuk_expander(wp_col, wp_label)
                nieuwe_waarden[wp_col] = (score, verant)
                st.markdown("---")

    if is_eigenaar:
        col_opslaan, col_indienen = st.columns(2)
        with col_opslaan:
            opslaan = st.button("💾 Concept opslaan", use_container_width=True)
        with col_indienen:
            indienen = st.button("📤 Indienen bij mentor", type="primary", use_container_width=True)

        if opslaan or indienen:
            nu = datetime.now().isoformat(timespec="seconds")
            rijen = [
                GroeiActueel(studentnummer, wp, score, verant, nu)
                for wp, (score, verant) in nieuwe_waarden.items()
                if (wp not in actueel)
                or actueel[wp].score != score
                or actueel[wp].verantwoording != verant
            ]
            if rijen:
                sla_groei_op(studentnummer, rijen)
            if indienen:
                gewijzigde_wps = {r.wp_kolom for r in rijen}
                in_te_dienen = [
                    wp
                    for wp in nieuwe_waarden
                    if wp in gewijzigde_wps
                    or (wp not in actueel)
                    or actueel[wp].status != "goedgekeurd"
                ]
                dien_in(studentnummer, in_te_dienen)
                st.success("Ingediend bij je mentor.")
            elif rijen:
                st.success(f"{len(rijen)} wijziging(en) opgeslagen als concept.")
            else:
                st.info("Niets gewijzigd om op te slaan.")
            st.rerun()
    else:
        st.markdown("### Beoordeel ingediende werkprocessen")
        for kt_col in kt_cols:
            kt_eigen_wp = _wp_van_kt(kt_col)
            if not kt_eigen_wp or all(pd.isna(student.get(w, float("nan"))) for w in kt_eigen_wp):
                continue
            kt_label = oer_label(opleiding, kt_col, crebo)
            st.markdown(f"#### {kt_label}")

            for wp_col in kt_eigen_wp:
                if wp_col not in actueel:
                    continue
                rij = actueel[wp_col]
                wp_label = oer_label(opleiding, wp_col, crebo)
                _badges = {
                    "concept": "🟡 Concept (nog niet ingediend)",
                    "ingediend": "📤 Ingediend",
                    "goedgekeurd": "✅ Goedgekeurd",
                    "teruggegeven": "↩️ Teruggegeven",
                }
                st.markdown(f"**{wp_label}** — {_badges.get(rij.status, rij.status)}")
                st.caption(
                    f"Score student: {rij.score} · {rij.verantwoording or '(geen toelichting)'}"
                )

                if rij.status == "ingediend":
                    opmerking = st.text_area(
                        "Verbeterfeedback (verplicht bij teruggeven)",
                        key=f"opm_{studentnummer}_{wp_col}",
                        max_chars=1000,
                    )
                    col_goed, col_terug = st.columns(2)
                    with col_goed:
                        if st.button(
                            "✅ Goedkeuren",
                            key=f"goed_{studentnummer}_{wp_col}",
                            use_container_width=True,
                        ):
                            keur_goed(
                                studentnummer,
                                wp_col,
                                st.session_state.get("mentor_naam", "onbekend"),
                            )
                            st.session_state["df"] = overlay_self_scores(
                                st.session_state["df_basis"]
                            )
                            st.success("Goedgekeurd.")
                            st.rerun()
                    with col_terug:
                        if st.button(
                            "↩️ Teruggeven",
                            key=f"terug_{studentnummer}_{wp_col}",
                            use_container_width=True,
                        ):
                            if not opmerking.strip():
                                st.error("Geef verbeterfeedback mee bij het teruggeven.")
                            else:
                                geef_terug(
                                    studentnummer,
                                    wp_col,
                                    st.session_state.get("mentor_naam", "onbekend"),
                                    opmerking.strip(),
                                )
                                st.session_state["df"] = overlay_self_scores(
                                    st.session_state["df_basis"]
                                )
                                st.success("Teruggegeven met feedback.")
                                st.rerun()
                elif rij.status == "teruggegeven" and rij.mentor_opmerking:
                    st.caption(f"Jouw eerdere feedback: {rij.mentor_opmerking}")
                st.markdown("---")

        st.markdown("### Algemene feedback per kerntaak")
        for kt_col in kt_cols:
            kt_eigen_wp = _wp_van_kt(kt_col)
            if not kt_eigen_wp or all(pd.isna(student.get(w, float("nan"))) for w in kt_eigen_wp):
                continue
            kt_label = oer_label(opleiding, kt_col, crebo)
            huidige_fb = feedback[kt_col].tekst if kt_col in feedback else ""
            tekst = st.text_area(
                f"Feedback op {kt_label}",
                value=huidige_fb,
                key=f"fb_{studentnummer}_{kt_col}",
                max_chars=1000,
            )
            if st.button(f"💬 Feedback opslaan ({kt_col})", key=f"btn_fb_{studentnummer}_{kt_col}"):
                upsert_mentor_feedback(
                    MentorFeedback(
                        studentnummer=studentnummer,
                        kt_kolom=kt_col,
                        mentor_naam=st.session_state.get("mentor_naam", "onbekend"),
                        tekst=tekst,
                        geschreven_op=datetime.now().isoformat(timespec="seconds"),
                    )
                )
                st.success("Feedback opgeslagen.")
                st.rerun()


with tab_history:
    historie = get_historie(studentnummer)
    if not historie:
        st.info(
            "Nog geen groeihistorie — sla je beoordeling op om je eerste meetpunt vast te leggen."
        )
    else:
        hist_df = pd.DataFrame(
            [
                {
                    "datum": h.opgeslagen_op[:10],
                    "werkproces": oer_label(opleiding, h.wp_kolom, crebo),
                    "score": h.score,
                }
                for h in historie
            ]
        )
        st.line_chart(hist_df, x="datum", y="score", color="werkproces")

        st.markdown("#### Delta t.o.v. vorige meting")
        cols = st.columns(min(len(wp_cols), 3))
        for i, wp_col in enumerate(wp_cols):
            d = delta_t_o_v_vorige(studentnummer, wp_col)
            if d is None:
                continue
            with cols[i % 3]:
                pijl = "▲" if d > 0 else ("▼" if d < 0 else "■")
                kleur = "#27ae60" if d > 0 else ("#c0392b" if d < 0 else "#999")
                st.markdown(
                    f"<div style='border:1px solid #eee;padding:10px;border-radius:6px;'>"
                    f"<small>{oer_label(opleiding, wp_col, crebo)}</small><br>"
                    f"<span style='color:{kleur};font-size:1.4rem;font-weight:700;'>"
                    f"{pijl} {abs(d)}</span></div>",
                    unsafe_allow_html=True,
                )

with tab_spinneweb:
    st.caption(
        "Per kerntaak een radar van je werkprocessen. "
        "Groen gevuld = jouw huidige meting · oranje stippellijn = jouw vorige meting · "
        f"blauwe lijn = klasgemiddelde ({opleiding}, cohort {student['cohort']})."
    )

    import plotly.graph_objects as go

    klas_gem = klas_gemiddelden_per_wp(df, opleiding, str(student["cohort"]), wp_cols)

    for kt_col in kt_cols:
        kt_eigen_wp = _wp_van_kt(kt_col)
        if not kt_eigen_wp or all(pd.isna(student.get(w, float("nan"))) for w in kt_eigen_wp):
            continue

        metingen = laatste_twee_metingen_per_wp(studentnummer, kt_eigen_wp)
        labels = [oer_label(opleiding, w, crebo) for w in kt_eigen_wp]
        huidig = [metingen[w][0] if metingen[w][0] is not None else 0 for w in kt_eigen_wp]
        vorig = [metingen[w][1] for w in kt_eigen_wp]
        heeft_vorig = any(v is not None for v in vorig)
        klas = [klas_gem.get(w, float("nan")) for w in kt_eigen_wp]
        heeft_klas = any(not pd.isna(k) for k in klas)

        if not any(metingen[w][0] is not None for w in kt_eigen_wp):
            st.info(
                f"Nog geen metingen voor *{oer_label(opleiding, kt_col, crebo)}* — "
                "sla je beoordeling op om het spinneweb te zien."
            )
            continue

        fig = go.Figure()
        # Sluit de polygon: voeg eerste punt aan einde toe
        fig.add_trace(
            go.Scatterpolar(
                r=huidig + [huidig[0]],
                theta=labels + [labels[0]],
                fill="toself",
                name="Huidige meting",
                line={"color": "#27ae60"},
                fillcolor="rgba(39, 174, 96, 0.25)",
            )
        )
        if heeft_vorig:
            vorig_voor_plot = [v if v is not None else 0 for v in vorig]
            fig.add_trace(
                go.Scatterpolar(
                    r=vorig_voor_plot + [vorig_voor_plot[0]],
                    theta=labels + [labels[0]],
                    fill="none",
                    name="Vorige meting",
                    line={"color": "#e67e22", "dash": "dash"},
                )
            )
        if heeft_klas:
            klas_voor_plot = [0 if pd.isna(k) else float(k) for k in klas]
            fig.add_trace(
                go.Scatterpolar(
                    r=klas_voor_plot + [klas_voor_plot[0]],
                    theta=labels + [labels[0]],
                    fill="none",
                    name="Klasgemiddelde",
                    line={"color": "#2980b9", "dash": "dot"},
                )
            )
        fig.update_layout(
            polar={"radialaxis": {"visible": True, "range": [0, 100]}},
            showlegend=True,
            title=oer_label(opleiding, kt_col, crebo),
            height=420,
            margin={"l": 40, "r": 40, "t": 60, "b": 40},
        )
        st.plotly_chart(fig, use_container_width=True)

render_footer()
