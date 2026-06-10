"""Globale pytest-fixtures."""

import os

import pytest

# De FastAPI-app eist SESSION_SECRET (fail-closed) en zet standaard een Secure-cookie;
# de TestClient draait over http, dus de cookie-hardening hier uitschakelen voor de test.
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("COOKIE_HTTPS_ONLY", "0")

from validatie_samenwijzer import _ai  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_ai_client():
    """Voorkom dat een gecachete (mogelijk gemockte) Anthropic-client tussen tests lekt."""
    _ai._reset_default_client()
    yield
    _ai._reset_default_client()
