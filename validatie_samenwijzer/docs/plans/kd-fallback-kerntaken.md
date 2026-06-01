# Plan: KD-fallback voor kerntaken-extractie (issue #53)

**Status:** ontwerp goedgekeurd · **Datum:** 2026-06-01 · **Issue:** #53

## Probleem (en herziening van de issue-premisse)

Issue #53 stelt dat OER-PDFs waar kerntaken in **tabellen** staan na PR #50 nul kerntaken
opleveren (markitdown vlakt tabellen af tot losse cellen, die het strict-filter wegfiltert), en
draagt **tabel-extractie via pdfplumber** (Optie A) aan als voorkeursoplossing.

Onderzoek tegen de echte `oeren/`-bestanden weerlegt die premisse als hoofdoorzaak:

| Instelling | md-bestanden | met `B#-K#`-codes | kerntaken in DB |
|---|---|---|---|
| aeres | 37 | **0** | 0 / 29 |
| rijn_ijssel | 115 | **0** | 0 / 50 |
| talland | 305 | 256 | 155 / 238 |

- **Aeres en Rijn IJssel lijsten kerntaken helemaal niet in de OER** — het zijn examenplannen
  die naar het landelijke kwalificatiedossier verwijzen zonder B#-K#-codes te noemen. Geen
  tabel-extractie kan data herstellen die niet in het document staat.
- pdfplumber `extract_tables()` op de Beveiliger-PDF (crebo 25690) levert óók garble op
  (cellen vol intra-cel-newlines, willekeurig gesplitste kolommen) — Optie A is dus zelfs voor
  de écht tabel-zware Talland-PDF geen schone winst (getest met default settings).

## Oplossing: KD-fallback bij nul OER-kerntaken

Het project heeft de autoritatieve bron al: het **kwalificatiedossier per crebo**
(`kwalificatiedossiers/pdfs/<crebo>.md`, 240/247 dekking, al via Box gesynct). De inhoudsopgave
daarvan bevat schone `B1-K1: <naam>` en `B1-K1-W1: <naam>`-regels die de bestaande
`extraheer_kerntaken`-regex direct herkent.

**Mechanisme** — in `ingest._verwerk_bestand`, ná `extraheer_kerntaken(oer_tekst)`:

```
kerntaken = extraheer_kerntaken(oer_tekst)
als len(kerntaken) == 0 en crebo bekend en KD-md bestaat:
    kerntaken = extraheer_kerntaken(kd_tekst)   # zelfde extractor, andere bron
```

**Fire-at-zero + supplement-never-replace**: de fallback vuurt uitsluitend wanneer de OER nul
kerntaken oplevert. De 3 werkende instellingen (Da Vinci, Talland, ROC Utrecht) houden hun
OER-kerntaken ongewijzigd → geen regressie. Sluit aan bij het projectprincipe *de OER is
leidend; het KD is aanvullend*.

### Naam-opschoning

KD-inhoudsopgaveregels dragen trailing dotted leaders + paginanummers, bv.:

```
B1-K1:  Uitvoeren metingen leefomgeving en rapporteren resultaten  ............  6
```

Een opschoonstap verwijdert de trailing `\s*\.{2,}\s*\d*\s*$` zodat de naam
`Uitvoeren metingen leefomgeving en rapporteren resultaten` wordt. De KD-body herhaalt dezelfde
codes soms in gewrapte vorm zonder dubbelepunt; dedup gebeurt **per (type, code)** met voorkeur
voor de langste opgeschoonde naam (de inhoudsopgave-vorm), zodat gewrapte body-fragmenten geen
losse duplicaten worden.

### KD-pad-resolutie

Hergebruik de bestaande logica van `chat.pad_kwalificatiedossier(crebo)` (default
`<repo-root>/kwalificatiedossiers/pdfs`, override via `KWALDOSSIERS_PAD`). Eén dunne helper in
`ingest.py` die het `.md`-pad teruggeeft of `None` als het ontbreekt.

## Bewust buiten scope

- **Regex-verbreding** voor Talland's lopende-tekst `Examenonderdeel kerntaak B1-Kn: <naam>`
  (die de `^`-geankerde regex nu mist): KD-fallback dekt alle acceptatiecriteria al, inclusief
  de Beveiliger via crebo 25690. Niet doen — proza zoals "Om voor kerntaak B1-K1 te slagen…"
  zou vals gevangen worden, en de marginale Talland-winst is onduidelijk. YAGNI.
- **Bron-kolom** (`oer`/`kd`) in de kerntaken-tabel: acceptatiecriteria vragen het niet;
  schema-migratie vermijden.
- **pdfplumber tables / LLM-extractie** (issue-Opties A/B): niet nodig — KD-fallback is
  deterministisch, gratis en dekt de hoofd-blocker.

## Acceptatiecriteria (uit #53)

- [ ] Aeres MBO en Rijn IJssel terug in de seed-set met ≥ 1 OER met kerntaken per instelling
- [ ] Geen regressie op Da Vinci, Talland, ROC Utrecht (fire-at-zero borgt dit)
- [ ] Test in `tests/test_ingest.py`: KD-fallback levert kerntaken op voor een crebo waarvan de
      OER er nul geeft (Beveiliger 25690 / een KD-fixture)
- [ ] `bulk_seed` produceert weer ~1000 studenten over 5 instellingen
- [ ] README/CLAUDE.md-update als de ingest-flow een extra stap krijgt

## Verificatie-aanpak

1. Unit (TDD): naam-opschoning verwijdert trailing dotted leaders; dedup-per-code prefereert inhoudsopgave.
2. Unit: `_verwerk_bestand` valt op KD terug bij nul OER-kerntaken, niet anders (mock/fixture).
3. Integratie: `ingest --reset` lokaal → DB toont kerntaken voor aeres + rijn_ijssel crebos.
4. `seed_bulk.py` → ~1000 studenten, 5 instellingen, geen "overgeslagen instelling".
