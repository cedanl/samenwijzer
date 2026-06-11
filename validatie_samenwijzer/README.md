# Validatie Samenwijzer

Standalone **FastAPI-app** ("De digitale gids") waarmee MBO-studenten en mentoren conversationeel kunnen chatten met hun OER (Onderwijs- en Examenregeling) via volledige Claude-documentcontext, aangevuld met landelijke kwalificatiedossiers, instellingsbrede regelingen en een skills-taxonomie (CompetentNL/ESCO) — zodat de chat ook "welke skills heb ik nodig voor mijn beroep?" beantwoordt.

> De Streamlit-frontend (`app/`) is per juni 2026 **geretired**; `app_fastapi/` is DE frontend en
> draait in productie als `digitale-gids` op Fly. De Python-kern (`chat.py`, `db.py`, `_ai.py`,
> `auth.py`) is ongewijzigd gedeeld.

## Vereisten

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- Tesseract OCR (`sudo apt install tesseract-ocr tesseract-ocr-nld`)
- `.env` in de projectmap (zie hieronder en CLAUDE.md)

### Verplichte env-variabelen

```
ANTHROPIC_API_KEY=sk-ant-...   # alle AI-functies
SESSION_SECRET=...             # signeert de sessie-cookie (fail-closed: geen default)
ALGEMEEN_WACHTWOORD=...         # toegangspoort vóór de hele app (fail-closed: geen default)
DB_PATH=data/validatie.db      # default
OEREN_PAD=../oeren             # default (root-oeren/ hergebruikt)
BEHEER_ENABLED=true            # optioneel: activeer /beheer (alleen op dev-machines)
```

Zonder `SESSION_SECRET` of `ALGEMEEN_WACHTWOORD` weigert de app bewust te starten.

## Starten

Uitvoeren vanuit `validatie_samenwijzer/`:

```bash
uv sync
uv run uvicorn app_fastapi.main:app --port 8504 --reload
```

De app draait op http://localhost:8504. De hele app zit achter het **algemene wachtwoord**
(`/toegang`). Daarachter is de publieke OER-vraag op `/` zonder login bereikbaar; student/mentor
loggen in via `/login`.

Login-wachtwoord voor alle geseede accounts: **Welkom123**. Studentnummers, mentornamen en de exacte
OER-koppeling worden bij elke seed-run weggeschreven naar `gebruikers.txt` (niet handmatig wijzigen).

| Rol | Inlogwaarde (voorbeeld) | Identifier-vorm |
|---|---|---|
| student | `100201` (Hamza Vermeer) | studentnummer |
| mentor | `Mark Kaur (25915)` | naam met nummer tussen haakjes |

## OERs indexeren én testdata seeden

De volgorde is belangrijk: `seed_bulk` koppelt studenten aan OER-records die `ingest` aanmaakt.
Zet daarom eerst je PDFs op de juiste plek en draai dan in volgorde:

```bash
# 1. Zet PDFs in oeren/<instelling>_oeren/ (utrecht_oeren, davinci_oeren, …)
# 2. Bestandsnamen aanvullen met crebo/leerweg/cohort + indexeren
./scripts/verwerk_oers.sh              # hernoem + indexeer (productie)
./scripts/verwerk_oers.sh --preview    # droge run

# 3. Synthetische gebruikers seeden (vereist een geïndexeerde DB)
uv run python scripts/seed.py           # 3 studenten + 2 mentoren (sanity check)
uv run python scripts/seed_bulk.py      # ~1700 studenten over de geïndexeerde OERs

# 4. Afgeleide bronnen (KD + skills) reconciliëren — bouwt alleen ontbrekende
uv run python -m validatie_samenwijzer.sync_afgeleid --alles
```

`bootstrap.sh` doet stap 4 automatisch, en de `watcher` reconcilieert per crebo zodra OER-bestanden
wijzigen.

`seed_bulk` faalt met instructie als stap 2 niet is gedraaid. Het rapporteert expliciet welke
instellingen overgeslagen zijn (typisch wanneer `extraheer_kerntaken` geen kerntaken uit de PDF kan
halen) — dan ontbreekt voor die instelling testdata zonder dat dat stilletjes wordt verstopt achter
wees-koppelingen.

## Tests en kwaliteit

Geen CI-gate voor dit subproject (de root-`ci.yml` raakt de eigen `.venv` niet) — draai lokaal:

```bash
uv sync --extra dev && uv run pytest
uv run ruff check --fix src/ app_fastapi/ scripts/ && uv run ruff format src/ app_fastapi/ scripts/
```

## Route-overzicht (`app_fastapi/main.py`)

| Route | Rol | Functie |
|---|---|---|
| `/toegang` | poort | Algemeen wachtwoord vóór de hele app |
| `/` | publiek | Conversationele OER-vraag zonder login (kiest/laadt de juiste OER) |
| `/login`, `/uitloggen` | beide | Studentnummer of mentornaam + wachtwoord |
| `/student` | student | Chat met eigen OER via volledige documentcontext |
| `/student/studiegids` | student | Volledig OER inzien of downloaden |
| `/student/voortgang` | student | Voortgang, BSA, scores |
| `/mentor` | mentor | Studentenlijst van eigen koppeling |
| `/mentor/student/{id}` | mentor | Begeleidingssessie: profiel + OER-chat + OER-viewer (IDOR-guard) |
| `/beheer` | dev-only | Beheertaken draaien (alleen met `BEHEER_ENABLED=true`) |

Zie [CLAUDE.md](CLAUDE.md) en [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) voor uitgebreide
architectuurdocumentatie.
