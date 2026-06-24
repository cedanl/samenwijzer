"""Tests voor de OER-catalogus-check. Geen netwerk: de pure diff + transform
worden getest met sample-data; de instelling-adapters (HTTP) zijn geïsoleerd."""

import sys
from pathlib import Path

from validatie_samenwijzer import oer_catalogus
from validatie_samenwijzer.oer_catalogus import CatalogusItem


def _item(crebo, leerweg, cohort, naam="x", instelling="deltion"):
    return CatalogusItem(crebo, leerweg, cohort, naam, instelling)


def test_nieuwe_oers_geeft_alleen_onbekende_tupels():
    catalogus = [_item("25180", "BOL", "2025"), _item("25180", "BOL", "2026")]
    db_tupels = {("25180", "BOL", "2025")}
    nieuw = oer_catalogus.nieuwe_oers(catalogus, db_tupels)
    assert [i.sleutel for i in nieuw] == [("25180", "BOL", "2026")]  # nieuw cohort zichtbaar


def test_nieuwe_oers_dedupliceert_op_sleutel():
    catalogus = [_item("25180", "BOL", "2026"), _item("25180", "BOL", "2026", naam="dubbel")]
    nieuw = oer_catalogus.nieuwe_oers(catalogus, set())
    assert [i.sleutel for i in nieuw] == [("25180", "BOL", "2026")]  # geen dubbel


def test_tupels_uit_rows_filtert_op_instelling():
    rows = [
        {"crebo": "25180", "leerweg": "BOL", "cohort": "2025", "naam": "deltion"},
        {"crebo": "25099", "leerweg": "BBL", "cohort": "2025", "naam": "curio"},
    ]
    assert oer_catalogus._tupels_uit_rows(rows, "deltion") == {("25180", "BOL", "2025")}


def test_diff_op_crebo_cohort_negeert_leerweg():
    # Aeres levert geen leerweg → diff op (crebo, cohort), anders valse "nieuw".
    velden = ("crebo", "cohort")
    rows = [{"crebo": "25981", "leerweg": "BOL", "cohort": "2026", "naam": "aeres"}]
    db_tupels = oer_catalogus._tupels_uit_rows(rows, "aeres", velden)
    assert db_tupels == {("25981", "2026")}  # leerweg weggelaten
    catalogus = [
        _item("25981", "onbekend", "2026", instelling="aeres"),  # hebben we al (op crebo+cohort)
        _item("25730", "onbekend", "2026", instelling="aeres"),  # nieuw
    ]
    nieuw = oer_catalogus.nieuwe_oers(catalogus, db_tupels, velden)
    assert [i.crebo for i in nieuw] == ["25730"]


def test_aeres_diff_sleutel_is_crebo_cohort():
    assert oer_catalogus._DIFF_SLEUTEL_VELDEN["aeres"] == ("crebo", "cohort")


_AERES_BASIS = "/-/media/aeres-mbo/files/regelingen-en-statuten"
_AERES_HTML = (
    f'<a href="{_AERES_BASIS}/2026-2027/examenplannen/'
    'examenplan-25981-medewerker-teelt-vastgesteld.pdf">x</a>\n'
    f'<a href="https://www.aeresmbo.nl{_AERES_BASIS}/2026-2027/examenplannen/'
    'examenplan-25730-bedrijfsleider-dierverzorging-vastgesteld.pdf">y</a>\n'
    f'<a href="{_AERES_BASIS}/2025-2026/'
    'examenplannen-teelt-en-loonwerk-25-26.pdf">gebundeld, overslaan</a>\n'
)


def test_parse_aeres_pakt_per_crebo_en_slaat_bundel_over():
    items = oer_catalogus._parse_aeres(_AERES_HTML)
    paren = sorted((i.crebo, i.cohort) for i in items)
    assert paren == [("25730", "2026"), ("25981", "2026")]  # cohort genormaliseerd; bundel weg
    assert all(i.instelling == "aeres" and i.leerweg == "onbekend" for i in items)


def test_items_naar_catalogus_slaat_none_over():
    raw = [{"id": 1}, {"id": 2}]

    def parse(item):  # simuleert fetch_deltion._record (None = onbruikbaar item)
        if item["id"] == 1:
            return {"crebo": "25180", "leerweg": "BOL", "cohort": "2026", "naam": "Kok"}
        return None

    uit = oer_catalogus._items_naar_catalogus(raw, "deltion", parse)
    assert len(uit) == 1
    assert uit[0] == CatalogusItem("25180", "BOL", "2026", "Kok", "deltion")


def test_haal_items_op_zonder_cohort_stuurt_leeg_filter():
    """cohort=None mag GEEN cohortfilter sturen (anders mis je nieuwe cohorten)."""
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    sys.path.insert(0, str(scripts_dir))
    import fetch_deltion

    verstuurd = {}

    class _FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [], "meta": {"total": 0}}

    class _FakeClient:
        def post(self, url, params, json):
            verstuurd.update(json)
            return _FakeResp()

    fetch_deltion.haal_items_op(_FakeClient(), None)
    assert verstuurd["filters"] == {}  # leeg = alle cohorten

    fetch_deltion.haal_items_op(_FakeClient(), "2026-2027")
    assert verstuurd["filters"] == {"cohort": ["2026-2027"]}
