# Spec: chat-KD-fallback bij onleesbare OER

**Datum:** 2026-06-09
**Status:** spec (goedgekeurd, implementatie volgt)
**Gerelateerd:** issue #180 (deel 1), PR #181 (db-kant — ingest KD-fallback), `kd-fallback-kerntaken.md`

## Probleem

Een handvol OER's (de gescande Da Vinci cohort-2025 examenplannen, ~13 crebo's) heeft géén
leesbare tekstlaag: `chat.laad_oer_tekst()` geeft een lege string terug. PR #181 loste de
**db-kant** op (kerntaken komen nu via het kwalificatiedossier), maar de **chat-laag** haakt nog
af: de pagina's bouwen de system-prompt alleen `if oer_tekst`, dus bij een lege OER wordt
`oer_systeem = ""` en toont de chat `LAGE_RELEVANTIE_BERICHT` — ook al zijn er bruikbare bronnen
(KD, instellingsregelingen) geladen.

Gevolg: studenten/mentoren met zo'n OER krijgen op élke chatvraag de "ik kan dit niet
beantwoorden"-melding, terwijl het landelijke kwalificatiedossier het antwoord vaak wél bevat.

## Doel

Wanneer de OER-fulltext onleesbaar is **maar er een KD óf instellingsbron beschikbaar is**, laat
de chat tóch antwoorden op basis van die bronnen — met (a) een zichtbare melding aan de gebruiker
en (b) een correcte citatie — in plaats van `LAGE_RELEVANTIE_BERICHT`.

### Niet-doelen (YAGNI / scope-grens)
- **Geen rotatie-OCR** om de gescande OER-fulltext zelf te herstellen. Dat is deel 2 van #180 en
  draagt een kwaliteitsrisico voor de verbatim-citatieplicht (OCR-tekst corrumpeert de woordelijke
  bewoording). Buiten deze spec.
- `laad_oer_tekst()` blijft ongewijzigd een lege string teruggeven bij een onleesbare OER — dat is
  correct gedrag; de fix zit in de consumenten.
- Geen wijziging aan het db-/ingest-pad (al gedekt door PR #181).

## Terugval-trigger (besloten)

De chat valt terug zodra er **een KD óf een instellingsbron** is. Concreet: bouw de system-prompt
als `oer_tekst` **of** `dossier_tekst` **of** `instelling_bronnen` niet leeg is.

- **Skills alleen** is géén trigger (te magere basis voor OER-achtige vragen), maar een
  skills-blok mag wél meeliften als het toevallig aanwezig is.
- Is er werkelijk niets (geen OER-tekst, geen KD, geen instellingsbron) → de pagina toont nog
  steeds `LAGE_RELEVANTIE_BERICHT`.

## Transparantie (besloten)

De gebruiker krijgt een **zichtbare, eenmalige melding** boven de chat wanneer de terugval actief
is (OER onleesbaar):

> "De OER van jouw opleiding is niet machine-leesbaar; antwoorden komen uit het landelijke
> kwalificatiedossier en de instellingsregelingen."

Past bij de citatieplicht-filosofie van de app: de student moet weten dat het antwoord niet uit de
eigen OER komt. Renderen via de bestaande `alert()`-helper (info-niveau), niet via inline HTML.

## Ontwerp (aanpak A — "OER-onleesbaar"-modus in `bouw_systeem`)

### 1. `chat.py` — `bouw_systeem`

`bouw_systeem` accepteert nu al een lege `oer_tekst`, maar het `_SYSTEEM_TEMPLATE` hardcodeert
"de OER is leidend" en het KD-gebruik-voorbeeld "De OER beschrijft dit niet. Volgens het
kwalificatiedossier…". Bij een volledig lege OER leidt dat tot rommelige output (elke claim
voorafgegaan door "De OER beschrijft dit niet") en een verwarrend leeg OER-blok.

Wijziging:
- Detecteer `oer_onleesbaar = not oer_tekst.strip()`.
- In de onleesbaar-modus:
  - **Citatie-instructie wisselen**: vervang "de OER is leidend / raadpleeg het KD alléén als de
    OER het niet behandelt" door een instructie in de geest van: *"De OER van deze opleiding is
    niet beschikbaar. Baseer je antwoord op het kwalificatiedossier en de instellingsregelingen en
    citeer die direct (bron + vindplaats + woordelijk citaat). Begin niet elke claim met 'De OER
    beschrijft dit niet'."* De rest van de citatieplicht (3 elementen, blockquote-vorm) blijft
    gelijk.
  - **OER-blok vervangen**: i.p.v. `=== ONDERWIJS- EN EXAMENREGELING (OER) ===\n{lege tekst}` een
    korte notitie `=== ONDERWIJS- EN EXAMENREGELING (OER) ===\n(De OER van deze opleiding is niet
    machine-leesbaar; gebruik de aanvullende bronnen hieronder.)`.
- **Contract ongewijzigd**: `bouw_systeem` blíjft altijd een prompt bouwen (ook bij lege OER) —
  dat is het bestaande contract (zie `test_bouw_systeem_leeg_bij_geen_tekst`). Alleen de *inhoud*
  wisselt naar onleesbaar-modus. De "moeten we überhaupt antwoorden?"-beslissing blijft in de
  pagina's (zie sectie 3), nu verruimd naar "is er een OER-tekst óf KD óf instellingsbron".

Implementatie-richting: een interne `oer_onleesbaar`-tak die een variant-citatieblok en
variant-OER-blok kiest; bestaande aanroepers blijven werken (geen verplichte nieuwe parameter).

### 2. `chat.py` — `bouw_gecombineerd_systeem` (publieke multi-OER)

`0_oer_vraag.py` filtert nu OER's met lege tekst weg (`if tekst:`) vóór ze als item meegaan.
Wijziging: neem een OER-loos item tóch op wanneer het een `dossier_tekst` (of instellingsbron)
heeft, gerenderd als KD-blok met dezelfde "OER niet beschikbaar"-notitie per item. De gecombineerde
citatie-instructie krijgt dezelfde onleesbaar-nuance als bij `bouw_systeem`.

### 3. De drie pagina's

`1_oer_assistent.py`, `5_begeleidingssessie.py`, `0_oer_vraag.py`:
- **Gate verruimen**: vervang de afhaak-conditie `if oer_tekst` door een "is er een bruikbare
  bron?"-check: `heeft_bron = bool(oer_tekst.strip() or dossier_tekst or instelling_bronnen)`.
  Bouw `oer_systeem` alleen als `heeft_bron`; anders blijft `oer_systeem = ""` → `LAGE_RELEVANTIE_BERICHT`.
- **Sessie-flag** `oer_onleesbaar` afleiden: `heeft_bron and not oer_tekst.strip()` (prompt wél
  gebouwd, maar zonder leesbare OER).
- **Banner** tonen via `st.info(...)` boven de chat als `oer_onleesbaar` waar is (consistent met de
  bestaande `st.info(LAGE_RELEVANTIE_BERICHT)`-aanpak; dit subproject heeft geen `alert()`-helper).
- Voor de multi-OER-pagina (`0_oer_vraag.py`): banner tonen als ten minste één geselecteerde OER
  onleesbaar is (afleiden uit de per-OER laad-resultaten).

## Tests

### Unit (`tests/test_chat.py` — bestaat al)
- `bouw_systeem("", …, dossier_tekst=<KD>)` → bevat het KD-blok én de onleesbaar-modus-instructie
  (assert op een kenmerkende zin, bv. "OER van deze opleiding is niet beschikbaar"), géén
  hardcoded "de OER is leidend" meer.
- `bouw_systeem(<echte OER-tekst>, …)` → ongewijzigd: normale modus, bevat "de OER is leidend",
  géén onleesbaar-zin (regressiecheck; bestaande tests `test_bouw_systeem_bevat_oer_tekst` e.d.
  blijven groen).
- `bouw_systeem("", "Kok", "Da Vinci")` (geen bron) → bouwt nog steeds een prompt (contract
  ongewijzigd, `test_bouw_systeem_leeg_bij_geen_tekst` blijft groen) maar in onleesbaar-modus.
- `bouw_gecombineerd_systeem([<OER-loos item met KD>])` (één item) → delegeert naar `bouw_systeem`,
  bevat KD-blok + onleesbaar-modus. Meervoudig met één OER-loos-maar-KD-item → dat item opgenomen
  als KD-blok.

> De "echt-niets → LAGE_RELEVANTIE_BERICHT"-beslissing zit in de pagina-gate, niet in
> `bouw_systeem`; die wordt via de UI-smoke-test gedekt (een OER zonder enige bron blijft de
> melding tonen).

### UI-smoke-test (verplicht — raakt 3 pagina's)
Met een Da Vinci-account op een onleesbare OER (zie aandachtspunt):
- Banner zichtbaar boven de chat.
- Chatvraag → antwoord begint/citeert "Volgens het kwalificatiedossier…" (niet `LAGE_RELEVANTIE_BERICHT`).
- Een OER mét leesbare tekst toont géén banner en gedraagt zich ongewijzigd (regressiecheck).

## Aandachtspunt: testdata

Er hangt momenteel **geen student** aan de 13 onleesbare OER's (de seed draaide vóór PR #181, toen
ze `geindexeerd=0` waren). Voor de UI-smoke-test koppelen we tijdelijk een testaccount aan bv.
crebo 25168, óf nemen we een gerichte re-seed mee. Te beslissen bij het implementatieplan.

## Bestanden (verwachte aanraking)
- `src/validatie_samenwijzer/chat.py` — `bouw_systeem`, `bouw_gecombineerd_systeem`, template(s).
- `app/pages/1_oer_assistent.py`, `app/pages/5_begeleidingssessie.py`, `app/pages/0_oer_vraag.py`
  — gate + sessie-flag + banner.
- `tests/test_chat.py` (of bestaand chat-testbestand) — unit-tests.
- CLAUDE.md — korte notitie bij de OER-chat-flow over de onleesbaar-modus (na implementatie).
