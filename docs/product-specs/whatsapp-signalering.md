# Product Spec: WhatsApp Signalering

**Status:** draft
**Prioriteit:** fase 2
**Geïnspireerd op:** Annie Advisor (annieadvisor.com)

## Doel

Studenten proactief bereiken op kritieke studiemomenten via WhatsApp, zonder dat zij zelf de app hoeven te openen. Signalen worden herkend en doorgestuurd naar de juiste ondersteuning — mentor, studentendienst of AI leercoach.

Annie-onderzoek toont aan dat ~80% van studenten die hulp nodig hebben dit niet zelf vragen. WhatsApp verlaagt die drempel maximaal: geen login, geen app, kanaal dat studenten al dagelijks gebruiken.

---

## Actoren

| Actor | Rol |
|---|---|
| Student | Ontvangt check-ins, antwoordt via WhatsApp |
| Mentor / docent | Ziet signaleringen in groepsoverzicht |
| Samenwijzer-systeem | Verstuurt berichten, verwerkt antwoorden |

---

## Features

### 1. Wekelijkse welzijnscheck

Het systeem stuurt elke maandagochtend een kort check-in bericht naar alle studenten met een geregistreerd telefoonnummer.

**Gespreksstroom:**
```
Samenwijzer → student:
  "Hoi [naam] 👋 Hoe was jouw week?
   Antwoord met een cijfer:
   1 – Goed, ik zit lekker in het ritme
   2 – Matig, het valt me wat zwaarder
   3 – Zwaar, ik kan wel wat hulp gebruiken"

Student → Samenwijzer:
  "2"

Samenwijzer → student (bij score 2 of 3):
  "Dank je. Weet je dat je altijd terecht kunt bij je mentor [naam]
   of via de Samenwijzer app. Wil je dat ik iets doorgeef?"
```

**Acceptatiecriteria:**
- [ ] Berichten worden verstuurd via goedgekeurde WhatsApp Business-template.
- [ ] Student ontvangt bericht alleen als telefoonnummer is geregistreerd en opt-in is gegeven.
- [ ] Systeem herkent antwoord 1, 2 of 3 en slaat welzijnsscore op.
- [ ] Bij score 2 of 3: automatisch vervolgbericht met doorverwijzing.
- [ ] Bij onherkenbaar antwoord: vriendelijk foutbericht met herhaling van opties.

---

### 2. Signaleringoverzicht voor docenten

In het groepsoverzicht verschijnt een nieuw tabblad "Signaleringen" met studenten die recent een lage welzijnsscore hebben gegeven of structureel risico vertonen (combinatie welzijn + studiedata).

**Risicoscore-logica:**
```
risicoscore = (academisch × 0.4) + (motivatie × 0.3) + (persoonlijk × 0.3)
signalering als risicoscore < 0.45  (schaal 0–1)
```

Academisch, motivatie en persoonlijk worden afgeleid uit de WhatsApp-antwoorden. In fase 1 is het één gecombineerde vraag; in fase 2 worden drie aparte vragen gesteld.

**Acceptatiecriteria:**
- [ ] Groepsoverzicht toont tabel met studenten met actieve signalering.
- [ ] Per student: naam, mentor, datum laatste check-in, risicoscore.
- [ ] Mentor kan een notitie toevoegen ("Heb contact opgenomen").
- [ ] Studenten zonder signalering worden niet getoond.
- [ ] Privacyprincipe: scores zijn alleen zichtbaar voor de eigen mentor.

---

### 3. Opt-in en telefoonnummerbeheer

WhatsApp vereist expliciete opt-in van de student vóór het ontvangen van berichten.

**Flow:**
1. Bij eerste login in Samenwijzer: opt-in scherm met uitleg.
2. Student voert telefoonnummer in en bevestigt.
3. Systeem stuurt verificatiebericht via WhatsApp ("Antwoord JA om te bevestigen").
4. Na bevestiging: telefoonnummer actief in systeem.

**Acceptatiecriteria:**
- [ ] Student kan opt-in geven én intrekken vanuit de app.
- [ ] Telefoonnummer wordt versleuteld opgeslagen (geen plaintext in CSV).
- [ ] Verificatiestap via WhatsApp vóór activatie.
- [ ] Opt-out via WhatsApp zelf mogelijk ("STOP" sturen).

---

### 4. AI-doorverwijzing vanuit WhatsApp

Bij score 2 of 3 kan de student direct via WhatsApp doorpraten met de AI leercoach, zonder de app te openen.

**Gespreksstroom (uitgebreid):**
```
Student: "3"

Samenwijzer: "Dat klinkt zwaar. Wil je even kwijt wat er speelt?
              Of wil je dat ik je mentor [naam] een seintje geef?"

Student: "Mijn stage loopt niet lekker"

Samenwijzer (AI): [Socratische reactie via Claude API, max. 3 berichten]
                  "Wat maakt het lastig — de taken zelf, de sfeer,
                   of iets anders?"

Na 3 berichten: "Ik stuur je een link naar de leercoach voor een
                 volledig gesprek: [link naar app]"
```

**Acceptatiecriteria:**
- [ ] Bij score 2/3: optie voor kort AI-gesprek via WhatsApp (max. 3 exchanges).
- [ ] Na 3 exchanges: doorverwijzing naar app of mentor.
- [ ] AI-reacties zijn kort (max. 2 zinnen) en geschikt voor mobiel.
- [ ] Gesprek wordt opgeslagen als context voor leercoach-sessie in de app.

---

## Technische architectuur

```
┌─────────────────────────────────────────────────────────┐
│  GitHub Actions (cron: elke maandag 08:00)              │
│  → src/samenwijzer/scheduler.py                         │
│    → whatsapp.py → Twilio API → WhatsApp                │
└───────────────────────┬─────────────────────────────────┘
                        │ inkomend antwoord
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Webhook endpoint (FastAPI, apart van Streamlit)         │
│  → src/samenwijzer/whatsapp.py → wellbeing.py           │
│  → data/02-prepared/welzijn.csv                         │
└───────────────────────┬─────────────────────────────────┘
                        │ signalering
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Streamlit app                                           │
│  → app/pages/2_groepsoverzicht.py (signaleringtabblad)  │
└─────────────────────────────────────────────────────────┘
```

**Nieuwe modules:**

| Module | Verantwoordelijkheid |
|---|---|
| `src/samenwijzer/whatsapp.py` | Verzenden en ontvangen via Twilio/Meta |
| `src/samenwijzer/wellbeing.py` | Welzijnscheck datamodel en risicoscore |
| `src/samenwijzer/scheduler.py` | Wekelijkse verzending |
| `app/webhook.py` | FastAPI webhook (buiten Streamlit) |

**Externe afhankelijkheden:**

| Service | Gebruik | Kosten |
|---|---|---|
| Twilio WhatsApp API | Verzenden/ontvangen berichten | ~€0,05/bericht |
| Meta WhatsApp Business | Vereist voor goedkeuring templates | Gratis t/m 1.000 gesprekken/maand |
| FastAPI | Webhook endpoint | Open source |

**Omgevingsvariabelen:**
```
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_WHATSAPP_NUMBER
```

---

## Privacy en veiligheid

- Telefoonnummers worden **niet** opgeslagen in de demo CSV; alleen in beveiligde opslag (fase 2: database of secrets manager).
- Welzijnsscores zijn **alleen zichtbaar voor de eigen mentor** — niet voor andere docenten.
- Opt-out is altijd mogelijk via "STOP" sturen aan het WhatsApp-nummer.
- Gesprekken via WhatsApp worden **niet langer dan 30 dagen** bewaard.
- Voldoet aan AVG: doelbinding (studiesucces), minimale gegevensverwerking, recht op verwijdering.

---

## Uitsluitingen (fase 2)

- Geen authenticatie of account koppeling — telefoonnummer als identifier.
- Geen twee-weg conversatie buiten de gedefinieerde flows.
- Geen SMS-fallback (alleen WhatsApp).
- Geen push notificaties vanuit de Streamlit-app zelf.

## Fase 3 (toekomst)

- SMS-fallback voor studenten zonder WhatsApp.
- Meerdere check-in momenten (bijv. voor tentamenperiode).
- Integratie met studenteninformatiesysteem (SIS) voor automatisch telefoonnummer ophalen.
- Notificatie naar mentor via e-mail bij score 3.
