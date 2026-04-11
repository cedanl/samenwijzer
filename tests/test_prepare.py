"""Tests voor samenwijzer.prepare."""

import json
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from samenwijzer.prepare import load_berend_csv, load_student_csv


@pytest.fixture
def demo_csv(tmp_path: Path) -> Path:
    """Minimale geldige CSV met twee studenten."""
    content = textwrap.dedent("""\
        studentnummer,naam,mentor,opleiding,crebo,niveau,leerweg,cohort,leeftijd,geslacht,bsa_behaald,bsa_vereist,voortgang,kt1_taak,wp1_1_werkproces
        S001,Jan Jansen,M. de Vries,Verzorgende IG,25491,3,BOL,2024-2025,19,M,42,60,0.70,72,70
        S002,Anna Bakker,M. de Vries,Verzorgende IG,25491,3,BBL,2024-2025,21,V,55,60,0.92,85,82
    """)
    p = tmp_path / "studenten.csv"
    p.write_text(content)
    return p


def test_laad_geldig_csv(demo_csv):
    df = load_student_csv(demo_csv)
    assert len(df) == 2
    assert set(df["studentnummer"]) == {"S001", "S002"}


def test_voortgang_is_float(demo_csv):
    df = load_student_csv(demo_csv)
    assert df["voortgang"].dtype == float


def test_niveau_is_int(demo_csv):
    df = load_student_csv(demo_csv)
    assert pd.api.types.is_integer_dtype(df["niveau"])


def test_bestand_niet_gevonden():
    with pytest.raises(FileNotFoundError):
        load_student_csv(Path("/bestaat/niet.csv"))


def test_ontbrekende_kolom(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("studentnummer,naam\nS001,Jan\n")
    with pytest.raises(ValueError, match="Ontbrekende verplichte kolommen"):
        load_student_csv(p)


def test_dubbel_studentnummer(tmp_path):
    content = textwrap.dedent("""\
        studentnummer,naam,mentor,opleiding,crebo,niveau,leerweg,cohort,leeftijd,geslacht,bsa_behaald,bsa_vereist,voortgang
        S001,Jan,M,Opl,12345,3,BOL,2024-2025,19,M,30,60,0.50
        S001,Piet,M,Opl,12345,3,BOL,2024-2025,20,M,40,60,0.67
    """)
    p = tmp_path / "dup.csv"
    p.write_text(content)
    with pytest.raises(ValueError, match="Dubbele studentnummers"):
        load_student_csv(p)


def test_ongeldig_niveau(tmp_path):
    content = textwrap.dedent("""\
        studentnummer,naam,mentor,opleiding,crebo,niveau,leerweg,cohort,leeftijd,geslacht,bsa_behaald,bsa_vereist,voortgang
        S001,Jan,M,Opl,12345,9,BOL,2024-2025,19,M,30,60,0.50
    """)
    p = tmp_path / "niveau.csv"
    p.write_text(content)
    with pytest.raises(ValueError, match="Niveau"):
        load_student_csv(p)


def test_ongeldige_leerweg(tmp_path):
    content = textwrap.dedent("""\
        studentnummer,naam,mentor,opleiding,crebo,niveau,leerweg,cohort,leeftijd,geslacht,bsa_behaald,bsa_vereist,voortgang
        S001,Jan,M,Opl,12345,3,ONLINE,2024-2025,19,M,30,60,0.50
    """)
    p = tmp_path / "leerweg.csv"
    p.write_text(content)
    with pytest.raises(ValueError, match="leerweg"):
        load_student_csv(p)


def test_ongeldige_voortgang(tmp_path: Path) -> None:
    content = textwrap.dedent("""\
        studentnummer,naam,mentor,opleiding,crebo,niveau,leerweg,cohort,leeftijd,geslacht,bsa_behaald,bsa_vereist,voortgang
        S001,Jan,M,Opl,12345,3,BOL,2024-2025,19,M,30,60,1.50
    """)
    p = tmp_path / "voortgang.csv"
    p.write_text(content)
    with pytest.raises(ValueError, match="Voortgang"):
        load_student_csv(p)


# ── load_berend_csv ───────────────────────────────────────────────────────────


@pytest.fixture
def berend_csv(tmp_path: Path) -> Path:
    """Minimale Berend-format CSV met twee studenten."""
    content = textwrap.dedent("""\
        Studentnummer,Naam,Klas,Mentor,Opleiding,StudentAge,StudentGender,absence_unauthorized
        S001,Ali Yilmaz,3A,M. Bakker,Verzorgende,19,1,5
        S002,Ben de Vries,2B,M. Bakker,Verzorgende,21,0,20
    """)
    p = tmp_path / "studenten.csv"
    p.write_text(content)
    return p


@pytest.fixture
def berend_csv_met_oer(tmp_path: Path) -> Path:
    """Berend-format CSV met bijbehorend oer_kerntaken.json."""
    csv_inhoud = textwrap.dedent("""\
        Studentnummer,Naam,Klas,Mentor,Opleiding,StudentAge,StudentGender,absence_unauthorized
        S001,Ali Yilmaz,3A,M. Bakker,Verzorgende,19,1,5
        S002,Ben de Vries,2B,M. Bakker,Verzorgende,21,0,20
    """)
    oer = {
        "Verzorgende": {
            "kerntaken": [
                {"code": "kt_1", "naam": "KT1 Zorgverlening"},
                {"code": "kt_2", "naam": "KT2 Begeleiding"},
            ],
            "werkprocessen": [
                {"code": "wp_1_1", "naam": "WP1.1 Intake"},
                {"code": "wp_1_2", "naam": "WP1.2 Plan"},
                {"code": "wp_2_1", "naam": "WP2.1 Uitvoer"},
            ],
        }
    }
    (tmp_path / "studenten.csv").write_text(csv_inhoud)
    (tmp_path / "oer_kerntaken.json").write_text(json.dumps(oer))
    return tmp_path / "studenten.csv"


def test_load_berend_csv_bestand_niet_gevonden(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_berend_csv(tmp_path / "bestaat_niet.csv")


def test_load_berend_csv_geeft_dataframe(berend_csv: Path) -> None:
    df = load_berend_csv(berend_csv)
    assert len(df) == 2
    assert set(df["studentnummer"]) == {"S001", "S002"}


def test_load_berend_csv_standaard_kolommen(berend_csv: Path) -> None:
    df = load_berend_csv(berend_csv)
    for kolom in ("naam", "mentor", "opleiding", "niveau", "leerweg", "cohort", "voortgang"):
        assert kolom in df.columns, f"Kolom '{kolom}' ontbreekt"


def test_load_berend_csv_leerweg_is_bol(berend_csv: Path) -> None:
    df = load_berend_csv(berend_csv)
    assert (df["leerweg"] == "BOL").all()


def test_load_berend_csv_voortgang_tussen_0_en_1(berend_csv: Path) -> None:
    df = load_berend_csv(berend_csv)
    assert df["voortgang"].between(0, 1).all()


def test_load_berend_csv_geslacht_mapping(berend_csv: Path) -> None:
    df = load_berend_csv(berend_csv)
    geslacht = dict(zip(df["studentnummer"], df["geslacht"]))
    assert geslacht["S001"] == "V"  # StudentGender=1 → V
    assert geslacht["S002"] == "M"  # StudentGender=0 → M


def test_load_berend_csv_niveau_uit_klascode(berend_csv: Path) -> None:
    # "3A" → niveau 3, "2B" → niveau 2
    df = load_berend_csv(berend_csv)
    niveaus = dict(zip(df["studentnummer"], df["niveau"]))
    assert niveaus["S001"] == 3
    assert niveaus["S002"] == 2


def test_load_berend_csv_met_oer_voegt_kt_kolommen_toe(berend_csv_met_oer: Path) -> None:
    df = load_berend_csv(berend_csv_met_oer)
    assert "kt_1" in df.columns
    assert "kt_2" in df.columns


def test_load_berend_csv_met_oer_kt_scores_binnen_bereik(berend_csv_met_oer: Path) -> None:
    df = load_berend_csv(berend_csv_met_oer)
    kt_waarden = df["kt_1"].dropna()
    assert (kt_waarden >= 0).all()
    assert (kt_waarden <= 100).all()


def test_load_berend_csv_zonder_oer_json(berend_csv: Path) -> None:
    # Geen oer_kerntaken.json naast de CSV → geen crash, wel kt-kolommen met 0
    df = load_berend_csv(berend_csv)
    assert df is not None


def test_load_berend_csv_opleiding_met_slechts_een_kt(tmp_path: Path) -> None:
    # OER bevat alleen kt_1 voor deze opleiding → kt_2 wordt NaN (dekt regel 206)
    csv_inhoud = textwrap.dedent("""\
        Studentnummer,Naam,Klas,Mentor,Opleiding,StudentAge,StudentGender,absence_unauthorized
        S001,Test Student,3A,M. Bakker,EenKtOpleiding,20,0,10
    """)
    oer = {
        "EenKtOpleiding": {
            "kerntaken": [{"code": "kt_1", "naam": "KT1 Enige kerntaak"}],
            "werkprocessen": [{"code": "wp_1_1", "naam": "WP1.1"}],
        }
    }
    (tmp_path / "studenten.csv").write_text(csv_inhoud)
    (tmp_path / "oer_kerntaken.json").write_text(json.dumps(oer))

    df = load_berend_csv(tmp_path / "studenten.csv")
    assert pd.isna(df.iloc[0]["kt_2"])
