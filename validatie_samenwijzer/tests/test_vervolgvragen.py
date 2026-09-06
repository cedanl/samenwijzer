"""Tests voor `/api/vervolgvragen` — klikbare vervolgvragen na elk antwoord.

Patronen overgenomen uit `tests/test_intake_vervolg.py` (TestClient + toegangspoort,
monkeypatch van `get_sessie` en de AI-aanroep i.p.v. een echte Anthropic-call).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()
_WW = os.environ.get("ALGEMEEN_WACHTWOORD", "")


def _client():
    """TestClient die al door de algemene toegangspoort is (gedeeld wachtwoord)."""
    from fastapi.testclient import TestClient

    from app_fastapi.main import app

    c = TestClient(app)
    c.post("/toegang", data={"wachtwoord": _WW})
    return c


def test_geen_oer_systeem_geeft_lege_lijst_zonder_ai_call(monkeypatch):
    import app_fastapi.main as m
    from app_fastapi.sessie import Sessie

    def _boom(*a, **k):
        raise AssertionError("genereer_vervolgvragen mag niet aangeroepen worden")

    monkeypatch.setattr(m, "genereer_vervolgvragen", _boom)

    s = Sessie(toegang=True)
    monkeypatch.setattr(m, "get_sessie", lambda request: s)

    r = _client().post("/api/vervolgvragen")

    assert r.status_code == 200
    assert r.json() == {"vragen": []}


def test_te_korte_historie_geeft_lege_lijst(monkeypatch):
    import app_fastapi.main as m
    from app_fastapi.sessie import Sessie

    def _boom(*a, **k):
        raise AssertionError("genereer_vervolgvragen mag niet aangeroepen worden")

    monkeypatch.setattr(m, "genereer_vervolgvragen", _boom)

    s = Sessie(
        toegang=True,
        oer_systeem="PROMPT",
        chat_history=[{"role": "user", "content": "Hoe zit het met herkansen?"}],
    )
    monkeypatch.setattr(m, "get_sessie", lambda request: s)

    r = _client().post("/api/vervolgvragen")

    assert r.status_code == 200
    assert r.json() == {"vragen": []}


def test_lege_assistant_content_geeft_lege_lijst(monkeypatch):
    import app_fastapi.main as m
    from app_fastapi.sessie import Sessie

    def _boom(*a, **k):
        raise AssertionError("genereer_vervolgvragen mag niet aangeroepen worden")

    monkeypatch.setattr(m, "genereer_vervolgvragen", _boom)

    s = Sessie(
        toegang=True,
        oer_systeem="PROMPT",
        chat_history=[
            {"role": "user", "content": "en dan?"},
            {"role": "assistant", "content": ""},
        ],
    )
    monkeypatch.setattr(m, "get_sessie", lambda request: s)

    r = _client().post("/api/vervolgvragen")

    assert r.status_code == 200
    assert r.json() == {"vragen": []}


def test_met_geladen_oer_roept_ai_aan_en_geeft_vragen_terug(monkeypatch):
    import app_fastapi.main as m
    from app_fastapi.sessie import Sessie

    monkeypatch.setattr(m, "ai_client", lambda: "FAKE_CLIENT")

    gezien_args = {}

    def _fake_genereer(client, vraag, antwoord, labels, **kwargs):
        gezien_args["client"] = client
        gezien_args["vraag"] = vraag
        gezien_args["antwoord"] = antwoord
        gezien_args["labels"] = labels
        return ["Wat is de urenverdeling?", "Hoe zit herkansen?"]

    monkeypatch.setattr(m, "genereer_vervolgvragen", _fake_genereer)

    s = Sessie(
        toegang=True,
        oer_systeem="PROMPT",
        oer_labels=["Talland College · Kok · BOL 2025"],
        chat_history=[
            {"role": "user", "content": "Hoeveel uren BPV moet ik draaien?"},
            {"role": "assistant", "content": "Je moet 700 uur BPV draaien."},
        ],
    )
    monkeypatch.setattr(m, "get_sessie", lambda request: s)

    r = _client().post("/api/vervolgvragen")

    assert r.status_code == 200
    assert r.json() == {"vragen": ["Wat is de urenverdeling?", "Hoe zit herkansen?"]}
    assert gezien_args["client"] == "FAKE_CLIENT"
    assert gezien_args["vraag"] == "Hoeveel uren BPV moet ik draaien?"
    assert gezien_args["antwoord"] == "Je moet 700 uur BPV draaien."
    assert gezien_args["labels"] == ["Talland College · Kok · BOL 2025"]


def test_post_naar_vervolgvragen_bewaart_sessie_niet(tmp_path, monkeypatch):
    """Lost-update-fix (zie `_toegangspoort`): ondanks de POST-methode is deze route
    read-only en mag de middleware de sessie niet terugschrijven."""
    monkeypatch.setattr("app_fastapi.sessie._DB_PAD", str(tmp_path / "s.db"))
    import app_fastapi.sessie as sessie_mod

    sessie_mod._reset_store_voor_test()

    c = _client()  # toegang verleend + (echt) bewaard

    saves: list[str] = []
    monkeypatch.setattr(sessie_mod, "bewaar", lambda sid, s: saves.append(sid))
    r = c.post("/api/vervolgvragen")

    assert r.status_code == 200
    assert saves == []
