"""Tests voor de reconciliatie-motor. Geen subprocess/netwerk: build-stappen gemockt."""

import pytest

from validatie_samenwijzer import sync_afgeleid


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    kd = tmp_path / "kd"
    sk = tmp_path / "skills"
    kd.mkdir()
    sk.mkdir()
    monkeypatch.setattr(sync_afgeleid, "_KD_DIR", kd)
    monkeypatch.setattr(sync_afgeleid, "_SKILLS_DIR", sk)
    return kd, sk


def test_vereist_crebo_of_alles():
    with pytest.raises(ValueError):
        sync_afgeleid.werk_afgeleide_bronnen_bij()


def test_rapporteert_nieuwe_artefacten(dirs, monkeypatch):
    kd, sk = dirs
    monkeypatch.setattr(
        sync_afgeleid, "_bouw_kd", lambda crebo: (kd / f"{crebo}.md").write_text("x")
    )
    monkeypatch.setattr(
        sync_afgeleid, "_bouw_skills", lambda crebo, force: (sk / f"{crebo}.json").write_text("{}")
    )
    s = sync_afgeleid.werk_afgeleide_bronnen_bij(crebo="25180")
    assert s.nieuwe_kd == ["25180"]
    assert s.nieuwe_skills == ["25180"]
    assert s.kd_gaten == []
    assert s.iets_veranderd


def test_kd_gat_gerapporteerd(dirs, monkeypatch):
    kd, sk = dirs
    monkeypatch.setattr(sync_afgeleid, "_bouw_kd", lambda crebo: None)  # geen md → gat
    monkeypatch.setattr(
        sync_afgeleid, "_bouw_skills", lambda crebo, force: (sk / f"{crebo}.json").write_text("{}")
    )
    s = sync_afgeleid.werk_afgeleide_bronnen_bij(crebo="26027")
    assert s.kd_gaten == ["26027"]
    assert s.nieuwe_kd == []
    assert s.nieuwe_skills == ["26027"]


def test_idempotent_skipt_bestaande_kd(dirs, monkeypatch):
    kd, sk = dirs
    (kd / "25180.md").write_text("bestaat al")
    aangeroepen = []
    monkeypatch.setattr(sync_afgeleid, "_bouw_kd", lambda crebo: aangeroepen.append(crebo))
    monkeypatch.setattr(sync_afgeleid, "_bouw_skills", lambda crebo, force: None)
    s = sync_afgeleid.werk_afgeleide_bronnen_bij(crebo="25180")
    assert aangeroepen == []  # KD bestond → _bouw_kd niet aangeroepen
    assert s.nieuwe_kd == []
    assert not s.iets_veranderd


def test_force_herbouwt_bestaande_kd(dirs, monkeypatch):
    kd, sk = dirs
    (kd / "25180.md").write_text("oud")
    aangeroepen = []
    monkeypatch.setattr(sync_afgeleid, "_bouw_kd", lambda crebo: aangeroepen.append(crebo))
    monkeypatch.setattr(sync_afgeleid, "_bouw_skills", lambda crebo, force: None)
    sync_afgeleid.werk_afgeleide_bronnen_bij(crebo="25180", force=True)
    assert aangeroepen == ["25180"]  # force → toch aangeroepen


def test_alles_dispatch_en_gaten(dirs, monkeypatch):
    kd, sk = dirs
    monkeypatch.setattr(sync_afgeleid, "geindexeerde_crebos", lambda: {"A", "B"})

    def fake_kd(crebo):
        assert crebo is None  # alles → batch
        (kd / "A.md").write_text("x")  # A gebouwd, B blijft een gat

    def fake_skills(crebo, force):
        assert crebo is None
        (sk / "A.json").write_text("{}")
        (sk / "B.json").write_text("{}")

    monkeypatch.setattr(sync_afgeleid, "_bouw_kd", fake_kd)
    monkeypatch.setattr(sync_afgeleid, "_bouw_skills", fake_skills)
    s = sync_afgeleid.werk_afgeleide_bronnen_bij(alles=True)
    assert s.nieuwe_kd == ["A"]
    assert s.kd_gaten == ["B"]
    assert set(s.nieuwe_skills) == {"A", "B"}


def test_skills_gat_gerapporteerd(dirs, monkeypatch):
    """Een artefact met beroep=null telt als skills-gat (zichtbaar, niet stil 'compleet')."""
    kd, sk = dirs
    (sk / "26027.json").write_text('{"crebo": "26027", "beroep": null, "skills": []}')
    monkeypatch.setattr(sync_afgeleid, "_bouw_kd", lambda crebo: None)
    monkeypatch.setattr(sync_afgeleid, "_bouw_skills", lambda crebo, force: None)
    s = sync_afgeleid.werk_afgeleide_bronnen_bij(crebo="26027")
    assert s.skills_gaten == ["26027"]
    assert s.nieuwe_skills == []  # bestond al → geen nieuwe


def test_samenvatting_niets_veranderd():
    assert not sync_afgeleid.Samenvatting().iets_veranderd
    assert sync_afgeleid.Samenvatting(nieuwe_skills=["X"]).iets_veranderd
