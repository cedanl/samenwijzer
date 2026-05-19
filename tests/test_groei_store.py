"""Tests voor samenwijzer.groei_store."""

import sqlite3
from pathlib import Path

import pytest

from samenwijzer.groei_store import (
    BewijsstukMeta,
    GroeiActueel,
    GroeiHistorieRij,
    MentorFeedback,
    init_db,
)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    pad = tmp_path / "test_groei.db"
    init_db(pad)
    return pad


def _tabelnamen(db_path: Path) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    finally:
        conn.close()
    return {r[0] for r in rows}


def _count(db_path: Path, tabel: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {tabel}").fetchone()[0]
    finally:
        conn.close()


def test_init_db_maakt_alle_tabellen(db: Path) -> None:
    tabellen = _tabelnamen(db)
    assert "groei_actueel" in tabellen
    assert "groei_historie" in tabellen
    assert "mentor_feedback" in tabellen
    assert "bewijsstuk" in tabellen


def test_init_db_idempotent(db: Path) -> None:
    init_db(db)  # mag geen fout opleveren bij tweede call
    assert _count(db, "groei_actueel") == 0


def test_bewijsstuk_check_constraint_weigert_zonder_wp_en_kt(db: Path) -> None:
    """De CHECK-constraint moet een bewijsstuk zonder wp_kolom én kt_kolom weigeren."""
    conn = sqlite3.connect(db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO bewijsstuk
                    (studentnummer, wp_kolom, kt_kolom, bestandsnaam, bestandspad,
                     mime_type, grootte_bytes, geupload_op)
                VALUES (?, NULL, NULL, ?, ?, ?, ?, ?)
                """,
                ("S001", "x.pdf", "S001/x.pdf", "application/pdf", 1, "2026-05-19T10:00:00"),
            )
    finally:
        conn.close()


def test_dataclasses_zijn_instantieerbaar() -> None:
    """Smoketest: de geëxporteerde dataclasses hebben de verwachte velden."""
    actueel = GroeiActueel("S001", "wp_1_1", 60, "ok", "2026-05-19T10:00:00")
    assert actueel.score == 60

    historie = GroeiHistorieRij("S001", "wp_1_1", 60, "ok", "2026-05-19T10:00:00")
    assert historie.id is None

    feedback = MentorFeedback("S001", "kt_1", "Jan", "Goed bezig", "2026-05-19T10:00:00")
    assert feedback.kt_kolom == "kt_1"

    bewijs = BewijsstukMeta(
        studentnummer="S001",
        bestandsnaam="x.pdf",
        bestandspad="S001/x.pdf",
        mime_type="application/pdf",
        grootte_bytes=1,
        geupload_op="2026-05-19T10:00:00",
    )
    assert bewijs.wp_kolom is None
    assert bewijs.kt_kolom is None
    assert bewijs.toelichting == ""
    assert bewijs.id is None


def test_sla_groei_op_schrijft_actueel_en_historie(db: Path) -> None:
    from samenwijzer.groei_store import get_actueel, get_historie, sla_groei_op

    rijen = [
        GroeiActueel("S001", "wp_1_1", 60, "ik kan dit", "2026-05-19T10:00:00"),
        GroeiActueel("S001", "wp_1_2", 75, "soms", "2026-05-19T10:00:00"),
    ]
    sla_groei_op("S001", rijen, db)

    actueel = get_actueel("S001", db)
    assert {r.wp_kolom for r in actueel} == {"wp_1_1", "wp_1_2"}
    assert next(r for r in actueel if r.wp_kolom == "wp_1_1").score == 60

    historie = get_historie("S001", db)
    assert len(historie) == 2


def test_sla_groei_op_upserts_en_voegt_historie_toe(db: Path) -> None:
    from samenwijzer.groei_store import get_actueel, get_historie, sla_groei_op

    sla_groei_op(
        "S001",
        [GroeiActueel("S001", "wp_1_1", 40, "v1", "2026-05-19T10:00:00")],
        db,
    )
    sla_groei_op(
        "S001",
        [GroeiActueel("S001", "wp_1_1", 70, "v2", "2026-05-19T11:00:00")],
        db,
    )

    actueel = get_actueel("S001", db)
    assert len(actueel) == 1
    assert actueel[0].score == 70
    assert actueel[0].verantwoording == "v2"

    historie = get_historie("S001", db)
    assert len(historie) == 2
    assert {h.score for h in historie} == {40, 70}


def test_sla_groei_op_is_atomic_bij_fout(db: Path) -> None:
    """Als een rij in de batch ongeldig is, mag geen enkele wijziging blijven hangen."""
    from samenwijzer.groei_store import get_actueel, sla_groei_op

    rijen = [
        GroeiActueel("S001", "wp_1_1", 50, "ok", "2026-05-19T10:00:00"),
        GroeiActueel("S001", "wp_1_1", None, "fout", "2026-05-19T10:00:00"),  # type: ignore[arg-type]
    ]
    with pytest.raises(sqlite3.IntegrityError):
        sla_groei_op("S001", rijen, db)

    actueel = get_actueel("S001", db)
    assert actueel == []


def test_get_actueel_voor_onbekende_student(db: Path) -> None:
    from samenwijzer.groei_store import get_actueel

    assert get_actueel("S999", db) == []


def test_get_alle_actueel_groepeert_per_studentnummer(db: Path) -> None:
    from samenwijzer.groei_store import get_alle_actueel, sla_groei_op

    sla_groei_op(
        "S001",
        [GroeiActueel("S001", "wp_1_1", 50, "", "2026-05-19T10:00:00")],
        db,
    )
    sla_groei_op(
        "S002",
        [GroeiActueel("S002", "wp_2_1", 80, "", "2026-05-19T10:00:00")],
        db,
    )

    alle = get_alle_actueel(db)
    assert set(alle.keys()) == {"S001", "S002"}
    assert alle["S001"][0].wp_kolom == "wp_1_1"
    assert alle["S002"][0].score == 80


def test_upsert_mentor_feedback_en_lezen(db: Path) -> None:
    from samenwijzer.groei_store import get_mentor_feedback, upsert_mentor_feedback

    upsert_mentor_feedback(
        MentorFeedback("S001", "kt_1", "Jan Jansen", "Mooie groei!", "2026-05-19T10:00:00"),
        db,
    )
    fb = get_mentor_feedback("S001", db)
    assert fb["kt_1"].tekst == "Mooie groei!"

    upsert_mentor_feedback(
        MentorFeedback("S001", "kt_1", "Jan Jansen", "Update", "2026-05-19T11:00:00"),
        db,
    )
    fb = get_mentor_feedback("S001", db)
    assert fb["kt_1"].tekst == "Update"


def test_bewijsstuk_insert_en_lijst(db: Path) -> None:
    from samenwijzer.groei_store import (
        get_bewijsstukken,
        insert_bewijsstuk,
        verwijder_bewijsstuk,
    )

    meta = BewijsstukMeta(
        studentnummer="S001",
        wp_kolom="wp_1_1",
        bestandsnaam="stage.pdf",
        bestandspad="S001/abc.pdf",
        mime_type="application/pdf",
        grootte_bytes=12345,
        toelichting="stageverslag",
        geupload_op="2026-05-19T10:00:00",
    )
    bewijsstuk_id = insert_bewijsstuk(meta, db)
    assert bewijsstuk_id > 0

    lijst = get_bewijsstukken("S001", db)
    assert len(lijst) == 1
    assert lijst[0].bestandsnaam == "stage.pdf"
    assert lijst[0].id == bewijsstuk_id

    verwijder_bewijsstuk(bewijsstuk_id, db)
    assert get_bewijsstukken("S001", db) == []


def test_bewijsstuk_get_via_id(db: Path) -> None:
    from samenwijzer.groei_store import get_bewijsstuk, insert_bewijsstuk

    meta = BewijsstukMeta(
        studentnummer="S001",
        kt_kolom="kt_1",
        bestandsnaam="kt.docx",
        bestandspad="S001/kt.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        grootte_bytes=2048,
        geupload_op="2026-05-19T10:00:00",
    )
    new_id = insert_bewijsstuk(meta, db)
    opgehaald = get_bewijsstuk(new_id, db)
    assert opgehaald is not None
    assert opgehaald.bestandsnaam == "kt.docx"
    assert opgehaald.kt_kolom == "kt_1"
    assert opgehaald.wp_kolom is None

    assert get_bewijsstuk(99999, db) is None
