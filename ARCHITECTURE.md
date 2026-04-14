# Architecture

## Overview

Samenwijzer is a single-service Python application with a Streamlit frontend.

## Layer model

```
app/            ← UI only (Streamlit). No business logic.
src/samenwijzer/
  prepare.py    ← Ingest and clean raw data
  transform.py  ← Shape data for analysis
  analyze.py    ← Core learning analytics + transitiemoment detection
  visualize.py  ← Chart/figure generation
  export.py     ← Write results to data/03-output/

Cross-cutting modules (no layer restriction, import explicitly):
  _ai.py            ← Shared Anthropic client factory (_client())
  auth.py           ← Role checks and mentor filter
  outreach.py       ← At-risk selection, referral logic, AI message generation, email
  outreach_store.py ← SQLite persistence (StudentStatus, Interventie, Campagne, WelzijnsCheck)
  welzijn.py        ← Student self-assessment AI responses
  wellbeing.py      ← CSV-gebaseerde welzijnssignalering (WelzijnsCheck, welzijnswaarde, notities)
  tutor.py          ← Socratic AI tutor (Anthropic SDK, streaming)
  coach.py          ← Study material, practice tests, work feedback (Anthropic SDK)
  styles.py         ← EduPulse CSS + render_nav() (vaste header) + render_footer()
```

Dependency direction is strictly left-to-right (prepare → export).
Cross-cutting concerns (auth, outreach, welzijn, styles) come in via explicit imports, not globals.

## Data flow

```
data/01-raw/ → prepare → data/02-prepared/ → transform → analyze → visualize → app
                                                                  → export → data/03-output/
```

SQLite (`data/02-prepared/outreach.db`) is written by `outreach_store.py` and read by both
the outreach page (docent) and the welzijn page (student).

## AI integration

The Anthropic SDK (`anthropic`) is the primary AI client.
AI calls are isolated in dedicated modules; they are **never** called from the UI layer directly.

| Module | AI purpose |
|---|---|
| `tutor.py` | Socratic tutor conversation (streaming) |
| `coach.py` | Study material, practice tests, work feedback |
| `outreach.py` | Personalised outreach message generation |
| `welzijn.py` | Empathic response to student self-assessment |

## Pages

| File | Role | Access |
|---|---|---|
| `app/main.py` | Login + session init | public |
| `app/pages/1_mijn_voortgang.py` | Student progress view | student |
| `app/pages/2_groepsoverzicht.py` | Groepsoverzicht: voortgang + welzijnssignaleringen + notities | docent |
| `app/pages/3_leercoach.py` | AI tutor, study material, feedback | student |
| `app/pages/4_outreach.py` | Werklijst, campagnes, effectiviteit | docent |
| `app/pages/5_welzijn.py` | Student self-assessment | student |
| `app/pages/uitloggen.py` | Sessie wissen + redirect naar `/` | — |

## Key dependencies

| Package | Purpose |
|---|---|
| streamlit | Interactive UI |
| pandas | Tabular data |
| anthropic | Claude API client |
| python-dotenv | Secrets from `.env` |
| pytest + pytest-cov | Testing |
| ruff | Linting & formatting |
| altair | Declarative charts |
