"""Gedeelde Anthropic API-client helper."""

from os import environ

import anthropic

APITimeoutError = anthropic.APITimeoutError


def vriendelijke_fout(e: Exception) -> str:
    """Vertaal een Anthropic-API-fout naar een leesbare boodschap voor de UI.

    Stack-trace details horen via `log.exception(...)` in de logs — niet op het scherm.
    """
    if isinstance(e, anthropic.APITimeoutError):
        return "De AI-service reageert niet. Probeer het over een moment opnieuw."
    if isinstance(e, anthropic.APIStatusError) and getattr(e, "status_code", None) == 529:
        return "De AI is even overbelast. Wacht een paar seconden en probeer opnieuw."
    if isinstance(e, anthropic.RateLimitError):
        return "Te veel verzoeken aan de AI-service. Wacht even en probeer opnieuw."
    if isinstance(e, anthropic.AuthenticationError):
        return "API-sleutel ontbreekt of klopt niet. Controleer je .env."
    if isinstance(e, anthropic.APIConnectionError):
        return "Geen verbinding met de AI-service. Controleer je internetverbinding."
    return "Er ging iets mis met de AI-service. Probeer het opnieuw."


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
