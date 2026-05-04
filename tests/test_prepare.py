"""Tests voor samenwijzer.prepare."""

import os
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from samenwijzer import oer_store, prepare
from samenwijzer.prepare import load_student_csv, load_synthetisch_csv


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


# ── load_synthetisch_csv ──────────────────────────────────────────────────────

# Synthetisch CSV-formaat: bevat onder andere Instelling, Opleiding, crebo,
# leerweg en cohort als kolommen (geen mapping meer).
_SYNTHETISCH_HEADER = (
    "Studentnummer,Naam,Klas,Mentor,Instelling,Opleiding,crebo,leerweg,cohort,"
    "StudentAge,StudentGender,Dropout,Aanmel_aantal,max1studie,absence_unauthorized,"
    "absence_authorized,Richting_nan,Economie,Landbouw,Techniek,DSV,Zorgenwelzijn,"
    "Anders,VooroplNiveau_HAVO,VooroplNiveau_MBO,VooroplNiveau_basis,"
    "VooroplNiveau_educatie,VooroplNiveau_prak,VooroplNiveau_VMBO_BB,"
    "VooroplNiveau_VMBO_GL,VooroplNiveau_VMBO_KB,VooroplNiveau_VMBO_TL,"
    "VooroplNiveau_nan,VooroplNiveau_VWOplus,VooroplNiveau_other"
)


def _synth_row(
    studentnummer: str,
    naam: str,
    klas: str,
    opleiding: str,
    crebo: str = "25655",
    instelling: str = "Rijn IJssel",
    leerweg: str = "BOL",
    cohort: str = "2025",
    leeftijd: int = 19,
    geslacht: int = 1,
    absence_unauthorized: float = 5.0,
) -> str:
    """Bouw een synthetische CSV-rij. Onbelangrijke kolommen krijgen 0."""
    velden = [
        studentnummer,
        naam,
        klas,
        "M. Bakker",
        instelling,
        opleiding,
        crebo,
        leerweg,
        cohort,
        str(leeftijd),
        str(geslacht),
        "0",
        "1.0",
        "0.0",
        str(absence_unauthorized),
        "2.0",
    ]
    # 19 nullen voor de Richting_* en VooroplNiveau_* kolommen
    velden.extend(["0"] * 19)
    return ",".join(velden)


@pytest.fixture
def db_pad_met_oer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Maak een tmp oeren.db met enkele opleidingen + kerntaken en monkeypatch het pad."""
    db = tmp_path / "oeren.db"
    oer_store.voeg_instelling_toe(db, "TestInstelling", "Test Instelling")
    rij = oer_store.get_instelling_by_naam(db, "TestInstelling")
    assert rij is not None
    instelling_id = int(rij["id"])

    # Verzorgende IG niveau 3 — 2 kerntaken + 3 werkprocessen
    oer_id = oer_store.voeg_oer_document_toe(
        db, instelling_id, "Verzorgende IG", "25655", "2025", "BOL", 3, "n.v.t."
    )
    oer_store.voeg_kerntaak_toe(db, oer_id, "B1-K1", "KT1 Zorgverlening", "kerntaak", None, 1)
    oer_store.voeg_kerntaak_toe(db, oer_id, "B1-K2", "KT2 Begeleiding", "kerntaak", None, 2)
    oer_store.voeg_kerntaak_toe(db, oer_id, "B1-K1-W1", "WP1.1 Intake", "werkproces", "B1-K1", 1)
    oer_store.voeg_kerntaak_toe(db, oer_id, "B1-K1-W2", "WP1.2 Plan", "werkproces", "B1-K1", 2)
    oer_store.voeg_kerntaak_toe(db, oer_id, "B1-K2-W1", "WP2.1 Uitvoer", "werkproces", "B1-K2", 3)

    # EenKtOpleiding — 1 kerntaak + 1 werkproces (zodat kt_2 NaN wordt)
    oer_id2 = oer_store.voeg_oer_document_toe(
        db, instelling_id, "EenKtOpleiding", "99999", "2025", "BOL", 3, "n.v.t."
    )
    oer_store.voeg_kerntaak_toe(db, oer_id2, "B1-K1", "Enige KT", "kerntaak", None, 1)
    oer_store.voeg_kerntaak_toe(db, oer_id2, "B1-K1-W1", "Enige WP", "werkproces", "B1-K1", 1)

    monkeypatch.setattr(prepare, "_DB_PAD_VOOR_KT", db)
    return db


@pytest.fixture
def synthetisch_csv(tmp_path: Path, db_pad_met_oer: Path) -> Path:
    """Synthetisch-format CSV met twee studenten in een opleiding die in de tmp DB staat."""
    rijen = [
        _SYNTHETISCH_HEADER,
        _synth_row("100001", "Ali Yilmaz", "3B", "Verzorgende IG", absence_unauthorized=5),
        _synth_row(
            "100002",
            "Ben de Vries",
            "3B",
            "Verzorgende IG",
            geslacht=0,
            absence_unauthorized=20,
        ),
    ]
    p = tmp_path / "studenten.csv"
    p.write_text("\n".join(rijen) + "\n")
    return p


def test_load_synthetisch_csv_bestand_niet_gevonden(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_synthetisch_csv(tmp_path / "bestaat_niet.csv")


def test_load_synthetisch_csv_geeft_dataframe(synthetisch_csv: Path) -> None:
    df = load_synthetisch_csv(synthetisch_csv)
    assert len(df) == 2
    assert set(df["studentnummer"]) == {"100001", "100002"}


def test_load_synthetisch_csv_standaard_kolommen(synthetisch_csv: Path) -> None:
    df = load_synthetisch_csv(synthetisch_csv)
    for kolom in (
        "naam",
        "mentor",
        "instelling",
        "opleiding",
        "crebo",
        "niveau",
        "leerweg",
        "cohort",
        "voortgang",
    ):
        assert kolom in df.columns, f"Kolom '{kolom}' ontbreekt"


def test_load_synthetisch_csv_leerweg_uit_csv(synthetisch_csv: Path) -> None:
    df = load_synthetisch_csv(synthetisch_csv)
    assert (df["leerweg"] == "BOL").all()


def test_load_synthetisch_csv_cohort_uit_csv(synthetisch_csv: Path) -> None:
    df = load_synthetisch_csv(synthetisch_csv)
    assert (df["cohort"] == "2025").all()


def test_load_synthetisch_csv_crebo_uit_csv(synthetisch_csv: Path) -> None:
    df = load_synthetisch_csv(synthetisch_csv)
    assert (df["crebo"] == "25655").all()


def test_load_synthetisch_csv_voortgang_tussen_0_en_1(synthetisch_csv: Path) -> None:
    df = load_synthetisch_csv(synthetisch_csv)
    assert df["voortgang"].between(0, 1).all()


def test_load_synthetisch_csv_geslacht_mapping(synthetisch_csv: Path) -> None:
    df = load_synthetisch_csv(synthetisch_csv)
    geslacht = dict(zip(df["studentnummer"], df["geslacht"]))
    assert geslacht["100001"] == "V"  # StudentGender=1 → V
    assert geslacht["100002"] == "M"  # StudentGender=0 → M


def test_load_synthetisch_csv_niveau_uit_klascode(synthetisch_csv: Path) -> None:
    df = load_synthetisch_csv(synthetisch_csv)
    # "3B" → niveau 3
    assert (df["niveau"] == 3).all()


def test_load_synthetisch_csv_voegt_kt_kolommen_toe(synthetisch_csv: Path) -> None:
    df = load_synthetisch_csv(synthetisch_csv)
    assert "kt_1" in df.columns
    assert "kt_2" in df.columns
    for wp in ("wp_1_1", "wp_1_2", "wp_1_3", "wp_2_1", "wp_2_2", "wp_2_3"):
        assert wp in df.columns


def test_load_synthetisch_csv_kt_scores_binnen_bereik(synthetisch_csv: Path) -> None:
    df = load_synthetisch_csv(synthetisch_csv)
    kt_waarden = df["kt_1"].dropna()
    assert (kt_waarden >= 0).all()
    assert (kt_waarden <= 100).all()


def test_load_synthetisch_csv_opleiding_met_slechts_een_kt(
    tmp_path: Path, db_pad_met_oer: Path
) -> None:
    # OER bevat alleen kt_1 voor deze opleiding → kt_2 wordt NaN
    rijen = [
        _SYNTHETISCH_HEADER,
        _synth_row(
            "100003",
            "Test Student",
            "3B",
            "EenKtOpleiding",
            crebo="99999",
            absence_unauthorized=10,
        ),
    ]
    p = tmp_path / "studenten_eenkt.csv"
    p.write_text("\n".join(rijen) + "\n")

    df = load_synthetisch_csv(p)
    assert pd.isna(df.iloc[0]["kt_2"])
    # kt_1 is wel gevuld
    assert not pd.isna(df.iloc[0]["kt_1"])


def test_load_synthetisch_csv_onbekende_opleiding_geeft_nan(
    tmp_path: Path, db_pad_met_oer: Path
) -> None:
    """Studenten in een opleiding die niet in oeren.db staat krijgen NaN voor kt/wp."""
    rijen = [
        _SYNTHETISCH_HEADER,
        _synth_row(
            "100004",
            "Onbekend Student",
            "3B",
            "OnbekendeOpleiding",
            crebo="00000",
            absence_unauthorized=10,
        ),
    ]
    p = tmp_path / "studenten_onbekend.csv"
    p.write_text("\n".join(rijen) + "\n")

    df = load_synthetisch_csv(p)
    assert pd.isna(df.iloc[0]["kt_1"])
    assert pd.isna(df.iloc[0]["kt_2"])


# ── Bestandsrechten ───────────────────────────────────────────────────────────


@pytest.mark.skipif(os.getuid() == 0, reason="root negeert bestandsrechten")
def test_load_student_csv_geen_leesrechten(tmp_path: Path) -> None:
    """load_student_csv geeft PermissionError als het bestand niet leesbaar is."""
    p = tmp_path / "studenten.csv"
    p.write_text("dummy")
    p.chmod(0o000)
    try:
        with pytest.raises(PermissionError):
            load_student_csv(p)
    finally:
        p.chmod(0o644)


@pytest.mark.skipif(os.getuid() == 0, reason="root negeert bestandsrechten")
def test_load_welzijn_csv_geen_leesrechten(tmp_path: Path) -> None:
    """load_welzijn_csv geeft PermissionError als het bestand niet leesbaar is."""
    from samenwijzer.prepare import load_welzijn_csv

    p = tmp_path / "welzijn.csv"
    p.write_text("dummy")
    p.chmod(0o000)
    try:
        with pytest.raises(PermissionError):
            load_welzijn_csv(p)
    finally:
        p.chmod(0o644)


@pytest.mark.skipif(os.getuid() == 0, reason="root negeert bestandsrechten")
def test_load_synthetisch_csv_geen_leesrechten(tmp_path: Path) -> None:
    """load_synthetisch_csv geeft PermissionError als het bestand niet leesbaar is."""
    p = tmp_path / "studenten.csv"
    p.write_text("dummy")
    p.chmod(0o000)
    try:
        with pytest.raises(PermissionError):
            load_synthetisch_csv(p)
    finally:
        p.chmod(0o644)
