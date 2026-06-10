"""Tests voor de FastAPI-POC (publieke OER-chat)."""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from app_fastapi.context import laad_context

load_dotenv()  # OEREN_PAD=../oeren etc. — zoals de app bij opstart doet
_WW = os.environ.get("ALGEMEEN_WACHTWOORD", "")


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
        systeem, _labels, _dom, _onl = laad_context([row["id"]])
        if systeem:
            return row["id"]
    return None


def test_laad_context_lege_lijst():
    # Contract: 4-tuple (systeem, labels, domeinen, oer_onleesbaar).
    assert laad_context([]) == ("", [], [], False)


def test_laad_context_onbekende_id():
    # Een niet-bestaand id levert geen leesbare OER → lege context.
    assert laad_context([99_999_999]) == ("", [], [], False)


def test_laad_context_geeft_systeem_en_label():
    oer_id = _leesbare_oer_id()
    if oer_id is None:
        pytest.skip("Geen geïndexeerde OER met leesbare tekst beschikbaar (DB/oeren afwezig).")
    systeem, labels, domeinen, _ = laad_context([oer_id])
    assert systeem and len(systeem) > 500
    assert len(labels) == 1 and " · " in labels[0]
    assert isinstance(domeinen, list)


def test_laad_context_student_soorten_minstens_zo_breed():
    """Meer instelling-soorten (student) → minstens zoveel context als publiek (examenreglement)."""
    from app_fastapi.context import STUDENT_SOORTEN

    oer_id = _leesbare_oer_id()
    if oer_id is None:
        pytest.skip("Geen geïndexeerde OER met leesbare tekst beschikbaar.")
    publiek, _, _, _ = laad_context([oer_id])
    student, _, _, _ = laad_context([oer_id], STUDENT_SOORTEN)
    assert len(student) >= len(publiek)


def test_laad_context_onleesbare_oer_via_kd(monkeypatch):
    """Een OER zonder leesbare tekst maar mét KD levert tóch context + oer_onleesbaar=True."""
    import app_fastapi.context as ctx

    fake_row = {
        "id": 1,
        "crebo": "25168",
        "opleiding": "Gastheer",
        "display_naam": "Da Vinci",
        "naam": "davinci",
        "leerweg": "BBL",
        "cohort": "2025",
        "instelling_id": 2,
        "bestandspad": "x.pdf",
    }
    monkeypatch.setattr(ctx, "_oer_blok", lambda oid: (fake_row, ""))
    monkeypatch.setattr(ctx, "laad_kwalificatiedossier_tekst", lambda c: "KD-INHOUD")
    monkeypatch.setattr(ctx, "laad_skills_tekst", lambda c: "")
    monkeypatch.setattr(ctx.db, "haal_instelling_document_op", lambda *a, **k: None)
    monkeypatch.setattr(ctx, "web_zoek_domeinen", lambda items: [])

    systeem, labels, domeinen, onleesbaar = laad_context([1])
    assert "KD-INHOUD" in systeem
    assert onleesbaar is True
    assert len(labels) == 1


def test_laad_context_leesbare_oer_niet_onleesbaar(monkeypatch):
    import app_fastapi.context as ctx

    fake_row = {
        "id": 1,
        "crebo": "25168",
        "opleiding": "Gastheer",
        "display_naam": "Da Vinci",
        "naam": "davinci",
        "leerweg": "BBL",
        "cohort": "2025",
        "instelling_id": 2,
        "bestandspad": "x.pdf",
    }
    monkeypatch.setattr(ctx, "_oer_blok", lambda oid: (fake_row, "ECHTE OER-TEKST"))
    monkeypatch.setattr(ctx, "laad_kwalificatiedossier_tekst", lambda c: "")
    monkeypatch.setattr(ctx, "laad_skills_tekst", lambda c: "")
    monkeypatch.setattr(ctx.db, "haal_instelling_document_op", lambda *a, **k: None)
    monkeypatch.setattr(ctx, "web_zoek_domeinen", lambda items: [])

    systeem, labels, domeinen, onleesbaar = laad_context([1])
    assert "ECHTE OER-TEKST" in systeem
    assert onleesbaar is False


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


# ── sessiestore (SQLite, write-through + TTL) ───────────────────────────────────
def test_sessiestore_bewaart_en_laadt(tmp_path, monkeypatch):
    from app_fastapi import sessie as sessie_mod

    monkeypatch.setattr(sessie_mod, "_DB_PAD", str(tmp_path / "sessies.db"))
    sessie_mod._reset_store_voor_test()
    s = sessie_mod.Sessie()
    s.oer_systeem = "PROMPT"
    s.oer_ids = [1, 2]
    s.voeg_beurt_toe("vraag", "antwoord")
    sessie_mod.bewaar("sid-1", s)

    geladen = sessie_mod.laad("sid-1")
    assert geladen is not None
    assert geladen.oer_systeem == "PROMPT"
    assert geladen.oer_ids == [1, 2]
    assert geladen.chat_history == [
        {"role": "user", "content": "vraag"},
        {"role": "assistant", "content": "antwoord"},
    ]


def test_sessiestore_laad_onbekende_sid_is_none(tmp_path, monkeypatch):
    from app_fastapi import sessie as sessie_mod

    monkeypatch.setattr(sessie_mod, "_DB_PAD", str(tmp_path / "sessies.db"))
    sessie_mod._reset_store_voor_test()
    assert sessie_mod.laad("bestaat-niet") is None


def test_sessiestore_ttl_verwijdert_verouderd(tmp_path, monkeypatch):
    from app_fastapi import sessie as sessie_mod

    monkeypatch.setattr(sessie_mod, "_DB_PAD", str(tmp_path / "sessies.db"))
    monkeypatch.setattr(sessie_mod, "_TTL_SECONDEN", 100)
    sessie_mod._reset_store_voor_test()
    klok = [1_000_000.0]
    monkeypatch.setattr(sessie_mod.time, "time", lambda: klok[0])
    sessie_mod.bewaar("oud", sessie_mod.Sessie())
    klok[0] += 200  # voorbij de TTL
    sessie_mod.bewaar("nieuw", sessie_mod.Sessie())  # triggert lazy opruiming
    assert sessie_mod.laad("oud") is None
    assert sessie_mod.laad("nieuw") is not None


def test_get_sessie_write_through_round_trip(tmp_path, monkeypatch):
    """get_sessie + bewaar_sessie: een tweede request met dezelfde sid krijgt de state terug."""
    from types import SimpleNamespace

    from app_fastapi import sessie as sessie_mod

    monkeypatch.setattr(sessie_mod, "_DB_PAD", str(tmp_path / "s.db"))
    sessie_mod._reset_store_voor_test()

    req1 = SimpleNamespace(session={}, state=SimpleNamespace())
    s1 = sessie_mod.get_sessie(req1)
    s1.toegang = True
    sessie_mod.bewaar_sessie(req1)
    sid = req1.session["sid"]

    req2 = SimpleNamespace(session={"sid": sid}, state=SimpleNamespace())
    s2 = sessie_mod.get_sessie(req2)
    assert s2.toegang is True


def test_session_secret_verplicht(monkeypatch):
    """Zonder SESSION_SECRET moet het opzetten van de app falen (fail-closed)."""
    import importlib

    import app_fastapi.main as main_mod

    monkeypatch.delenv("SESSION_SECRET", raising=False)
    try:
        with pytest.raises(RuntimeError, match="SESSION_SECRET"):
            importlib.reload(main_mod)
    finally:
        # Herstel een werkende module voor de overige tests.
        monkeypatch.setenv("SESSION_SECRET", "test-secret")
        importlib.reload(main_mod)


def test_read_only_get_bewaart_niet(tmp_path, monkeypatch):
    """Lost-update-fix: een read-only GET schrijft de sessie niet terug; mutaties wel."""
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    monkeypatch.setattr("app_fastapi.sessie._DB_PAD", str(tmp_path / "s.db"))
    import app_fastapi.sessie as sessie_mod

    sessie_mod._reset_store_voor_test()
    from fastapi.testclient import TestClient

    from app_fastapi.main import app

    client = TestClient(app)
    client.post("/toegang", data={"wachtwoord": _WW})  # toegang verleend + (echt) bewaard

    saves: list[str] = []
    monkeypatch.setattr(sessie_mod, "bewaar", lambda sid, s: saves.append(sid))
    client.get("/")  # read-only → géén save
    assert saves == []
    client.post("/api/reset")  # mutaterend → wél save
    assert len(saves) == 1


# ── api (geen AI-call) ─────────────────────────────────────────────────────────
def _client():
    """TestClient die al door de algemene toegangspoort is (gedeeld wachtwoord)."""
    from fastapi.testclient import TestClient

    from app_fastapi.main import app

    c = TestClient(app)
    c.post("/toegang", data={"wachtwoord": _WW})
    return c


def test_toegangspoort_blokkeert_zonder_wachtwoord():
    from fastapi.testclient import TestClient

    from app_fastapi.main import app

    c = TestClient(app)  # geen toegang
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/toegang"
    assert c.post("/api/reset").status_code == 401


def test_api_index_serveert_landing():
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    r = _client().get("/")
    assert r.status_code == 200 and "/static/app.css" in r.text


def test_api_vraag_zonder_match_geeft_intake():
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    r = _client().post("/api/vraag", json={"vraag": "zxcvqwer onbekende instelling blabla"})
    assert r.status_code == 200 and r.json()["modus"] == "intake"


def test_api_reset_ok():
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    r = _client().post("/api/reset")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_api_geschiedenis_geeft_beurten():
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    r = _client().get("/api/geschiedenis")
    assert r.status_code == 200 and r.json() == {"beurten": []}


# ── auth / ingelogde pagina's (skip als seed-DB ontbreekt) ─────────────────────
def _student_met_mentor():
    """(studentnummer, student_id, mentor_naam, mentor_id) of None."""
    import os

    from validatie_samenwijzer import db

    db_path = os.environ.get("DB_PATH", "data/validatie.db")
    if not os.path.exists(db_path):
        return None
    conn = db.get_connection(db_path)
    row = conn.execute(
        """SELECT s.studentnummer, s.id AS sid, m.naam AS mnaam, m.id AS mid
           FROM studenten s JOIN mentoren m ON m.id = s.mentor_id LIMIT 1"""
    ).fetchone()
    return tuple(row) if row else None


def test_login_student_en_paginas():
    info = _student_met_mentor()
    if info is None:
        pytest.skip("Seed-DB ontbreekt.")
    studentnummer = info[0]
    c = _client()
    r = c.post(
        "/login",
        data={"rol": "student", "identifier": studentnummer, "wachtwoord": "Welkom123"},
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"] == "/student"
    assert c.get("/student").status_code == 200
    assert c.get("/student/voortgang").status_code == 200
    assert c.get("/student/studiegids").status_code == 200


def test_login_fout_wachtwoord_redirect():
    info = _student_met_mentor()
    if info is None:
        pytest.skip("Seed-DB ontbreekt.")
    r = _client().post(
        "/login",
        data={"rol": "student", "identifier": info[0], "wachtwoord": "fout"},
        follow_redirects=False,
    )
    assert r.headers["location"] == "/login?fout=1"


def test_mentor_idor_guard():
    info = _student_met_mentor()
    if info is None:
        pytest.skip("Seed-DB ontbreekt.")
    import os

    from validatie_samenwijzer import db

    _, eigen_sid, mnaam, mid = info
    conn = db.get_connection(os.environ.get("DB_PATH", "data/validatie.db"))
    vreemd = conn.execute(
        "SELECT id FROM studenten WHERE mentor_id IS NOT ? OR mentor_id IS NULL LIMIT 1", (mid,)
    ).fetchone()
    c = _client()
    c.post(
        "/login",
        data={"rol": "mentor", "identifier": mnaam, "wachtwoord": "Welkom123"},
        follow_redirects=False,
    )
    assert c.get(f"/mentor/student/{eigen_sid}").status_code == 200  # eigen student → ok
    if vreemd is not None:
        # vreemde student → geweerd (redirect naar /mentor)
        r = c.get(f"/mentor/student/{vreemd['id']}", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/mentor"
