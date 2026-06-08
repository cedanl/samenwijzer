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


# ── sessie ────────────────────────────────────────────────────────────────────
def test_sessie_voeg_beurt_kapt_op_max():
    from app_fastapi.sessie import MAX_GESCHIEDENIS, Sessie

    s = Sessie()
    for i in range(MAX_GESCHIEDENIS):  # elk = 2 berichten → ruim over de cap
        s.voeg_beurt_toe(f"v{i}", f"a{i}")
    assert len(s.chat_history) == MAX_GESCHIEDENIS
    assert s.chat_history[-1]["content"].startswith("a")  # nieuwste behouden


def test_sessie_reset_leegt_alles():
    from app_fastapi.sessie import Sessie

    s = Sessie(oer_systeem="x", oer_labels=["l"], oer_ids=[1])
    s.voeg_beurt_toe("v", "a")
    s.reset()
    assert s.chat_history == [] and s.oer_systeem is None and s.oer_ids == []


# ── api (geen AI-call) ─────────────────────────────────────────────────────────
def _client():
    from fastapi.testclient import TestClient

    from app_fastapi.main import app

    return TestClient(app)


def test_api_index_serveert_landing():
    r = _client().get("/")
    assert r.status_code == 200 and "/static/app.css" in r.text


def test_api_vraag_zonder_match_geeft_intake():
    r = _client().post("/api/vraag", json={"vraag": "zxcvqwer onbekende instelling blabla"})
    assert r.status_code == 200 and r.json()["modus"] == "intake"


def test_api_reset_ok():
    r = _client().post("/api/reset")
    assert r.status_code == 200 and r.json()["ok"] is True
