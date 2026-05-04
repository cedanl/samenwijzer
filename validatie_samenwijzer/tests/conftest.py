"""Globale pytest-fixtures."""

import pytest

from validatie_samenwijzer import _ai


@pytest.fixture(autouse=True)
def _reset_ai_client():
    """Voorkom dat een gecachete (mogelijk gemockte) Anthropic-client tussen tests lekt."""
    _ai._reset_default_client()
    yield
    _ai._reset_default_client()
