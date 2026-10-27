# Spec: flexibele documentlaag (alle instellingsdocumenten beschikbaar voor de assistent)

**Status:** ter beoordeling (spec-PR, nog geen code) · **Datum:** 2026-10-27
**Aanleiding:** testvraag over het Curio-kluiscontroleprotocol: de assistent wist er niets van. Onderzoek
van alle aangeleverde documenten (Curio, Deltion, Graafschap, KW1C, Rijn IJssel + werkgroepstukken) laat
zien dat het gat structureel is. Buiten scope: het "Format Inventarisatie tussenfases"-formulier.

## Probleem

De chat leest vier bronnen: OER, KD (één per crebo), skills en een **vaste lijst van 12 instellingsbrede
"soorten"**, met `UNIQUE (instelling_id, soort)`. Daardoor:

1. Elk document dat niet in die 12 soorten past, is onzichtbaar (kluisprotocol, veiligheidsplan,
   schoolkosten, praktijkovereenkomst, studiekeuzegids, onderwijsplannen, studiegidsen, **examenplannen**,
   **nominale lijnen (NML)**). Ze staan op schijf in `oeren/<inst>/_bronmateriaal/` (niet geïndexeerd).
2. Maar één document per soort per instelling; documenten die bij een **opleiding/cohort** horen
   (examenplan, NML, studiegids, onderwijsplan) passen er niet in.
3. Eén KD per crebo: een oudere KD-versie (bv. KW1C Werkvoorbereider, KD 2016, cohort 2025) kan niet
   naast de nieuwe bestaan.
4. Geen privacybeleid op documentniveau: sommige bronnen bevatten namen (versiehistorie, auteurs,
   coachlijsten, docentcodes).

## Doel

Elke instelling kan elk documenttype aanleveren; de assistent gebruikt wat bij de gekozen
studiegids (instelling + opleiding + leerweg + cohort) hoort, met bron/vindplaats/citaat; persoonsgegevens
komen er aantoonbaar niet uit.

## Ontwerp

### 1. Documentmodel (schema)
Eén tabel `documenten` (opvolger van `instelling_documenten`), additieve migratie, oude rijen worden
overgenomen:

| Veld | Betekenis |
|---|---|
| `instelling_id`, `titel`, `bestandspad`, `content_hash`, `geindexeerd` | zoals nu |
| `soort` | **open label** uit een register (zie 2), geen CHECK |
| `bereik` | `instelling` (geldt voor alle opleidingen) of `opleiding` |
| `crebo`, `leerweg`, `cohort` | alleen bij `bereik='opleiding'` (kunnen deels leeg zijn: "alle cohorten") |
| `versie_label`, `geldig_vanaf`, `geldig_tot` | schooljaar/versie, voor selectie bij een cohort |
| `publiek` | mag in de publieke chat (default ja; `nee` voor bv. medewerkersbeleid) |
| `gevoeligheid` | `normaal` · `geredigeerd` (PII verwijderd) · `uitgesloten` (nooit indexeren) |
| `samenvatting`, `tekens` | catalogusinformatie en budgetbewaking |

`UNIQUE` vervalt; nieuwe sleutel: `(instelling_id, soort, bereik, crebo, leerweg, cohort, bestandspad)`.

### 2. Soortenregister (code, niet DB)
`INSTELLING_SOORTEN` wordt een register met per soort: label, standaardbereik, `juridisch` (volledige tekst
+ harde citatieplicht) of `informatief`, standaard `publiek`. Nieuwe soorten = één regel.
Voorgesteld: de bestaande 12 + `examenplan` (opleiding), `nominale_lijn` (opleiding), `studiegids`
(opleiding), `onderwijsplan` (opleiding), `praktijkovereenkomst`, `schoolkosten`, `veiligheidsplan`,
`protocol`, `keuzedelen`, `studiekeuzegids`, `overig`.
Examenreglement blijft `instelling`; examenplan is `opleiding` (per crebo/cohort).

### 3. Contextselectie per vraag
Context wordt al per gekozen OER (instelling + crebo + leerweg + cohort) opgebouwd. Nieuw: documenten
met `bereik='instelling'` **plus** documenten met `bereik='opleiding'` die matchen op crebo/leerweg/cohort
(`NULL` = geldt voor alle). Volgorde bij budgetdruk: juridisch eerst, daarna opleidingsgebonden, dan overig;
wat niet past wordt gelogd en in de chat aan de student gemeld ("niet alle documenten pasten").
Het budget (nu 300K tekens voor instellingsbronnen) wordt per bronsoort configureerbaar en gemeten.

**Beslispunt A — hoe omgaan met veel/grote niet-juridische documenten:**
- **A1 (aanbevolen eerst): alles volledig in de prompt**, met prioriteit + budget. Houdt woordelijke
  citaten intact; prompt caching dempt de kosten. Eerst meten hoeveel tekens de aangeleverde set is.
- A2: catalogus + selectie (klein model kiest per vraag welke documenten geladen worden).
- A3: vectorstore voor niet-juridische documenten (chunk-citaten; heroverweegt PR #33).
Juridische documenten blijven volledig, ongeacht A.

### 4. KD-versies
KD per `(crebo, versie, geldig_vanaf, geldig_tot)`; kies de versie die geldt voor het cohort van de OER,
anders de nieuwste. Een oudere KD wordt alleen geregistreerd als er een OER van dat cohort voor die
opleiding bestaat (ingest waarschuwt anders). Het landelijke KD wordt nooit overschreven door een
instellingsvariant (bestaande invariant); de oude versie komt ernaast.

### 5. Privacy-guardrails
1. **Uitsluiten:** `gevoeligheid='uitgesloten'` wordt nooit ingeladen (SLB/coach-namenlijsten, docentcodes
   en lestaken, personeelslijsten). Uitsluitlijst staat in het ingestmanifest en is testbaar.
2. **Redigeren bij ingest:** deterministische pass (e-mail, telefoon, IBAN, BSN-achtig, handtekeningblokken,
   versiebeheer/auteurstabellen) → `[verwijderd]`; resultaat als apart `.md`, origineel ongemoeid;
   een reviewrapport toont wat verwijderd is.
3. **Antwoordregel** in de systeemprompt: noem geen persoonsnamen of contactgegevens uit bronnen; verwijs
   naar de rol (mentor, SLB'er, studentenbalie).
4. **Tests:** (a) `laad_context` bevat geen canary-PII uit testdocumenten; (b) een evaluatiescript met
   red-team-vragen ("wie schreef dit protocol?", "noem de coaches van …") tegen het live model, met
   canary-namen; geen LLM-aanroep in de standaard pytest-run.

### 6. Aanleveren en inlezen
Mappen volgen de Box-structuur (`10-instellingen/<inst>/0..7-…`): de map bepaalt de standaard
soort/bereik; crebo/cohort/leerweg komen uit de bestandsnaam (bestaande parser) of een manifest.
Nieuwe formaten: `xlsx/xlsm` (alleen zichtbare, relevante bladen → markdowntabellen), `docx`, en OCR voor
scans (`tesseract`, door Ed te installeren; bv. KW1C studiegids 25779). Uitkomst per bestand:
geclassificeerd, geredigeerd, geïndexeerd of bewust overgeslagen met reden.

## Fasering (elk een eigen PR)
1. Schema + register + contextselectie + budgetmeting (bestaande documenten blijven werken).
2. KD-versies.
3. Ingest nieuwe formaten + privacy-pass + guardrailtests.
4. Data laden (Curio, KW1C, Graafschap, Rijn IJssel, Deltion) → nieuwe deploy (DB zit in het image).

## Acceptatiecriteria
| # | Criterium |
|---|---|
| 1 | Meerdere documenten van dezelfde soort per instelling zijn mogelijk; bestaande data migreert zonder verlies |
| 2 | Een opleidingsgebonden document verschijnt alleen in de context van een matchende OER (crebo/leerweg/cohort) |
| 3 | Vraag naar kluiscontrole bij een Curio-OER wordt beantwoord met bron, vindplaats, citaat |
| 4 | Een oudere KD-versie wordt gekozen voor het bijbehorende cohort; nieuwste als geen match |
| 5 | Een `uitgesloten` document of canary-PII komt nooit in `laad_context` voor |
| 6 | Over budget: prioriteit klopt, overschot wordt gelogd en gemeld |
| 7 | `ruff`, `pytest` groen; UI-smoke op startpagina + overlay |

## Open punten voor de beoordelaar
1. Beslispunt A (A1 aanbevolen). 2. Welke soorten zijn `publiek`? (nu: alleen examenreglement + generieke
regelingen; voorstel: alles behalve `publiek=nee`). 3. Redactiestrategie: alleen deterministisch +
uitsluitlijst (voorstel), of ook modelgestuurde detectie? 4. Plaats van de bestanden in de repo
(`oeren/<inst>_oeren/_documenten/<soort>/` als voorstel).
