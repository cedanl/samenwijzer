"""Tests voor generate_synthetisch_data.py."""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from generate_synthetisch_data import (  # noqa: E402
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
