# Runbook: Fase 2 — niet-publieke OER's uit de git-historie purgen

**Status:** klaar om uit te voeren — **gecoördineerde teamactie, niet solo draaien**
**Datum:** 2026-06-04
**Aanleiding:** Fase 1 (PR #143) haalde de OER's van Da Vinci, KWIC, Graafschap en Deltion uit de
git-**tip** + gitignore. Op een **publieke** repo blijven die bestanden echter via oude commits
downloadbaar. Pas ná deze history-purge is de richtlijn "niet publiek beschikbaar, alleen via de
app" écht vervuld. Onderbouwing: `2026-06-04-opslagstrategie-data-en-deployment.md`.

> ⚠️ **Onomkeerbaar en verstorend.** Deze procedure herschrijft de volledige git-historie en
> vereist een **force-push op een publieke repo**. Alle bestaande clones en open PR's breken;
> iedereen moet opnieuw klonen. Lees dit document volledig en stem af met het team vóór stap 5.

---

## 1. Doel & scope

Verwijder **alle historische versies** van deze vier mappen uit `cedanl/samenwijzer`, op elke
branch en in elke commit:

```
oeren/davinci_oeren/
oeren/kwic_oeren/
oeren/graafschap_oeren/
oeren/deltion_oeren/
```

Buiten scope: alle overige instellingen (publiek), de code, en de afgeleide data
(`data/skills/`, KD's staan al niet in git).

---

## 2. Definition of done

- `git log --all --oneline -- oeren/davinci_oeren oeren/kwic_oeren oeren/graafschap_oeren oeren/deltion_oeren`
  geeft **nul** resultaten in de herschreven repo.
- `origin/main` (en alle branches) bevatten de mappen niet meer, in geen enkele commit.
- Repo-grootte op GitHub significant gedaald (was ~435 MB).
- GitHub Support heeft bevestigd dat cached views/unreachable commits zijn opgeruimd; forks zijn
  geadresseerd.
- Het team draait allemaal op een **verse clone**.

---

## 3. Overweeg eerst het alternatief

Als deze documenten principieel **nooit** publiek mogen staan en het risico op herhaling reëel is,
weeg dan af of de repo **privaat** moet worden i.p.v. publiek-met-purge. Purge + gitignore is de
juiste weg **als** de repo bewust publiek moet blijven (open CEDA-code). Die afweging hoort bij de
projectleiding, niet in dit runbook — maar maak hem expliciet vóór je gaat herschrijven.

---

## 4. Preconditions — afvinken vóór stap 5

- [ ] **Fase 1 (PR #143) is gemerged** in `main`.
- [ ] **Box is compleet.** Draai `./scripts/push_oeren.sh` en verifieer dat de vier mappen op
      `box:samenwijzer/oeren` staan. Dit is het enige vangnet tegen dataverlies.
- [ ] **Lokale kopie geborgd.** Bevestig dat de vier mappen nog fysiek op schijf staan
      (`find oeren/{davinci,kwic,graafschap,deltion}_oer* -type f | wc -l`).
- [ ] **Open PR's afgehandeld.** Merge of sluit alles wat openstaat — een history-rewrite
      invalideert de base/head-SHA's. Ten tijde van schrijven open: #142, #143, #139 (dependabot).
- [ ] **Merge-freeze afgesproken.** Geen nieuwe commits/PR's tijdens de operatie; communiceer een
      tijdvenster naar alle committers.
- [ ] **Admin-toegang geregeld** voor het tijdelijk versoepelen van branch-protection op `main`.
- [ ] **`git filter-repo` geïnstalleerd** (`pipx install git-filter-repo` of `uv tool install
      git-filter-repo`; niet de losse `git filter-branch` — die is traag en foutgevoelig).

---

## 5. Procedure

### 5.1 Volledige back-up (mirror)

Maak een complete spiegel die je **niet** aanraakt; dit is je rollback.

```bash
git clone --mirror git@github.com:cedanl/samenwijzer.git samenwijzer-backup.git
# Bewaar samenwijzer-backup.git buiten de werkmap (en idealiter offline).
```

### 5.2 Verse werk-clone

`git filter-repo` draait het veiligst op een schone, net geklonede repo.

```bash
git clone git@github.com:cedanl/samenwijzer.git samenwijzer-purge
cd samenwijzer-purge
```

### 5.3 Pre-flight: bevestig dat de paden kloppen

```bash
git log --all --oneline -- oeren/davinci_oeren oeren/kwic_oeren oeren/graafschap_oeren oeren/deltion_oeren | head
# Verwacht: meerdere historische commits. Nul = paden kloppen niet, STOP en controleer.
```

### 5.4 De purge draaien

`filter-repo` herschrijft **alle** branches en tags in deze clone.

```bash
git filter-repo \
  --invert-paths \
  --path oeren/davinci_oeren/ \
  --path oeren/kwic_oeren/ \
  --path oeren/graafschap_oeren/ \
  --path oeren/deltion_oeren/
```

> `filter-repo` verwijdert bewust de `origin`-remote na de rewrite (veiligheidsmaatregel tegen
> per ongeluk pushen). Dat is verwacht gedrag.

### 5.5 Lokaal verifiëren (vóór je iets pusht)

```bash
git log --all --oneline -- oeren/davinci_oeren oeren/kwic_oeren oeren/graafschap_oeren oeren/deltion_oeren
# MOET leeg zijn. Zo niet: niet pushen, onderzoek de paden.
du -sh .git   # moet fors kleiner zijn dan de ~931 MB van vóór
```

### 5.6 Branch-protection tijdelijk versoepelen

In GitHub → Settings → Branches → `main`: sta force-push tijdelijk toe (of schakel de regel even
uit). Noteer de oorspronkelijke instellingen zodat je ze exact kunt herstellen (stap 5.9).

### 5.7 Force-push naar GitHub

```bash
git remote add origin git@github.com:cedanl/samenwijzer.git
git push origin --force --all
git push origin --force --tags
```

> Pushed dit alle branches die je wilt behouden? `filter-repo` herschreef alle lokale branches uit
> de verse clone. Branches die alleen remote bestonden en niet meegekomen zijn (bv. afgesloten
> dependabot-branches) kun je los afhandelen of laten verlopen.

### 5.8 GitHub-caches, unreachable commits en forks

Een force-push verwijdert de data **niet** direct van GitHub:

- Oude commits blijven een tijd bereikbaar **via hun SHA** tot GitHub garbage-collect draait.
- **Forks** houden hun eigen kopie.
- Cached diff-/blob-views kunnen blijven hangen.

Acties:

1. Open een ticket bij **GitHub Support** ("Removing sensitive data from a repository"): vraag om
   het opruimen van unreachable objects/cached views en om verwijdering van forks die de data nog
   bevatten.
2. Inventariseer forks (repo → Insights → Forks) en adresseer ze.
3. Pas als Support bevestigt is de data feitelijk weg. Tot dan: behandel als nog-blootgesteld.

### 5.9 Branch-protection herstellen

Zet de branch-protection op `main` exact terug zoals genoteerd in stap 5.6.

### 5.10 Team laten herklonen

Stuur een duidelijke instructie naar alle committers:

> De historie van `cedanl/samenwijzer` is herschreven. **Verwijder je lokale clone en kloon
> opnieuw.** `git pull` op een oude clone herintroduceert de verwijderde bestanden — niet doen.

Wie lokaal werk had: laat ze een patch/bundle van hun branch maken vóór ze verwijderen, en daarna
rebasen op de nieuwe historie.

---

## 6. Nazorg

- [ ] Werk de doc-claims bij die nog zeggen dat de hele `oeren/`-tree getrackt is en dat een verse
      clone de volledige tree bevat (in `validatie_samenwijzer/CLAUDE.md` en de hoofd-`CLAUDE.md`:
      de multi-machine-tabel en de "fresh clone bevat de oeren-tree"-zin). Carve de vier
      niet-publieke instellingen daar uit.
- [ ] Bevestig dat `bootstrap.sh` / `sync_oeren.sh` de vier instellingen nog uit Box halen voor wie
      Box-toegang heeft (gitignore blokkeert alleen git, niet de rclone-sync).
- [ ] Documenteer in het beslisdocument dat Fase 2 is uitgevoerd (datum + door wie).

---

## 7. Rollback / abort

- **Vóór de force-push (stap 5.7):** gewoon de werk-clone weggooien. Er is niets aan GitHub
  veranderd.
- **Na de force-push:** herstel vanuit de mirror uit stap 5.1:
  ```bash
  cd samenwijzer-backup.git
  git push --mirror git@github.com:cedanl/samenwijzer.git
  ```
  Let op: dit zet álle refs terug zoals ze waren, inclusief de verwijderde bestanden. Gebruik alleen
  als de purge moet worden teruggedraaid.

---

## 8. Gotcha's

- **Alle commit-SHA's veranderen.** Links naar commits in issues, PR-omschrijvingen of docs worden
  ongeldig. Inventariseer waar dat pijn doet.
- **Geen `git pull` op oude clones** — herintroduceert de data. Alleen verse clones.
- **Signed commits / verификatie** gaan verloren bij rewrite (niet van toepassing hier, maar weet
  het).
- **CI/Actions** draaien opnieuw op de herschreven branches; verwacht een golf van runs.
- **filter-repo is niet idempotent t.o.v. remote** — draai de purge één keer op een verse clone,
  niet herhaald op een al-gepushte repo.
