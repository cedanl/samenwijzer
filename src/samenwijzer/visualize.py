"""Visualisaties voor studiedata (Altair + Plotly), thema-bewust per rol.

Elke publieke functie accepteert een optioneel ``rol``-argument
(``"student"``, ``"docent"`` of ``None``); ``None`` valt terug op het docent-
paper-thema. De kleuren, achtergronden en typografie matchen het systeem uit
``styles.py``.

Het groei-spinneweb is een radar (Plotly Scatterpolar) — Altair kent geen
poolcoördinaten.
"""

from __future__ import annotations

from typing import TypedDict

import altair as alt
import pandas as pd
import plotly.graph_objects as go


class _Theme(TypedDict):
    bg: str
    fg: str
    fg_dim: str
    fg_faint: str
    grid: str
    accent: str
    alert: str
    neutral: str
    track: str


_STUDENT_THEME: _Theme = {
    "bg": "#1A1A1F",  # surface op donker
    "fg": "#FFFFFF",
    "fg_dim": "rgba(255,255,255,0.85)",
    "fg_faint": "rgba(255,255,255,0.55)",
    "grid": "rgba(255,255,255,0.08)",
    "accent": "#A8FF60",  # lime — primair / positief
    "alert": "#FF5E3A",  # coral — risico
    "neutral": "#84B8FF",  # zacht blauw voor neutrale categorieën
    "track": "rgba(255,255,255,0.10)",  # achtergrond van een bar/ring
}

_DOCENT_THEME: _Theme = {
    "bg": "#FAF5EC",
    "fg": "#1F1D18",
    "fg_dim": "#6A6354",
    "fg_faint": "#8A8270",
    "grid": "rgba(31,29,24,0.08)",
    "accent": "#6F8265",  # sage — primair / positief
    "alert": "#B04A1A",  # rust — risico
    "neutral": "#4D6044",  # diep sage voor neutrale categorieën
    "track": "rgba(31,29,24,0.10)",
}


def _theme(rol: str | None) -> _Theme:
    """Geef het kleurpalet voor de gegeven rol terug (default = docent)."""
    return _STUDENT_THEME if rol == "student" else _DOCENT_THEME


# ─────────────────────────────────────────────────────────────────────────────
# Altair-helpers
# ─────────────────────────────────────────────────────────────────────────────


def _axis(t: _Theme, *, title: str | None = None, format: str | None = None) -> alt.Axis:
    """Altair-as met thema-kleuren (labels, lijnen, gridlines)."""
    if format is None:
        return alt.Axis(
            labelColor=t["fg_dim"],
            titleColor=t["fg_faint"],
            titleFont="Satoshi, sans-serif",
            labelFont="JetBrains Mono, monospace",
            labelFontSize=10,
            titleFontSize=10,
            titleFontWeight="normal",
            domainColor=t["grid"],
            tickColor=t["grid"],
            gridColor=t["grid"],
            title=title,
        )
    return alt.Axis(
        labelColor=t["fg_dim"],
        titleColor=t["fg_faint"],
        titleFont="Satoshi, sans-serif",
        labelFont="JetBrains Mono, monospace",
        labelFontSize=10,
        titleFontSize=10,
        titleFontWeight="normal",
        domainColor=t["grid"],
        tickColor=t["grid"],
        gridColor=t["grid"],
        title=title,
        format=format,
    )


def _legend(t: _Theme, title: str | None = None) -> alt.Legend:
    return alt.Legend(
        title=title,
        labelColor=t["fg_dim"],
        titleColor=t["fg_faint"],
        labelFont="Satoshi, sans-serif",
        titleFont="JetBrains Mono, monospace",
        labelFontSize=10,
        titleFontSize=10,
        symbolType="circle",
    )


_SCORE_DOMAIN = [0, 100]
_VOORTGANG_DOMAIN = [0, 1]
_MAX_LABEL = 32


def _kort(tekst: str) -> str:
    """Kap een label af op _MAX_LABEL tekens met een ellipsis."""
    return tekst if len(tekst) <= _MAX_LABEL else tekst[:_MAX_LABEL].rstrip() + "…"


# ─────────────────────────────────────────────────────────────────────────────
# Publieke API
# ─────────────────────────────────────────────────────────────────────────────


def voortgang_gauge(
    voortgang: float, label: str = "Voortgang", *, rol: str | None = None
) -> alt.Chart:
    """Horizontale staafgrafiek die voortgang als percentage toont.

    Args:
        voortgang: Waarde tussen 0 en 1.
        label: Omschrijving boven de balk.
        rol: ``"student"``, ``"docent"`` of ``None`` (= docent-default).

    Returns:
        Altair Chart.
    """
    t = _theme(rol)
    pct = round(voortgang * 100)
    if voortgang >= 0.75:
        kleur = t["accent"]
    elif voortgang >= 0.50:
        kleur = t["neutral"]
    else:
        kleur = t["alert"]

    data = pd.DataFrame({"label": [label], "waarde": [pct], "max": [100]})

    achtergrond = (
        alt.Chart(data)
        .mark_bar(color=t["track"], cornerRadiusEnd=4)
        .encode(
            x=alt.X("max:Q", scale=alt.Scale(domain=[0, 100]), axis=_axis(t)),
            y=alt.Y("label:N", axis=_axis(t)),
        )
    )

    voorgrond = (
        alt.Chart(data)
        .mark_bar(color=kleur, cornerRadiusEnd=4)
        .encode(
            x=alt.X("waarde:Q", scale=alt.Scale(domain=[0, 100]), axis=_axis(t, title="%")),
            y=alt.Y("label:N", axis=_axis(t)),
        )
    )

    tekst = (
        alt.Chart(data)
        .mark_text(align="left", dx=4, color=t["fg"], fontWeight="bold")
        .encode(
            x=alt.X("waarde:Q"),
            y=alt.Y("label:N"),
            text=alt.Text("waarde:Q", format=".0f"),
        )
    )

    return (achtergrond + voorgrond + tekst).properties(height=80, background=t["bg"])


def bsa_staaf(bsa_behaald: float, bsa_vereist: float, *, rol: str | None = None) -> alt.Chart:
    """Gestapelde staaf: behaalde vs. nog te behalen BSA-punten.

    Returns:
        Altair Chart.
    """
    t = _theme(rol)
    data = pd.DataFrame(
        {
            "categorie": ["Behaald", "Restant"],
            "punten": [bsa_behaald, max(0, bsa_vereist - bsa_behaald)],
            "kleur": [t["accent"], t["track"]],
        }
    )

    return (
        alt.Chart(data)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "punten:Q",
                stack="zero",
                scale=alt.Scale(domain=[0, bsa_vereist * 1.1]),
                axis=_axis(t, title="Studiepunten"),
            ),
            y=alt.Y("categorie:N", sort=["Behaald", "Restant"], axis=_axis(t)),
            color=alt.Color("kleur:N", scale=None, legend=None),
            tooltip=["categorie:N", "punten:Q"],
        )
        .properties(height=110, background=t["bg"])
    )


def kerntaak_grafiek(kt_df: pd.DataFrame, *, rol: str | None = None) -> alt.Chart:
    """Horizontale staafgrafiek van kerntaakscores (0–100)."""
    t = _theme(rol)
    plot = kt_df.copy()
    plot["label_kort"] = plot["label"].apply(_kort)
    return (
        alt.Chart(plot)
        .mark_bar(color=t["accent"], cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "score:Q",
                scale=alt.Scale(domain=_SCORE_DOMAIN),
                axis=_axis(t, title="Score (0–100)"),
            ),
            y=alt.Y("label_kort:N", sort="-x", axis=_axis(t)),
            tooltip=[
                alt.Tooltip("label:N", title="Kerntaak"),
                alt.Tooltip("score:Q", title="Score"),
            ],
        )
        .properties(height=max(100, len(plot) * 55), background=t["bg"])
    )


def werkproces_grafiek(wp_df: pd.DataFrame, *, rol: str | None = None) -> alt.Chart:
    """Horizontale staafgrafiek van werkprocesscores (0–100)."""
    t = _theme(rol)
    plot = wp_df.copy()
    plot["label_kort"] = plot["label"].apply(_kort)
    return (
        alt.Chart(plot)
        .mark_bar(color=t["neutral"], cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "score:Q",
                scale=alt.Scale(domain=_SCORE_DOMAIN),
                axis=_axis(t, title="Score (0–100)"),
            ),
            y=alt.Y("label_kort:N", sort="-x", axis=_axis(t)),
            tooltip=[
                alt.Tooltip("label:N", title="Werkproces"),
                alt.Tooltip("score:Q", title="Score"),
            ],
        )
        .properties(height=max(140, len(plot) * 42), background=t["bg"])
    )


def groep_voortgang_grafiek(overzicht_df: pd.DataFrame, *, rol: str | None = None) -> alt.Chart:
    """Spreidingsplot: voortgang vs. BSA-percentage per student, risico gehighlight."""
    t = _theme(rol)
    df = overzicht_df.copy()
    df["risico_label"] = df["risico"].map({True: "Risico", False: "Op schema"})

    return (
        alt.Chart(df)
        .mark_circle(size=80, opacity=0.85)
        .encode(
            x=alt.X(
                "voortgang:Q",
                scale=alt.Scale(domain=_VOORTGANG_DOMAIN),
                axis=_axis(t, title="Voortgang", format="%"),
            ),
            y=alt.Y(
                "bsa_percentage:Q",
                scale=alt.Scale(domain=_VOORTGANG_DOMAIN),
                axis=_axis(t, title="BSA behaald", format="%"),
            ),
            color=alt.Color(
                "risico_label:N",
                scale=alt.Scale(
                    domain=["Risico", "Op schema"],
                    range=[t["alert"], t["accent"]],
                ),
                legend=_legend(t, title="Status"),
            ),
            tooltip=[
                "naam:N",
                "opleiding:N",
                "mentor:N",
                "voortgang:Q",
                "bsa_percentage:Q",
            ],
        )
        .properties(height=350, background=t["bg"])
    )


# ─────────────────────────────────────────────────────────────────────────────
# Plotly: spinneweb-radar
# ─────────────────────────────────────────────────────────────────────────────


def _spinneweb_dicht(reeks: list[float | None]) -> list[float]:
    """Vervang None/NaN door 0 en sluit de polygon door het eerste punt te herhalen."""
    schoon = [0.0 if v is None or pd.isna(v) else float(v) for v in reeks]
    return schoon + schoon[:1]


def _spinneweb_heeft_waarde(reeks: list[float | None]) -> bool:
    """True als de reeks minstens één echte (niet-None, niet-NaN) waarde bevat."""
    return any(v is not None and not pd.isna(v) for v in reeks)


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Converteer een #RRGGBB-kleur naar een rgba()-string met de gegeven alpha."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def spinneweb_figuur(
    titel: str,
    labels: list[str],
    huidig: list[float | None],
    vorig: list[float | None] | None = None,
    klas: list[float | None] | None = None,
    *,
    rol: str | None = None,
) -> go.Figure:
    """Radar (Scatterpolar) per kerntaak: huidige + optioneel vorige + klasgemiddelde.

    None/NaN-waarden worden als 0 geplot; een reeks die volledig leeg is krijgt geen lijn.

    Args:
        titel: Titel boven het spinneweb (meestal het kerntaaklabel).
        labels: Werkproces-labels op de assen.
        huidig: Huidige scores per werkproces (0–100).
        vorig: Vorige scores, of None als er geen vorige meting is.
        klas: Klasgemiddelden per werkproces, of None.
        rol: ``"student"``, ``"docent"`` of ``None`` (= docent-default).

    Returns:
        Plotly Figure.
    """
    t = _theme(rol)
    theta = labels + labels[:1]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=_spinneweb_dicht(huidig),
            theta=theta,
            fill="toself",
            name="Huidige meting",
            line={"color": t["accent"], "width": 2},
            fillcolor=_hex_to_rgba(t["accent"], 0.25),
        )
    )
    if vorig is not None and _spinneweb_heeft_waarde(vorig):
        fig.add_trace(
            go.Scatterpolar(
                r=_spinneweb_dicht(vorig),
                theta=theta,
                fill="none",
                name="Vorige meting",
                line={"color": t["alert"], "dash": "dash", "width": 1.5},
            )
        )
    if klas is not None and _spinneweb_heeft_waarde(klas):
        fig.add_trace(
            go.Scatterpolar(
                r=_spinneweb_dicht(klas),
                theta=theta,
                fill="none",
                name="Klasgemiddelde",
                line={"color": t["neutral"], "dash": "dot", "width": 1.5},
            )
        )

    fig.update_layout(
        polar={
            "bgcolor": t["bg"],
            "radialaxis": {
                "visible": True,
                "range": [0, 100],
                "color": t["fg_faint"],
                "gridcolor": t["grid"],
                "linecolor": t["grid"],
                "tickfont": {"family": "JetBrains Mono, monospace", "size": 9},
            },
            "angularaxis": {
                "color": t["fg_dim"],
                "gridcolor": t["grid"],
                "linecolor": t["grid"],
                "tickfont": {"family": "Satoshi, sans-serif", "size": 10},
            },
        },
        paper_bgcolor=t["bg"],
        plot_bgcolor=t["bg"],
        font={"color": t["fg_dim"], "family": "Satoshi, sans-serif"},
        title={
            "text": titel,
            "font": {
                "color": t["fg"],
                "family": "Cabinet Grotesk, sans-serif",
                "size": 16,
            },
        },
        legend={
            "font": {"color": t["fg_dim"], "family": "Satoshi, sans-serif", "size": 11},
            "bgcolor": "rgba(0,0,0,0)",
        },
        showlegend=True,
        height=420,
        margin={"l": 40, "r": 40, "t": 60, "b": 40},
    )
    return fig
