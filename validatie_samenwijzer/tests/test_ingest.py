import pytest
from validatie_samenwijzer.ingest import (
    parseer_bestandsnaam,
    chunk_tekst,
    extraheer_kerntaken,
)


def test_parseer_bestandsnaam_davinci():
    r = parseer_bestandsnaam("25168BOL2025Examenplan-Gastheer-vrouw-cohort-2025.pdf")
    assert r == {"crebo": "25168", "leerweg": "BOL", "cohort": "2025"}


def test_parseer_bestandsnaam_met_spatie():
    r = parseer_bestandsnaam("25655 BBL 2024 OER Verzorgende.pdf")
    assert r == {"crebo": "25655", "leerweg": "BBL", "cohort": "2024"}


def test_parseer_bestandsnaam_geen_match():
    assert parseer_bestandsnaam("Examenplannen Biologisch Dynamische landbouw.pdf") is None


def test_chunk_tekst_verdeelt_in_stukken():
    tekst = " ".join([f"woord{i}" for i in range(600)])
    chunks = chunk_tekst(tekst, chunk_grootte=100, overlap=10)
    assert len(chunks) > 1
    assert all(len(c.split()) <= 110 for c in chunks)


def test_chunk_tekst_korte_tekst():
    tekst = "Dit is een korte tekst."
    chunks = chunk_tekst(tekst, chunk_grootte=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0] == tekst


def test_chunk_tekst_overlap():
    woorden = [f"w{i}" for i in range(25)]
    tekst = " ".join(woorden)
    chunks = chunk_tekst(tekst, chunk_grootte=20, overlap=5)
    assert len(chunks) >= 2
    eerste_einde = chunks[0].split()[-3:]
    tweede_begin = chunks[1].split()[:3]
    assert any(w in tweede_begin for w in eerste_einde)


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
    Kerntaak 1: Werkzaamheden uitvoeren
    Werkproces 1.1: Plannen van werkzaamheden
    Werkproces 1.2: Uitvoeren van taken
    Kerntaak 2: Rapportage
    """
    kt = extraheer_kerntaken(tekst)
    typen = [k["type"] for k in kt]
    assert typen.count("kerntaak") >= 2
    assert typen.count("werkproces") >= 2


def test_extraheer_kerntaken_lege_tekst():
    assert extraheer_kerntaken("") == []
