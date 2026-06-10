"""Tests voor refresh_fallbacks(): her-check non-CompetentNL artefacten tegen CompetentNL.

Geen netwerk: competentnl_bron.haal_skills_record wordt gemockt.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import build_skills_taxonomie as bst  # noqa: E402

from validatie_samenwijzer.skills_bron import Beroep, Skill, SkillsRecord  # noqa: E402


def _esco_json(crebo: str) -> str:
    return json.dumps(
        {
            "crebo": crebo,
            "opleiding": f"{crebo}_BOL_2025__OER",
            "bron": "ESCO",
            "beroep": {"label": "vakdocent", "uri": "esco:1", "definitie": "..."},
            "match_methode": "llm-keuze",
            "kandidaten": ["vakdocent"],
            "skills": [{"label": "lesgeven", "uri": "esco:s1", "categorie": "essentieel"}],
        },
        ensure_ascii=False,
        indent=2,
    )


def _competentnl_json(crebo: str) -> str:
    return json.dumps(
        {
            "crebo": crebo,
            "opleiding": f"{crebo}_BOL_2025__OER",
            "bron": "CompetentNL",
            "beroep": {"label": "Kok", "uri": "", "definitie": "..."},
            "match_methode": "crebo-direct",
            "kandidaten": [],
            "skills": [{"label": "koken", "uri": "cnl:s1", "categorie": "essentieel"}],
        },
        ensure_ascii=False,
        indent=2,
    )


@pytest.fixture
def skills_dir(tmp_path, monkeypatch):
    d = tmp_path / "skills"
    d.mkdir()
    monkeypatch.setattr(bst, "_SKILLS_DIR", d)
    monkeypatch.setenv("COMPETENTNL_API_KEY", "test-key")
    return d


def test_upgrade_bij_competentnl_hit(skills_dir, monkeypatch):
    (skills_dir / "25180.json").write_text(_esco_json("25180"), encoding="utf-8")

    def fake(crebo, opleiding):
        return SkillsRecord(
            crebo=crebo,
            opleiding=opleiding,
            bron="CompetentNL",
            beroep=Beroep(label="Kok", uri="", definitie="..."),
            skills=[Skill(label="koken", uri="cnl:s1", categorie="essentieel")],
            match_methode="crebo-direct",
            kandidaten=[],
        )

    monkeypatch.setattr(bst.competentnl_bron, "haal_skills_record", fake)

    upgraded, nog_fallback = bst.refresh_fallbacks()

    assert upgraded == ["25180"]
    assert nog_fallback == []
    data = json.loads((skills_dir / "25180.json").read_text(encoding="utf-8"))
    assert data["bron"] == "CompetentNL"
    assert data["match_methode"] == "crebo-direct"
    csv = skills_dir / "_match_overzicht.csv"
    assert csv.exists()
    assert "CompetentNL" in csv.read_text(encoding="utf-8")  # CSV bevat de nieuwe bron


def test_miss_laat_esco_ongemoeid(skills_dir, monkeypatch):
    pad = skills_dir / "23110.json"
    origineel = _esco_json("23110")
    pad.write_text(origineel, encoding="utf-8")
    monkeypatch.setattr(bst.competentnl_bron, "haal_skills_record", lambda c, o: None)

    upgraded, nog_fallback = bst.refresh_fallbacks()

    assert upgraded == []
    assert nog_fallback == ["23110"]
    assert pad.read_text(encoding="utf-8") == origineel  # byte-identiek


def test_geen_api_key_geen_crash_met_waarschuwing(skills_dir, monkeypatch, caplog):
    monkeypatch.delenv("COMPETENTNL_API_KEY", raising=False)
    (skills_dir / "25180.json").write_text(_esco_json("25180"), encoding="utf-8")
    aangeroepen = []
    monkeypatch.setattr(
        bst.competentnl_bron, "haal_skills_record", lambda c, o: aangeroepen.append(c)
    )

    with caplog.at_level("WARNING"):
        upgraded, nog_fallback = bst.refresh_fallbacks()

    assert upgraded == []
    assert nog_fallback == []  # early-return: geen artefacten verwerkt
    assert aangeroepen == []  # zonder key nooit CompetentNL bevragen
    assert "COMPETENTNL_API_KEY" in caplog.text


def test_artefact_zonder_crebo_overgeslagen(skills_dir, monkeypatch, caplog):
    # Valide json maar ontbrekende verplichte sleutel → warn + skip, geen crash.
    (skills_dir / "kapot.json").write_text(
        json.dumps({"bron": "ESCO", "skills": []}), encoding="utf-8"
    )
    (skills_dir / "25180.json").write_text(_esco_json("25180"), encoding="utf-8")
    monkeypatch.setattr(bst.competentnl_bron, "haal_skills_record", lambda c, o: None)

    with caplog.at_level("WARNING"):
        upgraded, nog_fallback = bst.refresh_fallbacks()

    assert upgraded == []
    assert nog_fallback == ["25180"]  # het valide artefact wel verwerkt
    assert "Onleesbaar skills-artefact" in caplog.text


def test_competentnl_artefact_overgeslagen(skills_dir, monkeypatch):
    (skills_dir / "25234.json").write_text(_competentnl_json("25234"), encoding="utf-8")
    aangeroepen = []
    monkeypatch.setattr(
        bst.competentnl_bron, "haal_skills_record", lambda c, o: aangeroepen.append(c)
    )

    upgraded, nog_fallback = bst.refresh_fallbacks()

    assert aangeroepen == []  # CompetentNL-artefact nooit opnieuw bevraagd
    assert upgraded == []
    assert nog_fallback == []
