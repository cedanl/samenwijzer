"""Bron-catalogus: unieke titels, eenduidige koppen, resolve en register-round-trip."""

import json

import pytest

from validatie_samenwijzer.bron_catalogus import (
    Bron,
    BronCatalogus,
    BronRegister,
    OerInvoer,
)
from validatie_samenwijzer.chat import splits_bronnen
from validatie_samenwijzer.documenten import GekozenDocument
from validatie_samenwijzer.gesprek import Gesprek

_SKILLS = "\n\n=== SKILLS-TAXONOMIE (ESCO) — beroep: kok ===\nkooktechnieken"


def _doc(doc_id: int, kop: str, tekst: str = "doctekst") -> GekozenDocument:
    return GekozenDocument(doc_id, kop, tekst, "[INFORMATIEF]" not in kop, "instelling")


def _oer(**kw) -> OerInvoer:
    basis = {
        "opleiding": "Kok",
        "instelling": "Curio",
        "oer_id": 7,
        "instelling_sleutel": "curio",
        "leerweg": "BOL",
        "cohort": "2025",
        "crebo": "25180",
        "oer_tekst": "OER-TEKST",
    }
    return OerInvoer(**{**basis, **kw})


def _volledig(**kw) -> OerInvoer:
    return _oer(
        kd_tekst="KD-TEKST",
        skills_tekst=_SKILLS,
        documenten=(_doc(11, "Examenreglement"), _doc(12, "Protocol — Kluis [INFORMATIEF]")),
        **kw,
    )


def test_titels_uniek_en_met_identifiers():
    cat = BronCatalogus.bouw([_volledig()])
    assert [(b.type, b.titel) for b in cat.bronnen] == [
        ("studiegids", "OER Kok BOL 2025"),
        ("schooldocument", "Examenreglement"),
        ("schooldocument", "Protocol — Kluis"),
        ("kwalificatiedossier", "Kwalificatiedossier 25180"),
        ("skills", "ESCO kok"),
    ]
    oer, examen, _, kd, skills = cat.bronnen
    assert oer.oer_id == 7 and examen.doc_id == 11
    assert kd.crebo == "25180" and kd.oer_id == 7 and skills.crebo == "25180"


def test_koppen_identiek_in_single_en_multi():
    """Dezelfde OER rendert dezelfde koppen, alleen of hij alleen of naast een ander staat."""
    enkel = BronCatalogus.bouw([_volledig()])
    multi = BronCatalogus.bouw(
        [_volledig(), _oer(oer_id=8, opleiding="Bakker", instelling="Talland", crebo="25300")]
    )
    koppen_enkel = [b.kop for b in enkel.oers[0].blokken]
    koppen_multi = [b.kop for b in multi.oers[0].blokken]
    assert koppen_enkel == koppen_multi
    assert "=== EXAMENREGLEMENT (Curio) ===" in koppen_enkel
    assert "=== PROTOCOL — KLUIS [INFORMATIEF] (Curio) ===" in koppen_enkel
    assert "=== OER 1: Curio · Kok · BOL 2025 ===" in koppen_enkel
    assert "=== KWALIFICATIEDOSSIER 1 (Crebo 25180) ===" in koppen_enkel
    tekst = multi.bronblokken()
    assert "=== OER 2: Talland · Bakker · BOL 2025 ===" in tekst
    assert "\n\n---\n\n" in tekst


def test_botsende_titels_krijgen_instelling_en_daarna_oer_nummer():
    cat = BronCatalogus.bouw(
        [
            _oer(documenten=(_doc(1, "Examenreglement"),)),
            _oer(oer_id=8, instelling="Talland", documenten=(_doc(2, "Examenreglement"),)),
            _oer(oer_id=9, leerweg="BOL"),  # zelfde OER-titel én instelling als de eerste
        ]
    )
    titels = [b.titel for b in cat.bronnen]
    assert len(titels) == len({t.casefold() for t in titels})
    assert "Examenreglement (Curio)" in titels and "Examenreglement (Talland)" in titels
    assert "OER Kok BOL 2025 (Talland)" in titels
    assert "OER Kok BOL 2025 (Curio) (OER 1)" in titels
    assert "OER Kok BOL 2025 (Curio) (OER 3)" in titels


def test_oer_zonder_enige_bron_valt_weg_en_onleesbare_is_niet_citeerbaar():
    cat = BronCatalogus.bouw([_oer(oer_tekst=""), _oer(oer_id=8, oer_tekst="", kd_tekst="KD")])
    assert len(cat.oers) == 1 and cat.oer_onleesbaar
    assert [b.type for b in cat.bronnen] == ["kwalificatiedossier"]
    assert "niet machine-leesbaar" in cat.bronblokken()
    assert BronCatalogus.bouw([_oer(oer_tekst="")]).leeg


def test_resolve_kent_bekende_titels_en_wijst_onbekende_af():
    cat = BronCatalogus.bouw([_volledig()])
    assert cat.resolve("Examenreglement").doc_id == 11
    assert cat.resolve("  examenreglement ").doc_id == 11  # hoofdletter-/witruimte-ongevoelig
    assert cat.resolve("Protocol - Kluis [INFORMATIEF]").doc_id == 12  # streepje + markering
    assert cat.resolve("OER Kok BOL 2025").oer_id == 7
    assert cat.resolve("Studentenstatuut") is None  # verzonnen
    assert cat.resolve("OER Kapper BOL 2025") is None


def test_register_round_trip_zonder_teksten():
    cat = BronCatalogus.bouw([_volledig()])
    register = cat.register(["curio.nl", "indeed.nl"])
    json.dumps(register)  # serialiseerbaar voor de sessie
    assert "OER-TEKST" not in json.dumps(register)
    herbouwd = BronRegister.uit_dicts(json.loads(json.dumps(register)))
    for bron in cat.bronnen:
        assert herbouwd.resolve(bron.titel) == bron
    assert herbouwd.resolve("curio.nl", "https://www.curio.nl/open-dag") == Bron(
        "website", "curio.nl", "https://www.curio.nl/open-dag"
    )
    assert herbouwd.resolve("curio.nl", "https://evil.example/curio.nl") is None
    assert herbouwd.resolve("talland.nl") is None


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example\\@curio.nl/x",  # browser leest \\ als / → evil.example
        "https://user@curio.nl/x",  # userinfo
        "https://curio.nl:8443/x",  # poort
        "https://curio.nl/x y",  # witruimte
        "javascript:alert(1)",
        "https://curio.nl.evil.example/x",  # ander domein met curio.nl als prefix
    ],
)
def test_register_wijst_misleidende_website_urls_af(url):
    cat = BronCatalogus.bouw([_volledig()])
    herbouwd = BronRegister.uit_dicts(cat.register(["curio.nl"]))
    assert herbouwd.resolve("curio.nl", url) is None


def test_register_uit_dicts_negeert_rommel():
    reg = BronRegister.uit_dicts([{"type": "folder", "titel": "x"}, {"type": "skills"}, "x"])
    assert reg.bronnen == ()


def test_splits_bronnen_met_register_zet_identifiers_en_filtert_onbekenden():
    register = BronCatalogus.bouw([_volledig()]).register(["curio.nl"])
    tekst = (
        "Antwoord.\n<!-- bronnen: studiegids|oer kok bol 2025; schooldocument|Examenreglement; "
        "schooldocument|Verzonnen reglement; kwalificatiedossier|Kwalificatiedossier 25180; "
        "website|curio.nl|https://curio.nl/x; website|indeed.nl|https://indeed.nl/y -->"
    )
    schoon, bronnen = splits_bronnen(tekst, register)
    assert schoon == "Antwoord."
    assert bronnen == [
        Bron("studiegids", "OER Kok BOL 2025", oer_id=7),
        Bron("schooldocument", "Examenreglement", doc_id=11),
        Bron("kwalificatiedossier", "Kwalificatiedossier 25180", oer_id=7, crebo="25180"),
        Bron("website", "curio.nl", "https://curio.nl/x"),
    ]


def test_splits_bronnen_met_register_corrigeert_het_type():
    register = BronCatalogus.bouw([_volledig()]).register()
    _, bronnen = splits_bronnen("x\n<!-- bronnen: studiegids|Examenreglement -->", register)
    assert bronnen == [Bron("schooldocument", "Examenreglement", doc_id=11)]


def test_geschiedenis_voor_ui_met_register():
    register = BronCatalogus.bouw([_volledig()]).register()
    hist = [{"role": "assistant", "content": "a\n<!-- bronnen: studiegids|OER Kok BOL 2025 -->"}]
    assert Gesprek.van_lijst(hist).view_voor_ui(register)[0]["bronnen"][0]["oer_id"] == 7


def test_titel_zonder_scheidingstekens_van_de_bronnenregel():
    cat = BronCatalogus.bouw([_oer(documenten=(_doc(1, "Protocol — Kluis; deur|raam"),))])
    titel = cat.bronnen[1].titel
    assert "|" not in titel and ";" not in titel
    _, bronnen = splits_bronnen(f"x\n<!-- bronnen: schooldocument|{titel} -->", cat.register())
    assert bronnen[0].doc_id == 1
