# Ontwerp: `--refresh-fallbacks` (Skills Fase 3)

**Status:** ontwerp goedgekeurd · **Datum:** 2026-06-10 ·
**Context:** Fase 3 uit [`auto-sync-afgeleide-bronnen.md`](auto-sync-afgeleide-bronnen.md)

## Doel

De skills-taxonomie kent twee bronnen: **CompetentNL** (crebo-direct, exacte UWV-data, voorkeur)
en **ESCO** (LLM-gematchte fallback). CompetentNL groeit met ~20-30 beroepen per kwartaal. Een
crebo die vandaag op ESCO valt, kan volgend kwartaal wél in CompetentNL zitten. `--refresh-fallbacks`
checkt de bestaande non-CompetentNL artefacten periodiek opnieuw en **upgradet** ze zodra CompetentNL
ze toevoegt — zonder de gepinde ESCO-matches te verstoren.

Huidige stand: 243 artefacten `bron=CompetentNL`, 129 `bron=ESCO`. Die 129 zijn de upgrade-kandidaten.

## Scope

**Alleen de skills-kant.** De KD-kant van Fase 3 (kwartaal s-bb-bundle-refresh) is bewust **buiten
scope** — dat hangt af van een externe s-bb-kwartaalrelease en is een operationeel/handmatig proces,
geen code. Apart op te pakken.

## Kernprincipe: CompetentNL-only re-check (churn-vrij)

Voor elke non-CompetentNL crebo wordt **uitsluitend** `competentnl_bron.haal_skills_record()`
aangeroepen — de deterministische, crebo-directe bron:

- **Hit** → overschrijf `data/skills/<crebo>.json` met het CompetentNL-record (upgrade).
- **Miss** → laat het bestaande ESCO/geen-match-artefact byte-identiek ongemoeid.

De niet-deterministische ESCO-LLM-match wordt **nooit** opnieuw gerold. Gevolg: de git-diff bevat
alléén echte upgrades, perfect reviewbaar vóór een PR. Dit is het verschil met een naïeve
`--reset` op de fallbacks, die alle 129 ESCO-matches zou her-rollen en de "gepinde match"-eigenschap
zou breken.

## Architectuur & plaatsing

De kernlogica leeft in **`scripts/build_skills_taxonomie.py`**, omdat de json-write
(`record.to_dict()` → `<crebo>.json`) én `_schrijf_overzicht()` (CSV-herbouw) daar al staan. Zo
blijft de wijziging chirurgisch: geen write-logica naar het package verhuizen.

`sync_afgeleid.py` krijgt een doorgeef-vlag `--refresh-fallbacks` die via de bestaande `_run()`-helper
naar `build_skills_taxonomie.py --refresh-fallbacks` shelt — exact het patroon dat `_bouw_skills` nu
al gebruikt. Eén consistent entry point voor de gebruiker, minimale koppeling over de
subprocess-grens.

## Componenten

### 1. `build_skills_taxonomie.py` — `refresh_fallbacks()` + `--refresh-fallbacks`

```
refresh_fallbacks() -> tuple[list[str], list[str]]   # (upgraded, nog_fallback)
  voor elke data/skills/<crebo>.json (skip _match_overzicht.csv):
    record = json laden            # corrupt/onleesbaar → waarschuw + skip
    als record["bron"] == "CompetentNL":  skip        # nooit opnieuw bevragen
    opleiding = record["opleiding"]                    # uit de json, geen DB-roundtrip
    nieuw = competentnl_bron.haal_skills_record(crebo, opleiding)
    als nieuw is not None:                             # CompetentNL heeft 'm nu
      schrijf <crebo>.json met nieuw.to_dict()         # upgrade (overschrijf)
      upgraded.append(crebo)
    anders:
      nog_fallback.append(crebo)                       # ongemoeid laten
  als upgraded:  _schrijf_overzicht()                  # CSV herbouwen
  log samenvatting; return (upgraded, nog_fallback)
```

De `opleiding` komt uit de bestaande json (niet uit de DB) — robuuster en zonder DB-afhankelijkheid;
CompetentNL-lookup is toch crebo-direct, de opleidingsnaam dient alleen het record-label.

### 2. `sync_afgeleid.py` — `--refresh-fallbacks`

Nieuwe vlag in de mutually-exclusive groep (`--crebo` / `--alles` / `--refresh-fallbacks`). Shelt via
`_run()` naar het build-script. De rapportage wordt door het build-script geprint (zie hieronder),
dus `sync_afgeleid` parst geen counts terug.

## Rapportage (working-tree only)

Conform Fase 1/2: de reconciliatie schrijft alleen lokaal en raakt `main`/Box niet aan. Het
build-script print na afloop een zichtbare samenvatting met concrete vervolgactie:

```
Refresh-fallbacks klaar: 3 geüpgraded naar CompetentNL (25180, 25234, 25751), 126 nog ESCO/geen-match.
→ commit data/skills/ via PR
```

Bij 0 upgrades: expliciete regel dat er niets te upgraden viel (en, indien de key ontbreekt, dát als
oorzaak — zie error handling).

## Error handling

- **Geen `COMPETENTNL_API_KEY`**: `haal_skills_record` geeft overal `None` → 0 upgrades. Het script
  logt **expliciet** dat de key vereist is, zodat "0 upgrades" niet als "niets te doen" wordt gelezen.
- **SPARQL-fout op één crebo**: telt als miss (`None`); de loop gaat door — één hapering blokkeert de
  rest niet.
- **Corrupte/onleesbare `<crebo>.json`**: overslaan + waarschuwen, niet crashen.

## Testing

Unit-tests met gemockte `competentnl_bron.haal_skills_record`:

1. ESCO-crebo die nu een CompetentNL-hit geeft → json overschreven, `bron` flipt naar `CompetentNL`,
   crebo in `upgraded`, `_match_overzicht.csv` herbouwd.
2. ESCO-crebo die mist → bestand byte-identiek ongemoeid, in `nog_fallback`.
3. Geen API-key (functie geeft `None`) → 0 upgrades, geen crash, key-waarschuwing gelogd.
4. CompetentNL-crebo wordt nooit opnieuw bevraagd (mock niet aangeroepen voor die crebo).

## Bewust buiten scope

- **KD-kant** (kwartaal s-bb-bundle-refresh) — externe kwartaalrelease, operationeel proces.
- **Automatische trigger** (cron/ingest-hook) — `--refresh-fallbacks` draait handmatig/periodiek;
  bewust níet aan de ingest-hook gehangen (een OER-wijziging met dezelfde crebo mag geen churn geven).
- **Counts terug in `sync_afgeleid`'s `Samenvatting`** — het build-script rapporteert zelf; geen
  parsing over de subprocess-grens.

## Implementatie-aanknopingspunten

- `scripts/build_skills_taxonomie.py` — `_schrijf_overzicht()` (regel ~128), json-write (regel ~101),
  argparse (regel ~66).
- `src/validatie_samenwijzer/competentnl_bron.py::haal_skills_record(crebo, opleiding) -> SkillsRecord | None`.
- `src/validatie_samenwijzer/sync_afgeleid.py` — argparse-groep (regel ~213), `_run()` (regel ~103),
  `_skills_zonder_match()` (regel ~82, met de bestaande Fase 3-verwijzing op regel ~88).
