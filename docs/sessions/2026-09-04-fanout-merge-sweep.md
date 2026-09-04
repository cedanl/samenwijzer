# Sessie 2026-09-04 — parallelle merge-sweep (4 sonnet-subagents)

Uitgangspunt: PR #228 (FastAPI-frontend hoofd-app) al 2 maanden open met uncommitted werk,
10 Dependabot-PRs, 3 follow-ups uit PR #243 (digitale gids). Opgezet als fan-out: één
subagent per onafhankelijk domein, elk in een eigen worktree (hoofd-checkout onaangeraakt),
alle merges door de hoofdagent na zichtbare smoke-output.

## Gemerged (13 PRs)

| PR | Wat | Verificatie |
|---|---|---|
| #228 | FastAPI-frontend hoofd-app (`app_fastapi/`, poort 8505); `graphifyy` als per-ongeluk-runtime-dep verwijderd | 506 tests, ruff/ty clean, `_smoke_fastapi.py` 9/9, browser `/groep` + `/welzijn` desktop+mobiel |
| #247 | Kies-beurt telt mee in `chat_history` (`s.voeg_beurt_toe(vraag, "")` in kies-branch) | 282 tests (echte validatie.db: tandartsassistent → "in Nijmegen" → crebo 25699), Playwright-smoke |
| #248 | Cache-busting `static_url()` (?v=mtime, eenmalig bij opstart), dode `.picker`-CSS weg, ✕ sluit overlay niet-destructief | 282 tests, Playwright: assets 200 met `?v=`, overlay-state behouden, mobiel ok |
| #239 #233 | cryptography 50 / pillow 12.3 (validatie) | 277 passed (oudere basis), ruff clean |
| #245 #236 #246 #241 | postcss-selector-parser / postcss / browserslist / mermaid (presentatie) | `npm ci` + `slidev build` ✓, cli-pin 52.14.1 intact; #241 na `@dependabot rebase` |
| #244 #242 #240 #238 #232 | tornado / gitpython / cryptography 50 / aiohttp / pillow (root) | elk lokaal gemerged met main → 506 passed |

Deploy `digitale-gids` v29 (machine 784436dfe52de8, ams) — live geverifieerd: cache-bust-assets 200,
kies-scenario resolveert naar ROC Nijmegen met citaat, ✕ behoudt gesprek, mobiel 390×844 ok.

## Lessen

- Root-Dependabot-PRs stonden op een stale basis (vóór #228) terwijl GitHub `CLEAN` meldde;
  GitHub kijkt alleen naar tekstconflicten. Lokaal `git merge origin/main` + pytest is de echte check.
- `oeren/` is deels git-tracked: `cp -al oeren <wt>/oeren` op een worktree maakt `oeren/oeren/`.
  Alleen de gitignored instellingsmappen (davinci, kwic, graafschap, deltion, landstede) los hardlinken.
- Twee lokale FastAPI-apps op `localhost` (verschillende poorten) delen de sessie-cookie; parallelle
  browser-smokes via `127.0.0.1` vs `localhost` scheiden.
- `gh pr merge --delete-branch` faalt op de lokale delete als de branch in een worktree uitgecheckt
  is; de merge zelf slaagt wel.

## Open

- #203 (esbuild + `@slidev/cli` ≥52.15.2) bewust open: breekt de nested-repo-pin (52.14.1).
- Hoofd-app: mobiele nav scrollt horizontaal binnen de header (`/groep`); vega-lite-warn (spec v6 op
  runtime v5.33.1). Streamlit (`app/`) nog niet verwijderd.
- Digitale gids: `opties`-payload in `/api/vraag` is nog in gebruik door `test_intake_vervolg.py`
  (niet dood); monotone accumulatie (instelling blijft filteren) ongewijzigd.
- `validatie_samenwijzer/docs/sessions/2026-06-25-bronactualiteit-3b-3c.md` + 2 png's en
  `docs/uitleg-digitale-gids.html` staan nog untracked in de hoofd-checkout.

Ed de Feber, in nauwe samenwerking met Claude
