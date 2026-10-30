"""Heartbeat + harde tijdslimiet op de chat-stream (`/api/chat`).

Aanleiding (2026-10-29): het prod-proces bleef hangen vóór de Anthropic-call; de browser kreeg
alleen `{"status":"lezen"}` en de Fly-proxy kapte na ~60s stilte de verbinding ("Verbinding
verbroken"). De 30s-httpx-timeout ging niet af. Vangnet: bij stilte periodiek een `ping`-event
(houdt de proxy wakker) en na `AppDeps.chat_max_seconden` een `error: timeout` + stacktrace
in het log.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time

import pytest


def _verzamel(gen, heartbeat_s, max_s):
    import app_fastapi.main as m

    async def run():
        return [x async for x in m._met_heartbeat(gen, heartbeat_s=heartbeat_s, max_s=max_s)]

    return asyncio.run(run())


def _events(items: list[str]) -> list[dict]:
    return [json.loads(x[6:]) for x in items if x.startswith("data: ")]


def test_items_passeren_in_volgorde_zonder_ping_bij_snelle_stream():
    uit = _verzamel(iter(["a", "b", "c"]), heartbeat_s=1.0, max_s=5.0)
    assert uit == ["a", "b", "c"]


def test_ping_bij_stilte_en_daarna_gewoon_verder():
    def traag():
        yield "eerst"
        time.sleep(0.25)
        yield "later"

    uit = _verzamel(traag(), heartbeat_s=0.05, max_s=5.0)
    assert uit[0] == "eerst" and uit[-1] == "later"
    pings = [x for x in uit if x.startswith("data: ")]
    assert pings and all(json.loads(p[6:]) == {"ping": True} for p in pings)


def test_tijdslimiet_geeft_timeout_event_en_logt_stack(caplog):
    gestart = threading.Event()

    def hangt():
        yield "start"
        gestart.set()
        time.sleep(2.0)  # simuleert een thread die vastzit in de AI-call
        yield "te laat"

    with caplog.at_level(logging.ERROR, logger="oer_poc"):
        uit = _verzamel(hangt(), heartbeat_s=0.05, max_s=0.3)
    assert uit[0] == "start"
    assert _events(uit)[-1] == {"error": "timeout"}
    assert "te laat" not in uit
    assert gestart.is_set()
    # Diagnose voor de volgende keer: waar stond de vastgelopen thread?
    assert any(
        "chat-stream afgebroken" in r.message and "time.sleep" in r.message for r in caplog.records
    )


def test_exception_in_generator_wordt_doorgegeven():
    def kapot():
        yield "ok"
        raise RuntimeError("boem")

    with pytest.raises(RuntimeError, match="boem"):
        _verzamel(kapot(), heartbeat_s=1.0, max_s=5.0)


def test_api_chat_stuurt_ping_bij_stilte(maak_client, monkeypatch, stub_context):
    """End-to-end: een trage AI-generator levert ping-events tussen 'lezen' en het antwoord."""
    import app_fastapi.main as m

    stub_context()

    def traag(*a, **k):
        time.sleep(0.3)
        yield "Antwoord."

    monkeypatch.setattr(m, "genereer_antwoord", traag)
    c = maak_client(chat_heartbeat_seconden=0.05)
    c.post("/api/kies", json={"oer_ids": [1]})
    r = c.post("/api/chat", json={"vraag": "kluisjes?"})
    ev = [json.loads(x[6:]) for x in r.text.splitlines() if x.startswith("data: ")]
    assert ev[0] == {"status": "lezen"}
    assert {"ping": True} in ev
    assert "".join(e.get("chunk", "") for e in ev) == "Antwoord."
    assert ev[-1] == {"done": True}
    assert r.headers.get("x-accel-buffering") == "no"


# ── afgebroken beurt blijft in het Gesprek ────────────────────────────────────────
def test_bij_timeout_callback_draait_voor_het_error_event():
    volgorde: list[str] = []

    def hangt():
        yield "start"
        time.sleep(1.0)

    import app_fastapi.main as m

    async def run():
        uit = []
        async for x in m._met_heartbeat(
            hangt(), heartbeat_s=0.05, max_s=0.2, bij_timeout=lambda: volgorde.append("cb")
        ):
            uit.append(x)
            if not x.startswith("data: ") or json.loads(x[6:]) != {"ping": True}:
                volgorde.append("event")
        return uit

    asyncio.run(run())
    assert volgorde == ["event", "cb", "event"]  # start, callback, error


def test_fout_in_bij_timeout_callback_houdt_error_event(caplog):
    def hangt():
        yield "start"
        time.sleep(1.0)

    def kapot():
        raise RuntimeError("opslaan faalt")

    import app_fastapi.main as m

    async def run():
        return [
            x
            async for x in m._met_heartbeat(hangt(), heartbeat_s=0.05, max_s=0.2, bij_timeout=kapot)
        ]

    with caplog.at_level(logging.ERROR, logger="oer_poc"):
        uit = asyncio.run(run())
    assert _events(uit)[-1] == {"error": "timeout"}
    assert any("afgebroken beurt vastleggen mislukt" in r.message for r in caplog.records)


def test_api_chat_timeout_bewaart_afgebroken_beurt(maak_client, monkeypatch, stub_context):
    """Een hangende stream: vraag + gedeeltelijk antwoord blijven als afgebroken beurt in het
    Gesprek (zonder halve marker), en een late afronding van de losgelaten worker voegt geen
    tweede beurt toe."""
    import app_fastapi.main as m

    stub_context()

    def hangt(*a, **k):
        yield "Eerste deel.\n\n<!-- bro"
        time.sleep(0.8)  # de AI-call hangt
        yield "nnen: studiegids|OER -->"  # komt na de timeout alsnog binnen

    monkeypatch.setattr(m, "genereer_antwoord", hangt)
    c = maak_client(chat_heartbeat_seconden=0.05, chat_max_seconden=0.3)
    c.post("/api/kies", json={"oer_ids": [1]})

    r = c.post("/api/chat", json={"vraag": "kluisjes?"})
    assert _events(r.text.splitlines())[-1] == {"error": "timeout"}

    beurten = c.get("/api/geschiedenis").json()["beurten"]
    assert beurten == [
        {"role": "user", "content": "kluisjes?"},
        {"role": "assistant", "content": "Eerste deel.", "bronnen": [], "afgebroken": True},
    ]
    assert "<!--" not in c.get("/api/geschiedenis").text

    time.sleep(1.0)  # de losgelaten worker rondt af: mag niets meer toevoegen
    assert len(c.get("/api/geschiedenis").json()["beurten"]) == 2

    # Volgende beurt: het model ziet een consistente historie, zonder halve marker.
    gezien: list[list[dict]] = []

    def antwoord(client, systeem, berichten, **k):
        gezien.append(berichten)
        yield "Ok."

    monkeypatch.setattr(m, "genereer_antwoord", antwoord)
    # (de tijdslimiet van 0.3s is ruim voor een antwoord dat direct komt)
    c.post("/api/chat", json={"vraag": "nog eens"})
    assert gezien[0] == [
        {"role": "user", "content": "kluisjes?"},
        {"role": "assistant", "content": "Eerste deel.\n\n[antwoord afgebroken]"},
        {"role": "user", "content": "nog eens"},
    ]


def test_api_chat_exceptie_bewaart_afgebroken_beurt(client, monkeypatch, stub_context):
    import app_fastapi.main as m

    stub_context()

    def faalt(*a, **k):
        yield "Half antwoord"
        raise RuntimeError("boem")

    monkeypatch.setattr(m, "genereer_antwoord", faalt)
    c = client
    c.post("/api/kies", json={"oer_ids": [1]})

    r = c.post("/api/chat", json={"vraag": "kluisjes?"})
    assert _events(r.text.splitlines())[-1] == {"error": "onbekend"}
    beurten = c.get("/api/geschiedenis").json()["beurten"]
    assert beurten[0] == {"role": "user", "content": "kluisjes?"}
    assert beurten[1]["afgebroken"] is True and beurten[1]["content"] == "Half antwoord"
