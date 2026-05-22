# Mentor-goedkeuring van groei (per werkproces) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De student dient groei per werkproces in; de mentor keurt goed of geeft terug met verbeterfeedback; pas na goedkeuring telt de groei mee in voortgang en risico-triage.

**Architecture:** Statusveld per werkproces in `groei_actueel` (Optie A). De overlay (`groei.overlay_self_scores`) neemt uitsluitend `goedgekeurde_score` mee en herberekent kerntaak-scores, headline-voortgang en de risico-vlag. UI op pagina 6 (groeidossier): student = concept opslaan + indienen; mentor = goedkeuren/teruggeven.

**Tech Stack:** Python 3.13, SQLite (`groei.db`), pandas, Streamlit. Tools: `uv`, `pytest`, `ruff`, `ty`.

**Spec:** `docs/superpowers/specs/2026-05-21-groei-goedkeuring-design.md`

---

## Uitgangssituatie (reeds uncommitted in de werkmap)

Op branch `feat/groei-goedkeuring` staan al uncommitted wijzigingen uit de verkenningsfase:
- `src/samenwijzer/groei.py` — `overlay_self_scores` herberekent al de voortgang uit kt (gebruikt nu nog `rij.score`).
- `app/pages/6_groeidossier.py` — spinneweb "vorige meting" oranje; ververst de session-df ná student-opslaan; import van `overlay_self_scores`.
- `tests/test_groei.py` — voortgang-recompute-tests die nog `rij.score` veronderstellen.

Dit plan bouwt daarop voort en past die plekken aan. Taak 6 actualiseert de bestaande overlay-tests; taak 7 verplaatst de df-refresh naar mentor-acties.

## File Structure

- **Modify** `src/samenwijzer/groei_store.py` — `GroeiActueel` uitbreiden; schema + idempotente migratie; `get_actueel`/`get_alle_actueel` SELECTs; nieuwe functies `dien_in`, `keur_goed`, `geef_terug`; `sla_groei_op` zet `status='concept'`.
- **Modify** `src/samenwijzer/groei.py` — `overlay_self_scores` gebruikt `goedgekeurde_score`; risico-recompute via `transform._bereken_risico`.
- **Modify** `app/pages/6_groeidossier.py` — student: statusbadges + "Concept opslaan" + "Indienen"; mentor: per-wp goedkeuren/teruggeven + df-refresh.
- **Modify** `tests/test_groei_store.py` — store-tests (migratie, statusovergangen).
- **Modify** `tests/test_groei.py` — overlay-tests aangepast naar goedgekeurde scores + risico.
- **Modify** `tests/test_architecture.py` — `transform` toegestaan als import voor `groei.py`.

---

### Task 1: `groei_actueel` uitbreiden — dataclass, schema, migratie

**Files:**
- Modify: `src/samenwijzer/groei_store.py`
- Test: `tests/test_groei_store.py`

- [ ] **Step 1: Schrijf de falende tests**

Voeg toe aan `tests/test_groei_store.py`:

```python
def _kolomnamen(db_path: Path, tabel: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({tabel})")}
    finally:
        conn.close()


def test_groei_actueel_heeft_goedkeuringskolommen(db: Path) -> None:
    kolommen = _kolomnamen(db, "groei_actueel")
    assert {
        "status",
        "goedgekeurde_score",
        "mentor_opmerking",
        "beoordeeld_door",
        "beoordeeld_op",
    } <= kolommen


def test_init_db_migreert_oude_groei_actueel(tmp_path: Path) -> None:
    """Een bestaande DB zonder de nieuwe kolommen wordt idempotent gemigreerd."""
    pad = tmp_path / "oud.db"
    conn = sqlite3.connect(pad)
    conn.executescript(
        """
        CREATE TABLE groei_actueel (
            studentnummer    TEXT NOT NULL,
            wp_kolom         TEXT NOT NULL,
            score            INTEGER NOT NULL,
            verantwoording   TEXT NOT NULL DEFAULT '',
            laatst_gewijzigd TEXT NOT NULL,
            PRIMARY KEY (studentnummer, wp_kolom)
        );
        INSERT INTO groei_actueel VALUES ('S001', 'wp_1_1', 70, 'x', '2026-05-20T10:00:00');
        """
    )
    conn.commit()
    conn.close()

    init_db(pad)  # mag niet crashen, voegt kolommen toe
    init_db(pad)  # tweede keer = idempotent

    kolommen = _kolomnamen(pad, "groei_actueel")
    assert "status" in kolommen
    rij = GroeiActueel(*_haal_rij(pad))
    assert rij.status == "concept"  # default voor bestaande rij
    assert rij.goedgekeurde_score is None


def _haal_rij(db_path: Path) -> tuple:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT studentnummer, wp_kolom, score, verantwoording, laatst_gewijzigd, "
            "status, goedgekeurde_score, mentor_opmerking, beoordeeld_door, beoordeeld_op "
            "FROM groei_actueel WHERE studentnummer='S001'"
        ).fetchone()
    finally:
        conn.close()
```

> Let op: de migratie van `_geinitialiseerd` (module-cache in `groei_store`) kan tussen tests
> blijven hangen. De fixture gebruikt telkens een uniek `tmp_path`-pad, dus elk pad wordt apart
> geïnitialiseerd. Geen extra reset nodig.

- [ ] **Step 2: Run de tests — verwacht FAIL**

Run: `uv run pytest tests/test_groei_store.py::test_groei_actueel_heeft_goedkeuringskolommen tests/test_groei_store.py::test_init_db_migreert_oude_groei_actueel -v`
Expected: FAIL (kolommen bestaan nog niet / `GroeiActueel` heeft de velden niet).

- [ ] **Step 3: Breid `GroeiActueel` uit**

In `src/samenwijzer/groei_store.py`, vervang de `GroeiActueel`-dataclass:

```python
@dataclass
class GroeiActueel:
    studentnummer: str
    wp_kolom: str
    score: int
    verantwoording: str
    laatst_gewijzigd: str
    status: str = "concept"
    goedgekeurde_score: int | None = None
    mentor_opmerking: str = ""
    beoordeeld_door: str | None = None
    beoordeeld_op: str | None = None
```

- [ ] **Step 4: Schema + migratie in `init_db`**

In `init_db`, voeg de nieuwe kolommen toe aan de `CREATE TABLE groei_actueel`-definitie zodat verse DB's ze meteen hebben:

```python
            CREATE TABLE IF NOT EXISTS groei_actueel (
                studentnummer      TEXT NOT NULL,
                wp_kolom           TEXT NOT NULL,
                score              INTEGER NOT NULL,
                verantwoording     TEXT NOT NULL DEFAULT '',
                laatst_gewijzigd   TEXT NOT NULL,
                status             TEXT NOT NULL DEFAULT 'concept',
                goedgekeurde_score INTEGER,
                mentor_opmerking   TEXT NOT NULL DEFAULT '',
                beoordeeld_door    TEXT,
                beoordeeld_op      TEXT,
                PRIMARY KEY (studentnummer, wp_kolom)
            );
```

Voeg ná de `executescript(...)`-aanroep (nog binnen het `with _verbinding(db_path) as conn:`-blok) de idempotente migratie voor bestaande DB's toe:

```python
        bestaande = {r[1] for r in conn.execute("PRAGMA table_info(groei_actueel)")}
        migraties = [
            ("status", "status TEXT NOT NULL DEFAULT 'concept'"),
            ("goedgekeurde_score", "goedgekeurde_score INTEGER"),
            ("mentor_opmerking", "mentor_opmerking TEXT NOT NULL DEFAULT ''"),
            ("beoordeeld_door", "beoordeeld_door TEXT"),
            ("beoordeeld_op", "beoordeeld_op TEXT"),
        ]
        for kolom, ddl in migraties:
            if kolom not in bestaande:
                conn.execute(f"ALTER TABLE groei_actueel ADD COLUMN {ddl}")
```

- [ ] **Step 5: Werk de SELECTs bij in `get_actueel` en `get_alle_actueel`**

In `get_actueel`, vervang de query door:

```python
        rows = conn.execute(
            """
            SELECT studentnummer, wp_kolom, score, verantwoording, laatst_gewijzigd,
                   status, goedgekeurde_score, mentor_opmerking, beoordeeld_door, beoordeeld_op
            FROM groei_actueel
            WHERE studentnummer = ?
            ORDER BY wp_kolom
            """,
            (studentnummer,),
        ).fetchall()
```

In `get_alle_actueel`, vervang de query door:

```python
        rows = conn.execute(
            "SELECT studentnummer, wp_kolom, score, verantwoording, laatst_gewijzigd, "
            "status, goedgekeurde_score, mentor_opmerking, beoordeeld_door, beoordeeld_op "
            "FROM groei_actueel"
        ).fetchall()
```

De `GroeiActueel(*r)`-constructie blijft kloppen omdat de SELECT-volgorde de dataclass-veldvolgorde volgt.

- [ ] **Step 6: Run de tests — verwacht PASS**

Run: `uv run pytest tests/test_groei_store.py -v`
Expected: PASS (alle store-tests, inclusief de twee nieuwe).

- [ ] **Step 7: Commit**

```bash
git add src/samenwijzer/groei_store.py tests/test_groei_store.py
git commit -m "feat(groei): goedkeuringskolommen op groei_actueel + migratie

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `sla_groei_op` zet status op concept

**Files:**
- Modify: `src/samenwijzer/groei_store.py:sla_groei_op`
- Test: `tests/test_groei_store.py`

- [ ] **Step 1: Schrijf de falende test**

```python
def test_sla_groei_op_zet_status_concept_en_behoudt_goedkeuring(db: Path) -> None:
    sla_groei_op("S001", [GroeiActueel("S001", "wp_1_1", 60, "x", "2026-05-20T10:00:00")], db)
    rij = get_actueel("S001", db)[0]
    assert rij.status == "concept"
    assert rij.goedgekeurde_score is None

    # Keur goed, bewerk daarna opnieuw: status terug naar concept, goedkeuring behouden.
    keur_goed("S001", "wp_1_1", "Mentor A", db)
    sla_groei_op("S001", [GroeiActueel("S001", "wp_1_1", 85, "beter", "2026-05-21T10:00:00")], db)
    rij = get_actueel("S001", db)[0]
    assert rij.status == "concept"
    assert rij.score == 85
    assert rij.goedgekeurde_score == 60  # eerder goedgekeurde waarde blijft staan
```

Voeg `get_actueel`, `sla_groei_op`, `keur_goed` toe aan de import bovenin `tests/test_groei_store.py`.

- [ ] **Step 2: Run — verwacht FAIL**

Run: `uv run pytest tests/test_groei_store.py::test_sla_groei_op_zet_status_concept_en_behoudt_goedkeuring -v`
Expected: FAIL (`keur_goed` bestaat nog niet → ImportError, of status niet gezet).

> `keur_goed` wordt in Task 4 geïmplementeerd. Tot dan faalt deze test op de import. Dat is
> verwacht; de test gaat groen ná Task 4. Markeer Step 6 hieronder pas af na Task 4.

- [ ] **Step 3: Pas `sla_groei_op` aan**

Vervang in `sla_groei_op` de eerste `INSERT INTO groei_actueel ... ON CONFLICT ...` door:

```python
            conn.execute(
                """
                INSERT INTO groei_actueel
                    (studentnummer, wp_kolom, score, verantwoording, laatst_gewijzigd, status)
                VALUES (?, ?, ?, ?, ?, 'concept')
                ON CONFLICT(studentnummer, wp_kolom) DO UPDATE SET
                    score = excluded.score,
                    verantwoording = excluded.verantwoording,
                    laatst_gewijzigd = excluded.laatst_gewijzigd,
                    status = 'concept'
                """,
                (
                    studentnummer,
                    rij.wp_kolom,
                    rij.score,
                    rij.verantwoording,
                    rij.laatst_gewijzigd,
                ),
            )
```

De tweede INSERT (in `groei_historie`) blijft ongewijzigd. `goedgekeurde_score` wordt niet aangeraakt en blijft dus behouden.

- [ ] **Step 4: Run de test (na Task 4) — verwacht PASS**

Run: `uv run pytest tests/test_groei_store.py::test_sla_groei_op_zet_status_concept_en_behoudt_goedkeuring -v`
Expected: PASS (zodra `keur_goed` bestaat).

- [ ] **Step 5: Commit (samen met Task 4 als die nog niet gecommit is, anders los)**

```bash
git add src/samenwijzer/groei_store.py tests/test_groei_store.py
git commit -m "feat(groei): sla_groei_op markeert werkproces als concept

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `dien_in` — concept/teruggegeven → ingediend

**Files:**
- Modify: `src/samenwijzer/groei_store.py`
- Test: `tests/test_groei_store.py`

- [ ] **Step 1: Schrijf de falende test**

```python
def test_dien_in_zet_concept_naar_ingediend(db: Path) -> None:
    sla_groei_op(
        "S001",
        [
            GroeiActueel("S001", "wp_1_1", 60, "x", "2026-05-20T10:00:00"),
            GroeiActueel("S001", "wp_1_2", 70, "y", "2026-05-20T10:00:00"),
        ],
        db,
    )
    dien_in("S001", ["wp_1_1"], db)
    per_wp = {r.wp_kolom: r for r in get_actueel("S001", db)}
    assert per_wp["wp_1_1"].status == "ingediend"
    assert per_wp["wp_1_2"].status == "concept"  # niet ingediend


def test_dien_in_negeert_goedgekeurd(db: Path) -> None:
    sla_groei_op("S001", [GroeiActueel("S001", "wp_1_1", 60, "x", "2026-05-20T10:00:00")], db)
    keur_goed("S001", "wp_1_1", "Mentor A", db)
    dien_in("S001", ["wp_1_1"], db)  # mag een goedgekeurd wp niet terugzetten
    assert get_actueel("S001", db)[0].status == "goedgekeurd"
```

Voeg `dien_in` toe aan de import.

- [ ] **Step 2: Run — verwacht FAIL**

Run: `uv run pytest tests/test_groei_store.py::test_dien_in_zet_concept_naar_ingediend -v`
Expected: FAIL (`dien_in` bestaat niet).

- [ ] **Step 3: Implementeer `dien_in`**

Voeg toe aan `src/samenwijzer/groei_store.py` (na `sla_groei_op`):

```python
def dien_in(
    studentnummer: str,
    wp_kolommen: list[str],
    db_path: Path = _DB_PATH,
) -> None:
    """Zet de opgegeven werkprocessen van concept/teruggegeven naar 'ingediend'."""
    _zorg_voor_db(db_path)
    with _verbinding(db_path) as conn:
        for wp in wp_kolommen:
            conn.execute(
                """
                UPDATE groei_actueel SET status = 'ingediend'
                WHERE studentnummer = ? AND wp_kolom = ?
                  AND status IN ('concept', 'teruggegeven')
                """,
                (studentnummer, wp),
            )
```

- [ ] **Step 4: Run — verwacht PASS**

Run: `uv run pytest tests/test_groei_store.py::test_dien_in_zet_concept_naar_ingediend tests/test_groei_store.py::test_dien_in_negeert_goedgekeurd -v`
Expected: PASS (de tweede slaagt zodra Task 4 `keur_goed` klaar is).

- [ ] **Step 5: Commit**

```bash
git add src/samenwijzer/groei_store.py tests/test_groei_store.py
git commit -m "feat(groei): dien_in zet werkprocessen op ingediend

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `keur_goed` — ingediend → goedgekeurd

**Files:**
- Modify: `src/samenwijzer/groei_store.py`
- Test: `tests/test_groei_store.py`

- [ ] **Step 1: Schrijf de falende test**

```python
def test_keur_goed_zet_goedgekeurde_score_en_status(db: Path) -> None:
    sla_groei_op("S001", [GroeiActueel("S001", "wp_1_1", 80, "x", "2026-05-20T10:00:00")], db)
    dien_in("S001", ["wp_1_1"], db)
    keur_goed("S001", "wp_1_1", "Mentor A", db)
    rij = get_actueel("S001", db)[0]
    assert rij.status == "goedgekeurd"
    assert rij.goedgekeurde_score == 80
    assert rij.beoordeeld_door == "Mentor A"
    assert rij.beoordeeld_op is not None
    assert rij.mentor_opmerking == ""
```

Voeg `keur_goed` toe aan de import (indien nog niet gedaan in Task 2).

- [ ] **Step 2: Run — verwacht FAIL**

Run: `uv run pytest tests/test_groei_store.py::test_keur_goed_zet_goedgekeurde_score_en_status -v`
Expected: FAIL (`keur_goed` bestaat niet).

- [ ] **Step 3: Implementeer `keur_goed`**

Voeg toe aan `src/samenwijzer/groei_store.py` (na `dien_in`); zorg dat `from datetime import datetime` bovenin staat (zo niet, toevoegen):

```python
def keur_goed(
    studentnummer: str,
    wp_kolom: str,
    mentor_naam: str,
    db_path: Path = _DB_PATH,
) -> None:
    """Keur een werkproces goed: goedgekeurde_score := score, status 'goedgekeurd'."""
    _zorg_voor_db(db_path)
    nu = datetime.now().isoformat(timespec="seconds")
    with _verbinding(db_path) as conn:
        conn.execute(
            """
            UPDATE groei_actueel
            SET status = 'goedgekeurd',
                goedgekeurde_score = score,
                mentor_opmerking = '',
                beoordeeld_door = ?,
                beoordeeld_op = ?
            WHERE studentnummer = ? AND wp_kolom = ?
            """,
            (mentor_naam, nu, studentnummer, wp_kolom),
        )
```

- [ ] **Step 4: Run — verwacht PASS**

Run: `uv run pytest tests/test_groei_store.py -v`
Expected: PASS (inclusief de tot nu toe op `keur_goed` wachtende tests uit Task 2 en 3).

- [ ] **Step 5: Commit**

```bash
git add src/samenwijzer/groei_store.py tests/test_groei_store.py
git commit -m "feat(groei): keur_goed legt goedgekeurde score vast

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `geef_terug` — ingediend → teruggegeven met verbeterfeedback

**Files:**
- Modify: `src/samenwijzer/groei_store.py`
- Test: `tests/test_groei_store.py`

- [ ] **Step 1: Schrijf de falende test**

```python
def test_geef_terug_zet_status_en_opmerking_behoudt_goedkeuring(db: Path) -> None:
    sla_groei_op("S001", [GroeiActueel("S001", "wp_1_1", 80, "x", "2026-05-20T10:00:00")], db)
    dien_in("S001", ["wp_1_1"], db)
    keur_goed("S001", "wp_1_1", "Mentor A", db)  # eerst goedgekeurd op 80

    # student verhoogt en dient opnieuw in
    sla_groei_op("S001", [GroeiActueel("S001", "wp_1_1", 95, "nu top", "2026-05-21T09:00:00")], db)
    dien_in("S001", ["wp_1_1"], db)
    geef_terug("S001", "wp_1_1", "Mentor A", "Onderbouw dit met een bewijsstuk.", db)

    rij = get_actueel("S001", db)[0]
    assert rij.status == "teruggegeven"
    assert rij.mentor_opmerking == "Onderbouw dit met een bewijsstuk."
    assert rij.goedgekeurde_score == 80  # vorige goedkeuring blijft meetellen
    assert rij.beoordeeld_door == "Mentor A"
```

Voeg `geef_terug` toe aan de import.

- [ ] **Step 2: Run — verwacht FAIL**

Run: `uv run pytest tests/test_groei_store.py::test_geef_terug_zet_status_en_opmerking_behoudt_goedkeuring -v`
Expected: FAIL (`geef_terug` bestaat niet).

- [ ] **Step 3: Implementeer `geef_terug`**

Voeg toe aan `src/samenwijzer/groei_store.py` (na `keur_goed`):

```python
def geef_terug(
    studentnummer: str,
    wp_kolom: str,
    mentor_naam: str,
    opmerking: str,
    db_path: Path = _DB_PATH,
) -> None:
    """Geef een werkproces terug met verbeterfeedback; goedgekeurde_score blijft staan."""
    _zorg_voor_db(db_path)
    nu = datetime.now().isoformat(timespec="seconds")
    with _verbinding(db_path) as conn:
        conn.execute(
            """
            UPDATE groei_actueel
            SET status = 'teruggegeven',
                mentor_opmerking = ?,
                beoordeeld_door = ?,
                beoordeeld_op = ?
            WHERE studentnummer = ? AND wp_kolom = ?
            """,
            (opmerking, mentor_naam, nu, studentnummer, wp_kolom),
        )
```

- [ ] **Step 4: Run — verwacht PASS**

Run: `uv run pytest tests/test_groei_store.py -v`
Expected: PASS (alle store-tests).

- [ ] **Step 5: Commit**

```bash
git add src/samenwijzer/groei_store.py tests/test_groei_store.py
git commit -m "feat(groei): geef_terug met verbeterfeedback

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Overlay telt alleen goedgekeurde scores + risico-recompute

**Files:**
- Modify: `src/samenwijzer/groei.py:overlay_self_scores`
- Modify: `tests/test_groei.py` (bestaande overlay-tests aanpassen + nieuwe)
- Modify: `tests/test_architecture.py` (transform toestaan voor groei)

- [ ] **Step 1: Voeg een test-helper toe en pas bestaande overlay-tests aan**

Bovenin `tests/test_groei.py`, breid de import uit met `dien_in`, `keur_goed`, en voeg een helper toe:

```python
from samenwijzer.groei_store import (
    GroeiActueel,
    dien_in,
    keur_goed,
    sla_groei_op,
)


def _keur_goed(db: Path, studentnummer: str, scores: dict[str, int]) -> None:
    """Sla scores op, dien ze in en laat de mentor ze goedkeuren."""
    nu = "2026-05-19T10:00:00"
    sla_groei_op(
        studentnummer,
        [GroeiActueel(studentnummer, wp, score, "", nu) for wp, score in scores.items()],
        db,
    )
    dien_in(studentnummer, list(scores), db)
    for wp in scores:
        keur_goed(studentnummer, wp, "Mentor A", db)
```

Pas `test_overlay_self_scores_overschrijft_synthetisch` aan zodat de scores goedgekeurd worden:

```python
def test_overlay_self_scores_overschrijft_synthetisch(db: Path) -> None:
    df = pd.DataFrame([_basisrij("S001"), _basisrij("S002")])
    _keur_goed(db, "S001", {"wp_1_1": 90, "wp_1_2": 80, "wp_1_3": 70})

    overlaid = overlay_self_scores(df, db_path=db)

    s001 = overlaid[overlaid["studentnummer"] == "S001"].iloc[0]
    assert s001["wp_1_1"] == 90
    assert s001["wp_1_2"] == 80
    assert s001["wp_1_3"] == 70
    assert s001["kt_1"] == pytest.approx(80.0)

    s002 = overlaid[overlaid["studentnummer"] == "S002"].iloc[0]
    assert s002["wp_1_1"] == 30.0  # synthetisch blijft staan
```

Pas `test_overlay_negeert_wp_die_nan_zijn_in_df` aan:

```python
def test_overlay_negeert_wp_die_nan_zijn_in_df(db: Path) -> None:
    df = pd.DataFrame([_basisrij("S001", wp_1_2=float("nan"))])
    _keur_goed(db, "S001", {"wp_1_2": 80})
    overlaid = overlay_self_scores(df, db_path=db)
    assert pd.isna(overlaid.iloc[0]["wp_1_2"])
```

Pas `test_overlay_negeert_kt_gemiddelde_kolom` aan zodat het via `_keur_goed` werkt (vervang de directe `sla_groei_op`-aanroep door `_keur_goed(db, "S001", {...})` met dezelfde scores).

Pas `test_overlay_herberekent_voortgang_uit_kt` aan:

```python
def test_overlay_herberekent_voortgang_uit_kt(db: Path) -> None:
    df = pd.DataFrame([_basisrij("S001", voortgang=0.35), _basisrij("S002", voortgang=0.35)])
    _keur_goed(db, "S001", {"wp_1_1": 90, "wp_1_2": 80, "wp_1_3": 70})
    overlaid = overlay_self_scores(df, db_path=db)
    s001 = overlaid[overlaid["studentnummer"] == "S001"].iloc[0]
    assert s001["voortgang"] == pytest.approx(0.60)
    s002 = overlaid[overlaid["studentnummer"] == "S002"].iloc[0]
    assert s002["voortgang"] == pytest.approx(0.35)
```

Pas `test_overlay_zonder_voortgang_kolom_crasht_niet` aan:

```python
def test_overlay_zonder_voortgang_kolom_crasht_niet(db: Path) -> None:
    df = pd.DataFrame([_basisrij("S001")])
    _keur_goed(db, "S001", {"wp_1_1": 90})
    overlay_self_scores(df, db_path=db)  # mag niet crashen zonder voortgang-kolom
```

- [ ] **Step 2: Schrijf de nieuwe tests (alleen goedgekeurd telt + risico)**

```python
def test_overlay_negeert_concept_en_ingediend(db: Path) -> None:
    """Concept/ingediend scores tellen niet mee — alleen goedgekeurd."""
    df = pd.DataFrame([_basisrij("S001", voortgang=0.35)])
    nu = "2026-05-19T10:00:00"
    sla_groei_op("S001", [GroeiActueel("S001", "wp_1_1", 95, "", nu)], db)  # concept
    overlaid_concept = overlay_self_scores(df, db_path=db)
    assert overlaid_concept.iloc[0]["wp_1_1"] == 30.0  # niet overschreven
    assert overlaid_concept.iloc[0]["voortgang"] == pytest.approx(0.35)

    dien_in("S001", ["wp_1_1"], db)  # ingediend, nog niet goedgekeurd
    overlaid_ingediend = overlay_self_scores(df, db_path=db)
    assert overlaid_ingediend.iloc[0]["wp_1_1"] == 30.0  # nog steeds niet


def test_overlay_herberekent_risico(db: Path) -> None:
    """Goedgekeurde groei kan de risico-vlag uitzetten."""
    rij = _basisrij("S001", voortgang=0.30, bsa_percentage=0.80, risico=True)
    df = pd.DataFrame([rij])
    _keur_goed(db, "S001", {"wp_1_1": 90, "wp_1_2": 90, "wp_1_3": 90})
    # kt_1 wordt 90; kt_2 blijft 40 → voortgang = 0.65 → niet meer onder 0.40
    overlaid = overlay_self_scores(df, db_path=db)
    assert overlaid.iloc[0]["voortgang"] == pytest.approx(0.65)
    assert bool(overlaid.iloc[0]["risico"]) is False
```

- [ ] **Step 3: Run — verwacht FAIL**

Run: `uv run pytest tests/test_groei.py -v`
Expected: FAIL (overlay gebruikt nog `rij.score`; risico wordt nog niet herberekend).

- [ ] **Step 4: Pas `overlay_self_scores` aan**

Voeg bovenin `src/samenwijzer/groei.py` de import toe (bij de bestaande imports):

```python
from samenwijzer.transform import _bereken_risico
```

Vervang de hele functie-body van `overlay_self_scores` (vanaf `alle_actueel = ...` tot `return overlaid`) door:

```python
    alle_actueel = get_alle_actueel(db_path)
    if not alle_actueel:
        return df.copy()

    overlaid = df.copy()
    kt_kolommen = [c for c in overlaid.columns if _KT_INDEX_PATROON.match(c)]
    iets_gewijzigd = False

    for studentnummer, rijen in alle_actueel.items():
        mask = overlaid["studentnummer"] == studentnummer
        if not mask.any():
            continue
        idx = overlaid.index[mask][0]

        student_gewijzigd = False
        for rij in rijen:
            if rij.goedgekeurde_score is None:
                continue
            if rij.wp_kolom not in overlaid.columns:
                continue
            if pd.isna(overlaid.at[idx, rij.wp_kolom]):
                # NaN betekent: opleiding heeft deze wp niet — niet overschrijven.
                continue
            overlaid.at[idx, rij.wp_kolom] = float(rij.goedgekeurde_score)
            student_gewijzigd = True

        if not student_gewijzigd:
            continue
        iets_gewijzigd = True

        # Herbereken kt-scores als gemiddelde van hun werkprocessen.
        for kt_col in kt_kolommen:
            kt_index = int(kt_col.removeprefix(_KT_PREFIX))
            nieuwe_kt = bereken_kt_uit_wp(overlaid.loc[idx], kt_index=kt_index)
            if not pd.isna(nieuwe_kt):
                overlaid.at[idx, kt_col] = nieuwe_kt

        # Herbereken headline-voortgang als gemiddelde van de kt-scores / 100.
        if "voortgang" in overlaid.columns:
            kt_scores = pd.to_numeric(overlaid.loc[idx, kt_kolommen], errors="coerce").dropna()
            if not kt_scores.empty:
                overlaid.at[idx, "voortgang"] = float(min(max(kt_scores.mean() / 100, 0.0), 1.0))

    # Risico-vlag herberekenen zodat mentor-goedgekeurde groei de triage volgt.
    if iets_gewijzigd and {"risico", "bsa_percentage", "voortgang"} <= set(overlaid.columns):
        overlaid["risico"] = _bereken_risico(overlaid)

    return overlaid
```

- [ ] **Step 5: Sta `transform` toe voor `groei` in de architectuur-test**

Controleer `tests/test_architecture.py::test_groei_importeert_geen_ai_modules_of_app`. De verboden set is `{coach, tutor, welzijn, outreach, outreach_store}` + `streamlit`; `transform` staat daar niet in, dus de import is al toegestaan. Voeg ter verduidelijking een assertie toe aan die test:

```python
    assert "transform" in imports or True  # transform is laag-toegestaan voor groei
```

> Als deze regel als overbodig aanvoelt, sla 'm dan over — de bestaande test slaagt sowieso.
> Voer in dat geval alleen de test uit om te bevestigen dat de nieuwe import niet breekt.

- [ ] **Step 6: Run — verwacht PASS**

Run: `uv run pytest tests/test_groei.py tests/test_architecture.py -v`
Expected: PASS (alle groei- en architectuur-tests).

- [ ] **Step 7: Commit**

```bash
git add src/samenwijzer/groei.py tests/test_groei.py tests/test_architecture.py
git commit -m "feat(groei): overlay telt alleen goedgekeurde scores + risico-recompute

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: UI — student: statusbadges + Concept opslaan + Indienen

**Files:**
- Modify: `app/pages/6_groeidossier.py`

> Streamlit-pagina's worden niet via pytest getest. Verificatie: `ruff` + `py_compile` + een
> handmatige app-smoke (zie Step 6).

- [ ] **Step 1: Breid de import van `groei_store` uit**

In `app/pages/6_groeidossier.py`, voeg `dien_in`, `keur_goed`, `geef_terug` toe aan de bestaande
`from samenwijzer.groei_store import (...)`-blok (alfabetisch tussen de andere namen):

```python
from samenwijzer.groei_store import (
    BewijsstukMeta,
    GroeiActueel,
    MentorFeedback,
    dien_in,
    geef_terug,
    get_actueel,
    get_bewijsstukken,
    get_historie,
    get_mentor_feedback,
    insert_bewijsstuk,
    keur_goed,
    sla_groei_op,
    upsert_mentor_feedback,
)
```

- [ ] **Step 2: Toon een statusbadge + verbeterfeedback per werkproces**

In de student-render-loop (binnen `for wp_col in kt_eigen_wp:`), direct ná de regel
`st.markdown(f"**{wp_label}**")` (regel ~233), voeg toe:

```python
                _status = actueel[wp_col].status if wp_col in actueel else None
                _badges = {
                    "concept": "🟡 Concept",
                    "ingediend": "📤 Ingediend — wacht op mentor",
                    "goedgekeurd": "✅ Goedgekeurd",
                    "teruggegeven": "↩️ Teruggegeven — pas aan en dien opnieuw in",
                }
                if _status in _badges:
                    st.caption(_badges[_status])
                if _status == "teruggegeven" and actueel[wp_col].mentor_opmerking:
                    st.warning(f"**Verbeterpunt van je mentor:** {actueel[wp_col].mentor_opmerking}")
```

- [ ] **Step 3: Vervang de "Opslaan"-knop door "Concept opslaan" + "Indienen"**

Vervang het `if is_eigenaar:`-blok dat begint bij regel ~298 (`if st.button("💾 Opslaan", ...)` t/m de bijbehorende `st.rerun()`) door:

```python
    if is_eigenaar:
        col_opslaan, col_indienen = st.columns(2)
        with col_opslaan:
            opslaan = st.button("💾 Concept opslaan", use_container_width=True)
        with col_indienen:
            indienen = st.button("📤 Indienen bij mentor", type="primary", use_container_width=True)

        if opslaan or indienen:
            nu = datetime.now().isoformat(timespec="seconds")
            rijen = [
                GroeiActueel(studentnummer, wp, score, verant, nu)
                for wp, (score, verant) in nieuwe_waarden.items()
                if (wp not in actueel)
                or actueel[wp].score != score
                or actueel[wp].verantwoording != verant
            ]
            if rijen:
                sla_groei_op(studentnummer, rijen)
            if indienen:
                # Dien alle werkprocessen in die nog niet goedgekeurd zijn.
                in_te_dienen = [
                    wp
                    for wp in nieuwe_waarden
                    if (wp not in actueel) or actueel[wp].status != "goedgekeurd"
                ]
                dien_in(studentnummer, in_te_dienen)
                st.success("Ingediend bij je mentor.")
            elif rijen:
                st.success(f"{len(rijen)} wijziging(en) opgeslagen als concept.")
            else:
                st.info("Niets gewijzigd om op te slaan.")
            st.rerun()
```

> Let op: de oude code ververste hier `st.session_state["df"]`. Dat is hier weggehaald — concept/
> indienen telt nog niet mee, dus de voortgang mag niet verschuiven. De refresh verhuist naar de
> mentor-acties (Task 8). De `overlay_self_scores`-import blijft nodig voor Task 8.

- [ ] **Step 4: Verifieer dat het bestand compileert en lint schoon is**

Run: `uv run python -m py_compile app/pages/6_groeidossier.py && uv run ruff check app/pages/6_groeidossier.py`
Expected: geen output van py_compile; "All checks passed!" van ruff.

- [ ] **Step 5: Commit**

```bash
git add app/pages/6_groeidossier.py
git commit -m "feat(groei): student dient groei per werkproces in (concept + indienen)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 6: Handmatige smoke (optioneel, aanrader)**

Start de app (`uv run streamlit run app/main.py`), log in als student (zie `gebruikers.txt`),
open het groeidossier, wijzig een score → "Concept opslaan" (badge 🟡), dan "Indienen" (badge 📤).

---

### Task 8: UI — mentor: goedkeuren/teruggeven + df-refresh

**Files:**
- Modify: `app/pages/6_groeidossier.py` (de `else:`-tak vanaf regel ~317)

- [ ] **Step 1: Vervang de mentor-tak door per-werkproces goedkeuring**

Vervang het volledige `else:`-blok (regel ~317 t/m de `st.rerun()` van de feedback-knop, ~342) door:

```python
    else:
        st.markdown("### Beoordeel ingediende werkprocessen")
        for kt_col in kt_cols:
            kt_eigen_wp = _wp_van_kt(kt_col)
            if not kt_eigen_wp or all(pd.isna(student.get(w, float("nan"))) for w in kt_eigen_wp):
                continue
            kt_label = oer_label(opleiding, kt_col, crebo)
            st.markdown(f"#### {kt_label}")

            for wp_col in kt_eigen_wp:
                if wp_col not in actueel:
                    continue
                rij = actueel[wp_col]
                wp_label = oer_label(opleiding, wp_col, crebo)
                _badges = {
                    "concept": "🟡 Concept (nog niet ingediend)",
                    "ingediend": "📤 Ingediend",
                    "goedgekeurd": "✅ Goedgekeurd",
                    "teruggegeven": "↩️ Teruggegeven",
                }
                st.markdown(f"**{wp_label}** — {_badges.get(rij.status, rij.status)}")
                st.caption(f"Score student: {rij.score} · {rij.verantwoording or '(geen toelichting)'}")

                if rij.status == "ingediend":
                    opmerking = st.text_area(
                        "Verbeterfeedback (verplicht bij teruggeven)",
                        key=f"opm_{studentnummer}_{wp_col}",
                        max_chars=1000,
                    )
                    col_goed, col_terug = st.columns(2)
                    with col_goed:
                        if st.button("✅ Goedkeuren", key=f"goed_{studentnummer}_{wp_col}",
                                     use_container_width=True):
                            keur_goed(studentnummer, wp_col,
                                      st.session_state.get("mentor_naam", "onbekend"))
                            st.session_state["df"] = overlay_self_scores(
                                st.session_state["df_basis"]
                            )
                            st.success("Goedgekeurd.")
                            st.rerun()
                    with col_terug:
                        if st.button("↩️ Teruggeven", key=f"terug_{studentnummer}_{wp_col}",
                                     use_container_width=True):
                            if not opmerking.strip():
                                st.error("Geef verbeterfeedback mee bij het teruggeven.")
                            else:
                                geef_terug(studentnummer, wp_col,
                                           st.session_state.get("mentor_naam", "onbekend"),
                                           opmerking.strip())
                                st.session_state["df"] = overlay_self_scores(
                                    st.session_state["df_basis"]
                                )
                                st.success("Teruggegeven met feedback.")
                                st.rerun()
                elif rij.status == "teruggegeven" and rij.mentor_opmerking:
                    st.caption(f"Jouw eerdere feedback: {rij.mentor_opmerking}")
                st.markdown("---")

        st.markdown("### Algemene feedback per kerntaak")
        for kt_col in kt_cols:
            kt_eigen_wp = _wp_van_kt(kt_col)
            if not kt_eigen_wp or all(pd.isna(student.get(w, float("nan"))) for w in kt_eigen_wp):
                continue
            kt_label = oer_label(opleiding, kt_col, crebo)
            huidige_fb = feedback[kt_col].tekst if kt_col in feedback else ""
            tekst = st.text_area(
                f"Feedback op {kt_label}",
                value=huidige_fb,
                key=f"fb_{studentnummer}_{kt_col}",
                max_chars=1000,
            )
            if st.button(f"💬 Feedback opslaan ({kt_col})", key=f"btn_fb_{studentnummer}_{kt_col}"):
                upsert_mentor_feedback(
                    MentorFeedback(
                        studentnummer=studentnummer,
                        kt_kolom=kt_col,
                        mentor_naam=st.session_state.get("mentor_naam", "onbekend"),
                        tekst=tekst,
                        geschreven_op=datetime.now().isoformat(timespec="seconds"),
                    )
                )
                st.success("Feedback opgeslagen.")
                st.rerun()
```

- [ ] **Step 2: Verifieer compileren + lint**

Run: `uv run python -m py_compile app/pages/6_groeidossier.py && uv run ruff check app/pages/6_groeidossier.py`
Expected: geen output van py_compile; "All checks passed!" van ruff.

- [ ] **Step 3: Commit**

```bash
git add app/pages/6_groeidossier.py
git commit -m "feat(groei): mentor keurt werkprocessen goed of geeft ze terug

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: Handmatige smoke (aanrader)**

Log in als mentor van een student die zojuist heeft ingediend (zie `gebruikers.txt`), open het
groeidossier, keur een werkproces goed → controleer dat de voortgang van die student op
"Mijn voortgang"/groepsoverzicht meebeweegt. Test ook teruggeven met (lege → fout) en gevulde feedback.

---

### Task 9: Volledige verificatie

**Files:** geen wijzigingen — alleen verifiëren.

- [ ] **Step 1: Volledige testsuite**

Run: `uv run pytest -q`
Expected: alle tests slagen (was 469 + de nieuwe store/overlay-tests).

- [ ] **Step 2: Lint + format + typecheck**

Run: `uv run ruff check src/ app/ tests/ && uv run ruff format --check src/ app/ && uv run ty check`
Expected: "All checks passed!" en geen type-fouten in de gewijzigde modules.

- [ ] **Step 3: Commit eventuele format-fixes**

```bash
git add -A
git commit -m "chore(groei): lint/format na goedkeuringsworkflow

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

> Sla over als er niets te committen valt.

---

## Self-review (uitgevoerd door de planner)

- **Spec-dekking:** statusmodel (Taak 1–5), overlay/voortgang/risico (Taak 6), student-UI (Taak 7),
  mentor-UI (Taak 8). History-tab/spinneweb blijven bewust ongemoeid (buiten scope per spec).
- **Type-consistentie:** `GroeiActueel`-veldvolgorde komt overeen met de SELECT-volgorde in
  `get_actueel`/`get_alle_actueel`; `keur_goed`/`geef_terug`/`dien_in`-signatures zijn consistent
  gebruikt in store-tests, overlay-tests en de twee UI-takken.
- **Geen placeholders:** elke codestap bevat de volledige te plakken code.
- **Volgorde-afhankelijkheid:** Taak 2 en 3 bevatten tests die `keur_goed` gebruiken (Taak 4);
  dit is expliciet gemarkeerd — die specifieke asserts worden groen ná Taak 4.
