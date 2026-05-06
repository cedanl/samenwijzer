"""Tests voor generate_synthetisch_welzijn.py."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from generate_synthetisch_welzijn import (  # noqa: E402
    _antwoord_kansen,
    genereer_rijen,
    schrijf_csv,
)

from samenwijzer.prepare import load_welzijn_csv  # noqa: E402


def test_antwoord_kansen_hoge_voortgang_favoriseert_goed():
    p1, p2, p3 = _antwoord_kansen(0.9)
    assert p1 > p2 > p3
    assert abs(p1 + p2 + p3 - 1.0) < 1e-9


def test_antwoord_kansen_lage_voortgang_favoriseert_zwaar():
    p1, p2, p3 = _antwoord_kansen(0.2)
    assert p3 > p1
    assert abs(p1 + p2 + p3 - 1.0) < 1e-9


def test_genereer_rijen_reproduceerbaar():
    studenten = [{"studentnummer": "100000", "voortgang": 0.8}]
    eerste = genereer_rijen(studenten, seed=42, aantal_weken=8)
    tweede = genereer_rijen(studenten, seed=42, aantal_weken=8)
    assert eerste == tweede


def test_genereer_rijen_geeft_alleen_geldige_antwoorden():
    studenten = [{"studentnummer": str(100000 + i), "voortgang": 0.5} for i in range(50)]
    rijen = genereer_rijen(studenten, seed=42, aantal_weken=10)
    assert all(r["antwoord"] in (1, 2, 3) for r in rijen)


def test_genereer_rijen_dekt_meeste_studenten_bij_lange_periode():
    """Met 10 weken en 45% deelnamekans verwachten we dekking voor bijna iedereen."""
    studenten = [{"studentnummer": str(100000 + i), "voortgang": 0.6} for i in range(200)]
    rijen = genereer_rijen(studenten, seed=42, aantal_weken=10, kans_deelname=0.45)
    unieke = {r["studentnummer"] for r in rijen}
    assert len(unieke) >= 195  # ≤5 studenten uit 200 mogen geheel ontbreken


def test_genereer_rijen_datums_oplopend_per_student():
    studenten = [{"studentnummer": "100001", "voortgang": 0.5}]
    rijen = genereer_rijen(
        studenten,
        seed=1,
        aantal_weken=10,
        kans_deelname=1.0,
        laatste_check=date(2026, 5, 4),
    )
    datums = [r["datum"] for r in rijen]
    assert datums == sorted(datums)
    assert datums[-1] == "2026-05-04"


def test_schrijf_csv_round_trip(tmp_path: Path):
    rijen = [
        {
            "studentnummer": "100000",
            "datum": "2026-04-01",
            "antwoord": 1,
            "toelichting": "",
        },
        {
            "studentnummer": "100001",
            "datum": "2026-04-08",
            "antwoord": 3,
            "toelichting": "moeilijk",
        },
    ]
    pad = tmp_path / "welzijn.csv"
    schrijf_csv(rijen, pad)
    df = load_welzijn_csv(pad)
    assert len(df) == 2
    assert set(df["studentnummer"]) == {"100000", "100001"}
    assert df.iloc[1]["toelichting"] == "moeilijk"
