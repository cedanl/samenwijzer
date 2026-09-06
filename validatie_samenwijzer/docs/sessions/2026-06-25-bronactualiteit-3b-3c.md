# Sessielogboek 25 juni 2026 — Bronactualiteit Fase 3b + 3c

Eén-blik-overzicht van wat er vandaag is gebeurd, zodat je de draad zo weer oppakt.

## Resultaat: twee fasen af, gemerged én live geverifieerd

| Fase | Wat | PR | Op main |
|---|---|---|---|
| **3b** | `content_hash`-register + content-wijzigingsdetectie | #220 | `3771abc` |
| **3c** | beheer-paneel + tuple-manifest + wekelijkse GitHub Action | #221 | `1b8c202` |

De wekelijkse Action draait nu **ma 07:00 UTC** en is vandaag handmatig getest → opende **issue #222**.

## Fase 3b — wat het doet (PR #220)

Detecteert dat een OER die we **al** hebben upstream is **herzien** (zelfde crebo/leerweg/cohort, andere inhoud).

- Nullable `content_hash`-kolom op `oer_documenten` + `instelling_documenten` via idempotente `ALTER TABLE ADD COLUMN` (nooit DROP).
- Eén gedeelde `bereken_content_hash` (whitespace-genormaliseerd) — ingest schrijft 'm, de check vergelijkt 'm.
- `gewijzigde_oers()` refetcht per Deltion-OER de upstream-content (`/reports/<uuid>/html`) en vergelijkt de hash. Deltion-only; andere instellingen = "niet gecheckt".
- CLI: `check-bron-updates --oer-inhoud` (eigen flag — duur: refetch per document).
- Baseline-eerlijk: een rij zonder hash = "baseline ontbreekt", niet "ongewijzigd".

**Let op voor morgen:** de lokale/prod `validatie.db` heeft na de migratie alle `content_hash = NULL`. Pas na een `ingest --reset` worden de baselines gevuld; daarna meldt `--oer-inhoud` echte herzieningen i.p.v. "zonder baseline".

## Fase 3c — wat het doet (PR #221)

Maakt de check zichtbaar én operationeel.

- **Gecommit tuple-manifest** `data/oer_corpus_manifest.json` (snapshot van `(crebo,leerweg,cohort)` per instelling), regenereert bij elke ingest. Hiermee kan de Action diffen **zonder** de gitignorede `validatie.db`.
- **`--manifest`-modus + `--alleen-oer`** in `check-bron-updates` (diff tegen de manifest; alleen de OER-bron).
- **`/beheer`-paneel**: twee knoppen die `check-bron-updates` als subprocess draaien (via de bestaande allowlist; geen route-logica).
- **Wekelijkse Action** `.github/workflows/bronactualiteit.yml`: draait `--oer --manifest --alleen-oer`, opent/actualiseert bij een signaal een issue met label `bronactualiteit`.

## De grootste vangst van vandaag

De UI-smoke-test van het beheer-paneel legde een **pre-existing off-by-one** bloot (uit PR #187, niet van 3c): `_PROJECT_ROOT = parents[2]` (repo-root) brak **álle** beheer-subprocess-taken (module/scripts niet gevonden) in dev én prod. Gefixt naar `parents[1]` (subproject-root) — consistent met de prod-`WORKDIR` en `OEREN_PAD=../oeren`. Met regressietest. Dit is precies waarom je op browser-/UI-smoke staat: pytest + 3 code-reviews misten het, de live-klik niet.

## Werkwijze vandaag

Subagent-driven development: per taak een implementer-subagent (TDD) → spec+quality-review-subagent → fix indien nodig → whole-branch review (Opus) → PR → squash-merge. Elke "klaar"-claim onderbouwd met **uitgevoerd bewijs** (pytest, live migratie op 729 rijen, manifest≡DB-pariteit, panel-SSE exit 0, Action-run die issue #222 opende).

## Open follow-ups (geen van deze blokkeert iets)

1. **Issue #222 is echt werk**: 15 nieuwe OER's upstream (aeres 11, deltion 3, utrecht 1) wachten op een lokale ingest + gecommitte manifest-update. De Action blijft dit melden tot ze geïngest zijn.
2. **3b niet-blokkerend** (uit de reviews): graceful guard voor `--oer-inhoud` op een pré-migratie DB; per-OER "niet gecheckt"-teller bij refetch-fout; dedup in `gewijzigde_oers`; `details["gecheckt"]`-overlap.
3. **CI-annotatie**: `actions/checkout@v4` + `setup-uv@v4` draaien op geforceerde Node 24 (Node 20 deprecated) → ooit bumpen naar `@v5`.
4. **Bronactualiteit-roadmap**: 3a/3b/3c klaar. Resterende hiaten staan in de plannen (Talland/Curio geen adapter; MBO Utrecht v1 mist cohort-2025).

## Waar het allemaal staat

- Plannen: `docs/plans/2026-06-25-bronactualiteit-fase3b-*.md` + `-fase3c-*.md`
- PR-bodies #220/#221 (gedetailleerde NL-omschrijving op GitHub)
- SDD-ledgers (gitignored scratch): `.superpowers/sdd/progress.md` + per-task brief/report-bestanden
