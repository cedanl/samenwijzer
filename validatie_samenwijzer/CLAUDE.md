# CLAUDE.md

Guidance for Claude Code in dit subproject. Dagelijkse essentials + harde invarianten staan hier;
de volledige module-rollen, datapipelines en multi-machine-workflow staan in **`docs/ARCHITECTURE.md`**.

**Tradeoff:** deze richtlijnen kiezen voorzichtigheid boven snelheid. Voor triviale taken: gebruik
oordeel.

## Werkstijl (LLM-valkuilen vermijden)

1. **Denk vóór je codeert.** Maak aannames expliciet; bij twijfel vraag. Meerdere interpretaties →
   presenteer ze, kies niet stil. Simpeler pad → zeg het. Onduidelijk → stop en benoem het.
2. **Simpelheid eerst.** Minimale code die het probleem afdekt; niets speculatiefs. Geen features,
   abstracties of "flexibiliteit" die niet gevraagd is. 200 regels die 50 kunnen zijn → herschrijf.
3. **Chirurgische wijzigingen.** Raak alleen wat de taak vereist; geen refactor van aangrenzende code,
   comments of opmaak. Match bestaande stijl. Dode code die je opmerkt: meld, verwijder niet
   (tenzij je eigen wijziging 'm wees maakte).
4. **Doelgedreven.** Vertaal taken naar verifieerbare doelen ("voeg validatie toe" → "schrijf tests
   voor invalide input, maak ze groen"). Bij multi-step: noem kort het plan + per stap een check.

## Wat dit project is

Standalone **FastAPI-app** (`app_fastapi/`) die MBO-studenten en mentoren laat chatten met hun OER
(Onderwijs- en Examenregeling) via Claude streaming met de **volledige OER als context** (Sonnet 4.6,
1M-tokenvenster). Het landelijke **kwalificatiedossier (KD)** wordt waar beschikbaar mee-ingebed als
aanvullende bron — de OER blijft leidend; het KD wordt alleen geraadpleegd als de OER het onderwerp
niet of onvoldoende behandelt. Leeft als subproject binnen de `samenwijzer`-monorepo met eigen
`pyproject.toml`, `.venv` en database.

De **publieke startpagina** (`/`, geen login) is de primaire ingang: een vrije vraag of de
opleidingskiezer-cascade (`/api/opleidingen` → instelling → leerweg → opleiding → cohort) identificeert
de juiste OER(s) via `identificeer_oer_kandidaten`. De flow kent drie modi — `chat` (1 kandidaat,
direct laden), `kies` (meerdere → `/api/kies`), `intake` (geen) — en valt daarna terug op dezelfde
chat-streaming. Student/mentor-routes achter login (`/student`, `/mentor`, `/beheer`) delen die kern.

> **Frontend (juni 2026)**: de Streamlit-frontend (`app/`) is **geretired**; `app_fastapi/` is DE
> frontend en draait in productie als `digitale-gids` op Fly via `Dockerfile.fastapi`. De Python-kern
> (`chat.py`, `db.py`, `_ai.py`, `auth.py`) is ongewijzigd gedeeld. Referenties naar `app/`,
> `st.session_state` of poort 8503 betreffen de geretirede app — zie `docs/ARCHITECTURE.md`.

> **Geen vector store**: PR #33 verving ChromaDB + embeddings door full-document context
> (`chat.py:_MAX_OER_TEKST_TEKENS`).

## Dagelijkse commando's

Vanuit `validatie_samenwijzer/`. Volledige catalogus (ingest, KD/skills-build, bootstrap, sync) in
`docs/ARCHITECTURE.md`.

```bash
./start.sh                                                  # app op :8504 (PORT=… / --no-reload); checkt .env
uv run uvicorn app_fastapi.main:app --port 8504 --reload   # zelfde, zonder .env-check
uv sync --extra dev && uv run python -m pytest             # tests
uv run python -m pytest tests/test_ingest.py::test_parseer_bestandsnaam_davinci -v  # één test
uv run ruff check --fix src/ app_fastapi/ scripts/ && uv run ruff format src/ app_fastapi/ scripts/  # lint + format
uv run python -m validatie_samenwijzer.ingest --alles      # (her)indexeer OERs (+ --reset, --instelling <key>)
uv run python -m validatie_samenwijzer.sync_afgeleid --alles  # KD + skills reconciliëren (bouwt alleen ontbrekende)
uv run python -m validatie_samenwijzer.bron_updates        # bronactualiteit-rapport (ook wekelijks via GitHub Action)
```

Lint: line-length 100; selectie `E,F,I,N,W,UP`. `app_fastapi/*.py` wordt volledig gelint (HTML/CSS/JS
leeft in `app_fastapi/templates|static`, buiten ruff).

## Tests

De autouse-fixtures in `tests/conftest.py` resetten de gecachete `_ai`-client en de crebo-naam-cache
tussen tests, zodat een gemockte client of een gemonkeypatcht namenbestand niet lekt.

> **Geen CI-gate voor dit subproject**: de root-`ci.yml` draait `ruff`/`pytest` vanuit de
> monorepo-root en raakt dit subproject (eigen `.venv`) niet. Draai lint, format en tests **lokaal**
> vóór je commit.

## Omgeving

`.env` in `validatie_samenwijzer/` (sjabloon: `.env.example`):

```
ANTHROPIC_API_KEY=sk-ant-...
SESSION_SECRET=...           # verplicht, fail-closed: app weigert te starten zonder
ALGEMEEN_WACHTWOORD=...      # verplicht, fail-closed: poort vóór de hele app (/toegang)
COOKIE_HTTPS_ONLY=0          # lokaal over http nodig, anders wordt de sessiecookie niet gezet
DB_PATH=data/validatie.db   # default
OEREN_PAD=../oeren          # default (root-oeren/ hergebruikt)
BEHEER_ENABLED=true         # activeer beheerpagina (alleen op dev-machines; prod = false)
COMPETENTNL_API_KEY=...      # optioneel: skills-build gebruikt CompetentNL ipv ESCO
```

`tests/conftest.py` zet `SESSION_SECRET`, `ALGEMEEN_WACHTWOORD` en `COOKIE_HTTPS_ONLY=0` zelf;
tests hebben geen `.env` nodig.

**Deploy** (commando + Fly-app: root-`CLAUDE.md`): `validatie.db` en `data/skills` worden **in het
image gebakken** — na een re-ingest of re-seed is een nieuwe deploy nodig. `SESSION_SECRET`,
`ALGEMEEN_WACHTWOORD` en `ANTHROPIC_API_KEY` zijn Fly-secrets; `BEHEER_ENABLED=false` in prod.

## Architectuur-invarianten (niet breken)

Volledige beschrijving in `docs/ARCHITECTURE.md`. De regels die een wijziging niet mag overtreden:

- **AI-isolatie**: alle Anthropic-calls via `_ai._client()`; `chat.py` is de enige module met
  streaming-aanroepen. **Nooit** `anthropic.Anthropic()` direct instantiëren. De client dwingt het
  30s-timeout-contract af (`_CLIENT_OPTS`).
- **Geen business logic in `app_fastapi/`**; geen raw SQL in routes — alle DB-toegang via `db.py`
  (`get_connection()`), zowel in scripts/tests als via de route-lokale `_conn()`-helper.
  `app_fastapi/context.py` (chat-context uit OER-id's) en `data.py` (UI-vrije dicts voor de
  ingelogde pagina's) zijn dunne orchestrators over `chat.py`/`db.py`.
- **Toegangspoort**: middleware `_toegangspoort` in `main.py` zet de héle app achter
  `ALGEMEEN_WACHTWOORD` (`/toegang`); `/api/*` krijgt 401, pagina's een redirect. Alleen `/static`
  is vrij. Pas op: `/` is "publiek" (geen login) maar zit wél achter de poort.
- **Sessiestate leeft server-side** (`app_fastapi/sessie.py`): de cookie draagt alleen een `sid`;
  de chat-state (system-prompt tot ~500K × bronnen) staat in SQLite `data/sessies.db`
  (`SESSIE_DB_PATH`, TTL 6 uur). Consequentie: **één Fly-machine** (`min_machines_running = 1`,
  geen scale-out) en de store overleeft geen redeploy. De middleware bewaart alleen op
  niet-GET-requests (behalve `/api/chat`, dat zelf post-stream bewaart) — een GET die de sessie
  muteert moet expliciet `bewaar_sessie()` aanroepen, anders lost update.
- **Vier chat-bronnen**, alle full-document: OER (leidend) + KD + skills + instellingsbrede regelingen.
  Loaders + caps in `chat.py` (`laad_oer_tekst` 500K, KD 300K, skills 50K, instelling 300K).
- **Juridische citatieplicht**: elke claim eist **bron + vindplaats + woordelijk citaat tussen
  aanhalingstekens** (OER/KD/examenreglement). Skills hebben een aangepaste citatie (bron + beroep +
  categorie + skill-naam) — verzonnen paginanummers zijn verboden. Templates: `_SYSTEEM_TEMPLATE`,
  `_MULTI_SYSTEEM_TEMPLATE`.
- **Vier hardgecodeerde instelling-lijsten** moeten synchroon blijven (afgedwongen door
  `tests/test_instelling_lijsten_sync.py`): `ingest._INSTELLINGEN`, `ingest._MAP_NAAM`,
  `scripts/seed_bulk.py:INSTELLINGEN`, `app_fastapi/main.py:_INSTELLING_KEYS`. Ontbreekt een
  nieuwe instelling in de seed-lijst → stil **0 studenten**.
- **Parser-sync met de parent**: de parse-helpers in `ingest.py` worden bewust gespiegeld naar
  `src/samenwijzer/oer_parsing.py`. Wijzig je ze hier, werk de parent-kopie mee bij (en omgekeerd).
- **Opleidingsnaam-opschoning** loopt uitsluitend via `opleiding.py` (geen streamlit-import):
  `nette_opleiding_naam(crebo, …)` = autoritatieve crebo-asset (gebouwd door
  `scripts/build_opleidingsnamen.py`), `schoon_opleiding_naam(...)` = token-fallback. Gedeeld door
  `chat.py`, `app_fastapi/data.py` en ingest — voer ruwe `opleiding`-strings nooit ongeschoond naar UI.
- **OER-onleesbaar-modus**: bij lege OER-fulltext bouwt `bouw_systeem` de prompt met KD +
  instellingsregelingen als hoofdbron; alleen zónder enige bron volgt `LAGE_RELEVANTIE_BERICHT`.

## Nieuwe instelling toevoegen (volgorde)

Volledige, geverifieerde procedure (4 lijsten, seed **als laatste appenden**, ingest, ≥2 OER's met
kerntaken, smoke-test, aparte expliciet te bevestigen re-seed): skill **`add-institution`**.
KD + skills zijn crebo-gedeeld (niet instelling-gebonden): overschrijf het landelijke KD nooit met een
instelling-meegeleverde variant.

## Bekende valkuilen

**Niet-geïndexeerde OER**: een student gekoppeld aan een OER met `geindexeerd=0` krijgt geen
kerntaken en (afhankelijk van het bestandspad) een leeg chatantwoord. Check:

```python
conn.execute("SELECT geindexeerd, bestandspad FROM oer_documenten WHERE id=?", (student["oer_id"],))
```

**Ontbrekend bronbestand**: `geindexeerd=1` betekent dat kerntaken zijn geëxtraheerd, niet dat het
PDF/MD nog op schijf staat. `chat.laad_oer_tekst()` valt terug op `<stem>.md` → PDF; ontbreken beide
→ `LAGE_RELEVANTIE_BERICHT`.

**Markitdown-conversie mislukt**: `converteer_naar_markdown()` is best-effort; bij falen blijft alleen
pdfplumber over (geen tabellen). Log: `Markitdown-conversie mislukt voor '…'`.

**Static-asset-cache (`app_fastapi/`)**: templates linken assets via `static_url()` (`?v=<mtime>`,
eenmalig berekend bij **opstart**). `uvicorn --reload` herstart alleen bij `.py`-wijzigingen — na een
edit aan alleen `app.css`/`app.js`/`chat.js` blijft de oude `?v=` staan: herstart de app of hard-refresh.

## Kennisbank

| Onderwerp | Bestand |
|---|---|
| Architectuur, datapipelines, module-rollen | `docs/ARCHITECTURE.md` |
| Multi-machine workflow + volledige commando-catalogus | `docs/ARCHITECTURE.md` |
| Specs & plannen | `docs/plans/` (specs én plannen wonen hier in dit subproject) |
| Sessielogs | `docs/sessions/` (lees de laatste vóór substantieel werk) |
| Route-overzicht + seed-volgorde | `README.md` |
| Beheertaken (dev-only `/beheer`) | `app_fastapi/main.py:_BEHEER_TAKEN`-tabel → `scripts/*.sh`, ingest, seed, bron_updates |
| Bronactualiteit-Action (wekelijks) | `../.github/workflows/bronactualiteit.yml` |
| Mockups | `docs/mockups/` |
| Presentatie (Slidev, poort 3030) | `presentatie/` — `./start.sh` |
