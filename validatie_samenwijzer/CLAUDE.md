# CLAUDE.md

Guidance for Claude Code in dit subproject. Module-rollen, datapipelines, de volledige commando-catalogus
en de multi-machine-workflow staan in **`docs/ARCHITECTURE.md`**.

**Werkstijl:** voorzichtigheid boven snelheid. Maak aannames expliciet en vraag bij twijfel; lever de
minimale oplossing; raak alleen aan wat de taak vereist (dode code: melden, niet verwijderen); vertaal
taken naar verifieerbare doelen en noem bij multi-step kort plan + check per stap.

## Wat dit project is

Standalone **FastAPI-app** (`app_fastapi/`) waarin MBO-studenten en mentoren chatten met hun OER via
Claude streaming met de **volledige OER als context** (1M-tokenvenster). Het landelijke
**kwalificatiedossier (KD)** wordt mee-ingebed als aanvullende bron; de OER blijft leidend. Subproject
van de `samenwijzer`-monorepo met eigen `pyproject.toml`, `.venv` en database.

De **publieke startpagina** (`/`) is de ingang: vrije vraag of opleidingskiezer-cascade →
`identificeer_oer_kandidaten` → modus `chat` (1 kandidaat), `kies` (meerdere) of `intake` (geen) → daarna
chat-streaming. `/student`, `/mentor`, `/beheer` zitten achter login en delen die kern.

De Streamlit-frontend (`app/`) is **geretired**; `app_fastapi/` draait in productie als `digitale-gids`
op Fly (`Dockerfile.fastapi`). Er is geen vector store (full-document context, `bron_catalogus.py:_MAX_OER_TEKST_TEKENS`).

## Commando's

Vanuit `validatie_samenwijzer/`:

```bash
./start.sh                                                  # app op :8504 (PORT=… / --no-reload); checkt .env
uv sync --extra dev && uv run python -m pytest             # tests
uv run python -m pytest tests/test_ingest.py::test_parseer_bestandsnaam_davinci -v  # één test
uv run ruff check --fix src/ app_fastapi/ scripts/ && uv run ruff format src/ app_fastapi/ scripts/
uv run python -m validatie_samenwijzer.ingest --alles      # (her)indexeer OERs (+ --reset, --instelling <key>)
uv run python -m validatie_samenwijzer.sync_afgeleid --alles  # KD + skills reconciliëren
OEREN_PAD=../oeren uv run python scripts/vergelijk_modellen.py --uit <json>  # Sonnet vs Haiku: kosten + citaten
```

Geen CI-gate voor dit subproject (root-`ci.yml` raakt de eigen `.venv` niet): draai lint, format en tests
**lokaal** vóór je commit. `tests/conftest.py` zet `SESSION_SECRET`, `ALGEMEEN_WACHTWOORD` en
`COOKIE_HTTPS_ONLY=0` zelf en reset de `_ai`-client- en crebo-naam-cache.

## Omgeving & deploy

`.env` in `validatie_samenwijzer/` (zie `.env.example`). `SESSION_SECRET` en `ALGEMEEN_WACHTWOORD` zijn
fail-closed; lokaal over http is `COOKIE_HTTPS_ONLY=0` nodig; `BEHEER_ENABLED` alleen op dev-machines.
Extra gelezen paden: `KWALDOSSIERS_PAD`, `SKILLS_PAD`, `OPLEIDINGSNAMEN_PAD`, `SESSIE_DB_PATH`.
**Tesseract** is nodig voor ingest: `sudo apt install tesseract-ocr tesseract-ocr-nld`.

Deploy-commando: root-`CLAUDE.md`. `validatie.db` en `data/skills` zitten **in het image** — na re-ingest of
re-seed is een nieuwe deploy nodig. Fly-secrets: `SESSION_SECRET`, `ALGEMEEN_WACHTWOORD`, `ANTHROPIC_API_KEY`.

## Architectuur-invarianten (niet breken)

- **AI-isolatie**: alle Anthropic-calls via `_ai._client()` (dwingt 30s-timeout af); nooit
  `anthropic.Anthropic()` direct. `chat.py` is de enige module met streaming. Modellen: chat/intake
  `claude-sonnet-5-5`, vervolgvragen `claude-haiku-5-5` (best-effort), `skills_bron._MATCH_MODEL` nog
  `claude-haiku-4-5-20251001`. Haiku 5.5 kost 5× méér boven 100K prompttokens (p90 OER ≈ 112K): de
  hoofdchat blijft op Sonnet tot `vergelijk_modellen.py` op grotere schaal is gemeten.
- **Geen business logic in `app_fastapi/`**; geen raw SQL in routes — DB alleen via `db.py`
  (`get_connection()`). `context.py` en `data.py` zijn dunne orchestrators over `chat.py`/`db.py`.
- **Toegangspoort**: middleware `_toegangspoort` zet de héle app (ook `/`) achter `ALGEMEEN_WACHTWOORD`;
  `/api/*` krijgt 401, pagina's een redirect. Alleen `/static` is vrij.
- **Gesprek-module**: `gesprek.py` is de enige eigenaar van de gesprekshistorie (ruwe antwoordtekst
  mét bronnenmarker; saneren voor het model, UI-view, cap, afgebroken beurten via `LopendeBeurt`).
  Routes en `chat.py` raken de `{"role","content"}`-lijst niet direct aan; opslagsleutel in
  `sessies.db` blijft `chat_history`.
- **Sessiestate server-side** (`sessie.py`, SQLite `data/sessies.db`, TTL 6 uur; cookie draagt alleen
  een `sid`). Dus **één Fly-machine** en de store overleeft geen redeploy. De middleware bewaart alleen
  bij niet-GET-requests (behalve `/api/chat`, dat zelf post-stream bewaart, en `/api/vervolgvragen`):
  een GET die de sessie muteert moet `bewaar_sessie()` expliciet aanroepen.
- **Vier chat-bronnen**, allemaal full-document: OER (leidend) + KD + skills + instellingsregelingen
  (laders + caps in `bron_catalogus.py`: 500K / 300K / 50K / 300K). Alleen `BronCatalogus` kent de
  naam van een bron (promptkop + markertitel + register); `chat.bouw_prompt` is de enige
  prompt-builder. OER-onleesbaar → KD + regelingen als hoofdbron; zonder enige bron volgt
  `LAGE_RELEVANTIE_BERICHT`.
- **Juridische citatieplicht**: elke claim eist bron + vindplaats + woordelijk citaat (OER/KD/
  examenreglement); skills citeren bron + beroep + categorie + skill-naam. Verzonnen paginanummers
  zijn verboden (`chat._SYSTEEM_TEMPLATE`).
- **Instelling-registry**: alle per-instelling-kennis leeft in `instellingen.py`; consumenten leiden
  daar hun mapping van af (bewaakt door `tests/test_instelling_lijsten_sync.py`). `INSTELLINGEN` is de
  seed-volgorde (gedeelde `Random(2026)`): append alleen aan het eind. Procedure: skill `add-institution`.
  KD + skills zijn crebo-gedeeld: overschrijf het landelijke KD nooit met een instellingsvariant.
- **Webzoek-tools** (alleen `chat.stream_antwoord`) zijn gescoped via `allowed_domains`. Eén domein dat
  de Anthropic-crawler blokkeert geeft een 400 op de héle call: voeg alleen geverifieerd-crawlbare
  domeinen toe.
- **Parser-sync met de parent**: parse-helpers in `ingest.py` worden gespiegeld naar
  `src/samenwijzer/oer_parsing.py`; wijzig beide samen.
- **Opleidingsnamen** altijd via `opleiding.py` (`nette_opleiding_naam` / `schoon_opleiding_naam`);
  nooit ruwe `opleiding`-strings naar de UI.

## Bekende valkuilen

- **Niet-geïndexeerde OER** (`geindexeerd=0`): geen kerntaken en mogelijk een leeg chatantwoord. Check
  `SELECT geindexeerd, bestandspad FROM oer_documenten WHERE id=?`.
- **Ontbrekend bronbestand**: `geindexeerd=1` zegt niets over aanwezigheid op schijf.
  `bron_catalogus.laad_oer_tekst()` valt terug `<stem>.md` → PDF; ontbreken beide →
  `LAGE_RELEVANTIE_BERICHT`.
- **Curio 27052/27060**: de st- en vg-versie delen één DB-sleutel; vg is geforceerd en een
  `ingest --alles` kan dat terugdraaien.
- **Static-asset-cache**: `static_url()` berekent `?v=<mtime>` eenmalig bij opstart; na een edit aan
  alleen `app.css`/`app.js`/`chat.js` herstart de app of hard-refresh.
- **Markitdown-conversie** is best-effort; bij falen blijft alleen pdfplumber over (geen tabellen).
- **Hangende chat-stream** (2026-10-29: proces zat vast vóór de Anthropic-call, zonder timeout):
  `/api/chat` stuurt bij stilte elke 15s een `ping`-event (Fly-proxy kapt ~60s stilte) en breekt na
  `CHAT_MAX_SECONDEN` (default 90) af met `error: timeout` + stack van de hangende thread in het log.
  Handmatige thread-dump: `kill -USR1 <pid>` op de machine (faulthandler → stderr → Fly-logs).

## Kennisbank

`docs/ARCHITECTURE.md` (architectuur, commando-catalogus) · `docs/uitleg-digitale-gids.html`
(interactieve, wervende uitleg die laat zien hoe de Digitale Gids werkt) · `CONTEXT.md` + `../CONTEXT-MAP.md`
(glossary) · `gebruikers.txt` (test-accounts, wachtwoord `Welkom123`, door seed geschreven — niet
handmatig wijzigen) · `docs/plans/` (specs én plannen) · `docs/sessions/` (lees de laatste vóór
substantieel werk) · `README.md` (routes + seed-volgorde) · `graphify-out/` (kennisgraaf, gitignored —
structuurvragen eerst via `/graphify`).
