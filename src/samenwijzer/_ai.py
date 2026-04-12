"""Gedeelde Anthropic API-client helper."""

from os import environ

import anthropic


def _client(api_key: str | None = None) -> anthropic.Anthropic:
    """Maak een Anthropic-client aan met de opgegeven of omgevings-API-sleutel."""
    return anthropic.Anthropic(api_key=api_key or environ.get("ANTHROPIC_API_KEY"))
