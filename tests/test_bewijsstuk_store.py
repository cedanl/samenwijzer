"""Tests voor samenwijzer.bewijsstuk_store."""

from pathlib import Path

import pytest

from samenwijzer.bewijsstuk_store import (
    MAX_GROOTTE_BYTES,
    TOEGESTANE_EXTENSIES,
    BewijsstukFout,
    open_bestand,
    opslaan,
    verwijderen,
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "bewijsstukken"


def test_opslaan_legt_bestand_in_studentmap(root: Path) -> None:
    pad = opslaan(
        studentnummer="S001",
        bestandsnaam="stage.pdf",
        inhoud=b"%PDF-1.4 dummy",
        root=root,
    )
    abs_pad = root / pad
    assert abs_pad.exists()
    assert abs_pad.read_bytes() == b"%PDF-1.4 dummy"
    assert pad.startswith("S001/")
    assert pad.endswith(".pdf")


def test_opslaan_genereert_uuid_naam_dus_geen_collisions(root: Path) -> None:
    pad_a = opslaan("S001", "zelfde.pdf", b"a", root=root)
    pad_b = opslaan("S001", "zelfde.pdf", b"b", root=root)
    assert pad_a != pad_b


def test_opslaan_weigert_ongeldige_extensie(root: Path) -> None:
    with pytest.raises(BewijsstukFout, match="extensie"):
        opslaan("S001", "virus.exe", b"x", root=root)


def test_opslaan_weigert_grootte_boven_limiet(root: Path) -> None:
    inhoud = b"x" * (MAX_GROOTTE_BYTES + 1)
    with pytest.raises(BewijsstukFout, match="grootte"):
        opslaan("S001", "groot.pdf", inhoud, root=root)


def test_opslaan_weigert_ongeldig_studentnummer(root: Path) -> None:
    with pytest.raises(BewijsstukFout, match="studentnummer"):
        opslaan("../etc", "x.pdf", b"x", root=root)


def test_open_bestand_buiten_root_geweigerd(root: Path, tmp_path: Path) -> None:
    buiten = tmp_path / "buiten.pdf"
    buiten.write_bytes(b"geheim")
    with pytest.raises(BewijsstukFout, match="buiten"):
        open_bestand("../buiten.pdf", root=root)


def test_verwijderen_verwijdert_bestand(root: Path) -> None:
    pad = opslaan("S001", "weg.pdf", b"x", root=root)
    verwijderen(pad, root=root)
    assert not (root / pad).exists()


def test_verwijderen_van_pad_buiten_root_geweigerd(root: Path) -> None:
    with pytest.raises(BewijsstukFout, match="buiten"):
        verwijderen("../buiten.pdf", root=root)


def test_toegestane_extensies_zijn_pdf_jpg_png_docx_xlsx() -> None:
    assert TOEGESTANE_EXTENSIES == frozenset(
        {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".xlsx"}
    )
