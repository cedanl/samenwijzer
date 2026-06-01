# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Werkstijl: vraag bij twijfel vóór je begint; lever de kleinste oplossing die het probleem afdekt; raak alleen aan wat de taak vereist (geen ongevraagde refactors van aangrenzende code); definieer per taak een verifieerbaar success-criterium. Volledige agent-regels: `AGENTS.md`.

## Overview

Python/Streamlit app die AI en Data gebruikt om MBO-studenten te ondersteunen bij het leren.
Doelgroepen: studenten (voortgang, tutor, leercoach, welzijnscheck) en docenten (groepsoverzicht,
outreach, campagnebeheer, peer matching).

CEDA technical standards: https://github.com/cedanl/.github/tree/main/standards/README.md.

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
`CLAUDE.md` en poort 8503 — draai `uv`, `pytest` en `ruff` altijd vanuit de juiste projectroot.

## Environment

`.env` in projectroot. `ANTHROPIC_API_KEY` is verplicht voor alle AI-functies. Optioneel:
SMTP (outreach-mail), Twilio (`TWILIO_*`, `WHATSAPP_ENCRYPT_KEY` voor Fernet-encryptie).
Zie `README.md` voor de volledige lijst.

## Architecture

Source-package leeft in `src/samenwijzer/` (importeerbaar als `samenwijzer.*`). UI in `app/`,
scripts in `scripts/`, tests in `tests/`.

Dependency-richting **strikt**: `prepare → transform → analyze → feature-laag → app`.
Feature-laag (afgedwongen in `tests/test_architecture.py`) = `visualize, coach, tutor, welzijn,
wellbeing, outreach, outreach_store, whatsapp, whatsapp_store, auth, styles`. Nooit omgekeerd.
`groei.py` (groeidossier-businesslogic) staat naast die feature-laag en leunt uitsluitend op
`groei_store.py` + stdlib/pandas — geen AI- of app-imports. UI-laag (`app/`) bevat geen
business logic; pagina-refactors (bv. PR #95–#99) verplaatsten BSA-percentage, effectiviteit-
aggregatie en spinneweb-figuren naar respectievelijk `outreach.py`, `visualize.py` en
`wellbeing.py`. Laagovertredingen breken CI, niet alleen conventie.

**AI-isolatie**: alle Anthropic-calls zitten in `tutor.py`, `coach.py`, `outreach.py`, `welzijn.py`,
`whatsapp.py`. Maak de client **altijd** via `_ai._client()` — nooit een eigen `anthropic.Anthropic()`
instantiëren, en nooit `anthropic` direct importeren in `app/`.

**Sessiedata**: `st.session_state["df"]` wordt eenmalig geladen op de startpagina via
`prepare.load_synthetisch_csv()` + `transform.transform_student_data()`. Pagina's lezen daaruit —
nooit opnieuw laden.

**SQLite-isolatie**: schrijfbewerkingen naar `outreach.db` lopen uitsluitend via `outreach_store.py`,
naar `whatsapp.db` via `whatsapp_store.py`, naar `groei.db` (groeidossier) via `groei_store.py`.
Nooit raw SQL in `app/`. Alle drie DBs zijn gitignored. De read-only OER-catalog `oeren.db`
(eveneens gitignored) wordt uitsluitend gelezen via `oer_store.py` en alleen geschreven door
`scripts/build_oer_catalog.py` — herbouw lokaal als hij ontbreekt.

**Bewijsstukken**: file-uploads in het groeidossier lopen via `bewijsstuk_store.py` (filesystem-IO
onder `data/bewijsstukken/<studentnummer>/`, max 10 MB, alleen pdf/jpg/jpeg/png/docx/xlsx). Validatie
van studentnummer en extensie gebeurt daar — `app/` doet geen directe filesystem-writes.

**Groeidossier-goedkeuring**: elk werkproces in `groei_actueel` heeft een status
(`concept → ingediend → goedgekeurd / teruggegeven`). De student dient in (`dien_in`), de mentor
keurt goed (`keur_goed`) of geeft terug met verbeterfeedback (`geef_terug`). **Alleen
`goedgekeurde_score` telt mee**: `groei.overlay_self_scores()` legt uitsluitend goedgekeurde scores
over `df` en herberekent kt-scores, `voortgang` én de `risico`-vlag (via `transform._bereken_risico`).
Concept/ingediend tellen nooit mee; bewerken van een goedgekeurd werkproces zet het terug naar
concept terwijl de oude goedgekeurde score blijft tellen tot heraccordering. De store dwingt de
statusovergangen af via SQL-guards. Na een mentor-actie wordt `st.session_state["df"]` ververst zodat
voortgang/risico meteen meebewegen.

Volledige laagbeschrijving en module-rollen: zie `ARCHITECTURE.md` en `AGENTS.md`.

## UI- & paginaconventies

Geen sidebar — volledig verborgen via `.streamlit/config.toml` + CSS. Elke pagina:
1. `st.set_page_config(...)`
2. `inject_theme(rol)` (uit `styles.py`) — kiest student- of docent-thema op basis van
   `st.session_state["rol"]`. Bij ontbrekende rol (login of toegangsfout) `inject_theme(None)`.
3. `render_nav()` direct daarna (vaste header, `position:fixed`)
4. `render_footer()` onderaan
5. AI-calls > ~1 seconde in `st.spinner()`, met try/except voor `anthropic.APITimeoutError` (timeout = 30s)
6. Streaming: gebruik `st.write_stream()` en sla het resultaat op in `st.session_state` zodat
   re-renders de API-call niet opnieuw triggeren

Uitloggen verloopt via `app/pages/uitloggen.py` (sessie wissen + redirect naar `/`).

### Dual-theme design-systeem

`styles.py` exporteert twee thema's bovenop één gedeeld fundament:

* **student** — donker (#0F0F12 + #1A1A1F) met lime-accent (#A8FF60) en coral-alert (#FF5E3A).
  Mobile-first, energiek, pill-vormige badges en knoppen.
* **docent** — paper (#F0EBE1 + #FAF5EC) met sage-accent (#6F8265) en rust-alert (#B04A1A).
  Desktop-georiënteerd, atelier-rustig, rechthoekige chips en knoppen.

Gedeeld: Cabinet Grotesk display, Satoshi body, JetBrains Mono labels, spacing-scale, motion-curves.

**Component-helpers** in `styles.py` (gebruik die ipv inline HTML):

| Helper | Doel |
|---|---|
| `inject_theme(rol)` | Base + thema-CSS injecteren |
| `hero(naam, meta, badges=[])` | Hero-blok bovenaan pagina |
| `stat_card(label, value, *, value_sub, delta, delta_negative, sub, progress, alert_ring)` | Stat-card met optionele inline progress-ring |
| `badge(kind, text)` | HTML-string voor inline gebruik (in `st.markdown`) |
| `alert(text, level)` | Inline alert-balk (info/warning/urgent) |
| `section_label(text, *, warning)` | Mono-uppercase label |
| `action_tile(icon, titel, sub, page, *, key)` | Klikbare home-tegel (kaart + button + switch_page) |

Inline `st.markdown("<p style='...'>")` voor onderdelen die een helper hebben is niet
toegestaan — gebruik de helper zodat beide thema's correct meebewegen.

## Auth & toegangsbeheer

Login via `app/main.py`. Wachtwoord voor student én docent: **Welkom123** (SHA-256 gehashed).

Test-accounts (10 studenten, 10 mentoren, verspreid over 4 instellingen en risicocategorieën):
zie `gebruikers.txt` in de root. Daar staan de actuele studentnummers, mentor-namen en hun
voortgangsprofielen — gebruik die voor UI-tests in plaats van willekeurige IDs.

**UI-smoke-test verplicht** bij wijzigingen aan pagina's, navigatie, sessie-state of file-paths:
pytest groen ≠ feature werkt. Start de app (`uv run streamlit run app/main.py`), log in via
`chrome-devtools-mcp` met een account uit `gebruikers.txt` dat het gewijzigde scenario raakt
(bv. risico-student voor outreach, mentor voor groepsoverzicht) en doorloop de feature voordat
je "klaar" claimt.

`st.session_state` na login: `rol` ∈ {`"student"`, `"docent"`}, `df`, plus `studentnummer`
(student) of `mentor_naam` (docent).

**Docent-only pagina**: roep `auth.vereist_docent()` aan vlak na CSS-injectie, gevolgd door
`auth.mentor_filter(df)` voor de eigen-studenten-subset.
**Student-only pagina**: check `st.session_state.get("rol") == "student"` met `st.stop()` bij afwijking.

## Dataset & OER

Synthetische dataset (1000 studenten, seed=42, 4 instellingen × ~250 studenten,
~12-13 mentoren elk; Aeres MBO is uitgesloten omdat de geïndexeerde Aeres-OERs landbouw-specifieke
opleidingen betreffen zonder overlap met de gecureerde 14 generieke opleidingen). Bron-CSV:
`data/01-raw/synthetisch/studenten.csv`.

Per student worden via `prepare._voeg_kt_wp_scores_toe()` synthetische scores toegevoegd voor
`kt_1`, `kt_2` (kerntaken, 0–100, gecorreleerd met voortgang) en `wp_1_1`–`wp_2_3` (werkprocessen).
Studenten zonder kt_3/wp_3_x in hun opleiding krijgen NaN; analyse- en labelfuncties filteren NaN weg.

**OER-catalog** (`data/02-prepared/oeren.db`, gevuld door `scripts/build_oer_catalog.py`):
SQLite met `instellingen`, `oer_documenten`, `kerntaken`. Lookup-prioriteit in `analyze._oer_label()`
en `prepare`: **crebo** (cross-instelling, robuust) → opleidingsnaam (legacy). `oer_kerntaken.json`
is uitgefaseerd; `scripts/oer_kerntaken_fallback.json` bevat gecureerde kerntaken voor crebos
zonder parsebare kwalificatiestructuur (bv. crebo 25736).

`oer_context.haal_oer_context_op(student_row)` levert OER-tekst als context aan `tutor.py` en
`coach.py`.

**Data dictionary**: `src/samenwijzer/metadata/data_dictionary.csv` beschrijft de kolommen van
de synthetische dataset — raadpleeg dit bij twijfel over veldbetekenis (is een tracked package-asset,
geen gegenereerde data).

**OER-parsing** (`oer_parsing.py`): regex-helpers voor bestandsnaam → crebo/leerweg/jaar,
kerntaken, opleidingsnaam en niveau. Bewust **gesynchroniseerd** uit het `validatie_samenwijzer`-
subproject (`src/validatie_samenwijzer/ingest.py`) — houd functioneel gelijk; wijzig hier alleen
samen met de bron, niet los.

## Welzijn & gevoeligheid

Twee aparte modules: `welzijn.py` (student self-assessment via webapp; 5 hulpcategorieën, 3 urgentieniveaus)
en `wellbeing.py` (CSV-gebaseerde signalering voor groepsoverzicht). Toon vrije-tekst studentreacties
**nooit** in geaggregeerde dashboards — alleen de toegewezen mentor ziet individuele check-details.
Urgentie 3 vereist directe mentor-actie.

## WhatsApp lokaal testen

Twilio vereist een publieke URL. Drie terminals:
```
uv run streamlit run app/main.py
uv run uvicorn app.webhook:app --host 0.0.0.0 --port 8502
ngrok http 8502
```
Zet de ngrok-URL op **Twilio Console → Messaging → Sandbox → "When a message comes in"** →
`https://<ngrok-url>/webhook/whatsapp`.

Telefoonnummers worden Fernet-versleuteld opgeslagen; gesprekshistorie max 30 dagen bewaren (AVG).
De retentie wordt **lazy** afgedwongen: `verwerk_inkomend_bericht` roept bij elk inkomend bericht
`whatsapp.verwijder_verouderde_gesprekshistorie(peildatum=ontvangen_op)` aan, die `whatsapp_sessies`
(op `gestart_op`) én de `whatsapp_context_*.json`-bestanden (op mtime) ouder dan 30 dagen verwijdert.
Telefoonregistraties zijn opt-in-toestemming, geen gesprekshistorie, en blijven bewaard.

`scheduler.py` is het entry point voor de wekelijkse check-in cron (GitHub Actions, ma 08:00):
```bash
uv run python -m samenwijzer.scheduler             # echt versturen
DRY_RUN=true uv run python -m samenwijzer.scheduler  # alleen loggen
```

## Kennisbank

| Onderwerp | Bestand |
|---|---|
| Lokale opstart (alle services) | `INSTRUCTIONS.md` |
| Architectuur & module-rollen | `ARCHITECTURE.md`, `AGENTS.md` |
| Productvision & features | `docs/PRODUCT_SENSE.md` |
| Frontend- & UI-conventies | `docs/FRONTEND.md` |
| Ontwerpbeslissingen | `docs/designs/index.md` |
| Uitvoeringsplannen | `docs/plans/active/`, `docs/plans/completed/` |
| Product specs | `docs/specs/index.md` |
| Kwaliteitsscores | `docs/QUALITY_SCORE.md` |
| Beveiliging | `docs/SECURITY.md` |
| Betrouwbaarheid | `docs/RELIABILITY.md` |
| Tech debt | `docs/plans/tech-debt-tracker.md` |
| Test-accounts | `gebruikers.txt` |
| OER-chat subproject (poort 8503) | `validatie_samenwijzer/` — Streamlit-app voor conversationeel chatten met de eigen OER via volledige Claude-documentcontext, met landelijke kwalificatiedossiers én een skills-taxonomie (CompetentNL/ESCO) als aanvullende bronnen; afgeleide bronnen worden automatisch gereconcilieerd bij oeren-wijzigingen (eigen `CLAUDE.md`) |
| Presentatie (Slidev, poort 3030) | `validatie_samenwijzer/presentatie/` — zelfstandige CEDA/Npuls-deck over vector store → full-document context; `./start.sh` |

**Doc-locatie-conventie** (overschrijft skill-defaults): specs horen in `docs/specs/`, plannen in
`docs/plans/{active,completed}/`, ontwerpbeslissingen in `docs/designs/`. Schrijf **niet** naar
`docs/superpowers/` — die map is bij de folderstructuur-opschoning opgeheven. De brainstorming- en
writing-plans-skills defaulten naar `docs/superpowers/`; honoreer hier deze conventie als override.
In het `validatie_samenwijzer/`-subproject geldt `docs/plans/` voor zowel specs als plannen.

## Agent rules (samenvatting van AGENTS.md)

1. No handwritten code — every line is agent-generated.
2. No business logic in `app/`.
3. Validate external inputs at boundaries; trust internal types.
4. Structured logging only; no bare `print()` in production. Geen PII (namen, IDs) op INFO of hoger.
5. Never push directly to `main` — open een PR via `gh pr create`.
