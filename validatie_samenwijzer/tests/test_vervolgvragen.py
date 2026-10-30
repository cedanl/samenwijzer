"""Tests voor `/api/vervolgvragen` — klikbare vervolgvragen na elk antwoord.

Patronen overgenomen uit `tests/test_intake_vervolg.py` (test-``AppDeps`` met een vaste
begin-sessie via ``maak_client(sessie=s)`` en een nep-``ai_client``; de AI-aanroep zelf is
gestubd i.p.v. een echte Anthropic-call).
"""

from __future__ import annotations


def test_geen_oer_systeem_geeft_lege_lijst_zonder_ai_call(maak_client, monkeypatch):
    import app_fastapi.main as m
    from app_fastapi.sessie import Sessie

    def _boom(*a, **k):
        raise AssertionError("genereer_vervolgvragen mag niet aangeroepen worden")

    monkeypatch.setattr(m, "genereer_vervolgvragen", _boom)

    s = Sessie(toegang=True)

    r = maak_client(s).post("/api/vervolgvragen")

    assert r.status_code == 200
    assert r.json() == {"vragen": []}


def test_te_korte_historie_geeft_lege_lijst(maak_client, monkeypatch):
    import app_fastapi.main as m
    from app_fastapi.sessie import Sessie
    from validatie_samenwijzer.gesprek import Gesprek

    def _boom(*a, **k):
        raise AssertionError("genereer_vervolgvragen mag niet aangeroepen worden")

    monkeypatch.setattr(m, "genereer_vervolgvragen", _boom)

    s = Sessie(
        toegang=True,
        oer_systeem="PROMPT",
        gesprek=Gesprek.van_lijst([{"role": "user", "content": "Hoe zit het met herkansen?"}]),
    )

    r = maak_client(s).post("/api/vervolgvragen")

    assert r.status_code == 200
    assert r.json() == {"vragen": []}


def test_lege_assistant_content_geeft_lege_lijst(maak_client, monkeypatch):
    import app_fastapi.main as m
    from app_fastapi.sessie import Sessie
    from validatie_samenwijzer.gesprek import Gesprek

    def _boom(*a, **k):
        raise AssertionError("genereer_vervolgvragen mag niet aangeroepen worden")

    monkeypatch.setattr(m, "genereer_vervolgvragen", _boom)

    s = Sessie(
        toegang=True,
        oer_systeem="PROMPT",
        gesprek=Gesprek.van_lijst(
            [
                {"role": "user", "content": "en dan?"},
                {"role": "assistant", "content": ""},
            ]
        ),
    )

    r = maak_client(s).post("/api/vervolgvragen")

    assert r.status_code == 200
    assert r.json() == {"vragen": []}


def test_met_geladen_oer_roept_ai_aan_en_geeft_vragen_terug(maak_client, monkeypatch):
    import app_fastapi.main as m
    from app_fastapi.sessie import Sessie
    from validatie_samenwijzer.gesprek import Gesprek

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
        gesprek=Gesprek.van_lijst(
            [
                {"role": "user", "content": "Hoeveel uren BPV moet ik draaien?"},
                {"role": "assistant", "content": "Je moet 700 uur BPV draaien."},
            ]
        ),
    )

    r = maak_client(s, ai_client=lambda: "FAKE_CLIENT").post("/api/vervolgvragen")

    assert r.status_code == 200
    assert r.json() == {"vragen": ["Wat is de urenverdeling?", "Hoe zit herkansen?"]}
    assert gezien_args["client"] == "FAKE_CLIENT"
    assert gezien_args["vraag"] == "Hoeveel uren BPV moet ik draaien?"
    assert gezien_args["antwoord"] == "Je moet 700 uur BPV draaien."
    assert gezien_args["labels"] == ["Talland College · Kok · BOL 2025"]


def test_post_naar_vervolgvragen_bewaart_sessie_niet(client):
    """Lost-update-fix (zie `_toegangspoort`): ondanks de POST-methode is deze route
    read-only en mag de middleware de sessie niet terugschrijven."""
    saves = client.app.state.deps.sessie_store.bewaard
    saves.clear()  # de toegang-POST is (echt) bewaard
    r = client.post("/api/vervolgvragen")

    assert r.status_code == 200
    assert saves == []
