"""Visualisaties voor studiedata (Altair-based, Streamlit-compatible)."""

import altair as alt
import pandas as pd

_SCORE_DOMAIN = [0, 100]
_VOORTGANG_DOMAIN = [0, 1]
_KLEUR_GOED = "#2ecc71"
_KLEUR_RISICO = "#e74c3c"
_KLEUR_NEUTRAAL = "#3498db"
_KLEUR_SCHAAL = "#f39c12"


def voortgang_gauge(voortgang: float, label: str = "Voortgang") -> alt.Chart:
    """Horizontale staafgrafiek die voortgang als percentage toont.

    Args:
        voortgang: Waarde tussen 0 en 1.
        label: Omschrijving boven de balk.

    Returns:
        Altair Chart.
    """
    pct = round(voortgang * 100)
    if voortgang >= 0.75:
        kleur = _KLEUR_GOED
    elif voortgang >= 0.50:
        kleur = _KLEUR_SCHAAL
    else:
        kleur = _KLEUR_RISICO

    data = pd.DataFrame({"label": [label], "waarde": [pct], "max": [100]})

    achtergrond = (
        alt.Chart(data)
        .mark_bar(color="#e0e0e0", cornerRadiusEnd=4)
        .encode(
            x=alt.X("max:Q", scale=alt.Scale(domain=[0, 100]), title=None),
            y=alt.Y("label:N", title=None),
        )
    )

    voorgrond = (
        alt.Chart(data)
        .mark_bar(color=kleur, cornerRadiusEnd=4)
        .encode(
            x=alt.X("waarde:Q", scale=alt.Scale(domain=[0, 100]), title="%"),
            y=alt.Y("label:N", title=None),
        )
    )

    tekst = (
        alt.Chart(data)
        .mark_text(align="left", dx=4, color="white", fontWeight="bold")
        .encode(
            x=alt.X("waarde:Q"),
            y=alt.Y("label:N"),
            text=alt.Text("waarde:Q", format=".0f"),
        )
    )

    return (achtergrond + voorgrond + tekst).properties(height=80, background="white")


def bsa_staaf(bsa_behaald: float, bsa_vereist: float) -> alt.Chart:
    """Gestapelde staaf: behaalde vs. nog te behalen BSA-punten.

    Returns:
        Altair Chart.
    """
    data = pd.DataFrame(
        {
            "categorie": ["Behaald", "Restant"],
            "punten": [bsa_behaald, max(0, bsa_vereist - bsa_behaald)],
            "kleur": [_KLEUR_GOED, "#e0e0e0"],
        }
    )

    return (
        alt.Chart(data)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "punten:Q",
                stack="zero",
                title="Studiepunten",
                scale=alt.Scale(domain=[0, bsa_vereist * 1.1]),
            ),
            y=alt.Y("categorie:N", title=None, sort=["Behaald", "Restant"]),
            color=alt.Color("kleur:N", scale=None, legend=None),
            tooltip=["categorie:N", "punten:Q"],
        )
        .properties(height=80, background="white")
    )


def kerntaak_grafiek(kt_df: pd.DataFrame) -> alt.Chart:
    """Horizontale staafgrafiek van kerntaakscores (0–100).

    Args:
        kt_df: DataFrame met kolommen label en score (van analyze.kerntaak_scores).

    Returns:
        Altair Chart.
    """
    return (
        alt.Chart(kt_df)
        .mark_bar(color=_KLEUR_NEUTRAAL, cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "score:Q",
                scale=alt.Scale(domain=_SCORE_DOMAIN),
                title="Score (0–100)",
            ),
            y=alt.Y("label:N", sort="-x", title=None),
            tooltip=["label:N", "score:Q"],
        )
        .properties(height=max(100, len(kt_df) * 50), background="white")
    )


def werkproces_grafiek(wp_df: pd.DataFrame) -> alt.Chart:
    """Horizontale staafgrafiek van werkprocesscores (0–100).

    Args:
        wp_df: DataFrame met kolommen label en score (van analyze.werkproces_scores).

    Returns:
        Altair Chart.
    """
    return (
        alt.Chart(wp_df)
        .mark_bar(color=_KLEUR_SCHAAL, cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "score:Q",
                scale=alt.Scale(domain=_SCORE_DOMAIN),
                title="Score (0–100)",
            ),
            y=alt.Y("label:N", sort="-x", title=None),
            tooltip=["label:N", "score:Q"],
        )
        .properties(height=max(140, len(wp_df) * 40), background="white")
    )


def groep_voortgang_grafiek(overzicht_df: pd.DataFrame) -> alt.Chart:
    """Spreidingsplot: voortgang vs. BSA-percentage per student, risico gehighlight.

    Args:
        overzicht_df: Uitvoer van analyze.groepsoverzicht.

    Returns:
        Altair Chart.
    """
    df = overzicht_df.copy()
    df["risico_label"] = df["risico"].map({True: "Risico", False: "Op schema"})

    return (
        alt.Chart(df)
        .mark_circle(size=80, opacity=0.8)
        .encode(
            x=alt.X(
                "voortgang:Q",
                scale=alt.Scale(domain=_VOORTGANG_DOMAIN),
                title="Voortgang",
                axis=alt.Axis(format="%"),
            ),
            y=alt.Y(
                "bsa_percentage:Q",
                scale=alt.Scale(domain=_VOORTGANG_DOMAIN),
                title="BSA behaald",
                axis=alt.Axis(format="%"),
            ),
            color=alt.Color(
                "risico_label:N",
                scale=alt.Scale(
                    domain=["Risico", "Op schema"],
                    range=[_KLEUR_RISICO, _KLEUR_GOED],
                ),
                legend=alt.Legend(title="Status"),
            ),
            tooltip=[
                "naam:N",
                "opleiding:N",
                "mentor:N",
                "voortgang:Q",
                "bsa_percentage:Q",
            ],
        )
        .properties(height=350, background="white")
    )
