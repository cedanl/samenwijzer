# Quality Score

Tracks coverage and quality gaps per domain. Updated by the doc-gardening agent.

| Domain | Test coverage | Docs | Last verified |
|---|---|---|---|
| prepare | 100% | complete | 2026-04-11 |
| transform | 100% | complete | 2026-04-11 |
| analyze | 97% | complete | 2026-04-11 |
| visualize | 100% | complete | 2026-04-11 |
| export | 0% | stub | — |
| auth | 0% | complete | 2026-04-11 |
| outreach | 46% | complete | 2026-04-11 |
| outreach_store | 97% | complete | 2026-04-11 |
| welzijn | 100% | complete | 2026-04-11 |
| tutor | 100% | complete | 2026-04-11 |
| coach | 100% | complete | 2026-04-11 |
| architecture | 100% | n/a | 2026-04-11 |
| app/UI | n/a | complete | 2026-04-11 |

## Notes

- Coverage measured with `uv run pytest` (172 tests, all passing as of 2026-04-11).
- `export` has 0% coverage — stub implementation, not yet ready to test.
- `outreach_store` at 97%: `_verbinding()` context manager body (lines 25-27) en `_zorg_voor_db` indirect pad (line 124) niet gedekt — verwaarloosbaar.
