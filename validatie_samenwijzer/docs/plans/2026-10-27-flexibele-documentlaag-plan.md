# Flexibele documentlaag — implementatieplan

> **Voor uitvoerders:** gebruik superpowers:subagent-driven-development (aanbevolen) of superpowers:executing-plans.
> Stappen gebruiken checkboxes. Werk per fase op een eigen branch en open een PR; Ed keurt goed vóór mergen en deployen.

**Doel:** alle door de instellingen aangeleverde documenten (meerdere per soort, instellings- of opleidingsgebonden,
met KD-versies per cohort en privacy-guardrails) beschikbaar maken voor de assistent.
**Architectuur:** nieuwe tabel `documenten` + soortenregister in `db.py`; selectie/budgetlogica in een nieuwe
module `src/validatie_samenwijzer/documenten.py` (geen business logic in `app_fastapi/`); `laad_context` krijgt een
`niveau`; KD-versies via manifest; ingest + privacy in eigen modules.
**Stack:** Python 3.13, FastAPI, SQLite, pytest, ruff, Playwright (smoke), markitdown/tesseract (ingest).
**Spec:** `docs/plans/2026-10-27-flexibele-documentlaag.md` · **Besluitenlog:** `…-besluitenlog-documentverwerking.md`

## Global Constraints
- Alle Anthropic-calls alleen via `_ai._client()`; geen `anthropic.Anthropic()`; geen business logic of raw SQL in `app_fastapi/`.
- Lint: `ruff` line-length 100 (`uv run ruff check --fix src/ app_fastapi/ scripts/ && uv run ruff format …`); tests: `uv run python -m pytest` (geen CI-gate: lokaal draaien).
- Budgetten: OER 500K, KD 300K, skills 50K tekens (ongewijzigd); documenten-totaal **700K** (`DOC_BUDGET_TEKENS`, env-override).
- Prioriteit bij overschot: juridisch → opleidingsgebonden → informatief; binnen groep kleinste eerst; afgevallen titels loggen (geen PII op INFO) + melding via bestaande banner.
- `''` (lege string, NOT NULL DEFAULT '') = "alle" voor `crebo`, `leerweg`, `cohort`.
- `zichtbaarheid` ∈ {`publiek`,`ingelogd`,`intern`}; niveau `publiek` ziet alleen `publiek`, `student`/`mentor` zien `publiek`+`ingelogd`; `gereviewd=0` ⇒ behandeld als `intern`; `gevoeligheid='uitgesloten'` nooit geladen.
- Citatieplicht en systeemprompt-templates blijven intact; DB zit in het Fly-image ⇒ na data-wijzigingen nieuwe deploy.
- Nooit direct naar `main`; PR via `gh pr create`; mergen via `gh api -X PUT repos/cedanl/samenwijzer/pulls/N/merge -f merge_method=squash`; deploy `flyctl deploy -a digitale-gids --remote-only` vanuit repo-root. `gebruikers.txt` niet aanraken.

## Review Focus (elk heeft een test in de genoemde taak)
1. Document in manifest/DB wijst naar een ontbrekend bestand → overslaan + loggen, geen crash (Taak 1.3).
2. Leeg of onleesbaar document → niet in prompt, gemeld in rapport (Taak 1.3, 3.2).
3. Twee OER's van dezelfde instelling in één sessie → instellingsbreed document één keer (Taak 1.3).
4. Onbekende `soort` of `niveau` → duidelijke `ValueError`, geen stille fallback (Taak 1.1, 1.3).
5. Document met crebo/leerweg/cohort `''` matcht alle OER's van de instelling, met ingevuld veld alleen exact (Taak 1.3).

---

## Fase 0 — Image-hygiëne (PR 0)

### Taak 0.1: `_bronmateriaal` uit het Fly-image
**Files:** Modify `../.dockerignore` (monorepo-root); Test `tests/test_dockerignore.py`
- [ ] **Stap 1:** test `test_dockerignore_sluit_bronmateriaal_uit` leest `Path(__file__).resolve().parents[2]/".dockerignore"` en asserteert dat een regel `**/_bronmateriaal/` voorkomt.
- [ ] **Stap 2:** run `uv run python -m pytest tests/test_dockerignore.py -v` → FAIL.
- [ ] **Stap 3:** voeg `**/_bronmateriaal/` en `**/_documenten/**/origineel/` toe aan `.dockerignore`.
- [ ] **Stap 4:** run → PASS; `ruff` groen.
- [ ] **Stap 5:** commit `fix(deploy): _bronmateriaal niet in het image`; PR openen.
- [ ] **Na goedkeuring + merge:** deploy; verifieer `flyctl ssh console -a digitale-gids -C "ls /app/oeren/graafschap_oeren"` toont **geen** `_bronmateriaal`; prod-smoke (startpagina + keuze + overlay, `/api/chat` gemockt).

## Fase 1 — Schema, register, selectie (PR 1)

### Taak 1.1: Soortenregister
**Files:** Modify `src/validatie_samenwijzer/db.py`; Test `tests/test_db.py`
**Interfaces — Produces:** `@dataclass(frozen=True) class SoortInfo: label: str; bereik: Literal["instelling","opleiding"]; juridisch: bool; zichtbaarheid: Literal["publiek","ingelogd","intern"]`; `SOORTEN: dict[str, SoortInfo]`; `INSTELLING_SOORTEN: dict[str,str]` blijft bestaan (afgeleid: soort → label, alleen bereik `instelling`) zodat `test_instelling_lijsten_sync.py` en bestaande imports werken.
- [ ] Tests: `test_soorten_bevat_bestaande_en_nieuwe` (alle 12 oude sleutels + `examenplan`,`nominale_lijn`,`studiegids`,`onderwijsplan`,`praktijkovereenkomst`,`schoolkosten`,`veiligheidsplan`,`protocol`,`keuzedelen`,`studiekeuzegids`,`overig`); `test_examenplan_is_opleidingsgebonden_en_examenreglement_instellingsbreed`; `test_onbekende_soort_geeft_valueerror` (via `voeg_document_toe`, taak 1.2).
- [ ] Implementeer register: juridisch = examenreglement, studentenstatuut, bindend_studieadvies, klachtenregeling, gedragscode, privacyreglement, meldcode, gedragsregeling, praktijkovereenkomst; opleidingsgebonden = examenplan, nominale_lijn, studiegids, onderwijsplan, keuzedelen; overige informatief. `begeleidingsbeleid` blijft zichtbaarheid `ingelogd` (huidige `MENTOR_SOORTEN`-gedrag), de rest `publiek`.
- [ ] Run tests → PASS; commit.

### Taak 1.2: Tabel `documenten` + migratie + DB-functies
**Files:** Modify `db.py` (`init_db`, functies); Modify callers (`ingest.py:_verwerk_instelling_documenten`, `scripts/seed_bulk.py` FK-query op regel ~230, `app_fastapi/` zo gebruikt — vind met `grep -rn "instelling_document" src app_fastapi scripts tests`); Test `tests/test_db.py`
**Interfaces — Produces:**
`voeg_document_toe(conn, instelling_id: int, soort: str, titel: str, bestandspad: str, *, bereik: str | None = None, crebo: str = "", leerweg: str = "", cohort: str = "", zichtbaarheid: str | None = None, gevoeligheid: str = "normaal", gereviewd: bool = False, versie_label: str = "", samenvatting: str = "") -> int` (bereik/zichtbaarheid default uit `SOORTEN[soort]`; upsert op de sleutel `(instelling_id, soort, bereik, crebo, leerweg, cohort, bestandspad)`);
`get_documenten_voor_context(conn, instelling_id: int, crebo: str, leerweg: str, cohort: str, niveau: str) -> list[sqlite3.Row]`;
`markeer_document_geindexeerd(conn, doc_id: int) -> None`; `set_document_content_hash(conn, doc_id: int, content_hash: str) -> None`.
- [ ] Tests: `test_meerdere_documenten_zelfde_soort` (twee `protocol`-documenten, andere bestandspad → 2 rijen); `test_migratie_neemt_instelling_documenten_over` (oude tabel met 2 rijen → na `init_db` 2 rijen in `documenten`, `bereik='instelling'`, `gereviewd=1`, oude soorten behouden); `test_lege_string_is_alle_en_unique_werkt` (zelfde sleutel twee keer → 1 rij); `test_onbekende_soort_valueerror`; `test_zichtbaarheid_default_uit_register`.
- [ ] Implementeer: `CREATE TABLE IF NOT EXISTS documenten (… zie spec §1 …, UNIQUE(instelling_id, soort, bereik, crebo, leerweg, cohort, bestandspad))`; migratie na `init_db`: `INSERT OR IGNORE INTO documenten … SELECT … FROM instelling_documenten` (oude tabel blijft ongemoeid als legacy). Verwijder `UNIQUE`-aanname uit alle callers; update `seed_bulk.py` zodat de FK-guard `documenten` gebruikt.
- [ ] Run `uv run python -m pytest tests/test_db.py tests/test_ingest.py -v` → PASS; commit.

### Taak 1.3: Selectie en budget
**Files:** Create `src/validatie_samenwijzer/documenten.py`; Test `tests/test_documenten.py`
**Interfaces — Consumes:** `get_documenten_voor_context`, `SOORTEN`, `laad_instelling_bron_tekst` (chat.py). **Produces:**
`@dataclass(frozen=True) class GekozenDocument: doc_id: int; kop: str; tekst: str; juridisch: bool; bereik: str`;
`@dataclass(frozen=True) class Selectie: per_oer: dict[int, list[GekozenDocument]]; afgevallen: list[str]`;
`DOC_BUDGET_TEKENS: int` (default 700_000, env `DOC_BUDGET_TEKENS`);
`selecteer_documenten(conn, oers: Sequence[sqlite3.Row], niveau: str, budget: int | None = None) -> Selectie`.
- [ ] Tests (tmp-DB + tmp-bestanden): `test_opleidingsgebonden_alleen_bij_match`; `test_lege_string_matcht_alle_cohorten`; `test_dedupe_instellingsbreed_bij_twee_oers` (document alleen in `per_oer` van de eerste OER); `test_niveau_publiek_sluit_ingelogd_en_intern_uit`; `test_ongereviewd_en_uitgesloten_nooit`; `test_budget_prioriteit_juridisch_eerst_en_afvallen_gelogd` (budget klein → juridisch blijft, informatief valt, titel in `afgevallen`); `test_ontbrekend_bestand_wordt_overgeslagen`; `test_leeg_document_wordt_overgeslagen`; `test_onbekend_niveau_valueerror`.
- [ ] Implementeer volgens Global Constraints (Python; één query per OER; tekst via `laad_instelling_bron_tekst`, cap per document 300K blijft).
- [ ] Run `uv run python -m pytest tests/test_documenten.py -v` → PASS; commit.

### Taak 1.4: `laad_context` + routes + banner
**Files:** Modify `app_fastapi/context.py`, `app_fastapi/main.py` (4 call sites), `app_fastapi/static/app.js` (`setBanner`), `src/validatie_samenwijzer/chat.py` (templates ongewijzigd; `instelling_bronnen` komt nu uit `Selectie`); Test `tests/test_fastapi_poc.py`, `tests/test_chat.py`
**Interfaces — Produces:** `laad_context(oer_ids: list[int], niveau: str = "publiek") -> tuple[str, list[str], list[str], bool]` (4-tuple blijft; `laad_context([]) == ("", [], [], False)`); `laad_context_met_melding(oer_ids, niveau) -> tuple[str, list[str], list[str], bool, str]` (5e = melding, `""` als alles paste); sessie krijgt `melding: str`; `/api/kies` en `/api/vraag` (modus chat) geven `"melding"` mee. `main.py`: `STUDENT_SOORTEN`→`niveau="student"`, `MENTOR_SOORTEN`→`niveau="mentor"`; verwijder de vaste soort-tuples uit `context.py`.
- [ ] Tests: bestaande `test_laad_context_*` blijven groen; `test_kies_geeft_melding_bij_budgetoverschot` (env `DOC_BUDGET_TEKENS=10`); `test_vraag_over_kluiscontrole_context_bevat_protocol` (tmp-document soort `protocol` bij OER van die instelling → tekst zit in systeemprompt).
- [ ] `app.js`: `setBanner(onleesbaar, melding)` toont `melding` indien gezet (tekst: "Niet alle documenten pasten; X ontbreekt in dit gesprek."); update beide aanroepen.
- [ ] Run volledige suite + `ruff`; **UI-smoke** (`scripts/`-onafhankelijk Playwright-script zoals eerder: server op :8504 met `COOKIE_HTTPS_ONLY=0`, `/api/chat` mocken): kiezen → vraag → overlay; geen JS-fouten; mobiel 390 px.
- [ ] Commit; PR 1 openen met testresultaat + budgetmeting (`tekens` per instelling).

## Fase 2 — KD-versies (PR 2)

### Taak 2.1: Manifest en keuze
**Files:** Create `src/validatie_samenwijzer/kd_versies.py`, `../kwalificatiedossiers/versies.json`; Modify `chat.py` (`laad_kwalificatiedossier_tekst`), `app_fastapi/context.py`; Test `tests/test_kd_versies.py`
**Interfaces — Produces:** `kies_kd_pad(crebo: str, cohort: str | None, basis: Path | None = None) -> Path | None`; `laad_kwalificatiedossier_tekst(crebo: str | None, cohort: str | None = None) -> str` (zonder cohort = huidig gedrag). Manifest: `{"<crebo>": [{"versie": "2016", "bestand": "25122@2016.md", "cohorten": [2019, 2025]}, {"versie": "2026", "bestand": "25122.md", "cohorten": [2026, 2099]}]}`.
- [ ] Tests: `test_kiest_versie_waarvan_cohortbereik_het_cohort_bevat` (2025 → 2016-versie); `test_nieuwste_als_geen_bereik_matcht`; `test_zonder_manifest_valt_terug_op_crebo_md`; `test_ontbrekend_bestand_in_manifest_valt_terug`.
- [ ] Implementeer; `laad_context` geeft `row["cohort"]` door.
- [ ] Data: converteer KW1C "KD Werkvoorbereider fabricage.pdf" (KD 2016) naar `kwalificatiedossiers/pdfs/25122@2016.md` met de bestaande markitdown-route; manifest-regel voor 25122.
- [ ] Ingest-controle `controleer_kd_versies(conn) -> list[str]` (waarschuwt bij KD-versie zonder OER in cohortbereik); test erbij. Suite + ruff + smoke; commit; PR 2.

## Fase 3 — Ingest, OCR, privacy (PR 3)

### Taak 3.1: Privacy-pass
**Files:** Create `src/validatie_samenwijzer/privacy.py`; Test `tests/test_privacy.py`
**Interfaces — Produces:** `@dataclass(frozen=True) class Redactie: soort: str; aantal: int`; `redigeer(tekst: str) -> tuple[str, list[Redactie]]`; `verdachte_namen(tekst: str) -> list[str]` (heuristiek: blokken na "opgesteld door/auteur/versiebeheer/ondertekening" en tabellen met "naam"-kop; alleen voor het reviewrapport).
- [ ] Tests met canary's: `test_redigeert_email_telefoon_iban_bsn` (`jan.canary@example.test`, `06-12345678`, `NL91ABNA0417164300`, 9-cijferig BSN-patroon met elfproef) → `[verwijderd]`, telling klopt; `test_laat_gewone_tekst_ongemoeid` (artikelnummers/jaartallen/crebo's blijven staan); `test_verdachte_namen_in_versiebeheertabel`.
- [ ] Implementeer deterministisch (regex + elfproef); commit.

### Taak 3.2: Formaten, OCR en manifest-ingest
**Files:** Create `src/validatie_samenwijzer/document_ingest.py`, `scripts/maak_manifest.py`; Modify `ingest.py` (CLI-optie `--documenten`); Test `tests/test_document_ingest.py`
**Interfaces — Produces:** `@dataclass(frozen=True) class ManifestItem: bestand: str; soort: str; bereik: str; crebo: str; leerweg: str; cohort: str; zichtbaarheid: str; gevoeligheid: str; gereviewd: bool; titel: str`; `lees_manifest(map: Path) -> list[ManifestItem]` (valideert soort/bereik/zichtbaarheid, `ValueError` bij onbekend); `xlsx_naar_markdown(pad: Path) -> str` (alleen zichtbare bladen; sjabloonbladen `Voorblad`,`Controleblad`,`Vaststellingsformulier*`,`Versiebeheer`,`Invulmogelijkheden`,`_TemplateOpmaakEX` overgeslagen); `ingest_documenten(conn, instelling: str, oeren_pad: Path, reset: bool = False) -> IngestRapport` (per bestand: classificatie, redacties, `ingenomen|overgeslagen(reden)`).
- [ ] Tests: `test_manifest_wint_van_bestandsnaam_en_waarschuwt_bij_tegenspraak` (naam `27054_…`, manifest crebo `25648`); `test_xlsx_slaat_verborgen_en_sjabloonbladen_over`; `test_uitgesloten_wordt_nooit_geindexeerd`; `test_nieuw_document_zonder_review_is_intern`; `test_ontbrekend_bestand_in_manifest_wordt_gerapporteerd`; `test_scan_gebruikt_ocr_pad` (monkeypatch OCR-functie).
- [ ] Implementeer; `.md` schrijven naar `oeren/<inst>_oeren/_documenten/<soort>/`, origineel blijft in `…/origineel/` (dockerignored); reviewrapport als `…/_documenten/reviewrapport.md` (redacties + `verdachte_namen`).
- [ ] `scripts/maak_manifest.py <instelling> <bronmap>`: stelt manifest voor uit Box-mapnaam (`3-…` → regelingen enz.) + bestandsnaamparser + inhoud-sniff (crebo in eerste pagina); schrijft `manifest.json` met `gereviewd: false`.

### Taak 3.3: Antwoordregel en red-team
**Files:** Modify `chat.py` (`_SYSTEEM_TEMPLATE`, `_MULTI_SYSTEEM_TEMPLATE`); Create `scripts/privacy_redteam.py`; Test `tests/test_chat.py`
- [ ] Test `test_systeemprompt_bevat_antwoordregel_geen_persoonsnamen` (beide templates bevatten de regel: geen persoonsnamen of contactgegevens uit bronnen, verwijs naar de rol).
- [ ] `test_canary_pii_komt_niet_in_laad_context` (document met `jan.canary@example.test` gerediged → niet in systeemprompt).
- [ ] `privacy_redteam.py`: 10 vragen ("wie schreef dit protocol?", "noem de SLB'ers …") tegen het live model via `_ai._client()`, asserteert dat canary-namen niet voorkomen; **niet** in pytest; draaien na fase 4 en rapport in Box `90-analyse/`.
- [ ] Suite + ruff + smoke; commit; PR 3.

## Fase 4 — Data laden en deploy (PR 4 + deploy)

### Taak 4.1: Per instelling laden
Volgorde: Curio → KW1C → Graafschap → Rijn IJssel → Deltion (leeg, wacht op aanlevering).
- [ ] Per instelling: `rclone copy box:samenwijzer/use-case-samenwijzer/10-instellingen/<inst> <lokaal>`; `scripts/maak_manifest.py`; **Ed controleert manifest + reviewrapport** (zet `gereviewd: true` en `zichtbaarheid`); `uv run python -m validatie_samenwijzer.ingest --documenten --instelling <inst>`.
- [ ] Curio: registreer ontbrekende KD's (2026-crebo's) via bestaande KD-build; verplaats OER 25797-2025 naar `curio_oeren` + ingest; BSA 2026-27 aangeven als ontbrekend. KW1C: installeer `tesseract` (Ed), scan studiegids 25779 via OCR; examenplannen 25122/25779 als `examenplan` (niet als OER); studiegids 25122 registreren (sleutelconflict opgelost door `documenten`). Graafschap: 11 examenplannen + keuzedelen; Rijn IJssel: examenreglement 2026-27 aangeven als ontbrekend.
- [ ] Verificatie per instelling: telling `documenten` per soort (rapport in Box `90-analyse/`), `uv run python -m pytest`, en acceptatiecriterium 3: kluiscontrole-vraag bij een Curio-OER → antwoord met bron, vindplaats, citaat (1 echte API-vraag, daarna rest gemockt).
- [ ] `privacy_redteam.py` draaien; rapport bewaren; commit manifests (zonder originelen) + rapport; PR 4 openen.
- [ ] Na goedkeuring: merge → `flyctl deploy` → prod-smoke (kiezen, vraag, overlay) + één echte vraag per instelling; besluitenlog bijwerken met definitieve opname/uitsluitingen.

## Self-review (uitgevoerd)
- Spec-dekking: schema §1 (1.2), register §2 (1.1), selectie/budget §3 (1.3–1.4), KD §4 (2.1), privacy §5 (3.1–3.3), aanleveren §6 (3.2, 4.1), waar-leeft-wat §7 (3.2 paden), fase 0 (0.1), acceptatie 3/7 (4.1).
- Types consistent: `Selectie.per_oer`, `GekozenDocument`, `laad_context(…, niveau)` worden in 1.3/1.4/4.1 identiek gebruikt.
- Open voor Ed vóór uitvoering: **B1 reviewpoort** (plan neemt het voorstel over: nieuw document is `intern` tot `gereviewd`).
