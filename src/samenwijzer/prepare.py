"""Studiedata preparation: inlezen, valideren en opschonen van CSV-brondata."""

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "studentnummer",
    "naam",
    "mentor",
    "opleiding",
    "crebo",
    "niveau",
    "leerweg",
    "cohort",
    "leeftijd",
    "geslacht",
    "bsa_behaald",
    "bsa_vereist",
    "voortgang",
}

KERNTAAK_PREFIX = "kt"
WERKPROCES_PREFIX = "wp"


def load_student_csv(path: Path) -> pd.DataFrame:
    """Laad en valideer een studenten-CSV.

    Args:
        path: Pad naar het CSV-bestand.

    Returns:
        Gevalideerd en opgeschoond DataFrame.

    Raises:
        FileNotFoundError: Als het bestand niet bestaat.
        ValueError: Als verplichte kolommen ontbreken of data ongeldig is.
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV niet gevonden: {path}")

    df = pd.read_csv(path, dtype={"studentnummer": str, "crebo": str})

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Ontbrekende verplichte kolommen: {missing}")

    df = _clean(df)
    _validate(df)
    return df


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Verwijder leading/trailing whitespace en normaliseer types."""
    str_cols = df.select_dtypes(include=["object", "string"]).columns
    df[str_cols] = df[str_cols].apply(lambda c: c.str.strip())

    df["niveau"] = pd.to_numeric(df["niveau"], errors="coerce").astype("Int64")
    df["leeftijd"] = pd.to_numeric(df["leeftijd"], errors="coerce").astype("Int64")
    df["bsa_behaald"] = pd.to_numeric(df["bsa_behaald"], errors="coerce")
    df["bsa_vereist"] = pd.to_numeric(df["bsa_vereist"], errors="coerce")
    df["voortgang"] = pd.to_numeric(df["voortgang"], errors="coerce")

    kt_cols = [c for c in df.columns if c.startswith(KERNTAAK_PREFIX)]
    wp_cols = [c for c in df.columns if c.startswith(WERKPROCES_PREFIX)]
    for col in kt_cols + wp_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _validate(df: pd.DataFrame) -> None:
    """Raise ValueError als kritieke velden ontgeldige waarden bevatten."""
    if df["studentnummer"].duplicated().any():
        dupes = df.loc[df["studentnummer"].duplicated(), "studentnummer"].tolist()
        raise ValueError(f"Dubbele studentnummers: {dupes}")

    invalid_niveau = df["niveau"].dropna()
    if not invalid_niveau.between(1, 4).all():
        raise ValueError("Niveau moet tussen 1 en 4 liggen.")

    invalid_voortgang = df["voortgang"].dropna()
    if not invalid_voortgang.between(0, 1).all():
        raise ValueError("Voortgang moet een waarde tussen 0 en 1 zijn.")

    invalid_leerweg = df[~df["leerweg"].isin(["BOL", "BBL"])]
    if not invalid_leerweg.empty:
        raise ValueError(
            f"Ongeldige leerweg waarden: {invalid_leerweg['leerweg'].unique().tolist()}"
        )
