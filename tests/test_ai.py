"""Tests voor _ai.vriendelijke_fout."""

from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from samenwijzer._ai import vriendelijke_fout


def _maak_status_error(status_code: int) -> anthropic.APIStatusError:
    """Bouw een APIStatusError met een specifieke status code (zonder echte HTTP-call)."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = {}
    return anthropic.APIStatusError("test", response=response, body=None)


def test_timeout_error():
    e = anthropic.APITimeoutError(request=MagicMock())
    assert "reageert niet" in vriendelijke_fout(e)


def test_overloaded_529():
    e = _maak_status_error(529)
    assert "overbelast" in vriendelijke_fout(e)


def test_server_error_5xx():
    e = _maak_status_error(503)
    melding = vriendelijke_fout(e)
    assert "503" in melding
    assert "server" in melding.lower()


def test_unknown_status_code():
    e = _maak_status_error(418)
    melding = vriendelijke_fout(e)
    assert "418" in melding


def test_bad_request_error():
    e = anthropic.BadRequestError("bad", response=MagicMock(), body=None)
    melding = vriendelijke_fout(e)
    assert "ongeldig" in melding.lower()


def test_unknown_exception_includes_class_name():
    melding = vriendelijke_fout(ValueError("iets vreemds"))
    assert "ValueError" in melding


@pytest.mark.parametrize(
    "exc_factory,kernwoord",
    [
        (lambda: anthropic.AuthenticationError("auth", response=MagicMock(), body=None), ".env"),
        (lambda: anthropic.RateLimitError("rate", response=MagicMock(), body=None), "Te veel"),
        (lambda: anthropic.APIConnectionError(request=MagicMock()), "verbinding"),
    ],
)
def test_specifieke_klassen(exc_factory, kernwoord):
    assert kernwoord in vriendelijke_fout(exc_factory())
