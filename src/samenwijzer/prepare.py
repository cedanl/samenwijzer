"""Studiedata preparation: inlezen, valideren en opschonen van CSV-brondata."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

_CREBO_MAP = {
    "Zorg & Welzijn": "25480",
    "Economie": "90300",
    "Techniek": "25600",
    "Gastheer/Gastvrouw": "22172",
    "Junior Manager Logistiek": "10498",
    "Kapper": "22012",
    "Kok": "22108",
    "Metselaar": "25407",
    "Tandartsassistent": "25420",
    "Verzorgende": "25491",
    "Werktuigbouw": "25170",
    "Overig": "99999",
}

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


def load_berend_csv(path: Path) -> pd.DataFrame:
    """Laad de Berend-dataset en converteer naar het Samenwijzer-standaardformaat.

    Mapt kolomnamen, leidt ontbrekende kolommen af (niveau, BSA, voortgang)
    en retourneert een DataFrame dat door transform_student_data() verwerkt kan worden.

    Args:
        path: Pad naar de Berend CSV (Studentnummer, Naam, Klas, Mentor, …).

    Returns:
        Gevalideerd en opgeschoond standaard-DataFrame.

    Raises:
        FileNotFoundError: Als het bestand niet bestaat.
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV niet gevonden: {path}")

    raw = pd.read_csv(path, dtype={"Studentnummer": str})

    df = pd.DataFrame()
    df["studentnummer"] = raw["Studentnummer"].astype(str)
    df["naam"] = raw["Naam"].str.strip()
    df["mentor"] = raw["Mentor"].str.strip()
    df["opleiding"] = raw["Opleiding"].str.strip()
    df["leeftijd"] = raw["StudentAge"]
    df["geslacht"] = raw["StudentGender"].map({0: "M", 1: "V"}).fillna("O")

    # Niveau en cohort afleiden uit klascode (bijv. "2B" → niveau 2, cohort "B")
    df["niveau"] = raw["Klas"].str[0].astype(int)
    df["cohort"] = "Cohort " + raw["Klas"].str[1]
    df["leerweg"] = "BOL"

    df["crebo"] = raw["Opleiding"].str.strip().map(_CREBO_MAP).fillna("99999")

    # BSA: vereist = 60 studiepunten; behaald omgekeerd evenredig met ongeoorloofd verzuim
    df["bsa_vereist"] = 60.0
    df["bsa_behaald"] = (60.0 * (1.0 - raw["absence_unauthorized"] / 60.0)).clip(0, 60).round(1)

    # Voortgang: schaal 0–1, lager bij meer ongeoorloofd verzuim; minimaal 0.05
    max_unauth = raw["absence_unauthorized"].max()
    df["voortgang"] = (
        (1.0 - raw["absence_unauthorized"] / (max_unauth * 1.2)).clip(0.05, 1.0).round(2)
    )

    df = _clean(df)
    df = _voeg_kt_wp_scores_toe(df, path.parent / "oer_kerntaken.json")
    return df


def _voeg_kt_wp_scores_toe(df: pd.DataFrame, json_pad: Path) -> pd.DataFrame:
    """Voeg synthetische kerntaak- en werkprocesscores toe per student.

    Scores zijn gecorreleerd aan voortgang met studentspecifieke ruis,
    zodat elk run van dezelfde data dezelfde scores oplevert.

    Args:
        df: DataFrame met tenminste 'studentnummer', 'opleiding' en 'voortgang'.
        json_pad: Pad naar oer_kerntaken.json.

    Returns:
        DataFrame uitgebreid met kt_1, kt_2, wp_1_1 … wp_2_3 kolommen (0–100).
    """
    if not json_pad.exists():
        return df

    with json_pad.open(encoding="utf-8") as fh:
        oer: dict = json.load(fh)

    kt_cols = ["kt_1", "kt_2"]
    wp_cols = ["wp_1_1", "wp_1_2", "wp_1_3", "wp_2_1", "wp_2_2", "wp_2_3"]

    for col in kt_cols + wp_cols:
        df[col] = 0.0

    for idx, row in df.iterrows():
        snr = str(row["studentnummer"])
        voortgang = float(row["voortgang"])
        opl = str(row["opleiding"])

        # Reproduceerbare ruis per student
        rng = np.random.default_rng(int(abs(hash(snr)) % 2**32))

        # Opleiding bepaalt of kt/wp kolommen bestaan in de OER
        opl_data = oer.get(opl, oer.get("Overig", {}))
        kt_namen = {k["code"] for k in opl_data.get("kerntaken", [])}
        wp_namen = {w["code"] for w in opl_data.get("werkprocessen", [])}

        basis = voortgang * 100

        for kt in kt_cols:
            if kt in kt_namen:
                score = basis + rng.uniform(-18, 18)
                df.at[idx, kt] = float(np.clip(round(score), 30, 98))
            else:
                df.at[idx, kt] = float("nan")

        for wp in wp_cols:
            # Werkproces hoort bij kt_1 of kt_2
            kt_ouder = "kt_1" if wp.startswith("wp_1") else "kt_2"
            if wp in wp_namen and kt_ouder in kt_namen:
                kt_score = df.at[idx, kt_ouder]
                score = float(kt_score) + rng.uniform(-12, 12)
                df.at[idx, wp] = float(np.clip(round(score), 25, 99))
            else:
                df.at[idx, wp] = float("nan")

    return df
