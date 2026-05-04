"""OER-parsing helpers: bestandsnaam, kerntaken, opleidingsnaam, niveau.

Synced from validatie_samenwijzer/src/validatie_samenwijzer/ingest.py @ d64f3cf.
Houd functioneel gelijk; verschilt alleen waar samenwijzer geen ingest-pijplijn heeft.
"""

from __future__ import annotations

import re

# ── Bestandsnaam parsen ───────────────────────────────────────────────────────

_CREBO_LEERWEG_JAAR = re.compile(
    r"(?<!\d)(\d{5})\s*[-_]?\s*(BOL|BBL)(?:BOL|BBL)?\s*[-_]?\s*(\d{4})", re.IGNORECASE
)
_CREBO = re.compile(r"(?<!\d)(\d{5})(?!\d)")
_LEERWEG = re.compile(r"\b(BOL|BBL)\b", re.IGNORECASE)
_JAAR = re.compile(r"(?<!\d)(20[2-3]\d)(?!\d)")
_HUIDIG_COHORT = "2025"


def parseer_bestandsnaam(bestandsnaam: str) -> dict | None:
    """Haal crebo, leerweg en cohort op uit de bestandsnaam.

    Ondersteunt:
    - Da Vinci:     25168BOL2025Examenplan.pdf
    - Rijn IJssel:  content_oer-2024-2025-ci-25651-acteur.pdf
    - Talland:      25180 Kok 24 maanden BBL.pdf
    Geeft None als er geen 5-cijferig crebo gevonden wordt.
    """
    m = _CREBO_LEERWEG_JAAR.search(bestandsnaam)
    if m:
        return {"crebo": m.group(1), "leerweg": m.group(2).upper(), "cohort": m.group(3)}

    crebo_m = _CREBO.search(bestandsnaam)
    if not crebo_m:
        return None

    crebo = crebo_m.group(1)
    leerweg_m = _LEERWEG.search(bestandsnaam)
    leerweg = leerweg_m.group(1).upper() if leerweg_m else "BOL"
    jaar_m = _JAAR.search(bestandsnaam)
    cohort = jaar_m.group(1) if jaar_m else _HUIDIG_COHORT
    return {"crebo": crebo, "leerweg": leerweg, "cohort": cohort}


# ── Kerntaken extraheren ──────────────────────────────────────────────────────

_KT_PATROON = re.compile(
    r"^\s*(B\d+-K\d+(?:-W\d+)?|Kerntaak\s+\d+|Werkproces\s+\d+\.\d+)"
    r"\s*[:\-–]?\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)


def extraheer_kerntaken(tekst: str) -> list[dict]:
    """Haal kerntaken en werkprocessen uit OER-tekst via regex.

    Returns:
        Lijst van dicts met sleutels: code, naam, type ('kerntaak'|'werkproces'), volgorde.
    """
    if not tekst:
        return []

    resultaten = []
    volgorde = 0
    for m in _KT_PATROON.finditer(tekst):
        code = m.group(1).strip()
        naam = m.group(2).strip()[:200]
        if "werkproces" in code.lower() or re.match(r"B\d+-K\d+-W\d+", code):
            type_ = "werkproces"
        else:
            type_ = "kerntaak"
        resultaten.append({"code": code, "naam": naam, "type": type_, "volgorde": volgorde})
        volgorde += 1
    return resultaten


# ── Opleidingsnaam-extractie ──────────────────────────────────────────────────

_STOP_TOKENS = {
    "oer", "mjp", "tik", "ci", "examenplan", "examenplannen", "examenreglement",
    "addendum", "cohort", "bol", "bbl", "bolbbl", "vanaf", "voor", "en", "van",
    "de", "het", "te", "op", "een", "in", "ig", "n2", "n3", "n4", "d1", "d2",
    "v1", "v2", "v3", "def",
    "maanden", "jaar", "jaren", "uur",
}

_HASH_PATROON = re.compile(r"^[a-zA-Z0-9]{6,}$")
_KLINKER_PATROON = re.compile(r"[aeiou]", re.IGNORECASE)


def extraheer_opleidingsnaam(bestandsnaam: str) -> str | None:
    """Heuristiek: leid opleidingsnaam af uit bestandsnaam.

    Strategie:
      1. Strip extensie en alles vóór '__' (zodat metadata-prefix wegvalt).
      2. Splits op _, -, spaties.
      3. Filter weg: digits, jaartallen, BOL/BBL, OER/MJP/Examenplan-tokens,
         hash-achtige tokens (≥6 chars zonder klinkers), 1-letter tokens.
      4. Title-case, max 4 woorden.

    Returns:
        Schone opleidingsnaam, of None als er onvoldoende woorden overblijven.
    """
    naam = bestandsnaam.rsplit(".", 1)[0]  # strip .md/.pdf
    if "__" in naam:
        naam = naam.split("__", 1)[1]

    # Split CamelCase/digit-letter boundaries before tokenising (e.g. "25775BOL2025Examenplan")
    naam = re.sub(r"(?<=\d)(?=[a-zA-Z])|(?<=[a-zA-Z])(?=\d)", " ", naam)
    tokens = re.split(r"[_\-\s]+", naam)
    woorden: list[str] = []
    for t in tokens:
        t = t.strip().lower()
        if not t or len(t) < 2:
            continue
        if t.isdigit():
            continue
        if t in _STOP_TOKENS:
            continue
        if _HASH_PATROON.match(t) and not _KLINKER_PATROON.search(t):
            continue
        woorden.append(t)

    if not woorden:
        return None
    return " ".join(w.title() for w in woorden[:4])


# ── Niveau-extractie ──────────────────────────────────────────────────────────

_NIVEAU_BESTANDSNAAM = re.compile(r"N([234])(?!\d)", re.IGNORECASE)
_NIVEAU_TEKST = re.compile(
    r"\b(?:MBO[\s-]+)?[Nn]iveau\s*([234])\b"
)


def bepaal_niveau(bestandsnaam: str, tekst: str) -> int | None:
    """Bepaal opleidingsniveau (2/3/4) uit bestandsnaam-suffix of markdown-tekst.

    Bestandsnaam wint van tekst (suffix als 'N3' is een explicietere markering).
    Geeft None als geen niveau te herleiden is.
    """
    tekst = tekst or ""
    m = _NIVEAU_BESTANDSNAAM.search(bestandsnaam)
    if m:
        return int(m.group(1))
    m = _NIVEAU_TEKST.search(tekst)
    if m:
        return int(m.group(1))
    return None
