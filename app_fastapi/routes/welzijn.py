"""Welzijn — studentenzelfcheck met AI-reactie (student-only)."""

from __future__ import annotations

import json
from datetime import datetime

import anthropic  # alleen voor except-clausules; geen client-instantiatie hier
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, StreamingResponse

from app_fastapi import data
from app_fastapi.auth import eis_rol, sessie_context
from app_fastapi.templating import templates
from samenwijzer.outreach_store import (
    WelzijnsCheck,
    get_welzijnschecks_student,
    sla_welzijnscheck_op,
)
from samenwijzer.welzijn import (
    CATEGORIEËN,
    categorie_label,
    genereer_welzijnsreactie,
    stuur_welzijn_notificatie,
    urgentie_label,
)

router = APIRouter()

_URGENTIES = (1, 2, 3)

_MELDINGEN: dict[str, tuple[str, str]] = {
    "verstuurd_mail": (
        "Je check is verstuurd. Je mentor heeft een e-mailmelding ontvangen.",
        "ok",
    ),
    "verstuurd": ("Je check is verstuurd. Je mentor wordt op de hoogte gesteld.", "ok"),
}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _student_naam_en_mentor(studentnummer: str) -> tuple[str, str, str]:
    """Geef (voornaam, volledige naam, mentor) terug, met graceful fallback."""
    rij = data.student_row(studentnummer)
    if rij is None:
        return studentnummer, studentnummer, ""
    naam = str(rij["naam"])
    return naam.split()[0], naam, str(rij["mentor"])


# ── Hoofdpagina: formulier + eerdere checks ──────────────────────────────────
@router.get("/welzijn")
def welzijn_home(request: Request, melding: str = "", check_id: int = 0):
    redirect = eis_rol(request, "student")
    if redirect:
        return redirect

    studentnummer = str(request.session["studentnummer"])
    voornaam, _, _ = _student_naam_en_mentor(studentnummer)

    eerdere = get_welzijnschecks_student(studentnummer)
    nieuwe_check = next((c for c in eerdere if c.id == check_id), None) if check_id else None

    tekst, klasse = _MELDINGEN.get(melding, ("", ""))
    return templates.TemplateResponse(
        request,
        "welzijn.html",
        {
            **sessie_context(request),
            "titel": "Welzijn",
            "voornaam": voornaam,
            "categorieen": [{"value": c, "label": categorie_label(c)} for c in CATEGORIEËN],
            "urgenties": [{"value": u, "label": urgentie_label(u)} for u in _URGENTIES],
            "melding_tekst": tekst,
            "melding_klasse": klasse,
            "nieuwe_check": nieuwe_check,
            "eerdere": [
                {
                    "timestamp": c.timestamp,
                    "categorie_label": categorie_label(c.categorie),
                    "urgentie_label": urgentie_label(c.urgentie),
                    "toelichting": c.toelichting,
                }
                for c in eerdere[:5]
            ],
        },
    )


# ── Check versturen (PRG: opslaan + mailen, dan redirect) ────────────────────
@router.post("/welzijn")
def welzijn_versturen(
    request: Request,
    categorie: str = Form(...),
    toelichting: str = Form(""),
    urgentie: int = Form(1),
):
    redirect = eis_rol(request, "student")
    if redirect:
        return redirect

    if categorie not in CATEGORIEËN:
        categorie = CATEGORIEËN[0]
    if urgentie not in _URGENTIES:
        urgentie = 1

    studentnummer = str(request.session["studentnummer"])
    _, student_naam, mentor_naam = _student_naam_en_mentor(studentnummer)
    toelichting = toelichting.strip()

    check = WelzijnsCheck(
        studentnummer=studentnummer,
        timestamp=datetime.now().isoformat(),
        categorie=categorie,
        toelichting=toelichting,
        urgentie=urgentie,
    )
    check_id = sla_welzijnscheck_op(check)

    verstuurd = stuur_welzijn_notificatie(
        student_naam=student_naam,
        mentor_naam=mentor_naam,
        categorie=categorie,
        urgentie=urgentie,
        toelichting=toelichting,
        timestamp=check.timestamp,
    )
    melding = "verstuurd_mail" if verstuurd else "verstuurd"
    return RedirectResponse(f"/welzijn?melding={melding}&check_id={check_id}", status_code=303)


# ── AI-reactie op de zojuist verstuurde check (SSE-stream) ───────────────────
@router.post("/welzijn/reactie")
async def welzijn_reactie(request: Request):
    redirect = eis_rol(request, "student")
    if redirect:
        return redirect

    body = await request.json()
    check_id = body.get("check_id")
    studentnummer = str(request.session["studentnummer"])

    # Alleen eigen checks van de student in sessie — privacy-grens.
    eigen_checks = get_welzijnschecks_student(studentnummer)
    check = next((c for c in eigen_checks if c.id == check_id), None)
    if check is None:
        return StreamingResponse(
            iter([_sse({"error": "onbekende check"})]), media_type="text/event-stream"
        )

    voornaam, _, _ = _student_naam_en_mentor(studentnummer)

    def stream():
        try:
            for chunk in genereer_welzijnsreactie(
                voornaam, check.categorie, check.toelichting, check.urgentie
            ):
                yield _sse({"chunk": chunk})
            yield _sse({"done": True})
        except anthropic.APITimeoutError:
            yield _sse({"error": "timeout"})
        except anthropic.AnthropicError:
            yield _sse({"error": "AI-dienst niet bereikbaar"})

    return StreamingResponse(stream(), media_type="text/event-stream")
