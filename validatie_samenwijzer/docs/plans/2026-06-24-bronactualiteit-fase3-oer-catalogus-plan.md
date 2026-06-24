# Bronactualiteit Fase 3 — OER-catalogus-check Implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detecteer of een instelling **nieuwe OER's of cohorten** publiceert die wij nog niet hebben — een tuple-diff `(crebo, leerweg, cohort)` tussen de instellingscatalogus en `oer_documenten` — en surface dat in `check-bron-updates`. Eerste instelling: Deltion (gestructureerde JSON-API).

**Architecture:** Een `oer_catalogus`-module met per-instelling adapters die een catalogus opleveren als `CatalogusItem`-lijst; een pure diff-functie bepaalt wat nieuw is t.o.v. de DB. De netwerk-call zit geïsoleerd in de adapter; de diff-logica is deterministisch en getest. Gegate achter `--oer`, zodat het standaard `check-bron-updates` offline/instant blijft.

**Tech Stack:** Python 3.13, `httpx` (bestaande dep), pytest, `uv`. Hergebruikt `scripts/fetch_deltion.py` (`haal_items_op`, `_record`) en `db.get_alle_oers_met_instelling`.

## Global Constraints

- **Netwerk alleen achter `--oer`** — het standaard rapport blijft offline (skills + KD + "oer: niet gedraaid"). `--oer` is tevens wat de toekomstige geplande Action draait.
- **Out-of-band, muteert niets** — de check leest de catalogus + de DB en diff't; schrijft niets.
- **Alle cohorten, geen hardcoded cohort** — de Deltion-adapter vraagt met een **leeg cohortfilter** zodat een gloednieuw cohort (bv. 2026-2027, dat nu al bij Deltion staat) zichtbaar wordt. Een vast cohort zou exact de silent-coverage-val zijn.
- **`allowed_domains`-valkuil** geldt niet hier (directe `httpx`-call naar de Deltion-API, geen Anthropic `web_search`), maar blijft relevant voor latere instellingen die via `web_search`/`web_fetch` gaan.
- Lint: line-length 100, selectie `E,F,I,N,W,UP`. Draai `ruff` + `pytest` lokaal (geen CI-gate voor dit subproject).

---

## Scope-herziening (belangrijk, expliciet)

Het Fase 2-plan kondigde voor Fase 3 een "OER-crawlcheck **plus** het generieke `content_hash`-register" aan. Bij uitwerking splitsen die in twee verschillend-dure signalen:

| Signaal | Mechanisme | Kosten | Fase |
|---|---|---|---|
| **Nieuwe** OER's/cohorten beschikbaar | tuple-diff `(crebo, leerweg, cohort)` tegen de DB | goedkoop (gratis bij een structured-API-instelling) | **3a (dit plan)** |
| **Bestaande** OER inhoudelijk gewijzigd upstream | `content_hash` per document vergelijken met de bron | duur (vereist het register + per-bron content-fetch) | **3b (design, hieronder)** |

De tuple-diff **consumeert het register niet**. Het register nú bouwen zou opnieuw de "register-als-fundament"-fout zijn (afgeraden in de eerdere architectuur-review). Daarom blijft het register **design-niveau (3b)**, gekoppeld aan de content-wijzigingscheck die het wél consumeert. Dit is een bewuste versmalling, geen stille weglating.

---

## File Structure

- Modify: `scripts/fetch_deltion.py` — `haal_items_op(client, cohort=None)`: `None` → leeg cohortfilter (alle cohorten).
- Create: `src/validatie_samenwijzer/oer_catalogus.py` — `CatalogusItem`, pure diff, Deltion-adapter, registry, orchestratie.
- Modify: `src/validatie_samenwijzer/bron_updates.py` — `_oer_status(online)`, `verzamel_bron_status(online)`, `--oer`-flag in `main()`.
- Test: `tests/test_oer_catalogus.py` (nieuw), `tests/test_bron_updates.py` (OER-adapter bijwerken).

---

### Task 1: `oer_catalogus`-module + alle-cohorten-query

**Files:**
- Modify: `scripts/fetch_deltion.py:88-106` (`haal_items_op`)
- Create: `src/validatie_samenwijzer/oer_catalogus.py`
- Test: `tests/test_oer_catalogus.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) CatalogusItem(crebo, leerweg, cohort, naam, instelling)` met `.sleutel -> tuple[str, str, str]`.
  - `nieuwe_oers(catalogus: list[CatalogusItem], db_tupels: set[tuple[str, str, str]]) -> list[CatalogusItem]`
  - `_tupels_uit_rows(rows, instelling: str) -> set[tuple[str, str, str]]`
  - `_items_naar_catalogus(raw_items, instelling, parse) -> list[CatalogusItem]`
  - `instelling_nieuwe_oers(instelling: str, conn=None) -> list[CatalogusItem]`
  - `_CATALOGUS_BRONNEN: dict[str, Callable[[], list[CatalogusItem]]]` (nu: `{"deltion": deltion_catalogus}`)
- Consumes: `fetch_deltion.haal_items_op(client, cohort=None)` + `fetch_deltion._record`; `db.get_alle_oers_met_instelling`.

- [ ] **Step 1: Pas `haal_items_op` aan zodat een leeg cohortfilter alle cohorten geeft**

In `scripts/fetch_deltion.py`, vervang `haal_items_op`:

```python
def haal_items_op(client: httpx.Client, cohort: str | None = None) -> list[dict]:
    """Pagineer de zoek-API. cohort=None → alle cohorten (leeg filter), zodat ook
    een gloednieuw cohort (bv. 2026-2027) wordt meegenomen; een cohortstring
    filtert op dat ene cohort (zoals bij een gerichte download)."""
    filters = {"cohort": [cohort]} if cohort else {}
    items: list[dict] = []
    offset = 0
    while True:
        resp = client.post(
            SEARCH_URL,
            params={"size": _PAGE, "offset": offset},
            json={"query": "", "filters": filters, "language": "nl"},
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
```

- [ ] **Step 2: Schrijf de falende tests**

Maak `tests/test_oer_catalogus.py`:

```python
"""Tests voor de OER-catalogus-check. Geen netwerk: de pure diff + transform
worden getest met sample-data; de instelling-adapters (HTTP) zijn geïsoleerd."""

import sys
from pathlib import Path

from validatie_samenwijzer import oer_catalogus
from validatie_samenwijzer.oer_catalogus import CatalogusItem


def _item(crebo, leerweg, cohort, naam="x", instelling="deltion"):
    return CatalogusItem(crebo, leerweg, cohort, naam, instelling)


def test_nieuwe_oers_geeft_alleen_onbekende_tupels():
    catalogus = [_item("25180", "BOL", "2025"), _item("25180", "BOL", "2026")]
    db_tupels = {("25180", "BOL", "2025")}
    nieuw = oer_catalogus.nieuwe_oers(catalogus, db_tupels)
    assert [i.sleutel for i in nieuw] == [("25180", "BOL", "2026")]  # nieuw cohort zichtbaar


def test_tupels_uit_rows_filtert_op_instelling():
    rows = [
        {"crebo": "25180", "leerweg": "BOL", "cohort": "2025", "naam": "deltion"},
        {"crebo": "25099", "leerweg": "BBL", "cohort": "2025", "naam": "curio"},
    ]
    assert oer_catalogus._tupels_uit_rows(rows, "deltion") == {("25180", "BOL", "2025")}


def test_items_naar_catalogus_slaat_none_over():
    raw = [{"id": 1}, {"id": 2}]

    def parse(item):  # simuleert fetch_deltion._record (None = onbruikbaar item)
        if item["id"] == 1:
            return {"crebo": "25180", "leerweg": "BOL", "cohort": "2026", "naam": "Kok"}
        return None

    uit = oer_catalogus._items_naar_catalogus(raw, "deltion", parse)
    assert len(uit) == 1
    assert uit[0] == CatalogusItem("25180", "BOL", "2026", "Kok", "deltion")


def test_haal_items_op_zonder_cohort_stuurt_leeg_filter(monkeypatch):
    """cohort=None mag GEEN cohortfilter sturen (anders mis je nieuwe cohorten)."""
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    sys.path.insert(0, str(scripts_dir))
    import fetch_deltion

    verstuurd = {}

    class _FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [], "meta": {"total": 0}}

    class _FakeClient:
        def post(self, url, params, json):
            verstuurd.update(json)
            return _FakeResp()

    fetch_deltion.haal_items_op(_FakeClient(), None)
    assert verstuurd["filters"] == {}  # leeg = alle cohorten

    fetch_deltion.haal_items_op(_FakeClient(), "2026-2027")
    assert verstuurd["filters"] == {"cohort": ["2026-2027"]}
```

- [ ] **Step 3: Draai de tests, verifieer dat ze falen**

Run: `uv run python -m pytest tests/test_oer_catalogus.py -q`
Expected: FAIL — `ModuleNotFoundError: validatie_samenwijzer.oer_catalogus` (en de `haal_items_op`-test faalt tot Step 1 is opgeslagen).

- [ ] **Step 4: Implementeer `oer_catalogus.py`**

Maak `src/validatie_samenwijzer/oer_catalogus.py`:

```python
"""OER-catalogus-check: zijn er nieuwe OER's/cohorten bij een instelling die wij
nog niet hebben? Tuple-diff (crebo, leerweg, cohort) tegen oer_documenten.

Netwerk-isolatie: de pure functies (`nieuwe_oers`, `_tupels_uit_rows`,
`_items_naar_catalogus`) zijn deterministisch en getest; alleen de instelling-
adapters (nu: Deltion) doen een HTTP-call. Gegate achter --oer in het rapport,
zodat het standaard `check-bron-updates` offline/instant blijft.

De Deltion-adapter vraagt met een leeg cohortfilter (alle cohorten), zodat een
gloednieuw cohort (bv. 2026-2027) als 'nieuwe OER' zichtbaar wordt.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import db

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CatalogusItem:
    crebo: str
    leerweg: str
    cohort: str
    naam: str
    instelling: str

    @property
    def sleutel(self) -> tuple[str, str, str]:
        return (self.crebo, self.leerweg, self.cohort)


def nieuwe_oers(
    catalogus: list[CatalogusItem], db_tupels: set[tuple[str, str, str]]
) -> list[CatalogusItem]:
    """Catalogus-items waarvan de (crebo, leerweg, cohort) niet in de DB staat."""
    return [item for item in catalogus if item.sleutel not in db_tupels]


def _tupels_uit_rows(rows, instelling: str) -> set[tuple[str, str, str]]:
    """De (crebo, leerweg, cohort)-set die we al hebben voor één instelling.

    `rows` = `db.get_alle_oers_met_instelling()` (sqlite3.Row of dict met de
    sleutels crebo/leerweg/cohort/naam; `naam` = instelling-key).
    """
    return {(r["crebo"], r["leerweg"], r["cohort"]) for r in rows if r["naam"] == instelling}


def _items_naar_catalogus(
    raw_items: list[dict], instelling: str, parse: Callable[[dict], dict | None]
) -> list[CatalogusItem]:
    """Pure transform: ruwe API-items → CatalogusItem via de gegeven parse-functie."""
    uit: list[CatalogusItem] = []
    for raw in raw_items:
        rec = parse(raw)
        if rec:
            uit.append(
                CatalogusItem(rec["crebo"], rec["leerweg"], rec["cohort"], rec["naam"], instelling)
            )
    return uit


def _fetch_deltion():
    """Importeer het Deltion-script (sibling in scripts/), zoals de tests dat doen."""
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import fetch_deltion

    return fetch_deltion


def deltion_catalogus() -> list[CatalogusItem]:
    """Haal de volledige Deltion-catalogus (alle cohorten) op via de SQill-API."""
    import httpx

    fd = _fetch_deltion()
    with httpx.Client(headers=fd._HEADERS, timeout=30) as client:
        raw = fd.haal_items_op(client, None)  # None = alle cohorten
    return _items_naar_catalogus(raw, "deltion", fd._record)


_CATALOGUS_BRONNEN: dict[str, Callable[[], list[CatalogusItem]]] = {
    "deltion": deltion_catalogus,
}


def instelling_nieuwe_oers(instelling: str, conn=None) -> list[CatalogusItem]:
    """Haal de catalogus van een instelling en diff tegen de DB.

    Lege lijst als er (nog) geen adapter voor de instelling is.
    """
    bron = _CATALOGUS_BRONNEN.get(instelling)
    if bron is None:
        return []
    catalogus = bron()
    eigen = conn or db.get_connection(Path(os.environ.get("DB_PATH", "data/validatie.db")))
    rows = db.get_alle_oers_met_instelling(eigen)
    return nieuwe_oers(catalogus, _tupels_uit_rows(rows, instelling))
```

- [ ] **Step 5: Draai de tests, verifieer dat ze slagen**

Run: `uv run python -m pytest tests/test_oer_catalogus.py -q`
Expected: PASS — alle 4 tests groen.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check scripts/fetch_deltion.py src/validatie_samenwijzer/oer_catalogus.py tests/test_oer_catalogus.py
git add scripts/fetch_deltion.py src/validatie_samenwijzer/oer_catalogus.py tests/test_oer_catalogus.py
git commit -m "feat(validatie): oer_catalogus — tuple-diff nieuwe OER's (Deltion, alle cohorten)"
```

---

### Task 2: OER-adapter in `bron_updates` + `--oer`-flag

**Files:**
- Modify: `src/validatie_samenwijzer/bron_updates.py` (`_oer_status`, `verzamel_bron_status`, `main`, imports)
- Test: `tests/test_bron_updates.py`

**Interfaces:**
- Consumes: `oer_catalogus.instelling_nieuwe_oers` + `oer_catalogus._CATALOGUS_BRONNEN` (Task 1).
- Produces: `_oer_status(online: bool = False)`, `verzamel_bron_status(online: bool = False)`. Offline = huidige handmatig-status (met `--oer`-hint). Online = per adapter-instelling de diff, geaggregeerd.

- [ ] **Step 1: Schrijf de falende tests**

Voeg toe / vervang in `tests/test_bron_updates.py` (de bestaande `test_oer_status_is_handmatig` blijft de offline-tak toetsen; voeg de online-tak toe):

```python
def test_oer_status_offline_hint_naar_oer_flag(gemockte_bronnen):
    oer = {s.bron: s for s in bron_updates.verzamel_bron_status()}["oer"]
    assert oer.automatisch is False
    assert "--oer" in oer.signaal  # offline: verwijs naar de online-modus


def test_oer_status_online_aggregeert_nieuwe_oers(monkeypatch):
    from validatie_samenwijzer.oer_catalogus import CatalogusItem

    monkeypatch.setattr(
        bron_updates.oer_catalogus,
        "_CATALOGUS_BRONNEN",
        {"deltion": lambda: []},  # alleen de sleutels tellen voor "welke adapters"
    )
    monkeypatch.setattr(
        bron_updates.oer_catalogus,
        "instelling_nieuwe_oers",
        lambda inst, conn=None: [CatalogusItem("25180", "BOL", "2026", "Kok", "deltion")],
    )
    oer = bron_updates._oer_status(online=True)
    assert oer.automatisch is True
    assert "1" in oer.signaal and "deltion" in oer.signaal
    assert oer.details["nieuw_per_instelling"]["deltion"] == [("25180", "BOL", "2026")]
```

- [ ] **Step 2: Draai de tests, verifieer dat ze falen**

Run: `uv run python -m pytest tests/test_bron_updates.py -q`
Expected: FAIL — `bron_updates.oer_catalogus` bestaat nog niet / `_oer_status` mist de `online`-parameter.

- [ ] **Step 3: Werk `bron_updates.py` bij**

Voeg `oer_catalogus` toe aan de import:

```python
from . import kd_bundel, oer_catalogus, sync_afgeleid
```

Vervang `_oer_status`:

```python
def _oer_status(online: bool = False) -> BronStatus:
    if not online:
        return BronStatus(
            "oer",
            automatisch=False,
            signaal="OER-catalogus-check niet gedraaid — gebruik `check-bron-updates --oer`",
            details={"crawlbaar": _OER_CRAWLBAAR, "niet_crawlbaar": _OER_NIET_CRAWLBAAR},
        )
    nieuw: dict[str, list] = {}
    for inst in sorted(oer_catalogus._CATALOGUS_BRONNEN):
        items = oer_catalogus.instelling_nieuwe_oers(inst)
        if items:
            nieuw[inst] = items
    n_totaal = sum(len(v) for v in nieuw.values())
    rest = sorted(set(_OER_CRAWLBAAR) - set(oer_catalogus._CATALOGUS_BRONNEN))
    if n_totaal:
        per = ", ".join(f"{i}: {len(v)}" for i, v in sorted(nieuw.items()))
        signaal = f"{n_totaal} nieuwe OER('s) beschikbaar ({per}); {len(rest)} instelling(en) handmatig"
    else:
        signaal = f"geen nieuwe OER's via API; {len(rest)} instelling(en) nog handmatig"
    return BronStatus(
        "oer",
        automatisch=True,
        signaal=signaal,
        details={
            "nieuw_per_instelling": {i: [it.sleutel for it in v] for i, v in nieuw.items()},
            "handmatig": rest,
            "niet_crawlbaar": _OER_NIET_CRAWLBAAR,
        },
    )
```

Pas `verzamel_bron_status` aan zodat de flag wordt doorgegeven:

```python
def verzamel_bron_status(online: bool = False) -> list[BronStatus]:
    return [_skills_status(), _kd_status(), _oer_status(online=online)]
```

En `main()`:

```python
def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Bronactualiteit-rapport")
    parser.add_argument(
        "--oer", action="store_true", help="Draai ook de online OER-catalogus-check (netwerk)"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        statussen = verzamel_bron_status(online=args.oer)
    except sqlite3.OperationalError as e:
        logger.error("Kan de database niet lezen (%s) — is DB_PATH correct?", e)
        return 1
    print(rapporteer(statussen))
    return 0
```

- [ ] **Step 4: Draai de tests, verifieer dat ze slagen**

Run: `uv run python -m pytest tests/test_bron_updates.py tests/test_oer_catalogus.py -q`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/validatie_samenwijzer/bron_updates.py tests/test_bron_updates.py
git add src/validatie_samenwijzer/bron_updates.py tests/test_bron_updates.py
git commit -m "feat(validatie): --oer-flag draait online OER-catalogus-check"
```

---

### Task 3: Live rooktest + volledige suite

**Files:** geen (verificatie).

- [ ] **Step 1: Live Deltion-check tegen de echte API + DB**

Run: `uv run check-bron-updates --oer`
Expected: de OER-regel toont nu een echt signaal, bv. `[auto] oer — N nieuwe OER('s) beschikbaar (deltion: N); 5 instelling(en) handmatig`. (Deltion publiceert al 2026-2027-items; die horen als nieuw te verschijnen omdat onze Deltion-set cohort 2025 is.) Zonder `--oer` blijft de regel `OER-catalogus-check niet gedraaid — gebruik ...`.

- [ ] **Step 2: Volledige suite + lint**

Run:
```bash
uv run python -m pytest -q
uv run ruff check src/ scripts/ tests/
```
Expected: alles groen.

- [ ] **Step 3: Commit (alleen als Step 1/2 nog een tweak vergden; anders niets)**

---

## Design-niveau (vervolgplannen)

### 3a-vervolg — overige crawlbare instellingen

Voeg per instelling een adapter toe aan `_CATALOGUS_BRONNEN`, volgens hetzelfde contract (`() -> list[CatalogusItem]`). Recept per instelling (zie de reference-memory `reference_samenwijzer_oer_bronnen`):

- **Curio** — directe per-crebo PDF-URL's; crebo uit bestandsnaam.
- **Rijn IJssel** — sitemap → opleidingpagina's met crebo's.
- **Aeres** — media-pad per cohort; per-crebo `examenplan-<crebo>-…`.
- **Talland** — Educator-API per sector → program-UUID's (let op 504 bij parallelisme).
- **MBO Utrecht** — sitemap → academie-pagina's; **crebo zit in de PDF-inhoud, niet in de bestandsnaam**.

> **Contract-implicatie (advisor):** vorm `CatalogusItem` + de adapter zo dat de crebo **niet gratis uit de listing** hoeft te komen. MBO Utrecht vereist een PDF-open om de crebo te bepalen; het adapter-contract moet dus toestaan dat een adapter de crebo zelf moet ophalen (eventueel met een per-item fetch), niet aannemen dat de listing 'm meelevert zoals bij Deltion. Houd de listing-stap en de crebo-resolutiestap gescheiden.

Niet-crawlbaar (blijven handmatig, expliciet in het rapport): KWIC, Graafschap, Da Vinci.

### 3b — `content_hash`-register + content-wijzigingsdetectie

Detecteer dat een OER die we **al** hebben, upstream is **herzien** (zelfde crebo/cohort, andere inhoud):

- Voeg `content_hash`, `laatst_gecheckt`, `bron_url` toe aan `oer_documenten` + `instelling_documenten`. **Migratie**: idempotente `ALTER TABLE ADD COLUMN` geguard met `pragma table_info` (live `validatie.db`). Aangrijppunten: `db.py` (`voeg_oer_document_toe`, `update_oer_bestandspad`, `voeg_instelling_document_toe`, CREATE TABLE), `ingest.py` (`_verwerk_bestand`, `_verwerk_instelling_documenten`) berekenen SHA256 van de bronbytes + `laatst_gecheckt`.
- De content-wijzigingscheck fetcht per bekende OER de bron (bv. Deltion `/reports/<uuid>/html`) en vergelijkt de hash. Dit is **duur** (één fetch per document) → eigen flag, eigen plan.

### 3c — `/beheer`-pagina + scheduling

- **Bronactualiteit-paneel** achter `/beheer` (`BEHEER_ENABLED`) dat `verzamel_bron_status(online=…)` toont — geen logica in de route, hergebruik de module. Online-knop expliciet (netwerk).
- **GitHub Action** (wekelijks) draait `check-bron-updates --oer`; bij een niet-leeg signaal opent/actualiseert hij een issue. Sluit aan op het `checkin.yml`-patroon in de parent-repo.

---

## Self-Review

**Spec-dekking.** "Detecteer nieuwe OER's/cohorten" → Task 1 (catalogus + pure diff + Deltion-adapter, alle cohorten), Task 2 (`--oer` + rapportage), Task 3 (live verificatie). De duurdere content-wijzigingscheck + register (3b), overige instellingen (3a-vervolg) en weergave/scheduling (3c) zijn expliciet als vervolg belegd — niet stil weggelaten.

**Placeholder-scan.** Alle code-stappen bevatten volledige code; geen "TBD"/"handle errors"-platzhouders. De design-secties bevatten bewust geen checkbox-taken (scope-check writing-plans).

**Type-consistentie.** `CatalogusItem(crebo, leerweg, cohort, naam, instelling)` + `.sleutel: tuple[str,str,str]` wordt overal consistent gebruikt (`nieuwe_oers`, `_items_naar_catalogus`, `instelling_nieuwe_oers`, de tests, en `_oer_status`-details). `instelling_nieuwe_oers(instelling, conn=None)` matcht de mock in de bron_updates-test. `haal_items_op(client, cohort=None)` matcht de leeg-filter-test.
