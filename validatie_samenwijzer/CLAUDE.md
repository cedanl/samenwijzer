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

# Lint + format (line-length 100; selectie E,F,I,N,W,UP; E501 vrijgesteld voor app/ + styles.py)
uv run ruff check src/ app/ scripts/
uv run ruff check --fix src/ app/
uv run ruff format src/ app/ scripts/    # CI elders eist ook `ruff format --check`

# Ingestie-pipeline
uv run python -m validatie_samenwijzer.ingest --alles          # nieuw indexeren
uv run python -m validatie_samenwijzer.ingest --alles --reset  # alles herindexeren
uv run python -m validatie_samenwijzer.ingest --bestand oeren/davinci_oeren/25751BBL2025Examenplan.pdf

# Opleidingsnamen helen (records die als "Opleiding <crebo>" renderen → echte naam)
OEREN_PAD=../oeren uv run python scripts/fix_opleiding_namen.py --dry-run
OEREN_PAD=../oeren uv run python scripts/fix_opleiding_namen.py --instelling davinci

# Bestandswatcher (herindexeer + reconcilieer KD/skills automatisch bij wijzigingen in oeren/)
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

# Skills-taxonomie (aanvullende AI-bron, hybride: CompetentNL crebo-direct → ESCO fallback)
uv run python scripts/build_skills_taxonomie.py            # alle ontbrekende crebo's
uv run python scripts/build_skills_taxonomie.py --reset    # alles opnieuw matchen
uv run python scripts/build_skills_taxonomie.py --crebo 25180   # één crebo

# Afgeleide bronnen reconciliëren (KD + skills) — bouwt alleen ontbrekende, idempotent
uv run python -m validatie_samenwijzer.sync_afgeleid --alles      # alle geïndexeerde crebo's
uv run python -m validatie_samenwijzer.sync_afgeleid --crebo 25180 # één crebo
```

Overige scripts in `scripts/` (`seed_rebuild_students.py`, `convert_oers_markdown.py`,
`push_oeren.sh`, `check_bootstrap.sh`) zijn supporting tooling — bekijk de bestanden voor
gebruik.

## Tests

Tests in `tests/`; pytest discovery via `[tool.pytest.ini_options]` in `pyproject.toml`.
Coverage en fixtures worden niet centraal beheerd — bekijk individuele testbestanden. De
autouse-fixture in `conftest.py` reset de gecachete `_ai`-client tussen tests zodat een gemockte
client niet lekt.

> **Geen CI-gate voor dit subproject**: de root-workflow `.github/workflows/ci.yml` draait
> `ruff check` / `ruff format --check` / `pytest` vanuit de **monorepo-root** met `uv sync --dev`
> en raakt dit subproject (eigen `pyproject.toml` + `.venv`) niet aan. Lint, format en tests hier
> worden door niets afgedwongen op PR — draai ze lokaal vóór je commit.

## Omgeving

`.env` in `validatie_samenwijzer/`:

```
ANTHROPIC_API_KEY=sk-ant-...
DB_PATH=data/validatie.db   # default
OEREN_PAD=../oeren          # default in dit subproject (root-oeren/ hergebruikt)
BEHEER_ENABLED=true         # activeer beheerpagina (alleen op dev-machines)
COMPETENTNL_API_KEY=...      # optioneel: skills-build gebruikt CompetentNL ipv ESCO (zie Skills)
```

## Multi-machine workflow

**Wat zit waar** (bron → distributiekanaal):

| Bron | In git? | Op Box? | Per machine opgebouwd? |
|---|---|---|---|
| `oeren/` (publieke instellingen, PDF + markitdown-`.md`) | **ja** | ja (`box:samenwijzer/oeren`) | — |
| `oeren/{davinci,kwic,graafschap,deltion}_oeren/` | **nee — gitignored** | **ja — Box-only** | — |
| `kwalificatiedossiers/` | nee (gitignored) | **ja — Box-only** | — |
| `data/skills/` | **ja** (via `.gitignore`-negatie) | — | — |
| `validatie.db` | nee (gitignored) | nee | **ja** (`ingest` uit de oeren-tree) |

> De `oeren/`-regel in `validatie_samenwijzer/.gitignore` dekt alléén een (niet-bestaande)
> `validatie_samenwijzer/oeren/`, niet de root-tree die de app via `OEREN_PAD=../oeren` gebruikt —
> die staat dus **wél** in versiebeheer. **Uitzondering (rechten, PR #143):** Da Vinci, KWIC,
> Graafschap en Deltion publiceren hun OER's niet zelf; hun mappen zijn via de **root-`.gitignore`**
> Box-only gemaakt (mogen niet publiek vindbaar zijn, alleen via de app). Box blijft de centrale
> grote-bestanden-store/back-up náást git. De feitelijke verwijdering uit de git-**historie** (Fase 2)
> is een geplande teamactie — zie `docs/plans/2026-06-04-fase2-history-purge-runbook.md` en het
> beslisdocument `2026-06-04-opslagstrategie-data-en-deployment.md`.

**Eenmalige setup per machine.** Een fresh `git clone` bevat de **oeren-tree** uit git (op de vier
niet-publieke instellingen ná — die komen alleen van Box), maar **niet** de kwalificatiedossiers
(Box-only). rclone + Box blijft dus nodig voor de KD's én die vier instellingen:

```bash
# 1. Installeer rclone
curl https://rclone.org/install.sh | sudo bash
# 2. Configureer Box-remote (OAuth-flow in browser)
rclone config       # type "n", naam "box", storage "box", default-flags
# 3. Clone repo
git clone git@github.com:cedanl/samenwijzer.git
cd samenwijzer/validatie_samenwijzer
# 4. Bootstrap: sla de overbodige oeren-sync over (git leverde die al),
#    haal wél de KD's van Box, en draai ingest + seed
./scripts/bootstrap.sh --skip-oeren-sync
```

`bootstrap.sh` zónder vlag werkt ook — de oeren-sync is dan een idempotente `rclone copy` die
identieke bestanden overslaat, bovenop wat git al leverde. Draai de volle sync alleen als je oeren
níet via git hebt. (`--skip-sync` slaat óók de KD-sync over → gebruik dat alleen als beide trees al
lokaal staan, niet na een verse clone.)

**Nieuwe OER-bestanden toevoegen** gaat naar **beide** kanalen, anders mist git-cloners óf
Box-syncers ze stil:

```bash
git add oeren/<instelling>_oeren/... && git commit   # in versiebeheer
./scripts/push_oeren.sh                               # naar Box (rclone copy — verwijdert niets)
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
`oer_documenten`, `kerntaken`, `mentoren`, `mentor_oer`, `studenten`, `student_kerntaak_scores`,
`ingest_runs`, `instelling_documenten` (instellingsbrede regelingen — zie hieronder).
`INSTELLING_SOORTEN` (module-constante) is de **enige bron van waarheid** voor de bekende
instellingsbrede document-soorten → citeer-label; een nieuwe soort toevoegen = één regel daar,
geen schema-migratie (soort-validatie staat in `voeg_instelling_document_toe`, niet in een DB-CHECK).
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

**KD-fallback (issue #53)**: levert de OER nul kerntaken op (bv. Aeres/Rijn IJssel-examenplannen
die de kwalificatiestructuur niet uitschrijven), dan draait `_verwerk_bestand` dezelfde extractor
over het kwalificatiedossier van die crebo (`_kerntaken_uit_kd` over `<crebo>.md`, pad via
`_pad_kwalificatiedossier`). **Fire-at-zero + supplement-never-replace**: vuurt uitsluitend bij
nul OER-kerntaken, dus instellingen die hun kerntaken wél in de OER hebben blijven OER-bron.

`parseer_bestandsnaam()` kent twee patronen:
1. Da Vinci-stijl: `25168BOL2025Examenplan.pdf` — crebo+leerweg+jaar aaneengesloten
2. Fallback: 5-cijferig getal als crebo, BOL/BBL en jaar los — dekt Rijn IJssel en Talland

Bestanden zonder crebo in naam (Aeres, Utrecht) worden hernoemd via `scripts/rename_oers.py`
dat de titelpagina uitleest.

**Deltion = gestructureerde markdown** (`scripts/fetch_deltion.py`): de Deltion-studiegidsen komen
uit de SQill-publisher-API als rijke HTML en worden via **markitdown** naar gestructureerde
markdown (koppen, tabellen, lijsten, links, logo) geschreven — niet meer platgeslagen met
BeautifulSoup `get_text`. Daarom tolereert `_KT_PATROON` nu een optionele markdown lijst-marker
(`* `/`+ `/`- `), zodat de `B1-K1-W1`-codes in lijstitems blijven extracten; en weert
`extraheer_kerntaken` namen met een `|` (markdown-tabelrij waar de code toevallig vooraan staat).

**Bestandspad-selectie**: bij meerdere bestanden per crebo/leerweg/cohort (bv. Da Vinci's gescande
Examenplan náást een tekstrijke MJP) werkt `_resolveer_oer` de `bestandspad` pas bij **ná bewezen
leesbare tekst** (PDF-prioriteit behouden) — een tekstloze, gescande PDF wordt dus nooit de bron
als er een tekstrijke variant bestaat.

**Opleidingsnaam-afleiding**: primair de bestandsnaam-stem; bevat die geen naam (bv. de kale
Da Vinci `25882BOL2025Examenplan.pdf`), dan leest `_extraheer_opleiding_uit_pdf` de titelpagina —
herkent zowel het ROC Utrecht-format (`Kwalificatie (profiel): …`) als de drie Da Vinci-formaten
(`Examenplan <naam> vanaf cohort … – crebo …`, via `_OPLEIDING_LIJN_DAVINCI`). De ruwe waarde wordt
op de read-boundary opgeschoond door `opleiding.schoon_opleiding_naam` — een **UI-loze module**
(`src/validatie_samenwijzer/opleiding.py`) zodat ingest, `chat.py` (injectie in de system-prompt)
én scripts 'm delen; `styles.py` her-exporteert voor bestaande UI-callers. Bestaande DB-records die
nog als "Opleiding <crebo>" renderen heel je met `scripts/fix_opleiding_namen.py` (bron-volgorde:
eigen bestand — sibling-bestandsnaam of titelpagina, kwaliteit-gekozen — dan crebo-leen van een
ander record met dezelfde landelijke opleidingscode; idempotent, `--dry-run`). Dit is een
**data-heal op de gebakken DB**, dus draai 'm vóór een Fly-deploy als de namen wijzigen.

> **Sync met de parent-monorepo**: de parse-helpers in `ingest.py` (`parseer_bestandsnaam`,
> `extraheer_kerntaken`, opleidingsnaam/niveau-regex) zijn de **bron** die bewust gespiegeld wordt
> naar `src/samenwijzer/oer_parsing.py` in de parent. Wijzig je ze hier, werk dan de parent-kopie
> mee bij (en omgekeerd) — ze moeten functioneel gelijk blijven.

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

### FastAPI-frontend-POC (`app_fastapi/`)

Náást de Streamlit-app leeft een **proof-of-concept FastAPI-frontend** (`app_fastapi/`, eigen
poort 8504: `uv run uvicorn app_fastapi.main:app --port 8504`). Reden: de mock-up-kwaliteit
(`docs/mockups/oer-vraag-landing.html`) is in Streamlit structureel niet haalbaar (geen DOM-bezit,
geen page-JS, rerun-model). De POC vervangt **alleen de UI-schil** en hergebruikt de Python-laag
(`chat.py`, `db.py`, `_ai.py`, `auth.py`) **ongewijzigd** — die importeren geen streamlit.

- `main.py` (routes + SSE-chat), `context.py` (OER-context-orchestrator: OER + KD + skills +
  instellingsdocumenten per rol via `PUBLIEK/STUDENT/MENTOR_SOORTEN` + web-zoek-domeinen),
  `auth.py` (login-hergebruik), `data.py` (voortgang/studenten/profiel), `sessie.py` (server-side
  sessie via signed-cookie `sid`), `static/chat.js` (escapende markdown-renderer + SSE + viewer —
  één plek voor de security-gevoelige rendering), templates.
- **Toegangspoort**: de hele app achter `ALGEMEEN_WACHTWOORD` (`.env`); login student/mentor erachter.
- Streaming via `text/event-stream`; dezelfde `_ai._client()` → prompt-cache blijft werken.
- Tests: `tests/test_fastapi_poc.py`. Draait náást Streamlit (8503 ongemoeid).
- **Status**: POC op `main`. `Dockerfile.fastapi` is voorbereid maar **niet** aan `fly.toml`
  gekoppeld — de productie-deploy gebruikt nog de Streamlit-`Dockerfile`. Open vóór een
  FastAPI-deploy: sessiestore met TTL/gedeeld (i.p.v. in-memory) + cookie-hardening
  (`SESSION_SECRET` verplicht, `https_only`). Zie `docs/plans/2026-06-08-fastapi-poc-publieke-oer-chat.md`.

### AI-isolatie

Alle Anthropic-calls lopen via `_ai._client()`. `chat.py` is de enige module met streaming-aanroepen.
Nooit `anthropic.Anthropic()` direct instantiëren. De client wordt gebouwd met
`_CLIENT_OPTS = {timeout: httpx.Timeout(30.0, connect=10.0), max_retries: 2}` zodat het 30s-contract
écht wordt afgedwongen (de SDK-default read is 600s); bij streaming is de read-timeout per
inter-event, dus een lang antwoord wordt niet afgebroken — alleen een vastgelopen stream.

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

**Gespreksgeschiedenis & caching**: `bouw_berichten()` saneert de historie (lege/mislukte beurten
weg, alternerende rollen, onbeantwoorde laatste user-beurt vervangen) zodat één gefaalde AI-call de
sessie niet kan blokkeren met een API 400. `genereer_antwoord()` zet `cache_control` met **1h-TTL**
op het system-blok én een cache-breakpoint op de laatste beurt (`_messages_met_cache`), zodat de
volledige OER-context én de gespreksgeschiedenis bij vervolgvragen uit de prompt-cache worden gelezen
i.p.v. elke beurt vol betaald — overleeft leespauzes >5 min tussen vragen.

**Antwoord-rendering**: AI-antwoorden renderen via native `st.markdown(antwoord)` binnen een keyed
`st.container(key="chatantwoord_*")` — **niet** in een rauwe `<div>` met `unsafe_allow_html` (dat brak
op een letterlijke `<` of code in het antwoord). De bubble- en citaat-pull-quote-CSS targeten daarom
`.chat-antwoord` (statische loading-indicator) én `[class*="st-key-chatantwoord"]` (het antwoord).
Vraag-bubbels blijven `html.escape` + `.chat-vraag`.

`laad_kwalificatiedossier_tekst(crebo)` leest `kwalificatiedossiers/pdfs/<crebo>.md` (hard cap
`_MAX_DOSSIER_TEKST_TEKENS = 300_000`). Pad-resolutie via `pad_kwalificatiedossier(crebo)`:
default `<repo>/kwalificatiedossiers/pdfs`, override via env-var `KWALDOSSIERS_PAD`. Lege
string als de crebo geen KD heeft — de chat werkt dan OER-only.

`laad_skills_tekst(crebo)` leest het skills-artefact `data/skills/<crebo>.json` (hard cap
`_MAX_SKILLS_TEKST_TEKENS = 50_000`) en formatteert beroep + essentiële/optionele skills tot een
tekstblok. Pad-resolutie via `pad_skills(crebo)`: default `<subproject>/data/skills`, override via
env-var `SKILLS_PAD`. Lege string als de crebo geen artefact of geen gematcht beroep heeft — de
chat werkt dan zonder skills. Zie de Skills-taxonomie-sectie verderop.

`laad_instelling_bron_tekst(bestandspad)` leest een instellingsbreed document (examenreglement,
begeleidingsbeleid, studentenstatuut, algemene informatie; hard cap
`_MAX_INSTELLING_TEKST_TEKENS = 300_000`). Pagina's halen de paden uit `instelling_documenten`
(`db.haal_instelling_document_op`) en geven `(label, tekst)`-paren door als `instelling_bronnen`
aan `bouw_systeem` / `bouw_gecombineerd_systeem`, die ze als blokken `=== LABEL (instelling) ===`
in de system prompt zetten. Bedraad in `1_oer_assistent.py`, `5_begeleidingssessie.py` en
`0_oer_vraag.py`. Zie de Instellingsbrede-bron-sectie verderop.

**OER-onleesbaar-modus**: is de OER-fulltext leeg (gescande PDF zonder tekstlaag), dan bouwt
`bouw_systeem` de prompt in een aangepaste modus die het kwalificatiedossier + instellingsregelingen
als hoofdbron neemt (i.p.v. de OER) en de citatie-instructie daarop aanpast (drie template-varianten:
`_PRIMAIRE_BRON_*`, `_KD_INSTRUCTIE_*`, `_OER_SECTIE_*`). De chatpagina's antwoorden zolang er een
KD óf instellingsbron is (`heeft_bron`) en tonen dan een `st.info`-banner dat de OER niet
machine-leesbaar is. Alleen zónder enige bron volgt nog `LAGE_RELEVANTIE_BERICHT`. Spec/plan:
`docs/plans/2026-06-09-chat-kd-fallback-onleesbare-oer.md`.

Toon `LAGE_RELEVANTIE_BERICHT` wanneer `laad_oer_tekst()` een lege string teruggeeft én er geen
KD/instellingsbron is (bestand ontbreekt of niet leesbaar, zonder aanvullende bron).

**Juridische citatieplicht**: zowel `_SYSTEEM_TEMPLATE` als `_MULTI_SYSTEEM_TEMPLATE` eisen per
claim drie elementen: **bron** ("Volgens de OER", "Volgens het kwalificatiedossier" of "Volgens
het [examenreglement/studentenstatuut/…]"), **vindplaats** (sectie-nummer, kopje, artikel of
paginanummer) en een **woordelijk citaat tussen dubbele aanhalingstekens**. Reden: een OER is een
juridisch document — antwoorden moeten verifieerbaar zijn. De OER is leidend; het KD wordt alleen
geraadpleegd als de OER het onderwerp niet of onvoldoende behandelt, met de inleider "De OER
beschrijft dit niet; volgens het kwalificatiedossier…". Instellingsbrede regelingen zijn een
**eigen bron** in de citatie (een examenreglement is even juridisch bindend als de OER). Voor de **skills-taxonomie** geldt een **aangepaste citatie** (een
taxonomie heeft geen secties of pagina's): bron + beroep + categorie + exacte skill-naam, bijv.
*Volgens de ESCO-skillstaxonomie hoort bij het beroep "kok" de essentiële skill "kooktechnieken
gebruiken"*. Het template verbiedt expliciet verzonnen paginanummers bij skills.
Markdown-blockquotes uit het AI-antwoord renderen via CSS als pull-quote citaten. Spec:
`docs/specs/2026-05-06-publieke-oer-citaten-en-pdf-design.md` (vanuit repo-root).

**PDF-bekijken op publieke pagina** (`0_oer_vraag.py`): `pub_oer_paden: list[Path]` in session
state parallel aan `pub_oer_labels`. Per geladen OER een `📄 Bekijk OER N` knop boven de chat;
klik toggelt een expander met PDF-iframe (800px) + download-knop. Helper `_render_oer_bestand()`
spiegelt de logica van `2_mijn_oer.py`.

### OER-bestanden

`oeren/` (root-tree, via `OEREN_PAD=../oeren`) is grotendeels **getrackt in git** — behalve de vier
niet-publieke instellingen (`davinci_oeren/`, `kwic_oeren/`, `graafschap_oeren/`, `deltion_oeren/`),
die via de root-`.gitignore` **Box-only** zijn (rechten — zie Multi-machine workflow). Structuur: één
submap per instelling (`davinci_oeren/`, `rijn_ijssel_oer/`,
`talland_oeren/`, `aeres_oeren/`, `utrecht_oeren/`, `kwic_oeren/` = Koning Willem I College).
Daarnaast `oer_algemeen/` voor instelling-overstijgende documenten. De instelling-keys leven in
**drie hardgecodeerde lijsten** die synchroon moeten blijven: `ingest._INSTELLINGEN`/`_MAP_NAAM`,
`scripts/seed_bulk.py:INSTELLINGEN` en `9_beheer.py:_INSTELLING_KEYS` — ontbreekt een nieuwe
instelling in de seed-lijst, dan krijgt ze stil 0 studenten. Geïndexeerde OERs staan als
`geindexeerd=1` in `oer_documenten`. Studenten met `oer_id` naar niet-geïndexeerde OERs krijgen
geen chatantwoorden.

Per instelling kan een `_instelling/`-submap (`oeren/<inst>_oeren/_instelling/<soort>.{pdf,md}`)
de instellingsbrede regelingen bevatten; de bestandsnaam-stem is de `soort` (moet in
`db.INSTELLING_SOORTEN` staan). `ingest._verwerk_instelling_documenten` indexeert die apart van de
gewone OER-iteratie (`_INSTELLING_SUBMAP` wordt overgeslagen door de platte OER-loop).

### Instellingsbrede bron (aanvullende bron)

Naast de OER, het KD en skills is er een **vierde chat-bron**: instellingsbrede regelingen
(examenreglement, begeleidings-/welzijnsbeleid, studentenstatuut, algemene informatie). Anders dan
KD/skills (crebo-gekoppeld) hangt deze bron aan de **instelling**, dus elke student/mentor van die
school krijgt ze automatisch mee. Soorten staan in `db.INSTELLING_SOORTEN` en zijn **uitbreidbaar
met één regel** (geen schema-migratie). Documenten leven in `oeren/<inst>_oeren/_instelling/`,
worden geïndexeerd in `instelling_documenten` en in de chat als eigen blok + eigen citatie-bron
opgenomen (zie OER-chat-flow en de Juridische citatieplicht hierboven). Plan/onderbouwing:
`docs/plans/2026-06-02-instellingsbrede-bron.md`.

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

### Skills-taxonomie (aanvullende bron)

Een OER leidt op voor een beroep; van dat beroep willen we de benodigde **skills** kunnen tonen
("welke skills heb ik nodig voor het beroep Kok?"). De skills-build is **hybride met twee bronnen**
en een uniform, bron-agnostisch artefact per crebo.

**Bron 1 — CompetentNL** (`competentnl_bron.py`, voorkeur): de gecureerde NL skills-set áchter het
UWV-skills-dashboard. **Crebo-direct**, geen beroep-matching: een `cnlo:EducationalNorm` met
`ksmo:opleidingscode = <crebo>` verwijst via `prescribesHATEssential` / `prescribesHATImportant`
rechtstreeks naar skills (`humancapability` + `knowledgearea`) → categorieën `essentieel` /
`belangrijk`. SPARQL-endpoint `https://sparql.competentnl.nl/v1`, header `apikey` =
`COMPETENTNL_API_KEY`. Zonder key (of crebo niet in CompetentNL, ~58% dekking) → `None` → val terug
op ESCO. `prescribesHATImportant` kan ook naar `LanguageProficiency`-nodes wijzen (taalvereisten
zonder prefLabel); die worden overgeslagen.

**Bron 2 — ESCO** (`skills_bron.py`, fallback): de keyless REST-API `https://ec.europa.eu/esco/api`.
Geen crebo-sleutel, dus **OER → beroep → skills** via tekstmatching → categorieën `essentieel` /
`optioneel`:
```
opleidingsnaam → schoon_opleidingsnaam()  → beroep-zoekterm (strip crebo/jaar/leerweg/OER-ruis)
zoekterm+KD-domein → zoek_esco_beroepen() → kandidaat-beroepen (ESCO occupation-search, nl)
kandidaten     → _kies_met_llm()          → beste beroep, of "GEEN" (Haiku; brede opl. → GEEN)
beroep-uri     → haal_esco_beroep_details()→ definitie + essentiële/optionele skills
```
De **LLM-keuze** is essentieel: ESCO's top-1 is onbetrouwbaar (`chauffeur wegvervoer` →
"chauffeur gevaarlijke stoffen" i.p.v. "vrachtwagenchauffeur"). Claude kiest uit de kandidaten
met de opleidingsnaam **én het KD-domein** als context; brede instroomopleidingen (zoals
"Entree") krijgen bewust "GEEN" i.p.v. een willekeurig beroep.

**Hybride build** (`scripts/build_skills_taxonomie.py`): per crebo eerst CompetentNL, anders ESCO;
het `bron`-veld in elk `data/skills/<crebo>.json` toont welke gebruikt is. Plus een reviewbare
`data/skills/_match_overzicht.csv` (met `bron`-kolom). Anders dan de rest van `data/` (gitignored)
is **`data/skills/` wél getrackt** (via `.gitignore`-negatie): de artefacten zijn klein +
open-license, dus de gecureerde matches zitten in de repo en werken op elke machine zonder rebuild.
**Idempotent**: bestaande bestanden worden overgeslagen (de ESCO-LLM-match is niet-deterministisch
en wordt zo gepind); `--reset` forceert herbouw. De review-CSV is bedoeld voor **handmatige
eyeballing** — vooral de ESCO-matches (een match-score is geen correctheidscheck; taxonomiegaten
zoals "mediamaker" passeren stil). CompetentNL-matches zijn crebo-direct en betrouwbaar.

### Afgeleide bronnen automatisch bijwerken (reconciliatie)

Zodra OER's wijzigen (nieuwe OER's, updates, nieuwe instellingen) moeten KD + skills meebewegen.
De motor is **desired-state reconciliatie** (`sync_afgeleid.py` → `werk_afgeleide_bronnen_bij`):
vergelijk de geïndexeerde crebo's met de bestaande artefacten en bouw alleen wat ontbreekt.
Idempotent; **working-tree only** (raakt git/Box niet aan) en rapporteert wat te distribueren —
nieuwe skills (→ commit/PR), nieuwe KD (→ Box-sync), plus **KD-gaten** (geen dossier in de
s-bb-bundle) én **skills-gaten** (crebo zonder passend beroep).

```bash
uv run python -m validatie_samenwijzer.sync_afgeleid --alles       # alle crebo's
uv run python -m validatie_samenwijzer.sync_afgeleid --crebo 25180  # één crebo
```

Drie aanroepers: **`bootstrap.sh`** (stap 6, `--alles` ná ingest+seed; `--skip-derived` om over te
slaan), de **watcher** (per crebo ná een succesvolle ingest — latency-optimalisatie, draait inline
in de event-loop) en handmatig. De asymmetrie: **skills** zijn live per crebo (CompetentNL/ESCO,
altijd bouwbaar); **KD** komt uit de lokale s-bb-bundle, dus KD-reconciliatie werkt alleen op een
machine mét die bundle (master) — andere machines syncen KD via Box. Een OER-inhoudswijziging met
ongewijzigde crebo triggert niets (beide bronnen zijn crebo-gekoppeld). Volledig plan + fasering:
`docs/plans/auto-sync-afgeleide-bronnen.md` (Fase 1+2 geïmplementeerd; Fase 3 — `--refresh-fallbacks`
+ s-bb-bundle-refresh — staat nog open).

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
