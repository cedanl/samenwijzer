# Architecture

## Overview

Samenwijzer is a single-service Python application with a Streamlit frontend.

## Layer model

```
app/            ← UI only. Two processes:
  main.py + pages/  ← Streamlit frontend (poort 8501)
  webhook.py        ← FastAPI server (poort 8502) — verwerkt inkomende WhatsApp-berichten
src/samenwijzer/
  prepare.py    ← Ingest and clean raw data
  transform.py  ← Shape data for analysis
  analyze.py    ← Core learning analytics + transitiemoment detection
  visualize.py  ← Chart/figure generation

Cross-cutting modules (no layer restriction, import explicitly):
  _ai.py            ← Shared Anthropic client factory (_client())
  auth.py           ← Role checks and mentor filter
  outreach.py       ← At-risk selection, referral logic, AI message generation, email
  outreach_store.py ← SQLite persistence (StudentStatus, Interventie, Campagne, WelzijnsCheck)
  welzijn.py        ← Student self-assessment AI responses
  wellbeing.py      ← CSV-gebaseerde welzijnssignalering (WelzijnsCheck, welzijnswaarde, notities)
  whatsapp.py       ← WhatsApp via Twilio: check-ins, inkomende berichten, AI-gesprekssessies
  whatsapp_store.py ← SQLite persistence voor WhatsApp-registraties (Fernet-versleuteld) en sessies
  scheduler.py      ← Wekelijkse check-in verzender (GitHub Actions cron entry point)
  tutor.py          ← AI tutor with direct answers (Anthropic SDK, streaming)
  coach.py          ← Study material, practice tests, work feedback (Anthropic SDK)
  styles.py         ← Dual-theme tokens (student-donker / docent-paper) + inject_theme(rol) + component-helpers (hero, stat_card, badge, alert, action_tile, section_label) + render_nav() + render_footer()
  oer_store.py      ← SQLite persistence voor OER-catalog (oeren.db): instellingen, oer_documenten, kerntaken
  oer_parsing.py    ← OER PDF/bestandsnaam parsing: crebo, opleiding, niveau, kerntaken
  oer_context.py    ← OER-tekst ophalen per student (display_naam lookup + markitdown-tekst laden)
  groei.py          ← Groeidossier business-logic: overlay van goedgekeurde self-scores, herberekening kt/voortgang/risico
  groei_store.py    ← SQLite persistence voor groeidossier (groei.db): groei_actueel (status-workflow), groei_historie, mentor_feedback, bewijsstuk
  bewijsstuk_store.py ← Bewijsstuk-uploads: filesystem (data/bewijsstukken/<studentnummer>/) + metadata via groei_store
```

Dependency direction is strictly left-to-right (prepare → visualize).
Cross-cutting concerns (auth, outreach, welzijn, styles) come in via explicit imports, not globals.

## Data flow

```
data/01-raw/ → prepare → data/02-prepared/ → transform → analyze → visualize → app
```

SQLite (`data/02-prepared/outreach.db`) is written by `outreach_store.py` and read by both
the outreach page (docent) and the welzijn page (student).

SQLite (`data/02-prepared/oeren.db`) is built once by `scripts/build_oer_catalog.py` from OER
PDFs in `oeren/`. Tables: `instellingen`, `oer_documenten`, `kerntaken`. Read by
`prepare._voeg_kt_wp_scores_toe()` and `analyze._oer_label()` to resolve kerntaak names.

SQLite (`data/02-prepared/groei.db`) is written exclusively by `groei_store.py` and holds de
groeidossier-data: `groei_actueel` (self-rating per werkproces met goedkeuringsstatus
concept→ingediend→goedgekeurd/teruggegeven + `goedgekeurde_score`), `groei_historie` (snapshots),
`mentor_feedback`, `bewijsstuk`. `groei.overlay_self_scores()` legt **alleen goedgekeurde** scores
over de sessie-`df` en herberekent kt-scores, `voortgang` en de `risico`-vlag.

## AI integration

The Anthropic SDK (`anthropic`) is the primary AI client.
AI calls are isolated in dedicated modules; they are **never** called from the UI layer directly.

| Module | AI purpose |
|---|---|
| `tutor.py` | AI tutor with direct answers (streaming); injects OER-context via `oer_context.py` |
| `coach.py` | Study material, practice tests, work feedback; injects OER-context via `oer_context.py` |
| `outreach.py` | Personalised outreach message generation |
| `welzijn.py` | Empathic response to student self-assessment |
| `whatsapp.py` | WhatsApp check-ins, inbound message parsing, AI conversation |

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
| `app/webhook.py` | FastAPI webhook voor inkomende WhatsApp-berichten (Twilio) | intern |

## Key dependencies

| Package | Purpose |
|---|---|
| streamlit | Interactive UI |
| pandas | Tabular data |
| anthropic | Claude API client |
| python-dotenv | Secrets from `.env` |
| twilio | WhatsApp messaging via Twilio API |
| fastapi + uvicorn | Webhook endpoint (inbound WhatsApp messages) |
| cryptography | Fernet encryption for phone numbers in whatsapp_store |
| pytest + pytest-cov | Testing |
| ruff | Linting & formatting |
| altair | Declarative charts |
