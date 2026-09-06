# Conventies paginamigratie Streamlit → FastAPI

Doel: elke pagina uit `app/pages/` 1-op-1 functioneel migreren naar deze FastAPI-app.
Lees eerst de bron-Streamlitpagina volledig; repliceer het rolgedrag exact (student vs docent).

## Structuur (per feature — raak alleen je eigen bestanden aan)

- Router: `app_fastapi/routes/<feature>.py` (bestaat als stub — vervang de placeholder).
  `router = APIRouter()`; hoofdroute-pad staat al in de stub (bijv. `/voortgang`, `/groep`).
  Extra sub-routes onder hetzelfde pad-prefix (bijv. `/voortgang/api/...`).
- Templates: `app_fastapi/templates/<feature>*.html`, extends `base.html`.
  Geef ALTIJD `**sessie_context(request)` mee in de context (nav/thema hangen aan `rol`).
- Page-CSS/JS: `app_fastapi/static/pages/<feature>.css` / `.js`, laden via
  `{% block head %}` / `{% block scripts %}`. Gebruik eerst de bestaande classes in
  `static/app.css` (sw-hero, sw-stat, sw-grid, sw-card, sw-badge, sw-alert, sw-btn,
  sw-table, sw-chat, sw-section-label, sw-tile, sw-progress); page-CSS alleen voor extra's.
- NIET aanraken: `main.py`, `app.css`, `app.js`, `base.html`, andermans routes/templates.

## Sessies & auth

- Sessie: `request.session` met `rol` ("student"/"docent"), `studentnummer`, `mentor_naam`.
- Guards: `from app_fastapi.auth import eis_rol, sessie_context` —
  `redirect = eis_rol(request, "student")` (of beide rollen) bovenin elke route.
- Docent ziet alleen eigen studenten: `data.mentor_df(mentor_naam)`.

## Data

- `from app_fastapi import data` — `data.get_df()` (met groei-overlay, altijd vers),
  `data.student_row(snr)`, `data.mentor_df(naam)`. Nooit zelf CSV laden.
- Business logic blijft in `src/samenwijzer/` — importeer de bestaande functies
  (analyze, groei, groei_store, outreach, welzijn, tutor, coach, bewijsstuk_store, ...).
  GEEN business logic of raw SQL in `app_fastapi/`.

## AI-calls

- Alleen via de bestaande feature-modules (`tutor.py`, `coach.py`, `outreach.py`,
  `welzijn.py`) — nooit `anthropic` importeren in `app_fastapi/`.
- Streaming naar de browser: SSE via `StreamingResponse(..., media_type="text/event-stream")`,
  events als `data: {json}\n\n` met `{chunk}` / `{done}` / `{error}` — client-side helper
  `swStream(url, body, {onChunk,onDone,onError})` staat in `static/app.js`.
- Vang `anthropic.APITimeoutError` af (import in de router mag alléén voor except-clausules
  — geen client-instantiatie) en stuur `{error: "timeout"}`.

## Grafieken

- Hergebruik `samenwijzer.visualize`-functies waar mogelijk: Altair-chart →
  `chart.to_json()` → in template renderen met vega-embed (CDN in `{% block head %}`:
  jsdelivr vega@6.4.0 + vega-lite@6.4.3 + vega-embed@7.2.0 — exact gepind en gelijk aan de
  Altair-major, zie `tests/test_app_fastapi_templates.py`). Plotly → `fig.to_json()` + plotly CDN.
- Simpele voortgangsbalken/percentages: liever puur HTML/CSS (`sw-progress`).

## Verificatie (verplicht vóór je klaar meldt)

```bash
uv run python -c "from app_fastapi.main import app"
uv run ruff check app_fastapi/ && uv run ruff format app_fastapi/
```
Plus een `fastapi.testclient.TestClient`-rooktest: login-POST + je hoofdroute GET → 200.
Draai geen browser; de integratie-smoke gebeurt centraal na de merge van alle pagina's.
