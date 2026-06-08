# Sessie-log 2026-06-08 — OER-bronkwaliteit (Deltion/davinci/utrecht) + FastAPI-POC

*Subproject: `validatie_samenwijzer` ("De digitale gids", `digitale-gids.fly.dev`).*
*Twee sporen: (A) OER-rendering & databron-opschoning, (B) een FastAPI-frontend-POC naast Streamlit.*

## A. OER-bronkwaliteit (PR #170–#173, gedeployed)

### Deltion: gestructureerde markdown i.p.v. platte tekst (#170)
Klacht: de Deltion-studiegids-viewer toonde één muur tekst. Oorzaak: `fetch_deltion.py`
haalde de rijk-gestructureerde SQill-HTML op maar sloeg 'm plat met BeautifulSoup
`get_text()` — bewust, omdat `extraheer_kerntaken` de `B1-K1-W1`-codes anders niet vond.
- **Fix**: `fetch_deltion.py` converteert nu via **markitdown** naar gestructureerde markdown
  (koppen, tabellen, lijsten, links, **logo behouden** — Ed wilde bron-getrouw).
- **`_KT_PATROON`** (in `ingest.py` én gespiegeld in parent `src/samenwijzer/oer_parsing.py`)
  tolereert nu een optionele markdown lijst-marker (`* `/`+ `/`- `), zodat kerntaken in
  markitdown-lijstitems blijven extracten. Geverifieerd over **alle 162** Deltion-OER's:
  identieke kerntaken-code-sets, 0 regressies.
- `styles.render_oer_markdown` als viewer-vangnet voor resterende platte `.md`.
- 162 Deltion-OER's opnieuw opgehaald + her-ingest; naar Box gesynct.

### davinci/utrecht bronkwaliteit (#171)
- **ingest koos de tekstloze (gescande) Examenplan-PDF** boven de tekstrijke MJP. `_resolveer_oer`
  werkt de `bestandspad` nu pas ná bewezen leesbare tekst bij (PDF-prioriteit behouden) → 25690
  (BBL+BOL) en 25182 (BOL) wijzen nu naar hun MJP; 0 geïndexeerde davinci-OER's zonder tekst.
- `chat.laad_oer_tekst` valt nu bij een leeg `.md`-broertje terug op pdfplumber.
- 22 lege davinci-`.md`-wezen opgeruimd (lokaal + Box); utrecht-27002 ("Dataregister") was geen
  OER → uit git + DB + Box verwijderd.

### Kerntaken-opschoning (#172, #173)
- **Tabelfragment-filter**: namen met een `|` (markdown-tabelrij waar de code toevallig vooraan
  staat) worden geweerd in `extraheer_kerntaken` (ingest + parent gespiegeld). 3 garbled davinci-
  rijen opgeschoond.
- **Volledige sync** van `extraheer_kerntaken` parent↔validatie: de parent-kopie miste de garbled-
  filters (≥12 letters/lowercase) + dedup; nu functioneel identiek. 504 parent-tests groen.

Alles gedeployed naar Fly (`digitale-gids`), live geverifieerd (Deltion-studiegids rendert
gestructureerd in productie).

## B. FastAPI-POC: alternatieve frontend (PR #174, #175)

**Waarom**: de mock-up-kwaliteit (`docs/mockups/oer-vraag-landing.html`) is in Streamlit
structureel niet haalbaar (geen DOM-bezit, geen page-JS, rerun-model, iframe-sandbox). De
Python-"brein"-laag is al UI-vrij, dus de UI is te vervangen zonder het brein te herschrijven.
Plan: `docs/plans/2026-06-08-fastapi-poc-publieke-oer-chat.md`.

**Resultaat** (`validatie_samenwijzer/app_fastapi/`, draait náást Streamlit):
- **Publiek** (mock-up-landing + OER-chat, intake → kiezer → SSE-streaming), **student**
  (assistent, studiegids-viewer, voortgang), **mentor** (studentenlijst, begeleidingssessie).
- **Toegangspoort** (`ALGEMEEN_WACHTWOORD` uit `.env`): hele app achter een gedeeld wachtwoord
  (instellingen met afgeschermde OER). Login student/mentor (PBKDF2 via `auth.py`, ongewijzigd).
- **Alle bronnen** zoals Streamlit: OER + KD + skills (ESCO/CompetentNL) + instellingsdocumenten
  per rol (`PUBLIEK/STUDENT/MENTOR_SOORTEN` in `context.py`) + web-zoek-fallback (instelling-
  website via `web_search`/`web_fetch`).
- **Voortgang**: BSA in **studiepunten** (X/60), kerntaken met **geneste werkprocessen** als
  CSS-bars (geen chart-lib).
- **Security**: IDOR-guard (mentor → eigen studenten), OER-download-authz (alleen sessie-OER's),
  escape-first + tag-whitelist markdown-renderer (geen externe JS/CDN). Beide XSS-findings uit de
  automatische review verholpen + browser-geverifieerd.
- `chat.py`/`db.py`/`_ai.py`/`auth.py` **ongewijzigd** hergebruikt. Streamlit (8503) ongemoeid.
- 13 POC-tests, lint clean. Browser-review (desktop + mobiel) over alle pagina's; gefixt: mobiele
  ingelogde nav (te brede CSS-regel), `<hr>`-rendering, img-alt-escape.

Lokaal: `uv run uvicorn app_fastapi.main:app --port 8504`. `Dockerfile.fastapi` is voorbereid maar
**niet** aan `fly.toml` gekoppeld — de productie-deploy gebruikt nog de Streamlit-`Dockerfile`.

## Open (FastAPI-POC → vóór deploy)
- Sessiestore is in-memory zonder TTL/eviction + single-machine → sticky sessions of gedeelde
  store (Redis/sqlite) nodig vóór multi-machine-deploy.
- Cookie-hardening: `SESSION_SECRET` verplicht (geen dev-default) + `https_only=True`.
- Student laadt nu alleen examenreglement-type bronnen volgens `STUDENT_SOORTEN` (bewust, mirror
  van Streamlit).

## Afspraken / geheugen
- "OER" zoveel mogelijk vermijden in student-facing UI → "studiegids" (OER alleen in citaat-bron +
  1 parenthetische uitleg). Bron-getrouw renderen (instellingslogo behouden, niet strippen).
