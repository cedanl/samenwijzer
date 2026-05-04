"""Tests voor oer_store: SQLite-catalog van OERs."""

import sqlite3
from pathlib import Path

import pytest

from samenwijzer import oer_store


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "oeren.db"
    oer_store.init_db(p)
    return p


def test_init_db_maakt_tabellen_aan(db_path: Path):
    with sqlite3.connect(db_path) as conn:
        tabellen = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"instellingen", "oer_documenten", "kerntaken"} <= tabellen


def test_voeg_instelling_toe_en_get(db_path: Path):
    oer_store.voeg_instelling_toe(db_path, naam="rijn_ijssel", display_naam="Rijn IJssel")
    inst = oer_store.get_instelling_by_naam(db_path, "rijn_ijssel")
    assert inst is not None
    assert inst["display_naam"] == "Rijn IJssel"


def test_get_instelling_onbekend_geeft_none(db_path: Path):
    assert oer_store.get_instelling_by_naam(db_path, "onbekend") is None


def test_voeg_instelling_dubbel_faalt_silently(db_path: Path):
    """INSERT OR IGNORE — dubbele toevoeging mag niet exception-en."""
    oer_store.voeg_instelling_toe(db_path, naam="aeres", display_naam="Aeres MBO")
    oer_store.voeg_instelling_toe(db_path, naam="aeres", display_naam="Aeres MBO")
    inst = oer_store.get_instelling_by_naam(db_path, "aeres")
    assert inst["display_naam"] == "Aeres MBO"
