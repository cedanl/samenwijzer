# Product Spec: Studiedata

**Status:** gereed (geïmplementeerd)

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
| bsa_behaald | float | Studiepunten behaald |
| bsa_vereist | float | Normstudepunten voor BSA |
| bsa_percentage | float | bsa_behaald / bsa_vereist (geclipt op 1.0) |
| voortgang | float | Voortgang in % (0.0–1.0) |
| risico | bool | True als bsa_percentage < 0.50 of voortgang < 0.40 |
| kt_1, kt_2 | float | Kerntaakscores (0–100) |
| wp_1_1 … wp_2_3 | float | Werkprocesscores (0–100) |

## Inzichten voor student

- Overzicht behaalde vs. vereiste studiepunten (BSA-balk)
- Kerntaak- en werkprocesscores (Altair-grafieken)
- Leerpadniveau (Starter / Onderweg / Gevorderde / Expert)
- Cohortpositie (anoniem)

## Inzichten voor docent/mentor

- Voortgang per student in begeleide groep
- Risicosignalering (rood gemarkeerd in tabel)
- Welzijnschecks van studenten (urgentie-icoon)
- Peer matching op basis van kerntaakscores
- Cohortgemiddelden per opleiding

## Acceptatiecriteria

- [x] Studiedata ingeladen vanuit CSV (synthetische dataset, 1000 studenten).
- [x] Dashboard toont voortgang per student.
- [x] Docent kan filteren op opleiding en cohort.
- [x] Risicostudenten gemarkeerd in tabel en apart getoond.
- [x] Welzijnschecks zichtbaar in groepsoverzicht.
