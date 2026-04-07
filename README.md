# Samenwijzer

Python app die AI en Data gebruikt om studenten te ondersteunen bij het leren.

## Installation

```bash
# Requires uv (https://docs.astral.sh/uv/)
uv sync
```

## Usage

```bash
uv run streamlit run app/main.py
```

Open http://localhost:8501 in your browser.

## Development

### Devcontainer

Open the repository in VS Code and choose **Reopen in Container**.

### Tests

```bash
uv run pytest
```

### Linting

```bash
uv run ruff check .
uv run ruff format .
```

## License

MIT
