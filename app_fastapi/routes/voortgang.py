"""Voortgang — studievoortgang, kerntaak-/werkprocesscores en AI-weekplan.

Student ziet zijn eigen dashboard; docent kiest eerst een student uit de
eigen mentorgroep (``data.mentor_df``). 1-op-1 geport uit
``app/pages/1_mijn_voortgang.py``.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app_fastapi import data
from app_fastapi.auth import eis_rol, sessie_context
from app_fastapi.templating import templates
from samenwijzer._ai import APITimeoutError, vriendelijke_fout
from samenwijzer.analyze import (
    cohort_positie,
    get_student,
    kerntaak_scores,
    leerpad_niveau,
    werkproces_scores,
    zwakste_kerntaak,
    zwakste_werkproces,
)
from samenwijzer.coach import genereer_weekplan
from samenwijzer.groei import heeft_self_rating
from samenwijzer.visualize import werkproces_grafiek

log = logging.getLogger(__name__)

router = APIRouter()

# Bron-pagina gebruikt "gevorderde"/"onschema" als badge-kind (styles.py), maar de
# ported app.css kent alleen "gevorderd"/"ok" — zie static/app.css badge-classes.
_NIVEAU_KIND = {
    "starter": "starter",
    "onderweg": "onderweg",
    "gevorderde": "gevorderd",
    "expert": "expert",
}


def _eigen_studenten(request: Request) -> list[dict]:
    """Keuzelijst voor de docent: alleen de eigen mentorgroep, gesorteerd op naam."""
    groep = data.mentor_df(request.session["mentor_naam"])
    return (
        groep.sort_values("naam")[["naam", "studentnummer"]]
        .apply(lambda r: {"naam": r["naam"], "studentnummer": str(r["studentnummer"])}, axis=1)
        .tolist()
    )


def _bepaal_student(request: Request, gevraagd: str | None) -> tuple[str | None, list[dict]]:
    """Bepaal welke studentnummer getoond wordt + (voor docent) de keuzelijst."""
    if request.session.get("rol") == "student":
        return str(request.session["studentnummer"]), []
    opties = _eigen_studenten(request)
    if not opties:
        return None, []
    toegestaan = {o["studentnummer"] for o in opties}
    gekozen = gevraagd if gevraagd in toegestaan else opties[0]["studentnummer"]
    return gekozen, opties


def _voortgang_context(request: Request, studentnummer: str) -> dict:
    df = data.get_df()
    student = get_student(df, studentnummer)
    niveau = leerpad_niveau(student)

    positie_info = cohort_positie(df, studentnummer)
    pos = positie_info["positie"]
    totaal_cohort = positie_info["totaal"]
    voortgang_pct = int(student["voortgang"] * 100)
    gem_pct = int(positie_info["gemiddelde_voortgang"] * 100)
    delta = voortgang_pct - gem_pct

    behaald = int(student["bsa_behaald"])
    vereist = int(student["bsa_vereist"])
    bsa_progress = behaald / vereist if vereist else 0.0
    positie_progress = (totaal_cohort - pos + 1) / totaal_cohort if totaal_cohort else 0.0

    heeft_rating, laatst = heeft_self_rating(studentnummer)

    zkt = zwakste_kerntaak(df, studentnummer)
    zwp = zwakste_werkproces(df, studentnummer)

    kt_df = kerntaak_scores(df, studentnummer)
    wp_df = werkproces_scores(df, studentnummer)
    rol = request.session.get("rol")
    kerntaken = []
    for _, kt in kt_df.iterrows():
        kt_idx = str(kt["kerntaak"]).removeprefix("kt_")
        wps = wp_df[wp_df["werkproces"].str.startswith(f"wp_{kt_idx}_")]
        kerntaken.append(
            {
                "idx": kt_idx,
                "label": kt["label"],
                "score": kt["score"],
                "chart_id": f"kt-chart-{kt_idx}",
                "chart_json": (
                    werkproces_grafiek(wps, rol=rol).to_json() if not wps.empty else None
                ),
            }
        )

    niveau_kind = _NIVEAU_KIND.get(niveau.lower(), "starter")
    return {
        "student": student,
        "studentnummer": studentnummer,
        "niveau": niveau,
        "niveau_kind": niveau_kind,
        "status_label": "Aandacht nodig" if student["risico"] else "Op schema",
        "status_kind": "urgent" if student["risico"] else "ok",
        "heeft_rating": heeft_rating,
        "laatst": (laatst or "")[:10],
        "voortgang_pct": voortgang_pct,
        "gem_pct": gem_pct,
        "delta": delta,
        "bsa_behaald": behaald,
        "bsa_vereist": vereist,
        "bsa_progress": bsa_progress,
        "positie": pos,
        "totaal_cohort": totaal_cohort,
        "cohort": positie_info["cohort"],
        "positie_progress": positie_progress,
        "kerntaken": kerntaken,
        "zkt": zkt,
        "zwp": zwp,
        "zkt_label": zkt[0] if zkt else "",
        "zwp_label": zwp[0] if zwp else "",
    }


@router.get("/voortgang")
def voortgang_home(request: Request, studentnummer: str | None = None):
    redirect = eis_rol(request, "student", "docent")
    if redirect:
        return redirect

    gekozen, opties = _bepaal_student(request, studentnummer)
    ctx = {**sessie_context(request), "opties": opties, "gekozen": gekozen}
    if gekozen is None:
        return templates.TemplateResponse(
            request, "voortgang.html", {**ctx, "geen_studenten": True}
        )

    return templates.TemplateResponse(
        request,
        "voortgang.html",
        {**ctx, "geen_studenten": False, **_voortgang_context(request, gekozen)},
    )


@router.post("/voortgang/api/weekplan")
async def voortgang_weekplan(request: Request):
    redirect = eis_rol(request, "student", "docent")
    if redirect:
        return redirect

    body = await request.json()
    studentnummer = str(body.get("studentnummer", ""))

    if request.session.get("rol") == "student":
        snr = str(request.session["studentnummer"])
    else:
        toegestaan = {o["studentnummer"] for o in _eigen_studenten(request)}
        if studentnummer not in toegestaan:

            def afwijzen():
                yield f"data: {json.dumps({'error': 'onbekende student'})}\n\n"

            return StreamingResponse(afwijzen(), media_type="text/event-stream")
        snr = studentnummer

    df = data.get_df()
    student = get_student(df, snr)
    niveau = leerpad_niveau(student)
    zkt = zwakste_kerntaak(df, snr)
    zwp = zwakste_werkproces(df, snr)

    def gen():
        try:
            for chunk in genereer_weekplan(
                naam=str(student["naam"]),
                opleiding=str(student["opleiding"]),
                leerpad=niveau,
                voortgang=float(student["voortgang"]),
                bsa_behaald=float(student["bsa_behaald"]),
                bsa_vereist=float(student["bsa_vereist"]),
                zwakste_kerntaak=zkt[0] if zkt else "",
                zwakste_werkproces=zwp[0] if zwp else "",
            ):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except APITimeoutError:
            log.warning("Weekplan-generatie timeout (voortgang, %s)", snr)
            yield f"data: {json.dumps({'error': 'timeout'})}\n\n"
        except Exception as e:
            log.exception("Weekplan-generatie mislukt (voortgang)")
            yield f"data: {json.dumps({'error': vriendelijke_fout(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
