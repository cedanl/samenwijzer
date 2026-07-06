"""Groepsoverzicht — docentweergave: voortgang, risico's, peer-matching, signaleringen."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app_fastapi import data
from app_fastapi.auth import eis_rol, sessie_context
from app_fastapi.templating import templates
from samenwijzer.analyze import cohort_gemiddelden, groepsoverzicht, peer_profielen, signaleringen
from samenwijzer.prepare import load_welzijn_csv
from samenwijzer.visualize import groep_voortgang_grafiek
from samenwijzer.wellbeing import (
    antwoord_label,
    filter_signaleringen_voor_mentor,
    laad_notities,
    sla_notitie_op,
)

router = APIRouter()

_ROOT = Path(__file__).resolve().parent.parent.parent
_WELZIJN_CSV = _ROOT / "data" / "01-raw" / "synthetisch" / "welzijn.csv"
_NOTITIES_PAD = _ROOT / "data" / "02-prepared" / "notities.csv"


@router.get("/groep")
def groepsoverzicht_home(
    request: Request,
    opleiding: str = "Alle",
    cohort: str = "Alle",
    tab: str = "voortgang",
):
    redirect = eis_rol(request, "docent")
    if redirect:
        return redirect

    mentor_naam = request.session.get("mentor_naam", "")
    df = data.mentor_df(mentor_naam)

    totaal_alle = len(df)
    risico_alle = int(df["risico"].sum())
    op_schema = totaal_alle - risico_alle
    gem_voortgang = df["voortgang"].mean() if totaal_alle else 0.0

    opleidingen = ["Alle"] + sorted(df["opleiding"].unique().tolist())
    cohorten = ["Alle"] + sorted(df["cohort"].unique().tolist(), reverse=True)

    gefilterd = df.copy()
    if opleiding != "Alle" and opleiding in opleidingen:
        gefilterd = gefilterd[gefilterd["opleiding"] == opleiding]
    if cohort != "Alle" and cohort in cohorten:
        gefilterd = gefilterd[gefilterd["cohort"] == cohort]

    totaal = len(gefilterd)
    risico_aantal = int(gefilterd["risico"].sum())

    overzicht_df = groepsoverzicht(gefilterd)
    chart_json = None
    if not gefilterd.empty:
        chart_json = groep_voortgang_grafiek(overzicht_df, rol="docent").to_json()

    risico_df = gefilterd[gefilterd["risico"]].sort_values("voortgang")
    pp_df = peer_profielen(gefilterd)
    cohort_df = cohort_gemiddelden(gefilterd)

    df_welzijn = load_welzijn_csv(_WELZIJN_CSV)
    df_signalen = signaleringen(gefilterd, df_welzijn)
    df_signalen = filter_signaleringen_voor_mentor(df_signalen, mentor_naam)
    notities_df = laad_notities(_NOTITIES_PAD)

    signaleringen_lijst = []
    for _, rij in df_signalen.iterrows():
        snr = str(rij["studentnummer"])
        student_notities = notities_df[notities_df["studentnummer"].astype(str) == snr].sort_values(
            "timestamp", ascending=False
        )
        signaleringen_lijst.append(
            {
                "studentnummer": snr,
                "naam": rij["naam"],
                "datum": rij["datum"],
                "score_label": antwoord_label(int(rij["antwoord"])),
                "kleur": "urgent" if float(rij["welzijnswaarde"]) == 0.0 else "matig",
                "toelichting": rij["toelichting"] if rij["toelichting"] else None,
                "notities": [
                    {"datum": str(n["timestamp"])[:10], "notitie": n["notitie"]}
                    for _, n in student_notities.iterrows()
                ],
            }
        )

    return templates.TemplateResponse(
        request,
        "groepsoverzicht.html",
        {
            **sessie_context(request),
            "mentor_naam": mentor_naam,
            "totaal_alle": totaal_alle,
            "risico_alle": risico_alle,
            "op_schema": op_schema,
            "risico_alle_pct": round(risico_alle / totaal_alle * 100) if totaal_alle else 0,
            "gem_voortgang_pct": round(gem_voortgang * 100),
            "opleidingen": opleidingen,
            "cohorten": cohorten,
            "opleiding": opleiding,
            "cohort": cohort,
            "tab": tab if tab in ("voortgang", "signaleringen") else "voortgang",
            "totaal": totaal,
            "risico_aantal": risico_aantal,
            "chart_json": chart_json,
            "risico_studenten": risico_df.to_dict("records"),
            "alle_studenten": overzicht_df.to_dict("records"),
            "heeft_kt_gemiddelde": "kt_gemiddelde" in overzicht_df.columns,
            "peer_profielen": pp_df.to_dict("records") if not pp_df.empty else [],
            "cohort_gemiddelden": cohort_df.to_dict("records") if not cohort_df.empty else [],
            "signaleringen": signaleringen_lijst,
        },
    )


@router.post("/groep/notitie")
def groepsoverzicht_notitie(
    request: Request,
    studentnummer: str = Form(...),
    notitie: str = Form(""),
    opleiding: str = Form("Alle"),
    cohort: str = Form("Alle"),
):
    redirect = eis_rol(request, "docent")
    if redirect:
        return redirect

    mentor_naam = request.session.get("mentor_naam", "")
    try:
        sla_notitie_op(_NOTITIES_PAD, studentnummer, mentor_naam, notitie)
    except ValueError:
        pass
    return RedirectResponse(
        f"/groep?opleiding={opleiding}&cohort={cohort}&tab=signaleringen", status_code=303
    )
