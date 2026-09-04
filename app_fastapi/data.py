"""Dataset-toegang voor de FastAPI-frontend.

De basis-dataframe wordt éénmalig geladen (module-cache); per request wordt
``overlay_self_scores`` toegepast zodat goedgekeurde groeidossier-scores en de
herberekende risico's altijd actueel zijn (1000 rijen — goedkoop).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from samenwijzer.groei import overlay_self_scores
from samenwijzer.prepare import load_synthetisch_csv
from samenwijzer.transform import transform_student_data

_STUDENTEN_CSV = Path(__file__).parent.parent / "data" / "01-raw" / "synthetisch" / "studenten.csv"

_df_basis: pd.DataFrame | None = None


def get_df() -> pd.DataFrame:
    """Dataframe mét overlay van goedgekeurde self-scores (altijd vers)."""
    global _df_basis
    if _df_basis is None:
        _df_basis = transform_student_data(load_synthetisch_csv(_STUDENTEN_CSV))
    return overlay_self_scores(_df_basis)


def student_row(studentnummer: str) -> pd.Series | None:
    df = get_df()
    sel = df[df["studentnummer"].astype(str) == str(studentnummer)]
    return sel.iloc[0] if len(sel) else None


def mentor_df(mentor_naam: str) -> pd.DataFrame:
    df = get_df()
    return df[df["mentor"] == mentor_naam]
