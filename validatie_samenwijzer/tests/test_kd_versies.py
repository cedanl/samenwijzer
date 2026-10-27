"""KD-versies per cohort: oudere versie naast de nieuwste (manifest `versies/versies.json`)."""

import json
import sqlite3

import pytest

from validatie_samenwijzer.db import init_db, voeg_instelling_toe, voeg_oer_document_toe
from validatie_samenwijzer.kd_versies import controleer_kd_versies, kies_kd_pad

MANIFEST = {
    "25122": [
        {"versie": "2016", "bestand": "25122@2016.md", "cohorten": [2016, 2025]},
        {"versie": "2026", "bestand": "25122@2026.md", "cohorten": [2026, 2099]},
    ]
}


@pytest.fixture
def kd_map(tmp_path, monkeypatch):
    """`pdfs/` met het nieuwste KD als <crebo>.md en versies/ met manifest + oude versie."""
    (tmp_path / "versies").mkdir()
    (tmp_path / "25122.md").write_text("NIEUWSTE KD", encoding="utf-8")
    (tmp_path / "versies" / "25122@2016.md").write_text("KD 2016", encoding="utf-8")
    (tmp_path / "versies" / "25122@2026.md").write_text("KD 2026", encoding="utf-8")
    (tmp_path / "versies" / "versies.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    monkeypatch.setenv("KWALDOSSIERS_PAD", str(tmp_path))
    return tmp_path


def test_kiest_versie_waarvan_cohortbereik_het_cohort_bevat(kd_map):
    assert kies_kd_pad("25122", "2025").name == "25122@2016.md"
    assert kies_kd_pad("25122", 2026).name == "25122@2026.md"


def test_geen_match_geeft_none_zodat_de_nieuwste_geldt(kd_map):
    assert kies_kd_pad("25122", "2010") is None
    assert kies_kd_pad("99999", "2025") is None  # crebo zonder manifest


def test_zonder_manifest_of_cohort_geen_keuze(tmp_path, monkeypatch):
    monkeypatch.setenv("KWALDOSSIERS_PAD", str(tmp_path))
    assert kies_kd_pad("25122", "2025") is None


def test_cohort_leeg_of_geen_getal_geeft_none(kd_map):
    assert kies_kd_pad("25122", None) is None
    assert kies_kd_pad("25122", "") is None
    assert kies_kd_pad("25122", "twintig") is None


def test_ontbrekend_bestand_in_manifest_geeft_none(kd_map):
    (kd_map / "versies" / "25122@2016.md").unlink()
    assert kies_kd_pad("25122", "2025") is None


def test_kapot_manifest_geeft_none_zonder_crash(kd_map):
    (kd_map / "versies" / "versies.json").write_text("{kapot", encoding="utf-8")
    assert kies_kd_pad("25122", "2025") is None


def test_laad_kwalificatiedossier_tekst_gebruikt_de_cohortversie(kd_map):
    from validatie_samenwijzer.chat import laad_kwalificatiedossier_tekst

    assert laad_kwalificatiedossier_tekst("25122", "2025") == "KD 2016"
    assert laad_kwalificatiedossier_tekst("25122", "2010") == "NIEUWSTE KD"  # terugval
    assert laad_kwalificatiedossier_tekst("25122") == "NIEUWSTE KD"  # zonder cohort: ongewijzigd


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


def test_controle_waarschuwt_voor_versie_zonder_oer_in_cohortbereik(kd_map, conn):
    inst = voeg_instelling_toe(conn, "kwic", "KW1C")
    voeg_oer_document_toe(conn, inst, "Werkvoorbereider", "25122", "2025", "BBL", "x.pdf")
    meldingen = controleer_kd_versies(conn)
    # 2016-versie heeft een OER (cohort 2025); 2026-versie niet
    assert len(meldingen) == 1 and "25122" in meldingen[0] and "2026" in meldingen[0]


def test_controle_zonder_manifest_geeft_geen_meldingen(tmp_path, monkeypatch, conn):
    monkeypatch.setenv("KWALDOSSIERS_PAD", str(tmp_path))
    assert controleer_kd_versies(conn) == []
