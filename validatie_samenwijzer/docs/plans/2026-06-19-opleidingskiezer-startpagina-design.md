# Opleidingskiezer op de publieke startpagina — ontwerp

**Datum:** 2026-06-19
**Status:** ontwerp (goedgekeurd, wacht op implementatieplan)
**Scope:** publieke FastAPI-frontend (`app_fastapi/`) — De digitale gids

## Probleem

Op de publieke startpagina stelt de student z'n eerste vraag in vrije tekst. De OER-picker
(`identificeer_oer_kandidaten`) vindt dan regelmatig **te veel kandidaten** en toont een platte,
rommelige lijst (tot 9 regels met bestandsnaam-achtige labels). Voor een student die niet weet wie
welke studiegids is, is die lijst geen hulp maar een drempel.

De gevraagde oplossing: een **cascade van keuzemenu's** (Instelling → Leerweg → Opleiding → Cohort)
zodat de student z'n studiegids gericht kan kiezen — met *schone* opleidingsnamen ("Kapper",
"Kok", "Timmerman") in plaats van de ruwe bestandsnaam-strings.

## Uitgangspunten (vastgelegd tijdens brainstorm)

- **Aanvullen, niet vervangen.** De vrije-tekst-start blijft de held van de pagina
  ("Geen zoekfunctie. Een gesprek."). De cascade is een optionele afkorting *plus* de nette
  disambiguatie-UI in de picker.
- **Opleiding-dropdown toont de losse kwalificatie-namen per crebo**, niet de brede dossier-naam.
  Elk item leidt naar één crebo.
- **Cohort is een optionele 4e stap**, alleen zichtbaar als er >1 cohort is; default = nieuwste.
- **Resolutie:** `(instelling, leerweg, crebo, cohort)` → exact één studiegids.

## Datagrondslag (geverifieerd tegen `data/validatie.db`, 2026-06-19)

- 729 OER-documenten, 9 instellingen, leerwegen BOL/BBL, alle `geindexeerd=1`.
- Schone opleidingsnamen bestaan **niet** in de DB; `oer_documenten.opleiding` is een ruwe
  bestandsnaam-string (`23030_BOL_2025__TIK-2025-OER-Laboratoriumtechniek`). Wel aanwezig: `crebo`.
- Gecombineerde naamdekking **93%** (683/729) uit twee bronnen:
  - `kwalificatiedossiers/crebolijst.xlsx`, kolom **Kwalificatie** (specifiek, voorkeur) — ~74%.
  - `kwalificatiedossiers/mapping.json` → `crebo_naar_dossier` (brede dossier-naam, fallback) — ~65%.
  - Beide bronnen leven in de **parent-repo** (build-context = repo-root).
- Resolutie-sleutel `(instelling, leerweg, crebo, cohort)` is **uniek**: 0 dubbele rijen.
- **21 randgevallen** waar één naam → meerdere crebo's binnen instelling+leerweg (bv. Da Vinci ·
  "Haarverzorging" = Kapper + Junior kapper). Dit treedt op waar de brede dossier-naam als fallback
  geldt. Deze worden **samen geladen** (de app vergelijkt al tot 3 studiegidsen) — geen extra menu.

## Ontwerp

### 1. Data — schone opleidingsnaam per crebo

Een opzoektabel `crebo → nette kwalificatie-naam`, met prioriteit:

1. `crebolijst.xlsx` kolom **Kwalificatie** (specifiek per crebo).
2. `mapping.json` → `crebo_naar_dossier` (brede dossier-naam).
3. Best-effort uit de ruwe `opleiding`-string (laatste redmiddel — nooit de ruwe string tonen;
   minimaal "crebo NNNNN" als zelfs dat faalt).

Een **klein build-script** leest beide parent-bronnen en schrijft een **gecommit JSON-asset** in het
subproject (bv. `data/opleidingsnamen.json`, of een passende plek conform bestaande assets). Runtime
leest alléén die JSON — de `.xlsx` is geen runtime-afhankelijkheid. Geen schemawijziging op
`oer_documenten`, geen koppeling met `ingest`.

Een helper in `db.py`/`data.py` laadt de JSON (gecachet) en levert `nette_naam(crebo) -> str`.

### 2. Backend

- **`GET /api/opleidingen`** → genest JSON-boompje:
  `instelling → leerweg → opleiding (naam + oer-verwijzing(en)) → cohorten (nieuwste eerst)`.
  Alleen `geindexeerd=1`. ~729 rijen is klein genoeg om in één call te sturen en client-side te
  filteren; geen chatty per-stap-calls. Bouwlogica in `db.py`/`data.py` (geen raw SQL in de route).
  Opleidingen alfabetisch; cohorten aflopend; een naam die meerdere crebo's binnen het nieuwste
  cohort dekt levert de bijbehorende oer-set (≤3) op.
- **Laden:** hergebruik `POST /api/kies` — maak `wachtende_vraag` optioneel zodat het ook werkt
  zónder voorafgaande vrije-tekstvraag. Endpoint laadt context in de sessie (`laad_context`) en geeft
  labels/oer_ids terug.

### 3. Frontend — startpagina

Onder het hero-vraagveld een **ingeklapt blok "Of kies direct je opleiding"** met afhankelijke
`<select>`-elementen:

- Instelling → Leerweg → Opleiding (alfabetisch, schone namen) → Cohort (alleen bij >1, default
  nieuwste) → knop **Start**.
- Elke keuze filtert de volgende; ongekozen niveaus blijven uitgeschakeld.
- **Start** laadt de studiegids via `/api/kies` en opent de chat-overlay met de cursor in het
  vraagveld (leeg). De student typt z'n vraag → bestaande `/api/chat`-stream.
- Styling: hergebruik de bestaande donker-thema-tokens en `app.css`-patronen; cache-bust na
  edits aan `app.css`/`app.js`/`chat.js`.

### 4. Dezelfde cascade ín de picker (kernfix van de gemelde pijn)

Wanneer de **vrije-tekst**-route te veel kandidaten oplevert (`modus: "kies"`), toont de picker
**niet** een platte lijst, maar **dezelfde cascade** (instelling → leerweg → opleiding) die naar één
studiegids versmalt. Zo profiteert ook de student die de shortcut op de startpagina niet ontdekt.
Dit is een **harde eis**, geen bijzaak — het relabelen van een platte 9-itemlijst lost het
*aantals*probleem niet op.

De cascade in de picker mag vóórgefilterd worden op de kandidaten die de picker al vond (dezelfde
componenten als sectie 3, met een ingeperkte dataset).

### 5. Tests

**Unit:**
- Naam-builder: `crebo → naam` met de drie-traps-prioriteit en de fallback-keten.
- Boom-builder: groepering instelling/leerweg/opleiding, cohorten aflopend, een multi-crebo-naam
  levert de sibling-set (≤3) onder het nieuwste cohort.

**UI-smoke (verplicht — twee paden):**
1. **Bug-pad:** brede vrije vraag → te veel kandidaten → cascade versmalt naar één OER →
   geciteerd antwoord. *Dit bewijst dat de gemelde pijn weg is.*
2. **Shortcut-pad:** Instelling → Leerweg → Opleiding → Start → vraag → geciteerd antwoord; check dat
   de cohort-stap alleen verschijnt bij >1 cohort.

Smoke-test via de publieke landing (zie geheugen: `/oer_vraag` niet direct bereikbaar; via landing +
`ALGEMEEN_WACHTWOORD`).

## Buiten scope (YAGNI)

- Geen multi-select-vergelijken via de dropdowns (de vrije-tekst/picker-route doet dit al tot 3).
- Geen onthouden van de keuze across sessies.
- Geen schemawijziging op `oer_documenten`.

## Architectuur-invarianten die gelden

- Geen business logic in `app_fastapi/`; geen raw SQL in routes — alle DB-toegang via `db.py`.
- AI-isolatie ongemoeid (deze feature raakt geen Anthropic-calls).
- Drie hardgecodeerde instelling-lijsten blijven synchroon (deze feature voegt geen instelling toe).

## Open punten voor het implementatieplan

- Exacte bestandsnaam/plek van de JSON-asset en het build-script (`scripts/`).
- Precieze copy/plaatsing van het inklap-blok en de Start-knop in `index.html`.
- Of de picker-cascade in dezelfde PR komt of als directe vervolg-PR (kernfix → bij voorkeur samen).
