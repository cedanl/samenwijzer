# KD-fallback voor kerntaken-extractie — Implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wanneer een OER nul kerntaken oplevert, kerntaken alsnog uit het kwalificatiedossier (KD) van dezelfde crebo halen, zodat Aeres MBO en Rijn IJssel terugkomen in de seed-set (issue #53).

**Architecture:** Drie kleine, geïsoleerde toevoegingen aan `ingest.py`: (1) `_schoon_kd_naam` strpt trailing dotted leaders uit KD-inhoudsopgaveregels, (2) `_kerntaken_uit_kd` draait de bestaande `extraheer_kerntaken` over KD-tekst + dedupt per (type, code) met voorkeur voor de langste naam, (3) `_pad_kwalificatiedossier` resolvet het `<crebo>.md`-pad. In `_verwerk_bestand` vuurt de fallback **alleen bij nul OER-kerntaken** (fire-at-zero, supplement-never-replace) → geen regressie op de werkende instellingen. De OER-extractie (`extraheer_kerntaken`) blijft ongewijzigd.

**Tech Stack:** Python 3.13, sqlite3, pytest. Geen nieuwe dependencies.

**Spec:** `docs/plans/kd-fallback-kerntaken.md`

---

## File Structure

- `src/validatie_samenwijzer/ingest.py` — modify: 3 nieuwe module-functies + fallback-tak in `_verwerk_bestand`. `os` en `Path` zijn al geïmporteerd; `extraheer_kerntaken` staat al in deze module.
- `tests/test_ingest.py` — modify: unit-tests voor de 3 helpers + 2 integratietests voor `_verwerk_bestand` (fallback vuurt / vuurt niet). Bestaande tests blijven ongewijzigd.
- `validatie_samenwijzer/CLAUDE.md` — modify: ingest-pipeline-beschrijving krijgt de KD-fallback-stap.

---

## Task 1: `_schoon_kd_naam` — trailing dotted leaders strippen

**Files:**
- Modify: `src/validatie_samenwijzer/ingest.py` (na `extraheer_kerntaken`, rond regel 189)
- Test: `tests/test_ingest.py`

- [ ] **Step 1: Write the failing test**

Voeg toe aan `tests/test_ingest.py` (en breid de bovenste import uit met `_schoon_kd_naam`):

```python
def test_schoon_kd_naam_verwijdert_dotted_leaders():
    ruw = "Uitvoeren metingen leefomgeving en rapporteren resultaten  ...........  6"
    assert _schoon_kd_naam(ruw) == "Uitvoeren metingen leefomgeving en rapporteren resultaten"


def test_schoon_kd_naam_zonder_leaders_blijft_gelijk():
    assert _schoon_kd_naam("Voert toegangscontroles uit") == "Voert toegangscontroles uit"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_ingest.py::test_schoon_kd_naam_verwijdert_dotted_leaders -v`
Expected: FAIL met `ImportError: cannot import name '_schoon_kd_naam'`

- [ ] **Step 3: Write minimal implementation**

In `src/validatie_samenwijzer/ingest.py`, direct ná `def extraheer_kerntaken(...)` (regel ~189):

```python
# Inhoudsopgaveregels in een KD dragen trailing dotted leaders + paginanummer,
# bv. "Voert preventieve werkzaamheden uit  ...........  6".
_KD_LEADER_PATROON = re.compile(r"\s*\.{2,}\s*\d*\s*$")


def _schoon_kd_naam(naam: str) -> str:
    """Verwijder trailing dotted leaders en paginanummer uit een KD-inhoudsopgaveregel."""
    return _KD_LEADER_PATROON.sub("", naam).strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_ingest.py -k schoon_kd_naam -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add src/validatie_samenwijzer/ingest.py tests/test_ingest.py
git commit -m "feat(ingest): _schoon_kd_naam strpt KD dotted leaders (#53)"
```

---

## Task 2: `_kerntaken_uit_kd` — extractor over KD + dedup per code

**Files:**
- Modify: `src/validatie_samenwijzer/ingest.py` (na `_schoon_kd_naam`)
- Test: `tests/test_ingest.py`

- [ ] **Step 1: Write the failing test**

Voeg toe aan `tests/test_ingest.py` (breid import uit met `_kerntaken_uit_kd`):

```python
def test_kerntaken_uit_kd_schoont_en_dedupt_per_code():
    # TOC-regel (schoon, lang) + body-herhaling (gewrapt, korter, geen dubbelepunt).
    kd_tekst = """
    B1-K1:  Brengt de modewereld in beeld en ontwikkelt een modeconcept  ......  9
    B1-K1-W1:  Verzamelt en verwerkt informatie over ontwikkelingen in de mode  ..  10

    later in het document:
    B1-K1 Brengt de modewereld in beeld en
    """
    kt = _kerntaken_uit_kd(kd_tekst)
    per_code = {k["code"]: k for k in kt}
    # Eén record per code (TOC + gewrapte body-dup samengevoegd).
    assert sorted(per_code) == ["B1-K1", "B1-K1-W1"]
    # Langste (= TOC-)naam wint, dotted leaders weg.
    assert per_code["B1-K1"]["naam"] == "Brengt de modewereld in beeld en ontwikkelt een modeconcept"
    assert per_code["B1-K1"]["type"] == "kerntaak"
    assert per_code["B1-K1-W1"]["type"] == "werkproces"
    # volgorde is hernummerd vanaf 0.
    assert sorted(k["volgorde"] for k in kt) == [0, 1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_ingest.py::test_kerntaken_uit_kd_schoont_en_dedupt_per_code -v`
Expected: FAIL met `ImportError: cannot import name '_kerntaken_uit_kd'`

- [ ] **Step 3: Write minimal implementation**

In `src/validatie_samenwijzer/ingest.py`, direct ná `_schoon_kd_naam`:

```python
def _kerntaken_uit_kd(tekst: str) -> list[dict]:
    """Kerntaken/werkprocessen uit een kwalificatiedossier-markdown.

    Hergebruikt de OER-extractor maar schoont KD-specifieke dotted leaders uit de
    namen en dedupt per (type, code) — de inhoudsopgave noemt elke code één keer
    schoon, de body herhaalt hem soms gewrapt. De langste opgeschoonde naam wint.
    """
    beste: dict[tuple[str, str], dict] = {}
    for kt in extraheer_kerntaken(tekst):
        naam = _schoon_kd_naam(kt["naam"])
        sleutel = (kt["type"], kt["code"])
        if sleutel not in beste or len(naam) > len(beste[sleutel]["naam"]):
            beste[sleutel] = {**kt, "naam": naam}

    resultaat = sorted(beste.values(), key=lambda k: k["volgorde"])
    for i, kt in enumerate(resultaat):
        kt["volgorde"] = i
    return resultaat
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_ingest.py::test_kerntaken_uit_kd_schoont_en_dedupt_per_code -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/validatie_samenwijzer/ingest.py tests/test_ingest.py
git commit -m "feat(ingest): _kerntaken_uit_kd extract + dedup per code (#53)"
```

---

## Task 3: `_pad_kwalificatiedossier` — KD-pad resolveren

**Files:**
- Modify: `src/validatie_samenwijzer/ingest.py` (na `_kerntaken_uit_kd`)
- Test: `tests/test_ingest.py`

- [ ] **Step 1: Write the failing test**

Voeg toe aan `tests/test_ingest.py` (breid import uit met `_pad_kwalificatiedossier`):

```python
def test_pad_kwalificatiedossier_via_env(tmp_path, monkeypatch):
    (tmp_path / "25690.md").write_text("x", encoding="utf-8")
    monkeypatch.setenv("KWALDOSSIERS_PAD", str(tmp_path))
    pad = _pad_kwalificatiedossier("25690")
    assert pad is not None and pad.name == "25690.md"


def test_pad_kwalificatiedossier_ontbrekend_bestand(tmp_path, monkeypatch):
    monkeypatch.setenv("KWALDOSSIERS_PAD", str(tmp_path))
    assert _pad_kwalificatiedossier("99999") is None


def test_pad_kwalificatiedossier_lege_crebo(tmp_path, monkeypatch):
    monkeypatch.setenv("KWALDOSSIERS_PAD", str(tmp_path))
    assert _pad_kwalificatiedossier(None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_ingest.py -k pad_kwalificatiedossier -v`
Expected: FAIL met `ImportError: cannot import name '_pad_kwalificatiedossier'`

- [ ] **Step 3: Write minimal implementation**

In `src/validatie_samenwijzer/ingest.py`, direct ná `_kerntaken_uit_kd`:

```python
def _pad_kwalificatiedossier(crebo: str | None) -> Path | None:
    """Pad naar <crebo>.md van het kwalificatiedossier, of None als de crebo leeg is
    of het bestand ontbreekt.

    Spiegelt ``chat.pad_kwalificatiedossier`` bewust zonder import: chat.py trekt
    ``anthropic`` binnen en hoort niet in de ingest-pijplijn. Default-pad
    ``<repo-root>/kwalificatiedossiers/pdfs``; override via ``KWALDOSSIERS_PAD``.
    """
    if not crebo:
        return None
    base = os.environ.get("KWALDOSSIERS_PAD")
    if base:
        directory = Path(base).resolve()
    else:
        directory = Path(__file__).resolve().parents[3] / "kwalificatiedossiers" / "pdfs"
    pad = directory / f"{crebo}.md"
    return pad if pad.exists() else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_ingest.py -k pad_kwalificatiedossier -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/validatie_samenwijzer/ingest.py tests/test_ingest.py
git commit -m "feat(ingest): _pad_kwalificatiedossier resolver (#53)"
```

---

## Task 4: KD-fallback in `_verwerk_bestand`

**Files:**
- Modify: `src/validatie_samenwijzer/ingest.py:389,409` (de `oer_id, _meta = result`-regel en het blok na `extraheer_kerntaken`)
- Test: `tests/test_ingest.py`

- [ ] **Step 1: Write the failing test**

Voeg bovenaan `tests/test_ingest.py` een DB-fixture en imports toe (naast de bestaande), en de twee integratietests:

```python
import sqlite3

import pytest

from validatie_samenwijzer.db import (
    get_kerntaken_by_oer_id,
    init_db,
    voeg_instelling_toe,
)
from validatie_samenwijzer.ingest import _verwerk_bestand


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


def _oer_id(conn) -> int:
    return conn.execute("SELECT id FROM oer_documenten").fetchone()[0]


def test_verwerk_bestand_valt_terug_op_kd_bij_nul_oer_kerntaken(tmp_path, monkeypatch, conn):
    voeg_instelling_toe(conn, "talland", "Talland")
    # OER zonder kerntaak-codes → extraheer_kerntaken geeft 0.
    oer = tmp_path / "25690_BOL_2025__Beveiliger.md"
    oer.write_text("Algemene inleiding zonder enige kerntaakcode.\n", encoding="utf-8")
    # KD-fixture met schone inhoudsopgaveregels.
    kd_dir = tmp_path / "kd"
    kd_dir.mkdir()
    (kd_dir / "25690.md").write_text(
        "B1-K1:  Voert preventieve werkzaamheden uit ten behoeve van veiligheid  ....  6\n"
        "B1-K1-W1:  Voert toegangs- en uitgangscontroles uit  ..........  7\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KWALDOSSIERS_PAD", str(kd_dir))

    _verwerk_bestand(oer, "talland", conn)

    kt = get_kerntaken_by_oer_id(conn, _oer_id(conn))
    codes = {r["code"] for r in kt}
    assert {"B1-K1", "B1-K1-W1"} <= codes
    namen = {r["naam"] for r in kt}
    assert "Voert preventieve werkzaamheden uit ten behoeve van veiligheid" in namen


def test_verwerk_bestand_negeert_kd_als_oer_kerntaken_heeft(tmp_path, monkeypatch, conn):
    voeg_instelling_toe(conn, "talland", "Talland")
    oer = tmp_path / "25690_BOL_2025__Beveiliger.md"
    oer.write_text("B1-K1: Voert preventieve werkzaamheden uit ten behoeve\n", encoding="utf-8")
    kd_dir = tmp_path / "kd"
    kd_dir.mkdir()
    (kd_dir / "25690.md").write_text("B9-K9: Heel ander kerntaakprofiel uit het KD\n", encoding="utf-8")
    monkeypatch.setenv("KWALDOSSIERS_PAD", str(kd_dir))

    _verwerk_bestand(oer, "talland", conn)

    codes = {r["code"] for r in get_kerntaken_by_oer_id(conn, _oer_id(conn))}
    assert "B1-K1" in codes
    assert "B9-K9" not in codes  # KD niet geraadpleegd
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_ingest.py -k verwerk_bestand -v`
Expected: `test_..._valt_terug_op_kd...` FAILt (geen kerntaken — fallback bestaat nog niet); `test_..._negeert_kd...` PASSt al (OER levert kerntaken, KD wordt sowieso niet gelezen).

- [ ] **Step 3: Write minimal implementation**

In `src/validatie_samenwijzer/ingest.py`, regel ~389, hernoem de meta-variabele zodat we de crebo kunnen gebruiken:

```python
    oer_id, meta = result
```

(was: `oer_id, _meta = result`)

Vervang vervolgens het blok dat begint bij `kerntaken = extraheer_kerntaken(tekst)` (regel ~409) door:

```python
    kerntaken = extraheer_kerntaken(tekst)
    if not kerntaken:
        kd_pad = _pad_kwalificatiedossier(meta["crebo"])
        if kd_pad is not None:
            kd_tekst = kd_pad.read_text(encoding="utf-8", errors="replace")
            kerntaken = _kerntaken_uit_kd(kd_tekst)
            if kerntaken:
                log.info(
                    "Geen kerntaken in OER '%s'; %d kerntaken uit KD %s gehaald.",
                    pad.name,
                    len(kerntaken),
                    meta["crebo"],
                )
    for kt in kerntaken:
        voeg_kerntaak_toe(
            conn,
            oer_id=oer_id,
            code=kt["code"],
            naam=kt["naam"],
            type=kt["type"],
            volgorde=kt["volgorde"],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_ingest.py -k verwerk_bestand -v`
Expected: 2 PASS

- [ ] **Step 5: Run full suite + lint + format**

Run:
```bash
uv run python -m pytest
uv run ruff check src/ app/ scripts/ tests/
uv run ruff format --check src/ app/ scripts/ tests/
```
Expected: alles groen (geen regressie op bestaande ingest-tests).

- [ ] **Step 6: Commit**

```bash
git add src/validatie_samenwijzer/ingest.py tests/test_ingest.py
git commit -m "feat(ingest): KD-fallback bij nul OER-kerntaken (#53)"
```

---

## Task 5: Documentatie-update

**Files:**
- Modify: `validatie_samenwijzer/CLAUDE.md` (sectie "Ingestie-pipeline (`ingest.py`)")

- [ ] **Step 1: Werk de pipeline-beschrijving bij**

Voeg in de `## Architectuur` → `### Ingestie-pipeline (ingest.py)`-sectie, ná het code-blok dat de pipeline-stappen toont, een alinea toe:

```markdown
**KD-fallback (issue #53)**: levert de OER nul kerntaken op (bv. Aeres/Rijn IJssel-examenplannen
die de kwalificatiestructuur niet uitschrijven), dan draait `_verwerk_bestand` dezelfde extractor
over het kwalificatiedossier van die crebo (`_kerntaken_uit_kd` over `<crebo>.md`, pad via
`_pad_kwalificatiedossier`). **Fire-at-zero + supplement-never-replace**: vuurt uitsluitend bij
nul OER-kerntaken, dus instellingen die hun kerntaken wél in de OER hebben blijven OER-bron.
```

- [ ] **Step 2: Commit**

```bash
git add validatie_samenwijzer/CLAUDE.md
git commit -m "docs(validatie): documenteer KD-fallback in ingest-pipeline (#53)"
```

---

## Task 6: Integratie-verificatie tegen echte data (handmatig)

Geen automatische test — vereist de lokale `oeren/`- en `kwalificatiedossiers/`-bundels.

- [ ] **Step 1: Herindexeer en controleer kerntaak-dekking per instelling**

Run (vanuit `validatie_samenwijzer/`):
```bash
uv run python -m validatie_samenwijzer.ingest --alles --reset
uv run python -c "
import sqlite3
c=sqlite3.connect('data/validatie.db')
for r in c.execute('''SELECT i.naam, COUNT(DISTINCT o.id) oers,
  COUNT(DISTINCT CASE WHEN k.id IS NOT NULL THEN o.id END) met_kt
  FROM instellingen i JOIN oer_documenten o ON o.instelling_id=i.id
  LEFT JOIN kerntaken k ON k.oer_id=o.id WHERE o.geindexeerd=1
  GROUP BY i.naam'''):
    print(r['naam'], 'oers=%d met_kt=%d' % (r['oers'], r['met_kt']))
"
```
Expected: `aeres` en `rijn_ijssel` tonen nu `met_kt > 0` (waren 0); `davinci`, `talland`, `utrecht` blijven ≥ hun eerdere waarden (geen regressie).

- [ ] **Step 2: Bulk-seed en bevestig 5 instellingen**

Run:
```bash
uv run python scripts/seed_bulk.py
```
Expected: ~1000 studenten over **5** instellingen; geen "Overgeslagen instellingen: Aeres MBO / Rijn IJssel" in de output.

- [ ] **Step 3: Werk de issue-checkboxes bij en sluit af**

Vink de acceptatiecriteria af in issue #53 met een korte notitie dat de oorzaak het ontbreken van kerntaken in de Aeres/Rijn-OERs was (niet tabel-afvlakking) en dat KD-fallback dit dekt.

---

## Self-Review

**Spec coverage:**
- KD-fallback bij nul OER-kerntaken → Task 4. ✓
- Naam-opschoning (dotted leaders) → Task 1. ✓
- Dedup per (type, code), langste naam → Task 2. ✓
- KD-pad-resolutie (env-override, ontbrekend bestand) → Task 3. ✓
- Fire-at-zero / geen regressie → Task 4 (negatieve test) + Task 6 stap 1. ✓
- Beveiliger-test op crebo waarvan de OER 0 geeft → Task 4 (fixture-gebaseerd, crebo 25690). ✓
- ~1000 studenten / 5 instellingen → Task 6 stap 2. ✓
- Doc-update → Task 5. ✓
- Buiten scope (regex-verbreding, bron-kolom, pdfplumber/LLM) → niet geïmplementeerd, conform spec. ✓

**Placeholder scan:** geen TBD/TODO; alle code-stappen tonen volledige code. ✓

**Type consistency:** `_schoon_kd_naam(str)->str`, `_kerntaken_uit_kd(str)->list[dict]` (dict-vorm gelijk aan `extraheer_kerntaken`: `code/naam/type/volgorde`), `_pad_kwalificatiedossier(str|None)->Path|None`, `meta["crebo"]` matcht `parseer_bestandsnaam`-output. ✓
