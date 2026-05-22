"""Visualisaties voor studiedata (Altair-based, Streamlit-compatible).

Het groei-spinneweb is een radar (Plotly Scatterpolar) — Altair kent geen poolcoördinaten.
"""

import altair as alt
import pandas as pd
import plotly.graph_objects as go

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
        .properties(height=110, background="white")
    )


_MAX_LABEL = 32


def _kort(tekst: str) -> str:
    """Kap een label af op _MAX_LABEL tekens met een ellipsis."""
    return tekst if len(tekst) <= _MAX_LABEL else tekst[:_MAX_LABEL].rstrip() + "…"


def kerntaak_grafiek(kt_df: pd.DataFrame) -> alt.Chart:
    """Horizontale staafgrafiek van kerntaakscores (0–100).

    Args:
        kt_df: DataFrame met kolommen label en score (van analyze.kerntaak_scores).

    Returns:
        Altair Chart.
    """
    plot = kt_df.copy()
    plot["label_kort"] = plot["label"].apply(_kort)
    return (
        alt.Chart(plot)
        .mark_bar(color=_KLEUR_NEUTRAAL, cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "score:Q",
                scale=alt.Scale(domain=_SCORE_DOMAIN),
                title="Score (0–100)",
            ),
            y=alt.Y("label_kort:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("label:N", title="Kerntaak"),
                alt.Tooltip("score:Q", title="Score"),
            ],
        )
        .properties(height=max(100, len(plot) * 55), background="white")
    )


def werkproces_grafiek(wp_df: pd.DataFrame) -> alt.Chart:
    """Horizontale staafgrafiek van werkprocesscores (0–100).

    Args:
        wp_df: DataFrame met kolommen label en score (van analyze.werkproces_scores).

    Returns:
        Altair Chart.
    """
    plot = wp_df.copy()
    plot["label_kort"] = plot["label"].apply(_kort)
    return (
        alt.Chart(plot)
        .mark_bar(color=_KLEUR_SCHAAL, cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "score:Q",
                scale=alt.Scale(domain=_SCORE_DOMAIN),
                title="Score (0–100)",
            ),
            y=alt.Y("label_kort:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("label:N", title="Werkproces"),
                alt.Tooltip("score:Q", title="Score"),
            ],
        )
        .properties(height=max(140, len(plot) * 42), background="white")
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


def _spinneweb_dicht(reeks: list[float | None]) -> list[float]:
    """Vervang None/NaN door 0 en sluit de polygon door het eerste punt te herhalen."""
    schoon = [0.0 if v is None or pd.isna(v) else float(v) for v in reeks]
    return schoon + schoon[:1]


def _spinneweb_heeft_waarde(reeks: list[float | None]) -> bool:
    """True als de reeks minstens één echte (niet-None, niet-NaN) waarde bevat."""
    return any(v is not None and not pd.isna(v) for v in reeks)


def spinneweb_figuur(
    titel: str,
    labels: list[str],
    huidig: list[float | None],
    vorig: list[float | None] | None = None,
    klas: list[float | None] | None = None,
) -> go.Figure:
    """Radar (Scatterpolar) per kerntaak: huidige meting, optioneel vorige + klasgemiddelde.

    None/NaN-waarden worden als 0 geplot; een reeks die volledig leeg is krijgt geen lijn.

    Args:
        titel: Titel boven het spinneweb (meestal het kerntaaklabel).
        labels: Werkproces-labels op de assen.
        huidig: Huidige scores per werkproces (0–100).
        vorig: Vorige scores, of None als er geen vorige meting is.
        klas: Klasgemiddelden per werkproces, of None.

    Returns:
        Plotly Figure.
    """
    theta = labels + labels[:1]
    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=_spinneweb_dicht(huidig),
            theta=theta,
            fill="toself",
            name="Huidige meting",
            line={"color": "#27ae60"},
            fillcolor="rgba(39, 174, 96, 0.25)",
        )
    )
    if vorig is not None and _spinneweb_heeft_waarde(vorig):
        fig.add_trace(
            go.Scatterpolar(
                r=_spinneweb_dicht(vorig),
                theta=theta,
                fill="none",
                name="Vorige meting",
                line={"color": "#e67e22", "dash": "dash"},
            )
        )
    if klas is not None and _spinneweb_heeft_waarde(klas):
        fig.add_trace(
            go.Scatterpolar(
                r=_spinneweb_dicht(klas),
                theta=theta,
                fill="none",
                name="Klasgemiddelde",
                line={"color": "#2980b9", "dash": "dot"},
            )
        )
    fig.update_layout(
        polar={"radialaxis": {"visible": True, "range": [0, 100]}},
        showlegend=True,
        title=titel,
        height=420,
        margin={"l": 40, "r": 40, "t": 60, "b": 40},
    )
    return fig
