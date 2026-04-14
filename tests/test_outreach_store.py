"""Tests voor samenwijzer.outreach_store."""

from pathlib import Path

import pytest

from samenwijzer.outreach_store import (
    Campagne,
    Interventie,
    StudentStatus,
    WelzijnsCheck,
    get_alle_campagnes,
    get_alle_interventies,
    get_alle_statussen,
    get_alle_welzijnschecks,
    get_interventies_voor_student,
    get_student_status,
    get_welzijnschecks_student,
    init_db,
    log_interventie,
    maak_campagne,
    sla_welzijnscheck_op,
    sluit_campagne,
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
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
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
    iv1 = Interventie(**{**iv1.__dict__, "timestamp": "2026-04-01T08:00:00", "id": None})
    iv2 = Interventie(**{**iv1.__dict__, "timestamp": "2026-04-08T10:00:00", "id": None})
    log_interventie(iv1, db)
    log_interventie(iv2, db)

    resultaat = get_interventies_voor_student("S001", db)
    assert resultaat[0].timestamp > resultaat[1].timestamp


# ── Campagne ──────────────────────────────────────────────────────────────────


def _maak_campagne(naam: str = "BSA-campagne april") -> Campagne:
    return Campagne(
        naam=naam,
        transitiemoment="bsa_risico",
        bericht_template="Hoi {naam}, we willen even contact opnemen.",
        aangemaakt_door="Fatima",
        aangemaakt_op="2026-04-08T09:00:00",
        doelgroep_filter={"opleiding": "Verpleging"},
    )


def test_maak_campagne_geeft_id_terug(db: Path) -> None:
    campagne_id = maak_campagne(_maak_campagne(), db)
    assert isinstance(campagne_id, int)
    assert campagne_id > 0


def test_get_alle_campagnes_na_aanmaken(db: Path) -> None:
    maak_campagne(_maak_campagne("Campagne A"), db)
    maak_campagne(_maak_campagne("Campagne B"), db)

    campagnes = get_alle_campagnes(db)
    namen = [c.naam for c in campagnes]
    assert "Campagne A" in namen
    assert "Campagne B" in namen


def test_get_alle_campagnes_leeg(db: Path) -> None:
    assert get_alle_campagnes(db) == []


def test_campagne_status_is_actief_na_aanmaken(db: Path) -> None:
    maak_campagne(_maak_campagne(), db)
    campagnes = get_alle_campagnes(db)
    assert campagnes[0].status == "actief"


def test_campagne_doelgroep_filter_bewaard(db: Path) -> None:
    c = _maak_campagne()
    c.doelgroep_filter = {"opleiding": "Verpleging", "niveau": 3}
    maak_campagne(c, db)

    terug = get_alle_campagnes(db)[0]
    assert terug.doelgroep_filter == {"opleiding": "Verpleging", "niveau": 3}


def test_sluit_campagne_zet_status_afgesloten(db: Path) -> None:
    campagne_id = maak_campagne(_maak_campagne(), db)
    sluit_campagne(campagne_id, db)

    campagnes = get_alle_campagnes(db)
    assert campagnes[0].status == "afgesloten"


def test_sluit_campagne_laat_andere_campagnes_ongemoeid(db: Path) -> None:
    id1 = maak_campagne(_maak_campagne("A"), db)
    maak_campagne(_maak_campagne("B"), db)
    sluit_campagne(id1, db)

    campagnes = {c.naam: c for c in get_alle_campagnes(db)}
    assert campagnes["A"].status == "afgesloten"
    assert campagnes["B"].status == "actief"


# ── WelzijnsCheck ─────────────────────────────────────────────────────────────


def _maak_check(snr: str = "S001", urgentie: int = 2) -> WelzijnsCheck:
    return WelzijnsCheck(
        studentnummer=snr,
        timestamp="2026-04-08T11:00:00",
        categorie="welzijn",
        toelichting="Ik voel me overweldigd",
        urgentie=urgentie,
    )


def test_sla_welzijnscheck_op_geeft_id_terug(db: Path) -> None:
    check_id = sla_welzijnscheck_op(_maak_check(), db)
    assert isinstance(check_id, int)
    assert check_id > 0


def test_get_welzijnschecks_student_haalt_eigen_checks_op(db: Path) -> None:
    sla_welzijnscheck_op(_maak_check("S001"), db)
    sla_welzijnscheck_op(_maak_check("S001"), db)
    sla_welzijnscheck_op(_maak_check("S002"), db)

    checks = get_welzijnschecks_student("S001", db)
    assert len(checks) == 2
    assert all(c.studentnummer == "S001" for c in checks)


def test_get_welzijnschecks_student_leeg(db: Path) -> None:
    assert get_welzijnschecks_student("S999", db) == []


def test_welzijnscheck_velden_correct_opgeslagen(db: Path) -> None:
    check = WelzijnsCheck(
        studentnummer="S042",
        timestamp="2026-04-10T14:30:00",
        categorie="financiën",
        toelichting="Huurachterstand",
        urgentie=3,
    )
    sla_welzijnscheck_op(check, db)

    terug = get_welzijnschecks_student("S042", db)[0]
    assert terug.categorie == "financiën"
    assert terug.toelichting == "Huurachterstand"
    assert terug.urgentie == 3
    assert terug.id is not None


def test_get_alle_welzijnschecks_geeft_alle_studenten(db: Path) -> None:
    sla_welzijnscheck_op(_maak_check("S001"), db)
    sla_welzijnscheck_op(_maak_check("S002"), db)
    sla_welzijnscheck_op(_maak_check("S003"), db)

    alle = get_alle_welzijnschecks(db)
    assert len(alle) == 3


def test_welzijnschecks_gesorteerd_nieuwste_eerst(db: Path) -> None:
    oud = WelzijnsCheck(
        studentnummer="S001",
        timestamp="2026-04-01T08:00:00",
        categorie="overig",
        toelichting="",
        urgentie=1,
    )
    nieuw = WelzijnsCheck(
        studentnummer="S001",
        timestamp="2026-04-10T12:00:00",
        categorie="welzijn",
        toelichting="",
        urgentie=2,
    )
    sla_welzijnscheck_op(oud, db)
    sla_welzijnscheck_op(nieuw, db)

    checks = get_welzijnschecks_student("S001", db)
    assert checks[0].timestamp > checks[1].timestamp
