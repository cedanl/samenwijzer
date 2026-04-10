# Quality Score

Tracks coverage and quality gaps per domain. Updated by the doc-gardening agent.

| Domain | Test coverage | Docs | Last verified |
|---|---|---|---|
| prepare | 46% | draft | 2026-04-10 |
| transform | 100% | complete | 2026-04-10 |
| analyze | 46% | complete | 2026-04-10 |
| visualize | 0% | stub | — |
| export | 0% | stub | — |
| auth | 0% | complete | 2026-04-10 |
| outreach | 46% | complete | 2026-04-10 |
| outreach_store | 78% | complete | 2026-04-10 |
| welzijn | 0% | complete | 2026-04-10 |
| tutor | 100% | complete | 2026-04-10 |
| coach | 0% | stub | — |
| app/UI | n/a | complete | 2026-04-10 |

## Notes

- Coverage measured with `uv run pytest` (52 tests, all passing as of 2026-04-10).
- `welzijn`, `visualize`, `coach`, `export` have 0% coverage because they make live API calls
  or write to disk; they need mocked integration tests.
- `outreach_store` at 78%: Campagne and WelzijnsCheck CRUD paths not yet exercised in tests.
