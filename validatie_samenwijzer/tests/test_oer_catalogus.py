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


_RIJNIJSSEL_DOCS = "https://apicms.rijnijssel.nl/documents"
_RIJNIJSSEL_HTML = (
    f'<a href="{_RIJNIJSSEL_DOCS}/179/oer-2025-2026-ci-25633-mediavormgever.pdf">OER</a>\n'
    f'<a href="{_RIJNIJSSEL_DOCS}/194/EU_OER_2024_KAPPER_25641_BOL_BBL_3-7-24.pdf">OER</a>\n'
    # geen 5-cijferige crebo in de bestandsnaam → bewust overgeslagen (cheap subset)
    f'<a href="{_RIJNIJSSEL_DOCS}/186/vw-oer-bbk-bakkerij2025-bolbbl.pdf">OER</a>\n'
)


def test_parse_rijnijssel_pakt_crebo_cohort_uit_bestandsnaam():
    items = oer_catalogus._parse_rijnijssel(_RIJNIJSSEL_HTML)
    assert sorted((i.crebo, i.cohort) for i in items) == [("25633", "2025"), ("25641", "2024")]
    assert all(i.instelling == "rijn_ijssel" for i in items)


def test_parse_rijnijssel_slaat_over_zonder_crebo_of_cohort():
    # bestandsnaam zonder 5-cijferige crebo (alleen jaartallen) → niet goedkoop te bepalen
    naam = "OER_2025-2026_pedagogisch-werk-cohort-2025-bbl.pdf"
    html = f'<a href="{_RIJNIJSSEL_DOCS}/152/{naam}">x</a>'
    assert oer_catalogus._parse_rijnijssel(html) == []


def test_rijnijssel_diff_sleutel_is_crebo_cohort():
    assert oer_catalogus._DIFF_SLEUTEL_VELDEN["rijn_ijssel"] == ("crebo", "cohort")


def test_mbou_crebo_uit_tekst():
    # echte crebo-regels uit MBO Utrecht-PDF's (live geverifieerd)
    assert oer_catalogus._mbou_crebo_uit_tekst("voor crebo 25655 bestaat") == "25655"
    assert oer_catalogus._mbou_crebo_uit_tekst("Software developer (Crebonr. 25998)") == "25998"
    assert oer_catalogus._mbou_crebo_uit_tekst("CREBO: 25655") == "25655"  # colon-variant
    assert oer_catalogus._mbou_crebo_uit_tekst("geen nummer hier") is None


def test_mbou_cohort_uit_url():
    base = "https://mboutrecht.nl/wp-content/uploads/2025/05"
    # cohort = jaar vóór _OER_ in de bestandsnaam, NIET de uploadmaand (2025/05)
    assert oer_catalogus._mbou_cohort_uit_url(f"{base}/2024_OER_BOL_Verpleegkundige.pdf") == "2024"
    assert oer_catalogus._mbou_cohort_uit_url(f"{base}/2023_OER_Software-developer.pdf") == "2023"
    assert oer_catalogus._mbou_cohort_uit_url(f"{base}/geen-oer.pdf") is None


def test_mbou_pdf_urls_uit_html():
    base = "https://mboutrecht.nl/wp-content/uploads/2025/05"
    html = (
        f'<a href="{base}/2024_OER_BOL_Verpleegkundige.pdf">OER</a>'
        f'<a href="{base}/brochure.pdf">geen OER</a>'
    )
    urls = oer_catalogus._mbou_pdf_urls(html)
    assert urls == [f"{base}/2024_OER_BOL_Verpleegkundige.pdf"]


def test_utrecht_diff_sleutel_is_crebo_cohort():
    assert oer_catalogus._DIFF_SLEUTEL_VELDEN["utrecht"] == ("crebo", "cohort")


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


def test_bereken_content_hash_negeert_whitespace_verschillen():
    from validatie_samenwijzer.oer_catalogus import bereken_content_hash

    assert bereken_content_hash("hallo  wereld") == bereken_content_hash("hallo\n\nwereld\n")
    assert bereken_content_hash("hallo wereld") != bereken_content_hash("hallo werelt")
    # Deterministisch + hex SHA256 (64 tekens).
    h = bereken_content_hash("x")
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)
