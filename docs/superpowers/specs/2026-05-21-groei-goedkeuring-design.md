# Ontwerp — Mentor-goedkeuring van groei (per werkproces)

**Datum:** 2026-05-21
**Status:** Goedgekeurd ontwerp, gereed voor implementatieplan

## Probleem

De student schat in het groeidossier zijn groei per werkproces in (self-assessment).
Op dit moment werken die self-scores direct door in de voortgangsmodule (en zouden ze
ongefilterd ook de docent-risico-triage beïnvloeden). Gewenst is een
goedkeuringscyclus: **de student dient groei in → de mentor keurt goed of geeft terug met
verbeterfeedback → pas na goedkeuring telt de groei mee.**

Dit borgt dat zelfbeoordeling alléén niets verschuift bij de mentor; alleen
mentor-gevalideerde groei voedt de voortgang en de risico-triage.

## Scope

In scope:
- Goedkeuringsstatus per werkproces met vier toestanden en bijbehorende overgangen.
- Datamodeluitbreiding van `groei_actueel` (Optie A: bestaande tabel uitbreiden).
- Overlay die uitsluitend goedgekeurde scores meeneemt; herberekening van kerntaak-scores,
  headline-voortgang en risico-vlag.
- UI op pagina 6 (groeidossier): student dient in, mentor keurt goed/geeft terug.

Buiten scope (bewust):
- Bewijsstuk-goedkeuring.
- Notificaties naar de student bij teruggeven.
- Status-kleuring in de history-tab en het spinneweb (die tonen álle ingediende metingen).

## Beslissingen (uit brainstorm)

| Vraag | Keuze |
|---|---|
| Granulariteit van indienen/goedkeuren | **Per werkproces** |
| Indien-moment | **Concept opslaan + apart indienen** (twee stappen) |
| Bewerken van een goedgekeurd werkproces | **Terug naar ingediend**; oude goedgekeurde score blijft meetellen tot heraccordering |
| Plek van mentor-acties | **Pagina 6 (groeidossier)**, niet het groepsoverzicht |
| History-tab / spinneweb | Tonen **álle ingediende metingen**, niet alleen goedgekeurde |
| Datamodel | **Optie A** — `groei_actueel` uitbreiden |

## Statusmodel (per werkproces)

Toestanden:
- **concept** — opgeslagen, telt niet mee, mentor ziet het niet als actiepunt.
- **ingediend** — staat in de beoordeel-wachtrij van de mentor.
- **goedgekeurd** — `goedgekeurde_score` := score; **telt mee** in de overlay.
- **teruggegeven** — mentor gaf verbeterfeedback; student moet herzien en opnieuw indienen.

Overgangen:

```
              Opslaan              Indienen            Goedkeuren
   (niets) ─────────────► concept ──────────► ingediend ──────────► goedgekeurd
                            ▲  ▲                   │                     │
                            │  │      Teruggeven   │ (telt mee)          │
                            │  └──── teruggegeven ◄┘                     │
                            │         (+verbeterfeedback)                │
                            └──────── Opslaan (bewerken) ────────────────┘
```

Regels:
- `Opslaan` zet een werkproces (nieuw, of bewerkt vanuit `teruggegeven`/`goedgekeurd`) op
  `concept`. De `goedgekeurde_score` blijft daarbij ongewijzigd.
- `Indienen` zet `concept`/`teruggegeven` → `ingediend`.
- `Goedkeuren` (mentor) zet `ingediend` → `goedgekeurd`, en `goedgekeurde_score := score`.
- `Teruggeven` (mentor) zet `ingediend` → `teruggegeven` met verplichte `mentor_opmerking`.
- Wat in de overlay meetelt is uitsluitend `goedgekeurde_score`. Is die `NULL`, dan houdt het
  werkproces zijn synthetische basiswaarde.

## Datamodel (Optie A)

`groei_actueel` (PK blijft `(studentnummer, wp_kolom)`) krijgt vijf kolommen erbij:

| kolom | type | betekenis |
|---|---|---|
| `status` | `TEXT NOT NULL DEFAULT 'concept'` | concept/ingediend/goedgekeurd/teruggegeven |
| `goedgekeurde_score` | `INTEGER` (nullable) | laatst goedgekeurde score — wat meetelt |
| `mentor_opmerking` | `TEXT NOT NULL DEFAULT ''` | verbeterfeedback bij teruggeven |
| `beoordeeld_door` | `TEXT` (nullable) | mentor-naam |
| `beoordeeld_op` | `TEXT` (nullable) | ISO-timestamp |

Migratie: `init_db()` maakt de tabel voor verse DB's met de nieuwe kolommen, en voert voor
bestaande DB's een idempotente migratie uit via `PRAGMA table_info(groei_actueel)` gevolgd door
`ALTER TABLE groei_actueel ADD COLUMN ...` voor elke ontbrekende kolom.

Onveranderd:
- `groei_historie` — snapshot bij elke opslag (tijdlijn + spinneweb).
- `mentor_feedback` — algemene per-kerntaak reflectie, naast de per-wp `mentor_opmerking`.

## Store-functies (`groei_store.py`)

- `sla_groei_op(studentnummer, rijen)` — upsert werkende score met `status='concept'`; behoudt
  bestaande `goedgekeurde_score`. Snapshot in `groei_historie` zoals nu.
- `dien_in(studentnummer, wp_kolommen)` — zet de opgegeven werkprocessen van
  `concept`/`teruggegeven` naar `ingediend`.
- `keur_goed(studentnummer, wp_kolom, mentor_naam)` — `status='goedgekeurd'`,
  `goedgekeurde_score := score`, `mentor_opmerking=''`, `beoordeeld_door/op` gezet.
- `geef_terug(studentnummer, wp_kolom, mentor_naam, opmerking)` — `status='teruggegeven'`,
  `mentor_opmerking := opmerking`, `beoordeeld_door/op` gezet. `goedgekeurde_score` blijft
  ongewijzigd, zodat een eerder goedgekeurde waarde blijft meetellen.
- `GroeiActueel`-dataclass uitgebreid met `status`, `goedgekeurde_score`, `mentor_opmerking`,
  `beoordeeld_door`, `beoordeeld_op`.
- `get_actueel` / `get_alle_actueel` geven de uitgebreide velden mee.

## Overlay & afgeleide metrieken (`groei.py`)

`overlay_self_scores(df)`:
1. Legt per student uitsluitend `goedgekeurde_score` (niet de werkende score) over de
   wp-kolommen, alleen waar de wp in df niet `NaN` is en `goedgekeurde_score` niet `NULL`.
2. Herberekent de `kt_<int>`-scores als gemiddelde van hun werkprocessen.
3. Herberekent de headline-`voortgang` als gemiddelde van de kt-scores / 100 (geklemd op 0–1),
   alleen voor studenten met goedgekeurde scores.
4. Herberekent de `risico`-vlag via `transform._bereken_risico(df)` (laag-toegestaan: `groei`
   staat boven `transform` in de laagvolgorde).

Concept/ingediend/teruggegeven scores beïnvloeden geen enkele afgeleide metriek.

## UI — pagina 6 (`app/pages/6_groeidossier.py`)

### Student (eigenaar)
Per werkproces:
- statusbadge: 🟡 concept · 📤 ingediend · ✅ goedgekeurd · ↩️ teruggegeven;
- bij `teruggegeven`: opvallende callout met de `mentor_opmerking`;
- bestaande score-slider + verantwoording.

Onderaan twee knoppen:
- **💾 Concept opslaan** — slaat gewijzigde werkprocessen op als `concept` (zet goedgekeurde wp's
  terug naar `concept`). Ververst de session-df *niet* (concept telt niet mee).
- **📤 Indienen** — zet alle `concept`/`teruggegeven` werkprocessen op `ingediend`.

### Mentor
Per kerntaak, voor elk **ingediend** werkproces:
- de score + verantwoording van de student;
- een verbeterfeedback-veld;
- **✅ Goedkeuren** / **↩️ Teruggeven** (teruggeven vereist een ingevulde feedbacktekst).

Reeds goedgekeurde/teruggegeven werkprocessen tonen hun status. De bestaande per-kerntaak
feedback blijft. Na een mentor-actie wordt `st.session_state["df"] =
overlay_self_scores(st.session_state["df_basis"])` ververst zodat voortgang + risico meteen
meebewegen.

## Impact op reeds gemaakte wijzigingen

Tijdens de verkenning zijn al enkele wijzigingen gedaan; die worden als volgt aangepast:
- Voortgang-recompute in `overlay_self_scores`: **blijft**, maar leest nu `goedgekeurde_score`.
- Risico-recompute: **toegevoegd** in `overlay_self_scores`.
- De df-refresh na opslaan op pagina 6: **verplaatst** van de student-opslaan-actie naar de
  mentor-goedkeuren/teruggeven-acties.
- Spinneweb "vorige meting" oranje + caption: ongewijzigd (al gereed).

## Teststrategie

`tests/test_groei_store.py` (nieuw of uitgebreid):
- `sla_groei_op` zet `status='concept'` en behoudt `goedgekeurde_score`.
- `dien_in` zet concept/teruggegeven → ingediend.
- `keur_goed` zet status + `goedgekeurde_score` + beoordeeld_*.
- `geef_terug` zet status + `mentor_opmerking`.
- Bewerken van een goedgekeurd werkproces reset status naar concept maar behoudt
  `goedgekeurde_score`.
- Migratie: `init_db` op een bestaande DB zonder de nieuwe kolommen voegt ze toe (idempotent).

`tests/test_groei.py` (uitgebreid):
- Overlay neemt alleen `goedgekeurde_score` mee; concept/ingediend/teruggegeven tellen niet mee.
- Voortgang herberekend uit goedgekeurde kt-scores.
- Risico-vlag herberekend.
- Overlay zonder `voortgang`-kolom crasht niet (regressie).

`tests/test_architecture.py`:
- `groei.py` mag `transform` importeren (laag-toegestaan); blijft binnen de bestaande
  laagregels.

## Architectuur-naleving

- Alle SQLite-schrijfacties lopen via `groei_store.py` (geen raw SQL in `app/`).
- Business-logica (overlay, statusovergangen) in `groei.py` / `groei_store.py`, niet in `app/`.
- `groei` staat boven `transform` in de laagvolgorde, dus de `transform._bereken_risico`-import
  respecteert de richting.
