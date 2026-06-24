"""Tests voor het KD-bundelmanifest. Geen netwerk: werkt op nep-zips in tmp_path."""

import json

import pytest

from validatie_samenwijzer import kd_bundel


@pytest.fixture
def bundel(tmp_path):
    """Een nep-bundel: 4 'zips' + crebolijsten (incl. de 2025april-variant)."""
    (tmp_path / "ae.zip").write_bytes(b"ae-v1")
    (tmp_path / "fl.zip").write_bytes(b"fl-v1")
    (tmp_path / "mr.zip").write_bytes(b"mr-v1")
    (tmp_path / "sz.zip").write_bytes(b"sz-v1")
    lijsten = tmp_path / "lijsten"
    lijsten.mkdir()
    for naam in ("crebo_2024.xlsx", "crebo_2025.xlsx", "crebo_2025april.xlsx"):
        (lijsten / naam).write_bytes(b"x")
    return tmp_path


def test_nieuwste_crebolijst_jaar(bundel):
    assert kd_bundel.nieuwste_crebolijst_jaar(bundel) == 2025  # 2025april telt als 2025


def test_nieuwste_crebolijst_jaar_leeg(tmp_path):
    (tmp_path / "lijsten").mkdir()
    assert kd_bundel.nieuwste_crebolijst_jaar(tmp_path) is None


def test_zip_hashes_alleen_aanwezige(bundel):
    (bundel / "mr.zip").unlink()  # ontbrekende zip wordt overgeslagen
    hashes = kd_bundel.huidige_zip_hashes(bundel)
    assert set(hashes) == {"ae.zip", "fl.zip", "sz.zip"}


def test_schrijf_en_lees_manifest(bundel):
    geschreven = kd_bundel.schrijf_manifest(bundel, nu="2026-06-24T10:00:00+00:00")
    assert geschreven["crebolijst_jaar"] == 2025
    assert set(geschreven["zips"]) == {"ae.zip", "fl.zip", "mr.zip", "sz.zip"}
    op_schijf = json.loads((bundel / "bundle_manifest.json").read_text(encoding="utf-8"))
    assert op_schijf == geschreven


def test_status_geen_manifest(bundel):
    s = kd_bundel.bundel_status(bundel)
    assert s["toestand"] == "geen_manifest"
    assert s["crebolijst_jaar"] == 2025


def test_status_in_sync_na_schrijven(bundel):
    kd_bundel.schrijf_manifest(bundel, nu="2026-06-24T10:00:00+00:00")
    s = kd_bundel.bundel_status(bundel)
    assert s["toestand"] == "in_sync"
    assert s["gewijzigde_zips"] == []


def test_status_gewijzigd_bij_nieuwe_zip_inhoud(bundel):
    kd_bundel.schrijf_manifest(bundel, nu="2026-06-24T10:00:00+00:00")
    (bundel / "ae.zip").write_bytes(b"ae-v2-nieuwere-bundel")  # SBB-update
    s = kd_bundel.bundel_status(bundel)
    assert s["toestand"] == "gewijzigd"
    assert s["gewijzigde_zips"] == ["ae.zip"]
