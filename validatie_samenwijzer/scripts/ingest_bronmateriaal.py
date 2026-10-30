"""Converteer door scholen aangeleverd bronmateriaal naar markdown en registreer het als document.

Leest `oeren/<inst>_oeren/_bronmateriaal/` (alleen lokaal/Box, niet in het Fly-image), classificeert
elk bestand op bestandsnaam (zie `classificeer`), schrijft per ingenomen bestand een geredigeerde
`.md` naar `oeren/<inst>_oeren/_documenten/<soort>/<slug>.md` en registreert die in de
`documenten`-tabel van `data/validatie.db` (gereviewd, publiek, geïndexeerd). Daarnaast komt per
instelling een `_documenten/manifest.json` met per bestand soort/bereik/crebo/leerweg/cohort en
status (`ingenomen` of `overgeslagen` met reden). Spec:
docs/plans/2026-10-27-flexibele-documentlaag.md.

Het manifest wordt bij elke run opnieuw gegenereerd (handmatige wijzigingen in het manifest worden
dus overschreven). Het script is idempotent: `documenten` wordt ge-upsert, `.md` overschreven.
Er worden geen originelen gekopieerd; alleen `.md` komt onder `_documenten/`.

Gebruik (vanuit validatie_samenwijzer/, met OEREN_PAD=../oeren):
    uv run python scripts/ingest_bronmateriaal.py --instelling curio|graafschap|kwic [--dry-run]
    uv run python scripts/ingest_bronmateriaal.py --alles --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import unicodedata
import warnings
import zipfile
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from xml.etree import ElementTree as ET

from validatie_samenwijzer.db import (
    SOORTEN,
    get_connection,
    get_instelling_by_naam,
    init_db,
    markeer_document_geindexeerd,
    set_document_content_hash,
    voeg_document_toe,
)
from validatie_samenwijzer.ingest import (
    _MAP_NAAM,
    _OCR_DREMPEL,
    _pad_relatief_aan_oeren_root,
    extraheer_tekst_pdf,
)
from validatie_samenwijzer.oer_catalogus import bereken_content_hash

log = logging.getLogger("ingest_bronmateriaal")

INGENOMEN = "ingenomen"
OVERGESLAGEN = "overgeslagen"
INSTELLINGEN = ("curio", "graafschap", "kwic")
_PDF_TIMEOUT_S = 180
_MIN_TEKENS = 50  # korter = conversie waarschijnlijk mislukt (lege/scan-PDF zonder OCR-resultaat)


# ── Datamodel ─────────────────────────────────────────────────────────────────


@dataclass
class Item:
    """Eén bronbestand met zijn classificatie. `bestand` is relatief aan `_bronmateriaal/`."""

    bestand: str
    status: str = INGENOMEN
    reden: str = ""
    opmerking: str = ""
    soort: str = ""
    bereik: str = ""
    crebo: str = ""
    leerweg: str = ""
    cohort: str = ""
    titel: str = ""
    versie_label: str = ""
    md_pad: str = ""  # = DB-bestandspad: `oeren/<map>/_documenten/<soort>/<slug>.md`
    tekens: int = 0
    redacties: dict[str, int] = field(default_factory=dict)


def _slug(tekst: str, maxlen: int = 100) -> str:
    """ASCII-slug: lowercase, niet-alfanumeriek → '-'."""
    ascii_ = unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")[:maxlen].strip("-")


def _overgeslagen(bestand: str, reden: str) -> Item:
    return Item(bestand=bestand, status=OVERGESLAGEN, reden=reden)


def _ingenomen(
    instelling: str,
    bestand: str,
    soort: str,
    titel: str,
    slug: str,
    *,
    crebo: str = "",
    leerweg: str = "",
    cohort: str = "",
    versie_label: str = "",
    opmerking: str = "",
) -> Item:
    md_pad = f"oeren/{_MAP_NAAM[instelling]}/_documenten/{soort}/{_slug(slug)}.md"
    return Item(
        bestand=bestand,
        soort=soort,
        bereik=SOORTEN[soort].bereik,
        crebo=crebo,
        leerweg=leerweg,
        cohort=cohort,
        titel=titel,
        versie_label=versie_label,
        md_pad=md_pad,
        opmerking=opmerking,
    )


# ── Classificatie (alleen bestandsnamen, geen bestands-I/O) ──────────────────

# Curio: <naam>-<crebo>-<cohort> v<versie>[ (n)].pdf
_CURIO_EXAMENREGELEMENT = re.compile(
    r"^(?P<naam>.+)-(?P<crebo>\d{5})-(?P<cohort>20\d{2}) v(?P<versie>\d+(?:\.\d+)*)"
    r"(?P<dup> \(\d+\))?$"
)
# Curio: <crebo>_<nml|oer>_00_<cohort>_<st|vg>_<leerweg>_<slug>[_extra].pdf
_CURIO_NML = re.compile(
    r"^(?P<crebo>\d{5})_(?P<type>nml|oer)_00_(?P<cohort>20\d{2})_(?P<sector>st|vg)_"
    r"(?P<leerweg>bol-bbl|bol|bbl)_(?P<rest>.+)$",
    re.IGNORECASE,
)
_LEERWEG_UIT_NML = {"bol-bbl": "", "bol": "BOL", "bbl": "BBL"}

# Graafschap: <crebo>_<naam>_ExamenplanCohort<cohort>.xlsm
_GRAAFSCHAP_EXAMENPLAN = re.compile(
    r"^(?P<crebo>\d{5})_(?P<naam>.+)_ExamenplanCohort(?P<cohort>20\d{2})$"
)
_LEERWEG_TOKEN = re.compile(r"(?<![A-Za-z])(BOL|BBL)(?![A-Za-z])")


def _versie_tuple(versie: str) -> tuple[int, ...]:
    return tuple(int(d) for d in versie.split("."))


def _classificeer_curio(bestanden: list[str]) -> list[Item]:
    inst = "curio"
    items: list[Item] = []
    examenregelementen: dict[
        tuple[str, str], list[tuple[tuple[int, ...], bool, str, re.Match]]
    ] = {}

    wortel_regels: list[tuple[str, Callable[[str], Item]]] = [
        (
            "20240810 curio studentenstatuut",
            lambda b: _overgeslagen(b, "al geïndexeerd via _instelling/"),
        ),
        (
            "curio examenreglement mbo 2026-2027",
            lambda b: _overgeslagen(b, "al geïndexeerd via _instelling/"),
        ),
        (
            "onderwijsovereenkomst-ook",
            lambda b: _overgeslagen(b, "verouderd (onderwijsovereenkomst 2021-2022)"),
        ),
        (
            "protocol kluiscontrole",
            lambda b: _ingenomen(inst, b, "protocol", "Protocol kluiscontrole", "kluiscontrole"),
        ),
        (
            "bsa-info_voor_student",
            lambda b: _ingenomen(
                inst,
                b,
                "bindend_studieadvies",
                "BSA-informatie voor studenten 2025-2026",
                "bsa-informatie-studenten-2025-2026",
                versie_label="2025-2026",
            ),
        ),
        (
            "curio_schoolkostenmbo",
            lambda b: _ingenomen(
                inst, b, "schoolkosten", "Schoolkosten Curio mbo", "schoolkosten-curio-mbo"
            ),
        ),
        (
            "schoolveiligheidsplan_curio",
            lambda b: _ingenomen(
                inst,
                b,
                "veiligheidsplan",
                "Schoolveiligheidsplan Curio mbo",
                "schoolveiligheidsplan-curio-mbo",
            ),
        ),
        (
            "pok-beroepsonderwijs",
            lambda b: _ingenomen(
                inst,
                b,
                "praktijkovereenkomst",
                "Praktijkovereenkomst (POK) beroepsonderwijs vanaf schooljaar 2026-2027",
                "pok-beroepsonderwijs-2026-2027",
                versie_label="2026-2027",
            ),
        ),
        (
            "curio mbo studiekeuzegids",
            lambda b: _ingenomen(
                inst,
                b,
                "studiekeuzegids",
                "Studiekeuzegids Curio mbo 2027-2028",
                "studiekeuzegids-curio-mbo-2027-2028",
                versie_label="2027-2028",
            ),
        ),
    ]

    for bestand in bestanden:
        delen = Path(bestand).parts
        stem = Path(bestand).stem
        if len(delen) == 1:
            for sleutel, maak in wortel_regels:
                if sleutel in stem.lower():
                    items.append(maak(bestand))
                    break
            else:
                items.append(_overgeslagen(bestand, "geen classificatieregel voor dit bestand"))
        elif delen[0] == "Kwalificatiedossiers":
            items.append(_overgeslagen(bestand, "landelijk KD (zit al in kwalificatiedossiers/)"))
        elif delen[0] == "Examenregelement":
            m = _CURIO_EXAMENREGELEMENT.match(stem)
            if not m:
                items.append(
                    _overgeslagen(
                        bestand,
                        "bestandsnaam volgt niet het patroon <naam>-<crebo>-<cohort> v<versie> "
                        "(waarschijnlijk een OER, geen examenregelement)",
                    )
                )
                continue
            sleutel_ec = (m["crebo"], m["cohort"])
            examenregelementen.setdefault(sleutel_ec, []).append(
                (_versie_tuple(m["versie"]), bool(m["dup"]), bestand, m)
            )
        elif delen[0] == "NML":
            m = _CURIO_NML.match(stem)
            if not m:
                items.append(
                    _overgeslagen(bestand, "bestandsnaam volgt niet het NML-patroon (onbekend)")
                )
                continue
            if m["type"].lower() == "oer":
                log.warning("NML-map bevat een OER-bestand (overgeslagen): %s", bestand)
                items.append(
                    _overgeslagen(
                        bestand,
                        f"bestandsnaam bevat '_oer_' i.p.v. '_nml_' (crebo {m['crebo']} klopt "
                        "mogelijk niet met de inhoud)",
                    )
                )
                continue
            naam_slug, *extra = m["rest"].split("_")
            naam = naam_slug.replace("-", " ").capitalize()
            sector = m["sector"].lower()
            toelichting = ", ".join([sector, *extra])
            items.append(
                _ingenomen(
                    inst,
                    bestand,
                    "nominale_lijn",
                    f"Nominale lijn {naam} {m['cohort']} ({toelichting})",
                    stem,
                    crebo=m["crebo"],
                    cohort=m["cohort"],
                    leerweg=_LEERWEG_UIT_NML[m["leerweg"].lower()],
                )
            )
        else:
            items.append(_overgeslagen(bestand, "geen classificatieregel voor deze map"))

    # Examenregelement: per (crebo, cohort) alleen de hoogste versie; " (1)" = duplicaat.
    for (crebo, cohort), kandidaten in sorted(examenregelementen.items()):
        beste = max(kandidaten, key=lambda k: (k[0], not k[1]))
        for versie, dup, bestand, m in kandidaten:
            if (versie, dup, bestand) != (beste[0], beste[1], beste[2]):
                if dup and any(k[0] == versie and not k[1] for k in kandidaten):
                    reden = "duplicaat (' (1)'-kopie van een bestaand bestand)"
                else:
                    reden = f"oudere versie (v{'.'.join(map(str, beste[0]))} aanwezig)"
                items.append(_overgeslagen(bestand, reden))
                continue
            naam = re.sub(r"\s*\(Crebonr\.?\s*\d+\)", "", m["naam"]).strip()
            opmerking = ""
            if dup:
                opmerking = (
                    "enige exemplaar van deze versie is een ' (1)'-bestand; toch ingenomen "
                    "(geen origineel aanwezig om op terug te vallen)"
                )
            items.append(
                _ingenomen(
                    inst,
                    bestand,
                    "examenplan",
                    f"Examenplan {naam} ({crebo}) cohort {cohort}",
                    f"{crebo}-{cohort}-{naam}",
                    crebo=crebo,
                    cohort=cohort,
                    versie_label=f"v{m['versie']}",
                    opmerking=opmerking,
                )
            )
    return items


def _graafschap_naam(naam: str) -> str:
    """'ICT_System_Engineer-(Niv4)BBL' → 'ICT System Engineer (Niv4)'."""
    naam = _LEERWEG_TOKEN.sub("", naam).replace("_", " ")
    naam = re.sub(r"\s*-?\s*\(", " (", naam)
    return naam.strip()


def _classificeer_graafschap(bestanden: list[str]) -> list[Item]:
    inst = "graafschap"
    items: list[Item] = []
    for bestand in bestanden:
        delen = Path(bestand).parts
        stem = Path(bestand).stem
        map_ = delen[0] if len(delen) > 1 else ""
        if map_ == "examenplannen":
            m = _GRAAFSCHAP_EXAMENPLAN.match(stem)
            if not m:
                items.append(
                    _overgeslagen(bestand, "bestandsnaam volgt niet het examenplan-patroon")
                )
                continue
            lw = _LEERWEG_TOKEN.search(m["naam"])
            leerweg = lw[1] if lw else ""
            naam = _graafschap_naam(m["naam"])
            titel = f"Examenplan {naam}{' ' + leerweg if leerweg else ''} cohort {m['cohort']}"
            items.append(
                _ingenomen(
                    inst,
                    bestand,
                    "examenplan",
                    titel,
                    f"{m['crebo']}-{m['cohort']}-{leerweg}-{naam}",
                    crebo=m["crebo"],
                    cohort=m["cohort"],
                    leerweg=leerweg,
                )
            )
        elif map_ == "keuzedelen":
            items.append(
                _ingenomen(
                    inst,
                    bestand,
                    "keuzedelen",
                    "Overzicht keuzedelen ICT en Mediavormgeving",
                    "overzicht-keuzedelen-ict-mediavormgeving",
                )
            )
        elif map_ == "onderwijsschemas":
            # Bewust NIET ingenomen (afwijking van de aangeleverde mapping): de zichtbare bladen
            # zijn roosters vol docentcodes (77 unieke codes, ~1500 voorkomens). Plan §5 sluit
            # docentcodes/lestaken uit; ingenomen kan pas na redactie + review. Om toch in te
            # nemen: hier `_ingenomen(inst, bestand, "onderwijsplan", titel, slug, cohort="2026")`.
            items.append(
                _overgeslagen(
                    bestand,
                    "bevat docentcodes/lestaken in de roosterbladen (privacy-guardrail §5); "
                    "pas opnemen na redactie en review",
                )
            )
        elif map_ == "oer_docx":
            items.append(_overgeslagen(bestand, "OER's zijn al als PDF geïndexeerd"))
        else:
            items.append(_overgeslagen(bestand, "geen classificatieregel voor deze map"))
    return items


def _classificeer_kwic(bestanden: list[str]) -> list[Item]:
    inst = "kwic"
    regels: list[tuple[str, Callable[[str], Item]]] = [
        (
            "studentenstatuut addendum",
            lambda b: _ingenomen(
                inst,
                b,
                "studentenstatuut",
                "Studentenstatuut addendum",  # zelfbeschrijvend → kop "Studentenstatuut — addendum"
                "studentenstatuut-addendum",
                versie_label="addendum",
            ),
        ),
        (
            "procedure-rechten-van-betrokkenen",
            lambda b: _ingenomen(
                inst,
                b,
                "privacyreglement",
                "Procedure rechten van betrokkenen",
                "procedure-rechten-van-betrokkenen",
            ),
        ),
        (
            "onderwijsplan bbl 4-opleidingen",
            lambda b: _ingenomen(
                inst,
                b,
                "onderwijsplan",
                "Onderwijsplan BBL 4-opleidingen Design Based Learning",
                "onderwijsplan-bbl-4-opleidingen-design-based-learning",
                leerweg="BBL",
            ),
        ),
        (
            "module overzicht",
            lambda b: _ingenomen(
                inst,
                b,
                "onderwijsplan",
                "Module-overzicht BBL 4",
                "module-overzicht-bbl-4",
                leerweg="BBL",
            ),
        ),
        (
            "grof ontwerp challenges",
            lambda b: _overgeslagen(b, "bevat persoonsgegevens en is niet geredigeerd"),
        ),
        ("ibp-beleid", lambda b: _overgeslagen(b, "intern beleid (informatiebeveiliging/privacy)")),
        ("kd werkvoorbereider", lambda b: _overgeslagen(b, "landelijk KD")),
    ]
    items: list[Item] = []
    for bestand in bestanden:
        stem = Path(bestand).stem.lower()
        for sleutel, maak in regels:
            if sleutel in stem:
                items.append(maak(bestand))
                break
        else:
            items.append(_overgeslagen(bestand, "geen classificatieregel voor dit bestand"))
    return items


_CLASSIFICEERDERS: dict[str, Callable[[list[str]], list[Item]]] = {
    "curio": _classificeer_curio,
    "graafschap": _classificeer_graafschap,
    "kwic": _classificeer_kwic,
}


def classificeer(instelling: str, bestanden: Iterable[str]) -> list[Item]:
    """Classificeer bestandspaden (relatief aan `_bronmateriaal/`, met '/') voor een instelling.

    Raises:
        ValueError: bij een onbekende instelling of als twee ingenomen bestanden dezelfde
            `.md`-bestemming krijgen.
    """
    if instelling not in _CLASSIFICEERDERS:
        raise ValueError(
            f"Onbekende instelling: {instelling!r}. Bekend: {', '.join(INSTELLINGEN)}."
        )
    items = _CLASSIFICEERDERS[instelling](sorted(bestanden))
    bestemmingen = Counter(i.md_pad for i in items if i.status == INGENOMEN)
    dubbel = [pad for pad, n in bestemmingen.items() if n > 1]
    if dubbel:
        raise ValueError(f"Meerdere bestanden met dezelfde .md-bestemming: {dubbel}")
    return sorted(items, key=lambda i: i.bestand)


# ── Conversie ─────────────────────────────────────────────────────────────────

_LEGE_CEL_FOUT = {"#REF!", "#N/A", "#DIV/0!", "#VALUE!", "#NAME?", "#NUM!", "#NULL!"}
_SJABLOON_BLADEN = re.compile(
    r"^(voorblad|controleblad|vaststellingsformulier.*|versiebeheer|invulmogelijkheden"
    r"|_templateopmaakex)$",
    re.IGNORECASE,
)


def _cel(waarde: object) -> str:
    """Eén cel als compacte, markdown-veilige string."""
    if waarde is None:
        return ""
    if isinstance(waarde, bool):
        return "ja" if waarde else "nee"
    if isinstance(waarde, float):
        return f"{waarde:.2f}".rstrip("0").rstrip(".")
    if isinstance(waarde, datetime):
        return waarde.date().isoformat() if waarde.time() == time(0) else waarde.isoformat(" ")
    if isinstance(waarde, date):
        return waarde.isoformat()
    tekst = " ".join(str(waarde).split())
    if tekst in _LEGE_CEL_FOUT:
        return ""
    return tekst.replace("|", "\\|")


def _md_tabel(rijen: list[list[str]]) -> str:
    """Rijen (gelijke lengte, eerste = kop) als markdown-tabel, zonder lege kolommen."""
    breedte = max(len(r) for r in rijen)
    rijen = [r + [""] * (breedte - len(r)) for r in rijen]
    behouden = [c for c in range(breedte) if any(r[c] for r in rijen)]
    rijen = [[r[c] for c in behouden] for r in rijen]
    kop, *rest = rijen
    regels = ["| " + " | ".join(kop) + " |", "|" + " --- |" * len(kop)]
    regels += ["| " + " | ".join(r) + " |" for r in rest]
    return "\n".join(regels)


def _blad_naar_markdown(rijen: list[list[str]]) -> str:
    """Rijen van één blad: losse tekstregels (1 gevulde cel) als alinea, rest als tabel."""
    blokken: list[str] = []
    tabel: list[list[str]] = []
    tekst: list[str] = []

    def spoel() -> None:
        nonlocal tabel, tekst
        if tabel:
            blokken.append(_md_tabel(tabel))
            tabel = []
        if tekst:
            blokken.append("\n".join(tekst))
            tekst = []

    for rij in rijen:
        gevuld = [c for c in rij if c]
        if not gevuld:
            continue
        if len(gevuld) == 1:
            if tabel:
                spoel()
            tekst.append(gevuld[0])
        else:
            if tekst:
                spoel()
            tabel.append(rij)
    spoel()
    return "\n\n".join(blokken)


def xlsx_naar_markdown(pad: Path) -> str:
    """Zichtbare, niet-sjabloon-bladen van een xlsx/xlsm als markdown (tabellen + tekstregels)."""
    import openpyxl

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # openpyxl meldt alleen verloren opmaak-extensies
        wb = openpyxl.load_workbook(pad, data_only=True)
    delen: list[str] = []
    for ws in wb.worksheets:
        naam = ws.title.strip()
        if ws.sheet_state != "visible" or _SJABLOON_BLADEN.match(naam):
            continue
        rijen: list[list[str]] = []
        for rij in ws.iter_rows(values_only=True):
            cellen = [_cel(c) for c in rij]
            while cellen and not cellen[-1]:
                cellen.pop()
            rijen.append(cellen)
        inhoud = _blad_naar_markdown(rijen)
        if inhoud:
            delen.append(f"## Blad: {naam}\n\n{inhoud}")
    return "\n\n".join(delen)


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _alinea_tekst(p: ET.Element) -> str:
    stukken = []
    for el in p.iter():
        if el.tag == f"{_W}t" and el.text:
            stukken.append(el.text)
        elif el.tag in (f"{_W}tab", f"{_W}br"):
            stukken.append(" ")
    return " ".join("".join(stukken).split())


_MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"


def _verwijder_fallbacks(el: ET.Element) -> None:
    """Verwijder `mc:Fallback`-takken (tekstvakken staan anders dubbel in de uitvoer)."""
    for kind in list(el):
        if kind.tag == _MC_FALLBACK:
            el.remove(kind)
        else:
            _verwijder_fallbacks(kind)


def docx_naar_markdown(pad: Path) -> str:
    """Eenvoudige docx → markdown met alleen de standaardbibliotheek (koppen, lijsten, tabellen)."""
    with zipfile.ZipFile(pad) as z:
        document = ET.fromstring(z.read("word/document.xml"))
        _verwijder_fallbacks(document)
        stijlnamen: dict[str, str] = {}
        if "word/styles.xml" in z.namelist():
            for stijl in ET.fromstring(z.read("word/styles.xml")).iter(f"{_W}style"):
                naam = stijl.find(f"{_W}name")
                if naam is not None:
                    stijlnamen[stijl.get(f"{_W}styleId", "")] = naam.get(f"{_W}val", "").lower()
    body = document.find(f"{_W}body")
    blokken: list[str] = []
    if body is None:
        return ""
    for el in body:
        if el.tag == f"{_W}p":
            tekst = _alinea_tekst(el)
            if not tekst:
                continue
            ppr = el.find(f"{_W}pPr")
            stijl_el = ppr.find(f"{_W}pStyle") if ppr is not None else None
            stijl = stijlnamen.get(stijl_el.get(f"{_W}val", ""), "") if stijl_el is not None else ""
            kop = re.match(r"^(?:heading|kop) ?(\d)$", stijl)
            if stijl == "title":
                blokken.append(f"## {tekst}")
            elif kop:
                blokken.append("#" * min(int(kop[1]) + 1, 6) + f" {tekst}")
            elif ppr is not None and ppr.find(f"{_W}numPr") is not None:
                blokken.append(f"- {tekst}")
            else:
                blokken.append(tekst)
        elif el.tag == f"{_W}tbl":
            rijen = [
                [
                    _cel(" ".join(_alinea_tekst(p) for p in tc.iter(f"{_W}p")))
                    for tc in tr.findall(f"{_W}tc")
                ]
                for tr in el.findall(f"{_W}tr")
            ]
            rijen = [r for r in rijen if any(r)]
            if rijen:
                blokken.append(_md_tabel(rijen))
    # Opeenvolgende lijstitems horen bij elkaar (geen lege regel ertussen).
    uit: list[str] = []
    for blok in blokken:
        if uit and blok.startswith("- ") and uit[-1].startswith("- "):
            uit[-1] += "\n" + blok
        else:
            uit.append(blok)
    return "\n\n".join(uit)


def pdf_naar_markdown(pad: Path) -> str:
    """PDF → markdown via markitdown; valt terug op pdfplumber/OCR bij (bijna) lege uitvoer."""
    from markitdown import MarkItDown

    tekst = MarkItDown().convert(str(pad)).text_content or ""
    if len(tekst.strip()) < _OCR_DREMPEL:
        log.info(
            "markitdown leverde te weinig tekst voor '%s'; terugval op pdfplumber/OCR", pad.name
        )
        tekst = extraheer_tekst_pdf(pad)
    return tekst


def _pdf_met_timeout(pad: Path, timeout: int) -> str:
    """Converteer een PDF in een kindproces zodat een te trage conversie hard gestopt kan worden."""
    try:
        res = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--converteer-pdf", str(pad)],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(f"PDF-conversie duurde langer dan {timeout}s") from e
    if res.returncode != 0:
        fout = res.stderr.decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError(f"PDF-conversie mislukt: {fout[-1] if fout else res.returncode}")
    return res.stdout.decode("utf-8")


def converteer(pad: Path, timeout: int = _PDF_TIMEOUT_S) -> str:
    """Converteer een bronbestand naar markdown (op extensie)."""
    suffix = pad.suffix.lower()
    if suffix == ".pdf":
        return _pdf_met_timeout(pad, timeout)
    if suffix in {".xlsx", ".xlsm"}:
        return xlsx_naar_markdown(pad)
    if suffix == ".docx":
        return docx_naar_markdown(pad)
    raise ValueError(f"Niet-ondersteund bestandstype: {suffix}")


# ── Redactie (deterministisch; vangt geen namen in lopende tekst) ─────────────

_BEKENDE_NAMEN = (
    "Maico de Jong",
    "Willem van der Weijden",
    "Rogier van Erp",
    "Lotte van de Rijt",
)

_REDACTIES: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}\s?[A-Z]{4}(?:\s?\d{4}){2}\s?\d{2}\b"),
    "telefoon": re.compile(
        r"(?<![\d.,/-])(?:\+31|0031|0)[\s-]?(?:\(0\))?[\s-]?[1-9](?:[\s-]?\d){7,8}(?!\d)"
    ),
    "bsn": re.compile(r"(?i)\b(bsn|burgerservicenummer)\b[^\d\n]{0,15}\d{8,9}\b"),
    # Rol + persoonsnamen ("Projectleider: Willem van der Weijden - ..."): rest van de regel weg.
    "naam_bij_rol": re.compile(
        r"(?m)((?i:projectleiders?|auteurs?|opgesteld door|contactpersonen?|eigenaar))"
        r"[ \t]*:[ \t]*(?=[A-Z][a-zë'’.-]+ (?:(?:van|de|der|den|ter|te|'t) )*[A-Z])[^\n]*$"
    ),
    # Namen die bij handmatige review in de bronnen zijn aangetroffen (bestuurder in het Curio-
    # protocol, KWIC-projectleiders). Aanvullen bij nieuwe bevindingen; vangt geen onbekende namen.
    "naam_review": re.compile(r"\b(?:" + "|".join(re.escape(n) for n in _BEKENDE_NAMEN) + r")\b"),
}


def redigeer(tekst: str) -> tuple[str, dict[str, int]]:
    """Vervang e-mail, telefoon, IBAN, BSN en namen na een rol door `[verwijderd]`."""
    aantallen: dict[str, int] = {}
    for naam, patroon in _REDACTIES.items():
        tekst, n = patroon.subn(
            lambda m: (
                (f"{m[1]}: " if m.re.groups and naam == "naam_bij_rol" else "") + "[verwijderd]"
            ),
            tekst,
        )
        if n:
            aantallen[naam] = n
    return tekst, aantallen


# ── Orkestratie ───────────────────────────────────────────────────────────────


def _bronnen(bron_map: Path) -> list[str]:
    return sorted(
        p.relative_to(bron_map).as_posix()
        for p in bron_map.rglob("*")
        if p.is_file() and not p.name.startswith(".")
    )


def _manifest_dict(item: Item) -> dict:
    return asdict(item)


def verwerk_instelling(
    naam: str,
    oeren_pad: Path,
    conn,
    *,
    dry_run: bool,
    workers: int,
    timeout: int,
) -> list[Item]:
    """Classificeer, converteer, schrijf `.md` + manifest en registreer. Geeft alle items terug."""
    map_naam = _MAP_NAAM[naam]
    bron_map = oeren_pad / map_naam / "_bronmateriaal"
    if not bron_map.is_dir():
        log.error("Geen _bronmateriaal-map voor %s: %s", naam, bron_map)
        return []
    items = classificeer(naam, _bronnen(bron_map))
    te_doen = [i for i in items if i.status == INGENOMEN]
    if dry_run:
        return items

    root = oeren_pad.resolve().parent

    def werk(item: Item) -> tuple[Item, str | Exception]:
        try:
            return item, converteer(bron_map / item.bestand, timeout)
        except Exception as e:  # noqa: BLE001 — per bestand loggen en door
            return item, e

    inst = get_instelling_by_naam(conn, naam) if conn is not None else None
    if inst is None:
        raise RuntimeError(f"Instelling '{naam}' niet gevonden in database.")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for item, resultaat in pool.map(werk, te_doen):
            if isinstance(resultaat, Exception):
                log.error("Conversie mislukt voor '%s': %s", item.bestand, resultaat)
                item.status, item.reden = OVERGESLAGEN, f"conversiefout: {resultaat}"
                continue
            tekst, item.redacties = redigeer(resultaat.strip())
            if len(tekst) < _MIN_TEKENS:
                log.error("Lege conversie voor '%s' (%d tekens)", item.bestand, len(tekst))
                item.status, item.reden = OVERGESLAGEN, "lege conversie (geen extraheerbare tekst)"
                continue
            md = f"# {item.titel}\n\nBronbestand: {Path(item.bestand).name}\n\n{tekst}\n"
            item.tekens = len(md)
            md_pad = root / item.md_pad
            md_pad.parent.mkdir(parents=True, exist_ok=True)
            md_pad.write_text(md, encoding="utf-8")
            doc_id = voeg_document_toe(
                conn,
                inst["id"],
                item.soort,
                item.titel,
                _pad_relatief_aan_oeren_root(root / item.md_pad),
                bereik=item.bereik,
                crebo=item.crebo,
                leerweg=item.leerweg,
                cohort=item.cohort,
                zichtbaarheid="publiek",
                gevoeligheid="normaal",
                gereviewd=True,
                versie_label=item.versie_label,
            )
            set_document_content_hash(conn, doc_id, bereken_content_hash(md))
            markeer_document_geindexeerd(conn, doc_id)
            log.info("Ingenomen: %s → %s (%d tekens)", item.bestand, item.md_pad, item.tekens)

    manifest = oeren_pad.resolve() / map_naam / "_documenten" / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps([_manifest_dict(i) for i in items], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    log.info("Manifest geschreven: %s", manifest)
    return items


def _eindrapport(resultaten: dict[str, list[Item]], dry_run: bool) -> None:
    print(f"\n=== Eindrapport bronmateriaal{' (dry-run)' if dry_run else ''} ===")
    alle: list[Item] = []
    for naam, items in resultaten.items():
        ingenomen = [i for i in items if i.status == INGENOMEN]
        overgeslagen = [i for i in items if i.status != INGENOMEN]
        print(f"\n{naam}: {len(ingenomen)} ingenomen, {len(overgeslagen)} overgeslagen")
        for soort, n in sorted(Counter(i.soort for i in ingenomen).items()):
            print(f"  ingenomen  {soort}: {n}")
        for reden, n in Counter(i.reden for i in overgeslagen).most_common():
            print(f"  overgeslagen ({n}x): {reden}")
        for i in ingenomen:
            if i.opmerking:
                print(f"  opmerking {i.bestand}: {i.opmerking}")
        alle += ingenomen
    if not dry_run:
        print("\nGrootste .md's (tekens):")
        for i in sorted(alle, key=lambda i: i.tekens, reverse=True)[:3]:
            print(f"  {i.tekens:>9,}  {i.md_pad}")
        redacties: Counter[str] = Counter()
        for i in alle:
            redacties.update(i.redacties)
        print(f"Redacties totaal: {dict(redacties) or 'geen'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bronmateriaal → markdown + documenten-register")
    parser.add_argument("--instelling", choices=INSTELLINGEN)
    parser.add_argument("--alles", action="store_true", help="Alle instellingen met bronmateriaal")
    parser.add_argument(
        "--dry-run", action="store_true", help="Alleen classificeren en rapporteren"
    )
    parser.add_argument("--workers", type=int, default=4, help="Parallelle conversies (default 4)")
    parser.add_argument("--timeout", type=int, default=_PDF_TIMEOUT_S, help="Seconden per PDF")
    parser.add_argument("--converteer-pdf", help=argparse.SUPPRESS)  # intern: kindproces
    args = parser.parse_args()

    if args.converteer_pdf:
        sys.stdout.buffer.write(pdf_naar_markdown(Path(args.converteer_pdf)).encode("utf-8"))
        return

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    if not (args.instelling or args.alles):
        parser.print_help()
        return

    namen = list(INSTELLINGEN) if args.alles else [args.instelling]
    oeren_pad = Path(os.environ.get("OEREN_PAD", "oeren"))
    db_path = Path(os.environ.get("DB_PATH", "data/validatie.db"))
    conn = None
    if not args.dry_run:
        conn = get_connection(db_path)
        init_db(conn)
    resultaten = {
        naam: verwerk_instelling(
            naam, oeren_pad, conn, dry_run=args.dry_run, workers=args.workers, timeout=args.timeout
        )
        for naam in namen
    }
    _eindrapport(resultaten, args.dry_run)


if __name__ == "__main__":
    main()
