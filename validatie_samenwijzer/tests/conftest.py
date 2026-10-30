"""Globale pytest-fixtures."""

import os

import pytest

# De FastAPI-app eist SESSION_SECRET (fail-closed) en zet standaard een Secure-cookie;
# de TestClient draait over http, dus de cookie-hardening hier uitschakelen voor de test.
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("COOKIE_HTTPS_ONLY", "0")
os.environ.setdefault("ALGEMEEN_WACHTWOORD", "test-pw")

from validatie_samenwijzer import (
    _ai,  # noqa: E402
    opleiding,  # noqa: E402
)


@pytest.fixture(autouse=True)
def _reset_ai_client():
    """Voorkom dat een gecachete (mogelijk gemockte) Anthropic-client tussen tests lekt."""
    _ai._reset_default_client()
    yield
    _ai._reset_default_client()


@pytest.fixture(autouse=True)
def _reset_crebo_namen_cache():
    """Voorkom dat de lru_cache van de crebo→naam-lookup tussen tests lekt.

    test_opleiding_namen monkeypatcht ``OPLEIDINGSNAMEN_PAD`` naar tijdelijke bestanden;
    zonder reset houdt een latere test (bv. opleidingen_boom) een lege/verkeerde lookup vast.
    """
    opleiding.laad_crebo_namen.cache_clear()
    yield
    opleiding.laad_crebo_namen.cache_clear()


@pytest.fixture
def stub_context(monkeypatch):
    """Vervang ``app_fastapi.main.laad_context`` door een stub die een ``ChatContext`` geeft.

    ``stub_context(systeem="SYS", labels=["l"], domeinen=[], melding="")`` stubt standaard ook
    de id-guard van ``/api/kies`` (``data.geldige_oer_ids``), zodat tests geen echte,
    geïndexeerde OER-id's nodig hebben; ``stub_guard=False`` laat de echte guard staan; ``bron_register`` zet het
    ``BronCatalogus.register()``-register van de context.
    Geeft de lijst terug waarin elke aanroep (oer_ids) wordt vastgelegd.
    """

    def _stub(
        systeem="SYS",
        labels=None,
        domeinen=None,
        oer_onleesbaar=False,
        melding="",
        stub_guard=True,
        bron_register=None,
    ):
        import app_fastapi.main as m
        from app_fastapi.context import ChatContext

        aanroepen: list[list[int]] = []

        def _laad(oer_ids, *a, **k):
            aanroepen.append(list(oer_ids))
            return ChatContext(
                systeem,
                ["label"] if labels is None else labels,
                [] if domeinen is None else domeinen,
                oer_onleesbaar,
                melding,
                list(oer_ids),
                list(bron_register or []),
            )

        monkeypatch.setattr(m, "laad_context", _laad)
        if stub_guard:
            monkeypatch.setattr(m.data, "geldige_oer_ids", lambda ids: list(ids)[:3])
        return aanroepen

    return _stub
