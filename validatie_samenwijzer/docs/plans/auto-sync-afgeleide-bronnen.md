# Plan: automatische sync van KD + skills bij oeren-wijzigingen

**Status:** Fase 1 + 2 geïmplementeerd (PR #110, #111); Fase 3 open · **Datum:** 2026-06-01

## Doel

Zodra de `oeren/`-map wijzigt (nieuwe OER's, updates, nieuwe instellingen), worden de
afgeleide bronnen — het **kwalificatiedossier (KD)** en de **skills-taxonomie** — automatisch
bijgewerkt, incrementeel per crebo en idempotent.

## Kernprincipe: desired-state reconciliatie (niet de watcher)

De robuuste motor is **stateless**: vergelijk de geïndexeerde crebo's in `oer_documenten` met
de bestaande artefacten (`data/skills/<crebo>.json`, `kwalificatiedossiers/pdfs/<crebo>.md`) en
bouw alleen wat ontbreekt. Eén idempotente operatie dekt nieuwe OER's, nieuwe instellingen die
honderden bestanden dumpen, catch-up na downtime én gemiste filesystem-events — zonder
event-boekhouding.

Eén commando, drie aanroepers:

```
werk_afgeleide_bronnen_bij [--crebo X | --alles]
```

- `bootstrap.sh` / `ingest` → `--alles` ná indexeren (de echte update-route: Box→rclone→bootstrap)
- `watcher.py` → `--crebo X` (latency-optimalisatie voor een always-on machine)
- (later) periodiek vangnet → `--alles`

## De asymmetrie tussen de twee bronnen

| Bron | Mechanisme | "Direct" bij een nieuwe crebo? |
|---|---|---|
| **Skills** | live API per crebo (CompetentNL SPARQL → ESCO fallback) | **Ja, altijd instant** |
| **KD** | batch tegen de lokale s-bb-bundle (zips + crebolijsten) | **Alleen als het dossier al in de bundle zit**; een echt nieuw dossier wacht op de volgende s-bb-bundle-refresh (s-bb update't per kwartaal) |

Er is **geen live s-bb per-crebo-API** in de huidige code (`scripts/download_kwalificatiedossiers.py`
werkt tegen lokaal gedownloade zips + crebolijsten). KD-auto-update is dus begrensd door de
versheid van die bundle; ontbreekt een dossier, dan wordt dat **gelogd als gat, niet als fout**.

Een OER-**inhoudswijziging** met ongewijzigde crebo triggert **niets** — beide bronnen zijn
crebo-gekoppeld, dus reconciliatie slaat het correct over. Geen churn bij elke re-ingest.

## Beslissingen (vastgesteld met de gebruiker)

### Propagatie: working-tree only
De reconciliatie **schrijft alleen lokaal** en raakt `main` niet aan (conform agent-regel #5:
nooit auto-push naar main). Cruciaal gevolg: ze moet **zichtbaar rapporteren wat ze veranderde**,
zodat een mens weet wat te doen:

```
Reconciliatie klaar: +3 skills, +1 KD, 2 KD-gaten (crebo 25xxx, 25yyy).
→ commit data/skills/ via PR
→ sync KD naar Box: ./scripts/sync_kwalificatiedossiers.sh --upload
```

Dit sluit aan op het principe "achtergrond-processen tonen altijd zichtbare status" — geen
stille wijzigingen die zich opstapelen.

> Achtergrond van de keuze: skills zijn **git-tracked** (`data/skills/`), KD is **gitignored +
> Box-synced**. Dat zijn twee distributiekanalen. Auto-update naar één van beide stilletjes zou
> de andere machines/prod niet bereiken; daarom expliciet working-tree only + rapportage, en de
> mens kiest het kanaal (PR voor skills, Box-upload voor KD).

### Triggers: ingest/bootstrap-hook + watcher real-time
1. **Ingest/bootstrap-hook** (de kern): na `ingest`/`bootstrap.sh` → reconciliatie `--alles`.
   Dekt de echte update-route en bulk-imports van nieuwe instellingen. Geen daemon nodig.
2. **Watcher real-time**: `watcher.py` bepaalt na een succesvolle ingest de crebo van het
   bestand en roept reconciliatie `--crebo …` aan — gededupt per crebo binnen de debounce
   (200 bestanden → ~14 crebo-calls, niet 200×).

Géén cron-vangnet in v1 (kan later toegevoegd worden). Let op: een periodiek vangnet kan **niet**
op stock GitHub Actions draaien — daar ontbreken `oeren/`, de s-bb-zips, `validatie.db` en de
API-keys. Het moet op een machine met Box-synced data + keys.

## Fasering

| Fase | Werk | Verificatie | Status |
|---|---|---|---|
| **1** | Orchestrator `sync_afgeleid.py` + single-crebo entry points (KD-download + markitdown-convert per losse crebo; skills heeft al `--crebo`). `--crebo`/`--alles`, idempotent, KD-gat → loggen. | nieuwe crebo in DB → `--alles` maakt KD (indien in bundle) + skills; gat wordt gelogd | ✅ PR #110 |
| **2** | Ingest- + watcher-hook + change-rapportage (samenvatting van wat te committen/syncen) | bestand in `oeren/` → KD+skills verschijnen + samenvatting toont vervolgacties | ✅ PR #111 |
| **3** (later) | `--refresh-fallbacks`: de ESCO-crebo's periodiek opnieuw tegen CompetentNL checken (groeit ~20-30 beroepen/kwartaal); kwartaal s-bb-bundle-refresh | ESCO-crebo die later in CompetentNL komt, upgrade't naar CompetentNL | ⏳ open |

## Bewust buiten scope

- **Cron-vangnet** (niet gekozen voor v1) — ingest-hook + handmatige `--alles` dekken het.
- **On-demand s-bb-fetch per crebo** — geen bestaande capability; KD voor echt nieuwe dossiers
  blijft begrensd door de bundle-versheid. Zou apart onderzoek vergen.

## Implementatie-aanknopingspunten (huidige code)

- `watcher.py` — debounced filesystem-events → `_ingesteer(pad)` (ingest-subprocess per bestand).
  Haakpunt: ná succesvolle ingest crebo bepalen → reconciliatie aanroepen.
- `ingest.py::parseer_bestandsnaam()` / `oer_documenten.crebo` — crebo per bestand.
- `scripts/build_skills_taxonomie.py` — heeft al `--crebo`; idempotent.
- `scripts/download_kwalificatiedossiers.py` — batch tegen lokale bundle; **heeft een
  single-crebo modus nodig** (Fase 1-refactor).
- `scripts/convert_kwalificatiedossiers_md.py` — markitdown-convert; **single-file modus nodig**.
- `scripts/bootstrap.sh` — voegt `--alles`-aanroep toe ná ingest+seed.
