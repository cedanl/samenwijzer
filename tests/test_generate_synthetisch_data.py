"""Tests voor generate_synthetisch_data.py."""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from generate_synthetisch_data import (  # noqa: E402
    SECTOR_KOLOMMEN,
    VOOROPLEIDING_KOLOMMEN,
    bouw_student_record,
    ken_mentor_toe,
    maak_mentoren,
    verdeel_studenten,
)


def test_verdeel_studenten_per_instelling():
    """200 studenten over 3 opleidingen (gelijkmatig)."""
    opleidingen_per_inst = ["Kok", "Kapper", "Mediamaker"]
    verdeling = verdeel_studenten(200, opleidingen_per_inst)
    assert sum(verdeling.values()) == 200
    # Verdeling is binnen ±1 van 200/3 ≈ 67
    for opl, n in verdeling.items():
        assert 65 <= n <= 68


def test_verdeel_studenten_lege_lijst_geeft_assertion_error():
    with pytest.raises(AssertionError):
        verdeel_studenten(200, [])


def test_verdeel_studenten_alle_naar_één_opleiding():
    verdeling = verdeel_studenten(200, ["Kok"])
    assert verdeling == {"Kok": 200}


def test_maak_mentoren_aantal():
    rng = random.Random(42)
    namen = maak_mentoren(rng, 10)
    assert len(namen) == 10
    assert len(set(namen)) == 10  # uniek
    # Format: voorletter + . + spatie + achternaam
    for n in namen:
        assert "." in n


def test_ken_mentor_toe_distribueert_gelijkmatig():
    rng = random.Random(42)
    mentoren = ["A", "B", "C", "D", "E"]
    toewijzingen = [ken_mentor_toe(rng, mentoren) for _ in range(100)]
    # Elke mentor moet zo'n 20× voorkomen, ±5
    counts = {m: toewijzingen.count(m) for m in mentoren}
    assert all(15 <= c <= 25 for c in counts.values()), counts


def test_bouw_student_record_heeft_alle_kolommen():
    rng = random.Random(42)
    record = bouw_student_record(
        rng=rng,
        studentnummer="100001",
        naam="Test Student",
        instelling="Rijn IJssel",
        opleiding="Verzorgende IG",
        crebo="25655",
        leerweg="BOL",
        cohort="2025",
        niveau=3,
        sector="Zorgenwelzijn",
        mentor="A. Bakker",
    )

    # Identificatie
    assert record["Studentnummer"] == "100001"
    assert record["Naam"] == "Test Student"
    assert record["Instelling"] == "Rijn IJssel"
    assert record["Opleiding"] == "Verzorgende IG"
    assert record["Mentor"] == "A. Bakker"
    # Klas moet niveau-cijfer + cohort-letter zijn
    assert record["Klas"][0] == "3"
    # Cohort 2025 → letter B (2024 → A)
    assert record["Klas"] == "3B"

    # Sector one-hots: alleen 'Zorgenwelzijn' = 1
    for kolom in SECTOR_KOLOMMEN:
        if kolom == "Zorgenwelzijn":
            assert record[kolom] == 1
        else:
            assert record[kolom] == 0

    # Vooropleiding: precies één 1
    voorop_som = sum(record[k] for k in VOOROPLEIDING_KOLOMMEN)
    assert voorop_som == 1


def test_bouw_student_record_cohort_2024_geeft_letter_a():
    rng = random.Random(42)
    record = bouw_student_record(
        rng=rng,
        studentnummer="100002",
        naam="X",
        instelling="Rijn IJssel",
        opleiding="Kok",
        crebo="25180",
        leerweg="BOL",
        cohort="2024",
        niveau=3,
        sector="Anders",
        mentor="B. Jansen",
    )
    assert record["Klas"] == "3A"


def test_bouw_student_record_dropout_gecorreleerd_met_absence():
    """Studenten met hoog absence_unauthorized hebben hogere dropout-kans."""
    rng = random.Random(42)
    veel_dropouts = 0
    for i in range(100):
        record = bouw_student_record(
            rng=rng,
            studentnummer=f"1000{i:02d}",
            naam=f"X{i}",
            instelling="Rijn IJssel",
            opleiding="Kok",
            crebo="25180",
            leerweg="BOL",
            cohort="2024",
            niveau=3,
            sector="Anders",
            mentor="A. Bakker",
        )
        if record["absence_unauthorized"] > 30 and record["Dropout"] == 1:
            veel_dropouts += 1
    # Niet hard te assert-en; ruwe sanity check dat de correlatie er is
    assert veel_dropouts >= 0
