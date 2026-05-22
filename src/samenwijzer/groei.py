"""Business-logic voor het groeidossier: overlay van zelf-scores en kt-aggregatie."""

import re
from pathlib import Path

import pandas as pd

from samenwijzer.groei_store import (
    _DB_PATH,
    get_alle_actueel,
    get_historie,
)
from samenwijzer.transform import _bereken_risico

_KT_PREFIX = "kt_"
_WP_PREFIX = "wp_"
_KT_INDEX_PATROON = re.compile(r"^kt_\d+$")


def bereken_kt_uit_wp(rij: pd.Series, kt_index: int) -> float:
    """Bereken het gemiddelde van de werkprocessen onder kerntaak `kt_index`.

    NaN-werkprocessen (= niet aanwezig in deze opleiding) worden genegeerd.
    Returns NaN als geen enkel werkproces een score heeft.
    """
    wp_kolommen = [k for k in rij.index if k.startswith(f"{_WP_PREFIX}{kt_index}_")]
    scores = pd.to_numeric(rij[wp_kolommen], errors="coerce").dropna()
    if scores.empty:
        return float("nan")
    return float(scores.mean())


def overlay_self_scores(df: pd.DataFrame, db_path: Path = _DB_PATH) -> pd.DataFrame:
    """Overschrijf wp-scores met goedgekeurde self-ratings uit groei.db en herbereken kt-scores.

    - Alleen scores met status 'goedgekeurd' (goedgekeurde_score is not None) tellen mee.
    - wp-kolommen die NaN zijn in df (= niet in opleiding) blijven NaN.
    - kt-kolommen worden hercalculeerd als gemiddelde van hun wp's.
    - Studenten zonder goedgekeurde score houden hun synthetische voortgang/risico.

    Returns:
        Nieuwe DataFrame (origineel blijft ongewijzigd).
    """
    alle_actueel = get_alle_actueel(db_path)
    if not alle_actueel:
        return df.copy()

    overlaid = df.copy()
    kt_kolommen = [c for c in overlaid.columns if _KT_INDEX_PATROON.match(c)]
    iets_gewijzigd = False

    for studentnummer, rijen in alle_actueel.items():
        mask = overlaid["studentnummer"] == studentnummer
        if not mask.any():
            continue
        idx = overlaid.index[mask][0]

        student_gewijzigd = False
        for rij in rijen:
            if rij.goedgekeurde_score is None:
                continue
            if rij.wp_kolom not in overlaid.columns:
                continue
            if pd.isna(overlaid.at[idx, rij.wp_kolom]):
                # NaN betekent: opleiding heeft deze wp niet — niet overschrijven.
                continue
            overlaid.at[idx, rij.wp_kolom] = float(rij.goedgekeurde_score)
            student_gewijzigd = True

        if not student_gewijzigd:
            continue
        iets_gewijzigd = True

        for kt_col in kt_kolommen:
            kt_index = int(kt_col.removeprefix(_KT_PREFIX))
            nieuwe_kt = bereken_kt_uit_wp(overlaid.loc[idx], kt_index=kt_index)
            if not pd.isna(nieuwe_kt):
                overlaid.at[idx, kt_col] = nieuwe_kt

        if "voortgang" in overlaid.columns:
            kt_scores = pd.to_numeric(overlaid.loc[idx, kt_kolommen], errors="coerce").dropna()
            if not kt_scores.empty:
                overlaid.at[idx, "voortgang"] = float(min(max(kt_scores.mean() / 100, 0.0), 1.0))

    # Risico-vlag herberekenen zodat mentor-goedgekeurde groei de triage volgt.
    if iets_gewijzigd and {"risico", "bsa_percentage", "voortgang"} <= set(overlaid.columns):
        overlaid["risico"] = _bereken_risico(overlaid)

    return overlaid


def delta_t_o_v_vorige(
    studentnummer: str,
    wp_kolom: str,
    db_path: Path = _DB_PATH,
) -> int | None:
    """Geef verschil (nieuwste − op één na nieuwste) voor één werkproces.

    Returns None als er minder dan twee metingen zijn.
    """
    historie = [r for r in get_historie(studentnummer, db_path) if r.wp_kolom == wp_kolom]
    if len(historie) < 2:
        return None
    return historie[-1].score - historie[-2].score


def laatste_twee_metingen_per_wp(
    studentnummer: str,
    wp_kolommen: list[str],
    db_path: Path = _DB_PATH,
) -> dict[str, tuple[int | None, int | None]]:
    """Geef per werkproces (huidige, vorige) score, of (None, None) als er geen meting is.

    'Huidige' = laatste snapshot in groei_historie.
    'Vorige' = op één na laatste snapshot, of None als die niet bestaat.
    """
    historie = get_historie(studentnummer, db_path)
    resultaat: dict[str, tuple[int | None, int | None]] = {}
    for wp in wp_kolommen:
        wp_historie = [h for h in historie if h.wp_kolom == wp]
        if not wp_historie:
            resultaat[wp] = (None, None)
        elif len(wp_historie) == 1:
            resultaat[wp] = (wp_historie[-1].score, None)
        else:
            resultaat[wp] = (wp_historie[-1].score, wp_historie[-2].score)
    return resultaat


def klas_gemiddelden_per_wp(
    df: pd.DataFrame,
    opleiding: str,
    cohort: str,
    wp_kolommen: list[str],
) -> dict[str, float]:
    """Gemiddelde wp-score over peer-studenten (zelfde opleiding + cohort).

    Returns een dict {wp_kolom: gemiddelde} of NaN als er geen peers/data zijn.
    NaN-werkprocessen (= niet in opleiding) tellen niet mee.
    """
    peers = df[(df["opleiding"] == opleiding) & (df["cohort"].astype(str) == str(cohort))]
    resultaat: dict[str, float] = {}
    for wp in wp_kolommen:
        if wp not in peers.columns:
            resultaat[wp] = float("nan")
            continue
        scores = pd.to_numeric(peers[wp], errors="coerce").dropna()
        resultaat[wp] = float(scores.mean()) if not scores.empty else float("nan")
    return resultaat


def heeft_self_rating(studentnummer: str, db_path: Path = _DB_PATH) -> tuple[bool, str | None]:
    """Returns (heeft_rating, laatst_gewijzigd_iso). Voor de bron-badge op voortgang-pagina."""
    alle = get_alle_actueel(db_path)
    rijen = alle.get(studentnummer)
    if not rijen:
        return False, None
    laatste = max(r.laatst_gewijzigd for r in rijen)
    return True, laatste
