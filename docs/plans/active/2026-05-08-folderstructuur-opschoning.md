# Folderstructuur-opschoning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Maak de mappenstructuur van `samenwijzer/` (root) en `validatie_samenwijzer/` (subproject) platter en beter benoembaar — zonder source-paden te raken.

**Architecture:** Drie afgebakende migraties: (1) `validatie_samenwijzer/oeren/` ontdubbelen via `OEREN_PAD`-env-var, (2) `validatie_samenwijzer/{seed,tools}/` mergen in `scripts/`, (3) `docs/` consolideren van 6 sub-mappen naar 3 (`designs/`, `plans/{active,completed}/`, `specs/`). Elke migratie is op zichzelf groen (pytest + Streamlit-rooktest) voor we doorgaan naar de volgende.

**Tech Stack:** Bash/`git mv` voor folder-ops; `uv run pytest`/`uv run streamlit` voor verificatie; Streamlit 1.42+, FastAPI, SQLite (geen wijzigingen aan code-paden).

**Spec:** `docs/superpowers/specs/2026-05-08-folderstructuur-opschoning-design.md`

**Belangrijk vooraf:** alle `git mv` zorgt voor automatische rename-detectie in git history. Gebruik **nooit** `mv` + `git add` afzonderlijk — dat verbreekt blame.

---

## Task 0: Pre-flight check

**Files:** geen wijzigingen.

**Doel:** baseline vaststellen — beide projecten groen, werkboom schoon. Als deze taak rood is, **stop** en los eerst op.

- [ ] **Step 1: Verifieer schone werkboom**

```bash
cd /home/eddef/projects/samenwijzer
git status --porcelain
```

Verwacht: lege output. Niet leeg → committen of stashen voor we beginnen.

- [ ] **Step 2: Verifieer pytest groen op samenwijzer**

```bash
cd /home/eddef/projects/samenwijzer
uv run pytest -q
```

Verwacht: `passed` zonder failures. Genoteerd aantal passing tests = baseline-N.

- [ ] **Step 3: Verifieer pytest groen op validatie**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
uv run pytest -q
```

Verwacht: `passed`. Genoteerd aantal passing tests = baseline-V.

- [ ] **Step 4: Bevestig dat `.env`-bestanden gitignored zijn**

```bash
cd /home/eddef/projects/samenwijzer
git ls-files | grep -E '\.env$' || echo "OK — geen .env in git"
git -C validatie_samenwijzer ls-files | grep -E '\.env$' || echo "OK — geen .env in git"
```

Verwacht: voor beide projecten "OK — geen .env in git". Als één van beide treffer geeft → **stop** en escaleer naar gebruiker (gevoelige data).

---

## Task 1: Validatie — `oeren/` ontdubbelen

**Files:**
- Modify: `validatie_samenwijzer/.env` (regel toevoegen)
- Modify: `validatie_samenwijzer/.env.example` (regel wijzigen)
- Delete: `validatie_samenwijzer/oeren/` (hele tree, ~30 PDFs/MDs)

**Doel:** `validatie_samenwijzer/oeren/` opheffen; alle code blijft werken doordat `OEREN_PAD=../oeren` naar de root-`oeren/` wijst.

- [ ] **Step 1: Voeg `OEREN_PAD` toe aan validatie `.env`**

Open `validatie_samenwijzer/.env` en voeg toe (één nieuwe regel onderaan):

```
OEREN_PAD=../oeren
```

> Behoud bestaande `ANTHROPIC_API_KEY=...`, `TWILIO_*`-, `OPENAI_API_KEY`-, `NGROK_AUTHTOKEN`-regels ongewijzigd — niet aanraken.

- [ ] **Step 2: Update `.env.example`**

Bewerk `validatie_samenwijzer/.env.example`:

Vervang de regel `OEREN_PAD=oeren` door:

```
OEREN_PAD=../oeren
```

- [ ] **Step 3: Verifieer dat ingest werkt met de nieuwe oeren-pad**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
uv run python -m validatie_samenwijzer.ingest --help
```

Verwacht: helptekst zonder errors.

```bash
uv run python -c "
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
pad = Path(os.environ.get('OEREN_PAD', 'oeren'))
print(f'OEREN_PAD resolves naar: {pad.resolve()}')
print(f'Bestaat: {pad.exists()}')
print(f'Submappen: {sorted(p.name for p in pad.iterdir() if p.is_dir())}')
"
```

Verwacht: pad eindigt op `/projects/samenwijzer/oeren`, `Bestaat: True`, submappen = `['aeres_oeren', 'davinci_oeren', 'oer_algemeen', 'rijn_ijssel_oer', 'talland_oeren', 'utrecht_oeren']`.

Faalt? **Stop**. Mogelijke oorzaken: `python-dotenv` niet geïnstalleerd in env (zou wel moeten — staat in `pyproject.toml`), of werkmap is niet `validatie_samenwijzer/`.

- [ ] **Step 4: Streamlit-rooktest voor pagina's die OEREN_PAD gebruiken**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
uv run streamlit run app/main.py --server.port 8503 --server.headless true &
STREAMLIT_PID=$!
sleep 8
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8503
kill $STREAMLIT_PID 2>/dev/null
wait $STREAMLIT_PID 2>/dev/null
```

Verwacht: HTTP 200. Als 200 → app start zonder pad-fouten. Faalt → check Streamlit-logs in stdout.

> **Manuele rooktest** (door gebruiker, niet automatiseerbaar): open na deze stap `http://localhost:8503`, log in, navigeer naar `2_mijn_oer.py` en `5_begeleidingssessie.py`. Een lijst opleidingen moet zichtbaar zijn (komt uit `data/validatie.db`, niet uit oeren-folder direct, maar de OER-context wordt wel daarvandaan gelezen).

- [ ] **Step 5: pytest validatie nog steeds groen**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
uv run pytest -q
```

Verwacht: zelfde aantal passing als baseline-V uit Task 0.

- [ ] **Step 6: Verwijder `validatie_samenwijzer/oeren/`**

```bash
cd /home/eddef/projects/samenwijzer
git rm -r validatie_samenwijzer/oeren/
```

> `git rm -r` verwijdert ook eventueel niet-getrackte cache-bestanden niet — voor de zekerheid daarna:
>
> ```bash
> rm -rf validatie_samenwijzer/oeren/
> ```

- [ ] **Step 7: Verifieer geen oeren-map meer**

```bash
ls validatie_samenwijzer/ | grep oeren && echo "FOUT: oeren bestaat nog" || echo "OK"
```

Verwacht: `OK`.

- [ ] **Step 8: pytest validatie nog steeds groen**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
uv run pytest -q
```

Verwacht: zelfde baseline-V. Als nu rood: rollback met `git restore --staged validatie_samenwijzer/oeren/ && git checkout validatie_samenwijzer/oeren/` en onderzoek.

- [ ] **Step 9: Commit**

```bash
cd /home/eddef/projects/samenwijzer
git add validatie_samenwijzer/.env.example
git commit -m "$(cat <<'EOF'
refactor(validatie): ontdubbel oeren/ via OEREN_PAD=../oeren

Validatie-subproject hergebruikt nu de root-oeren/ map in plaats van
een eigen kopie. Alle code gebruikt al OEREN_PAD-env-var (default
'oeren'); door deze in .env op '../oeren' te zetten valt de duplicatie
weg. Bespaart ~tientallen MB en geeft een single source of truth voor
OER-PDFs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

> `validatie_samenwijzer/.env` zelf is gitignored (zie Task 0 stap 4); gebruiker moet handmatig `OEREN_PAD=../oeren` toevoegen aan zijn lokale `.env` (stap 1). De commit raakt alleen `.env.example` (en de `git rm -r oeren/` uit stap 6 die al staged is).

---

## Task 2: Validatie — `seed/` + `tools/` mergen in `scripts/`

**Files:**
- Move: `validatie_samenwijzer/seed/seed.py` → `validatie_samenwijzer/scripts/seed.py`
- Move: `validatie_samenwijzer/seed/bulk_seed.py` → `validatie_samenwijzer/scripts/seed_bulk.py`
- Move: `validatie_samenwijzer/seed/rebuild_students.py` → `validatie_samenwijzer/scripts/seed_rebuild_students.py`
- Move: `validatie_samenwijzer/tools/rename_oers.py` → `validatie_samenwijzer/scripts/rename_oers.py`
- Move: `validatie_samenwijzer/tools/verwerk_oers.sh` → `validatie_samenwijzer/scripts/verwerk_oers.sh`
- Delete: `validatie_samenwijzer/seed/__init__.py`, `seed/__pycache__/`, `tools/__pycache__/`
- Modify: `validatie_samenwijzer/scripts/rename_oers.py` (docstring-pad)
- Modify: `validatie_samenwijzer/scripts/verwerk_oers.sh` (interne pad-refs)

**Doel:** drie scriptmappen → één.

- [ ] **Step 1: Bevestig dat geen Python-import tussen seed/ en tools/ bestaat**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
grep -rn "from seed\|import seed\|from tools\|import tools" src/ app/ tests/ scripts/ seed/ tools/ 2>/dev/null | grep -v __pycache__
```

Verwacht: lege output. Niet leeg → cross-import bestaat, **stop** en escaleer.

- [ ] **Step 2: Bevestig dat geen `pyproject.toml` `[project.scripts]`-entry naar seed/ of tools/ wijst**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
grep -A 5 "project.scripts" pyproject.toml
```

Verwacht: `ingest = "validatie_samenwijzer.ingest:main"` en `watcher = "validatie_samenwijzer.watcher:main"` — beide naar `src/`-modules. Geen treffers naar `seed.` of `tools.`.

- [ ] **Step 3: Verplaats seed-bestanden met git mv (incl. rename)**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
git mv seed/seed.py scripts/seed.py
git mv seed/bulk_seed.py scripts/seed_bulk.py
git mv seed/rebuild_students.py scripts/seed_rebuild_students.py
```

- [ ] **Step 4: Verplaats tools-bestanden met git mv**

```bash
git mv tools/rename_oers.py scripts/rename_oers.py
git mv tools/verwerk_oers.sh scripts/verwerk_oers.sh
```

- [ ] **Step 5: Verwijder lege seed/ en tools/ mappen**

```bash
git rm seed/__init__.py
rm -rf seed/__pycache__/ tools/__pycache__/
rmdir seed/ tools/
```

> `rmdir` faalt als de map niet leeg is — dat is een goed teken: dan staat er nog iets niet-getrackt in. Onderzoek dat dan eerst.

- [ ] **Step 6: Update interne docstring in `scripts/rename_oers.py`**

Open `validatie_samenwijzer/scripts/rename_oers.py`. Op regel 8 staat:

```
    uv run python tools/rename_oers.py --map talland_oeren
```

Vervang door:

```
    uv run python scripts/rename_oers.py --map talland_oeren
```

- [ ] **Step 7: Update interne pad-refs in `scripts/verwerk_oers.sh`**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
grep -n "tools/\|seed/" scripts/verwerk_oers.sh
```

Voor elke treffer: vervang `tools/` door `scripts/` en `seed/` door `scripts/` (en pas seed-bestandsnamen aan: `bulk_seed.py` → `seed_bulk.py` etc.). Gebruik `Edit` per regel zodat we exacte context hebben.

> Als grep niets oplevert: niets te doen, ga door.

- [ ] **Step 8: Update docstring/help-text in seed-scripts indien zelf-verwijzend**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
grep -n "seed/seed\.py\|seed/bulk_seed\.py\|seed/rebuild_students\.py" scripts/seed*.py
```

Per treffer: pas pad aan naar nieuwe locatie. Geen treffers → niets te doen.

- [ ] **Step 9: Verifieer pytest validatie nog steeds groen**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
uv run pytest -q
```

Verwacht: baseline-V uit Task 0.

- [ ] **Step 10: Functionele rooktest van een seed-script**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
uv run python scripts/seed.py --help 2>&1 | head -5 || \
  uv run python -c "import ast; ast.parse(open('scripts/seed.py').read()); print('parse OK')"
```

Verwacht: geen `ImportError`. Een `--help` of een parse-bevestiging.

> Run `seed.py` zelf **niet** — die schrijft naar `data/validatie.db` en kan testdata overschrijven.

- [ ] **Step 11: Update `validatie_samenwijzer/CLAUDE.md`**

In `validatie_samenwijzer/CLAUDE.md` staan minstens 9 verwijzingen naar `seed/` en `tools/` (regels 30, 43, 44, 47, 48, 91 — zie scope-onderzoek). Open het bestand en vervang systematisch:

| Oud | Nieuw |
|-----|-------|
| `uv run ruff check src/ app/ seed/ tools/` | `uv run ruff check src/ app/ scripts/` |
| `uv run python seed/seed.py` | `uv run python scripts/seed.py` |
| `uv run python seed/bulk_seed.py` | `uv run python scripts/seed_bulk.py` |
| `./tools/verwerk_oers.sh` (en `--preview`) | `./scripts/verwerk_oers.sh` (resp. `--preview`) |
| `tools/rename_oers.py` | `scripts/rename_oers.py` |

Loop het bestand één keer door en check ook `OEREN_PAD=oeren` (regel 58) — wijzig naar `OEREN_PAD=../oeren` zodat de docs in lijn zijn met Task 1.

- [ ] **Step 12: Update `validatie_samenwijzer/README.md`**

Zelfde mapping als stap 11 toepassen op `validatie_samenwijzer/README.md`. Specifiek (uit grep): regels 34, 44, 45, 48, 49.

- [ ] **Step 13: Verifieer geen seed/ of tools/ refs meer in validatie-docs**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
grep -n "seed/\|tools/" CLAUDE.md README.md
```

Verwacht: lege output (of alleen treffers in code-blocks die we expliciet wilden behouden — controleer per regel).

- [ ] **Step 14: pytest validatie + samenwijzer beide groen**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer && uv run pytest -q
cd /home/eddef/projects/samenwijzer && uv run pytest -q
```

Verwacht: baseline-V resp. baseline-N.

- [ ] **Step 15: Commit**

```bash
cd /home/eddef/projects/samenwijzer
git add -A validatie_samenwijzer/
git status   # verifieer wat staged is — alleen scripts/, weg-mv'de seed/ en tools/, en docs
git commit -m "$(cat <<'EOF'
refactor(validatie): merge seed/ en tools/ in scripts/

Validatie heeft nu één scriptmap in plaats van drie. seed-bestanden
krijgen een seed_-prefix om herkomst zichtbaar te houden:
- seed/seed.py             -> scripts/seed.py
- seed/bulk_seed.py        -> scripts/seed_bulk.py
- seed/rebuild_students.py -> scripts/seed_rebuild_students.py
- tools/rename_oers.py     -> scripts/rename_oers.py
- tools/verwerk_oers.sh    -> scripts/verwerk_oers.sh

CLAUDE.md en README.md bijgewerkt; pyproject.toml [project.scripts]
verwijst al naar src/-modules en blijft ongewijzigd.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: docs/ — nieuwe structuur opzetten en bestanden classificeren

**Files:**
- Create: `docs/designs/`, `docs/plans/active/`, `docs/plans/completed/`, `docs/specs/` (lege mappen, met `.gitkeep` indien nodig)
- Move (per bestand classificeren):
  - `docs/design-docs/core-beliefs.md` → `docs/designs/core-beliefs.md`
  - `docs/design-docs/index.md` → `docs/designs/index.md`
  - `docs/exec-plans/completed/fase-1-fundament.md` → `docs/plans/completed/fase-1-fundament.md`
  - `docs/exec-plans/completed/fase-2-whatsapp-signalering.md` → `docs/plans/completed/fase-2-whatsapp-signalering.md`
  - `docs/exec-plans/tech-debt-tracker.md` → `docs/plans/tech-debt-tracker.md`
  - `docs/product-specs/ai-leerondersteuning.md` → `docs/specs/ai-leerondersteuning.md`
  - `docs/product-specs/index.md` → `docs/specs/index.md`
  - `docs/product-specs/new-user-onboarding.md` → `docs/specs/new-user-onboarding.md`
  - `docs/product-specs/outreach-welzijn.md` → `docs/specs/outreach-welzijn.md`
  - `docs/product-specs/studiedata.md` → `docs/specs/studiedata.md`
  - `docs/product-specs/whatsapp-signalering.md` → `docs/specs/whatsapp-signalering.md`
  - `docs/superpowers/plans/2026-04-22-validatie-samenwijzer.md` → `docs/plans/completed/2026-04-22-validatie-samenwijzer.md`
  - `docs/superpowers/plans/2026-05-04-synthetisch-dataset.md` → `docs/plans/completed/2026-05-04-synthetisch-dataset.md`
  - `docs/superpowers/specs/2026-04-22-validatie-samenwijzer-beslissingen.md` → `docs/specs/2026-04-22-validatie-samenwijzer-beslissingen.md`
  - `docs/superpowers/specs/2026-04-22-validatie-samenwijzer-design.md` → `docs/specs/2026-04-22-validatie-samenwijzer-design.md`
  - `docs/superpowers/specs/2026-05-04-synthetisch-dataset-design.md` → `docs/specs/2026-05-04-synthetisch-dataset-design.md`
  - `docs/superpowers/specs/2026-05-06-publieke-oer-citaten-en-pdf-design.md` → `docs/specs/2026-05-06-publieke-oer-citaten-en-pdf-design.md`
  - `docs/superpowers/specs/2026-05-08-folderstructuur-opschoning-design.md` → `docs/specs/2026-05-08-folderstructuur-opschoning-design.md`
  - `docs/superpowers/plans/2026-05-08-folderstructuur-opschoning.md` → `docs/plans/active/2026-05-08-folderstructuur-opschoning.md` (let op: dit is het plan dat zelf wordt uitgevoerd — zie stap 7)
- Delete: `docs/design-docs/`, `docs/exec-plans/`, `docs/product-specs/`, `docs/superpowers/`

**Classificatie-rationale**: `core-beliefs.md` en `index.md` van `design-docs/` zijn ontwerpbeslissingen → `designs/`. De fase-1/2 bestanden waren uitvoeringsplannen die afgerond zijn → `plans/completed/`. Tech-debt-tracker is doorlopend → `plans/` (root). De `product-specs/` zijn allemaal feature-specificaties → `specs/`. De superpowers-plannen 2026-04-22 (validatie) en 2026-05-04 (synthetisch dataset) zijn beide bij de vorige fase afgerond — naar `plans/completed/`. De 5 superpowers-specs zijn allemaal designs/specs → `specs/`.

- [ ] **Step 1: Maak nieuwe mapstructuur**

```bash
cd /home/eddef/projects/samenwijzer
mkdir -p docs/designs docs/plans/active docs/plans/completed docs/specs
```

> Geen `.gitkeep` nodig — we vullen elke map direct met `git mv` uit volgende stappen.

- [ ] **Step 2: Verplaats `design-docs/`-bestanden naar `designs/`**

```bash
cd /home/eddef/projects/samenwijzer
git mv docs/design-docs/core-beliefs.md docs/designs/core-beliefs.md
git mv docs/design-docs/index.md docs/designs/index.md
rmdir docs/design-docs
```

- [ ] **Step 3: Verplaats `exec-plans/`-bestanden naar `plans/`**

```bash
git mv docs/exec-plans/completed/fase-1-fundament.md docs/plans/completed/fase-1-fundament.md
git mv docs/exec-plans/completed/fase-2-whatsapp-signalering.md docs/plans/completed/fase-2-whatsapp-signalering.md
git mv docs/exec-plans/tech-debt-tracker.md docs/plans/tech-debt-tracker.md
rmdir docs/exec-plans/active docs/exec-plans/completed docs/exec-plans
```

- [ ] **Step 4: Verplaats `product-specs/`-bestanden naar `specs/`**

```bash
git mv docs/product-specs/ai-leerondersteuning.md docs/specs/ai-leerondersteuning.md
git mv docs/product-specs/index.md docs/specs/index.md
git mv docs/product-specs/new-user-onboarding.md docs/specs/new-user-onboarding.md
git mv docs/product-specs/outreach-welzijn.md docs/specs/outreach-welzijn.md
git mv docs/product-specs/studiedata.md docs/specs/studiedata.md
git mv docs/product-specs/whatsapp-signalering.md docs/specs/whatsapp-signalering.md
rmdir docs/product-specs
```

- [ ] **Step 5: Verplaats `superpowers/specs/`-bestanden naar `specs/`**

```bash
git mv docs/superpowers/specs/2026-04-22-validatie-samenwijzer-beslissingen.md docs/specs/2026-04-22-validatie-samenwijzer-beslissingen.md
git mv docs/superpowers/specs/2026-04-22-validatie-samenwijzer-design.md docs/specs/2026-04-22-validatie-samenwijzer-design.md
git mv docs/superpowers/specs/2026-05-04-synthetisch-dataset-design.md docs/specs/2026-05-04-synthetisch-dataset-design.md
git mv docs/superpowers/specs/2026-05-06-publieke-oer-citaten-en-pdf-design.md docs/specs/2026-05-06-publieke-oer-citaten-en-pdf-design.md
git mv docs/superpowers/specs/2026-05-08-folderstructuur-opschoning-design.md docs/specs/2026-05-08-folderstructuur-opschoning-design.md
```

- [ ] **Step 6: Verplaats `superpowers/plans/2026-04-22` en `2026-05-04` naar `plans/completed/`**

```bash
git mv docs/superpowers/plans/2026-04-22-validatie-samenwijzer.md docs/plans/completed/2026-04-22-validatie-samenwijzer.md
git mv docs/superpowers/plans/2026-05-04-synthetisch-dataset.md docs/plans/completed/2026-05-04-synthetisch-dataset.md
```

- [ ] **Step 7: Verplaats het lopende plan naar `plans/active/`**

> Dit is het plan dat zelf wordt uitgevoerd. Het verplaatsen tijdens execution is veilig zolang de executor (mens of agent) het pad onthoudt — de skill houdt geen file-handle open na lezen.

```bash
git mv docs/superpowers/plans/2026-05-08-folderstructuur-opschoning.md docs/plans/active/2026-05-08-folderstructuur-opschoning.md
```

- [ ] **Step 8: Ruim lege superpowers/ tree op**

```bash
rmdir docs/superpowers/plans docs/superpowers/specs docs/superpowers
```

- [ ] **Step 9: Verifieer dat alle 6 oude mappen weg zijn en 4 nieuwe staan**

```bash
cd /home/eddef/projects/samenwijzer
ls docs/
```

Verwacht: alleen `designs  plans  specs` (en eventueel `QUALITY_SCORE.md`, `SECURITY.md`, `RELIABILITY.md`, `PRODUCT_SENSE.md`, `FRONTEND.md` — losse markdowns die direct in `docs/` stonden, blijven daar).

```bash
ls docs/plans/
```

Verwacht: `active  completed  tech-debt-tracker.md`.

- [ ] **Step 10: pytest beide projecten groen**

```bash
cd /home/eddef/projects/samenwijzer && uv run pytest -q
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer && uv run pytest -q
```

Verwacht: baseline-N en baseline-V.

> Tests raken docs niet, dus dit is een sanity-check tegen onbedoelde collateral damage.

- [ ] **Step 11: Commit (mappen-move, zonder doc-refs)**

```bash
cd /home/eddef/projects/samenwijzer
git add -A docs/
git commit -m "$(cat <<'EOF'
docs: consolideer 6 sub-mappen naar 3 (designs/, plans/, specs/)

Was:
- docs/design-docs/
- docs/exec-plans/{active,completed}/
- docs/product-specs/
- docs/superpowers/{plans,specs}/

Wordt:
- docs/designs/
- docs/plans/{active,completed}/ + tech-debt-tracker.md
- docs/specs/

Per-bestand classificatie op basis van inhoud (ontwerp vs uitvoering vs
spec), niet blind op originele parent-map. Zie spec
docs/specs/2026-05-08-folderstructuur-opschoning-design.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Update verwijzingen in root-documentatie

**Files:**
- Modify: `CLAUDE.md` (regels 146, 147, 148, 152)
- Modify: `AGENTS.md` (regels 28, 29, 33, 34)
- Modify: `validatie_samenwijzer/CLAUDE.md` (regel 155)
- Modify: `ARCHITECTURE.md` (controleren)
- Modify: `README.md`, `INSTRUCTIONS.md` (controleren)

**Doel:** verwijzingen naar oude doc-paden bijwerken zodat de "Kennisbank"-tabel klopt.

- [ ] **Step 1: Update `CLAUDE.md` Kennisbank-tabel**

In `/home/eddef/projects/samenwijzer/CLAUDE.md` op regels rond 146-152, vervang:

```markdown
| Ontwerpbeslissingen | `docs/design-docs/index.md` |
| Uitvoeringsplannen | `docs/exec-plans/active/`, `docs/exec-plans/completed/` |
| Product specs | `docs/product-specs/index.md` |
```

en

```markdown
| Tech debt | `docs/exec-plans/tech-debt-tracker.md` |
```

door:

```markdown
| Ontwerpbeslissingen | `docs/designs/index.md` |
| Uitvoeringsplannen | `docs/plans/active/`, `docs/plans/completed/` |
| Product specs | `docs/specs/index.md` |
```

en

```markdown
| Tech debt | `docs/plans/tech-debt-tracker.md` |
```

- [ ] **Step 2: Update `AGENTS.md` referenties**

In `/home/eddef/projects/samenwijzer/AGENTS.md` regels 28-34. Wijzig:

| Oud | Nieuw |
|-----|-------|
| `docs/design-docs/index.md` | `docs/designs/index.md` |
| `docs/exec-plans/completed/` | `docs/plans/completed/` |
| `docs/exec-plans/tech-debt-tracker.md` | `docs/plans/tech-debt-tracker.md` |
| `docs/product-specs/index.md` | `docs/specs/index.md` |

- [ ] **Step 3: Update `validatie_samenwijzer/CLAUDE.md` regel 155**

Open `validatie_samenwijzer/CLAUDE.md`. Vervang:

```
Spec: `docs/superpowers/specs/2026-05-06-publieke-oer-citaten-en-pdf-design.md` (vanuit repo-root).
```

door:

```
Spec: `docs/specs/2026-05-06-publieke-oer-citaten-en-pdf-design.md` (vanuit repo-root).
```

- [ ] **Step 4: Scan andere root-markdowns op resterende oude paden**

```bash
cd /home/eddef/projects/samenwijzer
grep -rn "docs/design-docs\|docs/exec-plans\|docs/product-specs\|docs/superpowers" \
  --include='*.md' . 2>/dev/null
```

Verwacht: lege output. Per niet-lege treffer: bewerk dat bestand met dezelfde mapping.

> Treffers binnen `docs/specs/2026-05-08-folderstructuur-opschoning-design.md` zelf (de spec) verwijzen naar de **oude** structuur als historische referentie — daar **niets aanpassen**, anders verlies je de migratie-context. Negeer treffers in dat ene bestand.

- [ ] **Step 5: pytest beide projecten groen**

```bash
cd /home/eddef/projects/samenwijzer && uv run pytest -q
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer && uv run pytest -q
```

- [ ] **Step 6: Commit**

```bash
cd /home/eddef/projects/samenwijzer
git add CLAUDE.md AGENTS.md validatie_samenwijzer/CLAUDE.md
# eventueel meer indien stap 4 treffers gaf
git status   # verifieer staged set
git commit -m "$(cat <<'EOF'
docs: werk verwijzingen bij naar nieuwe docs-structuur

Volgt op de docs-consolidatie (designs/, plans/, specs/). Update
Kennisbank-tabellen in CLAUDE.md en AGENTS.md, en de spec-verwijzing
in validatie_samenwijzer/CLAUDE.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Eindverificatie — runtime-rooktest beide apps

**Files:** geen wijzigingen.

**Doel:** bevestigen dat geen runtime-pad gebroken is door alle migraties samen.

- [ ] **Step 1: pytest groen op beide projecten**

```bash
cd /home/eddef/projects/samenwijzer && uv run pytest -q
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer && uv run pytest -q
```

Verwacht: baseline-N en baseline-V.

- [ ] **Step 2: ruff check groen**

```bash
cd /home/eddef/projects/samenwijzer && uv run ruff check src/ app/ scripts/
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer && uv run ruff check src/ app/ scripts/
```

Verwacht: `All checks passed!` voor beide.

> Validatie's `ruff check` neemt nu `scripts/` mee (was `src/ app/ seed/ tools/`). Als ruff klaagt over stijl in net-gemigreerde scripts: dat zijn pre-existing issues, niet door de migratie veroorzaakt — fix indien klein, anders los track in tech-debt-tracker.md.

- [ ] **Step 3: Streamlit-rooktest samenwijzer**

```bash
cd /home/eddef/projects/samenwijzer
uv run streamlit run app/main.py --server.port 8501 --server.headless true &
PID=$!
sleep 8
curl -s -o /dev/null -w "samenwijzer http=%{http_code}\n" http://localhost:8501
kill $PID 2>/dev/null
wait $PID 2>/dev/null
```

Verwacht: `samenwijzer http=200`.

- [ ] **Step 4: Streamlit-rooktest validatie**

```bash
cd /home/eddef/projects/samenwijzer/validatie_samenwijzer
uv run streamlit run app/main.py --server.port 8503 --server.headless true &
PID=$!
sleep 8
curl -s -o /dev/null -w "validatie http=%{http_code}\n" http://localhost:8503
kill $PID 2>/dev/null
wait $PID 2>/dev/null
```

Verwacht: `validatie http=200`.

- [ ] **Step 5: Manuele rooktest** (door gebruiker)

> Niet automatiseerbaar — Streamlit-pagina's testen in de browser:

1. **Samenwijzer** (`http://localhost:8501`):
   - Login als student (zie `gebruikers.txt`)
   - Open "Mijn voortgang" — moet OER-context tonen → bevestigt `data/02-prepared/oeren.db` werkt
   - Login als docent — open "Groepsoverzicht" → bevestigt `data/01-raw/synthetisch/welzijn.csv` werkt
2. **Validatie** (`http://localhost:8503`):
   - Login (zie `validatie_samenwijzer/gebruikers.txt`)
   - Open "Mijn OER" → bevestigt `OEREN_PAD=../oeren` werkt voor PDF-citaten
   - Open "Begeleidingssessie" → idem
3. Stuur **één AI-call** in elk project (een chatvraag) → bevestigt `ANTHROPIC_API_KEY` en pad-onafhankelijke modules werken.

- [ ] **Step 6: Verplaats het uitgevoerde plan naar `plans/completed/`**

```bash
cd /home/eddef/projects/samenwijzer
git mv docs/plans/active/2026-05-08-folderstructuur-opschoning.md \
       docs/plans/completed/2026-05-08-folderstructuur-opschoning.md
git commit -m "$(cat <<'EOF'
docs(plans): markeer folderstructuur-opschoning als completed

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 7: Eind-overzicht voor gebruiker**

Print de nieuwe top-level structuur van beide projecten:

```bash
cd /home/eddef/projects/samenwijzer
echo "=== samenwijzer/ ==="
ls -d */ 2>/dev/null | grep -v -E "^(\.|node_modules|__pycache__|htmlcov)"
echo "=== docs/ ==="
ls docs/
echo "=== validatie_samenwijzer/ ==="
ls -d validatie_samenwijzer/*/ 2>/dev/null | grep -v -E "(__pycache__|.venv|.uv_cache)"
```

Verwacht (samenwijzer top): `app/ data/ docs/ oeren/ scripts/ src/ tests/ validatie_samenwijzer/`.
Verwacht (docs): `designs/ plans/ specs/` (+ losse markdowns).
Verwacht (validatie top): `app/ data/ scripts/ src/ tests/`.

---

## Acceptatiecriteria (uit spec, hier als checklist)

- [ ] `validatie_samenwijzer/` heeft 5 top-level mappen (`app`, `data`, `scripts`, `src`, `tests`)
- [ ] `docs/` heeft 3 sub-mappen (`designs`, `plans`, `specs`); `superpowers/` bestaat niet meer
- [ ] Eén `oeren/`-map (in root); validatie-tests/-pagina's werken via `OEREN_PAD`
- [ ] `uv run pytest` groen in beide projecten (baseline-N, baseline-V)
- [ ] Streamlit-apps openen op poort 8501 en 8503 zonder pad-fouten
- [ ] Geen wijziging aan source-paden in `data/01-raw|02-prepared|03-output/`

## Rollback-procedure

Als ergens een taak rood wordt en niet eenvoudig te fixen:

```bash
cd /home/eddef/projects/samenwijzer
git log --oneline -10                    # zie laatste commits
git reset --hard <baseline-commit>       # rollback naar vóór deze migratie
# in validatie/.env: OEREN_PAD-regel handmatig terugverwijderen indien gewenst
```

> `git reset --hard` is destructief — gebruiker moet expliciet akkoord geven.
