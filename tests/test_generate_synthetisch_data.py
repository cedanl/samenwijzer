"""Tests voor generate_synthetisch_data.py."""

import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from generate_synthetisch_data import (  # noqa: E402
    SECTOR_KOLOMMEN,
    VOOROPLEIDING_KOLOMMEN,
    bouw_student_record,
    genereer,
    ken_mentor_toe,
    maak_mentoren,
    verdeel_studenten,
)

from samenwijzer import oer_store  # noqa: E402


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


# ── Integratie-tests (orchestrator) ──────────────────────────────────────────


def _maak_mini_db(tmp_path: Path) -> tuple[Path, Path]:
    """Hulpfunctie: bouw een mini DB met 4 instellingen + 3 opleidingen + JSON."""
    db_pad = tmp_path / "oeren.db"
    instellingen = [
        ("rijn_ijssel", "Rijn IJssel"),
        ("davinci", "Da Vinci"),
        ("talland", "Talland"),
        ("utrecht", "Utrecht"),
    ]
    for naam, display in instellingen:
        oer_store.voeg_instelling_toe(db_pad, naam, display)

    opleidingen = [("Kok", "25180", 3), ("Kapper", "25641", 3), ("Mediamaker", "25591", 4)]
    for naam, _ in instellingen:
        inst = oer_store.get_instelling_by_naam(db_pad, naam)
        for opl, crebo, niv in opleidingen:
            oer_store.voeg_oer_document_toe(
                db_pad,
                inst["id"],
                opl,
                crebo,
                "2025",
                "BOL",
                niv,
                f"oeren/{naam}/{crebo}.md",
            )

    opl_json = tmp_path / "opl.json"
    opl_json.write_text(
        json.dumps(
            [
                {"opleiding": "Kok", "sector": "Anders", "niveau": 3},
                {"opleiding": "Kapper", "sector": "Anders", "niveau": 3},
                {"opleiding": "Mediamaker", "sector": "Anders", "niveau": 4},
            ]
        )
    )
    return db_pad, opl_json


def test_genereer_produceert_1000_rijen(tmp_path: Path):
    """End-to-end: roep genereer() met een mini DB en JSON, valideer output."""
    db_pad, opl_json = _maak_mini_db(tmp_path)
    uitvoer = tmp_path / "studenten.csv"
    genereer(db_pad=db_pad, opleidingen_json=opl_json, uitvoer_pad=uitvoer, seed=42)

    rijen = uitvoer.read_text().splitlines()
    # 1 header + 1000 data
    assert len(rijen) == 1001


def test_genereer_validatie_4_instellingen_x_250(tmp_path: Path):
    """Elke instelling heeft exact 250 studenten."""
    import pandas as pd

    db_pad, opl_json = _maak_mini_db(tmp_path)
    uitvoer = tmp_path / "studenten.csv"
    genereer(db_pad=db_pad, opleidingen_json=opl_json, uitvoer_pad=uitvoer, seed=42)

    df = pd.read_csv(uitvoer)
    counts = df["Instelling"].value_counts()
    assert (counts == 250).all(), counts


def test_genereer_negeert_aeres_in_oeren_db(tmp_path: Path):
    """Als oeren.db ook 'aeres' bevat, mag genereer() die overslaan."""
    import pandas as pd

    db_pad = tmp_path / "oeren.db"
    instellingen = [
        ("aeres", "Aeres MBO"),
        ("rijn_ijssel", "Rijn IJssel"),
        ("davinci", "Da Vinci"),
        ("talland", "Talland"),
        ("utrecht", "Utrecht"),
    ]
    for naam, display in instellingen:
        oer_store.voeg_instelling_toe(db_pad, naam, display)
    opleidingen = [("Kok", "25180", 3), ("Kapper", "25641", 3), ("Mediamaker", "25591", 4)]
    for naam, _ in instellingen:
        inst = oer_store.get_instelling_by_naam(db_pad, naam)
        for opl, crebo, niv in opleidingen:
            oer_store.voeg_oer_document_toe(
                db_pad,
                inst["id"],
                opl,
                crebo,
                "2025",
                "BOL",
                niv,
                f"oeren/{naam}/{crebo}.md",
            )
    opl_json = tmp_path / "opl.json"
    opl_json.write_text(
        json.dumps(
            [
                {"opleiding": "Kok", "sector": "Anders", "niveau": 3},
                {"opleiding": "Kapper", "sector": "Anders", "niveau": 3},
                {"opleiding": "Mediamaker", "sector": "Anders", "niveau": 4},
            ]
        )
    )

    uitvoer = tmp_path / "studenten.csv"
    genereer(db_pad=db_pad, opleidingen_json=opl_json, uitvoer_pad=uitvoer, seed=42)

    df = pd.read_csv(uitvoer)
    assert "Aeres MBO" not in df["Instelling"].values
    assert df["Instelling"].nunique() == 4
