# Validatie Samenwijzer

Standalone Streamlit-app waarmee MBO-studenten en mentoren conversationeel kunnen chatten met hun OER (Onderwijs- en Examenregeling) via volledige Claude-documentcontext.

## Vereisten

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- Tesseract OCR (`sudo apt install tesseract-ocr tesseract-ocr-nld`)
- `.env` in de projectmap (zie CLAUDE.md)

## Starten

Uitvoeren vanuit `validatie_samenwijzer/`:

```bash
uv sync
uv run streamlit run app/main.py
```

De app draait op http://localhost:8503.

Inloggen: wachtwoord **Welkom123** voor alle accounts.

| Rol | Inlogwaarde | Instelling |
|---|---|---|
| student | `100001` (Joris Yilmaz) | Talland |
| student | `100201` (Hanna Hoekstra) | Da Vinci College |
| student | `100401` (Eline Vos) | ROC Utrecht |
| mentor | `A. Bakker (25698)` | Talland |
| mentor | `A. Mulder (39665)` | Da Vinci College |
| mentor | `A. Bakker (25655)` | ROC Utrecht |

(De exacte studentnummers en namen volgen uit `seed/bulk_seed.py` met `RNG = random.Random(2026)` toegepast op de huidige geïndexeerde OER-set in `data/validatie.db`. Run `seed/bulk_seed.py` opnieuw om actuele accounts te zien.)

## OERs indexeren én testdata seeden

De volgorde is belangrijk: bulk_seed koppelt studenten aan OER-records die ingest aanmaakt.
Zet daarom eerst je PDFs op de juiste plek en draai dan in volgorde:

```bash
# 1. Zet PDFs in oeren/<instelling_naam>/ (utrecht_oeren, davinci_oeren, …)
# 2. Bestandsnamen aanvullen met crebo/leerweg/cohort + indexeren
./tools/verwerk_oers.sh              # hernoem + indexeer (productie)
./tools/verwerk_oers.sh --preview    # droge run

# 3. Synthetische gebruikers seeden (vereist een geïndexeerde DB)
uv run python seed/seed.py           # 3 studenten + 2 mentoren (sanity check)
uv run python seed/bulk_seed.py      # ~600 studenten over geïndexeerde OERs
```

`bulk_seed` faalt met instructie als stap 2 niet is gedraaid. Het rapporteert
expliciet welke instellingen overgeslagen zijn (typisch wanneer
`extraheer_kerntaken` regex geen kerntaken uit de PDF kan halen) — dan
ontbreekt voor die instelling testdata zonder dat dat stilletjes wordt
verstopt achter wezen-koppelingen.

## Tests en kwaliteit

```bash
uv sync --extra dev && uv run pytest
uv run ruff check src/ app/
```

## Pagina-overzicht

| Pagina | Rol | Functie |
|---|---|---|
| Login (`main.py`) | beide | Studentnummer of mentornaam + wachtwoord |
| `0_oer_vraag.py` | publiek | Conversationele OER-vraag zonder inlogvereiste |
| `1_oer_assistent.py` | student | Chat met eigen OER via volledige documentcontext |
| `2_mijn_oer.py` | student | Volledig OER inzien of downloaden |
| `3_mijn_voortgang.py` | student | Voortgang, BSA, scores visualiseren |
| `4_mijn_studenten.py` | mentor | Studentenlijst van eigen koppeling |
| `5_begeleidingssessie.py` | mentor | Studentprofiel + OER-chat + OER-viewer |

Zie [CLAUDE.md](CLAUDE.md) voor uitgebreide architectuurdocumentatie.
