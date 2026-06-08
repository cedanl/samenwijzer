"""Tests voor de FastAPI-POC (publieke OER-chat)."""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from app_fastapi.context import laad_context

load_dotenv()  # OEREN_PAD=../oeren etc. — zoals de app bij opstart doet


def _leesbare_oer_id() -> int | None:
    """Eerste geïndexeerde OER met leesbare tekst, of None (DB/oeren afwezig → skip)."""
    from validatie_samenwijzer import db

    db_path = os.environ.get("DB_PATH", "data/validatie.db")
    if not os.path.exists(db_path):
        return None
    conn = db.get_connection(db_path)
    for row in conn.execute(
        "SELECT id FROM oer_documenten WHERE geindexeerd = 1 ORDER BY id"
    ).fetchall():
        systeem, _labels, _dom = laad_context([row["id"]])
        if systeem:
            return row["id"]
    return None


def test_laad_context_lege_lijst():
    assert laad_context([]) == ("", [], [])


def test_laad_context_onbekende_id():
    # Een niet-bestaand id levert geen leesbare OER → lege context.
    assert laad_context([99_999_999]) == ("", [], [])


def test_laad_context_geeft_systeem_en_label():
    oer_id = _leesbare_oer_id()
    if oer_id is None:
        pytest.skip("Geen geïndexeerde OER met leesbare tekst beschikbaar (DB/oeren afwezig).")
    systeem, labels, domeinen = laad_context([oer_id])
    assert systeem and len(systeem) > 500
    assert len(labels) == 1 and " · " in labels[0]
    assert isinstance(domeinen, list)
