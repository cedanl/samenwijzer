# Execution Plan: Fase 1 — Fundament

**Status:** voltooid
**Doel:** Een werkende bèta met de twee kernfuncties die intern dagelijks bruikbaar zijn.
**Scope:** Studiedata dashboard + AI Tutor (conversationeel)

---

## Wat gebouwd is in fase 1?

### Blok A — Studiedata inladen en tonen

- [x] A1: Demo CSV-dataset aanmaken (`data/01-raw/demo/studenten.csv`)
- [x] A2: `prepare.py` — CSV inlezen, valideren, opschonen
- [x] A3: `transform.py` — Data omzetten naar analyse-klaar formaat
- [x] A4: `analyze.py` — Voortgang per student berekenen (BSA, kerntaken, werkprocessen)
- [x] A5: `visualize.py` — Grafieken: voortgangsoverzicht, kerntaakscores
- [x] A6: Streamlit pagina: **Mijn voortgang** (studentweergave)
- [x] A7: Streamlit pagina: **Groepsoverzicht** (docentweergave, filter op opleiding/cohort)
- [x] A8: Tests voor A2–A5 (alle geslaagd, 100% op pure functies)

### Blok B — AI Tutor

- [x] B1: `src/samenwijzer/tutor.py` — Claude API client (streaming, sessie-geheugen)
- [x] B2: Systeemprompt schrijven: Socratische methode, niveauaanpassing, kerntaak-context
- [x] B3: Streamlit pagina: **Tutor** — chatinterface
- [x] B4: Tutor ontvangt studentcontext (niveau, voortgang) als context uit Blok A
- [x] B5: Tests voor B1 (mock Claude API, 10/10 geslaagd)

### Blok C — Navigatie en onboarding

- [x] C1: Multipage Streamlit app (`app/pages/`)
- [x] C2: Welkomspagina met uitleg (voldoet aan onboarding spec)
- [x] C3: Login met rol (student / docent), sessie-state volledig ingericht

### Blok E — UI-polish & navigatie (toegevoegd 2026-04-10)

- [x] E1: Vaste navigatiebalk bovenin via `render_nav()` (position:fixed HTML, geen Streamlit sidebar)
- [x] E2: `uitloggen.py` — uniforme uitlogknop als pill-link, wist sessie via redirect
- [x] E3: Sidebar volledig verborgen (CSS + `showSidebarNavigation = false`)
- [x] E4: Welzijn-tegel toegevoegd aan student-startpagina (3 tegels: Voortgang, Leercoach, Welzijn)
- [x] E5: Mijn voortgang-pagina herschreven: hero-kaart, 3 statistieken, grafiek-koppels, aandachtspunten
- [x] E6: Footer-tekst gecorrigeerd naar "Samenwijzer" (was placeholder)
- [x] E7: `nowrap` op alle navigatie-pills (inclusief Uitloggen)

---

### Blok D — Outreach & Welzijn (Annie Advisor-geïnspireerd, toegevoegd 2026-04-10)

- [x] D1: `outreach.py` — at-risk selectie, AI-berichtgeneratie, e-mail, verwijslogica
- [x] D2: `outreach_store.py` — SQLite (StudentStatus, Interventie, Campagne, WelzijnsCheck)
- [x] D3: `analyze.py` — `detecteer_transitiemoment()`, `transitiemoment_label()`
- [x] D4: `4_outreach.py` — Werklijst (badges), Campagnes-tab, Effectiviteit-tab
- [x] D5: `welzijn.py` — self-assessment labels + AI-reactiegeneratie
- [x] D6: `5_welzijn.py` — student self-assessment pagina
- [x] D7: `2_groepsoverzicht.py` — welzijnschecks-sectie voor mentor

---

## Definitie van klaar

- [x] Demo draait lokaal zonder fouten (`uv run streamlit run app/main.py`)
- [x] CI is groen (lint + tests, 52/52 geslaagd, ruff clean)
- [x] Outreach + welzijn volledig geïmplementeerd en gedocumenteerd
- [ ] Minstens 3 interne gebruikers hebben de demo gezien en feedback gegeven

---

## Beslissingen

| Datum | Beslissing | Reden |
|---|---|---|
| 2026-04-07 | CSV als databron | Eenvoudig te demonstreren; geen koppeling nodig |
| 2026-04-07 | AI Tutor vóór lesmateriaal | Hoogste waarde, laagste complexiteit |
| 2026-04-10 | Student welzijnscheck toegevoegd | Annie Advisor-onderzoek: 1 op 5 studenten vraagt hulp |
| 2026-04-10 | Campagnes zonder auto-verzending | Human-in-the-loop vereiste; mentor blijft verantwoordelijk |
| 2026-04-10 | Geen WhatsApp/SMS | Buiten scope; AVG-overwegingen; mentor initieert via e-mail |
