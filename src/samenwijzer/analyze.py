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


def leerpad_niveau(student: pd.Series) -> str:
    """Leid het leerpadniveau af uit voortgang en kerntaakgemiddelde.

    Returns:
        Een van: 'Starter', 'Onderweg', 'Gevorderde', 'Expert'.
    """
    voortgang = student["voortgang"]
    kt_gem = student.get("kt_gemiddelde", 50)

    if voortgang >= 0.80 and kt_gem >= 75:
        return "Expert"
    elif voortgang >= 0.65 or kt_gem >= 60:
        return "Gevorderde"
    elif voortgang >= 0.40 or kt_gem >= 45:
        return "Onderweg"
    else:
        return "Starter"


def badge(student: pd.Series) -> str:
    """Geef een beloningsbadge op basis van voortgang.

    Returns:
        Badge-tekst met emoji.
    """
    voortgang = student["voortgang"]
    if voortgang >= 0.85:
        return "🏆 Expert Badge"
    elif voortgang >= 0.75:
        return "🥈 Gevorderde Badge"
    elif voortgang >= 0.65:
        return "🏅 Onderweg Badge"
    else:
        return "💡 Starter Badge"


def zwakste_kerntaak(df: pd.DataFrame, studentnummer: str) -> tuple[str, float] | None:
    """Geef de kerntaak met de laagste score voor een student.

    Returns:
        Tuple (label, score) of None als er geen kerntaakkolommen zijn.
    """
    student = get_student(df, studentnummer)
    kt_cols = get_kerntaak_columns(df)
    if not kt_cols:
        return None
    scores = {col: float(student[col]) for col in kt_cols}
    zwakste = min(scores, key=lambda k: scores[k])
    label = zwakste.replace("_", " ").replace("kt", "KT").title()
    return label, scores[zwakste]


def zwakste_werkproces(df: pd.DataFrame, studentnummer: str) -> tuple[str, float] | None:
    """Geef het werkproces met de laagste score voor een student.

    Returns:
        Tuple (label, score) of None als er geen werkproceskolommen zijn.
    """
    student = get_student(df, studentnummer)
    wp_cols = get_werkproces_columns(df)
    if not wp_cols:
        return None
    scores = {col: float(student[col]) for col in wp_cols}
    zwakste = min(scores, key=lambda k: scores[k])
    label = zwakste.replace("_", " ").replace("wp", "WP").title()
    return label, scores[zwakste]


def cohort_positie(df: pd.DataFrame, studentnummer: str) -> dict:
    """Geef de anonieme rangpositie van een student binnen zijn cohort op voortgang.

    Returns:
        Dict met 'positie', 'totaal' en 'cohort'.
    """
    student = get_student(df, studentnummer)
    cohort_df = (
        df[df["cohort"] == student["cohort"]]
        .sort_values("voortgang", ascending=False)
        .reset_index(drop=True)
    )
    positie = int(cohort_df[cohort_df["studentnummer"] == studentnummer].index[0]) + 1
    return {"positie": positie, "totaal": len(cohort_df), "cohort": student["cohort"]}


def peer_profielen(df: pd.DataFrame) -> pd.DataFrame:
    """Geef per student de sterkste en zwakste kerntaak voor peer-matching.

    Returns:
        DataFrame met kolommen: naam, sterkste_kt, sterkste_score,
        zwakste_kt, zwakste_score.
    """
    kt_cols = get_kerntaak_columns(df)
    if not kt_cols:
        return pd.DataFrame()

    records = []
    for _, row in df.iterrows():
        scores = {col: float(row[col]) for col in kt_cols}
        sterkste = max(scores, key=lambda k: scores[k])
        zwakste = min(scores, key=lambda k: scores[k])
        records.append(
            {
                "naam": row["naam"],
                "sterkste_kt": sterkste.replace("_", " ").title(),
                "sterkste_score": scores[sterkste],
                "zwakste_kt": zwakste.replace("_", " ").title(),
                "zwakste_score": scores[zwakste],
            }
        )

    return pd.DataFrame(records).sort_values("naam").reset_index(drop=True)


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
