# Security

## Rules

- Never commit secrets. Use `.env` (gitignored) and `python-dotenv`.
- Validate all external inputs at the boundary (file uploads, API responses, webhook payloads).
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

# Twilio WhatsApp (optional, for WhatsApp signalering)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
WHATSAPP_ENCRYPT_KEY=...   # Fernet-sleutel; auto-gegenereerd lokaal als leeg
```

Load with:

```python
from dotenv import load_dotenv
load_dotenv()
```

In production (GitHub Actions), set all secrets via repository secrets — never in `.env` committed to git.

## SQLite

`outreach.db` stores student contact statuses, intervention logs, campaigns, and wellbeing checks.
`whatsapp.db` stores phone registrations (encrypted) and conversation sessions.
Both live in `data/02-prepared/` (gitignored). Never commit them.
All writes go through `outreach_store.py` and `whatsapp_store.py` — never raw SQL in `app/`.

## Phone number encryption

Phone numbers in `whatsapp.db` are encrypted with Fernet (symmetric encryption) before storage.
The key comes from `WHATSAPP_ENCRYPT_KEY` env var, or is auto-generated and stored in
`data/02-prepared/.whatsapp.key` (gitignored). Never commit the key file.

## Webhook security

The FastAPI webhook endpoint (`app/webhook.py`) validates the Twilio request signature on every
inbound message. Requests without a valid `X-Twilio-Signature` header are rejected with HTTP 403.

## Wellbeing data

Wellbeing check responses (`welzijnschecks` table and `welzijn.csv`) are particularly sensitive.
- Do not display free-text student responses in aggregate dashboards.
- Only the assigned mentor sees individual check details.
- Urgentie level 3 ("Dringend") should prompt the mentor to act promptly.
- WhatsApp conversation history is not retained longer than 30 days (AVG compliance).
