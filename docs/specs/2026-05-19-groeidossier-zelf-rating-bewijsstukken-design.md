# Groeidossier — zelf-rating + bewijsstukken

**Datum:** 2026-05-19
**Status:** Ontwerp — wacht op review
**Auteur:** Ed de Feber (met Claude)

## Achtergrond

In de oude `edf_groeimonitor` (Flask, Azure) kon een student per werkproces een slider 0–100 zetten, een verantwoording schrijven, PDF-bewijsstukken uploaden, en kreeg de student feedback van de mentor. History werd in een `groeiarchief`-tabel bijgehouden zodat groei t.o.v. de vorige meting en t.o.v. de klas zichtbaar was.

Samenwijzer heeft op dit moment alleen *synthetische* kt/wp-scores (per student gegenereerd, gecorreleerd met voortgang). De student kan zichzelf niet beoordelen, er is geen verantwoording-tekst, geen bewijsstuk-functionaliteit en geen history. Dit ontwerp voegt die functionaliteit toe — met behoud van de huidige Streamlit-architectuur en de synthetische dataset als cold-start basis.

## Doel

Een student kan in Samenwijzer:

1. Per werkproces de eigen vaardigheid op een slider 0–100 zetten met de OER-niveau-labels (Starter / Op weg / Gevorderd / Beroepsbekwaam) zichtbaar.
2. Per werkproces een korte verantwoording schrijven ("Waarom vind je dit?"), eventueel ondersteund door een AI-aanscherpknop.
3. Bewijsstukken (PDF, JPG/PNG, DOCX, XLSX, max 10 MB) uploaden gekoppeld aan een werkproces of kerntaak.
4. Z'n groei over tijd zien als trendlijn per kerntaak, met delta t.o.v. de vorige meting.

De mentor kan per kerntaak een feedbacktekst schrijven en alle zelf-scores, verantwoordingen en bewijsstukken van zijn eigen studenten inzien.

## Niet-doelen

- Mentor scoort niet zelf (geen dubbel scoremodel). Zie [Alternatieven](#alternatieven).
- Geen object storage (S3/Azure Blob) — bestanden staan lokaal onder `data/bewijsstukken/`. Cloud-migratie is een latere afweging.
- Geen FastAPI-microservice voor uploads — `st.file_uploader` is voldoende voor 10 MB.
- Geen migratie van de oude `horizonstudenten.db` of `app.db` uit `edf_groeimonitor`.

## Architectuur

### Module-laag

Nieuwe modules zitten in dezelfde laag als `welzijn`/`outreach`:

```
prepare → transform → analyze → groei → app
                                ↑
                          groei_store
                       bewijsstuk_store
```

| Bestand | Rol |
|---|---|
| `src/samenwijzer/groei.py` | Business-logic. Aggregatie kt = gemiddelde wp; overlay van zelf-scores op `df`; berekenen delta t.o.v. vorige meting. Géén SQL, géén Streamlit. |
| `src/samenwijzer/groei_store.py` | SQLite-isolatie voor `groei.db` (volgt `outreach_store.py`-patroon: dataclasses, contextmanager, lazy `_geinitialiseerd`-set). |
| `src/samenwijzer/bewijsstuk_store.py` | Filesystem-IO voor `data/bewijsstukken/<studentnummer>/<uuid>.<ext>`. Path-validatie tegen traversal; metadata via `groei_store`. |
| `app/pages/6_groeidossier.py` | Streamlit-UI met student- en docent-view (rol-gestuurd). |

Bestaande modules blijven onveranderd, met één uitbreiding op `prepare.load_synthetisch_csv()`: na het laden draait `groei.overlay_self_scores(df)` over de DataFrame heen. Voor elke student met rijen in `groei_actueel` worden de wp-kolommen overschreven en kt-kolommen hercalculeerd als gemiddelde van hun werkprocessen. Cold-start (geen self-rating ooit) → synthetische score blijft staan.

### Geen FastAPI

`st.file_uploader` accepteert ons 10 MB-maximum probleemloos. De bestaande FastAPI-webhook (poort 8502) blijft uitsluitend voor WhatsApp.

## Data-model

SQLite-DB op `data/02-prepared/groei.db`, gitignored zoals `outreach.db` en `whatsapp.db`.

```sql
CREATE TABLE groei_actueel (
  studentnummer    TEXT NOT NULL,
  wp_kolom         TEXT NOT NULL,         -- bv. 'wp_1_2'
  score            INTEGER NOT NULL,       -- 0..100
  verantwoording   TEXT NOT NULL DEFAULT '',
  laatst_gewijzigd TEXT NOT NULL,         -- ISO timestamp
  PRIMARY KEY (studentnummer, wp_kolom)
);

CREATE TABLE groei_historie (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  studentnummer    TEXT NOT NULL,
  wp_kolom         TEXT NOT NULL,
  score            INTEGER NOT NULL,
  verantwoording   TEXT NOT NULL,
  opgeslagen_op    TEXT NOT NULL
);
CREATE INDEX idx_historie_student ON groei_historie(studentnummer, opgeslagen_op);

CREATE TABLE mentor_feedback (
  studentnummer  TEXT NOT NULL,
  kt_kolom       TEXT NOT NULL,            -- bv. 'kt_1' — feedback per kerntaak
  mentor_naam    TEXT NOT NULL,
  tekst          TEXT NOT NULL,
  geschreven_op  TEXT NOT NULL,
  PRIMARY KEY (studentnummer, kt_kolom)
);

CREATE TABLE bewijsstuk (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  studentnummer   TEXT NOT NULL,
  wp_kolom        TEXT,                    -- nullable: bewijs kan aan kt hangen
  kt_kolom        TEXT,                    -- één van de twee moet gezet zijn
  bestandsnaam    TEXT NOT NULL,           -- originele naam (display)
  bestandspad     TEXT NOT NULL,           -- relatief pad onder data/bewijsstukken/
  mime_type       TEXT NOT NULL,
  grootte_bytes   INTEGER NOT NULL,
  toelichting     TEXT NOT NULL DEFAULT '',
  geupload_op     TEXT NOT NULL,
  CHECK (wp_kolom IS NOT NULL OR kt_kolom IS NOT NULL)
);
CREATE INDEX idx_bewijs_student ON bewijsstuk(studentnummer);
```

### Filesystem-layout

```
data/bewijsstukken/<studentnummer>/<uuid4>.<ext>
```

UUID-naamgeving voorkomt collisions. Originele bestandsnaam zit in `bewijsstuk.bestandsnaam` voor display in de download-knop. Studentnummer wordt gevalideerd als digit-only voor pad-traversal-bescherming.

### Schrijfregel: atomic save

De "Opslaan"-knop in de student-UI schrijft *alle* wijzigingen in één SQLite-transactie:

1. Upsert in `groei_actueel` voor elke gewijzigde wp.
2. Insert in `groei_historie` voor elke gewijzigde wp (snapshot).

Bewijsstuk-uploads zijn aparte transacties (gebeuren direct bij upload, niet bij "Opslaan").

## UI-flow

Eén nieuwe pagina: `app/pages/6_groeidossier.py`. Rolafhankelijk.

### Pagina-skelet

Volgt de pagina-conventie uit `CLAUDE.md`:

```python
st.set_page_config(...)
st.markdown(CSS, unsafe_allow_html=True)
render_nav()
# ── rol-controle ──
# ── content ──
render_footer()
```

### Student-view (rol == "student")

- **Hero-kaart**: naam, opleiding, niveau, mentor — hergebruikt `styles.py`-patroon van `1_mijn_voortgang.py`.
- **Per kerntaak een `st.container(border=True)`**:
  - Kop met OER-label (uit `analyze._oer_label`).
  - Indien aanwezig: grijze kaart met mentor-feedback bovenin.
  - Voor elk werkproces in die kerntaak:
    - `st.slider("…", 0, 100, value=huidige_score)` met caption `Starter | Op weg | Gevorderd | Beroepsbekwaam` als visuele schaal.
    - `st.text_area("Waarom vind je dit?", value=verantwoording, max_chars=1000)`.
    - **AI-knop**: "✨ Laat tutor je verantwoording aanscherpen". Calls `tutor.aanscherp_verantwoording(...)` (nieuwe functie in `tutor.py`) — streamt suggestie in `st.write_stream`, slaat resultaat in `session_state` zodat re-renders geen nieuwe call doen. Student kopieert handmatig uit suggestie naar het tekstveld; we overschrijven niet automatisch om eigenaarschap te bewaren.
    - `st.expander("📎 Bewijsstukken (N)")`:
      - Lijst van geüploade bestanden met download-knop + verwijder-knop.
      - `st.file_uploader` met `type=["pdf", "jpg", "png", "docx", "xlsx"]`, max 10 MB check op `len(file.getvalue())`.
      - Optioneel toelichting-veld bij upload (`st.text_input`).
- **Eén "💾 Opslaan"-knop** onderaan: atomic save naar `groei_actueel` + `groei_historie`.

### Tab "Mijn groei over tijd"

Altair-lijngrafiek per kerntaak (x=`opgeslagen_op`, y=`score`), gebouwd uit `groei_historie`. Plus een "vs vorige meting"-deltacard per kerntaak (groene/rode delta-pijl).

### Docent-view (rol == "docent")

- `auth.vereist_docent()` direct na CSS-injectie.
- Studentselectie uit `auth.mentor_filter(df)`-subset (zelfde patroon als `1_mijn_voortgang.py`).
- Read-only weergave van sliders (gedisabled), verantwoordingen, bewijsstukken (download wel).
- Per kerntaak een `st.text_area("Feedback mentor", value=…)` + "Opslaan feedback"-knop → schrijft naar `mentor_feedback`.
- Identieke "Groei over tijd"-tab.

### AVG en toegang

Bewijsstukken zijn alleen zichtbaar voor (a) de student zelf, (b) de mentor van die student. Dit wordt afgedwongen in `app/pages/6_groeidossier.py` vóór elke render van een bewijsstuk-lijst of download-knop: studentnummer-check tegen `st.session_state["studentnummer"]` (student) of `auth.mentor_filter` (docent).

## Integratie met bestaande dashboards

- `prepare.load_synthetisch_csv()` → `transform.transform_student_data()` → **nieuw**: `groei.overlay_self_scores(df)` → `st.session_state["df"]`.
- Pagina's `1_mijn_voortgang.py` en `2_groepsoverzicht.py` blijven ongewijzigd; ze krijgen automatisch de overlaid scores binnen via `session_state`.
- `coach.genereer_weekplan` en `tutor` blijven ongewijzigd; ze gebruiken de overlaid scores als context.
- Eén kleine UI-toevoeging op `1_mijn_voortgang.py`: badge "📝 Zelf beoordeeld op {datum}" of "🤖 Schatting op basis van OER", afhankelijk van of er een record in `groei_actueel` bestaat. Zo weet de gebruiker welke bron de score is.

## AI-aanscherpknop

Nieuwe functie `tutor.aanscherp_verantwoording(werkproces_label: str, kerntaak_label: str, opleiding: str, huidige_tekst: str, score: int) -> Generator[str]`.

- Client via `_ai._client()` (nooit eigen instantiëren).
- Streaming response zodat UI direct feedback geeft.
- Prompt: "Je bent een leercoach voor een MBO-student. De student heeft voor werkproces *{werkproces_label}* (kerntaak: *{kerntaak_label}*, opleiding: *{opleiding}*) zichzelf {score}/100 gegeven en deze verantwoording geschreven: «{huidige_tekst}». Geef in 2-4 zinnen een aangescherpte versie die concreet voorbeeldgedrag noemt en past bij de OER-formulering. Schrijf in dezelfde persoon (ik-vorm)."
- `try/except anthropic.APITimeoutError` met vriendelijke foutmelding (`_ai.vriendelijke_fout`).
- Resultaat in `st.session_state[f"sw_aanscherp_{studentnummer}_{wp_kolom}"]` zodat re-renders niet opnieuw callen.

Geen automatische overschrijving van het tekstveld — de student kopieert zelf. Houdt eigenaarschap intact en voorkomt het verlies van eerder gemaakte tekst.

## Validatie en error-handling

| Boundary | Validatie |
|---|---|
| `st.file_uploader` | `type=[...]` filter + `len(file.getvalue()) <= 10 * 1024 * 1024` + MIME-check tegen extension-mismatch. |
| `bewijsstuk_store.opslaan(...)` | Studentnummer regex `^\d+$`; doelpad onder `data/bewijsstukken/`-root via `Path.resolve().is_relative_to(...)`. |
| `groei_store.opslaan_actueel(...)` | Score-range 0–100; wp_kolom in `transform.get_werkproces_columns(df)`. |
| AI-call | `try/except APITimeoutError` + generieke `Exception`-fallback via `_ai.vriendelijke_fout`. |

Interne functies (kt-aggregatie, overlay) krijgen geen defensieve checks — de boundaries vangen het op.

## Tests

- `tests/test_groei.py`:
  - `test_kt_score_is_gemiddelde_van_wp`
  - `test_overlay_self_scores_overschrijft_synthetisch`
  - `test_overlay_laat_synthetisch_staan_bij_cold_start`
  - `test_atomic_save_schrijft_actueel_en_historie`
  - `test_historie_snapshot_per_wijziging`
- `tests/test_bewijsstuk_store.py`:
  - `test_upload_genereert_uuid_pad`
  - `test_pad_traversal_geweigerd`
  - `test_grootte_limiet_afgedwongen`
- `tests/test_architecture.py`: uitbreiden met `groei` + `groei_store` in de juiste laag; importregels gecontroleerd.
- **UI-smoketest** (chrome-devtools-mcp) vóór merge-claim:
  - Login als test-student uit `gebruikers.txt`.
  - Verschuif slider, type verantwoording, upload PDF, klik Opslaan, refresh.
  - History-grafiek toont één punt.
  - Tweede save → grafiek toont twee punten met delta-pijl.
  - Logout; login als mentor van die student → ziet de scores read-only, kan feedback schrijven.
  - Logout; login als andere mentor (andere instelling) → ziet die student niet.

## Migratie

Geen migratie — `groei.db` start leeg. Bestaande synthetische dataset blijft de cold-start-baseline. Eerste "Opslaan" door een student maakt zijn rijen aan.

`scripts/init_groei_db.py` (optioneel) creëert de DB met schema; verder gebeurt init lazy in `groei_store` zoals bij `outreach_store`.

## Alternatieven (overwogen, niet gekozen)

- **Mentor scoort ook**: dubbele score-kolommen, verwarring "welke score telt waar?". Afgewezen — student-eigenaarschap is leidend; mentor geeft feedback-tekst.
- **Synthetische scores naast self-scores tonen**: verdubbelt visualisaties zonder duidelijke meerwaarde voor de student.
- **Bewijsstukken als BLOB in SQLite**: DB groeit snel, backup wordt traag. Filesystem + metadata is simpeler.
- **FastAPI-upload-endpoint**: nodig bij streaming uploads >50 MB; bij 10 MB is `st.file_uploader` geen knelpunt.
- **Automatisch overschrijven van verantwoording door AI**: ondermijnt student-eigenaarschap; nu suggestie-pattern.

## Open punten

Geen — alle keuzes zijn gemaakt in de brainstormfase. Bij ontdekking van nieuwe vragen tijdens implementatie: terug naar dit document en aanvullen vóór het schrijven van code.
