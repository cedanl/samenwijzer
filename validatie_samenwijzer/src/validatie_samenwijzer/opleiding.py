"""Opleidingsnaam-opschoning — gedeeld tussen UI (styles), ingest en chat.

Leeft los van styles.py zodat backend-modules (chat.py, ingest, scripts) de
opschoning kunnen hergebruiken zonder streamlit te importeren.
"""

from __future__ import annotations

import re

_OPLEIDING_DROP = {
    "oer",
    "mjp",
    "examenplan",
    "examenplannen",
    "addendum",
    "vanaf",
    "cohort",
    "vg",
    "zw",
    "tt",
    "def",
    "vastgesteld",
    "concept",
    "maanden",
    "jaar",
}
_OPLEIDING_KLEIN = {"En", "In", "De", "Van", "Het", "Op", "Of", "Met", "Voor", "Naar", "Te"}


def schoon_opleiding_naam(opleiding: str, crebo: str = "") -> str:
    """Leesbare opleidingsnaam uit het ruwe opleiding-/bestandsnaam-veld.

    De strings verschillen sterk per instelling (Aeres 'Examenplannen X 25-26',
    Curio '25581_oer_00_2025_vg_bol_…', Da Vinci '25099BBL2025MJP-MachinistGrondverzet').
    Token-gebaseerde opschoning: split camelCase + cijfergrenzen, gooi structurele
    tokens weg (crebo, leerweg, jaar, cohort, 'examenplan', 'oer', 'mjp', 'vastgesteld',
    niveau-/versie-codes) en houd de mensleesbare naam over. Valt terug op
    'Opleiding {crebo}' als er geen naam overblijft (de crebo staat sowieso als chip).
    """
    s = opleiding or ""
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", s)  # BOLExamenplan → BOL Examenplan
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)  # camelCase → camel Case
    s = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", s)  # Woord2025 → Woord 2025
    s = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", s)  # 2025Examenplan → 2025 Examenplan
    s = s.replace("_", " ").replace("-", " ")

    tokens: list[str] = []
    for t in s.split():
        tl = t.lower()
        if tl in _OPLEIDING_DROP or (crebo and t == crebo):
            continue
        if re.fullmatch(r"(?:bol|bbl)+", tl):  # leerweg (evt. samengevoegd, bv. BOLBBL)
            continue
        if re.fullmatch(r"\d+", t):  # alle pure-cijfer tokens (jaar/crebo/datum/cohort/niveau)
            continue
        if re.fullmatch(r"v\d+|n[1-4]|n", tl):  # versie / niveau (ook losse 'n' na cijfer-split)
            continue
        tokens.append(t)

    naam = re.sub(r"\s+", " ", " ".join(tokens)).strip()
    # ingesloten lowercase instellings-prefix vóór de TitleCase-naam (seed-data)
    naam = re.sub(r"^(?:[a-z]{3,}\s+)+(?=[A-Z])", "", naam).strip()
    if not naam:
        return f"Opleiding {crebo}" if crebo else "Opleiding"
    if naam == naam.lower():  # volledig lowercase → titel-case
        naam = naam.title()
    woorden = naam.split()  # Nederlandse voegwoorden/lidwoorden klein (behalve eerste)
    return " ".join(
        w if i == 0 or w not in _OPLEIDING_KLEIN else w.lower() for i, w in enumerate(woorden)
    )
