# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.


## Overview

Python/Streamlit app die AI en Data gebruikt om MBO-studenten te ondersteunen bij het leren.
Doelgroepen: studenten (voortgang, tutor, leercoach, welzijnscheck) en docenten (groepsoverzicht,
outreach, campagnebeheer, peer matching).

CEDA technical standards: https://github.com/cedanl/.github/tree/main/standards/README.md.

## Tech & tooling

Python 3.13, Streamlit, pandas, Anthropic SDK. Package manager: `uv`. Type checker: `ty`.
Linter/formatter: `ruff` (line-length 100, selectie `E,F,I,N,W,UP`; HTML-strings in `styles.py`,
`app/main.py` en `app/pages/*.py` zijn vrijgesteld van E501).

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

Dependency-richting **strikt**: `prepare → transform → analyze → visualize/coach/tutor/welzijn/groei → app`.
Nooit omgekeerd. `groei.py` (groeidossier-businesslogic) leunt uitsluitend op `groei_store.py` +
stdlib/pandas — geen AI- of app-imports (afgedwongen in `tests/test_architecture.py`). UI-laag (`app/`) bevat geen business logic. De laagregel wordt afgedwongen door
`tests/test_architecture.py` — laagovertredingen breken CI, niet alleen conventie.

**AI-isolatie**: alle Anthropic-calls zitten in `tutor.py`, `coach.py`, `outreach.py`, `welzijn.py`,
`whatsapp.py`. Maak de client **altijd** via `_ai._client()` — nooit een eigen `anthropic.Anthropic()`
instantiëren, en nooit `anthropic` direct importeren in `app/`.

**Sessiedata**: `st.session_state["df"]` wordt eenmalig geladen op de startpagina via
`prepare.load_synthetisch_csv()` + `transform.transform_student_data()`. Pagina's lezen daaruit —
nooit opnieuw laden.

**SQLite-isolatie**: schrijfbewerkingen naar `outreach.db` lopen uitsluitend via `outreach_store.py`,
naar `whatsapp.db` via `whatsapp_store.py`, naar `groei.db` (groeidossier) via `groei_store.py`.
Nooit raw SQL in `app/`. Alle drie DBs zijn gitignored.

**Bewijsstukken**: file-uploads in het groeidossier lopen via `bewijsstuk_store.py` (filesystem-IO
onder `data/bewijsstukken/<studentnummer>/`, max 10 MB, alleen pdf/jpg/jpeg/png/docx/xlsx). Validatie
van studentnummer en extensie gebeurt daar — `app/` doet geen directe filesystem-writes.

Volledige laagbeschrijving en module-rollen: zie `ARCHITECTURE.md` en `AGENTS.md`.

## UI- & paginaconventies

Geen sidebar — volledig verborgen via `.streamlit/config.toml` + CSS. Elke pagina:
1. `st.set_page_config(...)`
2. `st.markdown(CSS, unsafe_allow_html=True)` (uit `styles.py`)
3. `render_nav()` direct daarna (vaste header, `position:fixed`)
4. `render_footer()` onderaan
5. AI-calls > ~1 seconde in `st.spinner()`, met try/except voor `anthropic.APITimeoutError` (timeout = 30s)
6. Streaming: gebruik `st.write_stream()` en sla het resultaat op in `st.session_state` zodat
   re-renders de API-call niet opnieuw triggeren

Uitloggen verloopt via `app/pages/uitloggen.py` (sessie wissen + redirect naar `/`).

## Auth & toegangsbeheer

Login via `app/main.py`. Wachtwoord voor student én docent: **Welkom123** (SHA-256 gehashed).

Test-accounts (10 studenten, 10 mentoren, verspreid over 4 instellingen en risicocategorieën):
zie `gebruikers.txt` in de root. Daar staan de actuele studentnummers, mentor-namen en hun
voortgangsprofielen — gebruik die voor UI-tests in plaats van willekeurige IDs.

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
| OER-chat subproject (poort 8503) | `validatie_samenwijzer/` — Streamlit-app voor conversationeel chatten met de eigen OER via volledige Claude-documentcontext (eigen `CLAUDE.md`) |
| Presentatie (Slidev, poort 3030) | `validatie_samenwijzer/presentatie/` — zelfstandige CEDA/Npuls-deck over vector store → full-document context; `./start.sh` |

## Agent rules (samenvatting van AGENTS.md)

1. No handwritten code — every line is agent-generated.
2. No business logic in `app/`.
3. Validate external inputs at boundaries; trust internal types.
4. Structured logging only; no bare `print()` in production. Geen PII (namen, IDs) op INFO of hoger.
5. Never push directly to `main` — open een PR via `gh pr create`.
