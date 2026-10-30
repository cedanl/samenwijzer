"""Tests voor de FastAPI-POC (publieke OER-chat).

De app draait op een test-``AppDeps`` (zie ``tests/conftest.py``: in-memory validatie-DB en
sessie-store, nep-AI-client); OER's, mentoren en studenten worden per test geseed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import anthropic
import pytest

from app_fastapi.context import ChatContext, OerBlokken, laad_context
from app_fastapi.deps import AppDeps, ValidatieDb
from app_fastapi.sessie import Sessie, SessieStore
from validatie_samenwijzer import db

_OER_TEKST = "Onderwijs- en examenregeling. " * 40  # > 500 tekens: een leesbare OER


def _geen_ai():
    raise AssertionError("AI niet aanroepen")


def test_laad_context_lege_lijst(conn):
    assert laad_context(conn, []) == ChatContext()


def test_laad_context_onbekende_id(conn):
    # Een niet-bestaand id levert geen leesbare OER → lege context (id blijft genoteerd).
    assert laad_context(conn, [99_999_999]) == ChatContext(oer_ids=[99_999_999])


def test_laad_context_geeft_systeem_en_label(seed, conn):
    oer_id = seed.oer(tekst=_OER_TEKST)
    c = laad_context(conn, [oer_id])
    assert c.systeem and len(c.systeem) > 500
    assert len(c.labels) == 1 and " · " in c.labels[0]
    assert isinstance(c.domeinen, list)
    assert c.oer_ids == [oer_id]


def test_laad_context_student_niveau_minstens_zo_breed(seed, conn):
    """Student-niveau ziet minstens zoveel documenten als publiek."""
    oer_id = seed.oer(tekst=_OER_TEKST)
    publiek = laad_context(conn, [oer_id]).systeem
    student = laad_context(conn, [oer_id], "student").systeem
    assert len(student) >= len(publiek)


def test_laad_context_bevat_vacature_domeinen(seed, conn):
    domeinen = laad_context(conn, [seed.oer(tekst=_OER_TEKST)]).domeinen
    for d in ("stagemarkt.nl", "indeed.nl"):
        assert d in domeinen


def test_laad_context_onleesbare_oer_via_kd(seed, conn, monkeypatch):
    """Een OER zonder leesbare tekst maar mét KD levert tóch context + oer_onleesbaar=True."""
    import app_fastapi.context as ctx

    oer_id = seed.oer("Gastheer", instelling="davinci", display="Da Vinci", tekst=None)
    monkeypatch.setattr(ctx, "laad_kwalificatiedossier_tekst", lambda c, *a: "KD-INHOUD")

    c = laad_context(conn, [oer_id])
    assert "KD-INHOUD" in c.systeem
    assert c.oer_onleesbaar is True
    assert len(c.labels) == 1


def test_laad_context_leesbare_oer_niet_onleesbaar(seed, conn):
    oer_id = seed.oer("Gastheer", instelling="davinci", display="Da Vinci", tekst="ECHTE OER-TEKST")

    c = laad_context(conn, [oer_id])
    assert "ECHTE OER-TEKST" in c.systeem
    assert c.oer_onleesbaar is False


def test_laad_context_geeft_bron_register(seed, conn):
    """Het register hoort bij de context: bekende titels met oer_id, plus de webdomeinen."""
    from validatie_samenwijzer.chat import splits_bronnen

    oer_id = seed.oer("Gastheer", instelling="davinci", display="Da Vinci", tekst="ECHTE OER-TEKST")

    c = laad_context(conn, [oer_id])
    register = c.bron_register
    assert c.systeem and c.oer_ids == [oer_id]
    websites = {r["titel"] for r in register if r["type"] == "website"}
    assert websites == {"davinci.nl", "indeed.nl", "stagemarkt.nl"}
    titel = next(r["titel"] for r in register if r["type"] == "studiegids")
    tekst = f"x\n<!-- bronnen: studiegids|{titel}; studiegids|Nep -->"
    _, bronnen = splits_bronnen(tekst, register)
    assert [(b.titel, b.oer_id) for b in bronnen] == [(titel, oer_id)]


def test_laad_context_leeg_register_zonder_bron(conn):
    c = laad_context(conn, [1])  # lege DB: geen OER met id 1
    assert (c.systeem, c.labels, c.domeinen, c.oer_onleesbaar, c.melding) == ("", [], [], False, "")
    assert c.bron_register == [] and c.oer_ids == [1]


# ── OER-cache per app-instantie ─────────────────────────────────────────────────
def test_oer_blokken_cachet_per_instantie(seed, conn):
    """De cache hangt aan de instantie: dezelfde instantie leest het bestand niet opnieuw,
    een nieuwe (herstart/re-ingest) ziet de nieuwe tekst."""
    oer_id = seed.oer(tekst="EERSTE VERSIE")
    blokken = OerBlokken()
    assert "EERSTE VERSIE" in laad_context(conn, [oer_id], oer_blokken=blokken).systeem
    Path(db.get_oer_document_by_id(conn, oer_id)["bestandspad"]).write_text("TWEEDE VERSIE")

    assert "EERSTE VERSIE" in laad_context(conn, [oer_id], oer_blokken=blokken).systeem
    assert "TWEEDE VERSIE" in laad_context(conn, [oer_id], oer_blokken=OerBlokken()).systeem
    blokken.leeg()
    assert "TWEEDE VERSIE" in laad_context(conn, [oer_id], oer_blokken=blokken).systeem


def test_oer_blokken_is_begrensd(seed, conn):
    blokken = OerBlokken(maxsize=2)
    ids = [seed.oer(crebo=f"9900{i}", tekst=f"OER {i}") for i in range(3)]
    for oid in ids:
        blokken.haal(conn, oid)
    assert len(blokken) == 2


def test_twee_app_instanties_delen_geen_oer_cache(seed, maak_client, maak_deps):
    oer_id = seed.oer(tekst=_OER_TEKST)
    deps1, deps2 = maak_deps(), maak_deps()
    assert deps1.oer_blokken is not deps2.oer_blokken

    r = maak_client(deps=deps1).post("/api/kies", json={"oer_ids": [oer_id]})

    assert r.status_code == 200 and r.json()["oer_ids"] == [oer_id]
    assert len(deps1.oer_blokken) == 1
    assert len(deps2.oer_blokken) == 0


# ── sessie ────────────────────────────────────────────────────────────────────
def test_sessie_voeg_beurt_kapt_op_max():
    from app_fastapi.sessie import MAX_GESCHIEDENIS

    s = Sessie()
    for i in range(MAX_GESCHIEDENIS):  # elk = 2 berichten → ruim over de cap
        s.gesprek.voeg_beurt_toe(f"v{i}", f"a{i}")
    lijst = s.gesprek.naar_lijst()
    assert len(lijst) == MAX_GESCHIEDENIS
    assert lijst[-1]["content"].startswith("a")  # nieuwste behouden


def test_sessie_reset_leegt_alles():
    s = Sessie(oer_systeem="x", oer_labels=["l"], oer_ids=[1])
    s.gesprek.voeg_beurt_toe("v", "a")
    s.reset()
    assert s.gesprek.naar_lijst() == [] and s.oer_systeem is None and s.oer_ids == []


# ── sessiestore (SQLite, write-through + TTL) ───────────────────────────────────
def test_sessiestore_bewaart_en_laadt():
    store = SessieStore(":memory:")
    s = Sessie()
    s.oer_systeem = "PROMPT"
    s.oer_ids = [1, 2]
    s.gesprek.voeg_beurt_toe("vraag", "antwoord")
    store.bewaar("sid-1", s)

    geladen = store.laad("sid-1")
    assert geladen is not None
    assert geladen.oer_systeem == "PROMPT"
    assert geladen.oer_ids == [1, 2]
    assert geladen.gesprek.naar_lijst() == [
        {"role": "user", "content": "vraag"},
        {"role": "assistant", "content": "antwoord"},
    ]


def test_sessiestore_in_memory_instanties_zijn_gescheiden():
    a, b = SessieStore(":memory:"), SessieStore(":memory:")
    a.bewaar("sid", Sessie(toegang=True))
    assert a.laad("sid") is not None and b.laad("sid") is None


def test_sessiestore_op_bestand_overleeft_een_nieuwe_instantie(tmp_path):
    pad = tmp_path / "sub" / "sessies.db"
    SessieStore(pad).bewaar("sid", Sessie(toegang=True))
    geladen = SessieStore(pad).laad("sid")
    assert geladen is not None and geladen.toegang is True


def test_sessiestore_laad_onbekende_sid_is_none():
    assert SessieStore(":memory:").laad("bestaat-niet") is None


def test_sessiestore_ttl_verwijdert_verouderd():
    klok = [1_000_000.0]
    store = SessieStore(":memory:", ttl_seconden=100, klok=lambda: klok[0])
    store.bewaar("oud", Sessie())
    klok[0] += 200  # voorbij de TTL
    store.bewaar("nieuw", Sessie())  # triggert lazy opruiming
    assert store.laad("oud") is None
    assert store.laad("nieuw") is not None


def test_get_sessie_write_through_round_trip():
    """get_sessie + bewaar_sessie: een tweede request met dezelfde sid krijgt de state terug."""
    from app_fastapi import sessie as sessie_mod

    app = SimpleNamespace(
        state=SimpleNamespace(deps=SimpleNamespace(sessie_store=SessieStore(":memory:")))
    )

    req1 = SimpleNamespace(app=app, session={}, state=SimpleNamespace())
    s1 = sessie_mod.get_sessie(req1)
    s1.toegang = True
    sessie_mod.bewaar_sessie(req1)
    sid = req1.session["sid"]

    req2 = SimpleNamespace(app=app, session={"sid": sid}, state=SimpleNamespace())
    s2 = sessie_mod.get_sessie(req2)
    assert s2.toegang is True


# ── AppDeps ─────────────────────────────────────────────────────────────────────
def test_session_secret_verplicht():
    """Zonder SESSION_SECRET moet het opzetten van de app falen (fail-closed)."""
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        AppDeps.uit_env({"ALGEMEEN_WACHTWOORD": "pw"})


def test_algemeen_wachtwoord_verplicht():
    with pytest.raises(RuntimeError, match="ALGEMEEN_WACHTWOORD"):
        AppDeps.uit_env({"SESSION_SECRET": "s"})
    with pytest.raises(RuntimeError, match="ALGEMEEN_WACHTWOORD"):
        AppDeps.uit_env({"SESSION_SECRET": "s", "ALGEMEEN_WACHTWOORD": ""})


def test_constructor_is_ook_fail_closed():
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        AppDeps("", "pw", ValidatieDb(":memory:"), SessieStore(":memory:"))


def test_uit_env_leest_config_zonder_iets_te_openen(tmp_path):
    deps = AppDeps.uit_env(
        {
            "SESSION_SECRET": "s",
            "ALGEMEEN_WACHTWOORD": "pw",
            "COOKIE_HTTPS_ONLY": "0",
            "BEHEER_ENABLED": "True",
            "CHAT_MAX_SECONDEN": "12.5",
            "DB_PATH": str(tmp_path / "v.db"),
            "SESSIE_DB_PATH": str(tmp_path / "s" / "sessies.db"),
        }
    )
    assert (deps.cookie_https_only, deps.beheer_enabled) == (False, True)
    assert (deps.chat_max_seconden, deps.chat_heartbeat_seconden) == (12.5, 15.0)
    assert deps.validatie_db.pad == str(tmp_path / "v.db")
    assert deps.sessie_store.pad == str(tmp_path / "s" / "sessies.db")
    assert list(tmp_path.iterdir()) == []  # lazy: bouwen opent geen DB-bestanden


def test_uit_env_defaults():
    from validatie_samenwijzer import _ai

    deps = AppDeps.uit_env({"SESSION_SECRET": "s", "ALGEMEEN_WACHTWOORD": "pw"})
    assert deps.cookie_https_only is True and deps.beheer_enabled is False
    assert deps.chat_max_seconden == 90.0
    assert deps.validatie_db.pad == "data/validatie.db"
    assert deps.sessie_store.pad == "data/sessies.db"
    assert deps.ai_client is _ai._client


def test_read_only_get_bewaart_niet(client):
    """Lost-update-fix: een read-only GET schrijft de sessie niet terug; mutaties wel."""
    saves = client.app.state.deps.sessie_store.bewaard
    saves.clear()  # de toegang-POST is (echt) bewaard
    client.get("/")  # read-only → géén save
    assert saves == []
    client.post("/api/reset")  # mutaterend → wél save
    assert len(saves) == 1


# ── api (geen AI-call) ─────────────────────────────────────────────────────────
def test_toegangspoort_blokkeert_zonder_wachtwoord(maak_client):
    c = maak_client(toegang=False)
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/toegang"
    assert c.post("/api/reset").status_code == 401


def test_toegang_met_fout_wachtwoord_blijft_dicht(maak_client):
    c = maak_client(toegang=False)
    r = c.post("/toegang", data={"wachtwoord": "fout"}, follow_redirects=False)
    assert r.headers["location"] == "/toegang?fout=1"
    assert c.post("/api/reset").status_code == 401


def test_api_index_serveert_landing(client):
    r = client.get("/")
    assert r.status_code == 200 and "/static/app.css" in r.text


def test_landing_toont_eerst_de_kiezer_en_dan_het_vraagveld(client):
    """Keuze-eerst: de kiezer staat vóór het (vergrendelde) vraagveld en er is geen vrij
    vraagformulier (`data-ask`) meer op de startpagina."""
    html = client.get("/").text
    assert 'id="oplCascade"' in html and 'id="vraagveld"' in html
    assert html.index('id="oplCascade"') < html.index('id="vraagveld"')
    assert "data-ask" not in html
    assert 'class="vraagveld locked"' in html


def test_static_assets_hebben_cache_bust_versie(client):
    """Cache-busting: terugkerende bezoekers moeten een gewijzigde app.js/app.css oppikken
    zonder hard-refresh — static_url() hangt ?v=<mtime> aan elk static-asset-path."""
    r = client.get("/")
    assert r.status_code == 200
    assert "app.js?v=" in r.text
    assert "app.css?v=" in r.text
    assert "chat.js?v=" in r.text


def test_api_vraag_zonder_match_geeft_intake(client):
    r = client.post("/api/vraag", json={"vraag": "zxcvqwer onbekende instelling blabla"})
    assert r.status_code == 200 and r.json()["modus"] == "intake"


def test_api_vraag_en_chat_ongeldige_json_geven_400(client):
    """Kapotte of lege body mag geen 500 opleveren (input-validatie aan de grens)."""
    c = client
    for endpoint in ("/api/vraag", "/api/chat"):
        assert (
            c.post(
                endpoint, content=b"{niet json", headers={"Content-Type": "application/json"}
            ).status_code
            == 400
        )
        assert (
            c.post(endpoint, content=b"", headers={"Content-Type": "application/json"}).status_code
            == 400
        )
        # geldige JSON, maar géén object (bijv. een lijst) → ook nette 400
        assert c.post(endpoint, json=[1, 2, 3]).status_code == 400
    # geldige body werkt nog steeds (intake-modus op een verse sessie)
    r = c.post("/api/vraag", json={"vraag": ""})
    assert r.status_code == 200 and r.json()["modus"] == "intake"


def test_api_opleidingen_geeft_boom(seed, client):
    seed.oer()
    r = client.get("/api/opleidingen")
    assert r.status_code == 200
    boom = r.json()
    assert isinstance(boom, list) and boom
    assert {"instelling", "leerwegen"} <= set(boom[0])


def test_api_kies_zonder_wachtende_vraag(seed, client):
    seed.oer(tekst=_OER_TEKST)
    c = client  # verse sessie: geen vraag, geen geladen OER
    boom = c.get("/api/opleidingen").json()
    oer_id = boom[0]["leerwegen"][0]["opleidingen"][0]["cohorten"][0]["oer_ids"][0]
    r = c.post("/api/kies", json={"oer_ids": [oer_id]})
    assert r.status_code == 200
    body = r.json()
    assert body["oer_ids"] == [oer_id]
    assert body["wachtende_vraag"] is None
    assert "labels" in body


def test_api_kies_laadt_meerdere_studiegidsen_naast_elkaar(seed, client):
    """De kiezer laat er tot 3 combineren; /api/kies moet die lijst ook echt honoreren.

    Guard tegen een terugval naar één gids: elk meegestuurd id hoort in de sessie én
    in de labels terug te komen (de multi-OER-modus van `bouw_prompt`).
    """
    gekozen = [
        seed.oer("Kok", crebo="99001", tekst=_OER_TEKST),
        seed.oer("Bakker", crebo="99002", tekst=_OER_TEKST),
    ]

    body = client.post("/api/kies", json={"oer_ids": gekozen}).json()

    assert body["oer_ids"] == gekozen
    assert len(body["labels"]) == 2, "elke gekozen studiegids hoort een eigen label te krijgen"


def test_elke_soort_is_zichtbaar_voor_minstens_een_niveau():
    """Guard: een soort moet in minstens één chat-niveau voorkomen, anders is een geïndexeerde
    bron (zoals gedragscode) onzichtbaar als document-fallback."""
    zichtbaar = {
        z
        for niveau in ("publiek", "student", "mentor")
        for z in db.zichtbaarheden_voor_niveau(niveau)
    }
    onzichtbaar = {k for k, v in db.SOORTEN.items() if v.zichtbaarheid not in zichtbaar}
    assert not onzichtbaar, f"Soorten die nergens zichtbaar zijn: {sorted(onzichtbaar)}"


def test_generieke_regelingen_zijn_publiek_zichtbaar():
    """Generieke regelingen zijn een concept voor alle instellingen, ook in de publieke route."""
    for soort in (
        "privacyreglement",
        "pestprotocol",
        "meldcode",
        "ict_reglement",
        "gedragsregeling",
    ):
        assert soort in db.zichtbaarheden_voor_niveau("publiek") or (
            db.SOORTEN[soort].zichtbaarheid in db.zichtbaarheden_voor_niveau("publiek")
        )


def test_chat_toegewezen_maar_onleesbare_oer_geeft_lage_relevantie(maak_client, stub_context):
    """Toegewezen OER zonder bruikbare bron → expliciete melding, geen intake (geen AI-call)."""
    from validatie_samenwijzer.chat import LAGE_RELEVANTIE_BERICHT

    # laad_context geeft 'geen bruikbare bron' terug; ai_client mag niet aangeroepen worden.
    stub_context(systeem="", labels=[])
    c = maak_client(ai_client=_geen_ai)
    c.post("/api/kies", json={"oer_ids": [1]})  # sessie: oer_ids=[1], oer_systeem=""
    r = c.post("/api/chat", json={"vraag": "hoe werkt herkansen?"})
    assert r.status_code == 200
    assert LAGE_RELEVANTIE_BERICHT in r.text


def test_app_logger_staat_op_info():
    import app_fastapi.main  # noqa: F401 — configureert de root-logger bij import

    # Zonder root-config zou log.info() nergens aankomen (root default = WARNING).
    assert logging.getLogger("oer_poc").getEffectiveLevel() <= logging.INFO
    assert logging.getLogger().handlers


def test_chat_logt_timing_zonder_vraagtekst(client, monkeypatch, caplog, stub_context):
    """Elke voltooide chat-beurt logt timing/tekens/modus (Fly-zicht) — geen vraagtekst (PII)."""
    import app_fastapi.main as m

    stub_context(systeem="SYSTEEMPROMPT", domeinen=["stagemarkt.nl", "indeed.nl"])
    monkeypatch.setattr(m, "genereer_antwoord", lambda *a, **k: iter(["Hallo ", "wereld"]))
    c = client
    c.post("/api/kies", json={"oer_ids": [1]})  # sessie: oer_systeem="SYSTEEMPROMPT" → modus=oer
    vraag = "geheime studentvraag 12345"
    with caplog.at_level(logging.INFO, logger="oer_poc"):
        r = c.post("/api/chat", json={"vraag": vraag})
    assert r.status_code == 200

    treffers = [rec for rec in caplog.records if "chat-beurt" in rec.message]
    assert len(treffers) == 1
    bericht = treffers[0].getMessage()
    assert "ttft_s" in bericht and "totaal_s" in bericht
    assert "tekens=12" in bericht  # "Hallo " + "wereld"
    assert "modus=oer" in bericht and "domeinen=2" in bericht
    assert vraag not in bericht


def _events(tekst: str) -> list[dict]:
    return [json.loads(line[6:]) for line in tekst.splitlines() if line.startswith("data: ")]


_GEEN_IDS = {"doc_id": None, "oer_id": None, "crebo": None}


def test_chat_stuurt_status_lezen_bronnen_en_stript_marker(client, monkeypatch, stub_context):
    import app_fastapi.main as m
    from validatie_samenwijzer.chat import Status

    stub_context()
    monkeypatch.setattr(
        m,
        "genereer_antwoord",
        lambda *a, **k: iter(
            [
                Status("web"),
                "Antwoord.\n\n<!-- bro",
                "nnen: studiegids|OER Kok; website|curio.nl|https://curio.nl -->",
            ]
        ),
    )
    c = client
    c.post("/api/kies", json={"oer_ids": [1]})
    ev = _events(c.post("/api/chat", json={"vraag": "kluisjes?"}).text)
    assert ev[0] == {"status": "lezen"}
    assert {"status": "web"} in ev
    assert "".join(e["chunk"] for e in ev if "chunk" in e) == "Antwoord.\n\n"
    assert ev[-2] == {
        "bronnen": [
            {"type": "studiegids", "titel": "OER Kok", "url": None, **_GEEN_IDS},
            {"type": "website", "titel": "curio.nl", "url": "https://curio.nl", **_GEEN_IDS},
        ]
    }
    assert ev[-1] == {"done": True}
    # ruwe tekst mét marker in de historie; geschiedenis-API stript en levert bronnen
    g = c.get("/api/geschiedenis").json()["beurten"]
    assert g[-1]["content"] == "Antwoord." and g[-1]["bronnen"][0]["titel"] == "OER Kok"
    assert "<!-- bronnen:" not in c.get("/api/geschiedenis").text


def test_chat_gebruikt_bron_register_uit_de_sessie(client, monkeypatch, stub_context):
    """`/api/chat` herleidt de bronnenmarker via het sessieregister: een bekende titel komt mét
    `oer_id` door, een door het model verzonnen titel valt weg."""
    import app_fastapi.main as m

    stub_context(
        bron_register=[
            {"type": "studiegids", "titel": "OER Kok BOL 2025", "oer_id": 7, "doc_id": None,
             "crebo": "25180"},
        ]
    )  # fmt: skip
    monkeypatch.setattr(
        m,
        "genereer_antwoord",
        lambda *a, **k: iter(
            ["Antwoord.\n<!-- bronnen: studiegids|OER Kok BOL 2025; studiegids|Verzonnen gids -->"]
        ),
    )
    c = client
    c.post("/api/kies", json={"oer_ids": [7]})
    ev = _events(c.post("/api/chat", json={"vraag": "kluisjes?"}).text)
    bronnen = next(e["bronnen"] for e in ev if "bronnen" in e)
    assert [(b["titel"], b["oer_id"]) for b in bronnen] == [("OER Kok BOL 2025", 7)]


def test_chat_meldt_schooldoc_status_uit_tekstbegin(client, monkeypatch, stub_context):
    import app_fastapi.main as m
    from validatie_samenwijzer.chat import _SCHOOLDOC_DISCLAIMER

    stub_context()
    helft = len(_SCHOOLDOC_DISCLAIMER) // 2
    monkeypatch.setattr(
        m,
        "genereer_antwoord",
        lambda *a, **k: iter(
            [_SCHOOLDOC_DISCLAIMER[:helft], _SCHOOLDOC_DISCLAIMER[helft:], "\n\nAntwoord"]
        ),
    )
    c = client
    c.post("/api/kies", json={"oer_ids": [1]})
    ev = _events(c.post("/api/chat", json={"vraag": "statuut?"}).text)
    statussen = [e["status"] for e in ev if "status" in e]
    assert statussen == ["lezen", "schooldoc"]
    assert not any("bronnen" in e for e in ev)


def test_chat_meldt_webinfo_status_ook_bij_één_grote_chunk(client, monkeypatch, stub_context):
    import app_fastapi.main as m
    from validatie_samenwijzer.chat import _WEB_DISCLAIMER

    stub_context()
    monkeypatch.setattr(
        m, "genereer_antwoord", lambda *a, **k: iter([_WEB_DISCLAIMER + "\n\nAntwoord"])
    )
    c = client
    c.post("/api/kies", json={"oer_ids": [1]})
    ev = _events(c.post("/api/chat", json={"vraag": "web?"}).text)
    assert [e["status"] for e in ev if "status" in e] == ["lezen", "webinfo"]


def test_chat_intake_stuurt_status_intake_zonder_bronnen(client, monkeypatch):
    import app_fastapi.main as m

    monkeypatch.setattr(m, "genereer_intake_antwoord", lambda *a, **k: iter(["Welke school?"]))
    ev = _events(client.post("/api/chat", json={"vraag": "hoi"}).text)
    assert ev[0] == {"status": "intake"}
    assert not any("bronnen" in e for e in ev)


def test_chat_lage_relevantie_stuurt_geen_status(maak_client, stub_context):
    stub_context(systeem="", labels=[])
    c = maak_client(ai_client=_geen_ai)
    c.post("/api/kies", json={"oer_ids": [1]})
    ev = _events(c.post("/api/chat", json={"vraag": "x"}).text)
    assert not any("status" in e for e in ev)


def test_api_reset_ok(client):
    r = client.post("/api/reset")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_api_geschiedenis_geeft_beurten(client):
    r = client.get("/api/geschiedenis")
    assert r.status_code == 200 and r.json() == {"beurten": []}


def test_oer_bestand_download_geeft_attachment(seed, client):
    """?download=1 levert het bestand als attachment (mobiele download-fallback)."""
    oer_id = seed.oer(tekst=_OER_TEKST)
    client.post("/api/kies", json={"oer_ids": [oer_id]})  # zet oer_id in de sessie (IDOR-guard)
    r = client.get(f"/api/oer/{oer_id}/bestand?download=1")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "").lower()


def test_beheer_uit_zonder_flag(maak_client):
    c = maak_client(beheer_enabled=False)
    assert c.get("/beheer").status_code == 404
    assert c.get("/api/beheer/run?taak=sync_oeren").status_code == 404


def test_beheer_toont_status(seed, maak_client):
    seed.oer()
    r = maak_client(beheer_enabled=True).get("/beheer")
    assert r.status_code == 200 and "Talland College" in r.text


def test_beheer_onbekende_taak_400(maak_client):
    c = maak_client(beheer_enabled=True)
    assert c.get("/api/beheer/run?taak=bestaatniet").status_code == 400
    # ingest zonder geldige instelling → 400
    assert c.get("/api/beheer/run?taak=ingest&instelling=onzin").status_code == 400


def test_beheer_run_streamt_output(maak_client, conn, monkeypatch):
    import app_fastapi.main as m

    class _FakeStdout:
        def __init__(self, regels):
            self._it = iter([*regels])

        async def readline(self):
            try:
                return next(self._it)
            except StopIteration:
                return b""

    class _FakeProc:
        def __init__(self, *a, **k):
            self.stdout = _FakeStdout([b"regel1\n", b"regel2\n"])
            self.returncode = None
            self.pid = -1

        async def wait(self):
            self.returncode = 0
            return 0

    gedood = []
    monkeypatch.setattr(m.os, "killpg", lambda pid, sig: gedood.append((pid, sig)))

    async def _fake_exec(*a, **k):
        return _FakeProc()

    monkeypatch.setattr(m.asyncio, "create_subprocess_exec", _fake_exec)

    c = maak_client(beheer_enabled=True)
    blokken = c.app.state.deps.oer_blokken
    blokken.haal(conn, 1)  # iets in de OER-cache
    body = c.get("/api/beheer/run?taak=sync_oeren").text
    assert "regel1" in body and "regel2" in body
    assert '"done": true' in body
    assert len(blokken) == 0  # na een beheer-taak (bv. re-ingest) is de OER-cache leeg


# ── auth / ingelogde pagina's ────────────────────────────────────────────────────
@pytest.fixture
def student_met_mentor(seed):
    """(studentnummer, student_id, mentor_naam, mentor_id, vreemde_student_id)."""
    oer_id = seed.oer(tekst=_OER_TEKST)
    mid = seed.mentor("Mentor Een")
    ander = seed.mentor("Mentor Twee")
    sid = seed.student("100001", oer_id, mid)
    vreemd = seed.student("100002", oer_id, ander)
    return "100001", sid, "Mentor Een", mid, vreemd


def test_login_student_en_paginas(client, student_met_mentor):
    studentnummer = student_met_mentor[0]
    c = client
    r = c.post(
        "/login",
        data={"rol": "student", "identifier": studentnummer, "wachtwoord": "Welkom123"},
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"] == "/student"
    assert c.get("/student").status_code == 200
    assert c.get("/student/voortgang").status_code == 200
    assert c.get("/student/studiegids").status_code == 200


def test_login_fout_wachtwoord_redirect(client, student_met_mentor):
    r = client.post(
        "/login",
        data={"rol": "student", "identifier": student_met_mentor[0], "wachtwoord": "fout"},
        follow_redirects=False,
    )
    assert r.headers["location"] == "/login?fout=1"


def test_mentor_idor_guard(client, student_met_mentor):
    _, eigen_sid, mnaam, _, vreemd = student_met_mentor
    c = client
    c.post(
        "/login",
        data={"rol": "mentor", "identifier": mnaam, "wachtwoord": "Welkom123"},
        follow_redirects=False,
    )
    assert c.get("/mentor").status_code == 200
    assert c.get(f"/mentor/student/{eigen_sid}").status_code == 200  # eigen student → ok
    # vreemde student → geweerd (redirect naar /mentor)
    r = c.get(f"/mentor/student/{vreemd}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/mentor"


def test_api_chat_ongeldige_api_key_geeft_auth_fout(client, monkeypatch):
    """Een 401 van Anthropic (ingetrokken ANTHROPIC_API_KEY) moet als 'auth' in de SSE-stream
    landen, niet als generiek 'onbekend' — anders is een config-storing in de UI onzichtbaar."""
    import httpx

    from app_fastapi import main as main_mod

    def kapot(*a, **k):
        resp = httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com"))
        raise anthropic.AuthenticationError("API key is invalid.", response=resp, body=None)

    # Zonder gekozen OER loopt /api/chat via de intake-tak; die hoeft geen DB-state.
    monkeypatch.setattr(main_mod, "genereer_intake_antwoord", kapot)

    r = client.post("/api/chat", json={"vraag": "hoi"})
    assert r.status_code == 200
    assert 'data: {"error": "auth"}' in r.text
    assert "onbekend" not in r.text


def test_context_migreert_een_oud_schema_bij_eerste_gebruik(tmp_path):
    """De ingebakken productie-DB kan van vóór de `documenten`-tabel zijn: `ValidatieDb`
    migreert bij de eerste verbinding."""
    pad = tmp_path / "oud.db"
    c = db.get_connection(pad)
    db.init_db(c)
    c.execute("DROP TABLE documenten")
    c.commit()
    c.close()

    with ValidatieDb(pad).verbinding() as conn:
        assert conn.execute("SELECT COUNT(*) FROM documenten").fetchone()[0] == 0


def _voeg_documenten_toe(conn, inst: int, *docs) -> None:
    for soort, titel, bestand, kw in docs:
        doc = db.voeg_document_toe(conn, inst, soort, titel, str(bestand), gereviewd=True, **kw)
        db.markeer_document_geindexeerd(conn, doc)


def test_laad_context_bevat_opleidingsgebonden_en_kluisprotocol_uit_documenten(seed, conn):
    """Een gereviewd protocol van de instelling en een examenplan van de opleiding komen in de
    systeemprompt (acceptatie: de assistent kent het kluiscontroleprotocol)."""
    oer_id = seed.oer(crebo="99168", instelling="curio", display="Curio", tekst="OER-TEKST")
    protocol = seed.map / "kluiscontrole.md"
    protocol.write_text("PROTOCOL-KLUISCONTROLE: de kluis wordt wekelijks gecontroleerd.")
    plan = seed.map / "plan.md"
    plan.write_text("EXAMENPLAN-99168: weging 60/40.")
    _voeg_documenten_toe(
        conn,
        seed.instelling("curio", "Curio"),
        ("protocol", "Protocol kluiscontrole", protocol, {}),
        ("examenplan", "Examenplan Kok", plan, {"crebo": "99168"}),
    )

    systeem = laad_context(conn, [oer_id]).systeem
    assert "PROTOCOL-KLUISCONTROLE" in systeem and "EXAMENPLAN-99168" in systeem


def test_laad_context_meldt_documenten_buiten_budget(seed, conn, monkeypatch):
    oer_id = seed.oer(crebo="99168", instelling="curio", display="Curio", tekst="OER-TEKST")
    groot = seed.map / "groot.md"
    groot.write_text("x" * 500)
    _voeg_documenten_toe(
        conn, seed.instelling("curio", "Curio"), ("protocol", "Groot protocol", groot, {})
    )
    monkeypatch.setenv("DOC_BUDGET_TEKENS", "10")

    c = laad_context(conn, [oer_id])
    assert "Groot protocol" in c.melding and "x" * 500 not in c.systeem


def test_chat_js_bevat_status_en_bron_teksten():
    js = Path("app_fastapi/static/chat.js").read_text(encoding="utf-8")
    for code in ("lezen", "intake", "web", "schooldoc", "webinfo"):
        assert f"{code}:" in js
    for t in ("Studiegids", "Kwalificatiedossier", "Schooldocument", "Skills", "Website"):
        assert f'"{t}"' in js
    assert 'startsWith("<!--")' in js  # vangnet in renderMarkdown: elke HTML-commentaarregel
    assert "/api/oer/${b.oer_id}/bestand" in js  # studiegids-chip linkt naar de bestaande route
