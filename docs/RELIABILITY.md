# Reliability

## Requirements

- App startup: < 5 seconds cold start.
- AI call timeout: 30 seconds; surface error to user on timeout.
- No unhandled exceptions reach the Streamlit UI — catch at app layer and show a friendly message.

## Testing

- Unit tests cover all functions in `src/samenwijzer/`.
- Integration tests cover the full data pipeline (prepare → export).
- UI tests: manual for v0.1; agent-driven (Chrome DevTools) from v0.2.
