"""Samenwijzer FastAPI-frontend — login, home per rol, en feature-routers.

Lokaal draaien (naast Streamlit op 8501):
    uv run uvicorn app_fastapi.main:app --port 8505 --reload
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app_fastapi import data
from app_fastapi.auth import sessie_context, wachtwoord_ok
from app_fastapi.routes import (
    groeidossier,
    groepsoverzicht,
    leercoach,
    outreach,
    voortgang,
    welzijn,
)
from app_fastapi.templating import templates
from samenwijzer.whatsapp import stuur_verificatie
from samenwijzer.whatsapp_store import heeft_actieve_registratie, registreer_nummer

load_dotenv()
log = logging.getLogger("samenwijzer_web")

_HIER = Path(__file__).resolve().parent
app = FastAPI(title="Samenwijzer")

# Lokale dev-app (geen productie-deploy van de hoofd-app) → dev-default toegestaan,
# maar zet SESSION_SECRET in .env voor elke niet-lokale omgeving.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-secret-samenwijzer"),
    https_only=os.environ.get("COOKIE_HTTPS_ONLY", "0") != "0",
    same_site="lax",
)
app.mount("/static", StaticFiles(directory=_HIER / "static"), name="static")

for feature_router in (
    voortgang.router,
    groepsoverzicht.router,
    leercoach.router,
    outreach.router,
    welzijn.router,
    groeidossier.router,
):
    app.include_router(feature_router)


# ── Login ─────────────────────────────────────────────────────────────────────
@app.get("/")
def index(request: Request, fout: int = 0):
    if request.session.get("rol"):
        return RedirectResponse("/home", status_code=303)
    df = data.get_df()
    studenten = (
        df.sort_values("naam")[["naam", "studentnummer"]]
        .apply(lambda r: {"naam": r["naam"], "studentnummer": str(r["studentnummer"])}, axis=1)
        .tolist()
    )
    mentoren = sorted(df["mentor"].unique().tolist())
    return templates.TemplateResponse(
        request,
        "login.html",
        {"studenten": studenten, "mentoren": mentoren, "fout": bool(fout), "rol": None},
    )


@app.post("/login")
def login_post(
    request: Request,
    rol: str = Form(...),
    identifier: str = Form(...),
    wachtwoord: str = Form(...),
):
    if not wachtwoord_ok(wachtwoord):
        return RedirectResponse("/?fout=1", status_code=303)
    request.session.clear()
    if rol == "student":
        if data.student_row(identifier) is None:
            return RedirectResponse("/?fout=1", status_code=303)
        request.session["rol"] = "student"
        request.session["studentnummer"] = identifier
    elif rol == "docent":
        if identifier not in set(data.get_df()["mentor"]):
            return RedirectResponse("/?fout=1", status_code=303)
        request.session["rol"] = "docent"
        request.session["mentor_naam"] = identifier
    else:
        return RedirectResponse("/?fout=1", status_code=303)
    return RedirectResponse("/home", status_code=303)


@app.get("/uitloggen")
def uitloggen(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# ── Home per rol ──────────────────────────────────────────────────────────────
@app.get("/home")
def home(request: Request, whatsapp: str = ""):
    ctx = sessie_context(request)
    if ctx["rol"] == "student":
        student = data.student_row(ctx["studentnummer"])
        if student is None:
            request.session.clear()
            return RedirectResponse("/", status_code=303)
        snr = str(student["studentnummer"])
        behaald = int(student["bsa_behaald"])
        vereist = int(student["bsa_vereist"])
        return templates.TemplateResponse(
            request,
            "home_student.html",
            {
                **ctx,
                "student": student,
                "voornaam": str(student["naam"]).split()[0],
                "voortgang_pct": int(student["voortgang"] * 100),
                "bsa_behaald": behaald,
                "bsa_vereist": vereist,
                "bsa_progress": behaald / vereist if vereist else 0.0,
                "toon_whatsapp_optin": not heeft_actieve_registratie(snr),
                "whatsapp_status": whatsapp,
            },
        )
    if ctx["rol"] == "docent":
        eigen = data.mentor_df(ctx["mentor_naam"])
        totaal = len(eigen)
        risico = int(eigen["risico"].sum())
        return templates.TemplateResponse(
            request,
            "home_docent.html",
            {
                **ctx,
                "voornaam": ctx["mentor_naam"].split()[0] if ctx["mentor_naam"] else "mentor",
                "totaal": totaal,
                "risico": risico,
                "op_schema": totaal - risico,
                "risico_pct": round(risico / totaal * 100) if totaal else 0,
                "gem_voortgang": int(eigen["voortgang"].mean() * 100) if totaal else 0,
            },
        )
    return RedirectResponse("/", status_code=303)


# ── WhatsApp opt-in (studenten-home) ─────────────────────────────────────────
@app.post("/whatsapp/optin")
def whatsapp_optin(request: Request, nummer: str = Form(""), akkoord: str = Form("")):
    if request.session.get("rol") != "student":
        return RedirectResponse("/", status_code=303)
    snr = str(request.session["studentnummer"])
    nummer = nummer.strip()
    if not nummer.startswith("+") or len(nummer) < 10:
        return RedirectResponse("/home?whatsapp=ongeldig", status_code=303)
    if not akkoord:
        return RedirectResponse("/home?whatsapp=geen_akkoord", status_code=303)
    try:
        registreer_nummer(snr, nummer)
        stuur_verificatie(nummer)
        return RedirectResponse("/home?whatsapp=verstuurd", status_code=303)
    except OSError:
        registreer_nummer(snr, nummer)
        return RedirectResponse("/home?whatsapp=geen_twilio", status_code=303)
