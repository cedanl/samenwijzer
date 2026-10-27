import sqlite3

import pytest

from validatie_samenwijzer.db import (
    get_alle_oers_met_instelling,
    get_instelling_by_naam,
    get_instelling_display_namen,
    get_kerntaak_scores_by_student_id,
    get_kerntaken_by_oer_id,
    get_mentor_by_naam,
    get_oer_document,
    get_oer_ids_by_mentor_id,
    get_oer_met_instelling,
    get_oer_status_per_instelling,
    get_student_by_id,
    get_student_by_studentnummer,
    get_studenten_by_mentor_id,
    init_db,
    markeer_geindexeerd,
    update_oer_bestandspad,
    voeg_instelling_toe,
    voeg_kerntaak_toe,
    voeg_mentor_toe,
    voeg_oer_document_toe,
    voeg_student_kerntaak_score_toe,
    voeg_student_toe,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


def test_init_db_maakt_tabellen_aan(conn):
    rijen = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    tabellen = {r[0] for r in rijen}
    assert {
        "instellingen",
        "oer_documenten",
        "kerntaken",
        "mentoren",
        "mentor_oer",
        "studenten",
        "student_kerntaak_scores",
        "instelling_documenten",
        "documenten",
    } <= tabellen


def test_instelling_crud(conn):
    voeg_instelling_toe(conn, naam="aeres", display_naam="Aeres MBO")
    inst = get_instelling_by_naam(conn, "aeres")
    assert inst["display_naam"] == "Aeres MBO"
    assert get_instelling_by_naam(conn, "onbekend") is None


def test_oer_document_crud(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    inst = get_instelling_by_naam(conn, "rijn")
    oer_id = voeg_oer_document_toe(
        conn,
        instelling_id=inst["id"],
        opleiding="Verzorgende IG",
        crebo="25655",
        cohort="2025",
        leerweg="BOL",
        bestandspad="oeren/test.pdf",
    )
    oer = get_oer_document(conn, inst["id"], crebo="25655", cohort="2025", leerweg="BOL")
    assert oer["id"] == oer_id
    assert oer["opleiding"] == "Verzorgende IG"
    assert oer["geindexeerd"] == 0
    markeer_geindexeerd(conn, oer_id)
    oer2 = get_oer_document(conn, inst["id"], "25655", "2025", "BOL")
    assert oer2["geindexeerd"] == 1


def test_init_db_migreert_oude_check_tabel(conn):
    """Een instelling_documenten-tabel met de oude CHECK wordt herbouwd zonder CHECK."""
    conn.execute("DROP TABLE instelling_documenten")
    conn.execute(
        """CREATE TABLE instelling_documenten (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               instelling_id INTEGER NOT NULL REFERENCES instellingen(id),
               soort TEXT NOT NULL CHECK (soort IN ('examenreglement', 'begeleidingsbeleid')),
               titel TEXT NOT NULL, bestandspad TEXT NOT NULL,
               geindexeerd INTEGER NOT NULL DEFAULT 0,
               toegevoegd_op TEXT NOT NULL DEFAULT (datetime('now')),
               UNIQUE (instelling_id, soort))"""
    )
    conn.commit()
    init_db(conn)  # moet de oude-CHECK-tabel detecteren en herbouwen
    voeg_instelling_toe(conn, "davinci", "Da Vinci College")
    inst = get_instelling_by_naam(conn, "davinci")
    # Een soort die de oude CHECK zou weigeren, moet nu werken.
    conn.execute(
        "INSERT INTO instelling_documenten (instelling_id, soort, titel, bestandspad)"
        " VALUES (?, 'studentenstatuut', 't', 's.pdf')",
        (inst["id"],),
    )
    conn.commit()
    init_db(conn)  # migratie neemt de rij over
    assert (
        conn.execute("SELECT COUNT(*) FROM documenten WHERE soort = 'studentenstatuut'").fetchone()[
            0
        ]
        == 1
    )


def test_oer_document_gescheiden_per_instelling(conn):
    """Twee instellingen met hetzelfde crebo/cohort/leerweg krijgen aparte OER-records."""
    voeg_instelling_toe(conn, "talland", "Talland")
    voeg_instelling_toe(conn, "roc_utrecht", "ROC Utrecht")
    talland = get_instelling_by_naam(conn, "talland")
    roc = get_instelling_by_naam(conn, "roc_utrecht")

    id_talland = voeg_oer_document_toe(
        conn,
        talland["id"],
        "Sport en bewegingsleider",
        "25908",
        "2025",
        "BOL",
        "oeren/talland/25908BOL2025.pdf",
    )
    id_roc = voeg_oer_document_toe(
        conn,
        roc["id"],
        "Sport en bewegingsleider",
        "25908",
        "2025",
        "BOL",
        "oeren/roc_utrecht/25908BOL2025.pdf",
    )

    assert id_talland != id_roc
    oer_t = get_oer_document(conn, talland["id"], "25908", "2025", "BOL")
    oer_r = get_oer_document(conn, roc["id"], "25908", "2025", "BOL")
    assert oer_t["id"] == id_talland
    assert oer_r["id"] == id_roc
    assert oer_t["bestandspad"] != oer_r["bestandspad"]


def test_update_oer_bestandspad(conn):
    voeg_instelling_toe(conn, "da_vinci", "Da Vinci College")
    inst = get_instelling_by_naam(conn, "da_vinci")
    oer_id = voeg_oer_document_toe(
        conn,
        instelling_id=inst["id"],
        opleiding="Zorg",
        crebo="25168",
        cohort="2025",
        leerweg="BOL",
        bestandspad="oeren/25168BOL2025.txt",
    )
    update_oer_bestandspad(conn, oer_id, "oeren/25168BOL2025.pdf")
    oer = get_oer_document(conn, inst["id"], "25168", "2025", "BOL")
    assert oer["bestandspad"] == "oeren/25168BOL2025.pdf"


def test_kerntaken_crud(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    inst = get_instelling_by_naam(conn, "rijn")
    oer_id = voeg_oer_document_toe(
        conn, inst["id"], "Verzorgende IG", "25655", "2025", "BOL", "pad.pdf"
    )
    voeg_kerntaak_toe(
        conn,
        oer_id=oer_id,
        code="B1-K1",
        naam="Verpleegkundige zorg",
        type="kerntaak",
        volgorde=1,
    )
    voeg_kerntaak_toe(
        conn,
        oer_id=oer_id,
        code="B1-K1-W1",
        naam="Zorg plannen",
        type="werkproces",
        volgorde=2,
    )
    kt_lijst = get_kerntaken_by_oer_id(conn, oer_id)
    assert len(kt_lijst) == 2
    assert kt_lijst[0]["code"] == "B1-K1"


def test_voeg_kerntaak_toe_is_idempotent(conn):
    """UNIQUE(oer_id, type, naam) blokkeert duplicate inserts. De helper
    moet bij conflict het bestaande id teruggeven, niet None of een crash —
    callers (seed.py, ingest) gebruiken de return value om scores te koppelen."""
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    inst = get_instelling_by_naam(conn, "rijn")
    oer_id = voeg_oer_document_toe(conn, inst["id"], "VZ", "25655", "2025", "BOL", "pad.pdf")
    eerste = voeg_kerntaak_toe(
        conn,
        oer_id=oer_id,
        code="B1-K1",
        naam="Verpleegkundige zorg",
        type="kerntaak",
        volgorde=1,
    )
    # Tweede call met andere volgorde — INSERT OR IGNORE laat de oorspronkelijke
    # waarde staan; dat documenteert het contract voor toekomstige callers.
    tweede = voeg_kerntaak_toe(
        conn,
        oer_id=oer_id,
        code="B1-K1",
        naam="Verpleegkundige zorg",
        type="kerntaak",
        volgorde=99,
    )
    assert eerste == tweede
    assert isinstance(tweede, int)
    rijen = get_kerntaken_by_oer_id(conn, oer_id)
    assert len(rijen) == 1
    assert rijen[0]["volgorde"] == 1  # IGNORE behoudt eerste insert


def test_mentor_en_student_crud(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    inst = get_instelling_by_naam(conn, "rijn")
    oer_id = voeg_oer_document_toe(
        conn, inst["id"], "Verzorgende IG", "25655", "2025", "BOL", "pad.pdf"
    )

    mentor_id = voeg_mentor_toe(
        conn, naam="Jansen", wachtwoord_hash="abc123", instelling_id=inst["id"]
    )
    mentor = get_mentor_by_naam(conn, "Jansen")
    assert mentor["id"] == mentor_id

    voeg_student_toe(
        conn,
        studentnummer="100001",
        naam="Fatima",
        wachtwoord_hash="def456",
        instelling_id=inst["id"],
        oer_id=oer_id,
        mentor_id=mentor_id,
        leeftijd=19,
        geslacht="V",
        klas="VZ-1A",
        voortgang=0.54,
        bsa_behaald=37.0,
        bsa_vereist=60.0,
        absence_unauthorized=8.0,
        absence_authorized=2.0,
        vooropleiding="VMBO_TL",
        sector="Zorgenwelzijn",
        dropout=False,
    )
    student = get_student_by_studentnummer(conn, "100001")
    assert student["naam"] == "Fatima"
    assert student["voortgang"] == pytest.approx(0.54)
    assert get_student_by_id(conn, student["id"])["studentnummer"] == "100001"
    assert get_student_by_id(conn, 99999) is None

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


def test_get_instelling_display_namen(conn):
    assert get_instelling_display_namen(conn) == []
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    voeg_instelling_toe(conn, "da_vinci", "Da Vinci College")
    assert get_instelling_display_namen(conn) == ["Da Vinci College", "Rijn IJssel"]


def test_get_oer_met_instelling_geeft_join_terug(conn):
    voeg_instelling_toe(conn, "da_vinci", "Da Vinci College")
    dv = get_instelling_by_naam(conn, "da_vinci")
    oer_id = voeg_oer_document_toe(conn, dv["id"], "Kok", "25168", "2025", "BBL", "p.pdf")
    oer = get_oer_met_instelling(conn, oer_id)
    assert oer["opleiding"] == "Kok"  # uit oer_documenten (o.*)
    assert oer["display_naam"] == "Da Vinci College"  # uit instellingen (join)
    assert oer["naam"] == "da_vinci"
    assert get_oer_met_instelling(conn, 99999) is None


def test_get_oer_status_per_instelling(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    inst = get_instelling_by_naam(conn, "rijn")
    a = voeg_oer_document_toe(conn, inst["id"], "VZ", "25655", "2025", "BOL", "p1.pdf")
    voeg_oer_document_toe(conn, inst["id"], "Kok", "25168", "2025", "BBL", "p2.pdf")
    markeer_geindexeerd(conn, a)
    rijen = get_oer_status_per_instelling(conn)
    assert len(rijen) == 1
    assert rijen[0]["display_naam"] == "Rijn IJssel"
    assert rijen[0]["totaal"] == 2
    assert rijen[0]["geindexeerd"] == 1


def test_init_db_voegt_content_hash_kolom_toe(conn):
    for tabel in ("oer_documenten", "instelling_documenten"):
        kolommen = {r[1] for r in conn.execute(f"PRAGMA table_info({tabel})")}
        assert "content_hash" in kolommen


def test_init_db_migratie_is_idempotent_en_behoudt_data():
    """ALTER TABLE ADD COLUMN op een bestaande tabel mét data mag niet DROPpen."""
    import sqlite3

    from validatie_samenwijzer.db import init_db

    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    # Oud schema: oer_documenten ZONDER content_hash, met één rij.
    c.executescript(
        """
        CREATE TABLE instellingen (id INTEGER PRIMARY KEY, naam TEXT, display_naam TEXT);
        CREATE TABLE oer_documenten (
            id INTEGER PRIMARY KEY AUTOINCREMENT, instelling_id INTEGER NOT NULL,
            opleiding TEXT NOT NULL, crebo TEXT NOT NULL, cohort TEXT NOT NULL,
            leerweg TEXT NOT NULL, bestandspad TEXT NOT NULL,
            geindexeerd INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO instellingen (id, naam, display_naam) VALUES (1, 'deltion', 'Deltion');
        INSERT INTO oer_documenten (instelling_id, opleiding, crebo, cohort, leerweg, bestandspad)
            VALUES (1, 'Kok', '25180', '2025', 'BOL', 'x.md');
        """
    )
    c.commit()
    init_db(c)  # eerste keer: voegt kolom toe
    init_db(c)  # tweede keer: idempotent, geen fout
    rij = c.execute("SELECT crebo, content_hash FROM oer_documenten").fetchone()
    assert rij["crebo"] == "25180"  # rij behouden, niet ge-DROPt
    assert rij["content_hash"] is None  # nieuwe kolom, nog leeg
    c.close()


def test_set_oer_content_hash(conn):
    from validatie_samenwijzer.db import (
        set_oer_content_hash,
        voeg_instelling_toe,
        voeg_oer_document_toe,
    )

    inst = voeg_instelling_toe(conn, "deltion", "Deltion")
    oer_id = voeg_oer_document_toe(conn, inst, "Kok", "25180", "2025", "BOL", "x.md")
    set_oer_content_hash(conn, oer_id, "abc123")
    assert (
        conn.execute("SELECT content_hash FROM oer_documenten WHERE id = ?", (oer_id,)).fetchone()[
            0
        ]
        == "abc123"
    )


def test_student_kerntaak_score(conn):
    voeg_instelling_toe(conn, "rijn", "Rijn IJssel")
    inst = get_instelling_by_naam(conn, "rijn")
    oer_id = voeg_oer_document_toe(conn, inst["id"], "VZ", "25655", "2025", "BOL", "pad.pdf")
    mentor_id = voeg_mentor_toe(conn, "Mentor", "hash", inst["id"])
    voeg_student_toe(
        conn,
        "100001",
        "Fatima",
        "hash",
        inst["id"],
        oer_id,
        mentor_id,
        19,
        "V",
        "klas",
        0.5,
        30.0,
        60.0,
        0.0,
        0.0,
        "VMBO_TL",
        "Zorg",
        False,
    )
    student = get_student_by_studentnummer(conn, "100001")
    kt_id = voeg_kerntaak_toe(conn, oer_id, "B1-K1", "Zorg", "kerntaak", 1)
    voeg_student_kerntaak_score_toe(conn, student_id=student["id"], kerntaak_id=kt_id, score=72.5)
    scores = get_kerntaak_scores_by_student_id(conn, student["id"])
    assert len(scores) == 1
    assert scores[0]["score"] == pytest.approx(72.5)
    assert scores[0]["naam"] == "Zorg"


# ── Soortenregister ───────────────────────────────────────────────────────────


def test_soorten_bevat_bestaande_en_nieuwe_soorten():
    from validatie_samenwijzer.db import SOORTEN

    bestaand = {
        "examenreglement", "begeleidingsbeleid", "studentenstatuut", "bindend_studieadvies",
        "klachtenregeling", "gedragscode", "algemene_informatie", "privacyreglement",
        "pestprotocol", "meldcode", "ict_reglement", "gedragsregeling",
    }  # fmt: skip
    nieuw = {
        "examenplan", "nominale_lijn", "studiegids", "onderwijsplan", "praktijkovereenkomst",
        "schoolkosten", "veiligheidsplan", "protocol", "keuzedelen", "studiekeuzegids", "overig",
    }  # fmt: skip
    assert (bestaand | nieuw) <= set(SOORTEN)


def test_examenplan_is_opleidingsgebonden_en_examenreglement_instellingsbreed():
    from validatie_samenwijzer.db import SOORTEN

    assert SOORTEN["examenplan"].bereik == "opleiding"
    assert SOORTEN["nominale_lijn"].bereik == "opleiding"
    assert SOORTEN["examenreglement"].bereik == "instelling"
    assert SOORTEN["examenreglement"].juridisch is True
    assert SOORTEN["schoolkosten"].juridisch is False


def test_begeleidingsbeleid_blijft_alleen_ingelogd_zichtbaar():
    from validatie_samenwijzer.db import SOORTEN

    assert SOORTEN["begeleidingsbeleid"].zichtbaarheid == "ingelogd"
    assert SOORTEN["examenreglement"].zichtbaarheid == "publiek"


def test_openbare_schooldocumenten_zijn_publiek():
    """Statuut, BSA, klachtenregeling, gedragscode en algemene info staan openbaar op de
    schoolsites en horen dus ook in de publieke chat (besluit D2)."""
    from validatie_samenwijzer.db import _VRIJGEGEVEN_SOORTEN, SOORTEN

    for soort in _VRIJGEGEVEN_SOORTEN:
        assert SOORTEN[soort].zichtbaarheid == "publiek", soort


def test_init_db_zet_vrijgegeven_soorten_van_ingelogd_naar_publiek():
    """Bestaande rijen met de oude registerwaarde volgen het register; begeleidingsbeleid niet."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    voeg_instelling_toe(c, "curio", "Curio")
    inst = get_instelling_by_naam(c, "curio")["id"]
    c.execute(
        "INSERT INTO documenten (instelling_id, soort, bereik, titel, bestandspad, zichtbaarheid)"
        " VALUES (?, 'studentenstatuut', 'instelling', 's', 's.md', 'ingelogd'),"
        " (?, 'begeleidingsbeleid', 'instelling', 'b', 'b.md', 'ingelogd')",
        (inst, inst),
    )
    c.commit()
    init_db(c)
    rijen = c.execute("SELECT soort, zichtbaarheid FROM documenten ORDER BY soort").fetchall()
    assert [tuple(r) for r in rijen] == [
        ("begeleidingsbeleid", "ingelogd"),
        ("studentenstatuut", "publiek"),
    ]
    c.close()


def test_instelling_soorten_blijft_label_mapping_voor_instellingsbrede_soorten():
    from validatie_samenwijzer.db import INSTELLING_SOORTEN, SOORTEN

    assert INSTELLING_SOORTEN["examenreglement"] == "Examenreglement"
    assert "examenplan" not in INSTELLING_SOORTEN  # opleidingsgebonden
    assert set(INSTELLING_SOORTEN) == {k for k, v in SOORTEN.items() if v.bereik == "instelling"}


# ── Documenten (opvolger van instelling_documenten) ───────────────────────────


def _inst(conn, naam="curio", display="Curio"):
    voeg_instelling_toe(conn, naam, display)
    return get_instelling_by_naam(conn, naam)["id"]


def test_meerdere_documenten_zelfde_soort(conn):
    from validatie_samenwijzer.db import voeg_document_toe

    inst = _inst(conn)
    a = voeg_document_toe(conn, inst, "protocol", "Kluiscontrole", "a.md")
    b = voeg_document_toe(conn, inst, "protocol", "Pestprotocol KW", "b.md")
    assert a != b
    n = conn.execute("SELECT COUNT(*) FROM documenten WHERE soort = 'protocol'").fetchone()[0]
    assert n == 2


def test_zelfde_sleutel_twee_keer_geeft_een_rij_en_werkt_titel_bij(conn):
    from validatie_samenwijzer.db import voeg_document_toe

    inst = _inst(conn)
    eerste = voeg_document_toe(conn, inst, "examenplan", "oud", "x.md", crebo="25168", cohort="")
    tweede = voeg_document_toe(conn, inst, "examenplan", "nieuw", "x.md", crebo="25168", cohort="")
    assert eerste == tweede
    rij = conn.execute("SELECT titel, cohort FROM documenten WHERE id = ?", (eerste,)).fetchone()
    assert (rij["titel"], rij["cohort"]) == ("nieuw", "")  # lege string = alle cohorten


def test_bereik_en_zichtbaarheid_default_uit_register(conn):
    from validatie_samenwijzer.db import voeg_document_toe

    inst = _inst(conn)
    plan = voeg_document_toe(conn, inst, "examenplan", "t", "p.md", crebo="25168")
    beleid = voeg_document_toe(conn, inst, "begeleidingsbeleid", "t", "b.md")
    rij = conn.execute("SELECT bereik, zichtbaarheid FROM documenten WHERE id = ?", (plan,))
    assert tuple(rij.fetchone()) == ("opleiding", "publiek")
    rij = conn.execute("SELECT bereik, zichtbaarheid FROM documenten WHERE id = ?", (beleid,))
    assert tuple(rij.fetchone()) == ("instelling", "ingelogd")


def test_nieuw_document_is_standaard_ongereviewd_en_normaal(conn):
    from validatie_samenwijzer.db import voeg_document_toe

    inst = _inst(conn)
    doc = voeg_document_toe(conn, inst, "protocol", "t", "p.md")
    rij = conn.execute("SELECT gereviewd, gevoeligheid FROM documenten WHERE id = ?", (doc,))
    assert tuple(rij.fetchone()) == (0, "normaal")


def test_onbekende_soort_of_bereik_geeft_valueerror(conn):
    from validatie_samenwijzer.db import voeg_document_toe

    inst = _inst(conn)
    with pytest.raises(ValueError, match="Onbekende documentsoort"):
        voeg_document_toe(conn, inst, "willekeurig", "t", "x.md")
    with pytest.raises(ValueError, match="bereik"):
        voeg_document_toe(conn, inst, "protocol", "t", "x.md", bereik="overal")


def test_migratie_neemt_instelling_documenten_over():
    """Bestaande rijen uit de oude tabel komen in `documenten`: instellingsbreed, gereviewd."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    voeg_instelling_toe(c, "curio", "Curio")
    inst = get_instelling_by_naam(c, "curio")["id"]
    c.execute(
        "INSERT INTO instelling_documenten (instelling_id, soort, titel, bestandspad, geindexeerd)"
        " VALUES (?, 'examenreglement', 'Examenreglement Curio', 'e.pdf', 1),"
        " (?, 'begeleidingsbeleid', 'Beleid', 'b.pdf', 0)",
        (inst, inst),
    )
    c.commit()
    init_db(c)  # tweede init: migratie draait opnieuw en is idempotent
    init_db(c)
    rijen = c.execute(
        "SELECT soort, bereik, gereviewd, geindexeerd, zichtbaarheid FROM documenten ORDER BY soort"
    ).fetchall()
    assert [tuple(r) for r in rijen] == [
        ("begeleidingsbeleid", "instelling", 1, 0, "ingelogd"),
        ("examenreglement", "instelling", 1, 1, "publiek"),
    ]
    c.close()


def test_documenten_heeft_content_hash_kolom(conn):
    assert "content_hash" in {r[1] for r in conn.execute("PRAGMA table_info(documenten)")}


def test_markeer_en_hash_voor_document(conn):
    from validatie_samenwijzer.db import (
        markeer_document_geindexeerd,
        set_document_content_hash,
        voeg_document_toe,
    )

    inst = _inst(conn)
    doc = voeg_document_toe(conn, inst, "protocol", "t", "p.md")
    markeer_document_geindexeerd(conn, doc)
    set_document_content_hash(conn, doc, "abc123")
    rij = conn.execute("SELECT geindexeerd, content_hash FROM documenten WHERE id = ?", (doc,))
    assert tuple(rij.fetchone()) == (1, "abc123")


def _toon(conn, inst, **kw):
    from validatie_samenwijzer.db import get_documenten_voor_context

    argumenten = {"crebo": "25168", "leerweg": "BOL", "cohort": "2025", "niveau": "publiek"}
    argumenten.update(kw)
    return [r["titel"] for r in get_documenten_voor_context(conn, inst, **argumenten)]


def _gereed(conn, inst, soort, titel, pad, **kw):
    """Voeg een document toe dat geïndexeerd én gereviewd is (zoals na ingest + review)."""
    from validatie_samenwijzer.db import (
        markeer_document_geindexeerd,
        voeg_document_toe,
    )

    doc = voeg_document_toe(conn, inst, soort, titel, pad, gereviewd=True, **kw)
    markeer_document_geindexeerd(conn, doc)
    return doc


def test_context_instellingsbreed_en_opleidingsgebonden_matchen(conn):
    inst = _inst(conn)
    _gereed(conn, inst, "examenreglement", "Reglement", "r.md")
    _gereed(conn, inst, "examenplan", "Plan 25168", "p1.md", crebo="25168", cohort="2025")
    _gereed(conn, inst, "examenplan", "Plan 99999", "p2.md", crebo="99999", cohort="2025")
    _gereed(
        conn, inst, "examenplan", "Plan 25168 cohort 2024", "p3.md", crebo="25168", cohort="2024"
    )
    assert set(_toon(conn, inst)) == {"Reglement", "Plan 25168"}


def test_context_lege_string_matcht_alle_cohorten_en_leerwegen(conn):
    inst = _inst(conn)
    _gereed(conn, inst, "nominale_lijn", "NML alle", "n.md", crebo="25168")
    assert _toon(conn, inst, cohort="2023", leerweg="BBL") == ["NML alle"]
    assert _toon(conn, inst, crebo="11111") == []


def test_context_sluit_ongereviewd_ongeindexeerd_en_uitgesloten_uit(conn):
    from validatie_samenwijzer.db import voeg_document_toe

    inst = _inst(conn)
    voeg_document_toe(conn, inst, "protocol", "ongereviewd", "a.md")  # gereviewd=0
    voeg_document_toe(conn, inst, "protocol", "ongeindexeerd", "b.md", gereviewd=True)
    uit = _gereed(conn, inst, "protocol", "uitgesloten", "c.md")
    conn.execute("UPDATE documenten SET gevoeligheid = 'uitgesloten' WHERE id = ?", (uit,))
    conn.commit()
    _gereed(conn, inst, "protocol", "ok", "d.md")
    assert _toon(conn, inst) == ["ok"]


def test_context_niveau_bepaalt_zichtbaarheid(conn):
    inst = _inst(conn)
    _gereed(conn, inst, "examenreglement", "publiek-doc", "a.md")
    _gereed(conn, inst, "begeleidingsbeleid", "ingelogd-doc", "b.md")
    _gereed(conn, inst, "protocol", "intern-doc", "c.md", zichtbaarheid="intern")
    assert _toon(conn, inst, niveau="publiek") == ["publiek-doc"]
    assert set(_toon(conn, inst, niveau="student")) == {"publiek-doc", "ingelogd-doc"}
    assert set(_toon(conn, inst, niveau="mentor")) == {"publiek-doc", "ingelogd-doc"}


def test_context_onbekend_niveau_geeft_valueerror(conn):
    inst = _inst(conn)
    with pytest.raises(ValueError, match="niveau"):
        _toon(conn, inst, niveau="admin")


def test_context_documenten_van_andere_instelling_tellen_niet(conn):
    a = _inst(conn, "curio", "Curio")
    b = _inst(conn, "deltion", "Deltion")
    _gereed(conn, a, "examenreglement", "van-a", "a.md")
    _gereed(conn, b, "examenreglement", "van-b", "b.md")
    assert _toon(conn, a) == ["van-a"]


def test_alleen_begeleidingsbeleid_buiten_de_publieke_chat():
    """Alle instellingsbrede soorten zijn publiek (openbare schooldocumenten, besluit D2),
    behalve het begeleidings-/welzijnsbeleid — dat blijft voor ingelogde student/mentor."""
    from validatie_samenwijzer.db import SOORTEN

    niet_publiek = {
        k for k, v in SOORTEN.items() if v.bereik == "instelling" and v.zichtbaarheid != "publiek"
    }
    assert niet_publiek == {"begeleidingsbeleid"}
