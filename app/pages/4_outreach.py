"""Pagina: Outreach — mentorwerklijst en interventielog."""

import smtplib
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from samenwijzer.analyze import detecteer_transitiemoment, transitiemoment_label
from samenwijzer.auth import mentor_filter, vereist_docent
from samenwijzer.outreach import (
    at_risk_studenten,
    email_config_uit_env,
    genereer_outreach_bericht,
    suggereer_verwijzing,
    verstuur_email,
)
from samenwijzer.outreach_store import (
    Campagne,
    Interventie,
    StudentStatus,
    get_alle_campagnes,
    get_alle_interventies,
    get_alle_statussen,
    log_interventie,
    maak_campagne,
    sluit_campagne,
    upsert_status,
)
from samenwijzer.styles import CSS, render_footer, render_nav
from samenwijzer.welzijn import CATEGORIEËN, categorie_label

load_dotenv()

_STATUS_KLASSE = {
    "niet_gecontacteerd": "niet-gecontacteerd",
    "gecontacteerd": "gecontacteerd",
    "gereageerd": "gereageerd",
    "opgelost": "opgelost",
}

st.set_page_config(page_title="Outreach — Samenwijzer", page_icon="📬", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
render_nav()
vereist_docent()
st.title("📬 Outreach")

if "df" not in st.session_state:
    st.warning("Ga eerst naar de [startpagina](/) om de data te laden.")
    st.stop()

df = mentor_filter(st.session_state["df"])
at_risk = at_risk_studenten(df)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_werklijst, tab_campagnes, tab_effectiviteit = st.tabs(
    ["📋 Werklijst", "📣 Campagnes", "📊 Effectiviteit"]
)

# ════════════════════════════════════════════════════════════════════════════
# Tab 1 — Werklijst
# ════════════════════════════════════════════════════════════════════════════
with tab_werklijst:
    statussen = get_alle_statussen()
    smtp = email_config_uit_env()
    smtp_klaar = all(smtp[k] for k in ("smtp_host", "smtp_user", "smtp_password"))

    # Bulk-fetch van alle interventies — voorkomt N+1 queries in de loop
    alle_interventies = get_alle_interventies()
    interventies_per_student: dict[str, list] = {}
    for iv in alle_interventies:
        interventies_per_student.setdefault(iv.studentnummer, []).append(iv)

    st.subheader(f"Studenten die aandacht nodig hebben ({len(at_risk)})")
    st.caption("Studenten met risicovlag, voortgang < 40 % of meer dan 25 % achter op BSA-norm.")

    if at_risk.empty:
        st.success("Geen studenten vereisen op dit moment outreach.")
        st.stop()

    mentor_naam = st.session_state.get("mentor_naam", "")

    st.divider()

    for _, student in at_risk.iterrows():
        snr = student["studentnummer"]
        opgeslagen = statussen.get(
            snr, StudentStatus(studentnummer=snr, status="niet_gecontacteerd")
        )
        status_klasse = _STATUS_KLASSE.get(opgeslagen.status, "niet-gecontacteerd")
        moment = detecteer_transitiemoment(student)
        moment_badge = transitiemoment_label(moment)
        voortgang_pct = int(student["voortgang"] * 100)

        with st.container(border=True):
            col_info, col_actie = st.columns([3, 2])

            with col_info:
                transitie_deel = (
                    f" &nbsp; <span class='badge badge--transitie'>{moment_badge}</span>"
                    if moment_badge
                    else ""
                )
                st.markdown(
                    f"<strong>{student['naam']}</strong> &nbsp; "
                    f"<span class='badge badge--{status_klasse}'>"
                    f"{opgeslagen.status.replace('_', ' ')}</span>"
                    f"{transitie_deel}",
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"{student['opleiding']} · Niveau {student['niveau']} · "
                    f"Voortgang {voortgang_pct} % · "
                    f"BSA {int(student['bsa_behaald'])}/{int(student['bsa_vereist'])} pt"
                )
                if opgeslagen.laatste_contact:
                    st.caption(
                        f"Laatste contact: {opgeslagen.laatste_contact[:10]} "
                        f"door {opgeslagen.laatste_mentor or '—'}"
                    )
                if opgeslagen.notitie:
                    st.caption(f"📝 {opgeslagen.notitie}")

            with col_actie:
                nieuwe_status = st.selectbox(
                    "Status",
                    ("niet_gecontacteerd", "gecontacteerd", "gereageerd", "opgelost"),
                    index=(
                        "niet_gecontacteerd",
                        "gecontacteerd",
                        "gereageerd",
                        "opgelost",
                    ).index(opgeslagen.status),
                    key=f"status_{snr}",
                    label_visibility="collapsed",
                )

        with st.expander(
            f"Bericht opstellen voor {student['naam'].split()[0]}", expanded=(voortgang_pct < 30)
        ):
            col_toon, col_verwijzing = st.columns(2)
            with col_toon:
                toon = st.radio(
                    "Toon",
                    ["vriendelijk", "zakelijk", "motiverend"],
                    horizontal=True,
                    key=f"toon_{snr}",
                )
            with col_verwijzing:
                gebruik_verwijzing = st.checkbox("Verwijzing opnemen", key=f"verw_check_{snr}")
                verwijzing_cat = None
                if gebruik_verwijzing:
                    verwijzing_cat = st.selectbox(
                        "Verwijzen naar",
                        CATEGORIEËN,
                        format_func=categorie_label,
                        key=f"verw_cat_{snr}",
                    )

            verwijzing_info = suggereer_verwijzing(verwijzing_cat) if verwijzing_cat else None

            if verwijzing_info:
                st.info(
                    f"**{verwijzing_info['rol']}** — {verwijzing_info['toelichting']}",
                    icon="ℹ️",
                )

            if st.button("✨ Genereer bericht", key=f"gen_{snr}", type="secondary"):
                if not mentor_naam.strip():
                    st.warning("Vul eerst je naam in bovenaan de pagina.")
                else:
                    with st.spinner("Bericht genereren…"):
                        gegenereerd = st.write_stream(
                            genereer_outreach_bericht(
                                student, mentor_naam, toon, verwijzing=verwijzing_info
                            )
                        )
                    st.session_state[f"bericht_{snr}"] = gegenereerd

            bericht_tekst = st.text_area(
                "Bericht (pas aan indien gewenst)",
                value=st.session_state.get(f"bericht_{snr}", ""),
                height=180,
                key=f"tekst_{snr}",
            )

            notitie = st.text_input(
                "Interne notitie (optioneel)",
                value=opgeslagen.notitie or "",
                key=f"notitie_{snr}",
            )

            col_sla, col_mail = st.columns(2)

            with col_sla:
                if st.button("💾 Sla status op", key=f"save_{snr}", use_container_width=True):
                    nu = datetime.now().isoformat()
                    nieuwe = StudentStatus(
                        studentnummer=snr,
                        status=nieuwe_status,
                        laatste_contact=nu,
                        laatste_mentor=mentor_naam.strip() or None,
                        notitie=notitie.strip() or None,
                    )
                    status_voor = opgeslagen.status
                    upsert_status(nieuwe)

                    if bericht_tekst.strip():
                        log_interventie(
                            Interventie(
                                studentnummer=snr,
                                timestamp=nu,
                                mentor=mentor_naam.strip() or "onbekend",
                                status_voor=status_voor,
                                status_na=nieuwe_status,
                                bericht_samenvatting=bericht_tekst[:500],
                                voortgang_op_moment=float(student["voortgang"]),
                                bsa_percentage_op_moment=float(student["bsa_behaald"])
                                / float(student["bsa_vereist"])
                                if student["bsa_vereist"] > 0
                                else 0.0,
                            )
                        )

                    st.success("Status opgeslagen.")
                    st.rerun()

            with col_mail:
                email_adres = st.text_input(
                    "E-mailadres student",
                    placeholder="student@school.nl",
                    key=f"email_{snr}",
                    label_visibility="collapsed",
                )

                verzend_knop = st.button(
                    "📧 Verstuur e-mail",
                    key=f"mail_{snr}",
                    use_container_width=True,
                    disabled=not smtp_klaar,
                    help="Configureer SMTP_HOST, SMTP_USER en SMTP_PASSWORD in .env"
                    if not smtp_klaar
                    else None,
                )

                if verzend_knop:
                    if not email_adres.strip():
                        st.warning("Vul een e-mailadres in.")
                    elif not bericht_tekst.strip():
                        st.warning("Er is nog geen bericht opgesteld.")
                    else:
                        try:
                            verstuur_email(
                                ontvanger_email=email_adres.strip(),
                                onderwerp=f"Uitnodiging gesprek — {student['naam']}",
                                bericht=bericht_tekst,
                                smtp_host=smtp["smtp_host"],
                                smtp_port=smtp["smtp_port"],
                                smtp_user=smtp["smtp_user"],
                                smtp_password=smtp["smtp_password"],
                                afzender_email=smtp["afzender_email"],
                            )
                            st.success(f"E-mail verstuurd naar {email_adres}.")
                        except smtplib.SMTPException as exc:
                            st.error(f"Verzenden mislukt: {exc}")

            interventies = interventies_per_student.get(snr, [])
            if interventies:
                st.caption(f"**Eerdere interventies ({len(interventies)})**")
                for iv in interventies[:3]:
                    st.caption(
                        f"• {iv.timestamp[:10]} · {iv.mentor} · {iv.status_voor} → {iv.status_na}"
                    )

# ════════════════════════════════════════════════════════════════════════════
# Tab 2 — Campagnes
# ════════════════════════════════════════════════════════════════════════════
with tab_campagnes:
    st.subheader("Campagnes")
    st.caption(
        "Maak gerichte outreach-campagnes aan voor specifieke transitiemomenten. "
        "Gebruik de werklijst om individuele studenten te benaderen."
    )

    mentor_naam_c = st.session_state.get("mentor_naam", "")

    with st.expander("➕ Nieuwe campagne aanmaken", expanded=False):
        camp_naam = st.text_input("Naam campagne", placeholder="BSA-sprint april 2026")
        camp_moment = st.selectbox(
            "Transitiemoment",
            ["bsa_risico", "bijna_klaar"],
            format_func=lambda m: transitiemoment_label(m).replace("⚠️ ", "").replace("🎓 ", ""),
        )
        camp_template = st.text_area(
            "Berichttemplate",
            placeholder=(
                "Beste [naam],\n\n"
                "Ik zie dat je voortgang aandacht vraagt. "
                "Laten we een afspraak maken om je verder te helpen.\n\n"
                "Groeten, [mentor]"
            ),
            height=150,
        )
        if st.button("📣 Maak campagne aan", type="primary"):
            if not camp_naam.strip():
                st.warning("Geef de campagne een naam.")
            elif not camp_template.strip():
                st.warning("Vul een berichttemplate in.")
            else:
                nieuwe_campagne = Campagne(
                    naam=camp_naam.strip(),
                    transitiemoment=camp_moment,
                    bericht_template=camp_template.strip(),
                    aangemaakt_door=mentor_naam_c or "onbekend",
                    aangemaakt_op=datetime.now().isoformat(),
                )
                maak_campagne(nieuwe_campagne)
                st.success(f"Campagne '{camp_naam}' aangemaakt.")
                st.rerun()

    st.divider()

    campagnes = get_alle_campagnes()
    actief = [c for c in campagnes if c.status == "actief"]
    afgesloten = [c for c in campagnes if c.status == "afgesloten"]

    if not campagnes:
        st.info("Nog geen campagnes aangemaakt.")
    else:
        if actief:
            st.markdown("**Actieve campagnes**")
            for camp in actief:
                with st.container(border=True):
                    col_c, col_sluiten = st.columns([4, 1])
                    with col_c:
                        moment_tekst = transitiemoment_label(camp.transitiemoment)
                        st.markdown(
                            f"<strong>{camp.naam}</strong> &nbsp; "
                            f"<span class='badge badge--transitie'>{moment_tekst}</span>",
                            unsafe_allow_html=True,
                        )
                        st.caption(
                            f"Aangemaakt door {camp.aangemaakt_door} op {camp.aangemaakt_op[:10]}"
                        )
                        with st.expander("Berichttemplate"):
                            st.text(camp.bericht_template)
                    with col_sluiten:
                        if st.button("Afsluiten", key=f"sluit_{camp.id}", type="secondary"):
                            sluit_campagne(camp.id)
                            st.rerun()

        if afgesloten:
            with st.expander(f"Afgesloten campagnes ({len(afgesloten)})"):
                for camp in afgesloten:
                    st.caption(
                        f"**{camp.naam}** · {camp.aangemaakt_op[:10]} · "
                        f"{transitiemoment_label(camp.transitiemoment)}"
                    )

# ════════════════════════════════════════════════════════════════════════════
# Tab 3 — Effectiviteit
# ════════════════════════════════════════════════════════════════════════════
with tab_effectiviteit:
    st.subheader("Effectiviteit van interventies")

    alle = get_alle_interventies()
    statussen_alle = get_alle_statussen()

    if not alle:
        st.info("Nog geen interventies geregistreerd.")
    else:
        log_df = pd.DataFrame(
            [
                {
                    "datum": iv.timestamp[:10],
                    "student": iv.studentnummer,
                    "mentor": iv.mentor,
                    "status_voor": iv.status_voor,
                    "status_na": iv.status_na,
                    "voortgang": iv.voortgang_op_moment,
                    "bsa_pct": iv.bsa_percentage_op_moment,
                }
                for iv in alle
            ]
        )

        # ── Overzichtsmetrics ─────────────────────────────────────────────
        totaal_contacten = len(log_df)
        uniek_studenten = log_df["student"].nunique()

        status_teller = {"gecontacteerd": 0, "gereageerd": 0, "opgelost": 0}
        for s in statussen_alle.values():
            if s.status in status_teller:
                status_teller[s.status] += 1

        totaal_at_risk = len(at_risk)
        gecontacteerd_n = sum(
            1
            for s in statussen_alle.values()
            if s.status in ("gecontacteerd", "gereageerd", "opgelost")
        )
        gereageerd_n = sum(
            1 for s in statussen_alle.values() if s.status in ("gereageerd", "opgelost")
        )
        opgelost_n = status_teller["opgelost"]

        contact_rate = gecontacteerd_n / totaal_at_risk * 100 if totaal_at_risk else 0
        respons_rate = gereageerd_n / gecontacteerd_n * 100 if gecontacteerd_n else 0
        oplossing_rate = opgelost_n / gereageerd_n * 100 if gereageerd_n else 0

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(
                f"<div class='stat-card'><p class='stat-card__label'>Totaal interventies</p>"
                f"<p class='stat-card__value'>{totaal_contacten}</p></div>",
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f"<div class='stat-card'><p class='stat-card__label'>Contactratio</p>"
                f"<p class='stat-card__value'>{contact_rate:.0f}%</p>"
                f"<p class='stat-card__sub'>Gecontacteerd / at-risk</p></div>",
                unsafe_allow_html=True,
            )
        with m3:
            st.markdown(
                f"<div class='stat-card'><p class='stat-card__label'>Responsratio</p>"
                f"<p class='stat-card__value'>{respons_rate:.0f}%</p>"
                f"<p class='stat-card__sub'>Gereageerd / gecontacteerd</p></div>",
                unsafe_allow_html=True,
            )
        with m4:
            st.markdown(
                f"<div class='stat-card'><p class='stat-card__label'>Opgelost</p>"
                f"<p class='stat-card__value'>{oplossing_rate:.0f}%</p>"
                f"<p class='stat-card__sub'>Opgelost / gereageerd</p></div>",
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Statustrechter ─────────────────────────────────────────────────
        st.markdown("**Statustrechter**")
        trechter_data = {
            "Fase": ["At-risk", "Gecontacteerd", "Gereageerd", "Opgelost"],
            "Aantal": [totaal_at_risk, gecontacteerd_n, gereageerd_n, opgelost_n],
        }
        trechter_df = pd.DataFrame(trechter_data)
        st.dataframe(
            trechter_df.style.background_gradient(subset=["Aantal"], cmap="Greens"),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        # ── Interventies per mentor ────────────────────────────────────────
        st.markdown("**Interventies per mentor**")
        mentor_counts = (
            log_df.groupby("mentor")
            .agg(interventies=("student", "count"), uniek_studenten=("student", "nunique"))
            .reset_index()
            .rename(
                columns={
                    "mentor": "Mentor",
                    "interventies": "Interventies",
                    "uniek_studenten": "Unieke studenten",
                }
            )
            .sort_values("Interventies", ascending=False)
        )
        st.dataframe(mentor_counts, use_container_width=True, hide_index=True)

        st.divider()

        # ── Volledige log ─────────────────────────────────────────────────
        st.markdown("**Volledige interventielog**")
        st.dataframe(
            log_df.rename(
                columns={
                    "datum": "Datum",
                    "student": "Student",
                    "mentor": "Mentor",
                    "status_voor": "Van",
                    "status_na": "Naar",
                    "voortgang": "Voortgang",
                    "bsa_pct": "BSA %",
                }
            ).style.format({"Voortgang": "{:.0%}", "BSA %": "{:.0%}"}),
            use_container_width=True,
            hide_index=True,
        )

render_footer()
