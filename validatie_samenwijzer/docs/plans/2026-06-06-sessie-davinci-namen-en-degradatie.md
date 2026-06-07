# Sessie-log 2026-06-06 — Deltion-merge, Da Vinci-opleidingsnamen, degradatie-plan

*Subproject: `validatie_samenwijzer` ("De digitale gids"). Werk uitgevoerd 2026-06-06 (deploy/verificatie liep door tot 06-07).*

## Scope

Drie zaken aangepakt: (1) de openstaande Deltion-instelling afronden, (2) twee gebruikersmeldingen
onderzoeken+fixen (Graafschap geen OER, Da Vinci toont getallen), (3) een plan maken voor graceful
degradation via webzoeken.

## 1. Deltion College afgerond (PR #161)

De vorige sessie had Deltion inhoudelijk klaar maar niet geïntegreerd. Status bij aanvang: branch
`worktree-deltion-instelling`, CI groen, mergeable, niet gemerged.

- **PR #161 squash-gemerged** naar `main`; worktree + branch opgeruimd.
- 162 OER-`.md` stonden al op Box (dry-run push = 0 transfers).
- Open teambesluit (genoteerd, geen actie): Deltions OER's bleken publiek opvraagbaar via de
  SQill-API, wat de "Box-only wegens rechten"-aanname nuanceert. `.gitignore` ongewijzigd gelaten.

## 2a. Graafschap — geen bug, ontbrekende bron

Onderzocht: Graafschap staat niet in de DB, niet in de drie hardcoded instelling-lijsten, en er
bestaan **nergens** Graafschap-OER-studiegidsen — Box heeft alleen twee instellingsbronnen
(`gedragscode.pdf`, `studentenstatuut.pdf`), niet scrapebaar, geen fetch-script. Conclusie: niet
fixbaar met code; de blokkerende stap is het verkrijgen van minstens één studiegids-PDF. Recept ligt
klaar (3 lijsten → ingest → sync_afgeleid → Box-push → seed). De gebruiker bevestigde dat hij zich
vergiste over reeds-ontvangen Graafschap-OER's. Afgesloten.

## 2b. Da Vinci-opleidingsnamen (PR #162, gedeployd)

**Melding**: Da Vinci toont "Opleiding 25xxx" i.p.v. een leesbare naam; vermoeden OCR.

**Root cause (géén OCR)**: de PDF-tekst wordt prima gelezen. 18 van de 68 records hadden een kale
bestandsnaam (`25882BOL2025Examenplan.pdf`) zonder naam, terwijl de naam wél op de titelpagina staat
(`Examenplan Mediaredactiemedewerker vanaf cohort 2023 – Crebo 25882`). De bestaande PDF-fallback
matchte alleen het ROC Utrecht-format. De ~50 records mét naam in de stem toonden al schoon (de UI
liep al door `schoon_opleiding_naam`); het zichtbare probleem waren puur die 18.

**Fix** (zie ook CLAUDE.md → "Opleidingsnaam-afleiding"):
- `ingest._OPLEIDING_LIJN_DAVINCI` + uitgebreide `_extraheer_opleiding_uit_pdf` (3 Da Vinci-
  titelpagina-formaten) — future-proof voor nieuwe ingests.
- `scripts/fix_opleiding_namen.py` — heelt bestaande DB-records: pass 1 eigen bestand
  (sibling-bestandsnaam óf titelpagina, gekozen op kwaliteit = meeste natuurlijke woorden), pass 2
  crebo-leen van een ander record met dezelfde crebo. Idempotent, `--dry-run`. Davinci: **18→0**
  zichtbaar naamloos (aeres heeft nog 1 addendum dat terecht overblijft).
- `opleiding.py` (nieuw) — `schoon_opleiding_naam` verplaatst uit `styles.py` (UI-laag) naar een
  streamlit-loze module; `styles.py` re-exporteert.
- `chat.py` — schoont de opleidingsnaam op de injectie-boundary zodat het model een leesbare naam
  in de system-prompt ziet i.p.v. de ruwe stem (fixt álle instellingen).

**Verificatie**: ruff schoon; 160 tests groen (+9: Da Vinci-titelregex op echte titelregels,
chat-injectie-cleaning). UI-smoke-test (student 100301, crebo 25882): hero toont
"Mediaredactiemedewerker"; chat antwoordt met correcte citatie en noemt de schone naam. CI groen →
gemerged. **Fly-deploy** geslaagd en **live geverifieerd** op https://digitale-gids.fly.dev.

**Bewuste restpunten**: een handvol crebo-leen-namen is licht imperfect (bv. 25119
"…Uitstroomprofiel", 25779 niet volledig) door rommelige cross-instelling brondata. Perfecte
curatie vergt een s-bb crebo→naam-register — buiten scope van deze bugfix.

## 3. Plan graceful degradation (PR #162)

`docs/plans/2026-06-06-graceful-degradation-webzoeken.md`: webzoeken op de instellings-website via
Anthropic's server-side web search-tool (gescoped per domein via `allowed_domains`), altijd
beschikbaar maar alleen ingezet als de geladen bronnen tekortschieten, met verplichte
waarschuwingsbalk + aparte citatieformat zodat de juridische OER-citatieplicht intact blijft.
Gefaseerd; nog niet geïmplementeerd; 5 open keuzes voor team (scope publiek/login, domeinverificatie,
welke onderwerpen, AVG, kosten-plafond/feature-flag).

## Open follow-ups

- **Graceful degradation** implementeren zodra het team de open keuzes maakt.
- **Graafschap** onboarden zodra er een studiegids-PDF beschikbaar is.
- **Opleidingsnaam-curatie** (optioneel): s-bb crebo→naam-register als autoritatieve bron voor de
  paar imperfecte crebo-leen-namen.
- **Teambesluit** Deltion Box-only vs publiek (OER's bleken publiek opvraagbaar).
