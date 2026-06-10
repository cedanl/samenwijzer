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
uv run uvicorn app_fastapi.main:app --port 8504 --reload   # app (vereist SESSION_SECRET + ALGEMEEN_WACHTWOORD in .env)
uv sync --extra dev && uv run python -m pytest             # tests
uv run python -m pytest tests/test_ingest.py::test_parseer_bestandsnaam_davinci -v  # één test
uv run ruff check --fix src/ app/ && uv run ruff format src/ app/ scripts/          # lint + format
uv run python -m validatie_samenwijzer.ingest --alles      # (her)indexeer OERs (+ --reset)
```

Lint: line-length 100; selectie `E,F,I,N,W,UP`; E501 vrijgesteld voor `app/` + `styles.py`.

## Tests

Tests in `tests/`; discovery via `[tool.pytest.ini_options]`. De autouse-fixture in `conftest.py`
reset de gecachete `_ai`-client tussen tests zodat een gemockte client niet lekt.

> **Geen CI-gate voor dit subproject**: de root-`ci.yml` draait `ruff`/`pytest` vanuit de
> monorepo-root en raakt dit subproject (eigen `.venv`) niet. Draai lint, format en tests **lokaal**
> vóór je commit.

## Omgeving

`.env` in `validatie_samenwijzer/`:

```
ANTHROPIC_API_KEY=sk-ant-...
DB_PATH=data/validatie.db   # default
OEREN_PAD=../oeren          # default (root-oeren/ hergebruikt)
BEHEER_ENABLED=true         # activeer beheerpagina (alleen op dev-machines)
COMPETENTNL_API_KEY=...      # optioneel: skills-build gebruikt CompetentNL ipv ESCO
```

## Architectuur-invarianten (niet breken)

Volledige beschrijving in `docs/ARCHITECTURE.md`. De regels die een wijziging niet mag overtreden:

- **AI-isolatie**: alle Anthropic-calls via `_ai._client()`; `chat.py` is de enige module met
  streaming-aanroepen. **Nooit** `anthropic.Anthropic()` direct instantiëren. De client dwingt het
  30s-timeout-contract af (`_CLIENT_OPTS`).
- **Geen business logic in `app/`**; geen raw SQL in pagina's — alle DB-toegang via `db.py`
  (scripts/tests) of `_db.get_conn()` (pagina's).
- **Vier chat-bronnen**, alle full-document: OER (leidend) + KD + skills + instellingsbrede regelingen.
  Loaders + caps in `chat.py` (`laad_oer_tekst` 500K, KD 300K, skills 50K, instelling 300K).
- **Juridische citatieplicht**: elke claim eist **bron + vindplaats + woordelijk citaat tussen
  aanhalingstekens** (OER/KD/examenreglement). Skills hebben een aangepaste citatie (bron + beroep +
  categorie + skill-naam) — verzonnen paginanummers zijn verboden. Templates: `_SYSTEEM_TEMPLATE`,
  `_MULTI_SYSTEEM_TEMPLATE`.
- **Drie hardgecodeerde instelling-lijsten** moeten synchroon blijven: `ingest._INSTELLINGEN`/
  `_MAP_NAAM`, `scripts/seed_bulk.py:INSTELLINGEN`, `9_beheer.py:_INSTELLING_KEYS`. Ontbreekt een
  nieuwe instelling in de seed-lijst → stil **0 studenten**.
- **Parser-sync met de parent**: de parse-helpers in `ingest.py` worden bewust gespiegeld naar
  `src/samenwijzer/oer_parsing.py`. Wijzig je ze hier, werk de parent-kopie mee bij (en omgekeerd).
- **OER-onleesbaar-modus**: bij lege OER-fulltext bouwt `bouw_systeem` de prompt met KD +
  instellingsregelingen als hoofdbron; alleen zónder enige bron volgt `LAGE_RELEVANTIE_BERICHT`.

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

**Streamlit module-cache bij styles-wijzigingen** (geretirede app): hot-reload herlaadt `styles.py`
niet — bij CSS-edits in `src/validatie_samenwijzer/styles.py` is een volledige restart nodig.

## Kennisbank

| Onderwerp | Bestand |
|---|---|
| Architectuur, datapipelines, module-rollen | `docs/ARCHITECTURE.md` |
| Multi-machine workflow + volledige commando-catalogus | `docs/ARCHITECTURE.md` |
| Specs & plannen | `docs/plans/` (specs én plannen wonen hier in dit subproject) |
| Mockups | `docs/mockups/` |
| Presentatie (Slidev, poort 3030) | `presentatie/` — `./start.sh` |
