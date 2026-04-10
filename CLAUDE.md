# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Python/Streamlit app die AI en Data gebruikt om MBO-studenten te ondersteunen bij het leren.
Doelgroepen: studenten (voortgang, tutor, leercoach) en docenten (groepsoverzicht, peer matching).

## Standards

Follow CEDA technical standards: https://github.com/cedanl/.github/tree/main/standards/README.md

## Tech Stack

Python 3.13, Streamlit, pandas, Anthropic SDK.
Package management: `uv`. Type checking: `ty`. Linting/formatting: `ruff`.

## Commands

```bash
# Installeren
uv sync

# App starten
uv run streamlit run app/main.py

# Alle tests
uv run pytest

# Één testbestand
uv run pytest tests/test_analyze.py

# Één test
uv run pytest tests/test_analyze.py::test_leerpad_niveau

# Linting controleren
uv run ruff check src/ app/

# Linting + imports automatisch fixen
uv run ruff check --fix src/ app/
uv run ruff format src/ app/
```

## Omgeving

AI-functies (tutor, leercoach) vereisen een `.env` in de projectroot:

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Project Structure

```
samenwijzer/
├── AGENTS.md               ← Startpunt voor agents (verwijst naar alle kennis)
├── ARCHITECTURE.md         ← Lagenmodel en dependency-regels
├── app/
│   ├── main.py             ← Streamlit startpagina + sessie-initialisatie
│   └── pages/
│       ├── 1_mijn_voortgang.py   ← Studentweergave
│       ├── 2_groepsoverzicht.py  ← Docentweergave
│       └── 3_leercoach.py        ← AI tutor, lesmateriaal, oefentoets, werkfeedback
├── src/samenwijzer/
│   ├── prepare.py          ← CSV inladen en valideren
│   ├── transform.py        ← Berekende kolommen (BSA%, risico, kt_gemiddelde)
│   ├── analyze.py          ← Kernanalyses (leerpadniveau, badge, peer matching, …)
│   ├── visualize.py        ← Altair-grafieken
│   ├── tutor.py            ← Socratische tutor via Anthropic SDK (streaming)
│   ├── coach.py            ← Lesmateriaal, oefentoets, werkfeedback (Anthropic SDK)
│   ├── styles.py           ← EduPulse huisstijl CSS + render_footer()
│   └── export.py           ← Schrijven naar data/03-output/
├── tests/
├── data/
│   ├── 01-raw/demo/        ← Demo-CSV (gecommit)
│   ├── 02-prepared/        ← Tussenresultaten (gitignored)
│   └── 03-output/          ← Exports (gitignored)
└── docs/                   ← Kennisbank (design, plannen, specs)
```

## Architectuur

Dependency-richting is strikt: `prepare → transform → analyze → visualize/coach/tutor → app`.
Nooit omgekeerd. Zie `ARCHITECTURE.md` voor details.

**Sessiedata**: `st.session_state["df"]` bevat het getransformeerde DataFrame en wordt eenmalig
geladen op de startpagina. Alle pagina's lezen daaruit — nooit opnieuw laden.

**AI-isolatie**: alle Anthropic API-calls zitten in `tutor.py` en `coach.py`.
De UI-laag roept alleen de publieke functies aan; nooit `anthropic` direct importeren in `app/`.

**Huisstijl**: alle CSS zit in `src/samenwijzer/styles.py`. Elke pagina injecteert dit via
`st.markdown(CSS, unsafe_allow_html=True)` en roept `render_footer()` aan onderaan.
Geen sidebar gebruiken — de huisstijl schrijft dit voor.

## Agent rules

Zie `AGENTS.md` voor de volledige kaart. Kernregels:
1. No handwritten code — every line is agent-generated.
2. No business logic in `app/`.
3. Validate external inputs at boundaries; trust internal types.
4. Use structured logging; no bare `print()` in production.
