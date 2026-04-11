# Tech Debt Tracker

| ID | Description | Domain | Priority | Opened |
|---|---|---|---|---|
| TD-001 | ResourceWarning: unclosed SQLite connections in test suite (`test_prepare.py`). `init_db()` opens connections that are not closed when called indirectly during import. Fix: use `contextlib.closing` or restructure test fixtures. | outreach_store | low | 2026-04-10 |
| TD-002 | `welzijn.py`, `coach.py`, `visualize.py` have 0% test coverage. Need mocked Anthropic SDK tests and/or Altair snapshot tests. | testing | medium | 2026-04-10 |
| TD-003 | `outreach_store.py` Campagne and WelzijnsCheck CRUD paths not covered by existing tests. | testing | medium | 2026-04-10 |
| ~~TD-004~~ | ~~SMTP env var inconsistency~~ — **gesloten 2026-04-11**: geverifieerd geen lingering `AFZENDER_EMAIL` referenties. `SMTP_AFZENDER` is de standaard. | outreach | — | 2026-04-10 |
