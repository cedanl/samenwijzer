from validatie_samenwijzer.chat import (
    LAGE_RELEVANTIE_BERICHT,
    bouw_berichten,
    bouw_gecombineerd_systeem,
    bouw_systeem,
    identificeer_oer_kandidaten,
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


def test_identificeer_opleiding_woorden_max_2():
    oers = [_oer_row(opleiding="Verzorgende IG zorg medewerker")]
    # Drie matchende woorden (>3 chars: verzorgende, zorg, medewerker)
    # maar score is gecapt op 2
    resultaat = identificeer_oer_kandidaten(
        oers, "verzorgende zorg medewerker info", min_score=0
    )
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
