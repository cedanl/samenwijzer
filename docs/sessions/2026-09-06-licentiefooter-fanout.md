# Sessie 2026-09-06 — licentiefooter live + fan-out over de open punten (3 subagents)

Uitgangspunt: PR #250 (CC BY-SA 4.0-licentiefooter digitale gids) stond klaar; handoff van
2026-09-04 had drie open punten. Werkwijze: `/ship` voor #250 met zichtbare smoke vóór de merge,
daarna fan-out: één subagent per onafhankelijk punt (2× sonnet in eigen worktree, 1× opus in eigen
worktree; de docs-agent in de hoofd-checkout omdat de wijzigingen daar in de working tree stonden),
alle merges centraal na zichtbare smoke-output of expliciete "geen UI-surface"-rechtvaardiging.

## Gemerged (4 PRs)

| PR | Wat | Verificatie |
|---|---|---|
| #250 | `_licentie.html`-include op alle pagina's van de digitale gids (`base.html`, `index.html`, `login.html`, `toegang.html`) + `.licentie`/`.appfooter`-CSS | pytest 283; chrome-devtools op 127.0.0.1:8504: `/toegang`, `/`, `/login`, `/student` desktop + 390×844 (emulate), geen horizontale overflow |
| #251 | `npm audit fix` presentatie: js-yaml 4.3.2 + 3.15.2, dompurify 3.4.15, nanoid 3.3.18; `@slidev/cli` blijft 52.14.1; alleen lockfile | `slidev build` exit 0; resterend: image-size via pptxgenjs (vereist cli-bump → bewust open, zie #203) |
| #252 | CLAUDE.md-opschoning (root + validatie), stuurgroepdeck 11-9 + `theme-datacoalitie` + assets, Slidev 52.14 goto-dialog-CSS-fix, sessielog 2026-06-25 + uitleg-html; `*.pptx` genegeerd (export, 6 MB) | pytest 283; `slidev build 260911_samenwijzer_stuurgroep.md` exit 0 |
| #253 | Hoofd-app: mobiele nav (`.sw-nav` 620–645 px in 375 px, `overflow-x:auto`) → `@media ≤768px` sticky + `flex-wrap`; vega-svg's (440/492 px) → `max-width:100%`; vega-runtime 5.33.1 → `vega@6.4.0` + `vega-lite@6.4.3` + `vega-embed@7.2.0` (Altair 6 spec v6); template-test op de pins | ruff/format/ty groen, pytest 508 (506 + 2); Playwright 11 pagina's × rollen op 390: docSW ≤ innerWidth, nav SW==CW; console 0 warnings; spot-check hoofdagent `/home`, `/groep` 390 + `/groep` 1280 |

Deploy `digitale-gids` v30 (machine 784436dfe52de8, ams) — live geverifieerd: footer op `/toegang`,
`/`, `/login` (desktop + 390 mobiel) en `/student` (desktop, ingelogd als 100601).

## Lessen

- `pkill -f "uvicorn …"` in hetzelfde Bash-commando als de start matcht de eigen shell (exit 144);
  poort-check via `ss -ltnp` vooraf en `fuser -k <poort>/tcp` achteraf.
- chrome-devtools `resize_page` clampt op ~500 px vensterbreedte; echte 390 px alleen via
  `emulate viewport "390x844x3,mobile,touch"`.
- `scrollIntoView` direct na navigatie scrolt soms niet; `window.scrollTo(0, scrollHeight)` + korte
  wacht is betrouwbaar voor footer-checks.
- Een stale hoofd-app-cookie op `localhost:8505` (SESSION_SECRET=dev-secret) logt je stil in als
  eerdere testgebruiker; parallelle browser-smokes: orchestrator op `127.0.0.1`, agent op `localhost`.
- Agent-worktree blijft `locked` na afronden van de agent; `git worktree unlock` + `remove --force`.
- Playwright-MCP schrijft artefacten in de server-cwd (`validatie_samenwijzer/.playwright-mcp/`), niet
  in de agent-worktree — na afloop opruimen.

## Open

- Streamlit `app/` verwijderen: scope-besluit, niet in deze sessie gedaan.
- Hoofd-app loginpagina: `.sw-login__ti` erft donkere tekstkleur op het donkere studentpaneel
  (pre-existing, ook desktop) → kop "Hoe sta jij ervoor?" vrijwel onleesbaar.
- Hoofd-app `/groeidossier`: Plotly-charts (`responsive: true`) niet empirisch op 390 px gecheckt
  (testaccounts hebben geen zelfbeoordelingen).
- #203 blijft open (image-size high via pptxgenjs vereist `@slidev/cli`-bump voorbij de pin).
- Losse worktree `../samenwijzer-goedkoper` (branch `feat/goedkoper-model`, op 390e6fe) uit een
  andere sessie — niet aangeraakt.
