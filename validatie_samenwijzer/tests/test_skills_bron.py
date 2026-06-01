"""Tests voor de skills-taxonomie-bron (ESCO). Geen netwerk: ESCO/LLM zijn gemockt."""

from validatie_samenwijzer import skills_bron
from validatie_samenwijzer.skills_bron import Beroep, Skill, schoon_opleidingsnaam


def test_schoon_opleidingsnaam_strip_crebo_jaar_oer():
    assert schoon_opleidingsnaam("2021 - 25180 OER Kok (V1)") == "Kok"


def test_schoon_opleidingsnaam_strip_bestandsnaam_ruis():
    schoon = schoon_opleidingsnaam("25690_BOL_2025__25690 Beveiliger 2 24 maanden BOL ALK_PUR_")
    assert "Beveiliger" in schoon
    for ruis in ("25690", "BOL", "2025", "maanden", "OER"):
        assert ruis not in schoon


def test_schoon_opleidingsnaam_behoudt_meerwoordsberoep():
    schoon = schoon_opleidingsnaam("27015_BOL_2025__OER (OUD) - 27015O - ICT support technician")
    assert "ICT" in schoon and "support" in schoon
    assert "OUD" not in schoon


def test_record_to_dict_vorm():
    record = skills_bron.SkillsRecord(
        crebo="25180",
        opleiding="OER Kok",
        bron="ESCO",
        beroep=Beroep(label="kok", uri="uri:kok", definitie="Koks bereiden..."),
        skills=[Skill(label="kooktechnieken gebruiken", uri="uri:s1", categorie="essentieel")],
        match_methode="llm-keuze",
        kandidaten=["kok", "chefkok"],
    )
    d = record.to_dict()
    assert d["crebo"] == "25180"
    assert d["beroep"]["label"] == "kok"
    assert d["skills"][0]["categorie"] == "essentieel"
    assert d["kandidaten"] == ["kok", "chefkok"]


def test_bouw_skills_record_happy_path(monkeypatch):
    monkeypatch.setattr(
        skills_bron, "zoek_esco_beroepen", lambda term, limit=8: [Beroep("kok", "uri:kok")]
    )
    monkeypatch.setattr(skills_bron, "_kies_met_llm", lambda *a, **k: (0, "llm-keuze"))
    monkeypatch.setattr(
        skills_bron,
        "haal_esco_beroep_details",
        lambda uri: ("Koks bereiden maaltijden.", [Skill("kooktechnieken", "uri:s", "essentieel")]),
    )
    record = skills_bron.bouw_skills_record("25180", "OER Kok", "Keuken", client=object())
    assert record.beroep is not None
    assert record.beroep.label == "kok"
    assert record.beroep.definitie == "Koks bereiden maaltijden."
    assert record.skills[0].categorie == "essentieel"
    assert record.match_methode == "llm-keuze"


def test_bouw_skills_record_geen_kandidaten(monkeypatch):
    monkeypatch.setattr(skills_bron, "zoek_esco_beroepen", lambda term, limit=8: [])
    record = skills_bron.bouw_skills_record("99999", "Onbekend", "", client=object())
    assert record.beroep is None
    assert record.match_methode == "geen-kandidaten"
    assert record.to_dict()["beroep"] is None


def test_bouw_skills_record_llm_zegt_geen(monkeypatch):
    """Brede instroomopleiding: LLM kiest GEEN → geen beroep, geen verzonnen match."""
    monkeypatch.setattr(
        skills_bron, "zoek_esco_beroepen", lambda term, limit=8: [Beroep("laserlasser", "uri:x")]
    )
    monkeypatch.setattr(skills_bron, "_kies_met_llm", lambda *a, **k: (None, "geen-match"))
    record = skills_bron.bouw_skills_record("25250", "Entree", "Entree", client=object())
    assert record.beroep is None
    assert record.match_methode == "geen-match"
    assert record.kandidaten == ["laserlasser"]
