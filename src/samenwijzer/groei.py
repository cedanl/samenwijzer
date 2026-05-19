"""Business-logic voor het groeidossier: overlay van zelf-scores en kt-aggregatie."""

import re
from pathlib import Path

import pandas as pd

from samenwijzer.groei_store import (
    _DB_PATH,
    get_alle_actueel,
    get_historie,
)

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
    """Overschrijf wp-scores met self-ratings uit groei.db en herbereken kt-scores.

    - wp-kolommen die NaN zijn in df (= niet in opleiding) blijven NaN.
    - kt-kolommen worden hercalculeerd als gemiddelde van hun wp's.
    - Studenten zonder self-rating houden hun synthetische scores.

    Returns:
        Nieuwe DataFrame (origineel blijft ongewijzigd).
    """
    alle_actueel = get_alle_actueel(db_path)
    if not alle_actueel:
        return df.copy()

    overlaid = df.copy()
    studentnummer_kolom = "studentnummer"

    for studentnummer, rijen in alle_actueel.items():
        mask = overlaid[studentnummer_kolom] == studentnummer
        if not mask.any():
            continue
        idx = overlaid.index[mask][0]
        for rij in rijen:
            if rij.wp_kolom not in overlaid.columns:
                continue
            if pd.isna(overlaid.at[idx, rij.wp_kolom]):
                # NaN betekent: opleiding heeft deze wp niet — niet overschrijven.
                continue
            overlaid.at[idx, rij.wp_kolom] = float(rij.score)

        # Herbereken kt-scores: alleen kt_<int>-kolommen (kt_gemiddelde e.d. overslaan).
        for kt_col in overlaid.columns:
            if not _KT_INDEX_PATROON.match(kt_col):
                continue
            kt_index = int(kt_col.removeprefix(_KT_PREFIX))
            nieuwe_kt = bereken_kt_uit_wp(overlaid.loc[idx], kt_index=kt_index)
            if not pd.isna(nieuwe_kt):
                overlaid.at[idx, kt_col] = nieuwe_kt

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


def heeft_self_rating(studentnummer: str, db_path: Path = _DB_PATH) -> tuple[bool, str | None]:
    """Returns (heeft_rating, laatst_gewijzigd_iso). Voor de bron-badge op voortgang-pagina."""
    alle = get_alle_actueel(db_path)
    rijen = alle.get(studentnummer)
    if not rijen:
        return False, None
    laatste = max(r.laatst_gewijzigd for r in rijen)
    return True, laatste
