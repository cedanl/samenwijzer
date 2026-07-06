"""Welzijn — placeholder; wordt gevuld door de paginamigratie."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app_fastapi.auth import eis_rol, sessie_context
from app_fastapi.templating import templates

router = APIRouter()


@router.get("/welzijn")
def welzijn_home(request: Request):
    redirect = eis_rol(request, "student", "docent")
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request, "in_aanbouw.html", {**sessie_context(request), "titel": "Welzijn"}
    )
