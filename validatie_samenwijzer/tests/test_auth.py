import sqlite3
import pytest
from validatie_samenwijzer.db import init_db, voeg_instelling_toe, voeg_oer_document_toe, \
    voeg_mentor_toe, voeg_student_toe
from validatie_samenwijzer.auth import hash_wachtwoord, login_student, login_mentor


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    voeg_instelling_toe(c, "rijn", "Rijn IJssel")
    inst = c.execute("SELECT id FROM instellingen WHERE naam='rijn'").fetchone()
    oer_id = voeg_oer_document_toe(c, inst["id"], "VZ", "25655", "2025", "BOL", "pad.pdf")
    wh = hash_wachtwoord("Welkom123")
    mentor_id = voeg_mentor_toe(c, "Jansen", wh, inst["id"])
    voeg_student_toe(c, "100001", "Fatima", wh, inst["id"], oer_id, mentor_id,
                     19, "V", "VZ-1A", 0.54, 37.0, 60.0, 8.0, 2.0, "VMBO_TL", "Zorg", False)
    yield c
    c.close()


def test_hash_wachtwoord_bevat_salt():
    h = hash_wachtwoord("test")
    assert ":" in h, "Hash moet salt:dk formaat hebben"
    salt_hex, dk_hex = h.split(":", 1)
    assert len(bytes.fromhex(salt_hex)) == 32
    assert len(bytes.fromhex(dk_hex)) == 32


def test_hash_wachtwoord_uniek_per_aanroep():
    assert hash_wachtwoord("test") != hash_wachtwoord("test")


def test_login_student_geldig(conn):
    student = login_student(conn, "100001", "Welkom123")
    assert student is not None
    assert student["naam"] == "Fatima"


def test_login_student_fout_wachtwoord(conn):
    assert login_student(conn, "100001", "verkeerd") is None


def test_login_student_onbekend(conn):
    assert login_student(conn, "999999", "Welkom123") is None


def test_login_mentor_geldig(conn):
    mentor = login_mentor(conn, "Jansen", "Welkom123")
    assert mentor is not None
    assert mentor["naam"] == "Jansen"


def test_login_mentor_fout_wachtwoord(conn):
    assert login_mentor(conn, "Jansen", "verkeerd") is None
