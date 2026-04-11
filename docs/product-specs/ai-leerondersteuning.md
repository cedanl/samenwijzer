# Product Spec: AI Leerondersteuning

**Status:** geïmplementeerd (features 1–3, 6 gereed; 4–5 backlog)

## Doel

AI-gedreven hulpmiddelen die de student ondersteunen bij het leren, afgestemd op niveau en behoefte.

## Features

### 1. Gepersonaliseerd lesmateriaal

Bestaand of gegenereerd lesmateriaal aangeboden op het niveau van de student.

**Niveaus:**
| Niveau | Label |
|---|---|
| 1 | Starter |
| 2 | Op weg |
| 3 | Gevorderde |
| 4 | Expert |

**Invalshoeken:**
- Herschrijven van bestaand materiaal naar het niveau van de student.
- Genereren van nieuw materiaal op basis van kerntaak, werkproces of vak.

**Acceptatiecriteria:**
- [x] Student selecteert kerntaak/werkproces en niveau.
- [x] App genereert lesmateriaal via Claude API (`genereer_lesmateriaal()` in `coach.py`).
- [x] Output is leesbaar en educatief verantwoord op het gekozen niveau.

---

### 2. Oefentoetsen met automatisch nakijken

Toetsvragen gegenereerd op basis van lesmateriaal (zie feature 1).

**Acceptatiecriteria:**
- [x] Student kan een oefentoets starten op basis van een kerntaak.
- [x] Antwoorden worden automatisch nagekeken door de AI (`controleer_antwoorden()` in `coach.py`).
- [x] Student ontvangt toelichting bij fout antwoord.

---

### 3. Feedback op ingeleverd werk

Student levert tekst of antwoord in; AI geeft gerichte feedback.

**Acceptatiecriteria:**
- [x] Student kan tekst inleveren.
- [x] AI geeft feedback op inhoud, structuur en niveau (`geef_feedback_op_werk()` in `coach.py`).
- [x] Feedback is constructief en aansluitend bij het leerniveau.

---

### 4. Peer learning netwerk

Studenten kunnen vragen stellen en antwoorden geven aan elkaar.
*(Backlog — v0.2)*

---

### 5. Rollenspel

Oefenen van beroepssituaties via een gespreksinterface.

**Scenario's:**
- Beroepssituaties (passend bij kerntaak/werkproces)
- Stagegesprekken
- Sollicitatiegesprekken

**Acceptatiecriteria:**
- [ ] Student kiest een scenario.
- [ ] AI speelt de tegenpartij (werkgever, stagebegeleider, collega).
- [ ] Na afloop geeft de AI feedback op het gesprek.

*(Backlog — v0.2)*

---

### 6. Persoonlijke AI tutor

Een conversationele tutor die de student begeleidt bij leren en nadenken.

**Filosofie:**
- Moedigt student aan zelf antwoorden te formuleren (Socratische methode).
- Verbindt ideeën, geeft feedback en biedt oefeningen aan waar nodig.
- Geeft géén directe antwoorden maar stelt verdiepende vragen.

**Acceptatiecriteria:**
- [x] Student kan een open gesprek voeren met de tutor (`stuur_bericht()` in `tutor.py`).
- [x] Tutor past toon en complexiteit aan op basis van niveau van de student.
- [x] Tutor verwijst naar relevante kerntaken en werkprocessen via `StudentContext`.
