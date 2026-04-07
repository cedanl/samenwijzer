"""Data transformatie: van ruwe studiedata naar analyse-klaar formaat."""

import pandas as pd

from samenwijzer.prepare import KERNTAAK_PREFIX, WERKPROCES_PREFIX


def transform_student_data(df: pd.DataFrame) -> pd.DataFrame:
    """Voeg berekende kolommen toe en normaliseer de studiedata.

    Args:
        df: Opgeschoonde DataFrame van load_student_csv.

    Returns:
        DataFrame met extra kolommen voor analyse en visualisatie.
    """
    df = df.copy()

    df["bsa_percentage"] = (df["bsa_behaald"] / df["bsa_vereist"]).clip(upper=1.0)
    df["bsa_achterstand"] = (df["bsa_vereist"] - df["bsa_behaald"]).clip(lower=0)
    df["bsa_op_schema"] = df["bsa_behaald"] >= df["bsa_vereist"]

    kt_cols = [c for c in df.columns if c.startswith(KERNTAAK_PREFIX)]
    wp_cols = [c for c in df.columns if c.startswith(WERKPROCES_PREFIX)]

    if kt_cols:
        df["kt_gemiddelde"] = df[kt_cols].mean(axis=1)
    if wp_cols:
        df["wp_gemiddelde"] = df[wp_cols].mean(axis=1)

    df["risico"] = _bereken_risico(df)
    df["niveau_label"] = df["niveau"].map(
        {1: "Niveau 1", 2: "Niveau 2", 3: "Niveau 3", 4: "Niveau 4"}
    )

    return df


def get_kerntaak_columns(df: pd.DataFrame) -> list[str]:
    """Geef een gesorteerde lijst van ruwe kerntaakkolommen (geen berekende kolommen)."""
    return sorted(
        c for c in df.columns if c.startswith(KERNTAAK_PREFIX) and not c.endswith("_gemiddelde")
    )


def get_werkproces_columns(df: pd.DataFrame) -> list[str]:
    """Geef een gesorteerde lijst van ruwe werkproceskolommen (geen berekende kolommen)."""
    return sorted(
        c for c in df.columns if c.startswith(WERKPROCES_PREFIX) and not c.endswith("_gemiddelde")
    )


def melt_kerntaken(df: pd.DataFrame) -> pd.DataFrame:
    """Zet kerntaakkolommen om naar lang formaat voor visualisatie.

    Returns:
        DataFrame met kolommen: studentnummer, kerntaak, score.
    """
    kt_cols = get_kerntaak_columns(df)
    melted = df[["studentnummer", "naam"] + kt_cols].melt(
        id_vars=["studentnummer", "naam"],
        value_vars=kt_cols,
        var_name="kerntaak",
        value_name="score",
    )
    melted["kerntaak_label"] = melted["kerntaak"].str.replace("_", " ").str.title()
    return melted


def melt_werkprocessen(df: pd.DataFrame) -> pd.DataFrame:
    """Zet werkproceskolommen om naar lang formaat voor visualisatie.

    Returns:
        DataFrame met kolommen: studentnummer, werkproces, score.
    """
    wp_cols = get_werkproces_columns(df)
    melted = df[["studentnummer", "naam"] + wp_cols].melt(
        id_vars=["studentnummer", "naam"],
        value_vars=wp_cols,
        var_name="werkproces",
        value_name="score",
    )
    melted["werkproces_label"] = melted["werkproces"].str.replace("_", " ").str.title()
    return melted


def _bereken_risico(df: pd.DataFrame) -> pd.Series:
    """Bepaal of een student risico loopt op basis van BSA en voortgang.

    Een student heeft risico als:
    - BSA minder dan 50% van vereiste studiepunten behaald, of
    - Voortgang onder 0.40
    """
    return (df["bsa_percentage"] < 0.50) | (df["voortgang"] < 0.40)
