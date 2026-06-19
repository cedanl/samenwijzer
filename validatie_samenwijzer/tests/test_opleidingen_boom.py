"""opleidingen_boom: geneste, gesorteerde structuur uit de OER-documenten."""

import os
import sqlite3

from app_fastapi import data


def test_boom_structuur_en_sortering():
    boom = data.opleidingen_boom()
    assert isinstance(boom, list) and boom, "boom mag niet leeg zijn"

    # instellingen alfabetisch
    namen = [b["instelling"] for b in boom]
    assert namen == sorted(namen)

    eerste = boom[0]
    assert set(eerste) == {"instelling", "leerwegen"}
    lw = eerste["leerwegen"][0]
    assert set(lw) == {"leerweg", "opleidingen"}
    assert lw["leerweg"] in {"BOL", "BBL"}

    opl = lw["opleidingen"][0]
    assert set(opl) == {"naam", "cohorten"}
    assert opl["naam"] and not opl["naam"][0].isdigit()  # schone naam, geen ruwe string

    # opleidingen case-insensitief gesorteerd
    opl_namen = [o["naam"] for o in lw["opleidingen"]]
    assert opl_namen == sorted(opl_namen, key=str.casefold)

    coh = opl["cohorten"][0]
    assert set(coh) == {"cohort", "oer_ids"}
    assert coh["oer_ids"] and all(isinstance(i, int) for i in coh["oer_ids"])

    # cohorten aflopend (nieuwste eerst)
    cohorten = [c["cohort"] for c in opl["cohorten"]]
    assert cohorten == sorted(cohorten, reverse=True)


def test_boom_alleen_geindexeerd():
    # Alle oer_ids in de boom moeten geindexeerd=1 zijn.
    boom = data.opleidingen_boom()
    ids = {
        i
        for b in boom
        for lw in b["leerwegen"]
        for o in lw["opleidingen"]
        for c in o["cohorten"]
        for i in c["oer_ids"]
    }
    assert ids, "verwacht geïndexeerde OER's in de testdatabase"
    conn = sqlite3.connect(os.environ.get("DB_PATH", "data/validatie.db"))
    rij = conn.execute(
        f"SELECT COUNT(*) FROM oer_documenten WHERE geindexeerd=0 "
        f"AND id IN ({','.join('?' * len(ids))})",
        tuple(ids),
    ).fetchone()
    assert rij[0] == 0
