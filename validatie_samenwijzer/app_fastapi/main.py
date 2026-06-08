"""FastAPI-POC voor de publieke OER-chat — hergebruikt chat.py ongewijzigd.

Lokaal draaien (naast Streamlit op 8503):
    uv run uvicorn app_fastapi.main:app --port 8504 --reload
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app_fastapi.context import laad_context
from app_fastapi.sessie import get_sessie
from validatie_samenwijzer import db
from validatie_samenwijzer._ai import _client as ai_client
from validatie_samenwijzer.chat import (
    bouw_berichten,
    genereer_antwoord,
    genereer_intake_antwoord,
    identificeer_oer_kandidaten,
    resolve_oer_pad,
)

load_dotenv()
log = logging.getLogger("oer_poc")

_HIER = Path(__file__).resolve().parent
app = FastAPI(title="De digitale gids — POC")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET", "dev-poc-secret"))
app.mount("/static", StaticFiles(directory=_HIER / "static"), name="static")
templates = Jinja2Templates(directory=_HIER / "templates")

_MAX_KANDIDATEN = 40


def _conn():
    return db.get_connection(os.environ.get("DB_PATH", "data/validatie.db"))


def _instellingen() -> list[str]:
    rows = _conn().execute("SELECT DISTINCT display_naam FROM instellingen ORDER BY 1").fetchall()
    return [r["display_naam"] for r in rows]


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/vraag")
async def api_vraag(request: Request):
    """Identificeer de OER(s) voor een vraag; bepaal de modus (chat/kies/intake)."""
    vraag = (await request.json()).get("vraag", "").strip()
    if not vraag:
        return JSONResponse({"modus": "intake"})
    s = get_sessie(request)

    # Al een OER geladen? → direct doorchatten.
    if s.oer_systeem:
        return JSONResponse({"modus": "chat", "labels": s.oer_labels})

    oers = [dict(r) for r in db.get_alle_oers_met_instelling(_conn())]
    kandidaten = identificeer_oer_kandidaten(oers, vraag, min_score=1)

    if len(kandidaten) == 1:
        oer_id = kandidaten[0]["id"]
        s.oer_systeem, s.oer_labels, s.domeinen = laad_context([oer_id])
        s.oer_ids = [oer_id]
        return JSONResponse({"modus": "chat", "labels": s.oer_labels, "oer_ids": s.oer_ids})

    if len(kandidaten) > 1:
        s.kandidaten = kandidaten[:_MAX_KANDIDATEN]
        s.wachtende_vraag = vraag
        opties = [
            {
                "id": k["id"],
                "label": f"{k['display_naam']} · {k['opleiding']} · {k['leerweg']} {k['cohort']}",
            }
            for k in s.kandidaten
        ]
        return JSONResponse({"modus": "kies", "opties": opties})

    return JSONResponse({"modus": "intake"})


@app.post("/api/kies")
async def api_kies(request: Request):
    """Laad de gekozen OER's als context en geef de wachtende vraag terug."""
    oer_ids = (await request.json()).get("oer_ids", [])[:3]
    s = get_sessie(request)
    s.oer_systeem, s.oer_labels, s.domeinen = laad_context([int(i) for i in oer_ids])
    s.oer_ids = [int(i) for i in oer_ids]
    s.kandidaten = []
    vraag, s.wachtende_vraag = s.wachtende_vraag, None
    return JSONResponse({"labels": s.oer_labels, "oer_ids": s.oer_ids, "wachtende_vraag": vraag})


@app.post("/api/chat")
async def api_chat(request: Request):
    """Stream een antwoord (chat of intake) als Server-Sent Events."""
    vraag = (await request.json()).get("vraag", "").strip()
    s = get_sessie(request)
    berichten = bouw_berichten(s.chat_history, vraag)
    systeem = s.oer_systeem
    domeinen = s.domeinen or None
    instellingen = _instellingen()

    def stream():
        antwoord = ""
        try:
            client = ai_client()
            if systeem:
                gen = genereer_antwoord(client, systeem, berichten, web_search_domeinen=domeinen)
            else:
                gen = genereer_intake_antwoord(client, berichten, instellingen)
            for chunk in gen:
                antwoord += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            s.voeg_beurt_toe(vraag, antwoord)
            yield f"data: {json.dumps({'done': True})}\n\n"
        except anthropic.APITimeoutError:
            yield f"data: {json.dumps({'error': 'timeout'})}\n\n"
        except Exception:
            log.exception("chat-stream mislukt")
            yield f"data: {json.dumps({'error': 'onbekend'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/oer/{oer_id}/bestand")
def api_oer_bestand(oer_id: int):
    """Serveer het OER-bronbestand (PDF inline / markdown) voor de viewer."""
    row = (
        _conn().execute("SELECT bestandspad FROM oer_documenten WHERE id = ?", (oer_id,)).fetchone()
    )
    if row is None:
        return JSONResponse({"error": "onbekend"}, status_code=404)
    pad = resolve_oer_pad(row["bestandspad"])
    if not pad.exists():
        return JSONResponse({"error": "bestand ontbreekt"}, status_code=404)
    media = "application/pdf" if pad.suffix.lower() == ".pdf" else "text/plain; charset=utf-8"
    return FileResponse(pad, media_type=media)


@app.post("/api/reset")
def api_reset(request: Request):
    get_sessie(request).reset()
    return JSONResponse({"ok": True})
