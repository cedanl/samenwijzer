# Bronactualiteit-detectie Implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Een out-of-band `check_bron_updates`-rapport dat zichtbaar maakt of er updates beschikbaar zijn voor onze vier bronnen, te beginnen met het enige bron waar upstream-detectie vandaag al (bijna) bestaat: de skills-taxonomie.

**Architecture:** Eén rapportcommando met per-bron *adapters*. Elke adapter levert een `BronStatus` (signaal + details). De checks draaien **out-of-band** (CLI/cron/GitHub Action), nooit in het FastAPI-request-pad. Increment 1 implementeert de skills-adapter (echte upstream-signaal via een nieuwe dry-run op `refresh_fallbacks`) + een KD-dekkingsadapter; OER- en KD-bundel-upstreamchecks en een `/beheer`-pagina zijn ontworpen maar uitbesteed aan vervolgplannen.

**Tech Stack:** Python 3.13, sqlite (`db.py`), pytest, `uv`. Bestaande modules: `scripts/build_skills_taxonomie.py` (`refresh_fallbacks`), `src/validatie_samenwijzer/sync_afgeleid.py`, `src/validatie_samenwijzer/competentnl_bron.py`.

## Global Constraints

- **Out-of-band, nooit in het request-pad** — checks draaien als CLI/cron/Action; ze raken geen FastAPI-route. Een toekomstige weergave zit achter het bestaande `/beheer` (`BEHEER_ENABLED=true`).
- **Geen mutatie tijdens een check** — een "is er een update?"-rapport schrijft nooit naar `data/skills/`, `kwalificatiedossiers/` of de DB.
- **Niet-crawlbare instellingen melden "handmatige check"**, niet falen (KWIC, Graafschap, Da Vinci).
- **`allowed_domains`-valkuil** — als een latere OER-check `web_search`/`web_fetch` gebruikt: één niet-crawlbaar domein geeft een 400 op de héle call; alleen geverifieerd-crawlbare domeinen meesturen.
- **DB-migratie (alleen vervolgfase)**: `ALTER TABLE ADD COLUMN` geguard met `pragma table_info` — `validatie.db` bevat live data en gebruikt `CREATE TABLE IF NOT EXISTS`.
- Lint: line-length 100, selectie `E,F,I,N,W,UP`. Draai `ruff` + `pytest` lokaal (geen CI-gate voor dit subproject).

---

## Context: welk probleem

De pijplijn *reageert* op bestanden die een mens aanlevert (watcher + rclone-sync), maar *detecteert niet* of er bij de bron een nieuwere versie is. Dit is exact de fase-1-onzekerheid uit het projectplan ("datakwaliteit en versiebeheer van OER's verschilt per instelling"). De vier bronnen verschillen sterk in hoe haalbaar upstream-detectie is — daarom een gefaseerde aanpak die leidt met het goedkoopste echte signaal.

### Haalbaarheid per bron (feitelijk onderbouwd)

| Bron | Identiteit / opslag | Bestaand actualiteitssignaal | Haalbaarheid upstream-check | Fase |
|---|---|---|---|---|
| **Skills** (CompetentNL/ESCO) | `data/skills/<crebo>.json`, géén versieveld | `refresh_fallbacks()` her-checkt ESCO-crebo's tegen CompetentNL en upgrade't hits — **dit ís de upstream-detectie**, maar muteert direct (geen dry-run) | **Hoog** — alleen een dry-run nodig op bestaande code | **1** |
| **KD** (SBB / s-bb.nl) | `kwalificatiedossiers/pdfs/<crebo>.{pdf,md}`, geen bundel-manifest | `download_kwalificatiedossiers.py` extraheert al "Geldig vanaf" per PDF maar gebruikt het niet; zips worden handmatig gedownload | **Midden** — dekkingsgaten zijn nu te rapporteren; échte bundel-versheid vereist een nieuwe SBB-fetcher/hash-vergelijking | **1** (dekking) + **2** (bundel) |
| **OER** | `oer_documenten(instelling_id,crebo,cohort,leerweg)`, géén hash/URL/check-datum | alleen Deltion heeft een `--preview`-script; rest is "recept", geen code | **Laag/duur** — per-instelling catalogus-crawl; crawlbaar: Rijn IJssel, Curio, Aeres, MBO Utrecht, Talland, Deltion. Niet: KWIC, Graafschap, Da Vinci | **3** |
| **Instellingsregelingen** | `instelling_documenten(instelling_id,soort)`, `toegevoegd_op` aanwezig | padverandering reset `geindexeerd=0` | **Laag/duur** — zelfde crawlroute als OER | **3** |

### Gefaseerde roadmap

- **Fase 1 (DIT plan, gedetailleerd):** skills dry-run + `check_bron_updates`-rapport (skills-upgrades + KD-dekkingsgaten + eerlijke "handmatig"-status voor OER). Levert meteen een zichtbaar signaal, zonder migratie of crawl.
- **Fase 2 (apart plan — ontwerp hieronder):** generiek **bron-register** (`content_hash`, `laatst_gecheckt`, `bron_url` op `oer_documenten`/`instelling_documenten`) + **KD-bundel-versheidscheck** (SBB-crebolijst-jaar / zip-hash vs. opgeslagen manifest).
- **Fase 3 (apart plan — ontwerp hieronder):** **OER-/instellingscatalogus-crawlcheck** (hergebruik bestaand crawl-recept in preview/diff-modus) + **"Bronactualiteit"-pagina achter `/beheer`** + **scheduling** (GitHub Action die het rapport draait en bij wijziging een issue opent).

---

## File Structure (Fase 1)

- Modify: `scripts/build_skills_taxonomie.py` — `refresh_fallbacks()` krijgt een `dry_run`-parameter + `--dry-run` CLI-flag.
- Create: `src/validatie_samenwijzer/bron_updates.py` — aggregator met per-bron adapters, `verzamel_bron_status()`, `rapporteer()` en `main()` (console-script `check-bron-updates`).
- Modify: `pyproject.toml` — registreer `check-bron-updates` onder `[project.scripts]`.
- Test: `tests/test_refresh_fallbacks.py` — dry-run-gedrag (bestaand bestand).
- Test: `tests/test_bron_updates.py` — adapters + rapport (nieuw bestand).

---

### Task 1: Dry-run op `refresh_fallbacks`

Maakt het mogelijk om upgrade-kansen te rapporteren zónder `data/skills/` te muteren.

**Files:**
- Modify: `scripts/build_skills_taxonomie.py:176-227` (`refresh_fallbacks`) en `:66-81` (`main`)
- Test: `tests/test_refresh_fallbacks.py`

**Interfaces:**
- Produces: `refresh_fallbacks(dry_run: bool = False) -> tuple[list[str], list[str]]`. Met `dry_run=True` schrijft het niets weg (geen `pad.write_text`, geen `_schrijf_overzicht`) maar retourneert dezelfde `(upgraded, nog_fallback)`-lijsten alsof het gedraaid had. CLI: `--dry-run` (alleen zinvol samen met `--refresh-fallbacks`).

- [ ] **Step 1: Schrijf de falende test (dry-run muteert niet, rapporteert wel)**

Voeg toe aan `tests/test_refresh_fallbacks.py`:

```python
def test_dry_run_rapporteert_zonder_te_muteren(skills_dir, monkeypatch):
    pad = skills_dir / "25180.json"
    origineel = _esco_json("25180")
    pad.write_text(origineel, encoding="utf-8")

    def fake(crebo, opleiding):
        return SkillsRecord(
            crebo=crebo,
            opleiding=opleiding,
            bron="CompetentNL",
            beroep=Beroep(label="Kok", uri="", definitie="..."),
            skills=[Skill(label="koken", uri="cnl:s1", categorie="essentieel")],
            match_methode="crebo-direct",
            kandidaten=[],
        )

    monkeypatch.setattr(bst.competentnl_bron, "haal_skills_record", fake)

    upgraded, nog_fallback = bst.refresh_fallbacks(dry_run=True)

    assert upgraded == ["25180"]          # zou upgraden
    assert nog_fallback == []
    assert pad.read_text(encoding="utf-8") == origineel  # byte-identiek: niets geschreven
    assert not (skills_dir / "_match_overzicht.csv").exists()  # geen overzicht in dry-run
```

- [ ] **Step 2: Draai de test, verifieer dat hij faalt**

Run: `uv run python -m pytest tests/test_refresh_fallbacks.py::test_dry_run_rapporteert_zonder_te_muteren -v`
Expected: FAIL — `refresh_fallbacks()` accepteert nog geen `dry_run` (TypeError: unexpected keyword argument).

- [ ] **Step 3: Voeg de `dry_run`-parameter toe**

Vervang in `scripts/build_skills_taxonomie.py` de signatuur en de schrijf-tak van `refresh_fallbacks`:

```python
def refresh_fallbacks(dry_run: bool = False) -> tuple[list[str], list[str]]:
```

Vervang het schrijf-blok (huidig regel 207-212) door:

```python
        nieuw = competentnl_bron.haal_skills_record(crebo, opleiding)
        if nieuw is not None and nieuw.skills:
            if not dry_run:
                pad.write_text(
                    json.dumps(nieuw.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
                )
            upgraded.append(crebo)
            logger.info(
                "%s %s → CompetentNL (%d skills)",
                "ZOU UPGRADEN" if dry_run else "UPGRADE",
                crebo,
                len(nieuw.skills),
            )
        else:
            nog_fallback.append(crebo)
```

Vervang de `_schrijf_overzicht`-aanroep (huidig regel 216-217) door:

```python
    if upgraded and not dry_run:
        _schrijf_overzicht()
```

- [ ] **Step 4: Wire de `--dry-run` CLI-flag**

In `main()` (na de bestaande `--refresh-fallbacks`-arg, regel 71-75) toevoegen:

```python
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Met --refresh-fallbacks: rapporteer upgrades zonder te schrijven",
    )
```

En de dispatch (regel 79-81) wijzigen naar:

```python
    if args.refresh_fallbacks:
        refresh_fallbacks(dry_run=args.dry_run)
        return 0
```

- [ ] **Step 5: Draai de tests, verifieer dat ze slagen (incl. regressie)**

Run: `uv run python -m pytest tests/test_refresh_fallbacks.py -v`
Expected: PASS — de nieuwe test + alle bestaande (de bestaande roepen `refresh_fallbacks()` zonder argument; default `dry_run=False` behoudt het oude gedrag).

- [ ] **Step 6: Commit**

```bash
git add scripts/build_skills_taxonomie.py tests/test_refresh_fallbacks.py
git commit -m "feat(validatie): dry-run op refresh_fallbacks voor bronactualiteit-rapport"
```

---

### Task 2: `check_bron_updates`-rapport met per-bron adapters

Eén commando dat per bron een status oplevert; skills geeft het echte upstream-signaal, KD de dekkingsgaten, OER een eerlijke "handmatig"-status.

**Files:**
- Create: `src/validatie_samenwijzer/bron_updates.py`
- Modify: `pyproject.toml` (`[project.scripts]`)
- Test: `tests/test_bron_updates.py`

**Interfaces:**
- Consumes: `refresh_fallbacks(dry_run=True)` uit Task 1; `sync_afgeleid.geindexeerde_crebos() -> set[str]` en de module-constante `sync_afgeleid._KD_DIR` (Path naar `kwalificatiedossiers/pdfs`).
- Produces:
  - `@dataclass BronStatus(bron: str, automatisch: bool, signaal: str, details: dict)`
  - `verzamel_bron_status() -> list[BronStatus]`
  - `rapporteer(statussen: list[BronStatus]) -> str` (mensleesbaar blok)
  - `main() -> int` (console-script `check-bron-updates`)

- [ ] **Step 1: Schrijf de falende tests**

Maak `tests/test_bron_updates.py`:

```python
"""Tests voor het bronactualiteit-rapport. Geen netwerk: skills-check en
geïndexeerde crebo's worden gemockt."""

import sys
from pathlib import Path

import pytest

from validatie_samenwijzer import bron_updates, sync_afgeleid


@pytest.fixture
def gemockte_bronnen(tmp_path, monkeypatch):
    kd_dir = tmp_path / "kd"
    kd_dir.mkdir()
    (kd_dir / "25180.md").write_text("kd", encoding="utf-8")  # 25180 heeft dekking
    monkeypatch.setattr(sync_afgeleid, "_KD_DIR", kd_dir)
    monkeypatch.setattr(sync_afgeleid, "geindexeerde_crebos", lambda: {"25180", "23110"})
    # skills-adapter: 1 upgrade beschikbaar
    monkeypatch.setattr(bron_updates, "_skills_dry_run", lambda: (["25180"], ["23110"]))
    return tmp_path


def test_skills_status_meldt_upgrades(gemockte_bronnen):
    statussen = {s.bron: s for s in bron_updates.verzamel_bron_status()}
    skills = statussen["skills"]
    assert skills.automatisch is True
    assert skills.details["upgrades"] == ["25180"]
    assert "1" in skills.signaal


def test_kd_status_meldt_dekkingsgaten(gemockte_bronnen):
    kd = {s.bron: s for s in bron_updates.verzamel_bron_status()}["kd"]
    assert kd.details["ontbrekende_dekking"] == ["23110"]  # 25180 heeft .md, 23110 niet
    assert kd.automatisch is False  # bundel-versheid niet geautomatiseerd


def test_oer_status_is_handmatig(gemockte_bronnen):
    oer = {s.bron: s for s in bron_updates.verzamel_bron_status()}["oer"]
    assert oer.automatisch is False
    assert "davinci" in oer.details["niet_crawlbaar"]
    assert "rijn_ijssel" in oer.details["crawlbaar"]


def test_rapporteer_bevat_alle_bronnen(gemockte_bronnen):
    tekst = bron_updates.rapporteer(bron_updates.verzamel_bron_status())
    for bron in ("skills", "kd", "oer"):
        assert bron in tekst
```

- [ ] **Step 2: Draai de tests, verifieer dat ze falen**

Run: `uv run python -m pytest tests/test_bron_updates.py -v`
Expected: FAIL — `ModuleNotFoundError: validatie_samenwijzer.bron_updates`.

- [ ] **Step 3: Implementeer `bron_updates.py`**

Maak `src/validatie_samenwijzer/bron_updates.py`:

```python
"""Bronactualiteit-rapport: is er voor onze bronnen iets nieuws bij de bron?

Out-of-band ops-tool (CLI/cron/Action) — nooit in het FastAPI-request-pad, en
muteert niets. Per bron een adapter die een ``BronStatus`` oplevert:

- skills: echte upstream-detectie via ``refresh_fallbacks(dry_run=True)``
  (welke ESCO-crebo's nu een CompetentNL-match hebben).
- kd: dekkingsgaten (geïndexeerde crebo's zonder KD-bestand). Bundel-versheid
  bij SBB is (nog) niet geautomatiseerd — zie het bronactualiteit-roadmapplan.
- oer/instellingsregelingen: niet geautomatiseerd; meldt de handmatige
  catalogus-crawlroute en welke instellingen crawlbaar zijn.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import sync_afgeleid

logger = logging.getLogger(__name__)

# Crawlbaarheid per instelling (juni 2026 in kaart gebracht; zie reference-memory
# + scripts/fetch_deltion.py). Bepaalt of een OER-/instellingscatalogus-check
# geautomatiseerd kan worden (Fase 3) of handmatig blijft.
_OER_CRAWLBAAR = ["aeres", "curio", "deltion", "rijn_ijssel", "talland", "utrecht"]
_OER_NIET_CRAWLBAAR = ["davinci", "graafschap", "kwic"]


@dataclass
class BronStatus:
    bron: str
    automatisch: bool
    signaal: str
    details: dict = field(default_factory=dict)


def _skills_dry_run() -> tuple[list[str], list[str]]:
    """Importeer het build-script (sibling in scripts/) en draai de dry-run.

    scripts/ is geen package; we voegen het pad toe zoals tests/sync_afgeleid dat
    ook doen. Gebeurt lui zodat een import van deze module goedkoop blijft.
    """
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import build_skills_taxonomie as bst

    return bst.refresh_fallbacks(dry_run=True)


def _skills_status() -> BronStatus:
    upgraded, _nog_fallback = _skills_dry_run()
    signaal = (
        f"{len(upgraded)} skills-upgrade(s) naar CompetentNL beschikbaar"
        if upgraded
        else "geen skills-upgrades beschikbaar"
    )
    return BronStatus("skills", automatisch=True, signaal=signaal, details={"upgrades": upgraded})


def _kd_status() -> BronStatus:
    crebos = sync_afgeleid.geindexeerde_crebos()
    aanwezig = {p.stem for p in sync_afgeleid._KD_DIR.glob("*.md")}
    ontbrekend = sorted(crebos - aanwezig)
    signaal = (
        f"{len(ontbrekend)} crebo('s) zonder KD-dekking; SBB-bundel-versheid niet geautomatiseerd"
        if ontbrekend
        else "KD-dekking compleet; SBB-bundel-versheid niet geautomatiseerd"
    )
    return BronStatus(
        "kd", automatisch=False, signaal=signaal, details={"ontbrekende_dekking": ontbrekend}
    )


def _oer_status() -> BronStatus:
    return BronStatus(
        "oer",
        automatisch=False,
        signaal="OER-/instellingscatalogus-check niet geautomatiseerd — handmatige crawl",
        details={"crawlbaar": _OER_CRAWLBAAR, "niet_crawlbaar": _OER_NIET_CRAWLBAAR},
    )


def verzamel_bron_status() -> list[BronStatus]:
    return [_skills_status(), _kd_status(), _oer_status()]


def rapporteer(statussen: list[BronStatus]) -> str:
    regels = ["Bronactualiteit-rapport", "=" * 24]
    for s in statussen:
        markering = "auto" if s.automatisch else "handmatig"
        regels.append(f"[{markering:9}] {s.bron:6} — {s.signaal}")
    return "\n".join(regels)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(rapporteer(verzamel_bron_status()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Draai de tests, verifieer dat ze slagen**

Run: `uv run python -m pytest tests/test_bron_updates.py -v`
Expected: PASS — alle vier de tests groen.

- [ ] **Step 5: Registreer het console-script**

In `pyproject.toml`, onder `[project.scripts]` (naast `ingest` en `watcher`):

```toml
check-bron-updates = "validatie_samenwijzer.bron_updates:main"
```

- [ ] **Step 6: Handmatige rooktest + lint**

Run:
```bash
uv sync
uv run python -m validatie_samenwijzer.bron_updates
uv run ruff check src/validatie_samenwijzer/bron_updates.py tests/test_bron_updates.py
```
Expected: een rapport met drie regels (skills/kd/oer); ruff schoon. (Zonder `COMPETENTNL_API_KEY` meldt de skills-regel "geen skills-upgrades" + een waarschuwing uit `refresh_fallbacks` — dat is correct gedrag.)

- [ ] **Step 7: Commit**

```bash
git add src/validatie_samenwijzer/bron_updates.py tests/test_bron_updates.py pyproject.toml
git commit -m "feat(validatie): check_bron_updates-rapport (skills upstream + KD-dekking + OER-status)"
```

---

## Vervolgfasen (aparte plannen — ontwerp, geen taken)

### Fase 2 — Bron-register + KD-bundel-versheidscheck

**Bron-register.** Voeg op `oer_documenten` en `instelling_documenten` drie kolommen toe: `content_hash TEXT`, `laatst_gecheckt TEXT`, `bron_url TEXT`. Populeer ze in `ingest.py` (`_verwerk_bestand` ~451-536, `_verwerk_instelling_documenten` ~563-611) met de SHA256 van de bronbytes en `datetime('now')`. Aangrijppunten in `db.py`: `voeg_oer_document_toe` (~155-172), `update_oer_bestandspad` (~207-210), `voeg_instelling_document_toe` (~213-252). **Migratie**: idempotente `ALTER TABLE ADD COLUMN` geguard met `pragma table_info` (live `validatie.db`). Waarde: hash detecteert inhoudswijziging bij gelijk pad én voorkomt onnodig herindexeren; het is het vergelijkingsanker voor een upstream-fetcher. *Let op (advisor):* een hash van het bestand dat we al hebben zegt op zichzelf niets over upstream — bouw het register pas wanneer een KD/OER-adapter het echt vergelijkt, niet als losstaand fundament.

**KD-bundel-check.** Nieuwe adapter in `bron_updates.py` + helper bij `download_kwalificatiedossiers.py`: vergelijk het nieuwste SBB-crebolijst-jaar (`kwalificatiedossiers/lijsten/crebo_YYYY.xlsx`) en/of een zip-hash tegen een opgeslagen `bundle_manifest.json`. Hergebruik de al-geëxtraheerde "Geldig vanaf"-datums (`download_rapport.json`). Dit vereist een echte SBB-fetch/HEAD (bestaat nog niet); houd het achter een expliciete flag wegens netwerk.

### Fase 3 — OER-crawlcheck + weergave + scheduling

**OER-/instellingscatalogus-check.** Per crawlbare instelling (Rijn IJssel, Curio, Aeres, MBO Utrecht, Talland, Deltion) de bestaande catalogus-crawl in *preview/diff*-modus draaien: list de cataloguspagina's, resolve crebo/cohort, diff tegen `oer_documenten` → "nieuwe cohorten/crebo's/gewijzigde PDF's (hash)". Niet-crawlbare instellingen (KWIC, Graafschap, Da Vinci) blijven "handmatig". Respecteer de `allowed_domains`-valkuil bij `web_search`/`web_fetch`.

**Weergave.** Een "Bronactualiteit"-paneel achter `/beheer` (`BEHEER_ENABLED`) dat `verzamel_bron_status()` toont — geen logica in de route, hergebruik de module.

**Scheduling.** Een GitHub Action (wekelijks) draait `check-bron-updates`; bij een niet-leeg signaal opent/actualiseert hij een issue. Sluit aan op het bestaande `checkin.yml`-patroon in de parent-repo.

---

## Self-Review

**Spec-dekking.** De vraag "kunnen we onderzoeken of er updates zijn?" → Fase 1 levert een draaiend rapport met een echt skills-signaal + KD-dekkingsgaten + eerlijke OER-status. De duurdere upstream-checks (KD-bundel, OER-crawl) en het register zijn expliciet als vervolgplannen belegd, niet stilzwijgend weggelaten.

**Placeholder-scan.** Alle code-stappen bevatten volledige code; geen "TBD"/"handle errors"-platzhouders. De vervolgfasen zijn bewust ontwerp (geen checkbox-taken), conform de scope-check van de writing-plans-skill.

**Type-consistentie.** `refresh_fallbacks(dry_run=...) -> tuple[list[str], list[str]]` wordt in Task 2 via `_skills_dry_run()` consistent geconsumeerd. `BronStatus(bron, automatisch, signaal, details)` matcht in module, tests en `rapporteer()`. `sync_afgeleid.geindexeerde_crebos()` en `sync_afgeleid._KD_DIR` zijn geverifieerd aanwezig.
