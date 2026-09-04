"""Gedeelde Jinja2-templates-instantie (aparte module tegen circulaire imports)."""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

_HIER = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=_HIER / "templates")
