"""Tests voor build_oer_catalog.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from build_oer_catalog import bouw_catalog  # noqa: E402

from samenwijzer import oer_store


@pytest.fixture
def kleine_oeren_dir(tmp_path: Path) -> Path:
    """Maak een mini-oeren/-structuur aan met 2 instellingen, elk 1 file."""
    inst_a = tmp_path / "rijn_ijssel_oer"
    inst_a.mkdir()
    (inst_a / "25655_BOL_2025__verzorgende-ig.md").write_text(
        "# Verzorgende IG\nMBO niveau 3.\nB1-K1: Bieden van zorg\n"
        "B1-K1-W1: Onderkent zorg\n"
    )
    inst_b = tmp_path / "talland_oeren"
    inst_b.mkdir()
    (inst_b / "25180_BBL_2025__Kok 24 maanden.md").write_text(
        "# Kok\nB1-K1: Voorbereiden\n"
    )
    return tmp_path


def test_bouw_catalog_voegt_instellingen_toe(kleine_oeren_dir: Path, tmp_path: Path):
    db_pad = tmp_path / "oeren.db"
    bouw_catalog(kleine_oeren_dir, db_pad)
    rijn = oer_store.get_instelling_by_naam(db_pad, "rijn_ijssel")
    talland = oer_store.get_instelling_by_naam(db_pad, "talland")
    assert rijn is not None and rijn["display_naam"] == "Rijn IJssel"
    assert talland is not None and talland["display_naam"] == "Talland"


def test_bouw_catalog_voegt_oer_documenten_toe(kleine_oeren_dir: Path, tmp_path: Path):
    db_pad = tmp_path / "oeren.db"
    bouw_catalog(kleine_oeren_dir, db_pad)
    rijn = oer_store.get_instelling_by_naam(db_pad, "rijn_ijssel")
    oer = oer_store.get_oer_document(db_pad, rijn["id"], "25655", "BOL", "2025")
    assert oer is not None
    assert "Verzorgende" in oer["opleiding"]
    assert oer["niveau"] == 3


def test_bouw_catalog_voegt_kerntaken_toe(kleine_oeren_dir: Path, tmp_path: Path):
    db_pad = tmp_path / "oeren.db"
    bouw_catalog(kleine_oeren_dir, db_pad)
    rijn = oer_store.get_instelling_by_naam(db_pad, "rijn_ijssel")
    oer = oer_store.get_oer_document(db_pad, rijn["id"], "25655", "BOL", "2025")
    kts = oer_store.get_kerntaken_voor_oer(db_pad, oer["id"])
    codes = [k["code"] for k in kts]
    assert "B1-K1" in codes
    assert "B1-K1-W1" in codes


def test_bouw_catalog_negeert_bestanden_zonder_crebo(tmp_path: Path):
    inst = tmp_path / "aeres_oeren"
    inst.mkdir()
    (inst / "OER 2025 algemeen.md").write_text("Geen crebo.")
    (inst / "25655_BOL_2025__verzorgende-ig.md").write_text("# Verzorgende IG")
    db_pad = tmp_path / "oeren.db"
    bouw_catalog(tmp_path, db_pad)
    alle = oer_store.get_alle_oers(db_pad)
    assert len(alle) == 1  # alleen die met crebo
