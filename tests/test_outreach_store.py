"""Tests voor samenwijzer.outreach_store."""

from pathlib import Path

import pytest

from samenwijzer.outreach_store import (
    Interventie,
    StudentStatus,
    get_alle_interventies,
    get_alle_statussen,
    get_interventies_voor_student,
    get_student_status,
    init_db,
    log_interventie,
    upsert_status,
)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    """Tijdelijke SQLite-database per test."""
    pad = tmp_path / "test_outreach.db"
    init_db(pad)
    return pad


def test_init_db_maakt_tabellen(db: Path) -> None:
    import sqlite3

    with sqlite3.connect(db) as conn:
        tabellen = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "student_status" in tabellen
    assert "interventies" in tabellen


def test_get_student_status_standaard(db: Path) -> None:
    status = get_student_status("S999", db)
    assert status.studentnummer == "S999"
    assert status.status == "niet_gecontacteerd"
    assert status.laatste_contact is None


def test_upsert_en_ophalen_status(db: Path) -> None:
    s = StudentStatus(
        studentnummer="S001",
        status="gecontacteerd",
        laatste_contact="2026-04-08T10:00:00",
        laatste_mentor="Fatima",
        notitie="Bel teruggevraagd",
    )
    upsert_status(s, db)

    terug = get_student_status("S001", db)
    assert terug.status == "gecontacteerd"
    assert terug.laatste_mentor == "Fatima"
    assert terug.notitie == "Bel teruggevraagd"


def test_upsert_overschrijft_bestaande(db: Path) -> None:
    s1 = StudentStatus(studentnummer="S001", status="gecontacteerd")
    upsert_status(s1, db)

    s2 = StudentStatus(studentnummer="S001", status="opgelost", laatste_mentor="Piet")
    upsert_status(s2, db)

    terug = get_student_status("S001", db)
    assert terug.status == "opgelost"
    assert terug.laatste_mentor == "Piet"


def test_get_alle_statussen(db: Path) -> None:
    upsert_status(StudentStatus(studentnummer="S001", status="gecontacteerd"), db)
    upsert_status(StudentStatus(studentnummer="S002", status="gereageerd"), db)

    alle = get_alle_statussen(db)
    assert "S001" in alle
    assert "S002" in alle
    assert alle["S001"].status == "gecontacteerd"


def _maak_interventie(snr: str = "S001") -> Interventie:
    return Interventie(
        studentnummer=snr,
        timestamp="2026-04-08T10:00:00",
        mentor="Fatima",
        status_voor="niet_gecontacteerd",
        status_na="gecontacteerd",
        bericht_samenvatting="Hoi, kun je langskomen?",
        voortgang_op_moment=0.35,
        bsa_percentage_op_moment=0.70,
    )


def test_log_en_ophalen_interventie(db: Path) -> None:
    log_interventie(_maak_interventie(), db)
    interventies = get_interventies_voor_student("S001", db)

    assert len(interventies) == 1
    iv = interventies[0]
    assert iv.mentor == "Fatima"
    assert iv.status_voor == "niet_gecontacteerd"
    assert iv.status_na == "gecontacteerd"
    assert iv.voortgang_op_moment == pytest.approx(0.35)
    assert iv.id is not None


def test_get_interventies_voor_student_leeg(db: Path) -> None:
    assert get_interventies_voor_student("S999", db) == []


def test_get_alle_interventies(db: Path) -> None:
    log_interventie(_maak_interventie("S001"), db)
    log_interventie(_maak_interventie("S002"), db)

    alle = get_alle_interventies(db)
    assert len(alle) == 2


def test_interventies_gesorteerd_nieuwste_eerst(db: Path) -> None:
    iv1 = _maak_interventie()
    iv1 = Interventie(
        **{**iv1.__dict__, "timestamp": "2026-04-01T08:00:00", "id": None}
    )
    iv2 = Interventie(
        **{**iv1.__dict__, "timestamp": "2026-04-08T10:00:00", "id": None}
    )
    log_interventie(iv1, db)
    log_interventie(iv2, db)

    resultaat = get_interventies_voor_student("S001", db)
    assert resultaat[0].timestamp > resultaat[1].timestamp
