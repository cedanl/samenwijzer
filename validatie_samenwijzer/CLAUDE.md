# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Wat dit project is

Standalone Streamlit-app (`validatie_samenwijzer/`) die MBO-studenten en mentoren laat chatten met hun OER (Onderwijs- en Examenregeling) via volledige documentcontext in Claude. Leeft als subproject binnen de `samenwijzer`-monorepo maar heeft zijn eigen `pyproject.toml`, `.venv` en database.

## Commando's

Alle commando's uitvoeren vanuit `validatie_samenwijzer/`:

```bash
# App starten (poort 8503)
uv run streamlit run app/main.py

# Alle tests
uv sync --extra dev && uv run python -m pytest

# Eén test
uv run python -m pytest tests/test_ingest.py::test_parseer_bestandsnaam_davinci -v

# Lint
uv run ruff check src/ app/ seed/ tools/
uv run ruff check --fix src/ app/

# Ingestie-pipeline
uv run python -m validatie_samenwijzer.ingest --alles          # nieuw indexeren
uv run python -m validatie_samenwijzer.ingest --alles --reset  # alles herindexeren
uv run python -m validatie_samenwijzer.ingest --bestand oeren/davinci_oeren/25751BBL2025Examenplan.pdf

# Bestandswatcher (herindexeer automatisch bij wijzigingen in oeren/)
uv run python -m validatie_samenwijzer.watcher          # bewaakt oeren/ (default)
uv run python -m validatie_samenwijzer.watcher --oeren-pad /pad/naar/oeren

# Seed testdata
uv run python seed/seed.py        # 3 studenten + 2 mentoren
uv run python seed/bulk_seed.py   # 1000 studenten over alle geïndexeerde OERs

# Bestandsnamen aanvullen + indexeren (alles-in-één)
./tools/verwerk_oers.sh --preview  # droge run
./tools/verwerk_oers.sh            # hernoem + indexeer
```

## Omgeving

`.env` in `validatie_samenwijzer/`:

```
ANTHROPIC_API_KEY=sk-ant-...
DB_PATH=data/validatie.db    # default
OEREN_PAD=oeren              # default
```

## Architectuur

### Data-laag

**`db.py`** — SQLite schema en alle queries als losse functies, geen ORM. Schema: `instellingen`, `oer_documenten`, `kerntaken`, `mentoren`, `mentor_oer`, `studenten`, `student_kerntaak_scores`. Verbinding via `get_connection()` met WAL-modus en `check_same_thread=False`.

**`_db.py`** — dunne Streamlit-wrapper: `get_conn()` is `@st.cache_resource` en roept `get_connection()` + `init_db()` aan. Gebruik `_db.get_conn()` in pagina's, `db.get_connection()` in scripts en tests.

### Ingestie-pipeline (`ingest.py`)

```
bestandsnaam → parseer_bestandsnaam() → crebo/leerweg/cohort
PDF          → converteer_naar_markdown() → .md via markitdown (naast PDF opgeslagen)
bestand      → extraheer_tekst()      → tekst (pdfplumber → Tesseract OCR als < 100 tekens)
tekst        → extraheer_kerntaken()  → kerntaken/werkprocessen in SQLite
```

`parseer_bestandsnaam()` kent twee patronen:
1. Da Vinci-stijl: `25168BOL2025Examenplan.pdf` — crebo+leerweg+jaar aaneengesloten
2. Fallback: elk 5-cijferig getal als crebo, BOL/BBL en jaar los gesearcht — dekt Rijn IJssel- en Talland-bestanden

Bestanden zonder crebo in naam (Aeres, Utrecht) worden hernoemd via `tools/rename_oers.py` dat de titelpagina uitleest.

### OER-chat architectuur (`chat.py`)

- `laad_oer_tekst(pad)` — leest `.md`-broertje naast PDF → `.md` zelf → pdfplumber-fallback; max 500k tekens
- `bouw_systeem(oer_tekst, opleiding, instelling)` — assembleert systeemprompt met volledige OER
- `bouw_berichten(chat_history, vraag)` — voegt vraag toe aan gesprekshistorie
- `genereer_antwoord(client, system, berichten)` — streamt via `client.messages.stream`

OER wordt eenmalig per sessie geladen in `st.session_state.oer_systeem`.

### Sessiemodel

Login in `app/main.py`. Na login staat in `st.session_state`:

| Sleutel | Student | Mentor |
|---|---|---|
| `rol` | `"student"` | `"mentor"` |
| `oer_id` | id van hun OER | — |
| `oer_ids` | — | lijst van gekoppelde OER-ids |
| `opleiding` | naam | `"Mentor"` |
| `instelling` | display_naam | display_naam |
| `gebruiker_id` | student-id | mentor-id |

Rolbewaking: `vereist_student()` / `vereist_mentor()` bovenaan elke pagina aanroepen, direct na CSS-injectie.

### Authenticatie

Wachtwoorden opgeslagen als PBKDF2-HMAC-SHA256 (`salt_hex:hash_hex`). Legacy bare-SHA-256 hashes worden nog geaccepteerd en bij volgende login automatisch gemigreerd. Seed-wachtwoord voor alle test-accounts: **Welkom123**.

Login: studenten op studentnummer, mentoren op naam.

### Pagina's

| Bestand | Rol | Functie |
|---|---|---|
| `app/main.py` | beide | Login, sessie-initialisatie |
| `0_oer_vraag.py` | publiek | Conversationele OER-vraag zonder inlogvereiste |
| `1_oer_assistent.py` | student | Chat met eigen OER via volledige documentcontext |
| `2_mijn_oer.py` | student | Volledig OER inzien of downloaden |
| `3_mijn_voortgang.py` | student | Voortgang, BSA, scores visualiseren |
| `4_mijn_studenten.py` | mentor | Studentenlijst van eigen koppeling |
| `5_begeleidingssessie.py` | mentor | Profiel + twee tabs: OER-chat en volledig OER bekijken |

### AI-isolatie

- Anthropic (Claude): `_ai._client()` — alleen voor streaming chat in `chat.py`
- Nooit clients direct instantiëren buiten deze module

### OER-bestanden

`oeren/` is gitignored. Structuur: één submap per instelling (`davinci_oeren/`, `rijn_ijssel_oer/`, `talland_oeren/`, `aeres_oeren/`, `utrecht_oeren/`). Geïndexeerde OERs staan als `geindexeerd=1` in `oer_documenten`. Studenten met `oer_id` naar niet-geïndexeerde OERs krijgen geen chatantwoorden.

## Bekende valkuil

Een student die aan een niet-geïndexeerde OER gekoppeld is krijgt altijd "Ik kon geen relevante informatie vinden". Check met:

```sql
SELECT geindexeerd FROM oer_documenten WHERE id = <oer_id>;
```
