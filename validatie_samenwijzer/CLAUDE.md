# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Wat dit project is

Standalone Streamlit-app (`validatie_samenwijzer/`) die MBO-studenten en mentoren laat chatten met hun OER (Onderwijs- en Examenregeling) via hybride AI-retrieval (ChromaDB + Claude streaming). Leeft als subproject binnen de `samenwijzer`-monorepo maar heeft zijn eigen `pyproject.toml`, `.venv` en database.

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
OPENAI_API_KEY=sk-...
DB_PATH=data/validatie.db      # default
CHROMA_PATH=data/chroma        # default
OEREN_PAD=oeren                # default
```

## Architectuur

### Data-laag

**SQLite** (`db.py`) — schema met `instellingen`, `oer_documenten`, `kerntaken`, `mentoren`, `mentor_oer`, `studenten`, `student_kerntaak_scores`. Verbinding via `get_connection()` met WAL-modus en `check_same_thread=False` (vereist voor `@st.cache_resource`). Alle queries als losse functies, geen ORM.

**ChromaDB** (`vector_store.py`) — persistente collectie `oer_chunks`, cosine distance, gefilterd op `oer_id`. Drempelwaarde `DREMPELWAARDE = 0.7`: chunks boven die afstand worden weggegooid. Zoekfilter via `where={"oer_id": ...}` — een student ziet nooit chunks van andere OERs.

### Ingestie-pipeline (`ingest.py`)

```
bestandsnaam → parseer_bestandsnaam() → crebo/leerweg/cohort
bestand      → extraheer_tekst()      → tekst (pdfplumber → Tesseract OCR als < 100 tekens)
tekst        → chunk_tekst()          → chunks van ~500 woorden met overlap
chunks       → OpenAI embeddings      → vectoren
              → ChromaDB              → opgeslagen met oer_id-metadata
tekst        → extraheer_kerntaken()  → kerntaken/werkprocessen in SQLite
```

`parseer_bestandsnaam()` kent twee patronen:
1. Da Vinci-stijl: `25168BOL2025Examenplan.pdf` — crebo+leerweg+jaar aaneengesloten
2. Fallback: elk 5-cijferig getal als crebo, BOL/BBL en jaar los gesearcht — dekt Rijn IJssel- en Talland-bestanden

Bestanden zonder crebo in naam (Aeres, Utrecht) worden hernoemd via `tools/rename_oers.py` dat de titelpagina uitleest.

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

### Pagina's

| Bestand | Rol | Functie |
|---|---|---|
| `app/main.py` | beide | Login, sessie-initialisatie |
| `1_oer_assistent.py` | student | Hybride chat: embed vraag → zoek chunks op `oer_id` → stream Claude-antwoord |
| `2_mijn_oer.py` | student | Kerntaken/werkprocessen uit OER tonen |
| `3_mijn_voortgang.py` | student | Voortgang, BSA, scores visualiseren |
| `4_mijn_studenten.py` | mentor | Studentenlijst van eigen koppeling |
| `5_begeleidingssessie.py` | mentor | Profiel + chat voor actieve student |

### AI-isolatie

- Anthropic (Claude): `_ai._client()` — alleen voor streaming chat in `chat.py`
- OpenAI (embeddings): `_openai._client()` — alleen in `ingest.py` en pagina's die embeddings maken
- Nooit clients direct instantiëren buiten deze twee modules

### OER-bestanden

`oeren/` is gitignored. Structuur: één submap per instelling (`davinci_oeren/`, `rijn_ijssel_oer/`, `talland_oeren/`, `aeres_oeren/`, `utrecht_oeren/`). Geïndexeerde OERs staan als `geindexeerd=1` in `oer_documenten`. Studenten met `oer_id` naar niet-geïndexeerde OERs krijgen geen chatantwoorden.

## Bekende valkuil

Een student die aan een niet-geïndexeerde OER gekoppeld is krijgt altijd "Ik kon geen relevante informatie vinden". Check met:

```python
conn.execute("SELECT geindexeerd FROM oer_documenten WHERE id=?", (student["oer_id"],))
```
