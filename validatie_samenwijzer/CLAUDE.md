# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Wat dit project is

Standalone Streamlit-app (`validatie_samenwijzer/`) die MBO-studenten en mentoren laat chatten
met hun OER (Onderwijs- en Examenregeling) via Claude streaming met de **volledige OER als
context** (Sonnet 4.6, 1M-tokenvenster). Leeft als subproject binnen de `samenwijzer`-monorepo
maar heeft zijn eigen `pyproject.toml`, `.venv` en database.

> **Geen vector store**: PR #33 (mei 2026) heeft ChromaDB en OpenAI-embeddings verwijderd. De
> retrieval-laag is vervangen door full-document context. Zie ook `chat.py:_MAX_OER_TEKST_TEKENS`.

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
DB_PATH=data/validatie.db   # default
OEREN_PAD=oeren             # default
```

## Architectuur

### Data-laag

**`db.py`** — SQLite schema en alle queries als losse functies, geen ORM. Schema: `instellingen`,
`oer_documenten`, `kerntaken`, `mentoren`, `mentor_oer`, `studenten`, `student_kerntaak_scores`.
Verbinding via `get_connection()` met WAL-modus en `check_same_thread=False`.

**`_db.py`** — dunne Streamlit-wrapper: `get_conn()` is `@st.cache_resource` en roept
`get_connection()` + `init_db()` aan. Gebruik `_db.get_conn()` in pagina's,
`db.get_connection()` in scripts en tests.

### Ingestie-pipeline (`ingest.py`)

```
bestandsnaam → parseer_bestandsnaam()    → crebo/leerweg/cohort
bestand      → converteer_naar_markdown()→ <stem>.md naast bron (markitdown)
bestand      → extraheer_tekst()         → tekst (pdfplumber → Tesseract OCR als < 100 tekens)
tekst        → extraheer_kerntaken()     → kerntaken/werkprocessen in SQLite
oer_id       → markeer_geindexeerd()     → geindexeerd=1
```

Geen chunking, geen embeddings, geen vector store. De volledige OER-tekst wordt op
chat-tijd geladen door `chat.laad_oer_tekst()` (voorkeur: `<stem>.md` van markitdown,
fallback: pdfplumber over de PDF).

`parseer_bestandsnaam()` kent twee patronen:
1. Da Vinci-stijl: `25168BOL2025Examenplan.pdf` — crebo+leerweg+jaar aaneengesloten
2. Fallback: 5-cijferig getal als crebo, BOL/BBL en jaar los — dekt Rijn IJssel en Talland

Bestanden zonder crebo in naam (Aeres, Utrecht) worden hernoemd via `tools/rename_oers.py`
dat de titelpagina uitleest.

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
| `0_oer_vraag.py` | publiek (geen login) | Conversationele OER-chat; intake-stap als nog geen OER geselecteerd, multi-OER (max 3 tegelijk) |
| `1_oer_assistent.py` | student | OER-chat met volledige documentcontext (eigen `oer_id`) |
| `2_mijn_oer.py` | student | Volledig OER inzien of downloaden |
| `3_mijn_voortgang.py` | student | Voortgang, BSA, scores visualiseren |
| `4_mijn_studenten.py` | mentor | Studentenlijst van eigen koppeling |
| `5_begeleidingssessie.py` | mentor | Profiel + twee tabs: OER-chat en volledig OER bekijken |

### AI-isolatie

Alle Anthropic-calls lopen via `_ai._client()`. `chat.py` is de enige module met streaming-aanroepen.
Nooit `anthropic.Anthropic()` direct instantiëren.

### OER-chat-flow

`chat.py` levert drie ingangen, allemaal full-document context:

1. **Single-OER** (`bouw_systeem`) — gebruikt door `1_oer_assistent.py` en het tweede tabblad
   van `5_begeleidingssessie.py`. Laadt één OER via `laad_oer_tekst()`.
2. **Multi-OER** (`bouw_gecombineerd_systeem`) — gebruikt door `0_oer_vraag.py`. Combineert
   tot 3 OERs in één system prompt met blok-headers `=== OER 1: … ===`.
3. **Intake** (`genereer_intake_antwoord` + `identificeer_oer_kandidaten`) — fallback in
   `0_oer_vraag.py` zolang nog geen OER geselecteerd is. `identificeer_oer_kandidaten()`
   scoort op crebo (+3), leerweg (+2), cohort (+2), opleidingswoorden (+1, max 2),
   instelling (+1).

`laad_oer_tekst()` voorkeursvolgorde: `<stem>.md` (markitdown-output) → bron-`.md` →
pdfplumber over PDF. Hard cap: `_MAX_OER_TEKST_TEKENS = 500_000` tekens.

Toon `LAGE_RELEVANTIE_BERICHT` wanneer `laad_oer_tekst()` een lege string teruggeeft
(bestand ontbreekt of niet leesbaar).

### OER-bestanden

`oeren/` is gitignored. Structuur: één submap per instelling (`davinci_oeren/`, `rijn_ijssel_oer/`, `talland_oeren/`, `aeres_oeren/`, `utrecht_oeren/`). Geïndexeerde OERs staan als `geindexeerd=1` in `oer_documenten`. Studenten met `oer_id` naar niet-geïndexeerde OERs krijgen geen chatantwoorden.

## Bekende valkuilen

**Niet-geïndexeerde OER**: een student die aan een OER met `geindexeerd=0` gekoppeld is krijgt
geen kerntaken in de DB en (afhankelijk van het bestandspad) een leeg chatantwoord. Check met:

```python
conn.execute("SELECT geindexeerd, bestandspad FROM oer_documenten WHERE id=?", (student["oer_id"],))
```

**Ontbrekend bronbestand**: `geindexeerd=1` betekent dat kerntaken zijn geëxtraheerd, niet dat
het PDF/MD nog op de schijf staat. `chat.laad_oer_tekst()` valt eerst terug op `<stem>.md`,
daarna op de PDF. Ontbreken beide → `LAGE_RELEVANTIE_BERICHT`.

**Markitdown-conversie mislukt**: `converteer_naar_markdown()` is best-effort. Bij falen blijft
alleen pdfplumber over (mindere kwaliteit, geen tabellen). De log toont dan
`Markitdown-conversie mislukt voor '…'`.
