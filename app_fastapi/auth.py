"""Sessie-helpers en rol-guards voor de FastAPI-frontend.

Zelfde model als de Streamlit-app: één gedeeld wachtwoord (SHA-256 van
"Welkom123"), rol ∈ {"student", "docent"}, plus studentnummer of mentor_naam.
"""

from __future__ import annotations

import hashlib

from fastapi import Request
from fastapi.responses import RedirectResponse

_WACHTWOORD_HASH = hashlib.sha256(b"Welkom123").hexdigest()


def wachtwoord_ok(wachtwoord: str) -> bool:
    return hashlib.sha256(wachtwoord.encode()).hexdigest() == _WACHTWOORD_HASH


def rol(request: Request) -> str | None:
    return request.session.get("rol")


def eis_rol(request: Request, *rollen: str) -> RedirectResponse | None:
    """Geef een redirect naar de login terug als de sessie-rol niet toegestaan is."""
    if request.session.get("rol") not in rollen:
        return RedirectResponse("/", status_code=303)
    return None


def sessie_context(request: Request) -> dict:
    """Standaard template-context: rol + naam voor nav/hero."""
    return {
        "rol": request.session.get("rol"),
        "studentnummer": request.session.get("studentnummer"),
        "mentor_naam": request.session.get("mentor_naam"),
    }
