"""Image-hygiëne: bronmateriaal en ongeredigeerde originelen horen niet in het Fly-image."""

from __future__ import annotations

from pathlib import Path

_DOCKERIGNORE = Path(__file__).resolve().parents[2] / ".dockerignore"


def _regels() -> list[str]:
    return [r.strip() for r in _DOCKERIGNORE.read_text(encoding="utf-8").splitlines()]


def test_dockerignore_sluit_bronmateriaal_uit():
    """`Dockerfile.fastapi` doet `COPY oeren/`; `_bronmateriaal/` (ongeïndexeerd, kan
    personeelsgegevens bevatten) mag daardoor niet in het image terechtkomen."""
    assert "**/_bronmateriaal/" in _regels()


def test_dockerignore_sluit_ongeredigeerde_originelen_uit():
    """Geplande `_documenten/**/origineel/`-mappen (spec flexibele documentlaag) blijven buiten."""
    assert "**/_documenten/**/origineel/" in _regels()
