# CLAUDE.md

Guidance for Claude Code in deze repo. Dagelijkse essentials + harde invarianten staan hier; de
volledige laagbeschrijving en module-rollen staan in **`ARCHITECTURE.md`** + **`AGENTS.md`**,
UI-conventies in **`docs/FRONTEND.md`**, lokale opstart in **`INSTRUCTIONS.md`**.

Werkstijl: vraag bij twijfel vóór je begint; lever de kleinste oplossing die het probleem afdekt;
raak alleen aan wat de taak vereist (geen ongevraagde refactors van aangrenzende code); definieer
per taak een verifieerbaar success-criterium. Volledige agent-regels: `AGENTS.md`.

## Overview

Python/Streamlit app die AI en Data gebruikt om MBO-studenten te ondersteunen bij het leren.
Doelgroepen: studenten (voortgang, tutor, leercoach, welzijnscheck) en docenten (groepsoverzicht,
outreach, campagnebeheer, peer matching). CEDA technical standards:
https://github.com/cedanl/.github/tree/main/standards/README.md.

## Tech & tooling

Python 3.13, Streamlit, pandas, Anthropic SDK. Visualisatie: Altair + Plotly. Webhook:
FastAPI + uvicorn. Encryptie: cryptography (Fernet). Package manager: `uv`. Type checker: `ty`
(lokaal — CI gate is alleen `ruff check`, `ruff format --check` en `pytest`; draai `ty check`
zelf vóór een PR). Linter/formatter: `ruff` (line-length 100, selectie `E,F,I,N,W,UP`;
HTML-strings in `styles.py`, `app/main.py` en `app/pages/*.py` zijn vrijgesteld van E501).

**pandas, niet polars** — bewuste keuze: Altair en Streamlit verwachten pandas, en de dataset
(1000 studenten) maakt conversie nutteloos.

## Commands

```bash
uv sync                                                    # Install
uv run streamlit run app/main.py                           # App (poort 8501)
uv run uvicorn app.webhook:app --host 0.0.0.0 --port 8502  # WhatsApp-webhook
uv run pytest                                              # Tests + coverage
uv run pytest tests/test_analyze.py::test_leerpad_niveau   # Eén test
uv run ruff check --fix src/ app/ && uv run ruff format src/ app/
uv run ty check
uv run python scripts/build_oer_catalog.py                 # Herbouw oeren.db uit oeren/
uv run python scripts/generate_synthetisch_data.py         # Regenereer dataset (vereist oeren.db)
uv run python scripts/generate_synthetisch_welzijn.py      # Regenereer welzijn-data
```

`validatie_samenwijzer/` is een **zelfstandig subproject** met eigen `pyproject.toml`, `.venv`,
`CLAUDE.md` en poort — draai `uv`, `pytest` en `ruff` altijd vanuit de juiste projectroot.

## Deployment

De repo-root `Dockerfile` + `fly.toml` deployen **het validatie-subproject** (publieksnaam
"De digitale gids") naar Fly als app `digitale-gids` (https://digitale-gids.fly.dev, regio `ams`).
De build-context is bewust de **repo-root** omdat de data (`oeren/`, `kwalificatiedossiers/`) buiten
het subproject leeft. Deploy vanuit de repo-root:

```bash
flyctl deploy -a digitale-gids --remote-only
```

De hoofd-app (`app/main.py`) heeft geen eigen Fly-deploy. WhatsApp-check-in draait als cron via
`.github/workflows/checkin.yml` (ma 08:00, `python -m samenwijzer.scheduler`).

## Environment

`.env` in projectroot. `ANTHROPIC_API_KEY` is verplicht voor alle AI-functies. Optioneel:
SMTP (outreach-mail), Twilio (`TWILIO_*`, `WHATSAPP_ENCRYPT_KEY` voor Fernet-encryptie).
Zie `README.md` / `INSTRUCTIONS.md` voor de volledige lijst.

## Architectuur-invarianten (niet breken)

Source-package in `src/samenwijzer/`, UI in `app/`, scripts in `scripts/`, tests in `tests/`.
Volledige laagbeschrijving + module-rollen: `ARCHITECTURE.md`. De regels die een wijziging niet
mag overtreden:

- **Dependency-richting strikt**: `prepare → transform → analyze → feature-laag → app` — nooit
  omgekeerd (afgedwongen in `tests/test_architecture.py`; laagovertredingen breken CI). `groei.py`
  leunt uitsluitend op `groei_store.py` + stdlib/pandas, geen AI/app-imports.
- **Geen business logic in `app/`**; geen raw SQL in pagina's.
- **AI-isolatie**: Anthropic-calls alleen in `tutor.py`, `coach.py`, `outreach.py`, `welzijn.py`,
  `whatsapp.py`. Client **altijd** via `_ai._client()` — nooit eigen `anthropic.Anthropic()`, nooit
  `anthropic` importeren in `app/`.
- **Sessiedata**: `st.session_state["df"]` wordt eenmalig geladen op de startpagina
  (`prepare.load_synthetisch_csv()` + `transform.transform_student_data()`); pagina's lezen daaruit,
  nooit opnieuw laden.
- **SQLite-isolatie**: writes via de store-module — `outreach.db`→`outreach_store.py`,
  `whatsapp.db`→`whatsapp_store.py`, `groei.db`→`groei_store.py`. Read-only `oeren.db` alleen via
  `oer_store.py`, alleen geschreven door `scripts/build_oer_catalog.py` (herbouw lokaal als hij
  ontbreekt). Alle vier DBs gitignored.
- **Bewijsstukken**: uploads via `bewijsstuk_store.py` (filesystem onder
  `data/bewijsstukken/<studentnummer>/`, max 10 MB, alleen pdf/jpg/jpeg/png/docx/xlsx);
  studentnummer- + extensie-validatie gebeurt daar — `app/` schrijft niet direct naar filesystem.
- **Groeidossier-goedkeuring**: werkproces-status `concept → ingediend → goedgekeurd/teruggegeven`
  (`dien_in`/`keur_goed`/`geef_terug`, met SQL-guards in de store). **Alleen `goedgekeurde_score`
  telt mee**: `groei.overlay_self_scores()` legt goedgekeurde scores over `df` en herberekent
  kt-scores, `voortgang` én `risico` (`transform._bereken_risico`). Bewerken van een goedgekeurd
  werkproces zet het terug naar concept maar de oude score blijft tellen tot heraccordering. Na een
  mentor-actie wordt `st.session_state["df"]` ververst.
- **OER-parsing-sync**: `oer_parsing.py` is bewust **gesynchroniseerd** uit
  `validatie_samenwijzer/src/validatie_samenwijzer/ingest.py` — houd functioneel gelijk; wijzig hier
  alleen samen met de bron.

## UI-conventies (samenvatting)

Volledige conventies + helpers + thema-tokens: **`docs/FRONTEND.md`**. Kort: geen sidebar; elke
pagina volgt `set_page_config → inject_theme(rol) → render_nav() → render_footer()`; AI-calls >~1s in
`st.spinner()` met try/except op `anthropic.APITimeoutError` (timeout 30s); streaming via
`st.write_stream()` met resultaat in `st.session_state`. Gebruik de `styles.py`-helpers (`hero`,
`stat_card`, `badge`, `alert`, `section_label`, `action_tile`) i.p.v. inline HTML — anders bewegen de
student- (donker+lime) en docent- (paper+sage) thema's niet correct mee.

## Auth & toegangsbeheer

Login via `app/main.py`. Wachtwoord student én docent: **Welkom123** (SHA-256). `st.session_state`
na login: `rol` ∈ {`"student"`, `"docent"`}, `df`, plus `studentnummer` (student) of `mentor_naam`
(docent). Docent-only: `auth.vereist_docent()` + `auth.mentor_filter(df)`. Student-only:
`st.session_state.get("rol") == "student"` met `st.stop()` bij afwijking.

**UI-smoke-test verplicht** bij wijzigingen aan pagina's, navigatie, sessie-state of file-paths:
pytest groen ≠ feature werkt. Start de app, log in via `chrome-devtools-mcp` met een account uit
`gebruikers.txt` dat het gewijzigde scenario raakt (risico-student voor outreach, mentor voor
groepsoverzicht) en doorloop de feature voordat je "klaar" claimt.

## Dataset & OER

Synthetische dataset (1000 studenten, seed=42, 4 instellingen × ~250, ~12-13 mentoren elk; Aeres MBO
uitgesloten — geen overlap met de gecureerde 14 generieke opleidingen). Bron-CSV:
`data/01-raw/synthetisch/studenten.csv`. `prepare._voeg_kt_wp_scores_toe()` voegt synthetische
`kt_1`/`kt_2` + `wp_1_1`–`wp_2_3` toe (0–100, gecorreleerd met voortgang); ontbrekende kt_3/wp_3_x →
NaN (analyse-/labelfuncties filteren NaN weg).

**OER-catalog** (`data/02-prepared/oeren.db`, via `scripts/build_oer_catalog.py`): tabellen
`instellingen`, `oer_documenten`, `kerntaken`. Lookup-prioriteit in `analyze._oer_label()`/`prepare`:
**crebo** (robuust) → opleidingsnaam (legacy). `scripts/oer_kerntaken_fallback.json` = gecureerde
kerntaken voor crebos zonder parsebare structuur. `oer_context.haal_oer_context_op(student_row)`
levert OER-tekst aan `tutor.py`/`coach.py`. Velduitleg:
`src/samenwijzer/metadata/data_dictionary.csv` (tracked asset).

## Welzijn & privacy

Twee modules: `welzijn.py` (student self-assessment; 5 hulpcategorieën, 3 urgentieniveaus) en
`wellbeing.py` (CSV-signalering voor groepsoverzicht). Toon vrije-tekst studentreacties **nooit** in
geaggregeerde dashboards — alleen de toegewezen mentor ziet individuele check-details. Urgentie 3
vereist directe mentor-actie.

**WhatsApp/AVG**: telefoonnummers Fernet-versleuteld; gesprekshistorie **max 30 dagen** (lazy
afgedwongen — `verwerk_inkomend_bericht` → `whatsapp.verwijder_verouderde_gesprekshistorie` wist
`whatsapp_sessies` + `whatsapp_context_*.json` ouder dan 30 dagen). Telefoonregistraties (opt-in,
geen historie) blijven bewaard. Lokaal testen (ngrok/Twilio-sandbox) + scheduler: `INSTRUCTIONS.md`.

## Kennisbank

| Onderwerp | Bestand |
|---|---|
| Lokale opstart (alle services) | `INSTRUCTIONS.md` |
| Architectuur & module-rollen | `ARCHITECTURE.md`, `AGENTS.md` |
| Frontend- & UI-conventies | `docs/FRONTEND.md` |
| Productvision & features | `docs/PRODUCT_SENSE.md` |
| Ontwerpbeslissingen | `docs/designs/index.md` |
| Uitvoeringsplannen | `docs/plans/active/`, `docs/plans/completed/` |
| Product specs | `docs/specs/index.md` |
| Kwaliteit / Beveiliging / Betrouwbaarheid | `docs/QUALITY_SCORE.md`, `docs/SECURITY.md`, `docs/RELIABILITY.md` |
| Tech debt | `docs/plans/tech-debt-tracker.md` |
| Test-accounts | `gebruikers.txt` |
| OER-chat subproject | `validatie_samenwijzer/` — FastAPI-app voor conversationeel chatten met de eigen OER via volledige Claude-documentcontext (+ KD + skills-taxonomie); eigen `CLAUDE.md` + `docs/ARCHITECTURE.md` |
| Presentatie (Slidev, poort 3030) | `validatie_samenwijzer/presentatie/` — CEDA/Npuls-deck; `./start.sh` |

**Doc-locatie-conventie** (overschrijft skill-defaults): specs in `docs/specs/`, plannen in
`docs/plans/{active,completed}/`, ontwerpbeslissingen in `docs/designs/`. Schrijf **niet** naar
`docs/superpowers/` (opgeheven). In het `validatie_samenwijzer/`-subproject geldt `docs/plans/` voor
zowel specs als plannen.

## Agent rules (samenvatting van AGENTS.md)

1. No handwritten code — every line is agent-generated.
2. No business logic in `app/`.
3. Validate external inputs at boundaries; trust internal types.
4. Structured logging only; no bare `print()` in production. Geen PII (namen, IDs) op INFO of hoger.
5. Never push directly to `main` — open een PR via `gh pr create`.
