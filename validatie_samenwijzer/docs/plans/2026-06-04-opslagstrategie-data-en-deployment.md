# Beslisdocument: opslagstrategie data & deployment

**Status:** ter besluitvorming — analyse + advies, wacht op team-/projectleiding-besluit
**Datum:** 2026-06-04
**Aanleiding:** Vóór de geplande deployment van de app is de vraag opgekomen of we de data niet
**alleen via Box** moeten opslaan in plaats van (zoals nu) óók in de git-repo, met Box als backup.
Dit document legt de analyse, de afweging en het advies vast zodat het team erop kan reageren.

---

## 1. Kernboodschap

"Alleen Box" bundelt twee instincten — één goed, één riskant:

- ✅ **Goed:** de grote binaries (413 MB OER-PDF's) horen niet in een **publieke** git-historie.
- ❌ **Riskant:** Box als bron voor de *draaiende, gedeployde* app.

**Advies:** haal de zware PDF's uit git, maar maak Box **niet** je runtime-backend. Splits drie
dingen die nu door elkaar lopen: (a) data-distributie naar dev-machines, (b) runtime-data voor de
gedeployde app, (c) backup/archief. En behandel het **rechtenvraagstuk** (§5) als een apart,
urgenter spoor dat losstaat van opslag.

---

## 2. Feitelijke nulmeting (2026-06-04)

| Gegeven | Waarde |
|---|---|
| Repo `cedanl/samenwijzer` zichtbaarheid | **PUBLIC** |
| Repo-grootte op GitHub | ~435 MB |
| Lokale `.git` | ~931 MB (history-bloat door binaire churn) |
| `oeren/` totaal | 454 MB, 1875 getrackte bestanden |
| — `oeren/*.pdf` | **413,3 MB** over 775 bestanden |
| — `oeren/*.md` (markitdown) | **24,6 MB** over 781 bestanden |
| `data/skills/*.json` | 3 MB, 332 bestanden (in git, bewust) |
| `kwalificatiedossiers/` | 229 MB, 309 PDF's — **gitignored, Box-only** |
| `validatie.db` | gitignored, per machine via `ingest` opgebouwd |
| LICENSE | **MIT** |
| Git LFS | niet in gebruik |
| Deploy-artefacten | alleen `.devcontainer/Dockerfile`; nog geen app-Dockerfile/fly.toml |

De app leest OER-tekst **van schijf bij elke chat** (`chat.laad_oer_tekst()`, voorkeur `<stem>.md`,
fallback PDF). De bestanden moeten dus lokaal bij de runtime staan.

---

## 3. Het echte vraagstuk: runtime ≠ backup

De framing "repo óf Box" verbergt de kernvraag. Bij deployment is de vraag niet *"waar back-uppen
we"* maar *"waar leest de draaiende app uit"*. Het antwoord is **geen van beide**: de runtime hoort
te lezen uit het **lokale deploy-artefact** (image of gemount volume); de canonieke store wordt
opgehaald op **build-/deploytijd**, niet per request.

**Box-at-runtime sluiten we actief uit.** Dat zou productie laten afhangen van rclone + Box-OAuth-
refresh-tokens + een persoonlijk/team-account zónder SLA. De `CLAUDE.md` waarschuwt al dat
interactief-geauthenticeerde diensten in headless runs kunnen ontbreken — precies een prod-app.
Box blijft prima als **menselijke bron/backup voor het team**, niet als live datalaag.

---

## 4. Afweging van opties (gerangschikt voor onze schaal)

~700 MB read-mostly referentiedata, klein team, deploy waarschijnlijk op Fly (zoals andere
CEDA-apps). Dan is de pragmatisch-robuuste keuze simpeler dan object-storage.

| # | Aanpak | Beoordeling |
|---|---|---|
| **1 (advies)** | Corpus **in het image bakken** óf eenmalig op een **Fly-volume seeden**, daar `ingest` draaien → immutable artefact, **nul runtime-data-afhankelijkheid** | Simpelst robuust, reproduceerbaar, geen externe SLA |
| 2 | **Object storage** (Cloudflare R2 / MinIO / S3), app synct bij deploy | "Correcter op schaal", maar zwaarder op te zetten — nu overkill |
| 3 | **Box als runtime-bron** | **Afgeraden** (zie §3) |

Data-distributie naar dev-machines (git/Box) en runtime-distributie (image/volume) zijn aparte
dingen — los ze apart op.

---

## 5. Apart en urgenter spoor: rechten (staat los van deployment)

Dit speelt **nu**, onafhankelijk van de opslagkeuze:

- De repo is **publiek** en de **LICENSE is MIT**. Daarmee verleent het project iedereen vrij
  hergebruik/herdistributie van **alles** in de repo — inclusief 775 institutionele OER-PDF's
  waarvan cedanl niet de auteursrechthebbende is. cedanl kan andermans documenten niet onder MIT
  licenseren.
- Volgens projectkennis publiceren **Da Vinci en KWIC** hun OER's niet zelf openbaar. In de publieke
  tree staan nu **131 Da Vinci-PDF's en 7 KWIC-PDF's** — een levende blootstelling, geen toekomstig
  risico. (Curio/Deltion/Graafschap e.a. vergen aparte verificatie.)
- De huidige indeling is **rechten-omgekeerd**: de KD's (landelijke S-BB-documenten, juist het
  *veiliger* te herdistribueren materiaal) zijn Box-only/gitignored, terwijl de OER's
  (instelling-specifiek, risicovoller) publiek in git staan. Dat toont dat de huidige opzet niet door
  rechten gedreven is.

**Actie:** leg bij de projectleiding voor — is er per instelling toestemming voor publieke
herdistributie, en klopt MIT voor deze data? Dit pleit, los van deployment, al voor het uit de
publieke repo halen van (in elk geval) de niet-publicerende instellingen.

---

## 6. History-purge: een te plannen kostenpost

`git rm --cached` haalt de PDF's uit de werkende tree maar **niet uit de historie** — de publieke
repo blijft ~435 MB en de PDF's blijven downloadbaar via oude commits. Echt verwijderen =
`git filter-repo`/BFG + **force-push op een publieke repo** → kapotte clones voor iedereen,
kapotte PR-refs. De `CLAUDE.md` markeert dit terecht als "een apart teambesluit". Pas uitvoeren
**ná** de rechten-check, als bewuste actie — niet als losse stap.

---

## 7. Aanbevolen volgorde

1. **Nu (rechten):** MIT-vs-institutionele-PDF's en de Da Vinci/KWIC-blootstelling voorleggen aan de
   projectleiding. Meest tijdgevoelig.
2. **Korte termijn:** `oeren/*.pdf` op gitignore + borgen dat ze compleet op Box staan (is al zo);
   `*.md` (24,6 MB) in git houden — dat is de chat-input en blijft reproduceerbaar. Repo-tree wordt
   direct ~95% lichter voor nieuwe commits.
3. **Bij deployment:** PDF's (+ KD's) in het image bakken of een volume seeden bij build/deploy;
   **geen** Box-call op runtime.
4. **Team-besluit, gepland:** history-purge met `git filter-repo` zodra rechten helder zijn.

---

## 8. Open vragen (in te vullen door team)

- **Deploy-doel:** Fly-volume, container-image of k8s? Dit bepaalt of stap 3 "in image bakken" of
  "volume seeden" wordt.
- **Toestemming per instelling** voor publieke herdistributie van OER-PDF's; en of MIT de juiste
  licentie is voor de data (versus alleen voor de code).
- **Scope van de purge:** alle OER-PDF's uit git, of alleen die van niet-publicerende instellingen?

---

## 9. Wat expliciet niet verandert

- `data/skills/*.json` (3 MB tekst) blijft in git — klein, open-license, reproduceerbaarheid.
- `validatie.db` blijft gegenereerd per machine.
- `kwalificatiedossiers/` blijft Box-only/gitignored.
- Box blijft de team-backup/handoff-store — alleen niet de runtime-bron.
