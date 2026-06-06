"""Gedeelde Anthropic API-client helper."""

from os import environ

import anthropic
import httpx

APITimeoutError = anthropic.APITimeoutError

# Timeout = 30s read (bij streaming per inter-event → vangt een vastgelopen
# stream zonder een legitiem lang antwoord af te breken), 10s connect.
# max_retries=2 is de SDK-default; expliciet vastgelegd zodat het 30s-contract
# uit CLAUDE.md daadwerkelijk wordt afgedwongen (de SDK-default read is 600s).
_CLIENT_OPTS = {"timeout": httpx.Timeout(30.0, connect=10.0), "max_retries": 2}

_default_client: anthropic.Anthropic | None = None


def _client(api_key: str | None = None) -> anthropic.Anthropic:
    """Maak een Anthropic-client aan; hergebruik de default instantie als geen sleutel opgegeven."""
    global _default_client
    if api_key:
        return anthropic.Anthropic(api_key=api_key, **_CLIENT_OPTS)
    if _default_client is None:
        _default_client = anthropic.Anthropic(
            api_key=environ.get("ANTHROPIC_API_KEY"), **_CLIENT_OPTS
        )
    return _default_client


def _reset_default_client() -> None:
    """Reset de gecachete default-client. Bedoeld voor test-isolatie."""
    global _default_client
    _default_client = None
