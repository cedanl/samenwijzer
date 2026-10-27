# Spec: flexibele documentlaag (alle instellingsdocumenten beschikbaar voor de assistent)

**Status:** ter beoordeling (geen code) · **Datum:** 2026-10-27 · **Besluitenlog:**
`2026-10-27-besluitenlog-documentverwerking.md` · **Vervolg:** `2026-10-27-flexibele-documentlaag-plan.md`

## Aanleiding en intentie

Een testvraag over het Curio-kluiscontroleprotocol leverde niets op. Onderzoek van **alle** door de
projectleden aangeleverde documenten (Curio, Deltion, Graafschap College, KW1C, Rijn IJssel + werkgroepstukken)
laat zien dat dit structureel is. Intentie: elke deelnemende instelling kan elk documenttype aanleveren
en de assistent gebruikt wat bij de gekozen studiegids (instelling + opleiding + leerweg + cohort) hoort,
met bron/vindplaats/citaat, zonder dat persoonsgegevens uit bronnen terugkomen.

**Doelen:** (1) alle in scope zijnde documenten van alle vijf instellingen doorzoekbaar; (2) flexibel voor
nieuwe soorten en instellingen; (3) aantoonbare privacy-guardrails; (4) herleidbaar wat wel/niet is meegenomen.
**Niet-doelen:** het inventarisatieformulier; studentdata/voortgang (fase 2/3); nieuwe UI.
**Anti-doel:** een assistent die een document "kent" maar er zonder bron of met verzonnen vindplaats uit citeert,
of die namen uit bronnen noemt.

## Huidige situatie

De chat leest vier bronnen: OER, KD (één per crebo), skills en een vaste lijst van 12 instellingsbrede
soorten met `UNIQUE (instelling_id, soort)`. Alles daarbuiten staat onbenut op schijf
(`oeren/<inst>/_bronmateriaal/`, niet geïndexeerd). Documenten zijn nu ook in **Box** georganiseerd
(`samenwijzer/use-case-samenwijzer/10-instellingen/<inst>/0..7-…`, 168 bestanden), zie het besluitenlog.

## Bevindingen per instelling (hiaten)

| Instelling | Aangeleverd, maar niet in de chat | Overige hiaten |
|---|---|---|
| **Curio** | 34 examenplannen (map heet "Examenregelement"), 30 nominale lijnen (NML), kluisprotocol, veiligheidsplan, schoolkosten, praktijkovereenkomst, onderwijsovereenkomst, studiekeuzegids | KD's voor 2026-crebo's (27052–27066, 27136–27140) ontbreken in de KD-set; BSA-info alleen 2025-26; OER 25797-2025 stond in de verkeerde map; geen OER voor 27139/27140; geen generieke regelingen in de DB |
| **Deltion** | niets (alleen formulier; wacht op interne collega) | geen begeleidingsbeleid, geen BSA |
| **Graafschap** | 11 examenplannen (xlsm, onderling vergelijkbaar), keuzedelenoverzicht | geen examenreglement, geen klachtenregeling in de DB; onderwijsinrichting bewust uitgesloten (personeelsgegevens) |
| **KW1C** | onderwijsplan BBL4 (DBL), module-overzicht, grof ontwerp, addendum statuut, rechten-van-betrokkenen, IBP-beleid, studiegids 25122 | studiegids 25779 is een **scan** (OCR nodig); KD 2016 vs 2026 onder dezelfde crebo; examenplannen staan als "OER" geregistreerd; studiegids 25122 ontbreekt door dubbele sleutel |
| **Rijn IJssel** | niets nieuws (alles al aanwezig) | examenreglement 2026-27 ontbreekt; toekomstige OER's komen in Xerte (geen PDF) |

Het soort inhoud: *examenplan* = per werkproces examenvorm, weging, cesuur, periode (geen kalenderdata);
*NML* = verwacht tempo per periode, gekoppeld aan (bindend) studieadvies.

## Meting (tekens tekstlaag, zonder OER/KD)

Totaal 2,04 M tekens; instellingsbreed (regelingen + beleid + overig): **Curio ≈ 450K, KW1C ≈ 350K, Rijn IJssel
≈ 160K**. Opleidingsgebonden is per vraag klein (één examenplan ≈ 18K, één NML ≈ 14K tekens; Curio-totaal
600K/410K verspreid over ~30 opleidingen). Het huidige instellingsbudget is 300K tekens: het volledig laden van
alle instellingsbrede documenten past dus **niet** voor Curio en KW1C. Alle PDF's hebben een tekstlaag, behalve
de KW1C-studiegids 25779.

## Ontwerp

### 1. Documentmodel
Eén tabel `documenten` (opvolger van `instelling_documenten`; additieve migratie, bestaande rijen worden
overgenomen):

| Veld | Betekenis |
|---|---|
| `instelling_id`, `titel`, `bestandspad`, `content_hash`, `geindexeerd` | zoals nu |
| `soort` | open label uit een register (geen CHECK) |
| `bereik` | `instelling` of `opleiding` |
| `crebo`, `leerweg`, `cohort` | bij `bereik='opleiding'`; **`''` (lege string, NOT NULL DEFAULT '') = "alle"**, per veld apart (bv. één examenplan voor alle cohorten) |
| `versie_label`, `geldig_vanaf`, `geldig_tot` | schooljaar/versie |
| `zichtbaarheid` | `publiek` (ook publieke chat) · `ingelogd` (student/mentor) · `intern` (nergens in de chat) |
| `gereviewd` | privacy-review afgerond (zie §5); zonder review is een nieuw document `intern` |
| `gevoeligheid` | `normaal` · `geredigeerd` · `uitgesloten` |
| `samenvatting`, `tekens` | catalogus en budgetbewaking |

`UNIQUE` vervalt; nieuwe sleutel `(instelling_id, soort, bereik, crebo, leerweg, cohort, bestandspad)` — werkt omdat
"alle" als `''` wordt opgeslagen (SQLite behandelt NULL's in UNIQUE als ongelijk). `laad_context(oer_ids, niveau)`
krijgt een `niveau` (`publiek`/`student`/`mentor`) i.p.v. de vaste `*_SOORTEN`-tuples; `zichtbaarheid` bepaalt wat meegaat.

### 2. Soortenregister (code)
`INSTELLING_SOORTEN` wordt een register: label, standaardbereik, `juridisch` of `informatief`, standaard `publiek`.
Naast de bestaande 12: `examenplan` (opleiding), `nominale_lijn` (opleiding), `studiegids` (opleiding),
`onderwijsplan` (opleiding), `praktijkovereenkomst`, `schoolkosten`, `veiligheidsplan`, `protocol`,
`keuzedelen`, `studiekeuzegids`, `overig`. Examenreglement blijft instellingsbreed.

### 3. Contextselectie en budget
De system-prompt wordt **eenmalig per sessie** gebouwd (bij `/api/kies`) en 1 uur gecachet; selectie is daarom
statisch per sessie, niet per vraag (per-vraag-selectie zou de prompt-cache breken).
Per gekozen OER: alle documenten met `bereik='instelling'` plus `bereik='opleiding'` die matchen op
crebo/leerweg/cohort (`''` = alle) en `zichtbaarheid` ≤ niveau. Instellingsbrede documenten worden **per
instelling één keer** opgenomen, ook bij meerdere OER's van dezelfde instelling.
- **Budget:** OER 500K, KD 300K, skills 50K (ongewijzigd) en een **totaalbudget voor documenten van 700K tekens**
  (configureerbaar; meting: Curio-instellingsbreed ≈ 450K, KW1C ≈ 350K, dus alles past).
- **Prioriteit bij overschot:** juridisch → opleidingsgebonden → informatief; binnen een groep het kleinste
  document eerst. Wat afvalt wordt gelogd en via de bestaande banner (zoals `oer_onleesbaar`) aan de student gemeld.
- **A2 (catalogusselectie door een klein model) en A3 (vectorstore)** zijn uitgesteld; pas bouwen als de meting
  structureel budgetoverschrijding laat zien. Hiermee past de aanbeveling A1 voor alle huidige instellingen.

### 4. KD-versies
KD-versies staan in een **expliciet manifest** `kwalificatiedossiers/versies.json`: per crebo een lijst
`{versie, bestand, cohorten: [van, tot]}` (handmatig bevestigd, geen afleiding uit datums). Kies de versie waarvan
het cohortbereik het OER-cohort bevat, anders de nieuwste. Bestanden: `pdfs/<crebo>@<versie>.md`. Een oudere KD wordt alleen geregistreerd als er een OER van dat cohort voor die opleiding bestaat (ingest
waarschuwt anders). Het landelijke KD wordt nooit overschreven; de oude versie komt ernaast (bv. KW1C 25122: KD 2016).

### 5. Privacy-guardrails
1. **Uitsluiten:** `uitgesloten` wordt nooit geladen (coachlijsten, docentcodes/lestaken, personeelslijsten).
2. **Redigeren bij ingest:** deterministisch (e-mail, telefoon, IBAN, BSN-achtig, handtekeningblokken,
   versiebeheer/auteurstabellen) → `[verwijderd]`; apart `.md`, origineel ongemoeid; reviewrapport.
3. **Antwoordregel** in de systeemprompt: geen persoonsnamen/contactgegevens uit bronnen; verwijs naar de rol.
4. **Reviewpoort:** een nieuw document is `intern` tot het reviewrapport (wat is verwijderd + verdachte
   naampatronen) is goedgekeurd (`gereviewd`); deterministische redactie vangt geen namen in lopende tekst.
5. **Tests:** canary-PII komt niet in `laad_context`; evaluatiescript met red-team-vragen tegen het live model
   (niet in de standaard pytest-run).

### 6. Aanleveren en inlezen
De Box-mappen bepalen standaard soort/bereik. Per instelling een **manifest** (gegenereerd door een script uit
bestandsnaam + inhoud, daarna menselijk gecontroleerd) met soort, bereik, crebo/leerweg/cohort, zichtbaarheid,
gevoeligheid; **het manifest wint van de bestandsnaam**, ingest waarschuwt bij tegenspraak (bv. NML "27054" met
crebo 25648 in de inhoud). Nieuwe formaten: `xlsx/xlsm` (alleen zichtbare, relevante bladen → markdowntabellen), `docx`,
OCR voor scans (`tesseract`, door Ed geïnstalleerd). Uitkomst per bestand: geclassificeerd/geredigeerd/geïndexeerd
of bewust overgeslagen met reden (besluitenlog).

### 7. Waar leeft wat
| Wat | Plek | Rol |
|---|---|---|
| **Catalogus** (welk document, soort, bereik, zichtbaarheid, samenvatting, tekens) | tabel `documenten` in `data/validatie.db` | enige bron van waarheid; wat de app leest; in het image gebakken |
| Manifest per instelling (invoer voor de catalogus) | `oeren/<inst>_oeren/_documenten/manifest.json` | door mens gecontroleerd; ingest vult de catalogus hieruit |
| Geredigeerde teksten | `oeren/<inst>_oeren/_documenten/<soort>/*.md` | wat in de prompt komt |
| Soortenregister | code (`db.py`) | labels, standaardbereik, juridisch/informatief |
| KD-versies | `kwalificatiedossiers/versies.json` + `pdfs/<crebo>@<versie>.md` | cohortkoppeling |
| Originelen en projectdocumenten | Box `use-case-samenwijzer/` (niet in het image) | bron en archief |
| Leesbaar overzicht voor mensen | gegenereerd rapport in Box `90-analyse/` | geen aparte bron; afgeleid uit de catalogus |

## Beslispunt voor Ed
**B1 — reviewpoort.** Redactie is deterministisch en vangt geen namen in lopende tekst. Voorstel: nieuwe
documenten blijven `intern` tot een mens het reviewrapport goedkeurt (Ed of een door hem aangewezen persoon).
Alternatief: automatisch `publiek` na redactie, met de antwoordregel als enig vangnet. Aanbeveling: reviewpoort.

## Defaults die ik koos (door Ed te bevestigen of te wijzigen)
| # | Keuze | Reden |
|---|---|---|
| D1 | Statische selectie per sessie met totaalbudget 700K + prioriteit; A2/A3 uitgesteld | prompt wordt eenmalig gebouwd en gecachet; meting: alles past |
| D2 | `zichtbaarheid`: publiek / ingelogd / intern; alles `publiek` behalve expliciet intern (bv. IBP-beleid medewerkers) | de publieke chat is de hoofdingang; ingelogde routes behouden hun uitgebreidere set |
| D3 | Redactie deterministisch + uitsluitlijst + reviewpoort (B1), geen modelgestuurde detectie | reproduceerbaar en testbaar |
| D4 | Alleen geredigeerde `.md` onder `oeren/<inst>_oeren/_documenten/<soort>/`; originelen blijven buiten de image (Box/lokaal) | `COPY oeren/` bakt alles in het publieke image |
| D5 | `intern` i.p.v. verwijderen | herleidbaarheid |
| D6 | "Leeg = alle" als `''` per veld (crebo/leerweg/cohort) | SQLite-UNIQUE behandelt NULL's als ongelijk |
| D7 | KD-versies via expliciet manifest op cohort | datums kloppen niet altijd met cohortgebruik (KW1C 25122: KD 2016 voor cohort 2025) |
| D8 | Manifest per instelling wint van de bestandsnaam | bestandsnamen kloppen niet altijd (NML 27054, Curio-"Examenregelement") |
| D9 | Studentenstatuut, BSA-regeling, klachtenregeling, gedragscode en algemene informatie zijn `publiek` (2026-10-27); alleen `begeleidingsbeleid` blijft `ingelogd`. Bestaande rijen worden door `init_db` gelijkgetrokken | openbare documenten op de schoolsites; zonder ze in de publieke chat zocht het model op het web en toonde het de webwaarschuwing boven informatie uit het statuut (kluisjes-casus) |
| D10 | Antwoorden uit een schooldocument (niet de OER) krijgen een eigen ℹ️-banner; de ⚠️-webwaarschuwing alleen bij informatie die écht van de website komt; webzoek is laatste redmiddel na álle documenten | gebruiker moet in één oogopslag zien: website vs. door de instelling vastgesteld materiaal |

## Fasering (elk een eigen PR, elk met spec-criteria, lokale test en UI-smoke)
0. **`.dockerignore`-fix (los en eerst):** `Dockerfile.fastapi` doet `COPY oeren/`; `oeren/*/_bronmateriaal/`
   (o.a. Graafschap-onderwijsinrichting met docentcodes) zit nu in het Fly-image (niet publiek geserveerd, wel aanwezig).
   Uitsluiten, plus een regel dat originelen/`uitgesloten` bestanden nooit onder `oeren/` komen.
1. Schema + register + contextselectie + budgetmeting (bestaande documenten blijven werken).
2. KD-versies.
3. Ingest nieuwe formaten + OCR + privacy-pass + guardrailtests.
4. Data laden per instelling (Curio, KW1C, Graafschap, Rijn IJssel, Deltion) → nieuwe deploy (DB zit in het image).

## Acceptatiecriteria
0. Geen `_bronmateriaal`/uitgesloten bestanden meer in het Fly-image.
1. Meerdere documenten per soort per instelling; bestaande data migreert zonder verlies.
2. Opleidingsgebonden document alleen in de context van een matchende OER.
3. Vraag naar kluiscontrole bij een Curio-OER wordt beantwoord met bron, vindplaats, citaat.
4. Oudere KD-versie voor het bijbehorende cohort; nieuwste als geen match.
5. `uitgesloten` of canary-PII komt nooit in `laad_context`.
6. Over budget: prioriteit klopt, overschot gelogd en gemeld.
7. Voor elke instelling is vastgesteld welke aangeleverde documenten wel/niet zijn opgenomen (besluitenlog).
8. `ruff`, `pytest` groen; UI-smoke op startpagina en overlay.

## Risico's en open punten
- Curio 25742 (2026) is byte-identiek aan 2023: navragen of dezelfde tekst voor twee cohorten is aangeleverd.
- Rijn IJssel levert toekomstige OER's in Xerte: aparte ingestroute, buiten fase 1–4.
- Nominale lijnen/examenplannen zijn geen juridische documenten en bevatten soms tabellen: citeerbaarheid per
  tabelrij/blad moet in fase 3 worden gevalideerd.
- Kosten: meer context per vraag; prompt caching en budgetten dempen dat, meten in fase 1.
