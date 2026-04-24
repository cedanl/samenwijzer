# Reliability

## Requirements

- App startup: < 5 seconds cold start.
- AI call timeout: 30 seconds; surface error to user on timeout.
- No unhandled exceptions reach the Streamlit UI — catch at app layer and show a friendly message.

## Testing

- **325 tests** (5 overgeslagen: permission-tests die root vereisen). Totale coverage: 92%.
- Unit tests dekken alle modules in `src/samenwijzer/` — zie `docs/QUALITY_SCORE.md` voor details per domein.
- Schaal-tests (`tests/test_scale.py`) runnen de volledige data-pipeline op 1000 synthetische studenten en verifiëren correctheid van analyze-functies onder realistisch volume.
- Webhook-tests (`tests/test_webhook.py`) testen de FastAPI `/webhook/whatsapp`- en `/health`-endpoints via FastAPI `TestClient` (httpx), inclusief Twilio-handtekeningvalidatie.
- Boundary-tests controleren `PermissionError` bij bestanden zonder leesrechten en mappen zonder schrijfrechten (overgeslagen als root).
- UI tests: handmatig voor v0.1; agent-driven (Chrome DevTools) vanaf v0.2.
