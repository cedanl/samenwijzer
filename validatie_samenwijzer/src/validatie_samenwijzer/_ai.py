"""Gedeelde Anthropic API-client helper."""

from os import environ

import anthropic


def _client(api_key: str | None = None) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key or environ.get("ANTHROPIC_API_KEY"))
