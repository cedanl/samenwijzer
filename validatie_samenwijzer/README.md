# Validatie Samenwijzer

Standalone Streamlit-app waarmee MBO-studenten en mentoren kunnen chatten met hun OER (Onderwijs- en Examenregeling) via hybride AI-retrieval (ChromaDB + Claude streaming).

## Vereisten

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- Tesseract OCR (`sudo apt install tesseract-ocr tesseract-ocr-nld`)
- `.env` in de projectmap (zie CLAUDE.md)

## Starten

```bash
uv sync
uv run streamlit run app/main.py
```

De app draait op http://localhost:8501.

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

Zie [CLAUDE.md](CLAUDE.md) voor uitgebreide architectuurdocumentatie.
