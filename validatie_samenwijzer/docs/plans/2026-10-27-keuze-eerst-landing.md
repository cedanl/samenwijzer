# Spec: keuze-eerst startpagina

**Status:** ter goedkeuring (via PR) · **Datum:** 2026-10-27 · **Mockup:** `docs/mockups/keuze-c-combinatie.html`

## Probleem

Op de publieke startpagina staat het vraagveld bovenaan en de opleidingskiezer (vier `<select>`'s, later
uitgegrijsd) als bijzaak eronder. Gebruikers missen de kiezer, en de assistent moet de juiste OER raden
uit een vrije vraag.

## Doel

Eerst **kiezen**, dan **vragen**: instelling → opleiding → leerweg → cohort, daaronder het vraagveld,
vergrendeld tot de keuze compleet is. Visueel in de bestaande taal (papier, inkt, vermiljoen), compact,
met een dun rood randje voor "hier ben je nu" en een dun rood lijntje in het vraagveld.

## Beslissingen

1. **Geen API-wijziging.** `/api/opleidingen` blijft instelling → leerweg → opleiding → cohort. De
   nieuwe volgorde (opleiding vóór leerweg) wordt client-side uit dezelfde boom afgeleid: de
   opleidingen van een school = unie over haar leerwegen; de leerwegen van een opleiding = de
   leerwegen waarin die voorkomt; cohorten per (opleiding, leerweg).
2. **Eén kiezer-component** (`bouwCascade` in `app.js`), hergebruikt op de startpagina en in de
   overlay-picker (modus `kies`, na een vrije vraag). Zelfde regels in beide.
3. **Auto-selectie:** heeft een stap maar één mogelijkheid (leerweg of cohort), dan wordt die gekozen
   en als "automatisch gekozen" getoond (de bestaande kiezer verborg het cohort in dat geval).
4. **Max. 3 studiegidsen** vergelijken blijft (`MAX_GIDSEN`); "+ vergelijk met een andere" voegt de
   huidige keuze toe en start een nieuwe. Een keuze die meer dan de resterende ruimte aan OER-id's
   levert kan niet worden toegevoegd (bestaande regel).
5. **Vraagveld:** vergrendeld zolang er geen compleet gekozen studiegids is (en geen eerder
   toegevoegde). Ontgrendeld: invoerveld + 3 voorbeeldvragen sturen de vraag mét de gekozen
   `oer_ids` (`/api/kies`, daarna `/api/chat`); de modus-routering via `/api/vraag` wordt dan niet
   doorlopen. De overlay-chat voor vervolgvragen verandert niet.
6. **De vrije-vraag-ingang op de startpagina vervalt:** het hero-vraagveld wordt het vergrendelde
   vraagveld onder de kiezer; het afsluitende vraagveld onderaan wordt een knop naar de kiezer.
   `/api/vraag` en de modi `kies`/`intake` blijven bestaan voor de overlay (vervolgbeurten).
7. **Reset:** "Nieuw gesprek" in de overlay zet ook de kiezer terug.

## Acceptatiecriteria (verifieerbaar)

| # | Criterium | Check |
|---|---|---|
| 1 | `GET /` bevat de kiezer vóór het vraagveld en géén `data-ask`-formulier meer | pytest |
| 2 | `/api/opleidingen` ongewijzigd (bestaande tests groen) | pytest |
| 3 | Stappen worden in volgorde ontgrendeld; later gekozen stap wist de stappen erna | browser |
| 4 | Eén leerweg/cohort → automatisch gekozen | browser |
| 5 | Vraagveld vergrendeld tot keuze compleet; daarna ontgrendeld | browser |
| 6 | Vraag versturen opent de overlay met de gekozen gids(en) in de labels | browser |
| 7 | Tot 3 gidsen; 4e wordt geweigerd | browser |
| 8 | Overlay-picker (modus `kies`) gebruikt dezelfde kiezer en opent de gids | browser |
| 9 | Geen horizontaal scrollen op 390 px; dropdown wordt bottom sheet | browser |
| 10 | `ruff check`/`ruff format --check` en `pytest` groen | lokaal |

## Buiten scope

Ingelogde pagina's (`/student`, `/mentor`), de chat-overlay zelf, de API, de database, "Zo werkt
het"/bronnen-secties (alleen kleurtokens/lijntjes die al in de pagina zitten).

## Risico's

- De opleidingsnaam kan binnen één school voor twee leerwegen anders gespeld zijn (zelfde crebo,
  andere naam) en verschijnt dan als twee opleidingen. Zelfde gedrag als nu, andere presentatie.
- Het schrappen van de vrije-vraag-ingang is een productkeuze (door de gebruiker gevraagd); terug te
  draaien door het hero-formulier te herstellen.
