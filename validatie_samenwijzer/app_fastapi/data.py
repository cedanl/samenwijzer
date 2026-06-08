"""Data-fetchers voor de ingelogde pagina's (voortgang, studentenlijst, mentor-profiel).

Levert plain dicts (UI-vrij) op basis van de db.py-queries; kleurklassen worden hier
bepaald zodat de templates ze alleen hoeven te stylen.
"""

from __future__ import annotations

import os
import sqlite3

from validatie_samenwijzer import db
from validatie_samenwijzer.opleiding import schoon_opleiding_naam


def _conn() -> sqlite3.Connection:
    return db.get_connection(os.environ.get("DB_PATH", "data/validatie.db"))


def _kleur_score(score: float) -> str:
    """Kerntaak-score 0–100 → kleurklasse."""
    if score >= 70:
        return "groen"
    if score >= 50:
        return "oranje"
    return "rood"


def _kleur_voortgang(vg: float) -> str:
    """Voortgang 0–1 → kleurklasse."""
    if vg >= 0.7:
        return "groen"
    if vg >= 0.5:
        return "oranje"
    return "rood"


def _kleur_bsa(pct: float) -> str:
    if pct >= 0.8:
        return "groen"
    if pct >= 0.6:
        return "oranje"
    return "rood"


def _opleiding_label(oer_id: int) -> tuple[str, int | None]:
    row = (
        _conn()
        .execute(
            """SELECT o.opleiding, o.crebo, o.leerweg, o.cohort, i.display_naam
           FROM oer_documenten o JOIN instellingen i ON i.id = o.instelling_id
           WHERE o.id = ?""",
            (oer_id,),
        )
        .fetchone()
    )
    if row is None:
        return "Onbekende opleiding", None
    naam = schoon_opleiding_naam(row["opleiding"], row["crebo"])
    return f"{naam} · {row['leerweg']} {row['cohort']} · {row['display_naam']}", oer_id


def _kerntaken(student_id: int) -> list[dict]:
    """Gededupliceerde kerntaken (type 'kerntaak') met score + kleur."""
    rows = db.get_kerntaak_scores_by_student_id(_conn(), student_id)
    gezien: set[str] = set()
    out: list[dict] = []
    for r in rows:
        if r["type"] != "kerntaak" or r["naam"] in gezien:
            continue
        gezien.add(r["naam"])
        out.append(
            {"naam": r["naam"], "score": round(r["score"]), "kleur": _kleur_score(r["score"])}
        )
    return out


def _student_row(student_id: int) -> sqlite3.Row | None:
    return _conn().execute("SELECT * FROM studenten WHERE id = ?", (student_id,)).fetchone()


def _basis(student: sqlite3.Row) -> dict:
    vg = student["voortgang"] or 0.0
    bsa_b = student["bsa_behaald"] or 0.0
    bsa_v = student["bsa_vereist"] or 60.0
    bsa_pct = min(bsa_b / bsa_v, 1.0) if bsa_v else 0.0
    afw = student["absence_unauthorized"] or 0.0
    label, _ = _opleiding_label(student["oer_id"])
    return {
        "id": student["id"],
        "naam": student["naam"],
        "opleiding_label": label,
        "voortgang": vg,
        "voortgang_pct": round(vg * 100),
        "voortgang_kleur": _kleur_voortgang(vg),
        "bsa_behaald": round(bsa_b),
        "bsa_vereist": round(bsa_v),
        "bsa_pct": round(bsa_pct * 100),
        "bsa_kleur": _kleur_bsa(bsa_pct),
        "afwezigheid": round(afw),
        "afwezigheid_kleur": "rood" if afw > 10 else ("oranje" if afw > 5 else "groen"),
    }


def voortgang_voor_studentnummer(studentnummer: str) -> dict | None:
    student = db.get_student_by_studentnummer(_conn(), studentnummer)
    if student is None:
        return None
    data = _basis(student)
    data["kerntaken"] = _kerntaken(student["id"])
    return data


def studenten_van_mentor(mentor_id: int) -> list[dict]:
    rows = db.get_studenten_by_mentor_id(_conn(), mentor_id)
    return [_basis(r) for r in rows]


def profiel_van_student(student_id: int) -> dict | None:
    student = _student_row(student_id)
    if student is None:
        return None
    data = _basis(student)
    data["oer_id"] = student["oer_id"]
    data["kerntaken"] = _kerntaken(student_id)
    punten: list[str] = []
    if data["voortgang"] < 0.5:
        punten.append("⚠️ Lage voortgang — doorvragen naar oorzaak")
    if data["bsa_pct"] < 70:
        punten.append("⚠️ BSA-risico — aanwezigheid bespreken")
    if data["afwezigheid"] > 8:
        punten.append("⚠️ Hoge ongeoorloofde afwezigheid")
    for kt in data["kerntaken"]:
        if kt["score"] < 50:
            punten.append(f"📉 Lage score: {kt['naam']}")
    data["bespreekpunten"] = punten
    return data
