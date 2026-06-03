# Werkverslag 2026-06-03 — Instellingsbronnen & onboarding (KWIC, Graafschap, Curio)

Sessie waarin drie MBO-instellingen via hun publieke websites zijn verrijkt met
instellingsbrede regelingen (4e chat-bron) en, waar mogelijk, OER's. Alle drie
afgerond als aparte PR, gemerged op `main` en gesynct naar Box.

## Resultaat

| Instelling | PR | Aard | Status |
|---|---|---|---|
| Koning Willem I College (KWIC) | [#125](https://github.com/cedanl/samenwijzer/pull/125) | 5 instellingsbronnen, **geactiveerd** | gemerged + Box |
| Graafschap College | [#126](https://github.com/cedanl/samenwijzer/pull/126) | 2 instellingsbronnen, **alleen gestaged** | gemerged + Box |
| Curio (Onderwijsgroep West-Brabant) | [#127](https://github.com/cedanl/samenwijzer/pull/127) | **nieuwe instelling**: 9 OER's + 4 bronnen | gemerged + Box |

## KWIC (#125) — instellingsbronnen geactiveerd

Bron: `kw1c.nl/studentenstatuut` ("Regelingen en richtlijnen", 28 documenten).
Top-5 gedownload naar `oeren/kwic_oeren/_instelling/` en geïndexeerd:

- `studentenstatuut`, `examenreglement` (bestaande soorten)
- `begeleidingsbeleid` ← Regeling Studievoortgang (mentor-only)
- `bindend_studieadvies`, `klachtenregeling` ← **2 nieuwe soorten** toegevoegd aan
  `db.INSTELLING_SOORTEN` (één regel elk, geen migratie)

Allowlists in `app/main.py` uitgebreid (`_STUDENT_SOORTEN` + `_MENTOR_SOORTEN`):
zonder die stap zijn nieuw-geïndexeerde soorten **geïndexeerd-maar-onzichtbaar** —
een silent gap die pytest/DB-check niet vangt, alleen een browser-smoke-test.

Smoke-test (student-login, Amy Hendriks): woordelijke citaten uit studentenstatuut,
BSA-regeling én examenreglement; 10 blockquote-citaten correct gerenderd.

## Graafschap (#126) — alleen gestaged

Bron: `graafschapcollege.nl`. Per-opleiding OER's en het examenreglement zijn **niet
publiek** (zitten in studiegidsen achter de structuur). Gestaged naar
`oeren/graafschap_oeren/_instelling/`: `studentenstatuut` (25-26) en `gedragscode`
(huisregels). **Bewust niet geactiveerd**: Graafschap is geen instelling in het project,
dus de bestanden zijn inert tot onboarding. De publieke klachtenregeling-PDF is van de
commerciële tak (Graafschap Opleidingen BV/CIVON), niet de MBO-college → niet gestaged.

## Curio (#127) — nieuwe instelling mét OER's

Anders dan KWIC/Graafschap publiceert Curio OER's publiek per crebo
(`curio.nl/sites/default/files/oer_documents/<crebo>_oer_…pdf`), dus hier konden de
OER's daadwerkelijk mee.

Onboardvolgorde:

1. **3 hardcoded instelling-lijsten** synchroon: `ingest._INSTELLINGEN` + `_MAP_NAAM`,
   `seed_bulk.INSTELLINGEN` (**als laatste** — de seed deelt één `Random(2026)` in
   lijst-volgorde; appenden houdt bestaande studenten identiek), `9_beheer._INSTELLING_KEYS`.
2. **9 OER's** → `oeren/curio_oeren/`, alle geïndexeerd mét kerntaken (1–17 per OER).
3. **4 instellingsbronnen** → `oeren/curio_oeren/_instelling/`: studentenstatuut,
   examenreglement (centraal 2025-2026), klachtenregeling (regeling klachten en
   geschillen), begeleidingsbeleid (ondersteuningsprofiel). Geen nieuwe soort nodig —
   mappen op de soorten die al voor KWIC gewired zijn.
4. `ingest --instelling curio`; geverifieerd: ≥2 OER's met kerntaken (alle 9).

**Seedless smoke-test** via de publieke intake-pagina `0_oer_vraag` (geen login/seed):
vraag over BPV bij Curio software-developer → Curio-OER geselecteerd, woordelijk citaat
("Volgens de OER, Bijlage 6a … 1740" BPV-uren).

## Bewuste scope-grenzen

- **Geen re-seed.** `seed_bulk` draaien zou ~200 Curio-nepstudenten aan de gedeelde
  demo-dataset toevoegen — niet gevraagd. De lijst-edits staan klaar zodat een latere
  seed Curio meeneemt; tot dan heeft Curio **0 studenten** (verwacht).
- De publieke intake-pagina wired alleen `examenreglement`, dus de smoke-test dekt
  OER + examenreglement-citatie; studentenstatuut/klachten/begeleiding voor Curio zijn
  pas via student-login (= na seed) end-to-end te testen.
- De 9 Curio-OER's zijn een **zoekresultaat-sample**, niet de volledige catalogus
  (geen browsebare OER-index op curio.nl).

## Openstaande vervolgacties

- [ ] Curio re-seed (`seed_bulk`) als de student-side getest moet worden → ~200 studenten +
      mentoren, daarna student-login smoke-test van de overige bronnen.
- [ ] Curio Entree-OER (crebo 23301) ontbreekt — de gegokte URL gaf 404; nazoeken indien gewenst.
- [ ] Graafschap volledige onboarding vergt minimaal één Graafschap-OER (publiek niet
      beschikbaar → via Box of een studiegids-PDF) + de 5 activatiestappen.

## Geverifieerd (per PR)

`ruff check` + `ruff format --check` clean; `pytest` 145 passed; UI-smoke-tests zoals
hierboven beschreven.
