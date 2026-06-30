---
name: add-institution
description: Onboard a new MBO institution ("instelling") into samenwijzer end-to-end — discover the OER data source, scrape & split per-crebo docs, wire it into all guarded + unguarded code locations, ingest, run tests + browser smoke-test, open a PR, and verify the Fly deploy. Runs either as a guided checklist OR autonomously when given an institution name + study-guide source URL (subagent-orchestrated, stops at a verified PR for review). Use when adding/onboarding a new college/instelling (e.g. Graafschap, Deltion, ROC X) or asked to "onboard an institution" / "/add-institution" / "onboard-institution".
---

# Add institution (onboard a new MBO instelling)

Onboards one institution into the **`validatie_samenwijzer/`** subproject (the active
FastAPI pipeline) — and keeps the legacy root pipeline (`src/samenwijzer/`, `scripts/`) from
silently drifting. The dominant failure mode is **silent 0-students**: a list missed, an OER
without parseable kerntaken, an ungitignored private dir. Every step below exists to catch one
of those. Run `uv`/`pytest`/`ruff` from the **`validatie_samenwijzer/` root**, not the repo root.

Pick a short lowercase `<key>` (e.g. `graafschap`). The institution's display name and folder
name derive from it. Confirm the `<key>` with the user before wiring — it's load-bearing across
~10 locations and the seed order depends on it.

## Two modes

- **Guided (default):** walk the phases below with the user, pausing for confirmation at the
  `<key>`, the re-seed step, and the merge.
- **Autonomous (args-driven):** triggered when the user supplies an **institution name** and a
  **study-guide source URL** ("onboard Graafschap from https://…"). Run the pipeline end-to-end
  with subagents, then **stop at a verified, open PR** — do NOT auto-merge or deploy. The
  verify-before-merge rule is hard: a human gives green light after seeing the smoke output.

### Autonomous orchestration

Inputs: `name` (display name), `source_url` (where guides live), optional `<key>` (else derive).
Run these stages; each writes a structured result you carry forward, and you keep a running
**gaps list** of anything you could not auto-detect/auto-do:

1. **Map (Explore subagent).** Dispatch an `Explore` agent to re-derive the live institution-wiring
   locations (don't trust this doc's line numbers — they drift). It must return every guarded +
   unguarded list, the `.gitignore` rule, and parser branches, with current file:line. This is the
   authoritative edit-list for stage 3.
2. **Discover + scrape (subagent).** From `source_url`, discover the data API / sitemap (model on
   `scripts/fetch_deltion.py`'s SQill discovery), write `scripts/fetch_<key>.py`, and pull guides
   into `oeren/<key>_oeren/`. If the source isn't machine-scrapeable, **stop and add to gaps** with
   what manual download is needed — do not fabricate a scraper.
3. **Split per-crebo (subagent).** Split combined PDFs so each file maps to exactly one crebo;
   normalise names. Place `_instelling/` regelingen.
4. **Wire (implementer subagent).** Edit every location from stage 1's map (core four + unguarded
   set). Seed list appended LAST. Mirror parser changes into the parent.
5. **Index + TDD validate (subagent, against a baseline).** Ingest, then run the existing suite
   **plus** assert the make-or-break invariant on live data: this institution has **≥2 OERs with
   parseable kerntaken** (else it silently seeds 0 students). Capture the baseline student/OER
   counts before and after so the diff is provable, not asserted.
6. **Browser smoke-test.** Drive the public intake (`0_oer_vraag`) against a freshly-indexed OER
   via `chrome-devtools-mcp`; capture the output.
7. **PR.** Open a PR (never push to `main`). Body MUST include: lists edited (from stage 1), OER
   count + the ≥2-kerntaken proof, smoke-test output, and the **gaps list** (locations/steps not
   auto-handled). Then stop and report — await human review.

Anything uncertain (ambiguous `<key>`, novel file format needing a new parser branch, a private
source needing gitignore + Box) goes in the gaps list rather than a silent guess. Re-seeding the
shared demo dataset stays a separate explicit step even in autonomous mode.

## Phase 0 — Discover the data source

Find where this institution publishes its OERs (study guides) and whether they're scrapeable.
Check the memory `reference_samenwijzer_oer_bronnen` first — it records which MBOs publish
publicly and how (Rijn IJssel/Curio/Aeres/Utrecht/Talland/Deltion scrapeable; Deltion via SQill
API; KWIC/Graafschap/Da Vinci not). Decide the acquisition path:

- **Scrapeable** → you'll add a `fetch_<key>.py` (Phase 1a).
- **Public PDFs, no API** → download manually / via a one-off script into the data dir.
- **Private (Box-only)** → the dir must be gitignored (Phase 2, item *gitignore*); data comes
  from Box via the existing `sync_oeren.sh` / `bootstrap.sh`.

Also identify whether the institution publishes institution-wide regelingen (examenreglement,
studentenstatuut, begeleidingsbeleid) → those go under `_instelling/` and map to
`db.INSTELLING_SOORTEN`.

## Phase 1 — Acquire & split per-crebo docs

OERs often arrive as combined PDFs; the pipeline keys on **one document per crebo**. Place data
under `oeren/<key>_oeren/` (note the suffix: `_oeren`, except the legacy `rijn_ijssel_oer`).

- **1a. Scraper (if scrapeable):** add `validatie_samenwijzer/scripts/fetch_<key>.py` modelled
  on `scripts/fetch_deltion.py` (target dir → `oeren/<key>_oeren`). Run it with `--preview`
  first, then for real.
- **1b. Split combined docs:** if multiple crebos live in one PDF, split per crebo so each file
  maps to a single crebo. `scripts/rename_oers.py --map <key>_oeren` and
  `scripts/fix_opleiding_namen.py --instelling <key>` help normalise names.
- **1c. Institution-wide regelingen:** place under `oeren/<key>_oeren/_instelling/` named per the
  soort (e.g. `examenreglement.pdf`, `studentenstatuut.pdf`). Extend `db.INSTELLING_SOORTEN`
  (`src/validatie_samenwijzer/db.py:10`) only if a new soort appears.

## Phase 2 — Wire into all code locations

The sync test (`tests/test_instelling_lijsten_sync.py`) enforces **four** lists, not three —
CLAUDE.md prose is stale. And several lists are **unguarded** (no test), which is exactly where
silent bugs hide. Edit, at minimum:

**Guarded core four (keys must match exactly):**
1. `src/validatie_samenwijzer/ingest.py` → `_INSTELLINGEN` (key → display name)
2. `src/validatie_samenwijzer/ingest.py` → `_MAP_NAAM` (key → `oeren/` subdir)
3. `scripts/seed_bulk.py` → `INSTELLINGEN` — **append LAST**. The seed shares one
   `Random(2026)` keyed on list order; inserting mid-list reshuffles every existing student.
4. `app_fastapi/main.py` → `_INSTELLING_KEYS` (beheer re-ingest dropdown scope)

**Unguarded — the silent-failure set (check each):**
5. `src/validatie_samenwijzer/chat.py` → `_INSTELLING_DOMEINEN` (key → school web domain, e.g.
   `kw1c.nl`). Missing → no web-search fallback for that institution.
6. `src/validatie_samenwijzer/oer_catalogus.py` → `_CATALOGUS_BRONNEN` — only if the institution
   gets a freshness scraper (Phase 1a + adapter registration).
7. `src/validatie_samenwijzer/oer_catalogus.py` → `_DIFF_SLEUTEL_VELDEN` — add the key here if
   the catalogue lacks a reliable leerweg (else every OER looks "new" on the freshness diff).
8. `.gitignore` (repo root) → add `oeren/<key>_oeren/` **if the institution is private/Box-only**.

**Parser branches (only if the filename/title format is novel):**
9. `src/validatie_samenwijzer/ingest.py` → `parseer_bestandsnaam` / `_extraheer_opleiding_uit_pdf`.
   If you touch these, mirror the change into the parent `src/samenwijzer/oer_parsing.py`
   (CLAUDE.md sync invariant).

**Legacy root pipeline (fix if you're touching it / want catalogs consistent):**
10. `scripts/build_oer_catalog.py` → `_INSTELLING_DISPLAY` (currently STALE — missing 4 of 9).
11. `scripts/generate_synthetisch_data.py` → `_OVER_TE_SLAAN_INSTELLINGEN` / `_AANTAL_INSTELLINGEN`.

> Do **not** hand-edit `data/oer_corpus_manifest.json` — it's generated by `oer_catalogus.py`.

## Phase 3 — Index

```bash
# from validatie_samenwijzer/, OEREN_PAD points at the repo-root oeren/
OEREN_PAD=../oeren uv run python -m validatie_samenwijzer.ingest --instelling <key>
```

**Then verify ≥2 OERs have parseable kerntaken** — this is the make-or-break check. An OER that
indexes (`geindexeerd=1`) but yields no kerntaken produces 0 seeded students for that institution:

```bash
sqlite3 -readonly data/validatie.db \
  "SELECT o.opleiding, o.crebo, o.geindexeerd FROM oer_documenten o
   JOIN instellingen i ON o.instelling_id=i.id WHERE i.naam='<key>';"
```

If kerntaken are missing, the OER structure isn't parseable — check the per-institution parser
branch or add a curated fallback before proceeding.

## Phase 4 — Tests + lint

```bash
uv run ruff check --fix . && uv run ruff format .
uv run ty check
uv run pytest          # test_instelling_lijsten_sync MUST pass — it catches a missed core list
```

## Phase 5 — Browser smoke-test (the real gate)

Green pytest ≠ feature works. Start the app and drive the **public intake** (`0_oer_vraag` chat
— no login/seed needed) against an actually-indexed OER for the new institution, via
`chrome-devtools-mcp`. See the `ship` skill for the verify-then-merge discipline. Paste a
screenshot / concrete observation. The public-chat login path is in the
`reference_validatie_publieke_chat_login` memory if you need a seeded-student scenario.

Re-seeding the shared ~200-students/institution demo dataset (`seed_bulk.py`) is a **separate,
explicitly-confirmed** step — do NOT trigger it implicitly during onboarding. KD + skills are
crebo-shared (not institution-bound); never overwrite the national KD with an institution variant.

## Phase 6 — PR

Branch (never push to `main`), open a PR with `gh pr create`. Attribution ends with exactly
`Ed de Feber, in nauwe samenwerking met Claude` — no `Co-Authored-By`. Include in the body: which
lists were edited, OER count indexed, the kerntaken-verification result, and the smoke-test proof.

**Smoke-test output must be visible in the chat before merge** (a PreToolUse hook on `gh pr merge`
enforces this). Wait for green light, then merge.

## Phase 7 — Verify deploy

The repo-root `Dockerfile`/`fly.toml` deploy the subproject; corpus is baked into the image, so a
deploy is required for new OERs to appear in production. From the **repo root**:

```bash
flyctl deploy -a digitale-gids --remote-only
```

Then open https://digitale-gids.fly.dev and confirm the new institution's OER answers a question
live. "Done" = verified live, not "merge succeeded".

## Checklist

- [ ] `<key>` confirmed with the user
- [ ] Data source identified; scraper added if scrapeable
- [ ] OERs split per-crebo under `oeren/<key>_oeren/`; `_instelling/` regelingen placed
- [ ] Core four lists edited (seed appended LAST); unguarded set (5–8) checked; parser mirrored if touched
- [ ] `.gitignore` updated if institution is private
- [ ] Ingested; **≥2 OERs verified to have kerntaken**
- [ ] ruff + ty + pytest green (incl. `test_instelling_lijsten_sync`)
- [ ] Browser smoke-test on public intake, output shown in chat
- [ ] Re-seed treated as a separate explicit step (not auto-run)
- [ ] PR opened with correct attribution; merged only after smoke-test shown + green light
- [ ] Deployed + verified live on digitale-gids.fly.dev
