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
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
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
