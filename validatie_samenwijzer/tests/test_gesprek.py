"""Gesprek: de server-side gesprekshistorie (cap, sanering, UI-view, afgebroken beurten)."""

import json
import threading

from validatie_samenwijzer.chat import knip_bronnenregel
from validatie_samenwijzer.gesprek import MAX_GESCHIEDENIS, Gesprek


def test_opslagvorm_is_de_oude_json_lijst_en_roundtrip():
    g = Gesprek()
    g.voeg_beurt_toe("v", "a\n<!-- bronnen: studiegids|OER -->")
    lijst = g.naar_lijst()
    assert lijst == [
        {"role": "user", "content": "v"},
        {"role": "assistant", "content": "a\n<!-- bronnen: studiegids|OER -->"},
    ]
    assert Gesprek.van_lijst(json.loads(json.dumps(lijst))) == g


def test_naar_lijst_geeft_een_kopie():
    g = Gesprek()
    g.voeg_beurt_toe("v", "a")
    g.naar_lijst()[0]["content"] = "gewijzigd"
    assert g.naar_lijst()[0]["content"] == "v"


def test_van_lijst_none_is_leeg():
    assert len(Gesprek.van_lijst(None)) == 0


def test_cap_op_max_geschiedenis_behoudt_nieuwste():
    g = Gesprek()
    for i in range(MAX_GESCHIEDENIS):
        g.voeg_beurt_toe(f"v{i}", f"a{i}")
    lijst = g.naar_lijst()
    assert len(lijst) == MAX_GESCHIEDENIS
    assert lijst[-1]["content"] == f"a{MAX_GESCHIEDENIS - 1}"
    assert lijst[0]["role"] == "user"


def test_reset_leegt():
    g = Gesprek()
    g.voeg_beurt_toe("v", "a")
    g.reset()
    assert not g and g.naar_lijst() == []


def test_context_tekst_plakt_user_beurten_en_nieuwe_vraag():
    g = Gesprek()
    assert g.context_tekst("kok") == "kok"
    g.voeg_beurt_toe("Ik zit op Talland", "welke opleiding?")
    assert g.context_tekst("kok") == "Ik zit op Talland kok"


def test_laatste_beurt_alleen_voltooide():
    g = Gesprek()
    assert g.laatste_beurt() is None
    g.voeg_beurt_toe("v", "")  # kies-beurt: onbeantwoord
    assert g.laatste_beurt() is None
    g.voeg_beurt_toe("v2", "a2")
    beurt = g.laatste_beurt()
    assert beurt is not None and (beurt.vraag, beurt.antwoord) == ("v2", "a2")
    g.voeg_beurt_toe("v3", "deel", afgebroken=True)
    assert g.laatste_beurt() is None


def test_afgebroken_beurt_zonder_halve_marker_in_model_en_ui():
    g = Gesprek()
    g.voeg_beurt_toe("Vraag 1", "Eerste deel van het antwoord\n\n<!-- bro", afgebroken=True)
    assert g.naar_lijst()[1] == {
        "role": "assistant",
        "content": "Eerste deel van het antwoord",
        "afgebroken": True,
    }
    # het model ziet het deel mét notitie, en daarna gewoon de volgende vraag
    assert g.berichten_voor_model("Vraag 2") == [
        {"role": "user", "content": "Vraag 1"},
        {"role": "assistant", "content": "Eerste deel van het antwoord\n\n[antwoord afgebroken]"},
        {"role": "user", "content": "Vraag 2"},
    ]
    ui = g.view_voor_ui()
    assert ui[1] == {
        "role": "assistant",
        "content": "Eerste deel van het antwoord",
        "bronnen": [],
        "afgebroken": True,
    }
    assert (
        "afgebroken"
        not in Gesprek.van_lijst([{"role": "assistant", "content": "a"}]).view_voor_ui()[0]
    )


def test_afgebroken_beurt_zonder_deel_telt_als_onbeantwoord():
    g = Gesprek()
    g.voeg_beurt_toe("Vraag 1", "", afgebroken=True)
    assert g.berichten_voor_model("Vraag 2") == [{"role": "user", "content": "Vraag 2"}]


def test_knip_bronnenregel_varianten():
    assert knip_bronnenregel("a\n<!-- bronnen: x|y -->") == "a"
    assert knip_bronnenregel("a\n<!-- bronnen: x|y") == "a"
    assert knip_bronnenregel("a <!-- bro") == "a"
    assert knip_bronnenregel("a < b") == "a < b"
    assert knip_bronnenregel("gewoon") == "gewoon"


def test_lopende_beurt_rond_af_legt_een_keer_vast():
    g = Gesprek()
    b = g.begin_beurt("v")
    b.voeg_toe("een ")
    b.voeg_toe("antwoord")
    assert b.antwoord == "een antwoord"
    assert b.rond_af() is True
    assert b.breek_af() is False and b.rond_af() is False
    assert g.naar_lijst() == [
        {"role": "user", "content": "v"},
        {"role": "assistant", "content": "een antwoord"},
    ]


def test_lopende_beurt_breek_af_wint_van_laat_afronden():
    g = Gesprek()
    b = g.begin_beurt("v")
    b.voeg_toe("deel")
    assert b.breek_af() is True
    b.voeg_toe(" te laat")  # een losgelaten worker mag niets meer toevoegen
    assert b.rond_af() is False
    lijst = g.naar_lijst()
    assert len(lijst) == 2 and lijst[1]["content"] == "deel" and lijst[1]["afgebroken"] is True


def test_lopende_beurt_race_geeft_precies_een_winnaar():
    for _ in range(50):
        g = Gesprek()
        b = g.begin_beurt("v")
        uitkomst: list[bool] = []
        start = threading.Barrier(2)

        def klaar(start=start, b=b, uitkomst=uitkomst):
            start.wait()
            uitkomst.append(b.rond_af())

        t = threading.Thread(target=klaar)
        t.start()
        start.wait()
        uitkomst.append(b.breek_af())
        t.join()
        assert sorted(uitkomst) == [False, True]
        assert len(g) == 2


# ── bronnen per beurt vastleggen ──────────────────────────────────────────────────
_BRON = {"type": "studiegids", "titel": "OER Kok", "url": None, "doc_id": None,
         "oer_id": 7, "crebo": "25180"}  # fmt: skip


def test_beurt_legt_geresolvede_bronnen_vast_en_view_gebruikt_ze():
    g = Gesprek()
    g.voeg_beurt_toe("v", "a\n<!-- bronnen: studiegids|OER Kok -->", bronnen=[_BRON])
    assert g.naar_lijst()[1]["bronnen"] == [_BRON]
    # Ander register (andere studiegids) → de vastgelegde bronnen blijven gelden.
    ander = [{"type": "studiegids", "titel": "OER Bakker", "oer_id": 9}]
    assert g.view_voor_ui(ander)[1]["bronnen"] == [_BRON]
    assert g.view_voor_ui(ander)[1]["content"] == "a"
    assert Gesprek.van_lijst(json.loads(json.dumps(g.naar_lijst()))).view_voor_ui(None) == (
        g.view_voor_ui(None)
    )


def test_lege_vastgelegde_bronnen_worden_niet_opnieuw_geresolvet():
    g = Gesprek()
    g.voeg_beurt_toe("v", "a\n<!-- bronnen: studiegids|OER Kok -->", bronnen=[])
    register = [{"type": "studiegids", "titel": "OER Kok", "oer_id": 7}]
    assert g.view_voor_ui(register)[1]["bronnen"] == []


def test_oude_beurt_zonder_bronnen_valt_terug_op_resolven_met_register():
    oud = [
        {"role": "user", "content": "v"},
        {"role": "assistant", "content": "a\n<!-- bronnen: studiegids|OER Kok -->"},
    ]
    g = Gesprek.van_lijst(oud)
    assert g.naar_lijst() == oud  # laadt/bewaart ongewijzigd
    register = [{"type": "studiegids", "titel": "OER Kok", "oer_id": 7}]
    assert g.view_voor_ui(register)[1]["bronnen"][0]["oer_id"] == 7
    assert g.view_voor_ui(None)[1]["bronnen"][0]["titel"] == "OER Kok"


def test_lopende_beurt_rond_af_geeft_bronnen_door():
    g = Gesprek()
    b = g.begin_beurt("v")
    b.voeg_toe("a")
    assert b.rond_af([_BRON])
    assert g.naar_lijst()[1] == {"role": "assistant", "content": "a", "bronnen": [_BRON]}


def test_afgebroken_beurt_en_kies_beurt_dragen_geen_bronnen_sleutel():
    g = Gesprek()
    g.voeg_beurt_toe("v", "deel", afgebroken=True)
    g.voeg_beurt_toe("w", "")
    assert all("bronnen" not in b for b in g.naar_lijst())


def test_bronnen_sleutel_beinvloedt_het_model_niet():
    g = Gesprek()
    g.voeg_beurt_toe("v", "a", bronnen=[_BRON])
    assert g.berichten_voor_model("w") == [
        {"role": "user", "content": "v"},
        {"role": "assistant", "content": "a"},
        {"role": "user", "content": "w"},
    ]
