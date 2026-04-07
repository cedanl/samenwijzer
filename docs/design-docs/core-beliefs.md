# Core Beliefs

These principles guide how this repository is built and maintained.

## Agent-first

Every line of code is written by Claude Code. Humans give direction; agents execute.
This is a deliberate constraint to maximise development velocity.

## Repository as source of truth

Knowledge lives in the repository. If it is not in a versioned file, it does not
exist for the agent. Slack threads, Google Docs, and tacit knowledge must be
encoded as markdown before they are actionable.

## AGENTS.md is a map, not a manual

Keep `AGENTS.md` under ~100 lines. It points to deeper sources.
A 1000-page manual crowds out the task and the code.

## Depth-first decomposition

Break large goals into typed building blocks (design, code, test, docs).
Build the block, then use it to enable the next level of complexity.
When the agent fails, ask: "What capability is missing?"

## Enforce architecture mechanically

Rigid layer rules + custom linters > documentation alone.
Hard constraints enable speed without drift.

## Continuous garbage collection

Technical debt is a high-interest loan. Pay it in small daily increments.
Background agents scan for drift, open small PRs, auto-merge.
