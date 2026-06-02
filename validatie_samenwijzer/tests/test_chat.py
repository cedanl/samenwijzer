import json

from validatie_samenwijzer.chat import (
    LAGE_RELEVANTIE_BERICHT,
    bouw_berichten,
    bouw_gecombineerd_systeem,
    bouw_systeem,
    identificeer_oer_kandidaten,
    laad_instelling_bron_tekst,
    laad_kwalificatiedossier_tekst,
    laad_skills_tekst,
    pad_kwalificatiedossier,
    pad_skills,
)


def test_bouw_berichten_nieuwe_vraag():
    berichten = bouw_berichten([], "Hoeveel uren BPV?")
    assert berichten[0]["role"] == "user"
    assert berichten[0]["content"] == "Hoeveel uren BPV?"


def test_bouw_berichten_behoudt_history():
    history = [
        {"role": "user", "content": "Vraag 1"},
        {"role": "assistant", "content": "Antwoord 1"},
    ]
    berichten = bouw_berichten(history, "Vraag 2")
    rollen = [b["role"] for b in berichten]
    assert rollen == ["user", "assistant", "user"]
    assert berichten[-1]["content"] == "Vraag 2"


def test_bouw_systeem_bevat_oer_tekst():
    systeem = bouw_systeem("Dit is de OER-tekst.", "Verzorgende IG", "Rijn IJssel")
    assert "Verzorgende IG" in systeem
    assert "Rijn IJssel" in systeem
    assert "Dit is de OER-tekst." in systeem


def test_bouw_systeem_leeg_bij_geen_tekst():
    systeem = bouw_systeem("", "Kok", "Da Vinci")
    # Lege oer_tekst → systeem mag worden aangemaakt maar is inhoudsloos
    assert "Kok" in systeem


def test_lage_relevantie_bericht_is_string():
    assert isinstance(LAGE_RELEVANTIE_BERICHT, str)
    assert len(LAGE_RELEVANTIE_BERICHT) > 10


# ── bouw_gecombineerd_systeem ─────────────────────────────────────────────────


def _oer_item(**overrides):
    base = {
        "tekst": "OER-inhoud",
        "opleiding": "Verzorgende IG",
        "display_naam": "Rijn IJssel",
        "leerweg": "BOL",
        "cohort": "2025",
    }
    return {**base, **overrides}


def test_bouw_gecombineerd_systeem_enkel_delegeert_naar_bouw_systeem():
    item = _oer_item(tekst="Tekst A", opleiding="Kok", display_naam="Da Vinci")
    systeem = bouw_gecombineerd_systeem([item])
    assert systeem == bouw_systeem("Tekst A", "Kok", "Da Vinci")


def test_bouw_gecombineerd_systeem_meervoudig_bevat_alle_oers():
    items = [
        _oer_item(tekst="Tekst A", opleiding="Kok", display_naam="Da Vinci"),
        _oer_item(tekst="Tekst B", opleiding="Verzorgende IG", display_naam="Rijn IJssel"),
    ]
    systeem = bouw_gecombineerd_systeem(items)
    assert "OER 1" in systeem and "OER 2" in systeem
    assert "Tekst A" in systeem and "Tekst B" in systeem
    assert "Da Vinci" in systeem and "Rijn IJssel" in systeem
    assert "Kok" in systeem and "Verzorgende IG" in systeem


# ── identificeer_oer_kandidaten ───────────────────────────────────────────────


def _oer_row(**overrides):
    base = {
        "id": 1,
        "opleiding": "Verzorgende IG",
        "display_naam": "Rijn IJssel",
        "leerweg": "BOL",
        "cohort": "2025",
        "crebo": "25655",
        "bestandspad": "oeren/x.pdf",
    }
    return {**base, **overrides}


def test_identificeer_crebo_geeft_hoogste_score():
    oers = [
        _oer_row(id=1, crebo="25655"),
        _oer_row(id=2, crebo="25170"),
    ]
    resultaat = identificeer_oer_kandidaten(oers, "Ik zoek info over crebo 25655")
    assert resultaat[0]["id"] == 1
    assert resultaat[0]["_score"] >= 3


def test_identificeer_leerweg_en_cohort_tellen_mee():
    oers = [_oer_row(leerweg="BOL", cohort="2025")]
    resultaat = identificeer_oer_kandidaten(oers, "BOL 2025 informatie graag")
    # leerweg (+2) + cohort (+2) = 4
    assert resultaat[0]["_score"] >= 4


def test_identificeer_leerweg_case_insensitive():
    oers = [_oer_row(leerweg="BBL")]
    resultaat = identificeer_oer_kandidaten(oers, "ik volg de bbl-route")
    assert resultaat[0]["_score"] >= 2


# ── kwalificatiedossier ───────────────────────────────────────────────────────


def test_bouw_systeem_met_dossier_bevat_beide_bronnen():
    systeem = bouw_systeem(
        "OER-tekst hier.",
        "Kok",
        "Da Vinci",
        dossier_tekst="Kerntaak 1: bereid maaltijden.",
        crebo="25180",
    )
    assert "OER-tekst hier." in systeem
    assert "Kerntaak 1: bereid maaltijden." in systeem
    assert "KWALIFICATIEDOSSIER" in systeem
    assert "25180" in systeem


def test_bouw_systeem_zonder_dossier_heeft_geen_kd_blok():
    systeem = bouw_systeem("OER-tekst", "Kok", "Da Vinci")
    assert "KWALIFICATIEDOSSIER" not in systeem


def test_bouw_systeem_met_instelling_bron_bevat_blok():
    systeem = bouw_systeem(
        "OER-tekst",
        "ICT",
        "Rijn IJssel",
        instelling_bronnen=[("Examenreglement", "Artikel 6.3: één herkansing.")],
    )
    assert "=== EXAMENREGLEMENT (Rijn IJssel) ===" in systeem
    assert "Artikel 6.3: één herkansing." in systeem


def test_bouw_systeem_instelling_citatie_onderscheidt_van_oer():
    """De citatie-instructie moet de regeling als aparte bron behandelen, niet als de OER."""
    systeem = bouw_systeem("OER-tekst", "ICT", "Rijn IJssel")
    assert "Volgens het Examenreglement" in systeem
    assert 'citeer een regeling NOOIT als "de OER"' in systeem


def test_bouw_systeem_zonder_instelling_bron_geen_blok():
    systeem = bouw_systeem("OER-tekst", "Kok", "Da Vinci")
    assert "=== EXAMENREGLEMENT" not in systeem
    assert "=== BEGELEIDINGS" not in systeem


def test_bouw_systeem_lege_instelling_bron_tekst_geen_blok():
    systeem = bouw_systeem("OER-tekst", "Kok", "Da Vinci", instelling_bronnen=[("Examenreglement", "")])
    assert "=== EXAMENREGLEMENT" not in systeem


def test_bouw_systeem_meerdere_instelling_bronnen():
    systeem = bouw_systeem(
        "OER-tekst",
        "ICT",
        "Rijn IJssel",
        instelling_bronnen=[
            ("Examenreglement", "reglement-tekst"),
            ("Begeleidings- en welzijnsbeleid", "beleid-tekst"),
        ],
    )
    assert "=== EXAMENREGLEMENT (Rijn IJssel) ===" in systeem
    assert "=== BEGELEIDINGS- EN WELZIJNSBELEID (Rijn IJssel) ===" in systeem
    assert "reglement-tekst" in systeem
    assert "beleid-tekst" in systeem


def test_bouw_gecombineerd_systeem_includeert_instelling_bron_per_oer():
    items = [
        {
            "tekst": "OER A",
            "opleiding": "ICT",
            "display_naam": "Rijn IJssel",
            "leerweg": "BOL",
            "cohort": "2025",
            "instelling_bronnen": [("Examenreglement", "reglement A")],
        },
        {
            "tekst": "OER B",
            "opleiding": "Kok",
            "display_naam": "Da Vinci",
            "leerweg": "BBL",
            "cohort": "2025",
        },
    ]
    systeem = bouw_gecombineerd_systeem(items)
    assert "EXAMENREGLEMENT 1 (Rijn IJssel)" in systeem
    assert "reglement A" in systeem


def test_laad_instelling_bron_leeg_zonder_pad():
    assert laad_instelling_bron_tekst(None) == ""
    assert laad_instelling_bron_tekst("") == ""


def test_laad_instelling_bron_leest_bestaande_md(tmp_path):
    md = tmp_path / "examenreglement.md"
    md.write_text("Artikel 6.3 Herkansingen: ten hoogste één herkansing.", encoding="utf-8")
    assert "Herkansingen" in laad_instelling_bron_tekst(md)
    assert "Herkansingen" in laad_instelling_bron_tekst(str(md))


def test_laad_instelling_bron_leeg_bij_ontbrekend_bestand(tmp_path):
    assert laad_instelling_bron_tekst(tmp_path / "bestaat_niet.pdf") == ""


def test_laad_instelling_bron_cap(tmp_path, monkeypatch):
    import validatie_samenwijzer.chat as chat_mod

    monkeypatch.setattr(chat_mod, "_MAX_INSTELLING_TEKST_TEKENS", 10)
    md = tmp_path / "begeleidingsbeleid.md"
    md.write_text("x" * 100, encoding="utf-8")
    assert len(laad_instelling_bron_tekst(md)) == 10


def test_laad_kwalificatiedossier_leeg_zonder_crebo():
    assert laad_kwalificatiedossier_tekst(None) == ""
    assert laad_kwalificatiedossier_tekst("") == ""


def test_laad_kwalificatiedossier_leest_bestaande_md(tmp_path, monkeypatch):
    monkeypatch.setenv("KWALDOSSIERS_PAD", str(tmp_path))
    (tmp_path / "12345.md").write_text("Dossier-inhoud voor crebo 12345.")
    assert "Dossier-inhoud" in laad_kwalificatiedossier_tekst("12345")


def test_pad_kwalificatiedossier_respecteert_env(tmp_path, monkeypatch):
    monkeypatch.setenv("KWALDOSSIERS_PAD", str(tmp_path))
    assert pad_kwalificatiedossier("99999") == tmp_path / "99999.md"


def test_bouw_gecombineerd_systeem_includeert_dossier_per_oer():
    items = [
        {
            "tekst": "OER A",
            "opleiding": "Kok",
            "display_naam": "Da Vinci",
            "leerweg": "BOL",
            "cohort": "2025",
            "crebo": "25180",
            "dossier_tekst": "KD-tekst voor Kok.",
        },
        {
            "tekst": "OER B",
            "opleiding": "Verzorgende IG",
            "display_naam": "Rijn IJssel",
            "leerweg": "BOL",
            "cohort": "2025",
        },
    ]
    systeem = bouw_gecombineerd_systeem(items)
    assert "KD-tekst voor Kok." in systeem
    assert "KWALIFICATIEDOSSIER 1" in systeem
    assert "25180" in systeem
    # tweede OER heeft geen dossier — geen KD 2 blok
    assert "KWALIFICATIEDOSSIER 2" not in systeem


# ── skills-taxonomie ──────────────────────────────────────────────────────────


def _schrijf_skills(tmp_path, crebo, beroep="kok", skills=None):
    data = {
        "crebo": crebo,
        "opleiding": "OER Kok",
        "bron": "ESCO",
        "beroep": None if beroep is None else {"label": beroep, "uri": "u", "definitie": "Koks..."},
        "match_methode": "llm-keuze",
        "kandidaten": [],
        "skills": skills
        if skills is not None
        else [{"label": "kooktechnieken gebruiken", "uri": "u1", "categorie": "essentieel"}],
    }
    (tmp_path / f"{crebo}.json").write_text(json.dumps(data), encoding="utf-8")


def test_pad_skills_respecteert_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLS_PAD", str(tmp_path))
    assert pad_skills("25180") == tmp_path / "25180.json"


def test_laad_skills_leeg_zonder_crebo():
    assert laad_skills_tekst(None) == ""
    assert laad_skills_tekst("") == ""


def test_laad_skills_formatteert_blok(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLS_PAD", str(tmp_path))
    _schrijf_skills(tmp_path, "25180")
    blok = laad_skills_tekst("25180")
    assert "SKILLS-TAXONOMIE (ESCO)" in blok
    assert "kok" in blok
    assert "kooktechnieken gebruiken" in blok
    assert "Essentiële skills" in blok


def test_laad_skills_toont_belangrijk_categorie(tmp_path, monkeypatch):
    """CompetentNL-bron levert een 'belangrijk'-categorie naast essentieel."""
    monkeypatch.setenv("SKILLS_PAD", str(tmp_path))
    skills = [
        {"label": "Samenwerken", "uri": "u1", "categorie": "essentieel"},
        {"label": "Engels spreken", "uri": "u2", "categorie": "belangrijk"},
    ]
    _schrijf_skills(tmp_path, "25180", beroep="Kok", skills=skills)
    blok = laad_skills_tekst("25180")
    assert "Essentiële skills" in blok and "Samenwerken" in blok
    assert "Belangrijke skills" in blok and "Engels spreken" in blok


def test_laad_skills_leeg_bij_geen_beroep(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLS_PAD", str(tmp_path))
    _schrijf_skills(tmp_path, "25250", beroep=None)
    assert laad_skills_tekst("25250") == ""


def test_laad_skills_leeg_bij_ontbrekend_bestand(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLS_PAD", str(tmp_path))
    assert laad_skills_tekst("00000") == ""


def test_bouw_systeem_includeert_skills_blok():
    systeem = bouw_systeem(
        "OER-tekst",
        "Kok",
        "Da Vinci",
        skills_tekst="\n\n=== SKILLS-TAXONOMIE (ESCO) — beroep: kok ===\nskills hier",
    )
    assert "SKILLS-TAXONOMIE (ESCO)" in systeem
    assert "skills hier" in systeem


def test_bouw_systeem_zonder_skills_geen_blok():
    systeem = bouw_systeem("OER-tekst", "Kok", "Da Vinci")
    assert "SKILLS-TAXONOMIE (ESCO) — beroep" not in systeem


def test_bouw_gecombineerd_systeem_includeert_skills_per_oer():
    items = [
        {
            "tekst": "OER A",
            "opleiding": "Kok",
            "display_naam": "Da Vinci",
            "leerweg": "BOL",
            "cohort": "2025",
            "crebo": "25180",
            "skills_tekst": "\n\n=== SKILLS-TAXONOMIE (ESCO) — beroep: kok ===\nkooktechnieken",
        },
    ]
    systeem = bouw_gecombineerd_systeem(items)
    assert "SKILLS-TAXONOMIE (ESCO)" in systeem
    assert "kooktechnieken" in systeem


def test_identificeer_opleiding_woorden_max_2():
    oers = [_oer_row(opleiding="Verzorgende IG zorg medewerker")]
    # Drie matchende woorden (>3 chars: verzorgende, zorg, medewerker)
    # maar score is gecapt op 2
    resultaat = identificeer_oer_kandidaten(oers, "verzorgende zorg medewerker info", min_score=0)
    # Score ≤ 2 + 0 (geen leerweg/cohort match) + 0 (display_naam 'Rijn'/'IJssel' niet in tekst)
    assert resultaat[0]["_score"] == 2


def test_identificeer_camelcase_split_in_opleiding():
    oers = [_oer_row(opleiding="VerzorgendeIG")]
    resultaat = identificeer_oer_kandidaten(oers, "verzorgende info")
    # CamelCase moet "Verzorgende" matchen ondanks aanlopen aan "IG"
    assert resultaat[0]["_score"] >= 1


def test_identificeer_jaartal_telt_alleen_als_cohort():
    """2025 in de tekst telt alleen via cohort (+2), niet ook via opleidingswoorden."""
    oers = [_oer_row(opleiding="Cohort 2025 traject", cohort="2025", leerweg="BOL")]
    resultaat = identificeer_oer_kandidaten(oers, "2025")
    # cohort: +2, opleidingswoorden: 'cohort'/'traject' niet in tekst, '2025' uitgesloten als digit
    assert resultaat[0]["_score"] == 2


def test_identificeer_generieke_woorden_negeren_in_display_naam():
    oers = [_oer_row(display_naam="Da Vinci College")]
    resultaat = identificeer_oer_kandidaten(oers, "college informatie graag")
    # 'college' is generiek → telt niet
    assert resultaat[0]["_score"] == 0


def test_identificeer_filtert_op_min_score():
    oers = [
        _oer_row(id=1, crebo="11111", leerweg="BOL", cohort="2024", opleiding="Onbekend"),
        _oer_row(id=2, crebo="22222", leerweg="BBL", cohort="2025", opleiding="Onbekend"),
    ]
    # Tekst matcht alleen oer 2 op leerweg+cohort = 4 punten
    resultaat = identificeer_oer_kandidaten(oers, "BBL 2025", min_score=3)
    assert len(resultaat) == 1
    assert resultaat[0]["id"] == 2


def test_identificeer_woord_match_geen_substring():
    """'zorg' in opleidingsnaam mag niet als substring matchen op 'verzorgende'.

    Regressie: typen van 'Verzorgende' op de publieke OER-pagina leverde
    voorheen ook OERs als 'Helpende-zorg-en-welzijn' op (false-positive
    via substring 'zorg' in 'verzorgende').
    """
    oers = [
        _oer_row(id=1, opleiding="Verzorgende IG"),
        _oer_row(id=2, opleiding="Helpende-zorg-en-welzijn"),
        _oer_row(id=3, opleiding="Begeleider maatschappelijke zorg"),
    ]
    resultaat = identificeer_oer_kandidaten(oers, "Verzorgende", min_score=1)
    assert len(resultaat) == 1
    assert resultaat[0]["id"] == 1


def test_identificeer_sorteert_op_score_aflopend():
    oers = [
        _oer_row(id=1, crebo="11111", leerweg="BBL"),  # match: niets
        _oer_row(id=2, crebo="22222", leerweg="BBL"),  # match: leerweg (+2)
        _oer_row(id=3, crebo="33333", leerweg="BBL"),  # match: crebo (+3) + leerweg (+2)
    ]
    resultaat = identificeer_oer_kandidaten(oers, "33333 BBL", min_score=0)
    scores = [r["_score"] for r in resultaat]
    assert scores == sorted(scores, reverse=True)
    assert resultaat[0]["id"] == 3
