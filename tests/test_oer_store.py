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


def test_voeg_oer_document_toe_en_get(db_path: Path):
    oer_store.voeg_instelling_toe(db_path, "rijn_ijssel", "Rijn IJssel")
    inst = oer_store.get_instelling_by_naam(db_path, "rijn_ijssel")
    oer_id = oer_store.voeg_oer_document_toe(
        db_path,
        instelling_id=inst["id"],
        opleiding="Verzorgende IG",
        crebo="25655",
        cohort="2025",
        leerweg="BOL",
        niveau=3,
        bestandspad="oeren/rijn_ijssel_oer/25655_BOL_2025__verzorgende-ig.md",
    )
    assert oer_id > 0

    oer = oer_store.get_oer_document(db_path, inst["id"], "25655", "BOL", "2025")
    assert oer["opleiding"] == "Verzorgende IG"
    assert oer["niveau"] == 3


def test_oer_document_unique_per_instelling(db_path: Path):
    """Twee instellingen mogen dezelfde (crebo, leerweg, cohort) hebben."""
    oer_store.voeg_instelling_toe(db_path, "talland", "Talland")
    oer_store.voeg_instelling_toe(db_path, "rijn_ijssel", "Rijn IJssel")
    talland = oer_store.get_instelling_by_naam(db_path, "talland")
    rijn = oer_store.get_instelling_by_naam(db_path, "rijn_ijssel")

    id1 = oer_store.voeg_oer_document_toe(
        db_path, talland["id"], "Kok", "25180", "2025", "BBL", 3, "p1.md"
    )
    id2 = oer_store.voeg_oer_document_toe(
        db_path, rijn["id"], "Kok", "25180", "2025", "BBL", 3, "p2.md"
    )
    assert id1 != id2


def test_oer_document_dubbel_binnen_instelling_faalt(db_path: Path):
    oer_store.voeg_instelling_toe(db_path, "talland", "Talland")
    talland = oer_store.get_instelling_by_naam(db_path, "talland")
    oer_store.voeg_oer_document_toe(
        db_path, talland["id"], "Kok", "25180", "2025", "BBL", 3, "p1.md"
    )
    with pytest.raises(sqlite3.IntegrityError):
        oer_store.voeg_oer_document_toe(
            db_path, talland["id"], "Kok", "25180", "2025", "BBL", 3, "p1.md"
        )


def test_get_oer_document_voor_student(db_path: Path):
    """Lookup helper voor B: vind OER bij (instelling_naam, crebo, leerweg, cohort)."""
    oer_store.voeg_instelling_toe(db_path, "rijn_ijssel", "Rijn IJssel")
    inst = oer_store.get_instelling_by_naam(db_path, "rijn_ijssel")
    oer_store.voeg_oer_document_toe(
        db_path, inst["id"], "Verzorgende IG", "25655", "2025", "BOL", 3, "p.md"
    )
    oer = oer_store.get_oer_voor_student(
        db_path, instelling_naam="rijn_ijssel", crebo="25655", leerweg="BOL", cohort="2025"
    )
    assert oer["opleiding"] == "Verzorgende IG"


def test_get_oer_voor_student_geen_match(db_path: Path):
    assert oer_store.get_oer_voor_student(
        db_path, "onbekend", "00000", "BOL", "2025"
    ) is None


def test_voeg_kerntaak_toe_en_haal_op(db_path: Path):
    oer_store.voeg_instelling_toe(db_path, "rijn_ijssel", "Rijn IJssel")
    inst = oer_store.get_instelling_by_naam(db_path, "rijn_ijssel")
    oer_id = oer_store.voeg_oer_document_toe(
        db_path, inst["id"], "Verzorgende IG", "25655", "2025", "BOL", 3, "p.md"
    )
    oer_store.voeg_kerntaak_toe(
        db_path, oer_id, code="B1-K1", naam="Bieden van zorg", type_="kerntaak", volgorde=0
    )
    oer_store.voeg_kerntaak_toe(
        db_path, oer_id, code="B1-K1-W1", naam="Onderkent zorg", type_="werkproces",
        parent_code="B1-K1", volgorde=1,
    )
    kts = oer_store.get_kerntaken_voor_oer(db_path, oer_id)
    assert len(kts) == 2
    assert kts[0]["code"] == "B1-K1"
    assert kts[1]["parent_code"] == "B1-K1"


def test_get_kerntaken_voor_opleiding_zoekt_via_oer(db_path: Path):
    """Lookup helper: kerntaken voor een (opleiding, niveau, cohort) — pakt eerste OER."""
    oer_store.voeg_instelling_toe(db_path, "rijn_ijssel", "Rijn IJssel")
    inst = oer_store.get_instelling_by_naam(db_path, "rijn_ijssel")
    oer_id = oer_store.voeg_oer_document_toe(
        db_path, inst["id"], "Verzorgende IG", "25655", "2025", "BOL", 3, "p.md"
    )
    oer_store.voeg_kerntaak_toe(
        db_path, oer_id, "B1-K1", "Bieden van zorg", "kerntaak", None, 0
    )
    oer_store.voeg_kerntaak_toe(
        db_path, oer_id, "B1-K2", "Werken aan beroep", "kerntaak", None, 1
    )

    kts = oer_store.get_kerntaken_voor_opleiding(db_path, "Verzorgende IG", niveau=3)
    namen = [k["naam"] for k in kts]
    assert "Bieden van zorg" in namen


def test_get_kerntaken_voor_onbekende_opleiding_geeft_lijst_leeg(db_path: Path):
    assert oer_store.get_kerntaken_voor_opleiding(db_path, "Onbekend", niveau=3) == []
