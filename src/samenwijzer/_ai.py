"""Gedeelde Anthropic API-client helper."""

from os import environ

import anthropic

APITimeoutError = anthropic.APITimeoutError

_default_client: anthropic.Anthropic | None = None


def _client(api_key: str | None = None) -> anthropic.Anthropic:
    """Maak een Anthropic-client aan; hergebruik de default instantie als geen sleutel opgegeven."""
    global _default_client
    if api_key:
        return anthropic.Anthropic(api_key=api_key)
    if _default_client is None:
        _default_client = anthropic.Anthropic(api_key=environ.get("ANTHROPIC_API_KEY"))
    return _default_client


def _reset_default_client() -> None:
    """Reset de gecachete default-client. Bedoeld voor test-isolatie."""
    global _default_client
    _default_client = None
