"""Tests voor Task 1: `/api/vraag` scoort op opgetelde gesprekstekst (niet alleen de laatste vraag).

Patronen overgenomen uit `tests/test_fastapi_poc.py` (TestClient + toegangspoort, monkeypatch van
`db.get_alle_oers_met_instelling`/`get_sessie` i.p.v. de echte database — deterministisch en
onafhankelijk van de seed-data).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()
_WW = os.environ.get("ALGEMEEN_WACHTWOORD", "")

# Twee OER's van dezelfde instelling, zonder onderscheidend opleidingswoord in de teksten
# hieronder — een instellingsmatch alleen levert dus een gelijkspel (kies-modus, geen intake).
_FAKE_OERS = [
    {
        "id": 1,
        "crebo": "11111",
        "opleiding": "Kok",
        "display_naam": "Talland College",
        "naam": "talland",
        "leerweg": "BOL",
        "cohort": "2025",
    },
    {
        "id": 2,
        "crebo": "22222",
        "opleiding": "Banketbakker",
        "display_naam": "Talland College",
        "naam": "talland",
        "leerweg": "BBL",
        "cohort": "2024",
    },
]


def _client():
    """TestClient die al door de algemene toegangspoort is (gedeeld wachtwoord)."""
    from fastapi.testclient import TestClient

    from app_fastapi.main import app

    c = TestClient(app)
    c.post("/toegang", data={"wachtwoord": _WW})
    return c


def test_vraag_accumuleert_eerdere_gebruikersbeurten(monkeypatch):
    """Een fragment zonder eigen match ("en dan?") vindt kandidaten via de instelling die in
    een eerdere user-beurt genoemd is — en de kale vraag (niet de optelsom) blijft
    `wachtende_vraag`."""
    import app_fastapi.main as m
    from app_fastapi.sessie import Sessie

    monkeypatch.setattr(m.db, "get_alle_oers_met_instelling", lambda conn: _FAKE_OERS)

    s = Sessie(
        toegang=True,
        chat_history=[{"role": "user", "content": "Ik zit op Talland College"}],
    )
    monkeypatch.setattr(m, "get_sessie", lambda request: s)

    r = _client().post("/api/vraag", json={"vraag": "en dan?"})

    assert r.status_code == 200
    body = r.json()
    assert body["modus"] == "kies"
    assert len(body["opties"]) == 2
    # Kale nieuwe vraag, niet de concatenatie van historie + vraag.
    assert s.wachtende_vraag == "en dan?"


def test_vraag_zonder_historie_matcht_niet_op_fragment_alleen(monkeypatch):
    """Eerste beurt (geen chat_history): hetzelfde fragment matcht op zichzelf niets → intake.
    Bewijst dat het kies-resultaat hierboven echt uit de historie komt, niet uit "en dan?" zelf."""
    import app_fastapi.main as m
    from app_fastapi.sessie import Sessie

    monkeypatch.setattr(m.db, "get_alle_oers_met_instelling", lambda conn: _FAKE_OERS)

    s = Sessie(toegang=True)
    monkeypatch.setattr(m, "get_sessie", lambda request: s)

    r = _client().post("/api/vraag", json={"vraag": "en dan?"})

    assert r.status_code == 200
    assert r.json()["modus"] == "intake"


def test_vraag_accumuleert_naar_eenduidige_match_laadt_direct(monkeypatch):
    """Seeded historie + vervolgfragment lossen samen op tot precies 1 kandidaat → modus
    "chat" met `oer_ids` gezet, en de kies-state (`wachtende_vraag`/`kandidaten`) van een
    eerdere ronde wordt niet per ongeluk laten staan (regressie voor Finding 1)."""
    import app_fastapi.main as m
    from app_fastapi.sessie import Sessie

    monkeypatch.setattr(m.db, "get_alle_oers_met_instelling", lambda conn: _FAKE_OERS)
    monkeypatch.setattr(m, "laad_context", lambda oer_ids, **k: ("PROMPT", ["label"], [], False))

    s = Sessie(
        toegang=True,
        chat_history=[{"role": "user", "content": "Ik zit op Talland College, ik doe Kok"}],
        # Stale kies-state uit een eerdere ronde die deze beurt zou moeten opruimen.
        wachtende_vraag="oude vraag",
        kandidaten=[{"id": 99, "display_naam": "oud"}],
    )
    monkeypatch.setattr(m, "get_sessie", lambda request: s)

    r = _client().post("/api/vraag", json={"vraag": "en dan?"})

    assert r.status_code == 200
    body = r.json()
    assert body["modus"] == "chat"
    assert body["oer_ids"] == [1]
    assert s.wachtende_vraag is None
    assert s.kandidaten == []


def test_vraag_met_al_geladen_oer_blijft_shortcut_nemen(monkeypatch):
    """Bestaande shortcut (OER al geladen) blijft ongewijzigd: geen scoring, direct chat."""
    import app_fastapi.main as m
    from app_fastapi.sessie import Sessie

    def _boom(*a, **k):
        raise AssertionError("identificeer_oer_kandidaten mag niet aangeroepen worden")

    monkeypatch.setattr(m, "identificeer_oer_kandidaten", _boom)

    s = Sessie(
        toegang=True,
        oer_systeem="PROMPT",
        oer_labels=["Talland College · Kok · BOL 2025"],
        oer_onleesbaar=False,
        chat_history=[{"role": "user", "content": "Ik zit op Talland College"}],
    )
    monkeypatch.setattr(m, "get_sessie", lambda request: s)

    r = _client().post("/api/vraag", json={"vraag": "hoe zit het met herkansen?"})

    assert r.status_code == 200
    body = r.json()
    assert body["modus"] == "chat"
    assert body["labels"] == ["Talland College · Kok · BOL 2025"]
