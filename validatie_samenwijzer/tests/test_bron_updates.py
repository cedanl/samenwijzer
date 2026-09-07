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
    # KD-bundel: standaard in sync (crebolijst 2025)
    monkeypatch.setattr(
        bron_updates.kd_bundel,
        "bundel_status",
        lambda: {"toestand": "in_sync", "crebolijst_jaar": 2025, "gewijzigde_zips": []},
    )
    return tmp_path


def test_skills_status_meldt_upgrades(gemockte_bronnen):
    statussen = {s.bron: s for s in bron_updates.verzamel_bron_status()}
    skills = statussen["skills"]
    assert skills.automatisch is True
    assert skills.details["upgrades"] == ["25180"]
    assert "1" in skills.signaal


def test_kd_status_in_sync_meldt_jaar_en_gaten(gemockte_bronnen):
    kd = {s.bron: s for s in bron_updates.verzamel_bron_status()}["kd"]
    assert kd.automatisch is True  # bundelwijziging wordt nu automatisch gedetecteerd
    assert kd.details["crebolijst_jaar"] == 2025
    assert kd.details["ontbrekende_dekking"] == ["23110"]  # 25180 heeft .md, 23110 niet
    assert "2025" in kd.signaal


def test_kd_status_gewijzigd_vraagt_reingest(gemockte_bronnen, monkeypatch):
    monkeypatch.setattr(
        bron_updates.kd_bundel,
        "bundel_status",
        lambda: {"toestand": "gewijzigd", "crebolijst_jaar": 2025, "gewijzigde_zips": ["ae.zip"]},
    )
    kd = {s.bron: s for s in bron_updates.verzamel_bron_status()}["kd"]
    assert "gewijzigd" in kd.signaal
    assert kd.details["gewijzigde_zips"] == ["ae.zip"]


def test_oer_status_is_handmatig(gemockte_bronnen):
    oer = {s.bron: s for s in bron_updates.verzamel_bron_status()}["oer"]
    assert oer.automatisch is False
    assert "davinci" in oer.details["niet_crawlbaar"]
    assert "rijn_ijssel" in oer.details["crawlbaar"]


def test_oer_status_offline_hint_naar_oer_flag(gemockte_bronnen):
    oer = {s.bron: s for s in bron_updates.verzamel_bron_status()}["oer"]
    assert oer.automatisch is False
    assert "--oer" in oer.signaal  # offline: verwijs naar de online-modus


class _DummyConn:
    def close(self):
        pass


def test_oer_status_online_aggregeert_nieuwe_oers(monkeypatch):
    from validatie_samenwijzer.oer_catalogus import CatalogusItem

    monkeypatch.setattr(bron_updates.oer_catalogus, "open_conn", lambda: _DummyConn())
    monkeypatch.setattr(
        bron_updates.oer_catalogus,
        "_CATALOGUS_BRONNEN",
        {"deltion": lambda: []},  # alleen de sleutels tellen voor "welke adapters"
    )
    monkeypatch.setattr(
        bron_updates.oer_catalogus,
        "instelling_nieuwe_oers",
        lambda inst, conn=None, manifest=False: [
            CatalogusItem("25180", "BOL", "2026", "Kok", "deltion")
        ],
    )
    oer = bron_updates._oer_status(online=True)
    assert oer.automatisch is True
    assert "1" in oer.signaal and "deltion" in oer.signaal
    assert oer.details["nieuw_per_instelling"]["deltion"] == [("25180", "BOL", "2026")]


def test_oer_status_online_degradeert_bij_onbereikbare_api(monkeypatch):
    monkeypatch.setattr(bron_updates.oer_catalogus, "open_conn", lambda: _DummyConn())
    monkeypatch.setattr(bron_updates.oer_catalogus, "_CATALOGUS_BRONNEN", {"deltion": lambda: []})

    def _faalt(inst, conn=None, manifest=False):
        raise bron_updates.oer_catalogus.CatalogusOnbereikbaarError(f"{inst}: timeout")

    monkeypatch.setattr(bron_updates.oer_catalogus, "instelling_nieuwe_oers", _faalt)
    oer = bron_updates._oer_status(online=True)  # mag NIET crashen
    assert oer.details["onbereikbaar"] == ["deltion"]
    assert "onbereikbaar" in oer.signaal


def test_kd_status_ontbrekende_map_meldt_onbekend(gemockte_bronnen, monkeypatch):
    afwezig = gemockte_bronnen / "bestaat-niet"  # niet aangemaakt
    monkeypatch.setattr(sync_afgeleid, "kd_dir", lambda: afwezig)
    kd = bron_updates._kd_status()
    # Map mist → dekking is ONBEKEND, niet "0 zonder dekking" (geen valse volle dekking).
    assert kd.details["dekking_onbekend"] is True
    assert kd.details["ontbrekende_dekking"] == []
    assert "onbekend" in kd.signaal


def test_kd_status_aanwezige_map_dekking_bekend(gemockte_bronnen):
    kd = {s.bron: s for s in bron_updates.verzamel_bron_status()}["kd"]
    assert kd.details["dekking_onbekend"] is False  # map bestaat → dekking wél bekend


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


def test_oer_inhoud_status_aggregeert_gewijzigde_oers(monkeypatch):
    from validatie_samenwijzer.oer_catalogus import CatalogusItem

    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(bron_updates.oer_catalogus, "open_conn", lambda: _Conn())
    monkeypatch.setattr(bron_updates.oer_catalogus, "_CATALOGUS_BRONNEN", {"deltion": lambda: []})

    def _fake_gewijzigd(inst, conn=None):
        return ([CatalogusItem("25180", "BOL", "2025", "Kok", "deltion", "u")], 2)

    monkeypatch.setattr(bron_updates.oer_catalogus, "gewijzigde_oers", _fake_gewijzigd)

    status = bron_updates._oer_inhoud_status()
    assert status.bron == "oer-inhoud"
    assert status.automatisch is True
    assert "1" in status.signaal and "deltion" in status.signaal
    assert status.details["gewijzigd_per_instelling"]["deltion"] == [("25180", "BOL", "2025")]
    assert status.details["zonder_baseline"] == 2


def test_verzamel_bron_status_alleen_oer(monkeypatch):
    monkeypatch.setattr(bron_updates.oer_catalogus, "_CATALOGUS_BRONNEN", {"deltion": lambda: []})
    monkeypatch.setattr(
        bron_updates.oer_catalogus,
        "instelling_nieuwe_oers",
        lambda inst, conn=None, manifest=False: [],
    )
    statussen = bron_updates.verzamel_bron_status(online=True, manifest=True, alleen_oer=True)
    assert [s.bron for s in statussen] == ["oer"]  # geen skills/kd


def test_verzamel_bron_status_voegt_inhoud_toe_met_flag(monkeypatch, gemockte_bronnen):
    bronnen = {s.bron for s in bron_updates.verzamel_bron_status(inhoud=False)}
    assert "oer-inhoud" not in bronnen  # standaard niet
    monkeypatch.setattr(bron_updates.oer_catalogus, "_CATALOGUS_BRONNEN", {"deltion": lambda: []})
    dummy_conn_cls = type("C", (), {"close": lambda s: None})
    monkeypatch.setattr(bron_updates.oer_catalogus, "open_conn", lambda: dummy_conn_cls())
    monkeypatch.setattr(bron_updates.oer_catalogus, "gewijzigde_oers", lambda i, conn=None: ([], 0))
    bronnen2 = {s.bron for s in bron_updates.verzamel_bron_status(inhoud=True)}
    assert "oer-inhoud" in bronnen2
