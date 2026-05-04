"""Welzijnsdata: datamodel, risicoscoreberekening, signalering en notities."""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd


@dataclass
class WelzijnsCheck:
    """Resultaat van één welzijnscheck van een student.

    Fase 1: één gecombineerde vraag via WhatsApp (antwoord 1/2/3).
    Fase 3: uitbreiden met aparte velden per dimensie.

    Attributes:
        studentnummer: Uniek studentidentificatie.
        datum: Datum van de check.
        antwoord: WhatsApp-antwoord van de student (1=goed, 2=matig, 3=zwaar).
        toelichting: Optionele vrije tekst van de student.
    """

    studentnummer: str
    datum: date
    antwoord: int
    toelichting: str | None = None

    def __post_init__(self) -> None:
        if self.antwoord not in (1, 2, 3):
            raise ValueError(f"Antwoord moet 1, 2 of 3 zijn, niet: {self.antwoord}")


def welzijnswaarde(check: WelzijnsCheck) -> float:
    """Normaliseer het antwoord naar een waarde tussen 0 en 1 (hoger = beter).

    Mapping:
        1 (goed)  → 1.00
        2 (matig) → 0.50
        3 (zwaar) → 0.00

    Returns:
        Float tussen 0.0 en 1.0.
    """
    return (3 - check.antwoord) / 2


_ANTWOORD_LABELS = {1: "Goed", 2: "Matig", 3: "Zwaar"}


def antwoord_label(antwoord: int) -> str:
    """Geef de leesbare label voor een WhatsApp-antwoord (1/2/3)."""
    return _ANTWOORD_LABELS.get(antwoord, str(antwoord))


def heeft_signaal(check: WelzijnsCheck, drempel: float = 0.55) -> bool:
    """Geeft True als de welzijnswaarde onder de drempel ligt (score 2 of 3).

    Args:
        check: De te beoordelen welzijnscheck.
        drempel: Grenswaarde; standaard 0.55 (vangt antwoord 2 en 3).

    Returns:
        True als er een signaal is.
    """
    return welzijnswaarde(check) < drempel


# ── Notities ──────────────────────────────────────────────────────────────────

_NOTITIES_COLUMNS = ["studentnummer", "mentor", "timestamp", "notitie"]


def laad_notities(path: Path) -> pd.DataFrame:
    """Laad mentornotities uit CSV. Geeft leeg DataFrame terug als bestand niet bestaat.

    Returns:
        DataFrame met kolommen: studentnummer, mentor, timestamp, notitie.
    """
    if not path.exists():
        return pd.DataFrame(columns=_NOTITIES_COLUMNS)

    return pd.read_csv(path, sep=";", dtype={"studentnummer": str, "mentor": str})


def sla_notitie_op(path: Path, studentnummer: str, mentor: str, notitie: str) -> None:
    """Voeg een mentornotitie toe aan de notities-CSV.

    Args:
        path: Pad naar het notities-CSV-bestand (wordt aangemaakt indien nodig).
        studentnummer: De student waarover de notitie gaat.
        mentor: De mentor die de notitie schrijft.
        notitie: De notitietekst.

    Raises:
        ValueError: Als notitie leeg is.
    """
    notitie = notitie.strip()
    if not notitie:
        raise ValueError("Notitie mag niet leeg zijn.")

    df = laad_notities(path)
    nieuwe_rij = pd.DataFrame(
        [
            {
                "studentnummer": studentnummer,
                "mentor": mentor,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "notitie": notitie,
            }
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([df, nieuwe_rij], ignore_index=True).to_csv(path, sep=";", index=False)


def filter_signaleringen_voor_mentor(df_signaleringen: pd.DataFrame, mentor: str) -> pd.DataFrame:
    """Filter signaleringen zodat een mentor alleen zijn eigen studenten ziet.

    Args:
        df_signaleringen: Output van analyze.signaleringen().
        mentor: De naam van de mentor waarop gefilterd wordt.

    Returns:
        Gefilterd DataFrame.
    """
    if df_signaleringen.empty or not mentor:
        return df_signaleringen
    return df_signaleringen[df_signaleringen["mentor"] == mentor].reset_index(drop=True)
