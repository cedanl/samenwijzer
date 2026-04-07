# Security

## Rules

- Never commit secrets. Use `.env` (gitignored) and `python-dotenv`.
- Validate all external inputs at the boundary (file uploads, API responses).
- Do not log PII (student names, IDs) at INFO level or above.
- Dependencies are pinned in `uv.lock`; update via `uv lock --upgrade`.

## Secret management

Store secrets in `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

Load with:
```python
from dotenv import load_dotenv
load_dotenv()
```
