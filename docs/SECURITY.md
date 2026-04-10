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

# SMTP (optional, for outreach email)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=...
SMTP_AFZENDER=noreply@example.com
```

Load with:

```python
from dotenv import load_dotenv
load_dotenv()
```

## SQLite

`outreach.db` stores student contact statuses, intervention logs, campaigns, and wellbeing checks.
It lives in `data/02-prepared/` (gitignored). Never commit it.
All writes go through `outreach_store.py` — never raw SQL in `app/`.

## Wellbeing data

Wellbeing check responses (`welzijnschecks` table) are particularly sensitive.
- Do not display free-text student responses in aggregate dashboards.
- Only the assigned mentor sees individual check details.
- Urgentie level 3 ("Dringend") should prompt the mentor to act promptly.
