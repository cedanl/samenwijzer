# Haalbaarheid: validatie_samenwijzer deployen op Fly.io

**Status:** onderzoek afgerond — Fly is haalbaar; wacht op go/no-go vóór uitvoering
**Datum:** 2026-06-04
**Aanleiding:** De app moet straks ergens draaien. Onderzocht is of **Fly.io** een optie is, mét
de harde randvoorwaarde dat de **bestaande Fly-app `ceda-regiobijeenkomst` volledig ongemoeid blijft**.

> ⚠️ **Nog niets gedeployed.** Dit document is puur onderzoek. Er zijn alleen **read-only** flyctl-
> commando's gedraaid (`apps list`, `status`, `volumes list`). Geen `deploy`, `launch`, `scale`,
> `secrets`, `restart`, `destroy` of `ssh`.

---

## 1. Conclusie

**Ja, Fly is een goede optie** — en bovendien een *simpele*, omdat de app zich uitstekend leent voor
een immutable image zonder runtime-data-afhankelijkheid.

---

## 2. Bevindingen die het simpel maken

| Bevinding | Gevolg voor deploy |
|---|---|
| `app/` doet **geen** INSERT/UPDATE/DELETE/commit — read-only tegen `validatie.db` | Geen Fly-**volume** nodig; DB read-only in het image, ephemeral |
| Runtime leest **`.md`** (markitdown-output, al op schijf); PDF alleen voor "bekijk/download" | Geen markitdown/Tesseract/OCR in het runtime-image (build/ingest-tijd) |
| `ANTHROPIC_API_KEY` via `os.environ` (`_ai._client`) | Fly-**secret** |
| Python 3.13, Streamlit (poort 8503 lokaal), `uv` als package manager | Standaard `python:3.13-slim` + `uv sync` |
| Env die de app leest: `OEREN_PAD`, `KWALDOSSIERS_PAD`, `SKILLS_PAD`, `DB_PATH`, `BEHEER_ENABLED`, `COMPETENTNL_API_KEY` | Allemaal als env/secret in `fly.toml`/secrets |

---

## 3. Isolatie van de bestaande app (harde randvoorwaarde)

Read-only vastgesteld: er is **één** bestaande app — `ceda-regiobijeenkomst` (org `personal`,
region `ams`, met een 1GB-volume `recaps_restore`).

Waarborgen voor een nieuwe deploy:

- **Nieuwe, eigen app-naam** (voorstel: `ceda-samenwijzer-oer`) → eigen machines, eigen registry-
  image, eigen (optioneel) volume. Nul overlap met `ceda-regiobijeenkomst`.
- **Eigen `fly.toml`** in `validatie_samenwijzer/` met `app = "ceda-samenwijzer-oer"` hardgecodeerd.
- Elk commando **expliciet** met `-a ceda-samenwijzer-oer`; nooit een global/destructief commando.
- **Nooit** `flyctl destroy`, `scale` of `secrets` op de regio-app.
- Beide apps leven in dezelfde `personal`-org — dat is veilig: Fly isoleert per app.

---

## 4. Aanbevolen architectuur — corpus in het image bakken

Sluit aan op het opslag-beslisdocument (`2026-06-04-opslagstrategie-data-en-deployment.md`, optie 1):
immutable artefact, **nul runtime-data-afhankelijkheid** (geen Box/rclone op runtime).

```
Lokaal (master, heeft alle data incl. de 4 Box-only instellingen op schijf):
  1. validatie.db opbouwen:  uv run ingest --alles   (+ seed_bulk.py)
  2. docker build vanuit repo-root → image met:
       - validatie_samenwijzer/ (code + .venv via uv sync)
       - oeren/ (alle .md + .pdf, incl. de 4 Box-only — staan lokaal op schijf)
       - kwalificatiedossiers/pdfs/*.md (+ .pdf)
       - data/skills/*.json
       - vooraf-gebouwde validatie.db
  3. flyctl deploy -a ceda-samenwijzer-oer   (image → Fly registry → machine)
```

Waarom dit werkt voor de **Box-only instellingen**: de build draait **lokaal**, waar Da Vinci/KWIC/
Graafschap/Deltion gewoon op schijf staan. Zo komen ze in het image (en dus in de app) **zonder** dat
ze publiek in git of in een CI-build hoeven — precies "alleen via de app".

### Image-grootte (indicatie)
oeren ~454 MB + KD's ~229 MB + skills ~3 MB ≈ **~690 MB data**, plus python+deps. Totaal grof
~1,3–1,8 GB. Prima voor Fly. Te verkleinen door KD-PDF's weg te laten (runtime leest alleen KD-`.md`).

### Build-context-aandachtspunt
De data leeft buiten het subproject (root-`oeren/`, root-`kwalificatiedossiers/`). Dus **bouwen
vanuit de repo-root** met een Dockerfile die `validatie_samenwijzer/` + `oeren/` +
`kwalificatiedossiers/` kopieert, en een strakke `.dockerignore` (geen `.git`, `.venv`, PDFs die je
niet nodig hebt). Overweeg `flyctl deploy --local-only` (lokaal bouwen, image pushen) i.p.v. ~700 MB
build-context naar de remote builder uploaden per deploy.

---

## 5. fly.toml — schets (nog niet aanmaken)

```toml
app = "ceda-samenwijzer-oer"      # NIEUW — niet ceda-regiobijeenkomst
primary_region = "ams"

[build]
  dockerfile = "validatie_samenwijzer/Dockerfile"

[env]
  OEREN_PAD = "/app/oeren"
  KWALDOSSIERS_PAD = "/app/kwalificatiedossiers/pdfs"
  SKILLS_PAD = "/app/validatie_samenwijzer/data/skills"
  DB_PATH = "/app/validatie_samenwijzer/data/validatie.db"
  BEHEER_ENABLED = "false"        # NOOIT true op een gedeelde server (triggert rclone/ingest/seed)

[http_service]
  internal_port = 8080            # Streamlit --server.port 8080 --server.address 0.0.0.0
  force_https = true
  auto_stop_machines = true       # scale-to-zero: goedkoop voor demo
  auto_start_machines = true
  min_machines_running = 0        # of 1 voor snellere cold start

[[vm]]
  memory = "1gb"                  # ruim voldoende; evt. 512mb
  cpu_kind = "shared"
  cpus = 1
```

Secrets (apart, niet in fly.toml):
```bash
flyctl secrets set ANTHROPIC_API_KEY=... -a ceda-samenwijzer-oer
flyctl secrets set COMPETENTNL_API_KEY=... -a ceda-samenwijzer-oer   # optioneel
```

Streamlit-start (CMD in Dockerfile): `streamlit run app/main.py --server.port 8080
--server.address 0.0.0.0 --server.headless true`. Websockets werken via Fly's `http_service`.

---

## 6. Open keuzes vóór uitvoering

- **DB ephemeral vs persistent.** Nu is de app read-only → ephemeral DB in het image volstaat.
  Wil je later student-/mentor-data laten *muteren* en bewaren over deploys heen, dan een klein
  Fly-volume voor `validatie.db` (en de DB daarheen verplaatsen). Niet nu nodig.
- **KD-PDF's meenemen?** Runtime leest alleen KD-`.md`. PDF's weglaten scheelt ~100+ MB image.
- **Scale-to-zero of altijd 1 machine?** Zero = goedkoop, trager bij eerste request. 1 = snappy,
  kleine vaste kost.
- **App-naam** definitief kiezen.
- **BEHEER_ENABLED** blijft `false` in prod (beheerpagina kan rclone/ingest/seed triggeren).

---

## 7. Wat dit NIET regelt

- De **rechten-/Fase 2-purge** (apart spoor) — los van deployment.
- Een CI/CD-pipeline — eerste deploy is handmatig `flyctl deploy` vanaf de master-machine.
- Custom domein/DNS — kan later.

---

## 8. Voorgestelde volgende stap

Op go/no-go: ik maak in een aparte PR de **`Dockerfile`**, **`.dockerignore`** en **`fly.toml`** (met
de nieuwe app-naam), zodat je lokaal kunt bouwen en `flyctl deploy -a <nieuwe-naam>` kunt draaien.
**De daadwerkelijke `flyctl deploy`/`secrets set` doe jij (of doe ik alleen op expliciet verzoek)** —
en altijd tegen de nieuwe app, nooit tegen `ceda-regiobijeenkomst`.
