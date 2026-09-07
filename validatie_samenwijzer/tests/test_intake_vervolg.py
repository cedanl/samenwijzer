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


def test_kies_beurt_telt_mee_bij_genegeerde_picker(monkeypatch):
    """Regressie voor de #243-follow-up: de kies-beurt zelf ontbrak in `chat_history`, dus als
    de gebruiker de picker negeert en verder typt, mist de accumulatie de kandidaten-context.

    Gebruikt de echte `validatie.db` (geen synthetische fixture): "tandartsassistent" alleen
    levert meerdere kandidaten op (4 instellingen, kies-modus). Zonder de kies-beurt-fix ziet de
    vervolgvraag "in Nijmegen" alleen zichzelf en matcht op instelling-naam alleen (5 ROC
    Nijmegen-OER's, kies-modus opnieuw). Mét de fix telt "tandartsassistent" nog mee en
    resolveert de combinatie naar precies de ROC Nijmegen-tandartsassistent-OER (crebo 25699,
    bekende val: bestandsnaam-token "Tandartsassistent1" bij Da Vinci matcht niet op naam).
    """
    import app_fastapi.main as m
    from app_fastapi.sessie import Sessie

    monkeypatch.setattr(m, "laad_context", lambda oer_ids, **k: ("PROMPT", ["label"], [], False))

    s = Sessie(toegang=True)
    monkeypatch.setattr(m, "get_sessie", lambda request: s)

    c = _client()
    r1 = c.post("/api/vraag", json={"vraag": "tandartsassistent"})
    assert r1.json()["modus"] == "kies"
    assert len(r1.json()["opties"]) > 1
    # De kies-beurt moet nu ook zelf als user-turn in de historie staan.
    assert {"role": "user", "content": "tandartsassistent"} in s.chat_history

    r2 = c.post("/api/vraag", json={"vraag": "in Nijmegen"})
    body = r2.json()
    assert body["modus"] == "chat", body
    assert body["oer_ids"] == [1193]


def test_vraag_partiele_enkele_kandidaat_geeft_kies(monkeypatch):
    """Eén kandidaat die slechts partieel matcht (de genoemde school biedt de opleiding niet aan,
    een andere school wél) → modus "kies" i.p.v. stil de verkeerde studiegids laden."""
    import app_fastapi.main as m
    from app_fastapi.sessie import Sessie

    oers = [
        {
            "id": 1,
            "crebo": "25915",
            "opleiding": "25915_BOL_2026__vakbekwaam-medewerker-paardensport",
            "display_naam": "Aeres MBO",
            "naam": "aeres",
            "leerweg": "BOL",
            "cohort": "2026",
        },
        {
            "id": 2,
            "crebo": "25916",
            "opleiding": "25916_BOL_2025__Bedrijfsleider_paardensport",
            "display_naam": "Landstede MBO",
            "naam": "landstede",
            "leerweg": "BOL",
            "cohort": "2025",
        },
    ]
    monkeypatch.setattr(m.db, "get_alle_oers_met_instelling", lambda conn: oers)
    geladen = []
    monkeypatch.setattr(
        m, "laad_context", lambda oer_ids, **k: geladen.append(oer_ids) or ("P", ["l"], [], False)
    )
    s = Sessie(toegang=True)
    monkeypatch.setattr(m, "get_sessie", lambda request: s)

    r = _client().post(
        "/api/vraag", json={"vraag": "Bedrijfsleider paardensport bij Aeres, BOL 2025"}
    )

    assert r.status_code == 200
    assert r.json()["modus"] == "kies"
    assert geladen == []
    assert [k["id"] for k in s.kandidaten] == [1]
