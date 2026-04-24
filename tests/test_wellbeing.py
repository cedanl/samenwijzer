"""Tests voor samenwijzer.wellbeing en de welzijn-gerelateerde analyze-functies."""

import os
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from samenwijzer.analyze import signaleringen
from samenwijzer.prepare import load_welzijn_csv
from samenwijzer.transform import transform_student_data
from samenwijzer.wellbeing import (
    WelzijnsCheck,
    antwoord_label,
    filter_signaleringen_voor_mentor,
    heeft_signaal,
    laad_notities,
    sla_notitie_op,
    welzijnswaarde,
)

DEMO_WELZIJN = Path(__file__).parent.parent / "data" / "01-raw" / "demo" / "welzijn.csv"


# ── WelzijnsCheck ─────────────────────────────────────────────────────────────


def test_welzijnscheck_geldig():
    check = WelzijnsCheck("S001", date(2026, 4, 7), 2)
    assert check.antwoord == 2


def test_welzijnscheck_ongeldig_antwoord():
    with pytest.raises(ValueError, match="1, 2 of 3"):
        WelzijnsCheck("S001", date(2026, 4, 7), 4)


def test_welzijnscheck_nul_ongeldig():
    with pytest.raises(ValueError):
        WelzijnsCheck("S001", date(2026, 4, 7), 0)


# ── welzijnswaarde ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "antwoord, verwacht",
    [
        (1, 1.0),
        (2, 0.5),
        (3, 0.0),
    ],
)
def test_welzijnswaarde(antwoord, verwacht):
    check = WelzijnsCheck("S001", date(2026, 4, 7), antwoord)
    assert welzijnswaarde(check) == verwacht


# ── heeft_signaal ─────────────────────────────────────────────────────────────


def test_heeft_signaal_antwoord_1_geen_signaal():
    check = WelzijnsCheck("S001", date(2026, 4, 7), 1)
    assert not heeft_signaal(check)


def test_heeft_signaal_antwoord_2_wel_signaal():
    check = WelzijnsCheck("S001", date(2026, 4, 7), 2)
    assert heeft_signaal(check)


def test_heeft_signaal_antwoord_3_wel_signaal():
    check = WelzijnsCheck("S001", date(2026, 4, 7), 3)
    assert heeft_signaal(check)


def test_heeft_signaal_aangepaste_drempel():
    check = WelzijnsCheck("S001", date(2026, 4, 7), 2)
    assert not heeft_signaal(check, drempel=0.40)


# ── load_welzijn_csv ──────────────────────────────────────────────────────────


def test_load_welzijn_csv_demo():
    df = load_welzijn_csv(DEMO_WELZIJN)
    assert "studentnummer" in df.columns
    assert "datum" in df.columns
    assert "antwoord" in df.columns
    assert len(df) > 0


def test_load_welzijn_csv_antwoord_types(tmp_path):
    csv = tmp_path / "welzijn.csv"
    csv.write_text("studentnummer,datum,antwoord\nS001,2026-04-07,2\n")
    df = load_welzijn_csv(csv)
    assert int(df.iloc[0]["antwoord"]) == 2


def test_load_welzijn_csv_ongeldig_antwoord(tmp_path):
    csv = tmp_path / "welzijn.csv"
    csv.write_text("studentnummer,datum,antwoord\nS001,2026-04-07,9\n")
    with pytest.raises(ValueError, match="Ongeldige antwoordwaarden"):
        load_welzijn_csv(csv)


def test_load_welzijn_csv_ontbrekende_kolom(tmp_path):
    csv = tmp_path / "welzijn.csv"
    csv.write_text("studentnummer,datum\nS001,2026-04-07\n")
    with pytest.raises(ValueError, match="Ontbrekende verplichte kolommen"):
        load_welzijn_csv(csv)


def test_load_welzijn_csv_bestand_niet_gevonden(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_welzijn_csv(tmp_path / "bestaat_niet.csv")


# ── signaleringen ─────────────────────────────────────────────────────────────


@pytest.fixture
def df_studenten() -> pd.DataFrame:
    raw = pd.DataFrame(
        {
            "studentnummer": ["S001", "S002", "S003"],
            "naam": ["Alice", "Bob", "Carol"],
            "mentor": ["M. Bakker", "M. Bakker", "J. Smits"],
            "opleiding": ["Verzorgende IG"] * 3,
            "crebo": ["25491"] * 3,
            "niveau": pd.array([3, 3, 3], dtype="Int64"),
            "leerweg": ["BOL", "BOL", "BOL"],
            "cohort": ["2024-2025"] * 3,
            "leeftijd": pd.array([19, 20, 18], dtype="Int64"),
            "geslacht": ["V", "M", "V"],
            "bsa_behaald": [42.0, 38.0, 55.0],
            "bsa_vereist": [60.0, 60.0, 60.0],
            "voortgang": [0.70, 0.63, 0.92],
        }
    )
    return transform_student_data(raw)


@pytest.fixture
def df_welzijn() -> pd.DataFrame:
    return load_welzijn_csv(DEMO_WELZIJN)


def test_signaleringen_bevat_alleen_lage_scores(df_studenten, df_welzijn):
    result = signaleringen(df_studenten, df_welzijn)
    assert all(result["welzijnswaarde"] < 0.55)


def test_signaleringen_gesorteerd_op_waarde(df_studenten, df_welzijn):
    result = signaleringen(df_studenten, df_welzijn)
    waarden = result["welzijnswaarde"].tolist()
    assert waarden == sorted(waarden)


def test_signaleringen_bevat_naam_en_mentor(df_studenten, df_welzijn):
    result = signaleringen(df_studenten, df_welzijn)
    assert "naam" in result.columns
    assert "mentor" in result.columns


def test_signaleringen_leeg_bij_geen_welzijndata(df_studenten):
    leeg = pd.DataFrame(columns=["studentnummer", "datum", "antwoord", "toelichting"])
    result = signaleringen(df_studenten, leeg)
    assert result.empty


def test_signaleringen_geen_bij_hoge_drempel(df_studenten, df_welzijn):
    result = signaleringen(df_studenten, df_welzijn, drempel=0.0)
    assert result.empty


# ── antwoord_label ────────────────────────────────────────────────────────────


def test_antwoord_label_goed():
    assert antwoord_label(1) == "Goed"


def test_antwoord_label_matig():
    assert antwoord_label(2) == "Matig"


def test_antwoord_label_zwaar():
    assert antwoord_label(3) == "Zwaar"


def test_signaleringen_meest_recente_check_per_student(df_studenten):
    df_welzijn = pd.DataFrame(
        {
            "studentnummer": ["S001", "S001"],
            "datum": [date(2026, 3, 31), date(2026, 4, 7)],
            "antwoord": pd.array([3, 1], dtype="Int64"),
            "toelichting": [None, None],
        }
    )
    result = signaleringen(df_studenten, df_welzijn)
    assert result.empty


# ── Notities ──────────────────────────────────────────────────────────────────


def test_laad_notities_leeg_als_bestand_ontbreekt(tmp_path):
    df = laad_notities(tmp_path / "notities.csv")
    assert df.empty
    assert "studentnummer" in df.columns


def test_sla_notitie_op_en_laad(tmp_path):
    pad = tmp_path / "notities.csv"
    sla_notitie_op(pad, "S001", "M. Bakker", "Heb contact opgenomen")
    df = laad_notities(pad)
    assert len(df) == 1
    assert df.iloc[0]["studentnummer"] == "S001"
    assert df.iloc[0]["notitie"] == "Heb contact opgenomen"


def test_sla_notitie_op_meerdere_notities(tmp_path):
    pad = tmp_path / "notities.csv"
    sla_notitie_op(pad, "S001", "M. Bakker", "Eerste notitie")
    sla_notitie_op(pad, "S001", "M. Bakker", "Tweede notitie")
    df = laad_notities(pad)
    assert len(df) == 2


def test_sla_notitie_op_lege_tekst_geeft_fout(tmp_path):
    pad = tmp_path / "notities.csv"
    with pytest.raises(ValueError, match="leeg"):
        sla_notitie_op(pad, "S001", "M. Bakker", "   ")


def test_sla_notitie_op_maakt_map_aan(tmp_path):
    pad = tmp_path / "nieuw" / "notities.csv"
    sla_notitie_op(pad, "S001", "M. Bakker", "Test")
    assert pad.exists()


# ── filter_signaleringen_voor_mentor ──────────────────────────────────────────


@pytest.fixture
def df_signaleringen_twee_mentoren(df_studenten, df_welzijn):
    return signaleringen(df_studenten, df_welzijn)


def test_filter_mentor_geeft_subset(df_studenten, df_welzijn):
    alle = signaleringen(df_studenten, df_welzijn)
    if alle.empty:
        pytest.skip("Geen signaleringen in demo data voor deze fixture-studenten")
    mentor = alle.iloc[0]["mentor"]
    gefilterd = filter_signaleringen_voor_mentor(alle, mentor)
    assert all(gefilterd["mentor"] == mentor)


def test_filter_mentor_leeg_dataframe_blijft_leeg():
    leeg = pd.DataFrame(
        columns=[
            "studentnummer",
            "naam",
            "mentor",
            "datum",
            "antwoord",
            "toelichting",
            "welzijnswaarde",
        ]
    )
    result = filter_signaleringen_voor_mentor(leeg, "M. Bakker")
    assert result.empty


def test_filter_mentor_onbekende_mentor_geeft_leeg(df_studenten, df_welzijn):
    alle = signaleringen(df_studenten, df_welzijn)
    result = filter_signaleringen_voor_mentor(alle, "X. Onbekend")
    assert result.empty


# ── Bestandsrechten ───────────────────────────────────────────────────────────


@pytest.mark.skipif(os.getuid() == 0, reason="root negeert bestandsrechten")
def test_laad_notities_geen_leesrechten(tmp_path: Path) -> None:
    """laad_notities geeft PermissionError als het bestand niet leesbaar is."""
    pad = tmp_path / "notities.csv"
    pad.write_text("studentnummer,mentor,datum,notitie\n")
    pad.chmod(0o000)
    try:
        with pytest.raises(PermissionError):
            laad_notities(pad)
    finally:
        pad.chmod(0o644)


@pytest.mark.skipif(os.getuid() == 0, reason="root negeert bestandsrechten")
def test_sla_notitie_op_geen_schrijfrechten(tmp_path: Path) -> None:
    """sla_notitie_op geeft PermissionError als de map niet beschrijfbaar is."""
    beveiligde_map = tmp_path / "readonly"
    beveiligde_map.mkdir()
    beveiligde_map.chmod(0o555)
    try:
        with pytest.raises(PermissionError):
            sla_notitie_op(beveiligde_map / "notities.csv", "S001", "M. Bakker", "Test")
    finally:
        beveiligde_map.chmod(0o755)
