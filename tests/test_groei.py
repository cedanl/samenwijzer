"""Tests voor samenwijzer.groei."""

from pathlib import Path

import pandas as pd
import pytest

from samenwijzer.groei import (
    bereken_kt_uit_wp,
    delta_t_o_v_vorige,
    overlay_self_scores,
)
from samenwijzer.groei_store import GroeiActueel, init_db, sla_groei_op


@pytest.fixture
def db(tmp_path: Path) -> Path:
    pad = tmp_path / "test_groei.db"
    init_db(pad)
    return pad


def _basisrij(studentnummer: str, **kwargs: object) -> dict[str, object]:
    rij: dict[str, object] = {
        "studentnummer": studentnummer,
        "kt_1": 30.0,
        "kt_2": 40.0,
        "wp_1_1": 30.0,
        "wp_1_2": 30.0,
        "wp_1_3": 30.0,
        "wp_2_1": 40.0,
        "wp_2_2": 40.0,
        "wp_2_3": 40.0,
    }
    rij.update(kwargs)
    return rij


def test_bereken_kt_uit_wp_neemt_gemiddelde() -> None:
    rij = pd.Series(_basisrij("S001", wp_1_1=60.0, wp_1_2=80.0, wp_1_3=70.0))
    assert bereken_kt_uit_wp(rij, kt_index=1) == pytest.approx(70.0)


def test_bereken_kt_uit_wp_negeert_nan() -> None:
    rij = pd.Series(_basisrij("S001", wp_1_1=60.0, wp_1_2=float("nan"), wp_1_3=80.0))
    assert bereken_kt_uit_wp(rij, kt_index=1) == pytest.approx(70.0)


def test_overlay_self_scores_overschrijft_synthetisch(db: Path) -> None:
    df = pd.DataFrame([_basisrij("S001"), _basisrij("S002")])
    sla_groei_op(
        "S001",
        [
            GroeiActueel("S001", "wp_1_1", 90, "ik kan dit", "2026-05-19T10:00:00"),
            GroeiActueel("S001", "wp_1_2", 80, "soms", "2026-05-19T10:00:00"),
            GroeiActueel("S001", "wp_1_3", 70, "vaak", "2026-05-19T10:00:00"),
        ],
        db,
    )

    overlaid = overlay_self_scores(df, db_path=db)

    s001 = overlaid[overlaid["studentnummer"] == "S001"].iloc[0]
    assert s001["wp_1_1"] == 90
    assert s001["wp_1_2"] == 80
    assert s001["wp_1_3"] == 70
    assert s001["kt_1"] == pytest.approx(80.0)  # gemiddelde van 90/80/70

    s002 = overlaid[overlaid["studentnummer"] == "S002"].iloc[0]
    assert s002["wp_1_1"] == 30.0  # synthetisch blijft staan


def test_overlay_negeert_wp_die_nan_zijn_in_df(db: Path) -> None:
    """Als de student geen wp_x_y heeft in zijn opleiding (NaN), niet overschrijven."""
    df = pd.DataFrame([_basisrij("S001", wp_1_2=float("nan"))])
    sla_groei_op(
        "S001",
        [GroeiActueel("S001", "wp_1_2", 80, "", "2026-05-19T10:00:00")],
        db,
    )

    overlaid = overlay_self_scores(df, db_path=db)
    s001 = overlaid.iloc[0]
    assert pd.isna(s001["wp_1_2"])  # blijft NaN want opleiding heeft deze wp niet


def test_delta_t_o_v_vorige_geeft_verschil_per_kerntaak(db: Path) -> None:
    sla_groei_op(
        "S001",
        [GroeiActueel("S001", "wp_1_1", 40, "", "2026-05-19T10:00:00")],
        db,
    )
    sla_groei_op(
        "S001",
        [GroeiActueel("S001", "wp_1_1", 70, "", "2026-05-19T11:00:00")],
        db,
    )

    delta = delta_t_o_v_vorige("S001", "wp_1_1", db_path=db)
    assert delta == 30


def test_delta_zonder_historie_is_none(db: Path) -> None:
    assert delta_t_o_v_vorige("S999", "wp_1_1", db_path=db) is None


def test_heeft_self_rating_voor_student_met_actueel(db: Path) -> None:
    from samenwijzer.groei import heeft_self_rating

    sla_groei_op(
        "S001",
        [GroeiActueel("S001", "wp_1_1", 60, "", "2026-05-19T10:00:00")],
        db,
    )
    heeft, laatst = heeft_self_rating("S001", db_path=db)
    assert heeft is True
    assert laatst == "2026-05-19T10:00:00"


def test_heeft_self_rating_voor_onbekende_student(db: Path) -> None:
    from samenwijzer.groei import heeft_self_rating

    heeft, laatst = heeft_self_rating("S999", db_path=db)
    assert heeft is False
    assert laatst is None
