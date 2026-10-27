"""Selectie en budget van documenten voor de chat-context."""

import sqlite3

import pytest

from validatie_samenwijzer.db import (
    get_instelling_by_naam,
    init_db,
    markeer_document_geindexeerd,
    voeg_document_toe,
    voeg_instelling_toe,
)
from validatie_samenwijzer.documenten import selecteer_documenten


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


def _instelling(conn, naam="curio"):
    voeg_instelling_toe(conn, naam, naam.title())
    return get_instelling_by_naam(conn, naam)["id"]


def _oer(conn, oer_id, instelling_id, crebo="25168", leerweg="BOL", cohort="2025"):
    """Een OER-rij met precies de velden die de selectie gebruikt."""
    return conn.execute(
        "SELECT ? AS id, ? AS instelling_id, ? AS crebo, ? AS leerweg, ? AS cohort,"
        " 'Curio' AS display_naam",
        (oer_id, instelling_id, crebo, leerweg, cohort),
    ).fetchone()


def _doc(conn, tmp_path, inst, soort, titel, tekst="tekst", **kw):
    """Gereviewd + geïndexeerd document met een echt bestand (tekst) op schijf."""
    pad = tmp_path / f"{titel.replace(' ', '_')}.md"
    if tekst is not None:
        pad.write_text(tekst, encoding="utf-8")
    kw.setdefault("gereviewd", True)
    doc_id = voeg_document_toe(conn, inst, soort, titel, str(pad), **kw)
    markeer_document_geindexeerd(conn, doc_id)
    return doc_id


def _titels(selectie, oer_id=1):
    return [d.kop for d in selectie.per_oer.get(oer_id, [])]


def test_opleidingsgebonden_alleen_bij_match(conn, tmp_path):
    inst = _instelling(conn)
    _doc(conn, tmp_path, inst, "examenplan", "plan_match", crebo="25168", cohort="2025")
    _doc(conn, tmp_path, inst, "examenplan", "plan_ander_crebo", crebo="99999", cohort="2025")
    _doc(conn, tmp_path, inst, "examenplan", "plan_ander_cohort", crebo="25168", cohort="2024")
    sel = selecteer_documenten(conn, [_oer(conn, 1, inst)], "publiek")
    assert [d.kop for d in sel.per_oer[1]] == ["Examenplan — plan_match [INFORMATIEF]"]


def test_lege_string_matcht_alle_cohorten_en_leerwegen(conn, tmp_path):
    inst = _instelling(conn)
    _doc(conn, tmp_path, inst, "nominale_lijn", "nml_alle", crebo="25168")
    oer = _oer(conn, 1, inst, leerweg="BBL", cohort="2023")
    sel = selecteer_documenten(conn, [oer], "publiek")
    assert len(sel.per_oer[1]) == 1


def test_dedupe_instellingsbreed_bij_twee_oers_van_dezelfde_instelling(conn, tmp_path):
    inst = _instelling(conn)
    _doc(conn, tmp_path, inst, "examenreglement", "reglement")
    oers = [_oer(conn, 1, inst, crebo="1"), _oer(conn, 2, inst, crebo="2")]
    sel = selecteer_documenten(conn, oers, "publiek")
    assert len(sel.per_oer.get(1, [])) == 1
    assert sel.per_oer.get(2, []) == []  # één keer opgenomen, niet per OER


def test_niveau_publiek_sluit_ingelogd_en_intern_uit(conn, tmp_path):
    inst = _instelling(conn)
    _doc(conn, tmp_path, inst, "examenreglement", "publiek_doc")
    _doc(conn, tmp_path, inst, "begeleidingsbeleid", "ingelogd_doc")
    _doc(conn, tmp_path, inst, "protocol", "intern_doc", zichtbaarheid="intern")
    oer = _oer(conn, 1, inst)
    assert len(selecteer_documenten(conn, [oer], "publiek").per_oer[1]) == 1
    assert len(selecteer_documenten(conn, [oer], "mentor").per_oer[1]) == 2


def test_ongereviewd_en_uitgesloten_komen_nooit_in_de_selectie(conn, tmp_path):
    inst = _instelling(conn)
    _doc(conn, tmp_path, inst, "protocol", "ongereviewd", gereviewd=False)
    uit = _doc(conn, tmp_path, inst, "protocol", "uitgesloten")
    conn.execute("UPDATE documenten SET gevoeligheid = 'uitgesloten' WHERE id = ?", (uit,))
    conn.commit()
    sel = selecteer_documenten(conn, [_oer(conn, 1, inst)], "publiek")
    assert sel.per_oer.get(1, []) == []


def test_budget_prioriteit_juridisch_eerst_en_afvallen_gelogd(conn, tmp_path):
    inst = _instelling(conn)
    _doc(conn, tmp_path, inst, "schoolkosten", "informatief_klein", tekst="i" * 10)
    _doc(conn, tmp_path, inst, "examenplan", "opleiding_doc", tekst="o" * 30, crebo="25168")
    _doc(conn, tmp_path, inst, "examenreglement", "juridisch_groot", tekst="j" * 60)
    sel = selecteer_documenten(conn, [_oer(conn, 1, inst)], "publiek", budget=100)
    assert [d.juridisch for d in sel.per_oer[1]] == [True, False, False]  # alles past
    sel = selecteer_documenten(conn, [_oer(conn, 1, inst)], "publiek", budget=65)
    assert [d.juridisch for d in sel.per_oer[1]] == [True]  # alleen het juridische past in 65
    assert set(sel.afgevallen) == {"opleiding_doc", "informatief_klein"}


def test_binnen_een_groep_gaat_het_kleinste_document_eerst(conn, tmp_path):
    inst = _instelling(conn)
    _doc(conn, tmp_path, inst, "protocol", "groot", tekst="g" * 50)
    _doc(conn, tmp_path, inst, "protocol", "klein", tekst="k" * 5)
    sel = selecteer_documenten(conn, [_oer(conn, 1, inst)], "publiek", budget=20)
    assert [d.kop for d in sel.per_oer[1]] == ["Protocol — klein [INFORMATIEF]"]
    assert sel.afgevallen == ["groot"]


def test_ontbrekend_bestand_wordt_overgeslagen_zonder_crash(conn, tmp_path):
    inst = _instelling(conn)
    _doc(conn, tmp_path, inst, "protocol", "weg", tekst=None)  # bestand bestaat niet
    sel = selecteer_documenten(conn, [_oer(conn, 1, inst)], "publiek")
    assert sel.per_oer.get(1, []) == [] and sel.afgevallen == []


def test_leeg_document_wordt_overgeslagen(conn, tmp_path):
    inst = _instelling(conn)
    _doc(conn, tmp_path, inst, "protocol", "leeg", tekst="   \n")
    sel = selecteer_documenten(conn, [_oer(conn, 1, inst)], "publiek")
    assert sel.per_oer.get(1, []) == []


def test_onbekend_niveau_geeft_valueerror(conn):
    with pytest.raises(ValueError, match="niveau"):
        selecteer_documenten(conn, [], "admin")


def test_budget_komt_uit_env_als_niet_meegegeven(conn, tmp_path, monkeypatch):
    inst = _instelling(conn)
    _doc(conn, tmp_path, inst, "protocol", "doc", tekst="x" * 50)
    monkeypatch.setenv("DOC_BUDGET_TEKENS", "10")
    sel = selecteer_documenten(conn, [_oer(conn, 1, inst)], "publiek")
    assert sel.per_oer.get(1, []) == [] and sel.afgevallen == ["doc"]


def test_kop_markeert_niet_juridische_documenten_als_informatief(conn, tmp_path):
    """Alleen juridische bronnen vereisen een woordelijk citaat; de rest is `[INFORMATIEF]`."""
    inst = _instelling(conn)
    _doc(conn, tmp_path, inst, "examenreglement", "Examenreglement Curio")
    _doc(conn, tmp_path, inst, "protocol", "Protocol kluiscontrole")
    sel = selecteer_documenten(conn, [_oer(conn, 1, inst)], "publiek")
    assert sorted(d.kop for d in sel.per_oer[1]) == [
        "Examenreglement",  # oude titel: instellingsnaam weg, juridisch → geen markering
        "Protocol — kluiscontrole [INFORMATIEF]",
    ]
