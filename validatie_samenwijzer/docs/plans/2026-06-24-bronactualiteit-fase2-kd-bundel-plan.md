# Bronactualiteit Fase 2 — KD-bundel-versheidscheck Implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detecteer of de lokale KD-bundel (s-bb.nl) is gewijzigd sinds de laatste ingest, en surface het crebolijst-jaar dat we hebben — via een bundelmanifest dat het bestaande `check-bron-updates`-rapport voedt.

**Architecture:** Een nieuw `kd_bundel`-module registreert de huidige bundel (SHA256 per SBB-zip + nieuwste crebolijst-jaar) in `kwalificatiedossiers/bundle_manifest.json`. De KD-adapter in `bron_updates` vergelijkt de live bundel met dat manifest → `in_sync` / `gewijzigd` / `geen_manifest`, naast de bestaande dekkingsgaten. Geen netwerk: alles werkt op de lokale (Box-gesyncte) bestanden.

**Tech Stack:** Python 3.13, stdlib (`hashlib`, `json`, `re`, `datetime`), pytest, `uv`. Sluit aan op Fase 1: `src/validatie_samenwijzer/bron_updates.py`, `scripts/download_kwalificatiedossiers.py`.

## Global Constraints

- **Out-of-band, muteert niets tijdens een check** — `bundel_status()` leest alleen; alleen `schrijf_manifest()` (na een download of expliciet aangeroepen) schrijft.
- **Geen netwerk in Fase 2** — een echte "heeft SBB een nieuwer jaar?"-upstream-HEAD is bewust uitgesteld (zie *Buiten scope*). Het manifest surfaced het crebolijst-jaar dat we hebben, zodat een mens dat tegen s-bb.nl kan houden.
- **Manifest is Box-artefact, niet git-tracked** — `kwalificatiedossiers/` is volledig gitignored (`.gitignore:52`); `bundle_manifest.json` leeft daar net als `download_rapport.json`, per machine/Box.
- Lint: line-length 100, selectie `E,F,I,N,W,UP`. Draai `ruff` + `pytest` lokaal (geen CI-gate voor dit subproject).

---

## Scope-herziening t.o.v. het Fase 1-roadmap

Het Fase 1-plan noemde voor Fase 2 "een generiek bron-register (`content_hash`, `laatst_gecheckt`, `bron_url` op `oer_documenten`/`instelling_documenten`) **plus** een KD-bundel-versheidscheck". Bij uitwerking blijkt:

- De **KD-bundel-check werkt op bestanden** (SBB-zips), niet op de `oer_documenten`-tabel — KD leeft als bestanden per crebo, niet als DB-records met een hash. Het DB-register voegt hier dus niets toe.
- Het **generieke DB-register hoort bij de OER-hash-diff** (catalogus-crawl), die in Fase 3 zit. Conform de eerdere architectuur-review ("bouw het register niet als losstaand fundament; trek `content_hash` erbij wanneer een adapter het echt vergelijkt") verhuist het register daarom naar **Fase 3**, gekoppeld aan de OER-crawlcheck die het daadwerkelijk consumeert.

Fase 2 is daarmee een zelfstandige, KD-specifieke slice die meteen een zichtbaar signaal oplevert. Dit is een bewuste versmalling, niet een stille weglating.

---

## File Structure

- Create: `src/validatie_samenwijzer/kd_bundel.py` — manifest schrijven/lezen + `bundel_status()` + `__main__`.
- Modify: `src/validatie_samenwijzer/bron_updates.py` — `_kd_status()` gebruikt `kd_bundel.bundel_status()`.
- Modify: `scripts/download_kwalificatiedossiers.py` — schrijf het manifest na een succesvolle download.
- Test: `tests/test_kd_bundel.py` (nieuw), `tests/test_bron_updates.py` (KD-adapter bijwerken).

---

### Task 1: `kd_bundel`-module (manifest + status)

**Files:**
- Create: `src/validatie_samenwijzer/kd_bundel.py`
- Test: `tests/test_kd_bundel.py`

**Interfaces:**
- Produces:
  - `huidige_zip_hashes(kwal_dir: Path = _KWAL_DIR) -> dict[str, str]`
  - `nieuwste_crebolijst_jaar(kwal_dir: Path = _KWAL_DIR) -> int | None`
  - `schrijf_manifest(kwal_dir: Path = _KWAL_DIR, *, nu: str | None = None) -> dict`
  - `lees_manifest(kwal_dir: Path = _KWAL_DIR) -> dict | None`
  - `bundel_status(kwal_dir: Path = _KWAL_DIR) -> dict` met sleutels `toestand` (`"geen_manifest"|"gewijzigd"|"in_sync"`), `crebolijst_jaar` (`int|None`), `gewijzigde_zips` (`list[str]`).
  - `main() -> int` (CLI `python -m validatie_samenwijzer.kd_bundel` → schrijft manifest).

- [ ] **Step 1: Schrijf de falende tests**

Maak `tests/test_kd_bundel.py`:

```python
"""Tests voor het KD-bundelmanifest. Geen netwerk: werkt op nep-zips in tmp_path."""

import json

import pytest

from validatie_samenwijzer import kd_bundel


@pytest.fixture
def bundel(tmp_path):
    """Een nep-bundel: 4 'zips' + crebolijsten (incl. de 2025april-variant)."""
    (tmp_path / "ae.zip").write_bytes(b"ae-v1")
    (tmp_path / "fl.zip").write_bytes(b"fl-v1")
    (tmp_path / "mr.zip").write_bytes(b"mr-v1")
    (tmp_path / "sz.zip").write_bytes(b"sz-v1")
    lijsten = tmp_path / "lijsten"
    lijsten.mkdir()
    for naam in ("crebo_2024.xlsx", "crebo_2025.xlsx", "crebo_2025april.xlsx"):
        (lijsten / naam).write_bytes(b"x")
    return tmp_path


def test_nieuwste_crebolijst_jaar(bundel):
    assert kd_bundel.nieuwste_crebolijst_jaar(bundel) == 2025  # 2025april telt als 2025


def test_nieuwste_crebolijst_jaar_leeg(tmp_path):
    (tmp_path / "lijsten").mkdir()
    assert kd_bundel.nieuwste_crebolijst_jaar(tmp_path) is None


def test_zip_hashes_alleen_aanwezige(bundel):
    (bundel / "mr.zip").unlink()  # ontbrekende zip wordt overgeslagen
    hashes = kd_bundel.huidige_zip_hashes(bundel)
    assert set(hashes) == {"ae.zip", "fl.zip", "sz.zip"}


def test_schrijf_en_lees_manifest(bundel):
    geschreven = kd_bundel.schrijf_manifest(bundel, nu="2026-06-24T10:00:00+00:00")
    assert geschreven["crebolijst_jaar"] == 2025
    assert set(geschreven["zips"]) == {"ae.zip", "fl.zip", "mr.zip", "sz.zip"}
    op_schijf = json.loads((bundel / "bundle_manifest.json").read_text(encoding="utf-8"))
    assert op_schijf == geschreven


def test_status_geen_manifest(bundel):
    s = kd_bundel.bundel_status(bundel)
    assert s["toestand"] == "geen_manifest"
    assert s["crebolijst_jaar"] == 2025


def test_status_in_sync_na_schrijven(bundel):
    kd_bundel.schrijf_manifest(bundel, nu="2026-06-24T10:00:00+00:00")
    s = kd_bundel.bundel_status(bundel)
    assert s["toestand"] == "in_sync"
    assert s["gewijzigde_zips"] == []


def test_status_gewijzigd_bij_nieuwe_zip_inhoud(bundel):
    kd_bundel.schrijf_manifest(bundel, nu="2026-06-24T10:00:00+00:00")
    (bundel / "ae.zip").write_bytes(b"ae-v2-nieuwere-bundel")  # SBB-update
    s = kd_bundel.bundel_status(bundel)
    assert s["toestand"] == "gewijzigd"
    assert s["gewijzigde_zips"] == ["ae.zip"]
```

- [ ] **Step 2: Draai de tests, verifieer dat ze falen**

Run: `uv run python -m pytest tests/test_kd_bundel.py -q`
Expected: FAIL — `ModuleNotFoundError: validatie_samenwijzer.kd_bundel`.

- [ ] **Step 3: Implementeer `kd_bundel.py`**

Maak `src/validatie_samenwijzer/kd_bundel.py`:

```python
"""KD-bundelmanifest: detecteer of de lokale SBB-bundel is gewijzigd of verouderd.

De kwalificatiedossiers komen uit een handmatig gedownloade s-bb-bundle (4 zips +
crebolijsten). Er was geen registratie van *welke* bundel we hebben, dus een verse
bundel werd niet als wijziging gezien. Dit module schrijft een manifest met de SHA256
per zip + het nieuwste crebolijst-jaar, en vergelijkt de live bundel daartegen.

Geen netwerk: alles werkt op de lokale (Box-gesyncte) bestanden. Een echte 'heeft SBB
een nieuwer jaar?'-check (upstream HEAD) is bewust buiten scope — het manifest surfaced
het crebolijst-jaar dat we hebben zodat een mens dat tegen s-bb.nl kan houden.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# kwalificatiedossiers/ leeft in de repo-root (buiten het subproject); spiegelt
# sync_afgeleid._REPO_ROOT.
_KWAL_DIR = Path(__file__).resolve().parents[3] / "kwalificatiedossiers"
_MANIFEST_NAAM = "bundle_manifest.json"
_SBB_ZIPS = ("ae.zip", "fl.zip", "mr.zip", "sz.zip")
_JAAR_RE = re.compile(r"crebo_(\d{4})")


def _sha256(pad: Path) -> str:
    h = hashlib.sha256()
    with pad.open("rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def huidige_zip_hashes(kwal_dir: Path = _KWAL_DIR) -> dict[str, str]:
    """SHA256 per aanwezige SBB-zip (ontbrekende zips worden overgeslagen)."""
    return {naam: _sha256(kwal_dir / naam) for naam in _SBB_ZIPS if (kwal_dir / naam).exists()}


def nieuwste_crebolijst_jaar(kwal_dir: Path = _KWAL_DIR) -> int | None:
    """Hoogste jaartal uit lijsten/crebo_<jaar>*.xlsx, of None als er geen zijn."""
    lijsten = kwal_dir / "lijsten"
    if not lijsten.exists():
        return None
    jaren = [int(m.group(1)) for p in lijsten.glob("crebo_*.xlsx") if (m := _JAAR_RE.match(p.name))]
    return max(jaren) if jaren else None


def schrijf_manifest(kwal_dir: Path = _KWAL_DIR, *, nu: str | None = None) -> dict:
    """Registreer de huidige bundel (zip-hashes + crebolijst-jaar) in het manifest."""
    manifest = {
        "crebolijst_jaar": nieuwste_crebolijst_jaar(kwal_dir),
        "zips": huidige_zip_hashes(kwal_dir),
        "gegenereerd_op": nu or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (kwal_dir / _MANIFEST_NAAM).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def lees_manifest(kwal_dir: Path = _KWAL_DIR) -> dict | None:
    pad = kwal_dir / _MANIFEST_NAAM
    if not pad.exists():
        return None
    try:
        return json.loads(pad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def bundel_status(kwal_dir: Path = _KWAL_DIR) -> dict:
    """Vergelijk de live bundel met het manifest.

    toestand: 'geen_manifest' | 'gewijzigd' | 'in_sync'. Bij 'gewijzigd' bevat
    gewijzigde_zips de zips met een afwijkende hash (of toegevoegd/verdwenen).
    """
    jaar = nieuwste_crebolijst_jaar(kwal_dir)
    manifest = lees_manifest(kwal_dir)
    if manifest is None:
        return {"toestand": "geen_manifest", "crebolijst_jaar": jaar, "gewijzigde_zips": []}
    live = huidige_zip_hashes(kwal_dir)
    vorig = manifest.get("zips", {})
    gewijzigd = sorted(n for n in set(live) | set(vorig) if live.get(n) != vorig.get(n))
    return {
        "toestand": "gewijzigd" if gewijzigd else "in_sync",
        "crebolijst_jaar": jaar,
        "gewijzigde_zips": gewijzigd,
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    m = schrijf_manifest()
    logger.info(
        "Manifest geschreven: crebolijst %s, %d zips.", m["crebolijst_jaar"], len(m["zips"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Draai de tests, verifieer dat ze slagen**

Run: `uv run python -m pytest tests/test_kd_bundel.py -q`
Expected: PASS — alle 7 tests groen.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/validatie_samenwijzer/kd_bundel.py tests/test_kd_bundel.py
git add src/validatie_samenwijzer/kd_bundel.py tests/test_kd_bundel.py
git commit -m "feat(validatie): kd_bundel-manifest (zip-hashes + crebolijst-jaar)"
```

---

### Task 2: KD-adapter in `bron_updates` gebruikt de bundelstatus

**Files:**
- Modify: `src/validatie_samenwijzer/bron_updates.py` (`_kd_status`, imports)
- Test: `tests/test_bron_updates.py`

**Interfaces:**
- Consumes: `kd_bundel.bundel_status() -> dict` (Task 1); bestaande `sync_afgeleid.geindexeerde_crebos()` + `sync_afgeleid.kd_dir()`.
- Produces: `_kd_status()` levert nu `automatisch=True` (we detecteren bundelwijziging automatisch) met `details` = `{toestand, crebolijst_jaar, gewijzigde_zips, ontbrekende_dekking}`.

- [ ] **Step 1: Werk de KD-tests bij (falend)**

Vervang in `tests/test_bron_updates.py` de KD-gerelateerde verwachtingen. Voeg in de fixture `gemockte_bronnen` een gemockte bundelstatus toe en herschrijf `test_kd_status_meldt_dekkingsgaten`:

```python
@pytest.fixture
def gemockte_bronnen(tmp_path, monkeypatch):
    kd_dir = tmp_path / "kd"
    kd_dir.mkdir()
    (kd_dir / "25180.md").write_text("kd", encoding="utf-8")  # 25180 heeft dekking
    monkeypatch.setattr(sync_afgeleid, "kd_dir", lambda: kd_dir)
    monkeypatch.setattr(sync_afgeleid, "geindexeerde_crebos", lambda: {"25180", "23110"})
    monkeypatch.setattr(bron_updates, "_skills_dry_run", lambda: (["25180"], ["23110"]))
    monkeypatch.setattr(
        bron_updates.kd_bundel,
        "bundel_status",
        lambda: {"toestand": "in_sync", "crebolijst_jaar": 2025, "gewijzigde_zips": []},
    )
    return tmp_path


def test_kd_status_in_sync_meldt_jaar_en_gaten(gemockte_bronnen):
    kd = {s.bron: s for s in bron_updates.verzamel_bron_status()}["kd"]
    assert kd.automatisch is True
    assert kd.details["crebolijst_jaar"] == 2025
    assert kd.details["ontbrekende_dekking"] == ["23110"]
    assert "2025" in kd.signaal


def test_kd_status_gewijzigd_vraagt_reingest(gemockte_bronnen, monkeypatch):
    monkeypatch.setattr(
        bron_updates.kd_bundel,
        "bundel_status",
        lambda: {"toestand": "gewijzigd", "crebolijst_jaar": 2025, "gewijzigde_zips": ["ae.zip"]},
    )
    kd = {s.bron: s for s in bron_updates.verzamel_bron_status()}["kd"]
    assert "gewijzigd" in kd.signaal
    assert kd.details["gewijzigde_zips"] == ["ae.zip"]
```

Verwijder de oude `test_kd_status_meldt_dekkingsgaten` en `test_kd_status_meldt_ontbrekende_map` (vervangen door bovenstaande; de map-niet-gevonden-tak vervalt — zie Step 3).

- [ ] **Step 2: Draai de tests, verifieer dat ze falen**

Run: `uv run python -m pytest tests/test_bron_updates.py -q`
Expected: FAIL — `bron_updates.kd_bundel` bestaat nog niet / `_kd_status` mist de bundelvelden.

- [ ] **Step 3: Werk `_kd_status` bij**

In `src/validatie_samenwijzer/bron_updates.py`: voeg `kd_bundel` toe aan de import en vervang `_kd_status`:

```python
from . import kd_bundel, sync_afgeleid
```

```python
def _kd_status() -> BronStatus:
    crebos = sync_afgeleid.geindexeerde_crebos()
    kd_dir = sync_afgeleid.kd_dir()
    ontbrekend = sorted(crebos - {p.stem for p in kd_dir.glob("*.md")}) if kd_dir.exists() else []

    bundel = kd_bundel.bundel_status()
    toestand = bundel["toestand"]
    if toestand == "gewijzigd":
        signaal = (
            f"SBB-bundel gewijzigd sinds laatste ingest "
            f"({len(bundel['gewijzigde_zips'])} zip(s)) — re-ingest nodig"
        )
    elif toestand == "geen_manifest":
        signaal = "geen bundelmanifest — draai `python -m validatie_samenwijzer.kd_bundel`"
    else:
        signaal = (
            f"bundel in sync (crebolijst {bundel['crebolijst_jaar']}); "
            f"{len(ontbrekend)} crebo('s) zonder dekking"
        )
    return BronStatus(
        "kd",
        automatisch=True,
        signaal=signaal,
        details={
            "toestand": toestand,
            "crebolijst_jaar": bundel["crebolijst_jaar"],
            "gewijzigde_zips": bundel["gewijzigde_zips"],
            "ontbrekende_dekking": ontbrekend,
        },
    )
```

- [ ] **Step 4: Draai de tests, verifieer dat ze slagen**

Run: `uv run python -m pytest tests/test_bron_updates.py tests/test_kd_bundel.py -q`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/validatie_samenwijzer/bron_updates.py tests/test_bron_updates.py
git add src/validatie_samenwijzer/bron_updates.py tests/test_bron_updates.py
git commit -m "feat(validatie): KD-adapter rapporteert bundelversheid (manifest-diff)"
```

---

### Task 3: Schrijf het manifest na een KD-download

Zo blijft het manifest automatisch de werkelijk geïngeste bundel weerspiegelen.

**Files:**
- Modify: `scripts/download_kwalificatiedossiers.py` (einde `main()`, na het schrijven van `download_rapport.json` ~regel 276-277)

**Interfaces:**
- Consumes: `kd_bundel.schrijf_manifest()` (Task 1).

- [ ] **Step 1: Hook het manifest in `main()`**

In `scripts/download_kwalificatiedossiers.py`, voeg bij de imports toe:

```python
from validatie_samenwijzer import kd_bundel
```

En direct ná de regel die `download_rapport.json` schrijft (`(KWAL_DIR / "download_rapport.json").write_text(...)`):

```python
    manifest = kd_bundel.schrijf_manifest()
    print(f"Bundelmanifest bijgewerkt: crebolijst {manifest['crebolijst_jaar']}.")
```

- [ ] **Step 2: Baseline het manifest voor de huidige bundel + rooktest**

Run:
```bash
uv run python -m validatie_samenwijzer.kd_bundel
uv run check-bron-updates
```
Expected: het manifest wordt geschreven (crebolijst 2025, 4 zips), en de KD-regel toont nu `bundel in sync (crebolijst 2025); N crebo('s) zonder dekking`.

- [ ] **Step 3: Volledige suite + lint**

Run:
```bash
uv run python -m pytest -q
uv run ruff check src/ scripts/ tests/
```
Expected: alles groen.

- [ ] **Step 4: Commit**

```bash
git add scripts/download_kwalificatiedossiers.py
git commit -m "feat(validatie): schrijf bundelmanifest na KD-download"
```

---

## Buiten scope (vervolg)

- **Echte SBB-upstream-check** (heeft s-bb.nl een nieuwer crebolijst-jaar / nieuwere zips dan wij?) vereist netwerk-fetch/HEAD tegen s-bb.nl. Houd dit achter een expliciete flag wegens netwerk + de `allowed_domains`-valkuil; nu surfaced het manifest het crebolijst-jaar zodat een mens dat handmatig vergelijkt.
- **Generiek DB-register** (`content_hash`/`laatst_gecheckt`/`bron_url` op `oer_documenten` + `instelling_documenten`) — verhuisd naar Fase 3, gekoppeld aan de OER-catalogus-crawlcheck die het consumeert (zie scope-herziening boven).

## Self-Review

**Spec-dekking.** "Detecteer of de KD-bundel is gewijzigd/verouderd" → Task 1 levert het manifest + `bundel_status()`, Task 2 surfaced het in `check-bron-updates`, Task 3 houdt het manifest automatisch actueel. De echte upstream-SBB-check en het DB-register zijn expliciet als buiten-scope/vervolg benoemd (niet stil weggelaten).

**Placeholder-scan.** Alle stappen bevatten volledige code; de enige NB (import `logging` bovenaan) is expliciet gemarkeerd. Geen "TBD"/"handle errors"-platzhouders.

**Type-consistentie.** `bundel_status()` retourneert overal dezelfde sleutels (`toestand`, `crebolijst_jaar`, `gewijzigde_zips`); `_kd_status` en de tests consumeren exact die. `schrijf_manifest(..., nu=...)` matcht de test-aanroep met een vaste tijdstempel.
