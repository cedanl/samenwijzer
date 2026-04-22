"""OER-ingestie pipeline: parse → extraheer → chunk → embed → sla op."""

import re
from pathlib import Path


# ── Bestandsnaam parsen ───────────────────────────────────────────────────────

_CREBO_PATROON = re.compile(r"(\d{5})\s*[-_]?\s*(BOL|BBL)\s*[-_]?\s*(\d{4})", re.IGNORECASE)


def parseer_bestandsnaam(bestandsnaam: str) -> dict | None:
    """Haal crebo, leerweg en cohort op uit de bestandsnaam.

    Ondersteunt patronen zoals:
    - 25168BOL2025Examenplan.pdf
    - 25655 BBL 2024 OER.pdf
    Geeft None als er geen match is.
    """
    m = _CREBO_PATROON.search(bestandsnaam)
    if not m:
        return None
    return {
        "crebo": m.group(1),
        "leerweg": m.group(2).upper(),
        "cohort": m.group(3),
    }


# ── Tekst chunken ─────────────────────────────────────────────────────────────

def chunk_tekst(tekst: str, chunk_grootte: int = 500, overlap: int = 50) -> list[str]:
    """Splits tekst in chunks van ~chunk_grootte woorden met overlap."""
    woorden = tekst.split()
    if len(woorden) <= chunk_grootte:
        return [tekst]

    chunks = []
    start = 0
    while start < len(woorden):
        einde = min(start + chunk_grootte, len(woorden))
        chunk = " ".join(woorden[start:einde])
        chunks.append(chunk)
        if einde >= len(woorden):
            break
        start += chunk_grootte - overlap
    return chunks


# ── Kerntaken extraheren ──────────────────────────────────────────────────────

_KT_PATROON = re.compile(
    r"^\s*(B\d+-K\d+(?:-W\d+)?|Kerntaak\s+\d+|Werkproces\s+\d+\.\d+)"
    r"\s*[:\-–]?\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)


def extraheer_kerntaken(tekst: str) -> list[dict]:
    """Haal kerntaken en werkprocessen uit OER-tekst via regex."""
    if not tekst:
        return []

    resultaten = []
    volgorde = 0
    for m in _KT_PATROON.finditer(tekst):
        code = m.group(1).strip()
        naam = m.group(2).strip()[:200]
        code_lower = code.lower()

        if "werkproces" in code_lower or re.match(r"B\d+-K\d+-W\d+", code):
            type_ = "werkproces"
        else:
            type_ = "kerntaak"

        resultaten.append({"code": code, "naam": naam, "type": type_, "volgorde": volgorde})
        volgorde += 1

    return resultaten
