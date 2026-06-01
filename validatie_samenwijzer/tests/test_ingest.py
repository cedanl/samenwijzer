from validatie_samenwijzer.ingest import (
    _kerntaken_uit_kd,
    _schoon_kd_naam,
    extraheer_kerntaken,
    parseer_bestandsnaam,
)


def test_parseer_bestandsnaam_davinci():
    r = parseer_bestandsnaam("25168BOL2025Examenplan-Gastheer-vrouw-cohort-2025.pdf")
    assert r == {"crebo": "25168", "leerweg": "BOL", "cohort": "2025"}


def test_parseer_bestandsnaam_met_spatie():
    r = parseer_bestandsnaam("25655 BBL 2024 OER Verzorgende.pdf")
    assert r == {"crebo": "25655", "leerweg": "BBL", "cohort": "2024"}


def test_parseer_bestandsnaam_geen_match():
    assert parseer_bestandsnaam("Examenplannen Biologisch Dynamische landbouw.pdf") is None


def test_extraheer_kerntaken_herkent_codes():
    tekst = """
    B1-K1 Verpleegkundige zorg verlenen
    Hieronder valt: dagelijkse zorg voor cliënten.

    B1-K1-W1 Zorg plannen en organiseren
    De student plant de zorg zelfstandig.

    B1-K2 Begeleiding bieden
    Tweede kerntaak van de opleiding.
    """
    kt = extraheer_kerntaken(tekst)
    codes = [k["code"] for k in kt]
    assert "B1-K1" in codes
    assert "B1-K1-W1" in codes
    assert "B1-K2" in codes
    assert kt[0]["type"] == "kerntaak"
    assert kt[1]["type"] == "werkproces"


def test_extraheer_kerntaken_herkent_kerntaak_prefix():
    tekst = """
    Kerntaak 1: Werkzaamheden uitvoeren in het bedrijf
    Werkproces 1.1: Plannen van werkzaamheden
    Werkproces 1.2: Uitvoeren van dagelijkse taken
    Kerntaak 2: Rapportages opstellen voor management
    """
    kt = extraheer_kerntaken(tekst)
    typen = [k["type"] for k in kt]
    assert typen.count("kerntaak") >= 2
    assert typen.count("werkproces") >= 2


def test_extraheer_kerntaken_lege_tekst():
    assert extraheer_kerntaken("") == []


def test_extraheer_kerntaken_filtert_garbled_fragments():
    """Tabel-cellen die als losse regels worden afgevlakt mogen niet als
    kerntaak doorkomen. Echte beschrijvingen hebben minstens 12 letters
    en bevatten lowercase tekst."""
    tekst = """
    B1-K1- 1
    B1-K1- W2
    B1-K1- TE
    B1-K1: Verzorgt cliënten in dagelijkse activiteiten
    Kerntaak 2: 4
    Kerntaak 3: Begeleiding bij sociale ontwikkeling
    """
    kt = extraheer_kerntaken(tekst)
    namen = [k["naam"] for k in kt]
    assert "1" not in namen
    assert "W2" not in namen
    assert "TE" not in namen
    assert "4" not in namen
    assert "Verzorgt cliënten in dagelijkse activiteiten" in namen
    assert "Begeleiding bij sociale ontwikkeling" in namen


def test_extraheer_kerntaken_dedupt_binnen_document():
    """Dezelfde kerntaak komt vaak meerdere keren voor in een OER (introductie,
    tabel, uitwerking). Extractor levert per OER unieke records."""
    tekst = """
    B1-K1: Bieden van zorg en ondersteuning in het verpleegkundig proces
    ergens later in het document...
    B1-K1: Bieden van zorg en ondersteuning in het verpleegkundig proces
    en nog een keer:
    B1-K1: Bieden van zorg en ondersteuning in het verpleegkundig proces
    """
    kt = extraheer_kerntaken(tekst)
    namen = [k["naam"] for k in kt]
    assert namen.count("Bieden van zorg en ondersteuning in het verpleegkundig proces") == 1


def test_kerntaken_uit_kd_schoont_en_dedupt_per_code():
    # TOC-regel (schoon, lang) + body-herhaling (gewrapt, korter, geen dubbelepunt).
    kd_tekst = """
    B1-K1:  Brengt de modewereld in beeld en ontwikkelt een modeconcept  ......  9
    B1-K1-W1:  Verzamelt en verwerkt informatie over ontwikkelingen in de mode  ..  10

    later in het document:
    B1-K1 Brengt de modewereld in beeld en
    """
    kt = _kerntaken_uit_kd(kd_tekst)
    per_code = {k["code"]: k for k in kt}
    assert sorted(per_code) == ["B1-K1", "B1-K1-W1"]
    assert per_code["B1-K1"]["naam"] == "Brengt de modewereld in beeld en ontwikkelt een modeconcept"
    assert per_code["B1-K1"]["type"] == "kerntaak"
    assert per_code["B1-K1-W1"]["type"] == "werkproces"
    assert sorted(k["volgorde"] for k in kt) == [0, 1]


def test_schoon_kd_naam_verwijdert_dotted_leaders():
    ruw = "Uitvoeren metingen leefomgeving en rapporteren resultaten  ...........  6"
    assert _schoon_kd_naam(ruw) == "Uitvoeren metingen leefomgeving en rapporteren resultaten"


def test_schoon_kd_naam_zonder_leaders_blijft_gelijk():
    assert _schoon_kd_naam("Voert toegangscontroles uit") == "Voert toegangscontroles uit"
