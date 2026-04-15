# Quality Score

Tracks coverage and quality gaps per domain. Updated by the doc-gardening agent.

| Domain | Test coverage | Docs | Last verified |
|---|---|---|---|
| prepare | 100% | complete | 2026-04-15 |
| transform | 100% | complete | 2026-04-15 |
| analyze | 97% | complete | 2026-04-15 |
| visualize | 100% | complete | 2026-04-15 |
| export | 0% | stub | — |
| auth | 0% | complete | 2026-04-15 |
| outreach | 46% | complete | 2026-04-15 |
| outreach_store | 97% | complete | 2026-04-15 |
| welzijn | 100% | complete | 2026-04-15 |
| wellbeing | 100% | complete | 2026-04-15 |
| whatsapp | 80% | complete | 2026-04-15 |
| whatsapp_store | 96% | complete | 2026-04-15 |
| scheduler | 71% | complete | 2026-04-15 |
| _ai | n/a | complete | 2026-04-15 |
| styles | 0% | complete | 2026-04-15 |
| tutor | 100% | complete | 2026-04-15 |
| coach | 100% | complete | 2026-04-15 |
| architecture | 100% | n/a | 2026-04-15 |
| app/UI | n/a | complete | 2026-04-15 |

## Notes

- Coverage measured with `uv run pytest` (246 tests, all passing as of 2026-04-15).
- `export` heeft 0% coverage — stub implementatie, nog niet klaar om te testen.
- `auth` heeft 0% coverage — rolcontroles zijn session_state-afhankelijk, moeilijk unit-testbaar zonder Streamlit-context.
- `styles` heeft 0% coverage — puur CSS/HTML, geen testbare logica.
- `outreach_store` op 97%: `_verbinding()` context manager body (regels 25-27) en `_zorg_voor_db` indirect pad (regel 124) niet gedekt — verwaarloosbaar.
- `whatsapp` op 80%: Twilio API-aanroepen niet gedekt (vereisen externe service). Parseerlogica, foutpaden en score-verwerking volledig gedekt.
- `scheduler` op 71%: productiepaden (Twilio-verzending, ontbrekende env vars) niet gedekt in CI.
