"""Tests voor het bronactualiteit-rapport. Geen netwerk: skills-check en
geïndexeerde crebo's worden gemockt."""

import pytest

from validatie_samenwijzer import bron_updates, sync_afgeleid


@pytest.fixture
def gemockte_bronnen(tmp_path, monkeypatch):
    kd_dir = tmp_path / "kd"
    kd_dir.mkdir()
    (kd_dir / "25180.md").write_text("kd", encoding="utf-8")  # 25180 heeft dekking
    monkeypatch.setattr(sync_afgeleid, "kd_dir", lambda: kd_dir)
    monkeypatch.setattr(sync_afgeleid, "geindexeerde_crebos", lambda: {"25180", "23110"})
    # skills-adapter: 1 upgrade beschikbaar
    monkeypatch.setattr(bron_updates, "_skills_dry_run", lambda: (["25180"], ["23110"]))
    return tmp_path


def test_skills_status_meldt_upgrades(gemockte_bronnen):
    statussen = {s.bron: s for s in bron_updates.verzamel_bron_status()}
    skills = statussen["skills"]
    assert skills.automatisch is True
    assert skills.details["upgrades"] == ["25180"]
    assert "1" in skills.signaal


def test_kd_status_meldt_dekkingsgaten(gemockte_bronnen):
    kd = {s.bron: s for s in bron_updates.verzamel_bron_status()}["kd"]
    assert kd.details["ontbrekende_dekking"] == ["23110"]  # 25180 heeft .md, 23110 niet
    assert kd.automatisch is False  # bundel-versheid niet geautomatiseerd


def test_oer_status_is_handmatig(gemockte_bronnen):
    oer = {s.bron: s for s in bron_updates.verzamel_bron_status()}["oer"]
    assert oer.automatisch is False
    assert "davinci" in oer.details["niet_crawlbaar"]
    assert "rijn_ijssel" in oer.details["crawlbaar"]


def test_kd_status_meldt_ontbrekende_map(tmp_path, monkeypatch):
    afwezig = tmp_path / "bestaat-niet"  # niet aangemaakt
    monkeypatch.setattr(sync_afgeleid, "kd_dir", lambda: afwezig)
    monkeypatch.setattr(sync_afgeleid, "geindexeerde_crebos", lambda: {"25180"})
    kd = bron_updates._kd_status()
    assert kd.details["ontbrekende_dekking"] == []  # geen valse "alles ontbreekt"
    assert "niet gevonden" in kd.signaal


def test_rapporteer_bevat_alle_bronnen(gemockte_bronnen):
    tekst = bron_updates.rapporteer(bron_updates.verzamel_bron_status())
    for bron in ("skills", "kd", "oer"):
        assert bron in tekst


def test_oer_lijsten_dekken_alle_instellingen():
    """De OER-crawlbaarheidslijsten moeten synchroon blijven met ingest._INSTELLINGEN
    (vierde hardcoded instellingslijst — drift = stille status-degradatie)."""
    from validatie_samenwijzer import ingest

    ingest_namen = set(ingest._INSTELLINGEN.keys())
    gedekt = set(bron_updates._OER_CRAWLBAAR) | set(bron_updates._OER_NIET_CRAWLBAAR)
    assert gedekt == ingest_namen, f"Niet gedekt: {ingest_namen - gedekt}"
