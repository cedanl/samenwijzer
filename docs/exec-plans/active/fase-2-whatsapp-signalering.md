# Execution Plan: Fase 2 — WhatsApp Signalering

**Status:** draft
**Doel:** Studenten proactief bereiken via WhatsApp met wekelijkse welzijnschecks; signalen zichtbaar maken voor mentoren in het groepsoverzicht.
**Spec:** `docs/product-specs/whatsapp-signalering.md`
**Afhankelijk van:** Fase 1 afgerond (studiedata + AI leercoach)

---

## Wat bouwen we in fase 2?

### Blok D — Welzijnsdata en risicosignalering

Fundament voor alle signaleringsfunctionaliteit: datamodel, opslag en risicoscoreberekening.

**Stappen:**
- [x] D1: `src/samenwijzer/wellbeing.py` — `WelzijnsCheck` dataclass, `welzijnswaarde()`, `heeft_signaal()`
- [x] D2: Demo CSV aanmaken: `data/01-raw/demo/welzijn.csv` (studentnummer, datum, scores)
- [x] D3: `prepare.py` uitbreiden — `load_welzijn_csv()` met validatie en opschoning
- [x] D4: `analyze.py` uitbreiden — `signaleringen()`: combineer welzijnsscores met studiedata
- [x] D5: Tests voor D1–D4 — 21/21 geslaagd, `wellbeing.py` 100% coverage

### Blok E — Signaleringoverzicht (docentview)

Mentoren zien in het groepsoverzicht welke studenten een signaal afgeven.

**Stappen:**
- [x] E1: `app/pages/2_groepsoverzicht.py` uitbreiden — tabblad "Signaleringen"
- [x] E2: Tabel met naam, mentor, datum laatste check-in, welzijnswaarde en toelichting
- [x] E3: Mentor kan notitie toevoegen — opslaan in `data/02-prepared/notities.csv`
- [x] E4: Privacyfilter: signaleringen alleen zichtbaar bij mentorfilter; `filter_signaleringen_voor_mentor()`
- [x] E5: Tests voor E3–E4 — 32/32 geslaagd, `wellbeing.py` 100% coverage

### Blok F — WhatsApp koppeling

Verzenden en ontvangen van berichten via Twilio WhatsApp API.

**Stappen:**
- [ ] F1: `uv add twilio` — dependency toevoegen
- [ ] F2: `src/samenwijzer/whatsapp.py` — `stuur_checkin()`, `verwerk_antwoord()`, `stuur_foutbericht()`
- [ ] F3: Twilio sandbox opzetten, template aanmaken en testen met 1 testnummer
- [ ] F4: `app/webhook.py` — FastAPI endpoint `/webhook/whatsapp` (ontvangt inkomende berichten)
- [ ] F5: Webhook lokaal testen via ngrok; antwoorden verwerken naar `welzijn.csv`
- [ ] F6: Meta template goedkeuring aanvragen voor productie-template `wekelijkse_checkin_v1`
- [ ] F7: Tests voor F2 (mock Twilio-client, antwoordparsing, foutpaden)

### Blok G — Opt-in en telefoonnummerbeheer

Studenten geven toestemming en registreren hun telefoonnummer.

**Stappen:**
- [ ] G1: Opt-in scherm toevoegen aan welkomspagina (`app/main.py`) — uitleg + invoerveld nummer
- [ ] G2: `src/samenwijzer/whatsapp.py` uitbreiden — `stuur_verificatie()`, `verwerk_bevestiging()`
- [ ] G3: Telefoonnummer versleuteld opslaan (fase 2: `.env`-bestand lokaal; fase 3: secrets manager)
- [ ] G4: Opt-out verwerken: "STOP" bericht → nummer deactiveren in opslag
- [ ] G5: Tests voor G2–G4 (verificatieflow, opt-out)

### Blok H — Wekelijkse verzending

Automatische verzending elke maandagochtend via GitHub Actions.

**Stappen:**
- [ ] H1: `src/samenwijzer/scheduler.py` — `stuur_wekelijkse_checkins(df_studenten)`
- [ ] H2: GitHub Actions workflow `.github/workflows/checkin.yml` — cron `0 8 * * 1`
- [ ] H3: Secrets instellen in GitHub repo: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`
- [ ] H4: Droge run testen (log berichten zonder versturen — `DRY_RUN=true` envvar)
- [ ] H5: Tests voor H1 (mock Twilio, alleen nummers met opt-in ontvangen bericht)

### Blok I — AI-doorverwijzing via WhatsApp

Bij score 2 of 3 kan de student kort doorpraten met de AI leercoach via WhatsApp.

**Stappen:**
- [ ] I1: `src/samenwijzer/whatsapp.py` uitbreiden — gespreksstatus bijhouden per nummer (max. 3 exchanges)
- [ ] I2: `coach.py` koppeling — korte AI-reactie genereren (max. 2 zinnen, mobiel formaat)
- [ ] I3: Na 3 exchanges: doorverwijzingsbericht met link naar app sturen
- [ ] I4: Gesprek opslaan als context voor leercoach-sessie in de app (`data/02-prepared/`)
- [ ] I5: Tests voor I1–I3 (gespreksstatus, exchange-limiet, doorverwijzing)

---

## Wat bouwen we NIET in fase 2

- SMS-fallback (fase 3)
- Meerdere check-in momenten per week (fase 3)
- Koppeling met SIS voor automatisch telefoonnummer ophalen (fase 3)
- E-mail notificaties naar mentor (fase 3)
- Authenticatie of accountkoppeling (buiten scope fase 2)

---

## Volgorde van uitvoering

```
D (fundament) → E (docentview) → F (WhatsApp basis) → G (opt-in) → H (scheduler) → I (AI)
```

D en E kunnen gebouwd worden zonder Twilio-account. F t/m I vereisen externe service-setup.

---

## Technische vereisten

| Vereiste | Actie |
|---|---|
| Twilio account | Aanmaken op twilio.com — gratis sandbox |
| Meta Business verificatie | Aanvragen bij Meta (1–3 werkdagen) voor productie |
| ngrok (dev) | `uv tool install ngrok` voor lokale webhook-tests |
| FastAPI | `uv add fastapi uvicorn` |
| GitHub Secrets | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER` |

---

## Definitie van klaar

- [ ] Wekelijkse check-in verstuurd en ontvangen in Twilio sandbox (end-to-end test)
- [ ] Antwoord verwerkt en opgeslagen in `welzijn.csv`
- [ ] Signalering zichtbaar in groepsoverzicht voor mentor
- [ ] Opt-in en opt-out werken correct
- [ ] CI groen (lint + tests voor alle nieuwe modules)
- [ ] Privacy review gedaan: alleen eigen mentor ziet scores

---

## Beslissingen

| Datum | Beslissing | Reden |
|---|---|---|
| 2026-04-09 | Twilio boven Meta Cloud API | Snellere sandbox, minder setup; migratie later mogelijk |
| 2026-04-09 | FastAPI naast Streamlit voor webhook | Streamlit ondersteunt geen inkomende webhooks |
| 2026-04-09 | Één gecombineerde vraag in fase 2 | Drie losse vragen in fase 3 na validatie van response-rates |
| 2026-04-09 | Max. 3 WhatsApp-exchanges voor AI | Conversaties buiten de app moeten kort blijven; diepgang in de app |
| 2026-04-09 | Telefoonnummer lokaal versleuteld in fase 2 | Secrets manager te zwaar voor deze fase; AVG-vereiste blijft gelden |
