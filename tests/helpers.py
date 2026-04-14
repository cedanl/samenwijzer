"""Gedeelde test-helpers voor samenwijzer."""

from unittest.mock import MagicMock


def mock_stream(tekst: str) -> MagicMock:
    """Bouw een mock-stream die tekst als één fragment yieldt."""
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    mock.text_stream = iter([tekst])
    return mock
