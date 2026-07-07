# Sessie 2026-07-07 — FastAPI-frontend hoofd-app afgerond & geverifieerd

Branch: `feat/fastapi-frontend-hoofdapp` → PR **#228** (cedanl/samenwijzer, base `main`).

## Context

De hoofd-app-frontend migreert van Streamlit (`app/`) naar FastAPI + Jinja (`app_fastapi/`,
poort 8505), volgens hetzelfde draaiboek als het validatie-subproject eerder. Bij aanvang waren
scaffold + alle 6 pagina-migraties gecommit (25ba245, c00a986); de centrale integratie-verificatie
(bewust ná alle pagina-merges, cf. `app_fastapi/MIGRATIE.md`) stond nog open.

## Gedaan

**Parity-review** — 6 subagents (één per pagina) vergeleken de FastAPI-route/template met de
Streamlit-bronpagina. Uitkomst: alle 6 **functioneel volledig**; resterende punten uitsluitend
MINOR (zie Open punten).

**Verificatie** — `ruff` groen, `ty` groen, `pytest` 506 passed (91% cov), TestClient 9/9
rol-routes → 200. **Browser-smoke** (chrome-devtools, uvicorn :8505), beide rollen:
- Student: home → voortgang (vega-charts) → **leercoach live AI-tutor via SSE** → welzijn
  (check verstuurd, PRG + eerdere-checks) → groeidossier (score-inputs, tabs, upload-forms).
- Docent: home (`theme-docent`, mentor-gefilterd) → groep → **outreach live AI-bericht via SSE**.

**Bug gevonden + gefixt** (commit 2112424):
- `groepsoverzicht.html` laadde `vega-lite@5` + `vega-embed@6` bij een Altair vega-lite v6-spec →
  `vegaEmbed is not defined`, groep-voortganggrafiek renderde niet. Uitgelijnd met de werkende
  voortgang-pagina (`vega5 + vega-lite6 + vega-embed7`). Na fix: grafiek rendert, 0 console-errors.
- `welzijn`-SSE ving alleen Anthropic-fouten af → een andere fout liet de stream eeuwig op "…"
  hangen. Nu broad-except + `log.exception` + net error-event.
- `groep`-notitie `ValueError` werd stil ingeslikt → nu gelogd (structured logging).
- Obsolete `in_aanbouw.html` verwijderd.

**Documentatie bijgewerkt**: `ARCHITECTURE.md` (layer-model + routes-tabel + overview),
`CLAUDE.md` (Overview, Commands, Auth), `INSTRUCTIONS.md` (start-commando's + poort-tabel 8505).

## Environment-noten (voor volgende sessie)

- Server starten: `SESSION_SECRET=dev-secret uv run uvicorn app_fastapi.main:app --port 8505` via
  harness `run_in_background` + `dangerouslyDisableSandbox` (sandbox-netns anders onbereikbaar op localhost).
- **Niet** `pkill -f "uvicorn app_fastapi"` in hetzelfde commando dat de server start — matcht de
  eigen shell → self-kill (exit 144).
- chrome-devtools-mcp: bij "browser already running / profile locked" de stray chrome killen +
  `SingletonLock/Socket/Cookie` uit `~/.cache/chrome-devtools-mcp/chrome-profile/` verwijderen.
- Wegwerp-smoke: `scripts/_smoke_fastapi.py` (run met `PYTHONPATH=.`).

## Open punten (MINOR, bewust niet gefixt)

- **Reload-persistentie van gestreamde AI-output** (weekplan, lesmateriaal, aanscherp-suggestie,
  rollenspel-nabespreking): Streamlit bewaarde dit in `session_state`; de stateless FastAPI-versie
  verliest in-DOM-output bij page-reload. Inherent architectuurverschil, geen functieverlies binnen
  één sessie. Eventuele fix = server-side of localStorage-persistentie.
- Cosmetisch: heatmap-gradient op outreach-trechter, warning-accent op aandachtspunt-labels,
  newline→`<br>` in mentor-feedback/aanscherp-suggestie.
- Leercoach: lange gesprekshistorie wordt getrimd wegens 4 kB cookie-sessielimiet (bewust).

## Status

PR #228 open, **niet gemerged** — mergen van de hele frontend naar `main` wacht op groen licht.
