# Quality Score

Tracks coverage and quality gaps per domain. Updated by the doc-gardening agent.

| Domain | Test coverage | Docs | Last verified |
|---|---|---|---|
| prepare | 100% | complete | 2026-04-24 |
| transform | 100% | complete | 2026-04-24 |
| analyze | 97% | complete | 2026-04-24 |
| visualize | 100% | complete | 2026-04-24 |
| export | 0% | stub | — |
| auth | 100% | complete | 2026-04-24 |
| outreach | 74% | complete | 2026-04-24 |
| outreach_store | 97% | complete | 2026-04-24 |
| welzijn | 100% | complete | 2026-04-24 |
| wellbeing | 100% | complete | 2026-04-24 |
| whatsapp | 80% | complete | 2026-04-24 |
| whatsapp_store | 100% | complete | 2026-04-24 |
| scheduler | 98% | complete | 2026-04-24 |
| _ai | 100% | complete | 2026-04-24 |
| styles | 0% | complete | 2026-04-24 |
| tutor | 100% | complete | 2026-04-24 |
| coach | 100% | complete | 2026-04-24 |
| architecture | 100% | n/a | 2026-04-24 |
| app/webhook | ~90% | complete | 2026-04-24 |
| app/UI | n/a | complete | 2026-04-24 |

**Totaal:** 92% (src/samenwijzer) — 325 tests, 5 overgeslagen (permission-tests bij root).

## Notes

- Coverage gemeten met `uv run pytest` (325 tests, 5 skipped als root — 2026-04-24).
- `export` heeft 0% coverage — stub implementatie (`NotImplementedError`), nog niet klaar om te testen.
- `styles` heeft 0% coverage — puur CSS/HTML-constanten, geen testbare logica.
- `outreach` op 74%: `email_config_uit_env()` (regel 135) en de SMTP-verbindingscode in `verstuur_email()` (regels 166-174) worden niet geraakt in unit tests (vereisen echte SMTP-server).
- `outreach_store` op 97%: `_verbinding()` context manager body (regels 25-27) en één indirect pad (regel 124) niet gedekt — verwaarloosbaar.
- `whatsapp` op 80%: Twilio API-aanroepen en `stuur_checkin()`-internals niet gedekt (vereisen externe service). Parseerlogica, foutpaden, encryptie en score-verwerking volledig gedekt.
- `scheduler` op 98%: enkel regel 99 (`if __name__ == "__main__"`) niet gedekt — niet testbaar als module-import.
- `app/webhook`: gedekt via FastAPI `TestClient` in `tests/test_webhook.py`; buiten `--cov=src/samenwijzer` scope.
