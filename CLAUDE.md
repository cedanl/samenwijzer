# Samenwijzer

## Overview

Python app die AI en Data gebruikt om studenten te ondersteunen bij het leren.

## Standards

Follow CEDA technical standards: https://github.com/cedanl/.github/tree/main/standards/README.md

## Tech Stack

Python 3.13, Streamlit, pandas, Anthropic SDK.
Package management: `uv`. Type checking: `ty`. Linting: `ruff`.

## Project Structure

```
samenwijzer/
├── AGENTS.md               ← Start here (map to all knowledge)
├── ARCHITECTURE.md         ← Layer model and dependency rules
├── app/
│   ├── main.py             ← Streamlit UI (no business logic here)
│   └── config.toml
├── src/samenwijzer/        ← All business logic
│   ├── prepare.py
│   ├── transform.py
│   ├── analyze.py
│   ├── visualize.py
│   └── export.py
├── tests/
├── data/
│   ├── 01-raw/
│   ├── 02-prepared/
│   └── 03-output/
└── docs/                   ← Knowledge base (design, plans, specs)
```

## How to Run

```bash
uv sync
uv run streamlit run app/main.py
```

## How to Test

```bash
uv run pytest
```

## Data

- Raw input: `data/01-raw/`
- Prepared: `data/02-prepared/`
- Output: `data/03-output/`
- Demo datasets in `*/demo/` subfolders (these are committed; other data is gitignored)

## Agent rules

See `AGENTS.md` for the full map. Key rules:
1. No handwritten code — every line is agent-generated.
2. No business logic in `app/`.
3. Validate external inputs at boundaries; trust internal types.
4. Use structured logging; no bare `print()` in production.
