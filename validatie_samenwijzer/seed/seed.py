"""Seed-script: testgebruikers en synthetische scores aanmaken."""

import random
from pathlib import Path

from dotenv import load_dotenv

from validatie_samenwijzer.auth import hash_wachtwoord
from validatie_samenwijzer.db import (
    get_connection,
    get_instelling_by_naam,
    get_student_by_studentnummer,
    init_db,
    koppel_mentor_oer,
    voeg_instelling_toe,
    voeg_kerntaak_toe,
    voeg_mentor_toe,
    voeg_oer_document_toe,
    voeg_student_kerntaak_score_toe,
    voeg_student_toe,
)

load_dotenv()

WW_HASH = hash_wachtwoord("Welkom123")
RNG = random.Random(42)


def seed(db_path: Path) -> None:
    conn = get_connection(db_path)
    init_db(conn)

    # Instellingen
    voeg_instelling_toe(conn, "rijn_ijssel", "Rijn IJssel")
    voeg_instelling_toe(conn, "davinci", "Da Vinci College")
    inst_rijn = get_instelling_by_naam(conn, "rijn_ijssel")
    inst_dv = get_instelling_by_naam(conn, "davinci")

    # OER documenten
    oer_vz_bol = voeg_oer_document_toe(
        conn, inst_rijn["id"], "Verzorgende IG", "25655", "2025", "BOL",
        "oeren/rijn_ijssel_oer/OER_2025-2026_Verzorgende-IG_BOL.pdf",
    )
    oer_kok_bbl = voeg_oer_document_toe(
        conn, inst_dv["id"], "Kok", "25180", "2025", "BBL",
        "oeren/davinci_oeren/25180BBL2025MJP-Kok.pdf",
    )

    # Kerntaken voor VZ-BOL
    kt1 = voeg_kerntaak_toe(
        conn, oer_vz_bol, "B1-K1", "Verpleegkundige zorg verlenen", "kerntaak", 0
    )
    kt2 = voeg_kerntaak_toe(
        conn, oer_vz_bol, "B1-K1-W1", "Zorg plannen en organiseren", "werkproces", 1
    )
    kt3 = voeg_kerntaak_toe(conn, oer_vz_bol, "B1-K1-W2", "Zorg uitvoeren", "werkproces", 2)
    kt4 = voeg_kerntaak_toe(
        conn, oer_vz_bol, "B1-K2", "Begeleiding en ondersteuning bieden", "kerntaak", 3
    )
    kt5 = voeg_kerntaak_toe(
        conn, oer_vz_bol, "B1-K2-W1", "Begeleidingsgesprek voeren", "werkproces", 4
    )

    # Kerntaken voor Kok-BBL
    kk1 = voeg_kerntaak_toe(conn, oer_kok_bbl, "B1-K1", "Bereiden van gerechten", "kerntaak", 0)
    kk2 = voeg_kerntaak_toe(
        conn, oer_kok_bbl, "B1-K1-W1", "Mise en place uitvoeren", "werkproces", 1
    )
    kk3 = voeg_kerntaak_toe(conn, oer_kok_bbl, "B1-K1-W2", "Warm bereiden", "werkproces", 2)

    # Mentoren
    mentor1_id = voeg_mentor_toe(conn, "Jansen", WW_HASH, inst_rijn["id"])
    mentor2_id = voeg_mentor_toe(conn, "De Vries", WW_HASH, inst_dv["id"])
    koppel_mentor_oer(conn, mentor1_id, oer_vz_bol)
    koppel_mentor_oer(conn, mentor2_id, oer_kok_bbl)

    # Studenten
    studenten = [
        (
            "100001", "Fatima Al-Hassan", inst_rijn["id"], oer_vz_bol, mentor1_id,
            19, "V", "VZ-1A", 0.54, 37.0, 60.0, 8.0, 2.0, "VMBO_TL", "Zorgenwelzijn", False,
        ),
        (
            "100002", "Daan Vermeer", inst_rijn["id"], oer_vz_bol, mentor1_id,
            20, "M", "VZ-1A", 0.78, 52.0, 60.0, 1.0, 4.0, "VMBO_KB", "Zorgenwelzijn", False,
        ),
        (
            "100003", "Lina Kowalski", inst_dv["id"], oer_kok_bbl, mentor2_id,
            18, "V", "HO-1B", 0.38, 24.0, 60.0, 14.0, 0.0, "VMBO_BB", "Economie", False,
        ),
    ]

    kt_per_oer = {
        oer_vz_bol: [kt1, kt2, kt3, kt4, kt5],
        oer_kok_bbl: [kk1, kk2, kk3],
    }

    for (
        nr, naam, inst_id, oer_id, mentor_id,
        lft, gsl, klas, vg, bsa_b, bsa_v, afwn, afwg, voopl, sect, drop
    ) in studenten:
        if get_student_by_studentnummer(conn, nr):
            continue
        st_id = voeg_student_toe(
            conn, nr, naam, WW_HASH, inst_id, oer_id, mentor_id,
            lft, gsl, klas, vg, bsa_b, bsa_v, afwn, afwg, voopl, sect, drop,
        )
        for kt_id in kt_per_oer[oer_id]:
            basis = vg * 100
            score = max(0.0, min(100.0, basis + RNG.gauss(0, 12)))
            voeg_student_kerntaak_score_toe(conn, st_id, kt_id, round(score, 1))

    print("Seed voltooid.")
    print(f"  Studenten: {len(studenten)}")
    print("  Mentoren: Jansen (rijn_ijssel), De Vries (davinci)")
    print("  Wachtwoord voor allen: Welkom123")
    conn.close()


if __name__ == "__main__":
    import os

    db_pad = Path(os.environ.get("DB_PATH", "data/validatie.db"))
    db_pad.parent.mkdir(parents=True, exist_ok=True)
    seed(db_pad)
