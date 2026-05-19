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


def test_init_db_maakt_alle_tabellen(db: Path) -> None:
    with sqlite3.connect(db) as conn:
        tabellen = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "groei_actueel" in tabellen
    assert "groei_historie" in tabellen
    assert "mentor_feedback" in tabellen
    assert "bewijsstuk" in tabellen


def test_init_db_idempotent(db: Path) -> None:
    init_db(db)  # mag geen fout opleveren bij tweede call
    with sqlite3.connect(db) as conn:
        n = conn.execute("SELECT COUNT(*) FROM groei_actueel").fetchone()[0]
    assert n == 0
