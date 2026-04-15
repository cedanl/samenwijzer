# Product Sense

**Regiobijeenkomst 07-04-2026**

## Vision

Samenwijzer geeft studenten en docenten inzicht in leermogelijkheden op basis van studievoortgang.
De student leert op eigen manier en tempo. Zelfredzaamheid door inzicht in:

- **Waar sta ik?** — huidige voortgang en niveau
- **Waar moet ik naartoe?** — doelen op basis van opleiding
- **Hoe kom ik daar?** — gepersonaliseerd leerpad en AI-ondersteuning
- **Hoe gaat het met mij?** — welzijn en signalering naar begeleider

## Pijler — Studiesucces

Gepersonaliseerde leerondersteuning op basis van studiedata en AI.

### AI features (op prioriteit)

| Prioriteit | Feature | Status |
|---|---|---|
| 1 | Persoonlijke AI tutor (Socratisch) | gereed |
| 2 | Studiedata dashboard | gereed |
| 3 | Gepersonaliseerd lesmateriaal (4 niveaus) | gereed |
| 4 | Oefentoetsen met automatisch nakijken | gereed |
| 5 | Feedback op ingeleverd werk | gereed |
| 6 | Welzijnscheck student self-assessment | gereed |
| 7 | Outreach campagnebeheer (docent) | gereed |
| 8 | Rollenspel (beroepssituaties, stage, sollicitatie) | gereed |
| 9 | Peer learning netwerk | backlog |

### Lesmateriaal niveaus

| Niveau | Label |
|---|---|
| 1 | Starter |
| 2 | Op weg |
| 3 | Gevorderde |
| 4 | Expert |

## Pijler — Proactieve ondersteuning (geïnspireerd op Annie Advisor)

Onderzoek toont dat slechts 1 op de 5 studenten die hulp nodig heeft, ook actief om hulp vraagt.
Samenwijzer verlaagt deze drempel op twee manieren:

### Voor studenten
- **Welzijnscheck** (`5_welzijn.py`) — student geeft zelf aan waar moeite mee is
  (categorie + urgentie). AI geeft direct een empathische reactie. Mentor ontvangt signaal.
- **WhatsApp check-in** — wekelijks proactief bereikt via WhatsApp (score 1–3); bij score 2/3
  volgt een kort AI-gesprek (max. 3 exchanges) en doorverwijzing naar mentor of app.

### Voor docenten/mentoren
- **Transitiemoment-detectie** — automatische badge bij BSA-risico of bijna-afstuderen
- **Campagnebeheer** — gerichte outreach per transitiemoment met berichttemplate
- **Verwijslogica** — per hulpcategorie een passende doorverwijzing (SLB-er, decaan, etc.)
- **Effectiviteitsdashboard** — contactratio, responsratio, statustrechter per mentor

## Target users

- **Primair:** studenten (zelfredzaamheid, eigen leerpad, laagdrempelig hulp vragen)
- **Secundair:** docenten en mentoren (inzicht in voortgang, proactieve outreach)

## Non-goals

- Geen volwaardig LMS — Samenwijzer is een aanvulling, geen vervanging.
- Geen SMS-fallback of andere berichtenkanalen dan WhatsApp — buiten scope fase 2.
- Geen volledig autonome campagneverzending — altijd mentor-goedkeuring vereist.
- Aansluiting op arbeidsmarkt (RIASOC etc.) — buiten scope voor nu.
