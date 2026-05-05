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
| student | `100001` (Rick Mulder) | Rijn IJssel |
| student | `100168` (Mohammed Singh) | Da Vinci College |
| mentor | `Hans Klooster` | Rijn IJssel |
| mentor | `Hanneke Dijkman` | Da Vinci College |

## Testdata seeden

```bash
uv run python seed/seed.py        # 3 studenten + 2 mentoren
uv run python seed/bulk_seed.py   # 1000 studenten over alle geïndexeerde OERs
```

## OERs indexeren

```bash
# Zet PDF's in oeren/<instelling_naam>/
./tools/verwerk_oers.sh            # hernoem bestanden + indexeer
./tools/verwerk_oers.sh --preview  # droge run
```

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
