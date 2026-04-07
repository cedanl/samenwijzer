"""Tests voor samenwijzer.prepare."""

import textwrap
from pathlib import Path

import pandas as pd
import pytest

from samenwijzer.prepare import load_student_csv


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
