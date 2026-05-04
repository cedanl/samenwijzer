# Synthetisch dataset herstructureren (B3a)

**Status:** Design — goedgekeurd 2026-05-04
**Auteur:** Ed de Feber (`ed.de.feber@gmail.com`) i.s.m. Claude Code
**Scope:** alleen `samenwijzer/` — `validatie_samenwijzer/` blijft onaangeroerd

## 1. Doel

De synthetische 1000-studenten-dataset (nu in `data/01-raw/berend/`) omvormen tot een opleidingsspecifieke dataset waarbij elke student gekoppeld is aan een echte OER. Dit legt het fundament voor sub-project **B** (OER-markdown als context aan coach-functies meegeven) en sluit aan bij `validatie_samenwijzer`'s data-model.

Daarnaast: alle vermeldingen van "berend" verdwijnen uit de codebase — folder, code, tests, docs.

## 2. Niet-doelen

- Geen wijzigingen in `validatie_samenwijzer`.
- Geen wijziging aan `coach.py`, `tutor.py`, `welzijn.py`, `whatsapp.py`, `outreach.py` of UI-pagina's. Die volgen in sub-project B.
- Geen ChromaDB of embedding-pipeline in samenwijzer (geen retrieval — full-doc komt in B).
- Geen wijzigingen aan de data-dictionary van wat de samenwijzer-app gebruikt; alleen het _formaat_ van de bron-CSV verandert.

## 3. Architectuur

### Nieuwe componenten

| Pad | Doel |
|---|---|
| `oeren/` (top-level, gitignored) | Kopie van `validatie_samenwijzer/oeren/`. Bevat per instelling een sub-folder met `.md` bestanden. |
| `data/02-prepared/oeren.db` (gitignored) | SQLite-catalog van instellingen, OER-documenten en kerntaken. |
| `src/samenwijzer/oer_store.py` | DB-init en queries. Stijl van `outreach_store.py`. |
| `src/samenwijzer/oer_parsing.py` | Bestandsnaam-parser + kerntaak-extractie. Eenmalige kopie uit `validatie_samenwijzer/src/validatie_samenwijzer/ingest.py`, met header `# Synced from validatie_samenwijzer:ingest.py @ <commit>`. |
| `scripts/build_oer_catalog.py` | Eenmalig: scant `oeren/`, populeert `oeren.db`. |
| `scripts/generate_synthetisch_data.py` | Vervanger van `generate_berend_data.py`. Produceert `data/01-raw/synthetisch/studenten.csv`. |
| `scripts/synthetisch_opleidingen.json` | Handmatig gecureerde lijst van 15 opleidingen. |

### Hernoemd

| Oud | Nieuw |
|---|---|
| `data/01-raw/berend/` | `data/01-raw/synthetisch/` |
| `prepare.load_berend_csv()` | `prepare.load_synthetisch_csv()` |
| `scripts/generate_berend_data.py` | `scripts/generate_synthetisch_data.py` |
| Alle "berend"-vermeldingen in code/tests/docs | "synthetisch" |

### Verwijderd

| Pad | Reden |
|---|---|
| `data/01-raw/berend/oer_kerntaken.json` | Kerntaken nu in `oeren.db` |
| `prepare._CREBO_MAP` | Crebos komen nu uit `oeren.db` |
| Sector-niveau opleidingen ("Zorg & Welzijn", "Economie", "Techniek", "Overig") | Vervangen door specifieke opleidingen |

### Onaangeroerd

- `coach.py`, `tutor.py`, `welzijn.py`, `whatsapp.py`, `outreach.py`, `outreach_store.py`, `whatsapp_store.py`, `wellbeing.py`
- Alle `app/`-pagina's
- `validatie_samenwijzer/` (apart project, eigen test suite)

## 4. Data-model

### `oeren.db` schema

```sql
CREATE TABLE instellingen (
  id           INTEGER PRIMARY KEY,
  naam         TEXT UNIQUE NOT NULL,    -- "rijn_ijssel"  (snake_case folder-naam)
  display_naam TEXT NOT NULL            -- "Rijn IJssel"
);

CREATE TABLE oer_documenten (
  id            INTEGER PRIMARY KEY,
  instelling_id INTEGER NOT NULL,
  opleiding     TEXT NOT NULL,          -- "Verzorgende IG"
  crebo         TEXT NOT NULL,          -- "25655"
  cohort        TEXT NOT NULL,          -- "2025"
  leerweg       TEXT NOT NULL,          -- "BOL" of "BBL"
  niveau        INTEGER,                -- 2/3/4 of NULL (onbekend; alleen vereist voor de 15 gecureerde opleidingen)
  bestandspad   TEXT NOT NULL,          -- "oeren/rijn_ijssel_oer/25655_BOL_2025__verzorgende-ig.md"
  FOREIGN KEY (instelling_id) REFERENCES instellingen(id),
  UNIQUE (instelling_id, crebo, leerweg, cohort)
);

CREATE TABLE kerntaken (
  id              INTEGER PRIMARY KEY,
  oer_id          INTEGER NOT NULL,
  code            TEXT NOT NULL,        -- "B1-K1" of "kt_1"
  naam            TEXT NOT NULL,        -- "Bieden van zorg en ondersteuning"
  type            TEXT NOT NULL,        -- "kerntaak" | "werkproces"
  parent_code     TEXT,                 -- voor werkprocessen: bovenliggende kerntaak-code
  volgorde        INTEGER,
  FOREIGN KEY (oer_id) REFERENCES oer_documenten(id)
);
```

### `studenten.csv` (synthetisch)

Behoudt alle research-kolommen voor toekomstige studiesucces-voorspelling. Wijzigingen t.o.v. de huidige Berend-CSV:

| Kolom | Wijziging |
|---|---|
| `Opleiding` | Wordt opleidingsspecifiek (uit `oeren.db.oer_documenten.opleiding`) |
| `Instelling` | **Nieuw**, string-kolom (Aeres / DaVinci / RijnIJssel / Talland / Utrecht). Uitbreidbaar zonder schema-wijziging als er instellingen bijkomen. |
| `ROCMondriaan` | **Verwijderd** (vervangen door `Instelling`-kolom) |
| `Klas` | Behouden als `<niveau><cohort-letter>` (bv. "3A" voor niveau 3, cohort 2024). Niveau komt uit OER, cohort wordt jaartal-letter geconverteerd. |

Onaangeroerd:
- Alle `VooroplNiveau_*` (one-hots)
- Alle sector-one-hots: `Economie`, `Landbouw`, `Techniek`, `DSV`, `Zorgenwelzijn`, `Anders`
- `Aanmel_aantal`, `max1studie`, `Richting_nan`, `Dropout`
- `Studentnummer`, `Naam`, `Mentor`, `StudentAge`, `StudentGender`
- `absence_unauthorized`, `absence_authorized`

## 5. Generatie-pipeline

### Stap 1 — `scripts/build_oer_catalog.py`

Eenmalig (her)opbouwen van `oeren.db`:

```
voor elke <instelling>_oeren/ folder in oeren/:
  voeg instelling toe aan instellingen-tabel
  voor elke *.md in de folder:
    parseer bestandsnaam → crebo, leerweg, cohort  (oer_parsing.parseer_bestandsnaam)
    extraheer opleidingsnaam → heuristiek (filter digits/BOL/BBL/OER/etc., title-case, max 4 woorden)
    bepaal niveau:
      1) suffix N2/N3/N4 in bestandsnaam → gebruik dat
      2) anders: regex op markdown-tekst ("niveau 2", "MBO niveau 3")
      3) anders: NULL → wordt later gecureerd voor de 15 gekozen opleidingen
    voeg toe aan oer_documenten
    extraheer_kerntaken(markdown_tekst) → vul kerntaken-tabel
```

Resultaat: `oeren.db` met alle ~776 OERs, ~5 instellingen, ~5000 kerntaken.

### Stap 2 — Opleidingen kiezen (handmatig)

Query op `oeren.db`:
```sql
SELECT opleiding,
       COUNT(DISTINCT instelling_id) AS aantal_instellingen,
       COUNT(*) AS aantal_oers
FROM oer_documenten
WHERE niveau IS NOT NULL
GROUP BY opleiding
HAVING aantal_instellingen >= 2
ORDER BY aantal_oers DESC;
```

Curate **15 opleidingen** in `scripts/synthetisch_opleidingen.json`:
- Schone opleidingsnaam (heuristiek leverde iets bruikbaars op)
- Voorkomen in ≥ 2 instellingen
- Spreiding over sectoren (zorg, techniek, economie, dienstverlening, …)

Voorbeeld:
```json
[
  {"opleiding": "Verzorgende IG", "sector": "Zorgenwelzijn", "niveau": 3},
  {"opleiding": "Mediamaker", "sector": "Anders", "niveau": 4},
  ...
]
```

`sector` wordt later gebruikt om de sector-one-hots te zetten.

### Stap 3 — `scripts/generate_synthetisch_data.py`

Produceert `data/01-raw/synthetisch/studenten.csv`:

```
laad synthetisch_opleidingen.json (15 opleidingen)
laad oeren.db

# Verdeling: 1000 studenten / 5 instellingen = 200 per instelling
voor elke instelling (5):
  bepaal welke opleidingen hier beschikbaar zijn (subset van de 15)
  verdeel 200 studenten gelijkmatig over die opleidingen

# Mentoren: 50 totaal (gemiddeld 20 studenten per mentor)
voor elke instelling: 10 mentoren (NL-namen-pool, deterministisch geseed)
voor elke student: ken willekeurig één mentor uit eigen instelling toe

# Per student: vul de research-features synthetisch in
  StudentAge: 16–22, gewogen rond 18
  StudentGender: 0/1 (random)
  VooroplNiveau_*: één 1, rest 0  (random gewogen)
  Sector-one-hots: 1 voor de sector van de opleiding, rest 0
  Aanmel_aantal: 1.0–3.0
  max1studie, Richting_nan: realistische waarden
  Dropout: 0/1, gecorreleerd met absence_unauthorized
  absence_unauthorized: 0–60, exp-verdeling
  absence_authorized: 0–40
  Naam: NL-namen-pool
  Klas: niveau-cijfer + cohort-letter (bv. "3A" voor niveau 3 cohort 2024)
```

Reproduceerbaar via `random.seed(42)`.

### Stap 4 — Validatie (in het script)

Vóór wegschrijven harde check:
- Exact 1000 rijen
- Exact 5 verschillende instellingen, elk met 200 studenten
- Exact 50 mentoren, elk met 18–22 studenten
- Voor elke (Instelling, crebo, leerweg, cohort): bestaat als rij in `oeren.db.oer_documenten`

Bij faal: hard error met duidelijke melding (welke regel, welke check).

## 6. Aanpassingen aan bestaande code

### `prepare.py`

- `load_berend_csv()` → `load_synthetisch_csv()`
- `_CREBO_MAP` verwijderd (crebo komt nu rechtstreeks uit de CSV)
- `_voeg_kt_wp_scores_toe()`:
  - Gebruikt `oeren.db` i.p.v. `oer_kerntaken.json`
  - Lookup: `(opleiding, niveau, cohort)` → kerntaken via `oer_store.get_kerntaken_voor_opleiding()`
- Path-default: `data/01-raw/synthetisch/studenten.csv`

### `analyze.py`

- `_OER_PAD` weg (verwees naar `oer_kerntaken.json`)
- `_oer_label(opleiding, kolom)`: query op `oeren.db.kerntaken` i.p.v. JSON-lookup

### Tests

| Bestand | Wijziging |
|---|---|
| `tests/test_oer_store.py` (nieuw) | DB-init, queries, unique-constraint |
| `tests/test_synthetisch_data.py` (nieuw) | 1000 rijen, 5 instellingen × 200, 50 mentoren × ~20, alle (instelling, crebo, leerweg, cohort) bestaan in `oeren.db` |
| `tests/test_prepare.py` | Fixtures verwijzen naar `synthetisch/`, `load_synthetisch_csv()`, kt/wp-scores via DB-query |
| `tests/test_analyze.py` | `_oer_label()` leest uit DB |
| `tests/test_architecture.py` | Sweep-check: geen string "berend" meer in code |

## 7. Migratie-stappen (uitvoervolgorde)

1. Kopieer `validatie_samenwijzer/oeren/` → `samenwijzer/oeren/` (handmatig, eenmalig)
2. Voeg `oeren/` en `data/02-prepared/oeren.db` toe aan `.gitignore`
3. Schrijf `src/samenwijzer/oer_parsing.py` (kopie van validatie's `parseer_bestandsnaam` en `extraheer_kerntaken`, met sync-header)
4. Schrijf `src/samenwijzer/oer_store.py` + `tests/test_oer_store.py` — TDD
5. Schrijf `scripts/build_oer_catalog.py`
6. Run script → `oeren.db` lokaal gevuld
7. Curate handmatig `scripts/synthetisch_opleidingen.json` (15 opleidingen)
8. Schrijf `scripts/generate_synthetisch_data.py` + `tests/test_synthetisch_data.py` — TDD
9. Run → produceer `data/01-raw/synthetisch/studenten.csv`
10. Update `prepare.py`: rename + DB-lookup in `_voeg_kt_wp_scores_toe`
11. Update `analyze.py`: `_oer_label()` via DB
12. Update tests: `test_prepare.py`, `test_analyze.py`
13. Verwijder `data/01-raw/berend/`
14. Update CLAUDE.md, ARCHITECTURE.md en evt. README
15. Sweep: `grep -ri berend src/ app/ tests/ scripts/ docs/ data/` moet 0 hits geven
16. Run `uv run pytest && uv run ruff check src/ app/`

## 8. Risico's & mitigaties

| Risico | Mitigatie |
|---|---|
| Heuristiek voor opleidingsnaam levert onbruikbare namen | Curate-stap (stap 7): alleen 15 opleidingen die schone namen hebben overleven |
| Niveau-extractie faalt voor de 15 gekozen opleidingen | Handmatig invullen in `synthetisch_opleidingen.json`; `oer_documenten.niveau` mag NULL zijn voor niet-gekozen opleidingen |
| Sync-drift tussen `samenwijzer/oer_parsing.py` en `validatie_samenwijzer/ingest.py` | Sync-header in oer_parsing.py vermeldt commit; bij volgende wijziging bewuste merge of fork |
| Studenten-aantal niet exact 200 per instelling als opleidingen ongelijk verdeeld zijn | Generator gebruikt round-robin met afronding-correctie; validatiestap faalt hard bij afwijking |
| `oer_kerntaken.json` weg, prepare.py kan niet meer kt/wp-scores zetten | Tests dekken `_voeg_kt_wp_scores_toe()`-pad; CI faalt als er regressie is |

## 9. Volgende stap

Na implementatie van B3a volgt **sub-project B**: OER-markdown-context toevoegen aan `coach.py` en `tutor.py`. B leest uit dezelfde `oeren.db` en `oeren/`-folder die B3a oplevert.

Daarna **sub-project A**: vector-DB verwijderen uit `validatie_samenwijzer` (los van samenwijzer).
