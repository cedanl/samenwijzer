"""Tests voor de FastAPI-POC (publieke OER-chat)."""

from __future__ import annotations

import json
import logging
import os

import anthropic
import pytest
from dotenv import load_dotenv

from app_fastapi.context import ChatContext, laad_context
from validatie_samenwijzer.documenten import Selectie

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
        if laad_context([row["id"]]).systeem:
            return row["id"]
    return None


def test_laad_context_lege_lijst():
    assert laad_context([]) == ChatContext()


def test_laad_context_onbekende_id():
    # Een niet-bestaand id levert geen leesbare OER → lege context (id blijft genoteerd).
    assert laad_context([99_999_999]) == ChatContext(oer_ids=[99_999_999])


def test_laad_context_geeft_systeem_en_label():
    oer_id = _leesbare_oer_id()
    if oer_id is None:
        pytest.skip("Geen geïndexeerde OER met leesbare tekst beschikbaar (DB/oeren afwezig).")
    c = laad_context([oer_id])
    assert c.systeem and len(c.systeem) > 500
    assert len(c.labels) == 1 and " · " in c.labels[0]
    assert isinstance(c.domeinen, list)
    assert c.oer_ids == [oer_id]


def test_laad_context_student_niveau_minstens_zo_breed():
    """Student-niveau ziet minstens zoveel documenten als publiek."""
    oer_id = _leesbare_oer_id()
    if oer_id is None:
        pytest.skip("Geen geïndexeerde OER met leesbare tekst beschikbaar.")
    publiek = laad_context([oer_id]).systeem
    student = laad_context([oer_id], "student").systeem
    assert len(student) >= len(publiek)


def test_laad_context_bevat_vacature_domeinen():
    oer_id = _leesbare_oer_id()
    if oer_id is None:
        pytest.skip("Geen geïndexeerde OER met leesbare tekst beschikbaar (DB/oeren afwezig).")
    domeinen = laad_context([oer_id]).domeinen
    for d in ("stagemarkt.nl", "indeed.nl"):
        assert d in domeinen


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
    monkeypatch.setattr(ctx, "laad_kwalificatiedossier_tekst", lambda c, *a: "KD-INHOUD")
    monkeypatch.setattr(ctx, "laad_skills_tekst", lambda c: "")
    monkeypatch.setattr(ctx, "selecteer_documenten", lambda *a, **k: Selectie({}, []))
    monkeypatch.setattr(ctx, "web_zoek_domeinen", lambda items: [])

    c = laad_context([1])
    assert "KD-INHOUD" in c.systeem
    assert c.oer_onleesbaar is True
    assert len(c.labels) == 1


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
    monkeypatch.setattr(ctx, "laad_kwalificatiedossier_tekst", lambda c, *a: "")
    monkeypatch.setattr(ctx, "laad_skills_tekst", lambda c: "")
    monkeypatch.setattr(ctx, "selecteer_documenten", lambda *a, **k: Selectie({}, []))
    monkeypatch.setattr(ctx, "web_zoek_domeinen", lambda items: [])

    c = laad_context([1])
    assert "ECHTE OER-TEKST" in c.systeem
    assert c.oer_onleesbaar is False


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

    # main.load_dotenv() zou SESSION_SECRET uit een lokale .env herladen en de
    # fail-closed-check maskeren; noop'en zodat de test ook slaagt op een dev-machine
    # mét .env (niet alleen op CI zonder .env). ALGEMEEN_WACHTWOORD blijft via conftest
    # in os.environ, dus de eerdere fail-closed-guard gaat niet eerst af.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
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


def test_landing_toont_eerst_de_kiezer_en_dan_het_vraagveld():
    """Keuze-eerst: de kiezer staat vóór het (vergrendelde) vraagveld en er is geen vrij
    vraagformulier (`data-ask`) meer op de startpagina."""
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    html = _client().get("/").text
    assert 'id="oplCascade"' in html and 'id="vraagveld"' in html
    assert html.index('id="oplCascade"') < html.index('id="vraagveld"')
    assert "data-ask" not in html
    assert 'class="vraagveld locked"' in html


def test_static_assets_hebben_cache_bust_versie():
    """Cache-busting: terugkerende bezoekers moeten een gewijzigde app.js/app.css oppikken
    zonder hard-refresh — static_url() hangt ?v=<mtime> aan elk static-asset-path."""
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    r = _client().get("/")
    assert r.status_code == 200
    assert "app.js?v=" in r.text
    assert "app.css?v=" in r.text
    assert "chat.js?v=" in r.text


def test_api_vraag_zonder_match_geeft_intake():
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    r = _client().post("/api/vraag", json={"vraag": "zxcvqwer onbekende instelling blabla"})
    assert r.status_code == 200 and r.json()["modus"] == "intake"


def test_api_vraag_en_chat_ongeldige_json_geven_400():
    """Kapotte of lege body mag geen 500 opleveren (input-validatie aan de grens)."""
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    c = _client()
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


def test_api_opleidingen_geeft_boom():
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    r = _client().get("/api/opleidingen")
    assert r.status_code == 200
    boom = r.json()
    assert isinstance(boom, list) and boom
    assert {"instelling", "leerwegen"} <= set(boom[0])


def test_api_kies_zonder_wachtende_vraag():
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    c = _client()  # verse sessie: geen vraag, geen geladen OER
    boom = c.get("/api/opleidingen").json()
    if not boom:
        pytest.skip("geen geïndexeerde OER's in de testdatabase.")
    oer_id = boom[0]["leerwegen"][0]["opleidingen"][0]["cohorten"][0]["oer_ids"][0]
    r = c.post("/api/kies", json={"oer_ids": [oer_id]})
    assert r.status_code == 200
    body = r.json()
    assert body["oer_ids"] == [oer_id]
    assert body["wachtende_vraag"] is None
    assert "labels" in body


def test_api_kies_laadt_meerdere_studiegidsen_naast_elkaar():
    """De kiezer laat er tot 3 combineren; /api/kies moet die lijst ook echt honoreren.

    Guard tegen een terugval naar één gids: elk meegestuurd id hoort in de sessie én
    in de labels terug te komen (de multi-prompt van `bouw_gecombineerd_systeem`).
    """
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    c = _client()
    boom = c.get("/api/opleidingen").json()
    ids: list[int] = []
    for inst in boom:
        for lw in inst["leerwegen"]:
            for opl in lw["opleidingen"]:
                for coh in opl["cohorten"]:
                    for i in coh["oer_ids"]:
                        if i not in ids:
                            ids.append(i)
                    if len(ids) >= 2:
                        break
                if len(ids) >= 2:
                    break
            if len(ids) >= 2:
                break
        if len(ids) >= 2:
            break
    if len(ids) < 2:
        pytest.skip("minder dan 2 geïndexeerde OER's in de testdatabase.")
    gekozen = ids[:2]

    body = c.post("/api/kies", json={"oer_ids": gekozen}).json()

    assert body["oer_ids"] == gekozen
    assert len(body["labels"]) == 2, "elke gekozen studiegids hoort een eigen label te krijgen"


def test_elke_soort_is_zichtbaar_voor_minstens_een_niveau():
    """Guard: een soort moet in minstens één chat-niveau voorkomen, anders is een geïndexeerde
    bron (zoals gedragscode) onzichtbaar als document-fallback."""
    from validatie_samenwijzer import db

    zichtbaar = {
        z
        for niveau in ("publiek", "student", "mentor")
        for z in db.zichtbaarheden_voor_niveau(niveau)
    }
    onzichtbaar = {k for k, v in db.SOORTEN.items() if v.zichtbaarheid not in zichtbaar}
    assert not onzichtbaar, f"Soorten die nergens zichtbaar zijn: {sorted(onzichtbaar)}"


def test_generieke_regelingen_zijn_publiek_zichtbaar():
    """Generieke regelingen zijn een concept voor alle instellingen, ook in de publieke route."""
    from validatie_samenwijzer import db

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


def test_chat_toegewezen_maar_onleesbare_oer_geeft_lage_relevantie(monkeypatch, stub_context):
    """Toegewezen OER zonder bruikbare bron → expliciete melding, geen intake (geen AI-call)."""
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    import app_fastapi.main as m
    from validatie_samenwijzer.chat import LAGE_RELEVANTIE_BERICHT

    # laad_context geeft 'geen bruikbare bron' terug; ai_client mag niet aangeroepen worden.
    stub_context(systeem="", labels=[])
    monkeypatch.setattr(
        m, "ai_client", lambda: (_ for _ in ()).throw(AssertionError("AI niet aanroepen"))
    )
    c = _client()
    c.post("/api/kies", json={"oer_ids": [1]})  # sessie: oer_ids=[1], oer_systeem=""
    r = c.post("/api/chat", json={"vraag": "hoe werkt herkansen?"})
    assert r.status_code == 200
    assert LAGE_RELEVANTIE_BERICHT in r.text


def test_app_logger_staat_op_info():
    # Zonder root-config zou log.info() nergens aankomen (root default = WARNING).
    assert logging.getLogger("oer_poc").getEffectiveLevel() <= logging.INFO
    assert logging.getLogger().handlers


def test_chat_logt_timing_zonder_vraagtekst(monkeypatch, caplog, stub_context):
    """Elke voltooide chat-beurt logt timing/tekens/modus (Fly-zicht) — geen vraagtekst (PII)."""
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    import app_fastapi.main as m

    stub_context(systeem="SYSTEEMPROMPT", domeinen=["stagemarkt.nl", "indeed.nl"])
    monkeypatch.setattr(m, "genereer_antwoord", lambda *a, **k: iter(["Hallo ", "wereld"]))
    c = _client()
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


def test_chat_stuurt_status_lezen_bronnen_en_stript_marker(monkeypatch, stub_context):
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
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
    c = _client()
    c.post("/api/kies", json={"oer_ids": [1]})
    ev = _events(c.post("/api/chat", json={"vraag": "kluisjes?"}).text)
    assert ev[0] == {"status": "lezen"}
    assert {"status": "web"} in ev
    assert "".join(e["chunk"] for e in ev if "chunk" in e) == "Antwoord.\n\n"
    assert ev[-2] == {
        "bronnen": [
            {"type": "studiegids", "titel": "OER Kok", "url": None},
            {"type": "website", "titel": "curio.nl", "url": "https://curio.nl"},
        ]
    }
    assert ev[-1] == {"done": True}
    # ruwe tekst mét marker in de historie; geschiedenis-API stript en levert bronnen
    g = c.get("/api/geschiedenis").json()["beurten"]
    assert g[-1]["content"] == "Antwoord." and g[-1]["bronnen"][0]["titel"] == "OER Kok"
    assert "<!-- bronnen:" not in c.get("/api/geschiedenis").text


def test_chat_meldt_schooldoc_status_uit_tekstbegin(monkeypatch, stub_context):
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
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
    c = _client()
    c.post("/api/kies", json={"oer_ids": [1]})
    ev = _events(c.post("/api/chat", json={"vraag": "statuut?"}).text)
    statussen = [e["status"] for e in ev if "status" in e]
    assert statussen == ["lezen", "schooldoc"]
    assert not any("bronnen" in e for e in ev)


def test_chat_meldt_webinfo_status_ook_bij_één_grote_chunk(monkeypatch, stub_context):
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    import app_fastapi.main as m
    from validatie_samenwijzer.chat import _WEB_DISCLAIMER

    stub_context()
    monkeypatch.setattr(
        m, "genereer_antwoord", lambda *a, **k: iter([_WEB_DISCLAIMER + "\n\nAntwoord"])
    )
    c = _client()
    c.post("/api/kies", json={"oer_ids": [1]})
    ev = _events(c.post("/api/chat", json={"vraag": "web?"}).text)
    assert [e["status"] for e in ev if "status" in e] == ["lezen", "webinfo"]


def test_chat_intake_stuurt_status_intake_zonder_bronnen(monkeypatch):
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    import app_fastapi.main as m

    monkeypatch.setattr(m, "genereer_intake_antwoord", lambda *a, **k: iter(["Welke school?"]))
    ev = _events(_client().post("/api/chat", json={"vraag": "hoi"}).text)
    assert ev[0] == {"status": "intake"}
    assert not any("bronnen" in e for e in ev)


def test_chat_lage_relevantie_stuurt_geen_status(monkeypatch, stub_context):
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    import app_fastapi.main as m

    stub_context(systeem="", labels=[])
    monkeypatch.setattr(
        m, "ai_client", lambda: (_ for _ in ()).throw(AssertionError("AI niet aanroepen"))
    )
    c = _client()
    c.post("/api/kies", json={"oer_ids": [1]})
    ev = _events(c.post("/api/chat", json={"vraag": "x"}).text)
    assert not any("status" in e for e in ev)


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


def test_oer_bestand_download_geeft_attachment():
    """?download=1 levert het bestand als attachment (mobiele download-fallback)."""
    oer_id = _leesbare_oer_id()
    if oer_id is None or not _WW:
        pytest.skip("Geen geïndexeerde OER / ALGEMEEN_WACHTWOORD afwezig.")
    c = _client()
    c.post("/api/kies", json={"oer_ids": [oer_id]})  # zet oer_id in de sessie (IDOR-guard)
    r = c.get(f"/api/oer/{oer_id}/bestand?download=1")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "").lower()


def test_beheer_uit_zonder_flag(monkeypatch):
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    import app_fastapi.main as m

    monkeypatch.setattr(m, "_BEHEER_ENABLED", False)
    c = _client()
    assert c.get("/beheer").status_code == 404
    assert c.get("/api/beheer/run?taak=sync_oeren").status_code == 404


def test_beheer_onbekende_taak_400(monkeypatch):
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
    import app_fastapi.main as m

    monkeypatch.setattr(m, "_BEHEER_ENABLED", True)
    c = _client()
    assert c.get("/api/beheer/run?taak=bestaatniet").status_code == 400
    # ingest zonder geldige instelling → 400
    assert c.get("/api/beheer/run?taak=ingest&instelling=onzin").status_code == 400


def test_beheer_run_streamt_output(monkeypatch):
    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")
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
    monkeypatch.setattr(m, "_BEHEER_ENABLED", True)
    monkeypatch.setattr(m.os, "killpg", lambda pid, sig: gedood.append((pid, sig)))

    async def _fake_exec(*a, **k):
        return _FakeProc()

    monkeypatch.setattr(m.asyncio, "create_subprocess_exec", _fake_exec)

    body = _client().get("/api/beheer/run?taak=sync_oeren").text
    assert "regel1" in body and "regel2" in body
    assert '"done": true' in body


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


def test_api_chat_ongeldige_api_key_geeft_auth_fout(monkeypatch):
    """Een 401 van Anthropic (ingetrokken ANTHROPIC_API_KEY) moet als 'auth' in de SSE-stream
    landen, niet als generiek 'onbekend' — anders is een config-storing in de UI onzichtbaar."""
    import httpx

    from app_fastapi import main as main_mod

    if not _WW:
        pytest.skip("ALGEMEEN_WACHTWOORD niet gezet.")

    def kapot(*a, **k):
        resp = httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com"))
        raise anthropic.AuthenticationError("API key is invalid.", response=resp, body=None)

    # Zonder gekozen OER loopt /api/chat via de intake-tak; die hoeft geen DB-state.
    monkeypatch.setattr(main_mod, "genereer_intake_antwoord", kapot)
    monkeypatch.setattr(main_mod, "ai_client", lambda: object())

    r = _client().post("/api/chat", json={"vraag": "hoi"})
    assert r.status_code == 200
    assert 'data: {"error": "auth"}' in r.text
    assert "onbekend" not in r.text


def test_context_migreert_een_oud_schema_bij_eerste_gebruik(tmp_path, monkeypatch):
    """De ingebakken productie-DB kan van vóór de `documenten`-tabel zijn: `_conn()` migreert."""
    import app_fastapi.context as ctx
    from validatie_samenwijzer import db

    pad = tmp_path / "oud.db"
    c = db.get_connection(pad)
    db.init_db(c)
    c.execute("DROP TABLE documenten")
    c.commit()
    c.close()
    monkeypatch.setenv("DB_PATH", str(pad))
    ctx._gemigreerd.clear()

    conn = ctx._conn()
    assert conn.execute("SELECT COUNT(*) FROM documenten").fetchone()[0] == 0


def test_laad_context_bevat_opleidingsgebonden_en_kluisprotocol_uit_documenten(
    tmp_path, monkeypatch
):
    """Een gereviewd protocol van de instelling en een examenplan van de opleiding komen in de
    systeemprompt (acceptatie: de assistent kent het kluiscontroleprotocol)."""
    import app_fastapi.context as ctx
    from validatie_samenwijzer import db

    pad = tmp_path / "t.db"
    c = db.get_connection(pad)
    db.init_db(c)
    inst = db.voeg_instelling_toe(c, "curio", "Curio")
    protocol = tmp_path / "kluiscontrole.md"
    protocol.write_text("PROTOCOL-KLUISCONTROLE: de kluis wordt wekelijks gecontroleerd.")
    plan = tmp_path / "plan.md"
    plan.write_text("EXAMENPLAN-25168: weging 60/40.")
    for soort, titel, bestand, kw in (
        ("protocol", "Protocol kluiscontrole", protocol, {}),
        ("examenplan", "Examenplan Kok", plan, {"crebo": "25168"}),
    ):
        doc = db.voeg_document_toe(c, inst, soort, titel, str(bestand), gereviewd=True, **kw)
        db.markeer_document_geindexeerd(c, doc)
    monkeypatch.setenv("DB_PATH", str(pad))
    ctx._gemigreerd.clear()
    ctx._oer_blok.cache_clear()
    fake_row = {
        "id": 1, "crebo": "25168", "opleiding": "Kok", "display_naam": "Curio", "naam": "curio",
        "leerweg": "BOL", "cohort": "2025", "instelling_id": inst, "bestandspad": "x.pdf",
    }  # fmt: skip
    monkeypatch.setattr(ctx, "_oer_blok", lambda oid: (fake_row, "OER-TEKST"))
    monkeypatch.setattr(ctx, "laad_kwalificatiedossier_tekst", lambda c, *a: "")
    monkeypatch.setattr(ctx, "laad_skills_tekst", lambda c: "")
    monkeypatch.setattr(ctx, "web_zoek_domeinen", lambda items: [])

    systeem = ctx.laad_context([1]).systeem
    assert "PROTOCOL-KLUISCONTROLE" in systeem and "EXAMENPLAN-25168" in systeem


def test_laad_context_meldt_documenten_buiten_budget(tmp_path, monkeypatch):
    import app_fastapi.context as ctx
    from validatie_samenwijzer import db

    pad = tmp_path / "t.db"
    c = db.get_connection(pad)
    db.init_db(c)
    inst = db.voeg_instelling_toe(c, "curio", "Curio")
    groot = tmp_path / "groot.md"
    groot.write_text("x" * 500)
    doc = db.voeg_document_toe(c, inst, "protocol", "Groot protocol", str(groot), gereviewd=True)
    db.markeer_document_geindexeerd(c, doc)
    monkeypatch.setenv("DB_PATH", str(pad))
    monkeypatch.setenv("DOC_BUDGET_TEKENS", "10")
    ctx._gemigreerd.clear()
    fake_row = {
        "id": 1, "crebo": "25168", "opleiding": "Kok", "display_naam": "Curio", "naam": "curio",
        "leerweg": "BOL", "cohort": "2025", "instelling_id": inst, "bestandspad": "x.pdf",
    }  # fmt: skip
    monkeypatch.setattr(ctx, "_oer_blok", lambda oid: (fake_row, "OER-TEKST"))
    monkeypatch.setattr(ctx, "laad_kwalificatiedossier_tekst", lambda c, *a: "")
    monkeypatch.setattr(ctx, "laad_skills_tekst", lambda c: "")
    monkeypatch.setattr(ctx, "web_zoek_domeinen", lambda items: [])

    c = ctx.laad_context([1])
    assert "Groot protocol" in c.melding and "x" * 500 not in c.systeem


def test_chat_js_bevat_status_en_bron_teksten():
    from pathlib import Path

    js = Path("app_fastapi/static/chat.js").read_text(encoding="utf-8")
    for code in ("lezen", "intake", "web", "schooldoc", "webinfo"):
        assert f"{code}:" in js
    for t in ("Studiegids", "Kwalificatiedossier", "Schooldocument", "Skills", "Website"):
        assert f'"{t}"' in js
    assert 'startsWith("<!--")' in js  # vangnet in renderMarkdown: elke HTML-commentaarregel
