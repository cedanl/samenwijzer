"""ChatContext/Sessie: één eigenaar voor de chat-context, plus de guards eromheen."""

from __future__ import annotations

import json

import pytest

from app_fastapi.context import ChatContext
from app_fastapi.sessie import Sessie, SessieStore
from validatie_samenwijzer.gesprek import Gesprek


@pytest.fixture
def oer_db(seed):
    """In-memory DB met twee geïndexeerde en één niet-geïndexeerde Kok-OER."""
    return {
        sleutel: seed.oer(
            "Kok", crebo="25168", leerweg=leerweg, cohort=cohort, geindexeerd=sleutel != "x"
        )
        for sleutel, leerweg, cohort in (
            ("a", "BOL", "2025"),
            ("b", "BBL", "2025"),
            ("x", "BOL", "2024"),
        )
    }


# ── Sessie.laad_context ────────────────────────────────────────────────────────
def test_sessie_laad_context_zet_velden_en_wist_melding_en_wachtende_vraag():
    s = Sessie(
        melding="oude melding",
        wachtende_vraag="oude vraag",
        oer_onleesbaar=True,
        gesprek=Gesprek.van_lijst([{"role": "user", "content": "hoi"}]),
    )
    s.laad_context(ChatContext("SYS", ["lbl"], ["d.nl"], False, "", [4, 5]))

    assert (s.oer_systeem, s.oer_labels, s.domeinen) == ("SYS", ["lbl"], ["d.nl"])
    assert (s.oer_onleesbaar, s.melding, s.oer_ids) == (False, "", [4, 5])
    assert s.wachtende_vraag is None
    assert s.gesprek.naar_lijst() == [{"role": "user", "content": "hoi"}]  # gesprek blijft


def test_sessie_laad_context_kopieert_lijsten():
    ctx = ChatContext("S", ["l"], ["d"], False, "", [1])
    s = Sessie()
    s.laad_context(ctx)
    s.oer_labels.append("extra")
    assert ctx.labels == ["l"]


def test_mentorwissel_wist_oude_melding_en_historie(seed, maak_client, stub_context):
    oer_id = seed.oer()
    mentor_id = seed.mentor("Mentor")
    student_id = seed.student("100001", oer_id, mentor_id)
    aanroepen = stub_context(systeem="MENTOR", melding="")
    s = Sessie(
        toegang=True,
        rol="mentor",
        gebruiker={"id": mentor_id, "naam": "Mentor"},
        melding="oude melding van vorige student",
        gesprek=Gesprek.van_lijst([{"role": "user", "content": "vraag over vorige student"}]),
    )

    r = maak_client(s).get(f"/mentor/student/{student_id}")

    assert r.status_code == 200
    assert aanroepen == [[oer_id]]
    assert s.melding == ""
    assert s.gesprek.naar_lijst() == []
    assert (s.oer_systeem, s.oer_ids) == ("MENTOR", [oer_id])


def test_studentlogin_laadt_context_via_sessie(seed, maak_client, stub_context):
    oer_id = seed.oer()
    seed.student("123", oer_id, None)
    aanroepen = stub_context(systeem="STUDENT", melding="documenten weggelaten")
    s = Sessie(toegang=True, melding="stale")

    r = maak_client(s).post(
        "/login",
        data={"rol": "student", "identifier": "123", "wachtwoord": "Welkom123"},
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert aanroepen == [[oer_id]]
    assert (s.oer_systeem, s.oer_ids, s.melding) == ("STUDENT", [oer_id], "documenten weggelaten")


# ── /api/kies: id-guard ────────────────────────────────────────────────────────
def _kies(maak_client, stub_context, ids, body=None):
    aanroepen = stub_context(stub_guard=False)
    s = Sessie(toegang=True, wachtende_vraag="wachtende vraag")
    r = maak_client(s).post("/api/kies", json=body if body is not None else {"oer_ids": ids})
    return r, s, aanroepen


def test_kies_weigert_onbekend_en_niet_geindexeerd_id(oer_db, maak_client, stub_context):
    r, s, aanroepen = _kies(maak_client, stub_context, [99_999, oer_db["x"]])

    assert r.status_code == 400
    assert r.json() == {"error": "ongeldige oer_ids"}
    assert aanroepen == []
    assert s.oer_ids == [] and s.wachtende_vraag == "wachtende vraag"


def test_kies_weigert_ontbrekende_of_ongeldige_lijst(oer_db, maak_client, stub_context):
    for body in ({}, {"oer_ids": "1"}, {"oer_ids": ["a", None, True]}, {"oer_ids": []}):
        r, _, aanroepen = _kies(maak_client, stub_context, [], body=body)
        assert r.status_code == 400, body
        assert aanroepen == []


def test_kies_accepteert_kiezer_ids_zonder_voorafgaande_vraag(oer_db, maak_client, stub_context):
    """De publieke kiezer POST ids uit opleidingen_boom() direct; die zijn alleen geïndexeerd."""
    ids = [oer_db["a"], oer_db["b"]]
    r, s, aanroepen = _kies(maak_client, stub_context, ids)

    assert r.status_code == 200
    assert r.json()["oer_ids"] == ids
    assert aanroepen == [ids]
    assert s.oer_ids == ids
    assert s.wachtende_vraag is None


def test_kies_filtert_ongeldige_ids_weg(oer_db, maak_client, stub_context):
    r, s, aanroepen = _kies(maak_client, stub_context, [99_999, oer_db["a"], oer_db["x"]])

    assert r.status_code == 200
    assert aanroepen == [[oer_db["a"]]]
    assert s.oer_ids == [oer_db["a"]]


def test_kies_ontdubbelt_en_kapt_op_drie_geldige_ids(oer_db, maak_client, stub_context):
    """Dubbele ids laden dezelfde OER niet twee keer (kosten/contextbudget); max. 3 uniek."""
    ids = [oer_db["a"], oer_db["b"], oer_db["a"], oer_db["b"]]
    _, s, _ = _kies(maak_client, stub_context, ids)
    assert s.oer_ids == [oer_db["a"], oer_db["b"]]


def test_geweigerde_kies_opent_bronbestand_niet(oer_db, maak_client, stub_context):
    """Het omzeilen van de sessie-guard op /api/oer/{id}/bestand via /api/kies is dicht."""
    s = Sessie(toegang=True)
    c = maak_client(s)
    assert c.post("/api/kies", json={"oer_ids": [oer_db["x"]]}).status_code == 400  # geweigerd
    assert c.get(f"/api/oer/{oer_db['x']}/bestand").status_code == 403


# ── /api/vraag: alleen geïndexeerde kandidaten ─────────────────────────────────
def test_vraag_negeert_niet_geindexeerde_oers(oer_db, maak_client, stub_context):
    """'Kok BOL 2024' matcht alleen de niet-geïndexeerde OER; die mag geen kandidaat zijn."""
    aanroepen = stub_context()

    r = maak_client(Sessie(toegang=True)).post("/api/vraag", json={"vraag": "Kok BOL 2024"})

    body = r.json()
    ids = {o["id"] for o in body.get("opties", [])} | set(body.get("oer_ids", []))
    assert oer_db["x"] not in ids
    assert oer_db["x"] not in [i for call in aanroepen for i in call]


def test_kiesbare_oers_bevat_alleen_geindexeerd(oer_db, conn):
    from app_fastapi import data

    assert {o["id"] for o in data.kiesbare_oers(conn)} == {oer_db["a"], oer_db["b"]}


# ── (de)serialisatie ───────────────────────────────────────────────────────────
@pytest.fixture
def sessie_store():
    store = SessieStore(":memory:")
    yield store
    store.sluit()


def _zet_raw(store, sid, data):
    store._store().execute(
        "INSERT INTO sessies (sid, data, laatst_gebruikt) VALUES (?, ?, 9999999999)",
        (sid, data if isinstance(data, str) else json.dumps(data)),
    )
    store._store().commit()


def test_laad_tolereert_oude_velden_en_vult_ontbrekende_aan(sessie_store):
    # Rij van vóór deze refactor: bevat `kandidaten` + `actieve_student`, mist `melding`.
    _zet_raw(
        sessie_store,
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

    s = sessie_store.laad("oud")

    assert s is not None
    assert s.oer_systeem == "SYS" and s.oer_ids == [3] and s.toegang is True
    assert s.melding == "" and s.domeinen == []
    assert s.gesprek.naar_lijst() == [{"role": "user", "content": "hoi"}]  # oude opslagvorm
    assert not hasattr(s, "kandidaten") and not hasattr(s, "actieve_student")


def test_laad_geeft_none_bij_onleesbare_rij(sessie_store):
    _zet_raw(sessie_store, "kapot", "{geen json")
    _zet_raw(sessie_store, "lijst", "[1, 2]")
    assert sessie_store.laad("kapot") is None
    assert sessie_store.laad("lijst") is None
    assert sessie_store.laad("bestaat-niet") is None


def test_bewaar_en_laad_roundtrip(sessie_store):
    s = Sessie(toegang=True)
    s.laad_context(ChatContext("SYS", ["l"], ["d.nl"], True, "m", [2]))
    sessie_store.bewaar("sid1", s)
    assert sessie_store.laad("sid1") == s


def test_geldige_oer_ids_ontdubbelt_en_kapt_voor_de_db_call(conn, monkeypatch):
    """[5, 5, 5, 6, 7, 8] → DB krijgt hooguit drie unieke ids (geen 'too many SQL variables',
    geen drie keer dezelfde OER in de catalogus)."""
    from app_fastapi import data

    gezien: list[list[int]] = []

    def _filter(conn, ids):
        gezien.append(list(ids))
        return list(ids)

    monkeypatch.setattr(data.db, "filter_geindexeerde_oer_ids", _filter)
    assert data.geldige_oer_ids(conn, [5, 5, 5, 6, 7, 8, True, "x"]) == [5, 6, 7]
    assert gezien == [[5, 6, 7]]
