# Tech Debt Tracker

| ID | Description | Domain | Priority | Opened |
|---|---|---|---|---|
| ~~TD-001~~ | ~~ResourceWarning: unclosed SQLite connections~~ — **gesloten 2026-04-11**: `_verbinding()` context manager toegevoegd met `conn.close()` in `finally`. | outreach_store | — | 2026-04-10 |
| ~~TD-002~~ | ~~0% coverage op `welzijn.py`, `coach.py`, `visualize.py`~~ — **gesloten 2026-04-11**: 52 tests toegevoegd met gemockte Anthropic SDK; alle drie op 100%. | testing | — | 2026-04-10 |
| ~~TD-003~~ | ~~Campagne en WelzijnsCheck CRUD niet afgedekt~~ — **gesloten 2026-04-11**: 16 tests toegevoegd; `outreach_store.py` op 97%. | testing | — | 2026-04-10 |
| ~~TD-004~~ | ~~SMTP env var inconsistency~~ — **gesloten 2026-04-11**: geverifieerd geen lingering `AFZENDER_EMAIL` referenties. `SMTP_AFZENDER` is de standaard. | outreach | — | 2026-04-10 |
