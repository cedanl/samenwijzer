"""FastAPI-POC voor de publieke OER-chat — hergebruikt chat.py ongewijzigd.

Lokaal draaien (naast Streamlit op 8503):
    uv run uvicorn app_fastapi.main:app --port 8504 --reload
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app_fastapi import data
from app_fastapi.auth import auth_mentor, auth_student
from app_fastapi.context import MENTOR_SOORTEN, STUDENT_SOORTEN, laad_context
from app_fastapi.sessie import bewaar_sessie, get_sessie
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
_ALGEMEEN_WACHTWOORD = os.environ.get("ALGEMEEN_WACHTWOORD", "")

_HIER = Path(__file__).resolve().parent
app = FastAPI(title="De digitale gids — POC")


@app.middleware("http")
async def _toegangspoort(request: Request, call_next):
    """De hele app zit achter het algemene wachtwoord — sommige instellingen zetten
    hun OER achter een wachtwoord, dus niets is publiek vindbaar zonder de poort."""
    pad = request.url.path
    if pad.startswith("/static"):
        return await call_next(request)
    if pad != "/toegang" and not get_sessie(request).toegang:
        if pad.startswith("/api/"):
            return JSONResponse({"error": "geen toegang"}, status_code=401)
        return RedirectResponse("/toegang", status_code=303)
    response = await call_next(request)
    # Bewaar alleen op mutaterende requests. Een read-only GET zou zijn (stale) kopie
    # terugschrijven en zo een gelijktijdige chat-beurt kunnen overschrijven (lost update).
    # /api/chat bewaart zélf ná de stream (post-turn); de twee mutaterende GET-routes
    # (/uitloggen, /mentor/student/...) bewaren expliciet in hun handler.
    if request.method != "GET" and pad != "/api/chat":
        bewaar_sessie(request)
    return response


# SessionMiddleware ná de poort geregistreerd → draait als buitenste laag, zodat
# request.session (en dus get_sessie) in de poort beschikbaar is.
_SESSION_SECRET = os.environ.get("SESSION_SECRET")
if not _SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET is verplicht (geen default) — zet 'm in .env / Fly-secrets.")
app.add_middleware(
    SessionMiddleware,
    secret_key=_SESSION_SECRET,
    https_only=os.environ.get("COOKIE_HTTPS_ONLY", "1") != "0",
    same_site="lax",
)
app.mount("/static", StaticFiles(directory=_HIER / "static"), name="static")
templates = Jinja2Templates(directory=_HIER / "templates")

_MAX_KANDIDATEN = 40

# ── Beheer (dev-only, achter BEHEER_ENABLED) ────────────────────────────────────
_BEHEER_ENABLED = os.environ.get("BEHEER_ENABLED", "").lower() == "true"
_PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)  # repo-root: scripts/ + uv verwachten dit als cwd
_INSTELLING_KEYS = {
    "aeres",
    "curio",
    "davinci",
    "deltion",
    "kwic",
    "rijn_ijssel",
    "talland",
    "utrecht",
}
# Vaste commando-allowlist: de browser stuurt alleen een taak-KEY, nooit een commando-string.
_BEHEER_TAKEN: dict[str, list[str]] = {
    "sync_oeren": ["bash", "scripts/sync_oeren.sh"],
    "ingest_alles": ["uv", "run", "python", "-m", "validatie_samenwijzer.ingest", "--alles"],
    "ingest": ["uv", "run", "python", "-m", "validatie_samenwijzer.ingest"],  # vereist --instelling
    "seed_bulk": ["uv", "run", "python", "scripts/seed_bulk.py"],
    "seed_minimal": ["uv", "run", "python", "scripts/seed.py"],
    "kd_sync": ["bash", "scripts/sync_kwalificatiedossiers.sh"],
}


def _beheer_status() -> dict:
    """OERs per instelling (totaal + geïndexeerd) en de laatste ingest-run."""
    conn = db.get_connection(os.environ.get("DB_PATH", "data/validatie.db"))
    db.init_db(conn)
    rijen = conn.execute(
        "SELECT i.display_naam, COUNT(*) AS totaal, "
        "SUM(CASE WHEN o.geindexeerd=1 THEN 1 ELSE 0 END) AS geindexeerd "
        "FROM oer_documenten o JOIN instellingen i ON i.id = o.instelling_id "
        "GROUP BY i.display_naam ORDER BY i.display_naam"
    ).fetchall()
    laatste = db.laatste_ingest_run(conn)
    return {
        "per_instelling": [dict(r) for r in rijen],
        "laatste_ingest": dict(laatste) if laatste else None,
    }


@app.get("/toegang")
def toegang_form(request: Request, fout: int = 0):
    return templates.TemplateResponse(request, "toegang.html", {"fout": bool(fout)})


@app.post("/toegang")
def toegang_post(request: Request, wachtwoord: str = Form(...)):
    if _ALGEMEEN_WACHTWOORD and wachtwoord == _ALGEMEEN_WACHTWOORD:
        get_sessie(request).toegang = True
        return RedirectResponse("/", status_code=303)
    return RedirectResponse("/toegang?fout=1", status_code=303)


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
        return JSONResponse(
            {"modus": "chat", "labels": s.oer_labels, "oer_onleesbaar": s.oer_onleesbaar}
        )

    oers = [dict(r) for r in db.get_alle_oers_met_instelling(_conn())]
    kandidaten = identificeer_oer_kandidaten(oers, vraag, min_score=1)

    if len(kandidaten) == 1:
        oer_id = kandidaten[0]["id"]
        s.oer_systeem, s.oer_labels, s.domeinen, s.oer_onleesbaar = laad_context([oer_id])
        s.oer_ids = [oer_id]
        return JSONResponse(
            {
                "modus": "chat",
                "labels": s.oer_labels,
                "oer_ids": s.oer_ids,
                "oer_onleesbaar": s.oer_onleesbaar,
            }
        )

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
    s.oer_systeem, s.oer_labels, s.domeinen, s.oer_onleesbaar = laad_context(
        [int(i) for i in oer_ids]
    )
    s.oer_ids = [int(i) for i in oer_ids]
    s.kandidaten = []
    vraag, s.wachtende_vraag = s.wachtende_vraag, None
    return JSONResponse(
        {
            "labels": s.oer_labels,
            "oer_ids": s.oer_ids,
            "wachtende_vraag": vraag,
            "oer_onleesbaar": s.oer_onleesbaar,
        }
    )


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
            bewaar_sessie(request)
            yield f"data: {json.dumps({'done': True})}\n\n"
        except anthropic.APITimeoutError:
            yield f"data: {json.dumps({'error': 'timeout'})}\n\n"
        except Exception:
            log.exception("chat-stream mislukt")
            yield f"data: {json.dumps({'error': 'onbekend'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/oer/{oer_id}/bestand")
def api_oer_bestand(request: Request, oer_id: int, download: int = 0):
    """Serveer het OER-bronbestand (PDF inline / markdown) voor de viewer.

    Alleen de OER('s) die in de eigen sessie geladen zijn — anders kon men per id
    elke (ook rechten-beperkte) studiegids enumereren/downloaden. ``?download=1``
    serveert als attachment (mobiele fallback wanneer inline-rendering faalt).
    """
    if oer_id not in get_sessie(request).oer_ids:
        return JSONResponse({"error": "geen toegang"}, status_code=403)
    row = (
        _conn().execute("SELECT bestandspad FROM oer_documenten WHERE id = ?", (oer_id,)).fetchone()
    )
    if row is None:
        return JSONResponse({"error": "onbekend"}, status_code=404)
    pad = resolve_oer_pad(row["bestandspad"])
    if not pad.exists():
        return JSONResponse({"error": "bestand ontbreekt"}, status_code=404)
    media = "application/pdf" if pad.suffix.lower() == ".pdf" else "text/plain; charset=utf-8"
    if download:
        # filename= zet automatisch Content-Disposition: attachment
        return FileResponse(pad, media_type=media, filename=pad.name)
    return FileResponse(pad, media_type=media)


@app.post("/api/reset")
def api_reset(request: Request):
    s = get_sessie(request)
    if s.rol:  # ingelogd: OER-context blijft, alleen het gesprek wist
        s.nieuw_gesprek()
    else:
        s.reset()
    return JSONResponse({"ok": True})


@app.get("/api/geschiedenis")
def api_geschiedenis(request: Request):
    """Geef de bewaarde gespreksgeschiedenis terug voor rehydratie bij page-load."""
    return JSONResponse({"beurten": get_sessie(request).chat_history})


# ── Login / sessie ─────────────────────────────────────────────────────────────
@app.get("/login")
def login_form(request: Request, fout: int = 0):
    return templates.TemplateResponse(request, "login.html", {"fout": bool(fout)})


@app.post("/login")
def login_post(
    request: Request,
    rol: str = Form(...),
    identifier: str = Form(...),
    wachtwoord: str = Form(...),
):
    s = get_sessie(request)
    if rol == "student":
        student = auth_student(identifier, wachtwoord)
        if student:
            s.uitloggen()
            s.rol = "student"
            s.gebruiker = {
                "id": student["id"],
                "naam": student["naam"],
                "studentnummer": student["studentnummer"],
            }
            s.oer_systeem, s.oer_labels, s.domeinen, s.oer_onleesbaar = laad_context(
                [student["oer_id"]], STUDENT_SOORTEN
            )
            s.oer_ids = [student["oer_id"]]
            return RedirectResponse("/student", status_code=303)
    elif rol == "mentor":
        mentor = auth_mentor(identifier, wachtwoord)
        if mentor:
            s.uitloggen()
            s.rol = "mentor"
            s.gebruiker = {"id": mentor["id"], "naam": mentor["naam"]}
            return RedirectResponse("/mentor", status_code=303)
    return RedirectResponse("/login?fout=1", status_code=303)


@app.get("/uitloggen")
def uitloggen(request: Request):
    get_sessie(request).uitloggen()
    bewaar_sessie(request)  # mutaterende GET → expliciet bewaren (middleware slaat GET over)
    return RedirectResponse("/", status_code=303)


def _eis(request: Request, rol: str):
    s = get_sessie(request)
    return s if s.rol == rol else None


# ── Student ─────────────────────────────────────────────────────────────────────
@app.get("/student")
def student_home(request: Request):
    s = _eis(request, "student")
    if not s:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "student_assistent.html",
        {
            "rol": "student",
            "naam": s.gebruiker["naam"],
            "labels": s.oer_labels,
            "oer_onleesbaar": s.oer_onleesbaar,
        },
    )


@app.get("/student/studiegids")
def student_studiegids(request: Request):
    s = _eis(request, "student")
    if not s:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "studiegids.html",
        {
            "oer_id": s.oer_ids[0] if s.oer_ids else None,
            "labels": s.oer_labels,
            "rol": "student",
            "naam": s.gebruiker["naam"],
        },
    )


@app.get("/student/voortgang")
def student_voortgang(request: Request):
    s = _eis(request, "student")
    if not s:
        return RedirectResponse("/login", status_code=303)
    vg = data.voortgang_voor_studentnummer(s.gebruiker["studentnummer"])
    return templates.TemplateResponse(
        request, "voortgang.html", {"rol": "student", "vg": vg, "naam": s.gebruiker["naam"]}
    )


# ── Mentor ──────────────────────────────────────────────────────────────────────
@app.get("/mentor")
def mentor_home(request: Request):
    s = _eis(request, "mentor")
    if not s:
        return RedirectResponse("/login", status_code=303)
    studenten = data.studenten_van_mentor(s.gebruiker["id"])
    return templates.TemplateResponse(
        request,
        "mentor_studenten.html",
        {"rol": "mentor", "studenten": studenten, "naam": s.gebruiker["naam"]},
    )


@app.get("/mentor/student/{student_id}")
def mentor_sessie(request: Request, student_id: int):
    s = _eis(request, "mentor")
    if not s:
        return RedirectResponse("/login", status_code=303)
    # IDOR-guard: een mentor mag alleen z'n eigen studenten openen.
    if student_id not in {st["id"] for st in data.studenten_van_mentor(s.gebruiker["id"])}:
        return RedirectResponse("/mentor", status_code=303)
    prof = data.profiel_van_student(student_id)
    s.actieve_student = prof
    s.oer_systeem, s.oer_labels, s.domeinen, s.oer_onleesbaar = laad_context(
        [prof["oer_id"]], MENTOR_SOORTEN
    )
    s.oer_ids = [prof["oer_id"]]
    s.chat_history = []
    bewaar_sessie(request)  # mutaterende GET → expliciet bewaren (middleware slaat GET over)
    return templates.TemplateResponse(
        request,
        "mentor_sessie.html",
        {
            "rol": "mentor",
            "prof": prof,
            "labels": s.oer_labels,
            "naam": s.gebruiker["naam"],
            "oer_onleesbaar": s.oer_onleesbaar,
        },
    )


# ── Beheer (dev-only) ───────────────────────────────────────────────────────────
@app.get("/beheer")
def beheer_home(request: Request):
    if not _BEHEER_ENABLED:
        return JSONResponse({"error": "uit"}, status_code=404)
    return templates.TemplateResponse(
        request,
        "beheer.html",
        {
            "status": _beheer_status(),
            "instellingen": sorted(_INSTELLING_KEYS),
        },
    )


@app.get("/api/beheer/run")
def beheer_run(request: Request, taak: str, reset: int = 0, instelling: str = ""):
    """Stream de stdout van een vaste beheer-taak als SSE. GET → middleware bewaart niet.

    Veiligheid: dubbele gate (BEHEER_ENABLED + algemene poort), vaste commando-allowlist
    (lijst-vorm Popen, geen shell), gevalideerde scope, cwd hard op de repo-root.
    """
    if not _BEHEER_ENABLED:
        return JSONResponse({"error": "uit"}, status_code=404)
    cmd = list(_BEHEER_TAKEN.get(taak, []))
    if not cmd:
        return JSONResponse({"error": "onbekende taak"}, status_code=400)
    if taak == "ingest":
        if instelling not in _INSTELLING_KEYS:
            return JSONResponse({"error": "ongeldige instelling"}, status_code=400)
        cmd = cmd + ["--instelling", instelling]
    if reset:
        cmd.append("--reset")

    def stream():
        proc = subprocess.Popen(
            cmd,
            cwd=str(_PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for regel in iter(proc.stdout.readline, ""):
            yield f"data: {json.dumps({'regel': regel.rstrip()})}\n\n"
        proc.wait()
        yield f"data: {json.dumps({'done': True, 'exit': proc.returncode})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
