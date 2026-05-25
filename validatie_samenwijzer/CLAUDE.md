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


## Wat dit project is

Standalone Streamlit-app (`validatie_samenwijzer/`) die MBO-studenten en mentoren laat chatten
met hun OER (Onderwijs- en Examenregeling) via Claude streaming met de **volledige OER als
context** (Sonnet 4.6, 1M-tokenvenster). Het landelijke **kwalificatiedossier (KD)** wordt waar
beschikbaar mee-ingebed als aanvullende bron — de OER blijft leidend; het KD wordt alleen
geraadpleegd als de OER het onderwerp niet of onvoldoende behandelt. Leeft als subproject binnen
de `samenwijzer`-monorepo maar heeft zijn eigen `pyproject.toml`, `.venv` en database.

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
uv run ruff check src/ app/ scripts/
uv run ruff check --fix src/ app/

# Ingestie-pipeline
uv run python -m validatie_samenwijzer.ingest --alles          # nieuw indexeren
uv run python -m validatie_samenwijzer.ingest --alles --reset  # alles herindexeren
uv run python -m validatie_samenwijzer.ingest --bestand oeren/davinci_oeren/25751BBL2025Examenplan.pdf

# Bestandswatcher (herindexeer automatisch bij wijzigingen in oeren/)
uv run python -m validatie_samenwijzer.watcher          # bewaakt oeren/ (default)
uv run python -m validatie_samenwijzer.watcher --oeren-pad /pad/naar/oeren
# `ingest` en `watcher` zijn ook geregistreerd als project scripts (zie pyproject.toml)
# — `uv run ingest --alles` en `uv run watcher` werken identiek.

# Seed testdata
uv run python scripts/seed.py        # 3 studenten + 2 mentoren
uv run python scripts/seed_bulk.py   # ~1000 studenten over geïndexeerde OERs (vereist eerst `ingest --alles`)

# Bestandsnamen aanvullen + indexeren (alles-in-één)
./scripts/verwerk_oers.sh --preview  # droge run
./scripts/verwerk_oers.sh            # hernoem + indexeer

# Multi-machine setup: sync oeren vanuit Box + ingest + bulk-seed in één commando
./scripts/bootstrap.sh                  # default = bulk-seed (~1000 studenten)
./scripts/bootstrap.sh --skip-sync      # alleen ingest + seed (oeren/ al lokaal)
./scripts/bootstrap.sh --seed-minimal   # 3+2 dev-demo i.p.v. bulk
./scripts/bootstrap.sh --skip-seed      # geen testdata
./scripts/sync_oeren.sh                 # alleen rclone copy

# Kwalificatiedossiers (aanvullende AI-bron, gemapt op crebo)
uv run --with openpyxl python scripts/download_kwalificatiedossiers.py  # s-bb → kwalificatiedossiers/pdfs/<crebo>.pdf
uv run python scripts/convert_kwalificatiedossiers_md.py                 # PDF → <crebo>.md (markitdown, parallel)
./scripts/sync_kwalificatiedossiers.sh                                   # Box → lokaal
./scripts/sync_kwalificatiedossiers.sh --upload                          # lokaal → Box
```

Overige scripts in `scripts/` (`seed_rebuild_students.py`, `convert_oers_markdown.py`,
`push_oeren.sh`, `check_bootstrap.sh`) zijn supporting tooling — bekijk de bestanden voor
gebruik.

## Tests

Tests in `tests/`; pytest discovery via `[tool.pytest.ini_options]` in `pyproject.toml`.
Coverage en fixtures worden niet centraal beheerd — bekijk individuele testbestanden.

## Omgeving

`.env` in `validatie_samenwijzer/`:

```
ANTHROPIC_API_KEY=sk-ant-...
DB_PATH=data/validatie.db   # default
OEREN_PAD=../oeren          # default in dit subproject (root-oeren/ hergebruikt)
BEHEER_ENABLED=true         # activeer beheerpagina (alleen op dev-machines)
```

## Multi-machine workflow

`oeren/` (PDFs) en `validatie.db` zijn beide **gitignored** — te groot voor git en
copyright-gevoelig. Oeren staan centraal in een Box-folder; de DB wordt per machine
opgebouwd uit de oeren-tree.

**Eenmalige setup per machine** (vereist `rclone`):

```bash
# 1. Installeer rclone
curl https://rclone.org/install.sh | sudo bash
# 2. Configureer Box-remote (OAuth-flow in browser)
rclone config       # type "n", naam "box", storage "box", default-flags
# 3. Clone repo + run bootstrap
git clone git@github.com:cedanl/samenwijzer.git
cd samenwijzer/validatie_samenwijzer
./scripts/bootstrap.sh
```

Override de remote/pad via env-vars als je een andere Box-locatie of remote-naam hebt:

```bash
RCLONE_REMOTE=mijnbox RCLONE_OEREN_PAD=team/oeren ./scripts/sync_oeren.sh
```

## Beheerpagina

`app/pages/9_beheer.py` bundelt sync, re-ingest, seed en DB-status achter knoppen.
Bereikbaar op `/beheer` als `BEHEER_ENABLED=true` staat in `.env`. Subprocesses
draaien op de host en de output wordt live gestreamd in de UI. Niet aanzetten op
gedeelde servers — de pagina kan rclone, ingest en seed-scripts triggeren.

Tabs:
- **Status** — # OERs per instelling, # geïndexeerd, laatste ingest-run (uit
  tabel `ingest_runs`), aantal PDFs/markdown op schijf.
- **Sync oeren** — wrapper rond `scripts/sync_oeren.sh`.
- **Re-ingest** — scope-dropdown (alles/aeres/davinci/rijn_ijssel/talland/utrecht)
  + `--reset` checkbox.
- **Seed** — `seed_bulk.py` (~1000 studenten, default werkdata) of `seed.py` (3+2 dev-demo).

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

Bestanden zonder crebo in naam (Aeres, Utrecht) worden hernoemd via `scripts/rename_oers.py`
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
| `9_beheer.py` | dev | Sync/ingest/seed/status (alleen als `BEHEER_ENABLED=true`) |
| `uitloggen.py` | beide | Sessie wissen + redirect naar `/` |

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

`laad_kwalificatiedossier_tekst(crebo)` leest `kwalificatiedossiers/pdfs/<crebo>.md` (hard cap
`_MAX_DOSSIER_TEKST_TEKENS = 300_000`). Pad-resolutie via `pad_kwalificatiedossier(crebo)`:
default `<repo>/kwalificatiedossiers/pdfs`, override via env-var `KWALDOSSIERS_PAD`. Lege
string als de crebo geen KD heeft — de chat werkt dan OER-only.

Toon `LAGE_RELEVANTIE_BERICHT` wanneer `laad_oer_tekst()` een lege string teruggeeft
(bestand ontbreekt of niet leesbaar).

**Juridische citatieplicht**: zowel `_SYSTEEM_TEMPLATE` als `_MULTI_SYSTEEM_TEMPLATE` eisen per
claim drie elementen: **bron** ("Volgens de OER" of "Volgens het kwalificatiedossier"),
**vindplaats** (sectie-nummer, kopje, artikel of paginanummer) en een **woordelijk citaat
tussen dubbele aanhalingstekens**. Reden: een OER is een juridisch document — antwoorden
moeten verifieerbaar zijn. De OER is leidend; het KD wordt alleen geraadpleegd als de OER het
onderwerp niet of onvoldoende behandelt, met de inleider "De OER beschrijft dit niet; volgens
het kwalificatiedossier…". Markdown-blockquotes uit het AI-antwoord renderen via CSS als
pull-quote citaten. Spec: `docs/specs/2026-05-06-publieke-oer-citaten-en-pdf-design.md`
(vanuit repo-root).

**PDF-bekijken op publieke pagina** (`0_oer_vraag.py`): `pub_oer_paden: list[Path]` in session
state parallel aan `pub_oer_labels`. Per geladen OER een `📄 Bekijk OER N` knop boven de chat;
klik toggelt een expander met PDF-iframe (800px) + download-knop. Helper `_render_oer_bestand()`
spiegelt de logica van `2_mijn_oer.py`.

### OER-bestanden

`oeren/` is gitignored. Structuur: één submap per instelling (`davinci_oeren/`, `rijn_ijssel_oer/`, `talland_oeren/`, `aeres_oeren/`, `utrecht_oeren/`). Geïndexeerde OERs staan als `geindexeerd=1` in `oer_documenten`. Studenten met `oer_id` naar niet-geïndexeerde OERs krijgen geen chatantwoorden.

### Kwalificatiedossiers (aanvullende bron)

`kwalificatiedossiers/` (in repo-root, gitignored) bevat de landelijke kwalificatiedossiers
gemapt op crebo:

```
kwalificatiedossiers/
├── pdfs/<crebo>.pdf      # 240 PDFs, gedownload van s-bb.nl
├── pdfs/<crebo>.md       # markitdown-conversie naast iedere PDF (chat-bron)
├── lijsten/crebo_*.xlsx  # s-bb crebolijsten 2017-2026 (download-bron-mapping)
├── *.zip                 # 4 alfabetische bron-zips van s-bb
├── mapping.json
└── download_rapport.json # audit: welke crebo's gemapt, welke niet
```

**Multi-machine sync** verloopt via Box (`box:samenwijzer/kwalificatiedossiers/`, parallel aan
`oeren/`):

```bash
./scripts/sync_kwalificatiedossiers.sh           # Box → lokaal (default)
./scripts/sync_kwalificatiedossiers.sh --upload  # lokaal → Box (skipt *.zip)
```

**Opnieuw opbouwen** (alleen op de master-machine; andere machines syncen):

```bash
uv run --with openpyxl python scripts/download_kwalificatiedossiers.py
uv run python scripts/convert_kwalificatiedossiers_md.py
```

Het download-script bouwt crebo→dossier-mapping uit de s-bb crebolijsten (Complete lijst +
Vervallen/Wijzigingen-sheets) en handmatige overrides voor de recente "Gewijzigd 2024"-
herziening die nog niet in de lijsten staat. Coverage: 240/247 (97%) van de unieke crebo's in
`validatie.db`; de 7 missende crebo's zijn school-interne codes of opleidingsdomein-codes die
niet in het s-bb register voorkomen.

Conversie naar markdown gebruikt dezelfde markitdown-pipeline als de OER-conversie
(`ingest.converteer_naar_markdown`); de bulk-converter parallelliseert met 8 workers (~5min
voor 240 PDFs). Bij een ontbrekende `<crebo>.md` geeft `laad_kwalificatiedossier_tekst("")`
terug en werkt de chat OER-only — geen errors.

**Kosten-impact** (Sonnet 4.6, gemeten 2026-05 op crebo 25656 / VIG BBL FLEX, 3 typische
vragen): KD voegt ~40K extra prompt-tekens toe (mediane KD ≈ 85K tekens, range 26K-394K).
Eerste vraag in een sessie: ~$0.09 (OER-only) → ~$0.14 (OER+KD); vervolgvragen halen
prompt-cache en kosten ~$0.013 → ~$0.018. Totaal per sessie ≈ +47% (~$0.05). De
`_MAX_DOSSIER_TEKST_TEKENS = 300_000`-cap snijdt 7 van de 240 KDs af (3%); er is geen
aanleiding deze cap nu te verlagen. Herhaal de meting met `scripts/meet_token_kosten.py`.

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

**Streamlit module-cache bij styles-wijzigingen**: hot-reload herlaadt `styles.py` (en andere
imported modules) niet — alleen pagina-files worden direct opnieuw uitgevoerd. Bij CSS-edits in
`src/validatie_samenwijzer/styles.py` is een **volledige Streamlit-restart** nodig (`Ctrl-C` →
`uv run streamlit run app/main.py`). De R-toets in de browser triggert geen module-reload.

Snelle DOM-check of nieuwe CSS geladen is:
```js
Array.from(document.querySelectorAll('style')).some(s => s.textContent.includes('<class-naam>'))
```

## Presentatie

`presentatie/` bevat een **zelfstandige Slidev-deck** (CEDA/Npuls-huisstijl) over de evolutie
van vector store/RAG naar full-document context. Thema en assets zijn ingesloten, dus geen
externe repo nodig. Vereist Node:

```bash
cd presentatie
./start.sh        # = npm install (indien nodig) + npm run dev → http://localhost:3030
```

`node_modules/`, `dist/` en geëxporteerde PDF's zijn gegitignored; de slides, het thema en de
assets (incl. `public/screenshots/`) worden wél meegesynct.

> **Pin niet bumpen**: `@slidev/cli` staat vast op **52.14.1**. Vanaf 52.15.2 weigert de
> `slide-guard`-check de `public/`-assets omdat de deck genest in de samenwijzer-repo draait
> (dev-server geeft dan 500 op elke slide). Verifieer een versie-bump altijd in de **browser**,
> niet alleen via HTTP 200 of `slidev export` — die paden raken de bug niet.
