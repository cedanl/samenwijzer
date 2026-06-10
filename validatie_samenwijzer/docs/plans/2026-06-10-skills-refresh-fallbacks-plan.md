# Skills Fase 3 — `--refresh-fallbacks` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Her-check de bestaande non-CompetentNL skills-artefacten periodiek tegen CompetentNL en upgrade ze zodra CompetentNL de crebo toevoegt, zonder de gepinde ESCO-matches te verstoren.

**Architecture:** Kernlogica (`refresh_fallbacks()`) in `scripts/build_skills_taxonomie.py`, waar de json-write en CSV-herbouw al leven. `sync_afgeleid.py` krijgt een doorgeef-vlag die via de bestaande `_run()`-subprocess-helper naar het build-script shelt. Working-tree only: het build-script rapporteert de geüpgradede crebo's; een mens commit via PR.

**Tech Stack:** Python 3.13, stdlib (`json`, `argparse`, `csv`), pytest, `uv`. Bron: `validatie_samenwijzer.competentnl_bron.haal_skills_record(crebo, opleiding) -> SkillsRecord | None`.

**Spec:** `docs/plans/2026-06-10-skills-refresh-fallbacks-design.md`

---

## File Structure

- **Modify** `scripts/build_skills_taxonomie.py` — nieuwe `refresh_fallbacks()` + `--refresh-fallbacks` CLI-vlag (early-return vóór de DB-afhankelijke normale build).
- **Modify** `src/validatie_samenwijzer/sync_afgeleid.py` — `_refresh_fallbacks()` helper + `--refresh-fallbacks` in de mutually-exclusive groep + dispatch.
- **Create** `tests/test_refresh_fallbacks.py` — unit-tests voor `refresh_fallbacks()` (4 gevallen), import van het script via `sys.path` (patroon uit `test_rename_oers.py`).
- **Modify** `tests/test_sync_afgeleid.py` — één test dat de `--refresh-fallbacks`-dispatch naar het build-script shelt.
- **Modify** `docs/plans/auto-sync-afgeleide-bronnen.md` + `CLAUDE.md` — Fase 3-status `open` → `geïmplementeerd`.

**Belangrijke consistentie-regel:** upgrade alléén bij `nieuw is not None and nieuw.skills`. Dit spiegelt de bestaande build-guard (`if record is None or not record.skills:` → ESCO-fallback). Een CompetentNL-record zónder skills is geen upgrade maar een downgrade van een goede ESCO-match, dus dat laten we ongemoeid.

---

## Task 1: `refresh_fallbacks()` in het build-script

**Files:**
- Create: `tests/test_refresh_fallbacks.py`
- Modify: `scripts/build_skills_taxonomie.py` (nieuwe functie ná `_schrijf_overzicht`, ~regel 166)

- [ ] **Step 1: Write the failing test**

Create `tests/test_refresh_fallbacks.py`:

```python
"""Tests voor refresh_fallbacks(): her-check non-CompetentNL artefacten tegen CompetentNL.

Geen netwerk: competentnl_bron.haal_skills_record wordt gemockt.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import build_skills_taxonomie as bst  # noqa: E402

from validatie_samenwijzer.skills_bron import Beroep, Skill, SkillsRecord  # noqa: E402


def _esco_json(crebo: str) -> str:
    return json.dumps(
        {
            "crebo": crebo,
            "opleiding": f"{crebo}_BOL_2025__OER",
            "bron": "ESCO",
            "beroep": {"label": "vakdocent", "uri": "esco:1", "definitie": "..."},
            "match_methode": "llm-keuze",
            "kandidaten": ["vakdocent"],
            "skills": [{"label": "lesgeven", "uri": "esco:s1", "categorie": "essentieel"}],
        },
        ensure_ascii=False,
        indent=2,
    )


def _competentnl_json(crebo: str) -> str:
    return json.dumps(
        {
            "crebo": crebo,
            "opleiding": f"{crebo}_BOL_2025__OER",
            "bron": "CompetentNL",
            "beroep": {"label": "Kok", "uri": "", "definitie": "..."},
            "match_methode": "crebo-direct",
            "kandidaten": [],
            "skills": [{"label": "koken", "uri": "cnl:s1", "categorie": "essentieel"}],
        },
        ensure_ascii=False,
        indent=2,
    )


@pytest.fixture
def skills_dir(tmp_path, monkeypatch):
    d = tmp_path / "skills"
    d.mkdir()
    monkeypatch.setattr(bst, "_SKILLS_DIR", d)
    monkeypatch.setenv("COMPETENTNL_API_KEY", "test-key")
    return d


def test_upgrade_bij_competentnl_hit(skills_dir, monkeypatch):
    (skills_dir / "25180.json").write_text(_esco_json("25180"), encoding="utf-8")

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

    upgraded, nog_fallback = bst.refresh_fallbacks()

    assert upgraded == ["25180"]
    assert nog_fallback == []
    data = json.loads((skills_dir / "25180.json").read_text(encoding="utf-8"))
    assert data["bron"] == "CompetentNL"
    assert data["match_methode"] == "crebo-direct"
    assert (skills_dir / "_match_overzicht.csv").exists()


def test_miss_laat_esco_ongemoeid(skills_dir, monkeypatch):
    pad = skills_dir / "23110.json"
    origineel = _esco_json("23110")
    pad.write_text(origineel, encoding="utf-8")
    monkeypatch.setattr(bst.competentnl_bron, "haal_skills_record", lambda c, o: None)

    upgraded, nog_fallback = bst.refresh_fallbacks()

    assert upgraded == []
    assert nog_fallback == ["23110"]
    assert pad.read_text(encoding="utf-8") == origineel  # byte-identiek


def test_geen_api_key_geen_crash_met_waarschuwing(skills_dir, monkeypatch, caplog):
    monkeypatch.delenv("COMPETENTNL_API_KEY", raising=False)
    (skills_dir / "25180.json").write_text(_esco_json("25180"), encoding="utf-8")
    monkeypatch.setattr(bst.competentnl_bron, "haal_skills_record", lambda c, o: None)

    with caplog.at_level("WARNING"):
        upgraded, nog_fallback = bst.refresh_fallbacks()

    assert upgraded == []
    assert nog_fallback == ["25180"]
    assert "COMPETENTNL_API_KEY" in caplog.text


def test_competentnl_artefact_overgeslagen(skills_dir, monkeypatch):
    (skills_dir / "25234.json").write_text(_competentnl_json("25234"), encoding="utf-8")
    aangeroepen = []
    monkeypatch.setattr(
        bst.competentnl_bron, "haal_skills_record", lambda c, o: aangeroepen.append(c)
    )

    upgraded, nog_fallback = bst.refresh_fallbacks()

    assert aangeroepen == []  # CompetentNL-artefact nooit opnieuw bevraagd
    assert upgraded == []
    assert nog_fallback == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_refresh_fallbacks.py -v`
Expected: FAIL with `AttributeError: module 'build_skills_taxonomie' has no attribute 'refresh_fallbacks'`

- [ ] **Step 3: Write the implementation**

In `scripts/build_skills_taxonomie.py`, voeg deze functie toe ná `_schrijf_overzicht()` (vóór de `if __name__` guard):

```python
def refresh_fallbacks() -> tuple[list[str], list[str]]:
    """Her-check non-CompetentNL artefacten tegen CompetentNL; upgrade bij een hit.

    Roept alléén ``competentnl_bron.haal_skills_record()`` aan (deterministisch,
    crebo-direct). De niet-deterministische ESCO-LLM-match wordt nooit opnieuw
    gerold: een miss laat het bestaande artefact byte-identiek ongemoeid. Upgrade
    alleen bij een record mét skills (een leeg CompetentNL-record is geen upgrade).
    Working-tree only — returnt (upgraded, nog_fallback) voor de rapportage.
    """
    if not os.environ.get("COMPETENTNL_API_KEY"):
        logger.warning(
            "COMPETENTNL_API_KEY ontbreekt — refresh-fallbacks kan niets upgraden. "
            "Zet de key in .env en draai opnieuw."
        )

    upgraded: list[str] = []
    nog_fallback: list[str] = []
    for pad in sorted(_SKILLS_DIR.glob("*.json")):
        try:
            record = json.loads(pad.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Onleesbaar skills-artefact, overgeslagen: %s", pad.name)
            continue
        if record.get("bron") == "CompetentNL":
            continue  # al de voorkeursbron — nooit opnieuw bevragen

        crebo = record["crebo"]
        nieuw = competentnl_bron.haal_skills_record(crebo, record["opleiding"])
        if nieuw is not None and nieuw.skills:
            pad.write_text(
                json.dumps(nieuw.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
            upgraded.append(crebo)
            logger.info("UPGRADE %s → CompetentNL (%d skills)", crebo, len(nieuw.skills))
        else:
            nog_fallback.append(crebo)

    if upgraded:
        _schrijf_overzicht()

    logger.info(
        "Refresh-fallbacks klaar: %d geüpgraded naar CompetentNL%s, %d nog ESCO/geen-match.",
        len(upgraded),
        f" ({', '.join(sorted(upgraded))})" if upgraded else "",
        len(nog_fallback),
    )
    if upgraded:
        logger.info("→ commit data/skills/ via PR")
    return sorted(upgraded), sorted(nog_fallback)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_refresh_fallbacks.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/test_refresh_fallbacks.py scripts/build_skills_taxonomie.py
git commit -m "feat(validatie): refresh_fallbacks() — ESCO→CompetentNL upgrade

Ed de Feber, in nauwe samenwerking met Claude"
```

---

## Task 2: `--refresh-fallbacks` CLI-vlag op het build-script

**Files:**
- Modify: `scripts/build_skills_taxonomie.py:66-73` (argparse + early-return in `main()`)
- Test: `tests/test_refresh_fallbacks.py` (CLI-dispatch via `main()`)

- [ ] **Step 1: Write the failing test**

Voeg toe aan `tests/test_refresh_fallbacks.py`:

```python
def test_cli_refresh_fallbacks_roept_functie(skills_dir, monkeypatch):
    aangeroepen = []
    monkeypatch.setattr(bst, "refresh_fallbacks", lambda: aangeroepen.append(True) or ([], []))
    monkeypatch.setattr(sys, "argv", ["build_skills_taxonomie.py", "--refresh-fallbacks"])

    rc = bst.main()

    assert rc == 0
    assert aangeroepen == [True]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_refresh_fallbacks.py::test_cli_refresh_fallbacks_roept_functie -v`
Expected: FAIL — `--refresh-fallbacks` is een onbekend argument (`SystemExit: 2`).

- [ ] **Step 3: Write the implementation**

In `scripts/build_skills_taxonomie.py::main()`, voeg de vlag toe ná regel 70 (`--reset`):

```python
    parser.add_argument(
        "--refresh-fallbacks",
        action="store_true",
        help="Her-check non-CompetentNL artefacten tegen CompetentNL en upgrade hits (Fase 3)",
    )
```

En voeg de early-return toe direct ná `_SKILLS_DIR.mkdir(...)` (regel 73), vóór `_beste_opleiding_per_crebo()` (die de DB raakt en voor refresh onnodig is):

```python
    _SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    if args.refresh_fallbacks:
        refresh_fallbacks()
        return 0
    opleidingen = _beste_opleiding_per_crebo()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_refresh_fallbacks.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/build_skills_taxonomie.py tests/test_refresh_fallbacks.py
git commit -m "feat(validatie): --refresh-fallbacks CLI-vlag op build-script

Ed de Feber, in nauwe samenwerking met Claude"
```

---

## Task 3: `--refresh-fallbacks` op `sync_afgeleid`

**Files:**
- Modify: `src/validatie_samenwijzer/sync_afgeleid.py` (`_refresh_fallbacks()` helper ná `_bouw_skills` ~regel 144; argparse-groep + dispatch in `main()` ~regel 209)
- Test: `tests/test_sync_afgeleid.py`

- [ ] **Step 1: Write the failing test**

Voeg toe aan `tests/test_sync_afgeleid.py`:

```python
def test_refresh_fallbacks_shelt_naar_build_script(monkeypatch):
    cmds = []
    monkeypatch.setattr(sync_afgeleid, "_run", lambda cmd: cmds.append(cmd) or 0)

    sync_afgeleid._refresh_fallbacks()

    assert len(cmds) == 1
    assert str(sync_afgeleid._SKILLS_SCRIPT) in cmds[0]
    assert "--refresh-fallbacks" in cmds[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_sync_afgeleid.py::test_refresh_fallbacks_shelt_naar_build_script -v`
Expected: FAIL with `AttributeError: module 'validatie_samenwijzer.sync_afgeleid' has no attribute '_refresh_fallbacks'`

- [ ] **Step 3: Write the implementation**

In `src/validatie_samenwijzer/sync_afgeleid.py`, voeg de helper toe ná `_bouw_skills()` (regel 144):

```python
def _refresh_fallbacks() -> None:
    """Her-check non-CompetentNL skills-artefacten tegen CompetentNL (Fase 3).

    Shelt naar het build-script, dat zelf rapporteert welke crebo's upgraden en
    dat de mens ``data/skills/`` via een PR moet committen.
    """
    _run([sys.executable, str(_SKILLS_SCRIPT), "--refresh-fallbacks"])
```

Voeg de vlag toe aan de mutually-exclusive groep in `main()` (ná `--alles`, regel 218):

```python
    groep.add_argument(
        "--refresh-fallbacks",
        action="store_true",
        help="Her-check ESCO-fallbacks tegen CompetentNL en upgrade hits (Fase 3)",
    )
```

En dispatch vóór `werk_afgeleide_bronnen_bij(...)` (regel 222):

```python
    args = parser.parse_args()

    if args.refresh_fallbacks:
        _refresh_fallbacks()
        return 0
    werk_afgeleide_bronnen_bij(crebo=args.crebo, alles=args.alles, force=args.force)
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_sync_afgeleid.py -v`
Expected: PASS (alle tests in het bestand groen, incl. de nieuwe)

- [ ] **Step 5: Commit**

```bash
git add src/validatie_samenwijzer/sync_afgeleid.py tests/test_sync_afgeleid.py
git commit -m "feat(validatie): sync_afgeleid --refresh-fallbacks (Fase 3 entry point)

Ed de Feber, in nauwe samenwerking met Claude"
```

---

## Task 4: Volledige testsuite + lint + docs-status

**Files:**
- Modify: `docs/plans/auto-sync-afgeleide-bronnen.md` (Fase 3-rij + status-regel)
- Modify: `CLAUDE.md` (geen Fase 3-vermelding aanwezig — controleren; zo niet, niets doen)

- [ ] **Step 1: Draai de volledige testsuite**

Run: `uv run python -m pytest`
Expected: PASS — geen regressies; de nieuwe tests groen.

- [ ] **Step 2: Lint + format**

Run: `uv run ruff check --fix src/ app/ scripts/ tests/ && uv run ruff format src/ app/ scripts/ tests/`
Expected: "All checks passed!" en geen ongewenste herformatteringen buiten de aangeraakte regels.

- [ ] **Step 3: Update de Fase 3-status in het auto-sync-plan**

In `docs/plans/auto-sync-afgeleide-bronnen.md`:
- Regel 3 (`**Status:**`): wijzig `Fase 3 open` → `Fase 3 geïmplementeerd (skills-kant; KD-bundle-refresh blijft open)`.
- De Fase 3-rij in de tabel (regel ~81): wijzig status `⏳ open` → `✅ (skills) + ⏳ KD-bundle-refresh open`.

- [ ] **Step 4: Controleer CLAUDE.md op een Fase 3-vermelding**

Run: `grep -n "Fase 3\|refresh-fallbacks\|afgeleide bronnen" CLAUDE.md`
Als er een "Fase 3 open"-vermelding staat: werk die bij naar "skills-kant geïmplementeerd". Zo niet: geen wijziging.

- [ ] **Step 5: Commit**

```bash
git add docs/plans/auto-sync-afgeleide-bronnen.md CLAUDE.md
git commit -m "docs(validatie): Skills Fase 3 (--refresh-fallbacks) geïmplementeerd

Ed de Feber, in nauwe samenwerking met Claude"
```

---

## Self-Review

**Spec coverage:**
- CompetentNL-only re-check (churn-vrij) → Task 1 (`refresh_fallbacks`, alleen `competentnl_bron`, ESCO nooit gerold). ✅
- Upgrade bij hit / ongemoeid bij miss → Task 1 tests `test_upgrade_bij_competentnl_hit`, `test_miss_laat_esco_ongemoeid`. ✅
- Plaatsing build-script + doorgeef-vlag sync_afgeleid → Task 1/2 + Task 3. ✅
- Rapportage working-tree only (build-script print) → Task 1 (`logger.info(... → commit data/skills/ via PR)`). ✅
- Error handling: geen key → Task 1 `test_geen_api_key_...`; SPARQL-fout = miss → afgedekt doordat `haal_skills_record` zelf `None` geeft (bestaand contract); corrupte json → `except (JSONDecodeError, OSError)` in `refresh_fallbacks`. ✅
- CompetentNL nooit opnieuw bevraagd → Task 1 `test_competentnl_artefact_overgeslagen`. ✅
- 4 unit-tests uit de spec → Task 1 dekt alle vier. ✅

**Placeholder scan:** geen TBD/TODO; alle code-stappen tonen volledige code. ✅

**Type consistency:** `refresh_fallbacks() -> tuple[list[str], list[str]]` consistent in build-script, test en plan. `competentnl_bron.haal_skills_record(crebo, opleiding)` matcht de echte signatuur. `SkillsRecord(crebo, opleiding, bron, beroep, skills, match_methode, kandidaten)` + `Beroep(label, uri, definitie)` + `Skill(label, uri, categorie)` matchen `skills_bron.py`. `_SKILLS_SCRIPT` bestaat in `sync_afgeleid.py` (regel 47). ✅
