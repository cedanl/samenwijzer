import sqlite3
import pytest
from validatie_samenwijzer.db import init_db, voeg_instelling_toe, get_instelling_by_naam, \
    voeg_oer_document_toe, get_oer_document, voeg_mentor_toe, get_mentor_by_naam, \
    voeg_student_toe, get_student_by_studentnummer, get_studenten_by_mentor_id, \
    voeg_kerntaak_toe, get_kerntaken_by_oer_id, markeer_geindexeerd, \
    get_oer_ids_by_mentor_id, voeg_student_kerntaak_score_toe, \
    get_kerntaak_scores_by_student_id, update_oer_bestandspad, \
    get_alle_oers_met_instelling


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


def test_init_db_maakt_tabellen_aan(conn):
    tabellen = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"instellingen", "oer_documenten", "kerntaken", "mentoren", "mentor_oer",
            "studenten", "student_kerntaak_scores"} <= tabellen


def test_instelling_crud(conn):
    voeg_instelling_toe(conn, naam="aeres", display_naam="Aeres MBO")
    inst = get_instelling_by_naam(conn, "aeres")
    assert inst["display_naam"] == "Aeres MBO"
    assert get_instelling_by_naam(conn, "onbekend") is None


def test_oer_document_crud(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    inst = get_instelling_by_naam(conn, "rijn")
    oer_id = voeg_oer_document_toe(conn, instelling_id=inst["id"], opleiding="Verzorgende IG",
                                   crebo="25655", cohort="2025", leerweg="BOL",
                                   bestandspad="oeren/test.pdf")
    oer = get_oer_document(conn, inst["id"], crebo="25655", cohort="2025", leerweg="BOL")
    assert oer["id"] == oer_id
    assert oer["opleiding"] == "Verzorgende IG"
    assert oer["geindexeerd"] == 0
    markeer_geindexeerd(conn, oer_id)
    oer2 = get_oer_document(conn, inst["id"], "25655", "2025", "BOL")
    assert oer2["geindexeerd"] == 1


def test_oer_document_gescheiden_per_instelling(conn):
    """Twee instellingen met hetzelfde crebo/cohort/leerweg krijgen aparte OER-records."""
    voeg_instelling_toe(conn, "talland", "Talland")
    voeg_instelling_toe(conn, "roc_utrecht", "ROC Utrecht")
    talland = get_instelling_by_naam(conn, "talland")
    roc = get_instelling_by_naam(conn, "roc_utrecht")

    id_talland = voeg_oer_document_toe(conn, talland["id"], "Sport en bewegingsleider",
                                       "25908", "2025", "BOL", "oeren/talland/25908BOL2025.pdf")
    id_roc = voeg_oer_document_toe(conn, roc["id"], "Sport en bewegingsleider",
                                   "25908", "2025", "BOL", "oeren/roc_utrecht/25908BOL2025.pdf")

    assert id_talland != id_roc
    oer_t = get_oer_document(conn, talland["id"], "25908", "2025", "BOL")
    oer_r = get_oer_document(conn, roc["id"], "25908", "2025", "BOL")
    assert oer_t["id"] == id_talland
    assert oer_r["id"] == id_roc
    assert oer_t["bestandspad"] != oer_r["bestandspad"]


def test_update_oer_bestandspad(conn):
    voeg_instelling_toe(conn, "da_vinci", "Da Vinci College")
    inst = get_instelling_by_naam(conn, "da_vinci")
    oer_id = voeg_oer_document_toe(conn, instelling_id=inst["id"], opleiding="Zorg",
                                   crebo="25168", cohort="2025", leerweg="BOL",
                                   bestandspad="oeren/25168BOL2025.txt")
    update_oer_bestandspad(conn, oer_id, "oeren/25168BOL2025.pdf")
    oer = get_oer_document(conn, inst["id"], "25168", "2025", "BOL")
    assert oer["bestandspad"] == "oeren/25168BOL2025.pdf"


def test_kerntaken_crud(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    inst = get_instelling_by_naam(conn, "rijn")
    oer_id = voeg_oer_document_toe(conn, inst["id"], "Verzorgende IG", "25655", "2025", "BOL", "pad.pdf")
    kt_id = voeg_kerntaak_toe(conn, oer_id=oer_id, code="B1-K1", naam="Verpleegkundige zorg", type="kerntaak", volgorde=1)
    wp_id = voeg_kerntaak_toe(conn, oer_id=oer_id, code="B1-K1-W1", naam="Zorg plannen", type="werkproces", volgorde=2)
    kt_lijst = get_kerntaken_by_oer_id(conn, oer_id)
    assert len(kt_lijst) == 2
    assert kt_lijst[0]["code"] == "B1-K1"


def test_mentor_en_student_crud(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    inst = get_instelling_by_naam(conn, "rijn")
    oer_id = voeg_oer_document_toe(conn, inst["id"], "Verzorgende IG", "25655", "2025", "BOL", "pad.pdf")

    mentor_id = voeg_mentor_toe(conn, naam="Jansen", wachtwoord_hash="abc123", instelling_id=inst["id"])
    mentor = get_mentor_by_naam(conn, "Jansen")
    assert mentor["id"] == mentor_id

    voeg_student_toe(conn, studentnummer="100001", naam="Fatima", wachtwoord_hash="def456",
                     instelling_id=inst["id"], oer_id=oer_id, mentor_id=mentor_id,
                     leeftijd=19, geslacht="V", klas="VZ-1A", voortgang=0.54,
                     bsa_behaald=37.0, bsa_vereist=60.0, absence_unauthorized=8.0,
                     absence_authorized=2.0, vooropleiding="VMBO_TL", sector="Zorgenwelzijn",
                     dropout=False)
    student = get_student_by_studentnummer(conn, "100001")
    assert student["naam"] == "Fatima"
    assert student["voortgang"] == pytest.approx(0.54)

    studenten = get_studenten_by_mentor_id(conn, mentor_id)
    assert len(studenten) == 1
    assert studenten[0]["studentnummer"] == "100001"

    oer_ids = get_oer_ids_by_mentor_id(conn, mentor_id)
    assert oer_id in oer_ids


def test_get_alle_oers_met_instelling_geeft_join_terug(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    voeg_instelling_toe(conn, "da_vinci", "Da Vinci College")
    rijn = get_instelling_by_naam(conn, "rijn")
    dv = get_instelling_by_naam(conn, "da_vinci")
    voeg_oer_document_toe(conn, rijn["id"], "Verzorgende IG", "25655", "2025", "BOL", "p1.pdf")
    voeg_oer_document_toe(conn, dv["id"], "Kok", "25168", "2025", "BBL", "p2.pdf")

    rijen = get_alle_oers_met_instelling(conn)
    assert len(rijen) == 2
    display_namen = {r["display_naam"] for r in rijen}
    assert display_namen == {"Rijn IJssel", "Da Vinci College"}


def test_get_alle_oers_met_instelling_sorteert_op_display_naam(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    voeg_instelling_toe(conn, "aeres", "Aeres MBO")
    rijn = get_instelling_by_naam(conn, "rijn")
    aeres = get_instelling_by_naam(conn, "aeres")
    voeg_oer_document_toe(conn, rijn["id"], "Verzorgende IG", "25655", "2025", "BOL", "p1.pdf")
    voeg_oer_document_toe(conn, aeres["id"], "Dierenzorg", "97770", "2025", "BOL", "p2.pdf")

    rijen = get_alle_oers_met_instelling(conn)
    assert [r["display_naam"] for r in rijen] == ["Aeres MBO", "Rijn IJssel"]


def test_get_alle_oers_met_instelling_leeg(conn):
    assert get_alle_oers_met_instelling(conn) == []


def test_student_kerntaak_score(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    inst = get_instelling_by_naam(conn, "rijn")
    oer_id = voeg_oer_document_toe(conn, inst["id"], "VZ", "25655", "2025", "BOL", "pad.pdf")
    mentor_id = voeg_mentor_toe(conn, "Mentor", "hash", inst["id"])
    voeg_student_toe(conn, "100001", "Fatima", "hash", inst["id"], oer_id, mentor_id,
                     19, "V", "klas", 0.5, 30.0, 60.0, 0.0, 0.0, "VMBO_TL", "Zorg", False)
    student = get_student_by_studentnummer(conn, "100001")
    kt_id = voeg_kerntaak_toe(conn, oer_id, "B1-K1", "Zorg", "kerntaak", 1)
    voeg_student_kerntaak_score_toe(conn, student_id=student["id"], kerntaak_id=kt_id, score=72.5)
    scores = get_kerntaak_scores_by_student_id(conn, student["id"])
    assert len(scores) == 1
    assert scores[0]["score"] == pytest.approx(72.5)
    assert scores[0]["naam"] == "Zorg"
