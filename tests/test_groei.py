"""Tests voor samenwijzer.groei."""

from pathlib import Path

import pandas as pd
import pytest

from samenwijzer.groei import (
    bereken_kt_uit_wp,
    delta_t_o_v_vorige,
    overlay_self_scores,
)
from samenwijzer.groei_store import GroeiActueel, dien_in, init_db, keur_goed, sla_groei_op


def _keur_goed(db: Path, studentnummer: str, scores: dict[str, int]) -> None:
    """Sla scores op, dien ze in en laat de mentor ze goedkeuren."""
    nu = "2026-05-19T10:00:00"
    sla_groei_op(
        studentnummer,
        [GroeiActueel(studentnummer, wp, score, "", nu) for wp, score in scores.items()],
        db,
    )
    dien_in(studentnummer, list(scores), db)
    for wp in scores:
        keur_goed(studentnummer, wp, "Mentor A", db)


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
    _keur_goed(db, "S001", {"wp_1_1": 90, "wp_1_2": 80, "wp_1_3": 70})

    overlaid = overlay_self_scores(df, db_path=db)

    s001 = overlaid[overlaid["studentnummer"] == "S001"].iloc[0]
    assert s001["wp_1_1"] == 90
    assert s001["wp_1_2"] == 80
    assert s001["wp_1_3"] == 70
    assert s001["kt_1"] == pytest.approx(80.0)  # gemiddelde van 90/80/70

    s002 = overlaid[overlaid["studentnummer"] == "S002"].iloc[0]
    assert s002["wp_1_1"] == 30.0  # synthetisch blijft staan


def test_overlay_herberekent_voortgang_uit_kt(db: Path) -> None:
    """Headline-voortgang volgt de self-scores: gemiddelde van kt-scores / 100."""
    df = pd.DataFrame([_basisrij("S001", voortgang=0.35), _basisrij("S002", voortgang=0.35)])
    _keur_goed(db, "S001", {"wp_1_1": 90, "wp_1_2": 80, "wp_1_3": 70})

    overlaid = overlay_self_scores(df, db_path=db)

    # S001: kt_1=80 (90/80/70), kt_2=40 (synthetisch) → voortgang = 0.60
    s001 = overlaid[overlaid["studentnummer"] == "S001"].iloc[0]
    assert s001["voortgang"] == pytest.approx(0.60)
    # S002 heeft geen self-rating → voortgang blijft ongewijzigd.
    s002 = overlaid[overlaid["studentnummer"] == "S002"].iloc[0]
    assert s002["voortgang"] == pytest.approx(0.35)


def test_overlay_telt_heraccordering_na_bewerking(db: Path) -> None:
    """Een goedgekeurde score telt; na bewerken telt de oude tot heraccordering, dan de nieuwe."""
    df = pd.DataFrame([_basisrij("S001")])
    _keur_goed(db, "S001", {"wp_1_1": 60})
    assert overlay_self_scores(df, db_path=db).iloc[0]["wp_1_1"] == 60

    # Student verhoogt naar 90 (concept) en dient in — nog niet goedgekeurd:
    sla_groei_op("S001", [GroeiActueel("S001", "wp_1_1", 90, "", "2026-05-20T10:00:00")], db)
    dien_in("S001", ["wp_1_1"], db)
    assert overlay_self_scores(df, db_path=db).iloc[0]["wp_1_1"] == 60  # oude goedkeuring telt nog

    # Mentor keurt de nieuwe waarde goed:
    keur_goed("S001", "wp_1_1", "Mentor A", db)
    assert overlay_self_scores(df, db_path=db).iloc[0]["wp_1_1"] == 90  # nu telt de nieuwe


def test_overlay_zonder_voortgang_kolom_crasht_niet(db: Path) -> None:
    df = pd.DataFrame([_basisrij("S001")])
    _keur_goed(db, "S001", {"wp_1_1": 90})
    overlay_self_scores(df, db_path=db)  # mag niet crashen zonder voortgang-kolom


def test_overlay_negeert_wp_die_nan_zijn_in_df(db: Path) -> None:
    """Als de student geen wp_x_y heeft in zijn opleiding (NaN), niet overschrijven."""
    df = pd.DataFrame([_basisrij("S001", wp_1_2=float("nan"))])
    _keur_goed(db, "S001", {"wp_1_2": 80})

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


def test_laatste_twee_metingen_per_wp(db) -> None:
    from samenwijzer.groei import laatste_twee_metingen_per_wp

    # Eén meting voor wp_1_1, twee voor wp_1_2, geen voor wp_2_1
    sla_groei_op(
        "S001",
        [
            GroeiActueel("S001", "wp_1_1", 50, "", "2026-05-19T10:00:00"),
            GroeiActueel("S001", "wp_1_2", 40, "", "2026-05-19T10:00:00"),
        ],
        db,
    )
    sla_groei_op(
        "S001",
        [GroeiActueel("S001", "wp_1_2", 70, "", "2026-05-19T11:00:00")],
        db,
    )

    resultaat = laatste_twee_metingen_per_wp("S001", ["wp_1_1", "wp_1_2", "wp_2_1"], db_path=db)
    assert resultaat["wp_1_1"] == (50, None)  # alleen huidige
    assert resultaat["wp_1_2"] == (70, 40)  # huidige + vorige
    assert resultaat["wp_2_1"] == (None, None)  # geen meting


def test_overlay_negeert_kt_gemiddelde_kolom(db) -> None:
    """Regressie: overlay_self_scores moet kt_gemiddelde (en andere niet-int suffixes) overslaan.

    De transform-laag voegt een `kt_gemiddelde`-aggregatie toe. Een naïeve loop over
    alle kolommen met prefix 'kt_' crasht dan op `int('gemiddelde')`.
    """
    df = pd.DataFrame([{**_basisrij("S001"), "kt_gemiddelde": 35.0}])
    _keur_goed(db, "S001", {"wp_1_1": 90})
    overlay_self_scores(df, db_path=db)  # mag niet crashen


def test_klas_gemiddelden_per_wp_neemt_gemiddelde_van_zelfde_opleiding_en_cohort() -> None:
    from samenwijzer.groei import klas_gemiddelden_per_wp

    df = pd.DataFrame(
        [
            {**_basisrij("S001"), "opleiding": "OA", "cohort": "2025", "wp_1_1": 60.0},
            {**_basisrij("S002"), "opleiding": "OA", "cohort": "2025", "wp_1_1": 80.0},
            {**_basisrij("S003"), "opleiding": "OA", "cohort": "2024", "wp_1_1": 100.0},
            {**_basisrij("S004"), "opleiding": "ICT", "cohort": "2025", "wp_1_1": 100.0},
        ]
    )

    resultaat = klas_gemiddelden_per_wp(df, "OA", "2025", ["wp_1_1"])
    assert resultaat["wp_1_1"] == pytest.approx(70.0)  # alleen S001 en S002


def test_klas_gemiddelden_per_wp_negeert_nan() -> None:
    from samenwijzer.groei import klas_gemiddelden_per_wp

    df = pd.DataFrame(
        [
            {**_basisrij("S001"), "opleiding": "OA", "cohort": "2025", "wp_1_1": 60.0},
            {**_basisrij("S002"), "opleiding": "OA", "cohort": "2025", "wp_1_1": float("nan")},
        ]
    )
    resultaat = klas_gemiddelden_per_wp(df, "OA", "2025", ["wp_1_1"])
    assert resultaat["wp_1_1"] == pytest.approx(60.0)


def test_klas_gemiddelden_per_wp_zonder_peers_geeft_nan() -> None:
    import math

    from samenwijzer.groei import klas_gemiddelden_per_wp

    df = pd.DataFrame([{**_basisrij("S001"), "opleiding": "OA", "cohort": "2025"}])
    resultaat = klas_gemiddelden_per_wp(df, "ICT", "2025", ["wp_1_1"])
    assert math.isnan(resultaat["wp_1_1"])


def test_overlay_negeert_concept_en_ingediend(db: Path) -> None:
    """Concept/ingediend scores tellen niet mee — alleen goedgekeurd."""
    df = pd.DataFrame([_basisrij("S001", voortgang=0.35)])
    nu = "2026-05-19T10:00:00"
    sla_groei_op("S001", [GroeiActueel("S001", "wp_1_1", 95, "", nu)], db)  # concept
    overlaid_concept = overlay_self_scores(df, db_path=db)
    assert overlaid_concept.iloc[0]["wp_1_1"] == 30.0
    assert overlaid_concept.iloc[0]["voortgang"] == pytest.approx(0.35)

    dien_in("S001", ["wp_1_1"], db)  # ingediend, nog niet goedgekeurd
    overlaid_ingediend = overlay_self_scores(df, db_path=db)
    assert overlaid_ingediend.iloc[0]["wp_1_1"] == 30.0


def test_overlay_herberekent_risico(db: Path) -> None:
    """Goedgekeurde groei kan de risico-vlag uitzetten."""
    rij = _basisrij("S001", voortgang=0.30, bsa_percentage=0.80, risico=True)
    df = pd.DataFrame([rij])
    _keur_goed(db, "S001", {"wp_1_1": 90, "wp_1_2": 90, "wp_1_3": 90})
    overlaid = overlay_self_scores(df, db_path=db)
    assert overlaid.iloc[0]["voortgang"] == pytest.approx(0.65)
    assert bool(overlaid.iloc[0]["risico"]) is False
