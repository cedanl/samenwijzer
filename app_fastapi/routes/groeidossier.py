"""Groeidossier — student-zelfbeoordeling en mentor-beoordeling.

Migratie van app/pages/6_groeidossier.py. Student bewerkt scores/verantwoording
(concept → ingediend) en beheert bewijsstukken; mentor keurt goed of geeft terug
en schrijft feedback per kerntaak. Alle writes lopen via groei_store /
bewijsstuk_store (SQL-guards en bestandsvalidatie zitten dáár).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from urllib.parse import urlencode

import pandas as pd
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response, StreamingResponse

from app_fastapi import data
from app_fastapi.auth import eis_rol, sessie_context
from app_fastapi.templating import templates
from samenwijzer._ai import APITimeoutError, vriendelijke_fout
from samenwijzer.analyze import get_student, oer_label
from samenwijzer.bewijsstuk_store import (
    MAX_GROOTTE_BYTES,
    TOEGESTANE_EXTENSIES,
    BewijsstukFout,
    open_bestand,
)
from samenwijzer.bewijsstuk_store import opslaan as bewijsstuk_opslaan
from samenwijzer.bewijsstuk_store import verwijderen as bewijsstuk_verwijderen
from samenwijzer.groei import (
    delta_t_o_v_vorige,
    klas_gemiddelden_per_wp,
    laatste_twee_metingen_per_wp,
)
from samenwijzer.groei_store import (
    BewijsstukMeta,
    GroeiActueel,
    MentorFeedback,
    dien_in,
    geef_terug,
    get_actueel,
    get_bewijsstuk,
    get_bewijsstukken,
    get_historie,
    get_mentor_feedback,
    insert_bewijsstuk,
    keur_goed,
    sla_groei_op,
    upsert_mentor_feedback,
)
from samenwijzer.groei_store import verwijder_bewijsstuk as verwijder_bewijsstuk_meta
from samenwijzer.transform import get_kerntaak_columns, get_werkproces_columns
from samenwijzer.tutor import aanscherp_verantwoording
from samenwijzer.visualize import spinneweb_figuur

log = logging.getLogger(__name__)
router = APIRouter()

_NIVEAU_LABELS = "Starter · Op weg · Gevorderd · Beroepsbekwaam"

_STATUS_BADGES_STUDENT = {
    "concept": "🟡 Concept",
    "ingediend": "📤 Ingediend — wacht op mentor",
    "goedgekeurd": "✅ Goedgekeurd",
    "teruggegeven": "↩️ Teruggegeven — pas aan en dien opnieuw in",
}
_STATUS_BADGES_DOCENT = {
    "concept": "🟡 Concept (nog niet ingediend)",
    "ingediend": "📤 Ingediend",
    "goedgekeurd": "✅ Goedgekeurd",
    "teruggegeven": "↩️ Teruggegeven",
}

# melding-code → (tekst-template, alert-variant). {n} wordt ingevuld met query-param n.
_MELDINGEN = {
    "opgeslagen": ("{n} wijziging(en) opgeslagen als concept.", "ok"),
    "ingediend": ("{n} werkproces(sen) ingediend bij je mentor.", "ok"),
    "niets_gewijzigd": ("Niets gewijzigd om op te slaan.", ""),
    "niets_indienen": ("Niets om in te dienen — sla eerst een concept op.", ""),
    "upload_ok": ("Bewijsstuk geüpload.", "ok"),
    "upload_te_groot": ("Bestand is te groot; max 10 MB.", "error"),
    "upload_fout": ("Upload geweigerd: controleer bestandstype en grootte.", "error"),
    "verwijderd": ("Bewijsstuk verwijderd.", "ok"),
    "goedgekeurd": ("Goedgekeurd.", "ok"),
    "teruggegeven": ("Teruggegeven met feedback.", "ok"),
    "opmerking_verplicht": ("Geef verbeterfeedback mee bij het teruggeven.", "error"),
    "feedback_ok": ("Feedback opgeslagen.", "ok"),
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _redirect_terug(
    request: Request, melding: str = "", n: int = 0, student: str = "", tab: str = "scores"
) -> RedirectResponse:
    """Redirect naar de hoofdpagina met melding-code (PRG-patroon)."""
    params: dict[str, str] = {}
    if melding:
        params["melding"] = melding
    if n:
        params["n"] = str(n)
    if request.session.get("rol") == "docent" and student:
        params["student"] = student
    if tab != "scores":
        params["tab"] = tab
    suffix = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"/groeidossier{suffix}", status_code=303)


def _resolve_studentnummer(request: Request, student_q: str) -> tuple[str | None, bool]:
    """Bepaal (studentnummer, is_eigenaar) voor de huidige sessie.

    Student: altijd het eigen nummer (query-param wordt genegeerd).
    Docent: alleen studenten uit de eigen groep; None als de groep leeg is
    of het gevraagde nummer niet van een eigen student is.
    """
    if request.session.get("rol") == "student":
        return str(request.session["studentnummer"]), True
    groep = data.mentor_df(request.session.get("mentor_naam", ""))
    if groep.empty:
        return None, False
    nummers = set(groep["studentnummer"].astype(str))
    if student_q:
        return (str(student_q), False) if str(student_q) in nummers else (None, False)
    eerste = groep.sort_values("naam").iloc[0]
    return str(eerste["studentnummer"]), False


def _wp_van_kt(kt_col: str, wp_cols: list[str]) -> list[str]:
    idx = kt_col.removeprefix("kt_")
    return [w for w in wp_cols if w.startswith(f"wp_{idx}_")]


def _relevante_wps(student: pd.Series, df: pd.DataFrame) -> set[str]:
    """Werkproces-kolommen die deze opleiding daadwerkelijk heeft (niet-NaN in df)."""
    return {w for w in get_werkproces_columns(df) if not pd.isna(student.get(w, float("nan")))}


def _huidige_score(student: pd.Series, actueel: dict, wp_col: str) -> int:
    if wp_col in actueel:
        return actueel[wp_col].score
    try:
        waarde = student.get(wp_col)
        return int(float(waarde)) if waarde is not None else 50
    except (TypeError, ValueError):
        return 50


def _kerntaak_blokken(
    df: pd.DataFrame,
    student: pd.Series,
    studentnummer: str,
    opleiding: str,
    crebo: str,
) -> list[dict]:
    """Bouw de view-model-blokken (kerntaak → werkprocessen) voor de template."""
    actueel = {r.wp_kolom: r for r in get_actueel(studentnummer)}
    feedback = get_mentor_feedback(studentnummer)
    stukken_per_wp: dict[str, list] = {}
    for stuk in get_bewijsstukken(studentnummer):
        stukken_per_wp.setdefault(stuk.wp_kolom or "", []).append(stuk)

    wp_cols = get_werkproces_columns(df)
    blokken = []
    for kt_col in get_kerntaak_columns(df):
        eigen_wp = _wp_van_kt(kt_col, wp_cols)
        if not eigen_wp or all(pd.isna(student.get(w, float("nan"))) for w in eigen_wp):
            continue
        wps = []
        for wp_col in eigen_wp:
            rij = actueel.get(wp_col)
            wps.append(
                {
                    "wp_col": wp_col,
                    "label": oer_label(opleiding, wp_col, crebo),
                    "score": _huidige_score(student, actueel, wp_col),
                    "verantwoording": rij.verantwoording if rij else "",
                    "status": rij.status if rij else None,
                    "mentor_opmerking": rij.mentor_opmerking if rij else "",
                    "stukken": stukken_per_wp.get(wp_col, []),
                }
            )
        blokken.append(
            {
                "kt_col": kt_col,
                "label": oer_label(opleiding, kt_col, crebo),
                "feedback": feedback.get(kt_col),
                "wps": wps,
            }
        )
    return blokken


def _spinneweb_data(
    df: pd.DataFrame,
    student: pd.Series,
    studentnummer: str,
    blokken: list[dict],
    opleiding: str,
    crebo: str,
    rol: str | None,
) -> list[dict]:
    """Per kerntaak een Plotly-figuur-JSON (of None als er nog geen meting is)."""
    wp_cols = get_werkproces_columns(df)
    klas_gem = klas_gemiddelden_per_wp(df, opleiding, str(student["cohort"]), wp_cols)
    figuren = []
    for blok in blokken:
        eigen_wp = [wp["wp_col"] for wp in blok["wps"]]
        metingen = laatste_twee_metingen_per_wp(studentnummer, eigen_wp)
        huidig = [metingen[w][0] for w in eigen_wp]
        if not any(v is not None for v in huidig):
            figuren.append({"label": blok["label"], "fig_json": None})
            continue
        fig = spinneweb_figuur(
            titel=blok["label"],
            labels=[oer_label(opleiding, w, crebo) for w in eigen_wp],
            huidig=huidig,
            vorig=[metingen[w][1] for w in eigen_wp],
            klas=[klas_gem.get(w, float("nan")) for w in eigen_wp],
            rol=rol,
        )
        figuren.append({"label": blok["label"], "fig_json": fig.to_json()})
    return figuren


# ── Hoofdpagina ───────────────────────────────────────────────────────────────
@router.get("/groeidossier")
def groeidossier_home(
    request: Request,
    student: str = "",
    tab: str = "scores",
    melding: str = "",
    n: int = 0,
):
    redirect = eis_rol(request, "student", "docent")
    if redirect:
        return redirect

    df = data.get_df()
    ctx = sessie_context(request)
    studentnummer, is_eigenaar = _resolve_studentnummer(request, student)

    groep_opties: list[dict] = []
    if ctx["rol"] == "docent":
        groep = data.mentor_df(ctx["mentor_naam"] or "")
        groep_opties = (
            groep.sort_values("naam")[["naam", "studentnummer"]]
            .apply(lambda r: {"naam": r["naam"], "studentnummer": str(r["studentnummer"])}, axis=1)
            .tolist()
        )
        if studentnummer is None:
            if groep_opties:
                # Onbekend/vreemd studentnummer → terug naar de eigen (eerste) student.
                return RedirectResponse("/groeidossier", status_code=303)
            return templates.TemplateResponse(
                request,
                "groeidossier.html",
                {**ctx, "geen_studenten": True, "groep_opties": groep_opties},
            )

    assert studentnummer is not None
    rij = get_student(df, studentnummer)
    opleiding = str(rij["opleiding"])
    crebo = str(rij.get("crebo", ""))

    blokken = _kerntaak_blokken(df, rij, studentnummer, opleiding, crebo)

    # Historie-tab: lijndata + delta-kaartjes
    historie = get_historie(studentnummer)
    historie_punten = [
        {
            "datum": h.opgeslagen_op[:10],
            "werkproces": oer_label(opleiding, h.wp_kolom, crebo),
            "score": h.score,
        }
        for h in historie
    ]
    deltas = []
    for wp_col in get_werkproces_columns(df):
        d = delta_t_o_v_vorige(studentnummer, wp_col)
        if d is None:
            continue
        deltas.append(
            {
                "label": oer_label(opleiding, wp_col, crebo),
                "delta": d,
                "pijl": "▲" if d > 0 else ("▼" if d < 0 else "■"),
                "richting": "up" if d > 0 else ("down" if d < 0 else "flat"),
            }
        )

    figuren = _spinneweb_data(df, rij, studentnummer, blokken, opleiding, crebo, ctx["rol"])

    melding_info = _MELDINGEN.get(melding)
    return templates.TemplateResponse(
        request,
        "groeidossier.html",
        {
            **ctx,
            "geen_studenten": False,
            "groep_opties": groep_opties,
            "student": rij,
            "gekozen_studentnummer": studentnummer,
            "is_eigenaar": is_eigenaar,
            "opleiding": opleiding,
            "cohort": str(rij["cohort"]),
            "niveau": rij["niveau"],
            "blokken": blokken,
            "badges_student": _STATUS_BADGES_STUDENT,
            "badges_docent": _STATUS_BADGES_DOCENT,
            "niveau_labels": _NIVEAU_LABELS,
            "toegestane_extensies": ",".join(sorted(TOEGESTANE_EXTENSIES)),
            "historie_json": json.dumps(historie_punten),
            "heeft_historie": bool(historie_punten),
            "deltas": deltas,
            "figuren": figuren,
            "actieve_tab": tab if tab in ("scores", "historie", "spinneweb") else "scores",
            "melding_tekst": melding_info[0].format(n=n) if melding_info else "",
            "melding_soort": melding_info[1] if melding_info else "",
        },
    )


# ── Student: concept opslaan / indienen ───────────────────────────────────────
@router.post("/groeidossier/opslaan")
async def groeidossier_opslaan(request: Request):
    redirect = eis_rol(request, "student")
    if redirect:
        return redirect

    vorm = await request.form()
    actie = str(vorm.get("actie", "opslaan"))
    studentnummer = str(request.session["studentnummer"])
    df = data.get_df()
    rij = get_student(df, studentnummer)
    geldige_wps = _relevante_wps(rij, df)

    nieuwe_waarden: dict[str, tuple[int, str]] = {}
    for sleutel in vorm:
        if not sleutel.startswith("score__"):
            continue
        wp = sleutel.removeprefix("score__")
        if wp not in geldige_wps:
            continue
        try:
            score = max(0, min(100, int(str(vorm[sleutel]))))
        except (TypeError, ValueError):
            continue
        verant = str(vorm.get(f"verant__{wp}", ""))[:1000]
        nieuwe_waarden[wp] = (score, verant)

    actueel = {r.wp_kolom: r for r in get_actueel(studentnummer)}
    nu = datetime.now().isoformat(timespec="seconds")
    rijen = [
        GroeiActueel(studentnummer, wp, score, verant, nu)
        for wp, (score, verant) in nieuwe_waarden.items()
        if (wp not in actueel) or actueel[wp].score != score or actueel[wp].verantwoording != verant
    ]
    if rijen:
        sla_groei_op(studentnummer, rijen)

    if actie == "indienen":
        gewijzigde_wps = {r.wp_kolom for r in rijen}
        in_te_dienen = [
            wp
            for wp in nieuwe_waarden
            if wp in gewijzigde_wps or (wp not in actueel) or actueel[wp].status != "goedgekeurd"
        ]
        aantal = dien_in(studentnummer, in_te_dienen)
        if aantal:
            return _redirect_terug(request, "ingediend", n=aantal)
        return _redirect_terug(request, "niets_indienen")
    if rijen:
        return _redirect_terug(request, "opgeslagen", n=len(rijen))
    return _redirect_terug(request, "niets_gewijzigd")


# ── Student: AI-aanscherpen (SSE) ─────────────────────────────────────────────
@router.post("/groeidossier/aanscherpen")
async def groeidossier_aanscherpen(request: Request):
    redirect = eis_rol(request, "student")
    if redirect:
        return redirect

    body = await request.json()
    wp_col = str(body.get("wp_kolom", ""))
    huidige_tekst = str(body.get("tekst", ""))[:1000]
    try:
        score = max(0, min(100, int(body.get("score", 50))))
    except (TypeError, ValueError):
        score = 50

    studentnummer = str(request.session["studentnummer"])
    df = data.get_df()
    rij = get_student(df, studentnummer)
    if wp_col not in _relevante_wps(rij, df):
        return Response(status_code=400)
    opleiding = str(rij["opleiding"])
    crebo = str(rij.get("crebo", ""))
    kt_col = f"kt_{wp_col.removeprefix('wp_').split('_')[0]}"

    def event_stream():
        try:
            stroom = aanscherp_verantwoording(
                werkproces_label=oer_label(opleiding, wp_col, crebo),
                kerntaak_label=oer_label(opleiding, kt_col, crebo),
                opleiding=opleiding,
                huidige_tekst=huidige_tekst,
                score=score,
            )
            for chunk in stroom:
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except APITimeoutError:
            yield f"data: {json.dumps({'error': 'timeout'})}\n\n"
        except Exception as e:  # noqa: BLE001 — nette fout naar de browser
            log.exception("Aanscherpen mislukt")
            yield f"data: {json.dumps({'error': vriendelijke_fout(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Student: bewijsstukken ────────────────────────────────────────────────────
@router.post("/groeidossier/bewijsstuk")
async def groeidossier_upload(
    request: Request,
    wp_kolom: str = Form(...),
    toelichting: str = Form(""),
    bestand: UploadFile = File(...),
):
    redirect = eis_rol(request, "student")
    if redirect:
        return redirect

    studentnummer = str(request.session["studentnummer"])
    df = data.get_df()
    rij = get_student(df, studentnummer)
    if wp_kolom not in _relevante_wps(rij, df):
        return _redirect_terug(request, "upload_fout")

    inhoud = await bestand.read()
    if len(inhoud) > MAX_GROOTTE_BYTES:
        return _redirect_terug(request, "upload_te_groot")
    try:
        rel_pad = bewijsstuk_opslaan(
            studentnummer=studentnummer,
            bestandsnaam=bestand.filename or "bestand",
            inhoud=inhoud,
        )
        insert_bewijsstuk(
            BewijsstukMeta(
                studentnummer=studentnummer,
                wp_kolom=wp_kolom,
                bestandsnaam=bestand.filename or "bestand",
                bestandspad=rel_pad,
                mime_type=bestand.content_type or "application/octet-stream",
                grootte_bytes=len(inhoud),
                toelichting=toelichting[:200],
                geupload_op=datetime.now().isoformat(timespec="seconds"),
            )
        )
    except BewijsstukFout as e:
        log.warning("Upload geweigerd: %s", e)
        return _redirect_terug(request, "upload_fout")
    return _redirect_terug(request, "upload_ok")


@router.post("/groeidossier/bewijsstuk/{bewijsstuk_id}/verwijderen")
def groeidossier_verwijder(request: Request, bewijsstuk_id: int):
    redirect = eis_rol(request, "student")
    if redirect:
        return redirect

    stuk = get_bewijsstuk(bewijsstuk_id)
    if stuk is None or stuk.studentnummer != str(request.session["studentnummer"]):
        return _redirect_terug(request)
    try:
        bewijsstuk_verwijderen(stuk.bestandspad)
    except BewijsstukFout as e:
        log.warning("FS-verwijdering mislukt: %s", e)
    assert stuk.id is not None
    verwijder_bewijsstuk_meta(stuk.id)
    return _redirect_terug(request, "verwijderd")


@router.get("/groeidossier/bewijsstuk/{bewijsstuk_id}")
def groeidossier_download(request: Request, bewijsstuk_id: int):
    redirect = eis_rol(request, "student", "docent")
    if redirect:
        return redirect

    stuk = get_bewijsstuk(bewijsstuk_id)
    if stuk is None:
        return Response(status_code=404)
    if request.session.get("rol") == "student":
        if stuk.studentnummer != str(request.session["studentnummer"]):
            return Response(status_code=403)
    else:
        groep = data.mentor_df(request.session.get("mentor_naam", ""))
        if stuk.studentnummer not in set(groep["studentnummer"].astype(str)):
            return Response(status_code=403)
    try:
        inhoud = open_bestand(stuk.bestandspad)
    except (FileNotFoundError, BewijsstukFout) as e:
        log.warning("Bewijsstuk %s onbereikbaar: %s", stuk.id, e)
        return Response(status_code=404)
    veilige_naam = stuk.bestandsnaam.replace('"', "")
    return Response(
        content=inhoud,
        media_type=stuk.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{veilige_naam}"'},
    )


# ── Docent: beoordelen + kerntaak-feedback ────────────────────────────────────
def _docent_mag(request: Request, studentnummer: str) -> bool:
    groep = data.mentor_df(request.session.get("mentor_naam", ""))
    return str(studentnummer) in set(groep["studentnummer"].astype(str))


@router.post("/groeidossier/beoordeel")
def groeidossier_beoordeel(
    request: Request,
    studentnummer: str = Form(...),
    wp_kolom: str = Form(...),
    actie: str = Form(...),
    opmerking: str = Form(""),
):
    redirect = eis_rol(request, "docent")
    if redirect:
        return redirect
    if not _docent_mag(request, studentnummer):
        return RedirectResponse("/groeidossier", status_code=303)

    mentor = request.session.get("mentor_naam", "onbekend")
    if actie == "goedkeuren":
        keur_goed(studentnummer, wp_kolom, mentor)
        return _redirect_terug(request, "goedgekeurd", student=studentnummer)
    if actie == "teruggeven":
        if not opmerking.strip():
            return _redirect_terug(request, "opmerking_verplicht", student=studentnummer)
        geef_terug(studentnummer, wp_kolom, mentor, opmerking.strip()[:1000])
        return _redirect_terug(request, "teruggegeven", student=studentnummer)
    return _redirect_terug(request, student=studentnummer)


@router.post("/groeidossier/feedback")
def groeidossier_feedback(
    request: Request,
    studentnummer: str = Form(...),
    kt_kolom: str = Form(...),
    tekst: str = Form(""),
):
    redirect = eis_rol(request, "docent")
    if redirect:
        return redirect
    if not _docent_mag(request, studentnummer):
        return RedirectResponse("/groeidossier", status_code=303)

    upsert_mentor_feedback(
        MentorFeedback(
            studentnummer=studentnummer,
            kt_kolom=kt_kolom,
            mentor_naam=request.session.get("mentor_naam", "onbekend"),
            tekst=tekst[:1000],
            geschreven_op=datetime.now().isoformat(timespec="seconds"),
        )
    )
    return _redirect_terug(request, "feedback_ok", student=studentnummer)
