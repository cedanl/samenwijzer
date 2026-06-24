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


def test_tupels_uit_rows_filtert_op_instelling():
    rows = [
        {"crebo": "25180", "leerweg": "BOL", "cohort": "2025", "naam": "deltion"},
        {"crebo": "25099", "leerweg": "BBL", "cohort": "2025", "naam": "curio"},
    ]
    assert oer_catalogus._tupels_uit_rows(rows, "deltion") == {("25180", "BOL", "2025")}


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
