# Product Spec: Studiedata

**Status:** draft

## Doel

Inzicht geven aan student en docent op basis van beschikbare studiedata.

## Datamodel (student)

| Veld | Type | Beschrijving |
|---|---|---|
| studentnummer | string | Unieke identifier |
| naam | string | Volledige naam |
| mentor | string | Naam van de mentor |
| opleiding | string | Naam van de opleiding |
| crebo | string | CREBO-code |
| niveau | int | MBO-niveau (1–4) |
| leerweg | string | BBL / BOL |
| cohort | string | Instroom cohort (bijv. "2024-2025") |
| leeftijd | int | Leeftijd in jaren |
| geslacht | string | Geslacht |
| bsa | float | Studiepunten behaald (BSA) |
| voortgang | float | Voortgang in % |
| kerntaken | dict | Score per kerntaak |
| werkprocessen | dict | Score per werkproces |

## Inzichten voor student

- Overzicht behaalde vs. vereiste studiepunten
- Groei per kerntaak en werkproces over tijd
- Vergelijking met cohortgemiddelde (anoniem)

## Inzichten voor docent/mentor

- Overzicht voortgang per student in begeleide groep
- Signalering van studenten met risico op uitval (BSA onder norm)

## Acceptatiecriteria

- [ ] Studiedata kan worden ingeladen vanuit CSV (demo dataset beschikbaar).
- [ ] Dashboard toont voortgang per student.
- [ ] Docent kan filteren op opleiding, cohort, mentor.
