# Architecture

## Overview

Samenwijzer is a single-service Python application with a Streamlit frontend.

## Layer model

```
app/            ← UI only (Streamlit). No business logic.
src/samenwijzer/
  prepare.py    ← Ingest and clean raw data
  transform.py  ← Shape data for analysis
  analyze.py    ← Core learning analytics
  visualize.py  ← Chart/figure generation
  export.py     ← Write results to data/03-output/
```

Dependency direction is strictly left-to-right (prepare → export).
Cross-cutting concerns (logging, config, auth) come in via explicit imports, not globals.

## Data flow

```
data/01-raw/ → prepare → data/02-prepared/ → transform → analyze → visualize → app
                                                                  → export → data/03-output/
```

## AI integration

The Anthropic SDK (`anthropic`) is the primary AI client.
AI calls are isolated in dedicated modules; they are never called from the UI layer directly.

## Key dependencies

| Package | Purpose |
|---|---|
| streamlit | Interactive UI |
| pandas | Tabular data |
| anthropic | Claude API client |
| python-dotenv | Secrets from `.env` |
| pytest + pytest-cov | Testing |
| ruff | Linting & formatting |
