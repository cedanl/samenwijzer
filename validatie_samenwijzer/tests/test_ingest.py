from validatie_samenwijzer.ingest import (
    chunk_paginas,
    chunk_tekst,
    chunk_tekst_semantisch,
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


# ── chunk_tekst_semantisch ────────────────────────────────────────────────────


def test_chunk_tekst_semantisch_korte_tekst():
    tekst = "Dit is een korte tekst."
    chunks = chunk_tekst_semantisch(tekst, max_woorden=100)
    assert chunks == [tekst]


def test_chunk_tekst_semantisch_lege_tekst():
    assert chunk_tekst_semantisch("") == []


def test_chunk_tekst_semantisch_verdeelt_lange_tekst():
    alineas = [" ".join([f"woord{j}" for j in range(80)]) for _ in range(8)]
    tekst = "\n\n".join(alineas)
    chunks = chunk_tekst_semantisch(tekst, max_woorden=150, overlap_alineas=0)
    assert len(chunks) > 1
    assert all(len(c.split()) <= 250 for c in chunks)  # wat ruimte voor alinea-overschrijding


def test_chunk_tekst_semantisch_bewaart_alinea_grenzen():
    tekst = "Kerntaak 1: Zorg verlenen.\n\nKerntaak 2: Begeleiding bieden."
    chunks = chunk_tekst_semantisch(tekst, max_woorden=5, overlap_alineas=0)
    assert len(chunks) == 2
    assert "Kerntaak 1" in chunks[0]
    assert "Kerntaak 2" in chunks[1]


def test_chunk_tekst_semantisch_overlap_bewaart_laatste_alinea():
    alineas = [f"Alinea {i}: " + " ".join([f"w{j}" for j in range(20)]) for i in range(4)]
    tekst = "\n\n".join(alineas)
    chunks = chunk_tekst_semantisch(tekst, max_woorden=40, overlap_alineas=1)
    if len(chunks) >= 2:
        laatste_van_eerste = chunks[0].split("\n\n")[-1]
        assert laatste_van_eerste in chunks[1]


def test_chunk_tekst_semantisch_geen_lege_chunks():
    tekst = "\n\n".join(["Alinea één.", "", "   ", "Alinea twee."])
    chunks = chunk_tekst_semantisch(tekst, max_woorden=100)
    assert all(c.strip() for c in chunks)


# ── chunk_paginas ─────────────────────────────────────────────────────────────


def test_chunk_paginas_bewaart_paginanummer():
    paginas = [(3, "Kerntaak 1: Zorg.\n\nKerntaak 2: Begeleiding.")]
    chunks = chunk_paginas(paginas, max_woorden=5, overlap_alineas=0)
    assert all(c["pagina"] == 3 for c in chunks)
    assert len(chunks) == 2


def test_chunk_paginas_meerdere_paginas():
    paginas = [(1, "Pagina één inhoud."), (2, "Pagina twee inhoud.")]
    chunks = chunk_paginas(paginas, max_woorden=100)
    paginanrs = [c["pagina"] for c in chunks]
    assert 1 in paginanrs
    assert 2 in paginanrs


def test_chunk_paginas_lege_pagina_overgeslagen():
    paginas = [(1, "Inhoud."), (2, "   "), (3, "Meer inhoud.")]
    chunks = chunk_paginas(paginas, max_woorden=100)
    paginanrs = [c["pagina"] for c in chunks]
    assert 2 not in paginanrs
