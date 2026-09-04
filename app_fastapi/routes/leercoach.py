"""Leercoach — AI-tutor, lesmateriaal, oefentoets, werkfeedback en rollenspel.

Migratie van ``app/pages/3_leercoach.py``. Chat- en toetsstate leeft per
gebruiker in ``request.session`` (cookie, max ~4 kB): histories worden daarom
strak gebudgetteerd (`_trim_historie`). Omdat een cookie-sessie niet meer
muteerbaar is nadat een StreamingResponse gestart is, worden tutor- en
rollenspelantwoorden eerst server-side gebufferd en daarna als SSE afgespeeld;
stateless streams (lesmateriaal, werkfeedback, toetsfeedback) streamen direct.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable, Mapping, Sequence

import anthropic  # alleen voor except-clausules (zie MIGRATIE.md)
import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from app_fastapi import data
from app_fastapi.auth import eis_rol, sessie_context
from app_fastapi.templating import templates
from samenwijzer._ai import vriendelijke_fout
from samenwijzer.analyze import (
    get_student,
    kerntaak_scores,
    leerpad_niveau,
    werkproces_scores,
    zwakste_kerntaak,
)
from samenwijzer.coach import (
    SCENARIO_OPTIES,
    RollenspelSessie,
    controleer_antwoorden,
    geef_feedback_op_werk,
    genereer_lesmateriaal,
    genereer_oefentoets,
    genereer_rollenspel_feedback,
    stuur_rollenspel_bericht,
)
from samenwijzer.oer_context import haal_oer_context_op
from samenwijzer.tutor import StudentContext, TutorSessie, stuur_bericht
from samenwijzer.whatsapp import laad_whatsapp_gesprek

log = logging.getLogger(__name__)
router = APIRouter()

_TIMEOUT_FOUT = "timeout"
# Sessiecookie-budgetten: berichten en gesprekken cappen zodat de totale
# sessie (rol + leercoach-state) ruim onder de browserlimiet van 4 kB blijft.
_MAX_BERICHT_TEKENS = 600
_TUTOR_BUDGET = 1300
_RP_BUDGET = 1100
_LEERPAD_BADGE = {"gevorderde": "gevorderd"}


# ── Sessie-state helpers ──────────────────────────────────────────────────────
def _staat(request: Request, snr: str) -> dict:
    """Leercoach-state voor de actieve student; wisselen van student reset."""
    staat = request.session.get("leercoach") or {}
    if staat.get("snr") != snr:
        staat = {"snr": snr}
    return staat


def _bewaar_staat(request: Request, staat: dict) -> None:
    request.session["leercoach"] = staat


def _knip(tekst: str) -> str:
    if len(tekst) <= _MAX_BERICHT_TEKENS:
        return tekst
    return tekst[:_MAX_BERICHT_TEKENS] + " …"


def _trim_historie(historie: Sequence[Mapping], budget: int) -> list[dict]:
    """Cap berichten en laat de oudste vallen tot het gesprek binnen budget past.

    De API vereist dat het eerste bericht een user-bericht is, dus na het
    trimmen vervallen leidende assistant-berichten ook.
    """
    geknipt = [{"role": b["role"], "content": _knip(str(b["content"]))} for b in historie]
    while geknipt and len(json.dumps(geknipt, ensure_ascii=False)) > budget:
        geknipt.pop(0)
    while geknipt and geknipt[0]["role"] != "user":
        geknipt.pop(0)
    return geknipt


# ── Student- en profielhelpers ────────────────────────────────────────────────
def _actieve_student(request: Request, gevraagd: str | None, *, strikt: bool) -> str | None:
    """Bepaal de actieve student. Docent mag alleen eigen studenten kiezen."""
    if request.session.get("rol") == "student":
        return str(request.session.get("studentnummer"))
    groep = data.mentor_df(request.session.get("mentor_naam", ""))
    nummers = set(groep["studentnummer"].astype(str))
    if gevraagd is not None and str(gevraagd) in nummers:
        return str(gevraagd)
    if strikt or groep.empty:
        return None
    return str(groep.sort_values("naam")["studentnummer"].iloc[0])


def _profiel(df: pd.DataFrame, snr: str) -> tuple[pd.Series, str, str, str]:
    """Geef (studentrij, opleiding, leerpad, zwakste-kerntaaklabel)."""
    student = get_student(df, snr)
    zkt = zwakste_kerntaak(df, snr)
    return student, str(student["opleiding"]), leerpad_niveau(student), zkt[0] if zkt else ""


def _oer_tekst(student: pd.Series) -> str:
    """OER-context voor de student (``haal_oer_context_op`` verwacht een dict)."""
    return haal_oer_context_op(student.to_dict())


# ── SSE-helpers ───────────────────────────────────────────────────────────────
def _sse(fragmenten: Iterable[str]) -> StreamingResponse:
    """Stream een tekst-iterable als SSE-events: {chunk} / {done} / {error}."""

    def stream():
        try:
            for fragment in fragmenten:
                yield f"data: {json.dumps({'chunk': fragment})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except anthropic.APITimeoutError:
            yield f"data: {json.dumps({'error': _TIMEOUT_FOUT})}\n\n"
        except Exception as e:
            log.exception("Leercoach-stream mislukt")
            yield f"data: {json.dumps({'error': vriendelijke_fout(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


def _sse_fout(boodschap: str) -> StreamingResponse:
    def stream():
        yield f"data: {json.dumps({'error': boodschap})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


async def _api_context(request: Request) -> tuple[tuple[dict, str, pd.DataFrame] | None, object]:
    """Gedeelde validatie voor API-subroutes: rol-guard + student-autorisatie."""
    if eis_rol(request, "student", "docent"):
        return None, JSONResponse({"error": "geen toegang"}, status_code=403)
    body = await request.json()
    snr = _actieve_student(request, body.get("student"), strikt=True)
    if snr is None:
        return None, JSONResponse({"error": "onbekende student"}, status_code=403)
    return (body, snr, data.get_df()), None


# ── Hoofdpagina ───────────────────────────────────────────────────────────────
@router.get("/leercoach")
def leercoach_home(request: Request, student: str = ""):
    redirect = eis_rol(request, "student", "docent")
    if redirect:
        return redirect
    df = data.get_df()
    snr = _actieve_student(request, student or None, strikt=False)
    if snr is None:  # docent zonder studenten
        return RedirectResponse("/home", status_code=303)
    stud, opleiding, leerpad, zwakste = _profiel(df, snr)

    staat = _staat(request, snr)
    if "tutor" not in staat:
        # Eerste bezoek voor deze student: WhatsApp-gesprek als startcontext laden.
        historie: list[dict] = []
        wa = laad_whatsapp_gesprek(snr)
        if wa:
            for bericht in wa.get("gesprek", []):
                wa_rol = "assistant" if bericht.get("rol") == "coach" else "user"
                historie.append({"role": wa_rol, "content": bericht.get("tekst", "")})
            staat["wa_datum"] = str(wa.get("datum", ""))
        staat["tutor"] = _trim_historie(historie, _TUTOR_BUDGET)
        _bewaar_staat(request, staat)

    opties_docent = []
    if request.session.get("rol") == "docent":
        groep = data.mentor_df(request.session.get("mentor_naam", "")).sort_values("naam")
        opties_docent = [
            {"naam": str(r["naam"]), "studentnummer": str(r["studentnummer"])}
            for _, r in groep.iterrows()
        ]

    rp = staat.get("rp")
    rp_tegenpartij = ""
    if rp:
        rp_tegenpartij = RollenspelSessie(
            scenario=rp["scenario"], opleiding=opleiding, leerpad=leerpad, naam=str(stud["naam"])
        ).tegenpartij()

    return templates.TemplateResponse(
        request,
        "leercoach.html",
        {
            **sessie_context(request),
            "student": stud,
            "snr": snr,
            "opleiding": opleiding,
            "leerpad": leerpad,
            "leerpad_badge": _LEERPAD_BADGE.get(leerpad.lower(), leerpad.lower()),
            "zwakste_kt": zwakste,
            "focus_opties": (
                kerntaak_scores(df, snr)["label"].tolist()
                + werkproces_scores(df, snr)["label"].tolist()
            ),
            "opties_docent": opties_docent,
            "tutor_historie": staat.get("tutor", []),
            "wa_datum": staat.get("wa_datum", ""),
            "scenario_opties": SCENARIO_OPTIES,
            "rp": rp,
            "rp_scenario_label": SCENARIO_OPTIES.get(rp["scenario"], "") if rp else "",
            "rp_tegenpartij": rp_tegenpartij,
            "api_key_ontbreekt": not os.environ.get("ANTHROPIC_API_KEY"),
        },
    )


# ── Tutor ─────────────────────────────────────────────────────────────────────
@router.post("/leercoach/api/tutor")
async def api_tutor(request: Request):
    ctx, fout = await _api_context(request)
    if ctx is None:
        return fout
    body, snr, df = ctx
    vraag = str(body.get("vraag", "")).strip()[:2000]
    if not vraag:
        return JSONResponse({"error": "leeg bericht"}, status_code=400)
    stud, opleiding, leerpad, _ = _profiel(df, snr)

    staat = _staat(request, snr)
    sessie = TutorSessie(
        student=StudentContext(
            naam=str(stud["naam"]),
            opleiding=opleiding,
            niveau=int(stud["niveau"]),
            voortgang=float(stud["voortgang"]),
            kerntaak_focus=str(body.get("focus", "")).strip(),
        ),
        geschiedenis=list(staat.get("tutor", [])),
    )
    oer_tekst = _oer_tekst(stud)
    try:
        delen = await run_in_threadpool(lambda: list(stuur_bericht(sessie, vraag, oer_tekst)))
    except anthropic.APITimeoutError:
        return _sse_fout(_TIMEOUT_FOUT)
    except Exception as e:
        log.exception("Tutor-antwoord mislukt")
        return _sse_fout(vriendelijke_fout(e))
    staat["tutor"] = _trim_historie(sessie.geschiedenis, _TUTOR_BUDGET)
    _bewaar_staat(request, staat)
    return _sse(delen)


@router.post("/leercoach/api/tutor/reset")
async def api_tutor_reset(request: Request):
    ctx, fout = await _api_context(request)
    if ctx is None:
        return fout
    _body, snr, _df = ctx
    staat = _staat(request, snr)
    staat["tutor"] = []
    staat.pop("wa_datum", None)
    _bewaar_staat(request, staat)
    return JSONResponse({"ok": True})


# ── Lesmateriaal ──────────────────────────────────────────────────────────────
@router.post("/leercoach/api/les")
async def api_les(request: Request):
    ctx, fout = await _api_context(request)
    if ctx is None:
        return fout
    body, snr, df = ctx
    onderwerp = str(body.get("onderwerp", "")).strip()[:200]
    if not onderwerp:
        return JSONResponse({"error": "Vul een onderwerp in."}, status_code=400)
    stud, opleiding, leerpad, zwakste = _profiel(df, snr)
    return _sse(genereer_lesmateriaal(onderwerp, opleiding, leerpad, zwakste, _oer_tekst(stud)))


# ── Oefentoets ────────────────────────────────────────────────────────────────
@router.post("/leercoach/api/toets")
async def api_toets(request: Request):
    ctx, fout = await _api_context(request)
    if ctx is None:
        return fout
    body, snr, df = ctx
    onderwerp = str(body.get("onderwerp", "")).strip()[:200]
    if not onderwerp:
        return JSONResponse({"error": "Vul een onderwerp in."}, status_code=400)
    stud, opleiding, leerpad, _ = _profiel(df, snr)
    try:
        tekst = await run_in_threadpool(
            genereer_oefentoets, onderwerp, opleiding, leerpad, _oer_tekst(stud)
        )
    except anthropic.APITimeoutError:
        return JSONResponse({"error": _TIMEOUT_FOUT}, status_code=504)
    except Exception as e:
        log.exception("Oefentoets-generatie mislukt")
        return JSONResponse({"error": vriendelijke_fout(e)}, status_code=502)

    vragen_deel = tekst.split("ANTWOORDEN:")[0] if "ANTWOORDEN:" in tekst else tekst
    # Alleen de antwoordsleutel in de sessie (klein); de vragen kent de client.
    staat = _staat(request, snr)
    staat["toets_sleutel"] = tekst[len(vragen_deel) :].strip()[:200]
    _bewaar_staat(request, staat)
    return JSONResponse({"vragen": vragen_deel})


@router.post("/leercoach/api/toets/controleer")
async def api_toets_controleer(request: Request):
    ctx, fout = await _api_context(request)
    if ctx is None:
        return fout
    body, snr, df = ctx
    ruwe_antwoorden = body.get("antwoorden") or {}
    antwoorden: dict[int, str] = {}
    for k, v in ruwe_antwoorden.items():
        if str(v).upper() in {"A", "B", "C", "D"} and str(k).isdigit():
            antwoorden[int(k)] = str(v).upper()
    if len(antwoorden) < 5:
        return JSONResponse({"error": "Beantwoord eerst alle 5 vragen."}, status_code=400)
    vragen = str(body.get("vragen", "")).strip()[:6000]
    sleutel = _staat(request, snr).get("toets_sleutel", "")
    if not vragen or not sleutel:
        return JSONResponse({"error": "Genereer eerst een oefentoets."}, status_code=400)
    _stud, opleiding, leerpad, _ = _profiel(df, snr)
    return _sse(controleer_antwoorden(f"{vragen}\n\n{sleutel}", antwoorden, opleiding, leerpad))


# ── Feedback op werk ──────────────────────────────────────────────────────────
@router.post("/leercoach/api/werk")
async def api_werk(request: Request):
    ctx, fout = await _api_context(request)
    if ctx is None:
        return fout
    body, snr, df = ctx
    werk = str(body.get("tekst", "")).strip()[:20000]
    if not werk:
        return JSONResponse(
            {"error": "Upload een bestand of plak je werk in het tekstvak."}, status_code=400
        )
    stud, opleiding, leerpad, _ = _profiel(df, snr)
    return _sse(geef_feedback_op_werk(werk, opleiding, leerpad, _oer_tekst(stud)))


# ── Rollenspel ────────────────────────────────────────────────────────────────
def _rp_sessie(rp: dict, stud: pd.Series, opleiding: str, leerpad: str) -> RollenspelSessie:
    return RollenspelSessie(
        scenario=rp["scenario"],
        opleiding=opleiding,
        leerpad=leerpad,
        naam=str(stud["naam"]),
        geschiedenis=list(rp.get("hist", [])),
    )


@router.post("/leercoach/api/rollenspel/start")
async def api_rollenspel_start(request: Request):
    ctx, fout = await _api_context(request)
    if ctx is None:
        return fout
    body, snr, _df = ctx
    scenario = str(body.get("scenario", ""))
    if scenario not in SCENARIO_OPTIES:
        return JSONResponse({"error": "onbekend scenario"}, status_code=400)
    staat = _staat(request, snr)
    staat["rp"] = {"scenario": scenario, "hist": [], "klaar": False}
    _bewaar_staat(request, staat)
    return JSONResponse({"ok": True})


@router.post("/leercoach/api/rollenspel/bericht")
async def api_rollenspel_bericht(request: Request):
    ctx, fout = await _api_context(request)
    if ctx is None:
        return fout
    body, snr, df = ctx
    bericht = str(body.get("bericht", "")).strip()[:2000]
    staat = _staat(request, snr)
    rp = staat.get("rp")
    if not bericht or rp is None or rp.get("klaar"):
        return JSONResponse({"error": "geen actief rollenspel"}, status_code=400)
    stud, opleiding, leerpad, _ = _profiel(df, snr)
    sessie = _rp_sessie(rp, stud, opleiding, leerpad)
    oer_tekst = _oer_tekst(stud)
    try:
        delen = await run_in_threadpool(
            lambda: list(stuur_rollenspel_bericht(sessie, bericht, oer_tekst))
        )
    except anthropic.APITimeoutError:
        return _sse_fout(_TIMEOUT_FOUT)
    except Exception as e:
        log.exception("Rollenspel-antwoord mislukt")
        return _sse_fout(vriendelijke_fout(e))
    rp["hist"] = _trim_historie(sessie.geschiedenis, _RP_BUDGET)
    _bewaar_staat(request, staat)
    return _sse(delen)


@router.post("/leercoach/api/rollenspel/feedback")
async def api_rollenspel_feedback(request: Request):
    ctx, fout = await _api_context(request)
    if ctx is None:
        return fout
    _body, snr, df = ctx
    staat = _staat(request, snr)
    rp = staat.get("rp")
    if rp is None or not rp.get("hist"):
        return JSONResponse({"error": "geen gesprek om na te bespreken"}, status_code=400)
    stud, opleiding, leerpad, _ = _profiel(df, snr)
    # Klaar-vlag vóór de stream zetten: de cookie-sessie is daarna niet meer muteerbaar.
    rp["klaar"] = True
    _bewaar_staat(request, staat)
    return _sse(genereer_rollenspel_feedback(_rp_sessie(rp, stud, opleiding, leerpad)))


@router.post("/leercoach/api/rollenspel/reset")
async def api_rollenspel_reset(request: Request):
    ctx, fout = await _api_context(request)
    if ctx is None:
        return fout
    _body, snr, _df = ctx
    staat = _staat(request, snr)
    staat.pop("rp", None)
    _bewaar_staat(request, staat)
    return JSONResponse({"ok": True})
