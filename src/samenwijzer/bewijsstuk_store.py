"""Filesystem-IO voor bewijsstukken — opslag onder data/bewijsstukken/<studentnummer>/."""

import re
import uuid
from pathlib import Path

_DEFAULT_ROOT = Path(__file__).parent.parent.parent / "data" / "bewijsstukken"

MAX_GROOTTE_BYTES = 10 * 1024 * 1024  # 10 MB
TOEGESTANE_EXTENSIES: frozenset[str] = frozenset(
    {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".xlsx"}
)

_STUDENTNUMMER_PATROON = re.compile(r"^[A-Za-z0-9]{1,20}$")


class BewijsstukFout(ValueError):  # noqa: N818
    """Validatiefout bij opslaan/openen van bewijsstuk."""


def _valideer_studentnummer(studentnummer: str) -> None:
    if not _STUDENTNUMMER_PATROON.match(studentnummer):
        raise BewijsstukFout(f"Ongeldig studentnummer: {studentnummer!r}")


def _resolve_in_root(relatief_pad: str, root: Path) -> Path:
    """Resolve relatief pad onder root; raise BewijsstukFout bij traversal."""
    root = root.resolve()
    abs_pad = (root / relatief_pad).resolve()
    if not abs_pad.is_relative_to(root):
        raise BewijsstukFout(f"Pad {relatief_pad!r} valt buiten bewijsstukken-root")
    return abs_pad


def opslaan(
    studentnummer: str,
    bestandsnaam: str,
    inhoud: bytes,
    root: Path = _DEFAULT_ROOT,
) -> str:
    """Sla een bewijsstuk op onder <root>/<studentnummer>/<uuid>.<ext>.

    Returns:
        Relatief pad t.o.v. root (bv. 'S001/abc-123.pdf') — sla dit op in groei.db.

    Raises:
        BewijsstukFout: Bij ongeldige studentnummer, extensie of grootte.
    """
    _valideer_studentnummer(studentnummer)

    extensie = Path(bestandsnaam).suffix.lower()
    if extensie not in TOEGESTANE_EXTENSIES:
        raise BewijsstukFout(
            f"Bestandsextensie {extensie!r} niet toegestaan. "
            f"Toegestaan: {sorted(TOEGESTANE_EXTENSIES)}"
        )

    if len(inhoud) > MAX_GROOTTE_BYTES:
        raise BewijsstukFout(
            f"Bestand is {len(inhoud)} bytes; maximale grootte is {MAX_GROOTTE_BYTES}."
        )

    student_dir = root / studentnummer
    student_dir.mkdir(parents=True, exist_ok=True)

    nieuwe_naam = f"{uuid.uuid4().hex}{extensie}"
    abs_pad = student_dir / nieuwe_naam
    abs_pad.write_bytes(inhoud)

    return f"{studentnummer}/{nieuwe_naam}"


def open_bestand(relatief_pad: str, root: Path = _DEFAULT_ROOT) -> bytes:
    """Lees een opgeslagen bewijsstuk via zijn relatieve pad.

    Raises:
        BewijsstukFout: Als het pad buiten root valt.
        FileNotFoundError: Als het bestand niet (meer) bestaat.
    """
    abs_pad = _resolve_in_root(relatief_pad, root)
    return abs_pad.read_bytes()


def verwijderen(relatief_pad: str, root: Path = _DEFAULT_ROOT) -> None:
    """Verwijder een bewijsstuk; idempotent als het bestand al weg is.

    Raises:
        BewijsstukFout: Als het pad buiten root valt.
    """
    abs_pad = _resolve_in_root(relatief_pad, root)
    abs_pad.unlink(missing_ok=True)
