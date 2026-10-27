"""Tests voor scripts/ingest_bronmateriaal.py: classificatie op bestandsnaam, geen conversie."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import ingest_bronmateriaal as ib  # noqa: E402  (scripts/ is geen package)


def _per_bestand(items: list[ib.Item]) -> dict[str, ib.Item]:
    return {i.bestand: i for i in items}


def test_curio_examenregelement_hoogste_versie_en_duplicaten():
    bestanden = [
        "Examenregelement/Keuken/Kok-27060-2026 v1.0.pdf",
        "Examenregelement/Keuken/Kok-27060-2026 v1.0 (1).pdf",
        "Examenregelement/Keuken/Leidinggevende facilitaire dienstverlening-27140-2026 v1.0.pdf",
        "Examenregelement/Keuken/Leidinggevende facilitaire dienstverlening-27140-2026 v2.0.pdf",
        "Examenregelement/Keuken/Medewerker foodservice (Crebonr. 27061)-27061-2026 v1.0.pdf",
    ]
    items = _per_bestand(ib.classificeer("curio", bestanden))

    kok = items["Examenregelement/Keuken/Kok-27060-2026 v1.0.pdf"]
    assert (kok.status, kok.soort, kok.bereik) == (ib.INGENOMEN, "examenplan", "opleiding")
    assert (kok.crebo, kok.cohort, kok.leerweg, kok.versie_label) == ("27060", "2026", "", "v1.0")
    assert items["Examenregelement/Keuken/Kok-27060-2026 v1.0 (1).pdf"].status == ib.OVERGESLAGEN

    oud = items[
        "Examenregelement/Keuken/Leidinggevende facilitaire dienstverlening-27140-2026 v1.0.pdf"
    ]
    nieuw = items[
        "Examenregelement/Keuken/Leidinggevende facilitaire dienstverlening-27140-2026 v2.0.pdf"
    ]
    assert oud.status == ib.OVERGESLAGEN and "oudere versie" in oud.reden
    assert nieuw.status == ib.INGENOMEN and nieuw.versie_label == "v2.0"

    # crebo-toevoeging in de naam komt niet in de titel
    foodservice = items[
        "Examenregelement/Keuken/Medewerker foodservice (Crebonr. 27061)-27061-2026 v1.0.pdf"
    ]
    assert foodservice.titel == "Examenplan Medewerker foodservice (27061) cohort 2026"
    assert foodservice.md_pad.startswith("oeren/curio_oeren/_documenten/examenplan/27061-2026-")


@pytest.mark.parametrize(
    ("bestand", "crebo", "cohort", "leerweg"),
    [
        ("NML/Keuken/27060_nml_00_2026_vg_bol-bbl_kok.pdf", "27060", "2026", ""),
        (
            "NML/Brood en banket/27138_nml_00_2026_vg_bol_leidinggevende-bakkerij.pdf",
            "27138",
            "2026",
            "BOL",
        ),
        ("NML/Brood en banket/25614_nml_00_2023_vg_bbl_boulanger.pdf", "25614", "2023", "BBL"),
    ],
)
def test_curio_nml_velden_uit_bestandsnaam(bestand, crebo, cohort, leerweg):
    (item,) = ib.classificeer("curio", [bestand])
    assert (item.status, item.soort, item.bereik) == (ib.INGENOMEN, "nominale_lijn", "opleiding")
    assert (item.crebo, item.cohort, item.leerweg) == (crebo, cohort, leerweg)


def test_curio_nml_met_oer_in_naam_wordt_overgeslagen():
    (item,) = ib.classificeer(
        "curio", ["NML/Keuken/27054_oer_00_2026_vg_bol_zelfstandig-medewerker-leisure.pdf"]
    )
    assert item.status == ib.OVERGESLAGEN
    assert "_oer_" in item.reden


def test_curio_wortelbestanden_en_overslaan():
    items = _per_bestand(
        ib.classificeer(
            "curio",
            [
                "251811-Protocol kluiscontrole mbo incl template draaiboek.pdf",
                "bsa-info_voor_student_schooljaar_25-26_def.pdf",
                "Kwalificatiedossiers/Keuken/Kok.pdf",
                "curio examenreglement mbo 2026-2027.pdf",
            ],
        )
    )
    protocol = items["251811-Protocol kluiscontrole mbo incl template draaiboek.pdf"]
    assert (protocol.soort, protocol.titel, protocol.bereik) == (
        "protocol",
        "Protocol kluiscontrole",
        "instelling",
    )
    bsa = items["bsa-info_voor_student_schooljaar_25-26_def.pdf"]
    assert bsa.soort == "bindend_studieadvies"
    assert bsa.titel == "BSA-informatie voor studenten 2025-2026"
    assert items["Kwalificatiedossiers/Keuken/Kok.pdf"].status == ib.OVERGESLAGEN
    assert items["curio examenreglement mbo 2026-2027.pdf"].status == ib.OVERGESLAGEN


def test_graafschap_examenplan_leerweg_en_overslaan():
    items = _per_bestand(
        ib.classificeer(
            "graafschap",
            [
                "examenplannen/27016_ICT_System_Engineer-(Niv4)BBL_ExamenplanCohort2026.xlsm",
                "examenplannen/25998_Software_Developer(niv4)_ExamenplanCohort2025.xlsm",
                "onderwijsschemas/Onderwijsinrichting  I&C 2026_2027.xlsm",
                "oer_docx/OER ICT & Mediavormgeving 2025-2026.docx",
            ],
        )
    )
    bbl = items["examenplannen/27016_ICT_System_Engineer-(Niv4)BBL_ExamenplanCohort2026.xlsm"]
    assert (bbl.soort, bbl.crebo, bbl.cohort, bbl.leerweg) == ("examenplan", "27016", "2026", "BBL")
    assert bbl.titel == "Examenplan ICT System Engineer (Niv4) BBL cohort 2026"
    sd = items["examenplannen/25998_Software_Developer(niv4)_ExamenplanCohort2025.xlsm"]
    assert (sd.crebo, sd.cohort, sd.leerweg) == ("25998", "2025", "")
    plan = items["onderwijsschemas/Onderwijsinrichting  I&C 2026_2027.xlsm"]
    assert plan.status == ib.OVERGESLAGEN and "docentcodes" in plan.reden
    assert items["oer_docx/OER ICT & Mediavormgeving 2025-2026.docx"].status == ib.OVERGESLAGEN


def test_kwic_classificatie():
    items = _per_bestand(
        ib.classificeer(
            "kwic",
            [
                "Studentenstatuut addendum gepubliceerd.pdf",
                "Module overzicht.xlsx",
                "Grof ontwerp challenges BBL4 (1).pdf",
            ],
        )
    )
    statuut = items["Studentenstatuut addendum gepubliceerd.pdf"]
    assert (statuut.soort, statuut.titel, statuut.versie_label) == (
        "studentenstatuut",
        "Studentenstatuut — addendum",
        "addendum",
    )
    module = items["Module overzicht.xlsx"]
    assert (module.soort, module.leerweg, module.crebo) == ("onderwijsplan", "BBL", "")
    assert items["Grof ontwerp challenges BBL4 (1).pdf"].status == ib.OVERGESLAGEN


def test_ingenomen_items_hebben_geldige_soort_en_unieke_bestemming():
    bestanden = [
        "NML/Keuken/27052_nml_00_2026_st_bol-bbl_medewerker-hospitality_entree-mbobreed.pdf",
        "NML/Keuken/27052_nml_00_2026_vg_bol-bbl_medewerker-hospitality.pdf",
    ]
    items = ib.classificeer("curio", bestanden)
    assert len({i.md_pad for i in items}) == 2
    assert all(i.soort in ib.SOORTEN for i in items)


def test_onbekende_instelling_geeft_valueerror():
    with pytest.raises(ValueError, match="Onbekende instelling"):
        ib.classificeer("onbekend", [])


def test_redigeer_verwijdert_contactgegevens_maar_laat_crebo_staan():
    tekst = (
        "Mail info@curio.nl of bel 088 123 4567 of 06-12345678. "
        "IBAN NL91 ABNA 0417 1643 00. BSN: 123456782. Crebo 25742, cohort 2026."
    )
    schoon, aantallen = ib.redigeer(tekst)
    assert "info@curio.nl" not in schoon
    assert "088 123 4567" not in schoon
    assert "06-12345678" not in schoon
    assert "NL91" not in schoon
    assert "123456782" not in schoon
    assert "Crebo 25742, cohort 2026." in schoon
    assert set(aantallen) == {"email", "telefoon", "iban", "bsn"}


def test_redigeer_namen_na_rol_maar_niet_rollen_zelf():
    tekst = (
        "Locatie: Oss\nProjectleider: Willem van der Weijden - Lotte de Rijt\n"
        "Contactpersoon: de mentor"
    )
    schoon, aantallen = ib.redigeer(tekst)
    assert "Weijden" not in schoon and "Rijt" not in schoon
    assert "Projectleider: [verwijderd]" in schoon
    assert "Contactpersoon: de mentor" in schoon
    assert aantallen == {"naam_bij_rol": 1}


def test_redigeer_laat_label_zonder_naam_en_regeleinde_intact():
    tekst = (
        "Contactpersonen:\n\nContactpersoon voor- tijdens en na de controle\n(Naam contactpersoon)"
    )
    assert ib.redigeer(tekst) == (tekst, {})


def test_blad_naar_markdown_maakt_tabel_en_tekstregels():
    rijen = [["Titel van het blad"], ["Code", "Naam"], ["K1", "Kerntaak 1"], [], ["", ""]]
    md = ib._blad_naar_markdown(rijen)
    assert md.splitlines()[0] == "Titel van het blad"
    assert "| Code | Naam |" in md
    assert "| K1 | Kerntaak 1 |" in md


def test_redigeer_bekende_namen_uit_review():
    schoon, aantallen = ib.redigeer("Goedgekeurd door Maico de Jong, Raad van Bestuur.")
    assert "Maico" not in schoon and "Raad van Bestuur" in schoon
    assert aantallen == {"naam_review": 1}
