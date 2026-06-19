"""nette_opleiding_naam: autoritatieve crebo-naam met string-fallback."""

import json

from validatie_samenwijzer import opleiding


def test_nette_naam_gebruikt_crebo_lookup(tmp_path, monkeypatch):
    asset = tmp_path / "opleidingsnamen.json"
    asset.write_text(json.dumps({"25180": "Kok"}), encoding="utf-8")
    monkeypatch.setenv("OPLEIDINGSNAMEN_PAD", str(asset))
    opleiding.laad_crebo_namen.cache_clear()

    assert opleiding.nette_opleiding_naam("25180", "25180BBL2025MJP-Kok-rommel") == "Kok"


def test_nette_naam_valt_terug_op_string_opschoner(tmp_path, monkeypatch):
    asset = tmp_path / "opleidingsnamen.json"
    asset.write_text(json.dumps({"25180": "Kok"}), encoding="utf-8")
    monkeypatch.setenv("OPLEIDINGSNAMEN_PAD", str(asset))
    opleiding.laad_crebo_namen.cache_clear()

    # crebo 99999 niet in de lookup → val terug op schoon_opleiding_naam
    verwacht = opleiding.schoon_opleiding_naam("23030_BOL_2025__Laboratoriumtechniek", "99999")
    assert (
        opleiding.nette_opleiding_naam("99999", "23030_BOL_2025__Laboratoriumtechniek") == verwacht
    )


def test_laad_crebo_namen_zonder_bestand_geeft_leeg(tmp_path, monkeypatch):
    monkeypatch.setenv("OPLEIDINGSNAMEN_PAD", str(tmp_path / "bestaat-niet.json"))
    opleiding.laad_crebo_namen.cache_clear()
    assert opleiding.laad_crebo_namen() == {}
