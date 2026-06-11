# Architectuur & operationele referentie

Diepe referentie voor `validatie_samenwijzer`. `CLAUDE.md` houdt de dagelijkse essentials +
invarianten; dit bestand bevat de volledige module-rollen, datapipelines en multi-machine-workflow.

> **Frontend-status (juni 2026)**: de Streamlit-frontend (`app/`) is **geretired**; `app_fastapi/`
> (poort 8504) is DE frontend. De Python-kern (`chat.py`, `db.py`, `_ai.py`, `auth.py`) is gedeeld
> en UI-vrij. Een enkele verwijzing naar `app/`/`st.session_state` markeert bewust de geretirede
> Streamlit-laag. Spec/plan: `docs/plans/2026-06-10-fastapi-migratie-*.md`.

## Commando's (volledige catalogus)

Alle commando's vanuit `validatie_samenwijzer/`. De dagelijkse set staat in `CLAUDE.md`; hieronder
de volledige lijst inclusief data-pipelines.

```bash
# App + dev
uv run uvicorn app_fastapi.main:app --port 8504 --reload   # vereist SESSION_SECRET + ALGEMEEN_WACHTWOORD
uv sync --extra dev && uv run python -m pytest
uv run python -m pytest tests/test_ingest.py::test_parseer_bestandsnaam_davinci -v
uv run ruff check src/ app_fastapi/ scripts/
uv run ruff check --fix src/ app_fastapi/
uv run ruff format src/ app_fastapi/ scripts/              # geen CI-gate hier — draai lokaal vóór commit

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
# `ingest` en `watcher` zijn ook geregistreerd als project scripts (pyproject.toml) —
# `uv run ingest --alles` en `uv run watcher` werken identiek.

# Seed testdata
uv run python scripts/seed.py        # 3 studenten + 2 mentoren (dev-demo)
uv run python scripts/seed_bulk.py   # ~1700 studenten over geïndexeerde OERs (vereist eerst `ingest --alles`)

# Bestandsnamen aanvullen + indexeren (alles-in-één)
./scripts/verwerk_oers.sh --preview  # droge run
./scripts/verwerk_oers.sh            # hernoem + indexeer

# Multi-machine setup: sync oeren vanuit Box + ingest + bulk-seed
./scripts/bootstrap.sh                  # default = bulk-seed (~1700 studenten)
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
`push_oeren.sh`, `check_bootstrap.sh`) zijn supporting tooling — bekijk de bestanden voor gebruik.

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

Route `GET /beheer` (template `beheer.html`) + `GET /api/beheer/run` in `app_fastapi/main.py`
bundelen re-ingest, seed en DB-status. Bereikbaar als `BEHEER_ENABLED=true` staat in `.env` —
anders geeft de route 404. Taken draaien als subprocess op de host; de stdout wordt live als SSE
(`text/event-stream`) naar de pagina gestreamd. Niet aanzetten op gedeelde servers — de allowlist
omvat rclone-sync, ingest en seed-scripts.

Veiligheid van `/api/beheer/run`: dubbele gate (`BEHEER_ENABLED` + de algemene toegangspoort),
een vaste commando-allowlist (`_BEHEER_TAKEN`, lijst-vorm `Popen` zonder shell), instelling-scope
gevalideerd tegen `_INSTELLING_KEYS`, en `cwd` hard op de repo-root.

De pagina toont DB-status (`_beheer_status()`: # OERs per instelling, # geïndexeerd, laatste
ingest-run uit tabel `ingest_runs`) en draait de allowlist-taken `_BEHEER_TAKEN`: `sync_oeren` +
`kd_sync` (rclone vanaf Box), `ingest_alles`/`ingest` (per instelling, + optionele `--reset`) en
`seed_bulk`/`seed_minimal`.

## Data-laag

**`db.py`** — SQLite schema en alle queries als losse functies, geen ORM. Schema: `instellingen`,
`oer_documenten`, `kerntaken`, `mentoren`, `mentor_oer`, `studenten`, `student_kerntaak_scores`,
`ingest_runs`, `instelling_documenten` (instellingsbrede regelingen — zie hieronder).
`INSTELLING_SOORTEN` (module-constante) is de **enige bron van waarheid** voor de bekende
instellingsbrede document-soorten → citeer-label; een nieuwe soort toevoegen = één regel daar,
geen schema-migratie (soort-validatie staat in `voeg_instelling_document_toe`, niet in een DB-CHECK).
Verbinding via `get_connection()` met WAL-modus en `check_same_thread=False`.

**Verbinden vanuit de app**: routes openen de DB via een module-lokale `_conn()`-helper
(`app_fastapi/main.py` en `context.py`) die `db.get_connection(DB_PATH)` aanroept; scripts en tests
gebruiken `db.get_connection()` direct. (De geretirede Streamlit-wrapper `_db.py` met
`@st.cache_resource` bestaat niet meer.)

## Ingestie-pipeline (`ingest.py`)

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

## Sessiemodel

Server-side sessie in `app_fastapi/sessie.py`: een `Sessie`-dataclass per gebruiker, bewaard in
een SQLite-store met TTL die proces-restarts overleeft. De browser houdt alleen de door
`SESSION_SECRET` ondertekende `SessionMiddleware`-cookie vast met daarin een `sid`-sleutel; die
`sid` wijst naar het server-side `Sessie`-object. `get_sessie(request)` laadt/maakt het object,
write-through naar de store gebeurt via middleware (mutaterende GET-routes roepen `bewaar_sessie()`
expliciet aan).

Relevante velden: `toegang` (algemene poort gepasseerd), `rol` (`"student"`/`"mentor"`/`None`),
`gebruiker` (`{id, naam, studentnummer?}`), `oer_ids` + `oer_systeem` (geladen context),
`oer_labels`, `oer_onleesbaar`, `chat_history`, en mentor-specifiek `actieve_student`. Login
(`POST /login`) vult deze velden; `reset()`/`uitloggen()` wissen ze.

Rolbewaking: de `_eis(request, rol)`-helper in `main.py` redirect naar `/login` als de rol niet
klopt; mentor-routes checken bovendien IDOR (`/mentor/student/{id}` weigert studenten buiten de
eigen koppeling).

## Authenticatie

Wachtwoorden opgeslagen als PBKDF2-HMAC-SHA256 (`salt_hex:hash_hex`). Legacy bare-SHA-256 hashes
worden nog geaccepteerd en bij volgende login automatisch gemigreerd. Seed-wachtwoord voor alle
test-accounts: **Welkom123**. Login: studenten op studentnummer, mentoren op naam.

## Routes & frontend (`app_fastapi/`)

De volledige route-tabel (publieke OER-vraag, login, student-, mentor- en beheer-routes) staat in
`README.md`. De geretirede Streamlit-pagina's (`app/pages/*.py`) zijn vervangen; verwijzingen ernaar
elders in dit document beschrijven de gedeelde Python-kern, niet een bestaande UI-laag.

## FastAPI-frontend (`app_fastapi/`)

DE frontend sinds juni 2026. Vervangt **alleen de UI-schil** en hergebruikt de Python-laag
(`chat.py`, `db.py`, `_ai.py`, `auth.py`) **ongewijzigd** — die importeren geen streamlit.

- `main.py` (routes + SSE-chat), `context.py` (OER-context-orchestrator: OER + KD + skills +
  instellingsdocumenten per rol via `PUBLIEK/STUDENT/MENTOR_SOORTEN` + web-zoek-domeinen),
  `auth.py` (login-hergebruik), `data.py` (voortgang/studenten/profiel), `sessie.py` (server-side
  sessie via signed-cookie `sid`), `static/chat.js` (escapende markdown-renderer + SSE + viewer —
  één plek voor de security-gevoelige rendering), templates.
- **Toegangspoort**: de hele app achter `ALGEMEEN_WACHTWOORD` (`.env`); login student/mentor erachter.
- Streaming via `text/event-stream`; dezelfde `_ai._client()` → prompt-cache blijft werken.
- Tests: `tests/test_fastapi_poc.py`.
- Productie-`digitale-gids` draait `Dockerfile.fastapi` op Fly; vereist Fly-secret `SESSION_SECRET`.
  Plan: `docs/plans/2026-06-08-fastapi-poc-publieke-oer-chat.md` + `2026-06-10-fastapi-migratie-*.md`.

## AI-isolatie (detail)

Alle Anthropic-calls lopen via `_ai._client()`. `chat.py` is de enige module met streaming-aanroepen.
Nooit `anthropic.Anthropic()` direct instantiëren. De client wordt gebouwd met
`_CLIENT_OPTS = {timeout: httpx.Timeout(30.0, connect=10.0), max_retries: 2}` zodat het 30s-contract
écht wordt afgedwongen (de SDK-default read is 600s); bij streaming is de read-timeout per
inter-event, dus een lang antwoord wordt niet afgebroken — alleen een vastgelopen stream.

## OER-chat-flow

`chat.py` levert de system-prompt-bouwers; `app_fastapi/context.py:laad_context()` is de UI-loze
orchestrator die alle chat-routes (publiek `/`, `/student`, `/mentor/student/{id}`) gebruiken:

1. **Context bouwen** (`bouw_gecombineerd_systeem`) — `laad_context()` laadt per gekozen OER de
   volledige tekst + KD + skills + instellingsbronnen en combineert tot 3 OER's in één system
   prompt met blok-headers `=== OER 1: … ===`. Bij één OER delegeert `bouw_gecombineerd_systeem`
   naar `bouw_systeem` (single-OER pad), dus de student-/mentor-route (één gekoppelde OER) en de
   publieke multi-OER-vraag lopen door dezelfde functie.
2. **Intake** (`genereer_intake_antwoord` + `identificeer_oer_kandidaten`) — fallback in
   `POST /api/vraag` zolang nog geen OER gekozen is. `identificeer_oer_kandidaten()` scoort op
   crebo (+3), leerweg (+2), cohort (+2), opleidingswoorden (+1, max 2), instelling (+1) en
   bepaalt de modus (`chat` bij één match, `kies` bij meer, `intake` bij geen).

`laad_oer_tekst()` voorkeursvolgorde: `<stem>.md` (markitdown-output) → bron-`.md` →
pdfplumber over PDF. Hard cap: `_MAX_OER_TEKST_TEKENS = 500_000` tekens.

**Gespreksgeschiedenis & caching**: `bouw_berichten()` saneert de historie (lege/mislukte beurten
weg, alternerende rollen, onbeantwoorde laatste user-beurt vervangen) zodat één gefaalde AI-call de
sessie niet kan blokkeren met een API 400. `genereer_antwoord()` zet `cache_control` met **1h-TTL**
op het system-blok én een cache-breakpoint op de laatste beurt (`_messages_met_cache`), zodat de
volledige OER-context én de gespreksgeschiedenis bij vervolgvragen uit de prompt-cache worden gelezen
i.p.v. elke beurt vol betaald — overleeft leespauzes >5 min tussen vragen.

**Antwoord-rendering**: het AI-antwoord streamt als SSE naar `app_fastapi/static/chat.js`, dat de
markdown client-side rendert via een **escapende** renderer — één plek voor de security-gevoelige
weergave, zodat een letterlijke `<`, code of HTML in het antwoord niet als markup uitvoert.
Markdown-blockquotes worden als citaat-pull-quotes gestyled (`app.css`).

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
`_MAX_INSTELLING_TEKST_TEKENS = 300_000`). `context.laad_context()` haalt de paden uit
`instelling_documenten` (`db.haal_instelling_document_op`), gefilterd op de rol-soorten
(`PUBLIEK/STUDENT/MENTOR_SOORTEN`), en geeft `(label, tekst)`-paren door als `instelling_bronnen`
aan `bouw_gecombineerd_systeem`, dat ze als blokken `=== LABEL (instelling) ===` in de system
prompt zet. Zie de Instellingsbrede-bron-sectie verderop.

**OER-onleesbaar-modus**: is de OER-fulltext leeg (gescande PDF zonder tekstlaag), dan bouwt
`bouw_systeem` de prompt in een aangepaste modus die het kwalificatiedossier + instellingsregelingen
als hoofdbron neemt (i.p.v. de OER) en de citatie-instructie daarop aanpast (drie template-varianten:
`_PRIMAIRE_BRON_*`, `_KD_INSTRUCTIE_*`, `_OER_SECTIE_*`). `context.laad_context()` neemt de OER
tóch op zolang er een KD óf instellingsbron is en zet dan `oer_onleesbaar=True`; de route geeft die
vlag door aan de template → banner dat de OER niet machine-leesbaar is. Alleen zónder enige bron
geeft `laad_context` een lege system-prompt terug en volgt `LAGE_RELEVANTIE_BERICHT`. Spec/plan:
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
**eigen bron** in de citatie (een examenreglement is even juridisch bindend als de OER). Voor de
**skills-taxonomie** geldt een **aangepaste citatie** (een taxonomie heeft geen secties of pagina's):
bron + beroep + categorie + exacte skill-naam, bijv. *Volgens de ESCO-skillstaxonomie hoort bij het
beroep "kok" de essentiële skill "kooktechnieken gebruiken"*. Het template verbiedt expliciet
verzonnen paginanummers bij skills. Markdown-blockquotes uit het AI-antwoord renderen via CSS als
pull-quote citaten. Spec: `docs/specs/2026-05-06-publieke-oer-citaten-en-pdf-design.md` (vanuit repo-root).

**OER-bestand bekijken/downloaden**: de viewer in `static/chat.js` haalt het bronbestand op via
`GET /api/oer/{oer_id}/bestand` (FastAPI `FileResponse`). Dezelfde route bedient zowel de publieke
vraag als de student-studiegids; toegang loopt via de sessie-`oer_ids`, niet via een vrij
bestandspad.

## OER-bestanden

`oeren/` (root-tree, via `OEREN_PAD=../oeren`) is grotendeels **getrackt in git** — behalve de vier
niet-publieke instellingen (`davinci_oeren/`, `kwic_oeren/`, `graafschap_oeren/`, `deltion_oeren/`),
die via de root-`.gitignore` **Box-only** zijn (rechten — zie Multi-machine workflow). Structuur: één
submap per instelling (`davinci_oeren/`, `rijn_ijssel_oer/`,
`talland_oeren/`, `aeres_oeren/`, `utrecht_oeren/`, `kwic_oeren/` = Koning Willem I College).
Daarnaast `oer_algemeen/` voor instelling-overstijgende documenten. De instelling-keys leven in
**drie hardgecodeerde lijsten** die synchroon moeten blijven: `ingest._INSTELLINGEN`/`_MAP_NAAM`,
`scripts/seed_bulk.py:INSTELLINGEN` en `app_fastapi/main.py:_INSTELLING_KEYS` — ontbreekt een nieuwe
instelling in de seed-lijst, dan krijgt ze stil 0 studenten. Geïndexeerde OERs staan als
`geindexeerd=1` in `oer_documenten`. Studenten met `oer_id` naar niet-geïndexeerde OERs krijgen
geen chatantwoorden.

Per instelling kan een `_instelling/`-submap (`oeren/<inst>_oeren/_instelling/<soort>.{pdf,md}`)
de instellingsbrede regelingen bevatten; de bestandsnaam-stem is de `soort` (moet in
`db.INSTELLING_SOORTEN` staan). `ingest._verwerk_instelling_documenten` indexeert die apart van de
gewone OER-iteratie (`_INSTELLING_SUBMAP` wordt overgeslagen door de platte OER-loop).

## Instellingsbrede bron (aanvullende bron)

Naast de OER, het KD en skills is er een **vierde chat-bron**: instellingsbrede regelingen
(examenreglement, begeleidings-/welzijnsbeleid, studentenstatuut, algemene informatie). Anders dan
KD/skills (crebo-gekoppeld) hangt deze bron aan de **instelling**, dus elke student/mentor van die
school krijgt ze automatisch mee. Soorten staan in `db.INSTELLING_SOORTEN` en zijn **uitbreidbaar
met één regel** (geen schema-migratie). Documenten leven in `oeren/<inst>_oeren/_instelling/`,
worden geïndexeerd in `instelling_documenten` en in de chat als eigen blok + eigen citatie-bron
opgenomen (zie OER-chat-flow en de Juridische citatieplicht hierboven). Plan/onderbouwing:
`docs/plans/2026-06-02-instellingsbrede-bron.md`.

## Kwalificatiedossiers (aanvullende bron)

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

## Skills-taxonomie (aanvullende bron)

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

## Afgeleide bronnen automatisch bijwerken (reconciliatie)

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
