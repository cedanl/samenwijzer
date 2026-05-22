"""Globale pytest-fixtures."""

import pytest

from samenwijzer import _ai
from samenwijzer.analyze import _kerntaken_voor


@pytest.fixture(autouse=True)
def _reset_ai_client():
    """Voorkom dat een gecachete (mogelijk gemockte) Anthropic-client tussen tests lekt."""
    _ai._reset_default_client()
    yield
    _ai._reset_default_client()


@pytest.fixture(autouse=True)
def _reset_oer_label_cache():
    """Leeg de OER-kerntaken-cache zodat tests met een tijdelijke oeren.db niet lekken."""
    _kerntaken_voor.cache_clear()
    yield
    _kerntaken_voor.cache_clear()
