"""Download Landstede-OER's (examenmappen) van het Educator-studiegidsplatform.

Landstede MBO publiceert zijn studiegidsen op https://landstede.educator.eu/ als
**server-gerenderde HTML** (geen JSON-API, geen XHR — een platte ``httpx``-GET levert
de volledige pagina). De crawl loopt over vier niveaus:

1. **Root** ``/edu/studiegids/Landstede`` → 15 landschap-links
   (``/landschap/<UUID>/<cohort>``). De cohort-segment ``25`` = studiejaar 2025-2026,
   het nieuwste cohort mét gepubliceerde examenmappen (``26`` bestaat al maar de
   examenmappen zijn daar nog niet vrijgegeven).
2. **Landschap** → opleiding-links ``/opleiding/<UUID>/25/{BOL|BBL}`` — het trailing
   ``BOL``/``BBL`` is de **leerweg**.
3. **Opleiding-overzicht** → de opleidingsgids-variant
   ``/landschap/<UUID>/opleidingsgids/<UUID>`` (de variant mét "Examenplannen"; de
   "Algemene gids"-variant via ``/landschapsgids/.../cohort/...`` wordt genegeerd).
4. **Opleidingsgids** → één examenplan-link per uitstroomprofiel
   (``/examenplan/<UUID>/landschapsgids/<UUID>/opleidingsgids/<UUID>/edition/<N>``).
5. **Examenmap** (de examenplan-URL) → server-gerenderde HTML met de kerntaken
   (``B1-K1``), de crebo's en het cohortlabel — dé OER-inhoud.

De examenmap-HTML wordt via markitdown naar Markdown geconverteerd en opgeslagen als
``.md`` onder ``oeren/landstede_oeren/`` (zoals de overige instellingen). markitdown
rendert de kerntaken hier als koppen (``### Kerntaak: B1-K1 - …``) i.p.v. lijst-items;
``_normaliseer_kerntaken`` tilt die codes naar regelstart zodat
``ingest.extraheer_kerntaken`` ze herkent (de ingest-/parser-regex blijft ongemoeid).

**Crebo = uitstroomcode** (de code waarin de student diplomeert; waarop het KD-/skills-
bundle gesleuteld is), niet de bredere dossiercode. Op de examenmap-pagina staat de
uitstroomcode als eerste haakje in de ``Profieldeel: <naam> (UITSTROOM) (DOSSIER)``-regel,
met de ``Examenmap: DOSSIER - UITSTROOM``-regel als kruiscontrole. Lukt het niet de
uitstroomcode eenduidig te bepalen → waarschuwen en overslaan (niet gokken).

Dit script is tevens het **regeneratie-recept**: ``oeren/landstede_oeren/`` is gitignored
(Box-only), dus andere machines draaien dit script opnieuw of syncen via Box. ``OEREN_PAD``
overschrijft de oeren-tree, zodat naar dezelfde tree geschreven wordt als waar de app uit
leest.

Gebruik (vanuit ``validatie_samenwijzer/``):

    uv run python scripts/fetch_landstede.py            # download + schrijf
    uv run python scripts/fetch_landstede.py --preview  # droge run, schrijf niets
    OEREN_PAD=../oeren uv run python scripts/fetch_landstede.py
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import httpx
from markitdown import MarkItDown

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]

BASE = "https://landstede.educator.eu"
ROOT_URL = f"{BASE}/edu/studiegids/Landstede"
COHORT_SEGMENT = "25"  # /25 = studiejaar 2025-2026 (nieuwste mét examenmappen)
COHORT_LABEL = "2025"

_HEADERS = {
    "accept": "text/html,application/xhtml+xml",
    "user-agent": "Mozilla/5.0 (samenwijzer OER-ingestie)",
}
_WORKERS = 6
_TIMEOUT = 45.0  # zware landschap-/examenplan-pagina's hebben af en toe >30s nodig
_RETRIES = 5  # examenplan-pagina's worden traag server-side gegenereerd → ruim retryen

# ── Link-patronen (op de server-gerenderde HTML) ──────────────────────────────
_LANDSCHAP_RE = re.compile(r"/edu/studiegids/Landstede/landschap/[0-9A-Fa-f-]+/\d+")
_OPLEIDING_RE = re.compile(
    r"/edu/studiegids/Landstede/landschap/[0-9A-Fa-f-]+/opleiding/[0-9A-Fa-f-]+/25/(BOL|BBL)"
)
# De juiste opleidingsgids-variant: /landschap/<UUID>/opleidingsgids/<UUID> (mét
# "Examenplannen"); NIET /landschapsgids/.../cohort/... (de algemene gids zonder kerntaken).
_OPLEIDINGSGIDS_RE = re.compile(
    r"/edu/studiegids/Landstede/landschap/[0-9A-Fa-f-]+/opleidingsgids/[0-9A-Fa-f-]+(?=[\"'?#]|$)"
)
_EXAMENPLAN_ANCHOR_RE = re.compile(
    r'<a[^>]+href="(/edu/studiegids/Landstede/examenplan/[0-9A-Fa-f-]+'
    r'/landschapsgids/[0-9A-Fa-f-]+/opleidingsgids/[0-9A-Fa-f-]+/edition/\d+)"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")

# ── Inhoud-patronen (op de markitdown-Markdown) ───────────────────────────────
# Til "### Kerntaak: B1-K1 - …" / "Werkproces: B1-K1-W1 - …" naar regelstart.
_KT_KOP_RE = re.compile(
    r"^\s*#*\s*(?:Kerntaak|Werkproces)\s*:?\s*(B\d+-K\d+(?:-W\d+)?\b.*)$",
    re.IGNORECASE,
)
_PROFIELDEEL_RE = re.compile(r"Profieldeel:\s*(.+?)\s*\((\d{5})\)(?:\s*\((\d{5})\))?")
# Terugval voor opleidingen zonder Profieldeel-crebo (bv. niveau-2 zonder profieldeel):
# de diploma-examenmap draagt de uitstroomcode als leidend getal vóór de uitstroomnaam,
# op dezelfde regel als een kerntaakcode — bv. "Examenmap: 25350 Monteur … B1-K1 …".
_EXAMENMAP_LEAD_RE = re.compile(r"Examenmap:\s*(\d{5})\s+\D")
_KT_CODE_RE = re.compile(r"B\d+-K\d+")
_STARTJAAR_RE = re.compile(r"Startjaar:\s*(20\d\d)")
_ANKER_PAREN_RE = re.compile(r"\(([^()]+)\)\s*$")


def _landstede_dir() -> Path:
    """Doelmap ``<oeren>/landstede_oeren``; ``OEREN_PAD`` overschrijft de oeren-tree."""
    base = os.environ.get("OEREN_PAD")
    oeren = Path(base).resolve() if base else ROOT / "oeren"
    return oeren / "landstede_oeren"


def _slug(naam: str) -> str:
    """Maak een leesbare ascii-stem van de opleidingsnaam."""
    naam = unicodedata.normalize("NFKD", naam).encode("ascii", "ignore").decode()
    naam = re.sub(r"\d{5}", "", naam)  # losse crebo's uit de naam weren
    naam = re.sub(r"[^A-Za-z0-9]+", "_", naam).strip("_")
    return naam[:80] or "Examenplan"


def _anchor_tekst(html_fragment: str) -> str:
    """Platte ankertekst (uitstroomnaam) uit een <a>-binnenkant."""
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html_fragment)).strip()


def _get(client: httpx.Client, url: str) -> str:
    """GET met retry/backoff — examenplan-pagina's worden traag gegenereerd."""
    for poging in range(_RETRIES):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as exc:
            wacht = 1.5 * (poging + 1)
            log.debug("GET %s mislukt (poging %d/%d): %s", url, poging + 1, _RETRIES, exc)
            if poging < _RETRIES - 1:
                time.sleep(wacht)
    log.warning("GET definitief mislukt na %d pogingen: %s", _RETRIES, url)
    return ""


def _get_bytes(client: httpx.Client, url: str) -> bytes:
    """GET (bytes) met retry/backoff — voor markitdown-conversie van de HTML."""
    for poging in range(_RETRIES):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPError as exc:
            log.debug("GET %s mislukt (poging %d/%d): %s", url, poging + 1, _RETRIES, exc)
            if poging < _RETRIES - 1:
                time.sleep(1.5 * (poging + 1))
    log.warning("GET definitief mislukt na %d pogingen: %s", _RETRIES, url)
    return b""


def _normaliseer_kerntaken(md: str) -> str:
    """Til kerntaak-/werkproces-koppen naar regelstart zodat ``extraheer_kerntaken``
    de codes herkent (markitdown rendert ze als ``### Kerntaak: B1-K1 - …``-koppen,
    niet als lijst-items zoals de regex verwacht)."""
    regels = []
    for regel in md.splitlines():
        m = _KT_KOP_RE.match(regel)
        regels.append(f"- {m.group(1)}" if m else regel)
    return "\n".join(regels)


def haal_landschappen(client: httpx.Client) -> list[str]:
    """15 landschap-URL's uit de root; cohort-segment herschreven naar 25."""
    html = _get(client, ROOT_URL)
    gevonden = {re.sub(r"/\d+$", f"/{COHORT_SEGMENT}", m) for m in _LANDSCHAP_RE.findall(html)}
    return sorted(BASE + pad for pad in gevonden)


def haal_opleidingen(client: httpx.Client, landschap_url: str) -> list[tuple[str, str]]:
    """Opleiding-overzicht-URL's + leerweg uit een landschap-pagina."""
    html = _get(client, landschap_url)
    out: dict[str, str] = {}
    for m in _OPLEIDING_RE.finditer(html):
        out[m.group(0)] = m.group(1).upper()
    return [(BASE + pad, leerweg) for pad, leerweg in out.items()]


def haal_opleidingsgids(client: httpx.Client, opleiding_url: str) -> str | None:
    """De examenplannen-opleidingsgids-variant uit een opleiding-overzicht (of None)."""
    html = _get(client, opleiding_url)
    m = _OPLEIDINGSGIDS_RE.search(html)
    return BASE + m.group(0) if m else None


def haal_examenplannen(client: httpx.Client, opleidingsgids_url: str) -> list[tuple[str, str]]:
    """(examenplan-URL, uitstroomnaam) per uitstroomprofiel uit een opleidingsgids."""
    html = _get(client, opleidingsgids_url)
    out: dict[str, str] = {}
    for m in _EXAMENPLAN_ANCHOR_RE.finditer(html):
        out[BASE + m.group(1)] = _anchor_tekst(m.group(2))
    return list(out.items())


def _examenmap_md(client: httpx.Client, examenplan_url: str) -> str:
    """Examenmap-HTML → genormaliseerde Markdown (kerntaken op regelstart)."""
    content = _get_bytes(client, examenplan_url)
    if not content:
        return ""
    md = MarkItDown().convert_stream(BytesIO(content), file_extension=".html").text_content
    return _normaliseer_kerntaken(md)


def _leidende_examenmap_crebo(md: str) -> str | None:
    """Uitstroomcode uit de diploma-examenmap (leidend getal op een kerntaakregel).

    Terugval voor opleidingen zonder ``Profieldeel``-haakjescode.
    """
    for regel in md.splitlines():
        if "Examenmap:" in regel and _KT_CODE_RE.search(regel):
            m = _EXAMENMAP_LEAD_RE.search(regel)
            if m:
                return m.group(1)
    return None


def _namen_matchen(anker_naam: str, prof_naam: str) -> bool:
    """Soft-check: hoort de Profieldeel-naam bij dit uitstroomprofiel (anker)?

    De anker-tekst draagt soms de opleidingsnaam met de uitstroom tussen haakjes
    (``Pedagogisch Werk (Onderwijsassistent)``); de Profieldeel-naam kan net de
    binnenste of de volledige variant zijn. Vergelijk daarom bidirectioneel én
    tegen het laatste haakjesdeel van het anker.
    """
    a = anker_naam.strip().lower()
    p = prof_naam.strip().lower()
    if not a or not p:
        return True
    paren = _ANKER_PAREN_RE.search(anker_naam)
    inner = paren.group(1).strip().lower() if paren else a
    return p in a or a in p or p in inner or inner in p


def _bepaal_uitstroom_crebo(md: str, anker_naam: str) -> str | None:
    """Bepaal de uitstroom-crebo (diplomacode) van deze examenmap-pagina.

    Primair de ``Profieldeel: <naam> (UITSTROOM) (DOSSIER)``-regel (autoritatief —
    dit ís het uitstroomprofiel van de pagina, en de naam matcht het anker). Heeft
    de pagina geen Profieldeel-crebo, dan de leidende code uit de diploma-examenmap.
    Lukt geen van beide → None (overslaan; bv. een niet-gerenderde sjabloonpagina).
    """
    prof = _PROFIELDEEL_RE.search(md)
    if prof:
        prof_naam = prof.group(1) or ""
        if not _namen_matchen(anker_naam, prof_naam):
            log.warning(
                "Naam-mismatch uitstroom (anker=%r, Profieldeel=%r) — crebo %s aangehouden",
                anker_naam,
                prof_naam.strip(),
                prof.group(2),
            )
        return prof.group(2)
    lead = _leidende_examenmap_crebo(md)
    if lead:
        return lead
    log.warning("Geen uitstroom-crebo gevonden voor %r — overgeslagen", anker_naam)
    return None


def _cohort_label(md: str) -> str:
    m = _STARTJAAR_RE.search(md)
    return m.group(1) if m else COHORT_LABEL


def verzamel_examenplannen(client: httpx.Client) -> dict[str, dict]:
    """Crawl tot examenplan-niveau. Levert ``{examenplan_url: {naam, leerwegen}}``;
    ``leerwegen`` is de set leerwegen (BOL/BBL) waaronder de opleiding wordt aangeboden."""
    landschappen = haal_landschappen(client)
    log.info("Root: %d landschappen voor cohort %s.", len(landschappen), COHORT_LABEL)

    # Niveau 2: opleiding-overzichten (+ leerweg), parallel per landschap.
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        per_landschap = list(pool.map(lambda lu: haal_opleidingen(client, lu), landschappen))
    opleidingen = [pair for lijst in per_landschap for pair in lijst]
    leeg = sum(1 for lijst in per_landschap if not lijst)
    if leeg:
        log.warning("%d landschap(pen) leverden 0 opleidingen (mogelijk timeout).", leeg)
    log.info("%d opleiding-leerweg-overzichten.", len(opleidingen))

    # Niveau 3: opleidingsgids-variant per opleiding-overzicht; bundel leerwegen.
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        gidsen = list(pool.map(lambda ol: haal_opleidingsgids(client, ol[0]), opleidingen))
    gids_leerwegen: dict[str, set[str]] = {}
    for (_, leerweg), gids in zip(opleidingen, gidsen):
        if gids:
            gids_leerwegen.setdefault(gids, set()).add(leerweg)
    log.info("%d unieke opleidingsgids-varianten (met examenplannen).", len(gids_leerwegen))

    # Niveau 4: examenplan-links per opleidingsgids; bundel leerwegen per examenplan.
    gids_lijst = list(gids_leerwegen)
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        per_gids = list(pool.map(lambda g: haal_examenplannen(client, g), gids_lijst))
    examenplannen: dict[str, dict] = {}
    for gids, paren in zip(gids_lijst, per_gids):
        for url, naam in paren:
            rec = examenplannen.setdefault(url, {"naam": naam, "leerwegen": set()})
            rec["leerwegen"].update(gids_leerwegen[gids])
    log.info("%d unieke examenplannen (uitstroomprofielen).", len(examenplannen))
    return examenplannen


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Landstede-examenmappen als OER's")
    parser.add_argument(
        "--cohort", default="2025-2026", help="Studiejaar-label (informatief; default 2025-2026)"
    )
    parser.add_argument("--preview", action="store_true", help="Droge run; schrijf geen bestanden")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # extraheer_kerntaken stuurt zowel de dedup (kerntaak-rijke pagina wint) als de
    # make-or-break-controle; dezelfde regex die ingest later op de .md draait.
    from validatie_samenwijzer.ingest import extraheer_kerntaken

    limits = httpx.Limits(max_connections=_WORKERS, max_keepalive_connections=_WORKERS)
    with httpx.Client(
        headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True, limits=limits
    ) as client:
        examenplannen = verzamel_examenplannen(client)

        # Niveau 5: haal elke examenmap één keer op (parallel), converteer + crebo.
        urls = list(examenplannen)

        def _fetch(url: str) -> dict:
            info = examenplannen[url]
            md = _examenmap_md(client, url)
            crebo = _bepaal_uitstroom_crebo(md, info["naam"]) if md.strip() else None
            return {
                "url": url,
                "naam": info["naam"],
                "leerwegen": info["leerwegen"],
                "tekst": md,
                "crebo": crebo,
                "cohort": _cohort_label(md),
                "kerntaken": len(extraheer_kerntaken(md)) if md.strip() else 0,
            }

        with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
            pagina_s = list(pool.map(_fetch, urls))

    # Bouw records per (crebo, leerweg); sla pagina's zonder crebo/tekst over.
    records: list[dict] = []
    zonder_crebo = 0
    for p in pagina_s:
        if not p["tekst"].strip() or not p["crebo"]:
            zonder_crebo += 1
            continue
        for leerweg in sorted(p["leerwegen"]) or ["BOL"]:
            records.append(
                {
                    "crebo": p["crebo"],
                    "leerweg": leerweg,
                    "cohort": p["cohort"],
                    "naam": p["naam"],
                    "tekst": p["tekst"],
                    "kerntaken": p["kerntaken"],
                }
            )

    # Dedup op (crebo, leerweg) — bundel-sleutel van ingest. Rijkdoms-score:
    # een pagina mét kerntaken wint altijd van een (langere) kerntaakloze variant
    # (bv. een niet-gerenderde sjabloonpagina van dezelfde uitstroom), daarna lengte.
    def _score(rec: dict) -> tuple[bool, int]:
        return (rec["kerntaken"] > 0, len(rec["tekst"]))

    beste: dict[tuple[str, str], dict] = {}
    for rec in records:
        sleutel = (rec["crebo"], rec["leerweg"])
        if sleutel not in beste or _score(rec) > _score(beste[sleutel]):
            beste[sleutel] = rec

    crebos = {rec["crebo"] for rec in beste.values()}
    log.info(
        "%d OER-bestanden (over %d unieke crebo's) na dedup; %d pagina's zonder crebo/tekst.",
        len(beste),
        len(crebos),
        zonder_crebo,
    )

    # Kerntaken-controle (de make-or-break-invariant) + preview-overzicht.
    zonder_kerntaken = []
    for (crebo, leerweg), rec in sorted(beste.items()):
        if rec["kerntaken"] == 0:
            zonder_kerntaken.append(f"{crebo}_{leerweg} ({rec['naam']})")
        if args.preview:
            log.info(
                "  zou schrijven: %s_%s_%s__%s.md (%d tekens, %d kerntaken)",
                crebo,
                leerweg,
                rec["cohort"],
                _slug(rec["naam"]),
                len(rec["tekst"]),
                rec["kerntaken"],
            )
    if zonder_kerntaken:
        log.warning(
            "%d OER's zonder herkende kerntaken: %s", len(zonder_kerntaken), zonder_kerntaken
        )

    if args.preview:
        log.info("Preview — niets weggeschreven.")
        return

    doelmap = _landstede_dir()
    doelmap.mkdir(parents=True, exist_ok=True)
    for (crebo, leerweg), rec in beste.items():
        stem = f"{crebo}_{leerweg}_{rec['cohort']}__{_slug(rec['naam'])}"
        (doelmap / f"{stem}.md").write_text(rec["tekst"], encoding="utf-8")
    log.info("%d examenmappen geschreven naar %s.", len(beste), doelmap)


if __name__ == "__main__":
    main()
