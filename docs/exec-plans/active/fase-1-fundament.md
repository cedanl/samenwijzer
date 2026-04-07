# Execution Plan: Fase 1 — Fundament

**Status:** active
**Doel:** Een werkende bèta met de twee kernfuncties die intern dagelijks bruikbaar zijn.
**Scope:** Studiedata dashboard + AI Tutor (conversationeel)

---

## Wat bouwen we in fase 1?

### Blok A — Studiedata inladen en tonen

Studenten en docenten kunnen voortgang inzien op basis van een CSV-dataset.

**Stappen:**
- [x] A1: Demo CSV-dataset aanmaken (`data/01-raw/demo/studenten.csv`)
- [x] A2: `prepare.py` — CSV inlezen, valideren, opschonen
- [x] A3: `transform.py` — Data omzetten naar analyse-klaar formaat
- [x] A4: `analyze.py` — Voortgang per student berekenen (BSA, kerntaken, werkprocessen)
- [x] A5: `visualize.py` — Grafieken: voortgangsoverzicht, kerntaakscores
- [x] A6: Streamlit pagina: **Mijn voortgang** (studentweergave)
- [x] A7: Streamlit pagina: **Groepsoverzicht** (docentweergave, filter op opleiding/cohort)
- [x] A8: Tests voor A2–A5 (27/27 geslaagd, 100% op pure functies)

### Blok B — AI Tutor

Een conversationele tutor die de student Socratisch begeleidt.

**Stappen:**
- [ ] B1: `src/samenwijzer/tutor.py` — Claude API client (streaming, sessie-geheugen)
- [ ] B2: Systeemprompt schrijven: Socratische methode, niveauaanpassing, kerntaak-context
- [ ] B3: Streamlit pagina: **Tutor** — chatinterface
- [ ] B4: Tutor ontvangt studentcontext (niveau, voortgang) als context uit Blok A
- [ ] B5: Tests voor B1 (mock Claude API)

### Blok C — Navigatie en onboarding

- [ ] C1: Multipage Streamlit app (`app/pages/`)
- [ ] C2: Welkomspagina met uitleg (voldoet aan onboarding spec)
- [ ] C3: Sessie-state: student selecteert zichzelf uit lijst (geen auth in fase 1)

---

## Wat bouwen we NIET in fase 1

- Gepersonaliseerd lesmateriaal (fase 2)
- Oefentoetsen (fase 2)
- Rollenspel (fase 2)
- Peer learning (fase 3)
- Authenticatie (fase 2)
- Aansluiting op arbeidsmarkt (buiten scope)

---

## Definitie van klaar

- Demo draait lokaal zonder fouten (`uv run streamlit run app/main.py`)
- CI is groen (lint + tests)
- Minstens 3 interne gebruikers hebben de demo gezien en feedback gegeven
- Bekende problemen zijn gelogd in `docs/exec-plans/tech-debt-tracker.md`

---

## Beslissingen

| Datum | Beslissing | Reden |
|---|---|---|
| 2026-04-07 | Geen auth in fase 1 | Snelheid; student kiest zichzelf uit lijst |
| 2026-04-07 | CSV als databron | Eenvoudig te demonstreren; geen koppeling nodig |
| 2026-04-07 | AI Tutor vóór lesmateriaal | Hoogste waarde, laagste complexiteit |
