# Bronactualiteit Fase 3a-vervolg — Overige OER-catalogus-adapters (ontwerp)

> **Ontwerpdocument, geen TDD-implementatieplan.** De OER-catalogus van elke instelling
> is een eigen, brosse live-crawl; kloppende scrape-code is niet vooraf te schrijven zonder
> per instelling de actuele HTML/PDF te onderzoeken. Dit document legt het herbruikbare
> patroon + per instelling de geverifieerde entry points, crebo-strategie en openstaande
> onbekenden vast. Elke instelling wordt daarna een eigen implementatietaak (eigen plan)
> met een live-probe als eerste stap. Bevindingen komen uit 5 parallelle live-probes
> (24 juni 2026) + `reference_samenwijzer_oer_bronnen`.

**Doel:** de OER-catalogus-check (Fase 3a, Deltion) uitbreiden naar de overige crawlbare
instellingen, zodat `check-bron-updates --oer` per instelling "nieuwe OER('s)/cohorten
beschikbaar" meldt.

**Context:** Fase 3a leverde het raamwerk: `oer_catalogus._CATALOGUS_BRONNEN` (registry van
`() -> list[CatalogusItem]`-adapters), de pure tuple-diff `nieuwe_oers` (mét dedup op sleutel),
per-instelling degradatie bij een onbereikbare bron (`CatalogusOnbereikbaarError`), en de
`--oer`-gate. **Een nieuwe instelling toevoegen = een adapter schrijven en registreren** — het
raamwerk eromheen is af.

---

## Het adapter-patroon (herbruikbaar, al bewezen met Deltion)

Elke adapter is zelfstandig en levert `list[CatalogusItem]`. Het contract bakt **niets** in over
hoe de crebo verkregen wordt — een adapter mag intern eerst listen en daarna per item een PDF
ophalen+parsen. Splits altijd in twee lagen (zoals `fetch_deltion.haal_items_op` + `_record`):

1. **Geïsoleerde I/O** — `fetch_<inst>() -> raw` (HTTP/sitemap/PDF-download). Niet unit-getest;
   live smoke-test.
2. **Pure parse** — `_parse_<inst>(raw) -> list[CatalogusItem]`. Deterministisch, **TDD met een
   vastgelegd sample** (opgeslagen HTML/JSON/PDF-tekstfragment uit de live-probe).

De adapter `<inst>_catalogus()` rijgt ze aaneen en wordt in `_CATALOGUS_BRONNEN` gezet. Aggregatie,
dedup, degradatie en rapportage zijn al generiek.

### Crebo-strategie bepaalt de kosten

| Strategie | Kosten | Instellingen |
|---|---|---|
| Crebo uit **listing/bestandsnaam** | goedkoop (geen PDF-fetch) | Aeres (2026-2027), Rijn IJssel (primaire crebo) |
| Crebo uit **PDF-inhoud** | duur (1 fetch+parse per OER) | MBO Utrecht, Talland, Rijn IJssel (volledige crebo-set) |

### Cross-cutting ontwerpbeslissingen (vóór de eerste adapter)

- **Leerweg-onbekend-beleid.** De diff-sleutel is `(crebo, leerweg, cohort)`, maar Aeres levert
  **geen leerweg** (en de DB heeft wél BOL/BBL). Een tuple met `leerweg="onbekend"` matcht dan nooit
  → valse "nieuwe OER". **Beslissing nodig:** maak de diff-sleutel per adapter instelbaar — vergelijk
  op `(crebo, cohort)` wanneer de adapter geen betrouwbare leerweg levert, en op de volle tuple
  wanneer wel. (Implementatie: een `sleutel_velden`-parameter op de adapter/diff, default volledige
  tuple.)
- **Multi-crebo-bundeling.** Rijn IJssel bundelt meerdere crebo's per OER-document → één doc levert
  meerdere `CatalogusItem`s. De adapter expandeert; de bestaande dedup vangt dubbelen.
- **Cohort-format.** Houd consistent met `oer_documenten` (jaar-deel, bv. `"2025"`). Aeres/MBO
  Utrecht leveren `2026-2027` of `2024` in pad/naam → normaliseer naar het jaar-deel (zoals
  `fetch_deltion._record`).
- **Bestandsnaam ≠ DB-cohort.** WordPress-uploadmaand (MBO Utrecht `/uploads/2025/05/`) is **niet**
  het cohort; gebruik het jaar in de OER-bestandsnaam.

---

## Aanbevolen implementatievolgorde

1. **Aeres** (2026-2027) — goedkoopst: crebo + cohort uit één statische pagina. Eerste vervolg-adapter;
   tevens de testcase voor het leerweg-onbekend-beleid.
2. **Rijn IJssel** — primaire crebo uit bestandsnaam goedkoop; volledige crebo-set (bundel) als
   optionele verdieping (PDF-parse).
3. **MBO Utrecht** — PDF-parse voor crebo; degelijk maar duurder + sqill.it-afhankelijkheid.
4. **Talland** — duurst (~220 server-side PDF's, 504-gevoelig). Overweeg **uit te stellen** of in
   `_OER_NIET_CRAWLBAAR` te houden tot er een API/manifest is.
5. **Curio** — **eerst de recipe-divergentie reconciliëren** (zie hieronder) vóór er een adapter komt.

---

## Per instelling

### Aeres MBO — *moeilijkheid: laag (2026-2027)*

- **Entry point (geverifieerd 200):** één statische HTML-pagina
  `https://www.aeresmbo.nl/over-aeres-mbo/regelingen-en-statuten` — bevat alle ~73 examenplan-links
  statisch (geen JS). Media-map zelf is niet listbaar (404).
- **Enumeratie:** parse de pagina-HTML op `href="…examenplan-<crebo>-…-vastgesteld.pdf"`.
- **Crebo:** uit bestandsnaam, `examenplan-(\d{5})-…` (geverifieerd: 40 crebo's voor 2026-2027,
  o.a. 25981, 25730, 25705).
- **Cohort:** uit URL-pad `/<cohort>/examenplannen/` → normaliseer `2026-2027` → `2026`.
- **Leerweg:** **niet beschikbaar** in bestandsnaam of pagina → past het leerweg-onbekend-beleid toe
  (diff op `(crebo, cohort)`). Aparte "derde leerweg"-OER's bestaan los (regeling, geen examenplan).
- **Gotchas:** oudere cohorten (≤2025-2026) zijn **gebundeld per domein** (geen per-crebo;
  PDF's vaak beeld-gebaseerd/JPEG → tekstextractie faalt). Beperk de eerste adapter tot het
  per-crebo cohort (2026-2027 e.v.).
- **Open onbekenden:** bevat de examenplan-PDF zelf een BOL/BBL-aanduiding? Is er een Aeres-catalogus
  (API/spreadsheet) met crebo↔leerweg?
- **Parse-bron:** HTML-pagina → regex op de examenplan-hrefs. Sample voor de TDD: de opgeslagen
  pagina-HTML.

### Rijn IJssel — *moeilijkheid: midden-hoog*

- **Entry points (geverifieerd 200):** sitemap-index `https://www.rijnijssel.nl/sitemap.xml`
  → `…/sitemap-0.xml` (~500 opleiding-URL's, patroon `/mbo-opleidingen/<slug>`). OER-PDF's op
  `https://apicms.rijnijssel.nl/documents/<id>/<bestand>.pdf` (geverifieerd, bv. `…/documents/188/
  TIK_2025_OER_25998-software-developer.pdf`).
- **Enumeratie:** crawl de opleiding-pagina's (Next.js, maar de `apicms…/documents/<id>/`-links
  staan als hrefs in de gerenderde HTML); er is **geen** centraal `/documents`-lijst-endpoint.
- **Crebo:** **primaire** crebo uit de bestandsnaam-prefix (`(\d{5})_<leerweg>_<cohort>__…`,
  goedkoop). **Secundaire** crebo's (bundel) staan alleen in de PDF-inhoud (sectie 3.1
  "Kwalificatiedossier" + "Uitstroomkwalificaties") → PDF-parse voor de volledige set.
- **Leerweg/cohort:** uit de bestandsnaam; let op "BOL en BBL" in de PDF → expand naar beide.
- **Gotchas:** multi-crebo-bundeling (1 doc → N crebo's), bestandsnaam-wildgroei, niet-sequentiële
  document-ID's (alleen via paginacrawl vindbaar).
- **Open onbekenden:** zijn er live 2026-2027-OER's die lokaal ontbreken? Verandert een herziene OER
  het document-ID of alleen de PDF-inhoud?
- **Parse-bron:** opleiding-pagina-HTML (doc-links) + optioneel PDF-tekst (sectie 3.1). Begin met de
  goedkope primaire-crebo-variant; bundel-verdieping als aparte stap.

### MBO Utrecht — *moeilijkheid: hoog*

- **Entry points (geverifieerd 200):** Yoast `practicalinformation-sitemap.xml` → 11 academie-pagina's;
  OER-PDF's als WordPress-uploads
  `https://mboutrecht.nl/wp-content/uploads/<jaar>/<mm>/<jaar>_OER_<leerweg>_<naam>.pdf`
  (bv. `…/2025/05/2024_OER_BOL_Verpleegkundige.pdf`).
- **Crebo:** **niet in de bestandsnaam** → uit de PDF-inhoud (`crebonr?\.?\s*(\d{5})`, geverifieerd:
  25998, 25655, 25749).
- **Leerweg/cohort:** uit de bestandsnaam `(\d{4})_OER_([A-Za-z]+)_…` (leerweg ∈ BOL/BBL/Entree;
  map Entree → BOL of behoud apart). Cohort = jaar in de bestandsnaam (níet de uploadmaand).
- **Gotchas:** **cohort 2025 leeft op `mboutrecht.sqill.it/reports/<uuid>/html`** (het `/html`-endpoint
  is curl-baar/niet-JS, maar externe service zonder versiecontract); vestigings-/BBL-varianten per crebo
  (dedup op tuple vangt ze).
- **Open onbekenden:** leerweg/cohort van de sqill.it-rapporten (zit in de academie-pagina-linktekst,
  niet in de UUID); stabiliteit van sqill.it.
- **Parse-bron:** PDF-tekst (crebo) + bestandsnaam (leerweg/cohort); sqill.it-HTML voor 2025.

### Talland College — *moeilijkheid: hoog; overweeg uitstellen*

- **Entry points (geverifieerd 200):** 5 sector-overzichtspagina's
  `https://talland.educatorstudiegids.nl/gids-overzicht/<sector-id>/1` (sector-id's 72, 81, 85, 244,
  22740) met program-UUID's als `<option value="…">` in statische HTML. Download:
  `…/gids/<program-uuid>/1/<sector-id>/download` (server-side gegenereerde PDF).
- **Crebo:** **niet in de listing** → alleen op de **PDF-titelpagina** (5-cijferig nummer). Vereist
  per OER een PDF-download + parse.
- **Leerweg/cohort:** uit de PDF/bestandsnaam (`BOL|BBL`, jaar); leerweg ook als "NN maanden BOL/BBL".
- **Gotchas:** **504-timeout bij parallelisme** (server-side PDF-generatie) → strikt `-P4` + retries;
  geschat ~220 PDF's (~88 MB) per volledige run; werkelijk aantal pas bekend ná download.
- **Aanbeveling (probe):** houd Talland in `_OER_NIET_CRAWLBAAR` tot er een metadata-/manifest-route
  is; handmatig opvoeren vanuit Box is nu goedkoper dan 220 PDF-loops.
- **Open onbekenden:** echte OER-count (HTML toont filters, niet alle combinaties); UUID→crebo-mapping;
  exacte rate-limits.

### Curio — *status: geblokkeerd, recipe-divergentie reconciliëren*

- **Live-bevinding (24 juni 2026):** de probe kon de publieke OER-PDF's **niet** reproduceren —
  geraden `…/sites/default/files/oer_documents/<crebo>_oer…pdf`-URL's gaven 404, directory-listing
  is 403, opleiding-pagina's linken geen OER-PDF's, en er is geen open Drupal-API voor OER's. **Dit
  wijkt af van `reference_samenwijzer_oer_bronnen`** (dat Curio als "publiek scrapebaar" noemt) — de
  bestaande Curio-OER's in de DB zijn ooit wél binnengehaald, dus óf het URL-patroon/de crebo's zijn
  anders dan geraden, óf de publicatie is gewijzigd.
- **Wél beschikbaar:** crebo per opleiding-pagina als HTML-veld (`field--name-field-crebo`,
  bv. 27109) — genoeg voor een **programma-catalogus** (nieuwe opleiding/cohort), maar **niet**
  gekoppeld aan een OER-document.
- **Actie vóór een adapter:** reconcilieer tegen de **werkelijke** bestaande Curio-OER-bestandsnamen
  in de repo/Box (welk patroon, welke crebo's) en her-test die echte URL's. Werk daarna
  `reference_samenwijzer_oer_bronnen` bij. Pas dán is een adapter zinvol; tot die tijd: handmatig
  / niet-crawlbaar.

---

## Wat één instelling-adapter-taak omvat (template voor de vervolgplannen)

1. **Live-probe** (eerste stap, altijd): bevestig de entry points + crebo/leerweg/cohort-bron, en leg
   een **sample** vast (HTML/JSON/PDF-tekst) voor de TDD.
2. **`_parse_<inst>(raw) -> list[CatalogusItem]`** — pure functie, TDD met het sample (incl.
   leerweg-onbekend → diff-sleutel-beleid, en multi-crebo-expansie waar van toepassing).
3. **`fetch_<inst>()` + `<inst>_catalogus()`** — geïsoleerde I/O (respecteer throttle/retry waar nodig,
   bv. Talland `-P4`); wikkel netwerkfouten zodat `instelling_nieuwe_oers` `CatalogusOnbereikbaarError`
   geeft (degradatie is al generiek).
4. **Registreer** in `oer_catalogus._CATALOGUS_BRONNEN`.
5. **Live smoke-test** `check-bron-updates --oer` + volledige suite + lint.
6. **PR** met de bevinding + sample + tests.

Geen wijziging nodig aan `bron_updates` (aggregatie/degradatie/rapportage zijn al N-instelling-proof);
wél de cross-cutting **diff-sleutel-parameter** (leerweg-onbekend) toevoegen aan `oer_catalogus`
vóór de Aeres-adapter — dat is de enige gedeelde codewijziging die alle volgende adapters raakt.

---

## Samenvatting

- Het 3a-raamwerk maakt elke instelling een **op zichzelf staande adapter-taak**; alleen de
  **diff-sleutel-parameter** (leerweg-onbekend) is een gedeelde voorbereiding.
- Volgorde naar kosten: **Aeres → Rijn IJssel → MBO Utrecht → Talland (uitstellen) → Curio
  (eerst reconciliëren)**.
- Twee instellingen (Talland, MBO Utrecht) vereisen per-PDF crebo-extractie (duur); Talland's
  504-gevoeligheid maakt 'm de minst aantrekkelijke.
- **Curio is met de huidige live-bevinding niet publiek crawlbaar** — dat is een afwijking van de
  vastgelegde recipe die eerst uitgezocht moet worden (en de memory bijgewerkt).
