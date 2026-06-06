"""Download Deltion-studiegidsen (OER's) uit de SQill-publisher-API.

Deltion publiceert zijn studiegidsen via de JS-app op https://studiegidsen.deltion.nl/
met een publieke (keyless) backend op ``https://deltion.sqill.it/publisher/api/v0``.
Per opleiding levert de zoek-API een ``report``-UUID; ``/reports/<uuid>/html`` geeft de
volledige studiegids — dé OER, inclusief kerntaken/werkprocessen (B1-K1-W1-codes),
examenplan, BSA, examinering en LOB — als zelfstandige HTML.

De studiegids wordt als platte tekst (BeautifulSoup) opgeslagen als ``.md`` naast de
overige instellingen onder ``oeren/deltion_oeren/``. Reden voor ``.md`` en niet ``.pdf``:
``chat.laad_oer_tekst`` leest alleen ``.md``/``.pdf`` als chat-context, en BeautifulSoup-
tekst (één code+naam per regel) is de enige conversie waaruit ``ingest.extraheer_kerntaken``
de kerntaken betrouwbaar haalt (markitdown rendert ze als tabellen → 0 kerntaken).

Dit script is tevens het **regeneratie-recept**: ``oeren/deltion_oeren/`` is gitignored
(Box-only, zoals de andere niet-publieke instellingen), dus andere machines draaien dit
script opnieuw of syncen via Box. ``OEREN_PAD`` overschrijft de oeren-tree (zoals in
``ingest``), zodat naar dezelfde tree geschreven wordt als waar de app uit leest.

Gebruik (vanuit ``validatie_samenwijzer/``):

    uv run python scripts/fetch_deltion.py            # download + schrijf
    uv run python scripts/fetch_deltion.py --preview  # droge run, schrijf niets
    uv run python scripts/fetch_deltion.py --cohort 2025-2026
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]

API = "https://deltion.sqill.it/publisher/api/v0"
SEARCH_URL = f"{API}/studiegids/items/search"
REPORT_URL = "https://deltion.sqill.it/reports/{uuid}/html"

_HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "origin": "https://studiegidsen.deltion.nl",
    "user-agent": "Mozilla/5.0 (samenwijzer OER-ingestie)",
}
_PAGE = 30
_WORKERS = 6
_UUID_RE = re.compile(r"/reports/([0-9a-f-]+)")


def _deltion_dir() -> Path:
    """Doelmap ``<oeren>/deltion_oeren``; ``OEREN_PAD`` overschrijft de oeren-tree."""
    base = os.environ.get("OEREN_PAD")
    oeren = Path(base).resolve() if base else ROOT / "oeren"
    return oeren / "deltion_oeren"


def _collapse_leerweg(bol_bbl: list[str] | None) -> str:
    """Eén leerweg-token voor de bestandsnaam (BOL leidend bij BOL+BBL)."""
    soorten = {x.upper() for x in (bol_bbl or [])}
    if "BOL" in soorten:
        return "BOL"
    if "BBL" in soorten:
        return "BBL"
    return "BOL"


def _slug(naam: str) -> str:
    """Maak een leesbare ascii-stem van de opleidingsnaam."""
    naam = unicodedata.normalize("NFKD", naam).encode("ascii", "ignore").decode()
    naam = re.sub(r"\d{5}", "", naam)  # losse crebo's uit de naam weren
    naam = re.sub(r"[^A-Za-z0-9]+", "_", naam).strip("_")
    return naam[:80] or "Studiegids"


def haal_items_op(client: httpx.Client, cohort: str) -> list[dict]:
    """Pagineer de zoek-API en geef alle studiegids-items voor het cohort."""
    items: list[dict] = []
    offset = 0
    while True:
        resp = client.post(
            SEARCH_URL,
            params={"size": _PAGE, "offset": offset},
            json={"query": "", "filters": {"cohort": [cohort]}, "language": "nl"},
        )
        resp.raise_for_status()
        body = resp.json()
        batch = body.get("data", [])
        items.extend(batch)
        total = int(body.get("meta", {}).get("total", 0))
        offset += _PAGE
        if not batch or len(items) >= total:
            break
    return items


def _record(item: dict) -> dict | None:
    """Zet een ruw API-item om naar {crebo, leerweg, cohort, naam, uuid}.

    Crebo = uitstroomcode (``opleidingscode``), met de dossiercode
    (``opleidingscode_dossier``) als terugval. De uitstroomcode is de crebo
    waarin de student diplomeert en waarop ons KD-/skills-bundle gesleuteld is.
    """
    data = item.get("attributes", {}).get("data", {})
    crebo = data.get("opleidingscode") or data.get("opleidingscode_dossier")
    uuid_match = _UUID_RE.search(data.get("studiegids") or "")
    if not crebo or not re.fullmatch(r"\d{5}", str(crebo)) or not uuid_match:
        log.warning(
            "Item %s overgeslagen (crebo=%r, studiegids=%r)",
            item.get("id"),
            crebo,
            data.get("studiegids"),
        )
        return None
    return {
        "crebo": str(crebo),
        "leerweg": _collapse_leerweg(data.get("bol_bbl")),
        "cohort": (data.get("cohort") or "").split("-")[0] or "2025",
        "naam": (data.get("naam") or "").strip(),
        "uuid": uuid_match.group(1),
    }


def _haal_studiegids_tekst(client: httpx.Client, uuid: str) -> str:
    """Haal de volledige studiegids-HTML op en geef de zichtbare tekst.

    BeautifulSoup met newline-separator spiegelt ``ingest.extraheer_tekst_html``;
    dit is de conversie waaruit de kerntaken-regex de B1-K1-W1-codes haalt.
    """
    resp = client.get(REPORT_URL.format(uuid=uuid), timeout=30.0)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Deltion-studiegidsen als OER's")
    parser.add_argument(
        "--cohort", default="2025-2026", help="Studiejaar-filter (default 2025-2026)"
    )
    parser.add_argument("--preview", action="store_true", help="Droge run; schrijf geen bestanden")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    with httpx.Client(headers=_HEADERS, timeout=30.0) as client:
        items = haal_items_op(client, args.cohort)
        log.info("Zoek-API: %d studiegids-items voor cohort %s.", len(items), args.cohort)

        records = [r for r in (_record(it) for it in items) if r]
        log.info("Geldige records met crebo + report-UUID: %d.", len(records))

        # Haal alle studiegids-teksten parallel op (modest; rate-limit 600/min).
        def _fetch(rec: dict) -> dict:
            rec = dict(rec)
            try:
                rec["tekst"] = _haal_studiegids_tekst(client, rec["uuid"])
            except httpx.HTTPError as exc:
                log.warning("Studiegids %s (%s) mislukt: %s", rec["crebo"], rec["naam"], exc)
                rec["tekst"] = ""
            return rec

        with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
            records = list(pool.map(_fetch, records))

    # Dedup op (crebo, leerweg) — bundel-sleutel van ingest — en houd de rijkste tekst.
    bruikbaar = [r for r in records if r["tekst"].strip()]
    beste: dict[tuple[str, str], dict] = {}
    for rec in bruikbaar:
        sleutel = (rec["crebo"], rec["leerweg"])
        if sleutel not in beste or len(rec["tekst"]) > len(beste[sleutel]["tekst"]):
            beste[sleutel] = rec

    log.info(
        "%d unieke OER's na dedup op (crebo, leerweg); %d items zonder bruikbare tekst.",
        len(beste),
        len(records) - len(bruikbaar),
    )

    if args.preview:
        for (crebo, leerweg), rec in sorted(beste.items()):
            log.info(
                "  zou schrijven: %s_%s_%s__%s.md (%d tekens)",
                crebo,
                leerweg,
                rec["cohort"],
                _slug(rec["naam"]),
                len(rec["tekst"]),
            )
        log.info("Preview — niets weggeschreven.")
        return

    doelmap = _deltion_dir()
    doelmap.mkdir(parents=True, exist_ok=True)
    for (crebo, leerweg), rec in beste.items():
        stem = f"{crebo}_{leerweg}_{rec['cohort']}__{_slug(rec['naam'])}"
        (doelmap / f"{stem}.md").write_text(rec["tekst"], encoding="utf-8")
    log.info("%d studiegidsen geschreven naar %s.", len(beste), doelmap)


if __name__ == "__main__":
    main()
