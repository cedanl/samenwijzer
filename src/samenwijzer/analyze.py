"""Analyse: voortgang per student en groepsstatistieken."""

import pandas as pd

from samenwijzer.transform import get_kerntaak_columns, get_werkproces_columns


def get_student(df: pd.DataFrame, studentnummer: str) -> pd.Series:
    """Haal één student op uit het DataFrame.

    Args:
        df: Getransformeerd studenten-DataFrame.
        studentnummer: Het studentnummer om op te zoeken.

    Returns:
        Series met alle velden van de student.

    Raises:
        ValueError: Als het studentnummer niet gevonden wordt.
    """
    match = df[df["studentnummer"] == studentnummer]
    if match.empty:
        raise ValueError(f"Student niet gevonden: {studentnummer}")
    return match.iloc[0]


def groepsoverzicht(df: pd.DataFrame) -> pd.DataFrame:
    """Geef een samengevat overzicht per student voor de docentweergave.

    Returns:
        DataFrame met kolommen: studentnummer, naam, opleiding, cohort,
        mentor, voortgang, bsa_behaald, bsa_vereist, bsa_percentage,
        kt_gemiddelde, risico.
    """
    cols = [
        "studentnummer",
        "naam",
        "opleiding",
        "cohort",
        "leerweg",
        "mentor",
        "voortgang",
        "bsa_behaald",
        "bsa_vereist",
        "bsa_percentage",
        "risico",
    ]
    if "kt_gemiddelde" in df.columns:
        cols.append("kt_gemiddelde")

    return df[cols].sort_values("naam").reset_index(drop=True)


def kerntaak_scores(df: pd.DataFrame, studentnummer: str) -> pd.DataFrame:
    """Geef de kerntaakscores van één student als DataFrame.

    Returns:
        DataFrame met kolommen: kerntaak, score, label.
    """
    student = get_student(df, studentnummer)
    kt_cols = get_kerntaak_columns(df)
    records = [
        {
            "kerntaak": col,
            "label": col.replace("_", " ").replace("kt", "KT").title(),
            "score": student[col],
        }
        for col in kt_cols
    ]
    return pd.DataFrame(records)


def werkproces_scores(df: pd.DataFrame, studentnummer: str) -> pd.DataFrame:
    """Geef de werkprocesscores van één student als DataFrame.

    Returns:
        DataFrame met kolommen: werkproces, score, label.
    """
    student = get_student(df, studentnummer)
    wp_cols = get_werkproces_columns(df)
    records = [
        {
            "werkproces": col,
            "label": col.replace("_", " ").replace("wp", "WP").title(),
            "score": student[col],
        }
        for col in wp_cols
    ]
    return pd.DataFrame(records)


def cohort_gemiddelden(df: pd.DataFrame) -> pd.DataFrame:
    """Berek gemiddelde voortgang en BSA-percentage per cohort en opleiding.

    Returns:
        DataFrame gegroepeerd op opleiding en cohort.
    """
    return (
        df.groupby(["opleiding", "cohort"], as_index=False)
        .agg(
            aantal=("studentnummer", "count"),
            gem_voortgang=("voortgang", "mean"),
            gem_bsa_percentage=("bsa_percentage", "mean"),
            studenten_met_risico=("risico", "sum"),
        )
        .sort_values(["opleiding", "cohort"])
    )
