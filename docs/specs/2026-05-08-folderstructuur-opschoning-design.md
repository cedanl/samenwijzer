# Folderstructuur-opschoning — design

**Datum:** 2026-05-08
**Scope:** Folder-only herorganisatie van `samenwijzer/` (root) en `validatie_samenwijzer/` (subproject). Geen module-shuffles binnen `src/`. Geen verwijdering van legacy data of dode mappen.

## Doel

De mappenstructuur platter en beter benoembaar maken zodat overzicht in de IDE/file-explorer behouden blijft naarmate het project groeit. Inspiratie: Cookiecutter Data Science / Dave Ebbelaar's productie-templates (vlakke `src/`, korte mapnamen, één bron-van-waarheid voor data).

## Beslissingen

### §1 Top-level mappen — ongewijzigd

```
samenwijzer/
├── app/                       # Streamlit UI
├── data/                      # datasets + DBs (intern: zie §2)
├── docs/                      # documentatie (intern: zie §3)
├── oeren/                     # raw OER-PDFs (single source voor beide subprojecten)
├── scripts/                   # build/generate
├── src/samenwijzer/           # Python package (18 .py + metadata/)
├── tests/
└── validatie_samenwijzer/     # zelfstandig subproject (intern: zie §4)
```

Deze 8 namen zijn al vlak en betekenisvol. Geen wijziging.

### §2 `data/` — geen wijziging (Optie A)

```
data/
├── 01-raw/
│   ├── berend/
│   ├── demo/
│   └── synthetisch/
├── 02-prepared/
└── 03-output/
```

**Bewuste keuze om de `01-`/`02-`/`03-`-prefixen te behouden.**

Reden: deze paden worden hardcoded gerefereerd in ~20 source-bestanden
(`prepare.py`, `analyze.py`, `whatsapp_store.py`, `outreach_store.py`,
`oer_context.py`, `oer_store.py`, `scheduler.py`, `whatsapp.py`,
`webhook.py`, `app/main.py`, `app/pages/2_groepsoverzicht.py`,
`scripts/build_oer_catalog.py`, `scripts/generate_synthetisch_*.py`,
`app/config.toml`). Hernoemen valt buiten de scope "alleen folders, geen
code-aanpassingen".

### §3 `docs/` — 6 sub-mappen consolideren naar 3

**Huidig:**
```
docs/
├── design-docs/
├── exec-plans/
│   ├── active/
│   └── completed/
├── product-specs/
└── superpowers/
    ├── plans/
    └── specs/
```

**Doel:**
```
docs/
├── designs/         # samenvoeging design-docs/ + design-deel superpowers/
├── plans/
│   ├── active/      # samengevoegd met superpowers/plans (open plannen)
│   └── completed/   # samengevoegd met superpowers/plans (afgeronde)
└── specs/           # samenvoeging product-specs/ + superpowers/specs/
```

**Per-bestand-allocatie**: bij de migratie inhoudelijk per bestand bepalen of
het een design (besluit/architectuur), plan (uitvoeringsstappen) of spec
(requirements/feature-beschrijving) is. Niet blind op basis van originele
parent-map verplaatsen.

**Configuratie van de superpowers-skill**: na de migratie wijst de skill naar
`docs/specs/` voor nieuwe specs en `docs/plans/active/` voor nieuwe plannen.
De map `docs/superpowers/` verdwijnt volledig.

**Code-impact**: nul — docs worden niet geïmporteerd. Verwijzingen in
`README.md`, `CLAUDE.md`, `AGENTS.md`, `ARCHITECTURE.md` updaten.

### §4 `validatie_samenwijzer/` — 8 top-level → 5

**Huidig:**
```
validatie_samenwijzer/
├── app/
├── data/
├── oeren/                     # DUBBEL met root-oeren/
├── scripts/                   # 1 file: convert_oers_markdown.py
├── seed/                      # 3 files: bulk_seed.py, rebuild_students.py, seed.py
├── src/validatie_samenwijzer/
├── tests/
└── tools/                     # 2 files: rename_oers.py, verwerk_oers.sh
```

**Doel:**
```
validatie_samenwijzer/
├── app/                       # ongewijzigd
├── data/                      # ongewijzigd
├── scripts/                   # samengevoegd
│   ├── convert_oers_markdown.py
│   ├── rename_oers.py
│   ├── verwerk_oers.sh
│   ├── seed.py                # uit seed/
│   ├── seed_bulk.py           # was seed/bulk_seed.py
│   └── seed_rebuild_students.py  # was seed/rebuild_students.py
├── src/validatie_samenwijzer/
└── tests/
```

**Veranderingen:**

1. **`oeren/` opheffen.** De codebase gebruikt al `OEREN_PAD`-env-var overal
   (zie `src/validatie_samenwijzer/ingest.py`, `app/pages/2_mijn_oer.py`,
   `app/pages/5_begeleidingssessie.py`, `tools/rename_oers.py`,
   `scripts/convert_oers_markdown.py`). De default is `"oeren"`. Door
   `OEREN_PAD=../oeren` in `validatie_samenwijzer/.env` te zetten en
   `validatie_samenwijzer/.env.example` te updaten, wijst alles naar de
   root-`oeren/`. De lokale `validatie_samenwijzer/oeren/`-map kan dan
   verwijderd. Dat ontdubbelt ~tientallen MB aan PDFs en geeft één bron van
   waarheid.

2. **`seed/` opheffen, naar `scripts/`.** De drie seed-bestanden krijgen een
   `seed_`-prefix om het seed-karakter zichtbaar te houden in de platte
   `scripts/`-map (`scripts/seed.py` blijft, `bulk_seed.py` →
   `seed_bulk.py`, `rebuild_students.py` → `seed_rebuild_students.py`).

3. **`tools/` opheffen, naar `scripts/`.** Twee bestanden, geen prefix
   nodig.

4. **`pyproject.toml` `[project.scripts]`-entries** (`ingest`, `watcher`)
   wijzen al naar `src/validatie_samenwijzer/`-modules en blijven dus
   ongewijzigd.

**Risico-check geen Python-imports tussen seed/ en tools/**: bevestigd via
`grep -rn "from.*\(seed\|tools\)" validatie_samenwijzer/` — geen treffers.

## Buiten scope (expliciet niet meedoen)

- Module-shuffles binnen `src/samenwijzer/` (geen `ai/`, `data/`, `ui/`
  submappen) — dat raakt te veel imports.
- Verwijderen van legacy `data/01-raw/berend/` en `data/03-output/` (lege
  output-map) — kandidaat voor latere ronde.
- Verwijderen van `src/samenwijzer/metadata/` (bevat alleen
  `data_dictionary.csv`, geen Python-imports gevonden) — kandidaat voor
  latere ronde.
- Hernoemen van markdown-bestanden in root (`AGENTS.md`,
  `ARCHITECTURE.md`, `INSTRUCTIONS.md`).
- Hernoemen van data-mappen (`01-raw/`, `02-prepared/`, `03-output/`) — zie
  §2.

## Migratiestappen (op hoog niveau)

Detailplan in een opvolgend implementation-plan-document; hier alleen de
hoofdvolgorde:

1. **Veiligstellen**: schone werkkopie, recent commit, zorg dat
   `uv run pytest` groen is in beide projecten.
2. **§4a `oeren/`-dedup voor validatie**: `OEREN_PAD=../oeren` in
   `validatie_samenwijzer/.env` (en `.env.example`); test
   `uv run python -m validatie_samenwijzer.ingest` en de Streamlit-pagina's
   die `OEREN_PAD` gebruiken; verwijder `validatie_samenwijzer/oeren/`.
3. **§4b validatie scripts/seed/tools mergen**: `git mv` per bestand,
   prefix seed-bestanden, verwijder lege `seed/` en `tools/`. Update
   referenties in `validatie_samenwijzer/CLAUDE.md` en `README.md`.
4. **§3 docs-consolidatie**: per bestand designs/plans/specs-classificatie
   bepalen, `git mv` naar de nieuwe boom, `superpowers/`-tree leeg en
   verwijder. Update verwijzingen in root-`CLAUDE.md`, `README.md`,
   `AGENTS.md`, `ARCHITECTURE.md`.
5. **Verificatie**: `uv run pytest` in beide projecten + `uv run streamlit
   run app/main.py` voor beide projecten doorklikken (login,
   pagina-navigatie, één AI-call) zodat geen runtime-pad gebroken is.

## Acceptatiecriteria

- `validatie_samenwijzer/` heeft 5 top-level mappen (`app`, `data`,
  `scripts`, `src`, `tests`).
- `docs/` heeft 3 sub-mappen (`designs`, `plans`, `specs`); `superpowers/`
  bestaat niet meer.
- Eén `oeren/`-map (in root); validatie-tests/-pagina's werken via
  `OEREN_PAD`.
- `uv run pytest` groen in beide projecten.
- Streamlit-apps openen op poort 8501 en 8503 zonder pad-fouten.
- Geen wijziging aan source-paden in `data/01-raw|02-prepared|03-output/`.
