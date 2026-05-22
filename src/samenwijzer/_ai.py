"""Gedeelde Anthropic API-client helper."""

from os import environ

import anthropic

APITimeoutError = anthropic.APITimeoutError

# Standaardmodel voor tutor, coach, outreach en welzijn.
# whatsapp.py kiest bewust een eigen (lichter) model.
MODEL = "claude-sonnet-4-6"


def vriendelijke_fout(e: Exception) -> str:
    """Vertaal een Anthropic-API-fout naar een leesbare boodschap voor de UI.

    Specifieke subklassen eerst (RateLimitError etc. zijn ook APIStatusError);
    voor onbekende fouten wordt de klasnaam meegegeven zodat we kunnen herleiden
    welk geval we nog niet vangen. Stack-trace details horen via `log.exception(...)`
    in de logs — niet op het scherm.
    """
    if isinstance(e, anthropic.APITimeoutError):
        return "De AI-service reageert niet. Probeer het over een moment opnieuw."
    if isinstance(e, anthropic.RateLimitError):
        return "Te veel verzoeken aan de AI-service. Wacht even en probeer opnieuw."
    if isinstance(e, anthropic.AuthenticationError):
        return "API-sleutel ontbreekt of klopt niet. Controleer je .env."
    if isinstance(e, anthropic.APIConnectionError):
        return "Geen verbinding met de AI-service. Controleer je internetverbinding."
    if isinstance(e, anthropic.BadRequestError):
        return "Het verzoek aan de AI is ongeldig. Reset het gesprek en probeer opnieuw."
    if isinstance(e, anthropic.APIStatusError):
        code = getattr(e, "status_code", None)
        if code == 529:
            return "De AI is even overbelast. Wacht een paar seconden en probeer opnieuw."
        if code is not None and 500 <= code < 600:
            return f"De AI-server heeft een fout (HTTP {code}). Probeer het zo opnieuw."
        return f"De AI-service gaf een fout (HTTP {code}). Probeer het opnieuw."
    return f"Er ging iets mis met de AI-service ({type(e).__name__}). Probeer het opnieuw."


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
