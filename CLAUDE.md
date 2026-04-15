# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Python/Streamlit app die AI en Data gebruikt om MBO-studenten te ondersteunen bij het leren.
Doelgroepen: studenten (voortgang, tutor, leercoach, welzijnscheck) en docenten (groepsoverzicht,
outreach, campagnebeheer, peer matching).

## Standards

Follow CEDA technical standards: https://github.com/cedanl/.github/tree/main/standards/README.md

## Tech Stack

Python 3.13, Streamlit, pandas, Anthropic SDK.
Package management: `uv`. Type checking: `ty`. Linting/formatting: `ruff`.

**pandas vs Polars**: dit project gebruikt pandas bewust. Altair, Streamlit en de meeste
visualisatiebibliotheken verwachten pandas-DataFrames; conversiestappen zouden code-overhead
toevoegen zonder meetbare voordelen bij de huidige datasetgrootte (1000 studenten).

## Commands

```bash
# Installeren
uv sync

# App starten
uv run streamlit run app/main.py

# Alle tests (met coverage-rapport)
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

# Type checking
uv run ty check

# Dependencies upgraden
uv lock --upgrade && uv sync
```

## Omgeving

AI-functies (tutor, leercoach, outreach, welzijn) vereisen een `.env` in de projectroot:

```
ANTHROPIC_API_KEY=sk-ant-...

# Optioneel — voor e-mailfunctie op de outreach-pagina:
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=...
SMTP_AFZENDER=noreply@example.com

# Optioneel — voor WhatsApp-signalering via Twilio:
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886   # Twilio sandbox-default
WHATSAPP_ENCRYPT_KEY=...                       # Fernet-sleutel voor telefoonencryptie
                                               # (auto-gegenereerd lokaal als leeg)
```

## Project Structure

```
samenwijzer/
├── AGENTS.md               ← Startpunt voor agents (verwijst naar alle kennis)
├── ARCHITECTURE.md         ← Lagenmodel en dependency-regels
├── app/
│   ├── main.py             ← Startpagina + loginscherm + sessie-initialisatie
│   └── pages/
│       ├── 1_mijn_voortgang.py   ← Studentweergave (kerntaken, werkprocessen, BSA)
│       ├── 2_groepsoverzicht.py  ← Docentweergave (eigen studenten + welzijnschecks)
│       ├── 3_leercoach.py        ← AI tutor, lesmateriaal, oefentoets, werkfeedback
│       ├── 4_outreach.py         ← Werklijst, campagnes, effectiviteitsdashboard
│       ├── 5_welzijn.py          ← Student self-assessment + AI-reactie (student-only)
│       └── uitloggen.py          ← Wist sessie en stuurt terug naar startpagina
├── src/samenwijzer/
│   ├── _ai.py              ← Gedeelde Anthropic client factory (_client())
│   ├── prepare.py          ← CSV inladen, valideren, kt/wp-scores genereren
│   ├── transform.py        ← Berekende kolommen (BSA%, risico, kt_gemiddelde)
│   ├── analyze.py          ← Kernanalyses (leerpadniveau, badge, peer matching,
│   │                          OER-labels, transitiemoment-detectie, signaleringen())
│   ├── visualize.py        ← Altair-grafieken
│   ├── auth.py             ← Rolcontrole (vereist_docent) en mentorfilter
│   ├── outreach.py         ← At-risk selectie, verwijslogica, AI-berichtgeneratie,
│   │                          e-mail verzenden
│   ├── outreach_store.py   ← SQLite-persistentie (StudentStatus, Interventie,
│   │                          Campagne, WelzijnsCheck)
│   ├── welzijn.py          ← Student self-assessment: categorielabels,
│   │                          AI-reactiegeneratie (Anthropic SDK)
│   ├── wellbeing.py        ← CSV-gebaseerde welzijnssignalering (WelzijnsCheck
│   │                          dataclass, welzijnswaarde(), heeft_signaal())
│   ├── whatsapp.py         ← WhatsApp via Twilio: check-ins versturen, inkomende
│   │                          berichten parsen, AI-gesprekssessies beheren
│   ├── whatsapp_store.py   ← SQLite-persistentie voor WhatsApp-registraties en
│   │                          gesprekssessies; telefoonnummers Fernet-versleuteld
│   ├── scheduler.py        ← Wekelijkse check-in verzender (GitHub Actions cron)
│   ├── tutor.py            ← Socratische tutor via Anthropic SDK (streaming)
│   ├── coach.py            ← Lesmateriaal, oefentoets, werkfeedback (Anthropic SDK)
│   ├── styles.py           ← EduPulse huisstijl CSS + render_nav() + render_footer()
│   └── export.py           ← Schrijven naar data/03-output/
├── tests/
├── data/
│   ├── 01-raw/berend/
│   │   ├── studenten.csv       ← Berend-dataset (1000 MBO-studenten)
│   │   └── oer_kerntaken.json  ← OER-labels per opleiding (kt/wp namen)
│   ├── 02-prepared/            ← Tussenresultaten + outreach.db (gitignored)
│   └── 03-output/              ← Exports (gitignored)
└── docs/                   ← Kennisbank (design, plannen, specs)
```

## Architectuur

Dependency-richting is strikt: `prepare → transform → analyze → visualize/coach/tutor/welzijn → app`.
Nooit omgekeerd. Zie `ARCHITECTURE.md` voor details.

**Sessiedata**: `st.session_state["df"]` bevat het getransformeerde DataFrame en wordt eenmalig
geladen op de startpagina via `load_berend_csv()` + `transform_student_data()`. Alle pagina's lezen
daaruit — nooit opnieuw laden.

**AI-isolatie**: alle Anthropic API-calls zitten in `tutor.py`, `coach.py`, `outreach.py`,
`welzijn.py` en `whatsapp.py`. Alle AI-modules maken een client via `_ai._client()` — nooit een
eigen `anthropic.Anthropic()` instantiëren. De UI-laag roept alleen de publieke functies aan;
nooit `anthropic` direct importeren in `app/`.

**Huisstijl**: alle CSS zit in `src/samenwijzer/styles.py`. Elke pagina injecteert dit via
`st.markdown(CSS, unsafe_allow_html=True)`, roept `render_nav()` aan direct erna (injecteert een
vaste navigatiebalk bovenin via `position:fixed` HTML), en roept `render_footer()` aan onderaan.
Geen sidebar — volledig verborgen via CSS en `showSidebarNavigation = false` in `.streamlit/config.toml`.
Uitloggen verloopt via `app/pages/uitloggen.py` (wist sessie, redirect naar `/`).

**Paginaconventies**: elke pagina begint met `st.set_page_config()`, gevolgd door
`st.markdown(CSS, unsafe_allow_html=True)` en `render_nav()`. AI-calls langer dan ~1 seconde
worden gewrapped in `st.spinner()`. Toon gebruikersvriendelijke foutmeldingen — geen ruwe tracebacks.
AI-timeout is 30 seconden; vang `anthropic.APITimeoutError` op en toon een gebruikersvriendelijke melding.

**Streaming AI-calls**: gebruik altijd `st.write_stream()`. Sla het resultaat op in
`st.session_state` zodat re-renders de API-call niet opnieuw uitvoeren.

## Authenticatie & toegangsbeheer

Login via `app/main.py`. Wachtwoord voor student én docent: **Welkom123** (SHA-256 gehashed).

`st.session_state`-sleutels na login:

| Sleutel | Aanwezig bij | Waarde |
|---|---|---|
| `rol` | altijd | `"student"` of `"docent"` |
| `df` | altijd | getransformeerd DataFrame |
| `studentnummer` | rol=student | studentnummer string |
| `mentor_naam` | rol=docent | naam van de ingelogde mentor |

Beveiligingspatroon voor docent-only pagina's:
1. Roep `vereist_docent()` aan vlak na CSS-injectie — stopt de pagina als rol ≠ "docent".
2. Roep `mentor_filter(df)` aan — geeft alleen de eigen studenten terug.

Beveiligingspatroon voor student-only pagina's:
1. Controleer `st.session_state.get("rol") == "student"` — stop met `st.stop()` bij afwijking.
2. Haal `studentnummer` op uit `st.session_state["studentnummer"]`.

## Dataset & OER-kerntaken

De Berend-dataset heeft andere kolomnamen dan het standaard Samenwijzer-formaat. `load_berend_csv()`
in `prepare.py` doet de mapping én voegt synthetische kerntaak- en werkprocesscores toe op basis
van `oer_kerntaken.json`.

`oer_kerntaken.json` bevat per opleiding de echte OER-namen voor:
- `kt_1`, `kt_2` — kerntaken (scores 0–100, gecorreleerd met voortgang + per-student ruis)
- `wp_1_1` t/m `wp_2_3` — werkprocessen

`analyze.py` laadt dit JSON eenmalig (`_laad_oer()`) en gebruikt `_oer_label(opleiding, kolom)` om
overal echte OER-namen te tonen. Studenten zonder kt_3/wp_3_x in hun opleiding krijgen NaN;
alle analyse- en labelfuncties filteren NaN weg.

## Outreach-module

`outreach_store.py` slaat alle outreach-data op in SQLite (`data/02-prepared/outreach.db`).
Init-guard `_geinitialiseerd: set[Path]` voorkomt herhaald `CREATE TABLE`.

Vier dataclasses:

| Dataclass | Tabel | Doel |
|---|---|---|
| `StudentStatus` | `student_status` | Contactstatus per student (niet_gecontacteerd → opgelost) |
| `Interventie` | `interventies` | Auditlog van elke mentor-actie |
| `Campagne` | `campagnes` | Gerichte outreach-campagne per transitiemoment |
| `WelzijnsCheck` | `welzijnschecks` | Student self-assessment (categorie + urgentie) |

Op de outreach-pagina (`4_outreach.py`): bulk-fetch van alle interventies vóór de studentenloop
via `get_alle_interventies()` om N+1-queries te vermijden.

`outreach.py` bevat:
- `at_risk_studenten()` — selecteert studenten op risico (voortgang < 40%, BSA-achterstand > 25%)
- `suggereer_verwijzing(categorie)` — geeft passende doorverwijzing op basis van hulpcategorie
- `genereer_outreach_bericht()` — streamt gepersonaliseerd bericht (optioneel met verwijzing)
- `verstuur_email()` — SMTP-verzending via STARTTLS

Transitiemomenten (`analyze.py`):
- `detecteer_transitiemoment(student)` — geeft `"bsa_risico"`, `"bijna_klaar"` of `None`
- `transitiemoment_label(moment)` — geeft leesbaar label met emoji

## Welzijn-module

Er zijn twee aparte welzijnsmodules met verschillende verantwoordelijkheden:

**`welzijn.py`** — student self-assessment via de webapp (geïnspireerd op Annie Advisor).
Vijf hulpcategorieën: `studieplanning`, `welzijn`, `financiën`, `werkplekleren`, `overig`.
Drie urgentieniveaus: 1 (kan wachten), 2 (liefst snel), 3 (dringend).
`genereer_welzijnsreactie()` streamt een korte, empathische AI-reactie na het invullen.
Mentoren zien recente welzijnschecks van hun studenten in `2_groepsoverzicht.py`.

**`wellbeing.py`** — CSV-gebaseerde welzijnssignalering voor het groepsoverzicht.
`WelzijnsCheck` dataclass, `welzijnswaarde()` en `heeft_signaal()`.
Ingestion via `prepare.load_welzijn_csv()`, analyse via `analyze.signaleringen()`.

**Gevoeligheid**: toon vrije-tekst studentreacties nooit in geaggregeerde dashboards. Alleen de
toegewezen mentor ziet individuele check-details. Urgentie 3 ("Dringend") vereist directe
actie van de mentor.

## WhatsApp-module

`whatsapp.py` verzorgt proactieve outreach via Twilio's WhatsApp API.

- Stuurt wekelijkse check-ins naar geregistreerde studenten via `stuur_checkin()`
- Verwerkt inkomende berichten (score 1–5, vrije tekst, `STOP`, `JA`-opt-in)
- Beheert AI-gesprekssessies (maximaal `MAX_EXCHANGES` uitwisselingen) via `_client()` uit `_ai.py`
- Slaat `WelzijnsCheck`-resultaten op na ontvangst van een score

`whatsapp_store.py` beheert twee SQLite-tabellen (`whatsapp.db`):
- `registraties` — koppeling studentnummer ↔ versleuteld telefoonnummer
- `sessies` — actieve AI-gesprekssessies (gesprekshistorie als JSON)

Telefoonnummers worden versleuteld opgeslagen met Fernet. Sleutel komt uit `WHATSAPP_ENCRYPT_KEY`
of wordt auto-gegenereerd in `data/02-prepared/.whatsapp.key`.

`scheduler.py` wordt aangeroepen vanuit een GitHub Actions cron-job (elke maandag 08:00):
```bash
uv run python -m samenwijzer.scheduler
# DRY_RUN=true uv run python -m samenwijzer.scheduler  ← logt berichten zonder te versturen
```

## Linting & stijl

`ruff` line-length = 100. Selectie: `E, F, I, N, W, UP`. `styles.py` heeft een E501-uitzondering
(HTML-strings zijn inherent lang). `src/samenwijzer/` en `app/` zijn de lintdoelen.

## SQLite-isolatie

Alle schrijfbewerkingen naar `outreach.db` lopen via `outreach_store.py`. Nooit raw SQL in `app/`.
`outreach.db` is gitignored — commit hem nooit.

## Bekende tech debt

Zie `docs/exec-plans/tech-debt-tracker.md` voor de actuele lijst. Alle bekende items (TD-001 t/m TD-004) zijn gesloten per 2026-04-11.

## Agent rules

Zie `AGENTS.md` voor de volledige kaart. Kernregels:
1. No handwritten code — every line is agent-generated.
2. No business logic in `app/`.
3. Validate external inputs at boundaries; trust internal types.
4. Use structured logging; no bare `print()` in production.
5. Do not log PII (student names, IDs) at INFO level or above.
6. Never push directly to `main` — open a PR via `gh pr create`.
