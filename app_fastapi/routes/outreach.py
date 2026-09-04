"""Outreach — mentorwerklijst, campagnebeheer en effectiviteit (docent-only)."""

from __future__ import annotations

import json
import smtplib
from datetime import datetime

import anthropic  # alleen voor except-clausules; geen client-instantiatie hier
import pandas as pd
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, StreamingResponse

from app_fastapi import data
from app_fastapi.auth import eis_rol, sessie_context
from app_fastapi.templating import templates
from samenwijzer.analyze import detecteer_transitiemoment, transitiemoment_label
from samenwijzer.outreach import (
    at_risk_studenten,
    bereken_effectiviteit,
    bsa_percentage,
    email_config_uit_env,
    genereer_outreach_bericht,
    interventie_log,
    interventies_per_mentor,
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
    get_student_status,
    log_interventie,
    maak_campagne,
    sluit_campagne,
    upsert_status,
)
from samenwijzer.welzijn import CATEGORIEËN, categorie_label

router = APIRouter()

_STATUSSEN = ("niet_gecontacteerd", "gecontacteerd", "gereageerd", "opgelost")
_TONEN = ("vriendelijk", "zakelijk", "motiverend")
_TRANSITIEMOMENTEN = ("bsa_risico", "bijna_klaar")

_STATUS_KLASSE = {
    "niet_gecontacteerd": "niet-gecontacteerd",
    "gecontacteerd": "gecontacteerd",
    "gereageerd": "gereageerd",
    "opgelost": "opgelost",
}

_MELDINGEN: dict[str, tuple[str, str]] = {
    "status_opgeslagen": ("Status opgeslagen.", "ok"),
    "mail_verstuurd": ("E-mail verstuurd.", "ok"),
    "mail_mislukt": ("Verzenden mislukt — controleer de SMTP-instellingen.", "error"),
    "geen_email": ("Vul een e-mailadres in.", "error"),
    "geen_bericht": ("Er is nog geen bericht opgesteld.", "error"),
    "smtp_niet_klaar": (
        "Configureer SMTP_HOST, SMTP_USER en SMTP_PASSWORD in .env.",
        "error",
    ),
    "onbekende_student": ("Deze student hoort niet bij jouw mentorgroep.", "error"),
    "campagne_aangemaakt": ("Campagne aangemaakt.", "ok"),
    "campagne_afgesloten": ("Campagne afgesloten.", "ok"),
    "geen_naam": ("Geef de campagne een naam.", "error"),
    "geen_template": ("Vul een berichttemplate in.", "error"),
}


def _kaal_transitielabel(moment: str) -> str:
    """Transitiemoment-label zonder emoji (voor selectopties, zoals in Streamlit)."""
    return transitiemoment_label(moment).replace("⚠️ ", "").replace("🎓 ", "")


def _mentor_at_risk(request: Request) -> pd.DataFrame:
    """At-risk studenten binnen de eigen mentorgroep."""
    return at_risk_studenten(data.mentor_df(request.session.get("mentor_naam", "")))


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# ── Hoofdpagina ───────────────────────────────────────────────────────────────
@router.get("/outreach")
def outreach_home(request: Request, tab: str = "werklijst", melding: str = ""):
    redirect = eis_rol(request, "docent")
    if redirect:
        return redirect

    at_risk = _mentor_at_risk(request)
    statussen = get_alle_statussen()
    smtp = email_config_uit_env()
    smtp_klaar = all(smtp[k] for k in ("smtp_host", "smtp_user", "smtp_password"))

    # Bulk-fetch van alle interventies — voorkomt N+1 queries in de loop
    alle_interventies = get_alle_interventies()
    interventies_per_student: dict[str, list[Interventie]] = {}
    for iv in alle_interventies:
        interventies_per_student.setdefault(iv.studentnummer, []).append(iv)

    werklijst = []
    for _, student in at_risk.iterrows():
        snr = str(student["studentnummer"])
        opgeslagen = statussen.get(
            snr, StudentStatus(studentnummer=snr, status="niet_gecontacteerd")
        )
        moment = detecteer_transitiemoment(student)
        voortgang_pct = int(student["voortgang"] * 100)
        werklijst.append(
            {
                "snr": snr,
                "naam": str(student["naam"]),
                "voornaam": str(student["naam"]).split()[0],
                "opleiding": str(student["opleiding"]),
                "niveau": student["niveau"],
                "voortgang_pct": voortgang_pct,
                "bsa_behaald": int(student["bsa_behaald"]),
                "bsa_vereist": int(student["bsa_vereist"]),
                "status": opgeslagen,
                "status_klasse": _STATUS_KLASSE.get(opgeslagen.status, "niet-gecontacteerd"),
                "moment_label": transitiemoment_label(moment),
                "expanded": voortgang_pct < 30,
                "interventies": interventies_per_student.get(snr, [])[:3],
                "interventies_totaal": len(interventies_per_student.get(snr, [])),
            }
        )

    campagnes = get_alle_campagnes()
    actief = [c for c in campagnes if c.status == "actief"]
    afgesloten = [c for c in campagnes if c.status == "afgesloten"]

    effectiviteit = None
    if alle_interventies:
        log_df = interventie_log(alle_interventies)
        metrics = bereken_effectiviteit(list(statussen.values()), len(at_risk))
        effectiviteit = {
            "metrics": metrics,
            "totaal_interventies": len(log_df),
            "trechter": [
                ("At-risk", metrics.totaal_at_risk),
                ("Gecontacteerd", metrics.gecontacteerd),
                ("Gereageerd", metrics.gereageerd),
                ("Opgelost", metrics.opgelost),
            ],
            "mentor_counts": interventies_per_mentor(log_df).to_dict("records"),
            "log": log_df.to_dict("records"),
        }

    tekst, klasse = _MELDINGEN.get(melding, ("", ""))
    return templates.TemplateResponse(
        request,
        "outreach.html",
        {
            **sessie_context(request),
            "tab": tab if tab in ("werklijst", "campagnes", "effectiviteit") else "werklijst",
            "melding_tekst": tekst,
            "melding_klasse": klasse,
            "aantal_at_risk": len(at_risk),
            "werklijst": werklijst,
            "statussen_opties": _STATUSSEN,
            "tonen": _TONEN,
            "smtp_klaar": smtp_klaar,
            "verwijzingen": {
                cat: {"label": categorie_label(cat), **suggereer_verwijzing(cat)}
                for cat in CATEGORIEËN
            },
            "campagnes_actief": actief,
            "campagnes_afgesloten": afgesloten,
            "transitiemoment_opties": [(m, _kaal_transitielabel(m)) for m in _TRANSITIEMOMENTEN],
            "transitiemoment_label": transitiemoment_label,
            "effectiviteit": effectiviteit,
        },
    )


# ── Werklijst-actie: status opslaan of e-mail versturen ──────────────────────
@router.post("/outreach/werklijst")
def outreach_werklijst_actie(
    request: Request,
    actie: str = Form(...),
    studentnummer: str = Form(...),
    status: str = Form("niet_gecontacteerd"),
    bericht: str = Form(""),
    notitie: str = Form(""),
    email: str = Form(""),
):
    redirect = eis_rol(request, "docent")
    if redirect:
        return redirect

    def terug(melding: str) -> RedirectResponse:
        return RedirectResponse(f"/outreach?melding={melding}#student-{studentnummer}", 303)

    at_risk = _mentor_at_risk(request)
    sel = at_risk[at_risk["studentnummer"].astype(str) == str(studentnummer)]
    if sel.empty:
        return RedirectResponse("/outreach?melding=onbekende_student", status_code=303)
    student = sel.iloc[0]
    mentor_naam = str(request.session.get("mentor_naam", "")).strip()

    if actie == "mailen":
        smtp = email_config_uit_env()
        if not all(smtp[k] for k in ("smtp_host", "smtp_user", "smtp_password")):
            return terug("smtp_niet_klaar")
        if not email.strip():
            return terug("geen_email")
        if not bericht.strip():
            return terug("geen_bericht")
        try:
            verstuur_email(
                ontvanger_email=email.strip(),
                onderwerp=f"Uitnodiging gesprek — {student['naam']}",
                bericht=bericht,
                smtp_host=smtp["smtp_host"],
                smtp_port=smtp["smtp_port"],
                smtp_user=smtp["smtp_user"],
                smtp_password=smtp["smtp_password"],
                afzender_email=smtp["afzender_email"],
            )
        except smtplib.SMTPException:
            return terug("mail_mislukt")
        return terug("mail_verstuurd")

    # actie == "opslaan" (default)
    if status not in _STATUSSEN:
        status = "niet_gecontacteerd"
    nu = datetime.now().isoformat()
    status_voor = get_student_status(str(studentnummer)).status
    upsert_status(
        StudentStatus(
            studentnummer=str(studentnummer),
            status=status,
            laatste_contact=nu,
            laatste_mentor=mentor_naam or None,
            notitie=notitie.strip() or None,
        )
    )
    if bericht.strip():
        log_interventie(
            Interventie(
                studentnummer=str(studentnummer),
                timestamp=nu,
                mentor=mentor_naam or "onbekend",
                status_voor=status_voor,
                status_na=status,
                bericht_samenvatting=bericht[:500],
                voortgang_op_moment=float(student["voortgang"]),
                bsa_percentage_op_moment=bsa_percentage(
                    float(student["bsa_behaald"]), float(student["bsa_vereist"])
                ),
            )
        )
    return terug("status_opgeslagen")


# ── AI-conceptbericht (SSE-stream) ────────────────────────────────────────────
@router.post("/outreach/api/bericht")
async def outreach_genereer_bericht(request: Request):
    redirect = eis_rol(request, "docent")
    if redirect:
        return redirect

    body = await request.json()
    studentnummer = str(body.get("studentnummer", ""))
    toon = body.get("toon", "vriendelijk")
    if toon not in _TONEN:
        toon = "vriendelijk"
    categorie = body.get("verwijzing_categorie")
    verwijzing = suggereer_verwijzing(categorie) if categorie in CATEGORIEËN else None

    at_risk = _mentor_at_risk(request)
    sel = at_risk[at_risk["studentnummer"].astype(str) == studentnummer]
    if sel.empty:
        return StreamingResponse(
            iter([_sse({"error": "onbekende student"})]), media_type="text/event-stream"
        )
    student = sel.iloc[0]
    mentor_naam = str(request.session.get("mentor_naam", ""))

    def stream():
        try:
            for chunk in genereer_outreach_bericht(
                student, mentor_naam, toon, verwijzing=verwijzing
            ):
                yield _sse({"chunk": chunk})
            yield _sse({"done": True})
        except anthropic.APITimeoutError:
            yield _sse({"error": "timeout"})
        except anthropic.AnthropicError:
            yield _sse({"error": "AI-dienst niet bereikbaar"})

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── Campagnes ─────────────────────────────────────────────────────────────────
@router.post("/outreach/campagne")
def outreach_maak_campagne(
    request: Request,
    naam: str = Form(""),
    transitiemoment: str = Form("bsa_risico"),
    bericht_template: str = Form(""),
):
    redirect = eis_rol(request, "docent")
    if redirect:
        return redirect
    if not naam.strip():
        return RedirectResponse("/outreach?tab=campagnes&melding=geen_naam", status_code=303)
    if not bericht_template.strip():
        return RedirectResponse("/outreach?tab=campagnes&melding=geen_template", status_code=303)
    if transitiemoment not in _TRANSITIEMOMENTEN:
        transitiemoment = "bsa_risico"
    maak_campagne(
        Campagne(
            naam=naam.strip(),
            transitiemoment=transitiemoment,
            bericht_template=bericht_template.strip(),
            aangemaakt_door=request.session.get("mentor_naam") or "onbekend",
            aangemaakt_op=datetime.now().isoformat(),
        )
    )
    return RedirectResponse("/outreach?tab=campagnes&melding=campagne_aangemaakt", status_code=303)


@router.post("/outreach/campagne/{campagne_id}/sluiten")
def outreach_sluit_campagne(request: Request, campagne_id: int):
    redirect = eis_rol(request, "docent")
    if redirect:
        return redirect
    sluit_campagne(campagne_id)
    return RedirectResponse("/outreach?tab=campagnes&melding=campagne_afgesloten", status_code=303)
