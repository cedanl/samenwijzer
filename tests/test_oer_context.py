"""Tests voor samenwijzer.oer_context."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from samenwijzer.oer_context import haal_oer_context_op, laad_oer_tekst

_MAX_TEKENS = 120_000


# ── laad_oer_tekst ────────────────────────────────────────────────────────────


def test_laad_oer_tekst_bestaand_bestand(tmp_path: Path) -> None:
    bestand = tmp_path / "oer.md"
    bestand.write_text("# OER inhoud\nKerntaak 1", encoding="utf-8")
    assert laad_oer_tekst(bestand) == "# OER inhoud\nKerntaak 1"


def test_laad_oer_tekst_niet_bestaand(tmp_path: Path) -> None:
    assert laad_oer_tekst(tmp_path / "bestaat_niet.md") == ""


def test_laad_oer_tekst_afkappen(tmp_path: Path) -> None:
    bestand = tmp_path / "lang.md"
    bestand.write_text("x" * (_MAX_TEKENS + 5000), encoding="utf-8")
    resultaat = laad_oer_tekst(bestand)
    assert len(resultaat) == _MAX_TEKENS


def test_laad_oer_tekst_relatief_pad_bestaat_niet() -> None:
    # Relatief pad dat niet bestaat → lege string (geen exception)
    assert laad_oer_tekst("oeren/niet_bestaand/oer.md") == ""


# ── haal_oer_context_op ───────────────────────────────────────────────────────


def test_haal_oer_context_op_geen_db(tmp_path: Path) -> None:
    """Geeft lege string terug als oeren.db niet bestaat."""
    student = {"instelling": "da_vinci", "crebo": "25491", "leerweg": "BOL", "cohort": "2024"}
    with patch("samenwijzer.oer_context._DB_PAD", tmp_path / "bestaat_niet.db"):
        resultaat = haal_oer_context_op(student)
    assert resultaat == ""


def _maak_test_db(db_pad: Path, bestandspad: str) -> None:
    """Bouw een minimale in-memory-achtige oeren.db op schijf voor tests."""
    conn = sqlite3.connect(db_pad)
    conn.executescript("""
        CREATE TABLE instellingen (id INTEGER PRIMARY KEY, naam TEXT, display_naam TEXT);
        CREATE TABLE oer_documenten (
            id INTEGER PRIMARY KEY,
            instelling_id INTEGER,
            opleiding TEXT,
            crebo TEXT,
            cohort TEXT,
            leerweg TEXT,
            niveau INTEGER,
            bestandspad TEXT
        );
    """)
    conn.execute(
        "INSERT INTO instellingen VALUES (1, 'da_vinci', 'Da Vinci')",
    )
    conn.execute(
        "INSERT INTO oer_documenten VALUES (1, 1, 'Verzorgende IG', '25491', '2024', 'BOL', 3, ?)",
        (bestandspad,),
    )
    conn.commit()
    conn.close()


def test_haal_oer_context_op_student_niet_gevonden(tmp_path: Path) -> None:
    """Geeft lege string terug als student niet in de catalog staat."""
    db_pad = tmp_path / "oeren.db"
    _maak_test_db(db_pad, "oeren/da_vinci/oer.md")

    student = {"instelling": "rijn_ijssel", "crebo": "99999", "leerweg": "BOL", "cohort": "2024"}
    with patch("samenwijzer.oer_context._DB_PAD", db_pad):
        resultaat = haal_oer_context_op(student)
    assert resultaat == ""


def test_haal_oer_context_op_bestand_niet_beschikbaar(tmp_path: Path) -> None:
    """DB aanwezig maar OER-bestand ontbreekt → lege string."""
    db_pad = tmp_path / "oeren.db"
    _maak_test_db(db_pad, "oeren/da_vinci/niet_bestaand.md")

    student = {"instelling": "da_vinci", "crebo": "25491", "leerweg": "BOL", "cohort": "2024"}
    with patch("samenwijzer.oer_context._DB_PAD", db_pad):
        resultaat = haal_oer_context_op(student)
    assert resultaat == ""


def test_haal_oer_context_op_met_bestand(tmp_path: Path) -> None:
    """Geeft OER-tekst terug als DB en bestand beide beschikbaar zijn."""
    db_pad = tmp_path / "oeren.db"
    oer_bestand = tmp_path / "oer.md"
    oer_bestand.write_text("# Kerntaak 1\nWerkproces 1.1", encoding="utf-8")

    _maak_test_db(db_pad, str(oer_bestand))  # absoluut pad om project-root-lookup te omzeilen

    student = {"instelling": "da_vinci", "crebo": "25491", "leerweg": "BOL", "cohort": "2024"}
    with patch("samenwijzer.oer_context._DB_PAD", db_pad):
        resultaat = haal_oer_context_op(student)
    assert "Kerntaak 1" in resultaat
    assert "Werkproces 1.1" in resultaat


def test_haal_oer_context_op_pandas_series(tmp_path: Path) -> None:
    """Werkt ook met een pandas Series als student_row."""
    import pandas as pd

    db_pad = tmp_path / "oeren.db"
    oer_bestand = tmp_path / "oer.md"
    oer_bestand.write_text("OER-inhoud voor pandas test", encoding="utf-8")
    _maak_test_db(db_pad, str(oer_bestand))

    student_series = pd.Series(
        {"instelling": "da_vinci", "crebo": "25491", "leerweg": "BOL", "cohort": "2024"}
    )
    with patch("samenwijzer.oer_context._DB_PAD", db_pad):
        resultaat = haal_oer_context_op(student_series)
    assert "OER-inhoud" in resultaat
