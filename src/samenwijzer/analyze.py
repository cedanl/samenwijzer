"""Analyse: voortgang per student en groepsstatistieken."""

import json
from pathlib import Path

import pandas as pd

from samenwijzer.transform import get_kerntaak_columns, get_werkproces_columns
from samenwijzer.wellbeing import WelzijnsCheck, heeft_signaal, welzijnswaarde

_OER_DATA: dict | None = None
_OER_JSON = (
    Path(__file__).parent.parent.parent / "data" / "01-raw" / "berend" / "oer_kerntaken.json"
)


def _laad_oer() -> dict:
    """Laad de OER-kerntakendata eenmalig vanuit JSON en cache het resultaat."""
    global _OER_DATA
    if _OER_DATA is None:
        _OER_DATA = json.loads(_OER_JSON.read_text(encoding="utf-8")) if _OER_JSON.exists() else {}
    return _OER_DATA


def _oer_label(opleiding: str, kolom: str) -> str:
    """Zoek de OER-naam op voor een kt_ of wp_ kolom."""
    data = _laad_oer()
    opl = data.get(opleiding, data.get("Overig", {}))
    sectie = "kerntaken" if kolom.startswith("kt_") else "werkprocessen"
    for item in opl.get(sectie, []):
        if item["code"] == kolom:
            return item["naam"]
    return kolom.replace("_", " ").replace("kt", "KT").replace("wp", "WP").title()


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

    Args:
        df: Getransformeerd studenten-DataFrame.

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
    opleiding = str(student.get("opleiding", ""))
    kt_cols = get_kerntaak_columns(df)
    records = [
        {
            "kerntaak": col,
            "label": _oer_label(opleiding, col),
            "score": student[col],
        }
        for col in kt_cols
        if pd.notna(student.get(col))
    ]
    return pd.DataFrame(records)


def werkproces_scores(df: pd.DataFrame, studentnummer: str) -> pd.DataFrame:
    """Geef de werkprocesscores van één student als DataFrame.

    Returns:
        DataFrame met kolommen: werkproces, score, label.
    """
    student = get_student(df, studentnummer)
    opleiding = str(student.get("opleiding", ""))
    wp_cols = get_werkproces_columns(df)
    records = [
        {
            "werkproces": col,
            "label": _oer_label(opleiding, col),
            "score": student[col],
        }
        for col in wp_cols
        if pd.notna(student.get(col))
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
    opleiding = str(student.get("opleiding", ""))
    kt_cols = get_kerntaak_columns(df)
    scores = {col: float(student[col]) for col in kt_cols if pd.notna(student.get(col))}
    if not scores:
        return None
    zwakste = min(scores, key=lambda k: scores[k])
    return _oer_label(opleiding, zwakste), scores[zwakste]


def zwakste_werkproces(df: pd.DataFrame, studentnummer: str) -> tuple[str, float] | None:
    """Geef het werkproces met de laagste score voor een student.

    Returns:
        Tuple (label, score) of None als er geen werkproceskolommen zijn.
    """
    student = get_student(df, studentnummer)
    opleiding = str(student.get("opleiding", ""))
    wp_cols = get_werkproces_columns(df)
    scores = {col: float(student[col]) for col in wp_cols if pd.notna(student.get(col))}
    if not scores:
        return None
    zwakste = min(scores, key=lambda k: scores[k])
    return _oer_label(opleiding, zwakste), scores[zwakste]


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
        opleiding = str(row.get("opleiding", ""))
        scores = {col: float(row[col]) for col in kt_cols if pd.notna(row.get(col))}
        if not scores:
            continue
        sterkste = max(scores, key=lambda k: scores[k])
        zwakste = min(scores, key=lambda k: scores[k])
        records.append(
            {
                "naam": row["naam"],
                "sterkste_kt": _oer_label(opleiding, sterkste),
                "sterkste_score": scores[sterkste],
                "zwakste_kt": _oer_label(opleiding, zwakste),
                "zwakste_score": scores[zwakste],
            }
        )

    return pd.DataFrame(records).sort_values("naam").reset_index(drop=True)


def signaleringen(
    df_studenten: pd.DataFrame,
    df_welzijn: pd.DataFrame,
    drempel: float = 0.55,
) -> pd.DataFrame:
    """Geef studenten met een actieve welzijnssignalering.

    Neemt de meest recente check per student en geeft alleen studenten terug
    waarvan de welzijnswaarde onder de drempel ligt. Combineert welzijnsdata
    met naam en mentor uit de studentendata.

    Args:
        df_studenten: Getransformeerd studenten-DataFrame.
        df_welzijn: Geladen welzijn-DataFrame (uit load_welzijn_csv).
        drempel: Grenswaarde voor signalering (standaard 0.55 = antwoord 2 of 3).

    Returns:
        DataFrame met kolommen: studentnummer, naam, mentor, datum,
        antwoord, toelichting, welzijnswaarde. Gesorteerd op welzijnswaarde
        oplopend (meest zorgelijk bovenaan).
    """
    if df_welzijn.empty:
        return pd.DataFrame(
            columns=["studentnummer", "naam", "mentor", "datum",
                     "antwoord", "toelichting", "welzijnswaarde"]
        )

    meest_recent = (
        df_welzijn.sort_values("datum")
        .groupby("studentnummer", as_index=False)
        .last()
    )

    meest_recent["welzijnswaarde"] = meest_recent.apply(
        lambda r: welzijnswaarde(
            WelzijnsCheck(r["studentnummer"], r["datum"], int(r["antwoord"]))
        ),
        axis=1,
    )

    signalen = meest_recent[meest_recent["welzijnswaarde"] < drempel].copy()

    signalen = signalen.merge(
        df_studenten[["studentnummer", "naam", "mentor"]],
        on="studentnummer",
        how="left",
    )

    return (
        signalen[["studentnummer", "naam", "mentor", "datum",
                  "antwoord", "toelichting", "welzijnswaarde"]]
        .sort_values("welzijnswaarde")
        .reset_index(drop=True)
    )


def detecteer_transitiemoment(student: pd.Series) -> str | None:
    """Detecteer een kritiek transitiemoment voor een student.

    Transitiemomenten zijn gebaseerd op Annie Advisor-onderzoek: studenten
    hebben extra steun nodig bij BSA-risico, stage en afstuderen.

    Returns:
        Een van: 'bsa_risico', 'bijna_klaar', of None.
    """
    bsa_pct = float(student.get("bsa_percentage", 1.0))
    voortgang = float(student.get("voortgang", 0.0))

    if bsa_pct < 0.60:
        return "bsa_risico"
    if voortgang >= 0.80:
        return "bijna_klaar"
    return None


_TRANSITIE_LABEL: dict[str | None, str] = {
    "bsa_risico": "⚠️ BSA-risico",
    "bijna_klaar": "🎓 Bijna klaar",
    None: "",
}


def transitiemoment_label(moment: str | None) -> str:
    """Geef een leesbaar label terug voor een transitiemoment."""
    return _TRANSITIE_LABEL.get(moment, "")


def cohort_gemiddelden(df: pd.DataFrame) -> pd.DataFrame:
    """Bereken gemiddelde voortgang en BSA-percentage per cohort en opleiding.

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
