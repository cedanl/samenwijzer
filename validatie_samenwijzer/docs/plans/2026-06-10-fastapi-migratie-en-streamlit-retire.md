# Spec: migratie naar FastAPI-frontend + retire Streamlit

**Datum:** 2026-06-10
**Status:** spec (goedgekeurd, implementatieplan volgt)
**Gerelateerd:** `docs/plans/2026-06-08-fastapi-poc-publieke-oer-chat.md` (POC), issue #177 (doorontwikkelen)

## Aanleiding

De digitale gids heeft nu twee frontends: de productie-Streamlit-app (`app/` + repo-root
`Dockerfile`, live als `digitale-gids`) en een FastAPI-POC (`app_fastapi/`, niet gedeployed). Twee
parallelle UI's bovenop dezelfde Python-kern is structurele tech-debt: elke feature moet twee keer
gebouwd/getest worden en de twee lopen uiteen. Dat is **nu al gebeurd** — de chat-KD-fallback
(PR #182) zit alleen in de Streamlit-pagina's; `app_fastapi/context.py:66` heeft nog de oude gate.

De FastAPI-POC bestaat juist omdat Streamlit de gewenste UI-kwaliteit structureel niet haalt (geen
DOM-bezit, geen page-JS, rerun-model). Daarom: **FastAPI wordt de enige frontend; Streamlit wordt
geretired.**

## Doel

`app_fastapi/` is de enige frontend van De digitale gids. Streamlit (`app/`, repo-root
`Dockerfile`, Streamlit-deps) wordt verwijderd. Productie blijft `digitale-gids.fly.dev`. De
Python-kern (`chat.py`, `db.py`, `_ai.py`, `auth.py`, `oer_parsing.py`, `opleiding.py`, etc.) blijft
ongewijzigd gedeeld — die importeren geen UI-framework.

### Niet-doelen (YAGNI / scope-grens)
- Geen functionele uitbreidingen bovenop de bestaande Streamlit-features — dit is een UI-migratie,
  geen herontwerp. (De mockup-kwaliteit die de POC al biedt is meegenomen, niet meer.)
- Geen wijziging aan de data-/ingest-laag of de chat-kern.
- Geen rotatie-OCR (apart, #180 deel 2).

## Pariteit-audit (uitgangssituatie)

| Streamlit-pagina | FastAPI-route | Status |
|---|---|---|
| `main.py` login + algemeen-poort | `/login`, `/toegang` (middleware) | ✅ gedekt |
| `0_oer_vraag` (intake, multi-OER, chat-stream, PDF, reset) | `/`, `/api/vraag`, `/api/kies`, `/api/chat`, `/api/oer/{id}/bestand`, `/api/reset` | ✅ gedekt |
| `1_oer_assistent` (student-chat) | `/student` + `/api/chat` | ✅ gedekt |
| `2_mijn_oer` (studiegids) | `/student/studiegids` | ✅ gedekt |
| `3_mijn_voortgang` | `/student/voortgang` | ✅ gedekt |
| `4_mijn_studenten` | `/mentor` | ✅ gedekt |
| `5_begeleidingssessie` (profiel + chat + OER-view) | `/mentor/student/{id}` | ✅ gedekt |
| `9_beheer` (dev sync/ingest/seed) | — | ❌ niet geport |
| `uitloggen` | `/uitloggen` | ✅ gedekt |

**Bron-pariteit:** `app_fastapi/context.py` dekt OER + KD + skills + instellingsbronnen + web_zoek
via dezelfde `chat.py` (`bouw_gecombineerd_systeem`). PUBLIEK/STUDENT/MENTOR_SOORTEN spiegelen de
Streamlit-rolfilters.

## Besloten ontwerpkeuzes

- **Eindoel:** volledige cutover + Streamlit retiren (één systeem).
- **Sessiestore:** server-side sessies in **SQLite** (aparte schrijfbare db, gitignored) met
  TTL-opruiming; Fly draait op **1 machine**. (Geen Redis/externe infra; past bij de bestaande
  SQLite-stack. Bewuste afweging: geen HA/zero-downtime — acceptabel voor een laag-verkeer gids.)
- **beheer-pagina:** **porten** naar FastAPI (routes + template + live subprocess-streaming,
  achter `BEHEER_ENABLED`).
- **Aanpak:** harden → pariteit → cutover (één overstapmoment, Fly-rollback als vangnet).
- **Structuur:** één spec, **drie fase-PR's** (elk werkend/testbaar).

## Architectuur

UI-schil wisselt; de kern blijft. FastAPI + Jinja-templates + SSE-chat (`text/event-stream`) +
static JS (`chat.js` = escapende markdown-renderer + SSE + viewer). Server-side sessies via een
ondertekende `sid`-cookie (Starlette `SessionMiddleware`) → SQLite-store. Eén Anthropic-client via
`_ai._client()` (prompt-cache blijft werken). Container draait `uvicorn app_fastapi.main:app` op
poort 8080.

## Fasen

### Fase 1 — Productie-blockers (PR 1)
1. **SQLite-sessiestore** — vervang `app_fastapi/sessie.py` in-memory `_STORE: dict` door een
   SQLite-backed store: aparte schrijfbare db (bv. `data/sessies.db`, gitignored), tabel met
   `sid`, geserialiseerde sessie-state, `laatst_gebruikt`-timestamp. **TTL-opruiming** lazy bij
   toegang (patroon: WhatsApp-retentie in de hoofd-app). Sessie-state bevat de gecombineerde
   system-prompt (tot ~1,5 MB) → opslaan als tekst/blob, niet in de cookie.
2. **Cookie-hardening** — `SESSION_SECRET` verplicht (fail-closed, geen default), `https_only=True`
   op de `SessionMiddleware`.
3. **Fly 1 machine** — `fly.toml`: één machine (min=max=1) zodat de SQLite-sessiestore consistent
   is. (Nog steeds Streamlit-`Dockerfile` in deze fase — alleen de config/POC-code wijzigt.)
4. Tests: `tests/test_fastapi_poc.py` uitbreiden — sessie persist/herstel via store, TTL-verloop,
   fail-closed zonder `SESSION_SECRET`.

### Fase 2 — Feature/kwaliteits-pariteit (PR 2)
1. **chat-KD-fallback porten** — `context.py`: includeer een OER met onleesbare fulltext tóch
   wanneer er een KD óf instellingsbron is (mirror van `0_oer_vraag.py`/`1_oer_assistent.py`/
   `5_begeleidingssessie.py`); geef een `oer_onleesbaar`-signaal terug. Templates: toon de banner
   "De OER … is niet machine-leesbaar; antwoorden komen uit het kwalificatiedossier en de
   instellingsregelingen." `bouw_systeem`/`bouw_gecombineerd_systeem` hebben de onleesbaar-modus al
   (PR #182), dus dit is gate + banner, geen prompt-werk.
2. **beheer porten** — routes + template + live subprocess-streaming (sync/ingest/seed/status),
   achter `BEHEER_ENABLED`.
3. **Kwaliteits-pariteit verifiëren/fixen** — citatieplicht-blockquotes als pull-quote in
   `chat.js`; PDF-bekijk mobiel-proof (geen blanco data-URI-iframe op iOS/Android); dual-theme
   student/docent-kwaliteit gelijk aan Streamlit.
4. Tests: KD-fallback (gate + banner-signaal), beheer-route achter flag, per-route auth-bewaking.

### Fase 3 — Cutover + retire (PR 3)
1. **`Dockerfile.fastapi` finaliseren** — `CMD uvicorn app_fastapi.main:app --port 8080`, env
   (`OEREN_PAD`, `KWALDOSSIERS_PAD`, `SKILLS_PAD`, `DB_PATH`, `SESSION_SECRET`, `ALGEMEEN_WACHTWOORD`,
   `BEHEER_ENABLED=false`).
2. **`fly.toml` → `Dockerfile.fastapi`**.
3. **Deploy + volledige UI-smoke-test op productie** — publiek (incl. onleesbare OER → banner +
   KD), student (chat/studiegids/voortgang), mentor (studenten/sessie). Login + algemeen-poort.
4. **Streamlit retiren** — verwijder `app/` (Streamlit-pagina's + `main.py`), de repo-root
   `Dockerfile` (Streamlit), Streamlit-deps uit `pyproject.toml` (`streamlit`, `streamlit-pdf`,
   en eventueel alleen-Streamlit-afhankelijkheden), en werk `CLAUDE.md`/`README`/relevante docs
   bij. Behoud de `styles.py`-her-exports alleen als niet-UI-code ze nog gebruikt (controleren).
5. **Rollback-vangnet** — Fly houdt de vorige release; bij problemen `flyctl releases rollback`.

## Testing

- **Unit/integratie:** `tests/test_fastapi_poc.py` per fase uitbreiden (sessiestore, KD-fallback,
  auth-bewaking per rol, beheer-flag). Behoud de bestaande `chat.py`-tests (kern ongewijzigd).
- **UI-smoke-test (verplicht):** per rol lokaal vóór de cutover; productie-smoke ná de deploy.
  Publieke chat via landing → "Direct een vraag" + `ALGEMEEN_WACHTWOORD`. Voor een
  student-op-onleesbare-OER: tijdelijke `oer_id`-swap in `validatie.db` (origineel vastleggen +
  herstellen — die db wordt in de image gebakken).
- **Regressie:** leesbare OER → géén banner + "Volgens de OER"-citaat.

## Risico's & mitigatie

- **Sessieverlies bij restart** — bewust geaccepteerd (1 machine, SQLite-store overleeft
  app-restarts binnen de machine; bij machine-herstart begint een gebruiker een nieuw gesprek).
- **Onvolledige pariteit ontdekt na cutover** — gemitigeerd door de UI-smoke-test vóór én na, en
  `flyctl releases rollback` als directe terugval naar de Streamlit-release.
- **Divergentie tijdens migratie** — principe: geen nieuwe features in de Streamlit-pagina's
  zolang de migratie loopt; de migratie is de enige UI-wijziging.

## Bestanden (verwachte aanraking, globaal)

- Fase 1: `app_fastapi/sessie.py`, `app_fastapi/main.py` (middleware/secret), `fly.toml`,
  `tests/test_fastapi_poc.py`, `.gitignore` (sessies-db).
- Fase 2: `app_fastapi/context.py`, `app_fastapi/templates/*.html`, `app_fastapi/static/chat.js`,
  nieuwe beheer-route + template, `tests/test_fastapi_poc.py`.
- Fase 3: `Dockerfile.fastapi`, `fly.toml`, verwijderen `app/` + repo-root `Dockerfile`,
  `pyproject.toml`, `CLAUDE.md`/`README`/docs.
