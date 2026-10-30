"""ChatContext/Sessie: één eigenaar voor de chat-context, plus de guards eromheen."""

from __future__ import annotations

import json
import os

import pytest

from app_fastapi import sessie as sessie_mod
from app_fastapi.context import ChatContext
from app_fastapi.sessie import Sessie
from validatie_samenwijzer import db

_WW = os.environ.get("ALGEMEEN_WACHTWOORD", "")


def _client():
    from fastapi.testclient import TestClient

    from app_fastapi.main import app

    c = TestClient(app)
    c.post("/toegang", data={"wachtwoord": _WW})
    return c


@pytest.fixture
def oer_db(tmp_path, monkeypatch):
    """Tijdelijke DB met twee geïndexeerde en één niet-geïndexeerde Kok-OER."""
    pad = tmp_path / "t.db"
    conn = db.get_connection(pad)
    db.init_db(conn)
    inst = db.voeg_instelling_toe(conn, "talland", "Talland College")
    ids = {}
    for sleutel, leerweg, cohort in (
        ("a", "BOL", "2025"),
        ("b", "BBL", "2025"),
        ("x", "BOL", "2024"),
    ):
        ids[sleutel] = db.voeg_oer_document_toe(
            conn, inst, "Kok", "25168", cohort, leerweg, f"{sleutel}.pdf"
        )
    db.markeer_geindexeerd(conn, ids["a"])
    db.markeer_geindexeerd(conn, ids["b"])
    monkeypatch.setenv("DB_PATH", str(pad))
    return ids


# ── Sessie.laad_context ────────────────────────────────────────────────────────
def test_sessie_laad_context_zet_velden_en_wist_melding_en_wachtende_vraag():
    s = Sessie(
        melding="oude melding",
        wachtende_vraag="oude vraag",
        oer_onleesbaar=True,
        chat_history=[{"role": "user", "content": "hoi"}],
    )
    s.laad_context(ChatContext("SYS", ["lbl"], ["d.nl"], False, "", [4, 5]))

    assert (s.oer_systeem, s.oer_labels, s.domeinen) == ("SYS", ["lbl"], ["d.nl"])
    assert (s.oer_onleesbaar, s.melding, s.oer_ids) == (False, "", [4, 5])
    assert s.wachtende_vraag is None
    assert s.chat_history == [{"role": "user", "content": "hoi"}]  # historie blijft


def test_sessie_laad_context_kopieert_lijsten():
    ctx = ChatContext("S", ["l"], ["d"], False, "", [1])
    s = Sessie()
    s.laad_context(ctx)
    s.oer_labels.append("extra")
    assert ctx.labels == ["l"]


def test_mentorwissel_wist_oude_melding_en_historie(monkeypatch, stub_context):
    from fastapi.responses import PlainTextResponse

    import app_fastapi.main as m

    aanroepen = stub_context(systeem="MENTOR", melding="")
    s = Sessie(
        toegang=True,
        rol="mentor",
        gebruiker={"id": 5, "naam": "Mentor"},
        melding="oude melding van vorige student",
        chat_history=[{"role": "user", "content": "vraag over vorige student"}],
    )
    monkeypatch.setattr(m, "get_sessie", lambda request: s)
    monkeypatch.setattr(m.data, "studenten_van_mentor", lambda mid: [{"id": 7}])
    monkeypatch.setattr(m.data, "profiel_van_student", lambda sid: {"oer_id": 3})
    monkeypatch.setattr(m.templates, "TemplateResponse", lambda *a, **k: PlainTextResponse("ok"))

    r = _client().get("/mentor/student/7")

    assert r.status_code == 200
    assert aanroepen == [[3]]
    assert s.melding == ""
    assert s.chat_history == []
    assert (s.oer_systeem, s.oer_ids) == ("MENTOR", [3])


def test_studentlogin_laadt_context_via_sessie(monkeypatch, stub_context):
    import app_fastapi.main as m

    aanroepen = stub_context(systeem="STUDENT", melding="documenten weggelaten")
    s = Sessie(toegang=True, melding="stale")
    monkeypatch.setattr(m, "get_sessie", lambda request: s)
    monkeypatch.setattr(
        m,
        "auth_student",
        lambda ident, ww: {"id": 1, "naam": "S", "studentnummer": "123", "oer_id": 9},
    )

    r = _client().post(
        "/login",
        data={"rol": "student", "identifier": "123", "wachtwoord": "x"},
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert aanroepen == [[9]]
    assert (s.oer_systeem, s.oer_ids, s.melding) == ("STUDENT", [9], "documenten weggelaten")


# ── /api/kies: id-guard ────────────────────────────────────────────────────────
def _kies(monkeypatch, stub_context, ids, body=None):
    import app_fastapi.main as m

    aanroepen = stub_context(stub_guard=False)
    s = Sessie(toegang=True, wachtende_vraag="wachtende vraag")
    monkeypatch.setattr(m, "get_sessie", lambda request: s)
    r = _client().post("/api/kies", json=body if body is not None else {"oer_ids": ids})
    return r, s, aanroepen


def test_kies_weigert_onbekend_en_niet_geindexeerd_id(oer_db, monkeypatch, stub_context):
    r, s, aanroepen = _kies(monkeypatch, stub_context, [99_999, oer_db["x"]])

    assert r.status_code == 400
    assert r.json() == {"error": "ongeldige oer_ids"}
    assert aanroepen == []
    assert s.oer_ids == [] and s.wachtende_vraag == "wachtende vraag"


def test_kies_weigert_ontbrekende_of_ongeldige_lijst(oer_db, monkeypatch, stub_context):
    for body in ({}, {"oer_ids": "1"}, {"oer_ids": ["a", None, True]}, {"oer_ids": []}):
        r, _, aanroepen = _kies(monkeypatch, stub_context, [], body=body)
        assert r.status_code == 400, body
        assert aanroepen == []


def test_kies_accepteert_kiezer_ids_zonder_voorafgaande_vraag(oer_db, monkeypatch, stub_context):
    """De publieke kiezer POST ids uit opleidingen_boom() direct; die zijn alleen geïndexeerd."""
    ids = [oer_db["a"], oer_db["b"]]
    r, s, aanroepen = _kies(monkeypatch, stub_context, ids)

    assert r.status_code == 200
    assert r.json()["oer_ids"] == ids
    assert aanroepen == [ids]
    assert s.oer_ids == ids
    assert s.wachtende_vraag is None


def test_kies_filtert_ongeldige_ids_weg(oer_db, monkeypatch, stub_context):
    r, s, aanroepen = _kies(monkeypatch, stub_context, [99_999, oer_db["a"], oer_db["x"]])

    assert r.status_code == 200
    assert aanroepen == [[oer_db["a"]]]
    assert s.oer_ids == [oer_db["a"]]


def test_kies_kapt_op_drie_geldige_ids(oer_db, monkeypatch, stub_context):
    ids = [oer_db["a"], oer_db["b"], oer_db["a"], oer_db["b"]]
    _, s, _ = _kies(monkeypatch, stub_context, ids)
    assert len(s.oer_ids) == 3


def test_geweigerde_kies_opent_bronbestand_niet(oer_db, monkeypatch, stub_context):
    """Het omzeilen van de sessie-guard op /api/oer/{id}/bestand via /api/kies is dicht."""
    import app_fastapi.main as m

    _kies(monkeypatch, stub_context, [oer_db["x"]])  # geweigerd
    s = Sessie(toegang=True)
    monkeypatch.setattr(m, "get_sessie", lambda request: s)
    assert _client().get(f"/api/oer/{oer_db['x']}/bestand").status_code == 403


# ── /api/vraag: alleen geïndexeerde kandidaten ─────────────────────────────────
def test_vraag_negeert_niet_geindexeerde_oers(oer_db, monkeypatch, stub_context):
    """'Kok BOL 2024' matcht alleen de niet-geïndexeerde OER; die mag geen kandidaat zijn."""
    import app_fastapi.main as m

    aanroepen = stub_context()
    s = Sessie(toegang=True)
    monkeypatch.setattr(m, "get_sessie", lambda request: s)

    r = _client().post("/api/vraag", json={"vraag": "Kok BOL 2024"})

    body = r.json()
    ids = {o["id"] for o in body.get("opties", [])} | set(body.get("oer_ids", []))
    assert oer_db["x"] not in ids
    assert oer_db["x"] not in [i for call in aanroepen for i in call]


def test_kiesbare_oers_bevat_alleen_geindexeerd(oer_db):
    from app_fastapi import data

    assert {o["id"] for o in data.kiesbare_oers()} == {oer_db["a"], oer_db["b"]}


# ── (de)serialisatie ───────────────────────────────────────────────────────────
@pytest.fixture
def sessie_store(tmp_path, monkeypatch):
    monkeypatch.setattr(sessie_mod, "_DB_PAD", str(tmp_path / "sessies.db"))
    sessie_mod._reset_store_voor_test()
    yield
    sessie_mod._reset_store_voor_test()


def _zet_raw(sid, data):
    sessie_mod._store().execute(
        "INSERT INTO sessies (sid, data, laatst_gebruikt) VALUES (?, ?, 9999999999)",
        (sid, data if isinstance(data, str) else json.dumps(data)),
    )
    sessie_mod._store().commit()


def test_laad_tolereert_oude_velden_en_vult_ontbrekende_aan(sessie_store):
    # Rij van vóór deze refactor: bevat `kandidaten` + `actieve_student`, mist `melding`.
    _zet_raw(
        "oud",
        {
            "chat_history": [{"role": "user", "content": "hoi"}],
            "oer_systeem": "SYS",
            "oer_ids": [3],
            "kandidaten": [{"id": 1, "opleiding": "Kok"}],
            "actieve_student": {"id": 7},
            "toegang": True,
            "onbekend_toekomstig_veld": 1,
        },
    )

    s = sessie_mod.laad("oud")

    assert s is not None
    assert s.oer_systeem == "SYS" and s.oer_ids == [3] and s.toegang is True
    assert s.melding == "" and s.domeinen == []
    assert not hasattr(s, "kandidaten") and not hasattr(s, "actieve_student")


def test_laad_geeft_none_bij_onleesbare_rij(sessie_store):
    _zet_raw("kapot", "{geen json")
    _zet_raw("lijst", "[1, 2]")
    assert sessie_mod.laad("kapot") is None
    assert sessie_mod.laad("lijst") is None
    assert sessie_mod.laad("bestaat-niet") is None


def test_bewaar_en_laad_roundtrip(sessie_store):
    s = Sessie(toegang=True)
    s.laad_context(ChatContext("SYS", ["l"], ["d.nl"], True, "m", [2]))
    sessie_mod.bewaar("sid1", s)
    assert sessie_mod.laad("sid1") == s
