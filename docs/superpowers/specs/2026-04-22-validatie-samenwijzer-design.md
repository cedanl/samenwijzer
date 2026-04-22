# Design: Validatie Samenwijzer — OER-assistent voor MBO

**Datum:** 2026-04-22
**Status:** Goedgekeurd
**Sprint:** 1

## Overzicht

Standalone Streamlit-app in `validatie_samenwijzer/` voor SLB-ers/mentoren en studenten van MBO-instellingen waarvan OER's beschikbaar zijn. Kern: hybride OER-assistent (AI-antwoord + bronpassages) met doorvraagmogelijkheid, aangevuld met voortgangsdata en een begeleidingsinterface voor mentoren.

## Instellingen en OER-bronnen

Vijf instellingen met OER-documenten in `validatie_samenwijzer/oeren/`:

| Instelling | Map | Formaat |
|---|---|---|
| Aeres | `aeres_oeren/` | PDF |
| Da Vinci | `davinci_oeren/` | PDF |
| Rijn IJssel | `rijn_ijssel_oer/` | PDF + HTML |
| Talland | `talland_oeren/` | PDF + HTML |
| Utrecht | `utrecht_oeren/` | Markdown |

Crebo-code, leerweg (BOL/BBL) en cohort worden geparsed uit de bestandsnaam via regex `(\d{5})(BOL|BBL)(\d{4})`.

## Tech stack

- **App**: Python 3.13, Streamlit
- **Database**: SQLite via eigen `db.py` (geen ORM)
- **Vectordatabase**: ChromaDB (persistent op schijf)
- **Embeddings**: OpenAI `text-embedding-3-small`
- **AI**: Anthropic Claude Sonnet (`claude-sonnet-4-6`) via Anthropic SDK
- **PDF-extractie**: `pdfplumber`
- **HTML-extractie**: `BeautifulSoup4`
- **Package management**: `uv`

## Projectstructuur

```
validatie_samenwijzer/
├── app/
│   ├── main.py                      ← Login + sessie-initialisatie
│   └── pages/
│       ├── student/
│       │   ├── 1_oer_assistent.py   ← Hybride chat (hoofdpagina student)
│       │   ├── 2_mijn_oer.py        ← Volledig OER inzien / downloaden
│       │   └── 3_mijn_voortgang.py  ← Kerntaken, werkprocessen, BSA, aanwezigheid
│       ├── mentor/
│       │   ├── 1_mijn_studenten.py  ← Studentenoverzicht met voortgangsindicatoren
│       │   └── 2_begeleidingssessie.py ← Studentprofiel + OER-assistent naast elkaar
│       └── uitloggen.py
├── src/validatie_samenwijzer/
│   ├── _ai.py               ← Anthropic client factory
│   ├── _openai.py           ← OpenAI client factory (embeddings)
│   ├── db.py                ← SQLite: schema-init, queries
│   ├── auth.py              ← Login, wachtwoord-hash, rolcontrole, sessie
│   ├── ingest.py            ← CLI: OER-bestanden → chunks → ChromaDB + kerntaken → SQLite
│   ├── vector_store.py      ← ChromaDB wrapper: opslaan en zoeken
│   ├── chat.py              ← Hybride chat: retrieval + Claude streaming
│   └── styles.py            ← CSS + navigatie (gebaseerd op samenwijzer huisstijl)
├── data/
│   ├── oeren/               ← Symlink of copy van oeren/-map
│   ├── chroma/              ← Persistente ChromaDB (gitignored)
│   └── validatie.db         ← SQLite database (gitignored)
├── seed/
│   └── seed.py              ← Testgebruikers + synthetische scores aanmaken
├── pyproject.toml
└── .env
```

**Lagenregel**: `db → auth / vector_store → chat → app`. Nooit omgekeerd. `_ai.py` en `_openai.py` zijn cross-cutting.

## Datamodel (SQLite)

### `instellingen`
| kolom | type | opmerking |
|---|---|---|
| id | INTEGER PK | |
| naam | TEXT | bijv. `"aeres"` |
| display_naam | TEXT | bijv. `"Aeres MBO"` |

### `oer_documenten`
| kolom | type | opmerking |
|---|---|---|
| id | INTEGER PK | |
| instelling_id | FK → instellingen | |
| opleiding | TEXT | bijv. `"Verzorgende IG"` |
| crebo | TEXT | bijv. `"25655"` |
| cohort | TEXT | bijv. `"2025"` |
| leerweg | TEXT | `"BOL"` of `"BBL"` |
| bestandspad | TEXT | relatief pad naar bronbestand |
| geindexeerd | BOOLEAN | is dit OER al in ChromaDB opgenomen? |

### `kerntaken`
Gevuld tijdens ingestie vanuit OER-inhoud.

| kolom | type | opmerking |
|---|---|---|
| id | INTEGER PK | |
| oer_id | FK → oer_documenten | |
| code | TEXT | bijv. `"B1-K1"`, `"KT2"` |
| naam | TEXT | bijv. `"Verpleegkundige zorg verlenen"` |
| type | TEXT | `"kerntaak"` of `"werkproces"` |
| volgorde | INTEGER | voor sortering in de UI |

### `mentoren`
| kolom | type | opmerking |
|---|---|---|
| id | INTEGER PK | |
| naam | TEXT | |
| wachtwoord_hash | TEXT | SHA-256 |
| instelling_id | FK → instellingen | |

### `mentor_oer` (koppeltabel)
| kolom | type |
|---|---|
| mentor_id | FK → mentoren |
| oer_id | FK → oer_documenten |

### `studenten`
| kolom | type | opmerking |
|---|---|---|
| id | INTEGER PK | |
| studentnummer | TEXT UNIQUE | |
| naam | TEXT | |
| wachtwoord_hash | TEXT | SHA-256 |
| instelling_id | FK → instellingen | |
| oer_id | FK → oer_documenten | |
| mentor_id | FK → mentoren | |
| leeftijd | INTEGER | |
| geslacht | TEXT | |
| klas | TEXT | |
| voortgang | REAL | 0.0–1.0 |
| bsa_behaald | REAL | |
| bsa_vereist | REAL | |
| absence_unauthorized | REAL | uren |
| absence_authorized | REAL | uren |
| vooropleiding | TEXT | bijv. `"VMBO_TL"` |
| sector | TEXT | bijv. `"Zorgenwelzijn"` |
| dropout | BOOLEAN | |

### `student_kerntaak_scores`
| kolom | type | opmerking |
|---|---|---|
| student_id | FK → studenten | |
| kerntaak_id | FK → kerntaken | |
| score | REAL | 0–100 |

### ChromaDB metadata per chunk
```json
{
  "oer_id": 3,
  "instelling": "rijn_ijssel",
  "crebo": "25655",
  "cohort": "2025",
  "leerweg": "BOL",
  "bron_bestand": "OER_2025-2026_Verzorgende-IG_BOL.pdf",
  "pagina": 14
}
```

## Ingestie-pipeline (`ingest.py`)

CLI-script, eenmalig uitvoeren (herhalen bij nieuwe OER's of model-upgrade):

```bash
uv run python -m validatie_samenwijzer.ingest --instelling aeres
uv run python -m validatie_samenwijzer.ingest --bestand oeren/rijn_ijssel_oer/OER_2025-2026_Verzorgende-IG_BOL.pdf
uv run python -m validatie_samenwijzer.ingest --alles --reset
```

**Pipeline per bestand:**
1. **Detectie**: crebo, cohort, leerweg uit bestandsnaam via regex `(\d{5})(BOL|BBL)(\d{4})`. Instelling uit mapnaam.
2. **Extractie**: PDF → `pdfplumber`, HTML → `BeautifulSoup4`, MD → directe tekst.
3. **Kerntaken extraheren**: regex + heuristiek op kopjes (bijv. `"B1-K1"`, `"Kerntaak 1"`, `"Werkproces 1.1"`). Opslaan in `kerntaken`-tabel.
4. **Chunken**: ~500 tokens per chunk, 50-token overlap. Sectiegrenzen (kopjes, artikelnummers) als natuurlijke breekpunten.
5. **Embedden**: OpenAI `text-embedding-3-small` per chunk.
6. **Opslaan**: chunks + metadata in ChromaDB collection `oer_chunks`.
7. **Markeren**: `oer_documenten.geindexeerd = true` in SQLite.

## Chat-architectuur (`chat.py`)

```
Gebruikersvraag
    ↓
Embed vraag (OpenAI text-embedding-3-small)
    ↓
ChromaDB similarity search — gefilterd op oer_id(s) van ingelogde gebruiker
    → Top-5 chunks (tekst + metadata)
    ↓
Prompt: systeemrol + conversatiehistorie + top-5 chunks + vraag
    ↓
Claude claude-sonnet-4-6 streamt antwoord
    ↓
UI toont: gestreamd antwoord + bronpassages als kaartjes (pagina, artikel, exacte tekst)
```

- **Conversatiegeheugen**: `st.session_state["chat_history"]` als `[{rol, inhoud}]`. Geen DB-persistentie in sprint 1.
- **Toegangsfilter**: student → `where oer_id = student.oer_id`, mentor in begeleidingssessie → `where oer_id = actieve_student.oer_id`.
- **Lage relevantie**: als similarity < 0.3, meldt de AI expliciet dat het antwoord niet in de OER staat.
- **Systeemrol**: `"Je bent een OER-assistent voor [opleiding] ([instelling]). Antwoord uitsluitend op basis van de aangeleverde OER-passages."`

## Gebruikersinterface

### Algemeen
- Mobile-first, responsive. Geen sidebar — volledig verborgen via CSS.
- Navigatie via vaste topbalk (`render_nav()`), zelfde patroon als samenwijzer.
- EduPulse huisstijl CSS uit `styles.py`.

### Chat-layout (aanpak A — boven/onder)
Per antwoord:
1. AI-antwoord (gestreamd via `st.write_stream()`, opgeslagen in `session_state`)
2. Bronpassages als kaartjes direct eronder — op mobiel gestapeld, op desktop in 2-koloms grid
3. Invoerregel voor vervolgvraag onderaan

### Student-navigatie
| Pagina | Inhoud |
|---|---|
| OER-assistent | Hybride chat — hoofdpagina |
| Mijn OER | Volledig OER inzien (PDF-viewer of download) |
| Mijn voortgang | Kerntaken, werkprocessen, BSA, aanwezigheid |

### Mentor-navigatie
| Pagina | Inhoud |
|---|---|
| Mijn studenten | Overzicht alle studenten met voortgang/BSA-badges → klik opent sessie |
| Begeleidingssessie | Links: studentprofiel (voortgang, BSA, kerntaakscores, bespreekpunten). Rechts: OER-assistent in context van die student. Op mobiel: profiel inklapbaar bovenaan. |

### Begeleidingssessie-context
- Actieve student wordt opgeslagen in `st.session_state["actieve_student"]`.
- Chat-prompt bevat automatisch de OER van de actieve student.
- Profiel toont: voortgangsbar, BSA%, ongeoorloofde afwezigheid, kerntaakscores, automatische bespreekpuntsuggesties (lage scores, afwezigheid).

## Authenticatie

- Login via `app/main.py` met studentnummer (student) of naam (mentor) + wachtwoord.
- Wachtwoord SHA-256 gehashed opgeslagen in SQLite.
- `st.session_state`-sleutels na login: `rol`, `gebruiker_id`, `oer_id` (student) of `oer_ids` (mentor).
- Rolcontrole via `auth.vereist_student()` en `auth.vereist_mentor()` bovenaan elke pagina.

## Omgeving (.env)

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

## Sprint 1 scope

**In scope:**
- SQLite database-setup met volledig datamodel
- Seed-script met testgebruikers (3 studenten, 2 mentoren, gesynthetiseerde scores)
- OER-ingestie CLI voor alle 5 instellingen
- Inlogscherm (student / mentor)
- OER-assistent (hybride chat, doorvragen, bronpassages)
- Volledig OER raadplegen (PDF viewer / download)
- Studentvoortgang-pagina
- Mentor: studentenoverzicht + begeleidingssessie

**Buiten scope (later):**
- Beheerinterface voor gebruikersbeheer
- Meerdere bronnen naast OER
- WhatsApp-integratie
- Outreach en campagnes
- Chat-persistentie in database
