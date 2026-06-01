"""Tests voor de CompetentNL-skills-bron. Geen netwerk: de SPARQL-call is gemockt."""

from validatie_samenwijzer import competentnl_bron


def _binding(label=None, definitie=None, rel=None, skill=None, skill_label=None):
    b = {}
    if label is not None:
        b["label"] = {"value": label}
    if definitie is not None:
        b["def"] = {"value": definitie}
    if rel is not None:
        b["rel"] = {"value": f"https://linkeddata.competentnl.nl/def/competentnl#{rel}"}
    if skill is not None:
        b["skill"] = {"value": skill}
    if skill_label is not None:
        b["skillLabel"] = {"value": skill_label}
    return b


def _resultaat(bindings):
    return {"results": {"bindings": bindings}}


def test_haal_skills_record_parseert_en_categoriseert(monkeypatch):
    bindings = [
        _binding(
            label="Kok",
            definitie="Een kok bereidt maaltijden.",
            rel="prescribesHATEssential",
            skill="uri:s1",
            skill_label="Samenwerken",
        ),
        _binding(rel="prescribesHATEssential", skill="uri:s2", skill_label="Plannen"),
        _binding(rel="prescribesHATImportant", skill="uri:s3", skill_label="Engels spreken"),
    ]
    monkeypatch.setattr(competentnl_bron, "_sparql", lambda q: _resultaat(bindings))
    r = competentnl_bron.haal_skills_record("25180", "OER Kok")
    assert r is not None
    assert r.bron == "CompetentNL"
    assert r.match_methode == "crebo-direct"
    assert r.beroep.label == "Kok"
    assert r.beroep.definitie == "Een kok bereidt maaltijden."
    cats = {s.label: s.categorie for s in r.skills}
    assert cats == {
        "Samenwerken": "essentieel",
        "Plannen": "essentieel",
        "Engels spreken": "belangrijk",
    }


def test_haal_skills_record_dedupt_op_uri(monkeypatch):
    bindings = [
        _binding(
            label="Kok", rel="prescribesHATEssential", skill="uri:s1", skill_label="Samenwerken"
        ),
        _binding(
            label="Kok", rel="prescribesHATEssential", skill="uri:s1", skill_label="Samenwerken"
        ),
    ]
    monkeypatch.setattr(competentnl_bron, "_sparql", lambda q: _resultaat(bindings))
    r = competentnl_bron.haal_skills_record("25180", "OER Kok")
    assert len(r.skills) == 1


def test_haal_skills_record_none_zonder_key_of_fout(monkeypatch):
    monkeypatch.setattr(competentnl_bron, "_sparql", lambda q: None)
    assert competentnl_bron.haal_skills_record("25180", "OER Kok") is None


def test_haal_skills_record_none_bij_lege_bindings(monkeypatch):
    monkeypatch.setattr(competentnl_bron, "_sparql", lambda q: _resultaat([]))
    assert competentnl_bron.haal_skills_record("99999", "Onbekend") is None


def test_haal_skills_record_none_zonder_label(monkeypatch):
    """EducationalNorm-binding zonder bruikbare prefLabel → None (val terug op ESCO)."""
    bindings = [_binding(rel="prescribesHATEssential", skill="uri:s1", skill_label="Iets")]
    monkeypatch.setattr(competentnl_bron, "_sparql", lambda q: _resultaat(bindings))
    assert competentnl_bron.haal_skills_record("25180", "OER Kok") is None


def test_sparql_none_zonder_api_key(monkeypatch):
    monkeypatch.delenv("COMPETENTNL_API_KEY", raising=False)
    assert competentnl_bron._sparql("SELECT * WHERE { ?s ?p ?o }") is None
