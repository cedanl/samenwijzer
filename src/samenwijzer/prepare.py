"""Studiedata preparation: inlezen, valideren en opschonen van CSV-brondata."""

from pathlib import Path

import numpy as np
import pandas as pd

WELZIJN_REQUIRED_COLUMNS = {"studentnummer", "datum", "antwoord"}

_DEFAULT_PAD = (
    Path(__file__).parent.parent.parent / "data" / "01-raw" / "synthetisch" / "studenten.csv"
)
_DB_PAD_VOOR_KT = Path(__file__).parent.parent.parent / "data" / "02-prepared" / "oeren.db"

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


def load_welzijn_csv(path: Path) -> pd.DataFrame:
    """Laad en valideer een welzijn-CSV.

    Args:
        path: Pad naar het CSV-bestand.

    Returns:
        DataFrame met kolommen: studentnummer (str), datum (date),
        antwoord (int 1-3), toelichting (str of None).

    Raises:
        FileNotFoundError: Als het bestand niet bestaat.
        ValueError: Als verplichte kolommen ontbreken of antwoord ongeldig is.
    """
    if not path.exists():
        raise FileNotFoundError(f"Welzijn-CSV niet gevonden: {path}")

    df = pd.read_csv(path, sep=";", dtype={"studentnummer": str})

    missing = WELZIJN_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Ontbrekende verplichte kolommen in welzijn-CSV: {missing}")

    df["datum"] = pd.to_datetime(df["datum"], errors="coerce").dt.date
    df["antwoord"] = pd.to_numeric(df["antwoord"], errors="coerce").astype("Int64")

    if "toelichting" not in df.columns:
        df["toelichting"] = None
    else:
        df["toelichting"] = df["toelichting"].where(df["toelichting"].notna(), None)

    ongeldige_antwoorden = df[~df["antwoord"].isin([1, 2, 3])]
    if not ongeldige_antwoorden.empty:
        raise ValueError(
            f"Ongeldige antwoordwaarden (verwacht 1, 2 of 3): "
            f"{ongeldige_antwoorden['antwoord'].dropna().unique().tolist()}"
        )

    return df.sort_values(["studentnummer", "datum"]).reset_index(drop=True)


def load_synthetisch_csv(path: Path = _DEFAULT_PAD) -> pd.DataFrame:
    """Laad de synthetische studentendata en map naar het standaard samenwijzer-DataFrame.

    De synthetische CSV bevat al kolommen voor `Instelling`, `Opleiding`, `crebo`,
    `leerweg` en `cohort`. Niveau wordt afgeleid uit het eerste teken van `Klas`.
    BSA en voortgang worden afgeleid uit ongeoorloofd verzuim.

    Args:
        path: Pad naar de synthetische CSV.

    Returns:
        Gevalideerd, opgeschoond DataFrame met de standaard kolommen.

    Raises:
        FileNotFoundError: Als het bestand niet bestaat.
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV niet gevonden: {path}")

    raw = pd.read_csv(path, dtype={"Studentnummer": str, "crebo": str, "cohort": str})

    df = pd.DataFrame()
    df["studentnummer"] = raw["Studentnummer"]
    df["naam"] = raw["Naam"].str.strip()
    df["mentor"] = raw["Mentor"].str.strip()
    df["instelling"] = raw["Instelling"].str.strip()
    df["opleiding"] = raw["Opleiding"].str.strip()
    df["crebo"] = raw["crebo"]
    df["leerweg"] = raw["leerweg"]
    df["cohort"] = raw["cohort"]
    df["niveau"] = raw["Klas"].str[0].astype(int)
    df["leeftijd"] = raw["StudentAge"]
    df["geslacht"] = raw["StudentGender"].map({0: "M", 1: "V"}).fillna("O")

    # BSA: vereist = 60 studiepunten; behaald omgekeerd evenredig met ongeoorloofd verzuim
    df["bsa_vereist"] = 60.0
    df["bsa_behaald"] = (60.0 * (1.0 - raw["absence_unauthorized"] / 60.0)).clip(0, 60).round(1)

    # Voortgang: schaal 0–1, lager bij meer ongeoorloofd verzuim; minimaal 0.05
    max_unauth = raw["absence_unauthorized"].max() or 1.0
    df["voortgang"] = (
        (1.0 - raw["absence_unauthorized"] / (max_unauth * 1.2)).clip(0.05, 1.0).round(2)
    )

    df = _clean(df)
    df = _voeg_kt_wp_scores_toe(df)
    return df


def _voeg_kt_wp_scores_toe(df: pd.DataFrame) -> pd.DataFrame:
    """Voeg synthetische kt/wp-scores toe per student via oeren.db lookup.

    Voor elke unieke (opleiding, niveau) wordt één keer de kerntakenlijst opgehaald;
    daarna krijgt elke student gecorreleerd-met-voortgang scores op zijn kerntaken.

    Scores zijn reproduceerbaar (RNG gezaaid op studentnummer) en synthetisch:
    we mappen de eerste 2 kerntaken op kt_1/kt_2 en de eerste 6 werkprocessen op
    wp_1_1…wp_2_3. Heeft een opleiding minder kerntaken/werkprocessen dan deze
    standaardposities, dan krijgt de student NaN op de ontbrekende kolommen.

    Args:
        df: DataFrame met tenminste 'studentnummer', 'opleiding', 'niveau' en 'voortgang'.

    Returns:
        DataFrame uitgebreid met kt_1, kt_2, wp_1_1 … wp_2_3 kolommen (0–100 of NaN).
    """
    from samenwijzer import oer_store  # lazy import: cycle-vermijdend

    kt_cols = ["kt_1", "kt_2"]
    wp_cols = ["wp_1_1", "wp_1_2", "wp_1_3", "wp_2_1", "wp_2_2", "wp_2_3"]
    for col in kt_cols + wp_cols:
        df[col] = float("nan")

    # Cache: (opleiding, niveau) → aantal beschikbare kerntaken/werkprocessen
    cache: dict[tuple[str, int], tuple[int, int]] = {}

    for idx, row in df.iterrows():
        opl = str(row["opleiding"])
        niv = int(row["niveau"])
        sleutel = (opl, niv)
        if sleutel not in cache:
            kts = oer_store.get_kerntaken_voor_opleiding(_DB_PAD_VOOR_KT, opl, niveau=niv)
            n_kt = sum(1 for k in kts if k["type"] == "kerntaak")
            n_wp = sum(1 for k in kts if k["type"] == "werkproces")
            cache[sleutel] = (n_kt, n_wp)
        n_kt, n_wp = cache[sleutel]

        snr = str(row["studentnummer"])
        voortgang = float(row["voortgang"])
        rng = np.random.default_rng(int(abs(hash(snr)) % 2**32))
        basis = voortgang * 100

        # Synthetische score: vaste mapping op kt_1/kt_2 en wp_1_1…wp_2_3 (geen 1-op-1
        # koppeling met echte OER-codes — daar gaat _oer_label() in analyze.py over).
        for pos, kt in enumerate(kt_cols, start=1):
            if pos <= n_kt:
                df.at[idx, kt] = float(np.clip(round(basis + rng.uniform(-18, 18)), 30, 98))
        for pos, wp in enumerate(wp_cols, start=1):
            if pos <= n_wp:
                df.at[idx, wp] = float(np.clip(round(basis + rng.uniform(-22, 22)), 25, 98))

    return df
